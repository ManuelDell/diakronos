# Changelog

Alle nennenswerten Änderungen an Diakronos werden hier dokumentiert.
Format angelehnt an [Keep a Changelog](https://keepachangelog.com/de/1.0.0/).

---

## [Unreleased]

### Kronos – Terminsuche (Awesome Bar)

**Neu**
- Suchleiste für Kronos: öffnet per Klick auf „Suche" im Avatar-Dropdown oder mit Ctrl+F
- Zweiphasen-UI: zentrierte Suchleiste → nach Enter/Suchen-Klick bewegt sie sich nach oben, Ergebnisse erscheinen darunter (CSS-Transition)
- Wasserfallsuche: zuerst Titel, dann + Kalendername/Raum, dann + Beschreibung
- Serientermine werden gruppiert (frühste Instanz + Anzahl der Termine)
- Klick auf Ergebnis → Kalender springt in Monatsansicht auf den Termin, kurze Puls-Animation
- Auf der Moderationsseite: Klick auf Ergebnis leitet zum Kalender weiter (`/kronos/calendar?date=…`)
- Tastaturnavigation: Esc schließt, Pfeiltasten navigieren Ergebnisse, Enter öffnet aktives Ergebnis

**Technisch**
- Neues Backend-Modul `diakronos/kronos/api/search_api.py` mit Endpunkt `search_events`
- Neues Frontend-Modul `diakronos/public/js/search/kronos_search.js` (Overlay-Logik)
- Neues CSS `diakronos/public/css/kronos_search.scss` (Overlay + Puls-Animation)
- `kronos_search.scss` in `kronos.bundle.scss` und `kanban.bundle.scss` eingebunden
- `kronosCalendar.highlightEvent(id, dateStr)` + `_highlightEventId` in `kronos_calendar.js`
- Ctrl+F wird global abgefangen (Browser-Suche unterdrückt) – auf Kalender- und Moderationsseite

---

### Kronos – Moderationsbutton & Navigation

**Behoben**
- Moderationsbutton (FAB links unten) ist jetzt nur sichtbar wenn gleichzeitig der Bearbeitungsmodus aktiv ist UND Termine mit Status „Vorschlag" oder „Konflikt" vorliegen – im Beobachtungsmodus bleibt er immer ausgeblendet
- `Heute`-Button setzt jetzt auch den Mini-Kalender in der Sidebar auf den heutigen Tag zurück (vorher: nur Hauptkalender reagierte)
- Moderationsbutton: `display: flex` im CSS überschrieb das HTML-`hidden`-Attribut; Spezifitätsfehler behoben mit `.kronos-pending-btn[hidden] { display: none }`

**Neu**
- Backend-Endpunkt `get_moderation_count`: gibt die Anzahl zu moderierender Termine zurück (Vorschlag + Konflikt, Serien als ein Termin, nur für Kalender mit Moderationsrecht)

**Technisch**
- `_syncModerationBtn` ersetzt altes `_syncPendingBtn`: prüft Edit-Modus und holt Count aus DB statt aus Session-State
- `initMiniCalendar()` wird jetzt korrekt über den Singleton aufgerufen, sodass der exportierte `kronosMiniCalendar`-Binding für andere Module sichtbar ist
- `kronosCalendar.today()` statt direktem `kronosCalendar.calendar.today()` (EC hat keine native `today()`-Methode)

---

### Kronos – Raumbelegungsansicht

**Behoben**
- Ressourcen-Sidebar (Raumnamen) in der Wochen-Raumbelegungsansicht wird jetzt korrekt neben der Timeline angezeigt statt dahinter
- Timeline-Spalten verteilen sich gleichmäßig auf die volle Bildschirmbreite (vorher: Spalten nur so breit wie der Inhalt)
- Getimte Termine werden in der Raumbelegung korrekt als Nicht-Ganztags-Termine dargestellt

**Technisch**
- EC-Subgrid-Kette (`ec-main → ec-body → ec-grid`) bleibt intakt; nur `ec-main` wird überschrieben

---

## [0.3.0] – 2026-03-13

### CI/CD

**Neu**
- GitHub Actions Workflow: Python-Syntaxcheck + Import-Validierung auf push/PR
- ESLint für JavaScript (ES2022 modules, Browser-Globals)
- `scripts/check_imports.py`: prüft relative Imports in `__init__.py` gegen tatsächliche Exporte

---

## [0.2.0] – 2026-03-13

### Kronos – Raumbelegung (erster Anlauf)

**Neu**
- Raumbelegung-Button im Header (Desktop only)
- `resourceTimelineWeek`-Ansicht als erste Ressourcen-Timeline

**Behoben**
- HTTP 417 auf allen API-Calls: `get_event_details`-Import aus Phase-0-Bereinigung entfernt

---

## [0.1.0] – Initiale Version

### Kronos – Kalender

- Monats-, Wochen- und Tagesansicht
- Mehrere Kalender mit eigenen Farben und Zugriffsrechten
- Raum- und Ressourcenverwaltung mit Doppelbuchungs-Erkennung
- Wiederkehrende Termine (täglich, wöchentlich, monatlich, jährlich)
- Moderations-Workflow für Terminvorschläge
- CalDAV-Synchronisation (Apple Kalender, Thunderbird, DAVx⁵)
- Import aus Google Calendar und iCal-Dateien
- Mobile-optimierte Darstellung
