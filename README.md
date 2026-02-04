# Da ich noch in der Grundentwicklung bin ist die gesamte Readme KI-Generiert. Die App ist noch nicht Produktionsreif, der Main Branch ist noch immer im Entwicklungsstadium


# 📅 Diakronos - Gemeinde-Management App

Eine **Frappe/ERPNext-basierte Anwendung** für Gemeinde- und Kirchenverwaltung mit integriertem Kalender-System, Mitgliederverwaltung und Event-Management.

---

## 🎯 Überblick

**Diakronos** ist eine modulare Web-Anwendung für kirchliche und gemeinnützige Organisationen zur Verwaltung von:
- 📅 **Veranstaltungen** - Gottesdienste, Kurse, Events mit Wiederholungen
- 👥 **Mitgliedern** - Profile, Kontakte, Dienste und Verantwortungen
- 🎵 **Musik & Liederlisten** - Dirigenten, Vortragsrechte
- 🔐 **Berechtigungen** - Granulare Rollen und Zugriffskontrolle
- 🌍 **CalDAV-Sync** - Synchronisation mit Nextcloud (geplant)

---

## 📦 Modulstruktur

```
diakronos/                    ← Root App
├── kronos/                   ← 🗓️  Kalender-Modul (Kern)
├── diakonos/                 ← 👥 Mitgliederverwaltung
├── psalmos/                  ← 🎵 Musikverwaltung
└── [diakronos]/              ← ⚙️  Globale Komponenten & UI
```

### **Kronos** - Kalendermodul (Kern)

Das Hauptmodul für Event-Management:

| Feature | Status | Beschreibung |
|---------|--------|-------------|
| **FullCalendar Integration** | ✅ Live | Moderne Web-Kalender UI |
| **Event CRUD** | ✅ Live | Erstellen, Bearbeiten, Löschen |
| **Serien/Wiederholungen** | ✅ Live | Wiederkehrende Events (täglich, wöchentlich, etc.) |
| **Farb-Codierung** | ✅ Live | Automatische Farben je Event-Typ |
| **Monat/Wochenansicht** | ✅ Live | Umschaltbar zwischen Views |
| **Modal-Dialog** | ✅ Live | Schnelle Event-Erstellung |
| **Drag & Drop** | ✅ Live | Events verschieben/resizen |
| **Deutsch-Lokalisierung** | ✅ Live | Vollständig auf Deutsch |
| **CalDAV-Sync** | 🔄 Geplant | Nextcloud/CardDAV Synchronisation |
| **Berechtigungen** | ✅ Live | Granulare Zugriffskontrolle pro Kalender |

#### **Implementierte Event-Typen mit Farben:**
```
Gottesdienst   → Rot       (#c41e3a)
Bibelstunde    → Blau      (#4285f4)
Gebetskreis    → Grün      (#34a853)
Musikprobe     → Gelb      (#fbbc04)
Jugend         → Hell-Rot  (#ea4335)
Kinder         → Violett   (#9c27b0)
Seelsorge      → Cyan      (#00bcd4)
```

### **Diakonos** - Mitgliederverwaltung

Verwaltung der Gemeindeangehörigen:

| DocType | Status | Beschreibung |
|---------|--------|-------------|
| **Mitglied** | ✅ Live | Vollständige Mitgliederverwaltung |
| **Besucher** | ✅ Live | Gäste und Interessierte |
| **Kinder** | ✅ Live | Kindergottesdienst & Kinderbetreuung |
| **Dienstbereich** | ✅ Live | Dienste und Aufgaben |

#### **Mitglied DocType - Felder:**
- Name, Vorname, Geburtsdatum
- Adresse, Telefon, E-Mail
- Getauft, Konfirmation
- Status (aktiv/inaktiv)
- Dienstbereiche (Beziehungen)

### **Psalmos** - Musikverwaltung

Verwaltung von Musik und Vortragsrechten:

| Feature | Status |
|---------|--------|
| Liederlisten | 🔄 Geplant |
| Dirigenten & Musiker | 🔄 Geplant |
| Vortragsrechte | 🔄 Geplant |
| Paperless-Integration | 🔄 Geplant |

---

## 🏗️ Technische Struktur

### **Frontend-Architektur**

```
www/kronos-web/
└── index.html                          (Frappe Web-Page Template)
        ↓ lädt
public/js/kronos_web.js               (Main Entry Point - 182 Zeilen)
        ↓ lädt Module in Reihenfolge
        ├── modules/kronos_calendar.js (Calendar Init - 162 Zeilen)
        ├── modules/kronos_events.js   (Event CRUD - 78 Zeilen)
        └── modules/kronos_modal.js    (Dialog UI - 176 Zeilen)
        ↓ nutzt externe Library
public/js/fullcalendar.min.js          (FullCalendar v6)
        ↓ styled mit
public/css/kronos_web.css              (414 Zeilen, Responsive)
```

**Warum Modular?**
- ✅ Schneller Initial Load (~2KB Main)
- ✅ Lazy Loading der Features
- ✅ Einfacher zu debuggen
- ✅ Parallel-Entwicklung möglich

### **Backend-Struktur**

```
kronos/
├── api/
│   ├── events.py              ← Event APIs (GET/POST/PUT/DELETE)
│   ├── calendars.py           ← Kalender APIs (GET)
│   ├── permissions.py         ← Permission-Checks
│   ├── sync.py                ← CalDAV Sync (geplant)
│   └── tui_management.py      ← Frontend-Event-Handler
├── doctype/
│   ├── element/               ← Event DocType
│   │   ├── element.json
│   │   ├── element.py
│   │   └── element.js
│   ├── kalender/              ← Kalender DocType
│   └── nutzereinzelrechte/    ← Permission DocType
├── handlers/
│   └── (Event Hooks, Triggers)
└── __init__.py

diakonos/
├── doctype/
│   ├── mitglied/              ← Member DocType
│   ├── besucher/              ← Visitor DocType
│   ├── kinder/                ← Kids DocType
│   └── dienstbereich/         ← Service Area DocType
└── report/
    └── mitgliedsliste/        ← Member List Report

fixtures/
├── module_def.json            ← Module Definitions
├── workspace.json             ← Dashboard/Workspace
└── [weitere Fixtures]

hooks.py                        ← App Config
modules.txt                     ← Module Registry
README.md                       ← Diese Datei
```

---

## 📋 Bisher Implementierte Features

### ✅ Fertig (Production)

- **Kalender-Grundfunktionalität**
  - Monats- und Wochenansicht
  - Event-Anzeige mit Farbcodierung
  - Datum-Navigation (vor/zurück/heute)

- **Event-Management**
  - Erstellen (Modal-Dialog)
  - Bearbeiten (Drag & Drop)
  - Löschen
  - Zeit-Anpassung durch Verschieben

- **Benutzerinteraktionen**
  - Click auf Datum → neues Event
  - Click auf Event → Detail-View
  - Drag & Drop → Event verschieben
  - Resize → Event-Dauer ändern

- **Mitgliederverwaltung**
  - CRUD für Mitglied, Besucher, Kinder
  - Dienstbereiche zuordnen
  - Reports (Mitgliedsliste)

- **Berechtigungen**
  - Rollen-basierte Zugriffskontrolle
  - Granulare Kalender-Berechtigungen
  - Benutzerrechte Manager

- **Deutsch-Lokalisierung**
  - Alle UI-Texte auf Deutsch
  - FullCalendar auf Deutsch
  - Datums-Format Deutsch

### 🔄 In Entwicklung

- **Serie/Wiederholungen**
  - UI für Serientermin-Erstellung ✅
  - Backend-Logik für Generierung ✅
  - Bearbeitung von Einzelinstanzen (geplant)

- **API-Reorganisation**
  - Aufteilen in spezialisiertere Module
  - Bessere Separation of Concerns
  - Improved Testing (geplant)

### 🗺️ Geplant (Roadmap)

- CalDAV-Synchronisation (Nextcloud)
- SMS-Benachrichtigungen
- Mobile App (Progressive Web App)
- Musik-Modul (Psalmos) - vollständig
- Erweiterte Reports & Analytics
- Import/Export (CSV, iCal)
- Wiederkehrende Events editieren

---

## 🚀 Installation

### Voraussetzungen

```
- Frappe/ERPNext (v14+)
- Bench CLI
- Python 3.9+
- Node.js 14+
```

### Setup

```bash
# 1. App klonen
cd ~/frappe-bench
bench get-app https://github.com/deinname/diakronos.git

# 2. App installieren
bench --site sitename install-app diakronos

# 3. Datenbank migrieren
bench migrate

# 4. Cache leeren
bench clear-cache

# 5. Neustarten
bench restart

# 6. Öffne http://localhost:8000/app/kronos-web
```

---

## 📋 Verwendung

### Kalender öffnen

```
Menu → Kronos Calendar
oder direkt: http://your-bench.local/app/kronos-web
```

### Neuer Termin erstellen

```
1. Klick auf Datum im Kalender
2. Modal-Dialog öffnet sich
3. Fülle Felder aus:
   - Titel (z.B. "Gottesdienst")
   - Kalender (welcher Kalender)
   - Start/Ende (Datum & Uhrzeit)
   - (Optional) Serientermin-Einstellungen
4. Klick "Speichern"
5. Event erscheint im Kalender
```

### Event bearbeiten

```
Option A (Schnell):
1. Event im Kalender ziehen → Zeit ändern
2. Automatisch gespeichert

Option B (Detailliert):
1. Click auf Event
2. Detailseite öffnet sich
3. Felder bearbeiten
4. Speichern
```

### Event löschen

```
1. Click auf Event
2. Detailseite
3. Button "Delete"
4. Bestätigen
```

### Mitglieder verwalten

```
Menu → Mitglied (oder Besucher, Kinder)
1. Liste aller Mitglieder
2. + New zum Erstellen
3. Row klicken zum Bearbeiten
```

---

## ⚙️ Konfiguration

### Berechtigungen setzen

```
Desk → Setup → Role Permissions Manager

Verfügbare Rollen:
- Viewer: Nur Lesezugriff
- Editor: Erstellen/Bearbeiten
- Manager: Volle Kontrolle
- System Manager: Admin
```

### Standard-Kalender für Nutzer

```
Desk → Setup → Nutzer → [Nutzer bearbeiten]
Feld: "Default Calendar" 
Wert: z.B. "Gottesdienste"
```

### Event-Typen konfigurieren

```
Datei: public/js/modules/kronos_calendar.js
Suche: "colorMap = {"
Ändere Event-Namen und Farben nach Bedarf
```

---

## 🔧 Entwicklung

### Code-Qualität

```bash
cd apps/diakronos

# Pre-commit einrichten (optional)
pip install pre-commit
pre-commit install

# Manuell checken
pre-commit run --all-files
```

**Verwendete Tools:**
- ruff (Python Linting)
- pyupgrade (Python Modernisierung)
- eslint (JavaScript Linting)
- prettier (Code-Formatierung)

### Branch-Strategie

```
main      → Production (stabil)
  ├── develop  → Integration
  └── feature/* → Features
```

**Workflow:**
```bash
git checkout -b feature/mein-feature
# ... Code ändern ...
git add .
git commit -m "feat: kurze beschreibung"
git push origin feature/mein-feature
# → Pull Request erstellen
```

### API-Struktur (Nach Refactoring)

```
kronos/api/
├── calendar_get.py         # GET: Kalender, Events
├── event_crud.py           # CREATE/UPDATE/DELETE Events
├── series_create.py        # CREATE: Wiederkehrende
├── permission_check.py     # CHECK: Berechtigungen
└── permission_defaults.py  # GET: Dialog-Defaults

kronos/handlers/
└── series_handler.py       # Logik für Serien-Generierung
```

---

## 🐛 Troubleshooting

### "API nicht gefunden"

```bash
# Cache leeren
bench clear-cache

# Browser-Cache leeren (Ctrl+Shift+Del)

# Frappe neustarten
bench restart
```

### Kalender zeigt keine Events

```
1. Öffne Browser Console (F12)
2. Suche nach Fehlern
3. Prüfe ob Backend APIs erreichbar:
   frappe.call({
       method: 'diakronos.kronos.api.events.get_calendar_events',
       args: {...}
   })
4. Prüfe ob Mitglied Kalender-Leserechte hat
```

### Events werden nicht angezeigt, aber sollten

```
Prüfe:
1. Datum korrekt? (start_date ≤ event_date ≤ end_date)
2. Kalender sichtbar im Filter?
3. User-Berechtigungen ok?
4. Event-DocType im Backend vorhanden?
```

### Performance-Probleme

```
Für viele Events:
1. Erhöhe dayMaxEvents in kronos_calendar.js
   dayMaxEvents: 5  // statt 3
2. Nutze Wochenansicht statt Monatsansicht
3. Filterung nach Kalender einführen
```

---

## 📊 Datenbankschema

### Element (Event) DocType

```
name                  → Eindeutige ID (auto)
element_name          → Titel des Events
element_calendar      → Link zu Kalender
element_start         → Start DateTime
element_end           → End DateTime
repeatthisevent       → Boolean (Serie aktiv?)
repeaton              → "Daily", "Weekly", "Monthly", etc.
repeattill            → End-Datum (oder null = unendlich)
monday-sunday         → Checkboxes für Wochentage
owner                 → Ersteller (auto)
modified              → Änderungsdatum (auto)
```

### Kalender (Kalender) DocType

```
name                  → Kalender-Name (z.B. "Gottesdienste")
title                 → Anzeige-Name
owner                 → Besitzer
users                 → Tabelle mit Benutzern & Rechten
  - user              → Benutzer-ID
  - perm_read         → Leseberechtigung
  - perm_write        → Schreibberechtigung
  - perm_delete       → Löschberechtigung
```

### Mitglied DocType

```
name                  → ID (auto)
vorname               → Vorname
nachname              → Nachname
email                 → E-Mail
telefon               → Telefon
geburtsdatum          → Geburtsdatum
getauft               → Date of baptism
dienstbereiche        → Tabelle mit Dienstbereichen
  - dienst            → Link zu Dienstbereich
status                → "Aktiv" oder "Inaktiv"
```

---

## 📄 Lizenz

MIT License - Siehe `LICENSE` Datei


