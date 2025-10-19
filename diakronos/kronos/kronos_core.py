import caldav
import frappe
from datetime import datetime
from icalendar import Calendar, Event
import uuid

class KronosCalendarManager:
    def __init__(self):
        settings = frappe.get_single("Kronos Calendar Settings")
        self.client = caldav.DAVClient(
            settings.nextcloud_url,
            username=settings.username,
            password=settings.get_password("app_password")
        )
        self.principal = self.client.principal()

    @frappe.whitelist()
    def create_calendar(self, name, description=""):
        """Erstellt einen neuen Kalender in Nextcloud"""
        try:
            calendar = self.principal.make_calendar(
                name=name,
                displayname=name
            )
            
            # In Frappe-Doctype speichern
            kronos_cal = frappe.new_doc("Kronos Calendar")
            kronos_cal.calendar_name = name
            kronos_cal.nextcloud_calendar_url = str(calendar.url)
            kronos_cal.description = description
            kronos_cal.created_by_user = frappe.session.user
            kronos_cal.insert()
            
            return {"success": True, "calendar": kronos_cal.name}
            
        except Exception as e:
            frappe.log_error(f"Kalender erstellen fehlgeschlagen: {e}")
            frappe.throw(f"Fehler beim Erstellen: {e}")

    @frappe.whitelist()
    def sync_all_events(self):
        """Synchronisiert alle Events zwischen Nextcloud und Frappe"""
        kronos_calendars = frappe.get_all("Kronos Calendar", 
                                        filters={"status": "Active"})
        
        for cal_doc in kronos_calendars:
            self.sync_calendar_events(cal_doc.name)

    def sync_calendar_events(self, kronos_calendar_name):
        """Sync Events eines spezifischen Kalenders"""
        kronos_cal = frappe.get_doc("Kronos Calendar", kronos_calendar_name)
        nextcloud_cal = self.client.calendar(url=kronos_cal.nextcloud_calendar_url)
        
        # Events aus Nextcloud laden
        events = nextcloud_cal.events()
        
        for event in events:
            self.create_or_update_frappe_event(event, kronos_cal)

# Berechtigungsprüfungen
@frappe.whitelist()
def has_calendar_permission(calendar_name, permission_type="read"):
    """Prüft, ob User Berechtigung für Kalender hat"""
    kronos_cal = frappe.get_doc("Kronos Calendar", calendar_name)
    
    # Moderator hat immer alle Rechte
    if "Moderator" in frappe.get_roles():
        return True
    
    # Leiter hat Schreibrechte für zugewiesene Kalender  
    if permission_type == "write" and kronos_cal.responsible_leader == frappe.session.user:
        return True
    
    # Prüfe Rollenberechtigung
    user_roles = frappe.get_roles()
    allowed_roles = [r.role for r in kronos_cal.allowed_roles]
    
    return any(role in allowed_roles for role in user_roles)
