import frappe
import json
import os


def get_context(context):
    context.no_cache = 1

    # ── 1. Auth-Check ──────────────────────────────────────────────────────────
    if frappe.session.user in ("Guest", None):
        frappe.local.flags.redirect_location = "/login?redirect-to=/diakonos"
        raise frappe.Redirect

    user = frappe.session.user
    user_doc = frappe.db.get_value(
        "User", user,
        ["full_name", "user_image", "email"],
        as_dict=True,
    ) or {}

    # ── 2. Mitglied-Link ───────────────────────────────────────────────────────
    mitglied = frappe.db.get_value(
        "Mitglied",
        {"email": user_doc.get("email") or user},
        ["name", "vorname", "nachname", "status"],
        as_dict=True,
    )

    # ── 3. Admin-Status ────────────────────────────────────────────────────────
    roles = frappe.get_roles(user)
    is_admin = "Mitgliederadministrator" in roles or "System Manager" in roles

    # ── 4. Sidebar-Module (aus Diakronos Einstellungen) ────────────────────────
    accessible_modules = []
    try:
        from diakronos.kronos.api.permissions import get_accessible_modules
        accessible_modules = get_accessible_modules()
    except Exception:
        pass

    # ── 5. Vite Manifest – finde diakonos Assets ───────────────────────────────
    manifest_path = frappe.get_app_path("diakronos", "public", "frontend", ".vite", "manifest.json")
    manifest = {}
    if os.path.exists(manifest_path):
        with open(manifest_path) as f:
            manifest = json.load(f)

    # Finde den diakonos Entry Point
    diakonos_entry = None
    for key, value in manifest.items():
        if value.get("isEntry") and "diakonos" in key:
            diakonos_entry = value
            break

    css_files = []
    js_file = None
    if diakonos_entry:
        js_file = diakonos_entry.get("file")
        # Vite 5+ cssCodeSplit=false → globales style.css im Manifest
        style_entry = manifest.get("style.css")
        if style_entry:
            css_files.append(style_entry.get("file"))
        # Fallback: css direkt am Entry Point
        if diakonos_entry.get("css"):
            css_files.extend(diakonos_entry["css"])

    context.title = "Diakonos"
    context.user_email = user_doc.get("email") or user
    context.user_fullname = user_doc.get("full_name") or user
    context.user_image = user_doc.get("user_image") or ""
    context.csrf_token = frappe.sessions.get_csrf_token()
    context.is_admin = is_admin
    context.mitglied = mitglied
    context.modules = accessible_modules
    context.js_file = js_file
    context.css_files = css_files
