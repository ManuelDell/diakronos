"""Trockenlauf (P12/Werkzeug des Onboarding-Agenten): ohne Seiteneffekte.

``trockenlauf`` erzeugt fuer einen Plantyp einen begrenzten Vorschlag (z. B. 8
Wochen) samt Verstoessen und Bedarf — ohne Datenbank, ohne Persistenz. Damit
kann der Onboarding-Agent eine Plantyp-Datei pruefen, bevor ein echter Plan
entsteht (Konzept Teil D: "Trockenlauf (8 Wochen generieren, Konflikte ansehen)").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from .bedarf import Bedarf, bedarfspruefung
from .datenquelle import Datenquelle
from .generator import generiere
from .modell import Termin, Vorschlag, Verstoss
from .termine import erzeuge_termine


@dataclass
class TrockenlaufErgebnis:
    """Zusammenfassung eines Trockenlaufs (Onboarding-Werkzeug)."""

    termine: list[Termin] = field(default_factory=list)
    vorschlag: Vorschlag | None = None
    verstoesse: list[Verstoss] = field(default_factory=list)
    bedarf: list[Bedarf] = field(default_factory=list)
    meldungen: list[str] = field(default_factory=list)


def trockenlauf(
    plantyp: dict[str, Any],
    parameter: dict[str, Any],
    datenquelle: Datenquelle,
    wochen: int = 8,
    seed: int = 0,
    ab: date | None = None,
) -> TrockenlaufErgebnis:
    """Fuehrt einen Trockenlauf durch: Termine + Vorschlag + Verstoesse + Bedarf.

    ``ab`` ist der Beginn des Zeitfensters (Vorgabe: heute); ``wochen`` die
    Laenge. Es werden KEINE Seiteneffekte ausgeloest (keine DB, keine Endpunkte).
    """
    von = ab or date.today()
    bis = von + timedelta(weeks=wochen)

    termine_je_reihe = erzeuge_termine(plantyp, parameter, datenquelle, von=von, bis=bis)
    # flache Liste in Reihenfolge
    termine: list[Termin] = []
    for ts in termine_je_reihe.values():
        termine.extend(ts)
    termine.sort(key=lambda t: (t.datum, t.reihe))

    vorschlag = generiere(plantyp, parameter, termine, [], datenquelle, seed=seed)
    bedarf = bedarfspruefung(plantyp, datenquelle)

    return TrockenlaufErgebnis(
        termine=termine,
        vorschlag=vorschlag,
        verstoesse=vorschlag.verstoesse,
        bedarf=bedarf,
        meldungen=vorschlag.meldungen,
    )
