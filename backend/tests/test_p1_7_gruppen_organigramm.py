"""P1-7 — Gruppen/Organigramm reparieren (Nachtbefunde).

Reproduktionstests fuer die Befunde des Reparatur-Pakets P1-7. Jeder Test war
auf dem Stand VOR der Behebung rot und ist danach gruen:

  * UXD-R4 / OP-ADMIN-5  Parameter/Präfixe beim Anlegen und Umbenennen;
                          `can_edit_ids` in `get_user_create_permissions`;
                          `update_dienstbereich` existiert.
  * UXD-R7 / BLD-R4      `add_mitglied_to_gruppe` lehnt unbekannte Gruppen ab
                          (keine verwaiste Gruppenmitgliedschaft).
  * UXD-R25              Anzeigenamen (Dienstbereich/Obergruppe) im Detail.
  * UXD-R10              `get_gruppe_termine` (die alte SPA-Abfrage scheiterte
                          an der Signatur von `kalender.get_events`).
  * OP-ADMIN-6           `get_gruppen_page_data` trennt „meine" von „alle" und
                          liefert die Anlegen-Rechte + Auswahllisten.

Datenlage: dieselbe Hierarchie-Fixture wie `test_p4a_gruppen.py` (P4a).
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.diakonos import (
    Dienstbereich,
    DienstbereichVerantwortlicher,
    Gruppe,
    GruppeVerantwortlicher,
    Gruppenmitgliedschaft,
    Mitglied,
    Untergruppe,
    Untergruppenmitgliedschaft,
)


@pytest.fixture()
def hierarchie(patched_db):
    """Dieselbe Welt wie in `test_p4a_gruppen.py` (P4a)."""
    sess = patched_db()

    verw_bereich = DienstbereichVerantwortlicher(
        name="DVB-1", parent="DB-A", parenttype="Dienstbereich",
        parentfield="verantwortliche", user="bereichsverantw@example.org",
        docstatus=0, idx=1,
    )
    sess.add_all([
        Dienstbereich(name="DB-A", ministry="Gottesdienst",
                      ancestor_path="/|/DB-A/", docstatus=0, idx=0),
        Dienstbereich(name="DB-B", ministry="Jugend",
                      ancestor_path="/|/DB-B/", docstatus=0, idx=0),
        verw_bereich,
    ])
    sess.flush()
    sess.add_all([
        Gruppe(name="G-A1", gruppenname="Kleingruppe Nord", dienstbereich="DB-A",
               status="Aktiv", sichtbarkeit="Öffentlich",
               ancestor_path="/G-A1/|/DB-A/", docstatus=0, idx=0),
        Untergruppe(name="UG-A1", untergruppenname="Nord-Team", gruppe="G-A1",
                    status="Aktiv", sichtbarkeit="Öffentlich",
                    ancestor_path="/UG-A1/G-A1/|/DB-A/", docstatus=0, idx=0),
        GruppeVerantwortlicher(
            name="GRV-1", parent="G-A1", parenttype="Gruppe",
            parentfield="verantwortliche", user="gruppenverantw@example.org",
            docstatus=0, idx=1,
        ),
    ])
    sess.flush()

    from diakronos_app.models.core import HasRole, User
    sess.add_all([
        User(name="admin@example.org", email="admin@example.org",
             full_name="Admin", enabled=True),
        User(name="bereichsverantw@example.org", email="bereichsverantw@example.org",
             full_name="Bereichsverantw", enabled=True),
        User(name="gruppenverantw@example.org", email="gruppenverantw@example.org",
             full_name="Gruppenverantw", enabled=True),
        User(name="mitglied-a@example.org", email="mitglied-a@example.org",
             full_name="Mitglied A", enabled=True),
        HasRole(name="HR-1", parent="admin@example.org", parenttype="User",
                parentfield="roles", role="System Manager", docstatus=0, idx=1),
        # UXD-R10: der Kalender-Zugriff prueft die Rolle `Kalenderadministrator`.
        HasRole(name="HR-2", parent="admin@example.org", parenttype="User",
                parentfield="roles", role="Kalenderadministrator", docstatus=0, idx=2),
    ])
    sess.add_all([
        Mitglied(name="M-gruppe-a1", vorname="Greta", nachname="A",
                 email="mitglied-a@example.org", status="Mitglied",
                 user="mitglied-a@example.org",
                 ancestor_path="/G-A1/|/DB-A/", docstatus=0, idx=0),
        Mitglied(name="M-neu-d", vorname="Nina", nachname="Neu",
                 email="neu-d@example.org", status="Mitglied",
                 user="neu-d@example.org",
                 ancestor_path="/G-A1/|/DB-A/", docstatus=0, idx=0),
        Gruppenmitgliedschaft(name="GM-1", parent="G-A1", parenttype="Gruppe",
                              parentfield="mitglieder", mitglied="M-gruppe-a1",
                              rolle="Leiter", status="Aktiv",
                              beitrittsdatum=date(2024, 1, 1),
                              docstatus=0, idx=1),
        Untergruppenmitgliedschaft(
            name="UGM-1", parent="UG-A1", parenttype="Untergruppe",
            parentfield="mitglieder", mitglied="M-gruppe-a1", rolle="Mitglied",
            status="Aktiv", docstatus=0, idx=1,
        ),
    ])
    sess.commit()
    yield sess
    sess.close()


@pytest.fixture(autouse=True)
def _reset_session_user():
    yield
    set_user("Administrator")


# ── UXD-R4 / OP-ADMIN-5: Rechte-Liste und Präfixe ───────────────────────────


def test_can_edit_ids_enthaelt_admin_alles(hierarchie):
    """OP-ADMIN-5: vorher fehlte `can_edit_ids` ganz -> 0 Stift-Knöpfe."""
    from diakronos_app.api.gruppen import get_user_create_permissions

    set_user("admin@example.org")
    res = get_user_create_permissions()
    assert "can_edit_ids" in res
    # Rohe Namen (ohne Orgchart-Präfix db_/g_/ug_) — genau das erwartet die SPA.
    assert set(res["can_edit_ids"]) >= {"DB-A", "DB-B", "G-A1", "UG-A1"}
    assert not any(x.startswith(("db_", "g_", "ug_")) for x in res["can_edit_ids"])


def test_can_edit_ids_verantwortlicher_nur_seine_welt(hierarchie):
    from diakronos_app.api.gruppen import get_user_create_permissions

    # Bereichsverantwortlicher DB-A: darf DB-A, die Gruppe darunter und deren
    # Untergruppe ändern — nicht DB-B.
    set_user("bereichsverantw@example.org")
    res = get_user_create_permissions()
    assert "DB-A" in res["can_edit_ids"]
    assert "G-A1" in res["can_edit_ids"]
    assert "UG-A1" in res["can_edit_ids"]
    assert "DB-B" not in res["can_edit_ids"]

    # Gruppenverantwortlicher G-A1: G-A1, nicht DB-A.
    set_user("gruppenverantw@example.org")
    res = get_user_create_permissions()
    assert "G-A1" in res["can_edit_ids"]
    assert "DB-A" not in res["can_edit_ids"]


def test_create_gruppe_mit_rohem_dienstbereich(hierarchie):
    """UXD-R4: die SPA sendet jetzt den rohen Dienstbereichsnamen."""
    from diakronos_app.api.gruppen import create_gruppe, get_gruppe_detail

    set_user("admin@example.org")
    res = create_gruppe("Neue Gruppe", dienstbereich="DB-A")
    assert res["success"] is True
    assert get_gruppe_detail(res["name"])["gruppe"]["dienstbereich"] == "DB-A"


def test_create_gruppe_mit_orgchart_praefix_scheitert(hierarchie):
    """Gegenprobe: das alte Präfix `db_…` war die Ursache des 417.

    In der Betriebsdatenbank (PostgreSQL) greift der Fremdschlüssel
    `gruppe_dienstbereich_fkey`; in der SQLite-Testdatenbank wird er nicht
    erzwungen, deshalb wird hier nur geprüft, dass `create_gruppe` das Präfix
    NICHT als Dienstbereich akzeptiert (die Gruppe landet nicht in DB-A).
    """
    from diakronos_app.api.gruppen import create_gruppe
    from diakronos_app.frappe_compat.api_helpers import get_value

    set_user("admin@example.org")
    res = create_gruppe("Kaputt", dienstbereich="db_DB-A")
    # Der Dienstbereich ist nicht „DB-A" — der alte Aufruf war falsch verdrahtet.
    assert get_value("Gruppe", res["name"], "dienstbereich") == "db_DB-A"
    assert get_value("Gruppe", res["name"], "dienstbereich") != "DB-A"


def test_update_dienstbereich_ist_portiert(hierarchie):
    """UXD-R4: vorher 404 `Methode … nicht gefunden`."""
    from diakronos_app.api.gruppen import update_dienstbereich
    from diakronos_app.frappe_compat.api_helpers import get_value
    from diakronos_app.frappe_compat.registry import lookup

    # Der Endpunkt ist registriert (kein 404 mehr).
    assert lookup("diakronos.diakonos.api.gruppen.update_dienstbereich") is not None

    set_user("admin@example.org")
    res = update_dienstbereich("DB-A", ministry="Gottesdienst neu")
    assert res["success"] is True
    assert get_value("Dienstbereich", "DB-A", "ministry") == "Gottesdienst neu"


def test_update_dienstbereich_normalisiert_farbe(hierarchie):
    """UXD-R28 angrenzend: `3b82f6` ohne `#` ergab ungültiges CSS."""
    from diakronos_app.api.gruppen import update_dienstbereich
    from diakronos_app.frappe_compat.api_helpers import get_value

    set_user("admin@example.org")
    update_dienstbereich("DB-A", farbe="3b82f6")
    assert get_value("Dienstbereich", "DB-A", "farbe") == "#3b82f6"


def test_update_untergruppe_schreibt_untergruppenname(hierarchie):
    """UXD-R4: `update_untergruppe` antwortete „success", ohne zu ändern."""
    from diakronos_app.api.gruppen import get_untergruppe_detail, update_untergruppe

    set_user("admin@example.org")
    update_untergruppe("UG-A1", untergruppenname="Nord-Team (neu)")
    assert get_untergruppe_detail("UG-A1")["untergruppe"]["untergruppenname"] == "Nord-Team (neu)"


# ── BLD-R4: keine verwaiste Gruppenmitgliedschaft ───────────────────────────


def test_add_mitglied_unbekannte_gruppe_ist_doesnotexist(hierarchie):
    """BLD-R4: vorher HTTP 200 + verwaiste Zeile."""
    from diakronos_app.api.gruppen import add_mitglied_to_gruppe
    from diakronos_app.frappe_compat.exceptions import DoesNotExistError

    set_user("admin@example.org")
    with pytest.raises(DoesNotExistError):
        add_mitglied_to_gruppe("G-GIBTS-NICHT", "M-neu-d")

    sess = hierarchie
    assert sess.query(Gruppenmitgliedschaft).filter(
        Gruppenmitgliedschaft.parent == "G-GIBTS-NICHT"
    ).count() == 0


def test_create_mitglied_meldet_warnung_bei_unbekannter_gruppe(hierarchie):
    """BLD-R4: die Zuweisung schlägt fehl UND wird gemeldet, ohne das Mitglied
    zu verwerfen."""
    from diakronos_app.api.mitglieder import create_mitglied

    set_user("admin@example.org")
    res = create_mitglied("Test", "Person", gruppe_id="G-GIBTS-NICHT")
    assert res["success"] is True
    assert res["warnungen"], "unerwartete Gruppe ohne Warnung verschluckt"

    sess = hierarchie
    assert sess.query(Gruppenmitgliedschaft).filter(
        Gruppenmitgliedschaft.parent == "G-GIBTS-NICHT"
    ).count() == 0


# ── UXD-R25: Anzeigenamen in get_gruppe_detail / get_untergruppe_detail ─────


def test_gruppe_detail_liefert_dienstbereich_name(hierarchie):
    from diakronos_app.api.gruppen import get_gruppe_detail

    set_user("admin@example.org")
    detail = get_gruppe_detail("G-A1")
    assert detail["gruppe"]["dienstbereich"] == "DB-A"
    assert detail["gruppe"]["dienstbereich_name"] == "Gottesdienst"


def test_untergruppe_detail_liefert_gruppe_name(hierarchie):
    from diakronos_app.api.gruppen import get_untergruppe_detail

    set_user("admin@example.org")
    detail = get_untergruppe_detail("UG-A1")
    assert detail["untergruppe"]["gruppe"] == "G-A1"
    assert detail["untergruppe"]["gruppe_name"] == "Kleingruppe Nord"


# ── UXD-R10: Termine einer Gruppe ───────────────────────────────────────────


def test_get_gruppe_termine_liefert_termine_der_gruppe(hierarchie):
    """UXD-R10: die SPA-Abfrage scheiterte vorher bei jedem Laden mit 417."""
    from datetime import datetime

    from diakronos_app.api.gruppen import get_gruppe_termine
    from diakronos_app.models.kronos import Element, Kalender

    sess = hierarchie
    sess.add(Kalender(name="KAL-1", calendar_name="Gemeindekalender", docstatus=0, idx=0))
    start = datetime.combine(date.today() + timedelta(days=3), datetime.min.time())
    sess.add(Element(
        name="EV-1", element_name="Probe Nord", gruppe="G-A1",
        element_start=start, element_end=start + timedelta(hours=2),
        element_calendar="KAL-1",
        status="Festgelegt", docstatus=0, idx=0,
    ))
    sess.commit()

    set_user("admin@example.org")
    res = get_gruppe_termine("G-A1")
    assert res["success"] is True
    assert [t["name"] for t in res["termine"]] == ["EV-1"]


def test_get_gruppe_termine_verweigert_fremde_gruppe(hierarchie):
    from diakronos_app.api.gruppen import get_gruppe_termine
    from diakronos_app.frappe_compat.exceptions import PermissionError

    set_user("mitglied-a@example.org")
    with pytest.raises(PermissionError):
        get_gruppe_termine("G-B1")


# ── OP-ADMIN-6: Gruppenseite trennt „meine" von „alle" ─────────────────────


def test_gruppen_page_data_meine_nur_echte_mitgliedschaften(hierarchie):
    """OP-ADMIN-6: Admin ohne eigene Mitgliedschaft sah „Meine Gruppen 2"."""
    from diakronos_app.api.gruppen import get_gruppen_page_data

    set_user("admin@example.org")
    res = get_gruppen_page_data()
    assert res["is_admin"] is True
    # Admin ist in keiner Gruppe Mitglied/Verantwortlicher.
    assert res["meine_gruppen"] == []


def test_gruppen_page_data_liefert_anlegen_rechte(hierarchie):
    """OP-ADMIN-6: die Gruppenseite bekommt Rechte + Auswahllisten."""
    from diakronos_app.api.gruppen import get_gruppen_page_data

    set_user("bereichsverantw@example.org")
    res = get_gruppen_page_data()
    assert res["create_permissions"]["can_create_gruppe"] is True
    assert {"name": "DB-A", "ministry": "Gottesdienst"} in res["dienstbereich_auswahl"]
    assert any(g["name"] == "G-A1" for g in res["gruppen_auswahl"])


def test_gruppen_page_data_auswahllisten_leer_ohne_anlegerecht(hierarchie):
    """B5: ein reiner Leser bekommt keine Auswahllisten (kein Namensleck).

    Vorher lieferte `get_gruppen_page_data` jedem Nutzer alle Dienstbereich-
    und Gruppennamen — auch nicht sichtbare (privat)."""
    from diakronos_app.api.gruppen import get_gruppen_page_data

    set_user("mitglied-a@example.org")
    res = get_gruppen_page_data()
    assert res["create_permissions"]["can_create_any"] is False
    assert res["dienstbereich_auswahl"] == []
    assert res["gruppen_auswahl"] == []


# ── B2: Termine nur Festgelegt bzw. eigener Vorschlag (wie P0-3) ────────────


def _lesekalender(sess, kalender_name: str, rolle: str) -> None:
    """Gibt `rolle` Leserecht auf `kalender_name` (Kalender.leserechte)."""
    from diakronos_app.models.core import UserRole

    sess.add(UserRole(
        name=f"UR-LESE-{kalender_name}", parent=kalender_name, parenttype="Kalender",
        parentfield="leserechte", role=rolle, docstatus=0, idx=1,
    ))
    sess.commit()


def test_get_gruppe_termine_zeigt_nicht_festgelegte_nur_moderatoren(hierarchie):
    """B2: ein Nicht-Moderator sieht fremde Vorschlaege NICHT.

    Die regulaere Terminabfrage (kronos/calendar_get) zeigt im Lesemodus nur
    `Festgelegt`; get_gruppe_termine tat das vorher nicht und lieferte jedem
    Gruppen-Leser auch Vorschlaege/Konflikte anderer Nutzer."""
    from datetime import datetime

    from diakronos_app.api.gruppen import get_gruppe_termine
    from diakronos_app.models.kronos import Element, Kalender

    sess = hierarchie
    sess.add(Kalender(name="KAL-1", calendar_name="Gemeindekalender", docstatus=0, idx=0))
    _lesekalender(sess, "KAL-1", "All")
    start = datetime.combine(date.today() + timedelta(days=3), datetime.min.time())
    sess.add_all([
        Element(name="EV-FEST", element_name="Probe Nord", gruppe="G-A1",
                element_start=start, element_end=start + timedelta(hours=2),
                element_calendar="KAL-1", status="Festgelegt",
                owner="werauchimmer@example.org", docstatus=0, idx=0),
        Element(name="EV-VORSCHLAG", element_name="Vorschlag Nord", gruppe="G-A1",
                element_start=start, element_end=start + timedelta(hours=2),
                element_calendar="KAL-1", status="Vorschlag",
                owner="werauchimmer@example.org", docstatus=0, idx=0),
    ])
    sess.commit()

    set_user("mitglied-a@example.org")
    res = get_gruppe_termine("G-A1")
    namen = [t["name"] for t in res["termine"]]
    assert "EV-FEST" in namen, "Festgelegt-Termin fehlt"
    assert "EV-VORSCHLAG" not in namen, "fremder Vorschlag darf nicht sichtbar sein"


def test_get_gruppe_termine_zeigt_eigenen_vorschlag(hierarchie):
    """B2: der eigene Vorschlag bleibt sichtbar (wie P0-3)."""
    from datetime import datetime

    from diakronos_app.api.gruppen import get_gruppe_termine
    from diakronos_app.models.kronos import Element, Kalender

    sess = hierarchie
    sess.add(Kalender(name="KAL-1", calendar_name="Gemeindekalender", docstatus=0, idx=0))
    _lesekalender(sess, "KAL-1", "All")
    start = datetime.combine(date.today() + timedelta(days=3), datetime.min.time())
    sess.add(Element(
        name="EV-MEINER", element_name="Mein Vorschlag", gruppe="G-A1",
        element_start=start, element_end=start + timedelta(hours=2),
        element_calendar="KAL-1", status="Vorschlag",
        owner="mitglied-a@example.org", docstatus=0, idx=0,
    ))
    sess.commit()

    set_user("mitglied-a@example.org")
    res = get_gruppe_termine("G-A1")
    assert "EV-MEINER" in [t["name"] for t in res["termine"]]


def test_get_gruppe_termine_zeigt_laufenden_termin(hierarchie):
    """B2: schon begonnene, noch laufende Termine gehoeren dazu.

    Die alte Grenze `element_start >= heute` schnitt sie weg."""
    from datetime import datetime

    from diakronos_app.api.gruppen import get_gruppe_termine
    from diakronos_app.models.kronos import Element, Kalender

    sess = hierarchie
    sess.add(Kalender(name="KAL-1", calendar_name="Gemeindekalender", docstatus=0, idx=0))
    _lesekalender(sess, "KAL-1", "All")
    laufend_start = datetime.combine(date.today() - timedelta(days=1), datetime.min.time())
    sess.add(Element(
        name="EV-LAUFEND", element_name="Laufende Freizeit", gruppe="G-A1",
        element_start=laufend_start,
        element_end=datetime.combine(date.today() + timedelta(days=1), datetime.min.time()),
        element_calendar="KAL-1", status="Festgelegt", docstatus=0, idx=0,
    ))
    sess.commit()

    set_user("mitglied-a@example.org")
    res = get_gruppe_termine("G-A1")
    assert "EV-LAUFEND" in [t["name"] for t in res["termine"]]


# ── B4: Warnungen erreichen die Oberflaeche ─────────────────────────────────


def test_genehmige_anmeldung_meldet_warnung_bei_unbekannter_gruppe(hierarchie):
    """B4: Die Anmeldung nennt eine Zielgruppe; laesst sie sich nicht
    zuweisen, bleibt das Mitglied bestehen UND die Freigabe meldet den Grund.

    Vorher verschwand die Zuweisung stumm — das Mitglied war angelegt, aber
    ohne Gruppe, und niemand erfuhr davon.
    """
    from diakronos_app.api.admin_hub import genehmige_anmeldung
    from diakronos_app.models.diakonos import Anmeldung

    sess = hierarchie
    sess.add(Anmeldung(
        name="ANM-B4-FEHLT", status="Anmeldeanfrage", anmeldedatum=date.today(),
        vorname="Wanda", nachname="Warnung", anmeldungstyp="Mitglied-Registrierung",
        gruppe="G-GIBTS-NICHT",
    ))
    sess.commit()

    set_user("admin@example.org")
    res = genehmige_anmeldung("ANM-B4-FEHLT")

    assert res["success"] is True
    assert res["mitglied"], "Mitglied muss trotz fehlgeschlagener Gruppe entstehen"
    assert res["warnungen"], "unerwartete Gruppe darf nicht stumm bleiben"


def test_genehmige_anmeldung_weist_gruppe_zu(hierarchie):
    """B4: bei gueltiger Zielgruppe landet das neue Mitglied wirklich darin."""
    from diakronos_app.api.admin_hub import genehmige_anmeldung
    from diakronos_app.models.diakonos import Anmeldung, Gruppenmitgliedschaft

    sess = hierarchie
    sess.add(Anmeldung(
        name="ANM-B4-OK", status="Anmeldeanfrage", anmeldedatum=date.today(),
        vorname="Greta", nachname="Ziel", anmeldungstyp="Mitglied-Registrierung",
        gruppe="G-A1",
    ))
    sess.commit()

    set_user("admin@example.org")
    res = genehmige_anmeldung("ANM-B4-OK")

    assert res["success"] is True
    assert res["warnungen"] == []
    sess.expire_all()
    treffer = sess.query(Gruppenmitgliedschaft).filter(
        Gruppenmitgliedschaft.parent == "G-A1",
        Gruppenmitgliedschaft.mitglied == res["mitglied"],
    ).all()
    assert treffer, "Mitglied muss der Zielgruppe zugewiesen sein"

