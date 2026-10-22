"""Gemeinsame Datentypen der Engine (Termin, Slot, Eintrag, Vorschlag, Verstoss).

Diese Strukturen entstehen und fliessen zwischen den Engine-Modulen
(``termine``, ``struktur``, ``fuellen``, ``generator``, ``regeln``, ``bedarf``,
``trockenlauf``). Sie sind reine In-Memory-Objekte — keine Persistenz (die
kommen in spaeteren Ausbaustufen als DB-Adapter bzw. API-Ausgabe dazu).

Benennung folgt dem Konzept: ``plantyp``, ``feld``, ``rolle``, ``merkmal``,
``sammlung``, ``regel``, ``fuellen``, ``stufe`` ``muss/sollte/hinweis``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Any

from .datenquelle import Person


# --------------------------------------------------------------------------- #
# Termin
# --------------------------------------------------------------------------- #


@dataclass(eq=False)
class Termin:
    """Ein Termin (eine Zeile der Zeitachse), Quellen kombiniert (B2).

    ``reihe`` ist die Kennung der Terminreihe ('standard' fuer die Kurzform),
    ``anlaesse`` die zugeordneten Anlass-Kennungen (Feiertag setzt einen Anlass
    gleichen Namens + Sammelanlass 'feiertag'), ``bezug`` der Ursprungstermin
    einer abgeleiteten Reihe (None bei eigenstaendigen Terminen).

    ``eq=False``: Termine werden ueber Identitaet verglichen (jeder Termin ist
    ein eigenstaendiges Objekt; ``index``/``positionsnr_im_monat`` werden nach
    dem Erzeugen befuellt und waeren als ``eq``-Grundlage instabil).
    """

    datum: date
    reihe: str
    uhrzeit: time | None = None
    name: str = ""
    anlaesse: frozenset[str] = frozenset()
    bezug: "Termin | None" = None
    # Kennung des Termins in seiner Reihe (ab 0/1? hier ab 0 gezählt, für
    # bestimmen lassen wir die Nummer dem Aufrufer; zur Sicherheit ab 1).
    index: int = 0
    # 'termin_nr{jede}' und 'termin_im_monat' brauchen die Position des
    # Termins in seiner Reihe (fortlaufend ab 1, und je Monat neu gezaehlt).
    quelle: str = ""
    positionsnr_im_monat: int = 1  # n-ter Termin der Reihe innerhalb des Monats
    position_von_hinten: int = 1
    ablauf: dict[str, list[dict[str, str]]] = field(default_factory=dict)
    # OP-EVENT-18: die je Termin gueltige Variante (z. B. 'sonne'/'regen');
    # leer = die erste deklarierte Variante gilt (bisheriges Verhalten).
    variante: str | None = None

    @property
    def anlass_liste(self) -> list[str]:
        return sorted(self.anlaesse)


# --------------------------------------------------------------------------- #
# Slot (struktur.py)
# --------------------------------------------------------------------------- #


@dataclass
class Slot:
    """Ein aufloesbarer Einzelplatz innerhalb eines Termins (flache Liste).

    ``feld_pfad`` ist stabil und eindeutig (Format dokumentiert im LEITFADEN):
    ``lieder[0].dirigent``, ``abend@regen#programm.leitung``,
    ``gottesdienst:team`` (Reihen-Praefix), ``ablauf/<element_id>.<feld>``.
    """

    feld_pfad: str
    art: str  # person/personen/eintrag/text/zahl/datum/auswahl/team/...
    feld: dict[str, Any]  # die Feld-Deklaration (fuer fuellen/rolle/...)
    anzahl: int = 1  # 1 bei person/eintrag/team, sonst 1; personen: n
    pflicht: bool = True
    bedingung: Any = None
    varianten: list[str] = field(default_factory=list)
    teile: list[str] = field(default_factory=list)
    # Bei person/personen/team: die Rolle (Filter oder @referenz).
    rolle: Any = None
    # Bei eintrag: die Sammlung (ggf. Parameterreferenz).
    sammlung: str | None = None
    # Bei eintrag: enthaelt das Sammlungselement Unterfelder? -> dieser Slot
    # steht fuer das Element selbst; Unterfelder sind eigene Slots.
    fuellen: str = "optimieren"
    aus: str | None = None  # vorbelegen-Referenz
    mitglieder: Any = None  # team-Filter (Teilmenge)
    teams: Any = None  # team-Quelle


# --------------------------------------------------------------------------- #
# Eintrag (gefuellter Wert eines Slots)
# --------------------------------------------------------------------------- #


@dataclass
class Eintrag:
    """Ein gefuellter Wert in einem Plan (Slot -> konkreter Wert).

    ``wert`` ist die Kennung einer Person/eines Teams/Sammlungseintrags oder
    ein Skalar (text/zahl/...). ``fixiert`` schuetzt vor Ueberschreiben (P6),
    ``quelle`` nennt die Herkunft (fuellstrategie/uebernommen/manuell).
    ``termin`` ist der Termin, zu dem der Eintrag gehoert (fuer Regeln wie
    mindestabstand, die den Zeitpunkt brauchen).
    """

    feld_pfad: str
    wert: Any
    art: str
    termin: "Termin | None" = None
    fixiert: bool = False
    quelle: str = ""
    meldung: str = ""


# --------------------------------------------------------------------------- #
# Vorschlag / Plan
# --------------------------------------------------------------------------- #


@dataclass
class Vorschlag:
    """Das Ergebnis einer Generierung: Eintraege + Verstoesse + Meldungen."""

    termine: list[Termin] = field(default_factory=list)
    eintraege: list[Eintrag] = field(default_factory=list)
    verstoesse: list["Verstoss"] = field(default_factory=list)
    meldungen: list[str] = field(default_factory=list)
    bedarf: Any = None  # Ergebnis der Bedarfspruefung (bedarf.py)

    def eintrag_zu(self, feld_pfad: str) -> Eintrag | None:
        for e in self.eintraege:
            if e.feld_pfad == feld_pfad:
                return e
        return None


# --------------------------------------------------------------------------- #
# Verstoss (regeln.pruefe_plan)
# --------------------------------------------------------------------------- #


@dataclass
class Verstoss:
    """Ein Regelverstoss mit verstaendlicher Meldung (P7)."""

    stufe: str  # 'muss'/'sollte'/'hinweis'
    baustein: str
    feld_pfad: str
    meldung: str
    termin: Termin | None = None


# --------------------------------------------------------------------------- #
# Bewertungs-Ergebnis (regeln.bewerte)
# --------------------------------------------------------------------------- #


@dataclass
class Bewertung:
    """Ergebnis von ``bewerte``: zulaessig (muss), strafe (sollte), meldungen."""

    zulaessig: bool = True
    strafe: float = 0.0
    meldungen: list[str] = field(default_factory=list)
