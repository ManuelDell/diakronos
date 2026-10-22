"""Portierung von `diakonos/api/session.py` (P4g) — User-Context, 3 Endpunkte.

Quelle (READ-ONLY):
`referenz/diakronos-frappe/diakronos/diakonos/api/session.py`

Die SPA ruft die ORIGINAL-Pfade `diakronos.diakonos.api.session.<fn>` auf
(Aufrufliste des Frappe-Frontends).

ABWEICHUNG ZUM VERTRAG (gemeldet statt geraten, siehe Modul-Docstring von
`api/audit.py` und `api/audit_policy/`):
`frontend/BOOT_VERTRAG.md` fordert das Feld `user_email`. Das Original liefert
jedoch `email`. Der Port liefert BEIDE Schluessel (`email` 1:1 wie im Original,
`user_email` als Vertrags-Alias) — die SPA liest `user_email`, darf aber nicht
brechen, wenn ein Aufrufer den Originalnamen erwartet.

Der Vertrag nennt weitere Felder, die das Original NICHT liefert (`church_name`,
`logo_url`). Die sind NICHT Teil dieser Karte (sie gehoeren zum Boot-Schritt,
`spa.py`), deshalb werden sie hier nicht erfunden.

`csrf_token`: Das Original ruft `frappe.sessions.get_csrf_token()`. Die
Compat-Schicht hat keine Session-/CSRF-Verwaltung (siehe `session.py`).
Der Port liefert deshalb einen leeren String statt eines erfundenen
"Dummy-Tokens" — Aufgabe bleibt offen, siehe Dokument.

Frappe-Aufruf -> Compat-Schicht:

    frappe.session.user        -> session.user
    frappe.db.get_value(...)   -> get_value(...)   (as_dict=True fuer Dict)
    frappe.get_roles(user)     -> get_roles(user)
    frappe.sessions.get_csrf_token()
                               -> "" (kein CSRF im Compat, s.o.)
    frappe.throw(msg, exc)     -> throw(msg, exc)
    frappe._(...)              -> (i18n entfernt, Rohstring)
    kronos.api.permissions.get_accessible_modules
                               -> diakronos_app.api.kronos.permissions.get_accessible_modules
"""

from __future__ import annotations

# Original-Frappe-Pfad der SPA (Registry-Schluessel, s. registry.py).
FRAPPE_MODULE = "diakronos.diakonos.api.session"

from diakronos_app.frappe_compat.api_helpers import get_value, session, throw
from diakronos_app.frappe_compat.exceptions import DoesNotExistError
from diakronos_app.frappe_compat.permissions import (
    check_permission as _compat_check_permission,
    get_roles,
    mitglied_permissions as _compat_mitglied_permissions,
)
from diakronos_app.frappe_compat.registry import whitelist

ADMIN_ROLES = ["System Manager", "Mitgliederadministrator"]


@whitelist(allow_guest=False)
def sitzung_status(request=None):
    """Identität und CSRF der aktuellen Sitzung, zum Fortsetzen im offenen Tab."""
    from diakronos_app.frappe_compat import sitzungen
    from diakronos_app.frappe_compat.auth_middleware import sid_aus_headers

    sid = sid_aus_headers(request.headers) if request else None
    daten = sitzungen.lesen(sid) if sid else None
    if not daten or daten.get("user") != session.user:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=401, content={
            "message": "Deine Anmeldung ist abgelaufen. Bitte melde dich neu an.",
            "exc_type": "SessionExpired",
        })
    return {"user": session.user, "csrf_token": daten.get("csrf_token") or ""}


@whitelist(allow_guest=False)
def get_current_user_context():
    """Vollstaendiger User-Context fuer die Diakonos Vue-SPA.

    Returns: {
        user: str,
        user_fullname: str,
        user_email: str,   # Vertrags-Alias (BOOT_VERTRAG.md)
        user_image: str,
        email: str,        # Originalname (session.py)
        mitglied: dict|null,
        is_admin: bool,
        is_admin_mode: bool,
        roles: list,
        modules: list,
        permissions: {...},
        csrf_token: str,
    }
    """
    user = session.user

    user_doc = get_value(
        "User", user,
        ["full_name", "user_image", "email"],
        as_dict=True,
    ) or {}

    mitglied = get_value(
        "Mitglied",
        {"email": user_doc.get("email") or user},
        ["name", "vorname", "nachname", "status", "ancestor_path"],
        as_dict=True,
    )

    roles = get_roles(user)
    is_admin = any(r in roles for r in ADMIN_ROLES)

    # Admin-Mode pruefen (nur relevant wenn is_admin).
    is_admin_mode = False

    # Module (aus Diakronos Einstellungen). Original faengt HIER alles ab;
    # ein Fehler beim Modul-Laden darf den User-Context nie verhindern.
    accessible_modules = []
    try:
        from diakronos_app.api.kronos.permissions import get_accessible_modules

        accessible_modules = get_accessible_modules()
    except Exception:  # noqa: BLE001 — 1:1 wie im Original (try/except/pass)
        pass

    perms = _compute_permissions(user, mitglied, roles, is_admin, is_admin_mode)

    email = user_doc.get("email") or user
    return {
        "user": user,
        "user_fullname": user_doc.get("full_name") or user,
        "user_email": email,   # BOOT_VERTRAG.md
        "user_image": user_doc.get("user_image") or "",
        "email": email,        # Original (session.py)
        "mitglied": mitglied,
        "is_admin": is_admin,
        "is_admin_mode": is_admin_mode,
        "roles": roles,
        "modules": accessible_modules,
        "permissions": perms,
        "csrf_token": _csrf_token(),
    }


def _csrf_token() -> str:
    """`frappe.sessions.get_csrf_token()` — im Compat nicht vorhanden.

    Ehrlich: die Compat-Schicht hat keine Session-/CSRF-Verwaltung, und ein
    erfundenes Token waere schlimmer als ein leeres. Der Aufrufer faellt auf
    den `X-Frappe-CSRF-Token`-Header aus `spa.py` zurueck, sobald die
    Auth-Karte das echte Token liefert.
    """
    try:
        from diakronos_app.frappe_compat.session import session as _s

        token = _s.get("csrf_token")
        return token or ""
    except Exception:  # noqa: BLE001 — kein Session-Kontext -> leer
        return ""


@whitelist(allow_guest=False)
def get_mitglied_permissions(mitglied_id):
    """Permission-Map fuer ein Mitglied — duenner Wrapper.

    Logik in `frappe_compat.permissions.mitglied_permissions` (P3).
    Begruendung wie bei `check_permission`: eine Umsetzung, ein Ort.
    """
    return _compat_mitglied_permissions(mitglied_id)


@whitelist(allow_guest=False)
def check_permission(doctype, docname, permission_type="read"):
    """Generische Permission-Check-API — duenner Wrapper.

    Die Entscheidungslogik lebt AUSSCHLIESSLICH in
    `frappe_compat.permissions.check_permission` (portiert in P3, Spezifikation
    im Docstring dort). Dieser Endpunkt macht sie nur unter dem
    Original-Pfad `diakronos.diakonos.api.session.check_permission` erreichbar.

    Bewusst KEINE zweite Umsetzung: zwei Fassungen derselben Berechtigungslogik
    waeren der gefaehrlichste Zustand dieses Projekts — eine Korrektur wuerde
    nur an einer Stelle wirken, und welche der beiden greift, haengt vom
    Aufrufweg ab.
    """
    return _compat_check_permission(doctype, docname, permission_type)


# ── Helpers ─────────────────────────────────────────────────────────────────

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
        # Admin hat generell Vollzugriff (kein separater Admin-Mode mehr noetig).
        perms.update({k: True for k in perms})
        return perms

    # Normale User.
    if mitglied:
        perms.update({
            "can_view_mitglieder": True,
            "can_edit_mitglieder": True,  # Eigenes Profil
            "can_view_gruppen": bool(mitglied.get("ancestor_path")),
            "can_view_bereiche": bool(mitglied.get("ancestor_path")),
            "can_view_dienstplan": True,
        })

    return perms


