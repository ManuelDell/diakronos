# Diakronos

**Diakronos** ist eine [Frappe](https://frappeframework.com)-App für Gemeinden und kirchliche Einrichtungen – mit Kalender, Mitgliederpflege und Liederverwaltung als eigenständige, modular einsetzbare Werkzeuge.

---

## Module

| Modul | Status | Beschreibung |
|-------|--------|--------------|
| **Kronos** | ✅ Stabil | Webbasierter Kalender mit CalDAV-Unterstützung und Google Calendar Import |
| **Diakonos** | 🔧 In Entwicklung | Mitgliederverwaltung für Gemeinden |
| **Psalmos** | 🔜 Geplant | Liedverwaltung und Gottesdienst-Planung |

---

## Kronos – Was kann er?

Kronos ist ein vollständiger Kalender, der direkt im Browser läuft – ohne Installation, ohne App-Store. Er fühlt sich an wie Google Calendar, ist aber Teil eurer eigenen Frappe-Instanz und speichert alle Daten bei euch.

### Kalenderansichten
- **Monats-, Wochen- und Tagesansicht** – per Dropdown wechselbar, auf Mobilgeräten per Wischen
- **Heute-Button** bringt sofort zum aktuellen Tag zurück
- **Kalenderwochen** werden automatisch angezeigt
- **Mini-Kalender** in der Seitenleiste zur schnellen Navigation

### Termine verwalten
- Neuen Termin erstellen: per FAB-Button oder einfach auf einen freien Tag klicken
- **Wiederkehrende Termine** (täglich, wöchentlich, monatlich, jährlich) – einzeln oder als ganze Serie bearbeiten
- Drag & Drop zum Verschieben, Ziehen am Ende zum Verlängern
- Farbige Kennzeichnung pro Kalender

### Mehrere Kalender
- Jeder Nutzer sieht nur die Kalender, auf die er Zugriff hat
- Kalender lassen sich in der Seitenleiste ein- und ausblenden
- Jeder Kalender hat eine eigene Farbe

### Synchronisation
- **CalDAV-Server** eingebaut: funktioniert mit Apple Kalender, Thunderbird, DAVx⁵ und jedem CalDAV-Client
  - URL: `https://<domain>/api/method/diakronos.kronos.api.caldav.serve_caldav`
- **Google Calendar Import** per OAuth2 (inkl. Duplikatschutz)

### Ansichts- und Bearbeitungsmodus
- Im **Ansichtsmodus** ist nichts versehentlich veränderbar – ideal für Bildschirme im Foyer oder Gemeinderaum
- Im **Bearbeitungsmodus** sind Drag & Drop, Klick-Erstellen und alle Bearbeitungsfunktionen aktiv
- Umschaltbar direkt im Header per Toggle

---

## Rollen & Berechtigungen

| Rolle | Rechte |
|-------|--------|
| `Kalenderadministrator` | Alle Kalender lesen & schreiben, Kalender verwalten |
| `Mitglied` | Zugriff auf Kronos- und Diakonos-Workspace |
| Kalender-spezifisch | Lese- oder Schreibrecht pro Kalender frei konfigurierbar |

---

## Installation

```bash
bench get-app https://github.com/<org>/diakronos
bench --site <site> install-app diakronos
bench --site <site> migrate
```

---

## Technische Architektur

### Backend
```
diakronos/
  kronos/api/         – calendar_get, event_crud, series_update, permissions, caldav, google_import
  diakonos/doctype/   – Mitglied, Besucher, Dienstbereich, Kinder
  diakronos/doctype/  – Diakronos Einstellungen, Modulkonfig, Rollen
  workspace_sidebar/  – JSON-Fixtures für alle Workspace Sidebars
  desktop_icon/       – JSON-Fixtures für Desk-Icons
  www/kronos/         – SPA-Template (Jinja + EventCalendar)
```

### Frontend
```
public/js/
  builder/   – kronos_calendar.js, mini_calendar, header, sidebar, init
  backend/   – data.js (State), events_api.js (CRUD via fetch)
  modal/     – core, create, edit, view, day_events, series_handler
  lib/       – eventcalendar/ (vkurko/calendar), moment/
  html_utils.js – escHtml(), safeCssColor()
```

### Abhängigkeiten
- **[EventCalendar](https://github.com/vkurko/calendar)** (vkurko/calendar, MIT) – Kalender-Rendering
- **[Moment.js](https://momentjs.com)** – Datums-Formatierung im Mini-Kalender
- **[Flatpickr](https://flatpickr.js.org)** – Datums- und Zeitauswahl in Modals

---

## Changelog

### v16 – 2026-03-16 – Kalender-Engine, Mobile & Bugfixes

**Kalender-Engine: FullCalendar → EventCalendar**
- Vollständige Migration von FullCalendar v6 auf **EventCalendar** ([vkurko/calendar](https://github.com/vkurko/calendar), MIT-Lizenz)
- Kalender-Rendering über `window.EventCalendar.create()` statt FullCalendar-Bundle
- Event-Quellen umgestellt auf `eventSources: [{events: fn}]`-Format
- Navigation über `setOption('view', ...)` / `setOption('date', ...)` statt alter FullCalendar-API
- `datesSet`-Callback wird als DOM Custom Event `ec:datesSet` gebroadcastet – Mini-Kalender und Header reagieren darauf
- FullCalendar-Bundle vollständig entfernt (`public/js/lib/fullcalendar/` und `@fullcalendar`-Abhängigkeit)

**Layout & Darstellung**
- Kalender füllt jetzt die gesamte verfügbare Höhe korrekt aus
- Monatsansicht: Zeilen füllen die volle Höhe gleichmäßig
- Schriftart des Kalenders einheitlich mit der restlichen App

**Mobile – Echte Geräte statt Viewport-Breite**
- Mobile-Layout greift jetzt nur noch auf echten Touch-Geräten (`pointer: coarse`), nicht mehr beim Verkleinern des Desktop-Browsers
- Avatar (Profilbild) wird auf Desktop-Geräten (Maus/Trackpad) ausgeblendet
- Navigationspfeile bleiben auf Desktop immer sichtbar

**Bugfixes**
- Klick auf einen leeren Tag im Bearbeitungsmodus öffnet jetzt korrekt das „Neuer Termin"-Modal

---

### v16 – 2026-03-13 – Frappe v16 Migration & Desk-Struktur

**App-Struktur**
- Migration auf **Frappe v16**: vollständig kompatible Workspace- und Desktop-Icon-Struktur
- Vier Module im Frappe Desk integriert: **Kronos**, **Diakonos**, **Diakronos** (Einstellungen), Psalmos (versteckt – in Entwicklung)
- Jedes Modul hat ein eigenes Logo in `public/icons/desktop_icons/`
- Workspace Sidebars und Desktop Icons als JSON-Fixtures – werden automatisch bei `bench migrate` eingespielt

**Kronos Kalender – Avatar & Header**
- Benutzerbild und Vollname werden serverseitig übergeben (`calendar.py` → `body data-*`) – kein separater API-Aufruf
- Avatar zeigt Benutzerbild wenn vorhanden, sonst Initiale auf Primärfarbe
- `can_access_desk`-Check auf einen einzigen API-Call reduziert

**Demo-Daten**
- `create_demo_data()` und `delete_demo_data()` vollständig getestet und stabil
- 8 Kategorien, 4 Kalender, 10 Mitglieder, 5 Besucher, 76 Termine – vollständig reversibel

**Sicherheit**
- `permissions.py`: `can_access_desk()` nutzt `frappe.get_roles()` statt direktem DB-Zugriff

---

### 2026-03-03 – Sicherheitshärtung & Zugriffssteuerung

**Zugriffssteuerung**
- Desk-Link im Avatar-Dropdown nur für `Administrator` und `Kalenderadministrator` sichtbar
- Serverseitige Prüfung auf allen Seiten

**API-Sicherheit**
- `get_events()`: gibt nur Events aus zugriffsberechtigten Kalendern zurück (IDOR-Lücke geschlossen)
- `get_event_details()`, `delete_series_batch_fast()`, `update_series_batch_fast()`: Berechtigungsprüfung vor Ausführung
- Alle internen API-Endpunkte auf `@frappe.whitelist(allow_guest=False)` umgestellt
- `parse_iso_datetime_raw()`: Strict-Validierung mit `strptime()`

**Frontend-Sicherheit**
- `html_utils.js` mit `escHtml()` und `safeCssColor()` – XSS- und CSS-Injection-Schutz in allen Modals

---

## Roadmap

| Version | Schwerpunkt |
|---------|-------------|
| **v16.1** | Diakonos: Mitgliederliste, Berichte, Dienstbereiche fertigstellen |
| **v16.2** | Psalmos: Liedverwaltung und Gottesdienst-Planung (Grundstruktur) |
| **v17** | CalDAV-Schreibzugriff (bidirektionale Sync), Benachrichtigungen |
| **Langfristig** | Multi-Mandanten-Betrieb, öffentliche Kalenderseiten, Raumverwaltung |
