# Kochbuch — gepruefte Plantyp-Beispiele

Jede Datei in `kochbuch/*.json` ist ein **vollstaendiges, geprueftes** Beispiel
fuer eine Planart. Die Testsuite prueft alle Beispiel-Dateien gegen
`pruefe_plantyp` (keine Fehler, keine Warnungen) — ein Beispiel kann also nie
veralten, ohne dass die Tests rot werden.

Die Beispiele zeigen die Ausdruckskraft des Rahmens: Verschachtelung
(Gruppen mit Unterfeldern), Varianten, Teile, Bedingungen (als Struktur),
Parameter und Regelparameter. Du darfst sie als Vorlage nehmen und anpassen —
aber denke daran: Chor und Freizeit sind nur **Beispieldaten**, keine
eingebauten Sonderfaelle.

| Datei | Planart | Was es zeigt |
|---|---|---|
| `chorplan.json` | Chorplan | Mindestabstand, Vorbelegen (Lied → Dirigent/Klavier), Anlass-Wirkung (`ohne`), `reihum`, eingebaute Sammlung `lieder`, eingebaute Attribute (`kuerzel`, `nummer`) in der Formatvorlage |
| `freizeit.json` | Freizeitplan | `zeitraum`-Termine (taeglich), Varianten/Teile als **Objekte** (Regen mit eigenem Feld), `der_reihe_nach`, Sammlung mit `umfang: "plan"` (Themenreihe vorbereitend), Merkmale einer eigenen Sammlung (`stelle`, `lernvers`) |
| `predigerplan.json` | Predigerplan | Gastprediger, `max_pro_zeitraum`, Predigtreihe, Verfuegbarkeit |
| `musikerplan.json` | Musikerplan | Band-Besetzung mit Pflichtinstrumenten, `nicht_gleichzeitig`, ODER-Filter |
| `kindergottesdienst.json` | Kindergottesdienst | Altersgruppen als Varianten, `der_reihe_nach` |
| `putzplan.json` | Putzplan | `reihum` ueber eine Gruppe, `zusammen` |
| `technik.json` | Technik | Beamer/Ton, mind. 1 erfahrene Person je Merkmal (`min_pro_zeitraum`), faire Mischung |
| `gottesdienstablauf.json` | Gottesdienst-Ablauf | Ein einzelner Gottesdienst als **`ablauf`** (Feldart ablauf): modulare Elementtypen (Begruessung/Lied/Predigt/Abendmahl) nacheinander, das Abendmahl nur bei Anlass `abendmahl` (**strukturierte Bedingung**), Moderation `reihum`, Predigt aus einer Predigtreihe mit `umfang: "plan"`, Ansicht **`programm`** |
| `musikteams.json` | Musikteam-Aushang | Mehrere **Terminreihen** (`gottesdienst` + abgeleitete `probe` mit `versatz "-2T"`), Feldart **`team`** mit `mitglieder`-Teilmenge, Bedingung **`termin_im_monat`**, Ansicht **`kalender`** (Monatsspalten/KW), **bedingte Format-Platzhalter** `{gaeste: + …}`, `vorbelegen` aus `bezug.team` |
| `programm.json` | Programmablauf | Ein Programmheft/Liedzettel (C4): **Feldart `ablauf`** aus nummerierten `lied`-Elementen (mit Ensemble/Begleitung/Dirigent/Klavier, Heft-Seite optional), Zwischenszenen (`szene`) und einer `predigt`; **planuebergreifende Regel** `vorher_geuebt` mit `uebung: {plantyp:"chorplan", feld:"einueben"}`; Ansicht **`programm`** mit `kopf`/`fuss` und Format je Elementtyp |

---

## Chorplan (`chorplan.json`)

Wochlicher Gottesdienst am Sonntag (`FREQ=WEEKLY;BYDAY=SU`, Uhrzeit `10:00`) plus
ausgewaehlte Feiertage. Die drei Lieder kommen aus der **eingebauten Sammlung**
`lieder`; Dirigent und Klavier werden aus den Merkmalen des Liedes **vorbelegt**
(`fuellen: "vorbelegen"`, `aus: "eintrag.dirigent"`). Das Einsingen laeuft
**reihum**. Anlaesse **blenden Felder aus**: `kinderchor` deckelt Lieder,
Einsingen und Einueben, `chorfrei` (Freizeiten/Sommerpause) deaktiviert Lieder,
Einueben und Einsingen. Die Formatvorlage nutzt die **eingebauten Attribute**
`{eintrag.buch}`, `{eintrag.nummer}`, `{dirigent.kuerzel}` — das Personen-Kuerzel
wird NICHT als Merkmal deklariert.

Regeln: Abwesenheiten sind `muss`, der Mindestabstand von 8 Wochen und das
„vorher zweimal einueben" sind `sollte`, die Liedauswahl wird zum Anlass passend
gehalten (`passend_zum_anlass`).

## Freizeitplan (`freizeit.json`)

Mehrtagige Freizeit: die Termine kommen aus dem **Zeitraum-Parameter**
(`{parameter.zeitraum}`), jeder Tag. Der Tag ist in Gruppen mit festen
Zeitfenstern gegliedert. Die **Bibelarbeit** laeuft der Reihe nach durch die
Sammlung `bibelarbeiten`, die mit `umfang: "plan"` deklariert ist (Themenreihe
vorbereitend befuellt); sie traegt eigene Merkmale (`stelle`, `lernvers`; `titel`
kommt aus dem eingebauten Attribut). Nachmittags- und Abendblock haben
**Varianten** (Sonne/Regen) — die Regen-Variante ist ein **Objekt mit eigenem
Feld** (Ausweichraum). Der Abend hat **Teile** (Programm/Abschluss), der
Abschluss traegt ein eigenes `abendlied`. Tagesleitung und Mitarbeiter werden
fair verteilt.

## Predigerplan (`predigerplan.json`)

Sonntagspredigten: regulaere Prediger (Merkmal `prediger`) und Gastprediger
(`gastprediger`). Die Regel `max_pro_zeitraum` deckelt Gastprediger auf **2 je
Monat**. Eine Predigtreihe laeuft `der_reihe_nach`. `verfuegbarkeit` haelt ein
festes Muster ein (Beispiel „nur 1. Sonntag"). Der Moderator laeuft `reihum`.

## Musikerplan (`musikerplan.json`)

Band-Besetzung mit **Pflichtinstrumenten** als Merkmale (Schlagzeug, Bass,
Gitarre, Keyboard, Gesang). `nicht_gleichzeitig` stellt sicher, dass niemand
zwei Instrumente zugleich spielt. `gleich_verteilen` verteilt die Dienste fair
ueber die Musiker (ODER-Filter `eine: [...]`).

## Kindergottesdienst (`kindergottesdienst.json`)

Altersgetrennte Gruppen: die **Altersgruppe** ist eine `gruppe` mit **Varianten**
(0-3, 3-6, 6-10), je Gruppe ein Raum, ein Programm (der Reihe nach) und
Leiter/Helfer nach Merkmal.

## Putzplan (`putzplan.json`)

Wochentliche Reinigung (`FREQ=WEEKLY;BYDAY=SA`): die Familie wird **reihum**
ueber die Gruppe `Hauskreis` gewaehlt. Die Regel `zusammen` haelt ein festes
Paar immer gemeinsam. Abwesenheiten werden uebersprungen.

## Technik (`technik.json`)

Beamer und Ton je Gottesdienst. `min_pro_zeitraum` mit `zeitraum: "termin"`
erzwingt **mindestens 1 erfahrene Person je Bereich und Termin** (Merkmal
`erfahren_beamer`/`erfahren_ton`). Zusatzhelfer werden fair gemischt.

## Gottesdienst-Ablauf (`gottesdienstablauf.json`)

Ein einzelner Gottesdienst als **Ablauf** (Feldart `ablauf`): modulare
**Elementtypen** (`begruessung`, `lied`, `predigt`, `abendmahl`), die nacheinander
ablaufen. Das Element `abendmahl` erscheint nur bei Anlass `abendmahl` — ueber die
**strukturierte Bedingung** `{ "bedingung": { "anlass": "abendmahl" } }`. Die
Moderation laeuft `reihum`, die Predigt kommt der Reihe nach aus der Sammlung
`predigtreihe` mit `umfang: "plan"` (Themen vorbereitend befuellt). Die Ansicht
ist ein **`programm`** (Programmheft) mit `format` je Elementtyp.

## Programmablauf (`programm.json`)

Ein **Programmheft/Liedzettel** einer einzelnen Veranstaltung (Adventssingen,
Weihnachtsmarkt): die **Feldart `ablauf`** traegt die geordnete Liste heterogener
Elemente — `lied` (mit Lied, Ensemble, Begleitung, Dirigent, Klavier), `szene`
(nur Titel) und `predigt` (Prediger). Die Lieder sind `nummeriert` (laufende
Nummer innerhalb des `lied`-Typs), Szenen und Predigt nicht. Die Begleitung ist
eine **mehrwertige `auswahl`** (Orchester, Gitarre, Violine, Klavier), das
Ensemble ebenso (Chor, Maennerchor, Solo …) — ein `Mir/Orch` ist die Kombination
aus Person und Ensemble. Das **Lied-Attribut `seite`** (Heftseite) ist eingebaut
und darf fehlen; die Formatvorlage bedingt sie (`{lied.seite: S. {lied.seite}}`).

Die **planuebergreifende Regel** `vorher_geuebt` verweist auf den Chorplan
(`uebung: {plantyp: "chorplan", feld: "einueben"}`) und verlangt, dass jedes
Programm-Lied zuvor 3× geuebt wurde. Die Ansicht `programm` (A4-hoch) setzt einen
`kopf` aus Plan-/Termin-/Parameter-Platzhaltern, einen `fuss` und ein `format`
je Elementtyp zusammen.

## Musikteam-Aushang (`musikteams.json`)

Der Quartals-Aushang der Musikteams: zwei **Terminreihen** — `gottesdienst`
(jeder Sonntag, `FREQ=WEEKLY;BYDAY=SU`) und die daraus **abgeleitete** `probe`
(`abgeleitet: {von: "gottesdienst", versatz: "-2T"}`, fällt an Feiertagen aus).
Das Sonntagsfeld `team` ist eine **Feldart `team`** (Diakonos-Gruppe, `reihum`),
die Probe übernimmt dasselbe Team per `vorbelegen` aus `bezug.team` und filtert
mit `mitglieder: {merkmal: "saenger"}` nur die Sänger. Das Monatslied erscheint
nur am 2. Sonntag (**Bedingung `termin_im_monat: 2`**). Die Ansicht ist ein
**`kalender`** (Monatsspalten, alle Tage, KW-Spalte) mit **bedingten
Format-Platzhaltern** (`{gaeste: + {gaeste.vorname}}`). `verfuegbarkeit` legt
„Gruppe 3 = 1. Sonntag" fest, `gleich_verteilen` rotiert die übrigen Teams fair.

---

## Weiterlesen

- `LEITFADEN.md` — Was nehme ich wann.
- `REFERENZ.md` — jede Eigenschaft und jeder Baustein.
- `KONZEPT.md` — die Prinzipien dahinter.
