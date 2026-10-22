"""Bedingte Sammlungswerte vor der Besetzungs-Vorbelegung klaeren."""
from datetime import date

import pytest

from diakronos_app.planrahmen.engine import InMemoryDatenquelle, Sammlungseintrag, generiere
from diakronos_app.planrahmen.engine.modell import Eintrag, Termin
from diakronos_app.planrahmen.engine.struktur import aufloesen_mit_eintraegen
from diakronos_app.planrahmen.pruefung import pruefe_plantyp


@pytest.mark.parametrize("umgekehrt", [False, True])
@pytest.mark.parametrize("reihe", [False, True])
@pytest.mark.parametrize("quelle_art", ["automatisch", "fixiert", "ausgeblendet", "leer", "manuell", "unbedingt"])
def test_bedingtes_lied_geschwister_vor_besetzung(
    umgekehrt: bool, reihe: bool, quelle_art: str,
) -> None:
    """Auch unsichtbare Quellen sind nicht leer, solange ihre Freigabe offen ist."""
    lied = dict(id="lied", art="eintrag", sammlung="lieder")
    if quelle_art != "unbedingt":
        lied["bedingung"] = {"feld_gesetzt": "freigabe"}
    if quelle_art == "manuell":
        lied["fuellen"] = "manuell"
    besetzung = dict(id="dirigent", art="person", fuellen="vorbelegen", aus="eintrag.dirigent")
    inhalt = [besetzung, lied] if umgekehrt else [lied, besetzung]
    felder = [dict(id="programm", art="ablauf", elemente=[dict(typ="lied", inhalt=inhalt)]),
              dict(id="freigabe", art="person", rolle={"person": "unbekannt" if quelle_art == "ausgeblendet" else "a"})]
    plantyp = dict(schema="diakronos/plantyp@1", id="dienst", name="Dienst", felder=felder)
    if reihe:
        plantyp["terminreihen"] = [dict(id="dienst", termine={"manuell": [{"datum": "2026-01-04"}]},
                                        felder=plantyp.pop("felder"))]
    assert not [m for m in pruefe_plantyp(plantyp) if m.stufe == "fehler"]
    praefix = "dienst:" if reihe else ""
    termin = Termin(date(2026, 1, 4), "dienst" if reihe else "standard",
                    ablauf={praefix + "programm": [{"id": "e1", "typ": "lied"}]})
    daten = InMemoryDatenquelle.mit_personen(["a"])
    daten.sammlungen = {"lieder": [] if quelle_art == "leer" else [
        Sammlungseintrag("lied1", "lieder", merkmale={"dirigent": "a"})]}
    fixierte = [Eintrag(praefix + "programm/e1.lied", "lied1", "eintrag", termin, fixiert=True)] if quelle_art == "fixiert" else []
    vorschlag = generiere(plantyp, {}, [termin], fixierte, daten)
    eintrag = vorschlag.eintrag_zu(praefix + "programm/e1.dirigent")
    assert eintrag is not None
    gesetzt = quelle_art in {"automatisch", "fixiert", "unbedingt"}
    assert eintrag.wert == ("a" if gesetzt else None)
    if gesetzt:
        assert not vorschlag.meldungen
    else:
        assert "ist leer" in eintrag.meldung
        assert "ungeklaert" not in eintrag.meldung
    assert not vorschlag.verstoesse
    assert eintrag.feld_pfad in {s.feld_pfad for s in aufloesen_mit_eintraegen(plantyp, termin, vorschlag.eintraege)}
    if fixierte:
        assert vorschlag.eintrag_zu(fixierte[0].feld_pfad) is fixierte[0]
    assert termin.ablauf == {praefix + "programm": [{"id": "e1", "typ": "lied"}]}
