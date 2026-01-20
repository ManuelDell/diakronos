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
    "Role",
    "Custom Field",
    "Client Script",
    "Dashboard",
]
# Doc-Events (Cache-Invalidierung bleibt erhalten – sehr gut!)
doc_events = {
    "Element": {
        "before_insert": "diakronos.kronos.doctype.element.element.before_insert",
        "after_save": "diakronos.kronos.doctype.element.element.after_save",
        "after_insert": "diakronos.kronos.api.cache_invalidator.invalidate_events_cache",
        "after_update": "diakronos.kronos.api.cache_invalidator.invalidate_events_cache",
        "after_delete": "diakronos.kronos.api.cache_invalidator.invalidate_events_cache",
        "on_trash": "diakronos.kronos.api.cache_invalidator.invalidate_events_cache",
    }
}
# Whitelisted Methods (alles sehr sinnvoll – bleibt fast identisch)
whitelisted_methods = {
    # kronos_core
    'diakronos.kronos.kronos_core.get_accessible_calendars',
    'diakronos.kronos.kronos_core.get_calendar_details',
    'diakronos.kronos.kronos_core.get_calendar_events',
    'diakronos.kronos.kronos_core.get_event_details',
    'diakronos.kronos.kronos_core.check_user_permission',
    # Cache-Management
    'diakronos.kronos.api.cache_invalidator.invalidate_events_cache',
    'diakronos.kronos.api.calendar_get.clear_events_cache_endpoint',
    'diakronos.kronos.doctype.element.element.get_calendar_and_category_options',
}
# ───────────────────────────────────────────────────────────────
# Assets laden – FullCalendar v6 lokal aus deiner App
# ───────────────────────────────────────────────────────────────
app_include_js = [
    "/assets/diakronos/js/fullcalendar_bundle_include/fullcalendar.global.min.js",
    "/assets/diakronos/js/element_extract_id.js",
    "/assets/diakronos/js/kronos_events.js",
    # Entfernt: "/assets/diakronos/js/kronos_calendar.js", # Lädt nun on-demand in kronos_calendar_page.js
    "/assets/diakronos/js/kronos_modal.js",
    "/assets/diakronos/js/modal/modal_helpers.js",
    "/assets/diakronos/js/modal/modal_base.js",
    "/assets/diakronos/js/modal/modal_event_click.js",
    "/assets/diakronos/js/modal/modal_smart_edit.js",
    "/assets/diakronos/js/modal/modal_series_handler.js",
    "/assets/diakronos/js/modal/modal_create_dialog.js"
]

app_include_css = [
    # FullCalendar v6 CSS lokal
    "/assets/diakronos/js/fullcalendar_bundle_include/fullcalendar.global.min.css",
    # Deine Custom-Styles
    "/assets/diakronos/css/kronos_calendar_custom.css",
    "/assets/diakronos/css/kronos_modal.css"
]

# ───────────────────────────────────────────────────────────────
# Optionale, aber empfohlene Ergänzungen
# ───────────────────────────────────────────────────────────────
app_include_icons = [
    "/assets/diakronos/images/diakronos-logo.svg",
    "/assets/diakronos/images/kalender-icon.png",
    "/assets/diakronos/images/calendar-week-icon.svg"
]
# Standardmäßig deaktiviert – nur wenn du es wirklich brauchst
# app_include_fonts = []