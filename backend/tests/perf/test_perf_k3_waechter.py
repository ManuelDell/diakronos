"""PERF-K3 — Waechter: die Messwerkzeuge laufen NICHT in der normalen Suite.

Die Messung (`messung.py`, `fabrik.py`) braucht eine echte Postgres-Datenbank
und einen eigenen Wegwerf-Stack. Sie heisst deshalb NICHT `test_*` und wird
von pytest nicht eingesammelt. Dieser Test haelt das fest — damit niemand die
Dateien spaeter umbenennt und `make test` dadurch eine Datenbank anlegt oder
134 Mitglieder in die Testdatenbank schreibt.

Marker `perf`: per Default deselektiert (siehe pyproject.toml `addopts`).
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.perf

_PERF_DIR = Path(__file__).resolve().parent


def _dateien():
    return sorted(p for p in _PERF_DIR.glob("*.py") if p.name != Path(__file__).name)


def test_kein_messskript_wird_eingesammelt():
    """Keine Datei im Ordner heisst `test_*.py` (ausser diesem Waechter)."""
    eingesammelt = [p.name for p in _dateien() if p.name.startswith("test_")]
    assert eingesammelt == [], (
        f"Messwerkzeuge wuerden von pytest eingesammelt: {eingesammelt}. "
        "Messskripte heissen absichtlich nicht `test_*`."
    )


def test_messskripte_sind_vorhanden():
    """Beide Werkzeuge liegen da (Tippfehler im Namen faellt so auf)."""
    namen = {p.name for p in _dateien()}
    assert {"messung.py", "fabrik.py"} <= namen, f"fehlt: {namen}"


def test_fabrik_groessen_entsprechen_der_karte():
    """Die Vorgaben der Karte PERF-K3 stehen als Konstanten in der Fabrik."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("perfk3_fabrik", _PERF_DIR / "fabrik.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)  # type: ignore[union-attr]

    assert modul.GRUPPEN == 26
    assert modul.KALENDER == 14
    assert modul.MITGLIEDER == 134
    assert modul.TERMINE == 2000


def test_messung_zaehlt_ueber_before_cursor_execute():
    """Die Messung haengt am SQLAlchemy-Ereignis, nicht an einer Naeherung."""
    quelle = (_PERF_DIR / "messung.py").read_text(encoding="utf-8")
    assert "before_cursor_execute" in quelle
    assert "merkungsrahmen" in quelle, (
        "Ohne eigenen Merkungsrahmen je Messung waere die Abfragezahl geschont."
    )


@pytest.mark.skipif(
    os.environ.get("PERFK3_LAUF") != "1",
    reason="braucht den Wegwerf-Stack (perfk3) — nur mit PERFK3_LAUF=1",
)
def test_messung_gegen_echten_stack():
    """Optionaler Probelauf: nur im Wegwerf-Stack, nie in der normalen Suite.

    Bewusst ohne Zusicherungen an konkrete Zahlen: die Messung ist ein Bericht,
    kein Vertrag. Geprueft wird, dass sie ueberhaupt ein Ergebnis liefert.
    """
    pytest.importorskip("psycopg")
    from diakronos_app.db import engine

    if engine.dialect.name != "postgresql":
        pytest.skip("kein Postgres (Wegwerf-Stack nicht verbunden)")
