import json
import frappe
from diakronos.scripts.get_hashed_asset import find_latest_hashed_file


def get_context(context):
    context.no_cache = 1
    context.title = "Terminmoderation"

    user = frappe.session.user
    if user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect

    from diakronos.kronos.api.permissions import get_accessible_calendars
    allowed = get_accessible_calendars()
    can_moderate = any(c.get("is_moderator") for c in allowed)
    if not can_moderate:
        frappe.throw("Keine Moderationsberechtigung")

    user_doc = frappe.db.get_value("User", user, ["full_name", "user_image"], as_dict=True) or {}
    full_name = user_doc.get("full_name") or user
    context.user_initial  = full_name[0].upper()
    context.user_fullname = full_name
    context.user_image    = user_doc.get("user_image") or ""
    context.csrf_token    = frappe.sessions.get_csrf_token()
    context.user_roles_json = json.dumps(frappe.get_roles(user))
    context.kanban_css = find_latest_hashed_file("kanban.bundle", "css")
    context.kanban_js  = find_latest_hashed_file("kanban.bundle", "js")
