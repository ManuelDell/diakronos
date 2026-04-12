# Diakonos – Technische Dokumentation

→ [Zurück zur Übersicht](../README.md)

> 🚧 Modul in Entwicklung – Struktur steht, Felder und Logik werden ausgebaut

---

## Geplante Architektur

```
diakonos/
  doctype/
    mitglied/         # Vollständige Mitgliederdaten
    besucher/         # Besucherverwaltung (ohne Mitgliedschaft)
    kinder/           # Kinderdaten (mit Elternverweis)
    dienstbereich/    # Gruppen / Dienste
    gruppe/           # Gruppenstruktur (geplant)
    gruppe_mitglied/  # Child-Table: Mitgliedschaft in Gruppe (geplant)
    dsgvo_einwilligung/ # Consent-DocType (geplant)
  api/
    mitglied_api.py   # CRUD, Suche, Duplikatprüfung (geplant)
    dsgvo_api.py      # Export, Löschung (geplant)
  report/
    mitgliederliste/  # Bericht: alle Mitglieder (geplant)
    gruppenuebersicht/ # Bericht: Gruppen + Mitgliedszahlen (geplant)
  www/
    diakonos/         # Mitglieder-SPA (geplant)
```

---

## Datenbankmodell (Entwurf)

### `Mitglied`

| Feld | Typ | Beschreibung |
|------|-----|-------------|
| `vorname` | Data | Vorname |
| `nachname` | Data | Nachname |
| `geburtsdatum` | Date | Geburtsdatum |
| `geschlecht` | Select | Männlich / Weiblich / Divers |
| `strasse` | Data | Straße + Hausnummer |
| `plz` | Data | Postleitzahl |
| `ort` | Data | Ort |
| `telefon` | Phone | Telefonnummer |
| `email` | Data | E-Mail-Adresse |
| `eintrittsdatum` | Date | Eintrittsdatum in die Gemeinde |
| `austrittsdatum` | Date | Austrittsdatum (optional) |
| `taufdatum` | Date | Taufdatum (optional) |
| `gruppen` | Table | Mitgliedschaft in Gruppen (Child-Table) |
| `notizen` | Text | Interne Notizen |
| `dsgvo_einwilligung` | Link → DSGVO Einwilligung | Verknüpfung mit Consent-Dokument |

### `Gruppe`

| Feld | Beschreibung |
|------|-------------|
| `name` | Gruppenbezeichnung |
| `beschreibung` | Kurzbeschreibung |
| `leiter` | Link → Mitglied |
| `mitglieder` | Child-Table: Gruppe_Mitglied |

### `DSGVO_Einwilligung`

| Feld | Beschreibung |
|------|-------------|
| `mitglied` | Link → Mitglied |
| `einwilligungsdatum` | Date |
| `einwilligungstext` | Text (Version der Einwilligung) |
| `widerruf_datum` | Date (optional) |

---

## Geplante API-Endpunkte

Alle Endpunkte unter `@frappe.whitelist(allow_guest=False)` mit Rollenprüfung:

| Methode | Pfad | Beschreibung |
|---------|------|-------------|
| POST | `diakonos.api.mitglied_api.create_mitglied` | Neues Mitglied anlegen |
| POST | `diakonos.api.mitglied_api.update_mitglied` | Mitglied bearbeiten |
| POST | `diakonos.api.mitglied_api.search_mitglied` | Suche + Duplikatprüfung |
| POST | `diakonos.api.dsgvo_api.export_mitglied_data` | Personendaten-Export (Art. 20 DSGVO) |
| POST | `diakonos.api.dsgvo_api.delete_mitglied_data` | Datenlöschung (Art. 17 DSGVO) |

---

## Rollen

| Rolle | Zugriff |
|-------|---------|
| `Administrator` | Vollzugriff |
| `Gemeindeadministrator` (geplant) | Alle Mitglieder lesen/schreiben |
| `Mitglied` | Eigene Daten einsehen |

---

## Duplikat-Erkennung

Bei der Erfassung wird geprüft ob Vorname + Nachname + Geburtsdatum bereits existieren. Geplant ist zusätzlich eine Fuzzy-Suche auf dem Namen (Levenshtein-Distanz ≤ 2) um Tippfehler abzufangen.

---

## DSGVO-Implementierung

- `DSGVO_Einwilligung`-DocType speichert Einwilligungstext + Datum versioniert
- Einwilligung kann widerrufen werden (Widerruf-Datum setzen, Daten einfrieren)
- Ein-Klick-Export: alle Felder des Mitglieds als JSON/CSV (Art. 20)
- Ein-Klick-Löschung: Anonymisierung statt Hard-Delete (Audit-Trail bleibt erhalten) (Art. 17)

> **Hinweis:** Die rechtliche Verantwortung für DSGVO-konforme Nutzung (Einwilligungsgrundlage, Verarbeitungsverzeichnis, Datenschutzerklärung) liegt bei der betreibenden Gemeinde.
