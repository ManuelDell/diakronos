# Oikonomia – Technische Dokumentation

→ [Zurück zur Übersicht](../README.md)

> Modul geplant – noch nicht begonnen

---

## Aktueller Stand

Von Oikonomia existiert kein Code. Es gibt keine `oikonomia/`-Verzeichnisstruktur unter `diakronos/`.
Im Frappe-Desk existiert lediglich ein Workspace-Eintrag als Fixture (`fixtures/Workspace/`), der das Modul in der Navigation erscheinen lässt — ohne jegliche Funktionalität dahinter.

---

## Geplanter Zweck

Oikonomia soll die Finanzverwaltung der Gemeinde abdecken, ausgelegt für Körperschaften mit Einnahmenüberschussrechnung (EÜR nach § 4 Abs. 3 EStG):

- Kassenbuch mit unveränderlichen Buchungseinträgen (GoBD-Konzept)
- Kollekten-Erfassung mit Stückelungsprotokoll
- Spendenbescheinigungen nach amtlichem Muster
- Bankimport via CAMT.053 (ISO 20022) und CSV
- Monatliche und jährliche Abschlüsse mit Hash-Chain

---

## Geplante Architektur

```
oikonomia/
  doctype/
    kassenbuch_eintrag/      # Einzelbuchung (nach Abschluss gesperrt)
    kassenbuch_abschluss/    # Monats-/Jahresabschluss mit Hash-Chain
    kollekte/                # Kollekten-Erfassung + Zählprotokoll
    kollekte_position/       # Child-Table: Stückelung (Münzen/Scheine)
    spendenbescheinigung/    # PDF nach amtlichem Bundesfinanzministerium-Muster
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
    oikonomia/               # Finanz-SPA (Vue)
```

---

## Was fehlt um Oikonomia zu starten

1. Verzeichnis `diakronos/oikonomia/` mit `__init__.py` anlegen
2. Doctypes anlegen: `KassenbuchEintrag`, `KassenbuchAbschluss`, `Kollekte`, `KollektePosition`, `Spendenbescheinigung`, `BankImport`
3. API-Dateien erstellen
4. Whitelist-Einträge in `hooks.py` ergänzen
5. Frontend-SPA (Vue) bauen
6. Steuerrechtliche Prüfung durch Steuerberater vor Produktiveinsatz

---

## GoBD-Konzept (geplant)

| Anforderung | Geplante Umsetzung |
|-------------|-------------------|
| Unveränderlichkeit | `gesperrt`-Flag nach Monatsabschluss |
| Nachvollziehbarkeit | `erstellt_von`, `erstellt_am` (Frappe-Standard) |
| Vollständigkeit | Monatsabschluss-Mechanismus |
| Nachweis | SHA-256 Hash je Buchung; Hash-Chain über Abschlüsse |
| Aufbewahrung | Buchungen verbleiben dauerhaft in der Datenbank |

---

## Hinweise

**GoBD:** Die technische Implementierung allein stellt keine GoBD-Konformität sicher. Die Verantwortung für ordnungsgemäße Buchführung liegt bei der Gemeinde. Vor Produktiveinsatz ist eine Steuerberater-Prüfung erforderlich.

**Spendenbescheinigungen:** Nur für als gemeinnützig anerkannte Körperschaften rechtlich zulässig. Das amtliche Muster des Bundesfinanzministeriums kann sich ändern — die Gemeinde ist für Aktualität verantwortlich.

**CAMT.053:** XML-basiertes Kontoauszugsformat nach ISO 20022, von deutschen Banken unterstützt.

**Geltungsbereich:** Dieses Modul richtet sich an Vereine und Körperschaften mit EÜR. Nicht geeignet für bilanzpflichtige Körperschaften (HGB, doppelte Buchführung).

Geplante Umsetzung: nach Abschluss von Diakonos-Kern und Psalmos, erst nach externer steuerrechtlicher Prüfung.
