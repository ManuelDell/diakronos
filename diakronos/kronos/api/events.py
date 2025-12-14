# diakronos/kronos/api/events.py - FINAL KORRIGIERT
"""
API für Event/Element-Verwaltung und -Abfrage.
Feldnamen aus deinem Element DocType (JSON).
"""

import frappe
from frappe import _
from datetime import datetime
import json
from .permissions import has_calendar_permission


@frappe.whitelist()
def get_calendar_events(start_date, end_date, calendar_filter=None):
    """
    Gibt alle Events im Zeitraum für alle sichtbaren Kalender.
    
    Args:
        start_date (str): ISO-Datum (YYYY-MM-DD)
        end_date (str): ISO-Datum (YYYY-MM-DD)
        calendar_filter (str): JSON-Array von Kalender-Namen
    
    Returns:
        List[Dict]: Events im TUI-Calendar v2.x Format
    """
    try:
        user = frappe.session.user
        if not user or user == "Guest":
            frappe.throw(_("Sie müssen angemeldet sein."))

        # Parse filter
        calendars_to_show = []
        if calendar_filter:
            try:
                calendars_to_show = json.loads(calendar_filter)
            except:
                pass

        # Hole alle Kalender
        all_calendars = frappe.get_all(
            'Kalender',
            fields=['name', 'calendar_name', 'calendar_color'],
            order_by='calendar_name asc'
        )

        # Filter nach Berechtigungen
        accessible_calendars = []
        for cal in all_calendars:
            if has_calendar_permission(cal['name'], 'read'):
                accessible_calendars.append(cal['name'])

        # Wenn Filter, dann nur gefilterte die auch zugänglich sind
        if calendars_to_show:
            show_calendars = [c for c in calendars_to_show if c in accessible_calendars]
        else:
            show_calendars = accessible_calendars

        if not show_calendars:
            frappe.logger().warning(f'No accessible calendars for user {user}')
            return []

        # Hole Events - EXAKTE FELDNAMEN AUS DEINEM DOCTYPE
        elements = frappe.get_all(
            'Element',
            filters=[
                ['element_calendar', 'in', show_calendars],
                ['element_start', '>=', start_date + ' 00:00:00'],
                ['element_end', '<=', end_date + ' 23:59:59'],
                ['docstatus', '!=', 2]
            ],
            fields=[
                'name',
                'element_name',          # Der Titel
                'element_start',         # Start Datetime
                'element_end',           # End Datetime
                'all_day',               # Ganztägig
                'description',           # Beschreibung
                'element_color',         # Farbe (fetch_from calendar_color)
                'status',                # Status
                'element_calendar',      # Kalender Link
                'owner'
            ],
            order_by='element_start asc'
        )

        # Kalender-Farben Mapping
        calendar_colors = {}
        for cal in all_calendars:
            calendar_colors[cal['name']] = cal.get('calendar_color', '#007bff') or '#007bff'

        # Status zu Farb-Mapping
        STATUS_COLORS = {
            'Festgelegt': None,      # → Kalender-Farbe
            'Vorschlag': '#FEF3C7',  # Sanftes Gelb
            'Konflikt': '#FEE2E2'    # Sanftes Rot
        }

        # Formatiere für TUI-Calendar
        formatted = []
        for elem in elements:
            try:
                # Bestimme Farbe: Status-Farbe OR Kalender-Farbe
                color = STATUS_COLORS.get(elem.get('status'))
                if not color:
                    color = calendar_colors.get(elem.get('element_calendar'), '#007bff')

                # Parse Datumsstrings
                start_str = str(elem.get('element_start', '')).replace(' ', 'T')
                end_str = str(elem.get('element_end', '')).replace(' ', 'T')

                if not start_str or not end_str:
                    continue

                start_dt = datetime.fromisoformat(start_str)
                end_dt = datetime.fromisoformat(end_str)

                event = {
                    'id': elem.get('name'),
                    'title': elem.get('element_name', 'Untitled'),
                    'start': start_dt.isoformat(),
                    'end': end_dt.isoformat(),
                    'isAllday': bool(elem.get('all_day')),
                    'color': color,
                    'backgroundColor': color,
                    'borderColor': color,
                    'calendar': elem.get('element_calendar'),
                    'status': elem.get('status', 'Festgelegt'),
                    'description': elem.get('description', ''),
                    'canEdit': elem.get('owner') == user
                }
                formatted.append(event)

            except Exception as e:
                frappe.logger().warning(f'Error formatting event {elem.get("name")}: {str(e)}')
                continue

        frappe.logger().info(f'✅ get_calendar_events: {len(formatted)} events for {user}')
        return formatted

    except Exception as e:
        frappe.log_error(str(e), 'get_calendar_events')
        frappe.throw(_('Fehler beim Laden der Termine: ') + str(e))


@frappe.whitelist()
def get_event_details(element_name):
    """
    Gibt Details zu einem spezifischen Event/Element.
    """
    try:
        element = frappe.get_doc('Element', element_name)

        if not has_calendar_permission(element.element_calendar, 'read'):
            frappe.throw(_("Keine Berechtigung für dieses Event"))

        return {
            'name': element.name,
            'title': element.element_name,
            'start': str(element.element_start),
            'end': str(element.element_end),
            'isAllday': element.all_day,
            'description': element.description,
            'status': element.status,
            'calendar': element.element_calendar,
            'color': element.element_color,
        }

    except Exception as e:
        frappe.log_error(str(e), 'get_event_details')
        frappe.throw(_('Fehler beim Laden des Events: ') + str(e))
