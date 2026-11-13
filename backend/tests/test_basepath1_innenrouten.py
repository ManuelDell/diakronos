"""BASEPATH-1 — Innenrouten unter dem Betriebs-Praefix (``DIAKRONOS_BASE_PATH``).

BEFUND, DEN DIESE DATEI BELEGT
------------------------------
Nebenbefund aus UI-R6b (Worker-Bericht t_eeb44392): laeuft die App mit
``DIAKRONOS_BASE_PATH`` (z. B. ``/diakonos``), liefert ``/diakonos/diakronos``
einen 404. Vermutete Ursache: Starlette-``Mount`` setzt nur ``root_path`` und
laesst ``scope["path"]`` unveraendert — die Innenrouten der App matchen dann
nicht mehr.

GEPRUEFT WIRD DIE WIRKUNG, NICHT DIE URSACHE
--------------------------------------------
Vier Adressen aus vier verschiedenen Routen-Baeumen, jeweils MIT Praefix und
(dieselben Pfade) OHNE Praefix als Gegenprobe:

  * ``/{praefix}/healthz``               — Endpunkt der FastAPI-App
  * ``/{praefix}/diakonos``              — SPA-Auslieferung (``mount_spa``)
  * ``/{praefix}/api/method/ping``       — oeffentliche Methode des Compat-Routers
  * ``/{praefix}/gestaltung.css``        — feste Datei (Build-Artefakt)

Die SPA-Pruefung laeuft zusaetzlich mit SITZUNG: ohne Sitzung liefert die SPA
bewusst die Anmeldemaske (A1b2-rest), das sagt nichts ueber die Route.

Der Test treibt die App IN-PROCESS ueber den TestClient (kein Stack, kein
Netz) und raeumt den Prozess-Praefix danach wieder ab — er ist eine
Prozessgroesse (``base_path.aktiver_praefix``).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from diakronos_app import base_path
from diakronos_app.frappe_compat import sitzungen
from diakronos_app.main import erstelle_app
from diakronos_app.models.core import User
from diakronos_app.settings import settings as echte_settings

PRAEFIX = "/diakonos"


# ── Hilfen ──────────────────────────────────────────────────────────────────

def _app_mit(monkeypatch, praefix: str):
    monkeypatch.setattr(echte_settings, "diakronos_base_path", praefix)
    return erstelle_app()


@pytest.fixture()
def app_praefix(monkeypatch):
    """Anwendung mit Betriebs-Praefix; danach wird der Praefix zurueckgesetzt."""
    try:
        yield _app_mit(monkeypatch, PRAEFIX)
    finally:
        base_path.setze_praefix("")


@pytest.fixture()
def app_ohne(monkeypatch):
    """Dieselbe Anwendung OHNE Praefix — die Gegenprobe."""
    monkeypatch.setattr(echte_settings, "diakronos_base_path", "")
    base_path.setze_praefix("")
    try:
        yield erstelle_app()
    finally:
        base_path.setze_praefix("")


def _benutzer_und_sitzung(patched_db, name: str = "Administrator") -> tuple[str, str]:
    """Legt die ``user``-Zeile an (B1) und gibt ``(sid, csrf)`` zurueck."""
    fremd = patched_db()
    if fremd.get(User, name) is None:
        fremd.add(User(name=name, email=name, full_name=name, enabled=True))
        fremd.commit()
    fremd.close()
    return sitzungen.anlegen(name)


# ── Die vier Routen-Baeume ──────────────────────────────────────────────────

def test_healthz_unter_praefix(app_praefix, patched_db, fake_redis):
    """Endpunkt der FastAPI-App: ``/healthz`` liegt unter dem Praefix."""
    with TestClient(app_praefix) as c:
        r = c.get(f"{PRAEFIX}/healthz")
    assert r.status_code == 200, (r.status_code, r.text[:200])
    assert r.json()["status"] in {"ok", "degraded"}


def test_healthz_gegenprobe_ohne_praefix(app_ohne, patched_db, fake_redis):
    """Gegenprobe: ohne Praefix liegt ``/healthz`` an der Wurzel."""
    with TestClient(app_ohne) as c:
        r = c.get("/healthz")
    assert r.status_code == 200, (r.status_code, r.text[:200])


def test_spa_unter_praefix(app_praefix, patched_db, fake_redis):
    """SPA-Auslieferung: ``/{praefix}/diakonos`` liefert die SPA (mit Sitzung)."""
    sid, csrf = _benutzer_und_sitzung(patched_db)
    with TestClient(app_praefix) as c:
        r = c.get(f"{PRAEFIX}/diakonos", cookies={"sid": sid},
                  headers={"X-Frappe-CSRF-Token": csrf})
    assert r.status_code == 200, (r.status_code, r.text[:300])
    assert "window.__DIakonosBOOT" in r.text


def test_spa_gegenprobe_ohne_praefix(app_ohne, patched_db, fake_redis):
    sid, csrf = _benutzer_und_sitzung(patched_db)
    with TestClient(app_ohne) as c:
        r = c.get("/diakonos", cookies={"sid": sid},
                  headers={"X-Frappe-CSRF-Token": csrf})
    assert r.status_code == 200, (r.status_code, r.text[:300])
    assert "window.__DIakonosBOOT" in r.text


def test_api_method_unter_praefix(app_praefix, patched_db, fake_redis):
    """Oeffentliche Methode des Compat-Routers: ``/api/method/ping``."""
    sid, csrf = _benutzer_und_sitzung(patched_db)
    with TestClient(app_praefix) as c:
        r = c.get(f"{PRAEFIX}/api/method/ping", cookies={"sid": sid},
                  headers={"X-Frappe-CSRF-Token": csrf})
    assert r.status_code == 200, (r.status_code, r.text[:300])
    assert r.json().get("message") == "pong"


def test_api_method_gegenprobe_ohne_praefix(app_ohne, patched_db, fake_redis):
    sid, csrf = _benutzer_und_sitzung(patched_db)
    with TestClient(app_ohne) as c:
        r = c.get("/api/method/ping", cookies={"sid": sid},
                  headers={"X-Frappe-CSRF-Token": csrf})
    assert r.status_code == 200, (r.status_code, r.text[:300])
    assert r.json().get("message") == "pong"


def test_statische_datei_unter_praefix(app_praefix, patched_db):
    """Feste Datei: ``/gestaltung.css`` (Build-Artefakt, oeffentlich)."""
    with TestClient(app_praefix) as c:
        r = c.get(f"{PRAEFIX}/gestaltung.css")
    assert r.status_code == 200, (r.status_code, r.text[:200])


def test_statische_datei_gegenprobe_ohne_praefix(app_ohne, patched_db):
    with TestClient(app_ohne) as c:
        r = c.get("/gestaltung.css")
    assert r.status_code == 200, (r.status_code, r.text[:200])


# ── Die Gegenrichtung: ohne Praefix gibt es die praefigierten Pfade nicht ──

def test_praefigierte_pfade_ohne_praefix_404(app_ohne, patched_db, fake_redis):
    """Gegenprobe zu allen vier Baeumen — mit Praefix stehen sie NUR dort.

    ACHTUNG: ``/diakonos/diakronos`` ist ohne Praefix KEIN Beweis — das ist
    die SPA-Route ``/diakonos/{full_path:path}`` mit ``full_path="diakonos"``
    und liefert erwartungsgemaess 200. Geprueft wird hier deshalb ein
    Praefix-Segment, das die SPA nicht als Seite annimmt.
    """
    with TestClient(app_ohne) as c:
        assert c.get(f"{PRAEFIX}/healthz").status_code == 404
        assert c.get(f"{PRAEFIX}/api/method/ping").status_code == 404
        # Mit anderem Praefix-Namen (Adler-32 des Pfades trifft das
        # SPA-Routing nicht) — die Routen liegen NUR unter dem echten Praefix.
        # Die SPA-Route `/diakonos/{full_path:path}` nimmt jeden Pfad als Seite
        # an; `/{praefix}/gestaltung.css` liefert dort die SPA (200) und ist
        # deshalb KEIN Beweis fuer „Route weg".
        assert c.get("/betrieb/healthz").status_code == 404
        assert c.get("/betrieb/diakonos").status_code == 404
        assert c.get("/betrieb/gestaltung.css").status_code == 404
