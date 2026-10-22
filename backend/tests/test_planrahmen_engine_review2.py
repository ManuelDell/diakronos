"""Deklarative Feldbezuege und vollstaendiger Strukturkontext aus Review 2."""
from datetime import date
from typing import Any

import pytest

from diakronos_app.planrahmen.engine import InMemoryDatenquelle, generiere
from diakronos_app.planrahmen.engine.datenquelle import Abwesenheit
from diakronos_app.planrahmen.engine.modell import Eintrag, Termin
from diakronos_app.planrahmen.pruefung import pruefe_plantyp
from diakronos_app.planrahmen.regeln.auswertung import pruefe_plan


def _gueltig(plantyp):
    plantyp.update(schema="diakronos/plantyp@1", id="dienst", name="Dienst")
    assert not [m for m in pruefe_plantyp(plantyp) if m.stufe == "fehler"]
    return plantyp


@pytest.mark.parametrize("form", ["einfach", "anzahl", "reihe", "ablauf", "gruppe", "variante", "teil"])
@pytest.mark.parametrize("gesetzt", [False, True])
@pytest.mark.parametrize("negiert", [False, True])
def test_deklarative_bedingung_folgt_konkreten_quellen(form, gesetzt, negiert):
    quelle_feld = {"id": "leitung", "art": "person", "rolle": {"person": "a" if gesetzt else "unbekannt"}}
    bezug = "leitung"
    termin = Termin(date(2026, 1, 4), "dienst" if form == "reihe" else "standard")
    if form in ("anzahl", "reihe"):
        quelle_feld["anzahl"] = 2
    if form == "ablauf":
        quelle_feld = {"id": "programm", "art": "ablauf", "elemente": [
            {"typ": "dienst", "inhalt": [quelle_feld]}]}
        termin.ablauf = {"programm": [{"id": "e1", "typ": "dienst"}, {"id": "e2", "typ": "dienst"}]}
        bezug = "programm.dienst.leitung"
    if form in ("gruppe", "variante", "teil"):
        quelle_feld = {"id": "block", "art": "gruppe", "anzahl": 2, "inhalt": [quelle_feld]}
        bezug = "block.leitung"
        if form != "gruppe":
            quelle_feld["varianten" if form == "variante" else "teile"] = [
                {"id": "zweig", "inhalt": quelle_feld.pop("inhalt")}]
            bezug = "block" + ("@" if form == "variante" else "#") + "zweig.leitung"
    bedingung = {"feld_gesetzt": bezug}
    assistenz = {"id": "assistenz", "art": "person", "rolle": {"person": "b"},
                 "bedingung": {"nicht": bedingung} if negiert else bedingung}
    # Abhaengiges Feld steht zuerst: keine zufaellige Reihenfolgegarantie.
    felder = [assistenz, quelle_feld]
    plantyp = {"terminreihen": [{"id": "dienst", "termine": {"manuell": [{"datum": "2026-01-04"}]}, "felder": felder}]} if form == "reihe" else {"felder": felder}
    _gueltig(plantyp)
    quelle = InMemoryDatenquelle.mit_personen(["a", "b"])
    vorschlag = generiere(plantyp, {}, [termin], [], quelle)
    pfad = "dienst:assistenz" if form == "reihe" else "assistenz"
    assert [(e.feld_pfad, e.wert) for e in vorschlag.eintraege if e.feld_pfad == pfad] == (
        [(pfad, "b")] if gesetzt != negiert else [])
    # Dieselbe deklarative Bedingung muss bei der Endpruefung aktiv bleiben.
    quelle.abwesenheiten_liste = [Abwesenheit("b", termin.datum, termin.datum)]
    plantyp["regeln"] = [{"baustein": "abwesenheit_beachten", "stufe": "muss"}]
    verstoesse = pruefe_plan(plantyp, [termin], vorschlag.eintraege, quelle)
    assert [v.feld_pfad for v in verstoesse] == ([pfad] if gesetzt != negiert else [])


@pytest.mark.parametrize("anzahl", [0, 2])
def test_negierte_mehrfachquelle_wird_erst_nach_allen_instanzen_geklaert(anzahl):
    plantyp = _gueltig({"felder": [
        {"id": "ersatz", "art": "person", "rolle": {"person": "b"},
         "bedingung": {"nicht": {"feld_gesetzt": "leitung"}}},
        {"id": "leitung", "art": "person", "anzahl": anzahl, "rolle": {"person": "a"}},
    ]})
    termin = Termin(date(2026, 1, 4), "standard")
    # Ein leerer fixierter Wert klaert nicht die noch offene zweite Instanz.
    bestehende = [Eintrag("leitung[0]", None, "person", termin, fixiert=True)] if anzahl else []
    vorschlag = generiere(plantyp, {}, [termin], bestehende, InMemoryDatenquelle.mit_personen(["a", "b"]))
    assert any(e.feld_pfad == "ersatz" for e in vorschlag.eintraege) == (anzahl == 0)


@pytest.mark.parametrize("reihe", [False, True])
def test_negierte_deklarative_quelle_in_ausgeblendeter_reihe(reihe):
    felder = [
        {"id": "ersatz", "art": "person", "rolle": {"person": "b"},
         "bedingung": {"nicht": {"feld_gesetzt": "leitung"}}},
        {"id": "leitung", "art": "person", "anzahl": 2, "rolle": {"person": "a"},
         "bedingung": {"anlass": "fest"}},
    ]
    plantyp: dict[str, Any] = {"anlaesse": [{"id": "fest"}]}
    if reihe:
        plantyp["terminreihen"] = [{"id": "dienst", "termine": {"manuell": [{"datum": "2026-01-04"}]}, "felder": felder}]
    else:
        plantyp["felder"] = felder
    _gueltig(plantyp)
    termin = Termin(date(2026, 1, 4), "dienst" if reihe else "standard")
    vorschlag = generiere(plantyp, {}, [termin], [], InMemoryDatenquelle.mit_personen(["a", "b"]))
    assert [(e.feld_pfad, e.wert) for e in vorschlag.eintraege] == [
        ("dienst:ersatz" if reihe else "ersatz", "b")]


@pytest.mark.parametrize("elemente", [[], [{"id": "e1", "typ": "dienst"}]])
def test_negierte_deklarative_ablaufquelle_ohne_aktive_elemente(elemente):
    plantyp = _gueltig({"anlaesse": [{"id": "fest"}], "felder": [
        {"id": "ersatz", "art": "person", "rolle": {"person": "b"},
         "bedingung": {"nicht": {"feld_gesetzt": "programm.dienst.leitung"}}},
        {"id": "programm", "art": "ablauf", "elemente": [
            {"typ": "dienst", "bedingung": {"anlass": "fest"}, "inhalt": [
                {"id": "leitung", "art": "person", "rolle": {"person": "a"}}]}]},
    ]})
    termin = Termin(date(2026, 1, 4), "standard", ablauf={"programm": elemente})
    vorschlag = generiere(plantyp, {}, [termin], [], InMemoryDatenquelle.mit_personen(["a", "b"]))
    assert [(e.feld_pfad, e.wert) for e in vorschlag.eintraege] == [("ersatz", "b")]
