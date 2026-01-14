# diakronos/kronos/api/permissions.py
import frappe
from datetime import datetime


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
        
        if user == "Guest":
            return False
        
        user_roles = frappe.get_roles()
        
        # Administrator hat ALLES
        if "Administrator" in user_roles:
            return True
        
        # Hole Kalender-Doc
        try:
            calendar = frappe.get_doc('Kalender', calendar_name)
        except frappe.DoesNotExistError:
            frappe.log_error(f'Kalender nicht gefunden: {calendar_name}', 'has_calendar_permission')
            return False
        
        # Hole Rollen aus den Tabellen
        write_roles = [row.role for row in (calendar.schreibrechte or [])]
        read_roles = [row.role for row in (calendar.leserechte or [])]
        
        # SCHREIBZUGRIFF: Nur wenn in schreibrechte eingetragen
        if permission_type == "write":
            if any(role in user_roles for role in write_roles):
                return True
            return False
        
        # LESEZUGRIFF: Wenn in schreibrechte ODER leserechte eingetragen
        if permission_type == "read":
            all_allowed_roles = write_roles + read_roles
            if any(role in user_roles for role in all_allowed_roles):
                return True
            return False
        
        return False
        
    except Exception as e:
        frappe.log_error(str(e), 'has_calendar_permission')
        return False


@frappe.whitelist()
def can_create_event():
    """
    Wird aufgerufen wenn User auf Tag im Kalender klickt.
    """
    try:
        user = frappe.session.user
        
        if user == "Guest":
            return {
                'can_create': False,
                'default_calendar': None,
                'writable_calendars': []
            }
        
        user_roles = frappe.get_roles()
        
        # Administrator hat ALLES
        if "Administrator" in user_roles:
            all_calendars = frappe.db.get_list(
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
        
        # Für normale User: Hole alle Kalender und prüfe Berechtigungen
        all_calendars = frappe.db.get_list(
            'Kalender',
            fields=['name', 'calendar_name']
        )
        
        writable_calendars = []
        default_calendar = None
        
        for cal in all_calendars:
            cal_doc = frappe.get_doc('Kalender', cal['name'])
            write_roles = [row.role for row in (cal_doc.schreibrechte or [])]
            
            if any(role in user_roles for role in write_roles):
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
        
    except Exception as e:
        frappe.log_error(str(e), 'can_create_event')
        return {
            'can_create': False,
            'default_calendar': None,
            'writable_calendars': [],
            'error': str(e)
        }


@frappe.whitelist()
def get_element_creation_dialog_defaults(date_str=None, calendar_name=None):
    """
    Hole vorausgefüllte Werte für Quick Entry Dialog.
    """
    try:
        can_create_response = can_create_event()
        
        if not can_create_response['can_create']:
            return {
                'can_create': False,
                'defaults': {},
                'error': 'Keine Berechtigung zum Erstellen'
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
                frappe.log_error(f'Fehler beim Datums-Parsing: {str(e)}', 'get_element_creation_dialog_defaults')
        
        return {
            'can_create': True,
            'defaults': defaults,
            'writable_calendars': can_create_response['writable_calendars']
        }
        
    except frappe.ValidationError as ve:
        return {
            'can_create': False,
            'defaults': {},
            'error': str(ve)
        }
    except Exception as e:
        frappe.log_error(str(e), 'get_element_creation_dialog_defaults')
        return {
            'can_create': False,
            'defaults': {},
            'error': str(e)
        }
