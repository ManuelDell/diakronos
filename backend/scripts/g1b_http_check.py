"""G1b acceptance: disposable PostgreSQL, private Redis, real HTTP/RQ/Socket.IO.

Run with entrypoint overridden, PYTHONPATH=src:tests, G1B_DISPOSABLE_DB=1.
All Google traffic is handled by MockTransport in separate app/worker processes.
"""
import json
import os
from pathlib import Path
import socket
import subprocess
import threading
import time
from urllib.parse import parse_qs, urlsplit

import httpx
import socketio
from argon2 import PasswordHasher
from sqlalchemy import text

from redis_testdb import privates_redis

assert os.environ.get("G1B_DISPOSABLE_DB") == "1"
assert "g1b-postgres" in os.environ["DATABASE_URL"]
from diakronos_app import db as database
from diakronos_app.models.core import Role, User
from diakronos_app.models.diakonos import DashboardWidget

path = "/api/method/diakronos.kronos.api.google_import."
with database.SessionLocal.begin() as db:
    assert db.scalar(text('SELECT count(*) FROM "user"')) == 0
    db.add(User(name="Administrator", email="Administrator", full_name="Disposable Admin", enabled=True,
                password_hash=PasswordHasher().hash("g1b-test-password")))
try:
    with privates_redis() as redis_url:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        env = {**os.environ, "REDIS_URL": redis_url}
        process = subprocess.Popen(["python", "-m", "g1b_fake_google", "app", str(port)], env=env)
        receiver = socketio.Client()
        got = threading.Event()
        messages = []
        @receiver.on("gcal_import_progress")
        def receive(data):
            messages.append(data)
            if data.get("status") == "done":
                got.set()
        try:
            with httpx.Client(base_url=f"http://127.0.0.1:{port}") as client:
                deadline = time.monotonic() + 20
                while True:
                    try:
                        if client.get("/healthz").json().get("status") == "ok":
                            break
                    except httpx.ConnectError:
                        pass
                    assert time.monotonic() < deadline
                    time.sleep(.05)
                endpoints = ["get_credentials_status", "save_credentials", "upload_ical", "get_oauth_url",
                             "exchange_code", "get_google_calendars", "start_import"]
                for fn in endpoints:
                    assert client.get(path + fn).status_code == 403
                assert client.get("/google-calendar-callback").status_code == 403
                login = client.post("/api/method/diakronos_app.api.auth.login",
                                    json={"usr": "Administrator", "pwd": "g1b-test-password"})
                assert login.status_code == 200
                client.headers["X-Frappe-CSRF-Token"] = login.json()["csrf_token"]
                assert client.post(path + "save_credentials", json={"client_id": "fake-client", "client_secret": "fake-secret"}).status_code == 200
                response = client.get(path + "get_oauth_url")
                assert response.status_code == 200
                state = parse_qs(urlsplit(response.json()["message"]["url"]).query)["state"][0]
                response = client.get("/google-calendar-callback", params={"code": "fake-code", "state": state})
                assert response.status_code == 303
                assert response.headers["location"] == "/diakonos?gcal_step=2#/kalender/import"
                assert client.post(path + "exchange_code", json={"code": "fake-code", "state": state}).status_code == 417
                calendars = client.get(path + "get_google_calendars")
                assert calendars.status_code == 200
                assert [c["id"] for c in calendars.json()["message"]] == ["first", "second"]
                receiver.connect(f"http://127.0.0.1:{port}", headers={"Cookie": "sid=" + client.cookies.get("sid")}, transports=["polling"])
                mapping = {"google_id": "first", "google_name": "G1b disposable import", "create_new": True}
                for run in range(2):
                    got.clear()
                    response = client.post(path + "start_import", json={"mappings_json": json.dumps([mapping])})
                    assert response.status_code == 200 and response.json()["message"]["queued"]
                    subprocess.run(["python", "-m", "g1b_fake_google", "worker"], env=env, check=True)
                    assert got.wait(10), "Real RQ worker progress not received"
                    result = messages[-1]
                    assert "error" not in result, result
                    assert result["total_imported"] == (2 if run == 0 else 0)
                    assert result["total_skipped"] == (1 if run == 0 else 3)
                    mapping.update(create_new=False, target_kalender=result["calendars"][0]["frappe_kalender"])
                with database.engine.connect() as db:
                    assert db.scalar(text("SELECT count(*) FROM element")) == 2
                response = client.get("/api/method/diakronos.kronos.api.calendar_get.get_calendar_events",
                                      params={"start_date": "2026-10-01", "end_date": "2026-10-04"})
                assert response.status_code == 200
                events = response.json()["message"]
                assert next(e["start"] for e in events if e["title"] == "Fake timed event") == "2026-10-01 11:00:00"
                assert any(m["status"] == "starting" for m in messages)
                assert any(m["status"] == "importing" for m in messages)
                print("G1b real HTTP: 7 original paths Guest 403; OAuth callback 303; replay rejected; paged calendars 200")
                print("G1b real RQ+Socket.IO: two separate worker processes, 2 imports / 1 cancelled; reimport 0 / 3 skipped; local calendar read verified")
        finally:
            receiver.disconnect()
            process.terminate()
            process.wait(10)
finally:
    with database.engine.begin() as db:
        for table in ["element", "user_role", "kalender", "google_kalender_einstellungen", '"user"']:
            db.execute(text("DELETE FROM " + table))
        assert db.scalar(text("SELECT count(*) FROM mitglied")) == 0
        assert db.scalar(text('SELECT count(*) FROM "user"')) == 0
    print("Disposable records removed; mitglied=0 user=0")

# Seed the ORIGINAL inventory needed by unpatched full-suite collection, not live data.
fixture = Path("/reference/diakronos/diakonos/fixtures/dashboard_widget.json")
if fixture.exists():
    with database.SessionLocal.begin() as db:
        for row in json.loads(fixture.read_text()):
            role = row.get("required_role")
            if role and db.get(Role, role) is None:
                db.add(Role(name=role))
                db.flush()
            from diakronos_app.frappe_compat.api_helpers import _coerce
            fields = _coerce("Dashboard Widget", {k: v for k, v in row.items()
                     if k in DashboardWidget.__table__.columns.keys()})
            db.merge(DashboardWidget(name=row["widget_id"], **fields))
    print("Original Dashboard Widget fixture seeded for full-suite inventory checks")
