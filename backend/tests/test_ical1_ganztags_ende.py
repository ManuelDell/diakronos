"""ICAL-1: ganztägiges Ende konsistent — CalDAV-Export und Kalender-Importe.

FESTLEGUNG (belegt): Diakronos speichert das Ende ganztägiger Termine
EINSCHLIESSLICH (Formular `datumZeit.mjs`: „7.–8.“ = 2 Tage, eintägig
Ende == Beginn). iCalendar (RFC 5545) und Google führen das Ende
AUSSCHLIESSLICH. Damit ist jede Grenze eine Tagesgrenze:

    Diakronos  <->  iCal/Google
    7. .. 8.        DTSTART 7., DTEND 9.
    7. .. 7.        DTSTART 7., DTEND 8.

Dieser Test hält BEIDE Richtungen fest und prüft den Rundlauf Export ->
Import am selben Termin (dabei darf sich kein Tag verschieben).
"""
from __future__ import annotations

import base64
from datetime import date, datetime

import pytest
from icalendar import Calendar
from sqlalchemy import select

import re

from diakronos_app.models.kronos import Element

PATH = "/api/method/diakronos.kronos.api.google_import."


def el(start, ende, all_day=True, name="EV-1"):
    """Minimales Element-Dokument wie es `element_to_ical` liest."""

    class El:
        element_name = "Ganztägig"
        description = None
        series_id = None
        modified = None

    doc = El()
    doc.name = name
    doc.element_start = start
    doc.element_end = ende
    doc.all_day = all_day
    return doc


def dtend(ics):
    prop = Calendar.from_ical(ics).walk("VEVENT")[0]["DTEND"]
    return prop.dt


# ─────────────────────────────────────────────────────────────────────────────
# C1 — CalDAV-Export: DTEND ist AUSSCHLIESSLICH (gespeichertes Ende + 1 Tag)
# ─────────────────────────────────────────────────────────────────────────────


def test_export_eintaegig_ist_begin_plus_ein_tag():
    """Eintägig: gespeichert 7. .. 7. -> DTSTART 7., DTEND 8."""
    from diakronos_app.caldav.ical import element_to_ical

    ics = element_to_ical(el(datetime(2026, 10, 7), datetime(2026, 10, 7)))
    assert "DTSTART;VALUE=DATE:20261007" in ics
    assert "DTEND;VALUE=DATE:20261008" in ics
    assert dtend(ics) == date(2026, 10, 8)


def test_export_mehrtaegig_zaehlt_einen_tag_dazu():
    """7.–8. (zwei Tage) -> DTEND 9. Der Client zeigt damit beide Tage."""
    from diakronos_app.caldav.ical import element_to_ical

    ics = element_to_ical(el(datetime(2026, 10, 7), datetime(2026, 10, 8)))
    assert "DTEND;VALUE=DATE:20261009" in ics
    assert dtend(ics) == date(2026, 10, 9)


def test_export_langes_ende_zaehlt_einen_tag_dazu():
    from diakronos_app.caldav.ical import element_to_ical

    ics = element_to_ical(el(datetime(2026, 12, 30), datetime(2026, 12, 31, 23, 59, 59)))
    assert "DTEND;VALUE=DATE:20270101" in ics


def test_export_ende_um_mitternacht_zaehlt_einen_tag_dazu():
    """Ein gespeichertes Ende exakt 00:00 des Folgetags ist ein Kalendertag
    mehr — DTEND wandert entsprechend auf den Tag danach."""
    from diakronos_app.caldav.ical import element_to_ical

    ics = element_to_ical(el(datetime(2026, 11, 1), datetime(2026, 11, 2, 0, 0)))
    assert "DTEND;VALUE=DATE:20261103" in ics


def test_export_ohne_ende_ist_eintaegig():
    """Kein gespeichertes Ende = eintägig -> DTEND = Beginn + 1 Tag."""
    from diakronos_app.caldav.ical import element_to_ical

    ics = element_to_ical(el(datetime(2026, 11, 1), None))
    assert "DTSTART;VALUE=DATE:20261101" in ics
    assert "DTEND;VALUE=DATE:20261102" in ics


def test_export_mit_uhrzeit_bleibt_unveraendert():
    """Die +1-Tag-Regel gilt NUR ganztägig (RFC 5545: DATE-Werte)."""
    from diakronos_app.caldav.ical import element_to_ical

    ics = element_to_ical(el(datetime(2026, 10, 27, 10), datetime(2026, 10, 27, 11), all_day=False))
    assert "DTSTART:20261027T100000" in ics
    assert "DTEND:20261027T110000" in ics
    assert "VALUE=DATE" not in ics


def test_export_dtend_ist_immer_nach_dtstart():
    """RFC 5545: DTEND muss echt nach DTSTART liegen — für jede Länge."""
    from diakronos_app.caldav.ical import element_to_ical

    for start, ende in [
        (datetime(2026, 1, 1), datetime(2026, 1, 1)),
        (datetime(2026, 1, 1), datetime(2026, 1, 5)),
        (datetime(2026, 2, 27), datetime(2026, 3, 1)),  # über den Monatswechsel
    ]:
        ics = element_to_ical(el(start, ende))
        assert dtend(ics) > start.date()


# ─────────────────────────────────────────────────────────────────────────────
# C2 — Google-Import (API-JSON): ausschließliches Ende -> speichern einschließend
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("start,end,erwartet", [
    ("2026-10-02", "2026-10-03", datetime(2026, 10, 2)),     # eintägig
    ("2026-10-07", "2026-10-09", datetime(2026, 10, 8)),     # zwei Tage
    ("2026-12-30", "2027-01-02", datetime(2027, 1, 1)),      # über den Jahreswechsel
    ("2026-10-02", "2026-10-02", datetime(2026, 10, 2)),     # defensiv: Ende == Beginn
])
def test_google_json_ganztags_ende_wird_einschliesslich(start, end, erwartet):
    from diakronos_app.api.kronos.google_import import _map_google_event

    fields = _map_google_event({
        "id": "g-1", "summary": "Ganztägig",
        "start": {"date": start}, "end": {"date": end},
    }, "Kalender")
    assert fields["all_day"] is True
    assert fields["element_start"] == datetime.fromisoformat(start)
    assert fields["element_end"] == erwartet


def test_google_json_ende_vor_beginn_bleibt_verworfen():
    """Unverändertes Verhalten: ein Termin, der vor seinem Beginn endet, wird
    übersprungen — die Tagesregel macht daraus keinen Scheintermin."""
    from diakronos_app.api.kronos.google_import import _map_google_event

    assert _map_google_event({
        "id": "g-3", "summary": "Kaputt",
        "start": {"date": "2026-10-03"}, "end": {"date": "2026-10-01"},
    }, "Kalender") is None


def test_google_json_mit_uhrzeit_unveraendert():
    """Die Tagesregel gilt nur ganztägig — datetimes bleiben wie sie kommen."""
    from diakronos_app.api.kronos.google_import import _map_google_event

    fields = _map_google_event({
        "id": "g-2", "summary": "Mit Uhrzeit",
        "start": {"dateTime": "2026-10-02T09:00:00+02:00"},
        "end": {"dateTime": "2026-10-02T11:00:00+02:00"},
    }, "Kalender")
    assert fields["all_day"] is False
    assert fields["element_start"] == datetime(2026, 10, 2, 9)
    assert fields["element_end"] == datetime(2026, 10, 2, 11)


# ─────────────────────────────────────────────────────────────────────────────
# C2 — Google-Import (ICS): DTEND und DURATION
# ─────────────────────────────────────────────────────────────────────────────


def upload(client, body):
    return client.post(PATH + "upload_ical", json={
        "file_content_b64": base64.b64encode(body.encode()).decode(),
        "calendar_name_new": "ICAL-1",
    })


def ics_body(*lines):
    return ("BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\nUID:ical1-" + str(hash(lines)) + "\n"
            + "\n".join(lines) + "\nEND:VEVENT\nEND:VCALENDAR\n")


@pytest.mark.parametrize("lines,start,ende", [
    (["DTSTART;VALUE=DATE:20261002", "DTEND;VALUE=DATE:20261003"],  # eintägig
     datetime(2026, 10, 2), datetime(2026, 10, 2)),
    (["DTSTART;VALUE=DATE:20261007", "DTEND;VALUE=DATE:20261009"],  # zwei Tage
     datetime(2026, 10, 7), datetime(2026, 10, 8)),
    (["DTSTART;VALUE=DATE:20261230", "DTEND;VALUE=DATE:20270102"],
     datetime(2026, 12, 30), datetime(2027, 1, 1)),
])
def test_import_ics_ganztags_dtend_wird_einschliesslich(client, patched_db, lines, start, ende):
    assert upload(client, ics_body(*lines, "SUMMARY:ICAL-1 DTEND")).status_code == 200
    with patched_db() as db:
        row = db.scalar(select(Element))
        assert row.all_day
        assert row.element_start == start
        assert row.element_end == ende


def test_import_ics_ganztags_duration_wird_einschliesslich(client, patched_db):
    """DURATION-Fall: P1D ist ein Tag, P3D sind drei Tage (DTEND = Beginn + 3)."""
    assert upload(client, ics_body(
        "DTSTART;VALUE=DATE:20261007", "DURATION:P3D", "SUMMARY:ICAL-1 Dauer",
    )).status_code == 200
    with patched_db() as db:
        row = db.scalar(select(Element))
        assert row.element_start == datetime(2026, 10, 7)
        assert row.element_end == datetime(2026, 10, 9)   # 7., 8., 9.


def test_import_ics_ganztags_duration_ein_tag(client, patched_db):
    assert upload(client, ics_body(
        "DTSTART;VALUE=DATE:20261007", "DURATION:P1D", "SUMMARY:ICAL-1 ein Tag",
    )).status_code == 200
    with patched_db() as db:
        row = db.scalar(select(Element))
        assert row.element_end == datetime(2026, 10, 7)   # Ende == Beginn


def test_import_ics_mehrtaegige_serie_bleibt_je_termin_korrekt(client, patched_db):
    """Serie: jedes Vorkommen behält seine echte Länge (7.–8. = 2 Tage)."""
    assert upload(client, ics_body(
        "DTSTART;VALUE=DATE:20261007", "DTEND;VALUE=DATE:20261009",
        "RRULE:FREQ=DAILY;COUNT=2", "SUMMARY:ICAL-1 Serie",
    )).status_code == 200
    with patched_db() as db:
        rows = db.scalars(select(Element).order_by(Element.element_start)).all()
        assert [(r.element_start, r.element_end) for r in rows] == [
            (datetime(2026, 10, 7), datetime(2026, 10, 8)),
            (datetime(2026, 10, 8), datetime(2026, 10, 9)),
        ]


def test_import_ics_mit_uhrzeit_bleibt_unveraendert(client, patched_db):
    assert upload(client, ics_body(
        "DTSTART;TZID=Europe/Berlin:20261005T180000",
        "DTEND;TZID=Europe/Berlin:20261005T190000", "SUMMARY:ICAL-1 Uhrzeit",
    )).status_code == 200
    with patched_db() as db:
        row = db.scalar(select(Element))
        assert not row.all_day
        assert row.element_start == datetime(2026, 10, 5, 18)
        assert row.element_end == datetime(2026, 10, 5, 19)


# ─────────────────────────────────────────────────────────────────────────────
# Rundlauf: Export -> Import darf keinen Tag verschieben
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("tage", [1, 2, 5])
def test_rundlauf_export_import_haelt_das_ende(tage):
    """Der von Diakronos exportierte Termin (n Tage) kommt mit n Tagen zurück."""
    from diakronos_app.api.kronos.google_import import _parse_ical
    from diakronos_app.caldav.ical import element_to_ical

    start = datetime(2026, 11, 1)
    ende = datetime(2026, 11, 1) + (tage - 1) * (datetime(2026, 11, 2) - datetime(2026, 11, 1))
    ics = element_to_ical(el(start, ende, name="EV-RUND"))
    events = _parse_ical(ics)
    assert len(events) == 1
    assert events[0]["all_day"] is True
    assert events[0]["element_start"] == start
    assert events[0]["element_end"] == ende


def test_rundlauf_export_ist_von_client_lesbar():
    """Ein Standard-Parser (icalendar) liest den Zeitraum so, wie das Formular
    ihn meint: 7.–8. ist 2 Kalendertage (Differenz DTEND-DTSTART = 2)."""
    from diakronos_app.caldav.ical import element_to_ical

    ev = Calendar.from_ical(element_to_ical(el(datetime(2026, 10, 7), datetime(2026, 10, 8)))).walk("VEVENT")[0]
    anzeige_tage = (ev["DTEND"].dt - ev["DTSTART"].dt).days
    assert anzeige_tage == 2


# ─────────────────────────────────────────────────────────────────────────────
# C3 — kein anderer Weg rechnet das Ende um (Beleg statt Vermutung)
# ─────────────────────────────────────────────────────────────────────────────


def test_kein_weiterer_schreibweg_rechnet_ganztags_um():
    """CalDAV ist read-only (kein PUT/ics-Import), Serien/Kopieren übertragen
    `element_start`/`element_end` unverändert. Deshalb gibt es außer Export und
    Import nur EINE Stelle mit Tagesarithmetik auf `element_end`."""
    from pathlib import Path

    src = Path(__file__).resolve().parents[1] / "src" / "diakronos_app"
    treffer = []
    for py in src.rglob("*.py"):
        if "planrahmen" in py.parts:
            continue
        text = py.read_text(encoding="utf-8", errors="ignore")
        for nr, zeile in enumerate(text.splitlines(), 1):
            if "element_end" in zeile and re.search(r"timedelta|days=|[+-] 1\b", zeile):
                treffer.append(f"{py.relative_to(src)}:{nr}")
    assert treffer == [], treffer
