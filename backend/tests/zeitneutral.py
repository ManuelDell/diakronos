"""Zeitneutrale Namen fuer Testtermine (ZEIT-1).

Befund 09.11.: ``test_ux2b2_feedtes.py`` und ``test_ux2b2_lesepfade.py``
legten ihre Termine mit FESTEN Datumswerten an (``datetime(2026, 11, 8, …)``).
Die oeffentlichen Lesewege (iCal-Feed, Website-JSON, ``oeffentlich_daten``)
liefern aber nur ZUKUENFTIGES — ab dem 09.11.2026 lagen die Termine in der
Vergangenheit und die Dateien waren rot, ohne dass sich am Code etwas
geaendert haette. Das ist eine Zeitbombe, keine Regression.

Der Ausweg ist NICHT, die Uhr festzunageln (freezegun): das haette eine neue
Testabhaengigkeit gekostet und den Zeitbezug nur versteckt. Stattdessen
entstehen die Testtermine relativ zu HEUTE (in der Zeitzone der App). Der
Test sagt damit genau das, was er meint — "ein kommender Termin" —, und zwar
an jedem Kalendertag.

Der Tagesversatz wird aus dem Testnamen abgeleitet, nicht fortlaufend
vergeben: jeder Aufruf bekommt also denselben Versatz, unabhaengig davon, wie
oft und in welcher Reihenfolge die Tests laufen. Zwei Termine bleiben damit
immer in derselben relativen Lage zueinander (Vortag/Nachmittag usw.).
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime, time, timedelta

#: Kleinster Abstand in Tagen. 2 = uebermorgen: nie "heute frueh" (was je
#: nach Uhrzeit schon vorbei waere) und nie "morgen frueh" — ein Termin am
#: Folgetag um 10:00 waere ab 11:00 desselben Tages Vergangenheit, und ein
#: Testlauf kurz vor Mitternacht kippte in den naechsten Tag. Zwei Tage
#: Abstand halten jeden hier erzeugten Termin fuer mindestens einen Tag in
#: der Zukunft, zu jeder Uhrzeit.
MIN_TAGE = 2
#: Groesster Abstand. Bleibt innerhalb des Fensters, das die Lesewege
#: standardmaessig ausliefern (Website/iCal: kommende Wochen), siehe
#: ``website.oeffentlich_daten.termine``.
MAX_TAGE = 20


def _versatz(schluessel: str) -> int:
    """Stabiler Tagesversatz fuer einen Namen (MIN_TAGE..MAX_TAGE)."""
    roh = hashlib.sha256(schluessel.encode("utf-8")).digest()
    spanne = MAX_TAGE - MIN_TAGE + 1
    return MIN_TAGE + (roh[0] % spanne)


def heute() -> date:
    """Heute in der Zeitzone, die die App fuer oeffentliche Termine nutzt.

    Rueckgabewert kommt aus ``oeffentlich_daten._heute()`` — derselben Naht,
    die das Standardfenster der Lesewege benutzt. Damit bedeutet "Zukunft"
    hier und dort dasselbe, auch wenn ein Test die Uhr dort festnagelt.
    """
    from diakronos_app.website import oeffentlich_daten

    return oeffentlich_daten._heute()


def termin_tag(schluessel: str, plus_tage: int = 0) -> date:
    """Ein Tag in der Zukunft: ``heute + versatz(schluessel) + plus_tage``."""
    return heute() + timedelta(days=_versatz(schluessel) + plus_tage)


def termin(schluessel: str, stunde: int, minute: int = 0,
           plus_tage: int = 0, sekunde: int = 0) -> datetime:
    """Ein Terminbeginn/-ende in der Zukunft (naive Ortszeit wie die App)."""
    return datetime.combine(
        termin_tag(schluessel, plus_tage), time(stunde, minute, sekunde)
    )


def zeitfenster(schluessel: str, tage: int = 28) -> tuple[date, date]:
    """Ein zusammenhaengendes Fenster in der Zukunft (``tage`` Kalendertage).

    Fuer Zeitraeume (Planungsfenster, "von/bis"): Beginn erst ab
    ``MIN_TAGE`` (nie heute/morgen), Ende nie in der Vergangenheit. Der
    Beginn wird so weit nach vorn gelegt, dass das Fenster GANZ in die
    Spanne passt — die Laenge ist Teil der Aussage der Tests, die es
    benutzen.

    Grenze: laenger als ``MAX_TAGE`` geht nicht ohne den Beginn wieder in
    die Vergangenheit zu ziehen. Bei ``tage > MAX_TAGE`` beginnt das Fenster
    deshalb bei ``MIN_TAGE`` und laeuft entsprechend weiter ueber
    ``MAX_TAGE`` hinaus (die Laenge bleibt exakt ``tage``).
    """
    laenge = max(1, int(tage))
    beginn = heute() + timedelta(days=max(MIN_TAGE, MAX_TAGE - laenge))
    return beginn, beginn + timedelta(days=laenge)


__all__ = ["MAX_TAGE", "MIN_TAGE", "heute", "termin", "termin_tag", "zeitfenster"]
