"""P1-6 (OP-HANDY-2) — CalDAV-Antworten sind gueltiges XML.

Befund: Kalenderliste und Termindaten sind ungueltiges XML, sobald ein
Kalendername oder ein Termin Sonderzeichen enthaelt ("Musik & Chor", Titel mit
"&"/"<"). DAVx⁵, iOS-Kalender und Thunderbird parsen strikt -> die ganze Liste
scheitert ("not well-formed (invalid token)").

Geprueft wird gegen den ECHTEN HTTP-Baum (FastAPI-App + compat-Schicht) mit
`xml.etree.ElementTree` als strengem Parser — nicht nur der Status.

  * hrefs tragen die Kalender-/UID-Werte prozentkodiert (`_HREF_SAFE`)
  * Textwerte (displayname, calendar-data, etag) sind XML-escaped; in XML 1.0
    verbotene Steuerzeichen werden VOR dem Escapen entfernt (P1-5c, Punkt 1)
  * der Eingangspfad wird dekodiert, damit ein kodierter href wieder trifft
  * der ETag-Header aus GET ist identisch mit dem getetag aus PROPFIND
    (P1-5c, Punkt 2)
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest
from test_p6b_caldav import _basic  # noqa: F401

DAV = "{DAV:}"
CAL = "{urn:ietf:params:xml:ns:caldav}"

# Ein Kalender wie in der Gemeinde: "&" im Namen, etliche Termine mit "&"/"<".
SANDKALENDER = "Musik & Chor"
SAND_UID = "EV-SAND-1"


@pytest.fixture()
def sandwelt(patched_db):
    """Kalender "Musik & Chor" mit Terminen, deren Felder Sonderzeichen tragen."""
    from datetime import datetime

    from diakronos_app.models.core import HasRole, User, UserRole
    from diakronos_app.models.kronos import Element, Kalender
    from test_p6b_caldav import _frappe_hash

    sess = patched_db()
    sess.add(User(name="anna@example.org", email="anna@example.org",
                  full_name="Anna Beispiel", enabled=True,
                  password_hash=_frappe_hash("geheim")))
    sess.add(HasRole(name="anna@example.org-Mitglied", parent="anna@example.org",
                     parenttype="User", parentfield="roles", role="Mitglied",
                     docstatus=0, idx=1))
    sess.add(Kalender(name=SANDKALENDER, calendar_name=SANDKALENDER,
                      calendar_color="#ff8800", selbstverwaltet=False,
                      docstatus=0, idx=0))
    sess.add(UserRole(name="ur-sand", parent=SANDKALENDER, parenttype="Kalender",
                      parentfield="leserechte", role="Mitglied", docstatus=0, idx=1))

    t = datetime(2026, 9, 27, 10, 0, 0)
    sess.add_all([
        Element(name=SAND_UID, element_name="Chorprobe <Orgel & Gesang>",
                element_calendar=SANDKALENDER, element_start=t,
                element_end=t.replace(hour=11), all_day=False,
                description="Noten & Texte: Psalm 23 <bitte mitbringen>",
                status="Festgelegt", docstatus=0, idx=0,
                creation=t, modified=t),
        # Termin mit "&"/"<" NUR im Titel — deckt calendar-data im REPORT ab.
        Element(name="EV-SAND-2", element_name="Gottesdienst & Kaffee <danach>",
                element_calendar=SANDKALENDER, element_start=t,
                element_end=t.replace(hour=12), all_day=False,
                description=None, status="Festgelegt", docstatus=0, idx=0,
                creation=t, modified=t),
    ])
    sess.commit()
    yield sess
    sess.close()


def _hrefs(body):
    return [e.text for e in ET.fromstring(body).iter(DAV + "href")]


def _propfind_home(client):
    r = client.request("PROPFIND", "/dav/anna@example.org/",
                       headers=_basic("anna@example.org", "geheim"))
    assert r.status_code == 207
    return r.text


# ─────────────────────────────────────────────────────────────────────────────
# Kalenderliste (PROPFIND /dav/{user}/)
# ─────────────────────────────────────────────────────────────────────────────


def test_kalenderliste_ist_parsebares_xml(client, patched_db, sandwelt):
    """REPRODUKTION: "Musik & Chor" -> rohes & machte die Antwort unparsebar."""
    body = _propfind_home(client)
    ET.fromstring(body)  # rot vor der Behebung
    assert "Musik &amp; Chor" in body
    assert "Musik & Chor" not in body  # kein rohes &


def test_kalenderliste_href_ist_prozentkodiert(client, patched_db, sandwelt):
    """href traegt den kodierten Namen, der Client dekodiert ihn wieder."""
    hrefs = _hrefs(_propfind_home(client))
    assert "/dav/anna@example.org/Musik%20%26%20Chor/" in hrefs


def test_kalenderliste_roundtrip_ueber_kodierten_href(client, patched_db, sandwelt):
    """Der Weg, den ein Client geht: kodierten href zurueckholen -> 207.

    Starlette dekodiert `%20`/`%26` im Pfad bereits beim Routing, `_route`
    muss den Namen deshalb nicht noch einmal selbst dekodieren — er muss aber
    EXAKT der Kalendername sein, sonst gibt es faelschlich 404.
    """
    hrefs = _hrefs(_propfind_home(client))
    ziel = next(h for h in hrefs if h.rstrip("/").endswith("Musik%20%26%20Chor"))
    r = client.request("PROPFIND", ziel, headers=_basic("anna@example.org", "geheim"))
    assert r.status_code == 207
    ET.fromstring(r.text)


# ─────────────────────────────────────────────────────────────────────────────
# Event-Liste (PROPFIND Depth:1) und REPORT
# ─────────────────────────────────────────────────────────────────────────────


def test_propfind_depth1_mit_sonderzeichen_ist_parsebar(client, patched_db, sandwelt):
    r = client.request("PROPFIND", "/dav/anna@example.org/Musik%20%26%20Chor/",
                       headers={**_basic("anna@example.org", "geheim"), "Depth": "1"})
    assert r.status_code == 207
    root = ET.fromstring(r.text)
    hrefs = [e.text for e in root.iter(DAV + "href")]
    assert any(h.endswith(f"{SAND_UID}.ics") for h in hrefs)
    # P1-6/K4: Der Schluss war vorher `assert root is not None` — das gilt nach
    # einem erfolgreichen `ET.fromstring` immer und prueft nichts. Stattdessen
    # wird geprueft, was dieser Test wirklich zusichert: der getetag des Termins
    # ist vorhanden und traegt den Namen als Teil der ETag-Anfuehrung.
    etags = [e.text for e in root.iter(DAV + "getetag")]
    assert etags, "kein getetag in der Antwort"
    assert any(SAND_UID in (t or "") for t in etags)


def test_report_calendar_data_ist_parsebar(client, patched_db, sandwelt):
    """REPRODUKTION REPORT: <C:calendar-data>{ical} unescaped -> unparsebar."""
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

    r = client.request("REPORT", "/dav/anna@example.org/Musik%20%26%20Chor/",
                       headers=_basic("anna@example.org", "geheim"), content=query)
    assert r.status_code == 207
    root = ET.fromstring(r.text)  # rot vor der Behebung

    daten = [e.text for e in root.iter(CAL + "calendar-data")]
    assert daten, "calendar-data fehlt"
    ical = daten[0]
    # Der Client bekommt nach dem Auspacken wieder den rohen iCal-Text zurueck.
    assert "BEGIN:VCALENDAR" in ical
    assert "Chorprobe <Orgel & Gesang>" in ical


def test_report_zurueckgegebene_hrefs_bleiben_aufloesbar(client, patched_db, sandwelt):
    """Jeder href im REPORT laesst sich per GET erneut holen."""
    r = client.request("REPORT", "/dav/anna@example.org/Musik%20%26%20Chor/",
                       headers=_basic("anna@example.org", "geheim"), content=b"<x/>")
    assert r.status_code == 207
    root = ET.fromstring(r.text)
    hrefs = [e.text for e in root.iter(DAV + "href")]
    assert hrefs
    for h in hrefs:
        g = client.get(h, headers=_basic("anna@example.org", "geheim"))
        assert g.status_code == 200, h


def test_uid_mit_sonderzeichen_im_href(client, patched_db, sandwelt):
    """UIDs sind ebenfalls kodiert (Altbestand kann Sonderzeichen tragen)."""
    from datetime import datetime

    from diakronos_app.db import SessionLocal
    from diakronos_app.models.kronos import Element

    name = "EV mit & Zeichen"
    sess = SessionLocal()
    try:
        t = datetime(2026, 9, 27, 10, 0)
        sess.add(Element(name=name, element_name="Termin",
                         element_calendar=SANDKALENDER, element_start=t,
                         element_end=t.replace(hour=11), all_day=False,
                         status="Festgelegt", docstatus=0, idx=0,
                         creation=t, modified=t))
        sess.commit()
    finally:
        sess.close()

    r = client.request("PROPFIND", "/dav/anna@example.org/Musik%20%26%20Chor/",
                       headers={**_basic("anna@example.org", "geheim"), "Depth": "1"})
    assert r.status_code == 207
    root = ET.fromstring(r.text)
    hrefs = [e.text for e in root.iter(DAV + "href")]
    assert "/dav/anna@example.org/Musik%20%26%20Chor/EV%20mit%20%26%20Zeichen.ics" in hrefs

    # und die UID laesst sich ueber den kodierten href wieder abrufen
    g = client.get("/dav/anna@example.org/Musik%20%26%20Chor/EV%20mit%20%26%20Zeichen.ics",
                   headers=_basic("anna@example.org", "geheim"))
    assert g.status_code == 200
    assert "UID:EV mit & Zeichen@diakronos" in g.text


def test_multiget_mit_kodierter_uid_trifft_den_termin(client, patched_db, sandwelt):
    """REPORT calendar-multiget mit kodiertem href findet den Termin.

    Der Client schickt genau den href zurueck, den er im PROPFIND bekommen hat —
    also prozentkodiert. Ohne Dekodierung bei der Auswertung trifft die UID die
    Datenbank nie und die Antwort bliebe leer.
    """
    xml = ('<C:calendar-multiget xmlns:C="urn:ietf:params:xml:ns:caldav" xmlns:D="DAV:">'
           '<D:href>/dav/anna@example.org/Musik%20%26%20Chor/EV-SAND-1.ics</D:href>'
           '</C:calendar-multiget>')
    r = client.request("REPORT", "/dav/anna@example.org/Musik%20%26%20Chor/",
                       headers=_basic("anna@example.org", "geheim"), content=xml)
    assert r.status_code == 207
    ET.fromstring(r.text)
    assert "UID:EV-SAND-1@diakronos" in r.text
    assert "EV-SAND-2" not in r.text


def test_grosser_kalender_mit_sonderzeichen_bleibt_parsebar(client, patched_db, sandwelt):
    """Bericht nennt ausdruecklich "Veranstaltungen" mit 100 Terminen samt "&".

    Die Antwort darf auch bei vielen Terminen nicht an Sonderzeichen zerbrechen
    (und nicht am Verbindungspool, siehe B5-Regressionstest).
    """
    from datetime import datetime

    from diakronos_app.db import SessionLocal
    from diakronos_app.models.kronos import Element

    sess = SessionLocal()
    try:
        t = datetime(2026, 10, 20, 19, 0)
        for i in range(100):
            sess.add(Element(
                name=f"VER-{i:04d}",
                element_name=f"Veranstaltung Nummer {i} & Gäste <offen>",
                element_calendar=SANDKALENDER, element_start=t,
                element_end=t.replace(hour=20), all_day=False,
                description=f"Details: Kaffee & Kuchen <bitte mitbringen> ({i})",
                status="Festgelegt", docstatus=0, idx=i,
                creation=t, modified=t,
            ))
        sess.commit()
    finally:
        sess.close()

    r = client.request("REPORT", "/dav/anna@example.org/Musik%20%26%20Chor/",
                       headers=_basic("anna@example.org", "geheim"), content=b"<x/>")
    assert r.status_code == 207
    root = ET.fromstring(r.text)
    daten = list(root.iter(CAL + "calendar-data"))
    assert len(daten) >= 100, f"nur {len(daten)} Termine zurueckgeliefert"
    assert all("BEGIN:VCALENDAR" in (e.text or "") for e in daten)


# ─────────────────────────────────────────────────────────────────────────────
# P1-5c (1) — in XML 1.0 verbotene Steuerzeichen
# ─────────────────────────────────────────────────────────────────────────────


def _termin(sess, name, titel, beschreibung=None, uid=None):
    from datetime import datetime

    from diakronos_app.models.kronos import Element

    t = datetime(2026, 9, 27, 10, 0, 0)
    sess.add(Element(name=uid or name, element_name=titel,
                     element_calendar=SANDKALENDER, element_start=t,
                     element_end=t.replace(hour=11), all_day=False,
                     description=beschreibung, status="Festgelegt",
                     docstatus=0, idx=0, creation=t, modified=t))
    sess.commit()


def test_steuerzeichen_im_titel_machen_den_report_nicht_unlesbar(client, patched_db):
    """REPRODUKTION: `saxutils.escape` entfernt keine in XML 1.0 verbotenen
    Zeichen. Ein Vertikal-Tab (`\\x0b`) im Titel machte den GANZEN REPORT
    unparsebar ("not well-formed") — auch fuer alle anderen Termine.
    """
    sess = patched_db()
    from diakronos_app.models.core import HasRole, User, UserRole
    from diakronos_app.models.kronos import Kalender
    from test_p6b_caldav import _frappe_hash

    sess.add(User(name="anna@example.org", email="anna@example.org",
                  full_name="Anna Beispiel", enabled=True,
                  password_hash=_frappe_hash("geheim")))
    sess.add(HasRole(name="anna@example.org-Mitglied", parent="anna@example.org",
                     parenttype="User", parentfield="roles", role="Mitglied",
                     docstatus=0, idx=1))
    sess.add(Kalender(name=SANDKALENDER, calendar_name=SANDKALENDER,
                      calendar_color="#ff8800", selbstverwaltet=False,
                      docstatus=0, idx=0))
    sess.add(UserRole(name="ur-steuer", parent=SANDKALENDER, parenttype="Kalender",
                      parentfield="leserechte", role="Mitglied", docstatus=0, idx=1))
    sess.commit()

    # Titel mit Vertikal-Tab und Nullbyte (typisch fuer Einfuegen aus PDF/Word).
    titel = "Chorprobe\x0b mit \x00 Steuerzeichen"
    _termin(sess, "EV-STEUER-1", titel)
    _termin(sess, "EV-STEUER-2", "Normaler Termin")

    r = client.request("REPORT", "/dav/anna@example.org/Musik%20%26%20Chor/",
                       headers=_basic("anna@example.org", "geheim"), content=b"<x/>")
    assert r.status_code == 207
    root = ET.fromstring(r.text)  # rot vor der Behebung

    daten = [e.text or "" for e in root.iter(CAL + "calendar-data")]
    assert len(daten) == 2, "ein steuerzeichenbehafteter Termin riss die Antwort mit"
    # Das Steuerzeichen ist WEG, der Rest des Titels bleibt (nichts wird still
    # zu einem anderen Termin).
    assert all("\x0b" not in d and "\x00" not in d for d in daten)
    assert any("Chorprobe" in d and "Steuerzeichen" in d for d in daten)


def test_steuerzeichen_im_displayname_des_kalenders(client, patched_db):
    """Dieselbe Wache fuer Kalender-Namen (Anzeige + href)."""
    sess = patched_db()
    from diakronos_app.models.core import HasRole, User, UserRole
    from datetime import datetime

    from diakronos_app.models.kronos import Kalender
    from test_p6b_caldav import _frappe_hash

    sess.add(User(name="anna@example.org", email="anna@example.org",
                  full_name="Anna Beispiel", enabled=True,
                  password_hash=_frappe_hash("geheim")))
    sess.add(HasRole(name="anna@example.org-Mitglied", parent="anna@example.org",
                     parenttype="User", parentfield="roles", role="Mitglied",
                     docstatus=0, idx=1))
    t = datetime(2026, 9, 27, 10, 0)
    sess.add(Kalender(name="Steuer\x0bkalender", calendar_name="Steuer\x0bkalender",
                      calendar_color="#ff8800", selbstverwaltet=False,
                      docstatus=0, idx=0, creation=t, modified=t))
    sess.add(UserRole(name="ur-steuer2", parent="Steuer\x0bkalender",
                      parenttype="Kalender", parentfield="leserechte",
                      role="Mitglied", docstatus=0, idx=1))
    sess.commit()

    body = _propfind_home(client)
    ET.fromstring(body)  # rot vor der Behebung
    assert "\x0b" not in body


# ─────────────────────────────────────────────────────────────────────────────
# P1-5c (2) — ETag-Header == PROPFIND-getetag
# ─────────────────────────────────────────────────────────────────────────────


def test_etag_header_stimmt_mit_propfind_ueberein(client, patched_db, sandwelt):
    """REPRODUKTION: Der GET-ETag lief durch `_text` (XML-Escape). Bei einem
    Namen mit `&` stand dort `&amp;`, waehrend PROPFIND nach dem XML-Parsen `&`
    liefert — zwei verschiedene ETags fuer denselben Termin (Cache/If-Match).
    """
    uid = SAND_UID  # Name "EV-SAND-1" (ohne &) fuer den Pfad ...
    r = client.request("PROPFIND", "/dav/anna@example.org/Musik%20%26%20Chor/",
                       headers={**_basic("anna@example.org", "geheim"), "Depth": "1"})
    root = ET.fromstring(r.text)
    etag_propfind = None
    for resp in root.iter(DAV + "response"):
        href = next((e.text for e in resp.iter(DAV + "href")), None)
        if href and href.endswith(f"{uid}.ics"):
            etag_propfind = next(
                (e.text for e in resp.iter(DAV + "getetag")), None
            )
    assert etag_propfind, "kein getetag im PROPFIND"

    g = client.get(f"/dav/anna@example.org/Musik%20%26%20Chor/{uid}.ics",
                   headers=_basic("anna@example.org", "geheim"))
    assert g.status_code == 200
    assert g.headers["etag"] == etag_propfind


def test_etag_header_mit_ampersand_im_namen(client, patched_db, sandwelt):
    """Der eigentliche Befund: Name MIT `&` — Header darf kein `&amp;` tragen."""
    uid = "EV mit & Zeichen"

    from datetime import datetime

    from diakronos_app.db import SessionLocal
    from diakronos_app.models.kronos import Element

    sess = SessionLocal()
    try:
        t = datetime(2026, 9, 27, 10, 0)
        sess.add(Element(name=uid, element_name="Termin", element_calendar=SANDKALENDER,
                         element_start=t, element_end=t.replace(hour=11), all_day=False,
                         status="Festgelegt", docstatus=0, idx=0, creation=t, modified=t))
        sess.commit()
    finally:
        sess.close()

    g = client.get("/dav/anna@example.org/Musik%20%26%20Chor/EV%20mit%20%26%20Zeichen.ics",
                   headers=_basic("anna@example.org", "geheim"))
    assert g.status_code == 200
    etag_header = g.headers["etag"]
    assert "&amp;" not in etag_header, f"XML-Escape in der Kopfzeile: {etag_header}"
    assert "&" in etag_header

    # Und derselbe Termin ueber PROPFIND, nach dem XML-Parsen:
    r = client.request("PROPFIND", "/dav/anna@example.org/Musik%20%26%20Chor/",
                       headers={**_basic("anna@example.org", "geheim"), "Depth": "1"})
    root = ET.fromstring(r.text)
    etag_propfind = None
    for resp in root.iter(DAV + "response"):
        href = next((e.text for e in resp.iter(DAV + "href")), None)
        if href and href.endswith("EV%20mit%20%26%20Zeichen.ics"):
            etag_propfind = next((e.text for e in resp.iter(DAV + "getetag")), None)
    assert etag_propfind, "kein getetag im PROPFIND fuer den Termin mit '&'"
    assert etag_header == etag_propfind


# ─────────────────────────────────────────────────────────────────────────────
# P1-5c (3) — Anfuehrungszeichen, Umlaute, % und + in Namen
# ─────────────────────────────────────────────────────────────────────────────


def test_umlaute_und_anfuehrungszeichen_im_namen(client, patched_db, sandwelt):
    """Anfuehrungszeichen/Apostroph/Umlaut im Termin- UND Kalendernamen.

    Doppelpunkt und Prozent sind im PFAD heikel: `%` muss einmal kodiert werden
    (sonst Dekodierfehler), und ein Name mit `"` darf weder XML noch die
    ETag-Kopfzeile sprengen.
    """
    from datetime import datetime

    from diakronos_app.db import SessionLocal
    from diakronos_app.models.kronos import Element, Kalender
    from diakronos_app.models.core import UserRole

    sess = SessionLocal()
    try:
        t = datetime(2026, 9, 27, 10, 0)
        sess.add(Kalender(name='Kölner "Chor" + 100%', calendar_name='Kölner "Chor" + 100%',
                          calendar_color="#00aa00", selbstverwaltet=False,
                          docstatus=0, idx=0, creation=t, modified=t))
        sess.add(UserRole(name="ur-sonder", parent='Kölner "Chor" + 100%',
                          parenttype="Kalender", parentfield="leserechte",
                          role="Mitglied", docstatus=0, idx=1))
        sess.add(Element(name='EV "Zitat" 50% + mehr', element_name="Lobet & preist",
                         element_calendar='Kölner "Chor" + 100%', element_start=t,
                         element_end=t.replace(hour=11), all_day=False,
                         status="Festgelegt", docstatus=0, idx=0, creation=t, modified=t))
        sess.commit()
    finally:
        sess.close()

    body = _propfind_home(client)
    ET.fromstring(body)
    hrefs = _hrefs(body)
    ziel = next(h for h in hrefs if "Chor" in h)
    # `"` und `%` sind prozentkodiert, der Rest bleibt lesbar genug.
    assert "%22" in ziel and "%25" in ziel and "%20" in ziel

    # Der kodierte href trifft den Kalender wieder (genau ein Dekodierschritt).
    r = client.request("PROPFIND", ziel,
                       headers={**_basic("anna@example.org", "geheim"), "Depth": "1"})
    assert r.status_code == 207, ziel
    root = ET.fromstring(r.text)
    href_ev = next(h for h in (e.text for e in root.iter(DAV + "href")) if h.endswith(".ics"))
    g = client.get(href_ev, headers=_basic("anna@example.org", "geheim"))
    assert g.status_code == 200, href_ev
    assert 'UID:EV "Zitat" 50% + mehr@diakronos' in g.text
