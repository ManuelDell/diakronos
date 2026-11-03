"""BS-1b2 — Nachbesserung der oeffentlichen Lese-API (Opus-Review BS-1b).

Jeder Befund des Reviews hat hier seinen Test. Die Reihenfolge folgt den
Befund-Nummern (F1 … F8), F9 ist Doku und hat keinen Test.

Was geprueft wird
=================

F1  ``anmeldung_url`` nur fuer Links vom Typ GAST-Anmeldung (nicht fuer
    Mitglieds-Registrierungslinks) — Negativtest.
F2  ``termine()`` fragt nicht mehr je Zeile: die Zahl der SQL-Abfragen ist
    unabhaengig von der Zeilenzahl (1 Zeile vs. 8 Zeilen -> gleiche Zahl).
F3  Die Bild-Route schliesst VERSTECKTE Gruppen aus (``freigegebene_gruppe``).
F4  iCal nach RFC 5545: keine Leerzeilen im Dokument, ``DTEND;VALUE=DATE``
    exklusiv (Ende + 1 Tag, immer > DTSTART), ``DTSTAMP`` aus ``modified``,
    Steuerzeichen entfernt.
F5  '' (kein eigener Befund — F5 war die Testluecke, die F1–F4 schliessen)
F6  ``Vary: Origin`` auch auf iCal- und Bild-Antworten.
F7  ``Element.docstatus != 2`` im SQL-Filter; ID-Salz ohne ``secret_key`` ist
    zufaellig (kein fester Wert); im Register stehen KEINE nackten Namen.
F8  ``/website/oeffentlich/…`` liegt unter dem Praefix AUSSERHALB von
    ``/api/`` und wird nicht vom SPA-Catch-all geschluckt; der Kommentar in
    ``auth_middleware`` sagt das Richtige.

Netz (Kartenregel 11): ``patched_db`` (In-Memory-SQLite) und ``fake_redis``;
kein Test greift auf ``settings.database_url`` zu.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

import pytest

import diakronos_app.api  # noqa: F401 — registriert alle portierten Endpunkte
from diakronos_app.frappe_compat import sitzungen  # noqa: F401 — Fixture-Naht
from diakronos_app.models.diakonos import Gruppe, Registrierungslink
from diakronos_app.models.kronos import Element

PFAD = "website.oeffentlich"
MODUL = "diakronos_app.website.oeffentlich_api"

HEUTE = datetime.now().date()
MORGEN = HEUTE + timedelta(days=1)
UEBERMORGEN = HEUTE + timedelta(days=2)


# ── Bestand (eigener, kleiner Aufbau: die Tests hier brauchen nur Kalender
#    mit Freigabe, einen Gast-Link und einen Mitglieds-Link) ────────────────


@pytest.fixture()
def welt(patched_db):
    from diakronos_app.models.kronos import Kalender

    sess = patched_db()
    sess.add(
        Kalender(
            name="kal-gemeinde",
            calendar_name="Gemeinde",
            calendar_color="#1f6feb",
            website_freigabe=True,
            website_slug="gemeinde",
            website_nur_oeffentliche_kategorien=False,
        )
    )
    sess.add(
        Registrierungslink(
            name="link-gast",
            typ="Gast-Anmeldung",
            aktiv=True,
            slug="gasttoken123",
            element=None,
        )
    )
    # Mitglieds-Registrierungslink: eine Einladung in die Mitgliederverwaltung.
    sess.add(
        Registrierungslink(
            name="link-mitglied",
            typ="Mitglied-Registrierung",
            aktiv=True,
            slug="mitgliedtoken456",
            element=None,
        )
    )
    sess.add(
        Gruppe(
            name="gr-sichtbar",
            gruppenname="Jugendkreis",
            website_freigabe=True,
            website_slug="jugendkreis",
            sichtbarkeit="Öffentlich",
            bild=None,
        )
    )
    sess.add(
        Gruppe(
            name="gr-versteckt",
            gruppenname="Versteckter Kreis",
            website_freigabe=True,
            website_slug="versteckt",
            sichtbarkeit="Versteckt",
            bild=None,
        )
    )
    sess.commit()
    yield sess
    sess.close()


def _termin(sess, name: str, *, start=None, link: str | None = None,
            anmeldung_aktiv: bool = False, all_day: bool = False,
            ende=None, docstatus: int = 0, modified=None,
            beschreibung: str | None = None) -> Element:
    beginn = start or datetime.combine(MORGEN, datetime.min.time()).replace(hour=10)
    element = Element(
        name=name,
        element_name=f"Termin {name}",
        element_calendar="kal-gemeinde",
        element_start=beginn,
        element_end=ende or (beginn + timedelta(hours=1)),
        all_day=all_day,
        status="Festgelegt",
        description=beschreibung if beschreibung is not None
        else "<p>Beschreibung mit <b>HTML</b></p>",
        anmeldung_aktiv=anmeldung_aktiv,
        registrierungslink=link,
        docstatus=docstatus,
        modified=modified,
    )
    sess.add(element)
    sess.commit()
    return element


@pytest.fixture()
def gast(patched_db, fake_redis):
    from fastapi.testclient import TestClient

    from diakronos_app.main import app

    c = TestClient(app)
    c.__enter__()
    yield c
    c.__exit__(None, None, None)


def _get(c, name: str, **params):
    return c.get(f"/api/method/{PFAD}.{name}", params=params)


# ═══════════════════════════════════════════════════════════════════════════
# F1 — anmeldung_url nur fuer GAST-Anmeldelinks
# ═══════════════════════════════════════════════════════════════════════════


def test_f1_mitglieds_registrierungslink_wird_nicht_oeffentlich(gast, welt):
    """Ein Mitglieds-Registrierungslink darf NIE als ``anmeldung_url`` erscheinen.

    Er ist eine Einladung in die Mitgliederverwaltung (Person setzt ihr
    Passwort) — auf der oeffentlichen Website hat er nichts zu suchen.
    """
    _termin(welt, "t-mitglied", anmeldung_aktiv=True, link="link-mitglied")
    antwort = _get(gast, "termine", von=HEUTE.isoformat())
    assert antwort.status_code == 200, antwort.text
    daten = antwort.json()["message"][0]
    assert daten["titel"] == "Termin t-mitglied"
    assert daten["anmeldung_url"] == "", (
        f"Mitglieds-Registrierungslink wurde oeffentlich: {daten['anmeldung_url']}"
    )
    # Der Token selbst taucht nirgends auf.
    assert "mitgliedtoken456" not in antwort.text


def test_f1_gast_link_bleibt_oeffentlich(gast, welt):
    """Die Gegenprobe: ein GAST-Link erscheint weiterhin."""
    _termin(welt, "t-gast", anmeldung_aktiv=True, link="link-gast")
    daten = _get(gast, "termine", von=HEUTE.isoformat()).json()["message"][0]
    assert "gasttoken123" in daten["anmeldung_url"]
    assert "/gast" in daten["anmeldung_url"]


def test_f1_link_ohne_typ_ist_nicht_oeffentlich(gast, welt):
    """Ohne Typ (NULL) ist die Art unklar -> kein oeffentlicher Link."""
    link = welt.get(Registrierungslink, "link-gast")
    link.typ = None
    welt.commit()
    _termin(welt, "t-ohne-typ", anmeldung_aktiv=True, link="link-gast")
    daten = _get(gast, "termine", von=HEUTE.isoformat()).json()["message"][0]
    assert daten["anmeldung_url"] == ""


# ═══════════════════════════════════════════════════════════════════════════
# F2 — kein N+1: die Zahl der SQL-Abfragen haengt nicht an der Zeilenzahl
# ═══════════════════════════════════════════════════════════════════════════


def _abfragen_zaehlen(engine) -> list[int]:
    """Zaehlt die SELECT-Abfragen waehrend des Blocks."""
    from sqlalchemy import event

    zaehler: list[int] = [0]

    def _mitzaehlen(conn, cursor, statement, parameteren, context, many):
        if statement.lstrip().lower().startswith("select"):
            zaehler[0] += 1

    event.listen(engine, "before_cursor_execute", _mitzaehlen)
    return zaehler


def test_f2_abfragen_konstant_bei_mehr_zeilen(patched_db, engine, welt):
    """8 Termine kosten GENAU SO VIELE Abfragen wie 1 Termin (F2).

    Vorher: je Zeile 2 Abfragen (Gruppe + Registrierungslink) und je
    Anmeldelink eine EIGENE Sitzung fuer die Gemeinde-Adresse. Nachher: je
    eine ``IN (…)``-Abfrage fuer alle Zeilen und eine Einstellung pro Aufruf.
    """
    from sqlalchemy import event

    from diakronos_app.models.base import Base
    from diakronos_app.website import oeffentlich_daten as daten

    def _bauen(anzahl: int) -> object:
        """Frische Datenbank mit ``anzahl`` Terminen (je eigener Link+Gruppe)."""
        sitzung = patched_db()
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        from diakronos_app.models.kronos import Kalender

        sitzung.add(
            Kalender(
                name="kal-gemeinde", calendar_name="Gemeinde",
                website_freigabe=True, website_slug="gemeinde",
            )
        )
        for i in range(anzahl):
            sitzung.add(
                Registrierungslink(
                    name=f"link-{i}", typ="Gast-Anmeldung", aktiv=True,
                    slug=f"gasttoken{i}", element=None,
                )
            )
            sitzung.add(
                Gruppe(
                    name=f"gr-{i}", gruppenname=f"Gruppe {i}",
                    website_freigabe=True, website_slug=f"gruppe-{i}",
                    sichtbarkeit="Öffentlich",
                )
            )
            _termin(sitzung, f"t-{i}", anmeldung_aktiv=True, link=f"link-{i}")
            element = sitzung.get(Element, f"t-{i}")
            element.gruppe = f"gr-{i}"
            sitzung.commit()
        sitzung.commit()
        return sitzung

    anzahl: list[int] = [0]

    def _mitzaehlen(conn, cursor, statement, parameteren, context, many):
        if statement.lstrip().lower().startswith("select"):
            anzahl[0] += 1

    ergebnisse: dict[int, tuple[int, int]] = {}
    event.listen(engine, "before_cursor_execute", _mitzaehlen)
    try:
        for wieviele in (1, 8):
            sitzung = _bauen(wieviele)
            anzahl[0] = 0
            zeilen = daten.termine(sitzung, von=HEUTE, bis=HEUTE + timedelta(days=60))
            ergebnisse[wieviele] = (len(zeilen), anzahl[0])
            sitzung.close()
    finally:
        event.remove(engine, "before_cursor_execute", _mitzaehlen)

    einer_zeilen, einer_abfragen = ergebnisse[1]
    viele_zeilen, viele_abfragen = ergebnisse[8]
    assert einer_zeilen == 1
    assert viele_zeilen == 8
    assert viele_abfragen == einer_abfragen, (
        f"N+1: 1 Zeile -> {einer_abfragen} Abfragen, 8 Zeilen -> "
        f"{viele_abfragen} Abfragen"
    )


def test_f2_anreicherung_bleibt_korrekt(gast, welt):
    """Die Sammel-Abfragen liefern dieselben Werte wie vorher (Regressionsschutz)."""
    gruppe = welt.get(Gruppe, "gr-sichtbar")
    element = _termin(welt, "t-angereichert", anmeldung_aktiv=True, link="link-gast")
    element.gruppe = gruppe.name
    welt.commit()
    daten = _get(gast, "termine", von=HEUTE.isoformat()).json()["message"][0]
    assert daten["gruppe"] == {"slug": "jugendkreis", "name": "Jugendkreis"}
    assert "gasttoken123" in daten["anmeldung_url"]

    # Nicht freigegebene Gruppe bleibt bei ALLEN Zeilen ``null``.
    element2 = _termin(welt, "t-ohne-gruppe", start=datetime.combine(UEBERMORGEN, datetime.min.time()).replace(hour=10))
    element2.gruppe = "gr-versteckt"
    welt.commit()
    alle = _get(gast, "termine", von=HEUTE.isoformat()).json()["message"]
    versteckt = next(t for t in alle if t["titel"] == "Termin t-ohne-gruppe")
    assert versteckt["gruppe"] is None, "versteckte Gruppe wurde oeffentlich"


# ═══════════════════════════════════════════════════════════════════════════
# F3 — Bild-Route schliesst versteckte Gruppen aus
# ═══════════════════════════════════════════════════════════════════════════


def _bild_anlegen(monkeypatch, tmp_path, name: str = "foto.png") -> str:
    from diakronos_app.settings import settings

    monkeypatch.setattr(settings, "files_dir", str(tmp_path))
    daten = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00"
        b"\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    (tmp_path / name).write_bytes(daten)
    return f"/files/{name}"


def test_f3_versteckte_gruppe_hat_kein_bild(gast, welt, monkeypatch, tmp_path):
    adresse = _bild_anlegen(monkeypatch, tmp_path)
    for name in ("gr-sichtbar", "gr-versteckt"):
        gruppe = welt.get(Gruppe, name)
        gruppe.bild = adresse
    welt.commit()

    # Freigegeben und sichtbar -> Bild.
    assert gast.get("/website/bild/gruppe/jugendkreis").status_code == 200
    # Freigegeben, aber VERSTECKT -> 404 (BS-1b2/F3).
    antwort = gast.get("/website/bild/gruppe/versteckt")
    assert antwort.status_code == 404, (
        "das Bild einer versteckten Gruppe wurde ausgeliefert"
    )
    assert antwort.headers["content-type"].startswith("application/json")


# ═══════════════════════════════════════════════════════════════════════════
# F4 — iCal nach RFC 5545
# ═══════════════════════════════════════════════════════════════════════════


def _ics_zeilen(text: str) -> list[str]:
    """Inhaltszeilen eines ICS-Dokuments (RFC 5545: CRLF-getrennt)."""
    return [z for z in text.split("\r\n") if z != ""]


def test_f4_keine_leerzeilen_im_dokument(gast, welt):
    """Zeilen sind NIE leer; das Dokument beginnt und endet richtig (F4)."""
    _termin(welt, "t-1")
    _termin(welt, "t-2", start=datetime.combine(UEBERMORGEN, datetime.min.time()).replace(hour=9))
    text = gast.get("/website/ical/gemeinde.ics").text

    assert "\r\n\r\n" not in text, "Leerzeile im VCALENDAR"
    roh = text.split("\r\n")
    assert roh[-1] == "", "Dokument endet nicht mit CRLF"
    zeilen = [z for z in roh[:-1]]
    assert all(z != "" for z in zeilen), "es gibt eine leere Inhaltszeile"
    # Jede Zeile hat einen Namen (oder ist eine Fortsetzung mit Leerzeichen/TAB).
    for zeile in zeilen:
        assert zeile[:1] in (" ", "\t") or ":" in zeile or ";" in zeile, zeile
    assert zeilen[0] == "BEGIN:VCALENDAR"
    assert zeilen[-1] == "END:VCALENDAR"


def test_f4_ganztaegig_dtend_ist_exklusiv(gast, welt):
    """``DTEND;VALUE=DATE`` ist der erste Tag NACH dem Termin (RFC 5545).

    BS-1bc (iCal-Ganztagsende): Diakronos speichert das Ende EINSCHLIESSLICH
    (Formular zählt „n Tage" inkl. letztem Tag) — ein eintägiger Termin hat
    Ende == Beginn. iCal-DTEND ist AUSSCHLIESSLICH, also immer Ende + 1 Tag.

      * eintägig (Ende == Beginn) -> DTEND = Beginn + 1;
      * drei Tage (Ende = Beginn + 2, inkl.) -> DTEND = Beginn + 3;
      * Ende 00:00 des letzten Tages -> letzter Tag + 1.
    """
    from icalendar import Calendar

    beginn = datetime.combine(MORGEN, datetime.min.time())
    # Eintägig: gespeichertes Ende == Beginn (einschliesslich).
    _termin(welt, "t-eintag", start=beginn, ende=beginn, all_day=True)
    # Drei Tage 02.–04.11. einschliesslich: Ende = 04.11.
    _termin(
        welt, "t-dreitag", start=beginn,
        ende=beginn + timedelta(days=2), all_day=True,
    )
    # Ende mit Uhrzeit 00:00 des letzten Tages zaehlt wie das Datum selbst.
    _termin(
        welt, "t-mitternacht", start=beginn,
        ende=datetime.combine(MORGEN + timedelta(days=1), datetime.min.time()),
        all_day=True,
    )
    cal = Calendar.from_ical(gast.get("/website/ical/gemeinde.ics").content)
    events = {str(e.get("summary")): e for e in cal.walk("VEVENT")}

    eintag = events["Termin t-eintag"]
    assert eintag.decoded("dtstart") == MORGEN
    assert eintag.decoded("dtend") == MORGEN + timedelta(days=1), (
        f"DTEND des eintaegigen Termins ist nicht exklusiv: "
        f"{eintag.decoded('dtend')}"
    )

    dreitag = events["Termin t-dreitag"]
    assert dreitag.decoded("dtstart") == MORGEN
    assert dreitag.decoded("dtend") == MORGEN + timedelta(days=3), (
        f"DTEND des dreitaegigen Termins: {dreitag.decoded('dtend')}"
    )

    mitternacht = events["Termin t-mitternacht"]
    assert mitternacht.decoded("dtend") == MORGEN + timedelta(days=2), (
        f"DTEND bei Ende 00:00: {mitternacht.decoded('dtend')}"
    )
    # Strenge Pruefung fuer JEDEN Termin: DTEND > DTSTART.
    for event in cal.walk("VEVENT"):
        assert event.decoded("dtend") > event.decoded("dtstart"), str(event.get("summary"))


def test_f4_ganztaegig_ohne_ende_ist_ein_tag(gast, welt):
    """Ohne ``element_end`` ist der Termin eintägig -> DTEND = DTSTART + 1 (F4)."""
    from icalendar import Calendar

    element = _termin(welt, "t-ohne-ende", all_day=True)
    element.element_end = None
    welt.commit()
    cal = Calendar.from_ical(gast.get("/website/ical/gemeinde.ics").content)
    event = list(cal.walk("VEVENT"))[0]
    assert event.decoded("dtend") == event.decoded("dtstart") + timedelta(days=1)


def test_f4_dtstamp_kommt_aus_modified(gast, welt):
    """``DTSTAMP`` ist der Stand der Zeile, nicht ``jetzt`` (F4).

    ``modified`` liegt als WANDZEIT in der Gemeinde-Zeitzone (so speichert die
    App Termine); DTSTAMP ist nach RFC 5545 ein UTC-Zeitpunkt. Geprueft wird
    deshalb die Umrechnung, nicht die nackte Uhrzeit.
    """
    from icalendar import Calendar
    from zoneinfo import ZoneInfo

    from diakronos_app.website import oeffentlich_inhalt as inhalt

    stand = datetime(2026, 3, 4, 5, 6, 7)
    _termin(welt, "t-stand", modified=stand)
    cal = Calendar.from_ical(gast.get("/website/ical/gemeinde.ics").content)
    event = list(cal.walk("VEVENT"))[0]
    dtstamp = event.decoded("dtstamp")
    erwartet = stand.replace(tzinfo=ZoneInfo(inhalt.ZEITZONE)).astimezone(
        ZoneInfo("UTC")
    )
    assert dtstamp == erwartet, f"DTSTAMP {dtstamp} != {erwartet}"
    # Und NICHT "jetzt": der Test waere sonst zufaellig gruen.
    jetzt = datetime.now(tz=ZoneInfo("UTC"))
    assert abs((jetzt - dtstamp).days) > 30


def test_f4_steuerzeichen_werden_entfernt(gast, welt):
    """Steuerzeichen aus der Datenbank landen NICHT im Feed (F4)."""
    from icalendar import Calendar

    element = _termin(
        welt, "t-steuer",
        beschreibung="Zeile 1\r\nZeile 2\x00\x07\x1b[31mrot\x7f Ende",
    )
    element.element_name = "Titel\x01\x02 mit Steuer"
    welt.commit()

    text = gast.get("/website/ical/gemeinde.ics").text
    # Keine rohen Steuerzeichen ausser CR/LF/TAB (Faltung nutzt ein Leerzeichen).
    verboten = {chr(i) for i in range(0x00, 0x20)} - {"\r", "\n", "\t"}
    assert not (set(text) & verboten), "Steuerzeichen im Feed"
    assert "\x7f" not in text

    cal = Calendar.from_ical(text.encode("utf-8"))
    event = list(cal.walk("VEVENT"))[0]
    assert "Zeile 1" in str(event.get("summary")) or "Titel" in str(event.get("summary"))
    beschreibung = str(event.get("description"))
    assert "Zeile 1" in beschreibung and "Zeile 2" in beschreibung


# ═══════════════════════════════════════════════════════════════════════════
# F6 — Vary: Origin auf iCal- und Bild-Antworten
# ═══════════════════════════════════════════════════════════════════════════


def test_f6_vary_origin_auf_ical(gast, welt):
    _termin(welt, "t-vary")
    antwort = gast.get("/website/ical/gemeinde.ics")
    assert antwort.status_code == 200
    assert "origin" in antwort.headers.get("vary", "").lower(), (
        "Vary: Origin fehlt auf der iCal-Antwort"
    )


def test_f6_vary_origin_auf_bild(gast, welt, monkeypatch, tmp_path):
    adresse = _bild_anlegen(monkeypatch, tmp_path)
    gruppe = welt.get(Gruppe, "gr-sichtbar")
    gruppe.bild = adresse
    welt.commit()
    antwort = gast.get("/website/bild/gruppe/jugendkreis")
    assert antwort.status_code == 200
    assert "origin" in antwort.headers.get("vary", "").lower(), (
        "Vary: Origin fehlt auf der Bild-Antwort"
    )


# ═══════════════════════════════════════════════════════════════════════════
# F7 — Haertung
# ═══════════════════════════════════════════════════════════════════════════


def test_f7_geloeschte_termine_bleiben_innen(gast, welt):
    """``docstatus == 2`` (geloescht) erscheint nicht — auch nicht im iCal (F7)."""
    _termin(welt, "t-ok")
    geloescht = _termin(welt, "t-geloescht", start=datetime.combine(UEBERMORGEN, datetime.min.time()).replace(hour=9))
    geloescht.docstatus = 2
    welt.commit()

    daten = _get(gast, "termine", von=HEUTE.isoformat()).json()["message"]
    assert [t["titel"] for t in daten] == ["Termin t-ok"]
    text = gast.get("/website/ical/gemeinde.ics").text
    assert "Termin t-geloescht" not in text


def test_f7_salz_ohne_secret_key_ist_zufaellig(monkeypatch):
    """Ohne ``secret_key`` ist das Salz NICHT fest — sondern ein Prozesswert (F7).

    Der alte feste Wert (``"diakronos-website"``) machte die Kennung in jedem
    Betrieb nachrechenbar: jeder kennt das Salz und damit die Kennung zu einem
    bekannten internen Namen.
    """
    import hashlib

    from diakronos_app.settings import settings
    from diakronos_app.website import oeffentlich_auswahl as auswahl

    with monkeypatch.context() as m:
        m.setattr(auswahl, "_PROZESSSALZ", "", raising=False)
        m.setattr(settings, "secret_key", "")
        kennung = auswahl.oeffentliche_kennung("termin", "t-abc")
        assert len(kennung) == 32
        # Der alte feste Wert ist es NICHT.
        alt = hashlib.sha256(b"diakronos-website|termin|t-abc").hexdigest()[:32]
        assert kennung != alt, "das alte feste Salz wird weiter benutzt"
        # Innerhalb des Prozesses stabil.
        assert auswahl.oeffentliche_kennung("termin", "t-abc") == kennung

        # Ein neuer Prozesswert ergibt eine ANDERE Kennung.
        m.setattr(auswahl, "_PROZESSSALZ", "")
        assert auswahl.oeffentliche_kennung("termin", "t-abc") != kennung


def test_f7_platzhalter_secret_key_zaehlt_nicht_als_salz(monkeypatch):
    """Der Vorgabewert ``insecure-dev-key`` ist kein Geheimnis -> Prozesssalz."""
    from diakronos_app.settings import settings
    from diakronos_app.website import oeffentlich_auswahl as auswahl

    with monkeypatch.context() as m:
        m.setattr(auswahl, "_PROZESSSALZ", "", raising=False)
        m.setattr(settings, "secret_key", "insecure-dev-key")
        erste = auswahl.oeffentliche_kennung("termin", "t-abc")
        m.setattr(auswahl, "_PROZESSSALZ", "")
        assert auswahl.oeffentliche_kennung("termin", "t-abc") != erste


def test_f7_keine_nackten_namen_im_register():
    """Die Lese-API ist NUR unter ``website.oeffentlich.*`` (+ Frappe-Pfad) da (F7).

    Nackte Namen wie ``termine`` oder ``gruppe`` kollidieren mit den
    gleichnamigen Verwaltungsfunktionen.
    """
    from diakronos_app.frappe_compat import registry

    for name in ("kalender", "termine", "naechster_termin", "gruppen",
                 "gruppe", "beitraege"):
        fn = registry.lookup(f"{PFAD}.{name}")
        assert fn is not None, f"{PFAD}.{name} fehlt"
        assert fn.__module__ == MODUL
        # Der nackte Name zeigt NICHT auf die oeffentliche Fassung.
        nackt = registry.lookup(name)
        assert nackt is not fn, f"nackter Name '{name}' zeigt auf die Lese-API"
        # Der Frappe-Originalpfad bleibt erreichbar.
        assert registry.lookup(f"diakronos.diakronos.api.website.{name}") is fn


# ═══════════════════════════════════════════════════════════════════════════
# F8 — Praefix-Route ausserhalb /api/ wird nicht vom SPA-Catch-all geschluckt
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture()
def app_mit_praefix():
    from diakronos_app import base_path
    from diakronos_app.main import erstelle_app
    from diakronos_app.settings import settings as echte

    alt_wert = echte.diakronos_base_path
    alt_praefix = base_path.aktiver_praefix()
    object.__setattr__(echte, "diakronos_base_path", "/diakronos")
    try:
        yield erstelle_app()
    finally:
        object.__setattr__(echte, "diakronos_base_path", alt_wert)
        base_path.setze_praefix(alt_praefix)


@pytest.fixture()
def gast_praefix(app_mit_praefix, patched_db, fake_redis):
    from fastapi.testclient import TestClient

    c = TestClient(app_mit_praefix)
    c.__enter__()
    yield c
    c.__exit__(None, None, None)


def test_f8_oeffentlich_pfad_nicht_vom_spa_catch_all_geschluckt(gast_praefix, welt):
    """``/diakronos/website/oeffentlich/termine`` liefert JSON, kein HTML (F8)."""
    _termin(welt, "t-f8")
    antwort = gast_praefix.get("/diakronos/website/oeffentlich/termine")
    assert antwort.status_code == 200, antwort.text
    assert antwort.headers["content-type"].startswith("application/json")
    assert antwort.json()["message"][0]["titel"] == "Termin t-f8"
    assert "<html" not in antwort.text.lower()

    # iCal und Bild genauso.
    ics = gast_praefix.get("/diakronos/website/ical/gemeinde.ics")
    assert ics.headers["content-type"].startswith("text/calendar")
    assert "<html" not in ics.text.lower()


def test_f8_kommentar_in_auth_middleware_ist_korrekt():
    """Der Kommentar nennt den Pfad AUSSERHALB von /api/ (F8).

    Die alte Fassung sagte, ``website.oeffentlich.*`` stehe als eigener
    Eintrag in ``_OEFFENTLICHE_WEBSITE_NAMEN`` — es gibt keinen und es braucht
    keinen, weil die CORS-Variante unter ``/website/oeffentlich/…`` liegt.

    BS-1bc (Querfix): Die Ausnahmemenge darf die SECHTS oeffentlichen
    Lese-Endpunkte weiterhin NICHT nennen. Die Postfach-Liste
    (`website.oeffentlich.postfaecher` samt Aliasen) ist dagegen bewusst
    drin — BS-1c2 braucht sie fuer die Primo-Herkunft. Deshalb wird hier
    gegen die feste Lese-Liste geprueft und nicht mehr gegen das Wort
    „oeffentlich".
    """
    from pathlib import Path

    import diakronos_app.frappe_compat.auth_middleware as mw

    quelle = Path(mw.__file__).read_text(encoding="utf-8")
    assert "_OEFFENTLICHE_WEBSITE_NAMEN" in quelle
    # Die Ausnahmemenge nennt KEINEN oeffentlichen LESE-Endpunkt.
    lese_endpunkte = {
        "website.oeffentlich.kalender",
        "website.oeffentlich.termine",
        "website.oeffentlich.naechster_termin",
        "website.oeffentlich.gruppen",
        "website.oeffentlich.gruppe",
        "website.oeffentlich.beitraege",
    }
    assert not (lese_endpunkte & set(mw._OEFFENTLICHE_WEBSITE_NAMEN))
    assert not any(
        ".oeffentlich." in name and not name.endswith(".postfaecher")
        for name in mw._OEFFENTLICHE_WEBSITE_NAMEN
    )
    # Der Kommentar erklaert den Pfad ausserhalb /api/ — und behauptet NICHT
    # mehr, es gaebe einen Eintrag dafuer.
    assert "/website/oeffentlich/" in quelle
    assert not re.search(
        r"`website\.oeffentlich\.\*` steht als eigener", quelle
    ), "alter, falscher Kommentar steht noch da"

