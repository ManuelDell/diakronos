"""Tests fuer ``planrahmen/datenquelle_db.py`` (PR4, P4a).

SQLite-Fixture reicht hier (Parent macht die PostgreSQL-/HTTP-Durchstich-
Tests): die DB-Adapter-Logik ist engine-unabhaengig — Zuordnung, Filter und
Gebuendeltheit werden gegen die echten ORM-Modelle geprueft.

Abgedeckt: Personen/Merkmale/Gruppen (gueltige parenttype/parentfield),
Anmeldung (fail-closed: nur explizite ``feldlabel='rolle'``-Antwort bei
bestaetigtem Status, keine geratene Mitarbeiterrolle, Veranstaltungs-Bindung),
Sammlungen ('lieder' aus aktiven Lied + Merkmalwerte, eigene Sammlungen mit
Umfang gemeinde/plan), Abwesenheiten (nur zutreffender Plantyp), Historie
(alle Plaene des Plantyps als Schluessel, eigener Plan ausgeschlossen,
Listen-Werte entfaltet), Kalender (nur 'Festgelegt', keine privaten Daten)
sowie die Gebuendeltheit der Abfragen (kein N+1).
"""
from __future__ import annotations

from datetime import date, datetime

import pytest
from sqlalchemy import event

from diakronos_app.models.diakonos import (
    Anmeldung,
    AnmeldungAntwort,
    Gruppe,
    Gruppenmitgliedschaft,
    Mitglied,
)
from diakronos_app.models.kronos import Element, Eventkategorie
from diakronos_app.models.psalmos import Lied
from diakronos_app.models.planrahmen import (
    Abwesenheit as PrAbwesenheit,
)
from diakronos_app.models.planrahmen import (
    Eintrag as PrEintrag,
)
from diakronos_app.models.planrahmen import (
    Merkmal as PrMerkmal,
    MerkmalWert as PrMerkmalWert,
    Plan as PrPlan,
    Plantyp as PrPlantyp,
    PlantypVersion as PrPlantypVersion,
    Sammlung as PrSammlung,
    SammlungEintrag as PrSammlungEintrag,
    Termin as PrTermin,
)
from diakronos_app.planrahmen.datenquelle_db import DBDatenquelle
from diakronos_app.planrahmen.engine.datenquelle import Datenquelle


# --------------------------------------------------------------------------- #
# Seed: eine kleine, aber vollstaendige Gemeinde-Datenlage
# --------------------------------------------------------------------------- #


@pytest.fixture()
def db(session_factory):
    """Legt die Testdaten an und gibt die Session zurueck."""
    s = session_factory()

    # Plantypen + Plaene (Schluessel, nicht UUID).
    s.add_all([
        PrPlantyp(id="PT-CHOR", schluessel="chorplan", name="Chorplan"),
        PrPlantyp(id="PT-FREI", schluessel="freizeit", name="Freizeitplan"),
        PrPlantypVersion(id="PV-CHOR", plantyp="PT-CHOR", versionsnummer=1,
                         gueltig_ab=date(2025, 1, 1), definition={}),
        PrPlantypVersion(id="PV-FREI", plantyp="PT-FREI", versionsnummer=1,
                         gueltig_ab=date(2025, 1, 1), definition={}),
        # PLAN-A traegt ebenfalls einen (eingefrorenen) Stand: sobald er
        # veroeffentlicht ist, zaehlt er ohne Bindung genauso wie jeder andere
        # Plan — ausgeschlossen wird er nur ueber die plan_id-Bindung.
        PrPlan(id="PLAN-A", plantyp="PT-CHOR", titel="Chorplan 2026 (laufend)",
               status="veroeffentlicht",
               veroeffentlichter_stand={
                   "plan": {},
                   "termine": [{"id": "T-A1", "datum": "2026-02-01"}],
                   "eintraege": [
                       {"termin": "T-A1", "feld_pfad": "einsingen", "wert": "M-3"},
                   ],
               }),
        # OP-CHOR-2/8: Historie kommt nur aus dem veroeffentlichten Stand.
        # Ein veroeffentlichter Plan traegt daher seinen eingefrorenen Stand
        # (Termin-IDs + Werte) mit sich.
        PrPlan(id="PLAN-B", plantyp="PT-CHOR", titel="Chorplan 2025",
               status="veroeffentlicht",
               veroeffentlichter_stand={
                   "plan": {},
                   "termine": [{"id": "T-B1", "datum": "2025-11-02"},
                               {"id": "T-B2", "datum": "2027-01-04"}],
                   "eintraege": [
                       {"termin": "T-B1", "feld_pfad": "lieder[0]", "wert": "LIED-1"},
                       {"termin": "T-B1", "feld_pfad": "einsingen", "wert": "M-2"},
                       {"termin": "T-B2", "feld_pfad": "einsingen", "wert": "M-1"},
                   ],
               }),
        PrPlan(id="PLAN-C", plantyp="PT-FREI", titel="Freizeit Musterstadt",
               status="veroeffentlicht",
               veroeffentlichter_stand={
                   "plan": {},
                   "termine": [{"id": "T-C1", "datum": "2025-08-01"}],
                   "eintraege": [
                       {"termin": "T-C1", "feld_pfad": "leitung", "wert": ["M-1", "M-2"]},
                   ],
               }),
    ])

    # Personen: M3 ist storniert (docstatus=2) und darf nicht erscheinen.
    s.add_all([
        Mitglied(name="M-1", vorname="Anna", nachname="Beispiel",
                 email="anna@example.org", docstatus=0),
        Mitglied(name="M-2", vorname="Bruno", nachname="Beispiel",
                 email="bruno@example.org", docstatus=0),
        Mitglied(name="M-3", vorname="Clara", nachname="Clausen",
                 email="clara@example.org", docstatus=2),
    ])

    # Merkmale: Person 'klavier' (tag) + Sammlungs-Merkmale.
    s.add_all([
        PrMerkmal(id="MK-KLAV", ziel="person", schluessel="klavier", art="tag"),
        PrMerkmal(id="MK-STIMME", ziel="person", schluessel="stimme", art="auswahl"),
        PrMerkmal(id="MK-THEMA", ziel="sammlung:lieder", schluessel="thema",
                  art="auswahl"),
        PrMerkmal(id="MK-REIHE", ziel="sammlung:bibelarbeiten", schluessel="reihe",
                  art="text"),
    ])
    s.add_all([
        PrMerkmalWert(merkmal="MK-KLAV", ziel_id="M-1", wert=True),
        # JSON-Entpack-Konvention der Merkmal-Dienste: {"wert": ...}.
        PrMerkmalWert(merkmal="MK-STIMME", ziel_id="M-1", wert={"wert": "Alt"}),
        PrMerkmalWert(merkmal="MK-KLAV", ziel_id="M-2", wert=False),
        PrMerkmalWert(merkmal="MK-THEMA", ziel_id="LIED-1", wert={"wert": "Advent"}),
    ])

    # Gruppen + Mitgliedschaften (nur parenttype='Gruppe'/parentfield='mitglieder').
    s.add_all([
        Gruppe(name="CHOR", gruppenname="Chor", docstatus=0, obergruppe="GEMEINDE"),
        Gruppe(name="TEAM-1", gruppenname="Team 1", docstatus=0),
    ])
    s.add_all([
        Gruppenmitgliedschaft(name="GM-1", parent="CHOR", parenttype="Gruppe",
                              parentfield="mitglieder", mitglied="M-1", docstatus=0),
        # Ungueltiges parentfield -> keine Mitgliedschaft.
        Gruppenmitgliedschaft(name="GM-2", parent="CHOR", parenttype="Gruppe",
                              parentfield="verantwortliche", mitglied="M-2",
                              docstatus=0),
        # Stornierte Mitgliedschaft -> kein Mitglied.
        Gruppenmitgliedschaft(name="GM-3", parent="TEAM-1", parenttype="Gruppe",
                              parentfield="mitglieder", mitglied="M-2",
                              docstatus=2),
        Gruppenmitgliedschaft(name="GM-4", parent="TEAM-1", parenttype="Gruppe",
                              parentfield="mitglieder", mitglied="M-1",
                              docstatus=0),
    ])

    # Anmeldungen: Rolle NUR aus expliziter feldlabel='rolle'-Antwort.
    s.add_all([
        Anmeldung(name="AN-1", mitglied="M-1", element="EV-1", status="Bestätigt",
                  docstatus=0),
        Anmeldung(name="AN-2", mitglied="M-2", element="EV-1",
                  status="Anmeldeanfrage", docstatus=0),
        Anmeldung(name="AN-3", mitglied="M-1", element="EV-2", status="Bestätigt",
                  docstatus=0),
        Anmeldung(name="AN-4", mitglied="M-3", element="EV-1", status="Bestätigt",
                  docstatus=0),
    ])
    s.add_all([
        AnmeldungAntwort(name="AW-1", parent="AN-1", parenttype="Anmeldung",
                         parentfield="antworten", feldlabel="rolle",
                         antwort="mitarbeiter", docstatus=0),
        # Andere Feldlabel -> keine Rolle.
        AnmeldungAntwort(name="AW-2", parent="AN-1", parenttype="Anmeldung",
                         parentfield="antworten", feldlabel="Email",
                         antwort="anna@example.org", docstatus=0),
        AnmeldungAntwort(name="AW-3", parent="AN-2", parenttype="Anmeldung",
                         parentfield="antworten", feldlabel="rolle",
                         antwort="mitarbeiter", docstatus=0),
        AnmeldungAntwort(name="AW-4", parent="AN-3", parenttype="Anmeldung",
                         parentfield="antworten", feldlabel="rolle",
                         antwort="mitarbeiter", docstatus=0),
        AnmeldungAntwort(name="AW-5", parent="AN-4", parenttype="Anmeldung",
                         parentfield="antworten", feldlabel="rolle",
                         antwort="mitarbeiter", docstatus=0),
    ])

    # Lieder: nur aktive zaehlen; Thema-Merkmal auf LED-1.
    s.add_all([
        Lied(name="LIED-1", titel="Großer Gott, wir loben dich",
             gesangbuch_nummer="412", ccli_nummer="21001", aktiv=True, docstatus=0),
        Lied(name="LIED-2", titel="Ausgelassenes Lied", aktiv=False, docstatus=0),
        Lied(name="LIED-3", titel="Storniertes Lied", aktiv=True, docstatus=2),
    ])

    # Eigene Sammlungen: 'bibelarbeiten' (gemeinde) und 'themenreihe' (plan-
    # bezogen auf PLAN-C, uebergangsweise ueber definition umfang/plan).
    s.add_all([
        PrSammlung(id="SAM-BIBEL", schluessel="bibelarbeiten", name="Bibelarbeiten",
                   definition={}),
        PrSammlung(id="SAM-THEMEN", schluessel="themenreihe", name="Themenreihe",
                   umfang="plan", plan="PLAN-C", definition={}),
        PrSammlung(id="SAM-GEHEIM", schluessel="geheim", name="Intern",
                   definition={"umfang": "intern"}),
        # Gleichnamig zur Lied-Tabelle: Eintraege duerfen NICHT erscheinen.
        PrSammlung(id="SAM-LIEDER", schluessel="lieder", name="Lieder-Kopf",
                   definition={}),
    ])
    s.add_all([
        PrSammlungEintrag(id="SE-1", sammlung="SAM-BIBEL", reihenfolge=1,
                          daten={"titel": "Schöpfung"}, aktiv=True),
        PrSammlungEintrag(id="SE-2", sammlung="SAM-BIBEL", reihenfolge=2,
                          daten={"titel": "Passion"}, aktiv=False),
        PrSammlungEintrag(id="SE-3", sammlung="SAM-THEMEN", reihenfolge=1,
                          daten={"titel": "Advent"}, aktiv=True),
        PrSammlungEintrag(id="SE-4", sammlung="SAM-THEMEN", reihenfolge=2,
                          daten={"titel": "Weihnachten"}, aktiv=True),
        PrSammlungEintrag(id="SE-5", sammlung="SAM-LIEDER", reihenfolge=1,
                          daten={"titel": "Fremdling"}, aktiv=True),
    ])
    s.add(PrMerkmalWert(merkmal="MK-REIHE", ziel_id="SE-1", wert={"wert": "KT1"}))

    # Abwesenheiten: eine allgemein, eine chorplan-spezifisch, eine freizeit-
    # spezifisch.
    s.add_all([
        PrAbwesenheit(mitglied="M-1", von=date(2026, 3, 1), bis=date(2026, 3, 10)),
        PrAbwesenheit(mitglied="M-2", von=date(2026, 3, 5), bis=date(2026, 3, 7),
                      nur_plantyp="chorplan"),
        PrAbwesenheit(mitglied="M-2", von=date(2026, 4, 1), bis=date(2026, 4, 5),
                      nur_plantyp="freizeit"),
    ])

    # Historie: Eintraege frueherer Plaene (PLAN-B chorplan, PLAN-C freizeit)
    # sowie ein Eintrag im eigenen Plan (PLAN-A, muss rausfallen).
    s.add_all([
        PrTermin(id="T-B1", plan="PLAN-B", plantyp_version="PV-CHOR", datum=date(2025, 11, 2)),
        PrTermin(id="T-B2", plan="PLAN-B", plantyp_version="PV-CHOR", datum=date(2027, 1, 4)),
        PrTermin(id="T-C1", plan="PLAN-C", plantyp_version="PV-FREI", datum=date(2025, 8, 1)),
        PrTermin(id="T-A1", plan="PLAN-A", plantyp_version="PV-CHOR", datum=date(2026, 2, 1)),
    ])
    s.add_all([
        PrEintrag(termin="T-B1", feld_pfad="lieder[0]", wert="LIED-1"),
        PrEintrag(termin="T-B1", feld_pfad="einsingen", wert="M-2"),
        PrEintrag(termin="T-B2", feld_pfad="einsingen", wert="M-1"),
        PrEintrag(termin="T-C1", feld_pfad="leitung", wert=["M-1", "M-2"]),
        PrEintrag(termin="T-A1", feld_pfad="einsingen", wert="M-3"),
    ])

    # Kalender: nur 'Festgelegt' ist freigegeben.
    s.add(Eventkategorie(name="Gottesdienst", event_category_name="Gottesdienst"))
    s.add_all([
        Element(name="EV-1", status="Festgelegt",
                element_start=datetime(2026, 12, 24, 18, 0),
                element_name="Adventssingen", element_category="Gottesdienst",
                gruppe="CHOR", docstatus=0),
        Element(name="EV-2", status="Vorschlag",
                element_start=datetime(2026, 12, 31, 20, 0),
                element_name="Jahreswechsel", docstatus=0),
        Element(name="EV-3", status="Festgelegt", all_day=True,
                element_start=datetime(2026, 12, 25, 0, 0),
                element_name="2. Weihnachtstag", docstatus=0),
    ])

    s.commit()
    yield s
    s.close()


def _quelle(db, **bindung) -> DBDatenquelle:
    """Baut eine DBDatenquelle mit den ueblichen Bindungen."""
    return DBDatenquelle(
        db,
        plantyp=bindung.get("plantyp", "chorplan"),
        plan_id=bindung.get("plan_id"),
        veranstaltung=bindung.get("veranstaltung", ""),
    )


# --------------------------------------------------------------------------- #
# Protokoll + Personen/Gruppen/Merkmale
# --------------------------------------------------------------------------- #


def test_ist_datenquelle_protokoll(db):
    """Die Klasse erfuellt das Datenquelle-Protokoll der Engine."""
    quelle = _quelle(db)
    assert isinstance(quelle, Datenquelle)


def test_personen_mapping_und_storno(db):
    """Mitglieder werden zu Personen; stornierte Mitglieder fehlen."""
    quelle = _quelle(db)
    personen = {p.kennung: p for p in quelle.personen()}
    assert set(personen) == {"M-1", "M-2"}
    anna = personen["M-1"]
    assert anna.name == "Anna Beispiel"
    assert anna.vorname == "Anna"
    assert anna.nachname == "Beispiel"
    assert anna.email == "anna@example.org"
    # UXP-R3: kein Kuerzel-Feld im Datenmodell -> aus dem Namen abgeleitet.
    assert anna.kuerzel == "A. Beispiel"
    assert anna.gruppen == frozenset({"CHOR", "TEAM-1"})
    assert anna.hat_merkmal("klavier") is True
    assert anna.hat_merkmal("stimme") == "Alt"
    assert personen["M-2"].hat_merkmal("klavier") is False
    assert personen["M-2"].gruppen == frozenset()


def test_gruppen_nur_gueltige_mitgliedschaften(db):
    """Nur parenttype='Gruppe' + parentfield='mitglieder' zaehlt."""
    quelle = _quelle(db)
    gruppen = {g.kennung: g for g in quelle.gruppen()}
    assert gruppen["CHOR"].mitglieder == frozenset({"M-1"})  # GM-2 ungueltig
    assert gruppen["CHOR"].obergruppe == "GEMEINDE"
    assert gruppen["TEAM-1"].mitglieder == frozenset({"M-1"})  # GM-3 storniert
    assert gruppen["CHOR"].pflicht_mitglieder is None  # fail-closed: kein Feld
    assert quelle.gruppen_mitglieder("CHOR") == frozenset({"M-1"})
    assert quelle.gruppen_mitglieder("UNBEKANNT") == frozenset()


def test_merkmal_werte(db):
    """merkmal_werte liefert Person-Kennung -> Wert inkl. Entpack-Regel."""
    quelle = _quelle(db)
    assert quelle.merkmal_werte("klavier") == {"M-1": True, "M-2": False}
    assert quelle.merkmal_werte("stimme") == {"M-1": "Alt"}
    assert quelle.merkmal_werte("unbekannt") == {}


# --------------------------------------------------------------------------- #
# Anmeldung (fail-closed)
# --------------------------------------------------------------------------- #


def test_anmeldungen_nur_explizite_rolle_bestaetigt(db):
    """Rolle nur aus feldlabel='rolle' bei bestaetigtem Status — kein Default."""
    quelle = _quelle(db)
    # Bestaetigt + explizite Rollen-Antwort: M-1 (AN-1), M-3 (AN-4).
    assert quelle.anmeldungen("mitarbeiter") == {"M-1", "M-3"}
    # AN-2 ist nur 'Anmeldeanfrage' -> M-2 gehoert nicht dazu.
    assert "M-2" not in quelle.anmeldungen("mitarbeiter")
    # Die Antwort 'Email' traegt keine Rolle; fremde Rollen existieren nicht.
    assert quelle.anmeldungen("leiter") == frozenset()
    assert quelle.anmeldungen("") == frozenset()


def test_anmeldungen_veranstaltungsbindung(db):
    """Veranstaltungs-Filter: Bindung und explizites Argument."""
    gebunden = _quelle(db, veranstaltung="EV-1")
    assert gebunden.anmeldungen("mitarbeiter") == {"M-1", "M-3"}
    assert gebunden.anmeldungen("mitarbeiter", "EV-2") == frozenset()
    # Ohne Bindung greift der explizite Veranstaltungs-Filter.
    assert _quelle(db).anmeldungen("mitarbeiter", "EV-2") == {"M-1"}


# --------------------------------------------------------------------------- #
# Sammlungen
# --------------------------------------------------------------------------- #


def test_sammlung_lieder_aus_aktiven_liedern(db):
    """'lieder' kommt aus der Lied-Tabelle inkl. Merkmalswerten."""
    quelle = _quelle(db)
    lieder = quelle.sammlung("lieder")
    assert [l.kennung for l in lieder] == ["LIED-1"]
    lied = lieder[0]
    assert lied.titel == "Großer Gott, wir loben dich"
    assert lied.attribut("nr") == "412"
    assert lied.attribut("nummer") == "412"
    assert lied.attribut("ccli") == "21001"
    assert lied.merkmale == {"thema": "Advent"}
    # Die gleichnamige pr_sammlung-Zeile liefert keine Eintraege.
    assert all(e.kennung != "SE-5" for e in lieder)


def test_eigene_sammlungen_und_umfang(db):
    """Gemeinde-Sammlungen immer; planbezogene nur fuer ihren Plan."""
    quelle = _quelle(db)
    bibel = quelle.sammlung("bibelarbeiten")
    assert [e.kennung for e in bibel] == ["SE-1"]  # SE-2 inaktiv
    assert bibel[0].titel == "Schöpfung"
    assert bibel[0].attribute["titel"] == "Schöpfung"
    # Merkmale liegen im Merkmal-Dict, nicht in den Attributen.
    assert bibel[0].merkmale == {"reihe": "KT1"}

    # Planbezogene Sammlung: nur mit Bindung auf PLAN-C sichtbar.
    mit_plan = _quelle(db, plantyp="freizeit", plan_id="PLAN-C")
    themen = mit_plan.sammlung("themenreihe")
    assert [e.titel for e in themen] == ["Advent", "Weihnachten"]
    assert _quelle(db, plan_id="PLAN-A").sammlung("themenreihe") == []
    assert _quelle(db).sammlung("themenreihe") == []
    # Unbekannter Umfang -> nie sichtbar (fail-closed).
    assert _quelle(db, plan_id="PLAN-C").sammlung("geheim") == []
    assert quelle.sammlung("unbekannt") == []


# --------------------------------------------------------------------------- #
# Abwesenheiten
# --------------------------------------------------------------------------- #


def test_abwesenheiten_nur_zutreffender_plantyp(db):
    """nur_plantyp muss zur Bindung passen; sonst wird nicht geliefert."""
    chor = _quelle(db, plantyp="chorplan")
    assert [(a.person, a.von) for a in chor.abwesenheiten(date(2026, 1, 1), date(2026, 12, 31))] == [
        ("M-1", date(2026, 3, 1)),
        ("M-2", date(2026, 3, 5)),
    ]
    frei = _quelle(db, plantyp="freizeit")
    assert {a.person for a in frei.abwesenheiten(date(2026, 1, 1), date(2026, 12, 31))} == {
        "M-1", "M-2",
    }
    # Ohne Bindung bleiben nur allgemeine Zeilen.
    offen = _quelle(db, plantyp=None)
    assert [a.person for a in offen.abwesenheiten(date(2026, 1, 1), date(2026, 12, 31))] == ["M-1"]
    # Zeitraum-Filter: Schnittmenge.
    eng = chor.abwesenheiten(date(2026, 3, 6), date(2026, 3, 6))
    assert [a.person for a in eng] == ["M-1", "M-2"]


# --------------------------------------------------------------------------- #
# Historie
# --------------------------------------------------------------------------- #


def test_historie_alle_plaene_schluessel_ohne_eigenen_plan(db):
    """Historie liest alle Plaene des Plantyps; Schlüssel statt UUID."""
    quelle = _quelle(db, plan_id="PLAN-A")
    bis = date(2026, 12, 31)
    alle = quelle.historie("*", bis)
    assert {h.plantyp for h in alle} == {"chorplan", "freizeit"}
    assert all(h.plantyp != "PT-CHOR" for h in alle)  # nie eine UUID
    # Eigener Plan (PLAN-A, 'M-3') ist ausgeschlossen.
    assert all(h.wert != "M-3" for h in alle)
    # Plantyp-Filter greift ueber den Schluessel.
    chor = quelle.historie("*", bis, plantyp="chorplan")
    assert {(h.feld_pfad, h.wert) for h in chor} == {
        ("lieder[0]", "LIED-1"),
        ("einsingen", "M-2"),
    }
    # Unbekannter Schluessel -> leer (kein Raten auf UUID).
    assert quelle.historie("*", bis, plantyp="PT-CHOR") == []
    assert quelle.historie("*", bis, plantyp="unbekannt") == []


def test_historie_feldpfad_bis_datum_und_listenwerte(db):
    """passt_zu_feld normalisiert; bis_datum filtert; Listen entfalten."""
    quelle = _quelle(db, plan_id="PLAN-A")
    # Feldpfad 'lieder[0]' passt zum Feld 'lieder'.
    assert [h.wert for h in quelle.historie("lieder", date(2026, 12, 31))] == ["LIED-1"]
    # bis_datum schliesst den Termin 2027 aus.
    spaet = quelle.historie("einsingen", date(2026, 12, 31))
    assert [(h.datum, h.wert) for h in spaet] == [(date(2025, 11, 2), "M-2")]
    # Listen-Werte werden je Wert entfaltet (Mehrplatz-Slot).
    frei = quelle.historie("leitung", date(2026, 12, 31), plantyp="freizeit")
    assert [h.wert for h in frei] == ["M-1", "M-2"]


def test_historie_ohne_bindung_und_leerer_db(db):
    """Ohne plan_id zaehlt auch der laufende Plan; leere DB ist leer."""
    quelle = _quelle(db, plan_id=None)
    werte = {h.wert for h in quelle.historie("einsingen", date(2027, 12, 31))}
    assert werte == {"M-2", "M-1", "M-3"}


# --------------------------------------------------------------------------- #
# Kalender
# --------------------------------------------------------------------------- #


def test_kalender_nur_festgelegte_ohne_privatdaten(db):
    """Nur 'Festgelegt' wird ausgeliefert (Freigabe wie bestehender Kalender)."""
    quelle = _quelle(db)
    termine = {t.kennung: t for t in quelle.kalender_termine({})}
    assert set(termine) == {"EV-1", "EV-3"}  # EV-2 'Vorschlag' bleibt privat
    advent = termine["EV-1"]
    assert advent.datum == date(2026, 12, 24)
    assert advent.uhrzeit is not None
    assert advent.name == "Adventssingen"
    assert advent.kategorie == "Gottesdienst"
    assert advent.gruppe == "CHOR"
    # Ganztags-Events haben keine Uhrzeit; Attributliste ist privatfrei.
    assert termine["EV-3"].uhrzeit is None
    assert not hasattr(advent, "beschreibung")
    assert not hasattr(advent, "teilnehmer")


def test_kalender_filter(db):
    """Filter kategorie/gruppe/von/bis eingrenzend."""
    quelle = _quelle(db)
    assert [t.kennung for t in quelle.kalender_termine({"kategorie": "Gottesdienst"})] == ["EV-1"]
    assert [t.kennung for t in quelle.kalender_termine({"gruppe": "CHOR"})] == ["EV-1"]
    assert [t.kennung for t in quelle.kalender_termine({"von": date(2026, 12, 25)})] == ["EV-3"]
    assert [t.kennung for t in quelle.kalender_termine({"bis": date(2026, 12, 24)})] == ["EV-1"]


# --------------------------------------------------------------------------- #
# Gebuendeltheit + leere DB
# --------------------------------------------------------------------------- #


def test_gebuendelte_abfragen_kein_n_plus_eins(db, engine):
    """Der Konstruktor braucht konstant viele Abfragen (kein N+1)."""
    zaehler = []

    @event.listens_for(engine, "before_cursor_execute")
    def _zaehle(conn, cursor, statement, parameters, context, executemany):
        zaehler.append(statement)

    try:
        _quelle(db)
        _quelle(db, plan_id="PLAN-C", veranstaltung="EV-1")
    finally:
        event.remove(engine, "before_cursor_execute", _zaehle)

    # Pro Quelle: merkmale, gruppen+mitgliedschaften, personen, anmeldungen,
    # lieder+sammlungen+eintraege, abwesenheiten, historie(2), kalender = 12;
    # ST3 ergaenzt je Quelle eine Abfrage fuer die Kategorie-Quellenmerkmale
    # (quelle='psalmos.kategorie') = 13; UXP-R4 ergaenzt je Quelle zwei
    # Abfragen fuer Untergruppen als Teams (untergruppe + deren
    # Mitgliedschaften) = 15 -> 30.
    assert len(zaehler) <= 30, f"zu viele Abfragen: {len(zaehler)}"


def test_leere_db_liefert_leere_quelle(session_factory):
    """Ohne Daten: leere Listen statt Fehler (P10 gutmuetig)."""
    s = session_factory()
    quelle = DBDatenquelle(s)
    assert quelle.personen() == []
    assert quelle.gruppen() == []
    assert quelle.sammlung("lieder") == []
    assert quelle.anmeldungen("mitarbeiter") == frozenset()
    assert quelle.abwesenheiten(date(2026, 1, 1), date(2026, 12, 31)) == []
    assert quelle.historie("*", date(2026, 12, 31)) == []
    assert quelle.kalender_termine({}) == []
    s.close()
