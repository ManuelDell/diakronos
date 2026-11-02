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

#: Standardfarben der KALENDER (ON-0c, R2). Sie waren als Literal in sechs
#: Modulen wiederholt (`#3b82f6` fuenfmal, `#4f7cff`, `#9ca3af`) — dieselbe
#: Entscheidung an sechs Stellen, genau das, was die CSS-Single-Source-of-Truth
#: vermeiden soll. Sie sind NUTZDATEN (Kalender-/Ereignisfarbe, die die
#: Oberflaeche als `style`-Wert malt), keine Gestaltungsregel — deshalb stehen
#: sie hier zentral und nicht in `tokens.css`. Ein neuer Standard wird HIER
#: geaendert, nicht an einer Fundstelle.
KALENDER_STANDARD_FARBE = "#3b82f6"
KALENDER_STANDARD_FARBE_CALDAV = "#4f7cff"
KALENDER_STANDARD_FARBE_KONFLIKT = "#ef4444"
KALENDER_STANDARD_FARBE_OHNE = "#9ca3af"
GOOGLE_STANDARD_FARBE = "#4285F4"


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
