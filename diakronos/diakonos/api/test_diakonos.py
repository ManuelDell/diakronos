import frappe

@frappe.whitelist(allow_guest=True)
def bootstrap():
    """Temporärer Test-Endpunkt für Diakonos Bootstrap-Daten."""
    user = frappe.session.user
    
    user_doc = frappe.db.get_value(
        "User", user,
        ["full_name", "user_image", "email"],
        as_dict=True,
    ) or {}

    mitglied = frappe.db.get_value(
        "Mitglied",
        {"email": user_doc.get("email") or user},
        ["name", "vorname", "nachname", "status"],
        as_dict=True,
    )

    roles = frappe.get_roles(user)
    is_admin = "Mitgliederadministrator" in roles or "System Manager" in roles

    accessible_modules = []
    try:
        from diakronos.kronos.api.permissions import get_accessible_modules
        accessible_modules = get_accessible_modules()
    except Exception:
        pass

    return {
        "user": user,
        "user_fullname": user_doc.get("full_name") or user,
        "is_admin": is_admin,
        "mitglied": mitglied,
        "modules": accessible_modules,
        "csrf_token": frappe.sessions.get_csrf_token(),
    }

@frappe.whitelist(allow_guest=True)
def health_check():
    """Gibt Status aller API-Endpunkte zurück."""
    result = {"status": "ok", "endpoints": {}}
    # Teste jeden Endpunkt mit einem einfachen Aufruf
    for module, method in [
        ("session", "get_current_user_context"),
        ("zugriff", "verify_admin_session"),
        ("mitglieder", "get_mitglieder_liste"),
        ("gruppen", "get_gruppen_hierarchie"),
        ("dienstplan", "get_dienstplan"),
        ("kalender", "get_events"),
    ]:
        try:
            mod = frappe.get_module(f"diakronos.diakonos.api.{module}")
            # Nur prüfen, ob die Funktion existiert
            result["endpoints"][module] = hasattr(mod, method)
        except Exception as e:
            result["endpoints"][module] = str(e)
    return result

@frappe.whitelist(allow_guest=True)
def test_page(page_name):
    """Überprüft, ob eine Frontend-Page existiert."""
    pages = ["Home", "Mitglieder", "MitgliedDetail", "Gruppen", "GruppeDetail",
             "Adressbuch", "Kalender", "Dienstplan", "Anmeldungen",
             "Organigramm", "Statistik", "Dsgvo", "Profile"]
    return {"exists": page_name in pages, "available_pages": pages}
