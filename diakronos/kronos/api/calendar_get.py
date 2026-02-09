# diakronos/kronos/api/calendar_get.py

import frappe
from frappe import _
from .permissions import get_accessible_calendars
import json

@frappe.whitelist()
def get_calendar_events(start_date, end_date, calendar_filter=None):
    """
    Liefert Events für FullCalendar.
    Filtert auf ausgewählte Kalender + nur lesbare Kalender.
    """
    user = frappe.session.user
    if user == "Guest":
        frappe.throw(_("Nicht angemeldet"))

    try:
        # Zeitraum
        filters = {
            "element_start": [">=", f"{start_date} 00:00:00"],
            "element_end": ["<=", f"{end_date} 23:59:59"],
        }

        # Erlaubte Kalender (aus permissions)
            # Direkt die Funktion aufrufen (kein frappe.call nötig, da wir intern sind)
        allowed_calendars = get_accessible_calendars()
        allowed = [cal["name"] for cal in allowed_calendars if isinstance(cal, dict) and "name" in cal]
                # Filter anwenden
        if calendar_filter:
            try:
                requested = json.loads(calendar_filter)
                # Nur erlaubte + gewählte
                filters["element_calendar"] = ["in", list(set(requested) & set(allowed))]
            except:
                filters["element_calendar"] = ["in", allowed]
        else:
            filters["element_calendar"] = ["in", allowed]

        if not filters.get("element_calendar"):
            return []  # Keine Berechtigung → leer

        events = frappe.get_all(
            "Element",
            filters=filters,
            fields=[
                "name", "element_name as title",
                "element_start as start", "element_end as end",
                "all_day", "element_color", "element_calendar"
            ]
        )

        formatted = []
        for e in events:
            color = frappe.db.get_value("Kalender", e.element_calendar, "calendar_color") or e.element_color or "#3b82f6"
            formatted.append({
                "id": e.name,
                "title": e.title or "Termin",
                "start": str(e.start),
                "end": str(e.end) if e.end else None,
                "allDay": bool(e.all_day),
                "backgroundColor": color,
                "borderColor": color
            })

        return formatted

    except Exception as e:
        frappe.log_error(str(e), "get_calendar_events")
        frappe.throw(_("Fehler beim Laden der Termine"))