"""
CREATE, UPDATE, DELETE Events
"""

import frappe
from frappe import _
from dateutil import parser as dateutil_parser


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
def create_event(element_name, element_start, element_end, element_calendar,
                 all_day=False, description=None, status=None):
    """Erstelle neues Event"""
    try:
        start_dt = parse_iso_datetime_raw(element_start)
        end_dt = parse_iso_datetime_raw(element_end) if element_end else start_dt
        
        doc = frappe.new_doc("Element")
        doc.element_name = element_name
        doc.element_calendar = element_calendar
        doc.element_start = start_dt
        doc.element_end = end_dt
        doc.all_day = all_day if all_day else 0
        doc.status = status or "Festgelegt"
        
        if description:
            doc.description = description
        
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
