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

# Der Client wird PRO TEST gebaut, nicht beim Import: `/healthz` liest die
# Engine beim Aufruf aus `diakronos_app.db`, und `patched_db` setzt sie erst
# im Test auf die SQLite-Test-Engine. Ein Client auf Modulebene waere derselbe
# Endpunkt, aber die Reihenfolge (Import vor Fixture) macht den Unterschied
# nicht sichtbar — deshalb hier explizit je Test.


def test_healthz_returns_200():
    resp = TestClient(app).get("/healthz")
    assert resp.status_code == 200


def test_healthz_shape():
    body = TestClient(app).get("/healthz").json()
    # ABN-3: `version` ist neu. ABN-3b/N9: `git` gehoert NICHT hierher —
    # /healthz ist oeffentlich, der Hash nennt den genauen Quellstand. Er
    # steht im Boot-Objekt, aber nur fuer Administratoren. Ein weiteres Feld
    # hier auftauchen zu lassen, waere eine Aenderung am Vertrag.
    assert set(body) == {"status", "db", "redis", "version"}
    for key in ("db", "redis"):
        assert isinstance(body[key], bool)
    assert isinstance(body["version"], str) and body["version"]
    assert "git" not in body


def test_healthz_all_dependencies_up(patched_db, fake_redis, monkeypatch):
    """BEIDE Abhaengigkeiten ECHT erreichbar — gegen die Test-Engine/den Stub.

    Der Test lief bisher ohne Fixtures und fragte damit die im Container
    eingestellte Betriebs-URL ab; ohne DB-Host kam `{'status': 'degraded',
    'db': False, 'redis': True}` heraus und der Fehlschlag galt als “bekannt”.

    Geprueft wird weiter der echte Weg, kein Attrappen-Endpunkt:
    `main._check_db()` oeffnet `diakronos_app.db.engine` und faehrt
    `SELECT 1` — genau die Engine, die `patched_db` auf die In-Memory-SQLite
    umhaengt. `_check_redis()` geht ueber `Redis.from_url(settings.redis_url)`;
    `fake_redis` haengt den Stub an die Sitzungs-Schicht, nicht an diesen
    Pfad, deshalb wird hier `Redis.from_url` der `main`-Schicht auf einen
    Stub mit `ping()` gebogen. Faellt eine der beiden Pruefungen aus, meldet
    der Endpunkt wieder `degraded` — der Test kann also weiterhin scheitern.
    """

    class _PingStub:
        def ping(self):
            return True

    from diakronos_app import main as main_mod

    monkeypatch.setattr(main_mod.Redis, "from_url", lambda *a, **kw: _PingStub())

    body = TestClient(app).get("/healthz").json()
    # ABN-3: `version`/`git` gehoeren jetzt dazu (siehe test_healthz_shape);
    # geprueft werden weiter die drei Zustandswerte.
    assert {k: body[k] for k in ("status", "db", "redis")} == {
        "status": "ok", "db": True, "redis": True,
    }, body


