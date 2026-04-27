import frappe
from frappe.utils import now_datetime

CACHE_KEY = "diakronos:active_audit_policies"
CACHE_TTL = 60  # 1 Minute


def get_active_policies(doctype=None, action=None):
    """Holt aktive Audit-Policies aus dem Cache oder DB. Optional gefiltert."""
    policies = frappe.cache().get_value(CACHE_KEY)

    if policies is None:
        policies = frappe.get_all(
            "Audit Policy",
            filters={"is_active": 1},
            fields=[
                "name", "policy_name", "doctype_target", "field_target",
                "action", "actor_role", "target_is_other", "consequence",
                "confirm_prompt", "confirm_field_label", "notify_on_confirm",
                "priority", "is_active"
            ],
            order_by="priority desc, modified desc",
        )
        frappe.cache().set_value(CACHE_KEY, policies, expires_in_sec=CACHE_TTL)

    if doctype:
        policies = [p for p in policies if p.get("doctype_target") == doctype]
    if action:
        policies = [p for p in policies if p.get("action") == action]

    return policies


def evaluate_policy(policy, doc=None, actor=None, target_user=None, field_name=None):
    """Prüft, ob eine einzelne Policy für den aktuellen Kontext zutrifft."""
    if not policy.get("is_active"):
        return False

    # Prüfe Feld-Target, falls gesetzt
    if policy.get("field_target") and field_name != policy["field_target"]:
        return False

    # Prüfe Actor-Rolle, falls gesetzt
    if policy.get("actor_role"):
        user_roles = frappe.get_roles(actor or frappe.session.user)
        if policy["actor_role"] not in user_roles:
            return False

    # Prüfe target_is_other
    if policy.get("target_is_other"):
        if not target_user or target_user == (actor or frappe.session.user):
            return False

    return True


def clear_policy_cache():
    """Löscht den Policy-Cache."""
    frappe.cache().delete_value(CACHE_KEY)
