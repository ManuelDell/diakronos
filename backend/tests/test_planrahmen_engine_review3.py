"""Reihenfolgefeste Unterbaum-Bedingungen, Ablauf-Inferenz und Vorbelegung."""
from datetime import date
from typing import Any

import pytest

from diakronos_app.planrahmen.engine import InMemoryDatenquelle, generiere
from diakronos_app.planrahmen.engine.datenquelle import Abwesenheit
from diakronos_app.planrahmen.engine.modell import Termin
from diakronos_app.planrahmen.pruefung import pruefe_plantyp
from diakronos_app.planrahmen.regeln.auswertung import pruefe_plan


def _plantyp(felder: list[dict[str, Any]]) -> dict[str, Any]:
    """Alle Verhaltensproben auch gegen das deklarative Schema pruefen."""
    plantyp: dict[str, Any] = dict(schema="diakronos/plantyp@1", id="dienst", name="Dienst", felder=felder)
    assert not [m for m in pruefe_plantyp(plantyp) if m.stufe == "fehler"]
    return plantyp


@pytest.mark.parametrize("negiert", [False, True])
@pytest.mark.parametrize("freigabe", [False, True])
@pytest.mark.parametrize("form", ["gruppe", "variante", "teil", "ablauf"])
def test_container_wartet_auf_bedingte_kinder(form: str, freigabe: bool, negiert: bool) -> None:
    inhalt = [
        dict(id="leer", art="text", fuellen="manuell"),
        dict(id="leitung", art="person", rolle={"person": "a"},
             bedingung={"feld_gesetzt": "freigabe"}),
    ]
    block = dict(id="block", art="gruppe", inhalt=inhalt)
    termin = Termin(date(2026, 1, 4), "standard")
    if form in ("variante", "teil"):
        block["varianten" if form == "variante" else "teile"] = [{"id": "zweig"}]
    if form == "ablauf":
        block = dict(id="block", art="ablauf", elemente=[dict(typ="dienst", inhalt=inhalt)])
        termin.ablauf = {"block": [{"id": "e1", "typ": "dienst"}]}
    bedingung = {"feld_gesetzt": "block"}
    plantyp = _plantyp([
        dict(id="assistenz", art="person", rolle={"person": "b"},
             bedingung={"nicht": bedingung} if negiert else bedingung),
        block,
        dict(id="freigabe", art="person", rolle={"person": "a" if freigabe else "unbekannt"}),
    ])
    quelle = InMemoryDatenquelle.mit_personen(["a", "b"])
    vorschlag = generiere(plantyp, {}, [termin], [], quelle)
    erwartet = freigabe != negiert
    assert any(e.feld_pfad == "assistenz" for e in vorschlag.eintraege) == erwartet
    quelle.abwesenheiten_liste = [Abwesenheit("b", termin.datum, termin.datum)]
    plantyp["regeln"] = [{"baustein": "abwesenheit_beachten", "stufe": "muss"}]
    assert [v.feld_pfad for v in pruefe_plan(plantyp, [termin], vorschlag.eintraege, quelle)] == (
        ["assistenz"] if erwartet else [])


