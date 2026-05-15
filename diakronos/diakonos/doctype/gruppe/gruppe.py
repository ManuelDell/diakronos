import frappe
from frappe.model.document import Document


class Gruppe(Document):
    def before_save(self):
        self._set_ancestor_path()

    def _set_ancestor_path(self):
        gruppen_pfad = "/" + self.name + "/" if self.name else "/"
        bereich_pfad = "/" + (self.dienstbereich or "") + "/" if self.dienstbereich else "/"
        self.ancestor_path = gruppen_pfad + "|" + bereich_pfad
