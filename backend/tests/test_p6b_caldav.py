"""P6b — CalDAV-Port pruefen (`diakronos_app.caldav`).

VORLAGE: `referenz/diakronos-frappe/diakronos/caldav/{server,ical,auth}.py`

Geprueft wird gegen das ECHTE Ziel (FastAPI-App + compat-Schicht), nicht gegen
eine Attrappe:

  * `ical.py`   — reine Funktion, Element -> VCALENDAR (Escapes, all_day, UID)
  * `auth.py`   — Basic-Auth gegen die ECHTE `user`-Tabelle: Frappe-pbkdf2-Hash
                  und Argon2, deaktivierte/gesperrte Konten, fail closed
  * `server.py` — OPTIONS/PROPFIND/REPORT/GET ueber den echten HTTP-Baum,
                  inkl. Rechtefilter (User sieht nur seine Kalender) und der
                  403-Sperre fuer fremde Principals

Der Rechte-Teil stuetzt sich auf `get_accessible_calendars()` — dasselbe
Modul, das auch die SPA benutzt (die Karte verlangt ausdruecklich, die
Rechtelogik NICHT nachzubauen).
"""

from __future__ import annotations

import base64
import hashlib
from datetime import datetime

import pytest

# ─────────────────────────────────────────────────────────────────────────────
# Hilfen
# ─────────────────────────────────────────────────────────────────────────────


def _basic(user, pw):
    kopfwert = base64.b64encode(f"{user}:{pw}".encode()).decode()
    return {"Authorization": f"Basic {kopfwert}"}


def _frappe_hash(passwort: str, salt: bytes = b"caldavsalzcaldavs", runden: int = 29000) -> str:
    """Echter Frappe-`$pbkdf2-sha256$`-Hash im passlib-"adapted base64".

    Dieselbe Bauart wie `test_a1b1_login.py` — KEIN geratenes Echtpasswort,
    sondern ein Hash bekannten Klartexts.
    """
    digest = hashlib.pbkdf2_hmac("sha256", passwort.encode("utf-8"), salt, runden, dklen=32)

    def ab64(roh: bytes) -> str:
        return base64.b64encode(roh).decode().rstrip("=").replace("+", ".")

    return f"$pbkdf2-sha256${runden}${ab64(salt)}${ab64(digest)}"


def _lege_caldav_benutzer(session_factory, name, passwort, *, hash_=None, enabled=True):
    """Legt einen `user` mit echtem Passworthash an (CalDAV-Anmeldekonto)."""
    from diakronos_app.models.core import User

    sess = session_factory()
    try:
        sess.add(User(
            name=name,
            email=name,
            full_name=name,
            enabled=enabled,
            password_hash=hash_ if hash_ is not None else _frappe_hash(passwort),
        ))
        sess.commit()
    finally:
        sess.close()


@pytest.fixture()
def kalenderwelt(patched_db):
    """Zwei Kalender + vier Termine, mit Rollenrechten wie in der SPA.

    Rechte ueber Rollen (`UserRole`-Kind-Tabellen `leserechte`/`schreibrechte`
    am Kalender + `Has Role` am User):

      Kalender "Gottesdienst" -> leserechte: Rolle "Mitglied"
      Kalender "Vorstand"     -> leserechte: Rolle "Vorstand"

    `anna@example.org` hat Rolle "Mitglied" (sieht nur "Gottesdienst"),
    `bruno@example.org` hat Rolle "Vorstand" (sieht nur "Vorstand").
    """
    from diakronos_app.frappe_compat.api_helpers import session
    from diakronos_app.models.core import HasRole, User, UserRole
    from diakronos_app.models.kronos import Element, Kalender

    sess = patched_db()

    # Anmeldekonten: echte Passworthashes (Frappe-pbkdf2) statt Dev-Passworte.
    sess.add_all([
        User(name="anna@example.org", email="anna@example.org",
             full_name="Anna Beispiel", enabled=True,
             password_hash=_frappe_hash("geheim")),
        User(name="bruno@example.org", email="bruno@example.org",
             full_name="Bruno Beispiel", enabled=True,
             password_hash=_frappe_hash("geheim2")),
    ])

    # `Has Role` haengt am User (Vater), nicht an einer eigenen Role-Tabelle:
    # genau das liest `frappe_compat.permissions.get_roles`.
    sess.add_all([
        HasRole(name="anna@example.org-Mitglied", parent="anna@example.org",
                parenttype="User", parentfield="roles", role="Mitglied",
                docstatus=0, idx=1),
        HasRole(name="bruno@example.org-Vorstand", parent="bruno@example.org",
                parenttype="User", parentfield="roles", role="Vorstand",
                docstatus=0, idx=1),
    ])
    sess.flush()

    # Kalender + Rechtezeilen (Kind-Tabelle `User Role`, parentfield = Rechtefeld)
    sess.add_all([
        Kalender(name="Gottesdienst", calendar_name="Gottesdienst",
                 calendar_color="#ff8800", selbstverwaltet=False,
                 docstatus=0, idx=0),
        Kalender(name="Vorstand", calendar_name="Vorstand",
                 calendar_color="#0088ff", selbstverwaltet=False,
                 docstatus=0, idx=0),
    ])
    sess.add_all([
        UserRole(name="ur-1", parent="Gottesdienst", parenttype="Kalender",
                 parentfield="leserechte", role="Mitglied", docstatus=0, idx=1),
        UserRole(name="ur-2", parent="Vorstand", parenttype="Kalender",
                 parentfield="leserechte", role="Vorstand", docstatus=0, idx=1),
    ])

    t = datetime(2026, 9, 27, 10, 0, 0)
    sess.add_all([
        Element(name="EV-0001", element_name="Sonntagsgottesdienst",
                element_calendar="Gottesdienst", element_start=t,
                element_end=t.replace(hour=11), all_day=False,
                description="Predigt: Psalm 23", status="Festgelegt",
                series_id="SERIE-1", docstatus=0, idx=0,
                creation=t, modified=t),
        Element(name="EV-0002", element_name="Gebet, Abend; still",
                element_calendar="Gottesdienst", element_start=t,
                element_end=t.replace(hour=12), all_day=True,
                description=None, status="Festgelegt",
                docstatus=0, idx=0, creation=t, modified=t),
        Element(name="EV-0003", element_name="Sitzung",
                element_calendar="Vorstand", element_start=t,
                element_end=t.replace(hour=13), all_day=False,
                description="intern", status="Festgelegt",
                docstatus=0, idx=0, creation=t, modified=t),
        # Nicht "Festgelegt" -> darf NIE auftauchen
        Element(name="EV-0004", element_name="Entwurf",
                element_calendar="Gottesdienst", element_start=t,
                element_end=t.replace(hour=9), all_day=False,
                description=None, status="Entwurf",
                docstatus=0, idx=0, creation=t, modified=t),
    ])
    sess.commit()

    yield sess

    # `session` ist ein ContextVar — nach dem Test zuruecksetzen, sonst sieht
    # der naechste Test noch den zuletzt gesetzten User.
    session.user = "Administrator"
    sess.close()


# ─────────────────────────────────────────────────────────────────────────────
# ical.py — Element -> iCalendar
# ─────────────────────────────────────────────────────────────────────────────


def test_ical_ganztaegig_und_uid():
    from diakronos_app.caldav.ical import element_to_ical

    class El:
        name = "EV-0002"
        element_name = "Gebet, Abend; still"
        element_start = datetime(2026, 9, 27, 0, 0)
        element_end = datetime(2026, 9, 28, 0, 0)
        all_day = True
        description = None
        series_id = None
        modified = None

    ics = element_to_ical(El())
    assert 'UID:EV-0002@diakronos' in ics
    assert 'DTSTART;VALUE=DATE:20260927' in ics
    assert 'DTEND;VALUE=DATE:20260928' in ics
    # Escapes nach RFC 5545: Komma, Semikolon
    assert r'SUMMARY:Gebet\, Abend\; still' in ics
    assert ics.startswith('BEGIN:VCALENDAR\r\n')
    assert ics.endswith('END:VCALENDAR')
    # DESCRIPTION fehlt, wenn leer
    assert 'DESCRIPTION:' not in ics


def test_ical_mit_uhrzeit_und_feldern():
    from diakronos_app.caldav.ical import element_to_ical

    class El:
        name = "EV-0001"
        element_name = "Sonntagsgottesdienst"
        element_start = datetime(2026, 9, 27, 10, 0)
        element_end = datetime(2026, 9, 27, 11, 0)
        all_day = False
        description = "Predigt: Psalm 23"
        series_id = "SERIE-1"
        modified = datetime(2026, 9, 26, 8, 30, 15)

    ics = element_to_ical(El())
    assert 'DTSTART:20260927T100000' in ics
    assert 'DTEND:20260927T110000' in ics
    assert 'DESCRIPTION:Predigt: Psalm 23' in ics
    assert 'RELATED-TO;RELTYPE=SIBLING:SERIE-1' in ics
    assert 'LAST-MODIFIED:20260926T083015Z' in ics
    assert 'PRODID:-//Diakronos//Kronos CalDAV//DE' in ics


def test_ical_backslash_escape():
    from diakronos_app.caldav.ical import _escape

    assert _escape(r'a\b') == r'a\\b'
    assert _escape('') == ''
    assert _escape(None) == ''


# ─────────────────────────────────────────────────────────────────────────────
# auth.py — echte Passwortpruefung gegen die `user`-Tabelle
# ─────────────────────────────────────────────────────────────────────────────


def test_ohne_credentials_ist_401(client, patched_db):
    """Ohne Authorization-Header -> 401 (fail closed)."""
    r = client.request("PROPFIND", "/dav/")
    assert r.status_code == 401
    assert r.headers["www-authenticate"].startswith('Basic realm="Diakronos CalDAV"')


def test_richtige_zugangsdaten_liefern_207(client, patched_db, kalenderwelt):
    """Abnahme: PROPFIND /dav/ mit gueltigen Zugangsdaten -> 207.

    Der Benutzer kommt aus derselben `user`-Tabelle wie die SPA; das Passwort
    wird gegen seinen Frappe-`pbkdf2-sha256`-Hash geprueft.
    """
    r = client.request("PROPFIND", "/dav/", headers=_basic("anna@example.org", "geheim"))
    assert r.status_code == 207


def test_falsches_passwort_ist_401(client, patched_db, kalenderwelt):
    r = client.request("PROPFIND", "/dav/", headers=_basic("anna@example.org", "falsch"))
    assert r.status_code == 401


def test_unbekannter_benutzer_ist_401(client, patched_db, kalenderwelt):
    r = client.request("PROPFIND", "/dav/", headers=_basic("niemand@example.org", "geheim"))
    assert r.status_code == 401


def test_deaktiviertes_konto_ist_401(client, patched_db, session_factory):
    """`enabled=False` schliesst CalDAV auch bei korrektem Passwort aus."""
    _lege_caldav_benutzer(session_factory, "aus@example.org", "geheim", enabled=False)
    r = client.request("PROPFIND", "/dav/", headers=_basic("aus@example.org", "geheim"))
    assert r.status_code == 401


def test_konto_ohne_hash_ist_401(client, patched_db, session_factory):
    """Benutzer ohne hinterlegten Hash (z. B. importiert ohne Passwort) -> 401."""
    _lege_caldav_benutzer(session_factory, "ohne@example.org", "", hash_=None)
    r = client.request("PROPFIND", "/dav/", headers=_basic("ohne@example.org", "egal"))
    assert r.status_code == 401


def test_argon2_hash_wird_akzeptiert(client, patched_db, session_factory):
    """Neu gesetzte Passwoerter (Argon2) melden sich genauso an wie Frappe-Hashes."""
    from diakronos_app.frappe_compat.passwoerter import neuer_hash

    _lege_caldav_benutzer(session_factory, "neu@example.org", "",
                          hash_=neuer_hash("frisch-123"))
    r = client.request("PROPFIND", "/dav/", headers=_basic("neu@example.org", "frisch-123"))
    assert r.status_code == 207
    r2 = client.request("PROPFIND", "/dav/", headers=_basic("neu@example.org", "falsch"))
    assert r2.status_code == 401


def test_frappe_hash_wird_nach_login_auf_argon2_gehoben(client, patched_db, session_factory):
    """Nach erfolgreichem CalDAV-Login liegt ein Argon2-Hash in der Tabelle."""
    from diakronos_app.models.core import User

    _lege_caldav_benutzer(session_factory, "heben@example.org", "geheim")
    r = client.request("PROPFIND", "/dav/", headers=_basic("heben@example.org", "geheim"))
    assert r.status_code == 207

    sess = session_factory()
    try:
        assert sess.get(User, "heben@example.org").password_hash.startswith("$argon2")
    finally:
        sess.close()


@pytest.mark.parametrize("user", ["guest", "Guest", "administrator", "root"])
def test_gesperrte_konten_bleiben_gesperrt(client, patched_db, session_factory, user):
    """Client-/Admin-Platzhalter sind keine anmeldbaren Kalender-Nutzer.

    Auch ein ECHTER Hash oeffnet sie nicht — die Sperre greift vor der Pruefung.
    """
    _lege_caldav_benutzer(session_factory, user, "geheim")
    r = client.request("PROPFIND", "/dav/", headers=_basic(user, "geheim"))
    assert r.status_code == 401


def test_dev_variablen_existieren_nicht_mehr():
    """Der Dev-Schalter ist ersatzlos weg — kein Modul oeffnet CalDAV ohne DB."""
    from diakronos_app.caldav import auth as auth_mod

    assert not hasattr(auth_mod, "ENV_MODE")
    assert not hasattr(auth_mod, "ENV_DEV_PASSWORDS")


def test_kaputter_authorization_header_ist_401(client, patched_db, kalenderwelt):
    for bad in ("", "Bearer abc", "Basic !!!nicht-base64", "Basic " + base64.b64encode(b"ohnedoppelpunkt").decode()):
        r = client.request("PROPFIND", "/dav/", headers={"Authorization": bad})
        assert r.status_code == 401, bad


# ─────────────────────────────────────────────────────────────────────────────
# server.py — HTTP-Baum
# ─────────────────────────────────────────────────────────────────────────────


def test_well_known_leitet_auf_dav(client):
    r = client.get("/.well-known/caldav", follow_redirects=False)
    assert r.status_code == 301
    assert r.headers["location"] == "/dav/"


def test_options_meldet_dav_faehigkeiten(client):
    """OPTIONS ist Vorabanfrage: kommt OHNE Credentials durch."""
    r = client.request("OPTIONS", "/dav/")
    assert r.status_code == 200
    assert "calendar-access" in r.headers["dav"]
    assert "PROPFIND" in r.headers["allow"]
    assert "REPORT" in r.headers["allow"]


def test_propfind_root_liefert_principal(client, patched_db, kalenderwelt):
    r = client.request("PROPFIND", "/dav/", headers=_basic("anna@example.org", "geheim"))
    assert r.status_code == 207
    assert r.headers["content-type"].startswith("text/xml")
    body = r.text
    assert body.startswith('<?xml version="1.0" encoding="UTF-8"?>')
    assert '<D:current-user-principal><D:href>/dav/anna@example.org/</D:href>' in body
    assert '<C:calendar-home-set>' in body


def test_propfind_home_zeigt_nur_erlaubte_kalender(client, patched_db, kalenderwelt):
    """anna hat Rolle "Mitglied" -> nur "Gottesdienst", NICHT "Vorstand".

    Die Kalender-Liste haengt an /dav/{user}/ (calendar-home-set), NICHT an
    /dav/ (das ist nur die Principal-Discovery).
    """
    r = client.request("PROPFIND", "/dav/anna@example.org/", headers=_basic("anna@example.org", "geheim"))
    body = r.text
    assert '/dav/anna@example.org/Gottesdienst/' in body
    assert 'Vorstand' not in body

    r2 = client.request("PROPFIND", "/dav/bruno@example.org/", headers=_basic("bruno@example.org", "geheim2"))
    body2 = r2.text
    assert '/dav/bruno@example.org/Vorstand/' in body2
    assert 'Gottesdienst' not in body2


def test_propfind_fremdes_principal_ist_403(client, patched_db, kalenderwelt):
    """Der URL-User muss der angemeldete User sein."""
    r = client.request("PROPFIND", "/dav/bruno@example.org/",
                       headers=_basic("anna@example.org", "geheim"))
    assert r.status_code == 403


def test_propfind_root_liefert_parsebares_xml(client, patched_db, kalenderwelt):
    """Die Antwort ist echtes, parsebares XML — nicht nur Status 207.

    Karte: „PROPFIND auf /dav/ liefert gueltiges XML (parse es, pruefe nicht
    nur den Status)."
    """
    import xml.etree.ElementTree as ET

    r = client.request("PROPFIND", "/dav/", headers=_basic("anna@example.org", "geheim"))
    assert r.status_code == 207
    root = ET.fromstring(r.text)  # wirft bei ungueltigem XML
    assert root.tag == "{DAV:}multistatus"
    hrefs = [e.text for e in root.iter("{DAV:}href")]
    assert "/dav/anna@example.org/" in hrefs
    assert any(h == "mailto:anna@example.org" for h in hrefs)


def test_propfind_home_ist_parsebares_xml(client, patched_db, kalenderwelt):
    """Calendar-Home: XML parsen und die Kalender-Collection finden."""
    import xml.etree.ElementTree as ET

    r = client.request("PROPFIND", "/dav/anna@example.org/", headers=_basic("anna@example.org", "geheim"))
    assert r.status_code == 207
    root = ET.fromstring(r.text)
    hrefs = [e.text for e in root.iter("{DAV:}href")]
    assert "/dav/anna@example.org/Gottesdienst/" in hrefs


def test_propfind_calendar_depth1_listet_events_ohne_entwuerfe(client, patched_db, kalenderwelt):
    r = client.request("PROPFIND", "/dav/anna@example.org/Gottesdienst/",
                       headers={**_basic("anna@example.org", "geheim"), "Depth": "1"})
    assert r.status_code == 207
    body = r.text
    assert 'EV-0001.ics' in body
    assert 'EV-0002.ics' in body
    # "Entwurf" ist nicht "Festgelegt" -> nie im Kalender
    assert 'EV-0004' not in body


def test_propfind_calendar_ohne_recht_ist_404(client, patched_db, kalenderwelt):
    """Kein Recht -> Kalender existiert fuer diesen User nicht."""
    r = client.request("PROPFIND", "/dav/anna@example.org/Vorstand/",
                       headers=_basic("anna@example.org", "geheim"))
    assert r.status_code == 404


def test_propfind_calendar_ohne_recht_liefert_keine_events(client, patched_db, kalenderwelt):
    """Kein Leserecht -> Kalender ist fuer diesen User leer, keine Events.

    Der Port antwortet wie das Original: die Collection ist nicht auffindbar,
    also kommt keine einzige Event-Zeile zurueck. Weder "Sitzung" noch die
    UID EV-0003 duerfen durchsickern.
    """
    r = client.request("PROPFIND", "/dav/anna@example.org/Vorstand/",
                       headers={**_basic("anna@example.org", "geheim"), "Depth": "1"})
    body = r.text
    assert 'EV-0003' not in body
    assert 'Sitzung' not in body
    # 404 = "nicht vorhanden" (kein Leak der Existenz), genau wie GET/REPORT
    assert r.status_code == 404


def test_report_calendar_query_liefert_ical_daten(client, patched_db, kalenderwelt):
    query = b'''<?xml version="1.0" encoding="UTF-8"?>
<C:calendar-query xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
  <D:prop><D:getetag/><C:calendar-data/></D:prop>
  <C:filter>
    <C:comp-filter name="VCALENDAR">
      <C:comp-filter name="VEVENT">
        <C:time-range start="20260901T000000Z" end="20261001T000000Z"/>
      </C:comp-filter>
    </C:comp-filter>
  </C:filter>
</C:calendar-query>'''

    r = client.request("REPORT", "/dav/anna@example.org/Gottesdienst/",
                       headers=_basic("anna@example.org", "geheim"), content=query)
    assert r.status_code == 207
    body = r.text
    assert 'BEGIN:VCALENDAR' in body
    assert 'Sonntagsgottesdienst' in body
    assert 'UID:EV-0001@diakronos' in body
    assert '<D:getetag>' in body
    # Kein Entwurf
    assert 'EV-0004' not in body
    # Bruno's Kalender taucht hier nicht auf
    assert 'Sitzung' not in body


def test_report_multiget_holt_konkrete_uid(client, patched_db, kalenderwelt):
    query = b'''<?xml version="1.0" encoding="UTF-8"?>
<C:calendar-multiget xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
  <D:prop><D:getetag/><C:calendar-data/></D:prop>
  <D:href>/dav/anna@example.org/Gottesdienst/EV-0001.ics</D:href>
</C:calendar-multiget>'''

    r = client.request("REPORT", "/dav/anna@example.org/Gottesdienst/",
                       headers=_basic("anna@example.org", "geheim"), content=query)
    assert r.status_code == 207
    assert 'EV-0001' in r.text
    assert 'EV-0002' not in r.text


def test_report_ohne_recht_liefert_keine_daten(client, patched_db, kalenderwelt):
    """REPORT auf einen Kalender ohne Leserecht -> kein Termin im Body."""
    r = client.request("REPORT", "/dav/anna@example.org/Vorstand/",
                       headers=_basic("anna@example.org", "geheim"), content=b"<x/>")
    assert 'Sitzung' not in r.text
    assert 'EV-0003' not in r.text


def test_get_event_liefert_ics_mit_etag(client, patched_db, kalenderwelt):
    r = client.get("/dav/anna@example.org/Gottesdienst/EV-0001.ics",
                   headers=_basic("anna@example.org", "geheim"))
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/calendar")
    assert r.headers["etag"]
    assert 'UID:EV-0001@diakronos' in r.text
    assert 'Sonntagsgottesdienst' in r.text


def test_get_fremdes_event_ohne_recht_liefert_kein_ical(client, patched_db, kalenderwelt):
    """Event aus einem Kalender ohne Leserecht -> kein iCal-Inhalt.

    `_get_event` prueft zuerst das Kalenderrecht. Ohne Recht gibt es kein
    Event — der Body darf weder die UID noch den Terminnamen enthalten.
    """
    r = client.get("/dav/anna@example.org/Vorstand/EV-0003.ics",
                   headers=_basic("anna@example.org", "geheim"))
    assert 'EV-0003' not in r.text
    assert 'Sitzung' not in r.text
    assert r.status_code in (403, 404)


def test_get_unbekanntes_event_ist_404(client, patched_db, kalenderwelt):
    r = client.get("/dav/anna@example.org/Gottesdienst/EV-9999.ics",
                   headers=_basic("anna@example.org", "geheim"))
    assert r.status_code == 404


def test_get_entwurf_ist_nicht_sichtbar(client, patched_db, kalenderwelt):
    """B5: bekannte UID darf die Festgelegt-Sichtbarkeit nicht umgehen.

    Bewusste Haertung des unsicheren Originals, identisch zur Ereignisliste.
    """
    r = client.get("/dav/anna@example.org/Gottesdienst/EV-0004.ics",
                   headers=_basic("anna@example.org", "geheim"))
    assert r.status_code == 404
    assert 'BEGIN:VCALENDAR' not in r.text
    assert 'EV-0004' not in r.text


def test_report_viele_events_erschoepft_den_verbindungspool_nicht(client, patched_db, kalenderwelt):
    """Regression: 60 Termine in EINEM REPORT duerfen keinen Pool-Timeout geben.

    Vorher lud `_get_events` jedes Element mit `frappe.get_doc` -> eine eigene
    SQLAlchemy-Session pro Termin, die erst beim GC geschlossen wurde. Bei mehr
    Terminen als Pool-Slots (5 + 10 Overflow) lief der REPORT in einen
    `QueuePool`-Timeout -> 500. Jetzt eine gemeinsame Session.
    """
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.kronos import Element

    sess = SessionLocal()
    try:
        for i in range(60):
            sess.add(Element(
                name=f"BULK-{i:04d}", element_calendar="Gottesdienst",
                element_name=f"Termin {i}", element_start=datetime(2026, 10, 1, 10, 0),
                element_end=datetime(2026, 10, 1, 11, 0), status="Festgelegt",
                docstatus=0, idx=i,
            ))
        sess.commit()
    finally:
        sess.close()

    r = client.request("REPORT", "/dav/anna@example.org/Gottesdienst/",
                       headers=_basic("anna@example.org", "geheim"), content=b"<x/>")
    assert r.status_code == 207
    assert r.text.count(".ics</D:href>") >= 60


def test_schreibmethoden_sind_405(client, patched_db, kalenderwelt):
    """Der Server ist READ-ONLY: PUT/DELETE/PROPPATCH duerfen nichts aendern."""
    for method in ("PUT", "DELETE", "PROPPATCH", "MKCALENDAR", "POST"):
        r = client.request(method, "/dav/anna@example.org/Gottesdienst/EV-0001.ics",
                           headers=_basic("anna@example.org", "geheim"), content=b"x")
        assert r.status_code == 405, method


def test_routes_im_app_router_registriert(client):
    """Die DAV-Routen haengen im echten Router (nicht nur im Test-Client)."""
    from diakronos_app.main import app

    paths = {getattr(r, "path", None) for r in app.router.routes}
    assert "/dav/{rest:path}" in paths
    assert "/.well-known/caldav" in paths
