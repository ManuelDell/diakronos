# Psalmos – Technische Dokumentation

→ [Zurück zur Übersicht](../README.md)

> 📋 Modul geplant – Umsetzung nach Diakonos

---

## Geplante Architektur

```
psalmos/
  doctype/
    lied/                   # Lied-DocType (Metadaten + OpenLyrics XML)
    lied_vers/              # Child-Table: Strophen (optional, alternativ zu XML-Only)
    gottesdienst_ablauf/    # Ablaufplan-DocType
    ablauf_position/        # Child-Table: Position im Ablauf (Lied, Ankündigung, Gebet...)
  api/
    lied_api.py             # CRUD, Suche, Import
    ablauf_api.py           # Ablaufplan verwalten
    openlyrics_parser.py    # OpenLyrics XML → Frappe-Felder
    openlyrics_exporter.py  # Frappe-Felder → OpenLyrics XML
    openLP_importer.py      # OpenLP ODS-Datenbankformat → Lied-DocTypes
    songbeamer_exporter.py  # Lied → SongBeamer .sng (soweit rekonstruierbar)
  www/
    psalmos/                # Lied-SPA + Ablaufplaner
```

---

## Datenbankmodell (Entwurf)

### `Lied`

| Feld | Typ | Beschreibung |
|------|-----|-------------|
| `titel` | Data | Liedtitel |
| `autor` | Data | Autor / Komponist |
| `ccli_nummer` | Data | CCLI-Liednummer (für Lizenzreporting) |
| `sprache` | Select | Sprache (DE, EN, ...) |
| `stichwoerter` | Tags | Themen / Tags |
| `tonart` | Data | Tonart (z. B. G-Dur) |
| `tempo` | Int | BPM (optional) |
| `openlyrics_xml` | Code | Vollständiges OpenLyrics XML (master copy) |
| `verse` | Table | Child-Table: Lied_Vers (flache Kopie für Suche/Anzeige) |
| `notizen` | Text | Interne Notizen |

### `GottesdienstAblauf`

| Feld | Typ | Beschreibung |
|------|-----|-------------|
| `datum` | Date | Gottesdienst-Datum |
| `titel` | Data | Bezeichnung (z. B. "Sonntagsgottesdienst KW 15") |
| `kronos_ereignis` | Link → KalenderEreignis | Verknüpfung mit Kalender-Termin |
| `positionen` | Table | Child-Table: Ablauf_Position |

### `Ablauf_Position`

| Feld | Beschreibung |
|------|-------------|
| `idx` | Reihenfolge (SortableJS-Drag-&-Drop steuert diesen Wert) |
| `typ` | Select: Lied / Ankündigung / Gebet / Pause / Sonstiges |
| `lied` | Link → Lied (nur wenn typ = Lied) |
| `bemerkung` | Data (für Ankündigungen etc.) |
| `dauer_minuten` | Int (optional) |

---

## XML-Strategie

Lieder werden im [OpenLyrics-Format](https://openlyrics.org) als vollständiges XML im `openlyrics_xml`-Feld gespeichert. Zusätzlich werden Metadaten (Titel, CCLI, Autor) in flachen Feldern gespiegelt, damit Frappe-Suche und Berichte funktionieren ohne XML parsen zu müssen.

**Vorteile dieses Ansatzes:**
- Volle OpenLyrics-Kompatibilität (kein Datenverlust bei Import/Export)
- Frappe-Felder für Suche und Berichte nutzbar
- Einzelne Verse als Child-Table für Beamer-Ausgabe extrahierbar

---

## Import / Export

### OpenLP-Import
OpenLP speichert seine Datenbank als ODS-Datei (OpenDocument Spreadsheet). Der Importer liest diese Datei, extrahiert Lieder + Verse und erstellt `Lied`-DocTypes.

Geplante Bibliothek: `odfpy` (Python, LGPL)

### OpenLyrics-Export
Lied → vollständiges OpenLyrics-XML exportieren. Dieses Format wird von OpenLP, EasyWorship und anderen Beamer-Programmen verstanden.

### SongBeamer-Export (.sng)
Das SongBeamer-Format ist proprietär und nur teilweise dokumentiert. Der Export ist geplant, aber in Umfang und Vollständigkeit vom rekonstruierbaren Format abhängig.

> ⚠️ SongBeamer-Export ohne Gewähr auf Vollständigkeit – Format nicht offiziell dokumentiert.

---

## CCLI-Hinweise

Das `ccli_nummer`-Feld dient der Nachverfolgung welche Lieder aus dem CCLI-Repertoire gespielt wurden. Bei Beamer-Ausgabe und Export wird ein Hinweis auf CCLI-Lizenzpflichten angezeigt.

**Diakronos übernimmt keine Lizenzreporting-Pflichten.** Die korrekte Berichterstattung an CCLI liegt in der Verantwortung der Gemeinde.

Eine direkte API-Anbindung an CCLI ist evaluiert aber noch nicht bestätigt (abhängig von API-Zugang und rechtlicher Klärung).

---

## Zusätzlich evaluiert (nicht bestätigt)

| Feature | Aufwand | Risiko | Status |
|---------|---------|--------|--------|
| Nextcloud WebDAV-Sync | Mittel | Hoch (bidirektionale Sync-Komplexität) | Evaluiert |
| Mobile PWA für Worship-Leiter | Mittel | Mittel (Offline-State-Sync) | Evaluiert |
| CCLI API-Reporting | Mittel | Hoch (Rechtsprüfung + API-Zugang nötig) | Evaluiert |
