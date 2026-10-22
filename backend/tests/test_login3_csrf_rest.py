"""LOGIN-3 — Login-CSRF vollstaendig schliessen (Opus-Review R-LOGIN-2, H1 + N-1).

Befund H1: Die Herkunftspruefung aus LOGIN-2 galt nur fuer
`application/x-www-form-urlencoded`/`multipart`. Damit blieben drei Wege offen,
auf denen eine fremde Seite den Browser eines Opfers OHNE dessen Zutun in ein
Konto einloggen konnte (Session-Fixation von aussen):

  (a) GET-Anmeldung. `/api/method/{path}` nahm auch GET an, das Frappe-Protokoll
      erlaubt Argumente im Query-String. Ein `<img src="/api/method/login?usr=…">`
      oder ein Link genuegte — und GET traegt weder `Origin` (Navigation ohne
      Formular) noch faellt es unter die CSRF-Middleware.
  (b) `usr`/`pwd` aus Query-Parametern: derselbe Weg, ohne GET zu brauchen —
      `POST /api/method/login?usr=…&pwd=…` mit leerem Body.
  (c) Fremder Origin mit einem Content-Type, der nicht als "Formular" erkannt
      wurde: `<form enctype="text/plain">` schickt `text/plain`, und ein
      `fetch` mit `Content-Type: text/plain` galt als "kein Browser" (weil
      CORS es nicht einmal vorab pruefen muss). Beide kamen an der
      Herkunftspruefung vorbei. Ebenso fehlte `Sec-Fetch-Site: cross-site` —
      den Header setzt der Browser selbst und er ist der einzige Hinweis, den
      ein `<form>` ohne `enctype` (multipart) zuverlaessig mitbringt.

Was ausdruecklich UNVERAENDERT bleiben muss (Kartentext H1 d):

  * der JSON-Login der eigenen SPA (Same-Origin),
  * Clients ohne Browser-Header (Apps, curl, `requests`, Abnahme-Tools).

N-1: Der Herkunftsvergleich prueft Schema UND Port. `https://dev.example.org`
ist nicht `http://dev.example.org`, und `http://testserver:8000` ist nicht
`http://testserver`. Hinter dem Reverse-Proxy bleibt der legitime Login
gueltig, weil der Proxy `Host` durchreicht (`proxy_set_header Host $http_host`)
und `X-Forwarded-Proto: https` meldet.
"""

from __future__ import annotations

import pytest

from diakronos_app.models.core import User

FREMD = "https://boese.example.net"
EIGEN = "http://testserver"
USR = "anna@example.org"
PWD = "testpasswort-4711"

#: Kopfzeilen eines echten Browser-Formulars (LOGIN-2/M2: den Browser-Weg —
#: 303 zur Anmeldemaske statt 401+JSON — nimmt der Router nur bei `text/html`
#: im `Accept` bzw. `Sec-Fetch-Mode: navigate`).
_BROWSER = {"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}


def _lege_benutzer(session_factory, name: str = USR, passwort: str = PWD, **felder) -> None:
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


def _client(app, *, base_url: str = "http://testserver"):
    from fastapi.testclient import TestClient

    return TestClient(app, base_url=base_url)


def _set_cookie_koepfe(resp) -> list[str]:
    roh = resp.headers.get_list("set-cookie") if hasattr(resp.headers, "get_list") else []
    return [k for k in roh if k]


def _hat_sid(resp) -> bool:
    return any(k.lower().startswith("sid=") for k in _set_cookie_koepfe(resp))


# ── (a) GET meldet nie an ──────────────────────────────────────────────────


def test_get_mit_query_meldet_nicht_an(patched_db, fake_redis):
    """DIE Luecke (a): `<img src="/api/method/login?usr=…&pwd=…">` bzw. ein Link.

    Eine GET-Navigation traegt keinen `Origin` — die Herkunftspruefung aus
    LOGIN-2 konnte diesen Weg gar nicht sehen. Deshalb gilt hier: GET auf den
    Login-Endpunkt meldet NIEMALS an.
    """
    from diakronos_app.main import app

    _lege_benutzer(patched_db)

    with _client(app) as c:
        r = c.get(
            "/api/method/login",
            params={"usr": USR, "pwd": PWD},
            headers=_BROWSER,
            follow_redirects=False,
        )

    assert not _hat_sid(r), f"GET-Login hat eine Sitzung gesetzt: {_set_cookie_koepfe(r)}"
    # Ein Browser (Navigation) landet auf der Anmeldemaske, kein roher Fehler.
    assert r.status_code in (303, 405), r.text
    if r.status_code == 303:
        assert r.headers["location"].startswith("/login")


def test_get_ohne_browserkopf_meldet_nicht_an(patched_db, fake_redis):
    """Auch ein Skript bekommt per GET keine Sitzung — kein Sonderweg."""
    from diakronos_app.main import app

    _lege_benutzer(patched_db)

    with _client(app) as c:
        r = c.get("/api/method/login", params={"usr": USR, "pwd": PWD})

    assert not _hat_sid(r)
    assert r.status_code == 405, r.text
    assert r.json()["exc_type"] == "MethodNotAllowed"


def test_get_meldet_nicht_an_wenn_eine_sitzung_liegt(patched_db, fake_redis):
    """Mit liegendem `sid` bleibt GET wirkungslos (kein Kontowechsel per Link)."""
    from diakronos_app.main import app

    _lege_benutzer(patched_db)
    _lege_benutzer(patched_db, name="bea@example.org", email="bea@example.org")

    with _client(app) as c:
        post = c.post(
            "/api/method/login",
            data={"usr": USR, "pwd": PWD},
            headers={**_BROWSER, "Origin": EIGEN},
            follow_redirects=False,
        )
        assert _hat_sid(post)
        # Neu gesetzte Sitzung merken: ein GET darf sie NICHT ersetzen.
        davor = [k for k in _set_cookie_koepfe(post) if k.lower().startswith("sid=")]
        get = c.get(
            "/api/method/login",
            params={"usr": "bea@example.org", "pwd": PWD},
            headers=_BROWSER,
            follow_redirects=False,
        )

    assert not _hat_sid(get)
    assert davor


# ── (b) usr/pwd nur aus dem Body ───────────────────────────────────────────


def test_query_parameter_werden_ignoriert(patched_db, fake_redis):
    """POST mit leeren Zugangsdaten im Body, alles im Query: keine Anmeldung."""
    from diakronos_app.main import app

    _lege_benutzer(patched_db)

    with _client(app) as c:
        r = c.post(
            "/api/method/login",
            params={"usr": USR, "pwd": PWD},
            headers={**_BROWSER, "Origin": EIGEN},
            follow_redirects=False,
        )

    assert not _hat_sid(r), "Query-Parameter haben angemeldet"


def test_query_parameter_ueberschreiben_den_body_nicht(patched_db, fake_redis):
    """Body gewinnt bzw. Query wird gar nicht erst gelesen.

    Gegenprobe zum Vorigen: hier steht das RICHTIGE Passwort im Body und ein
    falsches im Query — angemeldet wird trotzdem (Body), nie umgekehrt.
    """
    from diakronos_app.main import app

    _lege_benutzer(patched_db)

    with _client(app) as c:
        r = c.post(
            "/api/method/login",
            params={"usr": "fremd@example.org", "pwd": "falsch"},
            data={"usr": USR, "pwd": PWD},
            headers={**_BROWSER, "Origin": EIGEN},
            follow_redirects=False,
        )

    assert _hat_sid(r)


def test_andere_endpunkte_lesen_query_weiter(patched_db, fake_redis):
    """Die Sperre gilt NUR fuer den Login — kein Nebeneffekt auf andere Endpunkte.

    Gegenprobe an einem echten Nachbar-Endpunkt: `check_permission` ist
    registriert und nimmt `doctype`/`docname`/`permission_type`. Kamen die
    Query-Parameter nicht mehr an, antwortete der Router mit 417 („Falsche
    Argumente") — erwartet wird 401 (kein Login) bzw. 200.
    """
    from diakronos_app.main import app

    with _client(app) as c:
        r = c.get(
            "/api/method/check_permission",
            params={"doctype": "Mitglied", "docname": "x", "permission_type": "read"},
            follow_redirects=False,
        )

    assert r.status_code in (200, 401), r.text
    assert r.json().get("exc_type") != "ValidationError", r.text


def test_router_argumente_aus_query_nur_beim_login_ignoriert():
    """Die Regel sitzt im Router und nur dort — Unit-Ebene der Gegenprobe.

    LOGIN-4/A: Die Entscheidung haengt am FUNKTIONSOBJEKT, nicht am
    Pfadnamen. Deshalb wird hier die Funktion uebergeben, die die jeweilige
    Schreibweise im Register trifft (fuer die drei alten Namen ist das
    `api.auth.login`). Die flaechendeckende Alias-Abnahme steht in
    `test_login4_aliaspfade.py`.
    """
    from diakronos_app.api.auth import login
    from diakronos_app.frappe_compat.registry import lookup
    from diakronos_app.frappe_compat.router import _query_erlaubt

    assert _query_erlaubt("login", login) is False
    assert _query_erlaubt("frappe.login", lookup("frappe.login")) is False
    assert _query_erlaubt("frappe.login.login", lookup("frappe.login.login")) is False
    for pfad in ("frappe.boot", "diakronos.diakonos.api.session.check_permission", "logout"):
        assert _query_erlaubt(pfad, lookup(pfad)) is True, pfad


# ── (c) Herkunft gilt fuer JEDEN Content-Type + Sec-Fetch-Site ─────────────


def test_text_plain_formular_von_fremder_seite(patched_db, fake_redis):
    """`<form enctype="text/plain">` schickt `text/plain` — vorher ungeprueft."""
    from diakronos_app.main import app

    _lege_benutzer(patched_db)

    with _client(app) as c:
        r = c.post(
            "/api/method/login",
            content=f"usr={USR}\r\npwd={PWD}\r\n".encode(),
            headers={**_BROWSER, "Origin": FREMD, "Content-Type": "text/plain"},
            follow_redirects=False,
        )

    assert not _hat_sid(r), "text/plain-Formular von fremder Seite hat angemeldet"


def test_multipart_formular_von_fremder_seite(patched_db, fake_redis):
    """`multipart/form-data` ist der Standard eines `<form>` ohne `enctype`."""
    from diakronos_app.main import app

    _lege_benutzer(patched_db)

    with _client(app) as c:
        r = c.post(
            "/api/method/login",
            files={"usr": (None, USR), "pwd": (None, PWD)},
            headers={**_BROWSER, "Origin": FREMD},
            follow_redirects=False,
        )

    assert not _hat_sid(r), "multipart-Formular von fremder Seite hat angemeldet"


def test_json_mit_fremdem_origin_und_browserkopf(patched_db, fake_redis):
    """Ein Browser-`fetch` mit `Content-Type: text/plain` (CORS-simpler Request)
    schickt `Origin` — der muss gelten, egal welcher Content-Type."""
    from diakronos_app.main import app

    _lege_benutzer(patched_db)

    with _client(app) as c:
        r = c.post(
            "/api/method/login",
            content=f'{{"usr": "{USR}", "pwd": "{PWD}"}}'.encode(),
            headers={
                "Origin": FREMD,
                "Content-Type": "text/plain",
                "Accept": "application/json",
                "Sec-Fetch-Site": "cross-site",
                "Sec-Fetch-Mode": "cors",
            },
            follow_redirects=False,
        )

    assert not _hat_sid(r), "text/plain-fetch von fremder Seite hat angemeldet"


def test_sec_fetch_site_cross_site_wird_abgewiesen(patched_db, fake_redis):
    """Der Header, den der Browser selbst setzt — gilt auch ohne Origin/Referer.

    Genau der Fall, den ein Angreifer nicht faelschen kann: eine fremde Seite
    kann `Origin` per `referrerpolicy=no-referrer` und einen Umweg zwar
    verwischen, `Sec-Fetch-Site` setzt aber der Browser.
    """
    from diakronos_app.main import app

    _lege_benutzer(patched_db)

    with _client(app) as c:
        r = c.post(
            "/api/method/login",
            data={"usr": USR, "pwd": PWD},
            headers={**_BROWSER, "Sec-Fetch-Site": "cross-site"},
            follow_redirects=False,
        )

    assert not _hat_sid(r), "Sec-Fetch-Site: cross-site hat angemeldet"


def test_sec_fetch_site_same_origin_meldet_an(patched_db, fake_redis):
    """Gegenprobe: `same-origin` ist der Normalfall der eigenen SPA."""
    from diakronos_app.main import app

    _lege_benutzer(patched_db)

    with _client(app) as c:
        r = c.post(
            "/api/method/login",
            json={"usr": USR, "pwd": PWD},
            headers={"Sec-Fetch-Site": "same-origin", "Sec-Fetch-Mode": "cors"},
            follow_redirects=False,
        )

    assert r.status_code == 200, r.text
    assert _hat_sid(r)


# ── (d) Was unveraendert bleiben MUSS ──────────────────────────────────────


def test_same_origin_json_login_der_spa(patched_db, fake_redis):
    """Der echte Weg der SPA: `fetch` mit JSON, `Origin` = eigener Host."""
    from diakronos_app.main import app

    _lege_benutzer(patched_db)

    with _client(app) as c:
        r = c.post(
            "/api/method/login",
            json={"usr": USR, "pwd": PWD},
            headers={
                "Origin": EIGEN,
                "Accept": "application/json",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-Mode": "cors",
            },
        )

    assert r.status_code == 200, r.text
    assert r.json()["message"] == "Logged In"
    assert _hat_sid(r)


def test_same_origin_formular_meldet_an(patched_db, fake_redis):
    """Die serverseitige Anmeldemaske (eigenes Formular, eigenes Origin)."""
    from diakronos_app.main import app

    _lege_benutzer(patched_db)

    with _client(app) as c:
        r = c.post(
            "/api/method/login",
            data={"usr": USR, "pwd": PWD, "redirect-to": "/diakonos"},
            headers={**_BROWSER, "Origin": EIGEN, "Sec-Fetch-Site": "same-origin"},
            follow_redirects=False,
        )

    assert r.status_code == 303
    assert r.headers["location"].startswith("/diakonos")
    assert _hat_sid(r)


@pytest.mark.parametrize("kopf", [{}, {"User-Agent": "python-requests/2.32"}])
def test_client_ohne_browserkopf_bleibt_erlaubt(patched_db, fake_redis, kopf):
    """Apps, curl, `requests`, Abnahme-Tools: kein Origin, kein Sec-Fetch-*.

    Der Schutz greift dort, wo er wirkt (Browser setzen die Header selbst);
    ein Client ohne Browser-Kontext bekommt unveraendert eine Sitzung.
    """
    from diakronos_app.main import app

    _lege_benutzer(patched_db)

    with _client(app) as c:
        r = c.post(
            "/api/method/login",
            json={"usr": USR, "pwd": PWD},
            headers=kopf,
            follow_redirects=False,
        )

    assert r.status_code == 200, r.text
    assert _hat_sid(r)


# ── N-1: Schema UND Port im Herkunftsvergleich ─────────────────────────────


def test_gleicher_host_anderes_schema_ist_fremd(patched_db, fake_redis):
    """`http://` ist nicht `https://` — sonst waere ein Downgrade-Origin eigen."""
    from diakronos_app.main import app

    _lege_benutzer(patched_db)

    with _client(app) as c:
        r = c.post(
            "/api/method/login",
            data={"usr": USR, "pwd": PWD},
            headers={**_BROWSER, "Origin": "https://testserver"},
            follow_redirects=False,
        )

    assert not _hat_sid(r), "Origin mit abweichendem Schema galt als eigener Host"


def test_gleicher_host_anderer_port_ist_fremd(patched_db, fake_redis):
    """`http://testserver:9999` ist ein ANDERER Origin als `http://testserver`."""
    from diakronos_app.main import app

    _lege_benutzer(patched_db)

    with _client(app) as c:
        r = c.post(
            "/api/method/login",
            data={"usr": USR, "pwd": PWD},
            headers={**_BROWSER, "Origin": "http://testserver:9999"},
            follow_redirects=False,
        )

    assert not _hat_sid(r), "Origin mit abweichendem Port galt als eigener Host"


def test_gleicher_port_wie_der_host_ist_eigen(patched_db, fake_redis):
    """Expliziter Port gleich dem Host-Port: eigener Origin."""
    from diakronos_app.main import app

    _lege_benutzer(patched_db)

    with _client(app) as c:
        r = c.post(
            "/api/method/login",
            data={"usr": USR, "pwd": PWD},
            headers={**_BROWSER, "Origin": "http://testserver:80"},
            follow_redirects=False,
        )

    assert r.status_code == 303
    assert _hat_sid(r)


def test_hinter_proxy_https_bleibt_der_login_gueltig(patched_db, fake_redis):
    """DER Betriebsfall: NPM terminiert TLS, schickt `Host: dev.example.org`
    (ohne Port) und `X-Forwarded-Proto: https`; der Browser meldet
    `Origin: https://dev.example.org`.

    Vorher wurde nur der Hostname verglichen — mit Schema- und Portvergleich
    muss diese Konstellation weiter funktionieren, sonst waere die Anmeldung
    hinter dem Proxy tot.
    """
    from diakronos_app.main import app

    _lege_benutzer(patched_db)

    with _client(app, base_url="https://dev.example.org") as c:
        r = c.post(
            "/api/method/login",
            data={"usr": USR, "pwd": PWD},
            headers={
                **_BROWSER,
                "Origin": "https://dev.example.org",
                "Host": "dev.example.org",
                "X-Forwarded-Proto": "https",
                "Sec-Fetch-Site": "same-origin",
            },
            follow_redirects=False,
        )

    assert r.status_code == 303, r.text
    assert _hat_sid(r)


def test_hinter_proxy_mit_port_im_host_bleibt_gueltig(patched_db, fake_redis):
    """`Host: dev.example.org:8443` und `Origin: https://dev.example.org:8443`."""
    from diakronos_app.main import app

    _lege_benutzer(patched_db)

    with _client(app) as c:
        r = c.post(
            "/api/method/login",
            data={"usr": USR, "pwd": PWD},
            headers={
                **_BROWSER,
                "Origin": "https://dev.example.org:8443",
                "Host": "dev.example.org:8443",
                "X-Forwarded-Proto": "https",
            },
            follow_redirects=False,
        )

    assert r.status_code == 303, r.text
    assert _hat_sid(r)


def test_hinter_proxy_fremder_origin_bleibt_abgewiesen(patched_db, fake_redis):
    """Gegenprobe: die Verschaerfung oeffnet nichts hinter dem Proxy."""
    from diakronos_app.main import app

    _lege_benutzer(patched_db)

    with _client(app, base_url="https://dev.example.org") as c:
        r = c.post(
            "/api/method/login",
            data={"usr": USR, "pwd": PWD},
            headers={
                **_BROWSER,
                "Origin": FREMD,
                "Host": "dev.example.org",
                "X-Forwarded-Proto": "https",
            },
            follow_redirects=False,
        )

    assert not _hat_sid(r)
