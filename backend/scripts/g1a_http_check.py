"""G1a real HTTP smoke against disposable PostgreSQL + private Redis only.

Run inside the isolated review image, with its default entrypoint overridden:
G1A_DISPOSABLE_DB=1 DATABASE_URL=... PYTHONPATH=src:tests python scripts/g1a_http_check.py
No production credentials; no Google calls; created data removed in finally.
"""
import base64
import os
from pathlib import Path
import socket
import subprocess
import time

import httpx
from argon2 import PasswordHasher
from sqlalchemy import create_engine, text

from redis_testdb import privates_redis

assert os.environ.get("G1A_DISPOSABLE_DB") == "1"
assert "g1a-postgres" in os.environ["DATABASE_URL"]
engine = create_engine(os.environ["DATABASE_URL"])
fixture = Path("tests/fixtures/google_import.ics").read_bytes()
path = "/api/method/diakronos.kronos.api.google_import."
calendar = None
with engine.begin() as db:
    assert db.scalar(text('SELECT count(*) FROM "user"')) == 0
    db.execute(text('''INSERT INTO "user" (name, email, full_name, enabled, password_hash)
        VALUES ('Administrator', 'Administrator', 'Test Admin', true, :hash)'''),
        {"hash": PasswordHasher().hash("g1a-test-password")})
try:
    with privates_redis() as redis_url:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        env = {**os.environ, "REDIS_URL": redis_url}
        process = subprocess.Popen([
            "uvicorn", "diakronos_app.main:app", "--host", "127.0.0.1",
            "--port", str(port), "--no-access-log", "--log-level", "warning",
        ], env=env)
        try:
            with httpx.Client(base_url=f"http://127.0.0.1:{port}") as client:
                deadline = time.monotonic() + 20
                while True:
                    try:
                        health = client.get("/healthz")
                        if health.status_code == 200:
                            assert health.json()["status"] == "ok"
                            break
                    except httpx.ConnectError:
                        pass
                    assert time.monotonic() < deadline, "App readiness timeout"
                    time.sleep(.1)
                for fn in ["get_credentials_status", "save_credentials", "upload_ical"]:
                    response = client.get(path + fn)
                    assert response.status_code == 403
                    print(f"Original path {fn}: Guest HTTP 403")
                response = client.post("/api/method/diakronos_app.api.auth.login",
                                       json={"usr": "Administrator", "pwd": "g1a-test-password"})
                assert response.status_code == 200
                client.headers["X-Frappe-CSRF-Token"] = response.json()["csrf_token"]
                assert client.get(path + "get_credentials_status").status_code == 200
                response = client.post(path + "save_credentials", json={
                    "client_id": "test-client", "client_secret": "test-secret",
                })
                assert response.status_code == 200
                assert "test-secret" not in response.text
                response = client.post(path + "upload_ical", json={
                    "file_content_b64": base64.b64encode(fixture).decode(),
                    "calendar_name_new": "G1a disposable HTTP check",
                })
                assert response.status_code == 200, response.text
                result = response.json()["message"]
                calendar = result["kalender"]
                assert result["imported"] == 5 and result["skipped"] == 0
                response = client.get("/api/method/diakronos.kronos.api.calendar_get.get_calendar_events",
                                      params={"start_date": "2026-10-01", "end_date": "2026-10-31"})
                assert response.status_code == 200
                events = response.json()["message"]
                assert sorted(e["start"] for e in events if e["title"] == "Chorprobe") == [
                    "2026-10-05 18:00:00", "2026-10-12 18:00:00", "2026-10-19 18:00:00",
                ]
                assert next(e["start"] for e in events if e["title"] == "Frühstück, Grüße") == "2026-10-01 11:00:00"
                print("Calendar read: Berlin 18:00 preserved; UTC 09:00 -> Berlin 11:00")
                with engine.connect() as db:
                    assert db.scalar(text("SELECT count(*) FROM element WHERE element_calendar=:cal"),
                                     {"cal": calendar}) == 5
                response = client.post(path + "upload_ical", json={
                    "file_content_b64": base64.b64encode(fixture).decode(),
                    "create_new": "false", "target_kalender": calendar,
                })
                assert response.status_code == 200
                assert response.json()["message"]["skipped"] == 5
                print("Original paths: Administrator HTTP 200; real ICS -> 5 rows; reimport -> 5 skipped")
        finally:
            process.terminate()
            process.wait(timeout=10)
finally:
    with engine.begin() as db:
        # These records belong solely to this disposable acceptance database.
        db.execute(text("DELETE FROM element"))
        db.execute(text("DELETE FROM user_role"))
        db.execute(text("DELETE FROM kalender"))
        db.execute(text("DELETE FROM google_kalender_einstellungen"))
        db.execute(text('DELETE FROM "user"'))
        assert db.scalar(text("SELECT count(*) FROM mitglied")) == 0
        assert db.scalar(text('SELECT count(*) FROM "user"')) == 0
    print("Disposable HTTP check: test records removed; mitglied=0, user=0")
