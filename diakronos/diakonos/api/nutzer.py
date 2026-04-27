import frappe
from frappe.utils import now_datetime


def mitglied_zu_nutzer(doc, method=None):
    """
    Server Action: Legt einen Frappe-User für das Mitglied an
    oder verknüpft einen bestehenden User.
    """
    if not doc.email:
        frappe.throw(
            "Das Mitglied hat keine E-Mail-Adresse. Bitte zuerst eine E-Mail eintragen.",
            title="E-Mail fehlt",
        )

    email = doc.email.strip().lower()

    if frappe.db.exists("User", email):
        user = frappe.get_doc("User", email)
        _ensure_mitglied_role(user)
        frappe.db.set_value("Mitglied", doc.name, "benutzer_mit_mitglied_anlegen", 1, update_modified=False)
        frappe.msgprint(
            f"Benutzer <b>{email}</b> existiert bereits und wurde mit dem Mitglied verknüpft.",
            title="Benutzer verknüpft",
            indicator="blue",
        )
        return

    user = frappe.get_doc({
        "doctype":    "User",
        "email":      email,
        "first_name": doc.vorname or "",
        "last_name":  doc.nachname or "",
        "enabled":    1,
        "user_type":  "System User",
        "send_welcome_email": 1,
        "roles": [{"role": "Mitglied"}],
    })
    user.insert(ignore_permissions=True)

    frappe.db.set_value("Mitglied", doc.name, "benutzer_mit_mitglied_anlegen", 1, update_modified=False)
    frappe.db.commit()

    frappe.msgprint(
        f"Benutzer <b>{email}</b> wurde angelegt. Eine Willkommens-E-Mail wurde verschickt.",
        title="Benutzer erstellt",
        indicator="green",
    )


def _ensure_mitglied_role(user):
    existing_roles = [r.role for r in user.get("roles") or []]
    if "Mitglied" not in existing_roles:
        user.append("roles", {"role": "Mitglied"})
        user.save(ignore_permissions=True)
