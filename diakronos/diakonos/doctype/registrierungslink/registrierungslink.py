import frappe
from frappe.model.document import Document


class Registrierungslink(Document):

    def before_insert(self):
        if not self.slug:
            self.slug = frappe.generate_hash("", 20)

    def after_insert(self):
        self._update_link_anzeige()

    def on_update(self):
        self._update_link_anzeige()

    def _update_link_anzeige(self):
        pfad = "registrierung" if self.typ == "Mitglied-Registrierung" else "gast"
        url = f"/diakonos/{pfad}?token={self.slug}"
        frappe.db.set_value("Registrierungslink", self.name, "link_anzeige", url, update_modified=False)
