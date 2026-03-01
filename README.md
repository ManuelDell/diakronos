> **Hinweis:** Diese App befindet sich aktiv in Entwicklung. Der `develop-frappe-page`-Branch ist der aktuelle Arbeitsstand. `main` ist noch nicht produktionsreif.

# Diakronos

Eine Frappe-App für Gemeinde- und Kirchenverwaltung. Kern ist ein webbasierter Kalender (`/kronos/calendar`) mit eingebettetem CalDAV-Server für die Synchronisation mit iPhone, Android und Thunderbird.

---

## Features

### Kronos – Kalender (Kern)

| Feature | Status |
|---------|--------|
| Monats-, Wochen-, Tagesansicht | ✅ |
| Termin erstellen, bearbeiten, löschen | ✅ |
| Serienlermine (täglich / wöchentlich / monatlich / jährlich, max. 100) | ✅ |
| Drag & Drop und Resize im Bearbeitungsmodus | ✅ |
| Kalender-Farbcodierung | ✅ |
| Rollen-basierte Berechtigungen (Lesen / Schreiben pro Kalender) | ✅ |
| Mini-Kalender in der Sidebar | ✅ |
| Profil-Dropdown mit Abmelden / Desk / Apps | ✅ |
| CalDAV-Server (eingebettet, Basic Auth mit Frappe-Zugangsdaten) | ✅ |
| Automatische nginx-Konfiguration bei Installation | ✅ |
| Startseiten-Weiterleitung nach Login (nach Rolle) | ✅ |

### Weitere Module (in Entwicklung)

- **Diakonos** – Mitgliederverwaltung (Mitglied, Besucher, Kinder, Dienstbereich)
- **Psalmos** – Musikverwaltung (geplant)

---

## Installation

```bash
# 1. App holen
cd ~/frappe-bench
bench get-app https://github.com/deinname/diakronos.git

# 2. App auf Site installieren (führt setup/install.py aus → nginx wird automatisch konfiguriert)
bench --site deine-site.de install-app diakronos

# 3. Assets bauen
bench build --app diakronos

# 4. Datenbank migrieren und Cache leeren
bench migrate
bench clear-cache

# 5. Neustart
bench restart
```

Kalender öffnen: `https://deine-domain.de/kronos/calendar`

---

## CalDAV-Sync

Der eingebettete CalDAV-Server stellt Kalender für externe Clients bereit.

**Zugangsdaten:**
| Feld | Wert |
|------|------|
| Server-Adresse | `https://deine-domain.de/dav/` |
| Benutzername | Frappe-E-Mail-Adresse |
| Passwort | Frappe-Passwort |

**Clients:**
- **iPhone/iPad:** Einstellungen → Apps → Kalender → Kalender-Accounts → Account hinzufügen → Andere → CalDAV
- **Android:** App [DAVx⁵](https://www.davx5.com/) (Play Store) → Mit URL und Benutzername anmelden
- **Thunderbird:** Kalender-Ansicht → Neuer Kalender → Im Netzwerk → CalDAV

> **Hinweis nginx:** Die Installation konfiguriert nginx automatisch (umgeht den Trailing-Slash-Rewrite für `/dav`).
> Nach `bench setup nginx` einmalig wiederherstellen:
> ```bash
> bench execute diakronos.setup.nginx.setup_caldav_nginx
> ```

---

## Berechtigungen

Jeder Kalender hat zwei Benutzer-Tabellen im Desk (`Kalender`-DocType):

- **Leserechte** – Benutzer sehen den Kalender (auch im CalDAV-Sync)
- **Schreibrechte** – Benutzer können Termine erstellen / bearbeiten / löschen

Die Benutzer-Rollen werden beim CalDAV-Zugriff geprüft – nur freigegebene Kalender werden synchronisiert.

---

## Login-Weiterleitung nach Rolle

In `hooks.py` kann konfiguriert werden, welche Rolle nach dem Login direkt zum Kalender weitergeleitet wird:

```python
role_home_page = {
    "Mitglied": "/kronos/calendar",
}
```

---

## Struktur

```
diakronos/
├── caldav/               ← Eingebetteter CalDAV-Server
│   ├── server.py         ← before_request Hook, Routing
│   ├── auth.py           ← Basic Auth gegen Frappe-Passwörter
│   └── ical.py           ← Element → iCalendar Konvertierung
├── kronos/
│   ├── api/              ← REST APIs (calendar_get, event_crud, permissions, ...)
│   └── doctype/          ← Element, Kalender, Eventkategorie
├── public/
│   ├── js/
│   │   ├── backend/      ← State (data.js), Events API (events_api.js)
│   │   ├── builder/      ← Header, Sidebar, Kalender-Init
│   │   └── modal/        ← Create, Edit, View, Series Modals
│   └── css/              ← SCSS-Module
├── setup/
│   ├── install.py        ← after_install Hook (Symlinks, Assets, nginx)
│   └── nginx.py          ← Idempotente nginx-Konfiguration für CalDAV
└── www/kronos/           ← Web-Page (calendar.html + calendar.py)
```

---

## Entwicklung

```bash
# Assets nach Änderungen neu bauen
bench build --app diakronos

# nginx CalDAV-Konfiguration wiederherstellen (nach bench setup nginx)
bench execute diakronos.setup.nginx.setup_caldav_nginx
```

**Branch-Strategie:**
- `main` – Production (angestrebt, noch nicht fertig)
- `develop-frappe-page` – Aktueller Entwicklungsstand

---

## Lizenz

MIT License
