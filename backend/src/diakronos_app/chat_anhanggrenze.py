"""CHAT-12c — die EINE Wahrheit über die Anhanggröße (Bytes) im Chat.

Manuel 21.11.: *„Lass die Anhanggröße in den Admineinstellungen einstellbar
sein.“* Konzept ``docs/konzepte/CHAT-KONZEPT.md`` S4 („10 MB je Datei“),
Entscheidung **F9** („ein Wert“ — dieselbe Zahl gilt später auch für
Gruppendateien) und Karte CHAT-12c.

Vorbild ist GENAU der Weg der Aufbewahrungsfristen (CHAT-8): die Einstellung
ist eine NULLBARE Integer-Spalte der bestehenden Gemeinde-Single
(``gemeinde_einstellungen.anhang_max_mb``, angelegt von
``alembic/versions/chat12c_anhang_groesse.py``), NULL heißt „noch nie
eingestellt“ und dann gilt der Standard (``ANHANG_MAX_MB_STANDARD``, 10 MB).

WARUM EIN EIGENES MODUL
-----------------------
Der Upload-Endpunkt (``api/chat.anhang_hochladen``), der Lese-Deckel
(``api/chat._anhang_herkunft``), die Verlauf-Kopfzeilen und die Prüfung selbst
müssen DIESELBE Zahl nennen. Eine zweite Ableitung wäre eine zweite Wahrheit:
hier stehen Prüfung, Lesen, Schreiben und die Umrechnung MB→Bytes an EINER
Stelle.

RECHTE stehen bewusst NICHT hier: die Rechtefrage beantwortet der Endpunkt
über den zentralen Rechte-Kern (``rechte.ist_admin``), genau wie bei den
Fristen. Diese Funktionen prüfen nur WERTE.
"""

from __future__ import annotations

import logging
from typing import Any

from diakronos_app.models.chat import (
    ANHANG_MAX_BYTES,
    ANHANG_MAX_MB_GRENZE,
    ANHANG_MAX_MB_STANDARD,
)

logger = logging.getLogger(__name__)

#: Feldname in der API (Einstellungen) und Spaltenname an der Gemeinde-Single.
FELD = "anhang_max_mb"
#: Feldname in der Antwort der Chat-Seite (``meine_gespraeche``) — in BYTES,
#: damit die Oberfläche nicht selbst umrechnen muss (dieselbe Zahl, die der
#: Server prüft).
FELD_BYTES = "anhang_max_bytes"

__all__ = [
    "ANHANG_MAX_BYTES",
    "ANHANG_MAX_MB_GRENZE",
    "ANHANG_MAX_MB_STANDARD",
    "AnhangGroesseFehler",
    "anhang_max_bytes",
    "anhang_max_mb",
    "holen_einstellungen",
    "setze_einstellungen",
]


class AnhangGroesseFehler(ValueError):
    """Ungültige Anhanggröße — der Text ist die Meldung für die Oberfläche."""


def _pruefe_mb(wert: Any, feld: str = "Anhanggröße") -> int:
    """Ganze Zahl von ``1`` bis ``ANHANG_MAX_MB_GRENZE`` MB.

    Buchstaben (``"abc"``), Kommazahlen (``"2,5"``) und Leerstrings sind keine
    ganze Zahl und werden abgewiesen; ``True``/``False`` ebenfalls (in Python
    sind sie ``int`` — als Einstellung wären sie Unsinn). ``0`` und ``51``
    liegen außerhalb.
    """
    if isinstance(wert, bool):
        raise AnhangGroesseFehler(f"{feld} muss eine ganze Zahl in MB sein.")
    try:
        zahl = int(str(wert).strip())
    except (TypeError, ValueError):
        raise AnhangGroesseFehler(f"{feld} muss eine ganze Zahl in MB sein.") from None
    # ``int("2.5")`` scheitert bereits — was hier ankommt, war eine ganze Zahl.
    if zahl < 1 or zahl > ANHANG_MAX_MB_GRENZE:
        raise AnhangGroesseFehler(
            f"{feld} muss zwischen 1 und {ANHANG_MAX_MB_GRENZE} MB liegen."
        )
    return zahl


def _gemeinde_zeile(session):
    """Die Gemeinde-Single über den BESTEHENDEN Weg (``api.gemeinde``).

    Kein zweites Anlegen — dieselbe Zeile, dieselbe Voreinstellung.
    """
    from diakronos_app.api.gemeinde import _gemeinde_zeile as bestehend

    return bestehend(session)


def mb_zu_bytes(mb: int) -> int:
    """MB → Bytes in der Schreibweise des Standards (``10 * 1024 * 1024``)."""
    return int(mb) * 1024 * 1024


def anhang_max_mb(session) -> int:
    """Die WIRKSAME Grenze in ganzen MB (Standard, wenn nichts eingestellt ist).

    Ein unbrauchbarer Wert in der Datenbank (z. B. von Hand gesetzt) darf den
    Upload nicht kippen und nicht „unbegrenzt“ bedeuten: es gilt der Standard
    — mit einer Warnung im Protokoll.

    Gelesen wird bei JEDEM Aufruf frisch: jede Aufrufstelle fragt höchstens
    einmal je Request (Upload, Lesedeckel, Antwort der Chat-Seite). Ein Merker
    (z. B. über ``rechte.kern``) wäre hier fremd — die Zahl ist eine
    Einstellung, keine Rechtefrage.
    """
    return _anhang_max_mb_roh(session)


def _anhang_max_mb_roh(session) -> int:
    """Der Wert aus der Gemeinde-Single — s. ``anhang_max_mb``.

    Gelesen wird die EINE Spalte als Skalar-Abfrage, NICHT die ganze Zeile über
    ``session.get``: die Zahl der Abfragen muss gleich bleiben, egal ob die
    Zeile zufällig schon in der Identity-Map des Aufrufs liegt (CHAT-PERF-1
    vergleicht zwei Messungen im selben Prozess). Fehlt die Zeile, gilt der
    Standard — ``api.gemeinde._gemeinde_zeile`` legt sie beim nächsten
    Einstellungs-Aufruf an.

    KEIN ``except Exception``: unter PostgreSQL ist die Transaktion nach einem
    gescheiterten SELECT abgebrochen — ein Fallback auf den Standard würde
    nicht helfen, sondern den späteren Commit scheitern lassen. Die Spalte
    kommt mit ``chat12c_anhang_groesse``; der Entrypoint migriert vorher.
    """
    from sqlalchemy import select

    from diakronos_app.models.gemeinde import (
        GEMEINDE_EINSTELLUNGEN_NAME,
        GemeindeEinstellungen,
    )

    wert = session.execute(
        select(GemeindeEinstellungen.anhang_max_mb).where(
            GemeindeEinstellungen.name == GEMEINDE_EINSTELLUNGEN_NAME)
    ).scalar_one_or_none()
    if wert is None:
        return ANHANG_MAX_MB_STANDARD
    try:
        return _pruefe_mb(wert)
    except AnhangGroesseFehler:
        logger.warning("Chat-Anhanggröße %s=%r unbrauchbar — Standard %s MB gilt.",
                       FELD, wert, ANHANG_MAX_MB_STANDARD)
        return ANHANG_MAX_MB_STANDARD


def anhang_max_bytes(session) -> int:
    """Die WIRKSAME Grenze in BYTES — die eine Quelle der Wahrheit.

    ALLE Stellen, die heute ``ANHANG_MAX_BYTES`` benutzen (Lesedeckel, Prüfung,
    Fehlermeldung, Antwort der Chat-Seite), nehmen ihre Zahl hier.
    """
    return mb_zu_bytes(anhang_max_mb(session))


def holen_einstellungen(session) -> dict[str, int]:
    """Die Einstellung als ``{"anhang_max_mb": …}`` — lesbar ohne Schreibrecht."""
    return {FELD: anhang_max_mb(session)}


def setze_einstellungen(session, *, mb: Any, benutzer: str | None = None,
                        jetzt=None) -> dict[str, int]:
    """Die Anhanggröße prüfen und schreiben (EINE Transaktion).

    Die RECHTE-Prüfung steht NICHT hier, sondern im Endpunkt
    (``api.chat.chat_einstellungen_speichern``) — über den zentralen Rechte-Kern,
    wie bei den Fristen. Geprüft wird hier nur der WERT.
    """
    geprueft = _pruefe_mb(mb)
    zeile = _gemeinde_zeile(session)
    setattr(zeile, FELD, geprueft)
    if jetzt is None:
        from diakronos_app.chat_aufbewahrung import jetzt_wanduhr as naht

        jetzt = naht()
    zeile.modified = jetzt
    zeile.modified_by = benutzer
    zeile.created_by = zeile.created_by or benutzer
    session.flush()
    return {FELD: geprueft}
