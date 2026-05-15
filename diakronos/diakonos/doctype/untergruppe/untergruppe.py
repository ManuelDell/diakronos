import frappe
from frappe.model.document import Document


class Untergruppe(Document):
    def before_save(self):
        self._set_ancestor_path()

    def _set_ancestor_path(self):
        teile = [self.name] if self.name else []
        dienstbereich = None
        if self.gruppe:
            teile.append(self.gruppe)
            dienstbereich = frappe.db.get_value("Gruppe", self.gruppe, "dienstbereich")
        gruppen_pfad = "/" + "/".join(teile) + "/" if teile else "/"
        bereich_pfad = "/" + dienstbereich + "/" if dienstbereich else "/"
        self.ancestor_path = gruppen_pfad + "|" + bereich_pfad
