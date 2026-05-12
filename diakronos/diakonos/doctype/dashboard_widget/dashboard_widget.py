import frappe
from frappe.model.document import Document


class DashboardWidget(Document):
    def before_delete(self):
        if self.is_system:
            frappe.throw(frappe._("System-Widgets können nicht gelöscht werden."))
