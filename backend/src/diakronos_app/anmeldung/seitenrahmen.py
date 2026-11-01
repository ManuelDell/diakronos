"""ON-0a — Seitenrahmen für server-seitig gerenderte Seiten (CSS aus einer Quelle).

WARUM ES DIESES MODUL GIBT
--------------------------
Anmeldung (`routen.py`), Passwort setzen (`passwortseite.py`) und die
Inline-Maske der SPA (`spa.py::render_login`) trugen ihre Farben, Schriften und
Radien als eigene Hex-/px-Werte. Das waren Duplikate der Tokens in
`frontend/src/diakonos/tokens.css` — vier Stellen, die auseinanderliefen, und
ein Dunkelmodus, den jede Seite selbst nachbaute.

Jetzt gilt: Werte kommen AUSSCHLIESSLICH aus `tokens.css`. Der Frontend-Build
legt die Token-Datei unter einem FESTEN Namen ab (siehe
`frontend/vite.config.mjs`), dieses Modul baut den `<head>`-Block dafür.

DIE ZWEI STYLESHEETS (Vertrag, ON-1 baut darauf)
-----------------------------------------------
  tokens.css   ->  {Präfix}/diakonos/assets/diakronos-tokens.css
  seiten.css   ->  {Präfix}/diakonos/assets/diakronos-seiten.css
                   (Quelle: frontend/src/ssot/seiten.css — Grundregeln für
                    Karte, Formularfelder, Knöpfe, Hinweis-/Fehlerboxen)

Reihenfolge: erst die Tokens, dann die Regeln, die sie benutzen.

PRÄFIX (WEB-5a)
---------------
Die Adressen werden mit `base_path.pfad()` gebaut — ohne Präfix sind sie
`/diakonos/assets/…`, mit `DIAKRONOS_BASE_PATH=/gemeinde` sind sie
`/gemeinde/diakonos/assets/…`. Kein fester Pfad in einer Vorlage.

CSP (SEC-4)
-----------
Beide Dateien liegen auf der EIGENEN Adresse; die App-Policy
(`sec_header.APP_CSP`) erlaubt `style-src 'self'` und `font-src 'self'`.
Es wird deshalb KEIN Inline-`<style>` mehr gebraucht — und entsprechend
kein `'unsafe-inline'` für Stile auf diesen Seiten.
"""

from __future__ import annotations

import hashlib
import html
from pathlib import Path

from diakronos_app import base_path

#: App-eigener Pfad der gebauten Dateien (der Betriebs-Präfix kommt davor).
ASSET_PFAD = "/diakonos/assets"

#: Stabile Dateinamen aus dem Frontend-Build (frontend/vite.config.mjs).
#: Die Namen stehen in `spa.py` — dort braucht sie die Cache-Regel
#: (`_asset_response` liefert sie mit `no-cache` statt `immutable`). Hier
#: werden sie nur ÜBERNOMMEN, damit es nicht zwei Wahrheiten gibt; der
#: Import steht lokal in den Funktionen, weil `spa.py` dieses Modul seinerseits
#: beim Rendern importiert (Ringbezug beim Modulstart vermeiden).
def _namen() -> tuple[str, str]:
    """(Token-Datei, Grund-Stylesheet) — die Namen aus `spa.py`."""
    from diakronos_app import spa

    return spa.SEITENRAHMEN_TOKENS, spa.SEITENRAHMEN_STIL


def tokens_url() -> str:
    """Adresse der ausgelieferten Token-Datei (präfixbewusst)."""
    tokens, _ = _namen()
    return base_path.pfad(f"{ASSET_PFAD}/{tokens}")


def seiten_url() -> str:
    """Adresse des gemeinsamen Grund-Stylesheets (präfixbewusst)."""
    _, seiten = _namen()
    return base_path.pfad(f"{ASSET_PFAD}/{seiten}")


def schrift_url(name: str) -> str:
    """Adresse einer Schriftdatei der Server-Seiten (präfixbewusst).

    ON-0b (F3): Der Frontend-Build legt die Schriften, die `tokens.css`
    einbindet, unter FESTEM Namen in `dist/schriften/` ab (`frontend/vite.config.mjs`).
    Hier wird nur die Adresse gebaut — VOR der Anmeldeschranke, weil der
    Catch-all echte Build-Dateien immer ausliefert (eine Anmeldung, die ihre
    eigene Schrift nicht laden darf, wäre keine Anmeldung).
    """
    from diakronos_app import spa

    return base_path.pfad(f"{ASSET_PFAD}/{spa.SEITENRAHMEN_SCHRIFTEN}/{name}")


def font_src() -> str:
    """Quellen-Angabe für CSP `font-src` (eigene Adresse, präfixbewusst).

    Der Präfix ist im Betrieb ein Pfad (`/gemeinde`) — als Quelle genügt
    `'self'`; die Funktion dokumentiert das an EINER Stelle, damit eine
    Server-Seite den Wert nicht selbst formulieren muss.
    """
    return "'self'"


def _etag(pfad: Path | None) -> str:
    """Kurzer Inhalts-Hash einer ausgelieferten Datei ("" wenn sie fehlt)."""
    if pfad is None or not pfad.is_file():
        return ""
    return hashlib.sha256(pfad.read_bytes()).hexdigest()[:12]


def versions_hash() -> str:
    """Der Cache-Busting-Wert für die zwei `<link>`-Tags.

    ON-0b (F7): Die Dateinamen sind FEST (`diakronos-tokens.css`), damit jede
    Server-Seite sie ohne Build-Hash nennen kann. Der Cache-Regel zuliebe
    (`no-cache` + ETag) reicht der Browser meist aus — manche Zwischenspeicher
    (Firewall, Proxy) beantworten aber auch `no-cache`-Anfragen ohne
    Rückfrage. `?v=<hash>` macht aus jeder Änderung eine neue Adresse.

    Der Hash deckt Tokens, Grundregeln UND die Schriften ab: eine geänderte
    Schrift ist genauso eine Änderung am Erscheinungsbild.
    """
    from diakronos_app import spa

    if spa.SPA_DIST is None:
        return ""
    h = hashlib.sha256()
    for datei in (spa.SPA_DIST / spa.SEITENRAHMEN_TOKENS, spa.SPA_DIST / spa.SEITENRAHMEN_STIL):
        h.update(_etag(datei).encode())
    schrift_ordner = spa.SPA_DIST / spa.SEITENRAHMEN_SCHRIFTEN
    for name in spa.SEITENRAHMEN_SCHRIFT_NAMEN:
        h.update(_etag(schrift_ordner / name).encode())
    return h.hexdigest()[:12]


def _mit_version(url: str) -> str:
    version = versions_hash()
    return f"{url}?v={version}" if version else url


def head_block() -> str:
    """Fertiger `<head>`-Block: die zwei `<link>`-Tags plus das Theme-Skript.

    Wird von JEDER server-gerenderten Seite eingefügt — so gibt es genau eine
    Stelle, an der die Adressen, die Reihenfolge und der Hell/Dunkel-Startwert
    festgelegt sind.

    WARUM DAS SKRIPT NÖTIG IST
    `tokens.css` kennt die dunklen Werte AUSSCHLIESSLICH unter
    `[data-theme="dark"]` — es gibt dort keinen `prefers-color-scheme`-Block
    (die SPA setzt das Merkmal selbst). Ohne diesen Schritt bliebe eine
    Server-Seite IMMER hell, auch auf einem dunkel eingestellten Gerät. Das
    war bei der Abnahme von ON-0a gemessen worden (die Fläche blieb die helle
    Grundfläche, auch bei dunkler Systemeinstellung).

    Die Regel ist EXAKT die der App und der öffentlichen SPA-Seiten
    (`frontend/src/diakonos/composables/oeffentliches-theme.mjs`, REG-1c):
    bewusste Wahl im Speicher `dk-theme` → sonst Systemeinstellung → sonst
    hell; spätere Wechsel der Systemeinstellung werden übernommen, solange
    keine Wahl gespeichert ist. Kein Umschalter: ein Besucher ohne Konto soll
    nichts einstellen müssen.

    Das Skript steht INLINE und ist damit von der CSP gedeckt
    (`script-src 'unsafe-inline'` in `sec_header.APP_CSP`); es schreibt kein
    Markup und liest keine Inhalte — nur die Theme-Wahl.
    """
    # ON-0b (F7): `?v=<Inhalts-Hash>` an beiden Adressen (Cache-Busting).
    tokens = html.escape(_mit_version(tokens_url()), quote=True)
    seiten = html.escape(_mit_version(seiten_url()), quote=True)
    return (
        f'    <meta name="color-scheme" content="light dark">\n'
        f'    <link rel="stylesheet" href="{tokens}">\n'
        f'    <link rel="stylesheet" href="{seiten}">\n'
        f"    <script>{THEME_SKRIPT}</script>"
    )


#: Theme-Startwert (REG-1c) — bewusst als Zeichenkette, damit derselbe Text in
#: jeder Vorlage landet und in `frontend/tests/on0a-css-ssot.test.mjs` prüfbar
#: ist. Kein Zugriff auf Nutzerinhalte; Fehler (gesperrter Speicher) werden
#: still übergangen, dann gilt die Systemeinstellung.
THEME_SKRIPT = (
    "(function(){"
    "var w='';"
    "try{w=localStorage.getItem('dk-theme')||''}catch(e){}"
    "var m=window.matchMedia&&window.matchMedia('(prefers-color-scheme: dark)');"
    "function s(){document.documentElement.setAttribute('data-theme',"
    "w==='dark'||w==='light'?w:(m&&m.matches?'dark':'light'))}"
    "s();"
    "if(!w&&m&&m.addEventListener){"
    "m.addEventListener('change',function(e){"
    "document.documentElement.setAttribute('data-theme',e.matches?'dark':'light')})}"
    "})();"
)
