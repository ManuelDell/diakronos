"""Reihenfolgefeste Unterbaum-Bedingungen, Ablauf-Inferenz und Vorbelegung."""
from datetime import date
from typing import Any

import pytest

from diakronos_app.planrahmen.engine import InMemoryDatenquelle, generiere
from diakronos_app.planrahmen.engine.modell import Termin
from diakronos_app.planrahmen.pruefung import pruefe_plantyp


def _plantyp(felder: list[dict[str, Any]]) -> dict[str, Any]:
    """Alle Verhaltensproben auch gegen das deklarative Schema pruefen."""
    plantyp: dict[str, Any] = dict(schema="diakronos/plantyp@1", id="dienst", name="Dienst", felder=felder)
    assert not [m for m in pruefe_plantyp(plantyp) if m.stufe == "fehler"]
    return plantyp


@pytest.mark.parametrize("umgekehrt", [False, True])
@pytest.mark.parametrize("gesetzt", [False, True])
@pytest.mark.parametrize("kette", [False, True])
def test_vorbelegung_klaert_automatische_quelle_vor_verbraucher(
    umgekehrt: bool, gesetzt: bool, kette: bool,
) -> None:
    felder = [
        dict(id="leitung", art="person", rolle={"person": "a" if gesetzt else "unbekannt"}),
        dict(id="assistenz", art="person", fuellen="vorbelegen", aus="leitung"),
    ]
    if kette:
        felder.append(dict(id="vertretung", art="person", fuellen="vorbelegen", aus="assistenz"))
    if umgekehrt:
        felder.reverse()
    plantyp = _plantyp(felder)
    termin = Termin(date(2026, 1, 4), "standard")
    vorschlag = generiere(plantyp, {}, [termin], [], InMemoryDatenquelle.mit_personen(["a"]))
    assert {e.feld_pfad: e.wert for e in vorschlag.eintraege} == {
        f["id"]: "a" if gesetzt else None for f in felder}
    if gesetzt:
        assert not vorschlag.meldungen
    else:
        assert any("Vorbelegen-Quelle" in m for m in vorschlag.meldungen)


@pytest.mark.parametrize("gesetzt", [False, True])
@pytest.mark.parametrize("reihe", [False, True])
def test_vorbelegung_wartet_auf_bedingte_quelle_in_der_aktuellen_reihe(
    gesetzt: bool, reihe: bool,
) -> None:
    felder = [
        dict(id="assistenz", art="person", fuellen="vorbelegen", aus="leitung"),
        dict(id="leitung", art="person", rolle={"person": "a"}, bedingung={"feld_gesetzt": "freigabe"}),
        dict(id="freigabe", art="person", rolle={"person": "a" if gesetzt else "unbekannt"}),
    ]
    plantyp = _plantyp(felder)
    if reihe:
        plantyp["terminreihen"] = [dict(id="dienst", termine={"manuell": [{"datum": "2026-01-04"}]},
                                        felder=plantyp.pop("felder"))]
        assert not [m for m in pruefe_plantyp(plantyp) if m.stufe == "fehler"]
    termin = Termin(date(2026, 1, 4), "dienst" if reihe else "standard")
    vorschlag = generiere(plantyp, {}, [termin], [], InMemoryDatenquelle.mit_personen(["a"]))
    assistenz = vorschlag.eintrag_zu("dienst:assistenz" if reihe else "assistenz")
    assert assistenz is not None
    assert assistenz.wert == ("a" if gesetzt else None)
    assert bool(vorschlag.meldungen) == (not gesetzt)
