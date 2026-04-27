import frappe


def get_context(context):
    context.no_cache = 1

    if frappe.session.user in ("Guest", None):
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect

    user = frappe.session.user
    user_doc = frappe.db.get_value("User", user, ["full_name", "user_image"], as_dict=True) or {}
    full_name = user_doc.get("full_name") or user

    context.title        = "Organigramm"
    context.user_fullname = full_name
    context.user_image   = user_doc.get("user_image") or ""
    context.csrf_token   = frappe.sessions.get_csrf_token()
