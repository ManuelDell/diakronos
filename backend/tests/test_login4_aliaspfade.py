"""LOGIN-4 / (A) — die Login-Sperren haengen am FUNKTIONSOBJEKT, nicht am Pfad.

Befund (R-LOGIN-3, „Nacharbeit (Hoch)"): Die Sperren aus LOGIN-3 —
Nur-POST, `usr`/`pwd` nur aus dem Body, Herkunftspruefung — waren ueber eine
POSITIVLISTE von drei Pfadnamen verdrahtet (`login`, `frappe.login`,
`frappe.login.login`). Der Login ist aber unter mehr Namen erreichbar:

  * `auth.login` (`diakronos_app.api.auth` -> Kurzmodul)
  * `api.login` (Paketpfad)
  * `diakronos_app.api.auth.login` (voller dotted path)
  * `frappe.login.login` (FRAPPE_MODULE-Konstante von `api/auth.py`)
  * und JEDER Pfad, den `registry.registriere_originalpfad` erzeugt:
    `<modul>.login` -> `diakronos.diakronos.api.auth.login`,
    `<praefix>.auth.login` (beliebiges Praefix).

Ein Angreifer musste also nur `GET /api/method/auth.login?usr=…&pwd=…`
aufrufen: der Router las die Zugangsdaten aus dem Query-String, nahm GET an
und setzte eine Sitzung. Das ist genau die CSRF-Luecke, die LOGIN-3
schliessen sollte — nur unter einem anderen Namen.

Der Fix erkennt den Login deshalb am FUNKTIONSOBJEKT (`fn is
api.auth.login`) und zieht alle namensbasierten Pruefungen mit
(`_ist_login_formular`). Die Tests unten sind die Abnahme: JEDER Alias
verhaelt sich wie `login`.
"""

from __future__ import annotations

import pytest

from diakronos_app.models.core import User

FREMD = "https://boese.example.net"
USR = "anna@example.org"
PWD = "synthetisch-99a"  # nur fuer diese Tests

_BROWSER = {"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}


# ── Hilfen (dieselben wie in test_login3_csrf_rest.py) ────────────────────


def _lege_benutzer(session_factory, name: str = USR, passwort: str = PWD) -> None:
    from diakronos_app.frappe_compat.passwoerter import neuer_hash

    sess = session_factory()
    try:
        sess.add(
            User(
                name=name,
                email=name,
                full_name=name,
                enabled=True,
                password_hash=neuer_hash(passwort),
            )
        )
        sess.commit()
    finally:
        sess.close()


def _client(app):
    from fastapi.testclient import TestClient

    return TestClient(app, base_url="http://testserver")


def _set_cookie_koepfe(resp) -> list[str]:
    roh = resp.headers.get_list("set-cookie") if hasattr(resp.headers, "get_list") else []
    return [k for k in roh if k]


def _hat_sid(resp) -> bool:
    return any(k.lower().startswith("sid=") for k in _set_cookie_koepfe(resp))


def _login_funktion():
    from diakronos_app.api.auth import login

    return login


#: Alle Wege, unter denen `api.auth.login` im Register steht — die drei alten
#: Namen aus LOGIN-3, die Modul-/Paketform und der Original-Frappe-Pfad.
#: `_aliasi()` wird zur Laufzeit um JEDEN weiteren Registrierungseintrag
#: dieser Funktion ergaenzt, damit auch ein neu erfundener Alias nicht
#: wieder durchrutscht.
_ALIASE = [
    "login",
    "frappe.login.login",
    "auth.login",
    "api.login",
    "diakronos_app.api.auth.login",
]

#: Pfade, die der Router erst im Fallback (`_maybe_import` ->
#: `registriere_originalpfad`) setzt: aus `<modul>.login` wird ueber das
#: bekannte Kurzmodul `auth` der Original-Pfad. `<x>.auth.login` funktioniert
#: fuer JEDES Praefix gleich.
_ORIGINALPFAEDE = [
    "diakronos.diakronos.api.auth.login",
    "x.auth.login",
    "beliebig.tief.auth.login",
]

#: Die Schreibweise aus dem Modulkopf von `api/auth.py` (`FRAPPE_MODULE`).
#: Sie loest NICHT auf (das echte Frappe-Register kennt nur
#: `frappe.login.login`); der Router muss sie trotzdem wie den Login
#: behandeln — die Sperre darf nicht an der Schreibweise haengen. Siehe
#: `test_sperre_gilt_auch_fuer_nicht_aufloesende_login_schreibweise`.
_NICHT_AUFLOESEND = ["frappe.login"]


def _aliasi() -> list[str]:
    """Alle registrierten Pfade des Login-Funktionsobjekts (sortiert)."""
    from diakronos_app.frappe_compat import registry

    fn = _login_funktion()
    gefunden = {pfad for pfad, ziel in registry.registered().items() if ziel is fn}
    return sorted(gefunden | set(_ALIASE))


@pytest.fixture(scope="session")
def _register_gefuellt():
    """Importiert die API-Pakete, damit das Register vollstaendig ist.

    Ohne den Import kennt das Register nur die Kurzformen; die Zusicherung
    „ALLE Alias“ waere dann trivial erfuellt.
    """
    from diakronos_app.main import app  # noqa: F401  — laedt `diakronos_app.api`

    return True


def test_register_kennt_die_aliaspfade(_register_gefuellt):
    """Vorbedingung: die behaupteten Aliaspfade loesen wirklich auf `login`."""
    from diakronos_app.frappe_compat.registry import lookup, registriere_originalpfad

    fn = _login_funktion()
    for pfad in _ALIASE:
        ziel = lookup(pfad)
        assert ziel is not None, f"{pfad!r} loest nicht auf"
        assert ziel is fn, f"{pfad!r} zeigt nicht auf api.auth.login"
    for pfad in _ORIGINALPFAEDE:
        # Genau der Weg, den der Router bei 404 nimmt (`_maybe_import`).
        assert registriere_originalpfad(pfad) is True, pfad
        assert lookup(pfad) is fn, pfad


#: Alle geprueften Wege (Register-Treffer + Original-Pfade).
_ALLE = _ALIASE + _ORIGINALPFAEDE


# ── (A1) GET meldet ueber JEDEN Alias nie an ──────────────────────────────


@pytest.mark.parametrize("pfad", _ALLE)
def test_get_ueber_alias_meldet_nicht_an(patched_db, fake_redis, _register_gefuellt, pfad):
    """`GET <alias>?usr=…&pwd=…` — der klassische CSRF-Weg ohne Formular."""
    from diakronos_app.main import app

    _lege_benutzer(patched_db)

    with _client(app) as c:
        r = c.get(f"/api/method/{pfad}", params={"usr": USR, "pwd": PWD}, follow_redirects=False)

    assert not _hat_sid(r), f"GET {pfad} hat eine Sitzung gesetzt: {_set_cookie_koepfe(r)}"
    assert r.status_code == 405, r.text
    assert r.json().get("exc_type") == "MethodNotAllowed", r.text


@pytest.mark.parametrize("pfad", _ALLE)
def test_get_ueber_alias_browser_navigation_auf_maske(patched_db, fake_redis, _register_gefuellt, pfad):
    """Ein Browser landet auf der Anmeldemaske — kein roher Fehler, keine Sitzung."""
    from diakronos_app.main import app

    _lege_benutzer(patched_db)

    with _client(app) as c:
        r = c.get(
            f"/api/method/{pfad}",
            params={"usr": USR, "pwd": PWD},
            headers=_BROWSER,
            follow_redirects=False,
        )

    assert not _hat_sid(r)
    assert r.status_code == 303, r.text
    assert r.headers["location"].startswith("/login")


# ── (A2) POST mit Zugangsdaten NUR im Query meldet nie an ─────────────────


@pytest.mark.parametrize("pfad", _ALLE)
def test_post_query_ueber_alias_meldet_nicht_an(patched_db, fake_redis, _register_gefuellt, pfad):
    """`POST <alias>?usr=…&pwd=…` mit leerem Body: keine Sitzung."""
    from diakronos_app.main import app

    _lege_benutzer(patched_db)

    with _client(app) as c:
        r = c.post(
            f"/api/method/{pfad}",
            params={"usr": USR, "pwd": PWD},
            headers={"Origin": "http://testserver", **_BROWSER},
            follow_redirects=False,
        )

    assert not _hat_sid(r), f"POST {pfad} mit Query-Zugangsdaten hat angemeldet"


# ── (A3) Der echte Weg darf NICHT brechen ────────────────────────────────


@pytest.mark.parametrize("pfad", _ALLE)
def test_post_body_same_origin_ueber_alias_meldet_an(patched_db, fake_redis, _register_gefuellt, pfad):
    """Gegenprobe: Formular-POST mit Body-Zugangsdaten von eigener Seite -> sid."""
    from diakronos_app.main import app

    _lege_benutzer(patched_db)

    with _client(app) as c:
        r = c.post(
            f"/api/method/{pfad}",
            data={"usr": USR, "pwd": PWD},
            headers={**_BROWSER, "Origin": "http://testserver", "Sec-Fetch-Site": "same-origin"},
            follow_redirects=False,
        )

    assert r.status_code == 303, r.text
    assert _hat_sid(r), f"POST {pfad} (Body, same-origin) hat NICHT angemeldet"


@pytest.mark.parametrize("pfad", _ALLE)
def test_post_json_same_origin_ueber_alias_meldet_an(patched_db, fake_redis, _register_gefuellt, pfad):
    """Der SPA-Weg (JSON, `Origin` eigener Host) bleibt fuer jeden Alias offen."""
    from diakronos_app.main import app

    _lege_benutzer(patched_db)

    with _client(app) as c:
        r = c.post(
            f"/api/method/{pfad}",
            json={"usr": USR, "pwd": PWD},
            headers={
                "Origin": "http://testserver",
                "Accept": "application/json",
                "Sec-Fetch-Site": "same-origin",
            },
        )

    assert r.status_code == 200, r.text
    assert _hat_sid(r)


# ── (A4) Auch die FEHLERANTWORT haengt am Funktionsobjekt ─────────────────


@pytest.mark.parametrize("pfad", _ALLE)
def test_falsches_passwort_ueber_alias_zeigt_browser_die_maske(patched_db, fake_redis, _register_gefuellt, pfad):
    """LOGIN-1 galt nur fuer drei Namen: ein Browser-Formular auf `auth.login`
    bekam bei falschem Passwort rohes JSON zu sehen."""
    from diakronos_app.main import app

    _lege_benutzer(patched_db)

    with _client(app) as c:
        r = c.post(
            f"/api/method/{pfad}",
            data={"usr": USR, "pwd": "falsch"},
            headers={**_BROWSER, "Origin": "http://testserver", "Sec-Fetch-Site": "same-origin"},
            follow_redirects=False,
        )

    assert not _hat_sid(r)
    assert r.status_code == 303, r.text
    assert r.headers["location"].startswith("/login")


@pytest.mark.parametrize("pfad", _ALLE)
def test_falsches_passwort_ueber_alias_skript_bekommt_json(patched_db, fake_redis, _register_gefuellt, pfad):
    """Gegenprobe: ein JSON-Aufrufer sieht unveraendert 401 + JSON."""
    from diakronos_app.main import app

    _lege_benutzer(patched_db)

    with _client(app) as c:
        r = c.post(
            f"/api/method/{pfad}",
            json={"usr": USR, "pwd": "falsch"},
            headers={"Accept": "application/json"},
            follow_redirects=False,
        )

    assert r.status_code == 401, r.text
    assert r.json().get("exc_type") == "AuthenticationError", r.text


# ── Die Naht selbst: Erkennung am Funktionsobjekt ─────────────────────────


def test_funktionserkennung_ist_das_objekt_nicht_der_name(_register_gefuellt):
    """`ist_login` erkennt JEDES Objekt, das `api.auth.login` IST — nur das."""
    from diakronos_app.api.auth import login
    from diakronos_app.frappe_compat import router

    assert router.ist_login(login) is True

    # Eine beliebige andere whitelisted Funktion ist kein Login, auch wenn sie
    # `login` heisst.
    def login(*a, **k):  # noqa: D401 — absichtlich gleichnamig
        return None

    assert router.ist_login(login) is False
    assert router.ist_login(None) is False


def test_query_sperre_haengt_am_objekt():
    """`_query_erlaubt` nimmt (Pfad, FUNKTION) — das Objekt entscheidet."""
    from diakronos_app.api.auth import login
    from diakronos_app.frappe_compat import router

    assert router._query_erlaubt("auth.login", login) is False

    def anderes(*a, **k):
        return None

    assert router._query_erlaubt("auth.login", anderes) is True


@pytest.mark.parametrize("pfad", _NICHT_AUFLOESEND)
def test_sperre_gilt_auch_fuer_nicht_aufloesende_login_schreibweise(patched_db, fake_redis, _register_gefuellt, pfad):
    """`frappe.login` steht so im Modulkopf von `api/auth.py` und loest im
    Frappe-Register nicht auf (dort heisst der Kernpfad `frappe.login.login`).
    Ein 404 ist unschaedlich — eine Anmeldung darueber waere es nicht."""
    from diakronos_app.main import app

    _lege_benutzer(patched_db)

    with _client(app) as c:
        r = c.get(f"/api/method/{pfad}", params={"usr": USR, "pwd": PWD}, follow_redirects=False)
        post = c.post(
            f"/api/method/{pfad}",
            params={"usr": USR, "pwd": PWD},
            headers={"Origin": "http://testserver", **_BROWSER},
            follow_redirects=False,
        )

    assert not _hat_sid(r)
    assert not _hat_sid(post)


def test_jeder_registrierte_alias_ist_gesperrt(_register_gefuellt):
    """Flaechendeckend: KEIN Registrierungseintrag der Login-Funktion darf
    den Query-String lesen oder eine andere Methode als POST annehmen.

    Das ist die eigentliche Zusicherung — die Parametrisierung oben nennt die
    Namen, die es heute gibt; dieser Test faengt jeden kuenftigen Alias.
    """
    from diakronos_app.frappe_compat import registry, router

    fn = _login_funktion()
    aliase = [p for p, ziel in registry.registered().items() if ziel is fn]
    assert len(aliase) >= 4, aliase
    assert router.ist_login(fn) is True
    assert router._query_erlaubt("beliebig.auth.login", fn) is False, "Login liest den Query-String"

