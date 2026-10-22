"""Regressionsschutz fuer den finalen Strukturkontext bedingter Team-Besetzung."""
from datetime import date

import pytest

from diakronos_app.planrahmen.engine import InMemoryDatenquelle
from diakronos_app.planrahmen.engine.datenquelle import Gruppe
from diakronos_app.planrahmen.engine.modell import Eintrag, Termin
from diakronos_app.planrahmen.pruefung import pruefe_plantyp
from diakronos_app.planrahmen.regeln.auswertung import pruefe_plan


@pytest.mark.parametrize("baustein", ["nicht_gleichzeitig", "zusammen", "nicht_zusammen"])
@pytest.mark.parametrize("teilmenge", ["a", "b"])
@pytest.mark.parametrize("bedingt", [False, True])
def test_finale_team_besetzung_behaelt_vollstaendige_bedingungsquelle(baustein, teilmenge, bedingt):
    team = {"id": "musik", "art": "team", "teams": ["band"], "mitglieder": {"person": teilmenge}}
    if bedingt:
        team["bedingung"] = {"feld_gesetzt": "leitung"}
    regel = {"baustein": baustein, "stufe": "muss"}
    regel.update({"felder": ["leitung", "musik"]} if baustein == "nicht_gleichzeitig" else {"personen": ["a", "b"]})
    plantyp = {"schema": "diakronos/plantyp@1", "id": "dienst", "name": "Dienst",
               "felder": [{"id": "leitung", "art": "person"}, team], "regeln": [regel]}
    assert not [m for m in pruefe_plantyp(plantyp) if m.stufe == "fehler"]
    termin = Termin(date(2026, 1, 4), "standard")
    quelle = InMemoryDatenquelle.mit_personen(["a", "b"])
    quelle.gruppen_liste = [Gruppe("band", mitglieder=frozenset({"a", "b"}))]
    eintraege = [Eintrag("leitung", "b", "person", termin), Eintrag("musik", "band", "team", termin)]
    verletzt = teilmenge == ("a" if baustein == "nicht_zusammen" else "b")
    verstoesse = pruefe_plan(plantyp, [termin], eintraege, quelle)
    assert bool(verstoesse) == verletzt
    assert all(v.baustein == baustein and v.stufe == "muss" for v in verstoesse)
