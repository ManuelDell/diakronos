"""Bewegliche Feiertags-Berechnung (Ostern, Advent, Erntedank ...).

Die *Deklaration* der Feiertage liegt in :mod:`diakronos_app.planrahmen.feiertage`;
hier steht die *Berechnung* der konkreten Daten fuer ein Jahr. Grundlage ist
die Osterformel (Computus, nach Meeus/Jones/Butcher): daraus leiten sich alle
beweglichen Feiertage ab, dazu die advents- und erntedankabhaengigen sowie die
festen Feiertage.

Der Schluessel eines Feiertags dient zugleich als Anlass-Kennung (Konzept B2:
Feiertag setzt einen Anlass gleichen Namens).
"""

from __future__ import annotations

from datetime import date, timedelta
import re

from ..feiertage import FEIERTAGE, Feiertag


def osterdatum(jahr: int) -> date:
    """Ostersonntag eines Jahres (Computus, anonyme Gregorianische Formel).

    Gilt fuer den Gregorianischen Kalender (ab 1583). Ergebnis ist der
    Ostersonntag als ``date``.
    """
    a = jahr % 19
    b = jahr // 100
    c = jahr % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    monat = (h + l - 7 * m + 114) // 31
    tag = ((h + l - 7 * m + 114) % 31) + 1
    return date(jahr, monat, tag)


# Versatz in Tagen relativ zum Ostersonntag.
_OSTER_VERSATZ: dict[str, int] = {
    "aschermittwoch": -46,
    "palmsonntag": -7,
    "gruendonnerstag": -3,
    "karfreitag": -2,
    "ostersonntag": 0,
    "ostermontag": 1,
    "himmelfahrt": 39,
    "pfingstsonntag": 49,
    "pfingstmontag": 50,
    "fronleichnam": 60,
}


def _advent_sonntag(jahr: int, welche: int) -> date:
    """Der 1./2./3./4. Advent ist der letzte Sonntag vor dem 24.12. (bzw.
    die Sonntage, die sich ab dem 4. Sonntag vor Weihnachten vorwaerts
    zaehlen)."""
    heiligabend = date(jahr, 12, 24)
    # Wochentag 6 = Sonntag (0 = Montag).
    letzter_sonntag_vor_heiligabend = heiligabend - timedelta(days=(heiligabend.weekday() + 1) % 7)
    # Der 4. Advent ist der letzte Sonntag vor dem 24.12.
    vierter_advent = letzter_sonntag_vor_heiligabend
    return vierter_advent + timedelta(weeks=welche - 4)


def _buss_und_bettag(jahr: int) -> date:
    """Buß- und Bettag: Mittwoch vor dem 23. November."""
    return date(jahr, 11, 22) - timedelta(days=(date(jahr, 11, 22).weekday() - 2) % 7)


def _erntedank_datum(jahr: int, konfiguration: str = "1. So im Oktober") -> date:
    """Regionaler Sonntag: '1. So im Oktober' (Default) oder z. B. September."""
    monate = ("Januar", "Februar", "Maerz", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember")
    muster = re.fullmatch(r"([1-4])\. So im (\w+)", konfiguration)
    if muster is None or muster[2] not in monate:
        raise ValueError("Erntedank braucht '1..4. So im <Monat>' (z. B. '1. So im Oktober').")
    erster = date(jahr, monate.index(muster[2]) + 1, 1)
    return erster + timedelta(days=(6 - erster.weekday()) % 7, weeks=int(muster[1]) - 1)


def feiertag_datum(schluessel: str, jahr: int, *, erntedank: str = "1. So im Oktober") -> date | None:
    """Das Datum eines benannten Feiertags in einem Jahr (oder None).

    Deckt alle Katalog-Eintraege aus ``feiertage.FEIERTAGE`` ab: osterbasiert,
    adventbasiert, feste Termine und der Sonderfall Erntedank.
    """
    deklar = next((f for f in FEIERTAGE if f.schluessel == schluessel), None)
    if deklar is None:
        return None

    if deklar.art == "oster":
        versatz = _OSTER_VERSATZ.get(schluessel)
        if versatz is None:
            return None
        return osterdatum(jahr) + timedelta(days=versatz)

    if deklar.art == "advent":
        if schluessel in ("1_advent", "2_advent", "3_advent", "4_advent"):
            nr = int(schluessel[0])
            return _advent_sonntag(jahr, nr)
        if schluessel == "buss_und_bettag":
            return _buss_und_bettag(jahr)
        return None

    if deklar.art == "erntedank":
        return _erntedank_datum(jahr, erntedank)

    # feste Termine
    fest = {
        "neujahr": date(jahr, 1, 1),
        "silvester": date(jahr, 12, 31),
        "heiligabend": date(jahr, 12, 24),
        "1_weihnachtstag": date(jahr, 12, 25),
        "2_weihnachtstag": date(jahr, 12, 26),
    }
    return fest.get(schluessel)


def feiertag_fuer_datum(d: date, *, erntedank: str = "1. So im Oktober") -> list[str]:
    """Alle Feiertags-Schluessel, die auf ein konkretes Datum fallen.

    Praktisch fuer die Zuordnung: ein Termin am 25.12. traegt den Anlass
    '1_weihnachtstag'. Liefert die Schluessel der Feiertage, die auf ``d``
    liegen (als Liste, meist leer oder ein Eintrag).
    """
    ergebnis = []
    for f in FEIERTAGE:
        if f.art == "oster":
            versatz = _OSTER_VERSATZ.get(f.schluessel)
            if versatz is not None and osterdatum(d.year) + timedelta(days=versatz) == d:
                ergebnis.append(f.schluessel)
        elif f.art == "advent":
            if f.schluessel in ("1_advent", "2_advent", "3_advent", "4_advent"):
                if _advent_sonntag(d.year, int(f.schluessel[0])) == d:
                    ergebnis.append(f.schluessel)
            elif f.schluessel == "buss_und_bettag" and _buss_und_bettag(d.year) == d:
                ergebnis.append(f.schluessel)
        elif f.art == "erntedank" and _erntedank_datum(d.year, erntedank) == d:
            ergebnis.append(f.schluessel)
        else:
            fest = {
                "neujahr": date(d.year, 1, 1),
                "silvester": date(d.year, 12, 31),
                "heiligabend": date(d.year, 12, 24),
                "1_weihnachtstag": date(d.year, 12, 25),
                "2_weihnachtstag": date(d.year, 12, 26),
            }
            if fest.get(f.schluessel) == d:
                ergebnis.append(f.schluessel)
    return ergebnis
