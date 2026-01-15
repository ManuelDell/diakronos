# diakronos/kronos/api/series_update.py
"""
UPDATE Wiederkehrende Events (Serien)
Batch-Updates für alle Elemente einer Serie
"""

import frappe
from frappe import _
import json


@frappe.whitelist()
def update_series_batch_fast(series_id, updates):
    """Schneller Update aller Elemente einer Serie via SQL."""
    
    if isinstance(updates, str):
        updates = json.loads(updates)
    
    if not series_id:
        frappe.throw("Series ID fehlt")
    
    if not updates or not isinstance(updates, dict):
        frappe.throw("Updates müssen ein Dictionary sein")

    allowed = {
        "element_name",
        "event_category_name",
        "status",
        "element_color",
        "element_start",
        "element_end"
    }

    invalid = set(updates) - allowed
    if invalid:
        frappe.throw(f"Nicht erlaubte Felder: {', '.join(invalid)}")

    set_parts = [f"`{field}` = %s" for field in updates.keys()]
    values = list(updates.values())
    values.append(series_id)

    frappe.db.sql(
        f"""
        UPDATE `tabElement`
        SET {', '.join(set_parts)}, modified = NOW()
        WHERE series_id = %s
        """,
        values
    )
    frappe.db.commit()

    count = frappe.db.count("Element", {"series_id": series_id})

    return {
        "success": True,
        "updated_count": count
    }


@frappe.whitelist()
def delete_series_batch(series_id):
    """Löscht alle Elemente einer Serie."""
    if not series_id:
        frappe.throw(_("Series ID erforderlich"))

    elements = frappe.get_all(
        "Element",
        filters={"series_id": series_id},
        fields=["name", "element_calendar"]
    )

    if not elements:
        frappe.throw(_("Keine Elemente für Serie {0} gefunden").format(series_id))

    deleted_count = 0
    for elem in elements:
        try:
            if elem.element_calendar:
                cal_doc = frappe.get_doc("Kalender", elem.element_calendar)

                rows_to_remove = [
                    row for row in cal_doc.calendar_table
                    if row.element == elem.name
                ]

                for row in rows_to_remove:
                    cal_doc.calendar_table.remove(row)

                if rows_to_remove:
                    cal_doc.save(ignore_permissions=True, ignore_version=True)

            frappe.delete_doc(
                "Element",
                elem.name,
                ignore_permissions=True,
                ignore_missing=True,
                delete_permanently=True,
                force=True
            )
            deleted_count += 1

        except Exception as e:
            frappe.log_error(
                f"Fehler beim Löschen von {elem.name}: {str(e)}",
                "Series Delete Error"
            )

    frappe.db.commit()
    return {
        "success": True,
        "deleted_count": deleted_count,
        "message": _("{0} Termine gelöscht").format(deleted_count)
    }
