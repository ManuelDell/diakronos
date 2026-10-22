"""Uebernahme von Wertefeldern inklusive Besetzung und Ablauf-Metadaten (C4)."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from .modell import Eintrag
from .pfade import passt_zu_feld


def uebernimm(ziel_plan: Any, quell_plan: Any, felder: list[str]) -> list[Eintrag]:
    """Kopiert Werte ohne Fixierung; der Aufrufer fuegt sie an und prueft Regeln.

    Ein einzelner Zieltermin nimmt den Quelltermin auf. Bei mehreren Terminen
    erfolgt die Zuordnung nach Datum/Reihe, niemals stillschweigend zum ersten.
    Ablauf-IDs und Reihenfolge bleiben erhalten; Besetzung wird mitkopiert.
    Bestehende Zielwerte und die Quelle werden nicht veraendert.
    """
    quelle = getattr(quell_plan, "eintraege", quell_plan or [])
    zieltermine = getattr(ziel_plan, "termine", [])
    vorhanden = {(e.termin, e.feld_pfad) for e in getattr(ziel_plan, "eintraege", [])}
    def ausgewaehlt(e: Eintrag) -> bool:
        if any(passt_zu_feld(e.feld_pfad, f) for f in felder):
            return True
        if e.termin is None or "/" not in e.feld_pfad:
            return False
        feld, rest = e.feld_pfad.split("/", 1)
        eid = rest.split(".", 1)[0]
        return any(element["id"] == eid and f"{feld}.{element['typ']}" in felder
                   for element in e.termin.ablauf.get(feld, []))
    gewaehlt = [e for e in quelle if ausgewaehlt(e)]
    elemente = {(e.termin, e.feld_pfad.split(".", 1)[0]) for e in gewaehlt if "/" in e.feld_pfad}
    gewaehlt = [e for e in quelle if e in gewaehlt or (e.termin, e.feld_pfad.split(".", 1)[0]) in elemente]
    neu: list[Eintrag] = []
    for e in gewaehlt:
        termin = e.termin
        if len(zieltermine) == 1:
            termin = zieltermine[0]
        elif zieltermine and e.termin is not None:
            passend = [t for t in zieltermine if (t.datum, t.reihe) == (e.termin.datum, e.termin.reihe)]
            if len(passend) != 1:
                raise ValueError("Uebernahme braucht eine eindeutige Zieltermin-Zuordnung.")
            termin = passend[0]
        if (termin, e.feld_pfad) in vorhanden:
            continue
        neu.append(Eintrag(e.feld_pfad, deepcopy(e.wert), e.art, termin, False, "uebernommen"))
        vorhanden.add((termin, e.feld_pfad))
        if e.termin is not None and termin is not None and "/" in e.feld_pfad:
            feld = e.feld_pfad.split("/", 1)[0]
            ids = {pfad.split("/", 1)[1] for t, pfad in elemente if t is e.termin and pfad.startswith(feld + "/")}
            ziel_liste = termin.ablauf.setdefault(feld, [])
            for element in e.termin.ablauf.get(feld, []):
                if element["id"] in ids and not any(x["id"] == element["id"] for x in ziel_liste):
                    ziel_liste.append(deepcopy(element))
    return neu
