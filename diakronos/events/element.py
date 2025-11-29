# apps/diakronos/diakronos/doctype/element/element.py
import frappe
from frappe.model.document import Document
from frappe.utils import getdate, add_days, add_months

class Element(Document):
    def before_insert(self):
        if self.repeat_this_event and not self.series_id:
            self.create_series()

    def create_series(self):
    # Nur Elemente erstellen – KEINE Elementlinks anfassen!
    self.series_id = f"SER-{frappe.generate_hash('', 8).upper()}"
    self.series_master = 1
    self.repeat_this_event = 0  # verhindert Endlosschleife

    # Welcher Kalender? → Der, den der User gerade ausgewählt hat
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

        # Neues Element anlegen – exakt wie der Master, aber ohne Sync-Flag
        new_el = frappe.get_doc({
            "doctype": "Element",
            "element_name": self.element_name,
            "element_start": f"{current} {self.element_start.split(' ')[1]}",
            "element_end": self.element_end and f"{current} {self.element_end.split(' ')[1]}" or None,
            "element_category": self.element_category,
            "element_color": self.element_color,
            "status": "Festgelegt",
            "element_calendar": target_calendar,  # ← WICHTIG: gleicher Kalender!
            "series_id": self.series_id,
            "series_master": 0,
            "repeat_this_event": 0,
            # Alle anderen Felder (Description, etc.) werden automatisch übernommen
        })
        new_el.insert(ignore_permissions=True)
        created_elements.append(new_el.name)

    # Jetzt: Für jedes neue Element den normalen Kalender-Sync triggern
    for name in created_elements:
        el = frappe.get_doc("Element", name)
        # Wir setzen den Flag, damit dein Sync-Code läuft
        frappe.flags.element_to_calendar_sync = False
        el.run_method("on_update")  # oder einfach el.save() → löst on_update aus

    total = len(created_elements) + 1
    frappe.msgprint(
        f"Serie erstellt: <b>{total}</b> Termine (inkl. Original)<br>"
        f"Serien-ID: <b>{self.series_id}</b><br>"
        f"Alle im Kalender: <b>{target_calendar}</b>",
        indicator="green"
    )
    def get_next_occurrence(self, current):
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
        if self.repeat_on == "Yearly":
            return add_months(current, 12)
        return None