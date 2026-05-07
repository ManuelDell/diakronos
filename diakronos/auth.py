import frappe

DESK_ROLES = {"System Manager", "Mitgliederadministrator"}


def get_home_page(user):
    """
    Frappe-Hook: get_website_user_home_page
    Bestimmt die Startseite nach dem Login.
    - Admins (System Manager / Mitgliederadministrator) → /app (Frappe Desk)
    - Alle anderen → /diakonos (Vue SPA)
    """
    roles = set(frappe.get_roles(user))
    if roles & DESK_ROLES:
        return "/app"
    return "/diakonos"
