# apps/diakronos/diakronos/kronos/doctype/element/element.py
from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils import getdate, add_days, add_months, now


class Element(Document):
    """
    Element DocType für Termine/Events.
    """

    def before_insert(self):
        """Vor dem Erstellen – Serien generieren wenn aktiviert."""
        if self.repeat_this_event and not self.series_id:
            self.create_series()


    # ════════════════════════════════════════════════════════════════
    # SERIEN-LOGIK
    # ════════════════════════════════════════════════════════════════

    def create_series(self):
        """Erstelle eine Serie von Elementen basierend auf Wiederholungsmuster."""
        self.series_id = f"SER-{frappe.generate_hash('', 8).upper()}"
        self.repeat_this_event = 0

        target_calendar = self.element_calendar
        if not target_calendar:
            frappe.throw("Bitte zuerst einen Kalender auswählen (Feld 'element_calendar')")

        start_date = getdate(self.element_start.split(" ")[0])
        current = start_date
        end_date = getdate(self.repeat_till) if self.repeat_till else None
        max_events = 200
        created_elements = []

        while max_events:
            max_events -= 1
            current = self.get_next_occurrence(current)
            if not current or (end_date and current > end_date):
                break

            new_el = frappe.get_doc({
                "doctype": "Element",
                "element_name": self.element_name,
                "element_start": f"{current} {self.element_start.split(' ')[1]}",
                "element_end": self.element_end and f"{current} {self.element_end.split(' ')[1]}" or None,
                "element_category": self.element_category,
                "element_color": self.element_color,
                "status": "Festgelegt",
                "element_calendar": target_calendar,
                "series_id": self.series_id,
                "repeat_this_event": 0,
            })
            new_el.insert(ignore_permissions=True)
            created_elements.append(new_el.name)

        total = len(created_elements) + 1
        frappe.msgprint(
            f"Serie erstellt: <b>{total}</b> Termine (inkl. Original)<br>"
            f"Serien-ID: <b>{self.series_id}</b><br>"
            f"Alle im Kalender: <b>{target_calendar}</b>",
            indicator="green"
        )

    def get_next_occurrence(self, current):
        """Berechne das nächste Wiederholungsdatum."""
        days_map = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

        if self.repeat_on == "Daily":
            return add_days(current, 1)

        if self.repeat_on == "Weekly":
            wd = current.weekday()
            for i in range(1, 8):
                if self.get(days_map[(wd + i) % 7]):
                    return add_days(current, i)
            return add_days(current, 7)

        if self.repeat_on == "Monthly":
            return add_months(current, 1)

        if self.repeat_on == "Quarterly":
            return add_months(current, 3)

        if self.repeat_on == "Half Yearly":
            return add_months(current, 6)

        if self.repeat_on == "Yearly":
            return add_months(current, 12)

        return None

# ════════════════════════════════════════════════════════════════
# BERECHTIGUNGEN – HILFSFUNKTION
# ════════════════════════════════════════════════════════════════

def can_edit_series_instance(doc: "Element") -> bool:
    """Steuert, ob ein Serienelement im Form-UI editierbar ist.
    - Normale Elemente: immer True
    - Serienelement (series_id gesetzt): nur, wenn ein spezielles Flag gesetzt ist.
    """
    if not getattr(doc, "series_id", None):
        return True
    return bool(frappe.flags.get("allow_series_edit"))


# ════════════════════════════════════════════════════════════════
# FRAPPE HOOKS (freie Funktionen für hooks.py)
# ════════════════════════════════════════════════════════════════

def before_insert(doc, method=None):
    """Frappe Hook: Wird aufgerufen BEVOR Element erstellt wird."""
    doc.before_insert()


def after_save(doc, method=None):
    """Frappe Hook: Wird aufgerufen NACHDEM Element gespeichert wurde."""
    doc.after_save()


# ════════════════════════════════════════════════════════════════
# API - DROPDOWN OPTIONS FÜR FRONTEND
# ════════════════════════════════════════════════════════════════

@frappe.whitelist(allow_guest=False)
def get_calendar_and_category_options():
    """
    Liefert Kalender- und Kategorielisten für Frontend Dropdowns.
    Nur autorisierte Nutzer.
    
    Returns:
        dict: {
            "calendars": [{"name": "...", "calendar_name": "..."}, ...],
            "categories": [{"name": "..."}, ...]
        }
    """
    try:
        # Kalender abrufen
        calendars = frappe.get_list(
            "Kalender",
            fields=["name", "calendar_name"],
            limit_page_length=999
        )
        
        # Kategorien abrufen
        categories = frappe.get_list(
            "Eventkategorie",
            fields=["name"],
            limit_page_length=999
        )
        
        return {
            "calendars": calendars,
            "categories": categories
        }
    except Exception as e:
        frappe.log_error(str(e), "get_calendar_and_category_options")
        return {"calendars": [], "categories": []}
