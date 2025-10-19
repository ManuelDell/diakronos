# api.py - Kronos Calendar API
import frappe

@frappe.whitelist()
def get_calendar_events(start, end, filters=None):
    """Events für Kalenderansicht laden"""
    
    # Nur Kalender laden, für die User Berechtigung hat
    user_calendars = get_user_calendars()
    calendar_names = [cal['name'] for cal in user_calendars if cal['visible']]
    
    if not calendar_names:
        return []
    
    events = frappe.db.sql("""
        SELECT 
            ce.name, ce.title, ce.description,
            ce.start_date, ce.end_date, ce.all_day,
            kc.calendar_name, kc.color
        FROM `tabCalendar Event` ce
        JOIN `tabKronos Calendar` kc ON ce.kronos_calendar = kc.name
        WHERE ce.start_date BETWEEN %s AND %s
        AND kc.name IN ({})
        ORDER BY ce.start_date
    """.format(','.join(['%s'] * len(calendar_names))), 
    [start, end] + calendar_names, as_dict=True)
    
    # Für FullCalendar formatieren
    return [{
        'id': event.name,
        'title': event.title,
        'start': event.start_date,
        'end': event.end_date,
        'color': event.color,
        'extendedProps': {
            'description': event.description,
            'calendar': event.calendar_name
        }
    } for event in events]

@frappe.whitelist()  
def get_user_calendars():
    """Kalender für aktuellen User laden"""
    
    calendars = frappe.db.sql("""
        SELECT kc.name, kc.calendar_name as display_name, 
               kc.color, kc.responsible_leader
        FROM `tabKronos Calendar` kc
        WHERE kc.status = 'Active'
    """, as_dict=True)
    
    user_calendars = []
    for cal in calendars:
        if has_calendar_permission(cal.name, "read"):
            cal['visible'] = True  # Standard: sichtbar
            cal['can_edit'] = has_calendar_permission(cal.name, "write")
            user_calendars.append(cal)
    
    return user_calendars
