import frappe
from frappe.model.document import Document
from frappe.utils import cint
from frappe import _


class AuditPolicy(Document):
    def validate(self):
        # DSGVO-Warnung wenn Systemadmin eine Regel anlegt, die ihn selbst betrifft
        user = frappe.session.user
        roles = frappe.get_roles(user)
        if "System Manager" in roles:
            if self.actor_role == "System Manager" and not cint(self.target_is_other):
                frappe.msgprint(
                    _("<b>DSGVO-Hinweis:</b> Diese Regel betrifft Systemadmins bei Eigenänderungen. "
                      "Änderungen an eigenen Daten werden geloggt und können von Verantwortlichen eingesehen werden. "
                      "Stellen Sie sicher, dass dies mit der Datenschutzerklärung vereinbar ist."),
                    indicator="orange",
                    alert=True,
                )

    def on_update(self):
        from diakronos.diakonos.api.audit_policy.engine import clear_policy_cache
        clear_policy_cache()
        self._log_policy_change("updated")

    def on_trash(self):
        from diakronos.diakonos.api.audit_policy.engine import clear_policy_cache
        clear_policy_cache()
        self._log_policy_change("deleted")

    def _log_policy_change(self, change_type):
        from frappe.utils import now_datetime
        frappe.local.audit_policy_logged = True
        try:
            frappe.get_doc({
                "doctype": "Audit Log",
                "zeitstempel": now_datetime(),
                "action_typ": "Berechtigungsänderung",
                "actor": frappe.session.user,
                "target_doctype": "Audit Policy",
                "target_name": self.name,
                "begruendung": f"Audit Policy {change_type}: {self.policy_name or self.name}",
            }).insert(ignore_permissions=True)
        finally:
            frappe.local.audit_policy_logged = False
