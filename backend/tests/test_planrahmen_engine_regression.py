"""Regressionen fuer Regeln, Rotation und planuebergreifende Historie (P2)."""
from datetime import date

import pytest

from diakronos_app.planrahmen.engine import InMemoryDatenquelle, Person, Sammlungseintrag, generiere
from diakronos_app.planrahmen.engine.datenquelle import Abwesenheit, Gruppe, Historieneintrag
from diakronos_app.planrahmen.engine.modell import Eintrag, Slot, Termin
from diakronos_app.planrahmen.regeln.auswertung import Kontext, bewerte, index_aufbauen, pruefe_plan
from diakronos_app.planrahmen.regeln.registry import bekannte_bausteine


def test_rotation_setzt_historie_fort():
    plantyp = {"id": "dienst", "felder": [{"id": "leitung", "art": "person", "fuellen": "reihum"}]}
    quelle = InMemoryDatenquelle.mit_personen(["a", "b", "c"])
    quelle.historie_liste = [Historieneintrag(date(2025, 12, 28), "dienst", "leitung", "b")]
    termin = Termin(date(2026, 1, 4), "standard")
    assert generiere(plantyp, {}, [termin], [], quelle).eintraege[0].wert == "c"


@pytest.mark.parametrize("strategie", ["optimieren", "reihum", "der_reihe_nach", "vorbelegen"])
def test_muss_regeln_gelten_fuer_alle_strategien(strategie):
    feld = {"id": "lied", "art": "eintrag", "sammlung": "musik", "fuellen": strategie}
    if strategie == "vorbelegen":
        feld["aus"] = "quelle"
    plantyp = {"id": "dienst", "felder": [feld], "regeln": [
        {"baustein": "mindestabstand", "feld": "lied", "wochen": 8, "stufe": "muss"}]}
    quelle = InMemoryDatenquelle(sammlungen={"musik": [Sammlungseintrag("alt", "musik"), Sammlungseintrag("neu", "musik")]},
        historie_liste=[Historieneintrag(date(2026, 1, 1), "dienst", "lied", "alt")])
    termin = Termin(date(2026, 1, 4), "standard")
    bestehende = [Eintrag("quelle", "alt", "eintrag", termin, True)] if strategie == "vorbelegen" else []
    vorschlag = generiere(plantyp, {}, [termin], bestehende, quelle)
    assert next(e for e in vorschlag.eintraege if e.feld_pfad == "lied").wert != "alt"


def test_vorbelegung_liest_denselben_termin():
    plantyp = {"id": "dienst", "felder": [{"id": "musik", "art": "eintrag", "sammlung": "musik", "fuellen": "der_reihe_nach", "inhalt": [
        {"id": "leitung", "art": "person", "fuellen": "vorbelegen", "aus": "eintrag.leitung"}]}]}
    quelle = InMemoryDatenquelle.mit_personen(["a", "b"])
    quelle.sammlungen = {"musik": [Sammlungseintrag("m1", "musik", merkmale={"leitung": "a"}), Sammlungseintrag("m2", "musik", merkmale={"leitung": "b"}, reihenfolge=1)]}
    termine = [Termin(date(2026, 1, d), "standard") for d in [4, 11]]
    assert [e.wert for e in generiere(plantyp, {}, termine, [], quelle).eintraege if e.art == "person"] == ["a", "b"]


def test_historie_programm_zaehlt_fuer_anderen_feldpfad():
    plantyp = {"id": "dienst", "regeln": [{"baustein": "mindestabstand", "feld": "musik", "wochen": 8, "auch_in": ["programm"], "stufe": "muss"}]}
    quelle = InMemoryDatenquelle(historie_liste=[Historieneintrag(date(2026, 1, 1), "programm", "ablauf/id-1.lied", "m1")])
    termin = Termin(date(2026, 1, 4), "standard")
    verstoesse = pruefe_plan(plantyp, [termin], [Eintrag("musik[0]", "m1", "eintrag", termin)], quelle)
    assert [v.baustein for v in verstoesse] == ["mindestabstand"]


def test_abstand_pruefung_erkennt_wiederholung_im_plan():
    plantyp = {"id": "dienst", "regeln": [{"baustein": "mindestabstand", "feld": "musik", "wochen": 8}]}
    termine = [Termin(date(2026, 1, d), "standard") for d in [4, 11, 18]]
    eintraege = [Eintrag("musik", "m1", "eintrag", t) for t in termine]
    assert len(pruefe_plan(plantyp, termine, eintraege, InMemoryDatenquelle())) == 2


@pytest.mark.parametrize("baustein", bekannte_bausteine())
def test_jeder_baustein_positive_und_negative_planpruefung(baustein):
    termin = Termin(date(2026, 1, 4), "standard", anlaesse=frozenset({"fest"}))
    quelle = InMemoryDatenquelle.mit_personen(["a", "b"])
    quelle.sammlungen = {"musik": [Sammlungseintrag("gut", "musik", merkmale={"thema": "fest"}), Sammlungseintrag("schlecht", "musik")]}
    regeln = {
        "abwesenheit_beachten": {},
        "mindestabstand": {"feld": "lied", "wochen": 8},
        "max_pro_zeitraum": {"anzahl": 1, "zeitraum": "monat"},
        "min_pro_zeitraum": {"anzahl": 1, "zeitraum": "monat", "rolle": {"person": "b"}},
        "gleich_verteilen": {"rolle": {"eine": [{"person": "a"}, {"person": "b"}]}},
        "nicht_gleichzeitig": {"felder": ["leitung", "klavier"]},
        "zusammen": {"personen": ["a", "b"]},
        "nicht_zusammen": {"personen": ["a", "b"]},
        "vorher_geuebt": {"feld": "lied", "uebung": {"plantyp": "probe", "feld": "einueben"}, "mindestens": 2},
        "passend_zum_anlass": {"feld": "lied", "merkmal": "thema"},
        "verfuegbarkeit": {"person": "b", "muster": "2.So"},
    }
    regel = {"baustein": baustein, "stufe": "muss", **regeln[baustein]}
    plantyp = {"id": "dienst", "felder": [{"id": "lied", "art": "eintrag", "sammlung": "musik"}], "regeln": [regel]}
    gut = [Eintrag("leitung", "a", "person", termin)]
    schlecht = [Eintrag("leitung", "b", "person", termin)]
    if baustein == "abwesenheit_beachten":
        quelle.abwesenheiten_liste = [Abwesenheit("b", termin.datum, termin.datum)]
    elif baustein == "mindestabstand":
        quelle.historie_liste = [Historieneintrag(date(2026, 1, 1), "dienst", "lied", "schlecht")]
        gut = [Eintrag("lied", "gut", "eintrag", termin)]
        schlecht = [Eintrag("lied", "schlecht", "eintrag", termin)]
    elif baustein == "max_pro_zeitraum":
        schlecht += [Eintrag("klavier", "b", "person", termin)]
    elif baustein == "min_pro_zeitraum":
        gut, schlecht = schlecht, gut
    elif baustein == "gleich_verteilen":
        gut += [Eintrag("klavier", "b", "person", termin)]
        schlecht = [Eintrag(str(i), "a", "person", termin) for i in range(3)]
    elif baustein == "nicht_gleichzeitig":
        gut += [Eintrag("klavier", "b", "person", termin)]
        schlecht += [Eintrag("klavier", "b", "person", termin)]
    elif baustein == "zusammen":
        gut += [Eintrag("klavier", "b", "person", termin)]
    elif baustein == "nicht_zusammen":
        schlecht += [Eintrag("klavier", "a", "person", termin)]
    elif baustein == "vorher_geuebt":
        quelle.historie_liste = [Historieneintrag(date(2025, 12, d), "probe", "einueben", "gut") for d in [7, 14]]
        gut = [Eintrag("lied", "gut", "eintrag", termin)]
        schlecht = [Eintrag("lied", "schlecht", "eintrag", termin)]
    elif baustein == "passend_zum_anlass":
        gut = [Eintrag("lied", "gut", "eintrag", termin)]
        schlecht = [Eintrag("lied", "schlecht", "eintrag", termin)]
    assert not pruefe_plan(plantyp, [termin], gut, quelle)
    assert pruefe_plan(plantyp, [termin], schlecht, quelle)


def test_bewertung_stufen_und_gewicht():
    termin = Termin(date(2026, 1, 4), "standard")
    quelle = InMemoryDatenquelle.mit_personen(["a"])
    quelle.abwesenheiten_liste = [Abwesenheit("a", termin.datum, termin.datum)]
    kontext = Kontext({"id": "dienst"}, termin, quelle)
    slot = Slot("leitung", "person", {})
    for stufe, zulaessig, strafe in [("muss", False, 0), ("sollte", True, 3), ("hinweis", True, 0)]:
        bewertung = bewerte("a", slot, kontext, {"baustein": "abwesenheit_beachten", "stufe": stufe, "gewicht": 3})
        assert (bewertung.zulaessig, bewertung.strafe) == (zulaessig, strafe)
        assert bewertung.meldungen
