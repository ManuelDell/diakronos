"""WEB-5a — Diakronos pfadfaehig: alles unter `DIAKRONOS_BASE_PATH`.

WARUM
-----
Unter einer Gemeinde-Domain liegt auf `/` die statische Website; ALLE
Diakronos-Funktionen liegen unter einem Praefix (z. B. `/diakronos/…`). Der
Eingang (nginx, WEB-4) reicht den Praefix UNVERAENDERT durch. Die App muss
deshalb ihre Routen selbst darunter anbieten und alle erzeugten Adressen
(Weiterleitungen, Cookies, Links, Datei-URLs) praefixbewusst bauen.

WAS HIER FESTGENAGELT WIRD
--------------------------
 1. Normalisierung der Einstellung (S1).
 2. Der ganze Betrieb unter dem Praefix: `/api/method`, `/api/resource`,
    `/login`, `/logout`, `/auth/…`, Dateien, Registrierungsbilder,
    `google-calendar-callback`, `/healthz`, `/socket.io`, SPA + Assets (S2).
 3. Pfade OHNE Praefix antworten mit gesetztem Praefix NICHT (404) — sonst
    kollidierte die App mit der Website (S2). Keine Ausnahme, auch nicht
    fuer `/healthz`.
 4. Erzeugte Adressen sind praefixbewusst: Login-Redirect, Cookie-Pfade,
    Datei-Upload/Abruf, Registrierungslink, Boot-JSON `basePath` (S3).
 5. Komfort: Wurzel `/` leitet NICHTS um, `{Praefix}` -> `{Praefix}/diakonos`
    (S4).

Der Test baut die Anwendung PRO TEST mit einem eigenen Einstellungsobjekt
(`erstelle_app(SimpleNamespace(...))`) — der Praefix ist eine Prozessgroesse
(`base_path.aktiver_praefix`) und wird danach zurueckgesetzt.
"""

from __future__ import annotations

import base64
import hashlib
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from diakronos_app import base_path
from diakronos_app.frappe_compat import sitzungen
from diakronos_app.main import erstelle_app
from diakronos_app.models.core import User
from diakronos_app.settings import settings as echte_settings

PRAEFIX = "/diakronos"


# ── Hilfen ──────────────────────────────────────────────────────────────────

def _frappe_hash(passwort: str, salt: bytes = b"testsalztestsalt", runden: int = 29000) -> str:
    digest = hashlib.pbkdf2_hmac("sha256", passwort.encode("utf-8"), salt, runden, dklen=32)

    def ab64(roh: bytes) -> str:
        return base64.b64encode(roh).decode().rstrip("=").replace("+", ".")

    return f"$pbkdf2-sha256${runden}${ab64(salt)}${ab64(digest)}"


def _lege_benutzer(session_factory, name: str, passwort: str) -> None:
    sess = session_factory()
    try:
        sess.add(User(name=name, email=name, full_name=name, enabled=True,
                      password_hash=_frappe_hash(passwort)))
        sess.commit()
    finally:
        sess.close()


def _socket_frei(monkeypatch):
    """socket.io ohne Redis-Manager — sonst haengt der Handshake netzlos.

    Der Betrieb nutzt `AsyncRedisManager` (Mehrprozess-Betrieb, P6a); im
    Testcontainer gibt es kein Redis. Geprueft wird hier der PFAD, nicht die
    Verteilung zwischen Prozessen.
    """
    from diakronos_app.frappe_compat import realtime

    monkeypatch.setattr(realtime, "socket_app", realtime.create_socket_server()[1])


@pytest.fixture()
def app_mit_praefix(monkeypatch):
    """Anwendung mit `DIAKRONOS_BASE_PATH=/diakronos`; Praefix danach zurueck."""
    monkeypatch.setattr(echte_settings, "diakronos_base_path", PRAEFIX)
    try:
        yield erstelle_app()
    finally:
        base_path.setze_praefix("")


@pytest.fixture()
def app_ohne_praefix(monkeypatch):
    """Anwendung OHNE Praefix — Pflicht, weil `base_path` eine Prozessgroesse
    ist: bliebe der Praefix des vorigen Tests stehen, zeigte auch dieser
    Aufbau auf die praefigierten Pfade."""
    monkeypatch.setattr(echte_settings, "diakronos_base_path", "")
    base_path.setze_praefix("")
    try:
        yield erstelle_app()
    finally:
        base_path.setze_praefix("")


@pytest.fixture()
def client_praefix(app_mit_praefix, patched_db, fake_redis):
    """Client gegen die praefigierte Anwendung — als `Administrator`.

    Dieselbe Bauform wie `conftest.client`: die Identitaet kommt aus der
    Test-Naht, die Sitzung (Cookie + CSRF-Token) aus `sitzungen.anlegen`.
    """
    from diakronos_app import frappe_compat
    from diakronos_app.models.core import User

    fremd = patched_db()
    if fremd.get(User, "Administrator") is None:
        fremd.add(User(name="Administrator", email="Administrator",
                       full_name="Administrator", enabled=True))
        fremd.commit()
    fremd.close()

    frappe_compat.set_user("Administrator")
    sid, csrf = sitzungen.anlegen("Administrator")
    with TestClient(app_mit_praefix) as c:
        c.cookies.set("sid", sid)
        c.headers["X-Frappe-CSRF-Token"] = csrf
        yield c
    frappe_compat.reset_user()


# ── S1: Einstellung / Normalisierung ────────────────────────────────────────

@pytest.mark.parametrize(
    "roh, erwartet",
    [
        ("", ""),
        (None, ""),
        ("/", ""),
        ("diakronos", "/diakronos"),
        ("/diakronos", "/diakronos"),
        ("/diakronos/", "/diakronos"),
        ("diakronos/", "/diakronos"),
        ("//app//instanz/", "/app/instanz"),
        ("  /x  ", "/x"),
    ],
)
def test_normalisierung(roh, erwartet):
    assert base_path.normalisiere(roh) == erwartet


@pytest.mark.parametrize("boese", ["/a b", "/a?x=1", "/a#b", "/a\\b", "/../etc", "/a\nb"])
def test_unbrauchbarer_praefix_wird_abgelehnt(boese):
    """Ein still verworfener Wert waere schlimmer als ein Startabbruch."""
    with pytest.raises(ValueError):
        base_path.normalisiere(boese)


def test_pfad_und_datei_url_idempotent_und_schonend(monkeypatch):
    base_path.setze_praefix(PRAEFIX)
    try:
        assert base_path.pfad("/login") == "/diakronos/login"
        assert base_path.pfad("/diakonos/login") == "/diakronos/diakonos/login"
        assert base_path.pfad("/diakronos/login") == "/diakronos/login"  # nicht doppelt
        assert base_path.pfad("https://example.org/x") == "https://example.org/x"
        assert base_path.datei_url("/files/a.pdf") == "/diakronos/files/a.pdf"
        assert base_path.datei_url("/private/files/a.pdf") == "/diakronos/private/files/a.pdf"
        assert base_path.datei_url("") == ""
        assert base_path.datei_url("https://example.org/f.pdf") == "https://example.org/f.pdf"
    finally:
        base_path.setze_praefix("")


def test_default_ist_leer_und_aendert_nichts():
    """S1: Default "" = heutiges Verhalten; die bestehende App bleibt unveraendert."""
    assert echte_settings.diakronos_base_path == ""


def test_oidc_redirect_ziel_traegt_praefix():
    """S3: OIDC-Redirect-URL wird aus APP_BASE_URL + Praefix gebaut."""
    s = echte_settings.model_copy(update={
        "app_base_url": "https://gemeinde.example.org",
        "auth_oidc_redirect_url": "",
        "diakronos_base_path": PRAEFIX,
    })
    assert s.oidc_redirect_ziel == "https://gemeinde.example.org/diakronos/auth/oidc/callback"

    ohne = s.model_copy(update={"diakronos_base_path": ""})
    assert ohne.oidc_redirect_ziel == "https://gemeinde.example.org/auth/oidc/callback"


# ── S2: Routen unter dem Praefix ────────────────────────────────────────────

def test_healthz_unter_praefix_und_nicht_ohne(client_praefix):
    r = client_praefix.get(f"{PRAEFIX}/healthz")
    assert r.status_code == 200
    assert r.json()["status"] in {"ok", "degraded"}
    # Keine Ausnahme: /healthz ohne Praefix gibt es NICHT (Karte S2).
    assert client_praefix.get("/healthz").status_code == 404


def test_login_masken_route_unter_praefix_nur_dort(client_praefix):
    assert client_praefix.get("/login").status_code == 404
    r = client_praefix.get(f"{PRAEFIX}/login")
    assert r.status_code == 200
    # S3: das Formular postet an die PRAEFIGIERTE API, nicht an /api/method.
    assert f'action="{PRAEFIX}/api/method/login"' in r.text
    assert 'href="/login"' not in r.text


def test_api_method_unter_praefix(client_praefix, patched_db):
    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")
    r = client_praefix.post(f"{PRAEFIX}/api/method/login",
                            json={"usr": "anna@example.org", "pwd": "geheim-123"})
    assert r.status_code == 200, r.text
    assert r.json()["message"] == "Logged In"
    # S2: derselbe Aufruf OHNE Praefix trifft nichts mehr.
    assert client_praefix.post("/api/method/login", json={}).status_code == 404


def test_api_resource_unter_praefix(client_praefix):
    """/api/resource liegt unter dem Praefix — und nur dort.

    Anders als bei `/api/method` genuegt hier die Existenz der Route: eine
    echte Zeile wuerde die Rechtematrix (BLD-R1) mitpruefen, die mit dem
    Praefix nichts zu tun hat. Geprueft wird der Unterschied zwischen
    „Route da" und „Route weg", nicht der Statuscode.
    """
    unter = client_praefix.get(f"{PRAEFIX}/api/resource/User")
    ohne = client_praefix.get("/api/resource/User")
    assert unter.status_code != 404, unter.text
    assert ohne.status_code == 404


def test_socket_io_handshake_unter_praefix(monkeypatch, patched_db, fake_redis):
    """Der Handshake antwortet UNTER dem Praefix — mit 200, nicht 404.

    BEFUND (Abnahme-Stack, 2026-10-30): `/diakronos/socket.io/?EIO=4…` gab
    404, ohne Praefix 200. Ursache: `python-engineio` vergleicht den ROHEN
    `scope["path"]` mit `/socket.io/` und liest `root_path` nicht. Fix:
    `frappe_compat/socket_praefix.PraefixSocketApp` schneidet den Praefix vor
    der Uebergabe ab. Dieser Test haengt an der WIRKUNG (Statuscode am
    gemounteten Pfad), nicht an der Huelle.
    """
    _socket_frei(monkeypatch)
    monkeypatch.setattr(echte_settings, "diakronos_base_path", PRAEFIX)
    try:
        app = erstelle_app()
        c = TestClient(app)
        unter = c.get(f"{PRAEFIX}/socket.io/?EIO=4&transport=polling")
        assert unter.status_code == 200, (unter.status_code, unter.text[:120])
        # Engine.IO OPEN-Paket (Beginn der Handshake-Antwort).
        assert unter.text.startswith("0{")
        # Ohne Praefix gibt es den Handshake nicht mehr.
        assert c.get("/socket.io/?EIO=4&transport=polling").status_code == 404
    finally:
        base_path.setze_praefix("")


def test_socket_io_handshake_ohne_praefix_unveraendert(monkeypatch, patched_db, fake_redis):
    """Regression: ohne Praefix bleibt der Handshake genau wie heute."""
    _socket_frei(monkeypatch)
    monkeypatch.setattr(echte_settings, "diakronos_base_path", "")
    base_path.setze_praefix("")
    c = TestClient(erstelle_app())
    r = c.get("/socket.io/?EIO=4&transport=polling")
    assert r.status_code == 200, (r.status_code, r.text[:120])
    assert r.text.startswith("0{")


def test_oidc_pfade_unter_praefix(app_mit_praefix, patched_db, fake_redis):
    """OIDC-Start liegt unter dem Praefix — ohne Praefix gibt es ihn nicht."""
    with TestClient(app_mit_praefix) as c:
        mit = c.get(f"{PRAEFIX}/auth/oidc/start")
        assert c.get("/auth/oidc/start").status_code == 404
        assert mit.status_code in {403, 404}


def test_spa_und_assets_unter_praefix(client_praefix):
    r = client_praefix.get(f"{PRAEFIX}/diakonos")
    assert r.status_code in {200, 303}
    assert client_praefix.get("/diakonos").status_code == 404


def test_ohne_praefix_bleibt_alles_wie_heute(app_ohne_praefix, patched_db, fake_redis):
    """S1: Default "" = unveraendertes Verhalten (Regression)."""
    with TestClient(app_ohne_praefix) as c:
        assert c.get("/healthz").status_code == 200
        assert c.get("/login").status_code == 200
        assert c.get("/diakonos").status_code in {200, 303}
        # Die praefigierte Adresse gibt es ohne Praefix NICHT.
        assert c.get(f"{PRAEFIX}/healthz").status_code == 404


# ── S3: praefixbewusste Adressen ────────────────────────────────────────────

def test_login_setzt_cookie_pfad_auf_praefix(client_praefix, patched_db):
    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")
    r = client_praefix.post(f"{PRAEFIX}/api/method/login",
                            json={"usr": "anna@example.org", "pwd": "geheim-123"})
    assert r.status_code == 200, r.text
    set_cookie = r.headers["set-cookie"].lower()
    assert "sid=" in set_cookie
    assert f"path={PRAEFIX}" in set_cookie


def test_logout_loescht_cookie_auf_praefixpfad(client_praefix, patched_db):
    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")
    login = client_praefix.post(f"{PRAEFIX}/api/method/login",
                                json={"usr": "anna@example.org", "pwd": "geheim-123"})
    sid, csrf = login.cookies["sid"], login.json()["csrf_token"]
    assert sitzungen.lesen(sid) is not None

    r = client_praefix.post(f"{PRAEFIX}/api/method/logout",
                            cookies={"sid": sid},
                            headers={"X-Frappe-CSRF-Token": csrf})
    assert r.status_code == 200, r.text
    assert sitzungen.lesen(sid) is None
    assert f"path={PRAEFIX}" in r.headers["set-cookie"].lower()


def test_logout_route_unter_praefix(client_praefix):
    assert client_praefix.post("/logout").status_code == 404
    assert client_praefix.post(f"{PRAEFIX}/logout").status_code in {200, 303}


def test_datei_upload_und_abruf_mit_praefix(client_praefix, patched_db, tmp_path, monkeypatch):
    """S3: DB bleibt bei `/files/…`, die AUSGABE traegt den Praefix."""
    monkeypatch.setattr(echte_settings, "files_dir", str(tmp_path))

    hoch = client_praefix.post(
        f"{PRAEFIX}/api/method/upload_file",
        files={"file": ("notiz.txt", b"hallo web-5a", "text/plain")},
        data={"is_private": "1"},
    )
    assert hoch.status_code == 200, hoch.text
    file_url = hoch.json()["message"]["file_url"]
    assert file_url.startswith(f"{PRAEFIX}/files/"), file_url

    # In der DB steht weiter der unveraenderte Frappe-Pfad.
    from diakronos_app.models.core import FileModel

    sess = patched_db()
    zeile = sess.query(FileModel).order_by(FileModel.creation.desc()).first()
    assert zeile is not None and zeile.file_url.startswith("/files/")
    name = zeile.file_url.rsplit("/", 1)[-1]
    sess.close()

    # Abruf unter dem Praefix funktioniert, ohne Praefix nicht.
    abruf = client_praefix.get(f"{PRAEFIX}/files/{name}")
    assert abruf.status_code == 200
    assert abruf.content == b"hallo web-5a"
    assert client_praefix.get(f"/files/{name}").status_code == 404


def test_boot_json_traegt_basepath(app_mit_praefix, patched_db, fake_redis, session_factory):
    """S3 / Kontrakt WEB-5b: das Boot-Objekt nennt den Praefix."""
    _lege_benutzer(session_factory, "anna@example.org", "geheim-123")
    # Angemeldet, damit die SPA-Seite (und nicht die Maske) ausgeliefert wird.
    sid, csrf = sitzungen.anlegen("anna@example.org")
    with TestClient(app_mit_praefix) as c:
        r = c.get(f"{PRAEFIX}/diakonos", cookies={"sid": sid},
                  headers={"X-Frappe-CSRF-Token": csrf})
    assert r.status_code == 200, r.status_code
    assert '"basePath": "/diakronos"' in r.text


def test_boot_json_ohne_praefix_leer(app_ohne_praefix, patched_db, fake_redis, session_factory):
    """Ohne Praefix steht der Schluessel im Boot-Objekt und ist leer."""
    from diakronos_app.frappe_compat import set_user

    _lege_benutzer(session_factory, "anna@example.org", "geheim-123")
    set_user("anna@example.org")
    try:
        from diakronos_app.spa import boot_fuer_request

        assert boot_fuer_request()["basePath"] == ""
    finally:
        set_user(None)


def test_registrierungslink_traegt_praefix(monkeypatch):
    """S3: der angezeigte Link zeigt unter den Praefix."""
    base_path.setze_praefix(PRAEFIX)
    monkeypatch.setattr(
        "diakronos_app.anmeldung.registrierungslink.oeffentliche_basis", lambda: ""
    )
    from diakronos_app.anmeldung.registrierungslink import link_anzeige

    try:
        anzeige = link_anzeige("Registrierung", "abc123")
        assert anzeige == f"{PRAEFIX}/diakonos/registrierung?token=abc123"
    finally:
        base_path.setze_praefix("")


def test_generische_resource_antwort_praefigiert_file_url(client_praefix, patched_db):
    """S3: `file_url` in /api/resource-Antworten traegt den Praefix."""
    from diakronos_app.models.core import FileModel

    sess = patched_db()
    sess.add(FileModel(name="F-0001", file_name="a.pdf", file_url="/files/abc-a.pdf",
                       is_private=False, docstatus=0, idx=0))
    sess.commit()
    sess.close()

    r = client_praefix.get(f"{PRAEFIX}/api/resource/File/F-0001")
    assert r.status_code == 200, r.text
    assert r.json()["data"]["file_url"] == f"{PRAEFIX}/files/abc-a.pdf"


# ── S4: Komfort ─────────────────────────────────────────────────────────────

def test_wurzel_leitet_nichts_um(client_praefix):
    """S4: mit Praefix gehoert `/` der Website — kein Redirect."""
    r = client_praefix.get("/", follow_redirects=False)
    assert r.status_code == 404


def test_praefix_allein_leitet_auf_app(client_praefix):
    r = client_praefix.get(PRAEFIX, follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == f"{PRAEFIX}/diakonos"
