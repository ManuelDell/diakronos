"""Reproduktionstests fuer P2-4 (Benachrichtigungen, Befund OP-HANDY-6).

Nachtpruefung: die Glocke „Benachrichtigungen" war ohne Funktion —
* der Zaehler kam nie an (`count` statt `unread_count`),
* es gab keine Liste (ein Klick setzte ungesehen alles auf gelesen),
* Plan-Veroeffentlichung, Terminaenderung und Buchungsentscheidung erzeugten
  nie einen Eintrag in ``Notification Log``.

Die Frontend-Haelfte (Zaehler/Liste/„erst dann gelesen") deckt
``frontend/tests/p2-4-benachrichtigungen.test.mjs`` ab. Hier steht die
Backend-Haelfte: das ERZEUGEN der Benachrichtigungen an den drei genannten
Stellen.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from diakronos_app.frappe_compat.api_helpers import _create

PFAD = "/api/method/diakronos.planrahmen.api."
PFAD_AUDIT = "/api/method/diakronos.diakonos.api.audit."


def aufruf(client, name, **daten):
    r = client.post(PFAD + name, json=daten)
    assert r.status_code == 200, r.text
    return r.json()["message"]


def anmelden(client, benutzer):
    from diakronos_app import frappe_compat
    from diakronos_app.frappe_compat import sitzungen

    frappe_compat.reset_user()
    sid, csrf = sitzungen.anlegen(benutzer)
    client.cookies.set("sid", sid)
    client.headers["X-Frappe-CSRF-Token"] = csrf


def stammdaten(sf, *benutzer):
    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import (
        Dienstbereich, DienstbereichVerantwortlicher, Mitglied,
    )

    with sf.begin() as s:
        s.add(Dienstbereich(name="Chor"))
        s.add_all([User(name=k, email=k, enabled=True) for k in benutzer])
        s.flush()
        s.add_all([Mitglied(name=k, user=k, email=k, vorname=k.capitalize(),
                            nachname="Test", status="Mitglied", docstatus=0, idx=0)
                   for k in benutzer])
        s.add(DienstbereichVerantwortlicher(
            name="bv-chor", parent="Chor", parenttype="Dienstbereich",
            parentfield="verantwortliche", user="planer"))


def chorplan_definition():
    return {
        "schema": "diakronos/plantyp@1", "id": "chor-p24", "name": "Chorplan",
        "bereich": "Chor",
        "termine": {"manuell": [{"datum": "2026-11-15", "uhrzeit": "10:00:00"}]},
        "felder": [
            {"id": "lieder", "art": "eintrag", "sammlung": "lieder", "name": "Lied",
             "inhalt": [
                 {"id": "dirigent", "art": "person", "name": "Dirigent"},
                 {"id": "klavier", "art": "person", "name": "Klavier"},
                 {"id": "solo", "art": "personen", "name": "Solo", "fuellen": "manuell"},
             ]},
        ],
    }


@pytest.fixture()
def planer(client, patched_db):
    stammdaten(patched_db, "planer", "mitglied", "dirigent")
    anmelden(client, "planer")
    return client


def _plan_mit_solo(client, mitglied="mitglied"):
    """Plantyp + Plan, ein Lied mit Dirigent und Solo — noch NICHT veroeffentlicht."""
    from diakronos_app.models.psalmos import Lied

    aufruf(client, "plantyp_speichern", definition=chorplan_definition(),
           gueltig_ab="2026-01-01")
    p = aufruf(client, "plan_anlegen", plantyp="chor-p24", titel="Chorplan P24",
               von="2026-11-01", bis="2026-11-30")["id"]
    plan = aufruf(client, "plan_holen", plan=p)
    termin = plan["termine"][0]["id"]
    aufruf(client, "eintrag_setzen", plan=p, termin=termin, feld_pfad="lieder", wert="lied-a")
    aufruf(client, "eintrag_setzen", plan=p, termin=termin, feld_pfad="lieder.dirigent",
           wert="dirigent")
    aufruf(client, "eintrag_setzen", plan=p, termin=termin, feld_pfad="lieder.solo",
           wert=[mitglied])
    return p, termin


@pytest.fixture()
def lieder(patched_db):
    from diakronos_app.models.psalmos import Lied

    with patched_db.begin() as s:
        s.add(Lied(name="lied-a", titel="Golgatha", aktiv=True,
                   gesangbuch_nummer="129", buch="JN"))


def _notifications(sf, user):
    """Subjects der Benachrichtigungen eines Users (Zeilen als Strings).

    Die Session wird IM Block gelesen — danach sind ORM-Objekte detached und
    ein Attributzugriff wuerde werfen.
    """
    from sqlalchemy import select

    from diakronos_app.models.core import NotificationLog

    with sf.begin() as s:
        return [r.subject for r in s.scalars(select(NotificationLog).where(
            NotificationLog.for_user == user)).all()]


# ── OP-HANDY-6a: unread_count liefert echte Zahl, Liste zeigt Eintraege ────


def test_unread_count_und_liste_liefern_eintraege(client, patched_db):
    """Eine geschriebene Benachrichtigung erscheint im Zaehler UND in der Liste."""
    stammdaten(patched_db, "mitglied")
    _create("Notification Log", {
        "subject": "Plan geändert: Chorplan P24", "for_user": "mitglied",
        "type": "Alert", "email_content": "Bitte prüfen.", "read": 0,
    })
    anmelden(client, "mitglied")

    r = client.post(PFAD_AUDIT + "get_unread_notifications", json={})
    assert r.status_code == 200, r.text
    assert r.json()["message"]["unread_count"] == 1

    r = client.post(PFAD_AUDIT + "get_my_notifications", json={})
    assert r.status_code == 200, r.text
    daten = r.json()["message"]["data"]
    assert [d["subject"] for d in daten] == ["Plan geändert: Chorplan P24"]


# ── OP-HANDY-6b: Plan-Veroeffentlichung benachrichtigt die Betroffenen ─────


def test_veroeffentlichen_benachrichtigt_eingeteilte(planer, patched_db, lieder):
    """Erstveroeffentlichung: der Eingeteilte bekommt genau eine Nachricht."""
    p, _ = _plan_mit_solo(planer, "mitglied")
    assert _notifications(patched_db, "mitglied") == []

    aufruf(planer, "veroeffentlichen", plan=p)

    nachrichten = _notifications(patched_db, "mitglied")
    assert len(nachrichten) == 1, "veroeffentlichen hat nicht benachrichtigt"
    assert "Chorplan P24" in nachrichten[0]


def test_veroeffentlichen_aenderung_benachrichtigt_umbesetzte(planer, patched_db, lieder):
    """Umbesetzung: der NEU Eingeteilte erfaehrt von der Aenderung.

    Beim zweiten Veroeffentlichen wurde das Solo von „mitglied" auf „dirigent"
    umgesetzt. Der bisherige Eintrag bleibt als Verlauf erhalten, deshalb
    erhaelt auch „mitglied" eine Nachricht (seine Zuordnung hat sich geaendert).
    Kern der Pruefung: „dirigent" (neu) wird informiert.
    """
    p, termin = _plan_mit_solo(planer, "mitglied")
    aufruf(planer, "veroeffentlichen", plan=p)
    vorher = _notifications(patched_db, "dirigent")

    aufruf(planer, "eintrag_setzen", plan=p, termin=termin, feld_pfad="lieder.solo",
           wert=["dirigent"])
    aufruf(planer, "veroeffentlichen", plan=p)

    neu = _notifications(patched_db, "dirigent")
    assert len(neu) == len(vorher) + 1, "Umbesetzung hat den neuen Eingeteilten nicht benachrichtigt"
    assert "geändert" in neu[-1]


def test_veroeffentlichung_ohne_eingeteilte_schreibt_nichts(planer, patched_db, lieder):
    """Kein Leerlauf: ohne betroffene Person entsteht kein Eintrag."""
    aufruf(planer, "plantyp_speichern", definition=chorplan_definition(),
           gueltig_ab="2026-01-01")
    p = aufruf(planer, "plan_anlegen", plantyp="chor-p24", titel="Leer",
               von="2026-11-01", bis="2026-11-30")["id"]
    aufruf(planer, "veroeffentlichen", plan=p)
    from diakronos_app.models.core import NotificationLog

    assert _notifications(patched_db, "mitglied") == []
    assert _notifications(patched_db, "dirigent") == []
    assert _notifications(patched_db, "planer") == []   # Planer mailt sich nicht selbst


# ── OP-HANDY-6c: Terminaenderung benachrichtigt die Eingeteilten ────────────


def _kalender_moderator_welt(sf, *,
                             aufrufer: str = "moderator",
                             eingeteilt: str = "talente",
                             mit_moderatorrecht: bool = True,
                             mit_leserecht: bool = True):
    """Kalender mit Schreibrecht (und optional Moderations-/Leserecht).

    P2-4b W-1/W-3: Der wirksame Pfad verlangt ein echtes Moderationsrecht
    (`Kalender Moderator`), die Benachrichtigung ein Leserecht des Empfaengers.
    """
    from diakronos_app.models.core import HasRole, User, UserRole
    from diakronos_app.models.diakonos import Mitglied
    from diakronos_app.models.kronos import (
        Element, ElementMitarbeiter, Kalender, KalenderModerator,
    )

    with sf.begin() as s:
        s.add(User(name=aufrufer, email=aufrufer, enabled=True))
        s.add(User(name=eingeteilt, email=eingeteilt, enabled=True))
        s.add(Mitglied(name="M-TAL", user=eingeteilt, email=eingeteilt,
                       vorname="Tina", nachname="Talente", status="Mitglied"))
        s.add(Kalender(name="K-GD", calendar_name="Gottesdienst", docstatus=0, idx=0))
        s.add(HasRole(name="r-auf", parent=aufrufer, parenttype="User",
                      parentfield="roles", role="Mitglied"))
        s.add(HasRole(name="r-ein", parent=eingeteilt, parenttype="User",
                      parentfield="roles", role="Mitglied"))
        s.add(UserRole(name="ur-auf", parent="K-GD", parenttype="Kalender",
                       parentfield="schreibrechte", role="Mitglied", docstatus=0, idx=1))
        if mit_leserecht:
            s.add(UserRole(name="ur-ein", parent="K-GD", parenttype="Kalender",
                           parentfield="leserechte", role="Mitglied", docstatus=0, idx=2))
        if mit_moderatorrecht:
            s.add(KalenderModerator(name="km-1", parent="K-GD", parenttype="Kalender",
                                    parentfield="kalendermoderatoren", user=aufrufer,
                                    docstatus=0, idx=1))
        s.add(Element(name="E-1", element_name="Gottesdienst", element_calendar="K-GD",
                      element_start=datetime(2026, 12, 6, 10, 0), element_end=datetime(2026, 12, 6, 11, 0),
                      status="Festgelegt", all_day=False, docstatus=0, idx=0, owner=aufrufer))
        s.add(ElementMitarbeiter(name="EM-1", parent="E-1", parenttype="Element",
                                 parentfield="mitarbeiter", mitglied="M-TAL",
                                 bestaetigt=True, docstatus=0, idx=1))


def test_terminaenderung_benachrichtigt_eingeteilte(client, patched_db):
    """W-1: Der WIRKSAME Moderator-Pfad erreicht die Eingeteilten.

    Vorher lief dieser Test nur ueber die Rolle „Mitglied“ + Schreibrecht — der
    Aufrufer war kein Moderator, die Verschiebung wartete als Vorschlag und die
    Asssertion traf die Wartend-Variante. Jetzt ist der Aufrufer wirklicher
    Moderator (`Kalender Moderator`) und die Aenderung wirkt sofort.
    """
    _kalender_moderator_welt(patched_db)
    anmelden(client, "moderator")
    r = client.post("/api/method/diakronos.kronos.api.event_crud.save_event",
                    json={"name": "E-1", "element_name": "Gottesdienst",
                          "element_start": "2026-12-06 14:00:00",
                          "element_end": "2026-12-06 15:00:00",
                          "element_calendar": "K-GD"})
    assert r.status_code == 200, r.text
    assert not r.json()["message"].get("aenderung_wartet"), "Änderung wartete statt zu wirken"

    nachrichten = _notifications(patched_db, "talente")
    assert len(nachrichten) == 1, "Terminverschiebung hat nicht benachrichtigt"
    assert "Termin geändert" in nachrichten[0]


def test_wartende_aenderung_meldet_nichts(client, patched_db):
    """W-2: Ohne Moderationsrecht wartet die Aenderung — und meldet noch nichts."""
    _kalender_moderator_welt(patched_db, mit_moderatorrecht=False)
    anmelden(client, "moderator")
    r = client.post("/api/method/diakronos.kronos.api.event_crud.save_event",
                    json={"name": "E-1", "element_name": "Gottesdienst",
                          "element_start": "2026-12-06 14:00:00",
                          "element_end": "2026-12-06 15:00:00",
                          "element_calendar": "K-GD"})
    assert r.status_code == 200, r.text
    assert r.json()["message"].get("aenderung_wartet"), "Änderung hätte warten müssen"
    assert _notifications(patched_db, "talente") == [], \
        "Ein wartender Vorschlag hat die Eingeteilten vorschnell benachrichtigt (W-2)"


def test_terminaenderung_ohne_mitarbeiter_schreibt_nichts(client, patched_db):
    """Ein Termin ohne Eingeteilte erzeugt keine Nachricht."""
    from diakronos_app.models.core import HasRole, User, UserRole
    from diakronos_app.models.kronos import Element, Kalender

    with patched_db.begin() as s:
        s.add(User(name="moderator", email="moderator", enabled=True))
        s.add(Kalender(name="K-GD", calendar_name="Gottesdienst", docstatus=0, idx=0))
        s.add(HasRole(name="r-mod", parent="moderator", parenttype="User",
                      parentfield="roles", role="Mitglied"))
        s.add(UserRole(name="ur-mod", parent="K-GD", parenttype="Kalender",
                       parentfield="schreibrechte", role="Mitglied", docstatus=0, idx=1))
        s.add(Element(name="E-2", element_name="Andacht", element_calendar="K-GD",
                      element_start=datetime(2026, 12, 6, 10, 0), element_end=datetime(2026, 12, 6, 11, 0),
                      status="Festgelegt", all_day=False, docstatus=0, idx=0, owner="moderator"))

    anmelden(client, "moderator")
    r = client.post("/api/method/diakronos.kronos.api.event_crud.save_event",
                    json={"name": "E-2", "element_name": "Andacht",
                          "element_start": "2026-12-06 14:00:00",
                          "element_end": "2026-12-06 15:00:00",
                          "element_calendar": "K-GD"})
    assert r.status_code == 200, r.text

    from diakronos_app.models.core import NotificationLog

    from sqlalchemy import select

    with patched_db.begin() as s:
        alle = s.scalars(select(NotificationLog)).all()
    assert alle == []


# ── OP-HANDY-6d: Buchungsentscheidung benachrichtigt den Antragsteller ─────


def test_buchungsentscheidung_benachrichtigt_antragsteller(client, patched_db):
    from diakronos_app.models.core import HasRole, User
    from diakronos_app.models.kronos import Ressource
    from diakronos_app.models.diakonos import RessourcenBuchung

    with patched_db.begin() as s:
        s.add(User(name="moderator", email="moderator", enabled=True))
        s.add(User(name="antrag", email="antrag", enabled=True))
        s.add(Ressource(name="R-1", ressource_name="Gemeindesaal", docstatus=0, idx=0))
        s.add(HasRole(name="r-mod", parent="moderator", parenttype="User",
                      parentfield="roles", role="Ressourcenmoderator"))
        s.add(RessourcenBuchung(
            name="B-1", ressource="R-1", zweck="Jugendabend",
            datum_von=datetime(2026, 12, 6, 18, 0), datum_bis=datetime(2026, 12, 6, 21, 0),
            gebucht_von="antrag", gebucht_von_name="Anton Antrag",
            status="Angefragt", docstatus=0, idx=0))

    anmelden(client, "moderator")
    r = client.post("/api/method/diakronos.diakonos.api.ressourcen.decide_buchung",
                    json={"buchung_id": "B-1", "entscheidung": "bestaetigen"})
    assert r.status_code == 200, r.text

    nachrichten = _notifications(patched_db, "antrag")
    assert len(nachrichten) == 1, "Buchungsentscheidung hat nicht benachrichtigt"
    assert "bestätigt" in nachrichten[0]
