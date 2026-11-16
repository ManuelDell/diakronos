"""ROUTER-ALIAS-c — Abnahme am ECHTEN Router (TestClient, angemeldet).

Die Waechter aus ROUTER-ALIAS-b fragten die Bausteine
(`registriere_originalpfad`, `_ist_eigener_pfad`, `lookup`) — nicht den Weg,
den ein Request nimmt. Genau daran gingen alle vier Befunde dieser Karte
vorbei:

  * `frappe.sessions.get_csrf_token` galt als „loest auf“, der Router
    antwortete aber 404 (`exc_type == "Error"`, nicht `"NotFound"` — der
    alte Test prueft den falschen Wert).
  * `_preflight` importierte je Fehlgriff einen Modulnamen aus der Anfrage.
  * Der Login-Alias schrieb sich in das Register (300 Anfragen = 300
    Eintraege).
  * Kurzformen (`insert`, `api.insert`, `sitzung_status`, …) loesten auf eine
    beliebige gleichnamige Funktion auf.

Hier laeuft deshalb JEDE Zusage durch `POST/GET /api/method/<pfad>` mit
angemeldeter Sitzung. „Aufloest“ heisst: Status ist NICHT 404 (die
Fachfunktion darf fachlich ablehnen — 401/403/405/417 —, aber der Pfad
existiert).
"""

from __future__ import annotations

import re
import sys

import pytest

from diakronos_app.models.core import User

USR = "ra-c@example.org"
PWD = "synthetisch-ra-c"  # nur fuer diese Tests

#: Was ein 404 des Routers traegt (`router._nicht_gefunden`).
_NICHT_GEFUNDEN = "Methode nicht gefunden"


# ── Hilfen ────────────────────────────────────────────────────────────────


def _lege_benutzer(session_factory) -> None:
    from diakronos_app.frappe_compat.passwoerter import neuer_hash

    sess = session_factory()
    try:
        sess.add(
            User(
                name=USR,
                email=USR,
                full_name=USR,
                enabled=True,
                password_hash=neuer_hash(PWD),
            )
        )
        sess.commit()
    finally:
        sess.close()


def _angemeldeter_client(app, session_factory):
    """TestClient mit gueltiger Sitzung (Cookie-Jar, `follow_redirects=False`)."""
    from fastapi.testclient import TestClient

    _lege_benutzer(session_factory)
    c = TestClient(app, base_url="http://testserver")
    c.__enter__()
    antwort = c.post(
        "/api/method/login",
        json={"usr": USR, "pwd": PWD},
        headers={"Origin": "http://testserver", "Accept": "application/json"},
    )
    assert antwort.status_code == 200, antwort.text
    return c


def _register_vollstaendig() -> None:
    """Laedt die App — und den Dev-Modus, wenn er EINGESCHALTET ist.

    ROUTER-ALIAS-e: Hier stand `devmodus_api.registriere()` OHNE `app`. Die
    Funktion verlangt `app` (TypeError), der von einem stillen
    `except Exception: pass` verschluckt wurde — die Dev-Modus-Bahn wurde
    also nie registriert. Jetzt gilt die Regel des Betriebs
    (`main.py:241`): `registriere(app)` MIT der App, ohne stilles `except`.

    Der Dev-Modus ist im Testlauf AUS (`DEVMODE_ENABLED` nicht gesetzt,
    siehe `devmodus/einstellungen.py`); `registriere` meldet das ueber
    `False` und importiert nichts — genau wie im Betrieb.
    """
    from diakronos_app.devmodus import api as devmodus_api
    from diakronos_app.main import app

    devmodus_api.registriere(app)

def _frontend_pfade() -> list[str]:
    """Alle SPA-Methodenpfade — dieselbe Quelle wie der Waechter aus ROUTER-ALIAS-b."""
    sys.path.insert(0, __file__.rsplit("/", 1)[0])
    import test_router_alias_waechter as W

    return W._frontend_pfade()


def _ist_modulebene(pfad: str) -> bool:
    import test_router_alias_waechter as W

    return W._ist_modulebene(pfad)


def _kein_404(antwort) -> bool:
    if antwort.status_code != 404:
        return True
    return antwort.json().get("message") != _NICHT_GEFUNDEN


# ── MUSS 1: jeder SPA-Pfad durch den echten Router ─────────────────────────


def test_alle_spa_pfade_antworten_im_echten_router_ohne_404(client, patched_db, engine, session_factory):
    """Jeder Pfad aus `frontend/src` erreicht im echten Ablauf eine Fachfunktion.

    Angemeldet (die SPA ruft nie als Gast), GET und POST. Ohne diese Pruefung
    blieb `frappe.sessions.get_csrf_token` unbemerkt ein 404: die alten
    Waechter fragten die Bausteine statt des Routers.
    """
    _register_vollstaendig()
    pfade = [p for p in _frontend_pfade() if not _ist_modulebene(p) and p != "diakronos.x.y"]
    assert len(pfade) >= 100, f"zu wenige Frontend-Pfade ({len(pfade)}) — Scanner pruefen"

    with _angemeldeter_client(__import__("diakronos_app.main", fromlist=["app"]).app, session_factory) as c:
        tot: list[str] = []
        for pfad in pfade:
            for methode in ("get", "post"):
                antwort = (
                    c.get(f"/api/method/{pfad}", follow_redirects=False)
                    if methode == "get"
                    else c.post(f"/api/method/{pfad}", json={}, follow_redirects=False)
                )
                if not _kein_404(antwort):
                    tot.append(f"{methode.upper()} {pfad}")
                    break
    assert tot == [], f"{len(tot)} SPA-Pfad(e) sind im Router 404:\n" + "\n".join(tot)


def test_csrf_token_kernpfad_antwortet_ohne_404(client):
    """`gastinhalt/App.vue:217` ruft genau diesen Pfad — er muss antworten.

    Ohne gueltige Sitzung ist die ehrliche Antwort 401 `SessionExpired` (kein
    Token erfinden) — entscheidend ist, dass der PFAD aufloest und die
    Antwort aus der Funktion stammt.
    """
    _register_vollstaendig()
    ohne = client.post("/api/method/frappe.sessions.get_csrf_token", json={})
    assert _kein_404(ohne), ohne.text
    assert ohne.status_code in (200, 401), ohne.text
    if ohne.status_code == 401:
        assert ohne.json()["exc_type"] == "SessionExpired", ohne.text
    else:
        assert ohne.json()["message"]["csrf_token"], ohne.text


# ── MUSS 2: kein Import und kein CPU-Verstaerker je Fehlgriff ──────────────


@pytest.mark.parametrize("methode", ["get", "post", "options"])
@pytest.mark.parametrize("pfad", ["this.zz", "foo.bar.baz", "x.y.z.deep.weiter"])
def test_fehlgriff_importiert_kein_modul(methode, pfad, client):
    """`OPTIONS /api/method/this.zz` importierte frueher das Modul `this`.

    Geprueft wird `sys.modules`: vorher und nachher dieselbe Menge. Der
    Anfragepfad darf NIE ein Importname sein.
    """
    vorher = set(sys.modules)
    antwort = getattr(client, methode)(f"/api/method/{pfad}", follow_redirects=False)
    neu = set(sys.modules) - vorher
    assert neu == set(), f"{methode.upper()} {pfad} hat Module importiert: {sorted(neu)[:5]}"
    if methode != "options":
        assert antwort.status_code == 404, antwort.text


@pytest.mark.parametrize("methode", ["get", "options"])
def test_fehlgriff_ruft_nachregistrieren_nicht(methode, client, monkeypatch):
    """`nachregistrieren()` laeuft beim Start, NICHT je Anfrage."""
    from diakronos_app.frappe_compat import registry

    gerufen: list[int] = []
    echt = registry.nachregistrieren
    monkeypatch.setattr(registry, "nachregistrieren", lambda: gerufen.append(1) or echt())
    for _ in range(5):
        getattr(client, methode)("/api/method/this.zz", follow_redirects=False)
    assert gerufen == [], f"nachregistrieren je Anfrage: {len(gerufen)}"


def test_preflight_bestaetigt_unbekannten_pfad_ohne_import(client):
    """OPTIONS bleibt ein leeres 204 (kein Register-Orakel), aber ohne Import."""
    antwort = client.options("/api/method/this.zz", headers={"Origin": "http://testserver"})
    assert antwort.status_code == 204, antwort.text
    assert antwort.content == b"", antwort.text
    assert "access-control-allow-origin" not in antwort.headers
    assert "this" not in sys.modules


# ── SOLL 3: das Register waechst nicht ────────────────────────────────────


def test_300_login_aliasse_vergroessern_das_register_nicht(client):
    """300 Anfragen `z<i>.login` = 0 neue Registereintraege (vorher: 300)."""
    from diakronos_app.frappe_compat import registry

    _register_vollstaendig()
    vorher = len(registry.registered())
    for i in range(300):
        client.get(f"/api/method/z{i}.login", follow_redirects=False)
    assert len(registry.registered()) == vorher, (
        f"Register gewachsen: {len(registry.registered()) - vorher} Eintraege"
    )
    assert registry.lookup("z1.login") is None, "Alias steht im Register"


def test_login_alias_wirkt_weiter_wie_login(client, patched_db, engine, session_factory):
    """Der Alias ist nicht gespeichert, aber genauso streng wie `login`."""
    antwort = client.get("/api/method/z1.auth.login", params={"usr": USR, "pwd": PWD})
    assert antwort.status_code == 405, antwort.text
    assert "set-cookie" not in {k.lower() for k in antwort.headers.keys()}, antwort.headers


# ── SOLL 4: Kurzformen nur eindeutig und ausdruecklich zugesagt ────────────


@pytest.mark.parametrize(
    "pfad",
    [
        # Mehrdeutig im Register (mehrere gleichnamige Fassungen).
        "sitzung_status",
        "status",
        "liste",
        # Vorlauf statt Kurzform (das fruehere paketweite `api.<name>`).
        "api.insert",
        "api.upload_file",
        "api.logout",
        "api.root_uebertragen",
        # Frappe-Kernfunktionen: nur ihre zugesagte Schreibweise.
        "insert",
        # Fremdes Modul.
        "diakronos.planrahmen.api.delete_lied",
    ],
)
def test_kurzform_ohne_zusage_ist_404(pfad, client):
    """Was nicht eindeutig UND zugesagt ist, ist ein 404 — kein Ratemal."""
    _register_vollstaendig()
    antwort = client.post(f"/api/method/{pfad}", json={})
    assert antwort.status_code == 404, (pfad, antwort.status_code, antwort.text)
    assert antwort.json()["message"] == _NICHT_GEFUNDEN, antwort.text


@pytest.mark.parametrize(
    ("alt", "neu"),
    [
        # Dev-Modus: das Modul traegt kein `FRAPPE_MODULE`; die SPA baut ihre
        # Adresse als `diakronos.devmodus.api.<fn>`.
        ("sitzung_status", "diakronos.devmodus.api.sitzung_status"),
        ("sitzung_starten", "diakronos.devmodus.api.sitzung_starten"),
        ("sitzung_beenden", "diakronos.devmodus.api.sitzung_beenden"),
    ],
)
def test_devmodus_kurzform_ist_404_modulbahn_bleibt(alt, neu, client):
    """SOLL 4: die nackte Kurzform ist 404, die Bahn der SPA bleibt.

    Gemessen: `diakronos.devmodus.api.sitzung_status` loest auf, `sitzung_status`
    nicht mehr (mehrdeutig im Register — `api.session` hat denselben Namen).
    """
    from diakronos_app.devmodus import api as devmodus_api

    devmodus_api.registriere(None)
    kurz = client.post(f"/api/method/{alt}", json={})
    # Zwei moegliche 404: der Router („Methode nicht gefunden“) oder der
    # Dev-Modus bei ausgeschaltetem Schalter („Nicht gefunden“). Beide heissen
    # 404 — entscheidend ist, dass die Kurzform NICHT die Fachfunktion erreicht.
    assert kurz.status_code == 404, (alt, kurz.text)
    bahn = client.post(f"/api/method/{neu}", json={})
    # Die Bahn erreicht die Fachfunktion: alles ausser einem 404 des ROUTERS
    # (der Dev-Modus antwortet mit eigenem 404, wenn sein Schalter aus ist).
    assert bahn.status_code != 404 or bahn.json().get("message") != _NICHT_GEFUNDEN, (neu, bahn.text)


@pytest.mark.parametrize(
    "pfad",
    [
        # Zugesagte Kurzform (Name gehoert genau EINER whitelisted Funktion).
        "ping",
        # Frappe-Kernpfade in ihrer dokumentierten Schreibweise.
        "frappe.client.insert",
        "upload_file",
        "logout",
        # Modulbahn, wie die SPA sie ruft.
        "session.sitzung_status",
        # Der Frappe-Kernpfad mit Umleitung.
        "frappe.sessions.get_csrf_token",
    ],
)
def test_zugesagte_schreibweisen_bleiben_erreichbar(pfad, client):
    """Die zugesagten Wege bleiben offen (kein 404) — die Gegenprobe."""
    _register_vollstaendig()
    antwort = client.post(f"/api/method/{pfad}", json={})
    assert _kein_404(antwort), (pfad, antwort.status_code, antwort.text)


# ── Der Waechter der Vorgaengerkarte, jetzt am Router ─────────────────────


def test_waechter_loest_auf_heisst_jetzt_auch_wirklich_aufloesen():
    """`_loest_auf` der Vorgaengerkarte fragte `_ist_eigener_pfad or lookup`.

    Genau daran ging `frappe.sessions.get_csrf_token` vorbei: `_ist_eigener_pfad`
    war True, `lookup` None, im Router also 404. Hier steht die Gegenprobe am
    Baustein, den der Router BENUTZT (`_kandidat`) — nicht an zwei Fragen, von
    denen eine schon genuegt.
    """
    from diakronos_app.frappe_compat import registry, router

    _register_vollstaendig()
    for pfad, fn in (
        ("frappe.sessions.get_csrf_token", registry.lookup("diakronos.diakonos.api.session.sitzung_status")),
        ("login", registry.lookup("login")),
        ("diakronos.diakonos.api.session.sitzung_status", registry.lookup("diakronos.diakonos.api.session.sitzung_status")),
    ):
        assert fn is not None, pfad
        assert router._kandidat(pfad) is fn, f"{pfad} loest im Router nicht auf"
