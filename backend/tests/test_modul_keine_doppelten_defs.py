"""Wächter: kein Modul definiert denselben Top-Level-Namen zweimal.

Anlass CHAT-PERF-1-2: ``api/chat.py`` trug einen Block von 2821 Zeilen
ZWEIMAL (79 Namen doppelt, u. a. ``_umfrage_form``, ``_darf_moderieren``,
``_kopfdaten_sammeln``). Python nimmt still die ZULETZT definierte Fassung —
die Tests waren grün, obwohl eine der beiden Kopien toter, abweichender Code
war, und jeder Merge auf dieser Stelle brach.

Der Test parst per ``ast`` ALLE Dateien unter ``backend/src/diakronos_app/``
und schlägt fehl, sobald ein Modul denselben Namen (``def``/``async def``/
``class``) auf Modulebene mehrfach definiert. Gemeint ist nur die
Modul-Ebene: gleichnamige Methoden in verschiedenen Klassen und Namens-
Wiederverwendung in inneren Funktionen sind kein Fehler.

Bekannte Ausnahmen: keine. Wird der Test auf einem anderen Modul rot, ist
DAS ein Befund (nicht dieser Test) — der Eintrag gehört dann mit
Begründung in ``BEKANNT``, die Reparatur in eine eigene Karte.
"""

from __future__ import annotations

import ast
from pathlib import Path

QUELLE = Path(__file__).resolve().parents[1] / "src" / "diakronos_app"

#: ``{pfad relativ zu src/: {name: begruendung}}`` — leer: alles muss sauber sein.
BEKANNT: dict[str, dict[str, str]] = {}


def _doppelte(datei: Path) -> list[tuple[str, list[int]]]:
    baum = ast.parse(datei.read_text(encoding="utf-8"), filename=str(datei))
    zeilen: dict[str, list[int]] = {}
    for knoten in baum.body:
        if isinstance(knoten, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            zeilen.setdefault(knoten.name, []).append(knoten.lineno)
    return [(name, nr) for name, nr in zeilen.items() if len(nr) > 1]


def test_kein_modul_definiert_einen_namen_zweimal() -> None:
    assert QUELLE.is_dir(), f"Quellbaum fehlt: {QUELLE}"
    module = sorted(QUELLE.rglob("*.py"))
    assert module, f"keine Module unter {QUELLE} gefunden"
    befunde: list[str] = []
    for datei in module:
        relativ = datei.relative_to(QUELLE).as_posix()
        ausnahmen = BEKANNT.get(relativ, {})
        for name, nr in _doppelte(datei):
            if name in ausnahmen:
                continue
            befunde.append(f"{relativ}:{name} — definiert in Zeilen {nr}")
    assert not befunde, (
        "Top-Level-Name mehrfach definiert (Python nimmt still die letzte "
        "Fassung; eine Kopie ist toter Code):\n  " + "\n  ".join(befunde)
    )
