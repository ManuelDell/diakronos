# diakronos/kronos/api/cache_invalidator.py
"""
Cache Invalidierung für Events
Wird automatisch von Frappe aufgerufen bei Element Änderungen
"""

import frappe


def invalidate_events_cache(doc, method):
    """
    Automatisch aufgerufen nach Insert/Update/Delete von Element
    
    Args:
        doc: Das Element DocType
        method: Der Hook-Name (after_insert, after_update, after_delete)
    """
    try:
        frappe.log_error(
            f"🔴 INVALIDATE CACHE: {doc.name} ({method})",
            "cache_invalidator"
        )
        
        # Leere den In-Memory Cache
        from .calendar_get import clear_events_cache
        clear_events_cache()
        
        # Optional: Leere auch Frappe's Redis Cache
        frappe.cache().delete_key("calendar_events_*")
        
        frappe.log_error(
            f"✅ Cache gelöscht für Element {doc.name}",
            "cache_invalidator"
        )
        
    except Exception as e:
        frappe.log_error(f"Fehler beim Cache-Löschen: {str(e)}", "cache_invalidator ERROR")
