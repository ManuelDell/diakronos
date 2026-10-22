"""LOGIN-2 / S1 — `AUTH_LOCAL_LOGIN` wird SERVERSEITIG erzwungen.

Der Befund aus dem Review zu LOGIN-1 (R-LOGIN-1, Punkt N3): die Einstellung
`AUTH_LOCAL_LOGIN` wurde bis dahin NUR an einer Stelle ausgewertet, und zwar
in der Anmeldeseite (`anmeldung/routen.py::_lokales_login_erlaubt`). Der
Endpunkt `/api/method/login` hat sie nie gesehen — ein Konto ohne
Administratorrolle kam mit `nur-admin` also weiterhin lokal hinein, und mit
`aus` sogar jedes Konto.

Diese Karte zieht die Regel dorthin, wo sie wirkt: in den Login selbst.

  * ``an``        — lokale Anmeldung fuer alle Konten (wie bisher).
  * ``nur-admin`` — nur Konten mit **Administratorrolle** („System Manager“
    ODER „Mitgliederadministrator“ — dieselbe Definition wie
    `anmeldung/routen.py` und `frappe_compat/permissions.ADMIN_ROLES`).
  * ``aus``       — lokale Anmeldung gar nicht; die Maske zeigt dann
    verstaendlich den Weg ueber den Anbieter. Ist kein Anbieter
    eingerichtet, sagt sie ehrlich, dass sie sich an die Gemeindeleitung
    wenden sollen (NIE eine leere Seite).

**Ununterscheidbarkeit** ist der Kern von ``nur-admin``: ein Konto ohne
Adminrolle bekommt exakt dieselbe Antwort wie bei falschem Passwort (Status,
Kopfzeilen, Meldung, Cookie, Antwortzeit) — der Betreiber darf nicht
erfahren, dass das Passwort gestimmt haette, und die Brute-Force-Bremse
zaehlt wie bei jedem Fehlversuch.

Die Regel greift NUR bei aktivem OIDC. Ohne Anbieter ist der lokale Login
der EINZIGE Weg (Bestandsschutz, gleiche Begruendung wie
`_lokales_login_erlaubt`); ein `AUTH_LOCAL_LOGIN=aus` ohne Anbieter wuerde
jede Gemeinde aussperren.
"""

from __future__ import annotations

import pytest

from diakronos_app.frappe_compat import loginversuche
from diakronos_app.models.core import HasRole, User

MELDUNG = "Ungueltige Anmeldedaten"
FLASH_COOKIE = "dk_login_flash"

#: Kopfzeilen eines echten Browser-Formulars (LOGIN-2/M2: den Browser-Weg
#: nimmt der Router nur bei `text/html` im `Accept` bzw. `Sec-Fetch-Mode`).
_BROWSER = {"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}


# ── Hilfen ────────────────────────────────────────────────────────────────


def _lege_benutzer(session_factory, name: str, passwort: str, *, rollen=(), **felder) -> None:
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
        for rolle in rollen:
            sess.add(HasRole(name=f"{name}-{rolle}", parent=name, parenttype="User", role=rolle))
        sess.commit()
    finally:
        sess.close()


def _client(app):
    from fastapi.testclient import TestClient

    return TestClient(app)


def _set_cookie_koepfe(resp) -> list[str]:
    roh = resp.headers.get_list("set-cookie") if hasattr(resp.headers, "get_list") else []
    return [k for k in roh if k]


@pytest.fixture()
def oidc_an(monkeypatch):
    """OIDC aktiv, aber OHNE Netzzugriff (kein Mock-Anbieter noetig).

    Geprueft wird nur die Entscheidung ueber den lokalen Weg; die
    Weiterleitung selbst deckt `test_sec1_anmeldung.py` ab.
    """
    from diakronos_app.settings import settings

    monkeypatch.setattr(settings, "auth_oidc_enabled", True)
    monkeypatch.setattr(settings, "auth_oidc_issuer", "http://localhost:9/application/o/diakronos/")
    monkeypatch.setattr(settings, "auth_oidc_client_id", "diakronos-test")
    monkeypatch.setattr(settings, "auth_oidc_client_secret", "geheim-secret")
    monkeypatch.setattr(settings, "auth_oidc_redirect_url", "http://testserver/auth/oidc/callback")
    yield settings


# ── nur-admin: JSON-Weg ───────────────────────────────────────────────────


def _login_json(c, usr: str, pwd: str):
    return c.post("/api/method/login", json={"usr": usr, "pwd": pwd})


def test_nur_admin_lehnt_nicht_admin_ab(patched_db, fake_redis, oidc_an):
    """Das ist der Befund aus R-LOGIN-1: vorher kam dieses Konto hier durch."""
    from diakronos_app.main import app

    oidc_an.auth_local_login = "nur-admin"
    _lege_benutzer(patched_db, "mitglied@example.org", "geheim-123", rollen=["Mitglied"])

    with _client(app) as c:
        r = _login_json(c, "mitglied@example.org", "geheim-123")

    assert r.status_code == 401, f"Nicht-Admin darf sich lokal NICHT anmelden, war {r.status_code}"
    assert r.json()["message"] == MELDUNG
    assert "location" not in r.headers
    assert not any(k.lower().startswith("sid=") for k in _set_cookie_koepfe(r))


def test_nur_admin_laesst_admin_zu(patched_db, fake_redis, oidc_an):
    """Der Notzugang fuer bestehende Administratoren bleibt offen."""
    from diakronos_app.main import app

    oidc_an.auth_local_login = "nur-admin"
    _lege_benutzer(patched_db, "chef@example.org", "geheim-123", rollen=["System Manager"])

    with _client(app) as c:
        r = _login_json(c, "chef@example.org", "geheim-123")

    assert r.status_code == 200, r.text
    assert r.json()["message"] == "Logged In"
    assert any(k.lower().startswith("sid=") for k in _set_cookie_koepfe(r))


def test_nur_admin_mitgliederadministrator_zaehlt_als_admin(patched_db, fake_redis, oidc_an):
    """Zweite Administratorrolle (dieselbe Definition wie routen.py)."""
    from diakronos_app.main import app

    oidc_an.auth_local_login = "nur-admin"
    _lege_benutzer(
        patched_db, "verwaltung@example.org", "geheim-123", rollen=["Mitgliederadministrator"]
    )

    with _client(app) as c:
        r = _login_json(c, "verwaltung@example.org", "geheim-123")

    assert r.status_code == 200, r.text


def test_nur_admin_ohne_rollen_abgelehnt(patched_db, fake_redis, oidc_an):
    from diakronos_app.main import app

    oidc_an.auth_local_login = "nur-admin"
    _lege_benutzer(patched_db, "ohne@example.org", "geheim-123")

    with _client(app) as c:
        r = _login_json(c, "ohne@example.org", "geheim-123")

    assert r.status_code == 401


def test_nur_admin_falsches_passwort_sieht_nicht_anders_aus(patched_db, fake_redis, oidc_an):
    """Falsches Passwort (Nicht-Admin) vs. richtiges Passwort (Nicht-Admin):
    identische Antwort — sonst verriete die Antwort die Passwortrichtigkeit."""
    from diakronos_app.main import app

    oidc_an.auth_local_login = "nur-admin"
    _lege_benutzer(patched_db, "mitglied@example.org", "geheim-123", rollen=["Mitglied"])

    with _client(app) as c:
        falsch = _login_json(c, "mitglied@example.org", "falsch")
        richtig = _login_json(c, "mitglied@example.org", "geheim-123")

    assert falsch.status_code == richtig.status_code == 401
    assert falsch.json() == richtig.json()
    assert sorted(falsch.headers.keys()) == sorted(richtig.headers.keys())
    assert _set_cookie_koepfe(falsch) == _set_cookie_koepfe(richtig) == []


def test_nur_admin_nicht_admin_zaehlt_in_der_bremse(patched_db, fake_redis, oidc_an, monkeypatch):
    """Abgewiesene lokale Anmeldung ist ein Fehlversuch wie jeder andere.

    Sonst waere `nur-admin` ein Freifahrtschein zum unbegrenzten
    Durchprobieren von Passwoertern auf dem Login-Endpunkt.
    """
    from diakronos_app.main import app

    oidc_an.auth_local_login = "nur-admin"
    _lege_benutzer(patched_db, "mitglied@example.org", "geheim-123", rollen=["Mitglied"])

    gesehen: list[tuple] = []
    echt = loginversuche.pruefe_und_merke

    def _mitloggen(user, ip, *a, **kw):
        gesehen.append((user, ip))
        return echt(user, ip, *a, **kw)

    monkeypatch.setattr(loginversuche, "pruefe_und_merke", _mitloggen)

    with _client(app) as c:
        _login_json(c, "mitglied@example.org", "geheim-123")
        _login_json(c, "mitglied@example.org", "geheim-123")

    assert len(gesehen) == 2, "jeder Versuch muss gezaehlt werden"


def test_nur_admin_json_falsches_passwort_zaehlt_weiterhin(patched_db, fake_redis, oidc_an):
    """Gegenprobe: die Bremse sperrt den Nicht-Admin nach mehreren Versuchen aus
    — er kann also nicht beliebig weiterprobieren."""
    from diakronos_app.main import app

    oidc_an.auth_local_login = "nur-admin"
    _lege_benutzer(patched_db, "mitglied@example.org", "geheim-123", rollen=["Mitglied"])

    with _client(app) as c:
        antworten = [_login_json(c, "mitglied@example.org", "falsch") for _ in range(8)]

    assert all(r.status_code == 401 for r in antworten)


# ── nur-admin: Formularweg ────────────────────────────────────────────────


def test_nur_admin_formular_nicht_admin_zurueck_zur_maske(patched_db, fake_redis, oidc_an):
    """Der Formularweg darf sich nicht unterscheiden — also auch hier: Meldung."""
    from diakronos_app.main import app

    oidc_an.auth_local_login = "nur-admin"
    _lege_benutzer(patched_db, "mitglied@example.org", "geheim-123", rollen=["Mitglied"])

    with _client(app) as c:
        r = c.post(
            "/api/method/login",
            data={"usr": "mitglied@example.org", "pwd": "geheim-123", "redirect-to": "/diakonos"},
            headers=_BROWSER,
            follow_redirects=False,
        )
        seite = c.get(r.headers["location"], follow_redirects=False)

    assert r.status_code == 303, f"Formular-Fehlschlag muss 303 liefern, war {r.status_code}"
    assert not any(k.lower().startswith("sid=") for k in _set_cookie_koepfe(r))
    assert sorted(k.split("=", 1)[0] for k in _set_cookie_koepfe(r)) == [FLASH_COOKIE]
    assert "E-Mail-Adresse oder Passwort ist falsch." in seite.text


def test_nur_admin_formular_admin_kommt_durch(patched_db, fake_redis, oidc_an):
    from diakronos_app.main import app

    oidc_an.auth_local_login = "nur-admin"
    _lege_benutzer(patched_db, "chef@example.org", "geheim-123", rollen=["System Manager"])

    with _client(app) as c:
        r = c.post(
            "/api/method/login",
            data={"usr": "chef@example.org", "pwd": "geheim-123", "redirect-to": "/diakonos"},
            headers=_BROWSER,
            follow_redirects=False,
        )

    assert r.status_code == 303
    assert any(k.lower().startswith("sid=") for k in _set_cookie_koepfe(r))


# ── aus: lokale Anmeldung gar nicht ───────────────────────────────────────


def test_aus_lehnt_jede_lokale_anmeldung_ab_json(patched_db, fake_redis, oidc_an):
    from diakronos_app.main import app

    oidc_an.auth_local_login = "aus"
    _lege_benutzer(patched_db, "chef@example.org", "geheim-123", rollen=["System Manager"])

    with _client(app) as c:
        r = _login_json(c, "chef@example.org", "geheim-123")

    assert r.status_code == 401, f"bei 'aus' darf auch ein Admin nicht lokal hinein, war {r.status_code}"
    assert r.json()["message"] == MELDUNG
    assert not any(k.lower().startswith("sid=") for k in _set_cookie_koepfe(r))


def test_aus_formular_zurueck_zur_maske(patched_db, fake_redis, oidc_an):
    from diakronos_app.main import app

    oidc_an.auth_local_login = "aus"
    _lege_benutzer(patched_db, "chef@example.org", "geheim-123", rollen=["System Manager"])

    with _client(app) as c:
        r = c.post(
            "/api/method/login",
            data={"usr": "chef@example.org", "pwd": "geheim-123", "redirect-to": "/diakonos"},
            headers=_BROWSER,
            follow_redirects=False,
        )

    assert r.status_code == 303
    assert not any(k.lower().startswith("sid=") for k in _set_cookie_koepfe(r))


def test_aus_maske_zeigt_anbieter_weg(patched_db, fake_redis, oidc_an):
    """Modus `aus`: keine leere Seite, sondern der Weg ueber den Anbieter."""
    from diakronos_app.main import app

    oidc_an.auth_local_login = "aus"

    with _client(app) as c:
        r = c.get("/login", params={"lokal": "1", "sso": "0", "noredirect": "1"},
                  follow_redirects=False)

    assert r.status_code == 200, r.status_code
    # Kein Passwortfeld — der lokale Weg ist aus.
    assert 'name="pwd"' not in r.text
    # Aber ein benannter Weg zum Anbieter, verstaendlich formuliert.
    assert "/login?sso=1" in r.text
    assert "anmelden" in r.text.lower()


def test_aus_ohne_anbieter_bleibt_bedienbar(patched_db, fake_redis, monkeypatch):
    """`aus` OHNE eingerichteten Anbieter sperrt niemanden aus.

    Die Regel gilt nur bei aktivem Anbieter (sonst gaebe es keinen zweiten
    Weg). Ohne Anbieter bleibt die Maske bedienbar — und das ist die
    ausdrueckliche Entscheidung dieser Karte: lieber lokal anmelden lassen
    als eine Gemeinde aussperren. Geprueft wird hier, dass die Seite nicht
    leer ist und das Formular zeigt.
    """
    from diakronos_app.main import app
    from diakronos_app.settings import settings

    monkeypatch.setattr(settings, "auth_oidc_enabled", False)
    monkeypatch.setattr(settings, "auth_local_login", "aus")

    with _client(app) as c:
        r = c.get("/login", follow_redirects=False)

    assert r.status_code == 200, r.status_code
    assert 'name="pwd"' in r.text, "ohne Anbieter muss das Formular bedienbar bleiben"
    assert len(r.text) > 200, "keine leere Seite"


# ── an: alles wie bisher ──────────────────────────────────────────────────


def test_an_laesst_jedes_konto_zu(patched_db, fake_redis, oidc_an):
    from diakronos_app.main import app

    oidc_an.auth_local_login = "an"
    _lege_benutzer(patched_db, "mitglied@example.org", "geheim-123", rollen=["Mitglied"])

    with _client(app) as c:
        r = _login_json(c, "mitglied@example.org", "geheim-123")

    assert r.status_code == 200, r.text


def test_ohne_oidc_gilt_die_schranke_nicht(patched_db, fake_redis, monkeypatch):
    """Bestandsschutz: ohne Anbieter ist der lokale Login der einzige Weg.

    `AUTH_LOCAL_LOGIN=aus` darf eine Gemeinde ohne OIDC nicht aussperren —
    die Regel gilt nur, wenn tatsaechlich ein Anbieter da ist.
    """
    from diakronos_app.main import app
    from diakronos_app.settings import settings

    monkeypatch.setattr(settings, "auth_oidc_enabled", False)
    monkeypatch.setattr(settings, "auth_local_login", "aus")
    _lege_benutzer(patched_db, "mitglied@example.org", "geheim-123", rollen=["Mitglied"])

    with _client(app) as c:
        r = _login_json(c, "mitglied@example.org", "geheim-123")

    assert r.status_code == 200, "ohne OIDC bleibt der lokale Login erlaubt"


# ── CalDAV: Befund, keine Aenderung ───────────────────────────────────────


def test_caldav_bleibt_vom_lokalen_login_unberuehrt(patched_db, fake_redis, oidc_an):
    """BEFUND (dokumentiert, bewusst NICHT geaendert):

    CalDAV/App-Passwoerter sind eine eigene Anmeldung gegen dieselbe
    Passwortpruefung, aber ohne Sitzung — Kalender-Abos (Thunderbird, Handy)
    koennen nicht ueber einen Anbieter interaktiv anmelden. Wuerde
    `AUTH_LOCAL_LOGIN=nur-admin` hier ebenfalls greifen, braechen alle
    bestehenden Abos von Nicht-Administratoren beim naechsten Sync, ohne
    dass sie das beheben koennten. Die Entscheidung gehoert deshalb nicht in
    diese Karte (siehe Abschlusskommentar, Frage an den Operator).
    """
    from diakronos_app.caldav import auth as caldav_auth

    oidc_an.auth_local_login = "nur-admin"
    _lege_benutzer(patched_db, "mitglied@example.org", "geheim-123", rollen=["Mitglied"])

    assert caldav_auth._check_credentials("mitglied@example.org", "geheim-123") is True
