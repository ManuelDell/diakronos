# Copyright (c) 2025, Dells Dienste and contributors
# For license information, please see license.txt

import frappe
from frappe import _

ADMIN_ROLES = ["System Manager", "Mitgliederadministrator"]


@frappe.whitelist()
def get_current_user_context():
    """
    Liefert den vollständigen User-Context für die Diakonos Vue-SPA.
    Returns: {
        user: str,
        mitglied: dict|null,
        is_admin: bool,
        is_admin_mode: bool,
        roles: list,
        modules: list,
        permissions: {
            can_view_mitglieder: bool,
            can_edit_mitglieder: bool,
            can_view_gruppen: bool,
            can_edit_gruppen: bool,
            can_view_bereiche: bool,
            can_view_dienstplan: bool,
            can_view_statistik: bool,
            can_view_dsgvo: bool,
            can_export_data: bool,
        }
    }
    """
    user = frappe.session.user

    user_doc = frappe.db.get_value(
        "User", user,
        ["full_name", "user_image", "email"],
        as_dict=True,
    ) or {}

    mitglied = frappe.db.get_value(
        "Mitglied",
        {"email": user_doc.get("email") or user},
        ["name", "vorname", "nachname", "status", "ancestor_path"],
        as_dict=True,
    )

    roles = frappe.get_roles(user)
    is_admin = any(r in roles for r in ADMIN_ROLES)

    # Admin-Mode prüfen (nur relevant wenn is_admin)
    is_admin_mode = False
    if is_admin:
        from diakronos.diakonos.api.zugriff import verify_admin_session
        try:
            admin_check = verify_admin_session()
            is_admin_mode = admin_check.get("active", False)
        except Exception:
            pass

    # Module (aus Diakronos Einstellungen)
    accessible_modules = []
    try:
        from diakronos.kronos.api.permissions import get_accessible_modules
        accessible_modules = get_accessible_modules()
    except Exception:
        pass

    # Permissions berechnen
    perms = _compute_permissions(user, mitglied, roles, is_admin, is_admin_mode)

    return {
        "user": user,
        "user_fullname": user_doc.get("full_name") or user,
        "user_image": user_doc.get("user_image") or "",
        "email": user_doc.get("email") or user,
        "mitglied": mitglied,
        "is_admin": is_admin,
        "is_admin_mode": is_admin_mode,
        "roles": roles,
        "modules": accessible_modules,
        "permissions": perms,
        "csrf_token": frappe.sessions.get_csrf_token(),
    }


@frappe.whitelist()
def get_mitglied_permissions(mitglied_id):
    """
    Gibt die Permission-Map für ein bestimmtes Mitglied zurück.
    Prüft, ob der aktuelle User Zugriff auf das Mitglied hat.
    """
    user = frappe.session.user
    current_mitglied = _get_current_user_mitglied()
    target = frappe.db.get_value(
        "Mitglied", mitglied_id,
        ["name", "ancestor_path", "email", "status"],
        as_dict=True,
    )

    if not target:
        frappe.throw(_("Mitglied nicht gefunden."), frappe.DoesNotExistError)

    roles = frappe.get_roles(user)
    is_admin = any(r in roles for r in ADMIN_ROLES)
    is_admin_mode = False
    if is_admin:
        from diakronos.diakonos.api.zugriff import verify_admin_session
        try:
            is_admin_mode = verify_admin_session().get("active", False)
        except Exception:
            pass

    # Admin hat generell Zugriff (kein separater Admin-Mode mehr nötig)
    if is_admin:
        return {
            "can_view": True,
            "can_edit": True,
            "can_delete": False,
            "can_view_sensitive": True,
            "reason": "admin_role",
        }

    # User ohne eigene Mitglied-Zuordnung: nur Selbstzugriff via Email-Match
    if not current_mitglied:
        user_email = frappe.db.get_value("User", user, "email")
        can_view = target.email == user_email
        return {
            "can_view": can_view,
            "can_edit": can_view,
            "can_delete": False,
            "can_view_sensitive": False,
            "reason": "self" if can_view else "no_access",
        }

    # User hat ancestor_path: Gruppen-/Bereichs-basierte Prüfung
    user_path = current_mitglied.get("ancestor_path", "|")
    target_path = target.get("ancestor_path", "|")

    # Gemeinsame Gruppen/Bereiche finden
    can_view = _paths_overlap(user_path, target_path)

    # Fallback: eigenes Profil immer erlaubt (auch wenn Pfade leer sind)
    if not can_view and target.email == current_mitglied.get("email"):
        can_view = True

    return {
        "can_view": can_view,
        "can_edit": can_view and target.name == current_mitglied.get("name"),
        "can_delete": False,
        "can_view_sensitive": False,
        "reason": "ancestor_path" if can_view else "no_overlap",
    }


@frappe.whitelist()
def check_permission(doctype, docname, permission_type="read"):
    """
    Generische Permission-Check API.
    doctype: 'Mitglied' | 'Gruppe' | 'Untergruppe' | 'Dienstbereich'
    permission_type: 'read' | 'write' | 'create' | 'delete'
    """
    user = frappe.session.user
    roles = frappe.get_roles(user)
    is_admin = any(r in roles for r in ADMIN_ROLES)

    is_admin_mode = False
    if is_admin:
        from diakronos.diakonos.api.zugriff import verify_admin_session
        try:
            is_admin_mode = verify_admin_session().get("active", False)
        except Exception:
            pass

    # Admin hat generell Vollzugriff (kein separater Admin-Mode mehr nötig)
    if is_admin:
        return {"allowed": True, "reason": "admin_role"}

    # Normale User: je nach Doctype prüfen
    if doctype == "Mitglied":
        perms = get_mitglied_permissions(docname)
        allowed = perms.get("can_edit" if permission_type in ("write", "create", "delete") else "can_view", False)
        return {"allowed": allowed, "reason": perms.get("reason")}

    if doctype in ("Gruppe", "Untergruppe", "Dienstbereich"):
        # Prüfen, ob User Mitglied dieser Gruppe/Bereich ist
        current_mitglied = _get_current_user_mitglied()
        if not current_mitglied:
            return {"allowed": False, "reason": "no_mitglied"}

        user_path = current_mitglied.get("ancestor_path", "|")
        target = frappe.db.get_value(doctype, docname, "ancestor_path")
        target_path = target or "|"
        allowed = _paths_overlap(user_path, target_path) and permission_type == "read"
        return {"allowed": allowed, "reason": "ancestor_path" if allowed else "no_overlap"}

    return {"allowed": False, "reason": "unsupported_doctype"}


# ── Helpers ─────────────────────────────────────────────────────────────────

def _get_current_user_mitglied():
    """Holt den Mitglied-Datensatz des aktuellen Users."""
    user = frappe.session.user
    email = frappe.db.get_value("User", user, "email") or user
    return frappe.db.get_value(
        "Mitglied", {"email": email},
        ["name", "ancestor_path", "email", "status"],
        as_dict=True,
    )


def _compute_permissions(user, mitglied, roles, is_admin, is_admin_mode):
    """Berechnet die feingranulare Permission-Map."""
    perms = {
        "can_view_mitglieder": False,
        "can_edit_mitglieder": False,
        "can_view_gruppen": False,
        "can_edit_gruppen": False,
        "can_view_bereiche": False,
        "can_view_dienstplan": False,
        "can_view_statistik": False,
        "can_view_dsgvo": False,
        "can_export_data": False,
    }

    if is_admin:
        # Admin hat generell Vollzugriff (kein separater Admin-Mode mehr nötig)
        perms.update({k: True for k in perms})
        return perms

    # Normale User
    if mitglied:
        perms.update({
            "can_view_mitglieder": True,
            "can_edit_mitglieder": True,  # Eigenes Profil
            "can_view_gruppen": bool(mitglied.get("ancestor_path")),
            "can_view_bereiche": bool(mitglied.get("ancestor_path")),
            "can_view_dienstplan": True,
        })

    return perms


def _paths_overlap(user_path, target_path):
    """
    Prüft, ob zwei ancestor_paths überlappen.
    Format: /Gruppe1/Gruppe2/|/BereichA/
    """
    if not user_path or not target_path:
        return False

    def _extract_segments(path):
        # Gruppen und Bereiche trennen
        parts = path.split("|")
        gruppen = [g for g in parts[0].split("/") if g]
        bereiche = [b for b in parts[1].split("/") if b] if len(parts) > 1 else []
        return set(gruppen), set(bereiche)

    user_gruppen, user_bereiche = _extract_segments(user_path)
    target_gruppen, target_bereiche = _extract_segments(target_path)

    # Überlappung in Gruppen ODER Bereichen
    return bool(user_gruppen & target_gruppen or user_bereiche & target_bereiche)
