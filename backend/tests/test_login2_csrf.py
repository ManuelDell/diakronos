"""LOGIN-2 / S2 — Login-CSRF: fremder Origin loggt niemanden ein.

Befund R-LOGIN-1 (N2): `/api/method/login` ist von der CSRF-Pruefung
ausgenommen (dort gibt es noch keine Sitzung) und nahm jeden POST an. Eine
fremde Seite konnte damit per `<form method="post" action="…/api/method/login">`
und dem (dem Angreifer bekannten) Konto eines Opfers DESSEN Browser
anmelden — Session-Fixation von aussen: das Opfer arbeitet danach in einem
Konto, das der Angreifer kontrolliert, ohne es zu merken.

Loesung im Stil des Codes (kein neues Token, kein JavaScript):

  * Ein BROWSER-Formular schickt `Origin` (bei POST immer, ausser bei sehr
    alten Browsern) — dieser Header ist vom Angreifer nicht faelschbar.
  * Fehlt `Origin`, entscheidet `Referer` (aeltere Browser, strenge
    Datenschutzeinstellungen).
  * Fehlt beides, ist es kein Browser: dann bleibt es beim bisherigen
    Verhalten (JSON/XHR-Clients ohne Browser — Apps, Tests, CalDAV-Tools —
    duerfen nicht brechen).
  * Passt der Origin nicht, wird genau wie bei falschem Passwort abgewiesen
    (gleiche Meldung, gleiche Kopfzeilen) — kein Hinweis, dass nur der
    Origin falsch war.
"""

from __future__ import annotations

import pytest

from diakronos_app.models.core import User

FLASH_COOKIE = "dk_login_flash"
FREMD = "https://boese.example.net"
EIGEN = "http://testserver"


def _lege_benutzer(session_factory, name: str, passwort: str, **felder) -> None:
    from diakronos_app.frappe_compat.passwoerter import neuer_hash

    sess = session_factory()
    try:
        sess.add(
            User(
                name=name,
                email=felder.pop("email", name),
                full_name=felder.pop("full_name", name),
                enabled=felder.pop("enabled", True),
                password_hash=neuer_hash(passwort),
            )
        )
        sess.commit()
    finally:
        sess.close()


def _client(app):
    from fastapi.testclient import TestClient

    return TestClient(app)


def _set_cookie_koepfe(resp) -> list[str]:
    roh = resp.headers.get_list("set-cookie") if hasattr(resp.headers, "get_list") else []
    return [k for k in roh if k]


#: Kopfzeilen eines echten Browser-Formulars (LOGIN-2/M2: den Browser-Weg
#: nimmt der Router nur bei `text/html` im `Accept` bzw. `Sec-Fetch-Mode`).
_BROWSER = {"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}


def _formular(c, *, origin=None, referer=None, usr="anna@example.org", pwd="geheim-123"):
    kopf = dict(_BROWSER)
    if origin is not None:
        kopf["Origin"] = origin
    if referer is not None:
        kopf["Referer"] = referer + "/login"
    return c.post(
        "/api/method/login",
        data={"usr": usr, "pwd": pwd, "redirect-to": "/diakonos"},
        headers=kopf,
        follow_redirects=False,
    )


# ── Der Kern: Cross-Site-POST darf nicht anmelden ─────────────────────────


def test_fremder_origin_formular_loggt_nicht_ein(patched_db, fake_redis):
    """DIE Luecke: vorher kam dieser Request mit `sid` zurueck."""
    from diakronos_app.main import app

    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    with _client(app) as c:
        r = _formular(c, origin=FREMD)

    assert not any(k.lower().startswith("sid=") for k in _set_cookie_koepfe(r)), (
        f"Cross-Site-Login hat eine Sitzung gesetzt: {_set_cookie_koepfe(r)}"
    )
    # Und der Browser landet wieder auf der Maske mit neutraler Meldung.
    assert r.status_code == 303
    assert r.headers["location"].startswith("/login?")


def test_fremder_origin_meldung_ist_neutral(patched_db, fake_redis):
    """Kein „Origin falsch“ auf der Maske — sonst waere der Fehlschlag erklaert
    und ein Angreifer koennte ihn gezielt umgehen."""
    from diakronos_app.main import app

    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    with _client(app) as c:
        r = _formular(c, origin=FREMD)
        seite = c.get(r.headers["location"], follow_redirects=False)

    assert "E-Mail-Adresse oder Passwort ist falsch." in seite.text
    assert "Origin" not in seite.text
    assert "Quelle" not in seite.text


def test_fremder_origin_antwort_ist_von_falschem_passwort_nicht_zu_unterscheiden(
    patched_db, fake_redis
):
    from diakronos_app.main import app

    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    with _client(app) as c:
        fremd = _formular(c, origin=FREMD)
        falsch = _formular(c, origin=EIGEN, pwd="falsch")

    assert fremd.status_code == falsch.status_code
    assert fremd.headers["location"] == falsch.headers["location"]
    assert sorted(k.split("=", 1)[0] for k in _set_cookie_koepfe(fremd)) == sorted(
        k.split("=", 1)[0] for k in _set_cookie_koepfe(falsch)
    )


def test_fremder_referer_ohne_origin_ebenso_abgewiesen(patched_db, fake_redis):
    """Aeltere Browser schicken kein `Origin` — dann entscheidet `Referer`."""
    from diakronos_app.main import app

    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    with _client(app) as c:
        r = _formular(c, referer=FREMD)

    assert not any(k.lower().startswith("sid=") for k in _set_cookie_koepfe(r))


def test_origin_schlaegt_referer(patched_db, fake_redis):
    """Beide vorhanden und widerspruechlich: `Origin` gewinnt (der Header ist
    bei POST verlaesslicher)."""
    from diakronos_app.main import app

    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    with _client(app) as c:
        gut = _formular(c, origin=EIGEN, referer=FREMD)
        boese = _formular(c, origin=FREMD, referer=EIGEN)

    assert any(k.lower().startswith("sid=") for k in _set_cookie_koepfe(gut))
    assert not any(k.lower().startswith("sid=") for k in _set_cookie_koepfe(boese))


# ── Eigener Origin: unveraendert bedienbar ────────────────────────────────


def test_eigener_origin_loggt_ein(patched_db, fake_redis):
    from diakronos_app.main import app

    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    with _client(app) as c:
        r = _formular(c, origin=EIGEN)

    assert r.status_code == 303
    assert r.headers["location"].startswith("/diakonos")
    assert any(k.lower().startswith("sid=") for k in _set_cookie_koepfe(r))


def test_eigener_origin_mit_port_und_https(patched_db, fake_redis):
    """Hinter dem Proxy lautet der Origin `https://…`; `X-Forwarded-Proto` des
    Proxys darf daran nichts kaputtmachen.

    LOGIN-3/N-1: der Vergleich prueft seit LOGIN-3 Schema UND Port. Der Host
    des Requests ist hier `testserver` (Port 80), ein `Origin` mit `:8000` ist
    deshalb ein ANDERER Origin — die Aussage dieses Tests von LOGIN-2 („Port
    egal") gilt nicht mehr. Geprueft wird jetzt beides: gleicher Port/Schema
    meldet an, abweichender Port nicht. Der Betriebsfall hinter dem Proxy
    (`Host: dev.example.org`, `X-Forwarded-Proto: https`) steht in
    `test_login3_csrf_rest.py::test_hinter_proxy_https_bleibt_der_login_gueltig`.
    """
    from diakronos_app.main import app

    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    with _client(app) as c:
        gleich = _formular(c, origin="http://testserver:80")
        anderer_port = _formular(c, origin="http://testserver:8000")

    assert gleich.status_code == 303
    assert any(k.lower().startswith("sid=") for k in _set_cookie_koepfe(gleich)), (
        "Origin mit demselben Port muss derselbe Origin sein"
    )
    assert not any(k.lower().startswith("sid=") for k in _set_cookie_koepfe(anderer_port)), (
        "ein abweichender Port ist ein anderer Origin (LOGIN-3/N-1)"
    )


def test_formular_ohne_origin_und_referer_bleibt_erlaubt(patched_db, fake_redis):
    """Kein Browser-Kontext erkennbar (Skript, sehr alter Browser): wie bisher.

    Bricht Abnahme-Tools und Tests nicht — der Schutz greift dort, wo er
    wirkt (Browser senden bei POST immer `Origin`).
    """
    from diakronos_app.main import app

    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    with _client(app) as c:
        r = _formular(c)

    assert r.status_code == 303
    assert any(k.lower().startswith("sid=") for k in _set_cookie_koepfe(r))


# ── JSON/XHR-Clients ohne Browser brechen nicht ───────────────────────────


def test_json_client_mit_fremdem_origin_bleibt_unveraendert(patched_db, fake_redis):
    """Ein JSON-Client (SPA, App, Test) ohne Browser-Kontext bleibt unberuehrt.

    LOGIN-3/H1(c) verschaerft die Regel: sobald ein Herkunftsmerkmal da ist,
    gilt sie fuer JEDEN Content-Type. Ein `fetch` aus einer fremden Seite
    schickt `Origin` — die Anmeldung im Browser des Opfers ist damit genau der
    Fall, den LOGIN-3 schliesst (auch mit `application/json`, denn der
    Angreifer sieht die Antwort nicht, die Anmeldung passiert trotzdem).
    Unberuehrt bleiben Clients OHNE Browser-Header (Apps, curl, Tests) — siehe
    `test_login3_csrf_rest.py::test_client_ohne_browserkopf_bleibt_erlaubt`.
    """
    from diakronos_app.main import app

    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    with _client(app) as c:
        r = c.post(
            "/api/method/login",
            json={"usr": "anna@example.org", "pwd": "geheim-123"},
            headers={"Origin": FREMD, "Accept": "application/json"},
        )

    assert r.status_code == 401, r.text
    assert not any(k.lower().startswith("sid=") for k in _set_cookie_koepfe(r))


def test_json_client_falsches_passwort_mit_fremdem_origin_401(patched_db, fake_redis):
    from diakronos_app.main import app

    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    with _client(app) as c:
        r = c.post(
            "/api/method/login",
            json={"usr": "anna@example.org", "pwd": "falsch"},
            headers={"Origin": FREMD},
        )

    assert r.status_code == 401
    assert r.headers["content-type"].startswith("application/json")


def test_formular_mit_json_accept_und_fremdem_origin_abgewiesen(patched_db, fake_redis):
    """Formular-kodiert mit fremdem `Origin`: abgewiesen, und zwar mit der
    Antwort des falschen Passworts (401 + JSON, weil JSON erwartet wird).

    Ein Skript, das wirklich ohne Browser arbeitet, schickt kein `Origin` und
    bleibt unberuehrt (siehe `test_json_client_mit_fremdem_origin_bleibt_unveraendert`).
    Ein `Origin` heisst: es WAR ein Browser — und dann gilt die Herkunftsregel.
    """
    from diakronos_app.main import app

    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    with _client(app) as c:
        r = c.post(
            "/api/method/login",
            data={"usr": "anna@example.org", "pwd": "geheim-123"},
            headers={"Origin": FREMD, "Accept": "application/json"},
            follow_redirects=False,
        )

    assert r.status_code == 401, r.text
    assert r.headers["content-type"].startswith("application/json")
    assert r.json()["message"] == "Ungueltige Anmeldedaten"
    assert not any(k.lower().startswith("sid=") for k in _set_cookie_koepfe(r))
