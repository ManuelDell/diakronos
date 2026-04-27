import frappe
from frappe.utils import add_to_date, now_datetime, cint
from frappe import _


def anonymize_expired_audit_logs():
    """
    Nightly Job: Anonymisiert Audit-Logs älter als die konfigurierte Aufbewahrungsfrist.
    DSGVO-konform: Kein physisches Löschen, sondern Pseudonymisierung.
    """
    try:
        retention_days = cint(frappe.db.get_single_value("Diakronos Einstellungen", "audit_log_retention_days"))
    except Exception:
        retention_days = 0

    retention_days = retention_days or 1095  # Default: 3 Jahre

    if retention_days <= 0:
        return

    cutoff_date = add_to_date(now_datetime(), days=-retention_days)

    logs = frappe.get_all(
        "Audit Log",
        filters={
            "anonymized_at": ["is", "not set"],
            "zeitstempel": ["<", cutoff_date],
        },
        fields=["name", "actor", "target_user", "old_value", "new_value", "confirm_reason", "ip_address", "user_agent"],
        limit=1000,
    )

    for log in logs:
        frappe.db.set_value(
            "Audit Log",
            log.name,
            {
                "actor": _hash_identifier(log.actor),
                "target_user": _hash_identifier(log.target_user),
                "old_value": "***" if log.old_value else None,
                "new_value": "***" if log.new_value else None,
                "confirm_reason": "***" if log.confirm_reason else None,
                "ip_address": None,
                "user_agent": None,
                "anonymized_at": now_datetime(),
            },
            update_modified=False,
        )

    frappe.db.commit()

    if logs:
        frappe.logger().info(f"Anonymisiert {len(logs)} Audit-Log-Einträge (alter als {retention_days} Tage).")


def _hash_identifier(value):
    """Erzeugt einen deterministischen Hash für einen Identifier mit Site-Salt."""
    if not value:
        return None
    import hashlib
    # Site-spezifischer Salt verhindert Rainbow-Table-Angriffe über verschiedene Instanzen
    salt = frappe.local.site or "diakronos"
    return f"sha256:{hashlib.sha256((value + salt).encode()).hexdigest()}"
