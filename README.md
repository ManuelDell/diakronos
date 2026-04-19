<img width="1353" height="440" alt="grafik" src="https://github.com/user-attachments/assets/df0d3c84-bf23-4bfe-bf23-7014b2e6333b" />


**Diakronos** ist eine kostenlose, selbst-gehostete Gemeinde-Software – eine offene Alternative zu ChurchTools. Eure Daten bleiben bei euch, auf eurem eigenen Server. Keine monatlichen Kosten, keine Cloud, kein Datenschutz-Kompromiss.

Gebaut für Freikirchen und kleinere Gemeinden, die eine einfache, ehrliche Lösung suchen.

---

## Was kann Diakronos?

| Modul | Stand | Kurzbeschreibung |
|-------|-------|-----------------|
| **Kronos** | ✅ Einsatzbereit | Gemeinde-Kalender mit CalDAV-Sync, Raumverwaltung und Freigabe-Workflow |
| **Diakonos** | 🚧 In Entwicklung | Mitgliederverwaltung, Gruppen, DSGVO-Tools |
| **Psalmos** | 📋 Geplant | Liedverwaltung, Gottesdienst-Ablaufplaner, OpenLP-Import |
| **Oikonomia** | 📋 Geplant | Kassenbuch, Kollekten, Spendenbescheinigungen |

---

## Kronos – Kalender

Kronos ist ein vollständiger Gemeinde-Kalender, der direkt im Browser läuft – keine App nötig. Termine lassen sich mit Apple Kalender, Thunderbird und allen gängigen Kalender-Apps synchronisieren (CalDAV).

![Kronos Beispiel](https://github.com/user-attachments/assets/fa249469-805a-46ff-a5ab-80d9d583f4e4)


**Was ihr bekommt:**
- Monats-, Wochen- und Tagesansicht
- **Raumbelegungsansicht** – alle Räume auf einen Blick, wer hat wann gebucht
- Mehrere Kalender mit eigenen Farben und Zugriffsrechten
- Räume und Ressourcen verwalten – mit automatischer Doppelbuchungs-Erkennung
- Wiederkehrende Termine (täglich, wöchentlich, monatlich, jährlich)
- Terminsuche: Suchleiste (Ctrl+F oder Avatar-Dropdown) mit Wasserfallsuche über Titel, Kalender und Raum
- Moderations-Workflow: neue Termine werden als Vorschlag eingereicht und von Berechtigten freigegeben
- Synchronisation mit Apple Kalender, Thunderbird, DAVx⁵ und Google Calendar
- Funktioniert auch auf dem Handy

→ [Technische Dokumentation Kronos](docs/kronos.md)

Import von Google Kalendar und iCal Dateien:
<img width="694" height="397" alt="Importierte Termine" src="https://github.com/user-attachments/assets/80bbe75f-6bdd-410d-a3c8-e711dbccb962" />
Moderation:
<img width="1854" height="1016" alt="Moderation" src="https://github.com/user-attachments/assets/7c3dbdbb-b208-4dbc-846e-7147dfdd4056" />
---

## Diakonos – Mitglieder

> 🚧 Grundstruktur vorhanden – vollständige Umsetzung in Arbeit

Diakonos wird die zentrale Anlaufstelle für alles rund um Mitglieder und Gruppen:

**Was kommt:**
- Mitgliederdaten verwalten (Kontakt, Adresse, Gruppen, Eintrittsdatum)
- Gruppenmanagement mit Mitgliedschaftsverwaltung
- DSGVO-Werkzeuge: Einwilligung erfassen, Daten auf Knopfdruck exportieren oder löschen
- Berichte und Übersichten

→ [Technische Dokumentation Diakonos](docs/diakonos.md)

---

## Psalmos – Liedverwaltung & Gottesdienst

> 📋 Geplant – Umsetzung nach Diakonos

Psalmos soll die Gottesdienstvorbereitung einfacher machen: Lieder verwalten, Ablaufpläne erstellen, direkt in OpenLP oder SongBeamer exportieren.

**Was auf jeden Fall kommt:**
- Liedverwaltung mit CCLI-Nummer und Textablage
- Drag-&-Drop-Ablaufplaner für den Gottesdienst
- Import aus OpenLP

**Was zusätzlich geprüft wird (noch nicht fix):**
- Synchronisation mit Nextcloud
- Mobile App für Worship-Leiter
- CCLI-Reporting (abhängig von externer Klärung)

> Die Verantwortung für CCLI- und GEMA-Lizenzen liegt bei der Gemeinde. Diakronos bietet technische Unterstützung, ersetzt aber keine Lizenzpflichten.

→ [Technische Dokumentation Psalmos](docs/psalmos.md)

---

## Oikonomia – Finanzen

> 📋 Geplant – Umsetzung nach rechtlicher Prüfung

Oikonomia soll die Gemeindefinanzen einfach und nachvollziehbar machen: Kassenbuch führen, Kollekten erfassen, Spendenbescheinigungen drucken.

> ⚠️ Das Finanzen-Modul ist ein **Hilfswerkzeug**. Die rechtliche Verantwortung für ordnungsgemäße Buchführung (GoBD), korrekte Spendenbescheinigungen und steuerrechtliche Anforderungen liegt ausschließlich bei der Gemeinde. Vor dem produktiven Einsatz empfehlen wir eine Prüfung durch einen Steuerberater.

→ [Technische Dokumentation Oikonomia](docs/oikonomia.md)

---

## Wer darf was?

| Rolle | Rechte |
|-------|--------|
| **Administrator** | Vollzugriff auf alles |
| **Kalenderadministrator** | Alle Kalender lesen & schreiben, Moderationsseite, Desk-Zugang |
| **Mitglied** | Kalender und Mitgliederbereich (je nach Konfiguration) |
| **Kalender-Moderator** | Pro Kalender einstellbar: Terminvorschläge bestätigen |

---

## Installation

```bash
bench get-app https://github.com/ManuelDell/diakronos
bench --site <site> install-app diakronos
bench --site <site> migrate
```

**Voraussetzungen:** Frappe v16, Python 3.11+, Node.js 18+

---

## Haftungsausschluss

Diakronos ist ein Hilfswerkzeug, das Gemeinden bei der Organisation und Verwaltung unterstützen soll. Es ersetzt keine rechtliche, steuerliche oder datenschutzrechtliche Beratung.

**Die Verantwortung für die rechtskonforme Nutzung liegt ausschließlich bei der betreibenden Gemeinde**, insbesondere:

- **DSGVO:** Die Gemeinde ist Verantwortliche im Sinne der DSGVO und muss die rechtmäßige Verarbeitung von Personendaten sicherstellen.
- **GoBD:** Das Finanzen-Modul unterstützt die Erfassung von Buchungen, ersetzt aber keine geprüfte Buchführungslösung.
- **CCLI:** Die Gemeinde ist für gültige Lizenzen und korrekte Berichterstattung verantwortlich.

Der Entwickler übernimmt keine Haftung für Schäden oder rechtliche Folgen aus der Nutzung dieser Software.

---

## Lizenz

MIT License – siehe [LICENSE](LICENSE)
