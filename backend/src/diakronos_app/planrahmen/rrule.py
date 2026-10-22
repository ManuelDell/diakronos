"""Gemeinsame RRULE-Fachpruefung (Plan-Rahmen P0-2b).

Diese Funktion ist die EINE Quelle fuer die zulaessige Wiederholungsregel.
Sie wird von zwei Stellen genutzt:

- ``planrahmen.pruefung`` — als FEHLER-Meldung im Editor/Speichern/Trockenlauf;
- ``planrahmen.engine.termine`` — als harte Grenze VOR der Iteration, damit
  eine unbegrenzte Regel (``INTERVAL=0``) die App nicht blockiert.

Die Auslagerung in ein eigenes Modul ist Absicht: ``pruefung`` und ``engine``
importieren sich gegenseitig (``pruefung -> regeln.auswertung ->
engine.datenquelle -> engine/__init__``), ein Import quer zwischen beiden
ergaebe einen Zyklus. Dieses Modul importiert nur ``re`` und ist damit frei
von Zyklen (Befund B1 der P0-2-Nachpruefung).
"""

from __future__ import annotations

import re

# RRULE zulaessige FREQ-Werte. Die Engine erzeugt Termine auf Tagesbasis —
# stuendliche, minuetliche oder sekundenweise Wiederholungen sind ohne Nutzen
# und rufen bei grossen Zeitraeumen eine praktisch unbegrenzte Anzahl Termine
# ab (BLD-R2: FREQ=SECONDLY blockierte die ganze App). Deshalb hier nur die
# vier groben Frequenzen.
FREQ = {"YEARLY", "MONTHLY", "WEEKLY", "DAILY"}

_RRULE_RE = re.compile(r"(?<![A-Z])FREQ\s*=")
# FREQ=<wert> — global (finditer), damit auch ein zweiter Treffer geprueft wird.
_RRULE_FREQ_RE = re.compile(r"(?:^|[;:\s])FREQ\s*=\s*([A-Za-z]+)", re.IGNORECASE | re.MULTILINE)
# INTERVAL=<wert> — Zahl muss >= 1 sein (INTERVAL=0 terminiert nie).
_RRULE_INTERVAL_RE = re.compile(r"(?:^|[;:\s])INTERVAL\s*=\s*([^;:\s]*)", re.IGNORECASE | re.MULTILINE)
# Eine Planrahmen-Regel ist genau EINE Zeile. Mehrzeiler, 'RRULE:'-Praefix und
# EXRULE/RDATE/EXDATE haben in der Engine nichts verloren (dateutil wuerde nur
# die erste Zeile auswerten), also klar ablehnen statt still falsch zu rechnen
# (Befund W1).
_RRULE_MEHRZEILIG_RE = re.compile(r"\r|\n")
_RRULE_VERBOTEN_RE = re.compile(r"(?:^|[;:\s])(?:RRULE|EXRULE|RDATE|EXDATE)\s*[:=]", re.IGNORECASE)
# Tages-Engine: stunden-/minuten-/sekundengenaue Expansion vervielfacht die
# Zahl der Termine je Tag, ohne dass die Planung sie braucht (Befund W3).
#
# BYSETPOS ist hier BEWUSST NICHT dabei (Nachtrag N1, P0-4b): es vervielfacht
# nichts, sondern WAEHLT aus der Menge der Treffer aus — 'letzter Sonntag im
# Monat' ist `FREQ=MONTHLY;BYDAY=SU;BYSETPOS=-1`, genau eine Zeile je Monat.
# Es mit BYHOUR gleichzusetzen war ein Fehler.
_RRULE_EXPANSION_RE = re.compile(r"(?:^|[;:\s])(BYHOUR|BYMINUTE|BYSECOND)\s*=", re.IGNORECASE)


def rrule_problem(regel: str) -> tuple[str, str, str] | None:
    """Fachliche Pruefung EINER Regel ohne Meldungs-/Pfad-Kontext.

    Liefert ``(code, meldung, hinweis)`` oder ``None``, wenn die Regel
    zulaessig ist. Geprueft werden ALLE Vorkommen (nicht nur das erste),
    Mehrzeiler, 'RRULE:'-Praefix, EXRULE/RDATE/EXDATE, die Frequenz (nur die
    vier groben), ein INTERVAL >= 1 sowie problematische Tages-Expansionen.
    """
    if _RRULE_MEHRZEILIG_RE.search(regel) or _RRULE_VERBOTEN_RE.search(regel):
        return (
            "rrule_mehrzeilig",
            f"Die Regel {regel!r} enthält mehr als eine Zeile bzw. eine RRULE/EXRULE/RDATE-Kennung. "
            "Der Planrahmen kennt genau EINE Regel je Terminreihe.",
            "Schreibe die Regel einzeilig und ohne 'RRULE:'-Präfix, z. B. 'FREQ=WEEKLY;BYDAY=SU'.",
        )

    freqs = [t.group(1).upper() for t in _RRULE_FREQ_RE.finditer(regel)]
    if not freqs:
        return (
            "rrule_unvollstaendig",
            f"Regel {regel!r} enthält kein 'FREQ=' und ist damit keine Wiederholung.",
            "Schreibe die Regel im RRULE-Format, z. B. 'FREQ=WEEKLY;BYDAY=SU'.",
        )
    for freq in freqs:
        if freq not in FREQ:
            return (
                "rrule_freq_zu_fein",
                f"Die Wiederholung {freq!r} ist feiner als täglich und wird hier nicht unterstützt.",
                "Erlaubt sind FREQ=DAILY, FREQ=WEEKLY, FREQ=MONTHLY und FREQ=YEARLY.",
            )

    interval_treffer = _RRULE_INTERVAL_RE.search(regel)
    if interval_treffer:
        roh = interval_treffer.group(1).strip()
        wert = int(roh) if roh.isdigit() else None
        if wert is None or wert < 1:
            return (
                "rrule_interval_ungueltig",
                f"Der Wiederholungs-Abstand INTERVAL={roh!r} ist ungültig — er muss eine ganze Zahl >= 1 sein.",
                "Lasse INTERVAL weg (= 1, jede Wiederholung) oder setze einen Wert >= 1, z. B. 'INTERVAL=2' für jede zweite.",
            )

    expansion = _RRULE_EXPANSION_RE.search(regel)
    if expansion:
        return (
            "rrule_expansion_zu_fein",
            f"Die Regel {regel!r} vervielfacht die Termine je Tag ({expansion.group(1).upper()}=). "
            "Der Planrahmen plant tagesgenau.",
            "Entferne BYHOUR/BYMINUTE/BYSECOND — die Uhrzeit einer Reihe steht in 'uhrzeit'. "
            "BYSETPOS dagegen ist erlaubt (z. B. 'letzter Sonntag im Monat').",
        )
    return None


def rrule_unvollstaendig(regel: str) -> bool:
    """True, wenn die Regel gar kein ``FREQ=`` enthaelt (Kurzform fuer Aufrufer)."""
    return not _RRULE_RE.search(regel)


__all__ = ["FREQ", "rrule_problem", "rrule_unvollstaendig"]
