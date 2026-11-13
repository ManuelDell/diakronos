"""MT-8 — Abmelden fuehrt NIE zum Anbieter; danach Website, sonst Login.

WARUM
-----
Befund (Manuel, Live-Test 11.11.): Ein Abmelden in Diakronos schickte den
Browser auf die Abmeldeseite von Authentik (`end_session_endpoint`), sobald
`AUTH_OIDC_ENABLED` und `AUTH_OIDC_LOGOUT` an waren.

REGEL NACH DEM REVIEW (Operator, 12.11.) — Ziel nach dem Abmelden:

  a) die OEFFENTLICHE WEBSITE, aber nur wenn ihre Adresse AUSDRUECKLICH
     konfiguriert ist (`PRIMO_PUBLIC_URL`). Der Server liefert genau diese
     Adresse aus; die interne `PRIMO_URL` und ein geratenes `/` zaehlen NICHT.
  b) sonst die eigene Login-Seite OHNE automatische SSO-Weiterleitung
     (`/login?sso=0`) — sonst waere man bei `nur-admin` sofort wieder beim
     Anbieter und das Abmelden wirkungslos.
  c) bei `AUTH_LOCAL_LOGIN=aus`: eine kurze „Du bist abgemeldet“-Seite mit dem
     SSO-Knopf — keine 503, keine automatische Weiterleitung.

NIEMALS eine Seite des Anbieters.

Geprueft wird beides — JSON-Aufruf (die SPA liest `redirect` und setzt
`window.location`) und Formular/Browser-POST (303 mit `Location`). Dazu der
Waechter: bei aktivem OIDC wird der `end_session_endpoint` des Anbieters NICHT
angesteuert (der Test zaehlt die Metadaten-Aufrufe).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from diakronos_app import base_path
from diakronos_app.frappe_compat import sitzungen
from diakronos_app.main import erstelle_app
from diakronos_app.models.core import User
from diakronos_app.settings import settings as echte_settings

PRAEFIX = "/diakronos"
OIDC_ISSUER = "https://auth.example.org/application/o/diakronos/"
WEBSITE = "https://gemeinde.example.org"


# ── Hilfen ──────────────────────────────────────────────────────────────────

def _benutzer_anlegen(patched_db) -> None:
    fremd = patched_db()
    if fremd.get(User, "Administrator") is None:
        fremd.add(User(name="Administrator", email="Administrator",
                       full_name="Administrator", enabled=True))
        fremd.commit()
    fremd.close()


def _mit_client(app, ohne_csrf: bool = False):
    """Client mit gueltiger Sitzung (Cookie + CSRF-Token) — wie `conftest.client`."""
    from diakronos_app import frappe_compat

    frappe_compat.set_user("Administrator")
    sid, csrf = sitzungen.anlegen("Administrator")
    c = TestClient(app)
    c.cookies.set("sid", sid)
    if not ohne_csrf:
        c.headers["X-Frappe-CSRF-Token"] = csrf
    return c, sid


@pytest.fixture()
def _praefix_aus(monkeypatch):
    monkeypatch.setattr(echte_settings, "diakronos_base_path", "")
    base_path.setze_praefix("")
    try:
        yield
    finally:
        base_path.setze_praefix("")


@pytest.fixture()
def _praefix_an(monkeypatch):
    monkeypatch.setattr(echte_settings, "diakronos_base_path", PRAEFIX)
    try:
        yield
    finally:
        base_path.setze_praefix("")


@pytest.fixture()
def _keine_website(monkeypatch):
    """Weder interne noch oeffentliche Website-Adresse konfiguriert."""
    monkeypatch.setattr(echte_settings, "primo_url", "")
    monkeypatch.setattr(echte_settings, "primo_public_url", "")
    yield


@pytest.fixture()
def _oidc_an(monkeypatch):
    monkeypatch.setattr(echte_settings, "auth_oidc_enabled", True)
    monkeypatch.setattr(echte_settings, "auth_oidc_logout", True)
    monkeypatch.setattr(echte_settings, "auth_oidc_issuer", OIDC_ISSUER)
    monkeypatch.setattr(echte_settings, "auth_oidc_client_id", "diakronos-test")
    yield


# ── a) Website konfiguriert: genau DIESE Adresse ────────────────────────────

def test_json_logout_mit_website_zielt_auf_die_website(
        _praefix_aus, _keine_website, patched_db, fake_redis, monkeypatch):
    """`PRIMO_PUBLIC_URL` gesetzt -> das genannte Ziel ist die Website."""
    monkeypatch.setattr(echte_settings, "primo_public_url", WEBSITE)
    _benutzer_anlegen(patched_db)
    app = erstelle_app()
    c, sid = _mit_client(app)

    r = c.post("/logout", headers={"Accept": "application/json"})

    assert r.status_code == 200, r.text
    assert r.json()["redirect"] == WEBSITE + "/", r.json()
    assert sitzungen.lesen(sid) is None, "lokale Sitzung muss beendet sein"


def test_formular_logout_mit_website_leitet_auf_die_website(
        _praefix_aus, _keine_website, patched_db, fake_redis, monkeypatch):
    monkeypatch.setattr(echte_settings, "primo_public_url", WEBSITE)
    _benutzer_anlegen(patched_db)
    app = erstelle_app()
    c, sid = _mit_client(app)

    r = c.post("/logout", headers={"Accept": "text/html"}, follow_redirects=False)

    assert r.status_code == 303, r.text
    assert r.headers["location"] == WEBSITE + "/"
    assert sitzungen.lesen(sid) is None


def test_website_gilt_auch_unter_praefix(
        _praefix_an, _keine_website, patched_db, fake_redis, monkeypatch):
    """Befund 1 des Reviews: mit Praefix war das Ziel `/` -> dort 404.

    Die konfigurierte Website-Adresse gilt in JEDEM Betriebsmodus.
    """
    monkeypatch.setattr(echte_settings, "primo_public_url", WEBSITE)
    _benutzer_anlegen(patched_db)
    app = erstelle_app()
    c, _sid = _mit_client(app)

    r = c.post(f"{PRAEFIX}/logout", headers={"Accept": "application/json"})

    assert r.status_code == 200, r.text
    assert r.json()["redirect"] == WEBSITE + "/", r.json()


def test_interne_primo_url_ist_kein_abmeldeziel(
        _praefix_aus, _keine_website, patched_db, fake_redis, monkeypatch):
    """Befund 3: `PRIMO_URL` ist Server-zu-Server — kein Browser-Ziel.

    `primo_public_url_effektiv` faellt auf `primo_url` zurueck; genau dieser
    Default darf NICHT als „Website vorhanden“ gelten.
    """
    monkeypatch.setattr(echte_settings, "primo_url", "http://192.168.1.11:8095")
    _benutzer_anlegen(patched_db)
    app = erstelle_app()
    c, _sid = _mit_client(app)

    r = c.post("/logout", headers={"Accept": "application/json"})

    assert r.status_code == 200, r.text
    assert r.json()["redirect"] == "/login?sso=0", r.json()


# ── b) Keine Website: Login OHNE automatische SSO-Weiterleitung ─────────────

def test_json_logout_ohne_website_zielt_auf_login_ohne_sso(
        _praefix_aus, _keine_website, patched_db, fake_redis):
    """Kein Praefix, keine Website -> `/login?sso=0` (nicht blankes `/login`)."""
    _benutzer_anlegen(patched_db)
    app = erstelle_app()
    c, sid = _mit_client(app)

    r = c.post("/logout", headers={"Accept": "application/json"})

    assert r.status_code == 200, r.text
    assert r.json()["redirect"] == "/login?sso=0"
    assert sitzungen.lesen(sid) is None, "lokale Sitzung muss beendet sein"


def test_formular_logout_ohne_website_leitet_auf_login_ohne_sso(
        _praefix_aus, _keine_website, patched_db, fake_redis):
    _benutzer_anlegen(patched_db)
    app = erstelle_app()
    c, sid = _mit_client(app)

    r = c.post("/logout", headers={"Accept": "text/html"}, follow_redirects=False)

    assert r.status_code == 303, r.text
    assert r.headers["location"] == "/login?sso=0"
    assert sitzungen.lesen(sid) is None


def test_login_ohne_sso_leitet_bei_nur_admin_nicht_zum_anbieter(
        _praefix_aus, _keine_website, _oidc_an, patched_db, fake_redis, monkeypatch):
    """Befund 2: `/login` leitete bei `nur-admin` automatisch zum Anbieter.

    Das Abmeldeziel `/login?sso=0` darf das NICHT tun — sonst ist das Abmelden
    wirkungslos. Erwartet: die Maske (200, Passwortfeld), keine 3xx.
    """
    monkeypatch.setattr(echte_settings, "auth_local_login", "nur-admin")
    _benutzer_anlegen(patched_db)
    app = erstelle_app()

    r = TestClient(app).get("/login", params={"sso": "0"}, follow_redirects=False)

    assert r.status_code == 200, (r.status_code, r.headers.get("location"))
    assert "Passwort" in r.text
    assert "auth.example.org" not in r.text


def test_login_ohne_sso_zeigt_bei_aus_die_abgemeldet_seite(
        _praefix_aus, _keine_website, _oidc_an, patched_db, fake_redis, monkeypatch):
    """Befund 2c: bei `aus` keine 503, sondern „abgemeldet“ + SSO-Knopf."""
    monkeypatch.setattr(echte_settings, "auth_local_login", "aus")
    _benutzer_anlegen(patched_db)
    app = erstelle_app()

    r = TestClient(app).get("/login", params={"sso": "0"}, follow_redirects=False)

    assert r.status_code == 200, (r.status_code, r.headers.get("location"))
    assert "abgemeldet" in r.text.lower()
    # Der SSO-Knopf ist sichtbar, aber es wird NICHT automatisch weitergeleitet.
    assert "sso=1" in r.text
    assert "auth.example.org" not in r.text
    assert "nicht verfügbar" not in r.text


def test_login_ohne_sso_unter_praefix(
        _praefix_an, _keine_website, _oidc_an, patched_db, fake_redis, monkeypatch):
    """Das Abmeldeziel unter dem Praefix ist `{Praefix}/login?sso=0`."""
    monkeypatch.setattr(echte_settings, "auth_local_login", "nur-admin")
    _benutzer_anlegen(patched_db)
    app = erstelle_app()
    c, _sid = _mit_client(app)

    r = c.post(f"{PRAEFIX}/logout", headers={"Accept": "application/json"})

    assert r.status_code == 200, r.text
    assert r.json()["redirect"] == f"{PRAEFIX}/login?sso=0", r.json()
    # Und die Route liefert dort auch wirklich die Maske (kein Anbieter).
    seite = TestClient(app).get(f"{PRAEFIX}/login", params={"sso": "0"},
                                follow_redirects=False)
    assert seite.status_code == 200, seite.headers.get("location")


# ── Waechter: der Anbieter wird NICHT angesteuert ───────────────────────────

def test_oidc_aktiv_kein_anbieter_logout(
        _praefix_aus, _keine_website, _oidc_an, patched_db, fake_redis, monkeypatch):
    """Mit aktivem OIDC + AUTH_OIDC_LOGOUT bleibt der Anbieter aussen vor."""
    from diakronos_app.anmeldung import routen

    aufrufe = []

    def _kein_abruf(*args, **kwargs):  # pragma: no cover — darf nicht laufen
        aufrufe.append(1)
        raise AssertionError("Metadaten des Anbieters duerfen beim Abmelden "
                             "nicht abgerufen werden (MT-8).")

    monkeypatch.setattr(routen.oidc, "hole_metadaten", _kein_abruf)
    _benutzer_anlegen(patched_db)
    app = erstelle_app()
    c, sid = _mit_client(app)

    r = c.post("/logout", headers={"Accept": "application/json"})

    assert r.status_code == 200, r.text
    ziel = r.json()["redirect"]
    assert ziel == "/login?sso=0", ziel
    assert "auth.example.org" not in ziel
    assert aufrufe == []
    assert sitzungen.lesen(sid) is None


def test_oeffentliche_startseite_nur_bei_konfigurierter_website(
        _praefix_aus, _keine_website, monkeypatch):
    """Einheitliche Regel: nur `PRIMO_PUBLIC_URL` -> Adresse, sonst `None`."""
    from diakronos_app.anmeldung.routen import (
        _abmelde_startseite,
        _oeffentliche_startseite,
    )

    assert _oeffentliche_startseite() is None
    assert _abmelde_startseite() == "/login?sso=0"

    # Interne Adresse allein zaehlt NICHT (Befund 3).
    monkeypatch.setattr(echte_settings, "primo_url", "http://primo.intern:8095")
    assert _oeffentliche_startseite() is None

    # Ohne Schema ist es keine Browser-Adresse.
    monkeypatch.setattr(echte_settings, "primo_public_url", "gemeinde.example.org")
    assert _oeffentliche_startseite() is None

    monkeypatch.setattr(echte_settings, "primo_public_url", WEBSITE + "/")
    assert _oeffentliche_startseite() == WEBSITE + "/"
    assert _abmelde_startseite() == WEBSITE + "/"

    # Der Betriebs-Praefix aendert NICHTS an der Regel (Befund 1).
    monkeypatch.setattr(echte_settings, "diakronos_base_path", PRAEFIX)
    base_path.setze_praefix(PRAEFIX)
    try:
        assert _oeffentliche_startseite() == WEBSITE + "/"
    finally:
        base_path.setze_praefix("")
