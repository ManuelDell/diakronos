# Diakonos – Technische Dokumentation

→ [Zurück zur Übersicht](../README.md)

---

## Überblick

Diakonos ist das Community-Management-Modul von Diakronos. Es verwaltet Mitglieder, Gruppen, Ressourcen, Beiträge, Wiki und das Registrierungssystem einer Kirchengemeinde. Die Oberfläche ist eine Vue 3 SPA unter `/diakonos`, die über eine Frappe-Whitelist-API kommuniziert.

---

## Architektur

```
diakonos/
  api/
    admin_hub.py             # Statistik-KPIs, Anmeldungsmanagement, DSGVO-Übersicht
    audit.py                 # Audit-Log-Abfragen
    audit_policy/
      engine.py              # Policy-Engine (Caching, Evaluation)
      anonymize.py           # Scheduler: tägliche Anonymisierung abgelaufener Logs
    beitraege.py             # CRUD Beiträge + Kommentare
    cleanup.py               # Scheduler: tägliches Löschen alter Anmeldeanfragen
    dashboard.py             # Dashboard-Widget-Daten
    dienstplan.py            # Dienstplan-Abfragen (auf Anmeldung-DocType gemappt)
    dsgvo_export.py          # Personendaten-Export nach Art. 20 DSGVO
    gruppen.py               # Gruppen-Hierarchie, CRUD, Organigramm-Daten
    kalender.py              # Kalenderansicht (SPA-seitig, Diakonos-Events)
    mitglieder.py            # CRUD Mitglieder, Adressbuch, Beziehungen
    nutzer.py                # Nutzerverwaltung
    orgchart_api.py          # Organigramm-Aufbereitung
    profile.py               # Eigenes Profil (lesen/bearbeiten/löschen)
    registrierung.py         # Token-Validierung, Registrierungsformular absenden
    registrierungslink_api.py# Verwaltung von Registrierungslinks
    ressourcen.py            # Ressourcen (Räume/Geräte) + Buchungen
    session.py               # Session-Kontext, Rechteprüfung per Pfad
    veranstaltungsanmeldung.py# Ein-Klick-Anmeldung zu Veranstaltungen
    wiki.py                  # CRUD Wiki-Artikel, Kategorien, Tags
    zugriff.py               # Zugriffskontrolle (Hilfsfunktionen)
  doctype/
    anmeldeformular/         # Konfiguration von Anmeldeformularen
    anmeldeformular_dokument/ # Gespeicherte Formular-Instanzen
    anmeldeformular_feld/    # Child-Table: Felder eines Formulars
    anmeldung/               # Anmeldung zu Veranstaltung (auch Basis für Dienstplan)
    anmeldung_antwort/       # Child-Table: Antworten auf Formularfelder
    anmeldung_kind/          # Child-Table: Kinder bei Anmeldung
    audit_log/               # Unveränderlicher Audit-Trail
    audit_policy/            # Konfigurierbare Audit-Richtlinien
    beitrag/                 # Gemeinde-Beiträge (Neuigkeiten, Ankündigungen)
    beitrag_kommentar/       # Child-Table: Kommentare zu Beiträgen
    dashboard_widget/        # Dashboard-Widget-Definition
    dashboard_widget_user_config/ # Nutzer-spezifische Widget-Konfiguration
    dienstbereich/           # Oberkategorie der Gruppen-Hierarchie
    dienstbereich_verantwortlicher/ # Child-Table: Verantwortliche eines Dienstbereichs
    dienstrolle/             # Rollen-Definition für Dienste
    dsgvo_einwilligung/      # DSGVO-Einwilligungs-DocType
    gruppe/                  # Gruppe (unterhalb Dienstbereich)
    gruppe_verantwortlicher/ # Child-Table: Verantwortliche einer Gruppe
    gruppenmitgliedschaft/   # Mitgliedschaft in einer Gruppe
    gruppenrolle/            # Konfigurierbarer Rollen-Katalog für Gruppen
    gruppentyp/              # Gruppen-Typkonfiguration
    mitglied/                # Mitglieds-DocType (Kerndaten)
    mitglied_bereich/        # Child-Table: Dienstbereichszugehörigkeit
    mitglied_beziehung/      # Beziehungen zwischen Mitgliedern (Familie etc.)
    mitglied_tag/            # Tags für Mitglieder
    registrierungslink/      # Zeitlich begrenzter Link zur Selbstregistrierung
    ressourcen_buchung/      # Buchung einer Ressource (Raum/Gerät)
    sicherer_anhang/         # Zugriffsgeschützter Datei-Anhang
    untergruppe/             # Untergruppe (unterhalb Gruppe)
    untergruppe_verantwortlicher/ # Child-Table: Verantwortliche einer Untergruppe
    untergruppenmitgliedschaft/   # Mitgliedschaft in einer Untergruppe
    wiki_artikel/            # Wiki-Artikel-DocType
```

### Frontend (Vue 3 SPA, `/diakonos`)

```
frontend/src/diakonos/pages/
  Home.vue              # Startseite mit Widget-Dashboard
  Mitglieder.vue        # Mitgliederliste mit Filter/Suche
  MitgliedDetail.vue    # Mitglieds-Detailansicht (Profil, Gruppen, Beziehungen)
  Gruppen.vue           # Gruppen-Übersicht (Hierarchie: Dienstbereich → Gruppe → Untergruppe)
  GruppeDetail.vue      # Gruppen-Detailansicht mit Mitgliederliste
  Organigramm.vue       # Grafisches Organigramm
  Adressbuch.vue        # Adressbuch (sichtbarkeitsgesteuerter Zugriff)
  Ressourcen.vue        # Ressourcen-Übersicht + Buchungskalender
  Beitraege.vue         # Gemeinde-Beiträge (Neuigkeiten, Kommentare)
  Wiki.vue              # Wiki-Artikel (Kategorien, Tags, Volltext)
  Dienstplan.vue        # Dienstplan-Ansicht (basiert auf Anmeldung-Docs)
  Kalender.vue          # Kalenderansicht (Diakonos-Events, SPA-seitig)
  Statistik.vue         # KPI-Dashboard (nur Admin, 4 Kennzahlen)
  Profile.vue           # Eigenes Profil (bearbeiten, Foto, Datenlöschung)
  Registrierung.vue     # Öffentliche Registrierungsseite (Token-basiert)
  Dsgvo.vue             # DSGVO-Einwilligung (Übersicht, Widerruf)
```

---

## Rollen-System

### Frappe-Rollen

| Rolle | Zweck |
|-------|-------|
| `Mitglied` | Zugang zur Diakonos-SPA |
| `Mitgliederadministrator` | Vollzugriff auf Mitglieder, Admin-Hub, Registrierung |
| `Kalenderadministrator` | Vollzugriff auf Kronos-Kalender |
| `Psalmos-Nutzer` | Zukünftig für Psalmos-Modul vorgesehen |

### ADMIN_ROLES in der API

`ADMIN_ROLES = ["System Manager", "Mitgliederadministrator"]`

Diese Konstante wird in `mitglieder.py`, `session.py`, `gruppen.py` und `admin_hub.py` geprüft, um Admin-Operationen (Mitglied anlegen/bearbeiten, Admin-Hub, DSGVO-Export) zu schützen.

### Mitglied-Status

Das `Mitglied`-DocType kennt vier Status-Werte:

| Status | Bedeutung |
|--------|-----------|
| `Mitglied` | Vollmitglied der Gemeinde |
| `Gast` | Gast mit aktivem Bezug zur Gemeinde |
| `Passives Mitglied` | Mitglied ohne aktive Teilnahme |
| `Passiver Gast` | Gast ohne aktive Teilnahme |

Standard bei Neuanlage via `create_mitglied()`: `Gast`.

---

## Registrierungsflow

```
Admin erstellt Registrierungslink (optional: Anmeldeformular, Ablaufdatum, max. Anmeldungen)
       │
       ↓
Interessent ruft /diakonos/registrierung?token=<token> auf
       │
registrierung.py: validate_token() → prüft Gültigkeit, Ablauf, Kapazität
       │
       ├── Token ungültig → Fehlermeldung
       └── Token gültig →
             submit_registrierung() → erstellt Anmeldung (Status: Anmeldeanfrage)
             oder submit_gast() → vereinfachter Gast-Flow (nur Name)
                    │
                    ↓
             Admin sieht Anmeldung im Admin-Hub
             admin_hub.genehmige_anmeldung() → Status: Bestätigt
               → on_update() erstellt Mitglied + DSGVO-Einwilligung + Frappe-User
             admin_hub.lehne_anmeldung_ab() → Status: Abgelehnt
```

---

## Gruppen-Hierarchie

```
Dienstbereich          (oberste Ebene, z. B. "Musik", "Jugend")
  └── Gruppe           (mittlere Ebene, z. B. "Lobpreisband")
        └── Untergruppe (unterste Ebene, z. B. "Gitarren-Section")
```

Mitgliedschaften existieren als eigene DocTypes (`Gruppenmitgliedschaft`, `Untergruppenmitgliedschaft`).
Pfad-basierte Zugriffskontrolle: `session.py` prüft über `ancestor_path`-Felder ob ein Nutzer lesenden/schreibenden Zugriff auf ein Mitglied hat.

---

## Audit-Log-System

- Jede sicherheitsrelevante Aktion schreibt einen `Audit Log`-Eintrag (unveränderlich per `doc_events`)
- `Audit Policy`-DocType konfiguriert welche Aktionen protokolliert werden (gecacht via `engine.py`, TTL 60 Sek.)
- Täglicher Scheduler-Job (`anonymize.py`): abgelaufene Logs werden anonymisiert, nicht gelöscht

---

## Scheduler-Jobs

| Job | Frequenz | Funktion |
|-----|----------|----------|
| `audit_policy.anonymize.anonymize_expired_audit_logs` | täglich | Anonymisiert Audit-Logs nach Ablauf der Aufbewahrungsfrist |
| `cleanup.delete_alte_anmeldeanfragen` | täglich | Löscht alte, nicht genehmigten Anmeldeanfragen |

---

## Eingeschränkt implementierte Features

### Dienstplan

Die Seite `Dienstplan.vue` existiert und zeigt Daten an. Die API (`dienstplan.py`) ist implementiert.
Es gibt jedoch **keinen eigenständigen Dienstplan-DocType** — die API mappt direkt auf den `Anmeldung`-DocType und filtert nach Datum. Der Dienstplan ist damit eine gefilterte Anmeldungs-Ansicht ohne eigenes Datenmodell.

### Statistik

`Statistik.vue` zeigt 4 KPI-Kennzahlen (Mitglieder, Gruppen, Anmeldungen, DSGVO-Einwilligungen) aus `admin_hub.get_statistik()`. Kein Dashboard-Framework, keine historischen Verläufe, keine Charts.

---

## Sicherheit

- Alle API-Endpunkte: `@frappe.whitelist(allow_guest=False)` (außer `registrierung.py`: öffentlich per Token)
- Admin-Operationen prüfen `ADMIN_ROLES` serverseitig
- Pfad-basierte Sichtbarkeit: Mitglieder sehen nur Mitglieder im eigenen Gruppen-Pfad (nicht global)
- DSGVO-Einwilligungen werden beim Widerruf eingefroren (kein Hard-Delete)
- Registrierungstoken sind zeitlich und kapazitiv begrenzt

---

## Abhängigkeiten (keine externen Python-Pakete)

Diakonos nutzt ausschließlich Frappe-Boardmittel und Standard-Python. Keine zusätzlichen `pip`-Abhängigkeiten.

---

## Login-Redirect

```python
get_website_user_home_page = "diakronos.auth.get_home_page"
```

Admins (System Manager) werden zu `/app` weitergeleitet, alle anderen zu `/diakonos`.
