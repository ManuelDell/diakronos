import frappe

ACTIVE_STATUS = {"Mitglied", "Gast"}
PASSIVE_TO_ACTIVE = {
    "Passiver Gast":    "Gast",
    "Passives Mitglied": "Mitglied",
}


def mitglied_zu_nutzer(doc, method=None):
    """
    Server Action: Legt einen Frappe-User für das Mitglied an
    oder verknüpft einen bestehenden User.

    Nutzertyp ist immer "Website User" – verhindert Frappe-Desk-Zugang.
    Passiver Status wird automatisch auf aktiven Status angehoben.
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
        _ensure_website_user(user)
        _activate_user(user)
        frappe.db.set_value("Mitglied", doc.name, "benutzer_mit_mitglied_anlegen", 1, update_modified=False)
        _activate_mitglied_status(doc)
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
        "user_type":  "Website User",
        "send_welcome_email": 1,
        "roles": [{"role": "Mitglied"}],
    })
    user.insert(ignore_permissions=True)

    frappe.db.set_value("Mitglied", doc.name, "benutzer_mit_mitglied_anlegen", 1, update_modified=False)
    _activate_mitglied_status(doc)
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


def _ensure_website_user(user):
    """Stellt sicher dass der User kein System User (Desk-Zugang) ist."""
    roles = [r.role for r in user.get("roles") or []]
    # Admins behalten System User type
    if "System Manager" in roles or "Mitgliederadministrator" in roles:
        return
    if user.user_type != "Website User":
        user.user_type = "Website User"
        user.save(ignore_permissions=True)


def _activate_user(user):
    if not user.enabled:
        frappe.db.set_value("User", user.name, "enabled", 1)


def _activate_mitglied_status(doc):
    """Hebt passiven Status auf aktiven an wenn User erstellt wird."""
    current_status = frappe.db.get_value("Mitglied", doc.name, "status") or doc.status
    new_status = PASSIVE_TO_ACTIVE.get(current_status)
    if new_status:
        frappe.db.set_value("Mitglied", doc.name, "status", new_status, update_modified=False)
