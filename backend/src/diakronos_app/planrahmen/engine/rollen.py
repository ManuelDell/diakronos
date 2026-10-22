"""Rollen-Filter-Auswertung: Kandidatenmenge aus Personen (B4).

Ein Rollen-Filter ist ein rekursiver Ausdruck ueber ``alle`` (UND), ``eine``
(ODER), ``nicht`` (Negation) und den Blaettern ``merkmal``, ``gruppe``,
``anmeldung``, ``person`` — gleiche Grammatik wie die Bedingungs-Knoten. Eine
Feld-Rolle ist entweder ein solcher Filter (Objekt) oder eine ``@``-Referenz
auf eine benannte Rolle (``@mitarbeiter``).

``kandidaten`` liefert die Personen-Liste der Rolle fuer einen Zeitpunkt (fuer
``abwesenheit_beachten`` wird daraus ggf. abwesende entfernt — das ist Aufgabe
der Regel, nicht des Filters).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from .datenquelle import Datenquelle, Person


def kandidaten(
    rolle: Any,
    datenquelle: Datenquelle,
    plantyp: dict[str, Any] | None = None,
    *,
    parameter: dict[str, Any] | None = None,
) -> list[Person]:
    """Alle Personen, auf die eine Rolle/Feld-Rolle zutrifft.

    ``rolle`` ist entweder ein Filter-Objekt oder eine ``@``-Referenz; bei
    einer Referenz wird die benannte Rolle aus ``plantyp['rollen']`` aufgeloest.
    Ohne Rolle (None) -> alle Personen (gutmuetig).
    """
    if rolle is None:
        return datenquelle.personen()

    if isinstance(rolle, str):
        if rolle.startswith("@"):
            return _benannte_rolle(rolle[1:], datenquelle, plantyp, parameter)
        # Ein schlichter String ist keine gueltige Rolle -> leer.
        return []

    if not isinstance(rolle, dict):
        return []

    return _filter_anwenden(rolle, datenquelle, plantyp, parameter)


def _benannte_rolle(
    kennung: str,
    datenquelle: Datenquelle,
    plantyp: dict[str, Any] | None,
    parameter: dict[str, Any] | None,
) -> list[Person]:
    if not isinstance(plantyp, dict):
        return []
    for r in plantyp.get("rollen") or []:
        if isinstance(r, dict) and r.get("id") == kennung:
            return _filter_anwenden(r.get("filter"), datenquelle, plantyp, parameter)
    return []


def _filter_anwenden(
    filter: dict[str, Any],
    datenquelle: Datenquelle,
    plantyp: dict[str, Any] | None,
    parameter: dict[str, Any] | None,
) -> list[Person]:
    """Wertet einen Filter-Knoten auf der Personenliste aus."""
    personen = datenquelle.personen()

    def passt(p: Person) -> bool:
        return _knoten_passt(filter, p, datenquelle, plantyp, parameter)

    return [p for p in personen if passt(p)]


def _knoten_passt(
    knoten: dict[str, Any],
    person: Person,
    datenquelle: Datenquelle,
    plantyp: dict[str, Any] | None,
    parameter: dict[str, Any] | None,
) -> bool:
    if not isinstance(knoten, dict):
        return False
    for schluessel, wert in knoten.items():
        if schluessel == "alle":
            return all(
                _knoten_passt(k, person, datenquelle, plantyp, parameter) for k in (wert or [])
            )
        if schluessel == "eine":
            return any(
                _knoten_passt(k, person, datenquelle, plantyp, parameter) for k in (wert or [])
            )
        if schluessel == "nicht":
            return not _knoten_passt(wert, person, datenquelle, plantyp, parameter)
        if schluessel == "merkmal":
            # tag: True-wertig; auswahl/text: vorhanden; sonst wert in merkmale.
            val = datenquelle.merkmal_werte(wert).get(person.kennung)
            if val is None:
                return False
            if isinstance(val, bool):
                return val
            return True
        if schluessel == "gruppe":
            return person.kennung in datenquelle.gruppen_mitglieder(wert)
        if schluessel == "anmeldung":
            return person.kennung in datenquelle.anmeldungen(wert)
        if schluessel == "person":
            return person.kennung == wert
    return False


def ist_abwesend(person: Person, datum: date, datenquelle: Datenquelle) -> bool:
    """True, wenn die Person am ``datum`` abwesend ist (fuer abwesenheit_beachten)."""
    for a in datenquelle.abwesenheiten(datum, datum):
        if a.person == person.kennung:
            return True
    return False


def verfuegbare_kandidaten(
    rolle: Any,
    termin_datum: date,
    datenquelle: Datenquelle,
    plantyp: dict[str, Any] | None = None,
    *,
    parameter: dict[str, Any] | None = None,
) -> list[Person]:
    """Kandidaten ohne Abwesende (fuer die Fuell- und Such-Logik)."""
    return [
        p for p in kandidaten(rolle, datenquelle, plantyp, parameter=parameter)
        if not ist_abwesend(p, termin_datum, datenquelle)
    ]
