"""UX1j — Positivliste der einstellbaren Gestaltungs-Tokens.

Die Werte (Standard, min, max, Skalen-Gruppe) sind NICHT frei erfunden: sie
stammen aus `frontend/src/diakonos/tokens.css` (Abschnitte „Form“ und „Raum“)
und aus der Konzept-Entscheidung Manuels vom 2026-11-03 (Abstandsskala
4·8·12·16·24·32·48·64 px, `--pad` 16 px, Karten ohne Rahmen).

`--karte-rahmen` ist die Ausnahme mit Standard `0`: das Konzept sagt „Karten
ohne Rahmen (getönte Fläche + sanfter Schatten)“, erlaubt aber einen Rahmen
als Abweichung. Der Standard ist damit die konzepttreue Null, und die
Einstellung ist der bewusste Ausnahmefall.

WAS HIER NICHT STEHT, IST NICHT EINSTELLBAR
-------------------------------------------
Klickflächen (`--control-h`, `--row-h`), Farben (jedes `--dk-*`, `--bg`,
`--primary`, Status-Töne), Schriften (Familie/Größe/Gewicht) und alles, was
nicht in `tokens.css` steht. Ein Wert außerhalb dieser Liste wird in
`pruefe_wert` verworfen — er kommt weder in die Tabelle noch ins CSS.

Die Prüfung sitzt SERVERSEITIG, nicht in der Oberfläche: die Oberfläche
spiegelt dieselben Grenzen für die Live-Prüfung beim Tippen (UX1k), aber was
durchkommt, entscheidet dieser Modul.

AUFSTEIGENDE SKALA
------------------
`--sp-1 .. --sp-8` bilden zusammen die Abstands-Skala und müssen aufsteigend
bleiben: `--sp-1 < --sp-2 < … < --sp-8`. Sonst verschiebt eine einzelne
Änderung die Ordnung der ganzen Oberfläche (Nähe soll Zusammengehörigkeit
bedeuten, Prinzip S3) — und niemand sieht dem Wert an, dass er größer ist als
der nächste. Geprüft wird die Skala als GANZES, auch beim Zurücksetzen eines
einzelnen Feldes (dann gilt der Standardwert für dieses Feld).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

__all__ = [
    "Token",
    "TOKENS",
    "TOKEN_NAMEN",
    "SKALA_GRUPPE",
    "SKALA_TOKEN",
    "pruefe_wert",
    "pruefe_skala",
    "standardwerte",
    "wert_oder_standard",
    "zahl_aus",
]

#: Name der Skalen-Gruppe (die Token, zwischen denen die Ordnung gilt).
SKALA_GRUPPE = "skala"

#: Die Token der Abstands-Skala in aufsteigender Reihenfolge.
SKALA_TOKEN = ("--sp-1", "--sp-2", "--sp-3", "--sp-4", "--sp-5", "--sp-6", "--sp-7", "--sp-8")


@dataclass(frozen=True)
class Token:
    """Ein einstellbares Maß: Name, Standard, Grenzen — alles in px.

    ``schritt`` ist die Schrittweite, die die Oberfläche beim Ziehen/Zählen
    anbietet; der Server prüft ihn bewusst NICHT (eine ganze Zahl im Bereich
    ist gültig, auch 13 px). Ein erzwungener Schritt wäre eine Gestaltungsregel
    und keine Sicherheit.
    """

    name: str
    standard: int
    minimum: int
    maximum: int
    gruppe: str = SKALA_GRUPPE
    schritt: int = 1

    @property
    def einheit(self) -> str:
        return "px"


#: DIE Liste. Reihenfolge = Anzeigereihenfolge in den Einstellungen.
TOKENS: tuple[Token, ...] = (
    # ── Abstandsskala (Konzept: 4·8·12·16·24·32·48·64 px) ────────────────
    Token("--sp-1", 4, 1, 32),
    Token("--sp-2", 8, 2, 40),
    Token("--sp-3", 12, 4, 48),
    Token("--sp-4", 16, 8, 64),
    Token("--sp-5", 24, 12, 80),
    Token("--sp-6", 32, 16, 96),
    Token("--sp-7", 48, 24, 128),
    Token("--sp-8", 64, 32, 160),
    # ── Abstände mit eigener Bedeutung ────────────────────────────────────
    # `--pad` ist der Innenabstand von Flächen/Formularfeldern (tokens.css: 14,
    # Konzept: 16 — 16 ist der Zielwert, 14 der Bestand vor der Umstellung).
    Token("--pad", 16, 4, 48),
    # Abstand ZWISCHEN Gruppen (Prinzip S3: deutlich größer als innerhalb).
    Token("--abstand-gruppe", 24, 8, 64),
    # Abstand INNERHALB einer Gruppe.
    Token("--abstand-innen", 8, 2, 32),
    # Innenabstand einer Karte.
    Token("--karte-innen", 16, 4, 48),
    # ── Rahmen ────────────────────────────────────────────────────────────
    # Standard 0 = konzepttreu „Karten ohne Rahmen“.
    Token("--karte-rahmen", 0, 0, 4, gruppe="rahmen"),
    Token("--rahmen-breite", 1, 0, 4, gruppe="rahmen"),
    # ── Radien (tokens.css „Form“) ────────────────────────────────────────
    Token("--radius-sm", 6, 0, 16, gruppe="radius"),
    Token("--radius", 8, 0, 24, gruppe="radius"),
    Token("--radius-lg", 12, 0, 32, gruppe="radius"),
)

#: Die Namen als Menge — die Grenze für alles, was gespeichert/geliefert wird.
TOKEN_NAMEN: frozenset[str] = frozenset(t.name for t in TOKENS)

#: Schnellzugriff je Name.
_JE_NAME: dict[str, Token] = {t.name: t for t in TOKENS}

#: Ein CSS-Wert, den wir selbst erzeugen: ganze Zahl + `px`. NUR diese Form
#: wird je in die Ausgabedatei geschrieben (CSS-Injection ausgeschlossen).
_WERT_MUSTER = re.compile(r"^(?P<zahl>\d{1,4})(?:px)?$")


def token_oder_none(name: object) -> Token | None:
    """Das `Token` zu einem Namen — `None`, wenn er nicht in der Liste steht."""
    return _JE_NAME.get(str(name or "").strip())


def standard_zu(name: object) -> int | None:
    """Der Standardwert eines Tokens — `None`, wenn der Name nicht in der Liste steht."""
    token = token_oder_none(name)
    return None if token is None else token.standard


def zahl_aus(wert: object) -> int | None:
    """Wert als ganze px-Zahl lesen — `None`, wenn er das nicht ist.

    Erlaubt sind ``16``, ``"16"`` und ``"16px"``. Alles andere (Kommazahl,
    negative Zahl, ``calc()``, ``var()``, ``url()``, Leerzeichen, Einheiten
    außer px) ist ungültig. Der Bereich wird hier NICHT geprüft — das macht
    `pruefe_wert` (es gibt Werte ohne Grenzen beim Zurücksetzen).
    """
    if isinstance(wert, bool):  # bool ist in Python eine Zahl — hier nie gewollt
        return None
    if isinstance(wert, int):
        return wert
    if isinstance(wert, float):
        # 16.0 ist ein ganzer px-Wert; 16.5 wäre ein halbes Pixel und damit
        # keine Größe, die die Skala kennt.
        return int(wert) if math.isfinite(wert) and wert.is_integer() else None
    text = str(wert if wert is not None else "").strip()
    treffer = _WERT_MUSTER.match(text)
    if not treffer:
        return None
    return int(treffer.group("zahl"))


def pruefe_wert(name: object, wert: object) -> int:
    """Einen Wert prüfen und als ganze Zahl zurückgeben — oder ablehnen.

    Wirft ``ValueError`` mit einer Meldung, die sagt, WAS falsch ist und WAS
    jetzt zu tun ist (Prinzip I4). Der Aufrufer (`api.py`) macht daraus die
    Frappe-Antwort 417.
    """
    token = token_oder_none(name)
    if token is None:
        raise ValueError("Dieses Maß lässt sich nicht einstellen.")
    zahl = zahl_aus(wert)
    if zahl is None:
        raise ValueError(
            f"{token.name}: Bitte eine ganze Zahl in Pixeln angeben "
            f"(erlaubt {token.minimum} bis {token.maximum})."
        )
    if zahl < token.minimum or zahl > token.maximum:
        raise ValueError(
            f"{token.name}: {zahl} px liegt außerhalb des erlaubten Bereichs "
            f"({token.minimum} bis {token.maximum} px)."
        )
    return zahl


def _skalen_werte(abweichungen: dict[str, int]) -> list[tuple[str, int]]:
    """Die Skala als ``[(name, wert)]`` — Abweichung, sonst Standard."""
    return [(n, abweichungen.get(n, _JE_NAME[n].standard)) for n in SKALA_TOKEN]


def pruefe_skala(abweichungen: dict[str, int]) -> None:
    """Die Abstands-Skala muss aufsteigend bleiben (streng, keine Gleichheit).

    ``abweichungen`` sind die Abweichungen, die NACH der Änderung gelten
    sollen; fehlende Token nehmen ihren Standardwert. Wirft ``ValueError``
    mit den zwei Namen, die die Ordnung brechen.
    """
    werte = _skalen_werte(abweichungen)
    for (name_a, wert_a), (name_b, wert_b) in zip(werte, werte[1:]):
        if wert_b > wert_a:
            continue
        raise ValueError(
            f"Die Abstände müssen aufsteigend bleiben: {name_a} ({wert_a} px) "
            f"muss kleiner sein als {name_b} ({wert_b} px). Bitte zuerst "
            f"{name_a} verkleinern oder {name_b} vergrößern."
        )


def standardwerte() -> dict[str, int]:
    """Alle Token mit ihrem Standardwert (die Grundlage von „Alles zurücksetzen“)."""
    return {t.name: t.standard for t in TOKENS}


def wert_oder_standard(abweichungen: dict[str, int]) -> dict[str, int]:
    """Die geltenden Werte: Abweichung, sonst Standard — für JEDES Token.

    Nur diese Form geht in das CSS: die Positivliste ist die Grenze, und ein
    Name, der nicht in ihr steht, kann hier nicht auftauchen (er kommt aus
    `TOKENS`, nicht aus der Datenbank).
    """
    return {t.name: int(abweichungen.get(t.name, t.standard)) for t in TOKENS}
