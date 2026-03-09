# diakronos/kronos/api/series_handler.py
"""
Series Handler - Backend für Serientermin-Verwaltung
Behandelt alle Aktionen die von KronosModal.showSmartEditDialog() aufgerufen werden
"""

import frappe
from frappe.utils import get_datetime
from datetime import datetime, timedelta

# ═══════════════════════════════════════════════════════════════
# 🗑️ REMOVE FROM SERIES
# ═══════════════════════════════════════════════════════════════

@frappe.whitelist()
def remove_event_from_series(element_name, parent_series):
    """
    Entfernt Event aus Serie - wird zu eigenständigem Event
    """
    try:
        element = frappe.get_doc('Element', element_name)
        
        # Entferne Serie-Referenzen
        element.repeat_this_event = 0
        element.parent_series = None
        element.is_series_exception = 1
        
        element.save()
        frappe.db.commit()
        
        frappe.log_error(f"✅ Event {element_name} aus Serie entfernt", "Series Handler")
        
        return {
            "status": "success",
            "message": "Termin aus Serie entfernt"
        }
    except Exception as e:
        frappe.log_error(f"❌ Fehler beim Entfernen: {str(e)}", "Series Handler Error")
        frappe.throw(f"❌ Fehler beim Entfernen: {str(e)}")


# ═══════════════════════════════════════════════════════════════
# ✏️ EDIT SERIES (alle Termine)
# ═══════════════════════════════════════════════════════════════

@frappe.whitelist()
def edit_series_all(parent_series, update_data):
    """
    Bearbeitet ALLE Events der Serie
    Update-Daten kommen als dict
    """
    try:
        # Konvertiere update_data wenn als String
        if isinstance(update_data, str):
            import json
            update_data = json.loads(update_data)
        
        # Finde alle Events dieser Serie
        events = frappe.get_list(
            'Element',
            filters={'parent_series': parent_series, 'is_series_exception': 0},
            pluck='name'
        )
        
        count = 0
        for event_name in events:
            element = frappe.get_doc('Element', event_name)
            
            # Update nur die übergebenen Felder
            for key, value in update_data.items():
                if hasattr(element, key) and value is not None:
                    setattr(element, key, value)
            
            element.save()
            count += 1
        
        frappe.db.commit()
        
        frappe.log_error(f"✅ {count} Events in Serie {parent_series} aktualisiert", "Series Handler")
        
        return {
            "status": "success",
            "count": count,
            "message": f"{count} Termine aktualisiert"
        }
    except Exception as e:
        frappe.log_error(f"❌ Fehler beim Aktualisieren der Serie: {str(e)}", "Series Handler Error")
        frappe.throw(f"❌ Fehler beim Aktualisieren der Serie: {str(e)}")


# ═══════════════════════════════════════════════════════════════
# ➡️ EDIT SERIES ONWARDS (ab hier)
# ═══════════════════════════════════════════════════════════════

@frappe.whitelist()
def edit_series_onwards(element_name, parent_series, update_data):
    """
    Bearbeitet ab DIESEM Event alle nachfolgenden
    """
    try:
        # Konvertiere update_data wenn als String
        if isinstance(update_data, str):
            import json
            update_data = json.loads(update_data)
        
        # Hole das aktuelle Element
        current_element = frappe.get_doc('Element', element_name)
        current_start = get_datetime(current_element.element_start)
        
        # Finde alle Events NACH diesem Datum (auch Exceptions!)
        events = frappe.get_list(
            'Element',
            filters=[
                ['parent_series', '=', parent_series],
                ['element_start', '>=', current_start],
            ],
            pluck='name',
            order_by='element_start asc'
        )
        
        count = 0
        for event_name in events:
            element = frappe.get_doc('Element', event_name)
            
            # Update nur die übergebenen Felder
            for key, value in update_data.items():
                if hasattr(element, key) and value is not None:
                    setattr(element, key, value)
            
            element.save()
            count += 1
        
        frappe.db.commit()
        
        frappe.log_error(f"✅ {count} Events ab {element_name} aktualisiert", "Series Handler")
        
        return {
            "status": "success",
            "count": count,
            "message": f"{count} Termine ab hier aktualisiert"
        }
    except Exception as e:
        frappe.log_error(f"❌ Fehler beim Aktualisieren ab hier: {str(e)}", "Series Handler Error")
        frappe.throw(f"❌ Fehler beim Aktualisieren ab hier: {str(e)}")
