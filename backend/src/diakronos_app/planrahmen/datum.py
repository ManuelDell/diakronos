"""Zentrale deutsche Datums-/Zeitausgabe fuer sichtbare Texte (UX2/C7).

Die API-Datenfelder bleiben ISO (`YYYY-MM-DD`); nur **Meldungen und
Regeltexte** sollen deutsch lesbar sein. Damit keine ISO-Daten mehr in
sichtbaren Texten landen, wird hier *eine* Quelle benutzt:

- ``datum_de(d)``       -> ``04.10.2026``
- ``datum_de_lang(d)``  -> ``So., 04.10.2026``
- ``zeitraum_de(von,bis)`` -> ``01.10.2026 – 31.12.2026``

Bewusst ohne ``locale``/``strftime``-Abhaengigkeit zur Systemsprache:
die Wochentagskuerzel sind fest verdrahtet (wie in ``engine/termine``),
damit die Ausgabe unabhaengig vom Container-Locale stabil bleibt.
"""

from __future__ import annotations

from datetime import date, datetime

# Python: 0 = Montag ... 6 = Sonntag.
WOCHENTAG_KURZ = ("Mo.", "Di.", "Mi.", "Do.", "Fr.", "Sa.", "So.")


def _als_datum(wert: date | datetime | str | None) -> date | None:
    """Normalisiert date/datetime/ISO-String zu ``date``; sonst None."""
    if wert is None:
        return None
    if isinstance(wert, datetime):
        return wert.date()
    if isinstance(wert, date):
        return wert
    if isinstance(wert, str):
        try:
            return date.fromisoformat(wert.strip()[:10])
        except ValueError:
            return None
    return None


def datum_de(wert: date | datetime | str | None) -> str:
    """Deutsches Datum ``TT.MM.JJJJ``; unbekannt -> Originaltext."""
    d = _als_datum(wert)
    if d is None:
        return "" if wert is None else str(wert)
    return f"{d.day:02d}.{d.month:02d}.{d.year:04d}"


def datum_de_lang(wert: date | datetime | str | None) -> str:
    """Deutsches Datum mit Wochentag, z. B. ``So., 04.10.2026``."""
    d = _als_datum(wert)
    if d is None:
        return "" if wert is None else str(wert)
    return f"{WOCHENTAG_KURZ[d.weekday()]}, {datum_de(d)}"


def datum_kurz_de(wert: date | datetime | str | None) -> str:
    """Kurzes deutsches Datum ``TT.MM.`` (fuer kapazitaetsbezogene Meldungen)."""
    d = _als_datum(wert)
    if d is None:
        return "" if wert is None else str(wert)
    return f"{d.day:02d}.{d.month:02d}."


def zeitraum_de(von: date | datetime | str | None, bis: date | datetime | str | None) -> str:
    """Zeitraum in deutscher Schreibweise, z. B. ``01.10.2026 – 31.12.2026``."""
    return f"{datum_de(von)} – {datum_de(bis)}"
