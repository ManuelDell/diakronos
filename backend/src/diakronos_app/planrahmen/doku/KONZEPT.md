# Plan-Rahmen — Konzept v0.1 (Entwurf, 2026-10-07)

Grundlage: `planrahmen-entscheidungen.md`. Ziel: **wenige Grundbausteine, frei kombinierbar**, mit denen
Menschen und KI-Agenten beliebig komplexe, individuelle Pläne bauen — ohne neuen Code pro Planart.
Chorplan und Freizeitplan sind nur **Beispiele**, nicht eingebaute Sonderfälle.

---

## Teil A — Prinzipien

**P1 Komposition statt Planarten.** Es gibt keinen „Chorplan-Code“. Es gibt Bausteine (Termine, Felder,
Rollen, Sammlungen, Merkmale, Regeln, Ansichten), die sich beliebig verschachteln. Ein neuer Plan ist
eine neue Kombination, keine neue Funktion.

**P2 Struktur, Daten und Darstellung sind getrennt.** Der *Plantyp* beschreibt die Struktur, der *Plan*
enthält die Einträge, die *Ansicht* bestimmt das Aussehen. Wer die Darstellung ändert, zerstört keine
Daten (Excel-Lehre: Spalten verschieben brach die Formeln).

**P3 Alles hat einen Namen, nichts eine Position.** Felder, Personen und Lieder werden über stabile IDs
angesprochen, nie über „Spalte K“ oder „Blatt 2021“. Personen und Lieder sind Datensätze, kein Freitext
(Excel-Lehre: TIN/TINA/Tin, hart verdrahtete Jahresblätter).

**P4 Versioniert, die Vergangenheit bleibt, wie sie war.** Jede Änderung am Plantyp ist eine neue Version mit
`gueltig_ab`. Bereits vergangene Termine behalten ihre Struktur. Jede Änderung an Einträgen ist
rückgängig zu machen (Undo + Verlauf).

**P5 Wer plant, erklärt, was er braucht.** Ein Plantyp *deklariert* seine Datenbedürfnisse (Merkmale wie
„spielt Klavier“). Das Programm prüft, ob die Daten da sind, und fragt: *jetzt einrichten oder
überspringen?* Fehlende Daten blockieren nie, sie machen den Plan nur weniger automatisch.

**P6 Die Maschine schlägt vor, der Mensch entscheidet.** Der Generator füllt Entwürfe, jeder Wert ist
überschreibbar. Von Hand gesetzte Werte werden **fixiert** und überleben jede Neugenerierung.

**P7 Regeln sind Bausteine mit Stufe.** `muss` (wird nie verletzt), `sollte` (wird möglichst erfüllt,
Verstoß sichtbar), `hinweis` (nur anzeigen). Regelverstöße erscheinen als verständliche Meldung am
Eintrag („Lied zuletzt vor 3 Wochen gesungen“), nicht als Fehler.

**P8 Ohne KI lauffähig.** Die KI ist *Autorin* von Plantyp-Dateien und Importen, nie Laufzeitabhängigkeit.
Generator, Regeln, Ansichten und Formular-Editor laufen rein im Programm.

**P9 Der Dienst bleibt bei den Menschen.** Personen können sich eintragen, tauschen, absagen, Abwesenheiten
melden. Der Rahmen organisiert Dienst, er ersetzt ihn nicht.

**P10 Gutmütig und erklärend.** Eine minimale Datei ist gültig, sinnvolle Vorgaben füllen den Rest. Jede
Ablehnung nennt Pfad, Grund und Beispiel, damit ein Agent (oder Mensch) sich im nächsten Versuch
korrigiert.

**P11 Erweiterbar ohne Bruch.** Neue Feldarten und Regelbausteine kommen per Code + Doku hinzu. Das Schema
trägt eine Versionsnummer, alte Plantypen bleiben gültig.

**P12 Die Dokumentation ist Teil des Produkts.** Schema, Referenz und Beispiele kommen aus *einer* Quelle (siehe
Teil E). Was nicht dokumentiert ist, existiert für den Agenten nicht.

---

## Teil B — Die Bausteine

### B1 Plantyp und Plan
- **Plantyp** = wiederverwendbare Vorlage (JSON). Kann **Parameter** deklarieren, die erst der konkrete
  Plan füllt (Zeitraum, Thema, Themenreihe, Teilnehmerkreis).
- **Plan** = Instanz eines Plantyps für einen Zeitraum („Chorplan 2026“, „Freizeit Musterstadt Herbst 2026“).
  Hält Parameterwerte, Termine, Einträge, Status (Entwurf → veröffentlicht) und Verlauf.

### B2 Termine (die Zeitachse)
Woher kommen die Zeilen des Plans? Quellen sind kombinierbar:
- `regel` — Wiederholung im iCalendar-RRULE-Format (`FREQ=WEEKLY;BYDAY=SU`).
- `zeitraum` — jeder Tag (oder bestimmte Wochentage) zwischen zwei Daten (Freizeit).
- `kalender` — Termine aus Kronos nach Kategorie/Gruppe (Gottesdienste, Proben).
- `feiertage` — benannte Feiertage (Karfreitag, Himmelfahrt, Heiligabend …), beweglich berechnet.
- `manuell` — einzelne Termine von Hand.
Dazu `ausnahmen` (Termin entfällt) und **Anlässe** (siehe B6).

### B3 Felder (was pro Termin geplant wird) — rekursiv
Ein Feld hat eine `art`, optional `anzahl` (fest oder `"min..max"`), `pflicht`, `zeit`, `bedingung`.

| art | bedeutet | Beispiel |
|---|---|---|
| `person` / `personen` | eine/mehrere Personen in einer **Rolle** | Einsingen, Tagesleitung |
| `eintrag` | Element aus einer **Sammlung** | Lied, Bibelarbeit, Spiel |
| `text`, `zahl`, `datum`, `auswahl` | freie Angaben | Thema, Bibelstelle, Raum |
| `gruppe` | enthält Unterfelder (`inhalt`) | „Frohe Stunde 10:30–12:00“ |

Eine `gruppe` kann zusätzlich **Varianten** haben (`sonne`/`regen`: es gilt *eine*, beide werden geplant)
und **Teile** (`programm`, `abschluss`: nacheinander). Weil Gruppen beliebig tief schachteln, entstehen
damit Raster (Tag × Block), Listen (Termin × Lieder) oder Abläufe (Gottesdienst-Ablauf) aus *demselben*
Baustein. Ein `eintrag` kann eigene Unterfelder tragen (Lied → Dirigent, Klavier, Solo).

### B4 Rollen (wer kommt in Frage)
Eine Rolle ist ein **Filter** über Personen, keine feste Liste:
```json
{ "alle": [ { "merkmal": "klavier" }, { "gruppe": "Chor" } ] }
{ "anmeldung": "mitarbeiter" }          // angemeldete Mitarbeiter der Veranstaltung
{ "eine": [ { "merkmal": "prediger" }, { "person": "gast" } ] }
```
Bausteine: `merkmal`, `gruppe`, `anmeldung`, `person`, `alle` (UND), `eine` (ODER), `nicht`.

### B5 Sammlungen und Merkmale (die „Stammdaten des Plans“)
- **Sammlung** = beliebige Liste von Dingen: Lieder (eingebaut, = Psalmos), Bibelarbeiten, Spiele,
  Predigtreihen, Räume. Eigene Sammlungen definiert der Plantyp.
- **Merkmal** = deklarierte Eigenschaft einer Person oder eines Sammlungseintrags: `tag` (ja/nein, „spielt
  Klavier“), `auswahl` (Stimme: Sopran/Alt/…), `text`, `zahl`, `person` (Lied → Standard-Dirigent).
- Merkmale haben einen **Schlüssel**, der über Pläne hinweg wiederverwendet wird: legt der Musikerplan
  `klavier` an, sieht der Chorplan dieselben Daten. Wer einen Plantyp anlegt, bekommt vorhandene Merkmale
  vorgeschlagen, bevor neue entstehen.
- **Pflege im Planer**, nicht beim Admin: wer einen Plan verantwortet, pflegt die Merkmale und Sammlungen,
  die sein Plan braucht (Matrix Personen × Merkmale, Tabelle der Sammlung).

**Bedarfsprüfung (P5):** Beim Anlegen oder Generieren berechnet das Programm, welche Merkmale die Rollen,
Vorbelegungen und Regeln benutzen, und prüft die Abdeckung („0 Personen mit *klavier*“, „120 von 371
Liedern ohne Dirigent“). Danach fragt es: **[Jetzt einrichten] [Überspringen]**. Überspringen heißt: das
Feld bleibt leer oder wird nur von Hand gefüllt, mit Hinweis.

### B6 Anlässe
Markierungen an Terminen (Abendmahl, Kinderchor, Taufe, Erntedank, Freizeit). Sie können **wirken**:
Felder ausblenden (`Kinderchor` → kein Chor), Felder hinzufügen, Regeln steuern (Lied passend zum
Anlass). Kommen manuell, aus dem Kalender oder aus Feiertagen.

### B7 Füllstrategien (wie der Generator ein Feld befüllt)
| strategie | Wirkung | Beispiel |
|---|---|---|
| `manuell` | nie automatisch | Lieder, die neu eingeübt werden |
| `reihum` | Personen der Rolle der Reihe nach, Abwesende überspringen | Einsingen, Tagesleitung |
| `der_reihe_nach` | Sammlungseinträge in ihrer Reihenfolge | Bibelarbeit Tag 1…n |
| `vorbelegen` | Wert aus einem anderen Feld/Merkmal übernehmen | Lied → Dirigent + Klavier |
| `optimieren` | bestmögliche Wahl nach allen Regeln (Standard) | Liedauswahl, Prediger |

### B8 Regeln (Bausteine mit Parametern und Stufe)
Startkatalog (erweiterbar, P11):

| baustein | Parameter | Beispiel |
|---|---|---|
| `abwesenheit_beachten` | — | Urlaub, „abgemeldet“ |
| `mindestabstand` | feld, Zeitraum, für eintrag/person | Lied nicht öfter als alle 8 Wochen |
| `max_pro_zeitraum` / `min_pro_zeitraum` | person/rolle, Anzahl, Zeitraum | max. 2 Predigten/Monat |
| `gleich_verteilen` | rolle | Fairness über alle Mitarbeiter |
| `nicht_gleichzeitig` | felder | nicht dirigieren und Klavier zugleich |
| `zusammen` / `nicht_zusammen` | personen | Ehepaar zusammen einteilen |
| `vorher_geuebt` | feld, übungsfeld, Anzahl | Lied erst nach 2× Einüben singen |
| `passend_zum_anlass` | feld, merkmal | Erntedank-Lied an Erntedank |
| `verfuegbarkeit` | person, Muster | „nur 1. Sonntag im Monat“ |

Jede Regel: `stufe` (`muss`/`sollte`/`hinweis`), optional `gewicht`. **Für später** (offen): eine sichere
Ausdruckssprache (z. B. JSONLogic) als Ausweg für Sonderregeln, die kein Baustein abdeckt.

### B9 Ansichten und Ausgabe
- `tabelle` (Termin × Felder: der Chorplan), `raster` (Tag × Block mit Karten: Musterstadt), `ablauf` (ein
  Termin als Liste), `meine_dienste` (Personensicht), `druck` (A4 hoch/quer), `ical` (Export).
- **Formatvorlagen** für Zellen: `"{eintrag.buch} Nr.{eintrag.nr} /{dirigent.kuerzel}/{klavier.kuerzel}/ {eintrag.titel}"`.
- Mehrere Ansichten pro Plantyp (Aushang, Chorleiter, Beamer).

### B10 Lebenszyklus
Entwurf → (generieren, beliebig oft; fixierte Werte bleiben) → veröffentlicht → Änderungen erzeugen
sichtbaren Diff + Benachrichtigung der Betroffenen. Undo über den Verlauf. Plantyp-Änderung = neue
Version mit `gueltig_ab`, Termine davor bleiben auf der alten Version.

---

## Teil C — Beispiele (Skizze, Syntax noch nicht final)

### C1 Chorplan
```json
{
  "schema": "diakronos/plantyp@1",
  "id": "chorplan", "name": "Chorplan", "bereich": "Chor",
  "merkmale": {
    "person":  [ { "id": "dirigent",  "art": "tag", "name": "dirigiert" },
                 { "id": "klavier",   "art": "tag", "name": "spielt Klavier" },
                 { "id": "einsingen", "art": "tag", "name": "leitet Einsingen" },
                 { "id": "instrument","art": "auswahl", "mehrfach": true, "werte": ["Flöte","Geige","Gitarre"] } ],
    "lieder":  [ { "id": "dirigent", "art": "person", "rolle": { "merkmal": "dirigent" } },
                 { "id": "klavier",  "art": "person", "rolle": { "merkmal": "klavier" } },
                 { "id": "thema",    "art": "auswahl", "mehrfach": true } ]
  },
  "termine": { "regel": "FREQ=WEEKLY;BYDAY=SU",
               "feiertage": ["karfreitag","ostersonntag","himmelfahrt","pfingstsonntag","heiligabend","1_weihnachtstag"] },
  "anlaesse": [ { "id": "kinderchor", "wirkung": { "ohne": ["lieder","einsingen","einueben"] } },
                { "id": "freizeit",   "wirkung": { "ohne": ["lieder","einueben"] } },
                { "id": "abendmahl" }, { "id": "erntedank" } ],
  "felder": [
    { "id": "lieder", "name": "Lied", "art": "eintrag", "sammlung": "lieder", "anzahl": 3,
      "inhalt": [
        { "id": "dirigent", "art": "person",   "rolle": { "merkmal": "dirigent" }, "fuellen": "vorbelegen", "aus": "eintrag.dirigent" },
        { "id": "klavier",  "art": "person",   "rolle": { "merkmal": "klavier" },  "fuellen": "vorbelegen", "aus": "eintrag.klavier" },
        { "id": "solo",     "art": "personen", "pflicht": false, "fuellen": "manuell" } ] },
    { "id": "einsingen", "art": "person", "rolle": { "merkmal": "einsingen" }, "fuellen": "reihum" },
    { "id": "einueben",  "name": "Wiederholen/Einüben", "art": "eintrag", "sammlung": "lieder", "anzahl": "0..2" }
  ],
  "regeln": [
    { "baustein": "abwesenheit_beachten", "stufe": "muss" },
    { "baustein": "mindestabstand", "feld": "lieder", "wochen": 8, "stufe": "sollte" },
    { "baustein": "vorher_geuebt",  "feld": "lieder", "uebungsfeld": "einueben", "mindestens": 2, "stufe": "sollte" },
    { "baustein": "passend_zum_anlass", "feld": "lieder", "merkmal": "thema", "stufe": "sollte" }
  ],
  "ansichten": [ { "art": "tabelle", "spalten": ["anlass","lieder","einueben","einsingen"],
                   "format": { "lieder": "{eintrag.buch} Nr.{eintrag.nr} /{dirigent.kuerzel}/{klavier.kuerzel}/ {eintrag.titel}" } } ]
}
```

### C2 Freizeitplan
```json
{
  "schema": "diakronos/plantyp@1",
  "id": "freizeit", "name": "Freizeitplan",
  "parameter": [ { "id": "zeitraum", "art": "zeitraum" }, { "id": "thema", "art": "text" },
                 { "id": "bibelarbeiten", "art": "sammlung", "name": "Themenreihe" } ],
  "termine": { "zeitraum": "{parameter.zeitraum}" },
  "felder": [
    { "id": "tagesleitung", "art": "person", "rolle": { "anmeldung": "mitarbeiter" }, "fuellen": "reihum" },
    { "id": "bibelfreude",  "art": "gruppe", "zeit": "08:00-08:30",
      "inhalt": [ { "id": "leitung", "art": "personen", "rolle": { "anmeldung": "mitarbeiter" } } ] },
    { "id": "frohe_stunde", "art": "gruppe", "zeit": "10:30-12:00",
      "inhalt": [ { "id": "bibelarbeit", "art": "eintrag", "sammlung": "{parameter.bibelarbeiten}", "fuellen": "der_reihe_nach" },
                  { "id": "leitung", "art": "personen", "anzahl": "1..2", "rolle": { "anmeldung": "mitarbeiter" } } ] },
    { "id": "nachmittag", "art": "gruppe", "zeit": "14:30-17:30", "varianten": ["sonne","regen"],
      "inhalt": [ { "id": "programm", "art": "text" }, { "id": "leitung", "art": "personen", "rolle": { "anmeldung": "mitarbeiter" } } ] },
    { "id": "abend", "art": "gruppe", "zeit": "19:30-22:00", "varianten": ["sonne","regen"], "teile": ["programm","abschluss"],
      "inhalt": [ { "id": "programm", "art": "text" }, { "id": "leitung", "art": "personen", "rolle": { "anmeldung": "mitarbeiter" } } ] }
  ],
  "regeln": [ { "baustein": "gleich_verteilen", "rolle": { "anmeldung": "mitarbeiter" }, "stufe": "sollte" },
              { "baustein": "max_pro_zeitraum", "anzahl": 2, "zeitraum": "termin", "stufe": "sollte" } ],
  "ansichten": [ { "art": "raster", "zeilen": "termin", "spalten": "felder", "druck": "A4-quer" } ]
}
```

Weitere Kochbuch-Beispiele für die Doku: Predigerplan (Gastprediger, max/Monat, Predigtreihe),
Musikerplan (Band-Besetzung mit Pflicht-Instrumenten), Kindergottesdienst (Altersgruppen als Varianten),
Technik/Beamer, Putz- und Hausmeisterplan, Begrüßungsdienst.

### C3 Musikteam-Plan (erfundenes Beispiel, Musterhausen, Q4 2026)
Aushang Q4/2026: drei Monatsspalten, jeder Tag eine Zeile, KW am Montag. Sonntags spielt ein **ganzes
Team** („Gruppe 3“), optional mit Gast („+ Gast“); freitags davor proben die **Sänger desselben Teams**.
Gruppe 3 liegt auf jedem 1. Sonntag (= Abendmahl) und an Heiligabend, die übrigen Sonntage rotieren
1/2/4 mit Handkorrekturen. Ein **Monatslied** wird am 2. Sonntag eingeführt (Dez.: „Wiederholung neue
Lieder“). Feiertags-Gottesdienste (24./25./31.12.) haben keine Probe; die Probe am 25.12. entfällt.
(Ein vollständiges, geprüftes Beispiel liegt unter `kochbuch/musikteams.json`.)

**Was C3 neu verlangt:**
1. **Mehrere Terminreihen pro Plantyp** (`terminreihen`), jede mit eigenen Feldern. Bisher kennt der
   Plantyp nur *eine* Zeitachse.
2. **Abgeleitete Termine** (B2 `abgeleitet`): Termin relativ zu einem anderen (`versatz`), mit `bezug`
   auf den Ursprungstermin; `vorbelegen` darf aus `bezug.*` lesen. Ändert sich der Gottesdienst-Eintrag,
   zieht die Probe nach.
3. **Feldart `team`**: Ein Wert ist eine *Gruppe von Personen* (Diakonos-Gruppe), nicht eine Person.
   Name bewusst nicht `gruppe`, das ist in B3 schon der Container. `mitglieder` filtert eine Teilmenge
   (Sänger des Teams). Abwesenheit: Team gilt als verfügbar, solange Pflicht-Mitglieder da sind (offen).
4. **Bedingung `termin_im_monat`** (n-ter Termin der Reihe im Monat), auch als Muster in `verfuegbarkeit`;
   `verfuegbarkeit` gilt für Personen **und Teams**.
5. **Feiertag `silvester`** (fester Termin) in die Feiertagsliste; Anlass `feiertag` als Sammelanlass.
6. **Ansicht `kalender`**: Monatsspalten, alle Tage inkl. leerer, KW-Spalte. Das ist der klassische
   Gemeinde-Aushang und neben `tabelle`/`raster` die dritte Grundform.
7. **Format-Platzhalter mit Bedingung** (`{gaeste: + …}` nur wenn gesetzt), sonst entstehen leere „+“.
8. **Onboarding-Falle:** am 4.12. steht „Sänger Gruppe“ **ohne Nummer**. Aus dem Gottesdienst am 6.12.
   (Gruppe 3) ist sie ableitbar; der Import soll so etwas erkennen und nachfragen, nicht raten.
9. **Offene Fragen (Onboarding-Fragenkatalog):** Ist „Gruppe 3 = 1. Sonntag“ eine feste Regel
   oder Zufall? Warum steht am 8.11. eine andere Gruppe als nach der Rotation zu erwarten (Wunsch,
   Abwesenheit)? Wer wählt das Monatslied, und gehört es auch in den Chorplan (gemeinsame Sammlung
   `lieder`)?

### C4 Programmablauf einer Veranstaltung (Beobachtung an zwei Beispiel-Programmen)
Ein Termin, ein **geordneter Ablauf aus gemischten Elementen**. Adventssingen: Lieder (nummeriert 1–9) mit
dazwischen **Szenen** eines Anspiels (nicht nummeriert) und einer **Predigt**. Weihnachtsmarkt: 13 Lieder
mit Spalten Heft | Lied | Dirigent/Klavier. Je Lied: Heft + Seite (`MB S. 150`, Seite teils fehlend),
**Ensemble** (Chor, Männerchor, Solo), **Begleitung** (Orchester, Gitarre, Violine), Personen
Dirigent/Klavier (teils drei: `Jo/Lea/Solo`, teils Ensemble statt Person: `Mir/Orch`). Kopf: Titel,
Datum/Uhrzeit, Motto, Untertitel; Fuß: Zitat bzw. Bibelvers. Beide Programme teilen Lieder **mit
identischer Besetzung** (bestätigt Vorbelegung aus dem Lied).

**Was C4 neu verlangt:**
1. **Feldart `ablauf`**: geordnete, frei sortierbare Liste **heterogener Elemente**; der Plantyp deklariert
   die erlaubten Elementtypen mit eigenem `inhalt`; `anzahl` mit offenem Ende (`1..*`). Nummerierung je
   Elementtyp (`nummeriert`), damit Szenen die Liednummern nicht verschieben. Vereinheitlicht den
   Gottesdienst-Ablaufplaner mit dem Rahmen.
2. **Planübergreifende Regeln/Bezüge**: Die Lieder des Programms müssen vorher im **Chorplan** geübt sein
   (`vorher_geuebt` mit `uebung: {plantyp, feld}`). Allgemein: Regeln und Vorbelegungen dürfen auf andere
   Pläne verweisen (Projekt: ein Programm, mehrere Auftritte, Proben im Chorplan).
3. **Ablauf übernehmen**: Ein Plan kann Einträge aus einem anderen Plan kopieren (Weihnachtsmarkt übernimmt
   Lieder des Adventssingens, inkl. Besetzung) und dann abweichen — Plantyp-Option `uebernahme`.
4. **Eingebaute Liedattribute** um `seite` (neben buch/nummer) erweitern; fehlende Seite ist erlaubt.
5. **Ansicht `programm`** (Programmheft/Liedzettel) mit `kopf`/`fuss` aus Plan-Parametern und Formaten je
   Elementtyp; vierte Grundform neben tabelle/raster/kalender.
6. **Personenfeld darf ein Ensemble statt einer Person enthalten** (`Mir/Orch`): Begleitung als Auswahl
   modellieren, nicht als Person erzwingen; Onboarding fragt bei solchen Kürzeln nach.

(Ein vollständiges, geprüftes Beispiel liegt unter `kochbuch/programm.json`; Instanzdaten von
Adventssingen und Weihnachtsmarkt unter `doku/instanzen/`.)

---

## Teil D — Onboarding (Agent) und Planer (ohne Agent)

**Agent (einmalig, optional später für Erweiterungen):**
1. Gemeinde lädt hoch: Excel, Fotos alter Pläne, PDFs, Mitgliederlisten.
2. **Stammdaten:** Personen, Gruppen, Kürzel abgleichen (TIN = TINA = Tina?), Rückfragen bei Unklarem.
3. **Pro Plan:** Agent erkennt Struktur → fragt gezielt nach (Fragenkatalog aus der Doku: „Wer wählt die
   Lieder? Gibt es feste Paare Lied–Dirigent? Was passiert an Abendmahl-Sonntagen?“) → schreibt Plantyp
   → **prüft** (Schema) → **Trockenlauf** (8 Wochen generieren, Konflikte ansehen) → zeigt Vorschau →
   Mensch bestätigt.
4. **Historie:** Gemeinde wählt, wie weit zurück importiert wird.
5. Merkmale, die der Agent nicht ermitteln kann, landen in der Bedarfsprüfung (B5), nicht im Admin.

**Agent-Werkzeuge (OpenAI-kompatibles Tool-Calling):** `doku_lesen`, `schema_holen`, `plantyp_pruefen`,
`trockenlauf`, `stammdaten_importieren`, `sammlung_importieren`, `historie_importieren`, `rueckfrage`.
Der Agent schreibt nichts direkt in die Datenbank: alles läuft über dieselben geprüften Wege wie das
Formular.

**Planer (Alltag, ohne KI):** Plantyp-Formular-Editor (P4-Versionen), Stammdaten des Plans (B5), Generator
mit Fixieren, Regelmeldungen, Undo, Veröffentlichen mit Diff, Selbsteintragung und Tausch (P9).

---

## Teil E — Dokumentation (eine Quelle, drei Leser)

1. **Das Schema ist die Referenz.** Jede Eigenschaft im JSON Schema hat `description` und `examples`. Daraus
   wird die Referenz-Doku **generiert**, damit Doku und Prüfung nie auseinanderlaufen.
2. **Leitfaden:** Teil A (Prinzipien) + B (Bausteine) in Prosa, mit „wann nehme ich was?“.
3. **Kochbuch:** vollständige, *geprüfte* Beispiele (C1, C2 + die Liste oben). Jedes Beispiel läuft in
   der Testsuite gegen Schema und Trockenlauf, damit kein Beispiel veraltet.
4. **Onboarding-Fragenkatalog** für den Agenten: welche Fragen bei welcher Planart, wie man Excel/Fotos
   liest, typische Fallen (Freitext-Kürzel, wandernde Spalten, kaputte Formeln).
5. **Fehlermeldungen sind Doku** (P10): Pfad, Grund, Verweis auf Referenz und Beispiel.

Leser: Agent (lädt alles als Kontext), Planer (Leitfaden + Kochbuch im Programm), Entwickler (Referenz +
„wie baue ich einen neuen Regelbaustein“).

---

## Präzisierungen aus Review PR1 (2026-10-08)
- **Bedingungen sind strukturiert**, gleiche Knoten-Grammatik wie Rollenfilter: `anlass`, `wochentag`,
  `variante`, `parameter`, `feld_gesetzt`, `datum_ab/bis`, `termin_nr`, verknüpft mit `alle`/`eine`/`nicht`.
  Kein freier Ausdrucks-String.
- **Varianten und Teile sind Objekte** `{id, name?, inhalt?, bedingung?}` (Kurzform String erlaubt). Ohne
  eigenes `inhalt` gilt das der Gruppe; mit eigenem ersetzt es dieses (Regen darf andere Felder haben).
- **Sammlungen haben einen Umfang:** `gemeinde` (dauerhaft, z. B. Lieder) oder `plan` (gehört zum
  einzelnen Plan, wird beim Vorbereiten befüllt, z. B. Themenreihe einer Freizeit).
- **Eingebaute Attribute** (Person: name, vorname, kuerzel …; Lied: titel, buch, nummer, ccli …; jede
  Sammlung: titel, reihenfolge) sind registriert; Formatvorlagen und Merkmale werden dagegen geprüft.
- Merkmal-Verweise ohne Deklaration im Plantyp sind **Warnung**, kein Fehler (Merkmale sind gemeindeweit).

## Offene Punkte (für später, nicht jetzt)
- Dürfen Personen eigene Merkmale selbst angeben („ich spiele Klavier“), mit Bestätigung durch den Planer?
- Ausdruckssprache als Ausweg für Sonderregeln (JSONLogic o. ä.): ab Version 1 oder später?
- Generator-Technik: eigene Heuristik (reicht für Gemeindegrößen) vs. Solver (Timefold/OR-Tools).
- Rechte: wer darf Plantypen eines Bereichs ändern, wer nur Einträge?
