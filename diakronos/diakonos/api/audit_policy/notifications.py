import frappe
from frappe import _
from frappe.utils import get_url


def send_notification(audit_log_name, target_user=None, subject=None, message=None, email=None):
    """Sendet In-App- und E-Mail-Benachrichtigung basierend auf User Notification Preferences."""
    if not target_user:
        return

    # Prüfe Benachrichtigungseinstellungen des Users
    prefs = frappe.db.get_value(
        "User Notification Preference",
        {"user": target_user},
        ["notify_in_app", "notify_email", "email"],
        as_dict=True,
    )

    if not prefs:
        # Fallback: Standardverhalten
        notify_in_app = True
        notify_email = True
        user_email = email or frappe.db.get_value("User", target_user, "email")
    else:
        notify_in_app = bool(prefs.get("notify_in_app"))
        notify_email = bool(prefs.get("notify_email"))
        user_email = prefs.get("email") or email or frappe.db.get_value("User", target_user, "email")

    audit_log = frappe.get_doc("Audit Log", audit_log_name)

    # Prüfe ob bereits gesendet
    if audit_log.notification_gesendet:
        return

    if not subject:
        subject = _("Audit-Ereignis: {0}").format(audit_log.action_typ)

    if not message:
        message = _(
            "Aktion: {action}<br>Ausführender: {actor}<br>"
            "Ziel: {target_doctype} / {target_name}"
        ).format(
            action=audit_log.action_typ,
            actor=audit_log.actor,
            target_doctype=audit_log.target_doctype or "–",
            target_name=audit_log.target_name or "–",
        )

    # In-App-Benachrichtigung
    if notify_in_app:
        try:
            notification = frappe.get_doc({
                "doctype": "Notification Log",
                "subject": subject,
                "email_content": message,
                "for_user": target_user,
                "type": "Alert",
                "document_type": "Audit Log",
                "document_name": audit_log_name,
            })
            notification.insert(ignore_permissions=True)
        except Exception:
            frappe.log_error("Audit In-App Notification failed")

    # E-Mail-Benachrichtigung
    if notify_email and user_email:
        try:
            frappe.sendmail(
                recipients=[user_email],
                subject=subject,
                message=message,
                reference_doctype="Audit Log",
                reference_name=audit_log_name,
            )
        except Exception:
            frappe.log_error("Audit E-Mail Notification failed")

    # Flag setzen, dass Notification versendet wurde
    try:
        frappe.db.sql(
            "UPDATE `tabAudit Log` SET notification_gesendet = 1 WHERE name = %s",
            (audit_log_name,)
        )
    except Exception:
        pass
