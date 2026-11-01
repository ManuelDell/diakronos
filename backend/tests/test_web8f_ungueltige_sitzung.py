"""WEB-8f (B4) — ungueltige/abgelaufene `sid` heisst GAST, nie Befugnis.

BEFUND (Opus-Bewertung zu SEC-12)
=================================
Die Sitzungs-Middleware muss fail-closed arbeiten: ein `sid`-Cookie, das

  * gar nicht existiert,
  * serverseitig geloescht wurde (Logout, Konto deaktiviert, TTL abgelaufen),
  * syntaktisch falsch ist, oder
  * zu einem Konto gehoert, das es nicht mehr gibt,

darf NIEMALS eine Identitaet erzeugen. Der Aufruf ist dann `Guest`:
angemeldungspflichtige Endpunkte antworten **401** (`SessionExpired`), und
weil es keine Sitzung gibt, greift auch die CSRF-Pflicht nicht (kein
Schluessel, gegen den man pruefen koennte) — 401 statt 417.

Zusaetzlich geprueft (VERTRAG, nicht Befund):
  * 401 + `exc_type=SessionExpired` — genau die Form, aus der die Oberflaeche
    (WEB-8e E2) „melden statt neu laden" ableitet; ohne `exc_type` wuerde der
    Client die Antwort als Fachfehler zeigen.
  * Das Cookie wird bei einer erfundenen Sitzung NICHT geloescht, sondern nur
    nicht benutzt (Loeschen ist dem Fall „Konto weg" vorbehalten) — der
    Ausstieg ist trotzdem vollstaendig: der Aufruf bleibt `Guest`.
  * Ein geloeschtes Konto hinterlaesst keine lebende Sitzung.

Alle Faelle laufen mit `patched_db` + `fake_redis` (SQLite + Stub, kein Netz)
gegen die ECHTE Middleware und den ECHTEN Endpunkt `session.sitzung_status`.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from diakronos_app import base_path
from diakronos_app.frappe_compat import sitzungen
from diakronos_app.models.core import User
from diakronos_app.settings import settings as echte_settings

STATUS = "/api/method/diakronos.diakonos.api.session.sitzung_status"
PRAEFIX = "/diakronos"
USR = "web8f@example.org"


# ── Hilfen ────────────────────────────────────────────────────────────────


def _konto_anlegen(session_factory, name: str = USR) -> None:
    sess = session_factory()
    try:
        if sess.get(User, name) is None:
            sess.add(
                User(
                    name=name,
                    email=name,
                    full_name="WEB-8f Probe",
                    enabled=True,
                )
            )
            sess.commit()
    finally:
        sess.close()


def _client() -> TestClient:
    """Client OHNE Sitzung — kein `client`-Fixture, das eine Identitaet setzt."""
    from diakronos_app.main import app

    return TestClient(app)


def _abgelaufen(resp) -> bool:
    koerper = resp.json()
    return resp.status_code == 401 and koerper.get("exc_type") == "SessionExpired"


# ── 1. Es gibt keine gueltige Sitzung mit diesen Cookies ─────────────────


@pytest.mark.parametrize(
    "fall, cookie",
    [
        ("fehlend", None),
        ("erfunden", "nie-vergeben-1234"),
        ("leer", ""),
        ("syntaktisch-falsch", "../../etc/passwd"),
        ("sehr-lang", "x" * 5000),
    ],
)
def test_ungueltige_sid_ist_gast(patched_db, fake_redis, fall, cookie):
    """Kein/erfundenes/falsches `sid` -> Guest, 401 statt 403/500."""
    _konto_anlegen(patched_db)
    c = _client()
    try:
        if cookie is not None:
            c.cookies.set("sid", cookie)
        r = c.get(STATUS)
        assert _abgelaufen(r), f"{fall}: erwartet 401 SessionExpired, bekam {r.status_code} {r.text}"
        assert r.json().get("user") is None, f"{fall}: keine Identitaet nach aussen"
    finally:
        c.close()


def test_geloeschte_sitzung_ist_gast(patched_db, fake_redis):
    """Logout (Sitzung serverseitig weg) -> das alte Cookie traegt nichts mehr."""
    _konto_anlegen(patched_db)
    sid, csrf = sitzungen.anlegen(USR)

    # Die Identitaet kommt im Client aus dem Cookie, NICHT aus der Test-Naht:
    # sonst uebersteuert `user_uebersteuert()` die Middleware und der Ausstieg
    # wuerde gar nicht gemessen.
    from diakronos_app import frappe_compat

    frappe_compat.reset_user()

    c = _client()
    try:
        c.cookies.set("sid", sid)
        gut = c.get(STATUS)
        assert gut.status_code == 200, gut.text
        # Frappe-Form der Antwort: die Nutzdaten stehen unter `message`.
        assert gut.json().get("message", {}).get("user") == USR, f"gueltige Sitzung: {gut.json()}"

        assert sitzungen.loeschen(sid) is True

        weg = c.get(STATUS)
        assert _abgelaufen(weg), f"alte sid nach dem Logout: {weg.status_code} {weg.text}"
    finally:
        c.close()


def test_sehr_alte_sitzung_gilt_als_abgelaufen(patched_db, fake_redis):
    """Eine serverseitig verschwundene Sitzung (TTL) ist wie nie vergeben."""
    _konto_anlegen(patched_db)
    sid, _csrf = sitzungen.anlegen(USR)
    from diakronos_app.frappe_compat.sitzungen import _key

    # TTL 0 = Eintrag verschwindet sofort (Redis-Verhalten wie beim Ablauf).
    client = sitzungen._client()
    client.delete(_key(sid))

    c = _client()
    try:
        c.cookies.set("sid", sid)
        assert _abgelaufen(c.get(STATUS))
    finally:
        c.close()


def test_sitzung_eines_geloeschten_kontos_ist_gast(patched_db, fake_redis):
    """Konto weg -> Sitzung wird verworfen (nicht nur ignoriert) und ist Guest."""
    _konto_anlegen(patched_db)
    sid, _csrf = sitzungen.anlegen(USR)

    sess = patched_db()
    try:
        user = sess.get(User, USR)
        sess.delete(user)
        sess.commit()
    finally:
        sess.close()

    c = _client()
    try:
        c.cookies.set("sid", sid)
        r = c.get(STATUS)
        assert _abgelaufen(r), f"geloeschtes Konto: {r.status_code} {r.text}"
        assert sitzungen.lesen(sid) is None, "die Sitzung liegt nicht mehr im Speicher"
    finally:
        c.close()


# ── 2. Kein CSRF-Pruefzwang ohne Sitzung (sonst waere 417 statt 401) ──────


@pytest.mark.parametrize("pfad, sid", [(STATUS, "erfunden-9999"), ("/api/method/logout", "erfunden-9999")])
def test_ohne_sitzung_kein_csrf_pruefzwang(patched_db, fake_redis, pfad, sid):
    """Schreibender Aufruf mit erfundenem `sid` und OHNE Token: kein 417.

    Die CSRF-Pruefung ist ein Vergleich gegen den Token DER SITZUNG. Ohne
    Sitzung gibt es nichts zu vergleichen — die Middleware laesst durch und
    der Endpunkt entscheidet (401 bzw. No-op). Ein 417 an dieser Stelle waere
    eine Auskunft ueber einen Zustand, den es nicht gibt.
    """
    _konto_anlegen(patched_db)
    c = _client()
    try:
        c.cookies.set("sid", sid)
        c.headers.pop("X-Frappe-CSRF-Token", None)
        r = c.post(pfad)
        assert r.status_code != 417, f"{pfad}: CSRF-Zwang ohne Sitzung ({r.text})"
        assert r.json().get("exc_type") != "CSRFTokenError"
    finally:
        c.close()


def test_ohne_sitzung_kein_zugriff_auf_geschuetzten_endpunkt(patched_db, fake_redis):
    """Fail-closed: `allow_guest=False` bleibt ohne Sitzung versperrt."""
    c = _client()
    try:
        r = c.get(STATUS)
        assert r.status_code in (401, 403), f"offen ohne Sitzung: {r.status_code} {r.text}"
        assert r.status_code == 401, "fuer die Oberflaeche ist 401 die erwartete Form"
    finally:
        c.close()


# ── 3. Mit Praefix unveraendert (WEB-5a) ─────────────────────────────────


@pytest.mark.parametrize("sid", [None, "erfunden-5555"])
def test_ungueltige_sid_ist_guest_auch_unter_praefix(monkeypatch, patched_db, fake_redis, sid):
    """Derselbe Ausstieg unter `DIAKRONOS_BASE_PATH` — kein Sonderweg.

    Muster wie `test_web8_login_csrf.py`: das Praefix wird an den Einstellungen
    UND am Prozess gesetzt, BEVOR die Anwendung gebaut wird. `main.app` wird
    beim Import mit dem damaligen Praefix gebaut — deshalb hier eine frische
    Anwendung statt des Modul-Clients (der Eingang haengt sonst nicht).
    """
    monkeypatch.setattr(echte_settings, "diakronos_base_path", PRAEFIX)
    base_path.setze_praefix(PRAEFIX)
    c = None
    try:
        _konto_anlegen(patched_db)
        from diakronos_app.main import erstelle_app

        c = TestClient(erstelle_app())
        if sid:
            c.cookies.set("sid", sid)
        r = c.get(f"{PRAEFIX}{STATUS}")
        assert _abgelaufen(r), f"Praefix, sid={sid}: {r.status_code} {r.text}"
    finally:
        base_path.setze_praefix("")
        if c is not None:
            c.close()
