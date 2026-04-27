import json
import frappe
from frappe.utils import now_datetime, add_to_date
from frappe import _

from diakronos.diakonos.api.audit import log as audit_log

ADMIN_MODE_CACHE_KEY = "diakonos_admin_mode:{user}"
ADMIN_MODE_TTL = 1800  # 30 Minuten in Sekunden
ADMIN_ROLES = ["System Manager", "Mitgliederadministrator"]


def _get_cache_key(user=None):
    """Generiert den Cache-Key für den Admin-Mode eines Users."""
    if user is None:
        user = frappe.session.user
    return ADMIN_MODE_CACHE_KEY.format(user=user)


def _has_admin_role():
    """Prüft, ob der aktuelle User eine Admin-Rolle besitzt."""
    user_roles = frappe.get_roles(frappe.session.user)
    return any(role in user_roles for role in ADMIN_ROLES)


@frappe.whitelist()
def request_admin_access(reason):
    """
    ⚠️  DEPRECATED — Admin-Mode wurde abgelöst durch den Policy Enforcement Layer.
    Diese Funktion existiert nur noch für Rückwärtskompatibilität.
    """
    frappe.msgprint(
        _("Der Admin-Mode wurde abgelöst. Admins können jetzt direkt bearbeiten. "
          "Bei DSGVO-relevanten Änderungen wird automatisch eine Begründung abgefragt."),
        indicator="blue",
    )
    return {
        "success": True,
        "deprecated": True,
        "message": _("Admin-Mode ist nicht mehr nötig."),
    }


@frappe.whitelist()
def verify_admin_session():
    """
    Prüft, ob der aktuelle User einen gültigen Admin-Mode hat.
    Returns: {"active": True/False, "reason": "...", "expires_at": "..."}
    """
    user = frappe.session.user
    cache_key = _get_cache_key(user)
    cached_value = frappe.cache().get_value(cache_key)

    if not cached_value:
        return {
            "active": False,
            "reason": None,
            "expires_at": None,
        }

    try:
        session_data = json.loads(cached_value) if isinstance(cached_value, str) else cached_value
    except (json.JSONDecodeError, TypeError):
        # Ungültiger Cache-Eintrag – löschen
        frappe.cache().delete_value(cache_key)
        return {
            "active": False,
            "reason": None,
            "expires_at": None,
        }

    # Prüfen, ob die Session abgelaufen ist (zusätzliche Sicherheit)
    expires_at = session_data.get("expires_at")
    if expires_at and now_datetime() > frappe.utils.get_datetime(expires_at):
        frappe.cache().delete_value(cache_key)
        return {
            "active": False,
            "reason": None,
            "expires_at": None,
        }

    return {
        "active": True,
        "reason": session_data.get("reason"),
        "expires_at": session_data.get("expires_at"),
    }


@frappe.whitelist()
def revoke_admin_access():
    """
    Beendet den Admin-Mode für den aktuellen User.
    """
    user = frappe.session.user
    cache_key = _get_cache_key(user)

    # Prüfen, ob ein aktiver Admin-Mode existiert
    cached_value = frappe.cache().get_value(cache_key)
    had_active_session = bool(cached_value)

    frappe.cache().delete_value(cache_key)

    if had_active_session:
        audit_log(
            action_typ="Berechtigungsänderung",
            target_doctype="User",
            target_name=user,
            begruendung="Admin-Mode manuell beendet"
        )

    return {
        "success": True,
        "message": _("Admin-Mode wurde beendet.") if had_active_session else _("Kein aktiver Admin-Mode vorhanden."),
    }


@frappe.whitelist()
def get_audit_log(limit=50):
    """
    Gibt Audit-Log-Einträge zurück (nur für System Manager).
    """
    if "System Manager" not in frappe.get_roles(frappe.session.user):
        frappe.throw(
            _("Nur System Manager dürfen den Audit-Log einsehen."),
            frappe.PermissionError
        )

    limit = int(limit)
    if limit < 1:
        limit = 1
    if limit > 500:
        limit = 500

    logs = frappe.get_all(
        "Audit Log",
        fields=[
            "name",
            "zeitstempel",
            "action_typ",
            "actor",
            "target_doctype",
            "target_name",
            "begruendung",
            "notification_gesendet",
        ],
        order_by="zeitstempel desc",
        limit_page_length=limit,
    )

    return {
        "success": True,
        "count": len(logs),
        "data": logs,
    }
