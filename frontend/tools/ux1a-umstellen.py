#!/usr/bin/env python3
"""UX1a — Einmal-Umsteller: feste Abstands-/Rahmen-/Radius-Werte auf Tokens.

Nimmt CSS-Deklarationen der abgedeckten Eigenschaften und ersetzt feste
px-Werte durch das passende Token. Beruehrt nur Werte, die sich eindeutig
abbilden lassen; alles andere bleibt stehen (der Waechter zaehlt es weiter,
die Liste schrumpft nur um das Umgestellte).

  margin/padding/gap/row-gap/column-gap  Zahl px -> var(--sp-N)  (Skala 4..64)
  top/right/bottom/left/inset            dito fuer Abstandswerte
  border-radius                          -> var(--radius-sm|--radius|--radius-lg)
  border-*-width / border(-seite)        -> 1px wird var(--rahmen-breite)
  border(-seite)-Farbwert                -> var(--rahmen-farbe)
"""
import re
import sys
from pathlib import Path

SKALA = {4: 1, 8: 2, 12: 3, 16: 4, 24: 5, 32: 6, 48: 7, 64: 8}

# Werte neben der Skala, die sich eindeutig auf die NAECHSTE Stufe abbilden
# lassen (Optik ~gleich, kein Layoutsprung). Jede Zeile ist eine Entscheidung
# der Karte UX1a und im Abschluss belegt:
#   6  -> 8   (Abstand; 6 lag zwischen 4 und 8, naechster Skalenwert ist 8)
#   10 -> 12  (Abstand; naechster Skalenwert ueber 10 ist 12)
#   14 -> 16  (Konzept --pad = 16)
#   20 -> 16  (altes --sp-5; die neue Skala kennt 20 nicht mehr)
#   2  -> 4   (winzige Abstaende auf die erste Stufe — nur fuer gap/margin/padding)
NAECHSTE = {6: 8, 10: 12, 14: 16, 20: 16, 2: 4, 3: 4, 5: 4, 7: 8, 9: 8, 11: 12, 13: 12, 18: 16, 22: 24, 28: 32, 40: 32, 60: 64}

ABSTAND = {
    'margin', 'padding', 'gap', 'row-gap', 'column-gap',
    'inset', 'top', 'right', 'bottom', 'left',
    'margin-top', 'margin-right', 'margin-bottom', 'margin-left',
    'margin-inline', 'margin-block', 'margin-inline-start', 'margin-inline-end',
    'margin-block-start', 'margin-block-end',
    'padding-top', 'padding-right', 'padding-bottom', 'padding-left',
    'padding-inline', 'padding-block', 'padding-inline-start', 'padding-inline-end',
    'padding-block-start', 'padding-block-end',
}
RADIUS = {
    'border-radius', 'border-top-left-radius', 'border-top-right-radius',
    'border-bottom-left-radius', 'border-bottom-right-radius',
}
RAHMEN_BREITE = {
    'border-width', 'border-top-width', 'border-right-width',
    'border-bottom-width', 'border-left-width',
}
RAHMEN_KURZ = {'border', 'border-top', 'border-right', 'border-bottom', 'border-left'}

# Farbnamen der Rahmen-Token, die NICHT ersetzt werden (schon Tokens).
EIGEN = re.compile(r'^[a-z-]+$')


def token_px(zahl: int) -> str | None:
    if zahl in SKALA:
        return f'var(--sp-{SKALA[zahl]})'
    if zahl in NAECHSTE:
        return f'var(--sp-{SKALA[NAECHSTE[zahl]]})'
    return None


def radius_token(zahl: int) -> str | None:
    if zahl <= 6:
        return 'var(--radius-sm)'
    if zahl <= 8:
        return 'var(--radius)'
    if zahl <= 14:
        return 'var(--radius-lg)'
    if zahl >= 999:
        return 'var(--badge-r)'
    return None


def ersetze_abstand(wert: str) -> str:
    """Jede nackte Zahl im Wert auf das Skalen-Token abbilden."""
    teile = wert.split()
    neu = []
    for teil in teile:
        m = re.fullmatch(r'(\d+)px', teil)
        if m and token_px(int(m.group(1))):
            neu.append(token_px(int(m.group(1))))
        else:
            neu.append(teil)
    return ' '.join(neu)


def ersetze_radius(wert: str) -> str:
    m = re.fullmatch(r'(\d+)px', wert.strip())
    if m and radius_token(int(m.group(1))):
        return radius_token(int(m.group(1)))
    return wert


def ersetze_rahmen_kurz(wert: str) -> str:
    """`1px solid var(--x)` -> Breite aus Token, Farbwert aus Token."""
    neu = re.sub(r'(?<![\w.-])1px(?![\w])', 'var(--rahmen-breite)', wert)
    # Nackte Farbwerte (hex/rgb/rgba/hsl) im Rahmen -> --rahmen-farbe.
    neu = re.sub(r'#[0-9a-fA-F]{3,8}\b', 'var(--rahmen-farbe)', neu)
    neu = re.sub(r'\brgba?\([^)]*\)', 'var(--rahmen-farbe)', neu)
    neu = re.sub(r'\bhsla?\([^)]*\)', 'var(--rahmen-farbe)', neu)
    return neu


DEKL = re.compile(r'(?<![\w-])([a-z-]+)\s*:\s*([^;{}]+)')
KOMMENTAR = re.compile(r'/\*[\s\S]*?\*/')
# JS/Markup, das wie eine CSS-Deklaration aussieht, aber keine ist:
# Objekt-Literal `{ top: 4 }`, Ternaer `? a : b`, Inline-Bindung `:style="…"`.
JS_SPUREN = re.compile(r'(=>|\?\s|:\s*[^;{}"\']*\?|\breturn\b|\btypeof\b|\bconst\b|\blet\b|\.\.\.)')


def css_bereich(text: str, pfad: str) -> tuple[str, str, str]:
    """Nur den `<style>`-Teil bearbeiten (Vue), sonst den ganzen Text.

    Im Vue-Template und im `<script>` steht JS; ein `top: 4` dort ist ein
    Objektfeld oder ein Ternaer, keine CSS-Deklaration. Der Umsteller hat
    dort einmal Code zerstoert — deshalb wird hier getrennt.
    """
    if not pfad.endswith('.vue'):
        return ('', text, '')
    treffer = list(re.finditer(r'<style[^>]*>|</style>', text))
    if not treffer:
        return ('', text, '')
    kopf = text[: treffer[0].end()]
    ende = text.rfind('</style>')
    if ende < 0:
        return ('', text, '')
    return (kopf, text[treffer[0].end():ende], text[ende:])


def umstellen(text: str) -> str:
    """Kommentare ausnehmen — ein `margin:0` im Kommentar ist kein CSS."""
    stelle = []

    def merke(m):
        stelle.append(m.group(0))
        return f'\x00{len(stelle) - 1}\x00'

    ohne = KOMMENTAR.sub(merke, text)

    def repl(m):
        name = m.group(1).lower()
        wert = m.group(2)
        gestrippt = wert.strip()
        if gestrippt.startswith('var(--') and ' ' not in gestrippt:
            return m.group(0)
        # JS-Spuren im Wert: das ist Code, keine Deklaration.
        if JS_SPUREN.search(gestrippt):
            return m.group(0)
        if name in ABSTAND:
            neu = ersetze_abstand(gestrippt)
        elif name in RADIUS:
            neu = ersetze_radius(gestrippt)
        elif name in RAHMEN_BREITE or name in RAHMEN_KURZ:
            neu = ersetze_rahmen_kurz(gestrippt)
        else:
            return m.group(0)
        return f'{m.group(1)}: {neu}'

    ohne = DEKL.sub(repl, ohne)
    return re.sub(r'\x00(\d+)\x00', lambda m: stelle[int(m.group(1))], ohne)


def umstellen_datei(text: str, pfad: str) -> str:
    kopf, css, rest = css_bereich(text, pfad)
    return kopf + umstellen(css) + rest


def main(pfade):
    for p in pfade:
        pfad = Path(p)
        alt = pfad.read_text(encoding='utf8')
        neu = umstellen_datei(alt, str(pfad))
        if neu != alt:
            pfad.write_text(neu, encoding='utf8')
            print('umgestellt:', pfad)


if __name__ == '__main__':
    main(sys.argv[1:])
