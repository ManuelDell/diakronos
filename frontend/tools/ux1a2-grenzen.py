#!/usr/bin/env python3
"""Erzeugt die OBERGRENZE-Tabelle fuer frontend/tests/ux1a-abstand-tokens.test.mjs.

Einmal-Werkzeug der Karte UX1a2 (F5): nachdem der Waechter die Luecken
geschlossen hat, ist der Bestand groeszer geworden. Die eingefrorene Grenze
muss den NEUEN Stand abbilden (gezaehlt, nicht geschaetzt), sonst misst sie
gegen eine Welt, die es nicht mehr gibt.

Aufruf (aus dem Repo-Wurzelverzeichnis):

    python3 frontend/tools/ux1a2-grenzen.py            # gibt den Block aus
    python3 frontend/tools/ux1a2-grenzen.py --schreiben # schreibt ihn ins Test
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FRONTEND = REPO / 'frontend'
LISTE = FRONTEND / 'tools' / 'abstand-bestand.txt'
TEST = FRONTEND / 'tests' / 'ux1a-abstand-tokens.test.mjs'


def gelesen() -> list[tuple[str, int]]:
    werte = []
    for zeile in LISTE.read_text(encoding='utf8').splitlines():
        z = zeile.strip()
        if not z or z.startswith('#'):
            continue
        pfad, _, zahl = z.partition('\t')
        if pfad and zahl.strip().isdigit():
            werte.append((pfad.strip(), int(zahl.strip())))
    return werte


def block(werte: list[tuple[str, int]]) -> str:
    zeilen = [f"  '{p}': {n}," for p, n in werte]
    summe = sum(n for _, n in werte)
    return (
        'const OBERGRENZE = {\n'
        + '\n'.join(zeilen)
        + '\n  // UX1a2 (F5): Stand nach dem Schliessen der Waechter-Luecken.\n'
        + f'  // Gemessen am {len(werte)} Dateien / {summe} Fundstellen — gezaehlt von\n'
        + '  // frontend/tools/abstand-bestand.mjs, nicht geschaetzt.\n'
        + '}\n'
    )


def main(argv: list[str]) -> int:
    werte = gelesen()
    neu = block(werte)
    if '--schreiben' not in argv:
        sys.stdout.write(neu)
        return 0
    text = TEST.read_text(encoding='utf8')
    muster = re.compile(r'const OBERGRENZE = \{\n.*?\n\}\n', re.S)
    assert muster.search(text), 'OBERGRENZE-Block im Test nicht gefunden'
    TEST.write_text(muster.sub(lambda _m: neu, text, count=1), encoding='utf8')
    print(f'OBERGRENZE ersetzt: {len(werte)} Dateien, {sum(n for _, n in werte)} Fundstellen')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
