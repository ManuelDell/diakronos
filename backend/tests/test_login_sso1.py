"""LOGIN-SSO1 — Login zeigt Formular UND SSO-Knopf, ohne Zwangsweiterleitung.

ANORDNUNG MANUEL (09.11.): Diakronos muss OHNE Authentik gehen; ist SSO
eingerichtet, soll es auf dem Login-Bildschirm ZUSÄTZLICH die Möglichkeit
geben, sich über Authentik anzumelden.

  * ``AUTH_LOCAL_LOGIN=an``  -> ``/login`` zeigt das Formular UND den Knopf
    „Mit <Anbietername> anmelden“, getrennt durch einen Trenner „oder“.
    KEINE automatische Weiterleitung (vorher leitete die Route bei aktivem OIDC
    IMMER weiter und zeigte das Formular nur noch mit ``?sso=0``).
  * ``nur-admin`` / ``aus``  -> bisheriges Verhalten: Weiterleitung zum
    Anbieter, ``?sso=0`` bleibt der Admin-Notzugang.

Dazu (Zusatz aus dem Live-Befund): alle für Menschen sichtbaren Texte im
Anmeldebereich tragen echte Umlaute — hier als Wächter über die gerenderten
Seiten (``/login``, Fehlerseite, Registrierungsseite), damit die
ASCII-Ersatzschreibung nicht zurückkommt.

Regel 19: Die bestehenden Login-Tests bleiben; hier kommen die Fälle der Karte
dazu (drei Modi × OIDC an/aus, ``redirect-to`` durchgereicht und fremde Ziele
abgewiesen, Trenner im Markup).
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, quote, urlsplit

import pytest

#: ASCII-Ersatzschreibung, die auf keiner Seite mehr auftauchen darf. Absichtlich
#: nur die Wortstämme — ``ueber`` fängt auch „Uebergabe“ und „ueberprueft“.
ERSATZ_MUSTER = re.compile(
    r"moeglich|fuer|ungueltig|geprueft|Rueck|ueber\b", re.IGNORECASE
)


@pytest.fixture()
def oidc_an(monkeypatch):
    """OIDC aktiv, ohne Netzzugriff (geprüft wird nur die Entscheidung)."""
    from diakronos_app.settings import settings

    monkeypatch.setattr(settings, "auth_oidc_enabled", True)
    monkeypatch.setattr(
        settings, "auth_oidc_issuer", "http://localhost:9/application/o/diakronos/"
    )
    monkeypatch.setattr(settings, "auth_oidc_client_id", "diakronos-test")
    monkeypatch.setattr(settings, "auth_oidc_client_secret", "geheim-secret")
    monkeypatch.setattr(
        settings, "auth_oidc_redirect_url", "http://testserver/auth/oidc/callback"
    )
    monkeypatch.setattr(settings, "auth_oidc_anbietername", "Authentik")
    # Tests setzen auth_local_login direkt -> Ausgangswert sichern, sonst Leck in Folgetests
    monkeypatch.setattr(settings, "auth_local_login", settings.auth_local_login)
    yield settings


@pytest.fixture()
def oidc_aus(monkeypatch):
    from diakronos_app.settings import settings

    monkeypatch.setattr(settings, "auth_oidc_enabled", False)
    monkeypatch.setattr(settings, "auth_local_login", settings.auth_local_login)
    yield settings


def _client():
    """Frischer Client OHNE Sitzung (die ``client``-Fixture meldet an)."""
    from fastapi.testclient import TestClient

    from diakronos_app.main import erstelle_app

    return TestClient(erstelle_app())


def _knopf_href(seite: str) -> str:
    """``href`` des Anbieter-Knopfs („Mit … anmelden“) aus dem HTML."""
    m = re.search(r'<a class="dk-knopf[^"]*" href="([^"]+)">Mit ', seite)
    assert m, f"Anbieter-Knopf fehlt in der Seite:\n{seite}"
    return m.group(1).replace("&amp;", "&")


# ── Modus `an`: beides wird gezeigt, nichts wird weitergeleitet ────────────


def test_an_zeigt_formular_und_knopf_ohne_weiterleitung(patched_db, fake_redis, oidc_an):
    oidc_an.auth_local_login = "an"

    with _client() as c:
        r = c.get("/login", follow_redirects=False)

    assert r.status_code == 200, f"`an` darf NICHT weiterleiten, war {r.status_code}"
    assert "location" not in r.headers
    # Beides da: Formular UND Anbieter-Knopf.
    assert 'name="pwd"' in r.text, "lokales Formular fehlt"
    assert "Mit Authentik anmelden" in r.text, "SSO-Knopf fehlt"
    # Und der Trenner zwischen Knopf und Formular.
    assert 'class="dk-oder"' in r.text, "Trenner „oder“ fehlt"
    assert ">oder<" in r.text


def test_an_trenner_steht_zwischen_knopf_und_formular(patched_db, fake_redis, oidc_an):
    """Reihenfolge ist Teil der Aussage: Knopf, Trenner, Formular."""
    oidc_an.auth_local_login = "an"

    with _client() as c:
        seite = c.get("/login", follow_redirects=False).text

    knopf = seite.index("Mit Authentik anmelden")
    trenner = seite.index('class="dk-oder"')
    formular = seite.index('<form class="dk-formular"')
    assert knopf < trenner < formular, (
        f"falsche Reihenfolge: Knopf {knopf}, Trenner {trenner}, Formular {formular}"
    )


def test_an_knopf_traegt_das_ziel_als_redirect_to(patched_db, fake_redis, oidc_an):
    oidc_an.auth_local_login = "an"

    with _client() as c:
        seite = c.get(
            "/login", params={"redirect-to": "/diakonos/kalender"}, follow_redirects=False
        ).text

    href = _knopf_href(seite)
    abfrage = parse_qs(urlsplit(href).query)
    assert urlsplit(href).path == "/login", href
    assert abfrage.get("redirect-to") == ["/diakonos/kalender"], href


def test_an_knopf_traegt_den_hash_als_frag(patched_db, fake_redis, oidc_an):
    """`location.hash` erreicht den Server nie — die Ziel-Seite schickt `frag`."""
    oidc_an.auth_local_login = "an"

    with _client() as c:
        seite = c.get(
            "/login",
            params={"redirect-to": "/diakonos", "frag": "/planrahmen/plan/7"},
            follow_redirects=False,
        ).text

    abfrage = parse_qs(urlsplit(_knopf_href(seite)).query)
    assert abfrage.get("redirect-to") == ["/diakonos"], abfrage
    assert abfrage.get("frag") == ["/planrahmen/plan/7"], abfrage


def test_an_ohne_ziel_nimmt_die_startseite(patched_db, fake_redis, oidc_an):
    oidc_an.auth_local_login = "an"

    with _client() as c:
        seite = c.get("/login", follow_redirects=False).text

    abfrage = parse_qs(urlsplit(_knopf_href(seite)).query)
    assert abfrage.get("redirect-to") == ["/diakonos"], abfrage


@pytest.mark.parametrize(
    "fremd",
    [
        "//evil.example.org",
        "https://evil.example.org/x",
        "/\\evil.example.org",
        "/%2e%2e//evil.example.org",
        "/..#//evil",
        "javascript:alert(1)",
        "",
    ],
)
def test_an_fremde_ziele_werden_abgewiesen(patched_db, fake_redis, oidc_an, fremd):
    """Open Redirect: fremde/ungültige Ziele landen NICHT im Knopf."""
    oidc_an.auth_local_login = "an"

    with _client() as c:
        seite = c.get("/login", params={"redirect-to": fremd}, follow_redirects=False).text

    href = _knopf_href(seite)
    abfrage = parse_qs(urlsplit(href).query)
    assert abfrage.get("redirect-to") == ["/diakonos"], f"{fremd!r} -> {href}"
    assert "evil" not in href, href


def test_an_trenner_fehlt_ohne_zweiten_weg(patched_db, fake_redis, oidc_an, monkeypatch):
    """Bei `aus` gibt es kein Formular — ein „oder“ wäre dann gelogen.

    Geprüft wird die GEBAUTE Seite (ohne Request): die Route selbst liefert bei
    `aus` ohne lokalen Weg die 503-Auskunft.
    """
    from diakronos_app.anmeldung import routen
    from diakronos_app.settings import settings

    monkeypatch.setattr(settings, "auth_local_login", "aus")

    seite = routen.erstelle_anmeldeseite("/diakonos")

    assert 'class="dk-oder"' not in seite, "Trenner ohne zweiten Weg"
    assert 'name="pwd"' not in seite, "Formular bei `aus`"
    assert "Mit Authentik anmelden" in seite, "der Anbieter-Weg muss benannt bleiben"


# ── nur-admin / aus: bisheriges Verhalten ─────────────────────────────────


def test_nur_admin_leitet_weiter(patched_db, fake_redis, oidc_an):
    oidc_an.auth_local_login = "nur-admin"

    with _client() as c:
        r = c.get("/login", follow_redirects=False)

    assert r.status_code == 200, r.status_code
    # Die Hash-Brücke ruft sich selbst mit `sso=1` auf und übernimmt dann der
    # Server (303 zum Anbieter) — hier zählt: KEIN Formular, sondern der Umweg.
    assert "Weiterleitung zur Anmeldung" in r.text, r.text[:400]
    assert 'name="pwd"' not in r.text


def test_nur_admin_startet_direkt_zum_anbieter(patched_db, fake_redis, oidc_an, monkeypatch):
    """`sso=1` startet den Anbieter-Weg (Metadaten hier ersetzt, kein Netz)."""
    from diakronos_app.anmeldung import oidc, transaktionen

    oidc_an.auth_local_login = "nur-admin"
    meta = oidc.OidcMetadaten(
        issuer="http://localhost:9/application/o/diakronos/",
        authorization_endpoint="http://localhost:9/authorize",
        token_endpoint="http://localhost:9/token",
        jwks_uri="http://localhost:9/jwks",
        end_session_endpoint=None,
        id_token_signing_alg_values_supported=("RS256",),
    )
    monkeypatch.setattr(oidc, "hole_metadaten", lambda cfg: meta)
    gemerkt: list = []
    monkeypatch.setattr(
        transaktionen, "ablegen", lambda *a, **kw: gemerkt.append(a)
    )

    with _client() as c:
        r = c.get("/login", params={"sso": "1"}, follow_redirects=False)

    assert r.status_code == 303, r.status_code
    assert r.headers["location"].startswith("http://localhost:9/authorize?"), r.headers
    assert gemerkt, "Transaktion (state/nonce/verifier) wurde nicht abgelegt"


def test_nur_admin_zeigt_die_maske_mit_sso_null(patched_db, fake_redis, oidc_an):
    """Admin-Notzugang bleibt wie heute: `?sso=0` zeigt das Formular."""
    oidc_an.auth_local_login = "nur-admin"

    with _client() as c:
        r = c.get("/login", params={"sso": "0"}, follow_redirects=False)

    assert r.status_code == 200
    assert 'name="pwd"' in r.text
    assert "Mit Authentik anmelden" in r.text
    # Notzugang: der Anbieter ist schon der Hauptweg, kein „oder“.
    assert 'class="dk-oder"' not in r.text


def test_an_zeigt_die_maske_mit_sso_null(patched_db, fake_redis, oidc_an):
    """MT-8b: `an` + OIDC + `sso=0` -> Maske MIT SSO-Knopf, KEINE Weiterleitung.

    Das ist der Rueckweg nach dem Abmelden im Modus `an`: die Maske zeigt
    beides, der Anbieter startet erst auf Klick (``sso=1``).
    """
    oidc_an.auth_local_login = "an"

    with _client() as c:
        r = c.get("/login", params={"sso": "0"}, follow_redirects=False)

    assert r.status_code == 200, r.status_code
    assert "location" not in r.headers, "keine automatische Weiterleitung zum Anbieter"
    assert "Weiterleitung zur Anmeldung" not in r.text
    assert 'name="pwd"' in r.text, "lokales Formular fehlt"
    assert "Mit Authentik anmelden" in r.text, "SSO-Knopf fehlt"
    # Der Knopf startet den Anbieter ausdruecklich (`sso=1`), nicht automatisch.
    assert parse_qs(urlsplit(_knopf_href(r.text)).query).get("sso") == ["1"]


def test_aus_leitet_weiter(patched_db, fake_redis, oidc_an):
    oidc_an.auth_local_login = "aus"

    with _client() as c:
        r = c.get("/login", follow_redirects=False)

    assert r.status_code == 200
    assert "Weiterleitung zur Anmeldung" in r.text
    assert 'name="pwd"' not in r.text


# ── OIDC aus: keine Weiterleitung, kein Knopf, kein Trenner ───────────────


@pytest.mark.parametrize("modus", ["an", "nur-admin", "aus"])
def test_ohne_oidc_immer_formular_ohne_knopf(patched_db, fake_redis, oidc_aus, modus):
    from diakronos_app.settings import settings

    oidc_aus.auth_local_login = modus

    with _client() as c:
        r = c.get("/login", follow_redirects=False)

    assert r.status_code == 200, f"ohne OIDC darf nichts weiterleiten ({modus})"
    assert 'name="pwd"' in r.text, "ohne Anbieter muss das Formular offen sein"
    assert "anmelden</a>" not in r.text, "ohne Anbieter gibt es keinen SSO-Knopf"
    assert 'class="dk-oder"' not in r.text, "ohne zweiten Weg kein Trenner"
    assert settings.auth_oidc_enabled is False


# ── Wächter: echte Umlaute auf den sichtbaren Seiten ──────────────────────


def test_login_seite_ohne_ascii_ersatz(patched_db, fake_redis, oidc_an):
    oidc_an.auth_local_login = "an"

    with _client() as c:
        seite = c.get("/login", follow_redirects=False).text

    treffer = ERSATZ_MUSTER.findall(seite)
    assert not treffer, f"ASCII-Ersatz auf /login: {treffer}"
    assert "für Registrierung und Gastzugriff" in seite


def test_fehlerseite_ohne_ascii_ersatz(patched_db, fake_redis, oidc_an):
    """Die Fehlerseite des Callbacks (Live-Befund: „nicht moeglich“)."""
    oidc_an.auth_local_login = "an"

    with _client() as c:
        r = c.get("/auth/oidc/callback", follow_redirects=False)

    assert r.status_code == 400, r.status_code
    assert "Anmeldung nicht möglich" in r.text
    assert "Ungültige Rückkehr vom Anbieter." in r.text
    treffer = ERSATZ_MUSTER.findall(r.text)
    assert not treffer, f"ASCII-Ersatz auf der Fehlerseite: {treffer}"


def test_aus_seite_ohne_ascii_ersatz(patched_db, fake_redis, oidc_an, monkeypatch):
    """Modus `aus` ohne lokalen Weg: die 503-Seite nennt den Grund.

    MT-8b: Mit ``?sso=0`` liefert die Route seit MT-8 GEWOLLT die
    Abgemeldet-Seite (200) statt der Auskunft. Die 503-Auskunft bleibt fuer
    den lokalen Weg OHNE ``sso=0`` (``?lokal=1``) — beide Seiten werden hier
    auf echte Umlaute geprueft.
    """
    from diakronos_app.settings import settings

    monkeypatch.setattr(settings, "auth_local_login", "aus")

    with _client() as c:
        r = c.get("/login", params={"lokal": "1"}, follow_redirects=False)

    assert r.status_code == 503, r.status_code
    assert "nicht verfügbar" in r.text
    treffer = ERSATZ_MUSTER.findall(r.text)
    assert not treffer, f"ASCII-Ersatz auf der Hinweisseite: {treffer}"


def test_aus_abgemeldet_seite_ohne_ascii_ersatz(patched_db, fake_redis, oidc_an, monkeypatch):
    """MT-8: Modus `aus` + ``sso=0`` -> Abgemeldet-Seite (200), echte Umlaute."""
    from diakronos_app.settings import settings

    monkeypatch.setattr(settings, "auth_local_login", "aus")

    with _client() as c:
        r = c.get("/login", params={"sso": "0"}, follow_redirects=False)

    assert r.status_code == 200, r.status_code
    assert "Du bist abgemeldet." in r.text
    treffer = ERSATZ_MUSTER.findall(r.text)
    assert not treffer, f"ASCII-Ersatz auf der Abgemeldet-Seite: {treffer}"


def test_registrierungsseite_ohne_ascii_ersatz(patched_db, fake_redis):
    """Öffentliche Registrierungsseite (SPA-Rahmen) — sichtbare Texte."""
    from diakronos_app.spa import render_login

    seite = render_login("/diakonos")
    treffer = ERSATZ_MUSTER.findall(seite)
    assert not treffer, f"ASCII-Ersatz in der Anmeldemaske (spa.render_login): {treffer}"


def test_redirect_to_wird_nicht_doppelt_kodiert(patched_db, fake_redis, oidc_an):
    """Der Knopf-Link bleibt ein Klickziel (keine doppelte URL-Kodierung)."""
    oidc_an.auth_local_login = "an"

    with _client() as c:
        seite = c.get(
            "/login", params={"redirect-to": "/diakonos?x=1&y=2"}, follow_redirects=False
        ).text

    href = _knopf_href(seite)
    assert "%252F" not in href, href
    abfrage = parse_qs(urlsplit(href).query)
    assert abfrage.get("redirect-to") == ["/diakonos?x=1&y=2"], href
    # Gegenprobe: die einfache Kodierung ist es, was der Browser zurückschickt.
    assert quote("/diakonos?x=1&y=2", safe="") in href


def test_an_knopfklick_startet_den_anbieter_mit_ziel(
    patched_db, fake_redis, oidc_an, monkeypatch
):
    """Review LOGIN-SSO1: Der Knopf muss bei `an` WIRKEN — sein `href`
    unverändert aufgerufen führt per 303 zum Anbieter, und das geprüfte Ziel
    liegt serverseitig in der Transaktion (nicht wieder die Maske)."""
    from diakronos_app.anmeldung import oidc, transaktionen

    oidc_an.auth_local_login = "an"
    meta = oidc.OidcMetadaten(
        issuer="http://localhost:9/application/o/diakronos/",
        authorization_endpoint="http://localhost:9/authorize",
        token_endpoint="http://localhost:9/token",
        jwks_uri="http://localhost:9/jwks",
        end_session_endpoint=None,
        id_token_signing_alg_values_supported=("RS256",),
    )
    monkeypatch.setattr(oidc, "hole_metadaten", lambda cfg: meta)
    gemerkt: list = []
    monkeypatch.setattr(transaktionen, "ablegen", lambda *a, **kw: gemerkt.append(a))

    with _client() as c:
        seite = c.get(
            "/login", params={"redirect-to": "/diakonos/kalender"}, follow_redirects=False
        ).text
        href = _knopf_href(seite)
        assert parse_qs(urlsplit(href).query).get("sso") == ["1"], href
        r = c.get(href, follow_redirects=False)

    assert r.status_code == 303, (r.status_code, href)
    assert r.headers["location"].startswith("http://localhost:9/authorize?")
    assert gemerkt and gemerkt[0][3].endswith("/diakonos/kalender"), gemerkt
