# Changelog

Alle nennenswerten Änderungen an Diakronos werden hier dokumentiert.
Format angelehnt an [Keep a Changelog](https://keepachangelog.com/de/1.0.0/).

---

## [Unreleased]

### Kronos – Raumbelegungsansicht

**Behoben**
- Ressourcen-Sidebar (Raumnamen) in der Wochen-Raumbelegungsansicht wird jetzt korrekt neben der Timeline angezeigt statt dahinter
- Timeline-Spalten verteilen sich gleichmäßig auf die volle Bildschirmbreite (vorher: Spalten nur so breit wie der Inhalt)
- Getimte Termine werden in der Raumbelegung korrekt als Nicht-Ganztags-Termine dargestellt

**Technisch**
- EC-Subgrid-Kette (`ec-main → ec-body → ec-grid`) bleibt intakt; nur `ec-main` wird überschrieben
- `Heute`-Button-Event-Listener werden erst nach Kalender-Initialisierung gesetzt (verhindert Race Condition)
- `resourceAreaWidth: 200` als explizite EC-Option gesetzt

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
