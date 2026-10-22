"""Dynamische Uebungskapazitaet darf aufloesbare Abhaengigkeiten nicht sperren."""
from datetime import date, timedelta
from typing import Any

import pytest

from diakronos_app.planrahmen.engine import generiere
from diakronos_app.planrahmen.engine.datenquelle import InMemoryDatenquelle, Sammlungseintrag
from diakronos_app.planrahmen.engine.modell import Eintrag, Termin


@pytest.mark.parametrize("umgekehrt", [False, True])
@pytest.mark.parametrize("zweig", ["unbedingt", "feld", "gruppe", "variante", "teil", "kette", "inaktiv", "statisch_inaktiv"])
def test_abhaengige_uebungsfelder_decken_beide_bedarfe(zweig: str, umgekehrt: bool) -> None:
    """Zwei freie Tage reichen auch bei spaeter aktivierter zweiter Uebung."""
    termine = [Termin(date(2026, 10, 4) + timedelta(weeks=i), "standard") for i in range(3)]
    uebung_b: dict[str, Any] = {"id": "uebung_b", "art": "eintrag", "sammlung": "objekte", "anzahl": "0..1"}
    felder = [
        {"id": "einsatz_a", "art": "eintrag", "sammlung": "objekte", "fuellen": "manuell"},
        {"id": "einsatz_b", "art": "eintrag", "sammlung": "objekte", "fuellen": "manuell"},
        {"id": "uebung_a", "art": "eintrag", "sammlung": "objekte", "anzahl": "0..1"},
    ]
    ziel_b = "uebung_b"
    if zweig in ("gruppe", "variante", "teil"):
        block: dict[str, Any] = {"id": "block", "art": "gruppe"}
        bedingung = {"feld_gesetzt": "uebung_a"}
        if zweig == "gruppe":
            block.update(bedingung=bedingung, inhalt=[uebung_b])
            ziel_b = "block.uebung_b"
        else:
            block["varianten" if zweig == "variante" else "teile"] = [
                {"id": "aktiv", "bedingung": bedingung, "inhalt": [uebung_b]}]
            ziel_b = "block" + ("@" if zweig == "variante" else "#") + "aktiv.uebung_b"
        felder.append(block)
    else:
        if zweig == "statisch_inaktiv":
            uebung_b["bedingung"] = {"wochentag": ["mo"]}
        if zweig in ("feld", "inaktiv"):
            uebung_b["bedingung"] = {"feld_gesetzt": "uebung_a" if zweig == "feld" else "leer"}
        if zweig == "kette":
            felder.extend([
                {"id": "kopie", "art": "text", "fuellen": "vorbelegen", "aus": "uebung_a"},
                {"id": "kette", "art": "text", "fuellen": "vorbelegen", "aus": "kopie"},
            ])
            uebung_b["bedingung"] = {"feld_gesetzt": "kette"}
        felder.append(uebung_b)
    felder.append({"id": "leer", "art": "text", "pflicht": False, "fuellen": "manuell"})
    if umgekehrt:
        felder.reverse()
    pt = {"id": "plan", "felder": felder, "regeln": [
        {"baustein": "vorher_geuebt", "feld": "einsatz_a", "uebungsfeld": "uebung_a", "mindestens": 2},
        {"baustein": "vorher_geuebt", "feld": "einsatz_b", "uebungsfeld": ziel_b, "mindestens": 2},
    ]}
    fixes = [Eintrag("einsatz_a", "x", "eintrag", termine[-1], fixiert=True),
             Eintrag("einsatz_b", "y", "eintrag", termine[-1], fixiert=True)]
    dq = InMemoryDatenquelle(sammlungen={"objekte": [Sammlungseintrag(w, "objekte") for w in ("x", "y")]})
    v = generiere(pt, {}, termine, fixes, dq, seed=7)
    assert all(e in v.eintraege for e in fixes)
    inaktiv = zweig in ("inaktiv", "statisch_inaktiv")
    for t in termine[:2]:
        assert any(e.termin is t and e.feld_pfad == "uebung_a[0]" and e.wert == "x" for e in v.eintraege)
        werte_b = [e.wert for e in v.eintraege if e.termin is t and e.feld_pfad == ziel_b + "[0]"]
        assert werte_b == ([] if inaktiv else ["y"])
    assert [v.feld_pfad for v in v.verstoesse] == (["einsatz_b"] if inaktiv else [])
