"""Uebungsplanung nutzt dieselbe abhaengigkeitsbewusste Fuellung wie Einsaetze."""
from datetime import date, timedelta
from typing import Any

import pytest

from diakronos_app.planrahmen.engine import generiere
from diakronos_app.planrahmen.engine.datenquelle import Historieneintrag, InMemoryDatenquelle, Sammlungseintrag
from diakronos_app.planrahmen.engine.modell import Eintrag, Termin, Vorschlag


def _plan(
    bedingtes_kind: bool = False, zusatz: list[dict[str, Any]] | None = None,
    *, umgekehrt: bool = False,
) -> tuple[Vorschlag, list[Termin]]:
    """Zwei Uebungstage vor einem fixierten Einsatz, mit optionalen Verbrauchern."""
    termine = [Termin(date(2026, 10, 4) + timedelta(weeks=i), "standard") for i in range(3)]
    notiz = {"id": "notiz", "art": "text", "fuellen": "vorbelegen", "aus": "eintrag.notiz"}
    if bedingtes_kind:
        notiz["bedingung"] = {"feld_gesetzt": "uebung"}
    pt = {"id": "plan", "felder": [
        {"id": "einsatz", "art": "eintrag", "sammlung": "objekte", "fuellen": "manuell"},
        {"id": "uebung", "art": "eintrag", "sammlung": "objekte", "anzahl": "0..2", "inhalt": [notiz]},
        *(zusatz or []),
    ], "regeln": [{"baustein": "vorher_geuebt", "feld": "einsatz", "uebungsfeld": "uebung", "mindestens": 2}]}
    if umgekehrt:
        pt["felder"].reverse()
    dq = InMemoryDatenquelle(sammlungen={"objekte": [Sammlungseintrag("x", "objekte", merkmale={"notiz": "vorbereiten"})]})
    fix = Eintrag("einsatz", "x", "eintrag", termine[-1], fixiert=True)
    return generiere(pt, {}, termine, [fix], dq), termine


@pytest.mark.parametrize("bedingt", [False, True])
def test_unterfeld_nach_geplanter_uebung_vorbelegen(bedingt: bool) -> None:
    v, termine = _plan(bedingtes_kind=bedingt)
    for t in termine[:2]:
        assert any(e.termin is t and e.feld_pfad == "uebung[0]" and e.wert == "x" for e in v.eintraege)
        assert any(e.termin is t and e.feld_pfad == "uebung[0].notiz" and e.wert == "vorbereiten" for e in v.eintraege)
    assert not v.verstoesse


@pytest.mark.parametrize("umgekehrt", [False, True])
def test_externe_vorbelegung_wartet_auf_geplante_uebung(umgekehrt: bool) -> None:
    v, termine = _plan(umgekehrt=umgekehrt, zusatz=[
        {"id": "kopie", "art": "text", "fuellen": "vorbelegen", "aus": "uebung"},
        {"id": "kette", "art": "text", "fuellen": "vorbelegen", "aus": "kopie"},
    ])
    for t in termine[:2]:
        assert any(e.termin is t and e.feld_pfad == "kopie" and e.wert == "x" for e in v.eintraege)
        assert any(e.termin is t and e.feld_pfad == "kette" and e.wert == "x" for e in v.eintraege)
        assert not any(e.termin is t and e.feld_pfad == "kopie" and e.wert is None for e in v.eintraege)


def test_negierte_bedingung_entscheidet_erst_nach_uebung() -> None:
    v, termine = _plan(zusatz=[{"id": "ohne_uebung", "art": "eintrag", "sammlung": "objekte",
                              "bedingung": {"nicht": {"feld_gesetzt": "uebung"}}}])
    assert not any(e.termin in termine[:2] and e.feld_pfad == "ohne_uebung" for e in v.eintraege)
    assert any(e.termin is termine[-1] and e.feld_pfad == "ohne_uebung" and e.wert == "x" for e in v.eintraege)


@pytest.mark.parametrize("zweig", ["gruppe", "variante", "teil"])
def test_bedingte_container_werden_nach_uebung_aufgeloest(zweig: str) -> None:
    inhalt = [{"id": "kopie", "art": "text", "fuellen": "vorbelegen", "aus": "uebung"}]
    feld = {"id": "block", "art": "gruppe"}
    bedingung = {"feld_gesetzt": "uebung"}
    if zweig == "gruppe":
        feld.update(inhalt=inhalt, bedingung=bedingung)
        pfad = "block.kopie"
    else:
        feld["varianten" if zweig == "variante" else "teile"] = [{"id": "aktiv", "bedingung": bedingung, "inhalt": inhalt}]
        pfad = "block" + ("@" if zweig == "variante" else "#") + "aktiv.kopie"
    v, termine = _plan(zusatz=[feld])
    for t in termine[:2]:
        assert any(e.termin is t and e.feld_pfad == pfad and e.wert == "x" for e in v.eintraege)
    assert not any(e.termin is termine[-1] and e.feld_pfad == pfad for e in v.eintraege)


@pytest.mark.parametrize("mehrdeutig", [False, True])
def test_manuelle_instanzwerte_bleiben_und_vorbelegung_waehlt_nicht_willkuerlich(mehrdeutig: bool) -> None:
    """Einzelner Wert ist kopierbar; zwei Instanzen brauchen einen exakten Bezug."""
    t = Termin(date(2026, 10, 4), "probe")
    pt = {"id": "plan", "terminreihen": [{"id": "probe", "felder": [
        {"id": "kopie", "art": "text", "fuellen": "vorbelegen", "aus": "uebung"},
        {"id": "exakt", "art": "text", "fuellen": "vorbelegen", "aus": "uebung[0]"},
        {"id": "uebung", "art": "eintrag", "sammlung": "objekte", "anzahl": "0..2", "fuellen": "manuell"},
    ]}], "regeln": [{"baustein": "vorher_geuebt", "feld": "einsatz", "uebungsfeld": "probe:uebung", "mindestens": 2}]}
    fixes = [Eintrag("probe:uebung[0]", "x", "eintrag", t, fixiert=True),
             Eintrag("probe:exakt", "Handkorrektur", "text", t, quelle="manuell")]
    if mehrdeutig:
        fixes.append(Eintrag("probe:uebung[1]", "y", "eintrag", t, quelle="manuell"))
    v = generiere(pt, {}, [t], fixes, InMemoryDatenquelle())
    assert all(e in v.eintraege for e in fixes)
    assert len([e for e in v.eintraege if e.feld_pfad == "probe:exakt"]) == 1
    kopie = next(e for e in v.eintraege if e.feld_pfad == "probe:kopie")
    assert kopie.wert == (None if mehrdeutig else "x")
    if mehrdeutig:
        assert kopie.meldung


def test_abgeleiteter_verbraucher_wartet_auf_uebung_des_ursprungs() -> None:
    """Negativer Terminversatz darf eine aufgeschobene Quelle nicht leer kopieren."""
    urspruenge = [Termin(date(2026, 10, 4) + timedelta(weeks=i), "quelle") for i in range(3)]
    abgeleitete = [Termin(t.datum - timedelta(days=2), "kopie", bezug=t) for t in urspruenge]
    pt = {"id": "plan", "terminreihen": [
        {"id": "quelle", "felder": [
            {"id": "einsatz", "art": "eintrag", "sammlung": "objekte", "fuellen": "manuell"},
            {"id": "uebung", "art": "eintrag", "sammlung": "objekte", "anzahl": "0..2"},
        ]},
        {"id": "kopie", "felder": [
            {"id": "wert", "art": "text", "fuellen": "vorbelegen", "aus": "bezug.uebung[0]"},
        ]},
    ], "regeln": [{"baustein": "vorher_geuebt", "feld": "quelle:einsatz", "uebungsfeld": "quelle:uebung", "mindestens": 2}]}
    fix = Eintrag("quelle:einsatz", "x", "eintrag", urspruenge[-1], fixiert=True)
    dq = InMemoryDatenquelle(sammlungen={"objekte": [Sammlungseintrag("x", "objekte")]})
    v = generiere(pt, {}, urspruenge + abgeleitete, [fix], dq)
    for t in abgeleitete[:2]:
        assert any(e.termin is t and e.feld_pfad == "kopie:wert" and e.wert == "x" for e in v.eintraege)
        assert not any(e.termin is t and e.feld_pfad == "kopie:wert" and e.wert is None for e in v.eintraege)


@pytest.mark.parametrize("historientyp", ["plan", "anderer_plan"])
def test_vorbereitete_kandidaten_bleiben_in_phase_eins_bevorzugt(historientyp: str) -> None:
    """Die Laufzeitoptimierung darf weder lokale noch zusaetzliche Historie ignorieren."""
    t = Termin(date(2026, 10, 4), "standard")
    pt = {"id": "plan", "felder": [
        {"id": "einsatz", "art": "eintrag", "sammlung": "objekte"},
        {"id": "uebung", "art": "eintrag", "sammlung": "objekte", "fuellen": "manuell"},
    ], "regeln": [{"baustein": "vorher_geuebt", "feld": "einsatz", "uebungsfeld": "uebung",
                   "auch_in": ["anderer_plan"], "mindestens": 2}]}
    dq = InMemoryDatenquelle(sammlungen={"objekte": [Sammlungseintrag(w, "objekte") for w in ("x", "y")]},
                            historie_liste=[Historieneintrag(date(2026, 9, d), historientyp, "uebung", "x") for d in (20, 27)])
    v = generiere(pt, {}, [t], [], dq, seed=0)
    assert next(e for e in v.eintraege if e.feld_pfad == "einsatz").wert == "x"
    assert not v.verstoesse
