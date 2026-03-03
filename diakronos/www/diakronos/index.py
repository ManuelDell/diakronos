import json
import frappe
from diakronos.scripts.get_hashed_asset import find_latest_hashed_file
from diakronos.diakronos.doctype.diakronos_einstellungen.diakronos_einstellungen import (
    KNOWN_MODULES,
    MODULE_DEFAULTS,
    MODULE_ROUTES,
)
from diakronos.kronos.api.permissions import _can_access_desk

no_cache = 1


def get_context(context):
    user = frappe.session.user
    if user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect

    accessible = _get_accessible_modules(user)

    # 1. Gespeicherte Nutzerpräferenz prüfen (hat Vorrang)
    try:
        user_settings = frappe.db.get_user_settings("Diakronos") or {}
        if isinstance(user_settings, str):
            user_settings = json.loads(user_settings) if user_settings else {}
    except Exception:
        user_settings = {}

    pref = user_settings.get("home_module")
    if pref and any(m["module_name"] == pref for m in accessible):
        frappe.local.flags.redirect_location = _module_route(pref)
        raise frappe.Redirect

    # 2. Nur ein Modul zugänglich → automatisch weiterleiten
    if len(accessible) == 1:
        frappe.local.flags.redirect_location = _module_route(accessible[0]["module_name"])
        raise frappe.Redirect

    # 3. Startseite anzeigen
    user_doc = frappe.get_doc("User", user)
    context.modules          = accessible
    context.current_pref     = pref or ""
    context.user_fullname    = user_doc.full_name or user
    context.user_initial     = (user_doc.full_name or user)[0].upper()
    context.user_image       = user_doc.user_image or ""
    context.csrf_token       = frappe.sessions.get_csrf_token()
    context.kronos_css       = find_latest_hashed_file("kronos.bundle", "css")
    context.can_access_desk  = _can_access_desk(user)
    context.no_cache         = 1


# ------------------------------------------------------------------ #
# Hilfsfunktionen (auch von permissions.py importiert)                #
# ------------------------------------------------------------------ #

def _get_accessible_modules(user):
    """
    Gibt die für 'user' zugänglichen Diakronos-Module zurück.
    Filtert nach globaler Sichtbarkeit (Diakronos Einstellungen) und Rollen.
    """
    try:
        settings = frappe.get_single("Diakronos Einstellungen")
    except Exception:
        return []

    user_roles = set(frappe.get_roles(user))
    result = []

    for prefix, module_name in KNOWN_MODULES:
        mod_defaults = MODULE_DEFAULTS.get(module_name, {})

        # Sichtbarkeit: None bedeutet "noch nie in Diakronos Einstellungen gespeichert"
        # → Fallback auf MODULE_DEFAULTS (nicht auf 0!)
        sichtbar = getattr(settings, f"{prefix}_sichtbar", None)
        if sichtbar is None:
            sichtbar = mod_defaults.get("im_app_bereich_anzeigen", 1)
        if not sichtbar:
            continue

        # Rollen-Einschränkung prüfen (leer = für alle sichtbar)
        role_rows = getattr(settings, f"{prefix}_rollen", None) or []
        if role_rows:
            allowed_roles = {row.role for row in role_rows}
            if not (user_roles & allowed_roles):
                continue

        # Icon und Anzeigename: Einstellungen haben Vorrang, sonst MODULE_DEFAULTS
        icon  = getattr(settings, f"{prefix}_icon", None) or mod_defaults.get("standard_icon", "")
        label = getattr(settings, f"{prefix}_anzeige_name", None) or mod_defaults.get("anzeige_name", module_name)

        result.append({
            "module_name": module_name,
            "prefix":      prefix,
            "anzeige_name": label,
            "icon":         icon,
            "route":        _module_route(module_name),
        })

    return result


def _module_route(module_name):
    """Gibt die Route für ein Modul zurück."""
    if module_name in MODULE_ROUTES:
        return MODULE_ROUTES[module_name]

    workspaces = frappe.get_all(
        "Workspace",
        filters={"module": module_name},
        fields=["name"],
        order_by="name",
        limit=1,
    )
    if workspaces:
        slug = workspaces[0]["name"].lower().replace(" ", "-")
        return f"/app/{slug}"

    return f"/app/{module_name.lower()}"
