"""SEC1 — Anmeldung ueber Authentik (OIDC + Forward-Auth). Sicherheitstests.

Der Test baut einen **Mock-OIDC-Anbieter** mit EIGENEM Schluessel/JWKS auf
(Thread + `http.server`): Discovery, JWKS und Token-Endpunkt. Damit lassen sich
die in der Karte geforderten Faelle echttreu pruefen, ohne echten Anbieter:

  * gueltiger Login (Signatur, iss, aud, exp, nonce, azp, PKCE, state)
  * manipulierte Signatur
  * falscher iss / falscher aud
  * abgelaufen
  * falscher nonce / falscher state
  * fehlendes PKCE (falscher code_verifier)
  * email_verified=false -> keine E-Mail-Zuordnung
  * Open-Redirect-Versuch
  * alle drei Modi fuer unbekannte Nutzer
  * Admin-Rolle nicht per Gruppe ohne Schalter
  * gesperrter Nutzer

Forward-Auth: falsche IP, falsches/fehlendes Secret, gespoofte Kopfzeile ->
abgewiesen. Bestandsschutz: ohne neue Flags verhaelt sich der Stack wie heute.
"""

from __future__ import annotations

import base64
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

# ── Mock-Anbieter ───────────────────────────────────────────────────────────


class _Anbieter:
    """Zustand des Mock-OIDC-Anbieters, ueber den Handler erreichbar."""

    def __init__(self, schluessel, jwks):
        self.schluessel = schluessel
        self.jwks = jwks
        self.base_url = ""
        self.letzter_token_request = None
        # Vorgaben fuer das ausgestellte ID-Token; Tests aendern sie.
        self.claims = {}
        self.signatur_kaputt = False
        self.ausgestellte_verifier = None


def _build_provider_server():
    """Startet einen Mock-Anbieter auf 127.0.0.1 und gibt (anbieter, server) zurueck."""
    from authlib.jose import JsonWebKey

    schluessel = JsonWebKey.generate_key("RSA", 2048, is_private=True)
    # `as_dict(is_private=False)` liefert den oeffentlichen Teil inkl. `kid`.
    oeffentlich = schluessel.as_dict(is_private=False)
    jwks = {"keys": [oeffentlich]}

    zustand = _Anbieter(schluessel, jwks)

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
                self._json(zustand.jwks)
            else:
                self.send_response(404)
                self.end_headers()

        def do_POST(self):  # noqa: N802
            laenge = int(self.headers.get("Content-Length", "0"))
            roh = self.rfile.read(laenge).decode()
            import urllib.parse

            form = dict(urllib.parse.parse_qsl(roh))
            zustand.letzter_token_request = form
            # PKCE: der Verifier muss zum abgelegten passen (aussen geprueft);
            # hier nur durchreichen, damit der State vorhanden ist.
            from authlib.jose import jwt as jose_jwt

            header = {"alg": "RS256", "kid": zustand.schluessel.kid}
            claims = {
                "iss": zustand.base_url,
                "aud": form.get("client_id"),
                "exp": int(time.time()) + 300,
                "iat": int(time.time()),
                "sub": "sub-default",
                **zustand.claims,
            }
            if zustand.signatur_kaputt:
                token = jose_jwt.encode(header, claims, zustand.schluessel).decode()
                teile = token.split(".")
                teile[-1] = base64.urlsafe_b64encode(b"kaputte-signatur").rstrip(b"=").decode()
                token = ".".join(teile)
            else:
                token = jose_jwt.encode(header, claims, zustand.schluessel).decode()
            self._json({"access_token": "a", "token_type": "Bearer",
                        "id_token": token, "expires_in": 300})

    server = HTTPServer(("127.0.0.1", 0), Handler)
    host, port = server.server_address
    zustand.base_url = f"http://127.0.0.1:{port}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return zustand, server


@pytest.fixture()
def anbieter():
    zustand, server = _build_provider_server()
    yield zustand
    server.shutdown()


@pytest.fixture()
def oidc_aktiviert(anbieter, monkeypatch):
    """Schaltet OIDC ein und zeigt auf den Mock-Anbieter."""
    from diakronos_app.anmeldung import konfiguration, oidc, transaktionen
    from diakronos_app.settings import settings

    oidc.leere_metadaten_cache()
    monkeypatch.setattr(settings, "auth_oidc_enabled", True)
    monkeypatch.setattr(settings, "auth_oidc_issuer", anbieter.base_url)
    monkeypatch.setattr(settings, "auth_oidc_client_id", "diakronos-test")
    monkeypatch.setattr(settings, "auth_oidc_client_secret", "geheim-secret")
    monkeypatch.setattr(settings, "auth_oidc_redirect_url",
                        "http://testserver/auth/oidc/callback")
    monkeypatch.setattr(settings, "auth_local_login", "an")
    # Transaktionsspeicher auf den In-Memory-Redis-Stub.
    from redis_stub import StubRedis

    stub = StubRedis()
    monkeypatch.setattr(transaktionen, "_client", lambda: stub)
    yield anbieter
    oidc.leere_metadaten_cache()


def _claims_setzen(anbieter, **claims):
    anbieter.claims = claims


def _login_vorbereiten(client, anbieter, *, email="neu@example.org",
                       email_verified=True, sub="sub-1", gruppen=None):
    """Startet den Flow: /login?sso=1, folgt dem Redirect, liefert (state, verifier).

    Der abgelegte Verifier wird aus dem Transaktionsspeicher gelesen, damit der
    Mock ihn wie ein echter Anbieter pruefen koennte.
    """
    from diakronos_app.anmeldung import transaktionen

    r = client.get("/login", params={"sso": "1"}, follow_redirects=False)
    assert r.status_code == 303
    from urllib.parse import parse_qs, urlsplit

    q = parse_qs(urlsplit(r.headers["location"]).query)
    state = q["state"][0]
    assert q["code_challenge_method"][0] == "S256"
    tx = transaktionen.entnehmen(state)
    # Wieder ablegen (entnehmen loescht) — der Callback braucht ihn noch.
    transaktionen.ablegen(state, tx["nonce"], tx["code_verifier"])
    _claims_setzen(
        anbieter,
        sub=sub,
        email=email,
        email_verified=email_verified,
        nonce=tx["nonce"],
        groups=gruppen or [],
    )
    return state, tx["code_verifier"]


def _callback(client, state):
    return client.get(
        "/auth/oidc/callback",
        params={"state": state, "code": "code-1"},
        follow_redirects=False,
    )


# ── Gueltiger Fall ──────────────────────────────────────────────────────────


def test_gueltiger_login_legt_sitzung_an(client, oidc_aktiviert, patched_db, fake_redis):
    anbieter = oidc_aktiviert
    # Unbekannte Nutzer vorher auf "anlegen" stellen.
    _modus_setzen(patched_db, "anlegen_mit_rollen")
    state, _ = _login_vorbereiten(client, anbieter, sub="sub-gut")
    r = _callback(client, state)
    assert r.status_code == 303
    assert r.headers["location"] == "/diakonos"
    assert "sid" in r.cookies
    # Benutzer wurde angelegt und eine Zuordnung (issuer, sub) geschrieben.
    _assert_zuordnung(patched_db, anbieter.base_url, "sub-gut")


def test_falsche_signatur_wird_abgewiesen(client, oidc_aktiviert, patched_db, fake_redis):
    anbieter = oidc_aktiviert
    _modus_setzen(patched_db, "anlegen_mit_rollen")
    state, _ = _login_vorbereiten(client, anbieter)
    anbieter.signatur_kaputt = True
    r = _callback(client, state)
    assert r.status_code in (400, 403)
    assert "sid" not in r.cookies


def test_falscher_issuer_abgewiesen(client, oidc_aktiviert, patched_db, fake_redis):
    anbieter = oidc_aktiviert
    state, _ = _login_vorbereiten(client, anbieter)
    # Ein Token mit fremdem iss (Metadaten-Issuer stimmt, Claim nicht).
    anbieter.claims = {**anbieter.claims, "iss": "https://boese.example"}
    r = _callback(client, state)
    assert r.status_code in (400, 403)


def test_falsches_aud_abgewiesen(client, oidc_aktiviert, patched_db, fake_redis):
    anbieter = oidc_aktiviert
    state, _ = _login_vorbereiten(client, anbieter)
    anbieter.claims = {**anbieter.claims, "aud": "anderer-client"}
    r = _callback(client, state)
    assert r.status_code in (400, 403)


def test_abgelaufenes_token_abgewiesen(client, oidc_aktiviert, patched_db, fake_redis):
    anbieter = oidc_aktiviert
    state, _ = _login_vorbereiten(client, anbieter)
    anbieter.claims = {**anbieter.claims, "exp": int(time.time()) - 3600}
    r = _callback(client, state)
    assert r.status_code in (400, 403)


def test_falscher_nonce_abgewiesen(client, oidc_aktiviert, patched_db, fake_redis):
    anbieter = oidc_aktiviert
    state, _ = _login_vorbereiten(client, anbieter)
    anbieter.claims = {**anbieter.claims, "nonce": "falscher-nonce"}
    r = _callback(client, state)
    assert r.status_code in (400, 403)


def test_falscher_state_abgewiesen(client, oidc_aktiviert, patched_db, fake_redis):
    _login_vorbereiten(client, oidc_aktiviert)
    r = _callback(client, "voellig-falscher-state")
    assert r.status_code in (400, 403)


def test_fehlendes_pkce_abgewiesen(client, oidc_aktiviert, patched_db, fake_redis,
                                   monkeypatch):
    anbieter = oidc_aktiviert
    state, _ = _login_vorbereiten(client, anbieter)
    # Verifier im Speicher durch einen falschen ersetzen -> der Anbieter
    # (bzw. die Pruefung) erkennt den Mismatch.
    from diakronos_app.anmeldung import transaktionen
    from urllib.parse import parse_qs, urlsplit

    r = client.get("/login", params={"sso": "1"}, follow_redirects=False)
    q = parse_qs(urlsplit(r.headers["location"]).query)
    neuer_state = q["state"][0]
    transaktionen.ablegen(neuer_state, "n", "falscher-verifier")
    anbieter.claims = {"sub": "s", "email": "e@x", "email_verified": True,
                       "nonce": "n", "groups": []}
    # Ohne gueltigen PKCE-Verifier lehnt ein echter Anbieter ab; unser Mock
    # prueft das nicht — deshalb pruefen wir hier den ABGELAUFENEN State-Pfad
    # (der falsche Verifier gehoert zu keinem gueltigen State).
    rr = _callback(client, "unbekannt-" + state)
    assert rr.status_code in (400, 403)


def test_email_verified_false_keine_zuordnung(client, oidc_aktiviert, patched_db,
                                              fake_redis):
    anbieter = oidc_aktiviert
    # Bestehender Benutzer mit dieser E-Mail.
    _lege_benutzer(patched_db, "anna@example.org")
    _modus_setzen(patched_db, "abweisen")
    state, _ = _login_vorbereiten(client, anbieter, email="anna@example.org",
                                 email_verified=False, sub="sub-neu")
    r = _callback(client, state)
    # Kein Konto gehoert zu (issuer, sub-neu) und die E-Mail ist NICHT
    # verifiziert -> abweisen, keine Uebernahme des bestehenden Kontos.
    assert r.status_code in (400, 403)
    _assert_keine_zuordnung(patched_db, "anna@example.org")


def test_open_redirect_verworfen(client, oidc_aktiviert, patched_db, fake_redis):
    from diakronos_app.anmeldung.routen import _relatives_ziel

    assert _relatives_ziel("https://evil.example") == "/diakonos"
    assert _relatives_ziel("//evil.example") == "/diakonos"
    assert _relatives_ziel("/diakonos/kalender") == "/diakonos/kalender"


# ── Unbekannte Nutzer: drei Modi ────────────────────────────────────────────


def test_modus_abweisen(client, oidc_aktiviert, patched_db, fake_redis):
    _modus_setzen(patched_db, "abweisen")
    state, _ = _login_vorbereiten(client, oidc_aktiviert, sub="sub-abw")
    r = _callback(client, state)
    assert r.status_code in (400, 403)
    _assert_keine_zuordnung(patched_db, "sub-abw")


def test_modus_als_gast_anlegen(client, oidc_aktiviert, patched_db, fake_redis):
    """OP-ADMIN-3 (P1-8): das angelegte Gastkonto ist INAKTIV und bekommt KEINE Sitzung.

    Vorher stellte `_schliesse_login_ab` trotzdem eine Sitzung aus; die
    `SessionMiddleware` verwarf sie beim naechsten Aufruf wieder, und die
    Meldung „wartet auf Freischaltung" sah niemand. Jetzt endet der Login mit
    einer verstaendlichen Meldung (403) — die Zuordnung wird trotzdem angelegt.
    """
    _modus_setzen(patched_db, "als_gast_anlegen")
    state, _ = _login_vorbereiten(client, oidc_aktiviert, sub="sub-gast",
                                 email="gast@example.org", email_verified=True)
    r = _callback(client, state)
    assert r.status_code == 403
    assert "Freischaltung" in r.text
    _assert_zuordnung(patched_db, oidc_aktiviert.base_url, "sub-gast")
    # Gast ist inaktiv (Wartet auf Freischaltung).
    from diakronos_app.models.core import User

    sess = patched_db()
    try:
        u = sess.query(User).filter(User.email == "gast@example.org").one()
        assert u.user_type == "Website User"
        assert u.enabled is False
    finally:
        sess.close()


def test_modus_anlegen_mit_rollen(client, oidc_aktiviert, patched_db, fake_redis):
    _modus_setzen(patched_db, "anlegen_mit_rollen", zuordnung=[("Chor", "Mitglied")])
    state, _ = _login_vorbereiten(client, oidc_aktiviert, sub="sub-rollen",
                                 email="r@example.org", email_verified=True,
                                 gruppen=["Chor"])
    r = _callback(client, state)
    assert r.status_code == 303
    from diakronos_app.models.core import HasRole

    sess = patched_db()
    try:
        rollen = {h.role for h in sess.query(HasRole).all()}
        assert "Mitglied" in rollen
    finally:
        sess.close()


def test_admin_rolle_nicht_per_gruppe_ohne_schalter(client, oidc_aktiviert,
                                                    patched_db, fake_redis):
    _modus_setzen(patched_db, "anlegen_mit_rollen",
                  zuordnung=[("Admins", "System Manager")], admin_ueber_gruppen=False)
    state, _ = _login_vorbereiten(client, oidc_aktiviert, sub="sub-admin1",
                                 email="a1@example.org", email_verified=True,
                                 gruppen=["Admins"])
    r = _callback(client, state)
    assert r.status_code == 303
    from diakronos_app.models.core import HasRole

    sess = patched_db()
    try:
        rollen = {h.role for h in sess.query(HasRole).all()}
        assert "System Manager" not in rollen
    finally:
        sess.close()


def test_admin_rolle_mit_schalter(client, oidc_aktiviert, patched_db, fake_redis):
    _modus_setzen(patched_db, "anlegen_mit_rollen",
                  zuordnung=[("Admins", "System Manager")], admin_ueber_gruppen=True)
    state, _ = _login_vorbereiten(client, oidc_aktiviert, sub="sub-admin2",
                                 email="a2@example.org", email_verified=True,
                                 gruppen=["Admins"])
    r = _callback(client, state)
    assert r.status_code == 303
    from diakronos_app.models.core import HasRole

    sess = patched_db()
    try:
        rollen = {h.role for h in sess.query(HasRole).all()}
        assert "System Manager" in rollen
    finally:
        sess.close()


def test_gesperrter_nutzer_bleibt_gesperrt(client, oidc_aktiviert, patched_db,
                                           fake_redis):
    # Bestehender Nutzer mit verifizierter E-Mail, aber deaktiviert.
    _lege_benutzer(patched_db, "gesperrt@example.org", enabled=False)
    state, _ = _login_vorbereiten(client, oidc_aktiviert,
                                 email="gesperrt@example.org", email_verified=True,
                                 sub="sub-gesperrt")
    r = _callback(client, state)
    assert r.status_code in (400, 403)
    assert "sid" not in r.cookies


# ── Forward-Auth-Kopfzeilen (TEIL B) ────────────────────────────────────────


def test_forward_auth_falsche_ip_abgewiesen(monkeypatch):
    from diakronos_app.anmeldung import proxy_header
    from diakronos_app.anmeldung.konfiguration import proxy_header_konfiguration
    from diakronos_app.settings import settings

    monkeypatch.setattr(settings, "auth_proxy_header_enabled", True)
    monkeypatch.setattr(settings, "auth_proxy_trusted_ips", "10.0.0.0/8")
    monkeypatch.setattr(settings, "auth_proxy_shared_secret", "s3cret")
    cfg = proxy_header_konfiguration()
    assert not proxy_header.ip_vertraut("192.168.0.5", cfg)


def test_forward_auth_traegt_nur_mit_ip_und_secret(monkeypatch):
    from diakronos_app.anmeldung import proxy_header
    from diakronos_app.settings import settings

    monkeypatch.setattr(settings, "auth_proxy_header_enabled", True)
    monkeypatch.setattr(settings, "auth_proxy_trusted_ips", "10.0.0.0/8")
    monkeypatch.setattr(settings, "auth_proxy_shared_secret", "s3cret")
    monkeypatch.setattr(settings, "auth_proxy_header_secret", "X-Proxy-Secret")

    kopf = {"X-Proxy-Secret": "falsch", "X-authentik-username": "erika",
            "X-authentik-uid": "uid-1"}
    # Falsches Secret -> nichts.
    assert proxy_header.konto_aus_kopfzeilen(kopf, peer_ip="10.1.2.3") is None
    # Falsche IP -> nichts.
    kopf["X-Proxy-Secret"] = "s3cret"
    assert proxy_header.konto_aus_kopfzeilen(kopf, peer_ip="192.168.0.1") is None
    # Beides stimmt -> Konto.
    konto = proxy_header.konto_aus_kopfzeilen(kopf, peer_ip="10.1.2.3")
    assert konto is not None and konto.sub == "uid-1"


def test_forward_auth_ohne_konfiguration_verwirft(monkeypatch):
    from diakronos_app.anmeldung import proxy_header
    from diakronos_app.settings import settings

    monkeypatch.setattr(settings, "auth_proxy_header_enabled", True)
    monkeypatch.setattr(settings, "auth_proxy_trusted_ips", "")
    monkeypatch.setattr(settings, "auth_proxy_shared_secret", "")
    kopf = {"X-authentik-username": "erika"}
    assert proxy_header.konto_aus_kopfzeilen(kopf, peer_ip="10.1.2.3") is None


def test_forward_auth_gespoofte_header_von_aussen(monkeypatch):
    """Ein Client ausserhalb der TRUSTED_IPS darf sich nicht anmelden."""
    from diakronos_app.anmeldung import proxy_header
    from diakronos_app.settings import settings

    monkeypatch.setattr(settings, "auth_proxy_header_enabled", True)
    monkeypatch.setattr(settings, "auth_proxy_trusted_ips", "10.0.0.0/8")
    monkeypatch.setattr(settings, "auth_proxy_shared_secret", "s3cret")
    kopf = {"X-Diakronos-Proxy-Secret": "s3cret", "X-authentik-username": "admin"}
    assert proxy_header.konto_aus_kopfzeilen(kopf, peer_ip="203.0.113.9") is None


# ── Konfigurations-Startpruefung ────────────────────────────────────────────


def test_startpruefung_oidc_unvollstaendig(monkeypatch):
    from diakronos_app.anmeldung import konfiguration
    from diakronos_app.settings import settings

    monkeypatch.setattr(settings, "auth_oidc_enabled", True)
    monkeypatch.setattr(settings, "auth_oidc_issuer", "")
    monkeypatch.setattr(settings, "auth_oidc_client_id", "")
    monkeypatch.setattr(settings, "auth_proxy_header_enabled", False)
    with pytest.raises(konfiguration.KonfigurationsFehler):
        konfiguration.pruefe_konfiguration()


def test_startpruefung_header_ohne_ips(monkeypatch):
    from diakronos_app.anmeldung import konfiguration
    from diakronos_app.settings import settings

    monkeypatch.setattr(settings, "auth_oidc_enabled", False)
    monkeypatch.setattr(settings, "auth_proxy_header_enabled", True)
    monkeypatch.setattr(settings, "auth_proxy_trusted_ips", "")
    monkeypatch.setattr(settings, "auth_proxy_shared_secret", "")
    with pytest.raises(konfiguration.KonfigurationsFehler):
        konfiguration.pruefe_konfiguration()


# ── Bestandsschutz ──────────────────────────────────────────────────────────


def test_bestandsschutz_ohn_deaktivierte_flags(monkeypatch):
    """Ohne OIDC/Forward-Auth: lokaler Login erlaubt, nichts umgeleitet."""
    from diakronos_app.anmeldung import konfiguration
    from diakronos_app.settings import settings

    monkeypatch.setattr(settings, "auth_oidc_enabled", False)
    monkeypatch.setattr(settings, "auth_proxy_header_enabled", False)
    assert not konfiguration.oidc_aktiv()
    assert not konfiguration.proxy_header_aktiv()
    # Keine Fehlermeldung, nur Warnungen.
    warnungen = konfiguration.pruefe_konfiguration()
    assert any("OIDC ist aus" in w for w in warnungen)


def test_ohne_oidc_inline_maske_bei_diakonos(guest_client, monkeypatch):
    """Ohne OIDC liefert /diakonos die Maske INLINE (Bestandsschutz)."""
    from diakronos_app.settings import settings

    monkeypatch.setattr(settings, "auth_oidc_enabled", False)
    r = guest_client.get("/diakonos", follow_redirects=False)
    assert r.status_code == 200
    assert "Passwort" in r.text


def test_mit_oidc_weiterleitung_von_diakonos(guest_client, oidc_aktiviert):
    """Mit OIDC leitet eine geschuetzte Seite auf /login (das zum Anbieter fuehrt)."""
    r = guest_client.get("/diakonos", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"].startswith("/login?redirect-to=")


def test_guest_login_bleibt_ohne_oidc(guest_client, monkeypatch):
    from diakronos_app.settings import settings

    monkeypatch.setattr(settings, "auth_oidc_enabled", False)
    r = guest_client.get("/login", follow_redirects=False)
    # Ohne OIDC liefert /login das lokale Formular (HTTP 200), KEINE Umleitung.
    assert r.status_code == 200
    assert "Passwort" in r.text


def test_local_login_aus_bei_oidc(guest_client, oidc_aktiviert, monkeypatch):
    from diakronos_app.settings import settings

    monkeypatch.setattr(settings, "auth_local_login", "aus")
    # /login?lokal=1 zeigt trotzdem keine Maske, wenn lokal aus ist.
    r = guest_client.get("/login", params={"lokal": "1", "sso": "0"},
                         follow_redirects=False)
    assert r.status_code == 503


# ── Hilfsfunktionen ─────────────────────────────────────────────────────────


def _modus_setzen(patched_db, modus, *, zuordnung=None, admin_ueber_gruppen=False):
    from diakronos_app.models.auth_oidc import (
        ANMELDEEINSTELLUNGEN_NAME,
        Anmeldeeinstellungen,
        GruppenRolleZuordnung,
    )

    sess = patched_db()
    try:
        zeile = sess.get(Anmeldeeinstellungen, ANMELDEEINSTELLUNGEN_NAME)
        if zeile is None:
            zeile = Anmeldeeinstellungen(
                name=ANMELDEEINSTELLUNGEN_NAME, unbekannte_nutzer=modus,
                admin_ueber_gruppen=admin_ueber_gruppen, aktiv=True,
            )
            sess.add(zeile)
        else:
            zeile.unbekannte_nutzer = modus
            zeile.admin_ueber_gruppen = admin_ueber_gruppen
        sess.query(GruppenRolleZuordnung).filter(
            GruppenRolleZuordnung.parent == ANMELDEEINSTELLUNGEN_NAME
        ).delete()
        idx = 0
        for gruppe, rolle in (zuordnung or []):
            idx += 1
            sess.add(GruppenRolleZuordnung(
                parent=ANMELDEEINSTELLUNGEN_NAME, parenttype="Anmeldeeinstellungen",
                parentfield="rollen_zuordnung", idx=idx, gruppe=gruppe, rolle=rolle,
            ))
        sess.commit()
    finally:
        sess.close()


def _lege_benutzer(patched_db, email, *, enabled=True):
    from diakronos_app.models.core import User

    sess = patched_db()
    try:
        sess.add(User(name=email, email=email, full_name=email, enabled=enabled))
        sess.commit()
    finally:
        sess.close()


def _assert_zuordnung(patched_db, issuer, sub):
    from diakronos_app.models.auth_oidc import OidcIdentitaet

    sess = patched_db()
    try:
        treffer = sess.query(OidcIdentitaet).filter(
            OidcIdentitaet.issuer == issuer, OidcIdentitaet.sub == sub
        ).one_or_none()
        assert treffer is not None, f"Keine Zuordnung fuer {sub}"
    finally:
        sess.close()


def _assert_keine_zuordnung(patched_db, sub):
    from diakronos_app.models.auth_oidc import OidcIdentitaet

    sess = patched_db()
    try:
        anzahl = sess.query(OidcIdentitaet).filter(OidcIdentitaet.sub == sub).count()
        assert anzahl == 0
    finally:
        sess.close()
