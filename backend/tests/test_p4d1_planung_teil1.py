"""P4d1 — Portiertes Modul `api.planung` (Teil 1).

Quelle (READ-ONLY): `referenz/diakronos-frappe/diakronos/diakonos/api/planung.py`

Abgedeckt:
  * Registrierung: `FRAPPE_MODULE` gesetzt, alle 17 SPA-Pfade aufloesbar.
  * Login-Pflicht (`allow_guest=False`) fuer jeden Endpunkt -> Guest = 403.
  * `get_vorlagen` / `get_plaene`: Filter, Sichtbarkeit, Entwurfsschranke.
  * `get_plan_uebersicht`: unbekannter Plan -> klarer Fehler; Planzahlen.
  * `get_positionen` / `set_position_verantwortlicher` / `get_teilnehmer`.
  * `set_rollenbesetzung`: Anlage + Aktualisierung, Schreibrecht.
  * `get_besetzungsmatrix`: Raster Rollen x Besetzungen.
  * `generiere_rotation` (dry_run) — reine Vorschau, keine Schreiberei.
  * `speichere_plan_entwurf`: Kopf + Kindzeilen ersetzen, Schreibrecht.
  * `veroeffentliche_plan` / `zurueckziehen_plan`: Statuswechsel + Entwurf.
  * `create_plan`: Pflichtfeldpruefung, Anlage, Lese-/Schreibpfade.
  * `get_abgeleitete_positionen`: Positionen des verknuepften Ablaufplans.
"""

from __future__ import annotations

from datetime import date, time, timedelta

import pytest

from diakronos_app.frappe_compat.registry import lookup
from diakronos_app.frappe_compat.session import set_user

MODUL = "diakronos.diakonos.api.planung"

SPA_PFADE = [
    "get_vorlagen",
    "get_plaene",
    "get_plan_uebersicht",
    "get_positionen",
    "set_position_verantwortlicher",
    "get_teilnehmer",
    "set_rollenbesetzung",
    "get_besetzungsmatrix",
    "generiere_rotation",
    "generiere_plan",
    "speichere_plan_entwurf",
    "veroeffentliche_plan",
    "zurueckziehen_plan",
    "get_abgeleitete_positionen",
    "create_plan",
]

# Direkt aufrufbare Endpunkte, die ohne Nutzlast antworten.
OHNE_ARGUMENT = ["get_vorlagen", "get_plaene"]

BEREICH = "DB-GOTTESDIENST"
BEREICH_FREMD = "DB-FREMD"
GRUPPE = "G-1"
VORLAGE = "DV-1"
PLAN = "DP-1"
LEITUNG = "M-0001"
ANNA = "anna@example.org"
VERANTWORTLICHER = "verantw@example.org"
FREMD = "fremd@example.org"


@pytest.fixture()
def welt(patched_db):
    """Dienstbereich, Gruppe, Vorlage, Plan, Mitglieder, Rollen, Positionen."""
    from diakronos_app.models.diakonos import (
        Dienstbereich,
        DienstbereichVerantwortlicher,
        Dienstplan,
        DienstplanMitwirkender,
        DienstplanPosition,
        DienstplanTermin,
        DienstplanVorlage,
        DienstplanVorlageKategorie,
        DienstplanVorlageSlot,
        Dienstrolle,
        Gruppe,
        GruppeVerantwortlicher,
        Mitglied,
        Rollenbesetzung,
    )
    from diakronos_app.models.kronos import Eventkategorie

    sess = patched_db()

    sess.add_all([
        Mitglied(name="M-0001", vorname="Anna", nachname="Beispiel",
                 email=ANNA, status="Mitglied", docstatus=0, idx=0,
                 ancestor_path="/M-0001"),
        Mitglied(name="M-0002", vorname="Bruno", nachname="Beispiel",
                 email="bruno@example.org", status="Mitglied", docstatus=0, idx=0,
                 ancestor_path="/M-0002"),
    ])

    sess.add_all([
        Dienstbereich(name=BEREICH, ministry="Gottesdienst", docstatus=0, idx=0),
        Dienstbereich(name=BEREICH_FREMD, ministry="Fremdbereich", docstatus=0, idx=0),
    ])

    sess.add_all([
        Gruppe(name=GRUPPE, gruppenname="Gruppe Eins", dienstbereich=BEREICH,
               docstatus=0, idx=0),
    ])

    # Verantwortliche fuer BEREICH bzw. GRUPPE.
    sess.add_all([
        DienstbereichVerantwortlicher(
            name="DBV-1", parent=BEREICH, parenttype="Dienstbereich",
            parentfield="verantwortliche", user=VERANTWORTLICHER, docstatus=0, idx=1),
        GruppeVerantwortlicher(
            name="GV-1", parent=GRUPPE, parenttype="Gruppe",
            parentfield="verantwortliche", user=ANNA, docstatus=0, idx=1),
    ])

    sess.add_all([
        Dienstrolle(name="DR-KL", rollenname="Klavier", docstatus=0, idx=0),
        Dienstrolle(name="DR-GE", rollenname="Gesang", docstatus=0, idx=0),
    ])

    sess.add_all([
        Eventkategorie(name="EK-GD", event_category_name="Gottesdienst",
                       hat_ablaufplan=0, docstatus=0, idx=0),
    ])

    sess.add_all([
        DienstplanVorlage(
            name=VORLAGE, vorlagenname="Gottesdienst-Vorlage", dienstbereich=BEREICH,
            betriebsmodus="Termine", positions_label="Position",
            positions_plural="Positionen", hat_planzahlen=1,
            einsatz_rhythmus="woechentlich", einsatz_wochentag="Sonntag",
            einsatz_uhrzeit=time(10, 0), rotation_modus="rotieren",
            rotation_einheit="monatlich", zuteilung_modus="manuell",
            docstatus=0, idx=0),
        DienstplanVorlage(
            name="DV-FREMD", vorlagenname="Fremd-Vorlage", dienstbereich=BEREICH_FREMD,
            betriebsmodus="Termine", docstatus=0, idx=0),
    ])

    sess.add_all([
        DienstplanVorlageKategorie(
            name="DVK-1", parent=VORLAGE, parenttype="Dienstplan Vorlage",
            parentfield="kategorien", eventkategorie="EK-GD", docstatus=0, idx=1),
        DienstplanVorlageSlot(
            name="DVS-1", parent=VORLAGE, parenttype="Dienstplan Vorlage",
            parentfield="slots", reihenfolge=1, bezeichnung="Eingang",
            inhalt_doctype="Lied", dienstrolle="DR-KL", docstatus=0, idx=1),
    ])

    sess.add_all([
        Dienstplan(
            name=PLAN, plantitel="Gottesdienst Oktober", vorlage=VORLAGE,
            dienstbereich=BEREICH, gruppe=GRUPPE, jahr=2026, status="Entwurf",
            ist_entwurf=1, start_datum=date(2026, 10, 1), ende_datum=date(2026, 10, 31),
            leitung=LEITUNG, kalender="KAL-GD", plan_anzahl_positionen=2,
            plan_anzahl_verantwortliche=2,
            plan_anzahl_teilnehmer=3, max_teilnehmer=10, anmeldung_aktiv=0,
            owner=ANNA, docstatus=0, idx=0),
        Dienstplan(
            name="DP-FREMD", plantitel="Fremdplan", vorlage="DV-FREMD",
            dienstbereich=BEREICH_FREMD, jahr=2026, status="Veroeffentlicht",
            ist_entwurf=0, start_datum=date(2026, 10, 1), ende_datum=date(2026, 10, 31),
            owner=FREMD, docstatus=0, idx=0),
        Dienstplan(
            name="DP-ENTWURF-FREMD", plantitel="Fremder Entwurf", vorlage=VORLAGE,
            dienstbereich=BEREICH, jahr=2026, status="Entwurf", ist_entwurf=1,
            start_datum=date(2026, 10, 1), ende_datum=date(2026, 10, 31),
            owner=FREMD, docstatus=0, idx=0),
    ])

    sess.add_all([
        DienstplanPosition(
            name="DPP-1", parent=PLAN, parenttype="Dienstplan", parentfield="positionen",
            reihenfolge=1, bezeichnung="Eingang", verantwortlicher="M-0001",
            dienstrolle="DR-KL", status="Offen", docstatus=0, idx=1),
        DienstplanPosition(
            name="DPP-2", parent=PLAN, parenttype="Dienstplan", parentfield="positionen",
            reihenfolge=2, bezeichnung="Ausgang", dienstrolle="DR-GE",
            status="Offen", docstatus=0, idx=2),
    ])

    sess.add_all([
        DienstplanMitwirkender(
            name="DPM-1", parent=PLAN, parenttype="Dienstplan", parentfield="mitwirkende",
            mitglied="M-0001", funktion="DR-KL", hauptverantwortlich=1, docstatus=0, idx=1),
    ])

    sess.add_all([
        DienstplanTermin(
            name="DPT-1", parent=PLAN, parenttype="Dienstplan", parentfield="termine",
            datum=date(2026, 10, 4), notiz="Hauptgottesdienst", docstatus=0, idx=1),
    ])

    sess.add_all([
        Rollenbesetzung(
            name="RB-1", dienstplan=PLAN, rolle="Klavier", teilnehmer="M-0001",
            besetzung_nr=1, status="Bestaetigt", docstatus=0, idx=0),
    ])

    sess.commit()
    yield sess
    sess.close()


@pytest.fixture()
def als_admin(welt):
    set_user("Administrator")
    yield "Administrator"


@pytest.fixture()
def als_verantwortlicher(welt):
    set_user(VERANTWORTLICHER)
    yield VERANTWORTLICHER
    set_user("Administrator")


@pytest.fixture()
def als_anna(welt):
    set_user(ANNA)
    yield ANNA
    set_user("Administrator")


@pytest.fixture()
def als_fremd(welt):
    set_user(FREMD)
    yield FREMD
    set_user("Administrator")


# ── Registrierung ──────────────────────────────────────────────────────────


def test_frappe_module_konstante():
    from diakronos_app.api import planung

    assert planung.FRAPPE_MODULE == MODUL


@pytest.mark.parametrize("fn", SPA_PFADE)
def test_spa_pfade_registriert(fn):
    assert lookup(f"{MODUL}.{fn}") is not None


@pytest.mark.parametrize("fn", SPA_PFADE)
def test_guest_wird_abgewiesen(client, fn):
    set_user("Guest")
    try:
        r = client.get(f"/api/method/{MODUL}.{fn}")
        assert r.status_code == 401, (fn, r.text)
    finally:
        set_user("Administrator")


# ── get_vorlagen / get_plaene ──────────────────────────────────────────────


def test_get_vorlagen_liefert_kategorien_und_slots(client, als_admin):
    r = client.get(f"/api/method/{MODUL}.get_vorlagen")
    assert r.status_code == 200, r.text
    vorlagen = r.json()["message"]
    namen = {v["name"] for v in vorlagen}
    assert VORLAGE in namen and "DV-FREMD" in namen

    v = next(x for x in vorlagen if x["name"] == VORLAGE)
    assert v["vorlagenname"] == "Gottesdienst-Vorlage"
    assert v["kategorien"] == ["EK-GD"]
    assert [s["bezeichnung"] for s in v["slots"]] == ["Eingang"]


def test_get_vorlagen_filtert_dienstbereich(client, als_admin):
    r = client.get(f"/api/method/{MODUL}.get_vorlagen",
                   params={"dienstbereich": BEREICH_FREMD})
    assert r.status_code == 200, r.text
    assert [v["name"] for v in r.json()["message"]] == ["DV-FREMD"]


def test_get_plaene_admin_sieht_alles(client, als_admin):
    r = client.get(f"/api/method/{MODUL}.get_plaene")
    assert r.status_code == 200, r.text
    namen = {p["name"] for p in r.json()["message"]}
    assert namen == {PLAN, "DP-FREMD", "DP-ENTWURF-FREMD"}


def test_get_plaene_filter_status(client, als_admin):
    r = client.get(f"/api/method/{MODUL}.get_plaene",
                   params={"status": "Veroeffentlicht"})
    assert r.status_code == 200, r.text
    assert [p["name"] for p in r.json()["message"]] == ["DP-FREMD"]


def test_get_plaene_fremder_entwurf_unsichtbar(client, als_anna):
    # Anna ist Gruppenverantwortliche -> sieht BEREICH-Plaene, aber fremde
    # Entwuerfe werden gefiltert.
    r = client.get(f"/api/method/{MODUL}.get_plaene")
    assert r.status_code == 200, r.text
    namen = {p["name"] for p in r.json()["message"]}
    assert "DP-ENTWURF-FREMD" not in namen
    assert "DP-FREMD" not in namen


def test_get_plaene_verantwortlicher_sieht_seinen_bereich(client, als_verantwortlicher):
    r = client.get(f"/api/method/{MODUL}.get_plaene")
    assert r.status_code == 200, r.text
    namen = {p["name"] for p in r.json()["message"]}
    assert PLAN in namen
    assert "DP-FREMD" not in namen


# ── get_plan_uebersicht ────────────────────────────────────────────────────


def test_get_plan_uebersicht_unbekannter_plan(client, als_admin):
    r = client.get(f"/api/method/{MODUL}.get_plan_uebersicht",
                   params={"plan": "GIBT-ES-NICHT"})
    assert r.status_code >= 400


def test_get_plan_uebersicht_liefert_kopf_und_planzahlen(client, als_admin):
    r = client.get(f"/api/method/{MODUL}.get_plan_uebersicht",
                   params={"plan": PLAN})
    assert r.status_code == 200, r.text
    msg = r.json()["message"]
    assert msg["plan"]["name"] == PLAN
    assert msg["plan"]["plantitel"] == "Gottesdienst Oktober"
    assert msg["soll_ist"]["plan_anzahl_verantwortliche"] == 2
    assert msg["soll_ist"]["plan_anzahl_teilnehmer"] == 3
    assert msg["soll_ist"]["ist_positionen"] == 2


def test_get_plan_uebersicht_fremder_plan_verweigert(client, als_fremd):
    r = client.get(f"/api/method/{MODUL}.get_plan_uebersicht",
                   params={"plan": PLAN})
    assert r.status_code in (403, 404)


# ── get_positionen ─────────────────────────────────────────────────────────


def test_get_positionen_sortiert_nach_reihenfolge(client, als_admin):
    r = client.get(f"/api/method/{MODUL}.get_positionen", params={"plan": PLAN})
    assert r.status_code == 200, r.text
    pos = r.json()["message"]
    assert [p["name"] for p in pos] == ["DPP-1", "DPP-2"]
    assert pos[0]["bezeichnung"] == "Eingang"
    assert pos[0]["verantwortlicher"] == "M-0001"


def test_get_positionen_unbekannter_plan(client, als_admin):
    r = client.get(f"/api/method/{MODUL}.get_positionen", params={"plan": "NIX"})
    assert r.status_code >= 400


# ── set_position_verantwortlicher ──────────────────────────────────────────


def test_set_position_verantwortlicher_aktualisiert(client, als_admin, welt):
    from diakronos_app.models.diakonos import DienstplanPosition

    r = client.post(
        f"/api/method/{MODUL}.set_position_verantwortlicher",
        data={"plan": PLAN, "row": "DPP-2", "mitglied": "M-0002"},
    )
    assert r.status_code == 200, r.text

    welt.expire_all()
    row = welt.get(DienstplanPosition, "DPP-2")
    assert row.verantwortlicher == "M-0002"


def test_set_position_verantwortlicher_unbekannte_position(client, als_admin):
    r = client.post(
        f"/api/method/{MODUL}.set_position_verantwortlicher",
        data={"plan": PLAN, "row": "GIBT-ES-NICHT", "mitglied": "M-0002"},
    )
    assert r.status_code >= 400


# ── get_teilnehmer ─────────────────────────────────────────────────────────


def test_get_teilnehmer_liefert_liste(client, als_admin):
    r = client.get(f"/api/method/{MODUL}.get_teilnehmer", params={"plan": PLAN})
    assert r.status_code == 200, r.text
    assert isinstance(r.json()["message"], list)


# ── set_rollenbesetzung ────────────────────────────────────────────────────


def test_set_rollenbesetzung_aktualisiert_vorhandene(client, als_admin, welt):
    from diakronos_app.models.diakonos import Rollenbesetzung

    r = client.post(
        f"/api/method/{MODUL}.set_rollenbesetzung",
        data={"plan": PLAN, "rolle": "Klavier", "mitglied": "M-0002",
              "besetzung_nr": 1},
    )
    assert r.status_code == 200, r.text

    welt.expire_all()
    rows = welt.query(Rollenbesetzung).filter_by(
        dienstplan=PLAN, rolle="Klavier", besetzung_nr=1).all()
    assert len(rows) == 1
    assert rows[0].teilnehmer == "M-0002"


def test_set_rollenbesetzung_legt_neue_an(client, als_admin, welt):
    from diakronos_app.models.diakonos import Rollenbesetzung

    r = client.post(
        f"/api/method/{MODUL}.set_rollenbesetzung",
        data={"plan": PLAN, "rolle": "Gesang", "mitglied": "M-0001",
              "besetzung_nr": 2},
    )
    assert r.status_code == 200, r.text

    welt.expire_all()
    rows = welt.query(Rollenbesetzung).filter_by(
        dienstplan=PLAN, rolle="Gesang", besetzung_nr=2).all()
    assert len(rows) == 1


def test_set_rollenbesetzung_ohne_schreibrecht(client, als_fremd):
    r = client.post(
        f"/api/method/{MODUL}.set_rollenbesetzung",
        data={"plan": PLAN, "rolle": "Gesang", "mitglied": "M-0001"},
    )
    assert r.status_code in (403, 404)


# ── get_besetzungsmatrix ───────────────────────────────────────────────────


def test_get_besetzungsmatrix_enthaelt_rollen(client, als_admin):
    r = client.get(f"/api/method/{MODUL}.get_besetzungsmatrix",
                   params={"plan": PLAN})
    assert r.status_code == 200, r.text
    msg = r.json()["message"]
    assert "Klavier" in msg["rollen"]
    assert msg["besetzungen"][0]["rolle"] == "Klavier"


# ── generiere_rotation (Vorschau) ──────────────────────────────────────────


def test_generiere_rotation_dry_run_schreibt_nichts(client, als_admin, welt):
    from diakronos_app.models.diakonos import Rollenbesetzung

    vorher = welt.query(Rollenbesetzung).count()

    r = client.post(
        f"/api/method/{MODUL}.generiere_rotation",
        data={"plan": PLAN, "von": "2026-10-01", "bis": "2026-10-31",
              "dry_run": 1},
    )
    assert r.status_code == 200, r.text

    welt.expire_all()
    assert welt.query(Rollenbesetzung).count() == vorher


# ── speichere_plan_entwurf ─────────────────────────────────────────────────


def test_speichere_plan_entwurf_ersetzt_kopf_und_kindzeilen(client, als_admin, welt):
    from diakronos_app.models.diakonos import (
        Dienstplan,
        DienstplanPosition,
        DienstplanTermin,
    )

    r = client.post(
        f"/api/method/{MODUL}.speichere_plan_entwurf",
        data={
            "plan": PLAN,
            "payload": '{"termine": [{"datum": "2026-10-11",'
                       ' "notiz": "Neuer Termin"}],'
                       ' "positionen": ['
                       '{"datum": "2026-10-11", "bezeichnung": "Nur eine",'
                       ' "reihenfolge": 1}]}',
        },
    )
    assert r.status_code == 200, r.text

    welt.expire_all()
    # Kopf bleibt unberuehrt — der Endpunkt ersetzt nur die Kindzeilen.
    doc = welt.get(Dienstplan, PLAN)
    assert doc.plantitel == "Gottesdienst Oktober"

    termine = welt.query(DienstplanTermin).filter_by(
        parent=PLAN, parentfield="termine").all()
    assert [t.datum for t in termine] == [date(2026, 10, 11)]

    pos = welt.query(DienstplanPosition).filter_by(
        parent=PLAN, parentfield="positionen").all()
    assert [p.bezeichnung for p in pos] == ["Nur eine"]
    assert pos[0].faellig_ab == date(2026, 10, 11)


def test_speichere_plan_entwurf_ohne_schreibrecht(client, als_fremd):
    r = client.post(
        f"/api/method/{MODUL}.speichere_plan_entwurf",
        data={"plan": PLAN, "payload": '{"plantitel": "X"}'},
    )
    assert r.status_code in (403, 404)


# ── veroeffentliche_plan / zurueckziehen_plan ──────────────────────────────


def test_veroeffentliche_plan_wechselt_status(client, als_admin, welt):
    from diakronos_app.models.diakonos import Dienstplan

    r = client.post(f"/api/method/{MODUL}.veroeffentliche_plan",
                    data={"plan": PLAN})
    assert r.status_code == 200, r.text

    welt.expire_all()
    doc = welt.get(Dienstplan, PLAN)
    assert bool(doc.ist_entwurf) is False


def test_zurueckziehen_plan_setzt_entwurf(client, als_admin, welt):
    from diakronos_app.models.diakonos import Dienstplan

    r = client.post(f"/api/method/{MODUL}.zurueckziehen_plan",
                    data={"plan": PLAN})
    assert r.status_code == 200, r.text

    welt.expire_all()
    doc = welt.get(Dienstplan, PLAN)
    assert bool(doc.ist_entwurf) is True


# ── create_plan ────────────────────────────────────────────────────────────


def test_create_plan_legt_plan_an(client, als_admin, welt):
    from diakronos_app.models.diakonos import Dienstplan

    r = client.post(
        f"/api/method/{MODUL}.create_plan",
        data={
            "payload": '{"plantitel": "Neu aus API", "vorlage": "DV-1",'
                       ' "dienstbereich": "DB-GOTTESDIENST", "gruppe": "G-1",'
                       ' "jahr": 2027, "start_datum": "2027-01-01",'
                       ' "ende_datum": "2027-01-31"}',
        },
    )
    assert r.status_code == 200, r.text
    name = r.json()["message"]
    if isinstance(name, dict):
        name = name.get("name")

    welt.expire_all()
    doc = welt.get(Dienstplan, name)
    assert doc is not None
    assert doc.plantitel == "Neu aus API"


def test_create_plan_ohne_berechtigung(client, als_fremd):
    r = client.post(
        f"/api/method/{MODUL}.create_plan",
        data={"payload": '{"plantitel": "Boese", "dienstbereich": "DB-GOTTESDIENST"}'},
    )
    assert r.status_code in (403, 404, 417)


def test_create_plan_ohne_titel_fehlerhaft(client, als_admin):
    r = client.post(
        f"/api/method/{MODUL}.create_plan",
        data={"payload": '{"dienstbereich": "DB-GOTTESDIENST"}'},
    )
    assert r.status_code >= 400


# ── get_abgeleitete_positionen ─────────────────────────────────────────────


def test_get_abgeleitete_positionen_ohne_quelle(client, als_admin):
    r = client.get(f"/api/method/{MODUL}.get_abgeleitete_positionen",
                   params={"plan": PLAN})
    assert r.status_code == 200, r.text
    assert isinstance(r.json()["message"], list)
