"""Reihenfolgefeste Unterbaum-Bedingungen, Ablauf-Inferenz und Vorbelegung."""
from copy import deepcopy
from datetime import date
from typing import Any

import pytest

from diakronos_app.planrahmen.engine import InMemoryDatenquelle, generiere
from diakronos_app.planrahmen.engine.datenquelle import Abwesenheit
from diakronos_app.planrahmen.engine.modell import Eintrag, Termin
from diakronos_app.planrahmen.pruefung import pruefe_plantyp
from diakronos_app.planrahmen.regeln.auswertung import pruefe_plan


def _plantyp(felder: list[dict[str, Any]]) -> dict[str, Any]:
    """Alle Verhaltensproben auch gegen das deklarative Schema pruefen."""
    plantyp: dict[str, Any] = dict(schema="diakronos/plantyp@1", id="dienst", name="Dienst", felder=felder)
    assert not [m for m in pruefe_plantyp(plantyp) if m.stufe == "fehler"]
    return plantyp


@pytest.mark.parametrize("metadaten", [False, True])
@pytest.mark.parametrize("gesetzt", [False, True])
@pytest.mark.parametrize("negiert", [False, True])
def test_ablauftyp_bezieht_sich_auch_auf_eindeutig_inferierte_elemente(
    metadaten: bool, gesetzt: bool, negiert: bool,
) -> None:
    bedingung = {"feld_gesetzt": "programm.dienst.leitung"}
    plantyp = _plantyp([
        dict(id="assistenz", art="person", rolle={"person": "b"},
             bedingung={"nicht": bedingung} if negiert else bedingung),
        dict(id="programm", art="ablauf", elemente=[dict(typ="dienst", inhalt=[
            dict(id="leitung", art="person", fuellen="manuell")])]),
    ])
    termin = Termin(date(2026, 1, 4), "standard", ablauf=(
        {"programm": [{"id": "e1", "typ": "dienst"}]} if metadaten else {}))
    vorher = deepcopy(termin.ablauf)
    eintrag = Eintrag("programm/e1.leitung", "a" if gesetzt else None, "person", termin, fixiert=True)
    quelle = InMemoryDatenquelle.mit_personen(["a", "b"])
    vorschlag = generiere(plantyp, {}, [termin], [eintrag], quelle)
    assert any(e.feld_pfad == "assistenz" for e in vorschlag.eintraege) == (gesetzt != negiert)
    assert eintrag in vorschlag.eintraege
    assert termin.ablauf == vorher
    quelle.abwesenheiten_liste = [Abwesenheit("b", termin.datum, termin.datum)]
    plantyp["regeln"] = [{"baustein": "abwesenheit_beachten", "stufe": "muss"}]
    assert [v.feld_pfad for v in pruefe_plan(plantyp, [termin], vorschlag.eintraege, quelle)] == (
        ["assistenz"] if gesetzt != negiert else [])
    assert termin.ablauf == vorher


@pytest.mark.parametrize("metadaten", [False, True])
@pytest.mark.parametrize("teilmenge", ["a", "b"])
def test_inferierte_ablaufquelle_erhaelt_bedingte_team_teilmenge(
    metadaten: bool, teilmenge: str,
) -> None:
    from diakronos_app.planrahmen.engine.datenquelle import Gruppe

    plantyp = _plantyp([
        dict(id="musik", art="team", teams=["band"], mitglieder={"person": teilmenge},
             bedingung={"feld_gesetzt": "programm.dienst.leitung"}),
        dict(id="programm", art="ablauf", elemente=[dict(typ="dienst", inhalt=[
            dict(id="leitung", art="person", fuellen="manuell")])]),
    ])
    plantyp["regeln"] = [dict(baustein="nicht_gleichzeitig", stufe="muss", felder=["programm.leitung", "musik"])]
    assert not [m for m in pruefe_plantyp(plantyp) if m.stufe == "fehler"]
    termin = Termin(date(2026, 1, 4), "standard", ablauf=(
        {"programm": [{"id": "e1", "typ": "dienst"}]} if metadaten else {}))
    quelle = InMemoryDatenquelle.mit_personen(["a", "b"])
    quelle.gruppen_liste = [Gruppe("band", mitglieder=frozenset({"a", "b"}))]
    leitung = Eintrag("programm/e1.leitung", "b", "person", termin, fixiert=True)
    vorschlag = generiere(plantyp, {}, [termin], [leitung], quelle)
    musik = vorschlag.eintrag_zu("musik")
    assert musik is not None
    assert musik.wert == ("band" if teilmenge == "a" else None)
    # Handbesetzung prueft denselben Typbezug und dieselbe Team-Teilmenge.
    eintraege = [leitung, Eintrag("musik", "band", "team", termin, fixiert=True)]
    assert bool(pruefe_plan(plantyp, [termin], eintraege, quelle)) == (teilmenge == "b")


