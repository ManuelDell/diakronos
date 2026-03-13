# Diakronos

Eine **Frappe-App** für Gemeinde- und Kirchenverwaltung – modular aufgebaut rund um Kalender, Mitgliederpflege und Liederverwaltung.

---

## Module

| Modul | Status | Beschreibung |
|-------|--------|--------------|
| **Kronos** | ✅ Stabil | Webbasierter Kalender mit CalDAV-Server und Google-Import |
| **Diakonos** | 🔧 In Entwicklung | Mitgliederverwaltung für Gemeinden |
| **Psalmos** | 🔜 Geplant | Liedverwaltung und Gottesdienst-Planung |

---

## Changelog

### v16 – 2026-03-13 – Frappe v16 Migration & Desk-Struktur

**App-Struktur**
- Migration auf **Frappe v16**: vollständig kompatible Workspace- und Desktop-Icon-Struktur
- Vier Module im Frappe Desk integriert: **Kronos**, **Diakonos**, **Diakronos** (Einstellungen), Psalmos (versteckt – in Entwicklung)
- Jedes Modul hat ein eigenes Logo in `public/icons/desktop_icons/` – erscheint im Workspaces-Dropdown
- Workspace Sidebars als JSON-Fixtures (`workspace_sidebar/`) – vollständig automatisch bei `bench migrate` eingespielt
- Desktop Icons als JSON-Fixtures (`desktop_icon/`) – flache Struktur, kein Folder-Nesting

**Kronos Kalender – Avatar & Header**
- Benutzerbild und Vollname werden serverseitig übergeben (`calendar.py` → `body data-*`) – kein separater API-Aufruf
- Avatar zeigt Benutzerbild wenn vorhanden, sonst Initiale auf `var(--primary)` Hintergrund
- „Startseite"-Link aus Avatar-Dropdown entfernt (Hub-Seite wurde abgelöst)
- `can_access_desk`-Check reduziert auf einen einzigen API-Call (nur für „Zurück zum Desk"-Link)

**Demo-Daten**
- `create_demo_data()` und `delete_demo_data()` vollständig getestet
- Besucher-Duplikat-Bug behoben: `set_name=f"{vorname} {nachname}"` umgeht Frappe-Meta-Cache-Problem mit `autoname: "format:..."`
- 8 Kategorien, 4 Kalender, 10 Mitglieder, 5 Besucher, 76 Termine – vollständig reversibel

**Sicherheit / Permissions**
- `permissions.py`: `can_access_desk()` nutzt `frappe.get_roles()` statt direktem DB-Zugriff

---

### 2026-03-03 – Sicherheitshärtung + Hub-Navigation

**Zugriffssteuerung**
- Desk-Link im Avatar-Dropdown nur für `Administrator` und `Kalenderadministrator` sichtbar
- Serverseitige Prüfung auf allen Seiten

**Sicherheitshärtung (API)**
- `get_events()`: gibt nur Events aus zugriffsberechtigten Kalendern zurück (IDOR-Lücke geschlossen)
- `get_event_details()`, `delete_series_batch_fast()`, `update_series_batch_fast()`: Berechtigungsprüfung vor Ausführung
- Alle internen API-Endpunkte auf `@frappe.whitelist(allow_guest=False)` umgestellt
- `parse_iso_datetime_raw()`: Strict-Validierung mit `strptime()`

**Sicherheitshärtung (Frontend)**
- `html_utils.js` mit `escHtml()` und `safeCssColor()` – XSS- und CSS-Injection-Schutz in allen Modals

---

## Überblick

Diakronos bringt Gemeinde-Werkzeuge direkt in die Frappe-Oberfläche, ohne die Frappe-Standard-UI zu erzwingen. Jedes Modul ist eigenständig und kann unabhängig eingesetzt werden.

---

## Kronos – Funktionen

### Kalenderansicht
- Monats-, Wochen- und Tagesansicht
- Heute-Button, Vor/Zurück-Navigation, Kalenderwochen
- Klick auf Tageszahl → Tagesansicht, auf KW → Wochenansicht

### Termin-Management
- Erstellen per FAB-Button oder Klick auf leeren Tag
- Flatpickr (Deutsch, 24 h, 5-Min-Schritte), Ende automatisch +1 h
- Ansichts-, Bearbeitungs- und Lösch-Modal
- **Wiederkehrende Termine**: täglich, wöchentlich, monatlich, jährlich – nur diesen oder gesamte Serie bearbeiten

### Mehrere Kalender
- Sidebar-Checkliste zum Ein-/Ausblenden, farbliche Kodierung
- Mini-Kalender zur schnellen Navigation
- Nutzer sieht nur Kalender mit Zugriffsrecht

### CalDAV-Server
- Vollwertiger CalDAV-Endpunkt für Apple Kalender, Thunderbird, DAVx⁵
- URL: `https://<domain>/api/method/diakronos.kronos.api.caldav.serve_caldav`

### Google Calendar Import
- OAuth2-basiert, Duplikat-Schutz via `google_event_id`

---

## Rollen & Berechtigungen

| Rolle | Rechte |
|-------|--------|
| `Kalenderadministrator` | Alle Kalender lesen & schreiben, Kalender verwalten |
| `Mitglied` | Zugriff auf Kronos- und Diakonos-Workspace |
| Kalender-spezifisch | Lese- oder Schreibrecht pro Kalender konfigurierbar |

---

## Technische Architektur

### Backend
```
diakronos/
  kronos/api/         – calendar_get, event_crud, series_update, permissions, caldav, google_import
  diakonos/doctype/   – Mitglied, Besucher, Dienstbereich, Kinder
  diakronos/doctype/  – Diakronos Einstellungen, Modulfig, Rollen
  workspace_sidebar/  – JSON-Fixtures für alle Workspace Sidebars
  desktop_icon/       – JSON-Fixtures für Desk-Icons
  www/kronos/         – SPA-Template (Jinja + FullCalendar)
```

### Frontend
```
public/js/
  builder/   – kronos_calendar.js, mini_calendar, header, sidebar, init
  backend/   – data.js (State), events_api.js (CRUD via fetch)
  modal/     – core, create, edit, view, day_events, series_handler
  html_utils.js – escHtml(), safeCssColor()
```

---

## Installation

```bash
bench get-app https://github.com/<org>/diakronos
bench --site <site> install-app diakronos
bench --site <site> migrate
```

---

## Roadmap

| Version | Schwerpunkt |
|---------|-------------|
| **v16.1** | Diakonos: Mitgliederliste, Berichte, Dienstbereiche fertigstellen |
| **v16.2** | Psalmos: Liedverwaltung und Gottesdienst-Planung (Grundstruktur) |
| **v17** | CalDAV-Schreibzugriff (bidirektionale Sync), Benachrichtigungen, Mobile-Optimierung |
| **Langfristig** | Multi-Mandanten-Betrieb, öffentliche Kalenderseiten, Raumverwaltung |
