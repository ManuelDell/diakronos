import frappe
from frappe.utils import add_days, nowdate


def delete_alte_anmeldeanfragen():
    """L\u00f6scht Anmeldeanfragen \u00e4lter als 14 Tage mit Status 'Anmeldeanfrage' oder 'Abgelehnt'."""
    cutoff = add_days(nowdate(), -14)

    anmeldungen = frappe.get_all(
        "Anmeldung",
        filters=[
            ["creation", "<", cutoff],
            ["status", "in", ["Anmeldeanfrage", "Abgelehnt"]],
        ],
        pluck="name",
    )

    deleted = 0
    for name in anmeldungen:
        try:
            frappe.delete_doc("Anmeldung", name, ignore_permissions=True)
            deleted += 1
        except Exception:
            frappe.log_error(f"Fehler beim L\u00f6schen von Anmeldung {name}")

    if deleted:
        frappe.db.commit()
        frappe.logger().info(f"Cleanup: {deleted} alte Anmeldeanfragen gel\u00f6scht.")
