import frappe
from frappe.model.document import Document


class DSGVOEinwilligung(Document):
    def before_save(self):
        if not self.is_new():
            frappe.throw(
                "Einwilligung-Logs sind unveränderlich und dürfen nicht bearbeitet werden.",
                frappe.PermissionError,
            )

    def on_trash(self):
        frappe.throw(
            "Einwilligung-Logs dürfen nicht gelöscht werden (DSGVO Art. 5 Abs. 2).",
            frappe.PermissionError,
        )
