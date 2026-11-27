"""ASVS2-1: Sortierfelder in get_value/get_all sind nur echte Spalten.

Ein unbekannter oder nicht-spaltiger Name (Methode, Dunder-Attribut) ist ein
klarer KeyError — kein AttributeError (500) und keine Sortierung nach etwas,
das keine Spalte ist.
"""
from __future__ import annotations

import pytest

from diakronos_app.frappe_compat import query


@pytest.mark.parametrize("feld", ["gibt_es_nicht", "__class__", "metadata"])
def test_get_value_lehnt_unbekanntes_sortierfeld_ab(patched_db, feld) -> None:
    patched_db()
    with pytest.raises(KeyError):
        query.get_value("Mitglied", {}, "name", order_by=f"{feld} desc")


@pytest.mark.parametrize("feld", ["gibt_es_nicht", "__class__", "metadata"])
def test_get_all_lehnt_unbekanntes_sortierfeld_ab(patched_db, feld) -> None:
    patched_db()
    with pytest.raises(KeyError):
        query.get_all("Mitglied", fields=["name"], order_by=f"{feld} asc")


def test_echtes_sortierfeld_geht(patched_db) -> None:
    patched_db()
    assert query.get_value("Mitglied", {}, "name", order_by="name desc") is None
