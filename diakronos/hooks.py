app_name = "diakronos"
app_title = "Diakronos"
app_publisher = "Dells Dienste"
app_description = "Eine Gemeindeverwaltungsapp mit um Gemeindemitgliedern im Dienst unter die Arme zu greifen."
app_email = "info@diedells.de"
app_license = "mit"
app_logo_url = "/assets/diakronos/images/diakronos-logo.svg"

# hooks.py - einfach halten
add_to_apps_screen = [
    {
        "name": "diakronos",  # ← lowercase, wie app_name
        "logo": "/assets/diakronos/images/diakronos-logo.svg",
        "title": "Diakronos",  # ← title kann capitalized sein
        "route": "/app/kronos",
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
    "Role",
    "Custom Field",
    "Client Script",
    "Dashboard",
]

doc_events = {
    "Element": {
        "before_insert": "diakronos.kronos.doctype.element.element.before_insert",
        "after_save": "diakronos.kronos.doctype.element.element.after_save",
    }
}

whitelisted_methods = {
    # kronos_core
    'diakronos.kronos.kronos_core.get_accessible_calendars',
    'diakronos.kronos.kronos_core.get_calendar_details',
    'diakronos.kronos.kronos_core.get_calendar_events',
    'diakronos.kronos.kronos_core.get_event_details',
    'diakronos.kronos.kronos_core.check_user_permission',
}
