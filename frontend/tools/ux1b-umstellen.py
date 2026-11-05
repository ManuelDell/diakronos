#!/usr/bin/env python3
"""UX1b (B1/B3) — feste Schriftgroessen und -gewichte auf die Tokens umstellen.

Einmal-Werkzeug der Karte UX1b, nach dem Muster von `ux1a-umstellen.py`.

WAS ES TUT
----------
In den genannten Dateien (Vorgabe: die Dateien mit den meisten Fundstellen,
`sortiert()` gibt sie aus) ersetzt es

  font-size: 13px            -> font-size: var(--fs-14)
  font-size: 11px            -> font-size: var(--fs-12)
  font-size: 0.82rem         -> font-size: var(--fs-14)   (13.1 px, naechste Stufe)
  font-size: 0.68rem         -> font-size: var(--fs-12)   (10.9 px -> kleinste Stufe)
  font-size: 22px            -> font-size: var(--fs-20)
  font-size: 48px            -> font-size: var(--fs-26)   (Sonderfall: Symbolgroesse
                                                           wird beim Aufruf NICHT
                                                           angefasst, s. u.)
  font-weight: 600|700|bold  -> font-weight: var(--fw-fett)
  font-weight: 500|550       -> font-weight: var(--fw-mittel)
  font-weight: 650           -> font-weight: var(--fw-fett)
  font-weight: 400           -> font-weight: var(--fw-normal)

ZUORDNUNG DER GROESSEN (naechste Stufe der fuenf 12/14/16/20/26)
  0–12.9 px  -> --fs-12
  13–14.9    -> --fs-14
  15–17.9    -> --fs-16
  18–23.9    -> --fs-20
  ab 24      -> --fs-26

NICHT umgestellt werden:
  * Werte, die schon ein Token sind (var(--…))
  * Symbolgroessen ab 32 px (Emoji-/Icon-Platzhalter, `font-size: 48px`) —
    sie sind keine Textgroesse und wuerden als Text unlesbar klein.
    Der Aufruf meldet sie als „uebersprungen“, damit nichts still verschwindet.
  * `font-weight: 800/900` (echte Sonderfaelle, im Bestand nicht vorhanden)

Aufruf (aus dem Repo-Wurzelverzeichnis):

    python3 frontend/tools/ux1b-umstellen.py --liste        # Dateien nach Anzahl
    python3 frontend/tools/ux1b-umstellen.py --anwenden DATEI [DATEI …]
"""
from __future__ import annotations

import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
SRC = REPO / 'frontend' / 'src'

STUFEN = [(12.9, '--fs-12'), (14.9, '--fs-14'), (17.9, '--fs-16'), (23.9, '--fs-20'), (1e9, '--fs-26')]
GEWICHTE = {'400': '--fw-normal', '500': '--fw-mittel', '550': '--fw-mittel',
            '600': '--fw-fett', '650': '--fw-fett', '700': '--fw-fett',
            'bold': '--fw-fett', 'bolder': '--fw-fett'}
SYMBOL_AB = 32.0

LAENGE = re.compile(r'(font-size\s*:\s*)(-?(?:\d+(?:\.\d+)?|\.\d+))(px|rem|em|pt)\b')
GEWICHT = re.compile(r'(font-weight\s*:\s*)([a-z]+|\d+(?:\.\d+)?)\b', re.I)


def stufe(px: float) -> str:
    for grenze, name in STUFEN:
        if px <= grenze:
            return name
    return '--fs-26'


def in_px(zahl: str, einheit: str) -> float:
    wert = float(zahl)
    return wert * 16 if einheit in ('rem', 'em') else wert * (4 / 3 if einheit == 'pt' else 1)


def umstellen(text: str) -> tuple[str, list[str]]:
    bericht: list[str] = []

    def groesse(m: re.Match[str]) -> str:
        px = in_px(m.group(2), m.group(3))
        if px >= SYMBOL_AB:
            bericht.append(f'uebersprungen (Symbolgroesse): {m.group(0).strip()}')
            return m.group(0)
        return f'{m.group(1)}var({stufe(px)})'

    def gewicht(m: re.Match[str]) -> str:
        wert = m.group(2).lower()
        name = GEWICHTE.get(wert)
        if not name:
            if wert not in ('var', 'inherit', 'initial', 'unset', 'revert', 'normal', 'lighter'):
                bericht.append(f'unbekanntes Gewicht: {m.group(0).strip()}')
            return m.group(0)
        return f'{m.group(1)}var({name})'

    neu = LAENGE.sub(groesse, text)
    neu = GEWICHT.sub(gewicht, neu)
    return neu, bericht


def aufruf_dateien() -> list[tuple[int, pathlib.Path]]:
    treffer = []
    for p in SRC.rglob('*'):
        if p.suffix not in ('.vue', '.css', '.mjs', '.js') or p.name == 'tokens.css':
            continue
        text = p.read_text(encoding='utf8')
        zahl = len(LAENGE.findall(text)) + len(GEWICHT.findall(text))
        if zahl:
            treffer.append((zahl, p))
    treffer.sort(reverse=True)
    return treffer


def main(argv: list[str]) -> int:
    if '--liste' in argv:
        for zahl, p in aufruf_dateien()[:20]:
            print(f'{zahl:4d}  {p.relative_to(REPO)}')
        return 0
    if '--anwenden' not in argv:
        print(__doc__)
        return 2
    for name in argv[argv.index('--anwenden') + 1:]:
        p = pathlib.Path(name) if pathlib.Path(name).is_absolute() else REPO / name
        alt = p.read_text(encoding='utf8')
        neu, bericht = umstellen(alt)
        if neu == alt:
            print(f'{name}: unveraendert')
            continue
        p.write_text(neu, encoding='utf8')
        rest = len(LAENGE.findall(neu)) + len(GEWICHT.findall(neu))
        print(f'{name}: umgestellt, {rest} Fundstelle(n) offen')
        for zeile in bericht:
            print(f'  {zeile}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
