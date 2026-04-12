# diakronos/diakronos/kronos/api/permissions.py

import json
import frappe
from frappe import _
from frappe.model.utils.user_settings import get_user_settings as _get_user_settings, update_user_settings as _update_user_settings

DESK_ROLES = {"Kalenderadministrator"}

def _user_has_role(user, role_name):
    """Prüft, ob User die angegebene Role hat."""
    if user == "Administrator":
        return True
    roles = [r.role for r in frappe.get_all("Has Role", filters={"parent": user}, fields=["role"])]
    return role_name in roles


def _is_kalenderadministrator(user):
    """Prüft ob User die globale Kalenderadministrator-Rolle hat (oder Administrator ist)."""
    if user == "Administrator":
        return True
    return _user_has_role(user, "Kalenderadministrator")


def _is_moderator_of(user, calendar_doc):
    """Prüft ob User Moderator dieses Kalenders ist (via Kalendermoderatoren-Tabelle)."""
    if user == "Administrator":
        return True
    for row in calendar_doc.get("kalendermoderatoren") or []:
        if row.user == user:
            return True
    return False

def _can_access_desk(user):
    """Nur Administrator und Kalenderadministrator dürfen den Frappe-Desk betreten."""
    if user == "Administrator":
        return True
    return bool(DESK_ROLES & set(frappe.get_roles(user)))

@frappe.whitelist(allow_guest=False)
def get_session_info():
    user = frappe.session.user
    if user == "Guest":
        frappe.throw("Nicht angemeldet")
    user_doc = frappe.get_doc("User", user)
    accessible = get_accessible_calendars()
    can_moderate = any(c.get("is_moderator") for c in accessible)
    return {
        "initial": (user_doc.full_name or user)[0].upper(),
        "full_name": user_doc.full_name or user,
        "name": user,
        "user_image": user_doc.user_image or None,
        "can_access_desk": _can_access_desk(user),
        "can_moderate": can_moderate,
    }

@frappe.whitelist(allow_guest=False)
def get_accessible_calendars():
    """
    Gibt alle Kalender zurück, auf die der User mindestens Leserecht hat.
    Frontend erwartet: name, title, color, write (bool)
    """
    user = frappe.session.user
    if user == "Guest":
        return []

    try:
        is_global_admin = _is_kalenderadministrator(user)
        calendars = frappe.get_all("Kalender", fields=["name"])

        result = []
        for cal in calendars:
            doc = frappe.get_doc("Kalender", cal.name)

            # Kalenderadministrator hat vollen Zugriff auf alle Kalender
            if is_global_admin:
                result.append({
                    "name":            doc.name,
                    "title":           doc.calendar_name or doc.name,
                    "color":           doc.calendar_color or "#9ca3af",
                    "write":           True,
                    "is_moderator":    True,
                    "selbstverwaltet": bool(doc.selbstverwaltet),
                })
                continue

            can_read = False
            can_write = False

            # Leserechte prüfen
            for row in doc.get("leserechte") or []:
                if _user_has_role(user, row.role):
                    can_read = True

            # Schreibrechte prüfen
            for row in doc.get("schreibrechte") or []:
                if _user_has_role(user, row.role):
                    can_write = True
                    can_read = True  # Schreibrecht impliziert immer Leserecht

            is_mod = _is_moderator_of(user, doc)
            if is_mod:
                can_read  = True
                can_write = True

            if can_read:
                result.append({
                    "name":            doc.name,
                    "title":           doc.calendar_name or doc.name,
                    "color":           doc.calendar_color or "#9ca3af",
                    "write":           can_write,
                    "is_moderator":    is_mod,
                    "selbstverwaltet": bool(doc.selbstverwaltet),
                })

        return result

    except Exception as e:
        frappe.log_error(str(e), "get_accessible_calendars")
        return []
# diakronos/kronos/api/permissions.py

@frappe.whitelist(allow_guest=False)
def get_writable_calendars():
    """Gibt nur Kalender zurück, auf die der User Schreibzugriff hat."""
    accessible = get_accessible_calendars()
    return [
        {"name": c["name"], "calendar_name": c["title"], "calendar_color": c["color"]}
        for c in accessible if c.get("write")
    ]


# ------------------------------------------------------------------ #
# Diakronos Home – Modul-Zugriff & Nutzerpräferenz                    #
# ------------------------------------------------------------------ #

@frappe.whitelist(allow_guest=False)
def get_accessible_modules():
    """
    Gibt die für den aktuellen Nutzer zugänglichen Diakronos-Module zurück.
    Nutzt die Konfiguration aus 'Diakronos Einstellungen'.
    """
    from diakronos.diakronos.doctype.diakronos_einstellungen.diakronos_einstellungen import (
        KNOWN_MODULES, MODULE_DEFAULTS, MODULE_ROUTES,
    )
    user = frappe.session.user
    try:
        settings = frappe.get_single("Diakronos Einstellungen")
    except Exception:
        return []

    user_roles = set(frappe.get_roles(user))
    result = []
    for prefix, module_name in KNOWN_MODULES:
        mod_defaults = MODULE_DEFAULTS.get(module_name, {})
        sichtbar = getattr(settings, f"{prefix}_sichtbar", None)
        if sichtbar is None:
            sichtbar = mod_defaults.get("im_app_bereich_anzeigen", 1)
        if not sichtbar:
            continue
        role_rows = getattr(settings, f"{prefix}_rollen", None) or []
        if role_rows:
            allowed_roles = {row.role for row in role_rows}
            if not (user_roles & allowed_roles):
                continue
        icon  = getattr(settings, f"{prefix}_icon", None) or mod_defaults.get("standard_icon", "")
        label = getattr(settings, f"{prefix}_anzeige_name", None) or mod_defaults.get("anzeige_name", module_name)
        route = MODULE_ROUTES.get(module_name) or f"/app/{module_name.lower()}"
        result.append({
            "module_name":  module_name,
            "prefix":       prefix,
            "anzeige_name": label,
            "icon":         icon,
            "route":        route,
        })
    return result


@frappe.whitelist(allow_guest=False)
def set_home_preference(module_name):
    """
    Speichert die bevorzugte Startseite des Nutzers.
    module_name muss ein zugängliches Modul sein.
    """
    accessible = get_accessible_modules()
    if module_name and not any(m["module_name"] == module_name for m in accessible):
        frappe.throw("Kein Zugriff auf dieses Modul.")

    try:
        raw = _get_user_settings("Diakronos") or {}
        settings = json.loads(raw) if isinstance(raw, str) else (raw or {})
    except Exception:
        settings = {}

    settings["home_module"] = module_name
    _update_user_settings("Diakronos", frappe.as_json(settings), for_update=True)
    return {"ok": True}


@frappe.whitelist(allow_guest=False)
def clear_home_preference():
    """Löscht die Startseiten-Präferenz (zurück zu 'Automatisch')."""
    _update_user_settings("Diakronos", frappe.as_json({}), for_update=True)
    return {"ok": True}