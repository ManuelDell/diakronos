# diakronos/hooks.py
app_name = "diakronos"
app_title = "Diakronos"
app_publisher = "Dells Dienste"
app_description = "Eine Gemeindeverwaltungsapp mit um Gemeindemitgliedern im Dienst unter die Arme zu greifen."
app_email = "info@diedells.de"
app_license = "MIT"
app_logo_url = "/assets/diakronos/images/diakronos-logo.svg"
# UI - Apps-Screen und Module
add_to_apps_screen = [
    {
        "name": "diakronos",
        "logo": "/assets/diakronos/images/diakronos-logo.svg",
        "title": "Diakronos",
        "route": "/app/übersichtsseite",
    }
]
modules = [
    {
        "module_name": "Kronos",
        "color": "#667eea",
        "icon": "fa fa-calendar-check-o",
        "type": "module"
    }
]
fixtures = [
    "Workspace",
    "Module Def",
    {"dt": "Role", "filters": [["name", "in", ["Mitglied", "Kalenderguru", "Psalmos-Nutzer"]]]},
    "Custom Field",
    "Client Script",
    "Dashboard",
]
# Doc-Events (Cache-Invalidierung bleibt erhalten – sehr gut!)
doc_events = {
    "Element": {
        "before_insert": "diakronos.kronos.doctype.element.element.before_insert",
        "after_save": "diakronos.kronos.doctype.element.element.after_save",
    }
}
# Whitelisted Methods (alles sehr sinnvoll – bleibt fast identisch)
whitelisted_methods = {
    'diakronos.kronos.api.calendar_get.get_calendar_events',
    # Cache-Management
    'diakronos.kronos.doctype.element.element.get_calendar_and_category_options',
    # Google Kalender Import
    'diakronos.kronos.api.google_import.get_credentials_status',
    'diakronos.kronos.api.google_import.save_credentials',
    'diakronos.kronos.api.google_import.get_oauth_url',
    'diakronos.kronos.api.google_import.exchange_code',
    'diakronos.kronos.api.google_import.get_google_calendars',
    'diakronos.kronos.api.google_import.start_import',
    'diakronos.kronos.api.google_import.upload_ical',
    # Diakronos Einstellungen
    'diakronos.diakronos.doctype.diakronos_einstellungen.diakronos_einstellungen.get_module_defaults',
    # Diakronos Startseite – Modul-Zugriff & Nutzerpräferenz
    'diakronos.kronos.api.permissions.get_accessible_modules',
    'diakronos.kronos.api.permissions.set_home_preference',
    'diakronos.kronos.api.permissions.clear_home_preference',
}
app_include_css = [
    "/assets/diakronos/css/kronos.bundle.css"  # ← genau dieser Pfad (Frappe handhabt Hash)
]

# Optional: Wenn du JS schon im Bundle hast, kannst du es auch hier einbinden
app_include_js = [
    "/assets/diakronos/js/kronos.bundle.js"
]
# ───────────────────────────────────────────────────────────────
# Optionale, aber empfohlene Ergänzungen
# ───────────────────────────────────────────────────────────────
app_include_icons = [
    "/diakronos/images/diakronos-logo.svg",
    "/diakronos/images/kalender-icon.png",
    "/diakronos/images/calendar-week-icon.svg"
]
# ── Startseite nach Login (nach Rolle) ───────────────────────────────────────
# Nutzer mit dieser Rolle landen direkt beim Kalender statt beim Desk.
# Mehrere Rollen möglich – erste Übereinstimmung gewinnt.
role_home_page = {
    # /diakronos übernimmt die smarte Weiterleitung:
    # 1 Modul → direkt dorthin, mehrere → Kachelseite, Präferenz → bevorzugtes Modul
    "Mitglied": "/diakronos",
}

after_install = "diakronos.setup.install.symlink_create_install"

# ── CalDAV-Server (minimal, read-only, eingebettet in Frappe) ────────────────
# Fängt /dav/* und /.well-known/caldav ab, bevor Frappe routet.
# Clients: Apple Calendar, Thunderbird, DAVx⁵ (Android)
# Zugriff:  Frappe-Zugangsdaten (E-Mail + Passwort) als Basic Auth
# URL:      https://<deine-domain>/dav/<deine-email>/
before_request = ["diakronos.caldav.server.intercept"]