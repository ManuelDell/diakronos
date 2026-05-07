import frappe


def execute():
    """
    Migriert bestehende Mitglied-Status-Werte auf das neue Modell:
      Mitglied  → Mitglied
      Gast      → Gast
      Kind      → Gast
      Inaktiv   → Passives Mitglied
      Archiviert→ Passives Mitglied

    Synchronisiert außerdem den Frappe-User enabled/disabled-Status:
      aktive Status (Mitglied, Gast) → User enabled = 1
      passive Status                 → User enabled = 0
    """
    mapping = {
        "Kind":       "Gast",
        "Inaktiv":    "Passives Mitglied",
        "Archiviert": "Passives Mitglied",
    }

    for old_status, new_status in mapping.items():
        frappe.db.sql(
            "UPDATE `tabMitglied` SET status = %s WHERE status = %s",
            (new_status, old_status),
        )

    frappe.db.commit()

    # Frappe-User synchronisieren
    alle = frappe.get_all(
        "Mitglied",
        fields=["name", "email", "status"],
    )

    passive = {"Passiver Gast", "Passives Mitglied"}

    for m in alle:
        if not m.email:
            continue
        user = frappe.db.get_value("User", {"email": m.email}, "name")
        if not user:
            continue
        should_enable = 0 if m.status in passive else 1
        current = frappe.db.get_value("User", user, "enabled")
        if current != should_enable:
            frappe.db.set_value("User", user, "enabled", should_enable)

    frappe.db.commit()
