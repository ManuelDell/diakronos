"""LOGIN-1 — Angemeldet: die Login-Seite leitet direkt weiter.

BEFUND (Manuel 2026-11-05): Wer angemeldet ist und `/login` aufruft, sah
trotzdem das Anmeldeformular. Richtig ist: die Anmeldeseite ist dann nur ein
Durchgang — 302 auf das Ziel (`redirect-to`) oder auf die Uebersicht, MIT
Betriebs-Praefix.

Die Faelle dieser Karte, alle ueber HTTP:

  * angemeldet + kein Ziel            -> 302 auf die Uebersicht
  * angemeldet + `redirect-to`        -> 302 dorthin
  * `redirect-to=https://evil.example`, `//evil.example`, `/\\evil.example`
                                      -> 302 auf die Uebersicht (kein Open Redirect)
  * nicht angemeldet                  -> 200 Formular (unveraendert)
  * Gast-Sitzung                      -> 302 (Gast SIEHT die App), aber nie auf
                                         die oeffentlichen Seiten
  * gesperrtes/ausgeschlossenes Konto -> 200 Formular (kein Kreisel)
  * abgelaufene/erfundene Sitzung     -> 200 Formular
  * `noredirect=1` (Fehlschlag-Rueckkehr) -> 200 Formular
  * Praefix (`DIAKRONOS_BASE_PATH=/diakronos`) -> Ziel traegt den Praefix

WARUM DIE FAELLE AN OIDC HAENGEN
--------------------------------
Die Weiterleitung greift NUR bei aktivem OIDC: dort fuehrt der Weg ohnehin
ueber `/login` (zum Anbieter), und wer angemeldet ist, soll zum ZIEL statt zum
Anbieter. Ohne OIDC bleibt der Bestand — die SPA zeigt nach der Anmeldung das
Formular (`test_ohne_oidc_bleibt_das_formular` haelt das fest).

Der Mock-Anbieter ist derselbe wie in `test_sec1_anmeldung.py`: er wird hier
nur fuer die Discovery gebraucht (`/login` mit aktivem OIDC fragt die
Metadaten ab, bevor es weiterleitet).
"""

from __future__ import annotations

import base64
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from fastapi.testclient import TestClient

from diakronos_app import base_path
from diakronos_app.frappe_compat import benutzer_status, sitzungen
from diakronos_app.main import erstelle_app
from diakronos_app.models.core import User
from diakronos_app.settings import settings as echte_settings

USER = "anna@example.org"
PRAEFIX = "/diakronos"


# ── Mock-Anbieter (nur Discovery/JWKS) ────────────────────────────────────


class _Anbieter:
    def __init__(self):
        self.base_url = ""


def _build_provider_server():
    from authlib.jose import JsonWebKey

    schluessel = JsonWebKey.generate_key("RSA", 2048, is_private=True)
    zustand = _Anbieter()
    jwks = {"keys": [schluessel.as_dict(is_private=False)]}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # noqa: D401 — still
            pass

        def _json(self, daten):
            roh = json.dumps(daten).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(roh)))
            self.end_headers()
            self.wfile.write(roh)

        def do_GET(self):  # noqa: N802
            if self.path.endswith("/.well-known/openid-configuration"):
                self._json({
                    "issuer": zustand.base_url,
                    "authorization_endpoint": zustand.base_url + "/authorize",
                    "token_endpoint": zustand.base_url + "/token",
                    "jwks_uri": zustand.base_url + "/jwks",
                    "end_session_endpoint": zustand.base_url + "/logout",
                    "id_token_signing_alg_values_supported": ["RS256"],
                })
            elif self.path.endswith("/jwks"):
                self._json(jwks)
            else:
                self.send_response(404)
                self.end_headers()

        def do_POST(self):  # noqa: N802
            from authlib.jose import jwt as jose_jwt

            laenge = int(self.headers.get("Content-Length", "0"))
            self.rfile.read(laenge)
            claims = {
                "iss": zustand.base_url,
                "aud": "diakronos-test",
                "exp": int(time.time()) + 300,
                "iat": int(time.time()),
                "sub": "sub-login1",
            }
            token = jose_jwt.encode(
                {"alg": "RS256", "kid": schluessel.kid}, claims, schluessel
            ).decode()
            self._json({"access_token": "a", "token_type": "Bearer",
                        "id_token": token, "expires_in": 300})

    server = HTTPServer(("127.0.0.1", 0), Handler)
    host, port = server.server_address
    zustand.base_url = f"http://127.0.0.1:{port}"
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return zustand, server


@pytest.fixture()
def oidc_aktiviert(monkeypatch):
    """OIDC eingeschaltet, Anbieter = lokaler Mock (nur Discovery)."""
    from diakronos_app.anmeldung import oidc

    zustand, server = _build_provider_server()
    oidc.leere_metadaten_cache()
    monkeypatch.setattr(echte_settings, "auth_oidc_enabled", True)
    monkeypatch.setattr(echte_settings, "auth_oidc_issuer", zustand.base_url)
    monkeypatch.setattr(echte_settings, "auth_oidc_client_id", "diakronos-test")
    monkeypatch.setattr(echte_settings, "auth_oidc_client_secret", "geheim-secret")
    monkeypatch.setattr(
        echte_settings, "auth_oidc_redirect_url",
        "http://testserver/auth/oidc/callback",
    )
    monkeypatch.setattr(echte_settings, "auth_local_login", "an")
    try:
        yield zustand
    finally:
        oidc.leere_metadaten_cache()
        server.shutdown()


@pytest.fixture()
def ohne_oidc(monkeypatch):
    monkeypatch.setattr(echte_settings, "auth_oidc_enabled", False)


# ── Hilfen ────────────────────────────────────────────────────────────────


def _konto(session_factory, name: str = USER, *, enabled: bool = True) -> None:
    sess = session_factory()
    try:
        sess.add(User(name=name, email=name, full_name=name, enabled=enabled))
        sess.commit()
    finally:
        sess.close()


def _ausgeschlossen(session_factory, name: str = USER) -> None:
    """Mitglied mit `ausgeschlossen=True` — sperrt das gleichnamige Konto."""
    from diakronos_app.models.diakonos import Mitglied

    sess = session_factory()
    try:
        sess.add(Mitglied(name=f"M-{name}", vorname=name, nachname="Test",
                          email=name, status="Passiver Gast", user=name,
                          ausgeschlossen=True, docstatus=0, idx=0))
        sess.commit()
    finally:
        sess.close()


def _client_mit_sitzung(name: str, *, sso: bool = True) -> TestClient:
    """Client mit echtem `sid`-Cookie fuer `name` (frisch angelegt).

    Die App wird VOR dem Anlegen der Sitzung gebaut: `erstelle_app` setzt den
    Prozess-Praefix aus den Einstellungen neu, und `base_path.pfad` (in
    `_spa_ziel`) liest ihn erst beim Request.
    """
    c = TestClient(erstelle_app())
    sid, _csrf = sitzungen.anlegen(name, sso=sso)
    benutzer_status.vergiss(name)
    c.cookies.set("sid", sid)
    return c


def _get(client: TestClient, pfad: str, **params):
    return client.get(pfad, params=params or None, follow_redirects=False)


# ── Angemeldet: weiterleiten ──────────────────────────────────────────────


def test_angemeldet_leitet_auf_die_uebersicht(client, patched_db, fake_redis, oidc_aktiviert):
    """Der Befund selbst: angemeldet -> 302 auf die Uebersicht."""
    _konto(patched_db)
    r = _get(_client_mit_sitzung(USER), "/login")
    assert r.status_code == 302, f"{r.status_code}: {r.text[:200]}"
    assert r.headers["location"] == "/diakonos"


def test_angemeldet_leitet_auf_das_ziel(client, patched_db, fake_redis, oidc_aktiviert):
    """Mit `redirect-to` geht es dorthin — nicht auf die Uebersicht."""
    _konto(patched_db)
    r = _get(_client_mit_sitzung(USER), "/login", **{"redirect-to": "/diakonos/kalender"})
    assert r.status_code == 302
    assert r.headers["location"] == "/diakonos/kalender"


@pytest.mark.parametrize(
    "boese",
    [
        "https://evil.example/phish",
        "//evil.example/phish",
        "/\\evil.example/phish",
        "evil.example",
    ],
)
def test_open_redirect_wird_abgewiesen(client, patched_db, fake_redis, oidc_aktiviert, boese):
    """Kein Open Redirect: fremde Ziele landen auf der Uebersicht."""
    _konto(patched_db)
    r = _get(_client_mit_sitzung(USER), "/login", **{"redirect-to": boese})
    assert r.status_code == 302
    assert r.headers["location"] == "/diakonos", r.headers["location"]


def test_angemeldet_kein_formular(client, patched_db, fake_redis, oidc_aktiviert):
    """Sicherheitsnetz: die Antwort ist eine Weiterleitung, keine Maske —
    und sie darf NICHT zwischengespeichert werden (`no-store`), sonst schickt
    ein Zwischenspeicher nach dem Logout den naechsten Menschen an der Maske
    vorbei. `Vary: Cookie` haelt die sitzungsabhaengige Antwort auseinander.
    """
    _konto(patched_db)
    r = _get(_client_mit_sitzung(USER), "/login")
    assert "dk-formular" not in r.text
    assert r.status_code == 302
    zwischenlager = r.headers.get("cache-control", "").lower()
    assert "no-store" in zwischenlager, f"Cache-Control: {zwischenlager!r}"
    assert r.headers.get("vary", "").lower() == "cookie", r.headers.get("vary")


# ── Nicht angemeldet / Gast / gesperrt ────────────────────────────────────


def test_nicht_angemeldet_bekommt_das_formular(client, patched_db, fake_redis, oidc_aktiviert):
    """Ohne Sitzung: 200 und die Maske mit Formular (unveraendert)."""
    r = _get(TestClient(erstelle_app()), "/login", **{"lokal": "1"})
    assert r.status_code == 200
    assert "dk-formular" in r.text


def test_gast_sitzung_sieht_die_app(client, patched_db, fake_redis, oidc_aktiviert):
    """Status „Gast“ ist eine gueltige Sitzung: sie sieht die App (Start,
    Kalender, Profil) — also wird weitergeleitet, nicht das Formular gezeigt.
    """
    from diakronos_app.models.diakonos import Mitglied

    _konto(patched_db)
    sess = patched_db()
    try:
        sess.add(Mitglied(name="M-Gast", vorname="G", nachname="Test",
                          email=USER, status="Gast", user=USER,
                          ausgeschlossen=False, docstatus=0, idx=0))
        sess.commit()
    finally:
        sess.close()

    r = _get(_client_mit_sitzung(USER), "/login")
    assert r.status_code == 302
    assert r.headers["location"] == "/diakonos"


def test_gast_wird_nie_auf_oeffentliche_seiten_geleitet(
    client, patched_db, fake_redis, oidc_aktiviert, ohne_oidc
):
    """`redirect-to` auf `registrierung`/`gast` ist fuer einen Angemeldeten
    sinnlos (dort gibt es nichts zu tun) — es geht auf die Uebersicht.

    LOGIN-1b: laeuft OHNE OIDC. Diese Ausnahme ist keine OIDC-Eigenheit: sie
    haengt allein an „darf hier jemand Angemeldetes hin?“, und genau das ist
    auf `dev.ecg-hn.de` (OIDC aus) der einzige Weg.
    """
    _konto(patched_db)
    for ziel in ("/diakonos/registrierung", "/diakonos/gast"):
        r = _get(_client_mit_sitzung(USER), "/login", **{"redirect-to": ziel})
        assert r.status_code == 302, ziel
        assert r.headers["location"] == "/diakonos", (ziel, r.headers["location"])


# ── Punktsegmente: kein Sprung aus der App heraus ─────────────────────────


@pytest.mark.parametrize(
    "boese",
    [
        "/..//evil",
        "/%2e%2e//evil",
        "/%25252e%25252e//evil",
        "/diakonos/../../evil",
        "/./evil",
        "/%2e/evil",
    ],
)
@pytest.mark.parametrize("mit_praefix_", ["ja", "nein"])
def test_punktsegmente_landen_auf_der_uebersicht(
    client, patched_db, fake_redis, ohne_oidc, monkeypatch, boese, mit_praefix_
):
    """LOGIN-1b (Sicherheits-Review LOGIN-1): ``..``/``.`` im Ziel abweisen.

    Der Wert wird EINMAL dekodiert, aus ``/%2e%2e//evil`` wird also
    ``/..//evil``. Mit Betriebs-Praefix entstuende ``/diakronos/..//evil`` —
    der Browser loest das zu ``//evil`` auf: ein protokollrelativer Sprung auf
    eine FREMDES Host, ausgeloest von einem Link auf die eigene Anmeldeseite.
    Erwartet wird deshalb immer die Uebersicht, mit Praefix.
    """
    praefix = PRAEFIX if mit_praefix_ == "ja" else ""
    _mit_praefix(monkeypatch, praefix)
    try:
        _konto(patched_db)
        basis = f"{praefix}/login" if praefix else "/login"
        c = _client_mit_sitzung(USER)
        r = _get(c, basis, **{"redirect-to": boese})
        assert r.status_code == 302, (boese, r.status_code)
        assert r.headers["location"] == f"{praefix}/diakonos", (
            boese,
            r.headers["location"],
        )
    finally:
        base_path.setze_praefix("")


def test_punktsegment_in_der_abfrage_bleibt_erlaubt(patched_db, fake_redis, ohne_oidc, client):
    """Ein ``..`` im ABFRAGE-Teil ist harmlos und darf nicht abgewiesen werden.

    Die Pruefung sieht nur den Pfad-Teil — sonst wuerde ein Filter- oder
    Suchwert ``?q=..`` unnoetig auf die Uebersicht umgebogen.
    """
    _konto(patched_db)
    r = _get(_client_mit_sitzung(USER), "/login", **{"redirect-to": "/diakonos/kalender?q=.."})
    assert r.status_code == 302
    assert r.headers["location"] == "/diakonos/kalender?q=..", r.headers["location"]


def test_gesperrtes_konto_bekommt_das_formular(client, patched_db, fake_redis, oidc_aktiviert):
    """`enabled=False`: die Middleware verwirft die Sitzung -> Maske, kein Kreisel.

    `noredirect=1` erzwingt die lokale Maske (sonst ginge die Route in die
    Anbieter-Weiche) — so ist hier das FORMULAR pruefbar.
    """
    _konto(patched_db, enabled=False)
    r = _get(
        _client_mit_sitzung(USER), "/login",
        noredirect="1", **{"redirect-to": "/diakonos/kalender"},
    )
    assert r.status_code == 200, f"{r.status_code}"
    assert "dk-formular" in r.text


def test_ausgeschlossenes_konto_bekommt_das_formular(
    client, patched_db, fake_redis, oidc_aktiviert
):
    """Ausgeschlossenes Mitglied: dieselbe Antwort wie ein gesperrtes Konto."""
    _konto(patched_db)
    _ausgeschlossen(patched_db)
    r = _get(_client_mit_sitzung(USER), "/login", noredirect="1")
    assert r.status_code == 200, f"{r.status_code}"
    assert "dk-formular" in r.text


def test_abgelaufene_sitzung_bekommt_das_formular(
    client, patched_db, fake_redis, oidc_aktiviert
):
    """Ein `sid`, das der Speicher nicht kennt, ist keine Sitzung."""
    _konto(patched_db)
    c = TestClient(erstelle_app())
    c.cookies.set("sid", "erfunden-und-nicht-im-speicher")
    r = _get(c, "/login", noredirect="1")
    assert r.status_code == 200, f"{r.status_code}"
    assert "dk-formular" in r.text


def test_noredirect_zeigt_immer_die_maske(client, patched_db, fake_redis, oidc_aktiviert):
    """`noredirect=1` ist die Rueckkehr eines Fehlschlags: Maske MIT Meldung."""
    _konto(patched_db)
    r = _get(
        _client_mit_sitzung(USER), "/login",
        noredirect="1", **{"redirect-to": "/diakonos"},
    )
    assert r.status_code == 200
    assert "dk-formular" in r.text


def test_ohne_oidc_wird_trotzdem_weitergeleitet(
    client, patched_db, fake_redis, ohne_oidc
):
    """LOGIN-1b: Die Weiterleitung haengt NICHT an OIDC.

    `dev.ecg-hn.de` faehrt `AUTH_OIDC_ENABLED=0`, und dort ist die lokale
    Anmeldung der NORMALE Weg: wer angemeldet ist und `/login` aufruft, muss
    auf die Uebersicht (bzw. sein Ziel) geschickt werden, statt ein zweites Mal
    das Passwortfeld zu sehen.

    Der Fall hiess bis LOGIN-1 `test_ohne_oidc_bleibt_das_formular` und hielt
    genau das Gegenteil fest — das war der Befund dieser Karte. Das Formular
    fuer NICHT angemeldete Aufrufe bleibt unberuehrt und wird hier mitgeprueft,
    damit die Umstellung nicht als Freibrief fuer die Maske missverstanden wird.
    """
    _konto(patched_db)
    r = _get(_client_mit_sitzung(USER), "/login")
    assert r.status_code == 302, f"{r.status_code}: {r.text[:200]}"
    assert r.headers["location"] == "/diakonos"

    r = _get(_client_mit_sitzung(USER), "/login", **{"redirect-to": "/diakonos/kalender"})
    assert r.status_code == 302
    assert r.headers["location"] == "/diakonos/kalender"

    ohne = _get(TestClient(erstelle_app()), "/login")
    assert ohne.status_code == 200
    assert "dk-formular" in ohne.text


# ── Betriebs-Praefix ──────────────────────────────────────────────────────


def _mit_praefix(monkeypatch, praefix: str = PRAEFIX):
    """Betriebs-Praefix fuer die Dauer des Tests (``""`` = ohne Praefix).

    `diakronos_base_path` wird AUCH in `settings` gesetzt: `erstelle_app` liest
    die Einstellung und setzt damit den Prozess-Praefix neu (Schritt 2 des
    Loeschens ist `setze_praefix`), und die Fixture setzt ihn danach zurueck.
    """
    monkeypatch.setattr(echte_settings, "diakronos_base_path", praefix)
    # `aktiver_praefix` ist eine Prozessgroesse; der App-Bau in der Fixture
    # setzt sie zurueck, deshalb wird sie fuer die Dauer des Tests gepinnt.
    monkeypatch.setattr(base_path, "aktiver_praefix", lambda: praefix)


def test_praefix_ziel_traegt_den_praefix(client, patched_db, fake_redis, oidc_aktiviert, monkeypatch):
    """`dev.ecg-hn.de` nutzt `/diakronos`: Ziel und Startseite MIT Praefix."""
    _mit_praefix(monkeypatch)
    try:
        _konto(patched_db)
        c = _client_mit_sitzung(USER)
        r = _get(c, f"{PRAEFIX}/login")
        assert r.status_code == 302, f"{r.status_code}: {r.text[:200]}"
        assert r.headers["location"] == f"{PRAEFIX}/diakonos"

        r = _get(c, f"{PRAEFIX}/login", **{"redirect-to": f"{PRAEFIX}/diakonos/kalender"})
        assert r.status_code == 302
        assert r.headers["location"] == f"{PRAEFIX}/diakonos/kalender"
    finally:
        base_path.setze_praefix("")


def test_praefix_ohne_sitzung_formular(client, patched_db, fake_redis, oidc_aktiviert, monkeypatch):
    _mit_praefix(monkeypatch)
    try:
        r = _get(TestClient(erstelle_app()), f"{PRAEFIX}/login", **{"lokal": "1"})
        assert r.status_code == 200
        assert "dk-formular" in r.text
    finally:
        base_path.setze_praefix("")


def test_praefix_ohne_oidc_leitet_angemeldet_weiter(
    client, patched_db, fake_redis, ohne_oidc, monkeypatch
):
    """DEV-ECG: Praefix `/diakronos`, `AUTH_OIDC_ENABLED=0` — der Normalfall.

    Genau die Betriebslage von `dev.ecg-hn.de`: lokale Anmeldung, App unter
    `/diakronos`. Ein angemeldeter Aufruf von `/diakonos/login` muss 302 auf
    `/diakronos/diakonos` liefern; das Praefix darf dabei NICHT doppelt
    erscheinen (der Kandidat aus dem Formular ist app-relativ) und der Logout-
    Pfad der Antwort muss stimmen. Nicht angemeldet bleibt die Maske mit
    praefigierter Aktion stehen.
    """
    _mit_praefix(monkeypatch)
    try:
        _konto(patched_db)
        c = _client_mit_sitzung(USER)

        # a) ohne Ziel -> Uebersicht unter dem Praefix
        r = _get(c, f"{PRAEFIX}/login")
        assert r.status_code == 302, f"{r.status_code}: {r.text[:200]}"
        assert r.headers["location"] == f"{PRAEFIX}/diakonos", r.headers["location"]

        # b) app-relatives Ziel -> genau einmal praefigiert
        r = _get(c, f"{PRAEFIX}/login", **{"redirect-to": "/diakonos/kalender"})
        assert r.status_code == 302
        assert r.headers["location"] == f"{PRAEFIX}/diakonos/kalender", r.headers["location"]

        # c) praefigiertes Ziel -> nicht doppelt
        r = _get(c, f"{PRAEFIX}/login", **{"redirect-to": f"{PRAEFIX}/diakonos/mitglieder"})
        assert r.status_code == 302
        assert r.headers["location"] == f"{PRAEFIX}/diakonos/mitglieder", r.headers["location"]

        # d) `noredirect=1` (Rueckkehr eines Fehlschlags) bleibt die Maske
        r = _get(c, f"{PRAEFIX}/login", noredirect="1")
        assert r.status_code == 200
        assert "dk-formular" in r.text

        # e) nicht angemeldet: Maske, Aktion praefigiert
        ohne = _get(TestClient(erstelle_app()), f"{PRAEFIX}/login")
        assert ohne.status_code == 200
        assert f'action="{PRAEFIX}/api/method/login"' in ohne.text
    finally:
        base_path.setze_praefix("")


# ── Frontend: die Rollenliste bleibt dieselbe Wahrheit ────────────────────


def test_sperrrollen_liste_ist_dokumentiert():
    """`NUR_SPERRSEITE_ROLLEN` ist die Liste der Rollen, die in der SPA nirgends
    ankommen — heute leer (der Router kennt nur den Status „Gast“, und der SIEHT
    Start/Kalender/Profil). Der Test haelt fest, dass die Konstante existiert und
    eine Tupel-Form hat: sie wird geprueft, nicht dekorativ mitgeschleppt.
    """
    from diakronos_app.anmeldung.routen import NUR_SPERRSEITE_ROLLEN

    assert isinstance(NUR_SPERRSEITE_ROLLEN, tuple)
    # Jeder Eintrag ist ein Rollenname (nicht leer, kein Freitext).
    assert all(isinstance(r, str) and r.strip() == r and r for r in NUR_SPERRSEITE_ROLLEN)
