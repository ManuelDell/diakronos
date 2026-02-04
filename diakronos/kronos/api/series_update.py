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
def delete_series_batch_fast(series_id):
    """Löscht alle Elemente einer Serie."""
    if not series_id:
        frappe.throw(_("Series ID erforderlich"))
    
    print(f"🗑️ DELETE SERIES: {series_id}")
    
    # 🔍 FIND ALL ELEMENTS
    elements = frappe.get_all(
        "Element",
        filters={"series_id": series_id},
        fields=["name", "element_calendar"]
    )
    
    print(f"🔍 Gefundene Elemente: {len(elements)}")
    for e in elements:
        print(f"   - {e.name} (Kalender: {e.element_calendar})")
    
    # ✅ WENN NICHTS GEFUNDEN: Trotzdem erfolgreich zurück (keine Serie vorhanden)
    if not elements:
        print("⚠️ Keine Elemente gefunden für Serie")
        return {
            "success": True,
            "deleted_count": 0,
            "message": _("Keine Termine in dieser Serie gefunden")
        }
    
    deleted_count = 0
    
    for elem in elements:
        try:
            print(f"🗑️ Lösche Element: {elem.name}")
            
            # Entferne aus Kalender
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
                        print(f"   ✅ Aus Kalender entfernt")
                except Exception as cal_error:
                    print(f"   ⚠️ Kalender-Fehler: {cal_error}")
            
            # Lösche Element
            frappe.delete_doc(
                "Element",
                elem.name,
                ignore_permissions=True,
                ignore_missing=True,
                delete_permanently=True,
                force=True
            )
            deleted_count += 1
            print(f"   ✅ Element gelöscht")
        
        except Exception as e:
            print(f"❌ Fehler beim Löschen von {elem.name}: {str(e)}")
            frappe.log_error(
                f"Fehler beim Löschen von {elem.name}: {str(e)}",
                "Series Delete Error"
            )
    
    frappe.db.commit()
    
    print(f"✅ FERTIG: {deleted_count} Termine gelöscht")
    
    return {
        "success": True,
        "deleted_count": deleted_count,
        "message": _("{0} Termine gelöscht").format(deleted_count)
    }
