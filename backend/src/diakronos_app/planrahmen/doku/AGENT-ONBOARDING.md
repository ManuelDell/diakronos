# Onboarding (Agent) — Fragenkatalog, Vorgehen, typische Fallen

Der Onboarding-Agent richtet eine Gemeinde in den Plan-Rahmen ein: er liest
Excel-Dateien, Fotos alter Plaene und Mitgliederlisten, erkennt die Struktur,
fragt gezielt nach und schreibt daraus **Plantyp-Dateien** — dann prueft er,
macht einen Trockenlauf und zeigt eine Vorschau, bevor ein Mensch bestaetigt.

Dieses Dokument gibt dem Agenten: den **Fragenkatalog** (pro Planart), das
**Vorgehen** beim Lesen von Excel/Fotos und die **typischen Fallen** sowie den
verbindlichen **Ablauf** pruefen → trockenlauf → vorschau.

---

## Der Ablauf (verbindlich)

1. **Stammdaten**: Personen, Gruppen, Kuerzel abgleichen (TIN = TINA = Tina?),
   bei Unklarem nachfragen (Werkzeug `rueckfrage`).
2. **Pro Plan**: Struktur erkennen → gezielt fragen (Fragenkatalog unten) →
   Plantyp-Datei schreiben.
3. **Pruefen**: `plantyp_pruefen` → Schemavalidierung + semantische Pruefung.
   Jede Meldung nennt Pfad, Grund und Beispiel — **korrigiere dich selbst**,
   bis keine Fehler und keine Warnungen mehr da sind (P10).
4. **Trockenlauf**: 8 Wochen generieren (`trockenlauf`), Konflikte ansehen.
5. **Vorschau** zeigen → **Mensch bestaetigt** (nicht der Agent).

Der Agent schreibt **nichts direkt in die Datenbank** — alles laeuft ueber
dieselben geprueften Wege wie das Formular.

---

## Fragenkatalog (welche Fragen bei welcher Planart)

Diese Fragen sind *Anregungen*; nicht jede passt auf jede Gemeinde. Ziel ist,
die Struktur so zu erkennen, dass die Plantyp-Datei sie vollstaendig abbildet.

### Allgemein (jede Planart)

- Welche **Termine** gibt es, und wie wiederholen sie sich (jeder Sonntag, jeder
  Tag der Woche, feste Daten)?
- Welche **Felder** werden pro Termin geplant — und in welcher Reihenfolge?
- Gibt es **Anlaesse**, die den Ablauf veraendern (Abendmahl, Kinderchor, …)?
- Wer darf die Werte **von Hand aendern**, was ist fest?
- Welche **Ansicht** braucht die Gemeinde (Aushang, Beamer, Personensicht)?

### Chor- und Musikerplan

- Wer waehlt die **Lieder** aus, und wonach?
- Gibt es **feste Paare** Lied ↔ Dirigent/Klavier (Vorbelegung)?
- Welche **Merkmale** haben die Personen (dirigiert, spielt Klavier, Stimme)?
- Wie oft darf ein Lied **wiederholt** werden (Mindestabstand)?
- Muessen neue Lieder **erst geuebt** werden, bevor sie gesungen werden?

### Musikteams (Quartals-Aushang)

- Ist „Gruppe 3 = 1. Sonntag" eine **feste Regel** oder Zufall? (→ als
  `verfuegbarkeit`-Muster oder `termin_im_monat`-Bedingung abbilden.)
- Warum weicht eine Gruppe von der erwarteten Reihenfolge ab (z. B. Gruppe 4
  statt Gruppe 1)? **Grund erfragen:** Wunsch oder Abwesenheit?
- Wer waehlt das **Monatslied**, und gehoert es in die gemeinsame Sammlung
  `lieder` (auch im Chorplan sichtbar)?
- Gehoeren die **Proben** als abgeleitete Reihe zum selben Plantyp (gleiches
  Team, Versatz −2 Tage, ohne Feiertage)?

### Programmheft / Programmablauf (Adventssingen, Weihnachtsmarkt)

- **Lieder sind nummeriert, Zwischentitel nicht.** Ein Programmzettel nummeriert
  die Lieder fortlaufend (1..9), die dazwischenliegenden *Szenen* eines Anspiels
  und die *Predigt* tragen keine Nummer. Das ist *eine* Liste heterogener
  Elemente, die als ein `ablauf`-Feld mit mehreren Elementtypen modelliert wird —
  nicht als getrennte Lieder-/Textlisten.
- **Ein Elementtyp pro Darstellungsform:** Lied (nummeriert, mit Heft/Seite,
  Ensemble, Begleitung, Dirigent/Klavier), Szene (nur Titel), Predigt (Prediger).
- **Kuerzel wie `Mir/Orch` sind Kombinationen aus Person und Ensemble.** Der
  Dirigent/Klavier-Slot kann eine Person *oder* ein Ensemble *oder* beides
  (`Jo/Lea/Solo`, `Mir/Orch`) tragen. Diese Kuerzel sind **nicht** beliebig
  aufloesbar — **nachfragen** (`rueckfrage`): Wer verbirgt sich hinter `Mir`,
  `Jo`, `Lea`, `Solo`? Welches Ensemble ist `Orch`? Modelliere die
  Begleitung als mehrwertige `auswahl` (Ensemble/Begleitung), nicht als
  Personenzwang.
- **Die Heftseite fehlt oft.** Viele Lieder nennen ein Heft (`MB`, `KB`) aber
  keine Seite (`MB S. 150` mal mit, mal ohne). Die **Seite ist optional** —
  fehlende Seite ist erlaubt, kein Fehler.
- **Bestätigte Vorbelegung:** teilen zwei Programme dasselbe Lied mit identischer
  Besetzung, wird die Besetzung aus dem Lied vorbelegt (gemeinsame Sammlung
  `lieder`).
- **Planübergreifend fragen:** Die Lieder eines Programms müssen zuvor im
  Chorplan geübt sein — prüfe, ob das im Chorplan als `einueben` auftaucht, und
  frage nach der Mindestzahl.

### Predigerplan

- Wer predigt wann (Rotation, Einladung)? Gibt es **Gastprediger**?
- Gibt es eine **Hoechstzahl** je Monat („max. 2")?
- Gibt es eine **Predigtreihe** (Themen, Sammlung)?

### Freizeitplan

- Welche **Zeitbloecke** gibt es je Tag (feste Uhrzeiten)?
- Gibt es **Varianten** (Sonne/Regen) und **Teile** (Programm/Abschluss)?
- Wer ist bei der **Anmeldung** dabei, und was bekommt er zugeteilt
  (Tagesleitung, Bibelarbeit, Spiele)?

### Kindergottesdienst / altersgemischte Gruppen

- Gibt es **Altersgruppen** (z. B. 0-3, 3-6, 6-10) als Varianten oder Felder?
- Wer leitet, wer hilft — nach welchem Merkmal?

### Putz- und Hausmeisterplan

- Wie laeuft die **Rotation ueber Familien**?
- Gibt es eine feste **Reihenfolge** (`der_reihe_nach` oder `reihum`)?

### Technik (Beamer/Ton)

- Welche **Aufgaben** gibt es (Beamer, Ton, Stream)?
- Gibt es eine **Mindestqualifikation** („mind. 1 erfahrene Person")?

---

## Vorgehen beim Lesen von Excel / Fotos

1. **Erst Struktur, dann Inhalt.** Erkenne zuerst die wiederkehrende Struktur
   (Zeilen = Termine, Spalten = Felder), bevor du Werte ueberträgst.
2. **Spalten und Blätter mit Namen ansprechen.** Merke dir stabile **Kennungen**,
   nie „Spalte K" oder „Blatt 2021" (P3).
3. **Personen und Lieder sind Datensätze, kein Freitext.** Ein Name taucht in
   vielen Schreibweisen auf — gleiche sie zu einer Kennung ab.
4. **Feste und bewegliche Termine trennen.** Feste Daten → `manuell`, Muster →
   `regel`/`zeitraum`, Feiertage → `feiertage`.
5. **Bei Formeln und verschmolzenen Zellen vorsichtig sein** (siehe Fallen).

---

## Typische Fallen

- **Freitext-Kuerzel TIN/TINA/Tin.** Derselbe Mensch in drei Schreibweisen.
  Immer auf *eine* Kennung abgleichen, bei Unsicherheit nachfragen — nie raten.
- **Wandernde Spalten.** Spalten wurden ueber die Jahre verschoben; die Formeln
  brachen. Deshalb P2/P3: Struktur, Daten, Darstellung getrennt und stabile
  Kennungen statt Positionen.
- **Kaputte Formeln.** Excel-Dateien mit `#REF!`/`#VALUE!` — nur die *Idee*
  zaehlt, nicht das rechnerische Ergebnis. Rechne nie an kaputten Formeln weiter.
- **Hart verdrahtete Jahresblaetter.** Pro Jahr ein Blatt („2021", „2022") —
  das ueberfuehren wir in *einen* Plantyp + Zeitraum-Parameter, nicht in
  Jahresversionen.
- **„Gruppe ohne Nummer" (Musikteams).** Steht in einer Probe-Zeile nur
  „Saenger Gruppe" *ohne* Nummer, ist sie aus dem zugehoerigen Gottesdienst am
  naechsten Sonntag ableitbar (gleiche Gruppe + Versatz). Der Import soll so
  etwas ERKENNEN und nachfragen („Welche Gruppe prueft am 4.12.?") statt raten.
- **Annahmen nicht als Fakten.** Was der Agent nur vermutet, landet als Frage
  (`rueckfrage`) oder in der Bedarfspruefung — nie als still angenommener Wert.

---

## Was nicht automatisch ermittelbar ist

Merkmale, die der Agent nicht sicher ermitteln kann (z. B. „spielt Klavier"),
landen in der **Bedarfspruefung** (P5): das Programm fragt den Planer beim
Anlegen, ob er sie jetzt einrichten oder ueberspringen will. Der Agent erzwingt
keine Daten.
