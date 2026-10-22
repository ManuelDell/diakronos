"""Feiertags-Ausnahmen gegen den Musikteam-Aushang Q4/2026 pruefen."""
from datetime import date

import pytest

from diakronos_app.planrahmen import ressourcen
from diakronos_app.planrahmen.engine import InMemoryDatenquelle, erzeuge_termine


def test_musikteam_proben_exakt_wie_aushang() -> None:
    """Aus einem Beispiel-Aushang uebernommene Daten (Musterhausen, Q4/2026)."""
    reihen = erzeuge_termine(ressourcen.kochbuch_laden("musikteams"), {},
                             InMemoryDatenquelle(), date(2026, 10, 1), date(2026, 12, 31))
    erwartet = [date(2026, 10, d) for d in (2, 9, 16, 23, 30)]
    erwartet += [date(2026, 11, d) for d in (6, 13, 20, 27)]
    erwartet += [date(2026, 12, d) for d in (4, 11, 18)]
    assert [t.datum for t in reihen["probe"]] == erwartet


@pytest.mark.parametrize("abgeleitet", [False, True])
def test_ausnahme_prueft_eigenes_datum_ohne_konfigurierte_feiertage(abgeleitet: bool) -> None:
    """Nicht deklarierte Festtage werden auch in eigenstaendigen Reihen entfernt."""
    termine = {"manuell": [{"datum": "2026-12-25"}], "ausnahmen": {"feiertage": True}}
    pt = {"termine": termine}
    if abgeleitet:
        pt = {"terminreihen": [
            {"id": "einsatz", "termine": {"manuell": [{"datum": "2026-12-27"}]}},
            {"id": "probe", "termine": {"abgeleitet": {"von": "einsatz", "versatz": "-2T"},
                                         "ausnahmen": {"feiertage": True}}},
        ]}
    reihen = erzeuge_termine(pt, {}, InMemoryDatenquelle())
    assert reihen["probe" if abgeleitet else "standard"] == []


@pytest.mark.parametrize("schluessel,datum,erntedank", [
    ("1_advent", "2026-11-29", "1. So im Oktober"),
    ("erntedank", "2026-09-13", "2. So im September"),
])
def test_anlass_am_ursprung_streicht_keinen_anderen_tag(schluessel: str, datum: str, erntedank: str) -> None:
    """Advent und regionaler Erntedank sind Anlaesse, keine Ausnahmetage."""
    pt = {"terminreihen": [
        {"id": "einsatz", "termine": {"manuell": [{"datum": datum}], "feiertage": [schluessel]}},
        {"id": "probe", "termine": {"abgeleitet": {"von": "einsatz", "versatz": "-2T"},
                                     "ausnahmen": {"feiertage": True}}},
    ]}
    reihen = erzeuge_termine(pt, {}, InMemoryDatenquelle(), date(2026, 1, 1), date(2026, 12, 31), erntedank=erntedank)
    assert len(reihen["probe"]) == 1
    pt = {"termine": {"manuell": [{"datum": datum}], "feiertage": [schluessel], "ausnahmen": {"feiertage": True}}}
    assert len(erzeuge_termine(pt, {}, InMemoryDatenquelle(), date(2026, 1, 1), date(2026, 12, 31), erntedank=erntedank)["standard"]) == 1
