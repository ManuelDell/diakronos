"""UX2 FACH 1: Uebungen vor von Hand festgelegten Singterminen.

Regression gegen den UX1-Folgebefund: ein fixierter Auftritt
ist Uebungsbedarf mit hoechster Prioritaet und bekommt seine Uebungen vor
dem Termin, solange fruehere Kapazitaet reicht. Reicht sie nicht, entsteht
eine klare kapazitaetsbezogene Meldung. Keine Chor-Sonderlogik — die
Vorrang-Regel gilt generisch fuer jedes ``vorher_geuebt``-Feld.
"""
from datetime import date

from diakronos_app.planrahmen import ressourcen
from diakronos_app.planrahmen.engine.datenquelle import InMemoryDatenquelle, Sammlungseintrag
from diakronos_app.planrahmen.engine.generator import generiere
from diakronos_app.planrahmen.engine.modell import Eintrag
from diakronos_app.planrahmen.engine.termine import erzeuge_termine
from diakronos_app.planrahmen.regeln.uebungsbedarf import uebungsbedarfe


def _vorlage() -> dict:
    pt = ressourcen.kochbuch_laden("chorplan")
    pt["termine"] = {"regel": "FREQ=WEEKLY;BYDAY=SU"}
    return pt


def _quelle() -> InMemoryDatenquelle:
    return InMemoryDatenquelle(sammlungen={
        "lieder": [Sammlungseintrag(f"l{i}", "lieder", titel=f"Lied {i:02d}") for i in range(40)]})


def _termine(pt, dq):
    return erzeuge_termine(pt, {}, dq, von=date(2026, 10, 1), bis=date(2026, 12, 31))["standard"]


def _fix(pt, dq, datum: date, wert: str = "l0") -> Eintrag:
    ziel = next(t for t in _termine(pt, dq) if t.datum == datum)
    return Eintrag("lieder[0]", wert, "eintrag", ziel, fixiert=True, quelle="manuell")


def _uebungen(v, wert: str, vor: date) -> list[date]:
    return sorted(e.termin.datum for e in v.eintraege
                  if e.wert == wert and e.feld_pfad.startswith("einueben") and e.termin.datum < vor)


def test_fixierter_auftritt_bekommt_zwei_uebungen_davor() -> None:
    """Von Hand festgelegter Singtermin am 08.11. erhaelt >= 2 Uebungen davor."""
    pt, dq = _vorlage(), _quelle()
    termine = _termine(pt, dq)
    fix = _fix(pt, dq, date(2026, 11, 8))
    v = generiere(pt, {}, termine, [fix], dq)
    uebungen = _uebungen(v, "l0", date(2026, 11, 8))
    assert len(uebungen) >= 2, uebungen
    # Nur Uebungstage desselben Werts, echte Kapazitaetstage der Reihe.
    assert all(u in {t.datum for t in termine} for u in uebungen)
    # Keine generische "erst 0 von 2"-Meldung mehr fuer den fixierten Eintrag.
    assert not [x for x in v.verstoesse
                if x.baustein == "vorher_geuebt" and x.feld_pfad == "einueben"
                and x.meldung.startswith("l0 ")]


def test_vorrang_gewinnt_gegen_frueher_faellige_auto_lieder() -> None:
    """Automatisch eingeplante Lieder draengen den fixierten Auftritt nicht weg."""
    pt, dq = _vorlage(), _quelle()
    termine = _termine(pt, dq)
    # Ohne den Fix gewinnen frueher faellige Auto-Lieder alle Plaetze.
    ohne = generiere(pt, {}, termine, [], dq)
    assert _uebungen(ohne, "l0", date(2026, 11, 8)) == []
    mit = generiere(pt, {}, termine, [_fix(pt, dq, date(2026, 11, 8))], dq)
    assert len(_uebungen(mit, "l0", date(2026, 11, 8))) >= 2


def test_bedarf_erbt_vorrang_vom_fixierten_einsatz() -> None:
    pt, dq = _vorlage(), _quelle()
    fix = _fix(pt, dq, date(2026, 11, 8))
    bedarfe = {b.wert: b for b in uebungsbedarfe(pt, [fix], [])}
    assert bedarfe["l0"].vorrang is True
    assert bedarfe["l0"].bis == date(2026, 11, 8)


def test_knappe_kapazitaet_meldet_klar_und_deutsch() -> None:
    """Reicht die Kapazitaet nicht, nennt die Meldung Wert, Termin und Plaetze."""
    pt, dq = _vorlage(), _quelle()
    for regel in pt["regeln"]:
        if regel["baustein"] == "vorher_geuebt":
            regel["vorlauf_wochen"] = 1  # nur ein Sonntag im Fenster
    termine = _termine(pt, dq)
    fix = _fix(pt, dq, date(2026, 11, 8))
    v = generiere(pt, {}, termine, [fix], dq)
    meldungen = [x.meldung for x in v.verstoesse if "Uebungsplaetzen" in (x.meldung or "")]
    assert len(meldungen) == 1
    text = meldungen[0]
    assert text.startswith("Lied 00 am 08.11.: nur ")
    assert "von 2 Uebungsplaetzen frei vor dem Termin" in text
    assert "08.11.2026" in text and "2026-11-08" not in text


def test_auto_einsaetze_bleiben_best_effort_ohne_kapazitaetsmeldung() -> None:
    """Nur Vorrang-Bedarfe warnen kapazitaetsbezogen; Auto-Einsaetze nicht."""
    pt, dq = _vorlage(), _quelle()
    for regel in pt["regeln"]:
        if regel["baustein"] == "vorher_geuebt":
            regel["vorlauf_wochen"] = 1
    termine = _termine(pt, dq)
    v = generiere(pt, {}, termine, [], dq)
    assert not [x for x in v.verstoesse if "Uebungsplaetzen" in (x.meldung or "")]


def test_fixierter_programmauftritt_plant_uebungen_im_bezugsplan() -> None:
    """Planuebergreifend: fixierter Programm-Auftritt ist Uebungsbedarf im Chorplan."""
    from diakronos_app.planrahmen.engine.modell import Termin

    pt, dq = _vorlage(), _quelle()
    programm = ressourcen.kochbuch_laden("programm")
    auftritt = Termin(date(2026, 11, 8), "standard", ablauf={"ablauf": [{"id": "e1", "typ": "lied"}]})
    pv = generiere(programm, {}, [auftritt],
                   [Eintrag("ablauf/e1.lied", "l0", "eintrag", auftritt, fixiert=True, quelle="manuell")], dq)
    termine = _termine(pt, dq)
    v = generiere(pt, {}, termine, [], dq, bezugsplaene=[(programm, pv)])
    # Der fixierte fremde Auftritt zaehlt als Uebungsbedarf im eigenen Plan.
    uebungen = [e.termin.datum for e in v.eintraege
                if e.wert == "l0" and e.feld_pfad.startswith("einueben")]
    assert len([d for d in uebungen if d < date(2026, 11, 8)]) >= 2, uebungen
