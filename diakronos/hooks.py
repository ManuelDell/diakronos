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
    "Page",
    {"dt": "Role", "filters": [["name", "in", ["Mitglied", "Kalenderadministrator", "Psalmos-Nutzer"]]]},
    "Custom Field",
    "Client Script",
    "Dashboard",
]
# Doc-Events (Cache-Invalidierung bleibt erhalten – sehr gut!)
doc_events = {
    "Element": {
        "before_insert": "diakronos.kronos.doctype.element.element.before_insert",
        "after_save": "diakronos.kronos.doctype.element.element.after_save",
    },
    "Audit Log": {
        "on_update": "diakronos.diakonos.doctype.audit_log.audit_log.prevent_modification",
        "on_trash": "diakronos.diakonos.doctype.audit_log.audit_log.prevent_modification",
    },
}

# Scheduler Events
scheduler_events = {
    "daily": [
        "diakronos.diakonos.api.audit_policy.anonymize.anonymize_expired_audit_logs",
        "diakronos.diakonos.api.cleanup.delete_alte_anmeldeanfragen",
    ],
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
    'diakronos.diakronos.doctype.diakronos_einstellungen.diakronos_einstellungen.run_demo_data_action',
    # Diakonos Organigramm
    'diakronos.diakonos.api.orgchart_api.get_orgchart_data',
    # Diakronos Startseite – Modul-Zugriff & Nutzerpräferenz
    'diakronos.kronos.api.permissions.get_accessible_modules',
    'diakronos.kronos.api.permissions.set_home_preference',
    'diakronos.kronos.api.permissions.clear_home_preference',
    # Diakonos Gruppen
    'diakronos.diakonos.api.gruppen.get_gruppen_hierarchie',
    # Diakonos Mitglied-Verwaltung
    'diakronos.diakonos.api.mitglieder.create_mitglied',
    'diakronos.diakonos.api.mitglieder.get_mitglied',
    'diakronos.diakonos.api.mitglieder.update_mitglied',
    'diakronos.diakonos.api.mitglieder.get_mitglieder_list',
    # Diakonos Admin-Hub
    'diakronos.diakonos.api.admin_hub.get_statistik',
    'diakronos.diakonos.api.admin_hub.get_anmeldungen_hub',
    'diakronos.diakonos.api.admin_hub.get_dsgvo_uebersicht',
    'diakronos.diakonos.api.admin_hub.genehmige_anmeldung',
    'diakronos.diakonos.api.admin_hub.lehne_anmeldung_ab',
    'diakronos.diakonos.api.admin_hub.get_anmeldeformulare',
    'diakronos.diakonos.api.admin_hub.create_anmeldeformular',
    'diakronos.diakonos.api.admin_hub.update_anmeldeformular_felder',
    # Diakonos Registrierungslinks
    'diakronos.diakonos.api.registrierungslink_api.create_link',
    'diakronos.diakonos.api.registrierungslink_api.update_link',
    'diakronos.diakonos.api.registrierungslink_api.delete_link',
    'diakronos.diakonos.api.registrierungslink_api.toggle_link',
    # Ressourcen
    'diakronos.diakonos.api.ressourcen.get_ressourcen_liste',
    'diakronos.diakonos.api.ressourcen.get_ressource_buchungen',
    'diakronos.diakonos.api.ressourcen.get_meine_buchungen',
    'diakronos.diakonos.api.ressourcen.check_verfuegbarkeit',
    'diakronos.diakonos.api.ressourcen.create_buchung',
    'diakronos.diakonos.api.ressourcen.update_buchung',
    'diakronos.diakonos.api.ressourcen.delete_buchung',
    # Kalender (SPA-Ansicht)
    'diakronos.diakonos.api.kalender.get_events',
    # Veranstaltungsanmeldung (One-Click für Mitglieder)
    'diakronos.diakonos.api.veranstaltungsanmeldung.register_mitglied',
    'diakronos.diakonos.api.veranstaltungsanmeldung.check_anmeldestatus',
    # Beiträge
    'diakronos.diakonos.api.beitraege.get_beitraege_liste',
    'diakronos.diakonos.api.beitraege.get_beitrag_detail',
    'diakronos.diakonos.api.beitraege.create_beitrag',
    'diakronos.diakonos.api.beitraege.update_beitrag',
    'diakronos.diakonos.api.beitraege.delete_beitrag',
    'diakronos.diakonos.api.beitraege.create_kommentar',
    # Wiki
    'diakronos.diakonos.api.wiki.get_wiki_artikel_liste',
    'diakronos.diakonos.api.wiki.get_wiki_artikel_detail',
    'diakronos.diakonos.api.wiki.create_wiki_artikel',
    'diakronos.diakonos.api.wiki.update_wiki_artikel',
    'diakronos.diakonos.api.wiki.delete_wiki_artikel',
    'diakronos.diakonos.api.wiki.get_wiki_kategorien',
    'diakronos.diakonos.api.wiki.get_wiki_tags',
}
# Kronos/Psalmos bundles werden NUR auf den jeweiligen www-Pages geladen
# (calendar.html / psalmos.html) – nicht auf dem Desk.
# app_include_js / app_include_css bewusst leer gelassen.

app_include_icons = [
    "/assets/diakronos/images/diakronos-logo.svg",
    "/assets/diakronos/images/icons/kalender-icon.png",
    "/assets/diakronos/images/icons/calendar-week-icon.svg"
]

after_install = "diakronos.setup.install.symlink_create_install"

# ── Login-Redirect: Admins → /app, alle anderen → /diakonos ─────────────────
get_website_user_home_page = "diakronos.auth.get_home_page"

# ── SPA Routing: catch-all für Diakonos ─────────────────────────────────────────────────────────────
# Alle /diakonos/* URLs werden auf index.py umgeleitet (Vue Router übernimmt Hash-Routing).
website_route_rules = [
    {"from_route": "/diakonos/<path:app_path>", "to_route": "/diakonos/index"},
]

# ── Diakonos Vue-Bundles (gebaut via `vite build` im App-Root) ───────────────
# Build-Befehl: cd /home/erpnext/frappe-bench/apps/diakronos && npm install && npm run build
# Output:       diakronos/public/frontend/{admin,registrierung,gast,organigramm}.js
# Desk-Pages laden admin.js via dynamischem import() in den jeweiligen page.js-Dateien.

# ── CalDAV-Server (minimal, read-only, eingebettet in Frappe) ────────────────
# Fängt /dav/* und /.well-known/caldav ab, bevor Frappe routet.
# Clients: Apple Calendar, Thunderbird, DAVx⁵ (Android)
# Zugriff:  Frappe-Zugangsdaten (E-Mail + Passwort) als Basic Auth
# URL:      https://<deine-domain>/dav/<deine-email>/
before_request = ["diakronos.caldav.server.intercept"]

# ── Raven (Chat – optional, noch nicht aktiv) ────────────────────────────────
# Raven ist eine native Frappe-Chat-App: https://github.com/The-Commit-Company/Raven
# Installation wenn gewünscht:
#   bench get-app raven
#   bench --site <site> install-app raven
#
# Geplante Integration (Phase spät):
# - Jede Gruppe automatisch einen Raven-Channel erstellen
# - Event: doc_events["Gruppe"]["after_insert"] → raven_integration.create_channel(doc)
# Solange Raven nicht installiert ist, bleibt dieser Block auskommentiert.