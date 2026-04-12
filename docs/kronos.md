# Kronos – Technische Dokumentation

→ [Zurück zur Übersicht](../README.md)

---

## Architektur

```
kronos/
  api/
    calendar_get.py      # GET: Termine abrufen (mit view_mode-Filter)
    event_crud.py        # CRUD: Erstellen, Bearbeiten, Löschen
    permissions.py       # Auth: Rollenprüfung, accessible_calendars
    series.py            # Serientermine (erstellen + bearbeiten)
    ressource_api.py     # Räume/Ressourcen
    kanban_api.py        # Kanban-Moderationsseite
    google_import.py     # Google Calendar OAuth2-Import
  doctype/
    kalender/            # Kalender-DocType (Felder, Moderatoren, Rechte)
    kalender_ereignis/   # Termin-DocType (Status, Ressource, Serienfeld)
    kronos_einstellungen/# Systemeinstellungen (Standard-Ressource, Pflichtfeld)
  www/
    kronos/index.py      # Kalender-SPA (Einstiegspunkt)
    kronos/moderation/   # Moderationsseite

caldav/
  server.py              # CalDAV-Server (RFC 4791/4918, read-only, nur Festgelegt)
```

### Frontend

```
public/js/
  builder/
    kronos_calendar.js        # EventCalendar-Klasse (Singleton kronosCalendar)
    calendar_build_init.js    # Initialisierungs-Orchestrator (FAB, Pending-Button)
    header_build_elements.js  # Header (Ansichten, View/Edit-Modus, Mini-Kalender)
    sidebar_build_elements.js # Sidebar (Kalender-Liste, Farbauswahl)
  backend/
    data.js                   # API-Calls (Kalender, Kategorien, Ressourcen)
    events_api.js             # Event-CRUD (create, update, delete)
    pending_manager.js        # Verwaltung ausstehender Termine (In-Memory)
  modal/
    modal_create.js           # Termin erstellen
    modal_edit.js             # Termin bearbeiten
    modal_view.js             # Termin ansehen (Lesemodus)
    modal_day_events.js       # Tagesansicht-Modal (Lesemodus, Mobile)
    modal_conflict.js         # Konflikt-Auflösung
    modal_series_handler.js   # Serien-Dialog (einzeln vs. alle)
    modal_session_save.js     # Abschließen-Modal + Admin-Massenfreigabe
  shared/
    header.js                 # Shared Header-Logik
    state.js                  # Globaler State (View-Modus, Kalenderauswahl)
  kanban/
    kanban.bundle.js          # Moderations-Kanban-Board (SortableJS)
  lib/
    event-calendar/           # vkurko/calendar (MIT) – Kalender-Rendering
    moment.js                 # Datumsformatierung
    flatpickr/                # Datums-/Zeitauswahl in Modals
```

---

## Datenbankmodell

### `KalenderEreignis` (Termin)

| Feld | Typ | Beschreibung |
|------|-----|-------------|
| `title` | Data | Titel des Termins |
| `element_start` | Datetime | Startzeit |
| `element_end` | Datetime | Endzeit |
| `all_day` | Check | Ganztages-Flag |
| `kalender` | Link → Kalender | Zugehöriger Kalender |
| `status` | Select | `Vorschlag` / `Festgelegt` / `Konflikt` |
| `ressource` | Link → Ressource | Optionale Raum-Zuweisung |
| `series_id` | Data | Gruppen-ID bei Serienterminen (gleiche ID = gleiche Serie) |
| `beschreibung` | Text Editor | Beschreibung (HTML) |
| `kategorie` | Link → Kategorie | Optionale Kategorie |

### `Kalender`

| Feld | Beschreibung |
|------|-------------|
| `leserechte` | Child-Tabelle: Nutzer mit Lesezugang |
| `schreibrechte` | Child-Tabelle: Nutzer mit Schreibzugang |
| `kalendermoderatoren` | Child-Tabelle: Nutzer, die Vorschläge bestätigen dürfen |
| `selbstverwaltet` | Wenn aktiv: Termine direkt als Festgelegt gespeichert |
| `farbe` | Hex-Farbe für die Kalenderdarstellung |

---

## Rollen & Berechtigungslogik

### Rollen
- `Kalenderadministrator` – Sieht alle Kalender und alle Statuses; Desk-Zugang; Massenfreigabe
- `Mitglied` – Zugang nur zu explizit freigegebenen Kalendern

### `_is_kalenderadministrator(user)`
Gibt `True` zurück wenn der Nutzer `Administrator` oder Mitglied der Rolle `Kalenderadministrator` ist. Diese Funktion übersteuert alle per-Kalender-Prüfungen in `get_accessible_calendars()`.

### `get_accessible_calendars(user)`
Iteriert über alle Kalender:
- Ist der Nutzer globaler Admin → Kalender direkt mit `write: True, is_moderator: True` anfügen, Schleife überspringen
- Sonst: Rechteprüfung über `leserechte`, `schreibrechte`, `kalendermoderatoren`

---

## Status-Workflow

```
Termin erstellen
       │
       ├── selbstverwaltet=True  → Status: Festgelegt
       └── selbstverwaltet=False → Status: Vorschlag
                                        │
                              Moderator bestätigt → Status: Festgelegt
                              Doppelbuchung erkannt → Status: Konflikt
```

**View-Modus (Lesemodus):** Nur `Festgelegt`-Termine sichtbar (für alle Nutzer, auch Moderatoren)
**Edit-Modus (Bearbeitungsmodus):** Moderatoren sehen alle drei Status; Nicht-Moderatoren nur `Festgelegt`

Der `view_mode`-Parameter in `get_calendar_events()` steuert das serverseitig:
```python
@frappe.whitelist(allow_guest=False)
def get_calendar_events(start_date, end_date, calendar_filter, view_mode=True):
    view_mode = str(view_mode).lower() not in ('false', '0', 'no')
    if view_mode:
        # Alle Nutzer: nur Festgelegt
        filters["status"] = "Festgelegt"
    else:
        # Moderatoren sehen Vorschlag + Konflikt + Festgelegt
        # Nicht-Moderatoren weiterhin nur Festgelegt
```

---

## CalDAV

- Endpunkt: `https://<site>/caldav/<kalender-name>/`
- Authentifizierung: Frappe Basic Auth (Benutzername + API-Key oder Passwort)
- Liefert ausschließlich `status: Festgelegt`-Termine (Vorschläge und Konflikte werden nie synchronisiert)
- Read-only: CalDAV-Clients können keine Termine anlegen oder bearbeiten
- Standard: RFC 4791 (CalDAV) + RFC 4918 (WebDAV)

---

## Ressourcen & Timeline-Ansicht

Ressourcen (Räume) sind ein eigener DocType mit:
- `title`, `kapazitaet`, `bild`

In der Timeline-Ansicht (EventCalendar `resourceTimeGrid`):
- Termine mit Ressource erscheinen in der jeweiligen Zeile
- Termine ohne Ressource erscheinen in einer eigenen Zeile `"Nicht zugeordnet"` (dummy resource `id: "__unassigned__"`)
- Doppelbuchungs-Check läuft in `ressource_api.py` bei Create und Update

---

## Google Calendar Import

- OAuth2-Flow via `google_import.py`
- Importiert Termine in einen wählbaren Kronos-Kalender
- Duplikatschutz: externe Google-Event-ID wird gespeichert, bereits importierte Termine werden übersprungen
- Konfiguration: `Diakronos Einstellungen → Google OAuth Client ID/Secret`

---

## Sicherheit

- Alle API-Endpunkte: `@frappe.whitelist(allow_guest=False)`
- Rollenprüfung serverseitig in jeder Funktion (kein Vertrauen in Frontend-State)
- XSS-Schutz: `escHtml()` / `safeCssColor()` in allen Modals vor HTML-Ausgabe
- CalDAV nur mit gültiger Frappe-Session (keine anonymen Zugriffe)
- SSH-Keys und Secrets sind in `.gitignore` erfasst und waren nie Bestandteil der veröffentlichten Historie

---

## Abhängigkeiten

| Bibliothek | Version | Zweck | Lizenz |
|-----------|---------|-------|--------|
| [EventCalendar](https://github.com/vkurko/calendar) | 1.x | Kalender-Rendering | MIT |
| [Moment.js](https://momentjs.com) | 2.x | Datumsformatierung | MIT |
| [Flatpickr](https://flatpickr.js.org) | 4.x | Datum-/Zeitauswahl | MIT |
| [SortableJS](https://sortablejs.github.io) | 1.x | Drag & Drop Kanban | MIT |
| [Tabler Icons](https://tabler.io/icons) | 3.x | SVG-Icons | MIT |

---

## Changelog

### v16 – Aktuelle Version

- Migration von FullCalendar v6 auf **EventCalendar** (vkurko/calendar, MIT)
- Ressourcen (Räume) mit Kapazität und Bild; Timeline-Ansicht
- Dreistufiger Moderationsstatus: `Vorschlag` → `Festgelegt` / `Konflikt`
- Kanban-Moderationsseite (`/kronos/moderation`) mit SortableJS
- `view_mode`-Parameter: Im Lesemodus sehen alle nur `Festgelegt`-Termine
- CalDAV liefert ausschließlich `Festgelegt`-Termine
- `Kalenderadministrator` sieht alle Kalender und alle Statuses
- Alle Icons auf Tabler Icons (SVG, MIT) umgestellt
- SSH-Key aus vollständiger Git-Historie entfernt
