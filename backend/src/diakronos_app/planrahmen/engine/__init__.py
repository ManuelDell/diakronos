"""Engine des Plan-Rahmens: reines Python auf In-Memory-Daten.

Ohne Datenbank, ohne Endpunkte (P8). Die Engine setzt den Plantyp in
konkrete Termine, Slots, Kandidaten und einen Vorschlag um: Termine
(``termine``), Feldbaum-Aufloesung (``struktur``), Rollen (``rollen``),
Regeln (``regeln``), Fuellstrategien und Generator (``fuellen``/``generator``),
Bedarfspruefung (``bedarf``), Trockenlauf (``trockenlauf``) und Uebernahme
(``uebernahme``).

Die einzige Abhaengigkeit zur Aussenwelt ist das :mod:`Datenquelle`-Protokoll
(``datenquelle``) — spaetere Ausbaustufen bauen den DB-Adapter darauf.
"""

from __future__ import annotations

from .bedarf import Bedarf, bedarfspruefung
from .datenquelle import (
    Abwesenheit,
    Anmeldung,
    Datenquelle,
    Gruppe,
    Historieneintrag,
    InMemoryDatenquelle,
    Kalendertermin,
    Person,
    Sammlungseintrag,
)
from .generator import generiere
from .modell import Bewertung, Eintrag, Slot, Termin, Verstoss, Vorschlag
from .termine import erzeuge_termine
from .trockenlauf import TrockenlaufErgebnis, trockenlauf
from .uebernahme import uebernimm

__all__ = [
    "Abwesenheit",
    "Anmeldung",
    "Bedarf",
    "Bewertung",
    "Datenquelle",
    "Eintrag",
    "Gruppe",
    "Historieneintrag",
    "InMemoryDatenquelle",
    "Kalendertermin",
    "Person",
    "Sammlungseintrag",
    "Slot",
    "Termin",
    "TrockenlaufErgebnis",
    "Verstoss",
    "Vorschlag",
    "bedarfspruefung",
    "erzeuge_termine",
    "generiere",
    "trockenlauf",
    "uebernimm",
]
