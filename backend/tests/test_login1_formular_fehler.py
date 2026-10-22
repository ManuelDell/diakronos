"""LOGIN-1 — Fehlgeschlagene Formular-Anmeldung: verständliche Meldung statt rohem JSON.

Ausgangsbefund (Manuel 2026-10-20): Die serverseitige Anmeldemaske ist ein
klassisches ``<form method="post">``. Bei falschem Passwort antwortete
``/api/method/login`` mit HTTP 401 und rohem JSON — der Browser zeigte genau
das als Seite.

Pflichtverhalten dieser Karte:

  * **L1** Formular-POST + Fehlschlag -> 303 zurück auf ``/login`` mit
    Meldung, Ziel und ``#Hash`` bleiben erhalten, die E-Mail wird
    vorausgefüllt (kurzlebiges Flash-Cookie, NIE in der URL, NIE das
    Passwort).
  * **L2** JSON/XHR-Aufrufe verhalten sich exakt wie bisher (401 + JSON).
  * **L3** Erfolgreicher Formular-Login leitet sauber auf das Ziel weiter.
  * **L4** Ohne JavaScript bedienbar, Meldung ``role="alert"``, Du-Form.

Alle Fehlschlagarten (unbekannt, falsches Passwort, deaktiviert, gesperrt)
bleiben ununterscheidbar — gleiche Meldung, gleiches Cookie.
"""

from __future__ import annotations

from urllib.parse import quote

import pytest

from diakronos_app.frappe_compat import loginversuche
from diakronos_app.models.core import User

MELDUNG = "E-Mail-Adresse oder Passwort ist falsch."

#: Felder des Flash-Cookies (siehe `api/auth.py::_FLASH_COOKIE`).
FLASH_COOKIE = "dk_login_flash"

#: Kopfzeilen eines echten Browser-Formulars. LOGIN-2/M2 hat den Browser-Weg
#: im Router an `text/html` im `Accept` gebunden (vorher genuegte das Fehlen
#: von `application/json`, was form-kodierende Skripte mit `Accept: */*`
#: mitgenommen hat). Diese Tests beschreiben einen BROWSER — also schicken sie
#: auch dessen Kopfzeilen; `httpx` setzt sonst `*/*`.
_BROWSER = {"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}


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
    """Frischer Client MIT leerem Cookie-Jar.

    Wichtig: `app` behaelt die CookieJar zwischen `with`-Bloecken, und der
    Flash-Cookie (Path=/login) wuerde sonst in den naechsten Test lecken.
    """
    from fastapi.testclient import TestClient

    return TestClient(app)


def _felder(html: str, name: str) -> list[str]:
    """Alle ``value``-Werte der versteckten Felder ``<name>`` (in Reihenfolge)."""
    import re

    return re.findall(rf'<input[^>]*name="{name}"[^>]*value="([^"]*)"', html)


def _set_cookie_koepfe(resp) -> list[str]:
    """Alle ``Set-Cookie``-Kopfzeilen einer Antwort (httpx fasst sie zusammen)."""
    roh = resp.headers.get_list("set-cookie") if hasattr(resp.headers, "get_list") else [resp.headers.get("set-cookie", "")]
    return [k for k in roh if k]


# ── L1: Formular-Fehlschlag landet wieder auf der Anmeldeseite ─────────────


def test_formular_falsches_passwort_303_zurueck_auf_login(patched_db, fake_redis):
    """Der Kern der Karte: kein rohes JSON im Browser mehr."""
    from diakronos_app.main import app

    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    with _client(app) as c:
        r = c.post(
            "/api/method/login",
            data={"usr": "anna@example.org", "pwd": "falsch", "redirect-to": "/diakonos"},
            headers=_BROWSER,
            follow_redirects=False,
        )

    assert r.status_code == 303, f"Formular-Fehlschlag muss 303 liefern, war {r.status_code}"
    ziel = r.headers["location"]
    assert ziel.startswith("/login?"), ziel
    # Die E-Mail steht NICHT in der URL (dafuer gibt es den Flash-Cookie).
    assert "anna" not in ziel and "%40" not in ziel, ziel
    # Und der Koerper ist leer statt JSON.
    assert r.text == ""
    assert not r.headers.get("content-type", "").startswith("application/json")


def test_loginseite_zeigt_meldung_als_alert(patched_db, fake_redis):
    """Nach dem Redirect: Meldung ueber dem Formular, `role="alert"`, Du-Form."""
    from diakronos_app.main import app

    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    with _client(app) as c:
        fehl = c.post(
            "/api/method/login",
            data={"usr": "anna@example.org", "pwd": "falsch", "redirect-to": "/diakonos"},
            headers=_BROWSER,
            follow_redirects=False,
        )
        assert fehl.status_code == 303
        # Browser folgt der 303 (Cookies des Clients werden mitgeschickt).
        seite = c.get(fehl.headers["location"], follow_redirects=False)
        c.cookies.delete(FLASH_COOKIE)  # Fixture-Jar nicht in den naechsten Test tragen

    assert seite.status_code == 200, seite.status_code
    html = seite.text
    assert 'role="alert"' in html, "Meldung muss als role=alert ausgezeichnet sein"
    assert MELDUNG in html
    # Du-Form der Meldung; unpersoenliches "Sie" waere ein Rueckfall.
    assert "Sie " not in html.split("<form")[0].split('role="alert"')[-1][:200]


def test_loginseite_nach_fehlschlag_fuellt_die_email_vor(patched_db, fake_redis):
    """Die E-Mail bleibt im Feld — aber NIE das Passwort."""
    from diakronos_app.main import app

    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    with _client(app) as c:
        fehl = c.post(
            "/api/method/login",
            data={"usr": "anna@example.org", "pwd": "falsch-passwort", "redirect-to": "/diakonos"},
            headers=_BROWSER,
            follow_redirects=False,
        )
        seite = c.get(fehl.headers["location"], follow_redirects=False)

    html = seite.text
    assert 'value="anna@example.org"' in html, "E-Mail muss vorausgefuellt sein"
    assert "falsch-passwort" not in html, "Das Passwort darf NIE zurueckkommen"
    # Das Passwortfeld traegt keinen Wert.
    import re

    pwd_feld = re.search(r'<input[^>]*name="pwd"[^>]*>', html)
    assert pwd_feld, "Passwortfeld fehlt"
    assert "value=" not in pwd_feld.group(0), pwd_feld.group(0)


def test_flash_cookie_ist_kurzlebig_und_nicht_lesbar(patched_db, fake_redis):
    """Der Flash-Cookie ist HttpOnly, kurzlebig und nur fuer die Maske gedacht."""
    from diakronos_app.main import app

    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    with _client(app) as c:
        fehl = c.post(
            "/api/method/login",
            data={"usr": "anna@example.org", "pwd": "falsch", "redirect-to": "/diakonos"},
            headers=_BROWSER,
            follow_redirects=False,
        )

    koepfe = [k.lower() for k in _set_cookie_koepfe(fehl)]
    flash = [k for k in koepfe if k.startswith(f"{FLASH_COOKIE}=")]
    assert flash, f"kein Flash-Cookie gesetzt: {koepfe}"
    kopf = flash[0]
    assert "httponly" in kopf
    assert "samesite=lax" in kopf
    assert "path=/login" in kopf, kopf
    assert "max-age=0 " not in kopf + " "
    # Keine Anmeldung, also kein `sid`.
    assert not any(k.startswith("sid=") for k in koepfe), koepfe


def test_meldung_erscheint_nur_einmal(patched_db, fake_redis):
    """Der Flash wird beim Anzeigen verbraucht: Neuladen zeigt keine Meldung mehr.

    Sonst bliebe nach einer spaeteren erfolgreichen Anmeldung/Abmeldung die
    alte Fehlermeldung stehen.
    """
    from diakronos_app.main import app

    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    with _client(app) as c:
        fehl = c.post(
            "/api/method/login",
            data={"usr": "anna@example.org", "pwd": "falsch", "redirect-to": "/diakonos"},
            headers=_BROWSER,
            follow_redirects=False,
        )
        erst = c.get(fehl.headers["location"], follow_redirects=False)
        assert MELDUNG in erst.text
        zweit = c.get("/login", follow_redirects=False)
    assert MELDUNG not in zweit.text, "die Meldung darf nur einmal erscheinen"


def test_ziel_und_hash_bleiben_erhalten(patched_db, fake_redis):
    """`redirect-to` (inkl. `#Hash`) kommt unveraendert zurueck auf die Maske."""
    from diakronos_app.main import app

    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")
    ziel = "/diakonos#/planrahmen/plan/P-1"

    with _client(app) as c:
        fehl = c.post(
            "/api/method/login",
            data={"usr": "anna@example.org", "pwd": "falsch", "redirect-to": quote(ziel, safe="")},
            headers=_BROWSER,
            follow_redirects=False,
        )
        seite = c.get(fehl.headers["location"], follow_redirects=False)

    werte = _felder(seite.text, "redirect-to")
    assert werte, "kein redirect-to-Feld auf der Maske"
    from urllib.parse import unquote

    assert unquote(werte[0]) == ziel, unquote(werte[0])
    # Und das Ziel steht auch im Location-Header (nicht nur im Cookie).
    assert "#" not in fehl.headers["location"], "Fragment gehoert nicht in die URL"
    # Das Fragment reist als ABFRAGE-Parameter (`frag=`) — ein echtes `#` im
    # Location-Header kaeme beim Server nie an. Die Maske haengt es wieder an.
    assert "frag=" in fehl.headers["location"], fehl.headers["location"]
    assert "#" not in fehl.headers["location"]


def test_boses_ziel_wird_auch_im_fehlschlag_abgewiesen(patched_db, fake_redis):
    """Offene Weiterleitung darf der Fehlerpfad nicht neu aufmachen."""
    from diakronos_app.main import app

    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    with _client(app) as c:
        fehl = c.post(
            "/api/method/login",
            data={"usr": "anna@example.org", "pwd": "falsch", "redirect-to": "https://evil.example.net"},
            headers=_BROWSER,
            follow_redirects=False,
        )
        seite = c.get(fehl.headers["location"], follow_redirects=False)

    assert "evil.example.net" not in fehl.headers["location"]
    from urllib.parse import unquote

    werte = [unquote(w) for w in _felder(seite.text, "redirect-to")]
    assert not any("evil.example.net" in w for w in werte), werte


# ── Alle Fehlschlagarten sind ununterscheidbar ────────────────────────────


@pytest.mark.parametrize("fall", ["falsches_passwort", "unbekannt", "deaktiviert", "ohne_hash"])
def test_alle_fehlschlaege_sehen_gleich_aus(patched_db, fake_redis, fall: str):
    """Gleiche Meldung, gleicher Status, gleiches Cookie — fuer JEDEN Fall."""
    from diakronos_app.main import app

    if fall == "deaktiviert":
        _lege_benutzer(patched_db, "anna@example.org", "geheim-123", enabled=False)
        daten = {"usr": "anna@example.org", "pwd": "geheim-123"}
    elif fall == "ohne_hash":
        sess = patched_db()
        sess.add(User(name="ohne@example.org", email="ohne@example.org", enabled=True))
        sess.commit()
        sess.close()
        daten = {"usr": "ohne@example.org", "pwd": "geheim-123"}
    elif fall == "unbekannt":
        daten = {"usr": "niemand@example.org", "pwd": "geheim-123"}
    else:
        _lege_benutzer(patched_db, "anna@example.org", "geheim-123")
        daten = {"usr": "anna@example.org", "pwd": "falsch"}

    with _client(app) as c:
        r = c.post("/api/method/login", data={**daten, "redirect-to": "/diakonos"},
                   headers=_BROWSER, follow_redirects=False)

    assert r.status_code == 303, f"{fall}: {r.status_code}"
    assert r.headers["location"] == "/login?noredirect=1&redirect-to=%2Fdiakonos", f"{fall}: {r.headers['location']}"
    # Cookie-Name und Lebensdauer identisch -> keine Unterscheidung nach aussen.
    koepfe = sorted(k.split("=", 1)[0] for k in _set_cookie_koepfe(r))
    assert koepfe == [FLASH_COOKIE], f"{fall}: {koepfe}"


def test_gesperrter_versuch_gleiche_meldung_und_gleiches_cookie(patched_db, fake_redis, monkeypatch):
    """Die Brute-Force-Bremse verraet sich NICHT: gleiche Meldung, gleiches Cookie."""
    from diakronos_app.main import app

    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    # Bremse zwingend ausloesen (kein echtes Durchprobieren im Test).
    monkeypatch.setattr(loginversuche, "pruefe_und_merke", lambda user, ip: (False, "user"))

    with _client(app) as c:
        r = c.post(
            "/api/method/login",
            data={"usr": "anna@example.org", "pwd": "geheim-123", "redirect-to": "/diakonos"},
            headers=_BROWSER,
            follow_redirects=False,
        )
        seite = c.get(r.headers["location"], follow_redirects=False)

    assert r.status_code == 303
    assert MELDUNG in seite.text
    assert "Zu viele" not in seite.text, "auth.py unterscheidet die Bremse nicht nach aussen"
    assert sorted(k.split("=", 1)[0] for k in _set_cookie_koepfe(r)) == [FLASH_COOKIE]


# ── Auch die Alternative Anmeldeseite (/login) zeigt die Meldung ───────────


def test_auch_login_seite_zeigt_die_meldung(patched_db, fake_redis):
    """`/login` (anmeldung/routen.py) ist der Weg nach dem Redirect und zeigt sie ebenso."""
    from diakronos_app.main import app

    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    with _client(app) as c:
        fehl = c.post(
            "/api/method/login",
            data={"usr": "anna@example.org", "pwd": "falsch", "redirect-to": "/diakonos"},
            headers=_BROWSER,
            follow_redirects=False,
        )
        assert fehl.headers["location"].startswith("/login?")
        seite = c.get(fehl.headers["location"], follow_redirects=False)

    assert seite.status_code == 200
    assert MELDUNG in seite.text
    assert 'role="alert"' in seite.text
    assert 'value="anna@example.org"' in seite.text


# ── L2: JSON/XHR bleibt EXAKT wie bisher ──────────────────────────────────


def test_json_weg_unveraendert_401(patched_db, fake_redis):
    """SPA/Apps/CalDAV-Clients: 401 + JSON, KEIN Redirect, KEIN Flash-Cookie."""
    from diakronos_app.main import app

    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    with _client(app) as c:
        r = c.post("/api/method/login", json={"usr": "anna@example.org", "pwd": "falsch"})

    assert r.status_code == 401
    assert r.headers["content-type"].startswith("application/json")
    assert r.json()["message"] == "Ungueltige Anmeldedaten"
    assert "location" not in r.headers
    assert not any(k.lower().startswith(FLASH_COOKIE) for k in r.headers.get("set-cookie", ""))


def test_json_weg_ohne_body_bleibt_json(patched_db, fake_redis):
    """Ein leerer POST ohne Content-Type ist ebenfalls kein Browser-Formular."""
    from diakronos_app.main import app

    with _client(app) as c:
        r = c.post("/api/method/login")

    assert r.status_code == 401
    assert r.headers["content-type"].startswith("application/json")
    assert "location" not in r.headers


def test_formular_mit_json_accept_wird_wie_bisher_behandelt(patched_db, fake_redis):
    """Ein `fetch` mit `Accept: application/json` bekommt JSON, auch als Formular.

    Sonst wuerde ein Skript-Client nach einem Redirect HTML parsen.
    """
    from diakronos_app.main import app

    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    with _client(app) as c:
        r = c.post(
            "/api/method/login",
            data={"usr": "anna@example.org", "pwd": "falsch"},
            headers={"Accept": "application/json"},
            follow_redirects=False,
        )

    assert r.status_code == 401
    assert r.headers["content-type"].startswith("application/json")


# ── L3: Erfolg leitet sauber weiter ───────────────────────────────────────


def test_erfolg_leitet_aufs_ziel_weiter(patched_db, fake_redis):
    from diakronos_app.main import app

    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    with _client(app) as c:
        r = c.post(
            "/api/method/login",
            data={"usr": "anna@example.org", "pwd": "geheim-123",
                  "redirect-to": quote("/diakonos#/planrahmen/plan/P-1", safe="")},
            headers=_BROWSER,
            follow_redirects=False,
        )

        assert r.status_code == 303
        assert r.headers["location"] == "/diakonos#/planrahmen/plan/P-1", r.headers["location"]
        # Kein Flash-Cookie nach Erfolg — und keine Meldung auf der Zielseite.
        assert not any(k.lower().startswith(FLASH_COOKIE) for k in _set_cookie_koepfe(r))
        ziel = c.get("/diakonos", follow_redirects=False)
        assert ziel.status_code == 200
        assert MELDUNG not in ziel.text


def test_erfolg_nach_fehlschlag_zeigt_keine_alte_meldung(patched_db, fake_redis):
    """Fehlschlag -> Meldung; dann richtig -> Ziel OHNE Meldung."""
    from diakronos_app.main import app

    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    with _client(app) as c:
        fehl = c.post("/api/method/login", data={"usr": "anna@example.org", "pwd": "falsch"},
                      headers=_BROWSER, follow_redirects=False)
        c.get(fehl.headers["location"], follow_redirects=False)
        gut = c.post("/api/method/login",
                     data={"usr": "anna@example.org", "pwd": "geheim-123", "redirect-to": "/diakonos"},
                     follow_redirects=False)
        assert gut.status_code == 303
        ziel = c.get("/diakonos", follow_redirects=False)

    assert MELDUNG not in ziel.text
    assert 'id="app"' in ziel.text


# ── L4: Ohne JavaScript bedienbar ─────────────────────────────────────────


def test_maske_funktioniert_ohne_javascript(patched_db, fake_redis):
    """Formular-POST ohne jedes Skript: 303 + Meldung auf der Folgeseite.

    Der TestClient fuehrt kein JavaScript aus; geprueft wird der reine
    Serverweg (Formular -> Redirect -> HTML mit Meldung).
    """
    from diakronos_app.main import app

    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    with _client(app) as c:
        maske = c.get("/login", follow_redirects=False)
        assert 'method="post"' in maske.text
        assert 'action="/api/method/login"' in maske.text
        r = c.post("/api/method/login", data={"usr": "anna@example.org", "pwd": "falsch"},
                   headers=_BROWSER, follow_redirects=False)
        seite = c.get(r.headers["location"], follow_redirects=False)

    # Die Meldung steht im HTML, nicht in einem Skript.
    kopf, _, rest = seite.text.partition("<script")
    assert MELDUNG in kopf, "Meldung muss serverseitig im HTML stehen"
    assert 'role="alert"' in kopf
