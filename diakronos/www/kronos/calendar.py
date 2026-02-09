import frappe
from diakronos.scripts.get_hashed_asset import find_latest_hashed_file  # ← Import aus scripts/
from diakronos.kronos.api.permissions import (
    get_session_info,
    get_accessible_calendars,
    can_create_event,
    get_element_creation_dialog_defaults
)
from diakronos.kronos.api.calendar_get import get_calendar_events

def get_context(context):
    context.no_cache = 1
    context.title = "Kronos Kalender"

    # Login-Status sicher setzen
    user = frappe.session.user
    context.is_logged_in = user != "Guest" and user is not None
    context.user_initial = user[0].upper() if context.is_logged_in else None
    context.user_fullname = frappe.db.get_value("User", user, "full_name") or "Gast" if context.is_logged_in else None


    user = frappe.session.user
    context.user_initial = user[0].upper()
    context.user_fullname = frappe.db.get_value("User", user, "full_name") or user

    # CSRF explizit setzen (bewährt aus ERPNext)
    context.csrf_token = frappe.sessions.get_csrf_token()

    # Assets
    context.kronos_css = find_latest_hashed_file("kronos.bundle", "css")
    context.kronos_js = find_latest_hashed_file("kronos.bundle", "js")

    frappe.log_error(f"Context gesetzt: user={user}, csrf={context.csrf_token}", "Kronos Debug")

    