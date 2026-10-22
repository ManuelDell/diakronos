"""Fairness unterscheidet eigene Entscheidungen von kopierten Eintraegen."""
from datetime import date

from diakronos_app.planrahmen.engine.datenquelle import InMemoryDatenquelle
from diakronos_app.planrahmen.engine.modell import Eintrag, Slot, Termin
from diakronos_app.planrahmen.regeln.auswertung import Kontext, bewerte, index_aufbauen, pruefe_plan


def test_fairness_zaehlt_vorbelegte_nicht_in_auswahl_und_pruefung() -> None:
    """Zwei echte Entscheidungen fuer a/b, zwei Kopien von a sind fair."""
    t = Termin(date(2026, 10, 4), "standard")
    r = {"baustein": "gleich_verteilen", "feld": "team"}
    pt = {"id": "plan", "regeln": [r]}
    dq = InMemoryDatenquelle()
    eintraege = [Eintrag("team", w, "team", t, quelle=q) for w, q in
                 [("a", "optimieren"), ("b", "optimieren"), ("a", "vorbelegt"), ("a", "vorbelegen"), ("a", "abgeleitet")]]
    k = Kontext(pt, t, dq, eintraege=eintraege, historie=[])
    index_aufbauen(k)
    slot = Slot("team", "team", {})
    assert bewerte("a", slot, k, r).strafe == bewerte("b", slot, k, r).strafe
    assert not pruefe_plan(pt, [t], eintraege, dq)
    r["vorbelegte_mitzaehlen"] = True
    assert bewerte("a", slot, k, r).strafe > bewerte("b", slot, k, r).strafe
    assert len(pruefe_plan(pt, [t], eintraege, dq)) == 1


def test_ersatz_fuer_unzulaessige_vorbelegung_ist_eigene_entscheidung() -> None:
    """Ein aktiv gewaehlter Ersatz ist keine Kopie und muss fair mitzaehlen."""
    from diakronos_app.planrahmen.engine import generiere
    from diakronos_app.planrahmen.engine.datenquelle import Abwesenheit, Sammlungseintrag
    t = Termin(date(2026, 10, 4), "standard")
    pt = {"id": "plan", "felder": [
        {"id": "objekt", "art": "eintrag", "sammlung": "objekte", "inhalt": [
            {"id": "leitung", "art": "person", "fuellen": "vorbelegen", "aus": "eintrag.leitung"}]}],
        "regeln": [{"baustein": "abwesenheit_beachten", "stufe": "muss"}]}
    dq = InMemoryDatenquelle.mit_personen(["a", "b"])
    dq.sammlungen = {"objekte": [Sammlungseintrag("x", "objekte", merkmale={"leitung": "a"})]}
    dq.abwesenheiten_liste = [Abwesenheit("a", t.datum, t.datum)]
    v = generiere(pt, {}, [t], [], dq)
    e = next(e for e in v.eintraege if e.feld_pfad == "objekt.leitung")
    assert e.wert == "b"
    assert e.quelle == "optimieren"


def test_fairness_beschraenkt_auswahl_auf_benanntes_feld() -> None:
    """Ein anderes Amt darf die Feldverteilung nicht verzerren."""
    t = Termin(date(2026, 10, 4), "standard")
    r = {"baustein": "gleich_verteilen", "feld": "leitung"}
    dq = InMemoryDatenquelle.mit_personen(["a", "b"])
    k = Kontext({"id": "plan"}, t, dq, eintraege=[Eintrag("technik", "a", "person", t)], historie=[])
    index_aufbauen(k)
    assert bewerte("a", Slot("leitung", "person", {}), k, r).strafe == 0
