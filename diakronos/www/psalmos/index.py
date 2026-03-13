# diakronos/www/psalmos/index.py
import frappe
from diakronos.scripts.get_hashed_asset import find_latest_hashed_file
from diakronos.kronos.api.permissions import _can_access_desk

no_cache = 1

PSALMOS_ROLES = {"Psalmos-Nutzer", "Administrator"}


def get_context(context):
    user = frappe.session.user

    # Gäste → Login
    if user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect

    # Berechtigungsprüfung: muss Psalmos-Nutzer oder Administrator sein
    roles = set(frappe.get_roles(user))
    if not (roles & PSALMOS_ROLES):
        frappe.local.flags.redirect_location = "/app"
        raise frappe.Redirect

    context.no_cache = 1
    context.title = "Psalmos"

    context.csrf_token   = frappe.sessions.get_csrf_token()
    context.user_initial = user[0].upper()
    context.user_fullname = frappe.db.get_value("User", user, "full_name") or user

    context.psalmos_css = find_latest_hashed_file("psalmos.bundle", "css")
    context.psalmos_js  = find_latest_hashed_file("psalmos.bundle", "js")
