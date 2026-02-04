import frappe


def sync_element_to_calendar(doc, method=None):
    """
    After-Save Hook: Synchronisiert Element-Änderungen mit Kalender.
    
    Wird automatisch ausgelöst, wenn ein Element gespeichert wird.
    Migrated vom UI Server-Skript "Kalender Sync".
    
    Logik:
    1. Wenn element_calendar sich ändert → alte Kalender-Einträge entfernen
    2. Neue Elementlink-Zeile in neuem Kalender einfügen/updaten
    3. Falls element_calendar leer → Element aus allen Kalendern entfernen
    """
    
    # Rekursionsschutz
    if frappe.flags.get("element_to_calendar_sync"):
        return
    
    frappe.flags.element_to_calendar_sync = True

    try:
        new_cal = doc.element_calendar
        old_cal = None
        
        # Hole vorherigen Stand
        previous = doc.get_doc_before_save()
        if previous:
            old_cal = previous.element_calendar

        # ===== 1. Alten Kalender bereinigen =====
        if old_cal and old_cal != new_cal and frappe.db.exists("Kalender", old_cal):
            cal = frappe.get_doc("Kalender", old_cal)
            
            # Finde das Link-Feld dynamisch
            link_field = "element"
            for f in frappe.get_meta("Elementlink").fields:
                if f.fieldtype == "Link" and f.options == "Element":
                    link_field = f.fieldname
                    break
            
            # Suche und entferne Zeilen
            rows_to_remove = []
            for r in cal.calendar_table:
                if r.get(link_field) == doc.name:
                    rows_to_remove.append(r)
            
            for r in rows_to_remove:
                cal.calendar_table.remove(r)
            
            if rows_to_remove:
                cal.save(ignore_permissions=True)

        # ===== 2. Neue Kalender-Verknüpfung =====
        if not new_cal:
            frappe.msgprint(
                "Element aus allen Kalendern entfernt",
                indicator="blue"
            )
        else:
            cal = frappe.get_doc("Kalender", new_cal)
            
            # Finde Link-Feld
            link_field = "element"
            for f in frappe.get_meta("Elementlink").fields:
                if f.fieldtype == "Link" and f.options == "Element":
                    link_field = f.fieldname
                    break

            # Suche existierenden Eintrag
            existing_row = None
            for r in cal.calendar_table:
                if r.get(link_field) == doc.name:
                    existing_row = r
                    break

            # Daten vorbereiten
            data = {
                "doctype": "Elementlink",
                link_field: doc.name,
                "elementlink_title": doc.element_name or doc.name,
                "elementlink_status": doc.get("status") or "",
                "elementlink_start": doc.element_start,
                "elementlink_end": doc.element_end,
            }

            # Update oder Insert
            if existing_row:
                existing_row.elementlink_title = data["elementlink_title"]
                existing_row.elementlink_status = data["elementlink_status"]
                existing_row.elementlink_start = data["elementlink_start"]
                existing_row.elementlink_end = data["elementlink_end"]
            else:
                cal.append("calendar_table", data)

            cal.save(ignore_permissions=True)

            frappe.msgprint(
                f"Mit Kalender verbunden → {new_cal}",
                indicator="green"
            )

    except Exception as e:
        frappe.log_error(str(e), "Kalender Sync Fehler")
        frappe.msgprint(
            f"Sync fehlgeschlagen: {str(e)}",
            indicator="red"
        )

    finally:
        frappe.flags.element_to_calendar_sync = False
