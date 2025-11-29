from __future__ import unicode_literals

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, add_days, add_months


class Element(Document):
    def on_update(self):
        # Nur ausführen, wenn:
        # - Repeat aktiv
        # - Noch keine Serie existiert
        # - Es ist der Master (series_master noch nicht gesetzt)
        # - Das Feld wurde gerade geändert
        if (self.repeat_this_event
                and not self.series_id
                and self.has_value_changed("repeat_this_event")):
            self.create_series()

    def create_series(self):
        if self.series_id:
            return

        if not self.element_calendar:
            frappe.throw("Bitte zuerst einen Kalender auswählen")

        self.series_id = f"SER-{frappe.generate_hash('', 8).upper()}"
        self.series_master = 1
        self.repeat_this_event = 0
        self.save(ignore_permissions=True)

        # --- Datum/Zeit extrahieren (robust)
        if isinstance(self.element_start, str):
            date_part = self.element_start.split(" ")[0]
            time_part = self.element_start.split(" ")[1] if " " in self.element_start else "10:00:00"
        else:
            date_part = self.element_start.date().isoformat()
            time_part = self.element_start.strftime("%H:%M:%S")

        end_time_part = None
        if self.element_end:
            if isinstance(self.element_end, str):
                end_time_part = self.element_end.split(" ")[1] if " " in self.element_end else None
            else:
                end_time_part = self.element_end.strftime("%H:%M:%S")

        current = getdate(date_part)
        end_date = getdate(self.repeat_till) if self.repeat_till else None
        max_events = 300
        created = 0

        while max_events > 0:
            max_events -= 1
            current = self.get_next_occurrence(current)
            if not current or (end_date and current > end_date):
                break

            new_doc = frappe.get_doc({
                "doctype": "Element",
                "element_name": self.element_name,
                "element_start": f"{current} {time_part}",
                "element_end": f"{current} {end_time_part}" if end_time_part else None,
                "element_category": self.element_category,
                "element_color": self.element_color,
                "status": self.status or "Festgelegt",
                "element_calendar": self.element_calendar,
                "series_id": self.series_id,
                "series_master": 0,
                "repeat_this_event": 0
            })
            new_doc.insert(ignore_permissions=True)
            new_doc.save(ignore_permissions=True)
            created += 1

        frappe.msgprint(
            f"Serie erstellt: <b>{created + 1}</b> Termine<br>ID: <b>{self.series_id}</b>",
            indicator="green"
        )

    def get_next_occurrence(self, current):
        days_map = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        if self.repeat_on == "Daily":
            return add_days(current, 1)
        elif self.repeat_on == "Weekly":
            wd = current.weekday()
            for i in range(1, 8):
                if self.get(days_map[(wd + i) % 7]):
                    return add_days(current, i)
            return add_days(current, 7)
        elif self.repeat_on == "Monthly":
            return add_months(current, 1)
        elif self.repeat_on == "Yearly":
            return add_months(current, 12)
        return None
