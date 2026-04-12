"""
CREATE, UPDATE, DELETE Events
"""

import frappe
from frappe import _
from dateutil import parser as dateutil_parser
from datetime import timedelta, datetime as _datetime
from dateutil.relativedelta import relativedelta

_DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'


def parse_iso_datetime_raw(iso_string):
    """Parse ISO UTC String – strikt validiert, kein blindes Durchleiten."""
    if not iso_string:
        return None

    try:
        iso_str = str(iso_string).strip()

        # Wenn bereits im Format "YYYY-MM-DD HH:MM:SS", strict validieren
        if ' ' in iso_str and 'T' not in iso_str:
            _datetime.strptime(iso_str, _DATETIME_FORMAT)  # wirft ValueError bei ungültigem Wert
            return iso_str

        # Parse als ISO-8601 / UTC
        dt = dateutil_parser.isoparse(iso_str)
        dt_naive = dt.replace(tzinfo=None)
        return dt_naive.strftime(_DATETIME_FORMAT)

    except Exception as e:
        frappe.log_error(f"Fehler: {str(e)}", "parse_iso_datetime_raw ERROR")
        frappe.throw(f"Ungültiges Datum: {iso_string}")




def _assert_write_access(calendar_name):
    """Wirft PermissionError wenn der aktuelle User kein Schreibrecht auf den Kalender hat."""
    from diakronos.kronos.api.permissions import get_accessible_calendars
    calendars = get_accessible_calendars()
    writable = {c["name"] for c in calendars if c.get("write")}
    if calendar_name not in writable:
        frappe.throw(_("Kein Schreibzugriff auf Kalender: {0}").format(calendar_name), frappe.PermissionError)


def _assert_read_access(calendar_name):
    """Wirft PermissionError wenn der aktuelle User kein Leserecht auf den Kalender hat."""
    from diakronos.kronos.api.permissions import get_accessible_calendars
    calendars = get_accessible_calendars()
    readable = {c["name"] for c in calendars}
    if calendar_name not in readable:
        frappe.throw(_("Kein Lesezugriff auf Kalender: {0}").format(calendar_name), frappe.PermissionError)


@frappe.whitelist()
def create_event(element_name, element_start, element_end, element_calendar,
                 all_day=False, description=None, status=None, element_category=None,
                 ressource=None, ignore_conflict=False):
    """Erstelle neues Event – Standard-Status: Vorschlag"""
    try:
        _assert_write_access(element_calendar)
        start_dt = parse_iso_datetime_raw(element_start)
        end_dt = parse_iso_datetime_raw(element_end) if element_end else start_dt

        doc = frappe.new_doc("Element")
        doc.element_name     = element_name
        doc.element_calendar = element_calendar
        doc.element_start    = start_dt
        doc.element_end      = end_dt
        doc.all_day          = int(all_day) if all_day else 0
        doc.status           = status or "Vorschlag"
        doc.description      = description or ''
        doc.element_category = element_category or ''
        doc.ressource        = ressource or ''
        doc.ignore_conflict  = int(ignore_conflict) if ignore_conflict else 0

        doc.save(ignore_permissions=True)
        frappe.db.commit()

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

        doc = frappe.get_doc("Element", name)
        _assert_write_access(doc.element_calendar)

        if element_name is not None:
            doc.element_name = element_name

        if element_start is not None:
            doc.element_start = parse_iso_datetime_raw(element_start)

        if element_end is not None:
            doc.element_end = parse_iso_datetime_raw(element_end)
        else:
            if element_start is not None:
                doc.element_end = doc.element_start

        if element_calendar is not None:
            _assert_write_access(element_calendar)
            doc.element_calendar = element_calendar

        if all_day is not None:
            doc.all_day = all_day

        if description is not None:
            doc.description = description

        if status is not None:
            doc.status = status

        doc.save(ignore_permissions=True)
        frappe.db.commit()

        return {"success": True, "id": doc.name}

    except Exception as e:
        frappe.log_error(f"{name}: {str(e)}", "update_event ERROR")
        frappe.throw(str(e))


@frappe.whitelist()
def delete_event(name):
    """Lösche Event"""
    try:
        if not name or name in ['undefined', 'null', '']:
            frappe.throw(f"Invalid ID: {name}")

        doc = frappe.get_doc("Element", name)
        _assert_write_access(doc.element_calendar)

        frappe.delete_doc("Element", name, ignore_permissions=True, force=True)
        frappe.db.commit()

        return {"success": True}

    except Exception as e:
        frappe.log_error(f"{name}: {str(e)}", "delete_event ERROR")
        frappe.throw(str(e))


@frappe.whitelist()
def save_event(name, element_name, element_start, element_end, element_calendar,
               all_day=0, description=None, status=None, element_category=None, series_id=None,
               ressource=None, ignore_conflict=None):
    """Volles Überschreiben eines Events – kein Diff, alle Felder werden gesetzt."""
    try:
        if not name or name in ['undefined', 'null', '']:
            frappe.throw(f"Invalid ID: {name}")

        doc = frappe.get_doc("Element", name)
        _assert_write_access(doc.element_calendar)

        # Leeres element_calendar bedeutet: Kalender unverändert lassen
        if not element_calendar or element_calendar in ('undefined', 'null'):
            element_calendar = doc.element_calendar
        elif element_calendar != doc.element_calendar:
            _assert_write_access(element_calendar)

        doc.element_name = element_name
        doc.element_calendar = element_calendar
        doc.element_start = parse_iso_datetime_raw(element_start)
        doc.element_end = parse_iso_datetime_raw(element_end)
        doc.all_day = int(all_day) if all_day else 0
        doc.description = description or ''
        doc.status = status or 'Festgelegt'
        doc.element_category = element_category or ''
        doc.series_id = series_id or ''
        if ressource is not None:
            doc.ressource = ressource or ''
        if ignore_conflict is not None:
            doc.ignore_conflict = int(ignore_conflict)

        frappe.flags.allow_series_edit = True
        doc.save(ignore_permissions=True)
        frappe.db.commit()

        return {"success": True, "id": doc.name}

    except Exception as e:
        frappe.log_error(f"{name}: {str(e)}", "save_event ERROR")
        frappe.throw(str(e))



@frappe.whitelist()
def create_series(element_name, element_start, element_end, element_calendar,
                  repeat_type='weekly', series_end=None, all_day=False,
                  description=None, status=None, element_category=None,
                  ressource=None, ignore_conflict=False):
    """Erstelle eine Serie wiederkehrender Termine."""
    try:
        from datetime import datetime
        _assert_write_access(element_calendar)

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
        created_ids = []
        max_events = 100  # Maximale Terminanzahl

        while created < max_events and (series_end_dt is None or current.date() <= series_end_dt.date()):
            doc = frappe.new_doc("Element")
            doc.element_name     = element_name
            doc.element_calendar = element_calendar
            doc.element_start    = current.strftime('%Y-%m-%d %H:%M:%S')
            doc.element_end      = (current + duration).strftime('%Y-%m-%d %H:%M:%S')
            doc.all_day          = int(all_day) if all_day else 0
            doc.status           = status or 'Vorschlag'
            doc.description      = description or ''
            doc.element_category = element_category or ''
            doc.ressource        = ressource or ''
            doc.ignore_conflict  = int(ignore_conflict) if ignore_conflict else 0
            doc.series_id        = series_id
            doc.repeat_this_event = 1
            doc.save(ignore_permissions=True)
            created_ids.append(doc.name)
            created += 1
            current = advance(current)

        frappe.db.commit()
        return {"success": True, "series_id": series_id, "created_count": created, "created_ids": created_ids}

    except Exception as e:
        frappe.log_error(str(e), "create_series ERROR")
        frappe.throw(str(e))
