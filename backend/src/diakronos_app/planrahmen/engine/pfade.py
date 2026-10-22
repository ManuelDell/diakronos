"""Gemeinsame Feldpfad-Normalisierung fuer Slots, Historie und Regeln."""
from functools import lru_cache
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .modell import Termin


def feld_deklaration(pfad: str, termin: "Termin", ablauf_typen: dict[str, str] | None = None) -> str:
    """Konkreten Pfad inklusive Ablauf-Elementtypen als Deklarationspfad lesen."""
    for ablauf, elemente in termin.ablauf.items():
        for element in elemente:
            anfang = f"{ablauf}/{element['id']}"
            if pfad == anfang or pfad.startswith(anfang + "."):
                pfad = f"{ablauf}.{element['typ']}" + pfad[len(anfang):]
    for anfang, deklaration in (ablauf_typen or {}).items():
        if pfad == anfang or pfad.startswith(anfang + "."):
            pfad = deklaration + pfad[len(anfang):]
    return feld_basis(pfad)


def feld_bezug_passt(pfad: str, bezug: str, termin: "Termin", *, unterfelder: bool = False,
                     ablauf_typen: dict[str, str] | None = None) -> bool:
    """Ordnet deklarative Bedingungen konkreten Instanzen desselben Termins zu.

    Indizes werden entfernt; Ablauf-IDs werden zusaetzlich auf ihren Elementtyp
    abgebildet (programm/e1.leitung -> programm.dienst.leitung). Ein expliziter
    Instanzbezug bleibt dagegen exakt. Ohne Reihenpraefix gilt die aktuelle Reihe.
    """
    typ_pfad = feld_deklaration(pfad, termin, ablauf_typen)
    if ":" not in bezug:
        pfad = pfad.split(":", 1)[-1]
        typ_pfad = typ_pfad.split(":", 1)[-1]
    if "[" in bezug or "/" in bezug:
        varianten = {pfad}
    else:
        varianten = {feld_basis(pfad), typ_pfad}
    return any(p == bezug or (unterfelder and any(p.startswith(bezug + t) for t in ".[@#/"))
               for p in varianten)


@lru_cache(maxsize=4096)
def feld_basis(pfad: str) -> str:
    """Entfernt Instanzindizes und opaque Ablauf-IDs, nicht Unterfelder."""
    return re.sub(r"/[^.]+", "", re.sub(r"\[[0-9]+\]", "", pfad))


@lru_cache(maxsize=4096)
def passt_zu_feld(pfad: str, feld: str) -> bool:
    """Vergleicht reine Wertepfade; wiederholte Kandidatenpruefungen nutzen den Cache."""
    basis = feld_basis(pfad)
    return basis == feld or (":" not in feld and basis.split(":", 1)[-1] == feld)
