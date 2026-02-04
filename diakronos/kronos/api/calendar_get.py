# diakronos/kronos/api/calendar_get.py

import frappe
from frappe import _
from datetime import datetime
import json
from .permissions import has_calendar_permission


@frappe.whitelist()
def get_calendar_events(start_date, end_date, calendar_filter=None):
    """
    Gibt alle Events im angeforderten Zeitraum.
    ✅ KEIN Cache - FullCalendar ruft sowieso bei jedem View-Wechsel auf!
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
        writable_calendars = []
        
        for cal in all_calendars:
            if has_calendar_permission(cal['name'], 'read'):
                accessible_calendars.append(cal['name'])
            if has_calendar_permission(cal['name'], 'write'):
                writable_calendars.append(cal['name'])

        # Wenn Filter, dann nur gefilterte die auch zugänglich sind
        if calendars_to_show:
            show_calendars = [c for c in calendars_to_show if c in accessible_calendars]
        else:
            show_calendars = accessible_calendars

        if not show_calendars:
            return []

        # ✅ Hole DIREKT aus DB - NUR für angeforderten Zeitraum
        frappe.log_error(f'📅 Loading events: {start_date} → {end_date}', "get_calendar_events")
        
        elements = frappe.get_all(
            'Element',
            filters=[
                ['element_calendar', 'in', show_calendars],
                ['element_start', '<=', end_date + ' 23:59:59'],
                ['element_end', '>=', start_date + ' 00:00:00'],
                ['docstatus', '!=', 2]
            ],
            fields=[
                'name',
                'element_name',
                'element_start',
                'element_end',
                'all_day',
                'description',
                'element_color',
                'status',
                'element_calendar',
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
            'Festgelegt': None,
            'Vorschlag': '#FEF3C7',
            'Konflikt': '#FEE2E2'
        }

        # Formatiere für FullCalendar
        formatted = []
        for elem in elements:
            try:
                status = elem.get('status', 'Festgelegt')
                if status in ['Vorschlag', 'Konflikt']:
                    cal_id = elem.get('element_calendar')
                    if cal_id not in writable_calendars:
                        continue

                color = STATUS_COLORS.get(status)
                if not color:
                    color = calendar_colors.get(elem.get('element_calendar'), '#007bff')

                start_str = str(elem.get('element_start', ''))
                end_str = str(elem.get('element_end', ''))

                if not start_str or not end_str:
                    continue

                # ✅ SIMPLE: Konvertiere zu ISO (FullCalendar mag das)
                try:
                    start_dt = datetime.strptime(start_str, '%Y-%m-%d %H:%M:%S')
                    end_dt = datetime.strptime(end_str, '%Y-%m-%d %H:%M:%S')
                    
                    start_iso = start_dt.isoformat()
                    end_iso = end_dt.isoformat()
                except Exception as e:
                    frappe.log_error(f"Fehler bei Konvertierung {elem.get('name')}: {str(e)}", "calendar_get_error")
                    start_iso = start_str.replace(' ', 'T')
                    end_iso = end_str.replace(' ', 'T')

                event = {
                    'id': elem.get('name'),
                    'title': elem.get('element_name', 'Untitled'),
                    'start': start_iso,
                    'end': end_iso,
                    'isAllday': bool(elem.get('all_day')),
                    'color': color,
                    'backgroundColor': color,
                    'borderColor': color,
                    'calendar': elem.get('element_calendar'),
                    'status': status,
                    'description': elem.get('description', ''),
                    'canEdit': elem.get('owner') == user or elem.get('element_calendar') in writable_calendars
                }
                formatted.append(event)

            except Exception as e:
                frappe.log_error(f'Error formatting event {elem.get("name")}: {str(e)}', "calendar_get_format_error")
                continue

        frappe.log_error(f'✅ {len(formatted)} events loaded', "get_calendar_events")
        return formatted

    except Exception as e:
        frappe.log_error(str(e), 'get_calendar_events ERROR')
        frappe.throw(_('Fehler beim Laden der Termine: ') + str(e))


@frappe.whitelist()
def get_accessible_calendars():
    """Gibt alle zugänglichen Kalender zurück"""
    try:
        user = frappe.session.user
        if not user or user == "Guest":
            frappe.throw(_("Sie müssen angemeldet sein."))
        
        calendars = frappe.get_all(
            'Kalender',
            fields=['name', 'calendar_name as title', 'calendar_color as color'],
            order_by='calendar_name asc'
        )
        
        accessible = []
        for cal in calendars:
            if has_calendar_permission(cal['name'], 'read'):
                accessible.append({
                    'name': cal['name'],
                    'title': cal['title'],
                    'color': cal['color'] or '#007bff'
                })
        
        return accessible
        
    except Exception as e:
        frappe.log_error(str(e), 'get_accessible_calendars ERROR')
        frappe.throw(_('Fehler beim Laden der Kalender: ') + str(e))
