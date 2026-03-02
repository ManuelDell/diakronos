# Diakronos – Kronos Kalender

Eine **Frappe-App** für Gemeinde- und Kirchenverwaltung mit webbasiertem Kalender, CalDAV-Server und feingranularen rollenbasierten Berechtigungen.

---

## Überblick

Diakronos bringt einen vollwertigen Kalender direkt in die Frappe-Oberfläche – ohne die Frappe-Standard-UI zu verwenden. Die App stellt eine eigenständige Webseite (`/kronos`) bereit, die auf **FullCalendar** basiert und nahtlos mit dem Frappe-Backend kommuniziert.

Kernziele:
- Gemeindetermine sichtbar und pflegbar machen
- Verschiedene Nutzergruppen (z. B. Gottesdienst-Team, Vorstand, Öffentlichkeit) mit unterschiedlichen Rechten versehen
- CalDAV-Export für externe Kalender-Apps (Apple Kalender, Thunderbird, etc.)
- Optionaler Google-Calendar-Import

---

## Funktionen

### Kalenderansicht
- **Monatsansicht**, **Wochenansicht** und **Tagesansicht** per Knopfdruck umschaltbar
- **Heute-Button** springt sofort auf das aktuelle Datum
- **Vor/Zurück-Navigation** über Pfeile im Header
- **Kalenderwochen** werden in der Monatsansicht angezeigt
- Klick auf **Tageszahl** → Tagesansicht (Desktop)
- Klick auf **Kalenderwochenzahl** → Wochenansicht (Desktop)
- Nur so viele Wochen wie der Monat braucht (`fixedWeekCount: false`)

### Termin-Management

#### Termin erstellen
- **FAB-Button** (`+`) in der Seitenleiste öffnet den Create-Dialog ohne Vorbelegung
- **Klick auf einen leeren Tag** füllt Datum + aktuelle Uhrzeit (5-Min-gerundet) vor
- Felder: Titel, Beginn, Ende, Ganztägig, Beschreibung, Kalender, Kategorie
- Datums-/Uhrzeitauswahl per **Flatpickr** (Deutsch, 24 h, 5-Minuten-Schritte)
- Ende wird automatisch auf Beginn + 1 h gesetzt

#### Termin anzeigen
- Klick auf einen Termin öffnet eine schreibgeschützte Detailansicht
- Zeigt: Titel, Zeitraum, Kalender, Kategorie, Beschreibung
- Button zum Wechsel in den Bearbeitungsmodus (nur bei Schreibrecht)

#### Termin bearbeiten
- Vollständiges Edit-Modal mit denselben Feldern wie Create
- Flatpickr für Datum/Uhrzeit
- Inline-Löschbestätigung (kein separates Popup)

#### Wiederkehrende Termine (Serien)
- Serientypen: täglich, wöchentlich, monatlich, jährlich
- Optionales Enddatum der Serie
- Serienbearbeitung: nur diesen Termin oder gesamte Serie

### Mehrere Kalender
- Jeder Nutzer sieht nur die Kalender, auf die er Zugriff hat
- **Sidebar-Checkliste** zum Ein-/Ausblenden einzelner Kalender
- Farbliche Kodierung: Jeder Kalender hat eine eigene Farbe
- **Mini-Kalender** in der Sidebar zur schnellen Datumsnavigation

### Kategorien
- Termine können einer **Eventkategorie** zugeordnet werden
- Kategorien werden als Frappe-DocType `Eventkategorie` verwaltet

### CalDAV-Server
- Vollwertiger CalDAV-Endpunkt für externe Kalender-Apps
- URL-Schema: `https://<domain>/api/method/diakronos.kronos.api.caldav.serve_caldav`
- Authentifizierung über Frappe-Benutzername + Passwort
- Unterstützt: Apple Kalender, Thunderbird (Ligntning), DAVx⁵ (Android)
- Hilfe-Overlay in der Sidebar mit Verbindungsanleitung

### Google Calendar Import
- OAuth2-basierter Import aus Google Calendar
- Verhindert Duplikate via `google_event_id`
- Konfiguration über Frappe-DocType `Google Calendar Settings`

---

## Rollen & Berechtigungen

Diakronos verwendet ein eigenes, fachliches Berechtigungssystem über Frappe-Rollen:

| Rolle | Rechte |
|-------|--------|
| `Kalenderguru` | Alle Kalender lesen & schreiben, Kalender verwalten |
| `Administrator` | Vollzugriff (Frappe-System-Rolle) |
| Kalender-spezifisch | Lese- oder Schreibrecht pro Kalender konfigurierbar |

- Lesende vs. schreibende Kalender werden serverseitig getrennt geprüft
- Die UI blendet Schaltflächen aus, wenn kein Schreibrecht besteht
- API-Endpunkte prüfen fachliche Rechte vor jedem Schreibzugriff

---

## Technische Architektur

### Backend (Python / Frappe)
```
diakronos/
  kronos/
    api/
      calendar_get.py     – Termine für FullCalendar abrufen
      event_crud.py       – Erstellen, Aktualisieren, Löschen
      series_update.py    – Serien-Sammelupdate (SQL-optimiert)
      permissions.py      – Schreib-/Lesezugriff prüfen
      caldav.py           – CalDAV-Server-Implementierung
      google_import.py    – Google Calendar OAuth + Import
    kronos_core.py        – Shared-Logik
  www/
    kronos/
      calendar.html       – SPA-Template (Jinja)
      calendar.py         – Server-Context (CSRF, Rollen, User-Info)
```

### Frontend (JavaScript / SCSS)
```
public/js/
  builder/
    kronos_calendar.js        – FullCalendar-Singleton
    kronos_mini_calendar.js   – Mini-Kalender in der Sidebar
    header_build_elements.js  – Header-DOM-Builder
    sidebar_build_elements.js – Sidebar-DOM-Builder (inkl. CalDAV-Overlay)
    calendar_build_init.js    – Initialisierungs-Orchestrator
  backend/
    data.js                   – Zentraler State (viewMode, selectedCalendars)
    events_api.js             – CRUD via fetch() (kein frappe.call)
  modal/
    modal_core.js             – Modal-Basis
    modal_create.js           – Termin erstellen
    modal_edit.js             – Termin bearbeiten
    modal_view.js             – Termin anzeigen (schreibgeschützt)
    modal_day_events.js       – Tages-Übersicht (mehrere Termine)
    modal_series_handler.js   – Serien-Auswahl-Dialog
  element_extract_id.js       – Utility
  kronos.bundle.js            – Einstiegspunkt

public/css/
  kronos.bundle.scss          – SCSS-Bundle-Einstiegspunkt
  kronos_layout.scss          – App-Layout, Kalender-Grid, Mobile
  kronos_sidebar.scss         – Sidebar inkl. Mobile-Overlay
  kronos_header_buttons.scss  – Header-Buttons, Avatar, Mobile
  kronos_modal.scss           – Modal-Styles, Flatpickr-Integration
  diakronos_color_theme.scss  – CSS Custom Properties (Light/Dark-ready)
```

### Externe Bibliotheken
| Bibliothek | Version | Einbindung |
|-----------|---------|------------|
| FullCalendar | 6.x | Lokal (Assets) |
| Moment.js | 2.x | Lokal (Assets) |
| Flatpickr | Latest | CDN (jsDelivr) |

---

## Installation

### Voraussetzungen
- Frappe Framework 14+ / ERPNext-Umgebung
- Python 3.10+
- Node.js 18+ (für `bench build`)

### App installieren
```bash
# Als erpnext-User
cd ~/frappe-bench
bench get-app diakronos <repository-url>
bench --site <site-name> install-app diakronos
bench --site <site-name> migrate
bench build --app diakronos
```

### Frappe-Rollen einrichten
1. System-Einstellungen → Rollen → `Kalenderguru` anlegen
2. Nutzer → Rolle `Kalenderguru` zuweisen
3. Diakronos → Kalender anlegen und Zugriffsrechte vergeben

### CalDAV aktivieren
Kein separater Setup nötig – der CalDAV-Endpunkt ist automatisch aktiv.
Verbindungsdetails für Nutzer: In der App → Sidebar → CalDAV-Symbol.

---

## Responsive Design

| Gerät | Verhalten |
|-------|-----------|
| Desktop (> 768 px) | Sidebar immer sichtbar, alle Ansichten verfügbar, NavLinks aktiv |
| Tablet / Mobile (≤ 768 px) | Hamburger-Menü, Sidebar als Vollbild-Overlay, Swipe-Navigation |
| Sehr klein (≤ 430 px) | Kompaktere Event-Chips, kleinere Tagesnummern |

### Mobile-Header
- Links: Hamburger + Monatsname
- Rechts: Heute-Button + Profil-Avatar
- Swipe links/rechts: nächster/vorheriger Zeitraum

---

## Sicherheit

- **CSRF-Schutz**: Jeder API-Aufruf sendet `X-Frappe-CSRF-Token`
- **Session-Authentifizierung**: Frappe-Session via Cookie
- **Fachliche Berechtigungsprüfung**: Jeder Schreibzugriff prüft Kalender-Rechte serverseitig
- **XSS-Schutz**: Terminbeschreibungen werden nicht als `innerHTML` gerendert
- **CalDAV-Auth**: `frappe.check_password()` (kein Eigenbau)
- **OAuth State-Validierung**: Google-Import prüft State-Parameter

---

## Frappe DocTypes

| DocType | Zweck |
|---------|-------|
| `Kronos Kalender` | Kalender-Definition mit Farbe und Zugriffsrechten |
| `Kronos Element` | Einzelner Termin |
| `Kronos Serie` | Seriendefinition (Typ, Enddatum) |
| `Eventkategorie` | Terminkalegorie (Name + ggf. Farbe) |
| `Google Calendar Settings` | OAuth-Credentials für Google-Import |

---

## Entwicklung

### Lokaler Build
```bash
bench build --app diakronos --watch
```

### Branch-Strategie
- `main` – Produktionsstand
- `develop-frappe-page` – Aktiver Entwicklungszweig

### Konventionen
- Kein `frappe.call()` / `frappe.show_alert()` im `www`-Bereich – nur `fetch()`
- Singleton `kronosCalendar` immer aus `builder/kronos_calendar.js` importieren
- Zentraler State in `backend/data.js` (nie doppelt deklarieren)
- SCSS-Variablen aus `diakronos_color_theme.scss` nutzen (keine Hartwert-Farben außer Ausnahmen)

---

## Lizenz

MIT – siehe `LICENSE`
