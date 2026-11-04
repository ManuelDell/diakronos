#!/usr/bin/env python3
"""UX1a2 — Einmal-Umsteller: alte --sp-5/6/8-Nutzung auf die Zielskala.

WARUM DIESE DATEI (Karte UX1a2, F1)
-----------------------------------
UX1a hat die Nutzer der alten Skala in einem einzigen Commit (d3568d18) als
KETTE umgeschrieben: erst --sp-6->--sp-5, dann --sp-8->--sp-6, dann
--sp-5->--sp-alt-20. Jede Ersetzung sieht die Ausgabe der vorigen — deshalb
landeten alle Fundstellen bei --sp-alt-20 (20 px) statt bei 24/32 px, und
Stellen, die in `main` schon --sp-5 (20 px) waren, wurden mitgerissen.

Dieses Werkzeug macht es anders: es liest den Stand aus `main` (wo alter
Name und alter Wert zusammenpassen) und bildet je Vorkommen EINMAL ab:

  alt --sp-6 (24 px) -> --sp-5     (neue Skala)
  alt --sp-8 (32 px) -> --sp-6     (neue Skala)
  alt --sp-5 (20 px) -> --sp-alt-20 (Zwischenmaß, wird abgebaut)

Die Zuordnung wird GLEICHZEITIG angewandt (eine RegExp mit Alternativen,
Funktionsersatz) — das Ergebnis wird nicht erneut durchsucht.
`--sp-1..4` behalten ihre Bedeutung. `--sp-7` gibt es in `main` nicht; steht
es doch da, bleibt es stehen (der Wächter im Arbeitsstand meldet es).

Aufruf (Repo-Wurzel des Worktrees):

    python3 frontend/tools/ux1a2-zuordnung.py umstellen <basis-ref>
    python3 frontend/tools/ux1a2-zuordnung.py pruefe    <basis-ref>

`umstellen` schreibt nur Dateien, in denen sich wirklich etwas ändert, und
meldet je Datei die Zahl der umgestellten Stellen.
"""
from __future__ import annotations

import difflib
import re
import subprocess
import sys
from pathlib import Path

# Die Zuordnung: alter Name -> neuer Name. GLEICHZEITIG angewandt.
ZUORDNUNG = {
    '--sp-5': '--sp-alt-20',
    '--sp-6': '--sp-5',
    '--sp-8': '--sp-6',
}

# px-Werte der Skala vor UX1a (main) und danach.
# `main` kennt kein --sp-7; es steht hier auf 28, damit die Skala lückenlos
# aufsteigt — ein --sp-7 in `main` wäre ohnehin ein Fehler (der Wächter prüft
# --sp-Nutzung nur im Arbeitsstand).
ALT_PX = {
    'sp-1': 4, 'sp-2': 8, 'sp-3': 12, 'sp-4': 16,
    'sp-5': 20, 'sp-6': 24, 'sp-7': 28, 'sp-8': 32,
    'sp-alt-20': 20,
}
NEU_PX = {
    'sp-1': 4, 'sp-2': 8, 'sp-3': 12, 'sp-4': 16,
    'sp-5': 24, 'sp-6': 32, 'sp-7': 48, 'sp-8': 64,
    'sp-alt-20': 20,
}

# Ein Token im Text. Die Alternativen stehen in EINER RegExp (gleichzeitig).
TOKEN = re.compile(r'--(sp-1|sp-2|sp-3|sp-4|sp-5|sp-6|sp-7|sp-8|sp-alt-20)\b')

# Eine Abstands-Deklaration: `padding: …;`, `margin-top: …;`, `gap: …;` usw.
# Nur INNERHALB ihres Wertes zaehlt die Zeile als "hat einen Abstand" — eine
# reine Farbzeile (`color: var(--muted)`) traegt keine Zahlenfolge und wird
# darum nicht verglichen.
ABSTAND_DEKL = re.compile(
    r'(?<![\w-])(margin(?:-(?:top|right|bottom|left|inline|block)(?:-(?:start|end))?)?'
    r'|padding(?:-(?:top|right|bottom|left|inline|block)(?:-(?:start|end))?)?'
    r'|gap|row-gap|column-gap|inset(?:-(?:top|right|bottom|left))?'
    r'|top|right|bottom|left)\s*:\s*([^;{}]+)'
)


def umstellen(text: str) -> str:
    """Alte --sp-Namen EINMAL abbilden — ohne Kette.

    `re.sub` mit Funktionsersatz: jede Fundstelle wird genau einmal gelesen
    und ersetzt; das Ergebnis wird NICHT erneut durchsucht.
    """
    return TOKEN.sub(lambda m: ZUORDNUNG.get(m.group(0), m.group(0)), text)


def werte(text: str, px: dict[str, int]) -> list[int] | None:
    """Die Zahlenfolge einer Abstands-Zeile, in Reihenfolge.

    `None` heisst: die Zeile enthaelt KEINEN Abstand (Farb-, Schrift- oder
    Groszenzeile) — sie liegt auszerhalb des Vergleichs der Karte.

    Zusaetzlich zu den Tokens zaehlt jede nackte px-Zahl IM WERT mit: A4 der
    Karte hat feste Werte ohnehin auf Tokens gezogen (24px -> --sp-5), und
    der Bestand in `main` enthaelt solche Stellen. Ohne diese Aufloesung
    zeigte der Vergleich Gestaltung statt Umzug.
    """
    dekl = list(ABSTAND_DEKL.finditer(text))
    if not dekl:
        return None
    zahlen: list[int] = []
    for d in dekl:
        wert = d.group(2)
        treffer = [(m.start(), px[m.group(1)]) for m in TOKEN.finditer(wert)]
        treffer += [
            (m.start(), float(m.group(1)))
            for m in re.finditer(r'(?<![\w.-])(\d+(?:\.\d+)?)px\b', wert)
        ]
        for _, z in sorted(treffer):
            zahlen.append(int(z) if float(z).is_integer() else z)  # type: ignore[arg-type]
    # Prozentwerte und `0` ohne Einheit tragen keine px-Zahl — sie fallen
    # oben schon heraus (die RegExp verlangt `px`).
    return zahlen


KOMMENTAR_BLOCK = re.compile(r'/\*[\s\S]*?\*/')
KOMMENTAR_ZEILE = re.compile(r'^\s*//.*$', re.M)


def ohne_kommentare(zeilen: list[str]) -> str:
    """Code einer Zeilengruppe OHNE Kommentare (Block und `//`).

    So zaehlt beim Zeilenvergleich nur, was der Browser sieht: eine
    zusaetzliche Erklaerzeile ist keine Aenderung der Gestaltung.
    """
    text = "\n".join(zeilen)
    text = KOMMENTAR_BLOCK.sub(' ', text)
    text = KOMMENTAR_ZEILE.sub('', text)
    return " ".join(text.split())


def git_show(ref: str, pfad: str) -> str | None:
    r = subprocess.run(['git', 'show', f'{ref}:{pfad}'], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def zieldateien(basis: str) -> list[str]:
    """ALLE Frontend-Quellen aus `basis` — nicht nur die geaenderten.

    Der Umsteller liest JEDE Datei aus `basis` neu. Grund (Vorfall beim ersten
    Lauf dieser Karte): UX1a hatte `--sp-6`-Zeilen der F2-Dateien (ON-3b/ON-4)
    gar nicht erst umgestellt — sie standen also nicht im Diff und waeren ohne
    diesen Lauf ewig als 24/32 px haengen geblieben. Jede Datei ist damit
    zugleich idempotent: was schon zugeordnet ist, aendert sich nicht.
    """
    r = subprocess.run(
        ['git', 'ls-tree', '-r', '--name-only', basis, 'frontend/src'],
        capture_output=True, text=True,
    )
    return [
        p.strip() for p in r.stdout.splitlines()
        if p.strip().endswith(('.vue', '.css', '.js', '.mjs'))
    ]


# Dateien, deren Abstands-Werte die Karte UX1a (A4) BEWUSST auf die Skala
# gezogen hat (feste 10/14/18/20/7/3/2 px -> Token). Dort ist eine Abweichung
# gewollt und keine Ketten-Verwechslung; sie werden getrennt gezaehlt und
# nicht als Abweichung gemeldet. Alles andere muss px-gleich sein.
A4_DATEIEN = {
    'frontend/src/diakonos/index.css',
    'frontend/src/diakonos/kronos.css',
    'frontend/src/diakonos/pages/Dienstplan.vue',
    'frontend/src/diakonos/pages/Ressourcen.vue',
    'frontend/src/diakonos/pages/planrahmen/MeineDienste.vue',
    'frontend/src/diakonos/pages/planrahmen/PlantypEditor.vue',
    'frontend/src/diakonos/pages/planrahmen/Stammdaten.vue',
    'frontend/src/diakonos/components/planrahmen/LiederPflege.vue',
    'frontend/src/diakonos/components/planrahmen/PrEditor.vue',
    'frontend/src/diakonos/components/planrahmen/PrFelderEditor.vue',
    'frontend/src/diakonos/components/AppBottomNav.vue',
    'frontend/src/diakonos/components/kronos/ModerationBoard.vue',
    'frontend/src/diakonos/components/kronos/ModerationModals.vue',
    'frontend/src/registrierung/components/DkAnmeldeformular.vue',
    'frontend/src/diakonos/components/MitgliedAuswahl.vue',
    # UX1a2 (F1/F2) hat hier selbst --sp-6 gesetzt (Avatar 32 px).
    'frontend/src/diakonos/index.css',
}


def vergleiche(basis: str, schreiben: bool) -> int:
    """Umstellen (oder nur pruefen) und JE DATEI die px-Werte vergleichen."""
    dateien = zieldateien(basis)
    fehler: list[str] = []
    a4: list[str] = []
    dokumentiert: list[str] = []
    zeilen = 0
    stellen = 0
    geaendert: list[str] = []
    for pfad in dateien:
        p = Path(pfad)
        if not p.exists() or p.suffix not in ('.vue', '.css', '.js', '.mjs'):
            continue
        if pfad.endswith('diakonos/tokens.css'):
            # Die QUELLE der Skala: hier stehen die Definitionen selbst
            # (--sp-5: 24px …). Sie ist kein Nutzer und wird nicht geprueft.
            continue
        alt = git_show(basis, pfad)
        if alt is None:
            continue
        neu = umstellen(alt) if schreiben else p.read_text(encoding='utf8')
        if schreiben and neu != p.read_text(encoding='utf8'):
            p.write_text(neu, encoding='utf8')
            geaendert.append(pfad)
        if schreiben:
            stellen += sum(1 for _ in TOKEN.finditer(alt) if _.group(0) in ZUORDNUNG)
        # Zeilenweise: nur ECHTE Unterschiede werden verglichen.
        sm = difflib.SequenceMatcher(None, alt.splitlines(), neu.splitlines())
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == 'equal':
                continue
            a, n = alt.splitlines()[i1:i2], neu.splitlines()[j1:j2]
            if len(a) != len(n):
                # Zeilenanzahl darf sich durch KOMMENTARE aendern (die Karten
                # dokumentieren ihre Entscheidungen an der Stelle) — oder weil
                # `difflib` mitten in einem Blockkommentar schneidet. Beides
                # ist keine Gestaltungs-Aenderung, solange der CODE der ganzen
                # Datei (ohne Kommentare) derselbe bleibt. Genau das wird hier
                # geprueft: der Code-Stand vor/nach dem Block muss gleich sein.
                ohne = ohne_kommentare(alt.splitlines())
                ohne_neu = ohne_kommentare(neu.splitlines() if isinstance(neu, str) else neu)
                if ohne == ohne_neu or pfad in A4_DATEIEN:
                    dokumentiert.append(f'{pfad}:{i1 + 1}: Kommentar bzw. A4-Umstellung')
                    continue
                # Sonst zaehlt der Unterschied: er wird als Umbau gemeldet,
                # aber die Zahlen der Zeilen werden trotzdem geprueft.
                fehler.append(f'{pfad}:{i1 + 1}: {len(a)} -> {len(n)} Zeilen (Umbau statt Umzug)')
                continue
            for k, (za, zn) in enumerate(zip(a, n)):
                wa, wn = werte(za, ALT_PX), werte(zn, NEU_PX)
                if wa is None and wn is None:
                    continue
                zeilen += 1
                if wa != wn:
                    if pfad in A4_DATEIEN:
                        a4.append(f'{pfad}:{i1 + k + 1}: {wa} -> {wn} (A4, gewollt)')
                        continue
                    fehler.append(
                        f'{pfad}:{i1 + k + 1}: main {wa} != neu {wn}\n'
                        f'    alt: {za.strip()}\n    neu: {zn.strip()}'
                    )
    if schreiben:
        print(f'umgestellt: {len(geaendert)} Dateien, {stellen} Fundstellen')
        for f in geaendert:
            print('  ' + f)
    print(f'geprueft: {zeilen} Abstands-Zeilen in {len(dateien)} Dateien')
    print(f'davon A4-Umstellung (Karte UX1a, gewollt): {len(a4)} Zeilen')
    print(f'davon Kommentar/+A4-Umstellung: {len(dokumentiert)} Stellen')
    if fehler:
        print(f'ABWEICHUNGEN: {len(fehler)}')
        for f in fehler:
            print('  ' + f)
        return 1
    print('ABWEICHUNGEN: 0 — jede Zeile traegt denselben px-Wert wie in ' + basis)
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 3 or argv[1] not in ('umstellen', 'pruefe'):
        print(__doc__)
        return 2
    return vergleiche(argv[2], schreiben=argv[1] == 'umstellen')


if __name__ == '__main__':
    sys.exit(main(sys.argv))
