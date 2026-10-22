"""Katalog der beweglichen Feiertage (Konzept B2, 'feiertage').

Eine zentrale Liste der benannten Feiertage, die der Plan-Rahmen kennt. Die
Berechnung der konkreten Daten (Oster-/Adventrechnung) kommt in der Engine
(`termine.py`); hier steht die *Deklaration* (Schluessel + deutscher
Anzeigename), auf die sich Pruefung und Dokumentation beziehen.

Ein Feiertag, der in `termine.feiertage` aufgefuehrt wird, setzt zugleich
einen Anlass gleichen Namens (z. B. 'karfreitag' -> Anlass 'karfreitag').
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Feiertag:
    """Deklaration eines beweglichen Feiertags."""

    schluessel: str
    name: str
    art: str  # "oster" (beweglich ueber Ostern) oder "advent"/"fest" etc.


# Bewgte Feiertage ueber das Osterdatum.
FEIERTAGE_OSTER: list[Feiertag] = [
    Feiertag("aschermittwoch", "Aschermittwoch", "oster"),
    Feiertag("palmsonntag", "Palmsonntag", "oster"),
    Feiertag("gruendonnerstag", "Gründonnerstag", "oster"),
    Feiertag("karfreitag", "Karfreitag", "oster"),
    Feiertag("ostersonntag", "Ostersonntag", "oster"),
    Feiertag("ostermontag", "Ostermontag", "oster"),
    Feiertag("himmelfahrt", "Christi Himmelfahrt", "oster"),
    Feiertag("pfingstsonntag", "Pfingstsonntag", "oster"),
    Feiertag("pfingstmontag", "Pfingstmontag", "oster"),
    Feiertag("fronleichnam", "Fronleichnam", "oster"),
]

# Feste bzw. adventabhaengige Feiertage.
FEIERTAGE_FEST: list[Feiertag] = [
    Feiertag("neujahr", "Neujahr", "fest"),
    Feiertag("silvester", "Silvester", "fest"),
    Feiertag("1_advent", "1. Advent", "advent"),
    Feiertag("2_advent", "2. Advent", "advent"),
    Feiertag("3_advent", "3. Advent", "advent"),
    Feiertag("4_advent", "4. Advent", "advent"),
    Feiertag("heiligabend", "Heiligabend", "fest"),
    Feiertag("1_weihnachtstag", "1. Weihnachtstag", "fest"),
    Feiertag("2_weihnachtstag", "2. Weihnachtstag", "fest"),
    Feiertag("buss_und_bettag", "Buß- und Bettag", "advent"),
    Feiertag("erntedank", "Erntedank", "erntedank"),
]

FEIERTAGE: list[Feiertag] = FEIERTAGE_OSTER + FEIERTAGE_FEST

FEIERTAGE_NA = {f.schluessel: f for f in FEIERTAGE}


def feiertage_katalog() -> set[str]:
    """Kennungen aller bekannten Feiertage (fuer Tippfehler-Vorschlaege)."""
    return set(FEIERTAGE_NA)


def hole_feiertag(schluessel: str) -> Feiertag:
    """Deklaration zu einer Feiertags-Kennung."""
    return FEIERTAGE_NA[schluessel]
