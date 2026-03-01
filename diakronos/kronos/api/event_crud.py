"""
CREATE, UPDATE, DELETE Events
"""

import frappe
from frappe import _
from dateutil import parser as dateutil_parser
from datetime import timedelta
from dateutil.relativedelta import relativedelta


def parse_iso_datetime_raw(iso_string):
    """Parse ISO UTC String"""
    if not iso_string:
        return None
    
    try:
        iso_str = str(iso_string).strip()
        
        # Wenn bereits im Format "YYYY-MM-DD HH:MM:SS", nutze direkt
        if ' ' in iso_str and 'T' not in iso_str:
            return iso_str
        
        # Parse als UTC
        dt = dateutil_parser.isoparse(iso_str)
        dt_naive = dt.replace(tzinfo=None)
        result = dt_naive.strftime('%Y-%m-%d %H:%M:%S')
        
        frappe.log_error(f"parse_iso_datetime_raw: '{iso_string}' → '{result}'", "parse_iso_datetime_raw")
        return result
        
    except Exception as e:
        frappe.log_error(f"Fehler: {str(e)}", "parse_iso_datetime_raw ERROR")
        frappe.throw(f"Ungültiges Datum: {iso_string}")



@frappe.whitelist()
def get_events(start, end):
    """event_get_with_calendar_color_join: Holt Events mit Farbe aus übergeordnetem Kalender."""
    events = frappe.db.sql("""
        SELECT
            elem.name AS id,
            elem.element_name AS title,
            elem.element_start AS start,
            elem.element_end AS end,
            elem.all_day,
            COALESCE(kal.calendar_color, elem.element_color, '#007bff') AS color  -- Priorisiert calendar_color, Fallback zu element_color oder Blau
        FROM `tabElement` elem
        LEFT JOIN `tabKalender` kal ON kal.name = elem.element_calendar
        WHERE elem.element_start >= %(start)s
          AND elem.element_end <= %(end)s
    """, {'start': start, 'end': end}, as_dict=True)
    
    # events_color_debug_log: Logge für Debugging (entferne in Prod)
    frappe.log_error(f"Events fetched: {len(events)}, Sample color: {events[0]['color'] if events else 'None'}", "event_get_debug")
    
    return events

@frappe.whitelist()
def create_event(element_name, element_start, element_end, element_calendar,
                 all_day=False, description=None, status=None, element_category=None):
    """Erstelle neues Event"""
    try:
        start_dt = parse_iso_datetime_raw(element_start)
        end_dt = parse_iso_datetime_raw(element_end) if element_end else start_dt

        doc = frappe.new_doc("Element")
        doc.element_name     = element_name
        doc.element_calendar = element_calendar
        doc.element_start    = start_dt
        doc.element_end      = end_dt
        doc.all_day          = int(all_day) if all_day else 0
        doc.status           = status or "Festgelegt"
        doc.description      = description or ''
        doc.element_category = element_category or ''

        doc.save(ignore_permissions=True)
        frappe.db.commit()

        frappe.log_error(f'✅ Event erstellt: {doc.name}', "create_event")
        return {"success": True, "id": doc.name}

    except Exception as e:
        frappe.log_error(str(e), "create_event ERROR")
        frappe.throw(str(e))


@frappe.whitelist()
def update_event(name, element_name=None, element_start=None, element_end=None,
                 element_calendar=None, all_day=None, description=None, status=None):
    """Update existierendes Event"""
    try:
        if not name or name in ['undefined', 'null', '']:
            frappe.throw(f"Invalid ID: {name}")
        
        frappe.log_error(f'🔧 Updating Event {name}:', "update_event")
        
        doc = frappe.get_doc("Element", name)
        
        if element_name is not None:
            doc.element_name = element_name
            frappe.log_error(f'  - element_name: {element_name}', "update_event")
        
        if element_start is not None:
            parsed_start = parse_iso_datetime_raw(element_start)
            doc.element_start = parsed_start
            frappe.log_error(f'  - element_start: {element_start} → {parsed_start}', "update_event")
        
        if element_end is not None:
            parsed_end = parse_iso_datetime_raw(element_end)
            doc.element_end = parsed_end
            frappe.log_error(f'  - element_end: {element_end} → {parsed_end}', "update_event")
        else:
            if element_start is not None:
                doc.element_end = doc.element_start
        
        if element_calendar is not None:
            doc.element_calendar = element_calendar
            frappe.log_error(f'  - element_calendar: {element_calendar}', "update_event")
        
        if all_day is not None:
            doc.all_day = all_day
        
        if description is not None:
            doc.description = description
        
        if status is not None:
            doc.status = status
        
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        
        frappe.log_error(f'✅ Event gespeichert: {doc.name}', "update_event")
        
        return {"success": True, "id": doc.name}
        
    except Exception as e:
        frappe.log_error(f'❌ {str(e)}', "update_event ERROR")
        frappe.throw(str(e))


@frappe.whitelist()
def delete_event(name):
    """Lösche Event"""
    try:
        if not name or name in ['undefined', 'null', '']:
            frappe.throw(f"Invalid ID: {name}")
        
        frappe.delete_doc("Element", name, ignore_permissions=True, force=True)
        frappe.db.commit()
        
        frappe.log_error(f'✅ Event gelöscht: {name}', "delete_event")
        return {"success": True}
        
    except Exception as e:
        frappe.log_error(str(e), "delete_event ERROR")
        frappe.throw(str(e))


@frappe.whitelist()
def save_event(name, element_name, element_start, element_end, element_calendar,
               all_day=0, description=None, status=None, element_category=None, series_id=None):
    """Volles Überschreiben eines Events – kein Diff, alle Felder werden gesetzt."""
    try:
        if not name or name in ['undefined', 'null', '']:
            frappe.throw(f"Invalid ID: {name}")

        doc = frappe.get_doc("Element", name)
        doc.element_name = element_name
        doc.element_calendar = element_calendar
        doc.element_start = parse_iso_datetime_raw(element_start)
        doc.element_end = parse_iso_datetime_raw(element_end)
        doc.all_day = int(all_day) if all_day else 0
        doc.description = description or ''
        doc.status = status or 'Festgelegt'
        doc.element_category = element_category or ''
        doc.series_id = series_id or ''  # Leer = aus Serie gelöst

        frappe.flags.allow_series_edit = True
        doc.save(ignore_permissions=True)
        frappe.db.commit()

        frappe.log_error(f'✅ Event gespeichert (save_event): {doc.name}', "save_event")
        return {"success": True, "id": doc.name}

    except Exception as e:
        frappe.log_error(f'❌ {str(e)}', "save_event ERROR")
        frappe.throw(str(e))


@frappe.whitelist()
def get_event_details(name):
    """Hole Event Details"""
    try:
        if not name or name in ['undefined', 'null']:
            frappe.throw(f"Invalid ID: {name}")
        
        element = frappe.get_doc("Element", name)
        return {
            'name': element.name,
            'element_name': element.element_name,
            'element_start': str(element.element_start),
            'element_end': str(element.element_end),
            'element_calendar': element.element_calendar,
            'all_day': element.all_day or 0,
            'status': element.status or 'Festgelegt',
            'description': element.description or '',
            'element_color': element.element_color or '#007bff',
            'repeat_this_event': element.repeat_this_event or 0,
            'series_id': element.series_id or None
        }
    except Exception as e:
        frappe.log_error(str(e), "get_event_details ERROR")
        frappe.throw(str(e))


@frappe.whitelist()
def create_series(element_name, element_start, element_end, element_calendar,
                  repeat_type='weekly', series_end=None, all_day=False,
                  description=None, status=None, element_category=None):
    """Erstelle eine Serie wiederkehrender Termine."""
    try:
        from datetime import datetime

        start_str = parse_iso_datetime_raw(element_start)
        end_str   = parse_iso_datetime_raw(element_end) if element_end else start_str

        start_dt = datetime.strptime(start_str, '%Y-%m-%d %H:%M:%S')
        end_dt   = datetime.strptime(end_str,   '%Y-%m-%d %H:%M:%S')
        duration = end_dt - start_dt

        if series_end:
            series_end_dt = datetime.strptime(series_end[:10], '%Y-%m-%d')
        else:
            series_end_dt = None  # Nur max_events begrenzt

        # Schrittweite je Typ
        steps = {
            'daily':   lambda d: d + timedelta(days=1),
            'weekly':  lambda d: d + timedelta(weeks=1),
            'monthly': lambda d: d + relativedelta(months=1),
            'yearly':  lambda d: d + relativedelta(years=1),
        }
        advance = steps.get(repeat_type, steps['weekly'])

        series_id = frappe.generate_hash(length=12)
        current = start_dt
        created = 0
        max_events = 100  # Maximale Terminanzahl

        while created < max_events and (series_end_dt is None or current.date() <= series_end_dt.date()):
            doc = frappe.new_doc("Element")
            doc.element_name     = element_name
            doc.element_calendar = element_calendar
            doc.element_start    = current.strftime('%Y-%m-%d %H:%M:%S')
            doc.element_end      = (current + duration).strftime('%Y-%m-%d %H:%M:%S')
            doc.all_day          = int(all_day) if all_day else 0
            doc.status           = status or 'Festgelegt'
            doc.description      = description or ''
            doc.element_category = element_category or ''
            doc.series_id        = series_id
            doc.repeat_this_event = 1
            doc.save(ignore_permissions=True)
            created += 1
            current = advance(current)

        frappe.db.commit()
        frappe.log_error(f'✅ Serie erstellt: {series_id}, {created} Termine', "create_series")
        return {"success": True, "series_id": series_id, "created_count": created}

    except Exception as e:
        frappe.log_error(str(e), "create_series ERROR")
        frappe.throw(str(e))
