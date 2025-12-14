# diakronos/kronos/api/permissions.py
"""
Berechtigungsverwaltung für Kronos Kalender.
Hierarchie:
1. Moderator → alle Kalender (alle Rechte)
2. Kalender-Leiter → Schreibrechte
3. Rollen-Mitgliedschaft → Lesezugriff
"""

import frappe


def has_calendar_permission(calendar_name, permission_type="read"):
    """
    Prüft, ob aktueller User Berechtigung für einen Kalender hat.
    
    Args:
        calendar_name (str): Name des Kalenders
        permission_type (str): 'read' oder 'write'
    
    Returns:
        bool: True wenn Berechtigung vorhanden
    """
    try:
        user = frappe.session.user
        
        # Guest hat nie Berechtigung
        if user == "Guest":
            return False
        
        user_roles = frappe.get_roles()
        
        # Moderator hat alles
        if "Moderator" in user_roles:
            return True
        
        # Hole Kalender-Doc
        try:
            calendar = frappe.get_doc('Kalender', calendar_name)
        except:
            return False
        
        # Schreibzugriff: nur Leiter
        if permission_type == "write":
            if hasattr(calendar, 'element_leiter') and calendar.element_leiter == user:
                return True
            if "Moderator" in user_roles:
                return True
            return False
        
        # Lesezugriff: Rolle-basiert
        if hasattr(calendar, 'element_berechtigungen'):
            allowed_roles = [r.element_rolle for r in calendar.element_berechtigungen]
            if any(role in user_roles for role in allowed_roles):
                return True
        
        # Standard: Alle angemeldeten können lesen
        return True
        
    except Exception as e:
        frappe.log_error(str(e), 'has_calendar_permission')
        return False


@frappe.whitelist()
def check_user_permission(calendar_name, permission_type="read"):
    """
    Whitelist-Wrapper für Frontend-Aufrufe.
    """
    return has_calendar_permission(calendar_name, permission_type)
