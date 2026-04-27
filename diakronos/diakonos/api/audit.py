import frappe
from frappe.utils import now_datetime, cint
from frappe import _

VALID_ACTIONS = {"Datenzugriff", "Profiländerung", "Dateizugriff", "Dateilöschung", "DSGVO-Export", "Berechtigungsänderung", "Sonstiges"}


def log(action_typ, target_doctype, target_name, begruendung=""):
    """Schreibt einen Audit-Log-Eintrag. Immer ignore_permissions, da intern."""
    if action_typ not in VALID_ACTIONS:
        action_typ = "Sonstiges"
    frappe.get_doc({
        "doctype": "Audit Log",
        "zeitstempel": now_datetime(),
        "action_typ": action_typ,
        "actor": frappe.session.user,
        "target_doctype": target_doctype,
        "target_name": target_name,
        "begruendung": begruendung,
        "notification_gesendet": 0,
    }).insert(ignore_permissions=True)


@frappe.whitelist()
def get_my_audit_log(start=0, limit=20, action_typ=None):
    """
    Gibt Audit-Log-Einträge des aktuell eingeloggten Users zurück.
    Filtert auf target_user = aktueller User ODER actor = aktueller User (DSGVO Art. 15).
    """
    user = frappe.session.user

    filters = {}
    if action_typ:
        if action_typ not in VALID_ACTIONS:
            frappe.throw(_("Ungültiger action_typ."), frappe.ValidationError)
        filters["action_typ"] = action_typ

    or_filters = [
        ["target_user", "=", user],
        ["actor", "=", user],
    ]

    logs = frappe.get_all(
        "Audit Log",
        filters=filters,
        or_filters=or_filters,
        fields=[
            "name", "zeitstempel", "action_typ", "actor", "target_doctype",
            "target_name", "policy_triggered", "consequence", "field_changed",
            "old_value", "new_value", "confirm_reason", "confirmed_at",
            "ip_address", "user_agent", "anonymized_at", "begruendung"
        ],
        order_by="zeitstempel desc",
        start=cint(start),
        page_length=cint(limit),
        ignore_permissions=True,
    )

    # db.count() unterstuetzt kein or_filters → SQL-Count
    total = frappe.db.sql("""
        SELECT COUNT(*) FROM `tabAudit Log`
        WHERE ({or_where}) {filter_where}
    """.format(
        or_where=" OR ".join([f"{f[0]} = %s" for f in or_filters]),
        filter_where=" AND " + " AND ".join([f"{k} = %s" for k in filters]) if filters else ""
    ), tuple([f[2] for f in or_filters] + list(filters.values())) if filters else tuple([f[2] for f in or_filters]))[0][0]

    return {
        "success": True,
        "data": logs,
        "total": total,
        "start": cint(start),
        "limit": cint(limit),
    }


@frappe.whitelist()
def get_unread_notifications():
    """
    Gibt die Anzahl ungelesener Notification-Log-Einträge des aktuellen Users zurück.
    """
    user = frappe.session.user
    count = frappe.db.count(
        "Notification Log",
        filters={
            "for_user": user,
            "read": 0,
        }
    )
    return {"success": True, "unread_count": count}


@frappe.whitelist()
def mark_notifications_read():
    """
    Markiert alle Notification-Log-Einträge des aktuellen Users als gelesen.
    """
    user = frappe.session.user
    frappe.db.set_value(
        "Notification Log",
        {"for_user": user, "read": 0},
        "read",
        1,
        update_modified=False,
    )
    return {"success": True}


@frappe.whitelist()
def get_my_notifications(start=0, limit=20):
    """
    Gibt Notification-Log-Einträge des aktuellen Users zurück.
    """
    user = frappe.session.user
    notifications = frappe.get_all(
        "Notification Log",
        filters={"for_user": user},
        fields=["name", "subject", "email_content", "document_type", "document_name", "creation", "read"],
        order_by="creation desc",
        start=int(start),
        page_length=int(limit),
    )
    return {"success": True, "data": notifications}
