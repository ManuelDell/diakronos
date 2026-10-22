"""Verhaltensregressionen aus der ersten Engine-Reviewrunde."""
from datetime import date

import pytest

from diakronos_app.planrahmen.engine import InMemoryDatenquelle, Sammlungseintrag, generiere
from diakronos_app.planrahmen.engine.bedarf import bedarfspruefung
from diakronos_app.planrahmen.engine.datenquelle import Gruppe, Abwesenheit
from diakronos_app.planrahmen.engine.modell import Termin, Eintrag
from diakronos_app.planrahmen.engine.rollen import kandidaten
from diakronos_app.planrahmen.regeln.auswertung import pruefe_plan


@pytest.mark.parametrize("umgekehrt", [False, True])
@pytest.mark.parametrize("leitung", ["a", "unbekannt"])
def test_feld_gesetzt_folgt_automatischer_vorbedingung(umgekehrt, leitung):
    felder = [
        {"id": "leitung", "art": "person", "rolle": {"person": leitung}},
        {"id": "assistenz", "art": "person", "rolle": {"person": "b"},
         "bedingung": {"feld_gesetzt": "leitung"}},
    ]
    plantyp = {"id": "dienst", "felder": felder[::-1] if umgekehrt else felder}
    termin = Termin(date(2026, 1, 4), "standard")
    vorschlag = generiere(plantyp, {}, [termin], [], InMemoryDatenquelle.mit_personen(["a", "b"]))
    werte = {e.feld_pfad: e.wert for e in vorschlag.eintraege}
    assert werte.get("assistenz") == ("b" if leitung == "a" else None)
    assert ("assistenz" in werte) == (leitung == "a")


@pytest.mark.parametrize("leitung", ["a", "unbekannt"])
def test_negierte_bedingung_wartet_auf_automatischen_wert(leitung):
    plantyp = {"id": "dienst", "felder": [
        {"id": "ersatz", "art": "person", "rolle": {"person": "b"},
         "bedingung": {"nicht": {"feld_gesetzt": "leitung"}}},
        {"id": "leitung", "art": "person", "rolle": {"person": leitung}},
    ]}
    termin = Termin(date(2026, 1, 4), "standard")
    werte = {e.feld_pfad: e.wert for e in generiere(
        plantyp, {}, [termin], [], InMemoryDatenquelle.mit_personen(["a", "b"])).eintraege}
    assert ("ersatz" in werte) == (leitung != "a")


@pytest.mark.parametrize("umgekehrt", [False, True])
@pytest.mark.parametrize("art", ["blatt", "gruppe", "variante", "teil", "ablauf"])
def test_negierte_bedingung_erkennt_ausgeblendete_vorbedingung(art, umgekehrt):
    blatt = {"id": "leitung", "art": "person", "rolle": {"person": "a"}}
    bedingung = {"anlass": "fest"}
    if art == "blatt":
        quelle, pfad = dict(blatt, bedingung=bedingung), "leitung"
    elif art == "ablauf":
        quelle = {"id": "block", "art": "ablauf", "elemente": [
            {"typ": "dienst", "bedingung": bedingung, "inhalt": [blatt]}]}
        pfad = "block/e1.leitung"
    else:
        quelle = {"id": "block", "art": "gruppe", "inhalt": [blatt]}
        if art == "gruppe":
            quelle["bedingung"], pfad = bedingung, "block.leitung"
        else:
            quelle["varianten" if art == "variante" else "teile"] = [{"id": "zweig", "bedingung": bedingung}]
            pfad = "block" + ("@" if art == "variante" else "#") + "zweig.leitung"
    felder = [quelle, {"id": "ersatz", "art": "person", "rolle": {"person": "b"},
                       "bedingung": {"nicht": {"feld_gesetzt": pfad}}}]
    plantyp = {"id": "dienst", "felder": felder[::-1] if umgekehrt else felder}
    termin = Termin(date(2026, 1, 4), "standard", ablauf={"block": [{"id": "e1", "typ": "dienst"}]} if art == "ablauf" else {})
    assert [(e.feld_pfad, e.wert) for e in generiere(
        plantyp, {}, [termin], [], InMemoryDatenquelle.mit_personen(["a", "b"])).eintraege] == [("ersatz", "b")]


def test_planpruefung_behaelt_mitglieder_bedingter_teams():
    plantyp = {"id": "dienst", "felder": [
        {"id": "leitung", "art": "person"},
        {"id": "musik", "art": "team", "mitglieder": {"person": "a"},
         "bedingung": {"feld_gesetzt": "leitung"}},
    ], "regeln": [{"baustein": "abwesenheit_beachten", "stufe": "muss"}]}
    termin = Termin(date(2026, 1, 4), "standard")
    quelle = InMemoryDatenquelle.mit_personen(["a", "b"])
    quelle.gruppen_liste = [Gruppe("band", mitglieder=frozenset({"a", "b"}))]
    quelle.abwesenheiten_liste = [Abwesenheit("b", termin.datum, termin.datum)]
    eintraege = [Eintrag("leitung", "a", "person", termin), Eintrag("musik", "band", "team", termin)]
    assert not pruefe_plan(plantyp, [termin], eintraege, quelle)


@pytest.mark.parametrize("zweite_art,zweiter_wert", [("person", "a"), ("team", "andere")])
@pytest.mark.parametrize("ueberlappt", [False, True])
def test_nicht_gleichzeitig_expandiert_teammitglieder(zweite_art, zweiter_wert, ueberlappt):
    plantyp = {"id": "dienst", "felder": [
        {"id": "musik", "art": "team", "teams": ["band"]},
        {"id": "technik", "art": zweite_art, **({"teams": [zweiter_wert]} if zweite_art == "team" else {"rolle": {"person": zweiter_wert}})},
    ], "regeln": [{"baustein": "nicht_gleichzeitig", "felder": ["musik", "technik"], "stufe": "muss"}]}
    quelle = InMemoryDatenquelle.mit_personen(["a", "b"])
    quelle.gruppen_liste = [Gruppe("band", mitglieder=frozenset({"a" if ueberlappt else "b"})),
                            Gruppe("andere", mitglieder=frozenset({"a"}))]
    termin = Termin(date(2026, 1, 4), "standard")
    vorschlag = generiere(plantyp, {}, [termin], [], quelle)
    assert next(e.wert for e in vorschlag.eintraege if e.feld_pfad == "technik") == (None if ueberlappt else zweiter_wert)
    assert not vorschlag.verstoesse
    fixierte = [Eintrag("musik", "band", "team", termin), Eintrag("technik", zweiter_wert, zweite_art, termin)]
    assert bool(pruefe_plan(plantyp, [termin], fixierte, quelle)) == ueberlappt


@pytest.mark.parametrize("baustein", ["zusammen", "nicht_zusammen"])
@pytest.mark.parametrize("vollstaendig", [False, True])
def test_paarregeln_expandieren_teams(baustein, vollstaendig):
    plantyp = {"id": "dienst", "felder": [{"id": "musik", "art": "team", "teams": ["band"]}],
               "regeln": [{"baustein": baustein, "personen": ["a", "b"], "stufe": "muss"}]}
    quelle = InMemoryDatenquelle.mit_personen(["a", "b"])
    quelle.gruppen_liste = [Gruppe("band", mitglieder=frozenset({"a", "b"} if vollstaendig else {"a"}))]
    termin = Termin(date(2026, 1, 4), "standard")
    verletzt = vollstaendig if baustein == "nicht_zusammen" else not vollstaendig
    vorschlag = generiere(plantyp, {}, [termin], [], quelle)
    assert vorschlag.eintraege[0].wert == (None if verletzt else "band")
    assert bool(pruefe_plan(plantyp, [termin], [Eintrag("musik", "band", "team", termin)], quelle)) == verletzt


def test_doppelbesetzung_beachtet_teilmenge_nicht_nur_pflichtmitglieder():
    plantyp = {"id": "dienst", "felder": [
        {"id": "musik", "art": "team", "teams": ["band"], "mitglieder": {"person": "b"}},
        {"id": "technik", "art": "person", "rolle": {"person": "b"}},
    ], "regeln": [{"baustein": "nicht_gleichzeitig", "felder": ["musik", "technik"], "stufe": "muss"}]}
    quelle = InMemoryDatenquelle.mit_personen(["a", "b"])
    quelle.gruppen_liste = [Gruppe("band", mitglieder=frozenset({"a", "b"}), pflicht_mitglieder=frozenset({"a"}))]
    termin = Termin(date(2026, 1, 4), "standard")
    assert generiere(plantyp, {}, [termin], [], quelle).eintraege[-1].wert is None


@pytest.mark.parametrize("filter,erwartet", [
    ({"merkmal": "klavier"}, ["a"]), ({"gruppe": "Chor"}, ["a"]),
    ({"alle": [{"merkmal": "klavier"}, {"gruppe": "Chor"}]}, ["a"]),
    ({"eine": [{"merkmal": "klavier"}, {"person": "b"}]}, ["a", "b"]),
    ({"nicht": {"gruppe": "Chor"}}, ["b"]),
])
def test_rollen_nutzen_protokolldaten_ohne_personenkopien(filter, erwartet):
    quelle = InMemoryDatenquelle.mit_personen(["a", "b"])
    quelle.merkmale = {"klavier": {"a": True, "b": False}}
    quelle.gruppen_liste = [Gruppe("Chor", mitglieder=frozenset({"a"}))]
    assert [p.kennung for p in kandidaten(filter, quelle)] == erwartet


def test_bedarf_folgt_benannten_rollen_auch_in_regeln():
    plantyp = {"id": "dienst", "rollen": [
        {"id": "musik", "filter": {"alle": [{"merkmal": "klavier"}, {"nicht": {"merkmal": "gast"}}]}},
        {"id": "predigt", "filter": {"merkmal": "prediger"}},
        {"id": "unbenutzt", "filter": {"merkmal": "irrelevant"}},
    ], "felder": [{"id": "leitung", "art": "person", "rolle": "@musik"}],
        "regeln": [{"baustein": "gleich_verteilen", "rolle": "@predigt"}]}
    bedarfe = bedarfspruefung(plantyp, InMemoryDatenquelle())
    assert {b.kennung for b in bedarfe if b.art == "merkmal"} == {"klavier", "gast", "prediger"}
    assert {b.kennung for b in bedarfe if b.art == "rolle"} == {"musik", "predigt"}


def test_sammlungsbedarfe_bleiben_bei_ihrer_quelle_inkl_regelmerkmal():
    plantyp = {"id": "dienst", "felder": [
        {"id": "lied", "art": "eintrag", "sammlung": "lieder", "inhalt": [
            {"id": "leitung", "art": "person", "fuellen": "vorbelegen", "aus": "eintrag.dirigent"}]},
        {"id": "spiel", "art": "eintrag", "sammlung": "spiele", "inhalt": [
            {"id": "leitung", "art": "person", "fuellen": "vorbelegen", "aus": "eintrag.betreuer"}]},
    ], "regeln": [{"baustein": "passend_zum_anlass", "feld": "lied", "merkmal": "thema"}]}
    quelle = InMemoryDatenquelle(sammlungen={
        "lieder": [Sammlungseintrag("l", "lieder", merkmale={"dirigent": "a"})],
        "spiele": [Sammlungseintrag("s", "spiele", merkmale={"betreuer": "b"})],
    })
    bedarfe = bedarfspruefung(plantyp, quelle)
    sammlungen = {b.kennung: b for b in bedarfe if b.art == "sammlung"}
    assert sammlungen["lieder"].einstufung == "eingeschraenkt"
    assert sammlungen["lieder"].detail == "1/1 ohne dirigent, thema"
    assert sammlungen["spiele"].einstufung == "ok"
    assert sammlungen["spiele"].detail == "0/1 ohne betreuer"
    assert not [b for b in bedarfe if b.art == "merkmal"]
