import frappe


def get_context(context):
    context.no_cache = 1
    context.title = "Diakonos Test"

    # Guest erlaubt – nur zu Testzwecken
    user = frappe.session.user
    user_doc = frappe.db.get_value(
        "User", user,
        ["full_name", "user_image", "email"],
        as_dict=True,
    ) or {}

    mitglied = frappe.db.get_value(
        "Mitglied",
        {"email": user_doc.get("email") or user},
        ["name", "vorname", "nachname", "status"],
        as_dict=True,
    )

    roles = frappe.get_roles(user)
    is_admin = "Mitgliederadministrator" in roles or "System Manager" in roles

    accessible_modules = []
    try:
        from diakronos.kronos.api.permissions import get_accessible_modules
        accessible_modules = get_accessible_modules()
    except Exception:
        pass

    context.user_fullname = user_doc.get("full_name") or user
    context.user_image = user_doc.get("user_image") or ""
    context.csrf_token = frappe.sessions.get_csrf_token()
    context.is_admin = is_admin
    context.mitglied = mitglied
    context.modules = accessible_modules
