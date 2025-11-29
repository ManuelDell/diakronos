# apps/diakronos/diakronos/kronos/series_handler.py
import frappe
from frappe import _


@frappe.whitelist()
def update_series_batch(series_id: str, updates: dict):
    if not series_id or not isinstance(updates, dict):
        frappe.throw(_("Series ID und Updates erforderlich"))

    allowed_fields = {"element_name", "element_category", "status"}
    invalid_fields = set(updates.keys()) - allowed_fields
    if invalid_fields:
        frappe.throw(_("Nicht erlaubte Felder: {}").format(", ".join(invalid_fields)))

    elements = frappe.get_all(
        "Element",
        filters={"series_id": series_id},
        fields=["name"],
        limit_page_length=0
    )

    if not elements:
        frappe.throw(_("Keine Elemente für Serie {0} gefunden").format(series_id))

    updated_count = 0
    for elem in elements:
        try:
            frappe.db.set_value("Element", elem.name, updates, ignore_permissions=True)
            updated_count += 1
        except Exception as e:
            frappe.log_error(f"Update Fehler {elem.name}: {str(e)}", "Series Update")

    frappe.db.commit()
    return {"success": True, "updated_count": updated_count}


@frappe.whitelist()
def delete_series_batch(series_id: str):
    if not series_id:
        frappe.throw(_("Series ID erforderlich"))

    # 1. Alle Elemente der Serie holen
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
            # 2. Falls Element einen Kalender hat → Kind-Eintrag aus Kalender.calendar_table entfernen
            if elem.element_calendar:
                cal_doc = frappe.get_doc("Kalender", elem.element_calendar)

                # Finde die Zeile(n) mit diesem Element
                rows_to_remove = [
                    row for row in cal_doc.calendar_table
                    if row.element == elem.name
                ]

                # Entferne sie
                for row in rows_to_remove:
                    cal_doc.get("calendar_table").remove(row)

                # Speichere den Kalender (ohne Validierung, sonst wieder Fehler)
                cal_doc.save(ignore_permissions=True, ignore_version=True)

            # 3. Jetzt das Element selbst löschen
            frappe.delete_doc(
                "Element",
                elem.name,
                ignore_permissions=True,
                ignore_missing=True,
                delete_permanently=True,
                force=True  # WICHTIG: überschreibt before_delete, on_trash etc.
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