# diakronos/kronos/api/series_create.py
"""
CREATE Wiederkehrende Events (Serien)
Generiert automatische Serien-Instanzen basierend auf repeat_this_event
"""

import frappe
from frappe.utils import get_datetime


@frappe.whitelist()
def create_event_series(series_element_id):
    """
    Erstelle Serie-Instanzen wenn repeat_this_event=True
    
    Args:
        series_element_id: Element name (ID) der Haupt-Serie
    
    Returns:
        Dict mit success, generated_count und message
    """
    try:
        element_doc = frappe.get_doc("Element", series_element_id)
        if not element_doc.get("repeat_this_event"):
            return {"success": True, "message": "Kein Serientermin"}
        repeat_pattern = element_doc.get("repeat_on", "Weekly")
        repeat_till = element_doc.get("repeat_till")
        weekdays = {
            "monday": element_doc.get("monday"),
            "tuesday": element_doc.get("tuesday"),
            "wednesday": element_doc.get("wednesday"),
            "thursday": element_doc.get("thursday"),
            "friday": element_doc.get("friday"),
            "saturday": element_doc.get("saturday"),
            "sunday": element_doc.get("sunday")
        }
        start_dt = get_datetime(element_doc.get("element_start"))
        end_dt = get_datetime(element_doc.get("element_end"))
        if repeat_till:
            series_end = get_datetime(repeat_till)
        else:
            from datetime import timedelta
            series_end = start_dt + timedelta(days=365)
        instances = generate_series_instances(
            element_doc,
            start_dt,
            end_dt,
            series_end,
            repeat_pattern,
            weekdays
        )
        return {
            "success": True,
            "generated_count": len(instances),
            "message": f"{len(instances)} Serie-Instanzen generiert"
        }
    except Exception as e:
        frappe.log_error(f"Fehler bei Serie-Erstellung: {str(e)}", "Series Create Error")
        frappe.throw(f"Fehler bei Serie-Erstellung: {str(e)}")


def generate_series_instances(element_doc, start_dt, end_dt, series_end, pattern, weekdays):
    """
    Generiere tatsächliche Event-Instanzen basierend auf Pattern
    
    Args:
        element_doc: Element DocType
        start_dt: Start datetime
        end_dt: End datetime
        series_end: Series end datetime
        pattern: Repeat pattern (Daily, Weekly, Monthly, etc)
        weekdays: Dict mit Wochentags-Flags
    
    Returns:
        List von erstellten Instanz-IDs
    """
    from datetime import timedelta
    instances = []
    current_dt = start_dt
    day_names = [
        "monday", "tuesday", "wednesday", "thursday",
        "friday", "saturday", "sunday"
    ]
    while current_dt <= series_end:
        should_create = False
        if pattern == "Daily":
            should_create = True
        elif pattern == "Weekly":
            weekday_name = day_names[current_dt.weekday()]
            should_create = weekdays.get(weekday_name, False)
        elif pattern == "Monthly":
            if current_dt.day == start_dt.day:
                should_create = True
        elif pattern == "Quarterly":
            months_diff = (current_dt.year - start_dt.year) * 12 + (
                current_dt.month - start_dt.month
            )
            if months_diff % 3 == 0 and current_dt.day == start_dt.day:
                should_create = True
        elif pattern == "Half Yearly":
            months_diff = (current_dt.year - start_dt.year) * 12 + (
                current_dt.month - start_dt.month
            )
            if months_diff % 6 == 0 and current_dt.day == start_dt.day:
                should_create = True
        elif pattern == "Yearly":
            if current_dt.month == start_dt.month and current_dt.day == start_dt.day:
                should_create = True
        if should_create and current_dt <= series_end:
            duration = end_dt - start_dt
            instance_end_dt = current_dt + duration
            try:
                doc = frappe.new_doc("Element")
                doc.element_name = element_doc.get("element_name")
                doc.element_calendar = element_doc.get("element_calendar")
                doc.element_start = current_dt
                doc.element_end = instance_end_dt
                doc.all_day = element_doc.get("all_day", False)
                doc.status = element_doc.get("status", "Festgelegt")
                doc.description = element_doc.get("description", "")
                doc.series_id = element_doc.get("name")
                doc.save(ignore_permissions=True)
                instances.append(doc.name)
            except Exception as e:
                frappe.log_error(
                    f"Fehler bei Instanz-Generierung: {str(e)}",
                    "Series Generate Error"
                )
        current_dt += timedelta(days=1)
    frappe.db.commit()
    return instances
