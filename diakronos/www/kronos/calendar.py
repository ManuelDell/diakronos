import json
import frappe
from diakronos.scripts.get_hashed_asset import find_latest_hashed_file


def get_context(context):
    context.no_cache = 1
    context.title = "Kronos Kalender"

    user = frappe.session.user
    context.is_logged_in = user not in ("Guest", None)

    user_doc = frappe.db.get_value("User", user, ["full_name", "user_image"], as_dict=True) or {}
    full_name = user_doc.get("full_name") or user
    context.user_initial  = full_name[0].upper()
    context.user_fullname = full_name
    context.user_image    = user_doc.get("user_image") or ""

    context.csrf_token      = frappe.sessions.get_csrf_token()
    context.user_roles_json = json.dumps(frappe.get_roles(user))
    context.kronos_css      = find_latest_hashed_file("kronos.bundle", "css")
    context.kronos_js       = find_latest_hashed_file("kronos.bundle", "js")
