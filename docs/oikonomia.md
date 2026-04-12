# Oikonomia – Technische Dokumentation

→ [Zurück zur Übersicht](../README.md)

> 📋 Modul geplant – Umsetzung erst nach externer steuerrechtlicher Prüfung

---

## Geplante Architektur

```
oikonomia/
  doctype/
    kassenbuch_eintrag/      # Einzelbuchung (unveränderlich nach Abschluss)
    kassenbuch_abschluss/    # Monats-/Jahresabschluss mit Hash-Chain
    kollekte/                # Kollekten-Erfassung + Zählprotokoll
    kollekte_position/       # Child-Table: Stückelung
    spendenbescheinigung/    # PDF-Bescheinigung nach amtlichem Muster
    bankimport/              # CAMT.053 / CSV-Importprotokoll
  api/
    kassenbuch_api.py        # CRUD (mit Unveränderlichkeits-Lock)
    kollekte_api.py          # Kollekte erfassen
    spende_api.py            # Spendenbescheinigung generieren
    bankimport_api.py        # CAMT.053 / CSV-Parser
  report/
    monatsuebersicht/        # Einnahmen/Ausgaben pro Monat
    jahresuebersicht/        # Jahresbericht
    kollektenbericht/        # Kollekten nach Datum und Verwendungszweck
  www/
    oikonomia/               # Finanz-SPA
```

---

## Datenbankmodell (Entwurf)

### `KassenbuchEintrag`

| Feld | Typ | Beschreibung |
|------|-----|-------------|
| `buchungsdatum` | Date | Buchungsdatum |
| `betrag` | Currency | Betrag (positiv = Einnahme, negativ = Ausgabe) |
| `buchungstext` | Data | Beschreibung der Buchung |
| `kategorie` | Link → Buchungskategorie | Einnahme-/Ausgabenkategorie |
| `beleg_nummer` | Data | Belegnummer für Dokumentation |
| `erstellt_von` | Link → User | Erfassender Nutzer |
| `gesperrt` | Check | True nach Monatsabschluss → unveränderlich |
| `hash` | Data | SHA-256 Hash der Buchungsdaten (GoBD-Nachweis) |

### `KollektePosition` (Child-Table)

| Feld | Beschreibung |
|------|-------------|
| `stueckelung` | Nennwert (z. B. 0.01, 0.02, 0.05, ..., 50.00, 100.00) |
| `anzahl` | Stückzahl |
| `summe` | Automatisch berechnet (stueckelung × anzahl) |

### `Spendenbescheinigung`

| Feld | Beschreibung |
|------|-------------|
| `mitglied` | Link → Mitglied |
| `spendensumme` | Currency |
| `zeitraum_von` | Date |
| `zeitraum_bis` | Date |
| `ausstellungsdatum` | Date |
| `pdf_datei` | Attach (generiertes PDF) |

---

## GoBD-Compliance-Konzept

GoBD (Grundsätze zur ordnungsmäßigen Führung und Aufbewahrung von Büchern) stellt folgende Anforderungen:

| Anforderung | Geplante Umsetzung |
|-------------|-------------------|
| Unveränderlichkeit | `gesperrt`-Flag nach Monatsabschluss; direkte DB-Änderungen werden durch Frappe-Permissions geblockt |
| Nachvollziehbarkeit | Jede Buchung enthält `erstellt_von`, `erstellt_am` (Frappe-Standard) |
| Vollständigkeit | Monatsabschluss-Mechanismus: offene Buchungen müssen vor Abschluss bestätigt werden |
| Unveränderlicher Nachweis | SHA-256 Hash je Buchung; Abschluss enthält Hash der Vorgänger-Buchung (Hash-Chain) |
| Aufbewahrung | Buchungen bleiben nach gesetzlicher Aufbewahrungsfrist (10 Jahre) in der Datenbank |

> ⚠️ **Wichtig:** Die technische Umsetzung allein macht ein System nicht GoBD-konform. Die Verantwortung für ordnungsgemäße Buchführung, korrekte Kategorisierung und fristgerechte Aufbewahrung liegt bei der Gemeinde. Eine Prüfung durch einen Steuerberater wird dringend empfohlen.

---

## CAMT.053 / CSV-Bankimport

- CAMT.053: XML-basiertes Kontoauszugsformat (ISO 20022), von deutschen Banken unterstützt
- CSV: Fallback für Banken ohne CAMT-Support (Mapping bank-spezifisch konfigurierbar)
- Import erstellt ungesperrte Entwurfs-Buchungen zur manuellen Prüfung vor Bestätigung

---

## Spendenbescheinigungen

- Generierung als PDF nach dem offiziellen Muster des Bundesfinanzministeriums
- Nur für als gemeinnützig anerkannte Körperschaften rechtlich zulässig
- PDF wird als Anhang am `Spendenbescheinigung`-Dokument gespeichert

> **Hinweis:** Das amtliche Muster für Spendenbescheinigungen kann sich ändern. Die Gemeinde ist verantwortlich sicherzustellen, dass das verwendete Muster aktuell und korrekt ist. Vor dem produktiven Einsatz Prüfung durch Steuerberater erforderlich.

---

## Geplante Berichte

| Bericht | Beschreibung |
|---------|-------------|
| Monatsübersicht | Einnahmen, Ausgaben, Saldo pro Monat |
| Jahresbericht | Jährliche Zusammenfassung mit Kategorien |
| Kollektenbericht | Kollekten nach Datum, Betrag und Verwendungszweck |
| Spendenliste | Alle Spenden eines Zeitraums mit Empfänger (für interne Kontrolle) |

---

## Rechtliche Einordnung

Dieses Modul richtet sich an Vereine und Körperschaften, die **Einnahmenüberschussrechnung (EÜR)** nach § 4 Abs. 3 EStG führen. Es ist **nicht** für bilanzpflichtige Körperschaften (doppelte Buchführung nach HGB) konzipiert.

Für bilanzpflichtige Gemeinden (z. B. Körperschaften des öffentlichen Rechts oder größere eingetragene Vereine) ist eine spezialisierte Buchhaltungssoftware erforderlich.
