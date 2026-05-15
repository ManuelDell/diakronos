# Psalmos – Technische Dokumentation

→ [Zurück zur Übersicht](../README.md)

> Modul geplant – noch nicht begonnen

---

## Aktueller Stand

Von Psalmos existiert ausschließlich das Python-Paket-Verzeichnis:

```
diakronos/psalmos/
  __init__.py    # leer
  doctype/       # leer
```

Kein Doctype, keine API, keine Frontend-Seite ist vorhanden. Das Modul ist ein Platzhalter.

In `hooks.py` ist die Rolle `Psalmos-Nutzer` als Fixture definiert — die Rolle wird bereits beim App-Install angelegt, aber noch nirgends geprüft.

---

## Geplanter Zweck

Psalmos soll die Liedverwaltung und Gottesdienst-Planung der Gemeinde abdecken:

- Lied-Datenbank mit OpenLyrics-XML-Speicherung
- Gottesdienst-Ablaufpläne (verknüpft mit Kronos-Terminen)
- Import aus OpenLP (ODS-Format)
- Export nach OpenLyrics (kompatibel mit OpenLP, EasyWorship)
- CCLI-Nummern-Tracking für Lizenzreporting

---

## Geplante Architektur

```
psalmos/
  doctype/
    lied/                   # Lied (Metadaten + OpenLyrics XML)
    lied_vers/              # Child-Table: Strophen (für Beamer-Ausgabe)
    gottesdienst_ablauf/    # Ablaufplan (Datum, Titel, Kronos-Verknüpfung)
    ablauf_position/        # Child-Table: Position (Lied / Ankündigung / Gebet / Pause)
  api/
    lied_api.py             # CRUD, Suche
    ablauf_api.py           # Ablaufplan verwalten
    openlyrics_parser.py    # OpenLyrics XML → Frappe-Felder
    openlyrics_exporter.py  # Frappe-Felder → OpenLyrics XML
    openLP_importer.py      # OpenLP ODS → Lied-DocTypes
    songbeamer_exporter.py  # Lied → SongBeamer .sng (Format nicht offiziell dokumentiert)
  www/
    psalmos/                # Lied-SPA + Ablaufplaner (Vue)
```

---

## Was fehlt um Psalmos zu starten

1. Doctypes anlegen: `Lied`, `Lied_Vers`, `GottesdienstAblauf`, `Ablauf_Position`
2. API-Dateien erstellen (mind. `lied_api.py`, `ablauf_api.py`)
3. Whitelist-Einträge in `hooks.py` ergänzen
4. Frontend-Seiten in der Diakonos-SPA oder eigene SPA anlegen
5. `Psalmos-Nutzer`-Rolle mit tatsächlichen Berechtigungen verbinden
6. Fixture-Workspace für das Psalmos-Modul erstellen

---

## Hinweise

**OpenLyrics:** Standardformat für Liedtexte (XML-basiert, open-source). Unterstützt von OpenLP, EasyWorship und anderen Beamer-Programmen.

**SongBeamer:** Proprietäres Format, nur teilweise rekonstruiert. Export ohne Vollständigkeitsgarantie.

**CCLI:** Das Feld `ccli_nummer` dient der Nachverfolgung genutzter Lieder. Die rechtliche Pflicht zur CCLI-Berichterstattung liegt bei der Gemeinde.

Geplante Umsetzung: nach Abschluss der Diakonos-Kernfunktionen.
