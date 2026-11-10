"""ZEIT-3: „Heute“ und Anzeige-Zeitpunkte in der Zeitzone der Gemeinde.

Der Container laeuft in **UTC**. ``date.today()`` und ``datetime.now()`` liefern
deshalb zwischen 0 und 1-2 Uhr Ortszeit den **Vortag**: eine Einwilligung, die
um 00:30 in Berlin erteilt wird, traegt das Datum von gestern, ein Dienstplan
springt erst um 02:00 auf die neue Woche, „Erstellt: …“ zeigt eine Uhrzeit
zwei Stunden in der Vergangenheit.

Hier steht deshalb EINE Rechnung: der Kalendertag in ``CALENDAR_TIMEZONE``
(``settings.calendar_timezone``, Default ``Europe/Berlin``).

Abgrenzung — was hier NICHT hingehoert:

* **Technische Zeitstempel bleiben UTC** (``frappe_compat.api_helpers._now``:
  ``creation``/``modified``). Sie sind Vergleichsbasis fuer Fristen, Jobs und
  Protokolle und wuerden bei einer Umstellung rueckwirkend eine Stunde
  doppelt zaehlen. Angezeigt werden sie ueber :func:`zeit_text` —
  umgerechnet, ohne den gespeicherten Wert zu beruehren.
* **Wandzeiten von Terminen** (``Element.element_start`` & Co.) sind bereits
  Ortszeit ohne Zeitzone; sie werden hier NICHT verschoben.

Oeffentliche Schnittstelle:

``jetzt_gemeinde()``   — ``datetime`` mit Zeitzone (``tzinfo`` gesetzt)
``heute_gemeinde()``   — ``date`` = Kalendertag in der Gemeinde
``heute_iso()``        — ``"JJJJ-MM-TT"`` desselben Tages
``zeit_text(wert)``    — UTC-Zeitstempel -> ``"JJJJ-MM-TT HH:MM"`` Ortszeit
"""

from __future__ import annotations

import datetime as _dt
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

__all__ = [
    "zeitzone",
    "jetzt_gemeinde",
    "heute_gemeinde",
    "heute_iso",
    "jetzt_wanduhr",
    "zeit_text",
]


def zeitzone() -> ZoneInfo:
    """Die Zeitzone der Gemeinde — unbrauchbare Einstellung ergibt UTC.

    Nie eine Exception: eine kaputte Zeitzone darf keinen Endpunkt toeten
    (dieselbe Regel wie in ``anmeldung.registrierungslink.jetzt_gemeinde``).
    """
    from diakronos_app.settings import settings

    wert = str(getattr(settings, "calendar_timezone", "") or "UTC")
    try:
        return ZoneInfo(wert)
    except (ValueError, ZoneInfoNotFoundError):
        return ZoneInfo("UTC")


def jetzt_gemeinde() -> _dt.datetime:
    """Jetzt in der Zeitzone der Gemeinde (``datetime`` mit ``tzinfo``)."""
    return _dt.datetime.now(zeitzone())


def heute_gemeinde() -> _dt.date:
    """HEUTE als Kalendertag in der Zeitzone der Gemeinde.

    Die eine Stelle, an der „heute“ fuer fachliche Daten bestimmt wird —
    ``date.today()`` des Containers ist es NICHT (UTC-Vortag bis 1-2 Uhr).
    """
    return jetzt_gemeinde().date()


def jetzt_wanduhr() -> _dt.datetime:
    """Jetzt als Wandzeit der Gemeinde OHNE ``tzinfo``.

    Fuer Vergleiche gegen Termin-Wandzeiten (``Element.element_start``), die
    zeitzonenlos in Ortszeit gespeichert sind. Ein ``datetime`` mit ``tzinfo``
    wuerde von Postgres als ``timestamptz`` gebunden und gegen UTC verglichen.
    """
    return jetzt_gemeinde().replace(tzinfo=None)


def heute_iso() -> str:
    """``heute_gemeinde()`` als ``"JJJJ-MM-TT"`` (Frappe-``today()``-Form)."""
    return heute_gemeinde().isoformat()


def zeit_text(wert, *, mit_sekunden: bool = False) -> str | None:
    """Zeitstempel -> Text in Ortszeit (``"JJJJ-MM-TT HH:MM"``).

    Gedacht fuer ANZEIGE technischer Zeitstempel (``creation``, ``modified``,
    ``zeitpunkt``): der gespeicherte Wert bleibt UTC, die Ausgabe steht in der
    Zeitzone der Gemeinde. Reine Datumswerte (``date`` bzw. ``"JJJJ-MM-TT"``)
    bleiben unveraendert — sie tragen keine Uhrzeit und werden nicht
    verschoben.

    ``None``/leer ergibt ``None``. Unlesbare Texte kommen unveraendert
    zurueck (keine erfundene Uhrzeit).
    """
    if wert is None or wert == "":
        return None
    # Typen aus dem ECHTEN Modul (``datetime.datetime``/``datetime.date``):
    # ``_dt`` ist nur fuer ``now()`` austauschbar (Tests frieren die Uhr).
    if isinstance(wert, datetime):
        zeitpunkt = wert
    elif isinstance(wert, date):
        return wert.isoformat()
    else:
        text = str(wert).strip()
        if not text:
            return None
        # Reines Datum (`2026-11-09`) ist kein Zeitpunkt — nicht verschieben.
        if len(text) <= 10 and "T" not in text and ":" not in text:
            return text
        try:
            zeitpunkt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return text

    if zeitpunkt.tzinfo is None:
        # Zeitzonenlose Zeitstempel dieser Anwendung sind UTC (alle
        # technischen Werte kommen aus ``_now()``); Wandzeiten von Terminen
        # laufen NICHT durch diese Funktion.
        zeitpunkt = zeitpunkt.replace(tzinfo=_dt.timezone.utc)
    muster = "%Y-%m-%d %H:%M:%S" if mit_sekunden else "%Y-%m-%d %H:%M"
    return zeitpunkt.astimezone(zeitzone()).strftime(muster)
