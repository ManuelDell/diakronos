"""Regressionen fuer vorausschauende Uebungsbedarfe statt leerer optionaler Felder."""
from datetime import date, timedelta
from typing import Any

from diakronos_app.planrahmen import ressourcen
from diakronos_app.planrahmen.engine import generiere, trockenlauf
from diakronos_app.planrahmen.engine.datenquelle import Historieneintrag, InMemoryDatenquelle, Sammlungseintrag
from diakronos_app.planrahmen.engine.modell import Eintrag, Termin


def _vorlage() -> dict[str, Any]:
    """Genug Uebungsplaetze fuer drei neue Eintraege mit je zwei Uebungen."""
    pt = ressourcen.kochbuch_laden("chorplan")
    pt["felder"] = [pt["felder"][0], pt["felder"][1]]
    pt["felder"][0].pop("inhalt")
    pt["felder"][1]["anzahl"] = "0..6"
    pt["termine"] = {"regel": "FREQ=WEEKLY;BYDAY=SU"}
    pt["regeln"] = [r for r in pt["regeln"] if r["baustein"] in ("vorher_geuebt", "mindestabstand")]
    return pt


def _quelle() -> InMemoryDatenquelle:
    return InMemoryDatenquelle(sammlungen={"lieder": [Sammlungseintrag(f"l{i}", "lieder") for i in range(40)]})


def test_chorplan_12_wochen_bedarf_fuellt_optionale_uebungen() -> None:
    pt, dq = _vorlage(), _quelle()
    ergebnis = trockenlauf(pt, {}, dq, wochen=12, ab=date(2026, 9, 27))
    assert ergebnis.vorschlag is not None
    assert any(e.feld_pfad.startswith("einueben[") for e in ergebnis.vorschlag.eintraege)
    verstoesse = [v for v in ergebnis.verstoesse if v.baustein == "vorher_geuebt"]
    assert verstoesse
    assert all(v.termin is not None and v.termin.datum < date(2026, 10, 11) for v in verstoesse)


def test_knappe_kapazitaet_nicht_an_unerfuellbare_fristen_verschwenden() -> None:
    """Mit zwei Plaetzen sind nicht alle, aber mehrere Einsaetze vorbereitbar."""
    pt, dq = _vorlage(), _quelle()
    pt["felder"][1]["anzahl"] = "0..2"
    v = trockenlauf(pt, {}, dq, wochen=10, ab=date(2026, 9, 27)).vorschlag
    assert v is not None
    assert len([x for x in v.verstoesse if x.baustein == "vorher_geuebt"]) < 33


def test_muss_vorbereitung_wird_geplant_und_unmoegliche_einsaetze_bleiben_leer() -> None:
    """Harte Regeln erlauben vorbereitete Einsaetze, aber keine unvorbereiteten."""
    pt, dq = _vorlage(), _quelle()
    pt["regeln"][1]["stufe"] = "muss"
    v = trockenlauf(pt, {}, dq, wochen=12, ab=date(2026, 9, 27)).vorschlag
    assert v is not None
    assert any(e.wert is not None and e.feld_pfad.startswith("lieder[") for e in v.eintraege)
    assert not [x for x in v.verstoesse if x.baustein == "vorher_geuebt"]
    assert all(e.wert is None for e in v.eintraege if e.termin is not None and e.termin.datum < date(2026, 10, 11) and e.feld_pfad.startswith("lieder["))


def test_uebungswert_und_seine_vorbelegte_besetzung_entstehen_gemeinsam() -> None:
    """Keine leere Vorbelegung aus einem noch nicht geplanten Uebungswert."""
    pt, dq = _vorlage(), _quelle()
    pt["felder"][1]["anzahl"] = "1..6"
    pt["felder"][1]["inhalt"] = [{"id": "hinweis", "art": "text", "fuellen": "vorbelegen", "aus": "eintrag.notiz"}]
    for lied in dq.sammlungen["lieder"]:
        lied.merkmale["notiz"] = "Vorbereiten"
    v = trockenlauf(pt, {}, dq, wochen=12, ab=date(2026, 9, 27)).vorschlag
    assert v is not None
    uebungen = [e for e in v.eintraege if e.art == "eintrag" and e.wert is not None and e.feld_pfad.startswith("einueben")]
    assert uebungen
    for e in uebungen:
        assert any(k.termin is e.termin and k.feld_pfad == e.feld_pfad + ".hinweis" and k.wert == "Vorbereiten" for k in v.eintraege)


def test_pflichtuebungsfeld_ohne_einsatzbedarf_meldet_leeren_platz() -> None:
    """Verschobene Pflichtfelder duerfen nicht lautlos aus dem Plan verschwinden."""
    pt, dq = _vorlage(), _quelle()
    pt["felder"] = [pt["felder"][1]]
    pt["felder"][0]["anzahl"] = "1..2"
    pt["regeln"] = [{"baustein": "vorher_geuebt", "feld": "lieder", "uebungsfeld": "einueben", "mindestens": 2}]
    t = Termin(date(2026, 10, 4), "standard")
    v = generiere(pt, {}, [t], [], dq)
    assert len(v.eintraege) == 1
    assert v.eintraege[0].wert is None
    assert v.eintraege[0].meldung


def test_historie_und_fixierte_uebungen_bleiben_erhalten() -> None:
    pt, dq = _vorlage(), _quelle()
    dq.historie_liste = [Historieneintrag(date(2026, 9, d), "chorplan", "einueben[0]", f"l{i}")
                        for d in (13, 20) for i in range(40)]
    termine = [Termin(date(2026, 9, 27) + timedelta(weeks=i), "standard") for i in range(12)]
    fix = Eintrag("einueben[4]", "l0", "eintrag", termine[0], fixiert=True, quelle="manuell")
    v = generiere(pt, {}, termine, [fix], dq)
    assert fix in v.eintraege
    assert not [x for x in v.verstoesse if x.baustein == "vorher_geuebt"]
    assert len([e for e in v.eintraege if e.termin is termine[0] and e.feld_pfad == fix.feld_pfad]) == 1


def test_programmbedarf_wird_im_anderen_plan_rechtzeitig_geuebt() -> None:
    pt, dq = _vorlage(), _quelle()
    programm = ressourcen.kochbuch_laden("programm")
    t = Termin(date(2026, 11, 29), "standard", ablauf={"ablauf": [{"id": "e1", "typ": "lied"}]})
    programm_v = generiere(programm, {}, [t], [Eintrag("ablauf/e1.lied", "l39", "eintrag", t, fixiert=True)], dq)
    termine = [Termin(date(2026, 10, 18) + timedelta(weeks=i), "standard") for i in range(7)]
    # Kein lokaler Einsatz: nur der fremde Programmplan fordert die Uebungen.
    pt["felder"] = [pt["felder"][1]]
    pt["regeln"] = []
    v = generiere(pt, {}, termine, [], dq, bezugsplaene=[(programm, programm_v)])
    uebungen = {e.termin.datum for e in v.eintraege if e.wert == "l39"}
    assert len(uebungen) == 3
    assert min(uebungen) >= t.datum - timedelta(weeks=4)
    assert max(uebungen) < t.datum
    from diakronos_app.planrahmen.regeln.auswertung import pruefe_plan
    dq.historie_liste = [Historieneintrag(e.termin.datum, pt["id"], e.feld_pfad, e.wert)
                        for e in v.eintraege if e.termin is not None]
    assert not [x for x in pruefe_plan(programm, [t], programm_v.eintraege, dq) if x.baustein == "vorher_geuebt"]
    dq.historie_liste = []
    assert [(e.feld_pfad, e.wert, e.termin.datum) for e in v.eintraege] == [
        (e.feld_pfad, e.wert, e.termin.datum) for e in generiere(pt, {}, termine, [], dq, bezugsplaene=[(programm, programm_v)]).eintraege]


def test_vorlauf_manuell_und_anlass_begrenzen_uebungsplanung() -> None:
    pt, dq = _vorlage(), _quelle()
    pt["regeln"] = [{"baustein": "vorher_geuebt", "feld": "lieder", "uebungsfeld": "einueben", "mindestens": 2, "vorlauf_wochen": 2}]
    termine = [Termin(date(2026, 10, 4) + timedelta(weeks=i), "standard") for i in range(5)]
    termine[2].anlaesse = frozenset({"chorfrei"})
    fixes = [Eintrag(f"lieder[{i}]", "l39", "eintrag", termine[-1], fixiert=True) for i in range(3)]
    v = generiere(pt, {}, termine, fixes, dq)
    assert not any(e.feld_pfad.startswith("einueben") for e in v.eintraege if e.termin is termine[2])
    assert all(e.termin is not None and e.termin.datum >= date(2026, 10, 18) for e in v.eintraege if e.wert == "l39" and e.feld_pfad.startswith("einueben"))
    pt["felder"][1]["fuellen"] = "manuell"
    assert not any(e.feld_pfad.startswith("einueben") for e in generiere(pt, {}, termine, fixes, dq).eintraege)
