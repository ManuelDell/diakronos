app_name = "diakronos"
app_title = "Diakronos"
app_publisher = "Dells Dienste"
app_description = "Eine Gemeindeverwaltungsapp mit um Gemeindemitgliedern im Dienst unter die Arme zu greifen."
app_email = "info@diedells.de"
app_license = "mit"
app_logo_url = "/assets/diakronos/images/diakronos-logo.svg"


# UI
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
    "Role",
    "Custom Field",
    "Client Script",
    "Dashboard",
]


# ✅ CACHE INVALIDIERUNG - Das ist der Fix!
doc_events = {
    "Element": {
        "before_insert": "diakronos.kronos.doctype.element.element.before_insert",
        "after_save": "diakronos.kronos.doctype.element.element.after_save",
        # ✅ NEUE: Cache-Invalidierung bei Änderungen
        "after_insert": "diakronos.kronos.api.cache_invalidator.invalidate_events_cache",
        "after_update": "diakronos.kronos.api.cache_invalidator.invalidate_events_cache",
        "after_delete": "diakronos.kronos.api.cache_invalidator.invalidate_events_cache",
        "on_trash": "diakronos.kronos.api.cache_invalidator.invalidate_events_cache",
    }
}


whitelisted_methods = {
    # kronos_core
    'diakronos.kronos.kronos_core.get_accessible_calendars',
    'diakronos.kronos.kronos_core.get_calendar_details',
    'diakronos.kronos.kronos_core.get_calendar_events',
    'diakronos.kronos.kronos_core.get_event_details',
    'diakronos.kronos.kronos_core.check_user_permission',
    # ✅ NEUE: Cache-Management Whitelisting
    'diakronos.kronos.api.cache_invalidator.invalidate_events_cache',
    'diakronos.kronos.api.calendar_get.clear_events_cache_endpoint',
}
