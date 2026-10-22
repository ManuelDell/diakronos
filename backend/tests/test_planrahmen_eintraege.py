"""Tests fuer die Struktur-Pruefung von Plan-Instanzdaten (Eintraege).

Gegenstelle zur Plantyp-Pruefung: hier wird geprueft, dass die konkreten
Eintraege eines Plans (z. B. der Programmablauf des Adventssingens und des
Weihnachtsmarkts, als JSON-Fixtures unter `doku/instanzen/`) strukturell zu
ihrem Plantyp ('programm') passen — jeder Eintrag nennt einen aufloesbaren
`feld_pfad` und einen `wert` mit erkannter `art` (Konzept P2: Struktur und
Daten sind getrennt).
"""

from __future__ import annotations

from diakronos_app.planrahmen import ressourcen
from diakronos_app.planrahmen.eintraege import eintraege_pruefen, katalogwerte_pruefen


def _programm() -> dict:
    return ressourcen.kochbuch_laden("programm")


def test_zufalls_instanzen_passen_zum_plantyp() -> None:
    """Adventssingen und Weihnachtsmarkt passen strukturell zu 'programm'."""
    programm = _programm()
    for name in ("adventssingen", "weihnachtsmarkt"):
        instanz = ressourcen.instanz_laden(name)
        fehler = eintraege_pruefen(programm, instanz["eintraege"])
        assert fehler == [], f"{name}: {fehler}"
        # UXP-R23/W3: die Strukturpruefung kennt die 'werte'-Listen einer
        # 'auswahl' nicht — die Katalogtreue wird eigens geprueft.
        katalog = katalogwerte_pruefen(programm, instanz["eintraege"])
        assert katalog == [], f"{name}: {katalog}"


def test_instanz_nennt_plantyp() -> None:
    """Jede Instanz-Fixteur traegt 'plantyp': 'programm'."""
    for name in ressourcen.instanz_dateinamen():
        instanz = ressourcen.instanz_laden(name)
        assert instanz.get("plantyp") == "programm"


def test_unbekanntes_feld_wird_gemeldet() -> None:
    """Ein Eintrag mit unbekanntem Feld wird mit Index gemeldet."""
    programm = _programm()
    fehler = eintraege_pruefen(programm, [{"feld_pfad": "gibtsnicht", "wert": {"art": "text"}}])
    assert any("gibtsnicht" in f for f in fehler)


def test_falsche_wertart_wird_gemeldet() -> None:
    """Ein wert ohne erkannte 'art' wird gemeldet."""
    programm = _programm()
    fehler = eintraege_pruefen(programm, [{"feld_pfad": "ablauf/l1.lied", "wert": {"irgendwas": 1}}])
    assert any("art" in f for f in fehler)


def test_ablauf_element_innerfeld_aufloesbar() -> None:
    """'ablauf/<element_id>.<innerfeld>' wird ueber den Elementtyp aufgeloest."""
    programm = _programm()
    fehler = eintraege_pruefen(programm, [
        {"feld_pfad": "ablauf/l1.lied", "wert": {"art": "eintrag", "titel": "X"}},
        {"feld_pfad": "ablauf/s1.titel", "wert": {"art": "text", "text": "Szene"}},
    ])
    assert fehler == []


def test_ablauf_element_unbekanntes_innerfeld() -> None:
    """Ein nicht deklariertes Innerfeld eines Ablauf-Elements wird gemeldet."""
    programm = _programm()
    fehler = eintraege_pruefen(programm, [{"feld_pfad": "ablauf/l1.gibtsnicht", "wert": {"art": "text"}}])
    assert any("gibtsnicht" in f for f in fehler)


def test_eintraege_keine_liste() -> None:
    """Nicht-Listen-Eingabe wird sauber abgelehnt."""
    programm = _programm()
    fehler = eintraege_pruefen(programm, {"nicht": "liste"})  # type: ignore[arg-type]
    assert fehler


def _programm_katalog() -> dict:
    """Plantyp mit einer geschlossenen Auswahlliste in einer Gruppe (Negativtest).

    Der Pfad braucht einen Punkt (`<gruppe>.<feld>`) — nur so greift die
    Pfadaufloesung von `katalogwerte_pruefen`.
    """
    return {
        "schema": "diakronos/plantyp@1",
        "felder": [
            {"id": "gruppe1", "art": "gruppe", "inhalt": [
                {"id": "ensemble", "art": "auswahl", "werte": ["Maennerchor", "Floete"],
                 "anzeigenamen": {"Maennerchor": "Männerchor", "Floete": "Flöte"}},
            ]},
        ],
    }


def test_katalogwerte_pruefen_meldet_fremdwert() -> None:
    """P3-1c (KLEIN 2): ein Wert ausserhalb der geschlossenen Liste wird gemeldet.

    Vorher gab es nur den Positivfall (Instanzen passen). Hier der Negativfall:
    ein erfundener Wert UND die ANZEIGE-Schreibweise mit Umlaut muessen auffallen
    — die gespeicherte Kennung ist ASCII und bleibt die einzige gueltige Form.
    """
    plantyp = _programm_katalog()
    for falsch in ("Quatsch", "Männerchor"):
        fehler = katalogwerte_pruefen(plantyp, [
            {"feld_pfad": "gruppe1.ensemble", "wert": {"art": "auswahl", "ensemble": falsch}},
        ])
        assert fehler, f"Wert {falsch!r} wurde nicht gemeldet"
        assert any(falsch in f for f in fehler)


def test_katalogwerte_pruefen_akzeptiert_kennung() -> None:
    """P3-1c (KLEIN 2): die gespeicherte ASCII-Kennung bleibt gueltig."""
    plantyp = _programm_katalog()
    fehler = katalogwerte_pruefen(plantyp, [
        {"feld_pfad": "gruppe1.ensemble", "wert": {"art": "auswahl", "ensemble": "Maennerchor"}},
    ])
    assert fehler == [], f"Kennung wurde faelschlich gemeldet: {fehler}"


def test_katalogwerte_pruefen_ohne_katalog_ist_leer() -> None:
    """Ohne geschlossene Werteliste (freier Text) gibt es nichts zu pruefen."""
    plantyp = {"schema": "diakronos/plantyp@1", "felder": [
        {"id": "gruppe1", "art": "gruppe", "inhalt": [{"id": "titel", "art": "text"}]},
    ]}
    assert katalogwerte_pruefen(plantyp, [
        {"feld_pfad": "gruppe1.titel", "wert": {"art": "text", "titel": "egal"}},
    ]) == []
