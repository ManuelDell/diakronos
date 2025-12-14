# diakronos/kronos/api/calendars.py
"""
API für Kalender-Verwaltung und -Abfrage.
"""

import frappe
from frappe import _
from .permissions import has_calendar_permission


@frappe.whitelist()
def get_accessible_calendars():
    """
    Gibt alle Kalender zurück, auf die der aktuelle User Lesezugriff hat.
    
    Returns:
        List[Dict]: [{"name": "...", "title": "...", "color": "#..."}]
    """
    try:
        user = frappe.session.user
        if not user or user == "Guest":
            frappe.throw(_("Sie müssen angemeldet sein."))
        
        # Hole alle Kalender
        calendars = frappe.get_all(
            'Kalender',
            fields=['name', 'element_name as title', 'element_color as color'],
            order_by='element_name asc'
        )
        
        # Filtere nach Berechtigungen
        accessible = []
        for cal in calendars:
            if has_calendar_permission(cal['name'], 'read'):
                accessible.append({
                    'name': cal['name'],
                    'title': cal['title'],
                    'color': cal['color'] or '#007bff'
                })
        
        frappe.logger().info(f'get_accessible_calendars: {len(accessible)} for user {user}')
        return accessible
        
    except Exception as e:
        frappe.log_error(str(e), 'get_accessible_calendars')
        frappe.throw(_('Fehler beim Laden der Kalender: ') + str(e))


@frappe.whitelist()
def get_calendar_details(calendar_name):
    """
    Gibt Details zu einem spezifischen Kalender zurück.
    """
    try:
        if not has_calendar_permission(calendar_name, 'read'):
            frappe.throw(_("Keine Berechtigung für diesen Kalender"))
        
        calendar = frappe.get_doc('Kalender', calendar_name)
        
        return {
            'name': calendar.name,
            'title': calendar.element_name,
            'color': calendar.element_color or '#007bff',
            'description': calendar.element_beschreibung or '',
            'leader': calendar.element_leiter if hasattr(calendar, 'element_leiter') else None,
            'can_edit': has_calendar_permission(calendar_name, 'write')
        }
        
    except Exception as e:
        frappe.log_error(str(e), 'get_calendar_details')
        frappe.throw(_('Fehler beim Laden der Kalender-Details: ') + str(e))
