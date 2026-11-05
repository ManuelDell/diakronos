"""UX2b (Karte P2) — Papierkorb-Verwaltung: Liste der geloeschten Zeilen (Admin).

WAS HIER STEHT
--------------
``papierkorb.liste`` zeigt, was in den letzten ``AUFBEWAHRUNG_TAGE`` (7) Tagen
geloescht wurde — mit Bereich, Titel, Zeitpunkt, wer geloescht hat und wann
die Zeile endgueltig verschwindet. Grundlage fuer das Zurueckholen in der
Oberflaeche (``<bereich>.wiederherstellen_*``).

Nur Administrator (wie das Loeschen der Bereiche): die Liste enthaelt auch
Inhalte, die einzelne Verantwortliche nicht sehen duerfen.

WARUM DIE TITEL HIER JE BEREICH STEHEN
--------------------------------------
Die fuenf Bereiche benennen ihren Titel unterschiedlich
(``element_name``, ``gruppenname``, ``titel``). Die Zuordnung ist an EINER
Stelle — nicht in der Oberflaeche — damit Liste und Wiederherstellen dieselbe
Wahrheit benutzen.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from diakronos_app import papierkorb
from diakronos_app.frappe_compat import permissions
from diakronos_app.frappe_compat.exceptions import PermissionError as FrappePermissionError
from diakronos_app.frappe_compat.exceptions import throw
from diakronos_app.frappe_compat.query import get_all
from diakronos_app.frappe_compat.registry import whitelist
from diakronos_app.frappe_compat.session import session

#: DocType -> Felder, die einen lesbaren Titel tragen (erster Treffer gewinnt).
_TITELFELDER: dict[str, tuple[str, ...]] = {
    "Beitrag": ("titel",),
    "Element": ("element_name",),
    "Gruppe": ("gruppenname",),
    "Wiki Artikel": ("titel",),
    "Lied": ("titel",),
}

#: DocType -> Bereichsname fuer die Oberflaeche (deutsch, wie die Menues).
BEREICHSNAMEN: dict[str, str] = {
    "Beitrag": "Beitrag",
    "Element": "Termin",
    "Gruppe": "Gruppe",
    "Wiki Artikel": "Wiki-Seite",
    "Lied": "Lied",
}


def _als_zeitpunkt(wert: Any) -> datetime:
    """Datenbankwert -> ``datetime`` (SQLite liefert hier einen String)."""
    if isinstance(wert, datetime):
        return wert
    return datetime.fromisoformat(str(wert))


def _require_admin() -> None:
    """Mitgliederadministrator oder System Manager (wie `_require_admin` der Bereiche)."""
    if session.user in ("", "Guest"):
        throw("Anmeldung erforderlich.", FrappePermissionError)
    roles = permissions.get_roles()
    if "Mitgliederadministrator" not in roles and "System Manager" not in roles:
        throw("Nur für Administratoren.", FrappePermissionError)


@whitelist(allow_guest=False)
def liste(limit: int = 200) -> dict[str, Any]:
    """Geloeschte Zeilen aller fuenf Bereiche, neueste Loeschung zuerst.

    Rueckgabe::

        {"success": True,
         "aufbewahrung_tage": 7,
         "eintraege": [{"bereich": "Termin", "doctype": "Element",
                        "name": "<Kennung>", "titel": "...",
                        "geloescht_am": "...", "geloescht_von": "...",
                        "laeuft_ab_am": "..."}],
         "anzahl": n}
    """
    _require_admin()

    anzahl_max = max(1, min(int(limit or 200), 500))
    jetzt = datetime.now().replace(microsecond=0)
    aufbewahrung = timedelta(days=papierkorb.AUFBEWAHRUNG_TAGE)
    eintraege: list[dict[str, Any]] = []

    for doctype in papierkorb.BEREICHE:
        felder = ["name", papierkorb.GELOESCHT_AM, papierkorb.GELOESCHT_VON,
                  *_TITELFELDER[doctype]]
        zeilen = get_all(
            doctype,
            filters=[[papierkorb.GELOESCHT_AM, "is", "set"]],
            fields=felder,
            order_by=f"{papierkorb.GELOESCHT_AM} desc",
            limit_page_length=anzahl_max,
        ) or []
        for zeile in zeilen:
            geloescht_am = zeile.get(papierkorb.GELOESCHT_AM)
            titel = ""
            for feld in _TITELFELDER[doctype]:
                wert = str(zeile.get(feld) or "").strip()
                if wert:
                    titel = wert
                    break
            eintraege.append({
                "bereich": BEREICHSNAMEN[doctype],
                "doctype": doctype,
                "name": zeile.get("name"),
                "titel": titel,
                "geloescht_am": str(geloescht_am) if geloescht_am else "",
                "geloescht_von": zeile.get(papierkorb.GELOESCHT_VON) or "",
                # SQLite (Test) liefert den Zeitstempel als String, PostgreSQL
                # als datetime — beide Formen muessen dieselbe Antwort geben.
                "laeuft_ab_am": (
                    (_als_zeitpunkt(geloescht_am) + aufbewahrung).isoformat(sep=" ")
                    if geloescht_am else ""
                ),
            })

    eintraege.sort(key=lambda e: e["geloescht_am"], reverse=True)
    eintraege = eintraege[:anzahl_max]
    return {
        "success": True,
        "aufbewahrung_tage": papierkorb.AUFBEWAHRUNG_TAGE,
        "anzahl": len(eintraege),
        "jetzt": jetzt.isoformat(sep=" "),
        "eintraege": eintraege,
    }


__all__ = ["BEREICHSNAMEN", "liste"]
