"""End-to-End-Abnahme von C3/C4 und rekursiven Strukturbedingungen."""
from copy import deepcopy
from datetime import date
import subprocess
import sys

import pytest

from diakronos_app.planrahmen import ressourcen
from diakronos_app.planrahmen.engine import InMemoryDatenquelle, Person, Sammlungseintrag, generiere, erzeuge_termine, uebernimm
from diakronos_app.planrahmen.engine.datenquelle import Abwesenheit, Gruppe
from diakronos_app.planrahmen.engine.datenquelle import Historieneintrag
from diakronos_app.planrahmen.engine.modell import Eintrag, Termin, Vorschlag
from diakronos_app.planrahmen.engine.struktur import aufloesen, ablauf_elemente
from diakronos_app.planrahmen.regeln.auswertung import pruefe_plan


def test_musikteams_rotation_probe_und_aenderung_am_ursprung():
    plantyp = ressourcen.kochbuch_laden("musikteams")
    quelle = InMemoryDatenquelle(personen_liste=[Person("s", merkmale={"saenger": True}), Person("i")],
        gruppen_liste=[Gruppe(f"Gruppe {i}", mitglieder=frozenset({"s", "i"}), obergruppe="Musikteams") for i in [1, 2, 3, 4]])
    reihen = erzeuge_termine(plantyp, {}, quelle, date(2026, 12, 1), date(2026, 12, 31))
    termine = reihen["gottesdienst"] + reihen["probe"]
    v = generiere(plantyp, {}, termine, [], quelle)
    gd = {e.termin: e for e in v.eintraege if e.feld_pfad == "gottesdienst:team"}
    proben = [e for e in v.eintraege if e.feld_pfad == "probe:team"]
    assert proben
    assert all(t.bezug is not None and "feiertag" not in t.bezug.anlaesse for t in reihen["probe"])
    assert gd[reihen["gottesdienst"][0]].wert == "Gruppe 3"
    assert all(e.wert == gd[e.termin.bezug].wert for e in proben)
    assert all(e.wert != "Gruppe 3" for t, e in gd.items() if t.positionsnr_im_monat != 1)
    assert not [x for x in v.verstoesse if x.stufe == "muss"]
    ursprung = reihen["gottesdienst"][1]
    fixiert = Eintrag("gottesdienst:team", "Gruppe 4", "team", ursprung, True)
    neu = generiere(plantyp, {}, termine, [fixiert], quelle)
    assert next(e.wert for e in neu.eintraege if e.feld_pfad == "probe:team" and e.termin.bezug is ursprung) == "Gruppe 4"


def test_team_pflichtmitglieder_und_teilmenge():
    t = Termin(date(2026, 1, 4), "standard")
    quelle = InMemoryDatenquelle(personen_liste=[Person("s", merkmale={"saenger": True}), Person("i")],
        gruppen_liste=[Gruppe("team", mitglieder=frozenset({"s", "i"}), pflicht_mitglieder=frozenset({"s"}))],
        abwesenheiten_liste=[Abwesenheit("i", t.datum, t.datum)])
    plantyp = {"id": "teams", "felder": [{"id": "team", "art": "team", "teams": ["team"], "fuellen": "reihum", "mitglieder": {"merkmal": "saenger"}}],
        "regeln": [{"baustein": "abwesenheit_beachten", "stufe": "muss"}]}
    assert generiere(plantyp, {}, [t], [], quelle).eintraege[0].wert == "team"
    quelle.abwesenheiten_liste.append(Abwesenheit("s", t.datum, t.datum))
    v = generiere(plantyp, {}, [t], [], quelle)
    assert v.eintraege[0].wert is None
    assert v.meldungen


def test_ablauf_variable_elemente_besetzung_nummerierung_und_uebernahme():
    plantyp = ressourcen.kochbuch_laden("programm")
    t = Termin(date(2026, 12, 6), "standard", ablauf={"ablauf": [{"id": "l1", "typ": "lied"}, {"id": "s1", "typ": "szene"}, {"id": "l2", "typ": "lied"}]})
    quelle = InMemoryDatenquelle.mit_personen(["a", "b"])
    quelle.sammlungen = {"lieder": [Sammlungseintrag("m1", "lieder", merkmale={"dirigent": "a", "klavier": "b"})]}
    bestehende = [Eintrag("ablauf/l1.lied", "m1", "eintrag", t, True), Eintrag("ablauf/l2.lied", "m1", "eintrag", t, True), Eintrag("ablauf/s1.titel", "Szene", "text", t, False, "manuell")]
    original = deepcopy(bestehende)
    v = generiere(plantyp, {}, [t], bestehende, quelle)
    assert next(e.wert for e in v.eintraege if e.feld_pfad == "ablauf/l1.dirigent") == "a"
    assert next(e.wert for e in v.eintraege if e.feld_pfad == "ablauf/l1.klavier") == ["b"]
    assert next(e.wert for e in v.eintraege if e.feld_pfad == "ablauf/s1.titel") == "Szene"
    assert [(e["id"], e.get("nr")) for e in ablauf_elemente(plantyp, t)] == [("l1", 1), ("s1", None), ("l2", 2)]
    t.ablauf["ablauf"].reverse()
    assert {s.feld_pfad for s in aufloesen(plantyp, t)} == {s.feld_pfad for s in aufloesen(plantyp, original[0].termin)}
    assert len([x for x in v.verstoesse if x.baustein == "vorher_geuebt"]) == 2
    zieltermin = Termin(date(2026, 12, 20), "standard")
    ziel = Vorschlag(termine=[zieltermin])
    neu = uebernimm(ziel, v, ["ablauf.lied"])
    assert {e.feld_pfad for e in neu} >= {"ablauf/l1.lied", "ablauf/l1.dirigent", "ablauf/l1.klavier", "ablauf/l2.lied"}
    assert all(e.termin is zieltermin for e in neu)
    assert all(e.quelle == "uebernommen" and not e.fixiert for e in neu)
    assert zieltermin.ablauf["ablauf"] == [{"id": "l2", "typ": "lied"}, {"id": "l1", "typ": "lied"}]
    assert all(e.quelle == o.quelle for e, o in zip(bestehende, original))


def test_bedingte_varianten_reihen_anlass_und_gruppenanzahl():
    plantyp = {"id": "p", "terminreihen": [{"id": "r", "felder": [
        {"id": "block", "art": "gruppe", "anzahl": 2, "varianten": ["sonne", "regen"], "inhalt": [
            {"id": "raum", "art": "text", "bedingung": {"variante": "regen"}}]},
        {"id": "nur_mit_lied", "art": "text", "bedingung": {"feld_gesetzt": "r:lied"}},
        {"id": "lied", "art": "eintrag", "sammlung": "musik"}]}], "anlaesse": [
        {"id": "fest", "wirkung": {"ohne": ["block"], "mit": [{"id": "sonder", "art": "text"}]}}]}
    t = Termin(date(2026, 1, 4), "r")
    assert {s.feld_pfad for s in aufloesen(plantyp, t, feld_gesetzt=lambda p: p == "r:lied")} == {"r:block[0]@regen.raum", "r:block[1]@regen.raum", "r:nur_mit_lied", "r:lied"}
    t.anlaesse = frozenset({"fest"})
    assert {s.feld_pfad for s in aufloesen(plantyp, t)} == {"r:lied", "r:sonder"}


def test_nicht_fixierte_automatik_wird_neu_bewertet():
    t = Termin(date(2026, 1, 4), "standard")
    quelle = InMemoryDatenquelle.mit_personen(["a", "b"])
    quelle.abwesenheiten_liste = [Abwesenheit("a", t.datum, t.datum)]
    plantyp = {"id": "p", "felder": [{"id": "dienst", "art": "person"}], "regeln": [{"baustein": "abwesenheit_beachten", "stufe": "muss"}]}
    v = generiere(plantyp, {}, [t], [Eintrag("dienst", "a", "person", t, False, "optimieren")], quelle)
    assert v.eintraege[0].wert == "b"


def test_fixierter_zukuenftiger_wert_geht_in_abstand_ein():
    frueh = Termin(date(2026, 1, 4), "standard")
    spaet = Termin(date(2026, 1, 11), "standard")
    quelle = InMemoryDatenquelle(sammlungen={"musik": [Sammlungseintrag("m", "musik")]})
    plantyp = {"id": "p", "felder": [{"id": "lied", "art": "eintrag", "sammlung": "musik"}], "regeln": [{"baustein": "mindestabstand", "feld": "lied", "wochen": 8, "stufe": "muss"}]}
    v = generiere(plantyp, {}, [frueh, spaet], [Eintrag("lied", "m", "eintrag", spaet, True)], quelle)
    assert next(e.wert for e in v.eintraege if e.termin is frueh) is None
    assert next(e.wert for e in v.eintraege if e.termin is spaet) == "m"


def test_programm_und_chorplan_gemeinsame_wertweise_historie():
    """Echte Kochbuch-Typen teilen Uebungen und Konzertverwendungen."""
    programm = ressourcen.kochbuch_laden("programm")
    chor = ressourcen.kochbuch_laden("chorplan")
    quelle = InMemoryDatenquelle(sammlungen={"lieder": [
        Sammlungseintrag("m", "lieder", titel="Kind der Verheissung")
    ]}, historie_liste=[Historieneintrag(date(2026, 11, 1), "chorplan", "einueben[0]", "m")])
    t = Termin(date(2026, 12, 6), "standard", ablauf={"ablauf": [{"id": "l1", "typ": "lied"}]})
    eintrag = Eintrag("ablauf/l1.lied", "m", "eintrag", t, True)
    fehlt = pruefe_plan(programm, [t], [eintrag], quelle)
    assert any("Kind der Verheissung: erst 1 von 3" in x.meldung for x in fehlt)
    quelle.historie_liste.extend(Historieneintrag(date(2026, 11, d), "chorplan", "einueben[1]", "m") for d in (8, 15))
    assert not pruefe_plan(programm, [t], [eintrag], quelle)
    quelle.historie_liste.append(Historieneintrag(t.datum, "programm", eintrag.feld_pfad, "m"))
    abstand = next(r for r in chor["regeln"] if r["baustein"] == "mindestabstand")
    abstand["auch_in"] = ["programm"]
    spaet = Termin(date(2026, 12, 13), "standard")
    assert any(x.baustein == "mindestabstand" for x in pruefe_plan(chor, [spaet], [Eintrag("lieder[0]", "m", "eintrag", spaet)], quelle))


def test_parameter_rrule_abgeleitete_bedingung_und_letzter_termin():
    """Die gleichen strukturierten Bedingungen gelten auch fuer Terminreihen."""
    plantyp = {"id": "p", "terminreihen": [
        {"id": "r", "termine": {"regel": "FREQ=WEEKLY;BYDAY={parameter.tag}"}, "felder": [
            {"id": "schluss", "art": "text", "bedingung": {"termin_im_monat": -1}}]},
        {"id": "probe", "termine": {"abgeleitet": {"von": "r", "versatz": "-2T", "nur_wenn": {"parameter": {"id": "proben", "gleich": True}}}}}
    ]}
    reihen = erzeuge_termine(plantyp, {"tag": "SU", "proben": False}, InMemoryDatenquelle(), date(2026, 1, 1), date(2026, 1, 31))
    assert len(reihen["r"]) == 4
    assert not reihen["probe"]
    assert [t.position_von_hinten for t in reihen["r"]] == [4, 3, 2, 1]
    assert [bool(aufloesen(plantyp, t)) for t in reihen["r"]] == [False, False, False, True]


@pytest.mark.parametrize("modul", ["referenz", "pruefung", "regeln", "engine"])
def test_kalter_import_ohne_zirkulaere_abhaengigkeit(modul):
    """Auch ein API-/Doku-Prozess darf ohne vorab importierte Engine starten."""
    prozess = subprocess.run([sys.executable, "-c", f"import diakronos_app.planrahmen.{modul}"], capture_output=True, text=True, timeout=15)
    assert prozess.returncode == 0, prozess.stderr


def test_erntedank_regional_konfigurierbar_ohne_plan_sonderlogik():
    """Regionale Berechnung gilt fuer Erzeugung und Anlasszuordnung zugleich."""
    plantyp = {"id": "p", "termine": {"feiertage": ["erntedank"]}}
    von, bis = date(2026, 9, 1), date(2026, 10, 31)
    standard = erzeuge_termine(plantyp, {}, InMemoryDatenquelle(), von, bis)["standard"]
    assert [t.datum for t in standard] == [date(2026, 10, 4)]
    regional = erzeuge_termine(plantyp, {}, InMemoryDatenquelle(), von, bis, erntedank="2. So im September")["standard"]
    assert [t.datum for t in regional] == [date(2026, 9, 13)]
    assert regional[0].anlaesse == frozenset({"erntedank", "feiertag"})


def test_uebernahme_typ_unabhaengig_von_innerfeldnamen():
    """Elementtyp, Ablauf-Feld und Innerfeld muessen nicht gleich heissen."""
    t = Termin(date(2026, 1, 4), "standard", ablauf={"programm": [{"id": "x", "typ": "musik"}]})
    quelle = Vorschlag(termine=[t], eintraege=[Eintrag("programm/x.stueck", "m", "eintrag", t), Eintrag("programm/x.leitung", "a", "person", t)])
    zieltermin = Termin(date(2026, 1, 11), "standard")
    neu = uebernimm(Vorschlag(termine=[zieltermin]), quelle, ["programm.musik"])
    assert {e.feld_pfad for e in neu} == {"programm/x.stueck", "programm/x.leitung"}
    assert zieltermin.ablauf == t.ablauf
