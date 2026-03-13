# diakronos/diakronos/kronos/api/permissions.py

import json
import frappe
from frappe import _
from datetime import datetime
from frappe.model.utils.user_settings import get_user_settings as _get_user_settings, update_user_settings as _update_user_settings

DESK_ROLES = {"Kalenderguru"}

def _user_has_role(user, role_name):
    """Prüft, ob User die angegebene Role hat."""
    if user == "Administrator":
        return True
    roles = [r.role for r in frappe.get_all("Has Role", filters={"parent": user}, fields=["role"])]
    return role_name in roles

def _can_access_desk(user):
    """Nur Administrator und Kalenderguru dürfen den Frappe-Desk betreten."""
    if user == "Administrator":
        return True
    return bool(DESK_ROLES & set(frappe.get_roles(user)))

@frappe.whitelist(allow_guest=False)
def get_session_info():
    user = frappe.session.user
    if user == "Guest":
        frappe.throw("Nicht angemeldet")
    user_doc = frappe.get_doc("User", user)
    return {
        "initial": (user_doc.full_name or user)[0].upper(),
        "full_name": user_doc.full_name or user,
        "name": user,
        "user_image": user_doc.user_image or None,
        "can_access_desk": _can_access_desk(user),
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
        calendars = frappe.get_all("Kalender", fields=["name"])

        result = []
        for cal in calendars:
            doc = frappe.get_doc("Kalender", cal.name)

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

            if can_read:
                result.append({
                    "name": doc.name,
                    "title": doc.calendar_name or doc.name,
                    "color": doc.calendar_color or "#9ca3af",  # var(--gray-400)
                    "write": can_write
                })

        return result

    except Exception as e:
        frappe.log_error(str(e), "get_accessible_calendars")
        return []
# diakronos/kronos/api/permissions.py

@frappe.whitelist(allow_guest=False)
def get_writable_calendars():
    user = frappe.session.user
    if user == "Administrator":
        return frappe.get_all("Kalender", fields=["name", "calendar_name", "calendar_color"], order_by="calendar_name")

    # Kalender, bei denen der User in der Child-Table "schreibrechte" vorkommt
    writable = frappe.get_all(
        "Kalender",
        filters={
            "schreibrechte": ["like", f"%{user}%"]  # funktioniert bei Text-Feld, aber bei Child-Table unsicher
        },
        fields=["name", "calendar_name", "calendar_color"],
        order_by="calendar_name"
    )

    # Besser: Child-Table abfragen
    if not writable:
        writable = frappe.get_all(
            "Kalender Has Role",
            filters={"role": ["in", frappe.get_roles(user)]},
            fields=["parent as name"],
            distinct=True
        )
        writable = frappe.get_all(
            "Kalender",
            filters={"name": ["in", [w.name for w in writable]]},
            fields=["name", "calendar_name", "calendar_color"],
            order_by="calendar_name"
        )

    return writable

@frappe.whitelist(allow_guest=False)
def can_create_event():
    """
    Prüfe ob aktueller Nutzer Events erstellen darf.
    Wird aufgerufen wenn User auf Tag im Kalender klickt.
    Returns: Dict mit can_create Flag und verfügbaren Kalendern
    """
    user = frappe.session.user
    if user == "Guest":
        return {'can_create': False, 'default_calendar': None, 'writable_calendars': []}

    accessible = get_accessible_calendars()
    writable_calendars = [
        {'label': c['title'], 'value': c['name']}
        for c in accessible if c.get('write')
    ]
    default_calendar = writable_calendars[0]['value'] if writable_calendars else None

    return {
        'can_create': len(writable_calendars) > 0,
        'default_calendar': default_calendar,
        'writable_calendars': writable_calendars
    }

@frappe.whitelist(allow_guest=False)
def get_element_creation_dialog_defaults(date_str=None, calendar_name=None):
    """
    Hole Default-Werte für Element-Erstellungs-Dialog
    
    Args:
        date_str: Datum als String "2026-01-05"
        calendar_name: Standard-Kalender
    
    Returns:
        Dict mit defaults und can_create Flag
    """
    try:
        can_create_response = can_create_event()
        if not can_create_response['can_create']:
            return {
                'can_create': False,
                'defaults': {},
                'writable_calendars': [],
                'error': _('Keine Berechtigung zum Erstellen')
            }
        
        selected_calendar = calendar_name or can_create_response['default_calendar']
        if selected_calendar:
            if not any(cal['value'] == selected_calendar for cal in can_create_response['writable_calendars']):
                frappe.throw(f'Keine Berechtigung für Kalender: {selected_calendar}')
        
        defaults = {
            'element_calendar': selected_calendar,
        }
        
        if date_str:
            try:
                dt = datetime.strptime(date_str, '%Y-%m-%d')
                start_time = dt.replace(hour=10, minute=0, second=0)
                end_time = start_time.replace(hour=11)
                defaults['element_start'] = start_time.strftime('%Y-%m-%d %H:%M:%S')
                defaults['element_end'] = end_time.strftime('%Y-%m-%d %H:%M:%S')
            except Exception as e:
                frappe.log_error(
                    f'Fehler beim Datums-Parsing: {str(e)}',
                    'get_element_creation_dialog_defaults'
                )
        
        return {
            'can_create': True,
            'defaults': defaults,
            'writable_calendars': can_create_response['writable_calendars']
        }
        
    except frappe.ValidationError as ve:
        return {
            'can_create': False,
            'defaults': {},
            'writable_calendars': [],
            'error': str(ve)
        }
    except Exception as e:
        frappe.log_error(str(e), 'get_element_creation_dialog_defaults')
        return {
            'can_create': False,
            'defaults': {},
            'writable_calendars': [],
            'error': str(e)
        }


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