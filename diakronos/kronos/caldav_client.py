import caldav
import frappe
from datetime import datetime
from icalendar import Calendar, Event


class NextcloudCalDAVClient:
    def __init__(self, url, username, password):
        self.client = caldav.DAVClient(url, username=username, password=password)
        self.principal = self.client.principal()
    
    def get_calendars(self):
        return self.principal.calendars()
    
    def create_event(self, calendar, title, start, end, description=""):
        event = calendar.save_event(
            summary=title,
            dtstart=start,
            dtend=end,
            description=description
        )
        return event
    
    def update_event(self, event, **kwargs):
        for key, value in kwargs.items():
            setattr(event.vobject_instance.vevent, key, value)
        event.save()
    
    def delete_event(self, event):
        event.delete()


@frappe.whitelist()
def test_konfiguration():
    """
    Testet die CalDAV-Verbindung und zeigt verfügbare Kalender an.
    """
    try:
        settings = frappe.get_single("Kronos Calendar Settings")
        url = settings.nextcloud_url
        username = settings.username
        password = settings.get_password("app_password")
        
        if not (url and username and password):
            frappe.throw("Bitte URL, Benutzername und Passwort in den Kronos Calendar Settings angeben!")
        
        # Verbindung testen
        client = caldav.DAVClient(url, username=username, password=password)
        principal = client.principal()
        
        if principal is None:
            frappe.throw("CalDAV-Verbindung fehlgeschlagen: Principal ist None")
        
        calendars = principal.calendars()
        
        # Kalender-Details sammeln
        calendar_info = []
        for cal in calendars:
            try:
                display_name = getattr(cal, 'display_name', 'Unbenannt')
                calendar_info.append({
                    'name': display_name,
                    'url': str(cal.url)
                })
            except:
                calendar_info.append({
                    'name': 'Kalender (Name nicht verfügbar)',
                    'url': str(cal.url) if hasattr(cal, 'url') else 'URL nicht verfügbar'
                })
        
        # Erfolgreiche Meldung mit Details
        if calendar_info:
            calendar_names = [info['name'] for info in calendar_info]
            message = f"✅ Verbindung erfolgreich!\n{len(calendar_info)} Kalender gefunden:\n• " + "\n• ".join(calendar_names[:5])
            if len(calendar_info) > 5:
                message += f"\n... und {len(calendar_info) - 5} weitere"
        else:
            message = "✅ Verbindung erfolgreich, aber keine Kalender gefunden."
        
        frappe.msgprint(message, title="CalDAV Test erfolgreich")
        
        # Log für Debugging (nicht für normale Nutzer sichtbar)
        frappe.logger().info(f"CalDAV Test erfolgreich: {len(calendar_info)} Kalender für User {username}")
        
        return {
            'success': True,
            'message': f"{len(calendar_info)} Kalender gefunden",
            'calendars': calendar_info
        }
        
    except Exception as e:
        error_msg = f"CalDAV-Verbindung fehlgeschlagen: {str(e)}"
        frappe.log_error(error_msg, "CalDAV Connection Test")
        frappe.throw(error_msg)


@frappe.whitelist()
def get_available_calendars():
    """
    Gibt Liste aller verfügbaren Kalender zurück (für Dropdowns, etc.)
    """
    try:
        settings = frappe.get_single("Kronos Calendar Settings")
        client = NextcloudCalDAVClient(
            settings.nextcloud_url,
            settings.username,
            settings.get_password("app_password")
        )
        
        calendars = client.get_calendars()
        calendar_list = []
        
        for cal in calendars:
            try:
                calendar_list.append({
                    'value': str(cal.url),
                    'label': getattr(cal, 'display_name', 'Unbenannt')
                })
            except:
                continue
                
        return calendar_list
        
    except Exception as e:
        frappe.log_error(f"Fehler beim Laden der Kalender: {str(e)}", "Get Calendars")
        return []


@frappe.whitelist()
def create_test_event():
    """
    Erstellt einen Test-Termin im ersten verfügbaren Kalender
    """
    try:
        settings = frappe.get_single("Kronos Calendar Settings")
        client = NextcloudCalDAVClient(
            settings.nextcloud_url,
            settings.username,
            settings.get_password("app_password")
        )
        
        calendars = client.get_calendars()
        if not calendars:
            frappe.throw("Keine Kalender verfügbar")
        
        # Ersten Kalender für Test verwenden
        first_calendar = calendars[0]
        
        # Test-Event erstellen
        start_time = datetime.now()
        end_time = datetime.now().replace(hour=start_time.hour + 1)
        
        event = client.create_event(
            first_calendar,
            "Test Event aus Kronos",
            start_time,
            end_time,
            "Automatisch erstellter Test-Termin aus dem Kronos-Modul"
        )
        
        frappe.msgprint(
            f"✅ Test-Event erfolgreich erstellt!\nKalender: {getattr(first_calendar, 'display_name', 'Unbenannt')}\nZeit: {start_time.strftime('%d.%m.%Y %H:%M')}", 
            title="Event erstellt"
        )
        
        return {
            'success': True,
            'message': 'Test-Event erstellt',
            'event_id': str(event.url) if hasattr(event, 'url') else 'Event erstellt'
        }
        
    except Exception as e:
        error_msg = f"Fehler beim Erstellen des Test-Events: {str(e)}"
        frappe.log_error(error_msg, "Create Test Event")
        frappe.throw(error_msg)
