# diakronos/diakronos/kronos/api/permissions.py

import frappe
from frappe import _
from datetime import datetime

def _user_has_role(user, role_name):
    """Prüft, ob User die angegebene Role hat."""
    if user == "Administrator":
        return True
    roles = [r.role for r in frappe.get_all("Has Role", filters={"parent": user}, fields=["role"])]
    return role_name in roles

@frappe.whitelist(allow_guest=False)
def get_session_info():
    user = frappe.session.user
    if user == "Guest":
        frappe.throw("Nicht angemeldet")
    user_doc = frappe.get_doc("User", user)
    return {
        "initial": user[0].upper(),
        "full_name": user_doc.full_name or user,
        "name": user
    }

@frappe.whitelist()
def has_calendar_permission(calendar_name, permission_type='read'):
    """
    Prüfe ob aktueller Benutzer Berechtigung für einen Kalender hat
    
    Schema: Kalender hat:
    - leserechte (Table mit Roles)
    - schreibrechte (Table mit Roles)
    
    Args:
        calendar_name (str): Name des Kalenders
        permission_type (str): 'read' oder 'write'
    
    Returns:
        bool: True wenn Berechtigung vorhanden
    """
    user = frappe.session.user
    user_roles = set(frappe.get_roles(user))
    
    # Admins haben immer alle Rechte
    if user == "Guest":
        return False
    if "Administrator" in user_roles or "System Manager" in user_roles:
        return True
    
    try:
        calendar = frappe.get_doc('Kalender', calendar_name)
    except frappe.DoesNotExistError:
        frappe.logger().warning(f'Kalender {calendar_name} nicht gefunden')
        return False
    
    if permission_type == 'read':
        # Prüfe leserechte Table
        read_roles = calendar.get('leserechte', []) or []
        for entry in read_roles:
            role = entry.get('role') or entry.get('user_role')
            if role and role in user_roles:
                return True
    elif permission_type == 'write':
        # Prüfe schreibrechte Table
        write_roles = calendar.get('schreibrechte', []) or []
        for entry in write_roles:
            role = entry.get('role') or entry.get('user_role')
            if role and role in user_roles:
                return True
    
    return False

@frappe.whitelist()
def get_accessible_calendars():
    """
    Gibt Kalender zurück, die der aktuelle User lesen darf (via leserechte).
    
    Returns:
        list: [{name, display_name, color, can_write}, ...]
    """
    user = frappe.session.user
    
    try:
        calendars = frappe.get_all(
            "Kalender",
            fields=["name", "calendar_name", "calendar_color"]
        )
        
        result = []
        for cal in calendars:
            doc = frappe.get_doc("Kalender", cal.name)
            
            can_read = False
            can_write = False
            
            # Leserechte prüfen
            for row in doc.leserechte or []:
                if _user_has_role(user, row.role):
                    can_read = True
            
            # Schreibrechte prüfen
            for row in doc.schreibrechte or []:
                if _user_has_role(user, row.role):
                    can_write = True
                    can_read = True
            
            if can_read:
                result.append({
                    "name": doc.name,
                    "display_name": doc.calendar_name or doc.name,
                    "color": doc.calendar_color or "#667eea",  # Aus _colors.scss (--blue)
                    "can_write": can_write,
                })
        
        return result
        
    except Exception as e:
        frappe.log_error(str(e), "get_accessible_calendars")
        return []

@frappe.whitelist()
def can_create_event():
    """
    Prüfe ob aktueller Nutzer Events erstellen darf
    
    Wird aufgerufen wenn User auf Tag im Kalender klickt
    
    Returns:
        Dict mit can_create Flag und verfügbaren Kalendern
    """
    user = frappe.session.user
    if user == "Guest":
        return {
            'can_create': False,
            'default_calendar': None,
            'writable_calendars': []
        }
    
    user_roles = frappe.get_roles(user)
    
    # Admins können überall erstellen
    if "Administrator" in user_roles or "System Manager" in user_roles:
        all_calendars = frappe.get_all(
            'Kalender',
            fields=['name', 'calendar_name']
        )
        writable_calendars = [
            {'label': cal['calendar_name'], 'value': cal['name']}
            for cal in all_calendars
        ]
        default_calendar = writable_calendars[0]['value'] if writable_calendars else None
        return {
            'can_create': len(writable_calendars) > 0,
            'default_calendar': default_calendar,
            'writable_calendars': writable_calendars
        }
    
    # Normale Benutzer: Prüfe Kalender-Berechtigungen
    all_calendars = frappe.get_all(
        'Kalender',
        fields=['name', 'calendar_name']
    )
    writable_calendars = []
    default_calendar = None
    for cal in all_calendars:
        if has_calendar_permission(cal['name'], 'write'):
            writable_calendars.append({
                'label': cal['calendar_name'],
                'value': cal['name']
            })
            if default_calendar is None:
                default_calendar = cal['name']
    
    return {
        'can_create': len(writable_calendars) > 0,
        'default_calendar': default_calendar,
        'writable_calendars': writable_calendars
    }

@frappe.whitelist()
def get_element_creation_dialog_defaults(date_str=None, calendar_name=None):
    """
    Hole Default-Werte für Element-Erstellungs-Dialog
    
    Args:
        date_str: Datum als String "2026-01-05"
        calendar_name: Standard-Kalender
    
    Returns:
        Dict mit defaults und can_create Flag
    """
    try:
        can_create_response = can_create_event()
        if not can_create_response['can_create']:
            return {
                'can_create': False,
                'defaults': {},
                'writable_calendars': [],
                'error': _('Keine Berechtigung zum Erstellen')
            }
        
        selected_calendar = calendar_name or can_create_response['default_calendar']
        if selected_calendar:
            if not any(cal['value'] == selected_calendar for cal in can_create_response['writable_calendars']):
                frappe.throw(f'Keine Berechtigung für Kalender: {selected_calendar}')
        
        defaults = {
            'element_calendar': selected_calendar,
        }
        
        if date_str:
            try:
                dt = datetime.strptime(date_str, '%Y-%m-%d')
                start_time = dt.replace(hour=10, minute=0, second=0)
                end_time = start_time.replace(hour=11)
                defaults['element_start'] = start_time.strftime('%Y-%m-%d %H:%M:%S')
                defaults['element_end'] = end_time.strftime('%Y-%m-%d %H:%M:%S')
            except Exception as e:
                frappe.log_error(
                    f'Fehler beim Datums-Parsing: {str(e)}',
                    'get_element_creation_dialog_defaults'
                )
        
        return {
            'can_create': True,
            'defaults': defaults,
            'writable_calendars': can_create_response['writable_calendars']
        }
        
    except frappe.ValidationError as ve:
        return {
            'can_create': False,
            'defaults': {},
            'writable_calendars': [],
            'error': str(ve)
        }
    except Exception as e:
        frappe.log_error(str(e), 'get_element_creation_dialog_defaults')
        return {
            'can_create': False,
            'defaults': {},
            'writable_calendars': [],
            'error': str(e)
        }