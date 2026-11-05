#!/usr/bin/env python3
"""UX2f — Umsteller: Objektbindung am Feldelement → `v-bind="feld.feldProps"`.

BEFUND (Abnahme im Wegwerf-Stack, UX2f): Wird das ganze Slot-Objekt an das
Eingabeelement gebunden (`v-bind="feld"` oder mit anderem Slot-Namen), landen
ALLE Felder als DOM-Attribute am Feld — auch das Objekt `feldProps`. Am
Eingabefeld stand dadurch `feldprops="[object Object]"` und
`ariadescribedby=` statt `aria-describedby`, `aria-invalid="false"` statt nur
bei Fehlern: die Prüfung war am Feld unsichtbar.

Richtig ist die Bindung des Feldsatzes: `v-bind="<slot>.feldProps"`.

Dieser Umsteller ändert NUR die Bindung am Eingabeelement; alle übrigen
Attribute bleiben unverändert.
"""
import re
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[3]
SRC = WURZEL / 'frontend/src'

# <input|select|textarea|DkEingabe|DkSelect … v-bind="X" …>  (X = Slot-Name)
MUSTER = re.compile(
    r'(?P<vor><(?:input|select|textarea|DkEingabe|DkSelect)\b[^>]*?)'
    r'v-bind="(?P<slot>[A-Za-z_$][\w$]*)"(?!\.)'
)

geaendert = []
for pfad in sorted(SRC.rglob('*.vue')):
    text = pfad.read_text(encoding='utf-8')
    if 'v-bind="' not in text:
        continue
    neu, n = MUSTER.subn(lambda m: f'{m.group("vor")}v-bind="{m.group("slot")}.feldProps"', text)
    if n:
        pfad.write_text(neu, encoding='utf-8')
        geaendert.append((pfad, n))

for pfad, n in geaendert:
    print(f'  {pfad.relative_to(WURZEL)}: {n}')
print('Dateien geändert:', len(geaendert))

# Restbestand: Bindung eines nackten Objekts an ein Feldelement, die NICHT
# auf .feldProps zeigt (z. B. `v-bind="attr"` mit eigenem Objekt) — melden.
rest = []
for pfad in sorted(SRC.rglob('*.vue')):
    for i, zeile in enumerate(pfad.read_text(encoding='utf-8').splitlines(), 1):
        if re.search(r'<(?:input|select|textarea|DkEingabe|DkSelect)\b[^>]*v-bind="[A-Za-z_$][\w$]*"', zeile):
            rest.append(f'{pfad.relative_to(WURZEL)}:{i}: {zeile.strip()}')
if rest:
    print('NICHT umgestellt (bitte prüfen):')
    for r in rest:
        print('  ' + r)
    sys.exit(1)
print('fertig')
