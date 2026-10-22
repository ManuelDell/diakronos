"""Gemeinsame Farbreinigung fuer Dienstbereich-Farben (UXD-R28/DES-04).

Es gibt zwei Lesepfade, die eine Dienstbereich-Farbe an die Oberflaeche
reichen — die Gruppenkacheln (`api/gruppen.py`) und das Organigramm
(`api/orgchart_api.py`). Beide muessen denselben Fremdwert abwehren, sonst
landet ein Alt- oder Schreibwert roh in einem `style`-String (CSS-Injection).
Deshalb liegt die eine Pruefstelle hier und nicht als Kopie in jedem Modul.
"""

from __future__ import annotations

import re
from typing import Any

# Nur Hex: `#RGB`, `#RRGGBB`, `#RRGGBBAA`.
FARB_MUSTER = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")

STANDARD_FARBE = "#667eea"


def _normalisiere_farbe(farbe: Any, *, standard: str = STANDARD_FARBE) -> str:
    """Bringt eine Dienstbereich-Farbe in eine sichere, gueltige Form.

    Erlaubt ist nur ein Hex-Wert (`#RGB`, `#RRGGBB`, `#RRGGBBAA`). Ein
    fuehrendes `#` darf fehlen — es wird ergaenzt (der Hinweis in der
    Oberflaeche nennt `3b82f6` ohne `#`). Alles andere (Klartext, CSS-
    Fragmente, `url(...)`) wird verworfen und durch den Standardwert
    ersetzt; so landet nie ein Fremdwert im `style`-String der Oberflaeche.

    Das ist die *eine* Stelle, an der die Farbe geprueft wird: alle
    Schreibpfade rufen sie auf, und die Lesepfade (`get_gruppen_for_orgchart`,
    `get_gruppen_page_data`, `orgchart_api.get_orgchart_data`) lassen auch
    Bestandsdaten (Altwert `zzz-keine-farbe`) durch sie laufen.
    """
    if farbe is None:
        return standard
    wert = str(farbe).strip()
    if not wert:
        return standard
    if not wert.startswith("#"):
        wert = "#" + wert
    return wert if FARB_MUSTER.match(wert) else standard
