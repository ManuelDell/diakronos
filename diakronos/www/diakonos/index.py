import frappe
from diakronos.diakonos.utils.frontend import get_frontend_assets


def get_context(context):
    context.no_cache = 1

    # ── 1. Auth-Check ──────────────────────────────────────────────────────────
    if frappe.session.user in ("Guest", None):
        frappe.local.flags.redirect_location = "/login?redirect-to=/diakonos"
        raise frappe.Redirect

    user = frappe.session.user
    user_doc = frappe.db.get_value(
        "User", user,
        ["full_name", "user_image", "email"],
        as_dict=True,
    ) or {}

    # ── 2. Mitglied-Link ───────────────────────────────────────────────────────
    mitglied = frappe.db.get_value(
        "Mitglied",
        {"email": user_doc.get("email") or user},
        ["name", "vorname", "nachname", "status"],
        as_dict=True,
    )

    # ── 3. Admin-Status ────────────────────────────────────────────────────────
    roles = frappe.get_roles(user)
    is_admin = "Mitgliederadministrator" in roles or "System Manager" in roles

    # ── 4. Sidebar-Module (aus Diakronos Einstellungen) ────────────────────────
    accessible_modules = []
    try:
        from diakronos.kronos.api.permissions import get_accessible_modules
        accessible_modules = get_accessible_modules()
    except Exception:
        pass

    js_file, css_files = get_frontend_assets("diakonos")

    context.title = "Diakonos"
    context.user_email = user_doc.get("email") or user
    context.user_fullname = user_doc.get("full_name") or user
    context.user_image = user_doc.get("user_image") or ""
    context.csrf_token = frappe.sessions.get_csrf_token()
    context.is_admin = is_admin
    context.mitglied = mitglied
    context.modules = accessible_modules
    context.js_file = js_file
    context.css_files = css_files
