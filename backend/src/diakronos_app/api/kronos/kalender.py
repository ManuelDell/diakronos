"""Portierung von `diakronos.diakonos.api.kalender` (Altcode, Frappe).

VORLAGE (READ-ONLY): `referenz/diakronos-frappe/diakronos/diakonos/api/kalender.py`

Portierter Endpunkt:

    get_events   (Original: kalender.py:5-38)

Der Endpunkt liefert bestaetigte Termine des Kronos-Kalenders fuer das
oeffentliche Anmelde-Frontend (`Element` mit `status = "Festgelegt"`).
Anders als `kronos.api.calendar_get.get_calendar_events` gibt es hier KEINEN
Kalender-Rechtefilter — die Liste ist fuer jeden angemeldeten User gleich
(Original prueft nur angemeldet, nicht berechtigt).

ABWEICHUNG (Nachtbefund OP-EVENT-R1): Der Port uebernimmt das NICHT. Die
Liste wird auf `get_accessible_calendars()` eingeschraenkt — Termine
gesperrter Kalender waren sonst fuer jedes Mitglied lesbar.

Frappe-Aufrufe des Originals -> Compat-Schicht:

    frappe.session.user                              -> session.user
    frappe.get_all("Element", filters=[...], limit=500) -> get_all(...)
    frappe.db.get_value("Registrierungslink", x, "slug") -> get_value(...)
    frappe.whitelist(allow_guest=False)              -> whitelist(allow_guest=False)
"""

from __future__ import annotations

# Original-Frappe-Pfad der SPA (Registry-Schluessel, s. registry.py).
FRAPPE_MODULE = "diakronos.diakonos.api.kalender"

from diakronos_app.frappe_compat.registry import whitelist

from diakronos_app.frappe_compat.api_helpers import (
    _coerce,
    _coerce_filters,
    get_all,
    get_value,
    session,
)

__all__ = ["get_events"]

# `_coerce_filters` kommt zentral aus `frappe_compat/api_helpers` (P8). Die
# frueh hier liegende Kopie war identisch mit der in `ressource_api.py` — und
# beide mit `_shared.py` (jetzt `api_helpers.py`).

@whitelist(allow_guest=False)
def get_events(start_date, end_date):
    """Gibt bestaetigte Termine aus dem Kronos-Kalender zurueck.

    Quelle: kalender.py:5-38.

    Original-Filter (Listenschreibweise, Konjunktion UND):

        ["element_start", "<=", end_date + " 23:59:59"]
        ["element_end",   ">=", start_date]
        ["status",        "=",  "Festgelegt"]

    Sortierung `element_start asc`, Limit 500 — beides ueber `get_all`.

    OP-EVENT-R1: Der Endpunkt liefert nur Termine aus Kalendern mit Leserecht
    (`get_accessible_calendars`) — wie `get_calendar_events`. Ohne diesen
    Filter waren Termine gesperrter Kalender fuer jedes Mitglied sichtbar.
    """
    user = session.user
    if user == "Guest":
        return []

    from diakronos_app.api.kronos.permissions import get_accessible_calendars

    kalender = [c["name"] for c in get_accessible_calendars()]
    if not kalender:
        return []

    events = get_all(
        "Element",
        filters=_coerce_filters(
            "Element",
            {
                "element_start": ["<=", str(end_date) + " 23:59:59"],
                "element_end": [">=", start_date],
                "status": "Festgelegt",
                "element_calendar": ["in", kalender],
            },
        ),
        fields=[
            "name",
            "element_name",
            "element_start",
            "element_end",
            "all_day",
            "anmeldung_aktiv",
            "registrierungslink",
        ],
        order_by="element_start asc",
        limit_page_length=500,
    ) or []

    result = []
    for e in events:
        slug = None
        if e.get("registrierungslink"):
            slug = get_value("Registrierungslink", e["registrierungslink"], "slug")

        result.append({
            "id": e["name"],
            "title": e.get("element_name") or "(Kein Titel)",
            "start": str(e["element_start"])[:10] if e.get("element_start") else "",
            "end": str(e["element_end"])[:10] if e.get("element_end") else "",
            "startDatetime": str(e["element_start"]) if e.get("element_start") else "",
            "endDatetime": str(e["element_end"]) if e.get("element_end") else "",
            "allDay": bool(e.get("all_day")),
            "anmeldungAktiv": bool(e.get("anmeldung_aktiv")),
            "registrierungslinkId": e.get("registrierungslink") or "",
            "registrierungslinkSlug": slug or "",
        })
    return result
