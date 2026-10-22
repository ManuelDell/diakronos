"""Tests fuer den /healthz-Endpunkt.

Der Test laeuft INNERHALB des app-Containers (Makefile-Target `test`), wo db
und redis per Compose-Netz erreichbar sind. Die harten Werte (db/redis == true)
werden geprueft, damit ein "gruener" Healthcheck nicht durch Netzausfall
entstehen kann.

Kein Radicale (P8): der Dienst wurde bewusst verworfen, CalDAV ist im Backend
portiert — ein zweiter Terminspeicher waere eine zweite Quelle der Wahrheit
gewesen (s. `diakronos_app/caldav/__init__.py`).
"""

from fastapi.testclient import TestClient

from diakronos_app.main import app

client = TestClient(app)


def test_healthz_returns_200():
    resp = client.get("/healthz")
    assert resp.status_code == 200


def test_healthz_shape():
    body = client.get("/healthz").json()
    assert set(body) == {"status", "db", "redis"}
    for key in ("db", "redis"):
        assert isinstance(body[key], bool)


def test_healthz_all_dependencies_up():
    body = client.get("/healthz").json()
    assert body["db"] is True, f"db nicht erreichbar: {body}"
    assert body["redis"] is True, f"redis nicht erreichbar: {body}"
    assert body["status"] == "ok"
