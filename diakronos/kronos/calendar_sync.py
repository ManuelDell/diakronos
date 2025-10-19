import frappe
from .caldav_client import NextcloudCalDAVClient

@frappe.whitelist()
def sync_with_nextcloud():
    settings = frappe.get_single("Kronos Calendar Settings")
    
    client = NextcloudCalDAVClient(
        settings.nextcloud_url,
        settings.username, 
        settings.app_password
    )
    
    # Frappe → NextCloud sync
    sync_frappe_to_caldav(client)
    
    # NextCloud → Frappe sync  
    sync_caldav_to_frappe(client)

def sync_frappe_to_caldav(client):
    # Unsynced Frappe events zu CalDAV pushen
    events = frappe.get_all("Calendar Event", 
                          filters={"caldav_synced": 0})
    
    for event_doc in events:
        # Create CalDAV event
        # Update sync status
        pass

# Scheduled Task in hooks.py:
# "* * * * *": ["diakronos.kronos.calendar_sync.sync_with_nextcloud"]
