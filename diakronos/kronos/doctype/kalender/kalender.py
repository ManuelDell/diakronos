# Copyright (c) 2025, Dells Dienste and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class Kalender(Document):
    pass

def _user_has_role(user, role_name):
    """Prüft, ob User die angegebene Role hat."""
    if user == "Administrator":
        return True
    roles = [r.role for r in frappe.get_all("Has Role", filters={"parent": user}, fields=["role"])]
    return role_name in roles

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
                    break
            
            # Schreibrechte prüfen
            for row in doc.schreibrechte or []:
                if _user_has_role(user, row.role):
                    can_write = True
                    break
            
            # Admin darf alles
            if user == "Administrator":
                can_read = True
                can_write = True
            
            if can_read:
                result.append({
                    "name": doc.name,
                    "display_name": doc.calendar_name or doc.name,
                    "color": doc.calendar_color or "#667eea",
                    "can_write": can_write,
                })
        
        frappe.logger().info(f"✓ get_accessible_calendars: {len(result)} calendars for {user}")
        return result
        
    except Exception as e:
        frappe.logger().error(f"Error in get_accessible_calendars: {str(e)}")
        frappe.throw(f"Error getting calendars: {str(e)}")

@frappe.whitelist()
def get_calendar_events(start_date, end_date):
    """
    Gibt alle Events für die sichtbaren Kalender des Users zurück.
    
    Status-Handling:
    - "Festgelegt": Keine Änderung, normale Farbe
    - "Vorschlag": Sanftes Gelb (#FEF3C7 = Amber-100)
    - "Konflikt": Sanftes Rot (#FEE2E2 = Red-100)
    """
    user = frappe.session.user
    
    frappe.logger().info(f"→ get_calendar_events: {start_date} to {end_date} for {user}")
    
    try:
        # 1. Kalender mit Leserechte laden
        accessible = get_accessible_calendars()
        
        if not accessible:
            frappe.logger().warning("✗ No accessible calendars found")
            return []
        
        calendar_names = [cal["name"] for cal in accessible]
        frappe.logger().info(f"  Calendars: {calendar_names}")
        
        # 2. Alle Elemente in diesem Zeitraum laden
        elements = frappe.get_all(
            "Element",
            filters=[
                ["element_calendar", "in", calendar_names],
                ["element_start", ">=", f"{start_date} 00:00:00"],
                ["element_end", "<=", f"{end_date} 23:59:59"]
            ],
            fields=[
                "name",
                "element_name",
                "element_start",
                "element_end",
                "element_color",
                "status",
                "element_calendar",
                "all_day",
                "description"
            ]
        )
        
        frappe.logger().info(f"  Found {len(elements)} events")
        
        # 3. Status → Farb-Mapping
        status_colors = {
            "Festgelegt": None,  # Keine Änderung
            "Vorschlag": "#FEF3C7",  # Sanftes Gelb (Amber-100)
            "Konflikt": "#FEE2E2",  # Sanftes Rot (Red-100)
        }
        
        # 4. Format für tui-calendar
        events = []
        for elem in elements:
            try:
                # Title OHNE Status Badge
                title = elem.element_name or "Unnamed Event"
                
                # Base Color von Element
                base_color = elem.element_color or "#667eea"
                
                # Status-basierte Farbe (überschreibt base_color falls vorhanden)
                status = elem.status or "Festgelegt"
                bg_color = status_colors.get(status, base_color)
                
                # Wenn keine spezielle Status-Farbe, nimm base_color
                if bg_color is None:
                    bg_color = base_color
                
                # WICHTIG: element_start und element_end müssen DateTime Strings sein
                try:
                    if isinstance(elem.element_start, str):
                        start_iso = elem.element_start.replace(" ", "T")
                    else:
                        start_iso = elem.element_start.strftime("%Y-%m-%dT%H:%M:%S")
                except Exception as date_err:
                    frappe.logger().warning(f"Could not convert start date for {elem.name}: {date_err}")
                    continue
                
                try:
                    if isinstance(elem.element_end, str):
                        end_iso = elem.element_end.replace(" ", "T")
                    else:
                        end_iso = elem.element_end.strftime("%Y-%m-%dT%H:%M:%S")
                except Exception as date_err:
                    frappe.logger().warning(f"Could not convert end date for {elem.name}: {date_err}")
                    continue
                
                # tui-calendar Event Object
                event = {
                    "id": elem.name,
                    "calendarId": elem.element_calendar,
                    "title": title,  # OHNE Status
                    "start": start_iso,
                    "end": end_iso,
                    "color": base_color,  # Text color bleibt original
                    "backgroundColor": bg_color,  # Background = Status-Farbe
                    "borderColor": base_color,  # Left border bleibt original
                    "isAllday": bool(elem.all_day),
                    "category": "allday" if elem.all_day else "time",
                    "body": elem.description or "",
                }
                
                events.append(event)
                frappe.logger().debug(f"  ✓ Event: {title} (Status: {status}, BG: {bg_color})")
                
            except Exception as event_err:
                frappe.logger().error(f"Error processing event {elem.name}: {event_err}")
                continue
        
        frappe.logger().info(f"✓ Returning {len(events)} events")
        return events
        
    except Exception as e:
        frappe.logger().error(f"Error in get_calendar_events: {str(e)}")
        frappe.throw(f"Error getting events: {str(e)}")

