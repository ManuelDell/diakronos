# diakronos/kronos/api/sync.py
"""
Synchronisierung mit Nextcloud CalDAV.
(Phase 2 - noch nicht implementiert)
"""

import frappe
from frappe import _


@frappe.whitelist()
def sync_nextcloud_events(calendar_name):
    """
    Synchronisiert Events aus Nextcloud CalDAV mit Frappe Elements.
    
    TODO: Phase 2
    """
    frappe.throw(_("Nextcloud-Synchronisierung ist noch in Entwicklung"))


@frappe.whitelist()
def sync_all_calendars():
    """
    Synchronisiert alle Kalender mit Nextcloud.
    
    TODO: Phase 2
    """
    frappe.throw(_("Calendars-Synchronisierung ist noch in Entwicklung"))
