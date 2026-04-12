# diakronos/kronos/api/calendar_get.py

import frappe
from frappe import _
from .permissions import get_accessible_calendars
import json

@frappe.whitelist()
def get_calendar_events(start_date, end_date, calendar_filter=None, view_mode=True):
    """
    Liefert Events für FullCalendar.
    view_mode=True  → Lesemodus: alle sehen nur 'Festgelegt'
    view_mode=False → Bearbeitungsmodus: Moderatoren sehen auch Vorschlag/Konflikt
    """
    user = frappe.session.user
    if user == "Guest":
        frappe.throw(_("Nicht angemeldet"))

    # view_mode als bool normalisieren (kommt als String vom POST-Body)
    if isinstance(view_mode, str):
        view_mode = view_mode.lower() not in ("false", "0", "")
    else:
        view_mode = bool(view_mode)

    try:
        # Zeitraum
        filters = {
            "element_start": [">=", f"{start_date} 00:00:00"],
            "element_end": ["<=", f"{end_date} 23:59:59"],
        }

        # Erlaubte Kalender (inkl. is_moderator, selbstverwaltet Flags)
        allowed_calendars = get_accessible_calendars()
        cal_info = {
            cal["name"]: cal
            for cal in allowed_calendars
            if isinstance(cal, dict) and "name" in cal
        }
        allowed = list(cal_info.keys())

        if calendar_filter:
            try:
                requested = json.loads(calendar_filter)
                effective = list(set(requested) & set(allowed))
            except Exception:
                effective = allowed
        else:
            effective = allowed

        if not effective:
            return []

        _fields = [
            "name",
            "element_name as title",
            "element_start as start",
            "element_end as end",
            "all_day",
            "element_color",
            "element_calendar",
            "element_category",
            "ressource",
            "ignore_conflict",
            "status",
            "description",
            "repeat_this_event",
            "series_id",
        ]

        events = []

        if view_mode:
            # Lesemodus: alle Kalender → nur Festgelegt, egal ob Moderator oder nicht
            f = {**filters, "element_calendar": ["in", effective], "status": "Festgelegt"}
            events = frappe.get_all("Element", filters=f, fields=_fields)
        else:
            # Bearbeitungsmodus: Moderatoren sehen alle Statuses
            mod_cals     = [n for n in effective if cal_info.get(n, {}).get("is_moderator")]
            regular_cals = [n for n in effective if not cal_info.get(n, {}).get("is_moderator")]

            if mod_cals:
                events.extend(frappe.get_all("Element",
                    filters={**filters, "element_calendar": ["in", mod_cals]},
                    fields=_fields))
            if regular_cals:
                events.extend(frappe.get_all("Element",
                    filters={**filters, "element_calendar": ["in", regular_cals], "status": "Festgelegt"},
                    fields=_fields))

        formatted = []
        for e in events:
            color = frappe.db.get_value("Kalender", e.element_calendar, "calendar_color") or e.element_color or "#3b82f6"

            category_name = ""
            if e.element_category:
                try:
                    category_name = frappe.db.get_value("Eventkategorie", e.element_category, "event_category_name") or e.element_category
                except:
                    pass  # Keine Rechte → Fallback auf ID

            # Status-basiertes Styling: Vorschlag = gestrichelt, Konflikt = rot
            border_color = color
            bg_color     = color
            if e.status == "Vorschlag":
                bg_color = color + "99"   # leicht transparent
            elif e.status == "Konflikt":
                border_color = "#ef4444"
                bg_color     = "#ef444433"

            formatted.append({
                "id":              e.name,
                "title":           e.title or "Termin",
                "start":           str(e.start),
                "end":             str(e.end) if e.end else None,
                "allDay":          bool(e.all_day),
                "backgroundColor": bg_color,
                "borderColor":     border_color,
                "resourceId":      e.ressource or "__unassigned__",
                "extendedProps": {
                    "name":               e.name,
                    "element_name":       e.title,
                    "element_calendar":   e.element_calendar,
                    "element_category":   e.element_category,
                    "event_category_name": category_name,
                    "element_start":      str(e.start),
                    "element_end":        str(e.end) if e.end else None,
                    "all_day":            e.all_day,
                    "status":             e.status,
                    "element_color":      color,
                    "ressource":          e.ressource or None,
                    "ignore_conflict":    bool(e.ignore_conflict),
                    "description":        e.description or "",
                    "repeat_this_event":  e.repeat_this_event,
                    "series_id":          e.series_id,
                }
            })

        return formatted
    except Exception as e:
        frappe.log_error(str(e), "get_calendar_events")
        frappe.throw(_("Fehler beim Laden der Termine"))