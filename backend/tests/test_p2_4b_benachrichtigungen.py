"""Reproduktionstests fuer P2-4b — Benachrichtigungen (Nachtpruefung).

Deckt die blockierenden Befunde B-1/B-2 und die wichtigen W-1..W-3 aus
des vorausgehenden Reviews ab:

* B-2/W-1: „Termin geändert“ nur bei ECHTEN Wertaenderungen (alt/neu), im
  wirksamen MODERATOR-Pfad — nicht bei jeder Speicherung des vollen Feldsatzes.
* W-2:   Serien-Batch buendelt zu EINER Nachricht je Empfaenger; ein wartender
  Vorschlag eines Nicht-Moderators meldet nichts (erst die Freigabe).
* W-3:   Nur Empfaenger mit Leserecht auf den Kalender werden benachrichtigt.

B-1 (Attributfehler in ``decide_termin_ressource``) wird von den
P1-4b-Tests abgedeckt (``test_p1_4b_ressourcen.py::test_b1_*``).
"""

from __future__ import annotations

from datetime import datetime

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


def _notifications(sf, user):
    """Subjects der Benachrichtigungen eines Users (Zeilen als Strings)."""
    from sqlalchemy import select

    from diakronos_app.models.core import NotificationLog

    with sf.begin() as s:
        return [r.subject for r in s.scalars(select(NotificationLog).where(
            NotificationLog.for_user == user)).all()]





def _moderator_welt(sf, *, mitglied_user: str = "talente"):
    """Kalender mit Schreibrecht für `moderator`, ein festgelegter Termin mit Eingeteiltem.

    `mitglied_user` bekommt Leserecht (W-3) — sonst wird er nicht benachrichtigt.
    """
    from diakronos_app.models.core import HasRole, User, UserRole
    from diakronos_app.models.diakonos import Mitglied
    from diakronos_app.models.kronos import (
        Element, ElementMitarbeiter, Kalender, KalenderModerator,
    )

    with sf.begin() as s:
        s.add(User(name="moderator", email="moderator", enabled=True))
        s.add(User(name=mitglied_user, email=mitglied_user, enabled=True))
        s.add(Mitglied(name="M-TAL", user=mitglied_user, email=mitglied_user,
                       vorname="Tina", nachname="Talente", status="Mitglied"))
        s.add(Kalender(name="K-GD", calendar_name="Gottesdienst", docstatus=0, idx=0))
        s.add(HasRole(name="r-mod", parent="moderator", parenttype="User",
                      parentfield="roles", role="Mitglied"))
        # W-3: der Eingeteilte traegt die Rolle, ueber die er den Kalender liest.
        s.add(HasRole(name="r-tal", parent=mitglied_user, parenttype="User",
                      parentfield="roles", role="Mitglied"))
        s.add(UserRole(name="ur-mod", parent="K-GD", parenttype="Kalender",
                       parentfield="schreibrechte", role="Mitglied", docstatus=0, idx=1))
        # W-1: der Aufrufer ist WIRKLICH Moderator (nicht nur Schreiber) — nur
        # so wirkt die Zeitänderung sofort und der wirksame Pfad wird geprüft.
        s.add(KalenderModerator(name="km-1", parent="K-GD", parenttype="Kalender",
                                parentfield="kalendermoderatoren", user="moderator",
                                docstatus=0, idx=1))
        # W-3: der Eingeteilte darf den Kalender LESEN.
        s.add(UserRole(name="ur-tal", parent="K-GD", parenttype="Kalender",
                       parentfield="leserechte", role="Mitglied", docstatus=0, idx=2))
        s.add(Element(name="E-1", element_name="Gottesdienst", element_calendar="K-GD",
                      element_start=datetime(2026, 12, 6, 10, 0),
                      element_end=datetime(2026, 12, 6, 11, 0),
                      status="Festgelegt", all_day=False, docstatus=0, idx=0, owner="moderator"))
        s.add(ElementMitarbeiter(name="EM-1", parent="E-1", parenttype="Element",
                                 parentfield="mitarbeiter", mitglied="M-TAL",
                                 bestaetigt=True, docstatus=0, idx=1))


def _speichere_termin(client, **felder):
    daten = {"name": "E-1", "element_calendar": "K-GD", **felder}
    r = client.post("/api/method/diakronos.kronos.api.event_crud.save_event", json=daten)
    assert r.status_code == 200, r.text
    return r


def test_b2_titel_aenderung_meldet_keine_terminverschiebung(client, patched_db):
    """B-2: Nur der Titel geändert (Moderator) — der Eingeteilte hört nichts.

    `save_event` schickt immer den vollen Feldsatz (Datum/Uhrzeit/Kalender).
    Vorher galt das als „Termin geändert“ mit Zeit-/Kalender-Hinweis, obwohl
    sich für den Eingeteilten nichts geändert hat.
    """
    _moderator_welt(patched_db)
    anmelden(client, "moderator")

    # Gleiche Zeit, gleicher Kalender, nur anderer Titel.
    _speichere_termin(client, element_name="Gottesdienst (neu)",
                      element_start="2026-12-06 10:00:00",
                      element_end="2026-12-06 11:00:00")

    assert _notifications(patched_db, "talente") == [], \
        "Reine Titeländerung hat eine Terminänderung gemeldet (B-2)"


def test_b2_echte_verschiebung_meldet_weiterhin(client, patched_db):
    """B-2 Gegenprobe: eine echte Zeitänderung erzeugt genau eine Nachricht."""
    _moderator_welt(patched_db)
    anmelden(client, "moderator")

    _speichere_termin(client, element_name="Gottesdienst",
                      element_start="2026-12-06 14:00:00",
                      element_end="2026-12-06 15:00:00")

    nachrichten = _notifications(patched_db, "talente")
    assert len(nachrichten) == 1, "Echte Verschiebung hat nicht benachrichtigt"
    assert "Termin geändert" in nachrichten[0]


def test_w1_moderator_ohne_wirksame_aenderung_keine_nachricht(client, patched_db):
    """W-1: Der WIRKSAME (Moderator-)Pfad — unverändert gespeichert = nichts."""
    _moderator_welt(patched_db)
    anmelden(client, "moderator")

    # Genau derselbe Stand wie in der DB.
    _speichere_termin(client, element_name="Gottesdienst",
                      element_start="2026-12-06 10:00:00",
                      element_end="2026-12-06 11:00:00")

    assert _notifications(patched_db, "talente") == [], \
        "Moderator-Speichern ohne Wertänderung hat gemeldet (B-2/W-1)"


def test_w2_wartende_aenderung_benachrichtigt_erst_bei_freigabe(client, patched_db):
    """W-2: Ein Nicht-Moderator-Vorschlag meldet NICHTS, die Freigabe dann schon."""
    from diakronos_app.models.core import HasRole, User, UserRole
    from diakronos_app.models.diakonos import Mitglied
    from diakronos_app.models.kronos import Element, ElementMitarbeiter, Kalender

    with patched_db.begin() as s:
        s.add(User(name="schreiber", email="schreiber", enabled=True))
        s.add(User(name="talente", email="talente", enabled=True))
        s.add(Mitglied(name="M-TAL", user="talente", email="talente",
                       vorname="Tina", nachname="Talente", status="Mitglied"))
        s.add(Kalender(name="K-GD", calendar_name="Gottesdienst", docstatus=0, idx=0))
        s.add(HasRole(name="r-sch", parent="schreiber", parenttype="User",
                      parentfield="roles", role="Mitglied"))
        s.add(HasRole(name="r-tal-w2", parent="talente", parenttype="User",
                      parentfield="roles", role="Mitglied"))
        s.add(UserRole(name="ur-sch", parent="K-GD", parenttype="Kalender",
                       parentfield="schreibrechte", role="Mitglied", docstatus=0, idx=1))
        s.add(UserRole(name="ur-tal", parent="K-GD", parenttype="Kalender",
                       parentfield="leserechte", role="Mitglied", docstatus=0, idx=2))
        s.add(Element(name="E-1", element_name="Gottesdienst", element_calendar="K-GD",
                      element_start=datetime(2026, 12, 6, 10, 0),
                      element_end=datetime(2026, 12, 6, 11, 0),
                      status="Festgelegt", all_day=False, docstatus=0, idx=0, owner="schreiber"))
        s.add(ElementMitarbeiter(name="EM-1", parent="E-1", parenttype="Element",
                                 parentfield="mitarbeiter", mitglied="M-TAL",
                                 bestaetigt=True, docstatus=0, idx=1))

    anmelden(client, "schreiber")
    r = client.post("/api/method/diakronos.kronos.api.event_crud.save_event",
                    json={"name": "E-1", "element_name": "Gottesdienst",
                          "element_start": "2026-12-06 14:00:00",
                          "element_end": "2026-12-06 15:00:00",
                          "element_calendar": "K-GD"})
    assert r.status_code == 200, r.text
    assert r.json()["message"].get("aenderung_wartet"), "Vorschlag wurde nicht als wartend gemeldet"
    assert _notifications(patched_db, "talente") == [], \
        "Ein wartender Vorschlag hat die Eingeteilten schon benachrichtigt (W-2)"


def test_w3_ohne_leserecht_keine_nachricht(client, patched_db):
    """W-3: Wer den Kalender nicht lesen darf, bekommt keine Terminnachricht."""
    from diakronos_app.models.core import HasRole, User, UserRole
    from diakronos_app.models.diakonos import Mitglied
    from diakronos_app.models.kronos import Element, ElementMitarbeiter, Kalender, KalenderModerator

    with patched_db.begin() as s:
        s.add(User(name="moderator", email="moderator", enabled=True))
        s.add(User(name="fremd", email="fremd", enabled=True))
        s.add(KalenderModerator(name="km-w3", parent="K-GD", parenttype="Kalender",
                                parentfield="kalendermoderatoren", user="moderator",
                                docstatus=0, idx=1))
        s.add(Mitglied(name="M-FR", user="fremd", email="fremd",
                       vorname="Fred", nachname="Fremd", status="Mitglied"))
        s.add(Kalender(name="K-GD", calendar_name="Gottesdienst", docstatus=0, idx=0))
        s.add(HasRole(name="r-mod", parent="moderator", parenttype="User",
                      parentfield="roles", role="Mitglied"))
        s.add(UserRole(name="ur-mod", parent="K-GD", parenttype="Kalender",
                       parentfield="schreibrechte", role="Mitglied", docstatus=0, idx=1))
        # KEIN Leserecht für `fremd`.
        s.add(Element(name="E-1", element_name="Geheime Sitzung", element_calendar="K-GD",
                      element_start=datetime(2026, 12, 6, 10, 0),
                      element_end=datetime(2026, 12, 6, 11, 0),
                      status="Festgelegt", all_day=False, docstatus=0, idx=0, owner="moderator"))
        s.add(ElementMitarbeiter(name="EM-1", parent="E-1", parenttype="Element",
                                 parentfield="mitarbeiter", mitglied="M-FR",
                                 bestaetigt=True, docstatus=0, idx=1))

    anmelden(client, "moderator")
    _speichere_termin(client, element_name="Geheime Sitzung",
                      element_start="2026-12-06 14:00:00",
                      element_end="2026-12-06 15:00:00")

    assert _notifications(patched_db, "fremd") == [], \
        "Empfänger ohne Leserecht wurde benachrichtigt (W-3)"


def test_w2_serie_buendelt_zu_einer_nachricht(client, patched_db):
    """W-2: Eine Serienverschiebung erzeugt EINE Nachricht je Person, nicht je Termin."""
    from diakronos_app.models.core import HasRole, User, UserRole
    from diakronos_app.models.diakonos import Mitglied
    from diakronos_app.models.kronos import (
        Element, ElementMitarbeiter, Kalender, KalenderModerator,
    )

    with patched_db.begin() as s:
        s.add(User(name="moderator", email="moderator", enabled=True))
        s.add(User(name="talente", email="talente", enabled=True))
        s.add(Mitglied(name="M-TAL", user="talente", email="talente",
                       vorname="Tina", nachname="Talente", status="Mitglied"))
        s.add(Kalender(name="K-GD", calendar_name="Gottesdienst", docstatus=0, idx=0))
        s.add(HasRole(name="r-mod", parent="moderator", parenttype="User",
                      parentfield="roles", role="Mitglied"))
        s.add(HasRole(name="r-tal-ser", parent="talente", parenttype="User",
                      parentfield="roles", role="Mitglied"))
        s.add(UserRole(name="ur-mod", parent="K-GD", parenttype="Kalender",
                       parentfield="schreibrechte", role="Mitglied", docstatus=0, idx=1))
        # W-1/W-2: nur ein WIRKLICHER Moderator aendert eine festgelegte Serie
        # sofort — sonst wartet jede Zeile als Vorschlag.
        s.add(KalenderModerator(name="km-ser", parent="K-GD", parenttype="Kalender",
                                parentfield="kalendermoderatoren", user="moderator",
                                docstatus=0, idx=1))
        s.add(UserRole(name="ur-tal", parent="K-GD", parenttype="Kalender",
                       parentfield="leserechte", role="Mitglied", docstatus=0, idx=2))
        for i in range(3):
            name = f"E-{i}"
            s.add(Element(name=name, element_name="Gottesdienst", element_calendar="K-GD",
                          element_start=datetime(2026, 12, 6 + i, 10, 0),
                          element_end=datetime(2026, 12, 6 + i, 11, 0),
                          status="Festgelegt", all_day=False, docstatus=0, idx=0,
                          owner="moderator", series_id="S-1"))
            s.add(ElementMitarbeiter(name=f"EM-{i}", parent=name, parenttype="Element",
                                     parentfield="mitarbeiter", mitglied="M-TAL",
                                     bestaetigt=True, docstatus=0, idx=1))

    anmelden(client, "moderator")
    r = client.post("/api/method/diakronos.kronos.api.series.update_series_batch_fast",
                    json={"series_id": "S-1",
                          "updates": {"element_start": "2026-12-06 16:00:00",
                                      "element_end": "2026-12-06 17:00:00"}})
    assert r.status_code == 200, r.text

    nachrichten = _notifications(patched_db, "talente")
    assert len(nachrichten) == 1, \
        f"Serienverschiebung erzeugte {len(nachrichten)} Nachrichten statt 1 (W-2)"
