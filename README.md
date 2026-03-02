# Diakronos – Kronos Kalender

Eine Frappe-App für Gemeinde- und Kirchenverwaltung mit webbasiertem Kalender, CalDAV-Server und rollenbasierten Berechtigungen.

---

## Neuigkeiten in diesem Release (März 2026)

### Mobile UX komplett überarbeitet

Der Header auf Mobilgeräten (`≤ 768 px`) wurde neu strukturiert:

- **Links:** Hamburger-Menü (öffnet Sidebar als Vollbild-Overlay) + aktueller Monatsname (ohne Jahr)
- **Rechts:** Heute-Button (Icon) + Profil-Avatar
- View-Switcher, Navigation und Mini-Kalender sind auf Mobile ausgeblendet
- Sidebar ist touch-scrollbar (`-webkit-overflow-scrolling: touch`)

### Profil-Avatar mit Frappe-Benutzerbildern

Wenn ein Nutzer in Frappe ein Profilbild hinterlegt hat, wird es im Avatar-Button angezeigt. Ohne Bild: Initialbuchstabe wie bisher.

### Flatpickr – neuer Datum/Uhrzeit-Picker

Der native `datetime-local`-Browser-Picker wurde durch **Flatpickr** ersetzt (CDN-geladen):

- Deutsch lokalisiert
- 24-h-Format, 5-Minuten-Schritte
- Anzeige: „15. März 2026, 14:30"
- **Beginn** und **Ende** in Create- und Edit-Modal
- **Serie endet am** im Create-Modal (nur Datum)
- Start → End wird automatisch auf +1 h gesetzt

### Datum-Vorausfüllung beim Klick auf einen leeren Tag

Im Bearbeitungsmodus: Klick auf einen Tag füllt Beginn mit dem Datum des Tages + aktueller Uhrzeit (auf 5 Min gerundet) vor. Ende = Beginn + 1 h. Der FAB-Button öffnet den Dialog weiterhin ohne Vorbelegung.

### NavLinks (Desktop): Klick navigiert direkt in die Ansicht

- Klick auf eine **Tageszahl** → Tagesansicht (`timeGridDay`)
- Klick auf eine **Kalenderwochenzahl** → Wochenansicht (`timeGridWeek`)
- Nur auf Desktop (`> 768 px`), Mobile-Verhalten unverändert

### Kalenderwochen

- Desktop: sichtbar in FullCalendars natürlicher Grid-Spalte (statt absolut positioniert)
- Mobile: blau (`#6a9fd8`), fett, 8 px (ca. 25 % kleiner als Tagesnummern)

### fixedWeekCount: false

FullCalendar zeigt jetzt nur so viele Wochen wie der Monat wirklich braucht. Behebt das Problem der winzigen letzten Zeile bei 5-Wochen-Monaten.

---

## Bugfixes

| # | Problem | Fix |
|---|---------|-----|
| 1 | Im Bearbeitungsmodus wurden zwei Create-Dialoge gleichzeitig geöffnet | `dateClick` überlässt dem `select`-Handler das Öffnen |
| 2 | CalDAV-Hilfe-Modal blockierte nach dem Schließen alle Klicks | Overlay wird nach `transitionend` aus dem DOM entfernt |
| 3 | Avatar-Dropdown öffnete links außerhalb des sichtbaren Bereichs | Position wird per `getBoundingClientRect()` korrigiert |
| 4 | Sidebar-Checkboxen starteten auf verschiedenen x-Positionen | Doppelte CSS-Regeln bereinigt, einheitliches Padding |

---

## Änderungsprotokoll der betroffenen Dateien

| Datei | Änderung |
|-------|---------|
| `public/js/builder/header_build_elements.js` | Mobile-Header, Heute-Icon, Avatar-Bild, Dropdown-Positionsfix |
| `public/js/builder/kronos_calendar.js` | `fixedWeekCount`, `navLinks`, `select`-Handler Datum+Zeit |
| `public/js/builder/sidebar_build_elements.js` | CalDAV-Overlay DOM-Cleanup |
| `public/js/modal/modal_create.js` | Flatpickr, series_end-Picker, Datum-Vorausfüllung |
| `public/js/modal/modal_edit.js` | Flatpickr, all-day Handler |
| `public/css/kronos_layout.scss` | Kalenderwochen-Styling, fixedWeekCount-CSS entfernt |
| `public/css/kronos_header_buttons.scss` | Mobile-Defaults, Heute-Icon-Button |
| `public/css/kronos_sidebar.scss` | Mobile Vollbild-Sidebar, touch-scroll |
| `public/css/kronos_modal.scss` | Flatpickr-Wrapper-CSS |
| `kronos/api/permissions.py` | `user_image` in `get_session_info` |
| `www/kronos/calendar.html` | Flatpickr CDN (CSS + JS + DE-Locale) |

---

## Bekannte Einschränkungen

- Flatpickr wird von CDN (jsDelivr) geladen – kein Offline-Betrieb ohne lokale Kopie
- Für lokalen Betrieb: Dateien nach `/assets/diakronos/js/lib/flatpickr/` kopieren und HTML-Pfade anpassen

---

*Vorheriger Release: `feat(mobile): swipe-Navigation, Google-Calendar-Styling, Sicherheitsfixes`*
