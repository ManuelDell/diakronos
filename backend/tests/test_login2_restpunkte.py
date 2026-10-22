"""LOGIN-2 / M1, M2, N1 und die Nits aus R-LOGIN-1.

M1 — Fehlerpfad `api/auth.py`: das Ziel muss VOLLSTAENDIG in `redirect-to`
     kodiert werden. Vorher wurde der Frageteil roh an die /login-URL
     gehaengt; `?redirect-to=/diakonos?x=1&y=2` verlor damit x/y, und ein
     Ziel konnte die /login-Parameter (`noredirect`, `frag`, `redirect-to`)
     ueberschreiben.
M2 — `frappe_compat/router.py`: der Browser-Weg (303) nur, wenn der Aufrufer
     wirklich ein Browser ist (`text/html` im `Accept` oder
     `Sec-Fetch-Mode: navigate`). Ein form-kodiertes Skript mit `*/*` bekommt
     wieder 401 + JSON wie in main.
N1 — E-Mail im Flash hoechstens 254 Zeichen (`Set-Cookie` < 4 KB).
Nits — toter Flash-Zweig in `spa.py`, Autofokus nach Fehlschlag aufs
     PASSWORTFELD, Docstrings.
"""

from __future__ import annotations

from urllib.parse import parse_qs, quote, unquote, urlsplit

import pytest

from diakronos_app.models.core import User

FLASH_COOKIE = "dk_login_flash"
MELDUNG = "E-Mail-Adresse oder Passwort ist falsch."


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


def _login_seite_up(kopf: dict) -> dict:
    """Accept/Header eines echten Browser-Formular-POSTs (siehe M2)."""
    return {"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", **kopf}


def _fehlschlag(c, redirect_to: str, **kopf):
    return c.post(
        "/api/method/login",
        data={"usr": "anna@example.org", "pwd": "falsch", "redirect-to": redirect_to},
        headers=_login_seite_up(kopf),
        follow_redirects=False,
    )


# ── M1: Ziel samt Query vollstaendig kodiert ──────────────────────────────


def test_m1_query_des_ziels_bleibt_erhalten(patched_db, fake_redis):
    """`/diakonos?x=1&y=2` kommt vollstaendig im Feld `redirect-to` an."""
    from diakronos_app.main import app

    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    with _client(app) as c:
        r = _fehlschlag(c, "/diakonos?x=1&y=2")
        seite = c.get(r.headers["location"], follow_redirects=False)

    location = r.headers["location"]
    # Die /login-ABFRAGE hat genau zwei Parameter — nichts aus dem Ziel.
    query = parse_qs(urlsplit(location).query)
    assert query["noredirect"] == ["1"]
    assert set(query) == {"noredirect", "redirect-to"}, query
    assert unquote(query["redirect-to"][0]) == "/diakonos?x=1&y=2"

    # Und das versteckte Feld der Maske traegt dasselbe Ziel.
    import re

    werte = re.findall(r'<input[^>]*name="redirect-to"[^>]*value="([^"]*)"', seite.text)
    assert werte
    assert unquote(werte[0]) == "/diakonos?x=1&y=2", unquote(werte[0])


def test_m1_ziel_kann_noredirect_nicht_ueberschreiben(patched_db, fake_redis):
    """`?noredirect=0` im Ziel schaltet die Maske nicht mehr ab (Starlette:
    letzter Wert gewinnt — genau das war die Luecke)."""
    from diakronos_app.main import app

    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    with _client(app) as c:
        r = _fehlschlag(c, "/diakonos?noredirect=0")

    query = parse_qs(urlsplit(r.headers["location"]).query)
    assert query["noredirect"] == ["1"], f"Ziel hat /login ueberschrieben: {r.headers['location']}"
    assert unquote(query["redirect-to"][0]) == "/diakonos?noredirect=0"


def test_m1_ziel_kann_redirect_to_nicht_ueberschreiben(patched_db, fake_redis):
    from diakronos_app.main import app

    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    with _client(app) as c:
        r = _fehlschlag(c, "/diakonos?redirect-to=https://evil.example.net")

    query = parse_qs(urlsplit(r.headers["location"]).query)
    assert len(query["redirect-to"]) == 1, r.headers["location"]
    assert "evil.example.net" not in unquote(query["redirect-to"][0]).split("?")[0]


def test_m1_ziel_kann_frag_nicht_ueberschreiben(patched_db, fake_redis):
    from diakronos_app.main import app

    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    with _client(app) as c:
        r = _fehlschlag(c, "/diakonos?frag=boese")

    query = parse_qs(urlsplit(r.headers["location"]).query)
    assert "frag" not in query, r.headers["location"]


def test_m1_fragment_reist_weiterhin_als_frag(patched_db, fake_redis):
    """Regression: das echte Fragment wird weiterhin ueber `frag` transportiert."""
    from urllib.parse import unquote

    from diakronos_app.main import app

    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    with _client(app) as c:
        r = _fehlschlag(c, quote("/diakonos#/planrahmen/plan/P-1", safe=""))

    query = parse_qs(urlsplit(r.headers["location"]).query)
    assert unquote(query["frag"][0]) == "/planrahmen/plan/P-1"
    assert unquote(query["redirect-to"][0]) == "/diakonos"


def test_m1_offenes_ziel_bleibt_abgewiesen(patched_db, fake_redis):
    from diakronos_app.main import app

    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    with _client(app) as c:
        r = _fehlschlag(c, "https://evil.example.net/x?y=1")

    query = parse_qs(urlsplit(r.headers["location"]).query)
    assert unquote(query["redirect-to"][0]) == "/diakonos"


# ── M2: Browser-Weg nur fuer Browser ──────────────────────────────────────


def test_m2_skript_ohne_html_accept_bekommt_401_json(patched_db, fake_redis):
    """`requests`/curl mit `Accept: */*` und Formular-Body: wie in main."""
    from diakronos_app.main import app

    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    with _client(app) as c:
        r = c.post(
            "/api/method/login",
            data={"usr": "anna@example.org", "pwd": "falsch"},
            headers={"Accept": "*/*"},
            follow_redirects=False,
        )

    assert r.status_code == 401, f"Skript darf nicht auf die Maske umgeleitet werden, war {r.status_code}"
    assert r.headers["content-type"].startswith("application/json")
    assert "location" not in r.headers
    assert not any(k.lower().startswith(FLASH_COOKIE) for k in _set_cookie_koepfe(r))


def test_m2_skript_ohne_accept_header_bekommt_401_json(patched_db, fake_redis):
    """Ohne `Accept` (httpx setzt `*/*`) darf kein Browser-Weg greifen."""
    from diakronos_app.main import app

    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    with _client(app) as c:
        r = c.post(
            "/api/method/login",
            data={"usr": "anna@example.org", "pwd": "falsch"},
            follow_redirects=False,
        )

    assert r.status_code == 401
    assert r.headers["content-type"].startswith("application/json")


def test_m2_browser_accept_bekommt_maske(patched_db, fake_redis):
    from diakronos_app.main import app

    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    with _client(app) as c:
        r = c.post(
            "/api/method/login",
            data={"usr": "anna@example.org", "pwd": "falsch"},
            headers={"Accept": "text/html,application/xhtml+xml,*/*;q=0.8"},
            follow_redirects=False,
        )

    assert r.status_code == 303
    assert r.headers["location"].startswith("/login?")


def test_m2_sec_fetch_navigate_ohne_accept_greift_ebenfalls(patched_db, fake_redis):
    """Manche Clients schicken `*/*`; ein echter Navigations-Request nennt
    `Sec-Fetch-Mode: navigate`."""
    from diakronos_app.main import app

    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    with _client(app) as c:
        r = c.post(
            "/api/method/login",
            data={"usr": "anna@example.org", "pwd": "falsch"},
            headers={"Accept": "*/*", "Sec-Fetch-Mode": "navigate"},
            follow_redirects=False,
        )

    assert r.status_code == 303


def test_m2_fetch_aus_browser_bleibt_json(patched_db, fake_redis):
    """`fetch` mit `Accept: application/json` (die SPA): unveraendert 401."""
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


# ── N1: Flash-Cookie bleibt klein ─────────────────────────────────────────


def test_n1_lange_email_bleibt_unter_4kb(patched_db, fake_redis):
    """6000 Zeichen `usr` -> `Set-Cookie` deutlich unter 4096 Bytes."""
    from diakronos_app.main import app

    with _client(app) as c:
        r = c.post(
            "/api/method/login",
            data={"usr": "a" * 6000, "pwd": "egal"},
            headers=_login_seite_up({}),
            follow_redirects=False,
        )

    assert r.status_code == 303
    flash = [k for k in _set_cookie_koepfe(r) if k.lower().startswith(FLASH_COOKIE)]
    assert flash, _set_cookie_koepfe(r)
    assert len(flash[0]) < 4096, f"Set-Cookie ist {len(flash[0])} Bytes — Browser verwerfen ihn"


def test_n1_lange_email_wird_gekuerzt_und_bleibt_lesbar(patched_db, fake_redis):
    """Der Anfang bleibt erhalten; der Cookie ist ausstellbar und lesbar."""
    from diakronos_app.anmeldung import flash
    from diakronos_app.main import app

    with _client(app) as c:
        r = c.post(
            "/api/method/login",
            data={"usr": "k" * 6000, "pwd": "egal"},
            headers=_login_seite_up({}),
            follow_redirects=False,
        )
        wert = [k for k in _set_cookie_koepfe(r) if k.lower().startswith(FLASH_COOKIE)][0]
        roh = wert.split(";")[0].split("=", 1)[1]
        gelesen = flash.lese_flash({FLASH_COOKIE: roh})

    assert gelesen is not None
    email, leer = gelesen
    assert leer is False
    assert len(email) <= 254
    assert email.startswith("kkk")


def test_n1_normale_email_unveraendert(patched_db, fake_redis):
    from diakronos_app.main import app

    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    with _client(app) as c:
        r = _fehlschlag(c, "/diakonos")
        seite = c.get(r.headers["location"], follow_redirects=False)

    assert 'value="anna@example.org"' in seite.text


# ── Nits: Autofokus auf dem Passwortfeld ──────────────────────────────────


def test_autofokus_liegt_nach_fehlschlag_auf_dem_passwortfeld(patched_db, fake_redis):
    """Die E-Mail ist schon gefuellt — der naechste Griff gehoert ins Passwort."""
    import re

    from diakronos_app.main import app

    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    with _client(app) as c:
        r = _fehlschlag(c, "/diakonos")
        seite = c.get(r.headers["location"], follow_redirects=False)

    html = seite.text
    pwd_feld = re.search(r'<input[^>]*name="pwd"[^>]*>', html)
    usr_feld = re.search(r'<input[^>]*name="usr"[^>]*>', html)
    assert pwd_feld and usr_feld
    assert "autofocus" in pwd_feld.group(0), "Passwortfeld muss den Fokus bekommen"
    assert "autofocus" not in usr_feld.group(0), "E-Mail-Feld darf ihn nicht behalten"


def test_autofokus_auf_spa_maske_ebenso(patched_db, fake_redis, monkeypatch):
    """Dieselbe Regel auf der Inline-Maske (`spa.render_login`, ohne OIDC)."""
    import re

    from diakronos_app.main import app
    from diakronos_app.settings import settings

    monkeypatch.setattr(settings, "auth_oidc_enabled", False)
    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    with _client(app) as c:
        r = c.post(
            "/api/method/login",
            data={"usr": "anna@example.org", "pwd": "falsch"},
            headers=_login_seite_up({}),
            follow_redirects=False,
        )
        seite = c.get(r.headers["location"], follow_redirects=False)

    html = seite.text
    pwd_feld = re.search(r'<input[^>]*name="pwd"[^>]*>', html)
    assert pwd_feld, "Passwortfeld fehlt"
    assert "autofocus" in pwd_feld.group(0), pwd_feld.group(0)


# ── Nit: toter Flash-Zweig in spa.py ──────────────────────────────────────


def test_spa_seite_schickt_kein_flash_loeschcookie(patched_db, fake_redis, monkeypatch, tmp_path):
    """Der Flash-Cookie hat `Path=/login` und kommt auf SPA-Pfaden nie an.

    Der Zweig in `spa._login_maske` war deshalb tot — er schickte aber auf
    jeder Anmelde-Antwort ein Loesch-Set-Cookie mit. Hier wird geprueft, dass
    auf der SPA-Maske kein `dk_login_flash`-Kopf mehr entsteht.

    `tmp_path` als leerer Build-Ordner: der Test laeuft auch, wenn im Image
    zufaellig kein `frontend/dist` liegt (dann antwortet `/diakonos` mit 503
    statt der Maske — geprueft wird hier nur der Cookie).
    """
    from diakronos_app import spa as spa_mod
    from diakronos_app.main import app
    from diakronos_app.settings import settings

    monkeypatch.setattr(settings, "auth_oidc_enabled", False)
    monkeypatch.setattr(spa_mod, "SPA_DIST", tmp_path)

    with _client(app) as c:
        r = c.get("/diakonos", follow_redirects=False)

    assert r.status_code in (200, 503), r.status_code
    assert not any(
        k.lower().startswith(FLASH_COOKIE) for k in _set_cookie_koepfe(r)
    ), "die SPA-Maske darf den Flash-Cookie nicht anfassen"
