"""SEC-4 — Security-Header auf allen Antworten, API-Doku abschaltbar.

Befund (Pentest dev.ecg-hn.de, Bericht 2 und 8):
  * Antworten — auch `/api/*` — tragen kein HSTS, keine CSP, kein
    X-Frame-Options, kein X-Content-Type-Options und keine Referrer-Policy.
  * `/docs`, `/redoc` und `/openapi.json` sind ohne Anmeldung erreichbar (200).

Die Tests hier pruefen beides an der laufenden App (`TestClient`), nicht an
einer Hilfsfunktion: genau die Antwort, die der Browser bekommt, muss die
Kopfzeilen tragen. Sie laufen ohne Netz — DB und Redis sind gepatcht
(`patched_db`, `fake_redis`), also weder Betriebs-DB noch Betriebs-Redis.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from diakronos_app.main import app

# ── S1: die Kopfzeilen, die auf JEDER Antwort stehen muessen ───────────────

HSTS = "max-age=31536000; includeSubDomains"
CSP_PRAEFIX = "default-src 'none'"


@pytest.fixture()
def client(patched_db, fake_redis):
    """Client gegen die App; `patched_db`/`fake_redis` halten den Betrieb draussen."""
    patched_db()
    with TestClient(app) as c:
        yield c


def _assert_sicherheits_header(resp, pfad: str) -> None:
    assert resp.headers.get("strict-transport-security") == HSTS, (
        f"{pfad}: HSTS fehlt oder weicht ab: {resp.headers.get('strict-transport-security')!r}"
    )
    assert resp.headers.get("x-frame-options") == "DENY", pfad
    assert resp.headers.get("x-content-type-options") == "nosniff", pfad
    assert resp.headers.get("referrer-policy") == "no-referrer", pfad
    csp = resp.headers.get("content-security-policy")
    assert csp, f"{pfad}: Content-Security-Policy fehlt"
    assert csp.startswith(CSP_PRAEFIX), f"{pfad}: CSP zu weit: {csp!r}"
    # Clickjacking-Schutz steht doppelt (alte Browser kennen nur den Header).
    assert "frame-ancestors 'none'" in csp, f"{pfad}: CSP ohne frame-ancestors: {csp!r}"


def test_header_auf_der_wurzel(client):
    """`/` (302 in die SPA) traegt die Kopfzeilen."""
    resp = client.get("/", follow_redirects=False)
    _assert_sicherheits_header(resp, "/")


def test_header_auf_spa_seite(client):
    """Die ausgelieferte Seite (`/diakonos`) traegt die Kopfzeilen."""
    _assert_sicherheits_header(client.get("/diakonos"), "/diakonos")


def test_header_auf_api_antwort(client):
    """`/api/resource/<doctype>` — die JSON-Antwort aus dem Pentest-Befund."""
    resp = client.get("/api/resource/Mitglied")
    assert resp.status_code != 500, resp.text
    _assert_sicherheits_header(resp, "/api/resource/Mitglied")


def test_header_auf_api_fehlerantwort(client):
    """Auch Fehlerantworten (4xx) tragen die Kopfzeilen — Middleware, kein Dekorator."""
    resp = client.get("/api/method/gibt.es.nicht")
    assert resp.status_code == 404, resp.text
    _assert_sicherheits_header(resp, "/api/method/gibt.es.nicht")


def test_header_auf_healthz(client):
    """Der Healthcheck (Betrieb ueberwacht ihn) traegt die Kopfzeilen."""
    _assert_sicherheits_header(client.get("/healthz"), "/healthz")


def test_header_werden_nicht_doppelt_gesetzt(client):
    """Jede Kopfzeile genau EINMAL — sonst entscheidet der Proxy ueber den Wert.

    Beleg fuer die Forderung „Doppelsetzung vermeiden": die vorhandenen
    Stellen (`/files`, `/public/...`, Anmeldemaske) setzen `nosniff` bzw. CSP
    selbst; die Middleware darf sie deshalb nicht ein zweites Mal anhaengen.
    """
    resp = client.get("/api/resource/Mitglied")
    rohe = resp.headers.get_list("x-content-type-options")
    assert rohe == ["nosniff"], rohe
    assert len(resp.headers.get_list("content-security-policy")) == 1
    assert len(resp.headers.get_list("x-frame-options")) == 1


def test_vorhandene_csp_wird_nicht_ueberschrieben():
    """Die engere CSP einer Datei-Auslieferung bleibt erhalten.

    `/public/registrierung/<token>/bild/<rolle>` liefert Bilder mit
    `default-src 'none'; sandbox`. Eine pauschale Kopfzeile darf das nicht
    aufweichen — sonst zeigt ein Bild ploetzlich mehr Rechte als vorgesehen.
    """
    from diakronos_app.sec_header import sicherheits_header_setzen

    class _Antwort:
        def __init__(self):
            self.headers = {"Content-Security-Policy": "default-src 'none'; sandbox"}

    antwort = _Antwort()
    sicherheits_header_setzen(antwort)
    assert antwort.headers["Content-Security-Policy"] == "default-src 'none'; sandbox"
    # Die uebrigen Kopfzeilen kommen trotzdem dazu.
    assert antwort.headers["X-Frame-Options"] == "DENY"


# ── S2: API-Doku nur mit ausdruecklichem Schalter ─────────────────────────


def test_doku_ist_ohne_schalter_abgeschaltet(client):
    """`/docs`, `/redoc` und `/openapi.json` sind ohne Debug-Flag nicht da."""
    for pfad in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(pfad).status_code == 404, pfad


def test_schalter_ist_standardmaessig_aus():
    """`SEC_DOKU_OEFFENTLICH` ist im Code AUS — eine Installation ohne Schalter zeigt keine Doku."""
    from diakronos_app.settings import Settings

    assert Settings.model_fields["sec_doku_oeffentlich"].default is False


def test_doku_mit_schalter_erreichbar():
    """Mit gesetztem Schalter ist die Doku wieder da (Dev/Debug).

    Geprueft ueber denselben Baustein, den `main.py` benutzt
    (`erstelle_app`) mit ausdruecklich andere Einstellungen: `docs_url` wird
    beim Anlegen von `FastAPI(...)` ausgewertet, ein nachtraegliches Umstellen
    waere eine andere App.
    """
    from types import SimpleNamespace

    from diakronos_app.main import erstelle_app

    an = SimpleNamespace(sec_doku_oeffentlich=True, devmode_enabled=False, log_level="INFO")
    with TestClient(erstelle_app(an)) as c:
        assert c.get("/openapi.json").status_code == 200
        assert c.get("/docs").status_code == 200
        assert c.get("/redoc").status_code == 200
        # Auch die Doku-Antworten tragen die Kopfzeilen (S1 gilt immer).
        _assert_sicherheits_header(c.get("/docs"), "/docs")


def test_doku_bleibt_aus_wenn_schalter_falsch_ist():
    """Gegenprobe zur vorigen Pruefung: derselbe Weg, Schalter aus -> 404."""
    from types import SimpleNamespace

    from diakronos_app.main import erstelle_app

    aus = SimpleNamespace(sec_doku_oeffentlich=False, devmode_enabled=False, log_level="INFO")
    with TestClient(erstelle_app(aus)) as c:
        for pfad in ("/docs", "/redoc", "/openapi.json"):
            assert c.get(pfad).status_code == 404, pfad
