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
    from diakronos.kronos.api.event_crud import _assert_write_access

    if isinstance(updates, str):
        updates = json.loads(updates)

    if not series_id:
        frappe.throw("Series ID fehlt")

    first_calendar = frappe.get_value("Element", {"series_id": series_id}, "element_calendar")
    if not first_calendar:
        frappe.throw(_("Serie nicht gefunden: {0}").format(series_id))
    _assert_write_access(first_calendar)
    
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

    # Sicherheitshinweis: Feldnamen werden per f-String in den SQL-String eingebaut.
    # Das ist sicher weil:
    #   1. Die Whitelist oben jeden Feldnamen prüft und bei Abweichung frappe.throw() auslöst.
    #   2. Feldnamen in Backticks gesetzt → Column-Name-Injection verhindert.
    #   3. Alle Werte via %s parametrisiert → keine Wert-Injection möglich.
    # Der Batch-UPDATE bleibt aus Performance-Gründen (ein SQL statt N einzelner Aufrufe).
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
def delete_future_series_events(series_id, from_date):
    """Löscht alle Elemente einer Serie ab einem bestimmten Datum (inkl. diesem Datum)."""
    from diakronos.kronos.api.event_crud import _assert_write_access

    if not series_id:
        frappe.throw(_("Series ID erforderlich"))
    if not from_date:
        frappe.throw(_("Startdatum erforderlich"))

    first_calendar = frappe.get_value("Element", {"series_id": series_id}, "element_calendar")
    if not first_calendar:
        frappe.throw(_("Serie nicht gefunden: {0}").format(series_id))
    _assert_write_access(first_calendar)

    elements = frappe.get_all(
        "Element",
        filters={"series_id": series_id, "element_start": [">=", from_date]},
        fields=["name", "element_calendar"]
    )

    if not elements:
        return {"success": True, "deleted_count": 0}

    deleted_count = 0
    for elem in elements:
        try:
            if elem.element_calendar:
                try:
                    cal_doc = frappe.get_doc("Kalender", elem.element_calendar)
                    rows_to_remove = [r for r in cal_doc.calendar_table if r.element == elem.name]
                    for row in rows_to_remove:
                        cal_doc.calendar_table.remove(row)
                    if rows_to_remove:
                        cal_doc.save(ignore_permissions=True, ignore_version=True)
                except Exception:
                    pass
            frappe.delete_doc("Element", elem.name, ignore_permissions=True,
                              ignore_missing=True, delete_permanently=True, force=True)
            deleted_count += 1
        except Exception as e:
            frappe.log_error(f"Fehler beim Löschen von {elem.name}: {str(e)}", "Series Delete Future Error")

    frappe.db.commit()
    return {"success": True, "deleted_count": deleted_count}


@frappe.whitelist()
def delete_series_batch_fast(series_id):
    """Löscht alle Elemente einer Serie."""
    from diakronos.kronos.api.event_crud import _assert_write_access

    if not series_id:
        frappe.throw(_("Series ID erforderlich"))

    first_calendar = frappe.get_value("Element", {"series_id": series_id}, "element_calendar")
    if not first_calendar:
        frappe.throw(_("Serie nicht gefunden: {0}").format(series_id))
    _assert_write_access(first_calendar)
    
    elements = frappe.get_all(
        "Element",
        filters={"series_id": series_id},
        fields=["name", "element_calendar"]
    )

    if not elements:
        return {
            "success": True,
            "deleted_count": 0,
            "message": _("Keine Termine in dieser Serie gefunden")
        }

    deleted_count = 0

    for elem in elements:
        try:
            if elem.element_calendar:
                try:
                    cal_doc = frappe.get_doc("Kalender", elem.element_calendar)
                    rows_to_remove = [
                        row for row in cal_doc.calendar_table
                        if row.element == elem.name
                    ]
                    for row in rows_to_remove:
                        cal_doc.calendar_table.remove(row)
                    if rows_to_remove:
                        cal_doc.save(ignore_permissions=True, ignore_version=True)
                except Exception as cal_error:
                    frappe.log_error(f"Kalender-Fehler bei {elem.name}: {cal_error}", "Series Delete Calendar Error")

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
            frappe.log_error(f"Fehler beim Löschen von {elem.name}: {str(e)}", "Series Delete Error")
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
