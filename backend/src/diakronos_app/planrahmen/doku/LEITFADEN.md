# Leitfaden — den Plan-Rahmen verstehen und verwenden

Der Plan-Rahmen ist ein **generischer Baukasten** fuer beliebige Gemeinde-Plaene:
Chorplan, Freizeitplan, Predigerplan, Musikerplan, Putzplan … Es gibt keinen
„Chorplan-Code". Es gibt **wenige Grundbausteine**, die sich frei kombinieren
lassen (Konzept `KONZEPT.md`). Ein neuer Plan ist eine neue *Kombination*, keine
neue Funktion.

Dieser Leitfaden erklaert die Prinzipien und Bausteine in Prosa und beantwortet
die wichtigste Frage: **Was nehme ich wann?** Er verweist auf die generierte
Referenz (`REFERENZ.md`) fuer jede Eigenschaft und auf gepruefte Beispiele im
Kochbuch (`KOCHBUCH.md`).

---

## Das Wichtigste in drei Saetzen

1. Eine **Plantyp-Datei** (JSON) beschreibt die *Struktur*: welche Termine,
   welche Felder, welche Personen, welche Regeln, welche Ansicht.
2. Der **Plan** ist eine *Instanz* eines Plantyps fuer einen Zeitraum und haelt
   die konkreten Eintraege — die Plantyp-Datei selbst haelt **keine** Daten.
3. Der **Generator** fuellt Entwuerfe nach den Regeln; jeder Wert ist
   ueberschreibbar, von Hand gesetzte Werte sind fixiert und ueberleben jede
   Neugenerierung.

---

## Die Prinzipien (Kurz, aus dem Konzept Teil A)

- **P1 Komposition statt Planarten** — kein Spezialfall, nur Bausteine.
- **P2 Struktur, Daten, Darstellung getrennt** — Plantyp (Struktur), Plan
  (Eintraege), Ansicht (Aussehen). Wer die Darstellung aendert, zerstört keine
  Daten.
- **P3 Alles hat einen Namen, nichts eine Position** — stabile Kennungen, nie
  „Spalte K".
- **P4 Versioniert** — jede Strukturaenderung ist eine neue Version mit
  `gueltig_ab`; vergangene Termine bleiben, wie sie waren.
- **P5 Wer plant, erklaert, was er braucht** — der Plantyp *deklariert* seine
  Datenbeduerfnisse (Merkmale); das Programm prueft und fragt: einrichten oder
  ueberspringen.
- **P6 Die Maschine schlaegt vor, der Mensch entscheidet** — fixierte Werte
  ueberleben jede Neugenerierung.
- **P7 Regeln sind Bausteine mit Stufe** — `muss`/`sollte`/`hinweis`; Verstoesse
  erscheinen als verstaendliche Meldung, nicht als Fehler.
- **P8 Ohne KI lauffaehig** — die KI ist Autorin von Plantyp-Dateien, nie
  Laufzeitabhaengigkeit.
- **P9 Der Dienst bleibt bei den Menschen** — eintragen, tauschen, absagen.
- **P10 Gutmuetig und erklaerend** — minimale Datei gueltig, jede Ablehnung nennt
  Pfad, Grund und Beispiel.
- **P11 Erweiterbar ohne Bruch** — neue Feldarten/Regeln per Code + Doku.
- **P12 Dokumentation ist Teil des Produkts** — Schema, Referenz, Beispiele aus
  *einer* Quelle.

---

## Die Bausteine — was nehme ich wann?

### B1 Plantyp und Plan

Ein **Plantyp** deklariert optional **Parameter**: Platzhalter, die erst der
konkrete Plan fuellt (Zeitraum, Thema, Themenreihe). Immer dann ein Parameter,
wenn der Wert pro Plan verschieden ist und die Struktur gleich bleibt.

> **Wann nehme ich was?** Ein festes Wochenlied? Direkt eingetragen. Ein
> Zeitraum, der sich von Plan zu Plan aendert (`Zeitraum`, `Thema`)? Als
> Parameter — referenziert als `{parameter.<id>}`.

### B2 Termine (die Zeitachse)

Woher kommen die Zeilen? Die Quellen sind **frei kombinierbar**:

| Quelle | Wann | Beispiel |
|---|---|---|
| `regel` | wiederkehrende Termine | `FREQ=WEEKLY;BYDAY=SU` (jeder Sonntag) |
| `zeitraum` | jeder Tag (bestimmte Wochentage) zwischen zwei Daten | Freizeit, taeglich |
| `kalender` | Termine aus Kronos nach Kategorie/Gruppe | Gottesdienste, Proben |
| `feiertage` | bewegliche Feiertage (Oster-/Adventrechnung) | Karfreitag, Himmelfahrt |
| `manuell` | einzelne Termine von Hand | Sondertermin |
| `abgeleitet` | Termine relativ zu einer anderen Reihe (`von`, `versatz`, `nur_wenn`) | Probe Freitag vor dem Gottesdienst |

Dazu `ausnahmen` (Termin entfällt — als Datumsliste ODER `{feiertage: true}`) und
**Anlässe** (B6). Ein Feiertag setzt automatisch einen Anlass gleichen Namens **und**
den Sammelanlass `feiertag`.

**Mehrere Terminreihen (`terminreihen`):** ein Plantyp kann mehrere Zeitachsen
haben, jede mit eigenen Feldern (z. B. `gottesdienst` und die abgeleitete `probe`).
Die bisherige Top-Level-Form `termine` + `felder` bleibt als KURZFORM für genau eine
Reihe (`id: "standard"`) gültig — nie beides zugleich. `vorbelegen` dürfen aus
`bezug.<feld>` lesen: das Feld des Ursprungstermins der abgeleiteten Reihe.

### B3 Felder (was pro Termin geplant wird) — rekursiv

Ein Feld hat eine `art`, optional `anzahl` (fest oder `"min..max"`), `pflicht`,
`zeit`, `bedingung`, `fuellen`.

**Was der Generator befuellt** (UXP-R18): Ohne eigenes `fuellen` gilt
`"optimieren"` fuer `person`, `personen`, `eintrag` und `team`, sonst
`"manuell"`. Ein optionales Feld (`pflicht: false`) auf einem Rollen- oder
Sammlungsfeld wird damit **trotzdem** automatisch besetzt — das ist gewollt
fuer `einsingen`, aber falsch fuer `solo`: ein Solo ist eine Entscheidung des
Planers. Wer ein optionales Feld NICHT automatisch besetzt haben will, setzt
ausdruecklich `"fuellen": "manuell"` (so im Kochbuch-Plantyp `chorplan`).

- `person` / `personen` — eine/mehrere Personen in einer **Rolle**.
- `eintrag` — Element aus einer **Sammlung** (Lied, Bibelarbeit, Spiel).
- `text`, `zahl`, `datum`, `auswahl` — freie Angaben.
- `gruppe` — enthaelt Unterfelder (`inhalt`); kann `varianten` (eine gilt) und
  `teile` (nacheinander) haben.
- `team` — eine **Gruppe von Personen** (Diakonos-Gruppe), nicht eine einzelne
  Person. Quelle ueber `teams` (z. B. `{gruppe_unter: "Musikteams"}` oder eine
  Liste); `mitglieder` filtert eine Teilmenge (z. B. nur die Sänger).
- `ablauf` — eine geordnete, frei sortierbare Liste **heterogener Elemente**
  (Programmablauf, Gottesdienst), deren erlaubte Elementtypen in `elemente`
  deklariert sind (siehe B9a).

**Gruppen schachteln beliebig tief** — daraus entstehen Raster (Tag × Block),
Listen (Termin × Lieder) oder Ablaeufe (Gottesdienst) aus *demselben* Baustein.
Ein `eintrag` kann eigene Unterfelder tragen.

**Varianten und Teile sind Objekte** `{id, name?, inhalt?, bedingung?}` (Kurzform
als String bleibt erlaubt). Ohne eigenes `inhalt` gilt das der Gruppe; mit
eigenem `inhalt` ersetzt es das der Gruppe fuer genau diese Variante bzw. diesen
Teil — so darf die Regen-Variante andere Felder haben als die Sonne-Variante.
Das Pfadformat fuer kombinierte Varianten × Teile ist `gruppe@variante#teil.feld`,
z. B. `abend@regen#abschluss.leitung`.

> **Wann nehme ich was?** Ein einzelnes Lied je Termin → `eintrag`. Drei Lieder
> → `eintrag` mit `anzahl: 3`. Ein Block mit festem Zeitfenster → `gruppe` mit
> `zeit` und `inhalt`. Ein Block mit Sonne/Regen-Alternative → `gruppe` mit
> `varianten`; hat nur die Regen-Variante ein Zusatzfeld, ist die Variante ein
> Objekt mit eigenem `inhalt`. Abschnitte nacheinander (Programm, Abschluss) →
> `teile`.

### B3a Bedingungen (strukturiert, nicht als Freitext)

Ein Feld, ein Teil, eine Variante oder eine Anlass-Wirkung erscheint nur unter
einer **Bedingung** — als strukturiertes JSON mit derselben Knoten-Grammatik wie
die Rollenfilter (KEIN freier Ausdrucks-String). Blattknoten:

| Knoten | Bedeutung | Beispiel |
|---|---|---|
| `anlass` | Termin traegt den Anlass | `{ "anlass": "abendmahl" }` |
| `wochentag` | Termin faellt auf den Wochentag | `{ "wochentag": ["so"] }` |
| `variante` | Variante ist aktiv | `{ "variante": "regen" }` |
| `parameter` | Plan-Parameter hat den Wert | `{ "parameter": { "id": "thema", "gleich": "herbst" } }` |
| `feld_gesetzt` | Feld ist gefuellt (Feld-Pfad) | `{ "feld_gesetzt": "abend.leitung" }` |
| `datum_ab` / `datum_bis` | Termin im Zeitfenster | `{ "datum_ab": "2026-06-01" }` |
| `termin_nr` | jeder n-te Termin | `{ "termin_nr": { "jede": 2 } }` |
| `termin_im_monat` | n-ter Termin der Reihe im Monat (-1 = letzter) | `{ "termin_im_monat": 2 }` |

Verknuepft wird mit `alle` (UND), `eine` (ODER) und `nicht`. Beispiel:

```json
{ "alle": [ { "anlass": "abendmahl" }, { "nicht": { "wochentag": ["mo"] } } ] }
```

### B4 Rollen (wer kommt in Frage)

Eine Rolle ist ein **Filter** ueber Personen, keine feste Liste — rekursiv aus
`merkmal`, `gruppe`, `anmeldung`, `person`, dazu `alle` (UND), `eine` (ODER),
`nicht`.

> **Wann nehme ich was?** „Wer Klavier spielt" → `merkmal`. „Wer im Chor ist" →
> `gruppe`. „Wer sich als Mitarbeiter angemeldet hat" → `anmeldung`. Ein
> bestimmter Gastredner → `person`.

### B5 Sammlungen und Merkmale (Stammdaten)

- **Sammlung** = beliebige Liste (Lieder = eingebaut, sonst selbst deklariert).
  Eine Sammlung hat einen **Umfang**: `gemeinde` (Vorgabe — dauerhafte,
  plannuebergreifende Liste) oder `plan` (gehoert zum einzelnen Plan und wird
  beim Anlegen/Vorbereiten befuellt). *Themen vorbereitend in einen Plan laden*
  heisst: eine Sammlung mit `umfang: "plan"` anlegen — kein gleichnamiger
  Parameter.
- **Merkmal** = Eigenschaft einer Person oder eines Sammlungseintrags: `tag`,
  `auswahl`, `text`, `zahl`, `datum`, `person`.

Merkmale haben einen **Schluessel**, der ueber Plaene hinweg wiederverwendet
wird — pflegt der Planer, nicht der Admin (Bedarfspruefung fragt nach).

**Eingebaute Attribute** (immer vorhanden, brauchen keine Merkmal-Deklaration):
eine Person traegt `name`, `vorname`, `nachname`, `kuerzel`, `email`; die
Sammlung `lieder` traegt `titel`, `buch`, `nummer`, `ccli`, …; **jede** Sammlung
traegt `titel` und `reihenfolge`. Der Chorplan deklariert darum KEIN Merkmal
`kuerzel`, sondern nutzt das eingebaute. Merkmale duerfen eingebaute Attribute
nicht ueberschatten (die Pruefung meldet das als Fehler). Formatvorlagen und
`aus`-Referenzen duerfen auf eingebaute Attribute zeigen (`{eintrag.titel}`).

### B6 Anlaesse

Markierungen an Terminen (Abendmahl, Kinderchor …). Sie koennen **wirken**:
Felder ausblenden (`ohne`), hinzufuegen (`mit`), Regeln steuern (`regeln`).

### B7 Fuellstrategien

`manuell` (nie automatisch) · `reihum` (Personen der Reihe nach) ·
`der_reihe_nach` (Sammlungsreihenfolge) · `vorbelegen` (Wert uebernehmen) ·
`optimieren` (bestmoeglich nach Regeln, Standard).

## Feiertags-Ausnahmen am eigenen Datum

`ausnahmen: {feiertage: true}` prueft das eigene Datum jeder Reihe gegen den
Feiertagskatalog, auch ohne eine `feiertage`-Quellliste. Bei abgeleiteten Terminen
zaehlen nicht die kopierten Anlaesse des Ursprungs. Alle Katalog-Festtage zaehlen
(auch kirchliche Tage, Heiligabend und Silvester); die vier Adventssonntage und
regional konfigurierte Erntedank-Sonntage sind nur Anlaesse und keine
Ausnahmetage. So bleibt die Freitagsprobe vor Erntedank/Advent bestehen, die
Probe am 25.12. entfaellt. `abgeleitet.nur_wenn` prueft weiterhin den Ursprung;
wer keine Probe fuer einen Feiertags-Gottesdienst will, filtert ihn dort.

### Uebungen vorausschauend planen

`vorher_geuebt` liefert dem Generator einen generischen Bedarf: Wert W braucht
`mindestens` verschiedene Uebungstage im Feld X strikt vor Datum D. Der
Generator legt zuerst die Einsaetze fest und fuellt dann die Uebungsfelder mit
`fuellen: "optimieren"`, einschliesslich optionaler Plaetze (`0..6` bis zur
Obergrenze). Fruehere Uebungen und fixierte Werte zaehlen mit; fixe Plaetze,
`manuell`, Anlass-Ausblendungen und Feldbedingungen bleiben geschuetzt.
`vorlauf_wochen` begrenzt die neu geplante Vorbereitung (Vorgabe
`max(4, mindestens)`); vorhandene aeltere Uebungen bleiben gueltig. Mehrere
Slots desselben Werts am selben Datum zaehlen nur als ein Uebungstag.

Aufgeschobene Uebungswerte sind in der ersten Phase **ungeklaert**, nicht leer.
Bedingte Unterfelder, Gruppen, Varianten/Teile und externe Vorbelegungen warten
bis zur Bedarfsphase. Das gilt auch fuer `bezug.*` aus abgeleiteten Terminen:
ein bereits besuchter Ursprung ist nicht gleichbedeutend mit einer geklaerten
Uebungsquelle. Diese Phase setzt den regulaeren abhaengigkeitsbewussten
Fuelllauf fort: nach neuen Werten wird die Struktur erneut aufgeloest, auch
negierte Bedingungen werden erst dann entschieden. Bereits gefuellte Werte
werden nicht neu gezogen; fixierte und manuelle Werte bleiben unveraendert.
Ein Bezug auf das Uebungs-Wertefeld wartet nur auf dessen Werte-Instanzen,
nicht auf die Unterfelder, die selbst von diesem Wert abhaengen.
`vorbelegen.aus: "einueben"` kann einen einzigen gesetzten Instanzwert lesen;
sind mehrere Instanzen gesetzt, ist ein konkreter Pfad wie `einueben[0]`
erforderlich. Mehrdeutige Bezuege bleiben leer, statt einen Wert zu erraten.

Die Kapazitaetsabschaetzung unterscheidet aktive von noch ungeklaerten
Uebungsfeldern: feldabhaengige Felder oder Container gelten als moegliche
kuenftige Uebungstage, nicht dauerhaft als ausgeblendet. Ein vom regulaeren
Resolver spaeter aktivierter Slot aktualisiert die Tageskapazitaet. Das gilt
auch fuer mehrere Uebungsfelder mit Bedingungen und Vorbelegungsketten;
nur tatsaechlich aktive Slots werden gefuellt. Die Abschaetzung ist bei
ungeklaerten Bedingungen eine optimistische Obergrenze, keine Zusage,
dass alle kuenftigen Bedingungen wahr werden. Finale Regeln bleiben wirksam.

Dringliche, noch erfuellbare Fristen kommen zuerst. Fuer einen Einsatz am
ersten/zweiten Sonntag koennen ohne Historie zwei vorherige Uebungstage fehlen;
dieser Rand wird gemeldet, statt knappe Plaetze an unerfuellbare Fristen zu
verschwenden. Bei `sollte` bleibt der Einsatz mit Meldung bestehen. Bei `muss`
bleibt ein nicht rechtzeitig vorbereitbarer automatisch gewaehlter Einsatz
leer (mit Begruendung); fixierte/manuelle Werte bleiben erhalten und werden
als Verstoss gemeldet. Es ist eine deterministische Heuristik, kein globaler
Kapazitaets-Solver: drei neue Werte jede Woche mit je zwei Uebungen brauchen
mehr als zwei Uebungsplaetze. Ausreichende Kapazitaet oder Historie einplanen!

Fuer planuebergreifende Vorbereitung dem Engine-Aufruf explizit die bereits
festgelegten Bezugsplaene geben:
`generiere(plantyp, parameter, termine, fixierte, datenquelle, seed=0,
bezugsplaene=[(programm_plantyp, programm_vorschlag)])`. Der Generator liest
auch deren `vorher_geuebt.uebung`, wenn dessen `plantyp` der aktuelle Typ ist;
er veraendert keinen Bezugsplan. Anschliessend kann die Programmpruefung die
geplanten Uebungen ueber die Datenquelle als Historie lesen. Ohne solche
Bezugsplaene werden keine fremden zukuenftigen Einsaetze erraten (DB/API-Anbindung
ist Aufgabe des Adapters). Regelfelder beziehen sich auf Wertefelder, nicht
auf Container; Unterfelder der Uebungswerte werden regulaer vorbelegt.

### Fairness ohne Doppelzaehlung

`gleich_verteilen` zaehlt standardmaessig nur eigene Entscheidungen:
`quelle` ungleich `vorbelegen`, `vorbelegt`, `abgeleitet`. So verdoppelt eine
Team-Kopie in einer abgeleiteten Probe nicht die Gottesdienst-Einteilung.
Mit `vorbelegte_mitzaehlen: true` zaehlen auch diese Kopien. Ein `feld` begrenzt
Auswahl und Endpruefung auf dieses Wertefeld. Historie hat bisher keine
Herkunftsangabe; solche Werte gelten als eigene Entscheidungen. Beim Import
also Kopien weglassen, wenn nur die eigentliche Einteilung zaehlen soll.

### B8 Regeln

Benannte Bausteine mit Parametern und Stufe. Der Startkatalog steht in
`REFERENZ.md` unter „Regel-Bausteine": `abwesenheit_beachten`, `mindestabstand`,
`max_pro_zeitraum`, `min_pro_zeitraum`, `gleich_verteilen`, `nicht_gleichzeitig`,
`zusammen`, `nicht_zusammen`, `vorher_geuebt`, `passend_zum_anlass`,
`verfuegbarkeit`.

> **Wann nehme ich was?** „Nicht oefter als alle 8 Wochen" → `mindestabstand`.
> „Max. 2 Predigten im Monat" → `max_pro_zeitraum`. „Fair verteilen" →
> `gleich_verteilen`.

### B9 Ansichten

`tabelle`, `raster`, `ablauf`, `meine_dienste`, `druck`, `ical`, `kalender` — mit
**Formatvorlagen** fuer Zellen (`"{eintrag.buch} Nr.{eintrag.nummer}"`). Mehrere
Ansichten pro Plantyp. `kalender` ist der klassische Monats-Aushang: Monatsspalten,
optional `alle_tage` (auch leere Tage) und `kw` (Kalenderwochen-Spalte).

Platzhalter in Formatvorlagen muessen auf etwas Existierendes zeigen — sonst
gibt es eine Warnung mit Vorschlag:

| Form | Bedeutung |
|---|---|
| `{eintrag.<attr>}` | eingebautes Attribut der Sammlung oder deklariertes Merkmal (`{eintrag.titel}`, `{eintrag.buch}`) |
| `{<feld>.<attr>}` | Feld plus Personen-/Sammlungsattribut (`{dirigent.kuerzel}`, `{team.name}`) |
| `{parameter.<id>}` | Plan-Parameter (`{parameter.thema}`) |
| `{termin.<feld>}` | Termin-Feld (`{termin.datum}`, `{termin.anlass}`, `{termin.uhrzeit}`) |
| `{anlass}` | die Anlässe des Termins |
| `{feld: text}` | **bedingt**: `text` nur ausgeben, wenn `feld` gesetzt ist (`{gaeste: + {gaeste.vorname}}`) |

### B9a Abläufe und Programme

Ein **Ablauf** (`art: "ablauf"`) ist eine geordnete, frei sortierbare Liste
**heterogener Elemente** — das, was ein Gottesdienst-Ablaufplanner und ein
Programmheft brauchen. Der Plantyp deklariert die erlaubten **Elementtypen** in
`elemente`; jedes Element ist `{typ, name?, nummeriert?, inhalt, bedingung?}`:

```json
{ "id": "ablauf", "art": "ablauf", "anzahl": "1..*",
  "elemente": [
    { "typ": "lied", "nummeriert": true, "inhalt": [ { "id": "lied", "art": "eintrag", "sammlung": "lieder" }, … ] },
    { "typ": "szene", "inhalt": [ { "id": "titel", "art": "text" } ] },
    { "typ": "predigt", "inhalt": [ { "id": "prediger", "art": "person", "pflicht": false } ] }
  ] }
```

- Die **Elementtypen** sind eindeutige, stabile Kennungen (`lied`, `szene`,
  `predigt`) — über sie spricht man Elemente an (P3). `anzahl` mit offenem Ende
  (`"1..*"`, `"0..*"`) erlaubt eine beliebig lange Liste.
- **Nummerierung je Elementtyp:** `nummeriert: true` lässt die Elemente dieses
  Typs eine laufende Nummer `nr` tragen; die Zählung läuft **nur innerhalb
  nummerierter Typen**. Szenen zwischen nummerierten Liedern verschieben die
  Liednummern also nicht: Lied 1, Szene (ohne Nr.), Lied 2, …
- **Feldpfade sind stabil bei Umsortierung.** Ein einzelnes Element wird über
  seine **Element-ID** angesprochen, nicht über seine Position:
  `ablauf/<element_id>.<innerfeld>` (z. B. `ablauf/l3.lied`). Verweise auf
  *alle* Elemente eines Typs laufen über `ablauf.<typ>` (z. B. `ablauf.lied`),
  Formatvorlagen je Elementtyp über den Typ-Schlüssel.
- Die Ansicht **`programm`** ist das Programmheft/der Liedzettel (A4-hoch): ein
  `kopf` und ein `fuss` aus Plan-, Termin- und Parameter-Platzhaltern sowie eine
  `format`-Vorlage **je Elementtyp** (dort ist `{nr}` die Elementnummer, `{lied.seite}`
  die — oft fehlende — Heftseite des Lieds).

### B9b Pläne, die zusammengehören (Projekte)

Viele Vorgänge spannen über **mehrere Pläne**: ein Konzert hat ein Oberprogramm,
das vom Adventssingen übernimmt, und die Lieder müssen zuvor im **Chorplan**
eingeübt werden. Dafür gibt es zwei Mechanismen:

- **Planübergreifende Verweise** in Regeln und Vorbelegungen zeigen auf Felder
  eines *anderen* Plantyps über `{plantyp: "<schluessel>", feld: "<pfad>"}`.
  Beispiel: `vorher_geuebt` mit `uebung: {plantyp: "chorplan", feld: "einueben"}`
  erzwingt, dass die Programm-Lieder vorher im Chorplan geübt wurden. Dabei darf
  der Verweis zur Prüfzeit nicht auflösbar sein (der fremde Plantyp liegt in
  einer anderen Datei) — das ist eine **Warnung** `fremder_plantyp_ungeprueft`,
  kein Fehler; die Engine löst ihn zur Laufzeit auf.
- **`auch_in`** erweitert `mindestabstand` und `vorher_geuebt` um eine
  **gemeinsame Historie** über Plantyp-Grenzen hinweg (ein Lied, das im Programm
  gesungen wird, zählt für den Chorplan-Abstand).
- **`uebernahme`** ist eine Plantyp-Option `{erlaubt_von: [plantyp…], felder: […]}`:
  sie erlaubt, Einträge (z. B. Lieder inkl. Besetzung) aus einem anderen Plan zu
  übernehmen und danach abzuweichen. Die Ausführung kommt in PR4; hier wird sie
  deklariert und dokumentiert.

### B10 Lebenszyklus

Entwurf → (generieren, fixieren) → veroeffentlicht → Aenderung erzeugt Diff +
Benachrichtigung. Plantyp-Aenderung = neue Version mit `gueltig_ab`.

---

## So arbeitet der Generator

Die Engine arbeitet mit dem Protokoll `Datenquelle` und reinen Python-Objekten,
ohne Datenbankzugriffe oder Endpunkte. `InMemoryDatenquelle` liefert dieselben
Personen, Gruppen, Sammlungen, Abwesenheiten und Historien wie ein spaeterer
DB-Adapter. `generiere(plantyp, parameter, termine, bestehende, datenquelle,
seed=0)` gibt einen `Vorschlag` mit Eintraegen, Verstoessen und Meldungen zurueck.

Der Generator loest den Felderbaum je Termin zu einer flachen Liste von
**Slots** auf (stabile Feld-Pfade wie `lieder[0].dirigent`,
`abend@regen#programm.leitung`), wertet Rollen aus und fuellt die Slots nach
den Fuellstrategien; `sollte`-Regeln fliessen als Strafen in eine gierige,
deterministische Auswahl ein, `muss`-Regeln sind harte Filter. Fixierte
Eintraege werden nie ueberschrieben. Kann ein Pflicht-Slot nicht gefuellt
werden, bleibt er leer und es erscheint eine Meldung — nie ein Absturz.

- `feld_gesetzt` liest die aktuelle Besetzung desselben Termins. Abhaengige
  Felder werden erst nach ihrer Vorbedingung ausgewertet (auch unter `nicht`,
  in Varianten, Teilen und Ablauf-Elementen); ein fehlender oder ausgeblendeter
  Wert gilt nicht als gesetzt. Die abschliessende Planpruefung verwendet
  denselben Zustand und dieselben Feld-Deklarationen. Deklarative Bezuege wie
  `leitung` treffen alle `leitung[0]`, `leitung[1]`, … derselben Reihe;
  `programm.dienst.leitung` trifft die Leitung aller Ablauf-Elemente vom Typ
  `dienst`. Gesetzt bedeutet: mindestens ein konkreter Wert ist nicht `None`.
  Unter Container-Bezuegen werden die Werte der Unterfelder betrachtet. Erst
  wenn alle aktiven Quellslots versucht oder fixiert und alle Bedingungen im
  referenzierten Unterbaum geklaert sind, wird die Bedingung entschieden. Ein
  bearbeitetes leeres Geschwister macht noch bedingte Kinder nicht bereit;
  insbesondere wartet `nicht` auf diese Kinder. Leere Mehrfachfelder und
  fehlende Ablauf-Typen sind leere Quellen.
  Explizite Instanzpfade der Python-Schnittstelle bleiben dagegen spezifisch.
  Bei der finalen Regelpruefung bleibt der gesamte Strukturzustand erhalten;
  nur die Selbstzaehlung des gerade bewerteten Eintrags wird ausgeschlossen.
- Rollenfilter lesen `merkmal_werte` und `gruppen_mitglieder` der Datenquelle;
  redundante Merkmale/Gruppen auf den Personenobjekten sind nicht erforderlich.
- `nicht_gleichzeitig`, `zusammen` und `nicht_zusammen` betrachten bei Teams
  die wirklichen Mitglieder, einschliesslich `mitglieder`-Teilmenge. Nur die
  Abwesenheitsregel beschraenkt die Pruefung auf deklarierte Pflichtmitglieder.
- `reihum` setzt nach dem zuletzt verwendeten Wert der Historie fort und
  ueberspringt unzulaessige Kandidaten. `der_reihe_nach` verwendet die stabile
  Sammlungsreihenfolge und ueberspringt bereits vergebene Werte.
- `vorbelegen` wartet auf seine automatische Quelle, unabhaengig von der
  Feldreihenfolge und auch entlang von Ketten. Das gilt ebenso fuer
  Sammlungsmerkmale aus einem Eltern-Eintrag oder einem Ablauf-Geschwister.
  Deklarierte Eintrag-Geschwister werden auch vor ihrer bedingten Freigabe als
  Quellen betrachtet. Ein noch nicht aktives Lied ist daher nicht schon leer.
  Sobald der Quellwert versucht, fixiert oder sicher ausgeblendet ist, kann
  die Besetzung folgen; der Unterbaum der Quelle muss nicht fertig sein
  (er kann die Besetzung selbst enthalten).
  Erst ein geklaerter leerer Quellwert erzeugt den Hinweis „Quelle ist leer“;
  ungeklaerte Quellen werden als solche gemeldet statt voreilig leer gesetzt.
  **Rueckfall (OP-CHOR-11):** ist die Quelle leer — etwa weil am Lied kein
  Dirigent/Klavier gepflegt ist —, greift die stabile `reihum`-Rotation aus der
  Rolle. So sind „Dirigent“ und „Klavier“ auch ohne Vorbelegung besetzt, statt
  dass der Planer jede Zelle von Hand waehlt.
- Alle automatischen Strategien beachten Muss-Regeln, auch Vorbelegung.
  Bei unzulaessiger Vorbelegung wird Ersatz aus Rolle/Quelle gesucht und die
  Ursache gemeldet. `hinweis` beeinflusst die Auswahl nicht.
- `optimieren` minimiert die gewichteten Sollte-Strafen, danach die bisherige
  Nutzung. Gleichstaende werden mit dem Seed reproduzierbar aufgeloest.
- Fixierte Werte bleiben bestehen, einschliesslich zukuenftiger Termine.
  Nicht fixierte automatische Werte werden neu erzeugt. Manuelle/uebernommene
  Werte bleiben als Eingaben erhalten und werden erneut auf Regeln geprueft.
- Abgeleitete Termine werden nach ihrem Ursprung befuellt, auch bei negativem
  Datumsversatz. `bezug.team` liest genau dessen Besetzung. Ein reserviertes
  Team-Zeitmuster (z. B. 1. Sonntag) schliesst andere Teams in diesem Muster aus.
- `Termin.ablauf` enthaelt je Feldpfad die manuell geordnete Liste `{id, typ}`.
  Nur diese konkreten Elemente werden zu Slots wie `ablauf/l1.dirigent`
  aufgeloest; kein Generator legt Elemente an oder sortiert sie um.
  Ohne Ablauf-Metadaten koennen bereits vorhandene flache Eintraege einen
  Elementtyp eindeutig ueber sein Innerfeld bestimmen. Deklarative Bedingungen
  verwenden dann dieselbe Typzuordnung wie die Slot-Aufloesung, auch in der
  finalen Regelpruefung. IDs sind opaque; der Typ wird nicht aus ihnen geraten
  und die Termin-Metadaten werden nicht nachtraeglich veraendert.
  `ablauf_elemente` berechnet die Nummer je nummeriertem Typ ohne Speicherung.
- Historie wird nach Plantyp und normalisiertem Wertefeld gelesen; Elemente
  aus anderen Programmen wirken ueber `mindestabstand.auch_in`. Uebungen zaehlen
  nur fuer denselben Wert und strikt vor dem Veranstaltungstag.
- `uebernimm` kopiert Werte inklusive Ablauf-Besetzung mit
  `quelle='uebernommen'`, ohne Fixierung. Der Aufrufer fuegt die Eintraege an und
  ruft `pruefe_plan` erneut auf. Ein einzelner Zieltermin nimmt die Quelle auf;
  mehrere Zieltermine muessen eindeutig nach Datum/Reihe passen.

`bedarfspruefung` meldet fehlende Merkmale, Rollen und Sammlungen mit der
Einstufung `blockiert_automatik`, `eingeschraenkt` oder `ok`. Benannte Rollen
werden bis zu ihren Filtern verfolgt; unbenutzte Rollen erzeugen keinen Bedarf.
Vorbelegungs- und Regelmerkmale eines Sammlungseintrags werden nur fuer dessen
Sammlung geprueft, nicht bei Personen oder allen anderen Katalogen. `trockenlauf`
erzeugt standardmaessig acht Wochen samt Bedarf und Verstoessen, ohne die
Datenquelle zu veraendern. Umfang `min..max` erzeugt den Mindestumfang; eine
Erweiterung und Ablauf-Elemente bleiben beim Menschen. Erntedank verwendet
den ersten Sonntag im Oktober; `erzeuge_termine(..., erntedank="2. So im
September")` erlaubt regionale Abweichungen je Aufruf (1. bis 4. Sonntag eines
deutsch benannten Monats). Berechnung und Anlasszuordnung nutzen dieselbe
Konfiguration. Es gibt dafuer keine globale Einstellung und kein neues
Plantyp-Schemafeld; die aufrufende Integrationsschicht reicht sie weiter.

---

## Kurzanleitung: so entsteht ein neuer Plantyp

1. **Struktur verstehen**: welche Termine, welche Felder, welche Rollen, welche
   Regeln? (ggf. Fragenkatalog in `AGENT-ONBOARDING.md`).
2. **Plantyp-Datei schreiben** (siehe `KOCHBUCH.md` als Vorlage).
3. **Prüfen**: `pruefe_plantyp(daten)` → keine Fehler, keine Warnungen.
4. **Trockenlauf**: 8 Wochen generieren, Konflikte und Datenbedarf ansehen.
5. **Vorschau → Mensch bestaetigt.**

---

## Weiterlesen

- `KONZEPT.md` — das vollstaendige Konzept (Prinzipien P1-P12, Beispiele C1/C2).
- `REFERENZ.md` — generierte Referenz (jede Eigenschaft, alle Bausteine).
- `KOCHBUCH.md` — gepruefte Beispiele, eines pro Planart.
- `AGENT-ONBOARDING.md` — Fragenkatalog fuer den Onboarding-Agenten.
