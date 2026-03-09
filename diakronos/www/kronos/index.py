import frappe
from diakronos.scripts.get_hashed_asset import find_latest_hashed_file
from diakronos.diakronos.doctype.diakronos_einstellungen.diakronos_einstellungen import (
    MODULE_PAGES,
)
from diakronos.kronos.api.permissions import _can_access_desk

no_cache = 1


def get_context(context):
    user = frappe.session.user
    if user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect

    pages = _get_kronos_pages()

    # Smart-Redirect: nur 1 Tool → direkt dorthin
    if len(pages) == 1:
        frappe.local.flags.redirect_location = pages[0]["route"]
        raise frappe.Redirect

    user_doc = frappe.get_doc("User", user)
    context.pages            = pages
    context.user_fullname    = user_doc.full_name or user
    context.user_initial     = (user_doc.full_name or user)[0].upper()
    context.user_image       = user_doc.user_image or ""
    context.csrf_token       = frappe.sessions.get_csrf_token()
    context.kronos_css       = find_latest_hashed_file("kronos.bundle", "css")
    context.can_access_desk  = _can_access_desk(user)
    context.no_cache         = 1


def _get_kronos_pages():
    """
    Liest die hartcodierten Kronos-Tools (MODULE_PAGES) und übernimmt
    Name/Icon-Overrides aus Diakronos Einstellungen.
    """
    base_pages = MODULE_PAGES.get("Kronos", [])
    if not base_pages:
        return []

    try:
        settings = frappe.get_single("Diakronos Einstellungen")
    except Exception:
        settings = None

    result = []
    for page in base_pages:
        key = page["key"]
        field_name = f"kronos_{key}_bezeichnung"
        field_icon = f"kronos_{key}_icon"

        name = (
            (getattr(settings, field_name, None) if settings else None)
            or page["default_name"]
        )
        icon = (
            (getattr(settings, field_icon, None) if settings else None)
            or page["default_icon"]
        )

        result.append({
            "key":   key,
            "name":  name,
            "route": page["route"],
            "icon":  icon,
        })

    return result
