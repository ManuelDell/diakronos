"""UX2 C7: sichtbare Meldungen/Regeltexte tragen deutsche Daten, kein ISO.

Die API-Datenfelder (`datum`, `uhrzeit`) bleiben ISO. Nur *Meldungen und
Regeltexte* werden deutsch ausgegeben. Dieser Test belegt beides: die zentrale
Formatierung und ein vollstaendiger Generatorlauf ohne ISO-Datum im sichtbaren
Text.
"""
import re
from datetime import date

from diakronos_app.planrahmen import ressourcen
from diakronos_app.planrahmen.datum import (datum_de, datum_de_lang, datum_kurz_de,
                                            zeitraum_de)
from diakronos_app.planrahmen.engine.datenquelle import InMemoryDatenquelle, Sammlungseintrag
from diakronos_app.planrahmen.engine.generator import generiere
from diakronos_app.planrahmen.engine.modell import Eintrag
from diakronos_app.planrahmen.engine.termine import erzeuge_termine

ISO = re.compile(r"\d{4}-\d{2}-\d{2}")


def test_zentrale_deutsche_datumsausgabe() -> None:
    d = date(2026, 10, 4)  # Sonntag
    assert datum_de(d) == "04.10.2026"
    assert datum_de_lang(d) == "So., 04.10.2026"
    assert datum_kurz_de(d) == "04.10."
    assert zeitraum_de(date(2026, 10, 1), date(2026, 12, 31)) == "01.10.2026 – 31.12.2026"
    # ISO-Strings werden akzeptiert (Datenfelder kommen so an).
    assert datum_de("2026-11-08") == "08.11.2026"
    assert datum_de_lang("2026-11-08") == "So., 08.11.2026"


def test_wochentagskuerzel_sind_deutsch() -> None:
    # 2026-10-04 Sonntag, 05 Montag, 06 Dienstag ...
    tage = [datum_de_lang(date(2026, 10, 4) + __import__("datetime").timedelta(days=i)).split(",")[0]
            for i in range(7)]
    assert tage == ["So.", "Mo.", "Di.", "Mi.", "Do.", "Fr.", "Sa."]


def test_generatorlauf_ohne_iso_datum_in_sichtbaren_texten() -> None:
    pt = ressourcen.kochbuch_laden("chorplan")
    pt["termine"] = {"regel": "FREQ=WEEKLY;BYDAY=SU"}
    # Knappe Kapazitaet + Fixierung erzwingt viele Meldungen (mindestabstand,
    # vorher_geuebt, Kapazitaet).
    for regel in pt["regeln"]:
        if regel["baustein"] == "vorher_geuebt":
            regel["vorlauf_wochen"] = 1
    dq = InMemoryDatenquelle(sammlungen={
        "lieder": [Sammlungseintrag(f"l{i}", "lieder", titel=f"Lied {i:02d}") for i in range(8)]})
    termine = erzeuge_termine(pt, {}, dq, von=date(2026, 10, 1), bis=date(2026, 12, 31))["standard"]
    ziel = next(t for t in termine if t.datum == date(2026, 11, 8))
    v = generiere(pt, {}, termine, [Eintrag("lieder[0]", "l0", "eintrag", ziel, True, "manuell")], dq)
    texte = [x.meldung for x in v.verstoesse if x.meldung] + list(v.meldungen)
    assert texte
    schlecht = [t for t in texte if ISO.search(t)]
    assert not schlecht, schlecht
    # Deutsche Meldung ist vorhanden und lesbar.
    assert any("Uebungsplaetzen" in t for t in texte)
    assert any("So.," in t or re.search(r"\d{2}\.\d{2}\.\d{4}", t) for t in texte)
