# diakronos/kronos/api/events.py - FINAL mit Permissions & Caching

import frappe
from frappe import _
from datetime import datetime
import json
from .permissions import has_calendar_permission

# ✅ In-Memory Cache für Events (pro Session)
_events_cache = {}

@frappe.whitelist()
def get_calendar_events(start_date, end_date, calendar_filter=None):
    """
    Gibt alle Events im Zeitraum mit 2-Jahres-Caching.
    Status-Visibilität nach Permissions (nur Schreibrecht sieht Konflikt/Vorschlag).
    
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
            frappe.logger().warning(f'No accessible calendars for user {user}')
            return []

        # ✅ CACHE-KEY mit 2-Jahres-Fenster berechnen
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        year_start = start_dt.year
        
        # Bestimme Cache-Fenster (2 Jahre auf einmal)
        cache_start = datetime(year_start, 1, 1)
        cache_end = datetime(year_start + 2, 12, 31)
        cache_key = f"{user}_{cache_start.strftime('%Y-%m-%d')}_{cache_end.strftime('%Y-%m-%d')}"

        # ✅ Prüfe Cache
        if cache_key not in _events_cache:
            frappe.logger().info(f'💾 Lade 2-Jahres-Cache: {cache_key}')
            
            # ✅ KORRIGIERTE FILTER für Events die sich über Tage spannen
            elements = frappe.get_all(
                'Element',
                filters=[
                    ['element_calendar', 'in', show_calendars],
                    ['element_start', '<=', cache_end.strftime('%Y-%m-%d') + ' 23:59:59'],
                    ['element_end', '>=', cache_start.strftime('%Y-%m-%d') + ' 00:00:00'],
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
                'Festgelegt': None,      # → Kalender-Farbe
                'Vorschlag': '#FEF3C7',  # Sanftes Gelb
                'Konflikt': '#FEE2E2'    # Sanftes Rot
            }

            # Formatiere für TUI-Calendar
            formatted = []
            for elem in elements:
                try:
                    # ✅ PERMISSIONS CHECK: Nur Schreibrecht sieht Konflikt/Vorschlag
                    status = elem.get('status', 'Festgelegt')
                    if status in ['Vorschlag', 'Konflikt']:
                        cal_id = elem.get('element_calendar')
                        if cal_id not in writable_calendars:
                            # Benutzer hat nur Lesrecht → Skip diese Events
                            continue

                    # Bestimme Farbe: Status-Farbe OR Kalender-Farbe
                    color = STATUS_COLORS.get(status)
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
                        'status': status,
                        'description': elem.get('description', ''),
                        'canEdit': elem.get('owner') == user or elem.get('element_calendar') in writable_calendars
                    }
                    formatted.append(event)

                except Exception as e:
                    frappe.logger().warning(f'Error formatting event {elem.get("name")}: {str(e)}')
                    continue

            _events_cache[cache_key] = formatted
            frappe.logger().info(f'✅ Cache gespeichert: {len(formatted)} events')
        
        # ✅ Filter aus Cache für angeforderten Zeitraum
        cached_events = _events_cache[cache_key]
        requested_start = datetime.fromisoformat(start_date + 'T00:00:00')
        requested_end = datetime.fromisoformat(end_date + 'T23:59:59')
        
        filtered = [
            e for e in cached_events
            if (
                datetime.fromisoformat(e['start']) <= requested_end and
                datetime.fromisoformat(e['end']) >= requested_start
            )
        ]

        frappe.logger().info(f'✅ get_calendar_events: {len(filtered)}/{len(cached_events)} events from cache')
        return filtered

    except Exception as e:
        frappe.log_error(str(e), 'get_calendar_events')
        frappe.throw(_('Fehler beim Laden der Termine: ') + str(e))


@frappe.whitelist()
def clear_events_cache():
    """
    Löscht den Event-Cache (bei neuen Events).
    """
    global _events_cache
    _events_cache = {}
    frappe.logger().info('✅ Events cache cleared')
    return {'success': True}
