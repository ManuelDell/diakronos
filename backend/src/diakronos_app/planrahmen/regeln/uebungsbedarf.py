"""Regelbausteine liefern terminierte Bedarfe fuer die generische Fuellung."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from ..engine.modell import Eintrag, Vorschlag
from ..engine.pfade import passt_zu_feld


@dataclass(frozen=True)
class Uebungsbedarf:
    """Ein Wert braucht mindestens N verschiedene Uebungstage vor seinem Einsatz.

    ``vorrang`` sagt, dass der Einsatz von Hand festgelegt ist (fixiert,
    manuell, uebernommen). Solche Bedarfe haben bei knapper Kapazitaet
    Vorrang: sie werden zuerst bedient, notfalls mit einer klaren
    kapazitaetsbezogenen Meldung (siehe ``engine.uebungen``).
    """

    feld: str
    wert: str
    bis: date
    mindestens: int
    vorlauf_wochen: int
    auch_in: tuple[str, ...] = ()
    vorrang: bool = False
    #: Deklariertes Sing-/Einsatzfeld der Regel (z. B. ``lieder``). Traegt die
    #: kapazitaetsbezogene Meldung, damit sie am Singtermin erscheint und die
    #: generische „erst n von m Uebungen"-Meldung desselben Felds ersetzt.
    einsatz_feld: str = ""


# Quellen, die einen Einsatz als "von Hand festgelegt" kennzeichnen.
VORRANG_QUELLEN = ("manuell", "uebernommen")


def ist_vorrang(eintrag: Eintrag) -> bool:
    """Wahr, wenn dieser Einsatz nicht vom Generator stammt (P6, fixiert)."""
    return bool(eintrag.fixiert or eintrag.quelle in VORRANG_QUELLEN)


def uebungsregeln(plantyp: dict[str, Any], bezugsplaene: list[tuple[dict[str, Any], Vorschlag]]) -> list[tuple[dict[str, Any], dict[str, Any], list[Eintrag] | None]]:
    """Lokale und explizit bereitgestellte Fremdregeln mit Ziel im aktuellen Typ."""
    result = []
    for typ, eintraege in [(plantyp, None)] + [(p, v.eintraege) for p, v in bezugsplaene]:
        for regel in typ.get("regeln", []):
            if regel["baustein"] != "vorher_geuebt":
                continue
            ziel = regel.get("uebung", {"plantyp": typ.get("id", ""), "feld": regel.get("uebungsfeld", regel["feld"])})
            if ziel["plantyp"] == plantyp.get("id", ""):
                result.append((regel, ziel, eintraege))
    return result


def uebungsbedarfe(plantyp: dict[str, Any], eintraege: list[Eintrag], bezugsplaene: list[tuple[dict[str, Any], Vorschlag]]) -> list[Uebungsbedarf]:
    """Einsatzwerte in Bedarfe uebersetzen; gleiche Bedarfe deterministisch vereinen.

    ``vorrang`` erbt der Bedarf von seinem Einsatz: von Hand festgelegte
    Singtermine sind Uebungsbedarf mit hoechster Prioritaet. Ueberschreibt
    ein Auto-Einsatz denselben Bedarf, gewinnt der Vorrang (Vereinigung).
    """
    result: dict[tuple[str, str, date], Uebungsbedarf] = {}
    for regel, ziel, fremde in uebungsregeln(plantyp, bezugsplaene):
        for e in eintraege if fremde is None else fremde:
            if e.termin is not None and e.wert is not None and passt_zu_feld(e.feld_pfad, regel["feld"]):
                bedarf = Uebungsbedarf(ziel["feld"], str(e.wert), e.termin.datum, regel["mindestens"],
                                       regel.get("vorlauf_wochen", max(4, regel["mindestens"])),
                                       tuple(regel.get("auch_in", [])), ist_vorrang(e), regel["feld"])
                schluessel = (bedarf.feld, bedarf.wert, bedarf.bis)
                alt = result.get(schluessel)
                # Gleichstand deterministisch aufloesen; Vorrang bleibt erhalten.
                if alt is None or (bedarf.vorrang and not alt.vorrang) or (
                        bedarf.vorrang == alt.vorrang and (bedarf.mindestens, bedarf.vorlauf_wochen) > (
                            alt.mindestens, alt.vorlauf_wochen)):
                    result[schluessel] = bedarf
    return sorted(result.values(), key=lambda b: (not b.vorrang, b.bis, -b.mindestens, b.feld, b.wert))
