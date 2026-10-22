"""Datenquelle-Protokoll des Plan-Rahmens (Engine, P2/SCOPE P2).

Die Engine arbeitet auf In-Memory-Daten und greift NIE direkt auf die
Datenbank zu (Konzept P8: ohne KI lauffaehig, reines Python). Alles, was die
Engine braucht — Personen, Merkmale, Gruppen, Anmeldungen, Sammlungen,
Abwesenheiten, Historie, Kalendertermine — bezieht sie ueber ein Protokoll
``Datenquelle``. Fuer Tests gibt es :class:`InMemoryDatenquelle`; den echten
DB-Adapter baut eine spaetere Ausbaustufe (P4).

Die Datentypen hier sind bewusst leichtgewichtig (``dataclass``): die Engine
ist eine reine Rechen- und Auswahlschicht, keine Persistenzschicht.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, time
from typing import Any, Protocol, runtime_checkable


# --------------------------------------------------------------------------- #
# Datentypen (fachlich, Deutsch benannt wie im Konzept)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Person:
    """Eine Person (Traeger von Merkmalen, Mitglied von Gruppen)."""

    kennung: str
    name: str = ""
    vorname: str = ""
    nachname: str = ""
    kuerzel: str = ""
    email: str = ""
    # Merkmale: schluessel -> Wert. Art 'tag' True/False, 'auswahl' der
    # gewaehlte Wert, 'person' eine Personen-Kennung usw.
    merkmale: dict[str, Any] = field(default_factory=dict)
    # Gruppen, denen die Person angehoert (Kennungen).
    gruppen: frozenset[str] = frozenset()
    # AUSTRITT-b (B4): ausgetreten ODER ausgeschlossen. Eine solche Person ist
    # NIE Kandidat (Zuteilbarkeit) — sie bleibt nur als gekuerzter Name in der
    # Historie alter Plaene sichtbar (Anzeige). Das Merkmal haengt an der
    # Person und nicht an der Rolle des Aufrufers, damit die Engine fuer alle
    # dieselbe Kandidatenmenge sieht.
    ausgeschieden: bool = False

    def hat_merkmal(self, schluessel: str) -> Any:
        """Wert des Merkmals oder None/False wenn nicht gesetzt."""
        return self.merkmale.get(schluessel)

    def attribut(self, schluessel: str) -> Any:
        """Eingebautes Attribut (name/vorname/nachname/kuerzel/email)."""
        return getattr(self, schluessel, None)


@dataclass(frozen=True)
class Sammlungseintrag:
    """Ein Eintrag aus einer Sammlung (Lied, Bibelarbeit, Spiel, Raum ...)."""

    kennung: str
    sammlung: str
    titel: str = ""
    reihenfolge: int = 0
    # Merkmale dieser Sammlung (z. B. Lied -> 'dirigent', 'klavier', 'thema').
    merkmale: dict[str, Any] = field(default_factory=dict)
    # Eingebaute Attribute (lied: buch/nummer/seite/ccli/...; jede Sammlung:
    # titel/reihenfolge). Frei, damit Format-Vorlagen und Merkmale beide lesen.
    attribute: dict[str, Any] = field(default_factory=dict)

    def attribut(self, schluessel: str) -> Any:
        """Eingebautes oder freies Attribut; Merkmal zuerst, dann Attribut."""
        if schluessel in self.merkmale:
            return self.merkmale[schluessel]
        return self.attribute.get(schluessel)


@dataclass(frozen=True)
class Kalendertermin:
    """Ein Termin aus dem Kalender (Kronos); Quelle 'kalender' in B2."""

    kennung: str
    datum: date
    uhrzeit: time | None = None
    name: str = ""
    kategorie: str = ""
    gruppe: str = ""
    anlaesse: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Abwesenheit:
    """Eine Abwesenheit einer Person (Urlaub, Krankheit, abgemeldet)."""

    person: str
    von: date
    bis: date
    grund: str = ""


@dataclass(frozen=True)
class Historieneintrag:
    """Ein frueherer Eintrag (aus diesem oder einem frueheren Plan).

    Dient Regeln wie ``mindestabstand`` und ``vorher_geuebt`` sowie der
    Fairness-Fortsetzung von ``reihum`` ueber Plangrenzen hinweg.

    P1-14b: ``plan`` traegt die Kennung des Plans, aus dem der Eintrag stammt
    (aus den veroeffentlichten Staenden). Damit kann ``_daten`` EIGENEN Plan
    (beidseitig gueltig) und FREMDPLAN (nur vor dem eigenen Termin) an der
    Ursache unterscheiden — vorher geschah das nach PLANTYP, wodurch ein
    ueberlappender zweiter Plan derselben Vorlage mit seinen spaeteren
    Terminen faelschlich mitzaehlte.
    """

    datum: date
    plantyp: str
    feld_pfad: str
    wert: Any  # z. B. Personen-Kennung oder Sammlungseintrag-Kennung
    plan: str | None = None


@dataclass(frozen=True)
class Anmeldung:
    """Anmeldung einer Person zu einer Veranstaltung/Rolle."""

    person: str
    rolle: str  # z. B. 'mitarbeiter'
    veranstaltung: str = ""


@dataclass(frozen=True)
class Gruppe:
    """Eine Diakonos-Gruppe (z. B. ein Musikteam) mit ihren Mitgliedern."""

    kennung: str
    name: str = ""
    mitglieder: frozenset[str] = frozenset()
    obergruppe: str = ""
    pflicht_mitglieder: frozenset[str] | None = None


# --------------------------------------------------------------------------- #
# Protokoll
# --------------------------------------------------------------------------- #


@runtime_checkable
class Datenquelle(Protocol):
    """Alles, was die Engine an Stamm- und Historien-Daten braucht.

    Alle Methoden liefern In-Memory-Daten (Listen/abbildende Strukturen). Die
    Engine ruft ausschliesslich diese Methoden — nie die Datenbank direkt.
    """

    def personen(self) -> list[Person]: ...

    def gruppen(self) -> list[Gruppe]: ...

    def merkmal_werte(self, merkmal: str) -> dict[str, Any]:
        """Person-Kennung -> Merkmalswert (fuer Rollenfilter 'merkmal')."""
        ...

    def gruppen_mitglieder(self, gruppe: str) -> frozenset[str]: ...

    def anmeldungen(self, rolle: str, veranstaltung: str = "") -> frozenset[str]: ...

    def sammlung(self, schluessel: str) -> list[Sammlungseintrag]: ...

    def abwesenheiten(self, von: date, bis: date) -> list[Abwesenheit]: ...

    def historie(self, feld: str, bis_datum: date, plantyp: str | None = None) -> list[Historieneintrag]:
        """Fruehere Werte je Plantyp und normalisiertem Feldpfad; '*' liest alle
        Wertefelder (auch Ablauf-Elemente) fuer planuebergreifende Regeln."""
        ...

    def kalender_termine(self, filter: dict[str, Any]) -> list[Kalendertermin]: ...


# --------------------------------------------------------------------------- #
# InMemoryDatenquelle (fuer Tests und Trockenlauf ohne DB)
# --------------------------------------------------------------------------- #


@dataclass
class InMemoryDatenquelle:
    """Eine Datenquelle auf Basis von In-Memory-Listen (fuer Tests).

    Alle Listen sind frei befuellbar; die Standard-Zugriffe filtern bzw.
    bilden ab. Bewusst grosszuegig: was nicht konfiguriert ist, fehlt einfach
    (leer), damit jeder Test nur die Daten vorgibt, die er braucht.
    """

    personen_liste: list[Person] = field(default_factory=list)
    gruppen_liste: list[Gruppe] = field(default_factory=list)
    merkmale: dict[str, dict[str, Any]] = field(default_factory=dict)
    anmeldungen_liste: list[Anmeldung] = field(default_factory=list)
    sammlungen: dict[str, list[Sammlungseintrag]] = field(default_factory=dict)
    abwesenheiten_liste: list[Abwesenheit] = field(default_factory=list)
    historie_liste: list[Historieneintrag] = field(default_factory=list)
    kalender_liste: list[Kalendertermin] = field(default_factory=list)

    @classmethod
    def mit_personen(cls, kennungen: list[str]) -> "InMemoryDatenquelle":
        """Hilfe: eine Quelle mit einfachen Personen (name = Kennung)."""
        return cls(personen_liste=[Person(k, name=k) for k in kennungen])

    # -- Datenquelle-Schnittstelle ------------------------------------------- #

    def personen(self) -> list[Person]:
        return list(self.personen_liste)

    def gruppen(self) -> list[Gruppe]:
        return list(self.gruppen_liste)

    def merkmal_werte(self, merkmal: str) -> dict[str, Any]:
        """Person-Kennung -> Merkmalswert. Deckt sowohl die explizite
        ``merkmale``-Ablage als auch die ``merkmale``-Attribute der Personen ab."""
        werte = dict(self.merkmale.get(merkmal, {}))
        for p in self.personen_liste:
            if merkmal in p.merkmale:
                werte[p.kennung] = p.merkmale[merkmal]
        return werte

    def gruppen_mitglieder(self, gruppe: str) -> frozenset[str]:
        for g in self.gruppen_liste:
            if g.kennung == gruppe:
                return g.mitglieder
        return frozenset()

    def anmeldungen(self, rolle: str, veranstaltung: str = "") -> frozenset[str]:
        return frozenset(
            a.person
            for a in self.anmeldungen_liste
            if a.rolle == rolle and (not veranstaltung or a.veranstaltung == veranstaltung)
        )

    def sammlung(self, schluessel: str) -> list[Sammlungseintrag]:
        return list(self.sammlungen.get(schluessel, []))

    def abwesenheiten(self, von: date, bis: date) -> list[Abwesenheit]:
        return [
            a
            for a in self.abwesenheiten_liste
            if a.bis >= von and a.von <= bis
        ]

    def historie(self, feld: str, bis_datum: date, plantyp: str | None = None) -> list[Historieneintrag]:
        """Filtert Plantyp und Wertefeld; '*' liest alle Felder eines Plantyps."""
        from .pfade import passt_zu_feld

        return [h for h in self.historie_liste if h.datum <= bis_datum
                and (plantyp is None or h.plantyp == plantyp)
                and (feld == "*" or passt_zu_feld(h.feld_pfad, feld))]

    def kalender_termine(self, filter: dict[str, Any]) -> list[Kalendertermin]:
        result = list(self.kalender_liste)
        if filter.get("kategorie"):
            result = [t for t in result if t.kategorie == filter["kategorie"]]
        if filter.get("gruppe"):
            result = [t for t in result if t.gruppe == filter["gruppe"]]
        return result


# --------------------------------------------------------------------------- #
# kleine Helfer
# --------------------------------------------------------------------------- #


def datum_zwischen(d: date, von: date, bis: date) -> bool:
    """True, wenn ``d`` im geschlossenen Intervall [von, bis] liegt."""
    return von <= d <= bis
