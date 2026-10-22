# Plantyp-Referenz (Version 1)

**Automatisch erzeugt aus `schema/plantyp-1.json` und der Baustein-Registry — nicht von Hand aendern.** Jede Eigenschaft des Schemas ist hier aufgefuehrt, dazu die Regel-Bausteine, Feldarten, Fuellstrategien und der Feiertags-Katalog. Der Einstieg fuer Menschen ist `LEITFADEN.md`, das Kochen nach Beispielen im `KOCHBUCH.md`.


## Datei (oberste Ebene)

- **`schema`** — Kennzeichnung der Datei als Plantyp-Version 1. Muss exakt diesen Wert haben, damit die Pruefung weiss, welches Schema anzuwenden ist.

Beispiele: `"diakronos/plantyp@1"`. (Pflicht)
- **`id`** — Stabiler, maschinenlesbarer Kurzname des Plantyps (Kleinbuchstaben, Ziffern, Unterstrich, Bindestrich; kein Leerzeichen, kein Umlaut). Ueber diese Kennung werden Plantypen angesprochen und versioniert — nie ueber den Anzeigenamen.

Beispiele: `"chorplan"`, `"freizeit"`, `"predigerplan"`. (Pflicht)
- **`name`** — Anzeigename des Plantyps, wie ihn Menschen sehen.

Beispiele: `"Chorplan"`, `"Freizeitplan"`.
- **`bereich`** — Organisatorische Zuordnung (z. B. Dienstbereich in Diakronos). Rein beschreibend; sie beeinflusst die Struktur nicht.

Beispiele: `"Chor"`, `"Freizeit"`.
- **`beschreibung`** — Freie, menschliche Beschreibung, was dieser Plantyp regelt und wie er zu verwenden ist.

Beispiele: `"Wochentliche Chorprobe am Sonntag mit Liedauswahl und Einsingen."`.
- **`gueltig_ab`** — Erster Tag, ab dem diese Version des Plantyps gilt. Aenderungen an der Struktur werden als neue Version angelegt; bereits vergangene Termine behalten ihre alte Struktur (P4).

Beispiele: `"2026-01-01"`.
- **`parameter`** — Parameter sind Platzhalter, die der Plantyp deklariert und die erst der konkrete Plan mit Werten fuellt (Zeitraum, Thema, Themenreihe …). Im Plantyp werden Parameter ueber '{parameter.<id>}' referenziert.
- **`gruppen`** — Diakonos-Gruppen, an die diese Planvorlage gebunden ist (Kennungen der Tabelle 'gruppe'). Ist mindestens eine Gruppe genannt, kommen als Personen nur noch Mitglieder dieser Gruppen in Frage (PERSONENPOOL) — die Planer sehen dann nur das, was sie sehen muessen. Leer/fehlend = alle Personen (bisheriges Verhalten). Mehrere Gruppen sind erlaubt (ODER).

Beispiele: `["Chor"]`, `["Chor", "Jugendchor"]`.
- **`inkl_untergruppen`** (Vorgabe: `False`) — Nur wirksam zusammen mit 'gruppen': true = Mitglieder aller Untergruppen der genannten Gruppen zaehlen zum Personenpool dazu (Untergruppe = eine Gruppe, deren 'obergruppe' die genannte Gruppe ist). false = nur die direkten Mitglieder der genannten Gruppen.

Beispiele: `true`.
- **`merkmale`** — siehe Abschnitt *Merkmale*.
- **`sammlungen`** — Eigene Sammlungen dieses Plantyps: benannte Listen von Dingen, die in Feldern als 'eintrag' ausgewaehlt werden (Bibelarbeiten, Spiele, Predigtreihen, Raeume …). Die Sammlung 'lieder' ist eingebaut (Psalmos-Liedgut) und braucht hier nicht angelegt zu werden.
- **`termine`** — siehe Abschnitt *Termine*.
- **`anlaesse`** — Anlaesse markieren einzelne Termine (Abendmahl, Kinderchor, Taufe, Erntedank …). Sie koennen auf die Struktur wirken: Felder ausblenden, hinzufuegen oder Regeln steuern. Anlaesse kommen manuell, aus dem Kalender oder aus Feiertagen.
- **`felder`** — siehe Abschnitt *Feld (rekursiv)*.
- **`terminreihen`** — Mehrere Terminreihen pro Plantyp, jede mit eigener Zeitachse und eigenen Feldern (z. B. 'gottesdienst' und 'probe'). Ist 'terminreihen' gesetzt, duerfen die Top-Level-Form 'termine' + 'felder' NICHT zusaetzlich verwendet werden (sie sind die KURZFORM fuer genau eine Reihe mit der Kennung 'standard'); beides gleichzeitig ist ein Fehler. Bei mehreren Reihen bekommen Feld-Pfade das Praefix '<reihe>:' (im Format 'reihe' nicht 'standard' => 'gottesdienst:team', die Kurzform-Reihe 'standard' bleibt ohne Praefix).
- **`rollen`** — Benannte Rollen, die in mehreren Feldern wiederverwendet werden koennen. Eine Rolle legt fest, WER fuer ein Feld in Frage kommt (ein Filter ueber Personen). Felder koennen eine Rolle entweder direkt inline angeben oder hier einmal benennen und per Kennung referenzieren.
- **`regeln`** — Regeln, die der Generator beim Fuellen des Plans beachten soll. Jede Regel ist ein benannter Baustein mit Parametern und einer Stufe (muss/sollte/hinweis). Welche Parameter ein Baustein akzeptiert, prueft die Baustein-Registry — nicht dieses Schema, damit neue Bausteine ohne Schema-Bruch dazukommen (P11).
- **`ansichten`** — Ausgaben des Plans: Tabelle, Raster, Ablauf, Personensicht, Druck, iCal-Export — mit Formatvorlagen fuer die Zellen. Ein Plantyp kann mehrere Ansichten haben (Aushang, Chorleiter, Beamer).
- **`uebernahme`** — Optionale Deklaration, dass dieser Plantyp Eintraege (bzw. Ablauf-Elemente) aus einem anderen Plan uebernehmen darf — z. B. uebernimmt der Weihnachtsmarkt die Lieder des Adventssingens inkl. Besetzung und weicht danach ab. Die Ausfuehrung kommt in einer spaeteren Ausbaustufe (PR4); hier wird nur deklariert und dokumentiert.


## Parameter

- **`id`** — siehe Abschnitt *Feld-Kennung*. (Pflicht)
- **`art`** — Art des Parameters: 'text' (freier Text, z. B. Thema), 'zahl', 'datum', 'zeitraum' (zwei Daten von/bis) oder 'auswahl' (einer aus einer festen Liste, mit `werte`). Hinweis: eine Sammlung wird NICHT ueber einen Parameter der Art 'sammlung' ausgewaehlt, sondern als eigene Sammlung mit `umfang: 'plan'` deklariert und direkt per Kennung referenziert. (Pflicht)
- **`name`** — Anzeigename des Parameters.
- **`werte`** — Feste Auswahlliste, nur bei art 'auswahl'. Die Werte sind zugleich die GESPEICHERTEN Kennungen (ASCII-Schreibweise ohne Umlaute, z. B. 'Maennerchor'); sie werden nie nachtraeglich umbenannt, sonst passen gespeicherte Plaene nicht mehr.
- **`anzeigenamen`** — Nur bei art 'auswahl': Anzeigename je Auswahlwert, z. B. {"Maennerchor": "Männerchor"}. Der Schluessel ist der gespeicherte Wert aus `werte`, der Text das, was die Oberflaeche zeigt. Fehlt ein Eintrag, wird der Wert selbst angezeigt.
- **`mehrfach`** — Ob der Parameter mehrere Werte gleichzeitig halten darf.


## Merkmale

- **`id`** — siehe Abschnitt *Feld-Kennung*. (Pflicht)
- **`name`** — Anzeigename des Merkmals.
- **`art`** — Art des Merkmalswerts: 'tag' (ja/nein, z. B. 'spielt Klavier'), 'auswahl' (ein Wert aus einer Liste, z. B. Stimme Sopran/Alt, mit `werte`), 'text', 'zahl', 'datum' oder 'person' (verweist auf eine Person, z. B. Standard-Dirigent eines Liedes — dann ueber `rolle` eingeschraenkt). (Pflicht)
- **`werte`** — Feste Auswahlliste, nur bei art 'auswahl'. Die Werte sind zugleich die GESPEICHERTEN Kennungen (ASCII-Schreibweise ohne Umlaute, z. B. 'Maennerchor'); sie werden nie nachtraeglich umbenannt, sonst passen gespeicherte Plaene nicht mehr.
- **`anzeigenamen`** — Nur bei art 'auswahl': Anzeigename je Auswahlwert, z. B. {"Maennerchor": "Männerchor"}. Der Schluessel ist der gespeicherte Wert aus `werte`, der Text das, was die Oberflaeche zeigt. Fehlt ein Eintrag, wird der Wert selbst angezeigt.
- **`mehrfach`** (Vorgabe: `False`) — Ob ein Traeger mehrere Werte gleichzeitig haben darf (z. B. Instrumente: mehrere zugleich).
- **`rolle`** — Nur bei art 'person': schraenkt ein, welche Personen als Wert in Frage kommen.
- **`quelle`** — Nur bei art 'auswahl': woher die Werte dieses Merkmals stammen. 'psalmos.kategorie' = die Werte sind die Psalmos-Liedkategorien (Tabelle 'liedkategorie'); die Zuordnung eines Liedes wird in 'lied_kategorie' gepflegt. Damit gibt es EINE Wahrheit fuer Themen: keine eigene Werteliste im Merkmal, sondern die bestehenden Liedkategorien. Ohne 'quelle' gelten die im Merkmal deklarierten 'werte'.


## Sammlung

- **`id`** — siehe Abschnitt *Feld-Kennung*. (Pflicht)
- **`name`** — Anzeigename der Sammlung. (Pflicht)
- **`beschreibung`** — Freie Beschreibung, was diese Sammlung enthaelt.
- **`umfang`** (Vorgabe: `gemeinde`) — Geltungsbereich der Sammlung: 'gemeinde' (Vorgabe — dauerhafte, gemeinde- oder plannuebergreifende Liste, z. B. Lieder, Raeume) oder 'plan' (gehoert zum einzelnen Plan und wird beim Anlegen/Vorbereiten befuellt, z. B. die Themenreihe einer Freizeit). Eine 'plan'-Sammlung ist der Weg, Themen vorbereitend in einen Plan zu laden — nicht ein gleichnamiger Parameter (der frueher fuer Verwirrung sorgte).

Beispiele: `"gemeinde"`, `"plan"`.


## Termine

- **`regel`** — Wiederholung im iCalendar-RRULE-Format, z. B. 'FREQ=WEEKLY;BYDAY=SU'. Gefuellt von einem 'zeitraum' (von-bis), dem der Plantyp angibt oder der Plan als Parameter '{parameter.<id>}' liefert.

Beispiele: `"FREQ=WEEKLY;BYDAY=SU"`.
- **`uhrzeit`** — Optionale (Start-)Uhrzeit der regelmaessigen Termine im Format HH:MM, z. B. die Gottesdienst-Uhrzeit '10:00'. Gilt fuer alle Termine der Reihe, ausser ein einzelner 'manuell'-Termin nennt eine eigene Uhrzeit.

Beispiele: `"10:00"`, `"19:30"`.
- **`von`** — Anfang des Zeitraums, in dem die Wiederholung gilt. Darf eine Parameterreferenz '{parameter.<id>}' sein.

Beispiele: `"2026-01-01"`, `"{parameter.zeitraum}"`.
- **`bis`** — Ende des Zeitraums, in dem die Wiederholung gilt. Darf eine Parameterreferenz '{parameter.<id>}' sein.

Beispiele: `"2026-12-31"`, `"{parameter.zeitraum}"`.
- **`zeitraum`** — Jeder Tag (oder bestimmte Wochentage, siehe `wochentage`) zwischen zwei Daten — typisch fuer eine Freizeit. Wert ist eine Parameterreferenz '{parameter.<id>}' auf einen Parameter der Art 'zeitraum'.

Beispiele: `"{parameter.zeitraum}"`.
- **`wochentage`** — Bei 'zeitraum': nur diese Wochentage einschliessen. Ohne Angabe gilt jeder Tag.
- **`kalender`** — Termine aus dem Diakronos-Kalender (Kronos) nach Kategorie oder Gruppe.
- **`feiertage`** — Benannte, bewegliche Feiertage, die als Termine eingefuegt werden (Karfreitag, Himmelfahrt, Heiligabend …). Jeder Feiertag setzt zugleich einen Anlass gleichen Namens.

Beispiele: `["karfreitag", "himmelfahrt", "heiligabend"]`.
- **`manuell`** — Einzelne Termine von Hand, die nicht aus einer Regel oder einem Kalender kommen.
- **`ausnahmen`** — Termine, die aus der berechneten Reihe entfallen. Zwei Formen: eine Liste einzeln genannter Termine ODER ein Objekt {feiertage: true}, das an Feiertagen automatisch ausfaellt (z. B. keine Probe an Feiertagen).

Beispiele: `[{"datum": "2026-12-25"}]`, `{"feiertage": true}`.
- **`abgeleitet`** — Termine, die relativ zu einer anderen Terminreihe berechnet werden (z. B. die Probe am Freitag vor dem Gottesdienst). Aendert sich der Ursprungstermin, zieht die abgeleitete Reihe nach.


## Manueller Termin

- **`datum`** — Datum dieses Termins. (Pflicht)
- **`name`** — Optionaler Anzeigename des Termins.
- **`uhrzeit`** — Uhrzeit im Format HH:MM, falls zutreffend.

Beispiele: `"19:30"`.
- **`anlaesse`** — Anlaesse, die auf diesen Termin zutreffen (Kennungen aus `anlaesse`).


## Ausnahme

- **`datum`** — Datum, das aus der berechneten Reihe entfaellt. (Pflicht)
- **`grund`** — Optionaler Grund der Ausnahme (erscheint dem Planenden als Hinweis).


## Anlass

- **`id`** — siehe Abschnitt *Feld-Kennung*. (Pflicht)
- **`name`** — Anzeigename des Anlasses.
- **`wirkung`** — Wie dieser Anlass auf die Struktur wirkt: Felder ausblenden ('ohne'), hinzufuegen ('mit') oder Regeln steuern ('regeln').


## Wirkung (eines Anlasses)

- **`ohne`** — Feld-Kennungen (oberste Ebene), die bei diesem Anlass entfallen. Beispiel: Kinderchor → kein Einsingen.

Beispiele: `["einsingen", "einueben"]`.
- **`mit`** — Zusaetzliche Felder, die nur bei diesem Anlass erscheinen.
- **`regeln`** — Regeln, die nur bei diesem Anlass greifen.
- **`bedingung`** — Optionale strukturierte Bedingung, unter der diese Wirkung erst greift (z. B. 'ohne' nur, wenn zugleich ein weiterer Anlass vorliegt). Gleiche Knoten-Grammatik wie die Feld-Bedingungen. Ohne Angabe gilt die Wirkung immer, wenn ihr Anlass gesetzt ist. Kann zudem die Feld-Kennung ein bedingungsbehaftetes Feld der Oberebene sein, das dann entfallt.


## Feld (rekursiv)

- **`id`** — siehe Abschnitt *Feld-Kennung*. (Pflicht)
- **`name`** — Anzeigename des Felds.
- **`art`** — Art des Felds: 'person' (genau eine Person in einer Rolle), 'personen' (eine oder mehrere Personen), 'eintrag' (ein Element aus einer Sammlung), 'text'/'zahl'/'datum'/'auswahl' (freie bzw. eingeschraenkte Angabe), 'gruppe' (enthaelt Unterfelder in `inhalt`), 'team' (eine Gruppe von Personen, ausgewaehlt ueber `teams`) oder 'ablauf' (eine geordnete, frei sortierbare Liste heterogener Elemente, deklariert in `elemente` — z. B. ein Programmablauf aus Liedern, Szenen und einer Predigt). (Pflicht)
- **`anzahl`** — Wie viele Instanzen dieses Felds je Termin geplant werden: eine feste Zahl oder einen Bereich 'min..max'. Ohne Angabe gilt 1.
- **`pflicht`** (Vorgabe: `True`) — Ob das Feld gefuellt sein muss. Ein nicht fuellbares Pflichtfeld bleibt leer und erzeugt eine Meldung (nie einen Fehler).
- **`zeit`** — Zeitfenster dieses Felds innerhalb des Termins, z. B. '10:30-12:00'.

Beispiele: `"10:30-12:00"`.
- **`bedingung`** — Strukturierte Bedingung, unter der dieses Feld erscheint (z. B. nur bei Anlass 'abendmahl' oder nur bei Variante 'regen'). Gleiche Knoten-Grammatik wie die Rollenfilter — KEIN freier Ausdrucks-String. Einzelknoten: 'anlass', 'wochentag', 'variante', 'parameter', 'feld_gesetzt', 'datum_ab', 'datum_bis', 'termin_nr'; verknuepft mit 'alle' (UND), 'eine' (ODER), 'nicht'.
- **`sammlung`** — Nur bei art 'eintrag': Kennung der Sammlung, aus der gewaehlt wird ('lieder' oder eine eigene). Darf eine Parameterreferenz '{parameter.<id>}' auf einen Sammlungsparameter sein.

Beispiele: `"lieder"`, `"{parameter.bibelarbeiten}"`.
- **`rolle`** — Nur bei art 'person'/'personen': welche Personen in Frage kommen. Entweder ein Filter direkt oder die Kennung einer benannten Rolle (mit '@' davor, z. B. '@mitarbeiter').
- **`teams`** — Nur bei art 'team': welche Teams (Diakonos-Gruppen) in Frage kommen. Entweder ein Objekt {gruppe_unter: '<Gruppentyp/Obergruppe>'} (alle Gruppen darunter) oder eine Liste von Team-Kennungen.

Beispiele: `{"gruppe_unter": "Musikteams"}`, `["Gruppe 1", "Gruppe 3"]`.
- **`mitglieder`** — Nur bei art 'team': optionaler Rollenfilter, der eine TEILMENGE der Teammitglieder auswaehlt (z. B. nur die Saenger des Teams).
- **`werte`** — Feste Auswahlliste, nur bei art 'auswahl'. Die Werte sind zugleich die GESPEICHERTEN Kennungen (ASCII-Schreibweise ohne Umlaute, z. B. 'Maennerchor'); sie werden nie nachtraeglich umbenannt, sonst passen gespeicherte Plaene nicht mehr.
- **`anzeigenamen`** — Nur bei art 'auswahl': Anzeigename je Auswahlwert, z. B. {"Maennerchor": "Männerchor"}. Der Schluessel ist der gespeicherte Wert aus `werte`, der Text das, was die Oberflaeche zeigt. Fehlt ein Eintrag, wird der Wert selbst angezeigt.
- **`mehrfach`** (Vorgabe: `False`) — Nur bei art 'auswahl': ob das Feld mehrere Werte zugleich halten darf (z. B. Ensemble 'Chor' UND Begleitung 'Orchester' — 'Mir/Orch' als Kombination aus Person und Ensemble).
- **`fuellen`** — Wie der Generator dieses Feld befuellt: manuell, reihum, der_reihe_nach, vorbelegen oder optimieren. Ohne Angabe gilt 'optimieren' bei Rollen-/Sammlungsfeldern, sonst 'manuell'.
- **`aus`** — Nur bei fuellen 'vorbelegen': woher der Wert kommt. Entweder ein Merkmal des Sammlungseintrags ('eintrag.<merkmal>', z. B. 'eintrag.dirigent') oder ein Feld-Pfad eines anderen Felds. Darf Parameterreferenzen enthalten.
- **`inhalt`** — Nur bei art 'gruppe': die Unterfelder dieser Gruppe.
- **`varianten`** — Nur bei art 'gruppe': alternative Auspraegungen, von denen EINE gilt (z. B. 'sonne'/'regen'); beide werden geplant, es gilt je Termin eine. Jede Variante ist ein Objekt {id, name?, inhalt?, bedingung?} ODER die Kurzform eines Strings (dann sind 'name', 'inhalt' und 'bedingung' leer). Ohne eigenes 'inhalt' gilt das der Gruppe; mit eigenem 'inhalt' ersetzt es das der Gruppe fuer diese Variante (die Regen-Variante darf so andere Felder haben).

Beispiele: `["sonne", "regen"]`, `[{"id": "regen", "name": "Regen", "inhalt": [{"id": "halle", "art": "text"}]}]`.
- **`teile`** — Nur bei art 'gruppe': Abschnitte, die nacheinander ablaufen (z. B. 'programm', 'abschluss'). Jeder Teil ist ein Objekt {id, name?, inhalt?, bedingung?} ODER die Kurzform eines Strings. Ohne eigenes 'inhalt' gilt das der Gruppe; mit eigenem 'inhalt' ersetzt es das der Gruppe fuer diesen Teil.

Beispiele: `["programm", "abschluss"]`, `[{"id": "abschluss", "name": "Abschluss", "bedingung": {"anlass": "abendmahl"}}]`.
- **`elemente`** — Nur bei art 'ablauf': die erlaubten Elementtypen des Ablaufs, in der Reihenfolge ihrer Deklaration. Jedes Element ist ein Objekt {typ, name?, nummeriert?, inhalt, bedingung?}; der `typ` muss innerhalb des Ablaufs eindeutig sein. Die Elemente eines konkreten Plans werden ueber eine stabile Element-Kennung angesprochen, nicht ueber ihre Position — Feldpfad-Format 'ablauf/<element_id>.<feld>' (bleibt beim Umsortieren stabil); Verweise in Regeln/Formaten nutzen 'ablauf.<typ>' fuer alle Elemente eines Typs.

Beispiele: `[{"typ": "lied", "nummeriert": true, "inhalt": [{"id": "lied", "art": "eintrag", "sammlung": "lieder"}]}, {"typ": "szene", "inhalt": [{"id": "titel", "art": "text"}]}]`.


## Rollen-Filter

- **`alle`** — UND-Verknuepfung: alle enthaltenen Kriterien muessen zutreffen.
- **`eine`** — ODER-Verknuepfung: mindestens eines der enthaltenen Kriterien muss zutreffen.
- **`nicht`** — Negation: das enthaltene Kriterium darf NICHT zutreffen.
- **`merkmal`** — Person hat das Merkmal mit dieser Kennung (aus 'merkmale.person').

Beispiele: `"klavier"`, `"dirigent"`.
- **`gruppe`** — Person gehoert zur Gruppe mit dieser Kennung.

Beispiele: `"Chor"`.
- **`anmeldung`** — Person hat sich fuer die Veranstaltung mit dieser Kennung angemeldet.

Beispiele: `"mitarbeiter"`.
- **`person`** — Eine konkrete Person (Kennung), z. B. der Gastredner.

Beispiele: `"gast"`.


## Benannte Rolle

- **`id`** — siehe Abschnitt *Feld-Kennung*. (Pflicht)
- **`name`** — Anzeigename der Rolle.
- **`filter`** — Der Filter, der diese Rolle auswaehlt. (Pflicht)


## Bedingung (strukturiert)

- **`alle`** — UND: alle enthaltenen Bedingungen muessen zutreffen.
- **`eine`** — ODER: mindestens eine der enthaltenen Bedingungen muss zutreffen.
- **`nicht`** — Negation: die enthaltene Bedingung darf NICHT zutreffen.
- **`anlass`** — Der Termin traegt den Anlass mit dieser Kennung.

Beispiele: `"abendmahl"`, `"kinderchor"`.
- **`wochentag`** — Der Termin faellt auf einen dieser Wochentage.

Beispiele: `["so"]`, `["so", "mi"]`.
- **`variante`** — Es gilt die Variante mit dieser Kennung (nur innerhalb eines 'gruppe'-Felds mit Varianten sinnvoll).

Beispiele: `"regen"`.
- **`parameter`** — Der Plan-Parameter mit dieser Kennung hat den angegebenen Wert.
- **`feld_gesetzt`** — Das Feld unter diesem Feld-Pfad ist gefuellt (Pfad wie 'abend.leitung' oder 'eintrag.dirigent').

Beispiele: `"abend.leitung"`, `"lieder"`.
- **`datum_ab`** — Der Termin liegt an oder nach diesem Datum (JJJJ-MM-TT).

Beispiele: `"2026-06-01"`.
- **`datum_bis`** — Der Termin liegt an oder vor diesem Datum (JJJJ-MM-TT).

Beispiele: `"2026-08-31"`.
- **`termin_nr`** — Regelmaessige Position des Termins in der Reihe (z. B. jeder 2. Termin).
- **`termin_im_monat`** — Der n-te Termin DER Reihe innerhalb seines Monats (negative Zahl = von hinten, z. B. -1 = der letzte Termin des Monats).

Beispiele: `1`, `2`, `-1`.


## Bedingung: Parameter-Vergleich

- **`id`** — siehe Abschnitt *Feld-Kennung*. (Pflicht)
- **`gleich`** — Wert, den der Parameter haben muss (String, Zahl oder Wahrheitswert).

Beispiele: `"herbst"`, `3`.


## Bedingung: Termin-Nummer

- **`jede`** — Jeder n-te Termin in der Reihe (z. B. 2 = jeder zweite Termin).

Beispiele: `2`. (Pflicht)


## Variante




## Variante (Objektform)

- **`id`** — siehe Abschnitt *Feld-Kennung*. (Pflicht)
- **`name`** — Anzeigename der Variante.
- **`inhalt`** — Eigene Unterfelder dieser Variante. Ohne Angabe gilt das 'inhalt' der Gruppe; mit Angabe ersetzt es dieses fuer diese Variante.
- **`bedingung`** — siehe Abschnitt *Bedingung (strukturiert)*.


## Teil




## Teil (Objektform)

- **`id`** — siehe Abschnitt *Feld-Kennung*. (Pflicht)
- **`name`** — Anzeigename des Teils.
- **`inhalt`** — Eigene Unterfelder dieses Teils. Ohne Angabe gilt das 'inhalt' der Gruppe; mit Angabe ersetzt es dieses fuer diesen Teil.
- **`bedingung`** — siehe Abschnitt *Bedingung (strukturiert)*.


## Terminreihe

- **`id`** — siehe Abschnitt *Feld-Kennung*. (Pflicht)
- **`name`** — Anzeigename der Reihe (z. B. 'Sänger').
- **`termine`** — siehe Abschnitt *Termine*. (Pflicht)
- **`felder`** — siehe Abschnitt *Feld (rekursiv)*. (Pflicht)
- **`anlaesse`** — Optionale, nur fuer diese Reihe gueltige Anlaesse (zusaetzlich zu den top-level Anlaessen).


## Abgeleitete Termine

- **`von`** — Kennung der anderen Terminreihe (oder 'standard' fuer die Kurzform-Reihe).

Beispiele: `"gottesdienst"`. (Pflicht)
- **`versatz`** — Versatz als vorzeichenbehaftete Dauer: +/- gefolgt von Zahl + Einheit (T Tag, W Woche, h Stunde, min Minute).

Beispiele: `"-2T"`, `"+1W"`, `"-3h"`. (Pflicht)
- **`nur_wenn`** — Optionale Bedingung, unter der ein abgeleiteter Termin ueberhaupt entsteht (z. B. keine Probe an Feiertagen).


## Ablauf-Element

- **`typ`** — Stabile Kennung des Elementtyps (z. B. 'lied', 'szene', 'predigt'); muss innerhalb desselben Ablaufs eindeutig sein. (Pflicht)
- **`name`** — Anzeigename des Elementtyps.
- **`nummeriert`** (Vorgabe: `False`) — Ob Elemente dieses Typs eine laufende Nummer (Attribut 'nr') tragen. Die Nummerierung zaehlt nur innerhalb desselben Elementtyps, nicht ueber alle Elemente.
- **`inhalt`** — Die Felder, die ein Element dieses Typs traegt (z. B. ein 'lied'-Element: das Lied selbst, Ensemble, Begleitung, Dirigent, Klavier). (Pflicht)
- **`bedingung`** — Optionale Bedingung, unter der ein Element dieses Typs ueberhaupt erscheint.


## Fremdes Feld (planuebergreifend)

- **`plantyp`** — Kennung des fremden Plantyps. (Pflicht)
- **`feld`** — Feld-Pfad im fremden Plantyp (z. B. 'einueben'). (Pflicht)


## Uebernahme (aus anderem Plan)

- **`erlaubt_von`** — Kennungen der Plantypen, aus denen uebernommen werden darf. (Pflicht)
- **`felder`** — Feld-Kennungen (bzw. -Pfade), die aus dem Quellplan uebernommen werden. (Pflicht)


## Regel

- **`baustein`** — Kennung des Regel-Bausteins (z. B. 'mindestabstand', 'max_pro_zeitraum'). Welche Parameter der Baustein akzeptiert, prueft die Baustein-Registry — nicht dieses Schema (P11). (Pflicht)
- **`stufe`** (Vorgabe: `sollte`) — 'muss' wird nie verletzt, 'sollte' wird moeglichst erfuellt (Verstoss sichtbar), 'hinweis' wird nur angezeigt.
- **`gewicht`** — Optionaler Gewichtungsfaktor, wenn mehrere 'sollte'-Regeln gegeneinander abgewogen werden.

Beispiele: `1.0`, `2.5`.


## Ansicht

- **`art`** — Art der Ansicht: 'tabelle' (Termin × Felder), 'raster' (Tag × Block mit Karten), 'ablauf' (ein Termin als Liste), 'meine_dienste' (Personensicht), 'druck' (Druckausgabe), 'ical' (Export), 'kalender' (Monats-Aushang: Monatsspalten, optional alle Tage inkl. leerer und KW-Spalte) oder 'programm' (Programmheft/Liedzettel eines 'ablauf'-Felds, A4-hoch, mit 'kopf'/'fuss' und einer Formatvorlage je Elementtyp). (Pflicht)
- **`name`** — Optionaler Name dieser Ansicht (z. B. 'Aushang').
- **`spalten`** — Welche Felder als Spalten erscheinen. Bei 'tabelle' eine Liste von Feld-Kennungen; bei 'kalender' eine Liste von Feld-Kennungen oder 'monat'.
- **`zeilen`** — Bei 'raster': was eine Zeile bildet (z. B. 'termin').
- **`alle_tage`** — Bei 'kalender': auch leere Tage als Zeilen zeigen (sonst nur Tage mit Termin).
- **`kw`** — Bei 'kalender': eine Kalenderwochen-Spalte anzeigen.
- **`format`** — Formatvorlagen fuer Zellen, Schluessel ist die Feld-Kennung (bei 'kalender'/mehreren Terminreihen ggf. 'reihe:feld'), Wert ein Muster mit Platzhaltern in geschweiften Klammern. Ein Platzhalter darf eine BEDINGUNG tragen: '{feld: text}' gibt 'text' nur aus, wenn 'feld' gesetzt ist (z. B. '{gaeste: + {gaeste.vorname}}').

Beispiele: `{"lieder": "{eintrag.buch} Nr.{eintrag.nummer} /{dirigent.kuerzel}/{klavier.kuerzel}/ {eintrag.titel}"}`, `{"gottesdienst": "{team.name}{gaeste: + {gaeste.vorname}}"}`.
- **`druck`** — Bei 'druck', 'kalender' und 'programm': Papierformat und Ausrichtung.

Beispiele: `"A4-quer"`, `"A4-hoch"`.
- **`kopf`** — Bei 'programm': die Ueberschrift des Programmhefts/Liedzettels, eine Formatvorlage mit Platzhaltern auf den Plan, den Termin und Plan-Parameter (z. B. '{plan.titel} {termin.datum}\n{parameter.motto}').
- **`fuss`** — Bei 'programm': die Fusszeile des Programmhefts/Liedzettels (Zitat, Bibelvers …), ebenfalls eine Formatvorlage auf Plan/Parameter (z. B. '{parameter.schlusswort}').


## Feld-Kennung




## Eingebaute Attribute (Stammdaten)

**Person** (immer vorhanden, brauchen keine Merkmal-Deklaration):

- `name` — Vollstaendiger Anzeigename (Nachname, Vorname) der Person.
- `vorname` — Vorname der Person.
- `nachname` — Nachname der Person.
- `kuerzel` — Kurzes Kuerzel der Person (z. B. fuer Formatvorlagen).
- `email` — E-Mail-Adresse der Person.

**Sammlung `lieder` (Psalmos-Liedgut)** (immer vorhanden, brauchen keine Merkmal-Deklaration):

- `titel` — Titel des Liedes (Psalmos: `titel`).
- `alternativtitel` — Alternativer Titel des Liedes (`alternativtitel`).
- `buch` — Gesangbuch des Liedes (Psalmos: `gesangbuch_nummer`-Grundlage).
- `nummer` — Nummer des Liedes im Gesangbuch (`gesangbuch_nummer`).
- `seite` — Seite im Gesangbuch/Heft, auf der das Lied steht (C4; darf fehlen — viele Programmhefte nennen keine Seite).
- `quelle` — Woher das Lied stammt: 'buch' (Liederbuch/Heft, mit Nummer/Seite), 'kopie' (Kopie/Einzelblatt, keine Nummer) oder 'ohne' (noch nichts gepflegt). Formatvorlagen nutzen das, um 'Nr.' nur bei einer echten Nummer zu zeigen.
- `anzeige` — Fertige, menschenlesbare Kennung des Liedes: 'Kopie', 'JN 1297', 'WH S. 150' — oder leer, wenn es keine Angabe gibt. Nie ein 'Nr.' ohne Nummer; die Formatvorlagen nutzen diesen Platzhalter (z. B. `{eintrag.anzeige}`).
- `ccli` — CCLI-Nummer (`ccli_nummer`).
- `zuletzt_gesungen` — Datum, wann das Lied zuletzt gesungen wurde (`zuletzt_gesungen`).
- `anzahl_gesungen` — Wie oft das Lied bereits gesungen wurde (`anzahl_gesungen`).
- `notiz` — Freie Notiz zum Lied (`notiz`).

**Jede Sammlung (Lieder und eigene)** (immer vorhanden, brauchen keine Merkmal-Deklaration):

- `titel` — Titel des Sammlungseintrags.
- `reihenfolge` — Position des Eintrags in seiner Sammlung (fuer 'der_reihe_nach').


## Meldungs-Codes

- `<a id="meldung-ablauf_ohne_elemente"></a>` `ablauf_ohne_elemente` — Ein 'ablauf'-Feld hat keine 'elemente'-Deklaration.
- `<a id="meldung-ableitung_zyklus"></a>` `ableitung_zyklus` — Eine Reihe leitet sich von sich selbst ab.
- `<a id="meldung-anzahl_umgekehrt"></a>` `anzahl_umgekehrt` — Ein anzahl-Bereich hat min > max.
- `<a id="meldung-attribut_ueberschattet"></a>` `attribut_ueberschattet` — Ein Merkmal verdeckt ein eingebautes Attribut.
- `<a id="meldung-doppelte_id"></a>` `doppelte_id` — Eine Kennung ist auf derselben Ebene mehrfach vergeben.
- `<a id="meldung-doppelter_elementtyp"></a>` `doppelter_elementtyp` — Ein Elementtyp ist innerhalb desselben Ablaufs mehrfach deklariert.
- `<a id="meldung-elemente_ohne_ablauf"></a>` `elemente_ohne_ablauf` — 'elemente' steht an einem Feld, das kein 'ablauf' ist.
- `<a id="meldung-format_platzhalter_unvollstaendig"></a>` `format_platzhalter_unvollstaendig` — Ein Format-Platzhalter nennt kein Attribut.
- `<a id="meldung-format_unbekannter_parameter"></a>` `format_unbekannter_parameter` — Ein Format-Platzhalter zeigt auf einen unbekannten Parameter.
- `<a id="meldung-format_unbekannter_termin"></a>` `format_unbekannter_termin` — Ein Format-Platzhalter zeigt auf ein unbekanntes Termin-Feld.
- `<a id="meldung-format_unbekanntes_attribut"></a>` `format_unbekanntes_attribut` — Ein Format-Platzhalter zeigt auf ein unbekanntes Attribut.
- `<a id="meldung-format_unbekanntes_feld"></a>` `format_unbekanntes_feld` — Ein Format-Platzhalter zeigt auf ein unbekanntes Feld.
- `<a id="meldung-fremder_plantyp"></a>` `fremder_plantyp` — Ein planübergreifender Verweis nennt den eigenen Plantyp.
- `<a id="meldung-fremder_plantyp_ungeprueft"></a>` `fremder_plantyp_ungeprueft` — Ein planübergreifender Verweis auf einen fremden Plantyp ist zur Prüfzeit nicht auflösbar.
- `<a id="meldung-gruppe_doppelt"></a>` `gruppe_doppelt` — Dieselbe Gruppe ist mehrfach an die Vorlage gebunden.
- `<a id="meldung-inhalt_ohne_gruppe"></a>` `inhalt_ohne_gruppe` — 'inhalt' an einem Feld, das weder gruppe noch eintrag ist.
- `<a id="meldung-inkl_untergruppen_ohne_gruppen"></a>` `inkl_untergruppen_ohne_gruppen` — Ein 'inkl_untergruppen' ohne gebundene 'gruppen' hat keine Wirkung.
- `<a id="meldung-kein_objekt"></a>` `kein_objekt` — Die Datei ist kein JSON-Objekt.
- `<a id="meldung-merkmal_nicht_deklariert"></a>` `merkmal_nicht_deklariert` — Ein Rollenfilter verweist auf ein nicht deklariertes Merkmal.
- `<a id="meldung-person_ohne_rolle"></a>` `person_ohne_rolle` — Ein Personen-Merkmal hat keine Rolle gesetzt.
- `<a id="meldung-quelle_ohne_auswahl"></a>` `quelle_ohne_auswahl` — Eine 'quelle' steht an einem Merkmal, das keine 'auswahl' ist.
- `<a id="meldung-regel_parameter"></a>` `regel_parameter` — Ein Regelparameter verletzt das Baustein-Schema.
- `<a id="meldung-rolle_ohne_filter"></a>` `rolle_ohne_filter` — Eine benannte Rolle ohne Filter.
- `<a id="meldung-rolle_ohne_person"></a>` `rolle_ohne_person` — Eine 'rolle' an einem Nicht-Personen-Feld.
- `<a id="meldung-rrule_expansion_zu_fein"></a>` `rrule_expansion_zu_fein` — Eine Wiederholungsregel vervielfacht die Termine je Tag (BYHOUR/BYMINUTE/BYSECOND/BYSETPOS).
- `<a id="meldung-rrule_freq_zu_fein"></a>` `rrule_freq_zu_fein` — Eine Wiederholungsregel wiederholt sich öfter als täglich.
- `<a id="meldung-rrule_interval_ungueltig"></a>` `rrule_interval_ungueltig` — Ein Wiederholungs-Abstand (INTERVAL) ist keine Zahl >= 1.
- `<a id="meldung-rrule_mehrzeilig"></a>` `rrule_mehrzeilig` — Eine Wiederholungsregel umfasst mehr als eine Zeile bzw. eine RRULE/EXRULE/RDATE-Kennung.
- `<a id="meldung-rrule_unlesbar"></a>` `rrule_unlesbar` — Eine syntaktisch ungültige RRULE.
- `<a id="meldung-rrule_unvollstaendig"></a>` `rrule_unvollstaendig` — Eine Wiederholungsregel ohne FREQ=.
- `<a id="meldung-schema"></a>` `schema` — Die Datei verletzt das JSON-Schema (Typ/Enum/Pflicht/Pattern).
- `<a id="meldung-team_ohne_teams"></a>` `team_ohne_teams` — Ein 'team'-Feld hat keine 'teams'-Angabe.
- `<a id="meldung-teile_ohne_gruppe"></a>` `teile_ohne_gruppe` — 'teile' an einem Nicht-Gruppen-Feld.
- `<a id="meldung-terminreihen_und_kurzform"></a>` `terminreihen_und_kurzform` — 'terminreihen' und die Kurzform 'termine'/'felder' stehen zugleich.
- `<a id="meldung-unbekannte_fuellstrategie"></a>` `unbekannte_fuellstrategie` — Eine nicht deklarierte Fuellstrategie.
- `<a id="meldung-unbekannte_reihe"></a>` `unbekannte_reihe` — Eine abgeleitete Reihe verweist auf eine unbekannte Reihe.
- `<a id="meldung-unbekannte_sammlung"></a>` `unbekannte_sammlung` — Ein eintrag verweist auf eine unbekannte Sammlung.
- `<a id="meldung-unbekannte_variante"></a>` `unbekannte_variante` — Eine Bedingung verweist auf eine unbekannte Variante.
- `<a id="meldung-unbekannter_anlass"></a>` `unbekannter_anlass` — Eine Bedingung verweist auf einen unbekannten Anlass.
- `<a id="meldung-unbekannter_baustein"></a>` `unbekannter_baustein` — Ein nicht deklarierter Regel-Baustein.
- `<a id="meldung-unbekannter_elementtyp"></a>` `unbekannter_elementtyp` — Ein Verweis (Regel/Format) nennt einen nicht deklarierten Elementtyp.
- `<a id="meldung-unbekannter_feiertag"></a>` `unbekannter_feiertag` — Ein Feiertag ist nicht im Katalog.
- `<a id="meldung-unbekannter_parameter"></a>` `unbekannter_parameter` — Ein für den Baustein nicht erlaubter Regelparameter.
- `<a id="meldung-unbekannter_parameter_bedingung"></a>` `unbekannter_parameter_bedingung` — Eine Bedingung verweist auf einen unbekannten Parameter.
- `<a id="meldung-unbekanntes_bezugsfeld"></a>` `unbekanntes_bezugsfeld` — Eine vorbelegen-Referenz 'bezug.<feld>' zeigt auf kein bekanntes Feld.
- `<a id="meldung-unbekanntes_feld"></a>` `unbekanntes_feld` — Eine Anlass-Wirkung blendet ein unbekanntes Feld aus.
- `<a id="meldung-unbekanntes_feld_bedingung"></a>` `unbekanntes_feld_bedingung` — Eine Bedingung verweist auf einen unbekannten Feld-Pfad.
- `<a id="meldung-unbekanntes_merkmal"></a>` `unbekanntes_merkmal` — Eine aus-Referenz verweist auf ein unbekanntes Merkmal.
- `<a id="meldung-unbekanntes_regel_feld"></a>` `unbekanntes_regel_feld` — Eine Regel verweist auf ein unbekanntes Feld.
- `<a id="meldung-variante_ohne_gruppe"></a>` `variante_ohne_gruppe` — Eine Varianten-Bedingung ausserhalb einer Varianten-Gruppe.
- `<a id="meldung-varianten_ohne_gruppe"></a>` `varianten_ohne_gruppe` — 'varianten' an einem Nicht-Gruppen-Feld.
- `<a id="meldung-versatz_unlesbar"></a>` `versatz_unlesbar` — Der Versatz eines abgeleiteten Termins ist keine gültige Dauer.
- `<a id="meldung-wochentag_langname"></a>` `wochentag_langname` — Ein Wochentag ist als langer Name statt als Kurzform geschrieben.


## Feldarten (B3)

| art | Bedeutung | Beispiele |
|---|---|---|
| `person` | genau eine Person in einer Rolle (z. B. Einsingen leiten). | Einsingen, Tagesleitung |
| `personen` | eine oder mehrere Personen in einer Rolle (Anzahl steuerbar). | Solo, Leitung |
| `eintrag` | ein Element aus einer Sammlung (z. B. ein Lied, eine Bibelarbeit). | Lied, Bibelarbeit, Spiel |
| `text` | freier Text (z. B. Thema, Bibelstelle). | Thema, Bibelstelle, Raum |
| `zahl` | eine Zahl. | Anzahl Stuehle |
| `datum` | ein Datum. | Frist |
| `auswahl` | genau ein Wert aus einer festen Liste (`werte`). | Ort |
| `gruppe` | tragendes Untergeruest: enthaelt Unterfelder (`inhalt`), optional `varianten` und `teile`. | Frohe Stunde |
| `team` | eine Gruppe von Personen (Diakonos-Gruppe), ausgewaehlt ueber `teams`; optional `mitglieder` als Teilmenge. | Musikteam, Saenger |
| `ablauf` | geordnete, frei sortierbare Liste heterogener Elemente (`elemente`, je Typ mit eigenem `inhalt` und optional `nummeriert`); offenes Ende via `anzahl: '1..*'`. | Programmablauf, Gottesdienst-Ablauf |


## Fuellstrategien (B7)

| strategie | Wirkung | Beispiel |
|---|---|---|
| `manuell` | nie automatisch — nur von Hand. | Lieder, die neu eingeuebt werden |
| `reihum` | Personen der Rolle der Reihe nach, Abwesende werden uebersprungen. | Einsingen, Tagesleitung |
| `der_reihe_nach` | Sammlungseintraege in ihrer Reihenfolge. | Bibelarbeit Tag 1..n |
| `vorbelegen` | Wert aus einem anderen Feld/Merkmal uebernehmen (`aus`). | Lied → Dirigent/Klavier |
| `optimieren` | bestmoegliche Wahl nach allen Regeln (Standard). | Liedauswahl, Prediger |


## Feiertage (Katalog)

| Schluessel | Name | Art |
|---|---|---|
| `aschermittwoch` | Aschermittwoch | oster |
| `palmsonntag` | Palmsonntag | oster |
| `gruendonnerstag` | Gründonnerstag | oster |
| `karfreitag` | Karfreitag | oster |
| `ostersonntag` | Ostersonntag | oster |
| `ostermontag` | Ostermontag | oster |
| `himmelfahrt` | Christi Himmelfahrt | oster |
| `pfingstsonntag` | Pfingstsonntag | oster |
| `pfingstmontag` | Pfingstmontag | oster |
| `fronleichnam` | Fronleichnam | oster |
| `neujahr` | Neujahr | fest |
| `silvester` | Silvester | fest |
| `1_advent` | 1. Advent | advent |
| `2_advent` | 2. Advent | advent |
| `3_advent` | 3. Advent | advent |
| `4_advent` | 4. Advent | advent |
| `heiligabend` | Heiligabend | fest |
| `1_weihnachtstag` | 1. Weihnachtstag | fest |
| `2_weihnachtstag` | 2. Weihnachtstag | fest |
| `buss_und_bettag` | Buß- und Bettag | advent |
| `erntedank` | Erntedank | erntedank |


## Regel-Bausteine (B8)

Jeder Baustein hat eine Stufe (`muss`/`sollte`/`hinweis`) und optional ein `gewicht`. Die unten genannten Parameter werden gegen die Registry geprueft — neue Bausteine kommen in der Registry hinzu, ohne das Hierarchie-Schema zu brechen.

### `abwesenheit_beachten`

Abwesenheiten respektieren (Urlaub, Krankheit, abgemeldet).

Personen, die im fraglichen Zeitraum abwesend sind, werden nicht eingeplant. Ist das Feld ein Pflichtfeld und es findet sich kein Ersatz, bleibt es leer und es erscheint eine verstaendliche Meldung — nie ein Absturz.

**Parameter:**

- (keine Parameter)

**Beispiel:**

```json
{
  "baustein": "abwesenheit_beachten",
  "stufe": "muss"
}
```

### `mindestabstand`

Gleicher Eintrag / gleiche Person nicht oefter als im Mindestabstand.

Haelt einen zeitlichen Mindestabstand zwischen Wiederholungen desselben Eintrags bzw. derselben Person ein (z. B. ein Lied nicht oefter als alle 8 Wochen).

**Parameter:**

- `feld` (Pflicht): Kennung des Felds (oder Feld-Pfads), auf das die Regel wirkt.
- `wochen` (Pflicht): Mindestabstand in Wochen.
- `fuer`: Ob der Abstand je Eintrag oder je Person gilt.
- `auch_in`: Kennungen weiterer Plantypen, deren gleiche Eintraege in die gemeinsame Abstands-Historie mitzaehlen (z. B. ein Lied im Programm zaehlt fuer den Chorplan-Abstand).

**Beispiel:**

```json
{
  "baustein": "mindestabstand",
  "feld": "lieder",
  "wochen": 8,
  "stufe": "sollte"
}
```

### `max_pro_zeitraum`

Hoechstzahl je Zeitraum (z. B. max. 2 Predigten/Monat).

Begrenzt, wie oft eine Person (oder eine Rolle insgesamt) in einem Zeitraum eingeplant werden darf.

**Parameter:**

- `anzahl` (Pflicht): Anzahl (z. B. Hoechstzahl oder Mindestzahl).
- `zeitraum` (Pflicht): Bezugszeitraum fuer die Hoechst-/Mindestzahl.
- `rolle`: Rolle bzw. Personen-Filter, auf den die Regel wirkt (Objekt-Filter oder '@'-Referenz).
- `person`: Kennung einer einzelnen Person (alternativ zu 'rolle').

**Beispiel:**

```json
{
  "baustein": "max_pro_zeitraum",
  "anzahl": 2,
  "zeitraum": "monat",
  "stufe": "sollte"
}
```

### `min_pro_zeitraum`

Mindestzahl je Zeitraum (z. B. mind. 1 Diensterfahrung/Monat).

Stellt sicher, dass eine Person (oder Rolle) in einem Zeitraum mindestens eine bestimmte Anzahl Dienste uebernimmt.

**Parameter:**

- `anzahl` (Pflicht): Anzahl (z. B. Hoechstzahl oder Mindestzahl).
- `zeitraum` (Pflicht): Bezugszeitraum fuer die Hoechst-/Mindestzahl.
- `rolle`: Rolle bzw. Personen-Filter, auf den die Regel wirkt (Objekt-Filter oder '@'-Referenz).

**Beispiel:**

```json
{
  "baustein": "min_pro_zeitraum",
  "anzahl": 1,
  "zeitraum": "monat",
  "stufe": "sollte"
}
```

### `gleich_verteilen`

Fairness: Dienste moeglichst gleichmaessig verteilen (Rolle oder Team-Feld).

Sorgt dafuer, dass die Dienste gleichmaessig verteilt werden — entweder ueber eine Rolle (Filter ueber Personen) oder ueber ein Feld (z. B. ein 'team'-Feld, dessen Teams fair rotieren). Vorbelegte/abgeleitete Eintraege zaehlen standardmaessig nicht; vorbelegte_mitzaehlen=true schliesst diese Kopien ein. Historie ohne Herkunftsangabe zaehlt als eigene Entscheidung.

**Parameter:**

- `rolle`: Rolle bzw. Personen-Filter, der fair verteilt wird (alternative zu 'feld').
- `feld`: Feld-Kennung (z. B. ein 'team'-Feld), das fair verteilt wird (alternative zu 'rolle').
- `vorbelegte_mitzaehlen`: Auch vorbelegte und abgeleitete Eintraege als Dienste zaehlen (Standard: nur eigene Entscheidungen).

**Beispiel:**

```json
{
  "baustein": "gleich_verteilen",
  "rolle": {
    "anmeldung": "mitarbeiter"
  },
  "stufe": "sollte"
}
```

### `nicht_gleichzeitig`

Zwei Felder nicht von derselben Person gleichzeitig (z. B. Dirigat + Klavier).

Verhindert, dass dieselbe Person in einem Termin zwei benannte Felder zugleich besetzt.

**Parameter:**

- `felder` (Pflicht): Die Feld-Kennungen, die nicht dieselbe Person tragen duerfen.

**Beispiel:**

```json
{
  "baustein": "nicht_gleichzeitig",
  "felder": [
    "dirigent",
    "klavier"
  ],
  "stufe": "muss"
}
```

### `zusammen`

Personen immer gemeinsam einteilen (z. B. Ehepaar).

Haelt zwei Personen immer zusammen: wird die eine eingeplant, auch die andere.

**Parameter:**

- `personen` (Pflicht): Die Kennungen der Personen, die zusammen bleiben.

**Beispiel:**

```json
{
  "baustein": "zusammen",
  "personen": [
    "anna",
    "bruno"
  ],
  "stufe": "muss"
}
```

### `nicht_zusammen`

Personen nie gemeinsam einteilen.

Verhindert, dass zwei Personen im selben Termin eingeplant werden.

**Parameter:**

- `personen` (Pflicht): Die Kennungen der Personen, die sich ausschliessen.

**Beispiel:**

```json
{
  "baustein": "nicht_zusammen",
  "personen": [
    "anna",
    "bruno"
  ],
  "stufe": "muss"
}
```

### `vorher_geuebt`

Ein Eintrag muss erst N mal geuebt sein, bevor er gesungen/gespielt wird.

Erlaubt einen Eintrag erst, wenn er zuvor eine bestimmte Anzahl Mal in einem Uebungsfeld erschienen ist. Die Uebung kann im selben Plantyp liegen ('uebungsfeld') ODER in einem ANDEREN Plantyp ('uebung', planuebergreifend, z. B. die Lieder eines Programms muessen zuvor im Chorplan geuebt sein — {'plantyp': 'chorplan', 'feld': 'einueben'}). 'auch_in' zaehlt zusaetzlich gleiche Eintraege in anderen Plantypen zur gemeinsamen Historie (z. B. ein Lied im Programm zaehlt fuer den Chorplan-Abstand). Der Generator fuellt optimierte Uebungsfelder vorausschauend anhand der festgelegten Einsaetze (auch aus expliziten Bezugsplaenen), priorisiert nach Frist. vorlauf_wochen begrenzt neue Uebungen; Vorgabe max(4, mindestens).

**Parameter:**

- `feld` (Pflicht): Kennung des Felds (oder Feld-Pfads), auf das die Regel wirkt.
- `uebungsfeld`: Kennung des Felds im SELBEN Plantyp, das als Uebung zaehlt (Alternative zu 'uebung').
- `uebung`: Planuebergreifender Verweis auf das Uebungsfeld in einem anderen Plantyp (Alternative zu 'uebungsfeld').
- `auch_in`: Kennungen weiterer Plantypen, deren gleiche Eintraege mitzaehlen.
- `mindestens` (Pflicht): Mindestzahl der Uebungen vor dem Einsatz.
- `vorlauf_wochen`: Neue Uebungen in diesem Vorlauf vor dem Einsatz planen; Vorgabe max(4, mindestens) Wochen. Vorhandene aeltere Uebungen zaehlen weiterhin.

**Beispiel:**

```json
{
  "baustein": "vorher_geuebt",
  "feld": "lieder",
  "uebungsfeld": "einueben",
  "mindestens": 2
}
```

### `passend_zum_anlass`

Nur Eintraege mit passendem Merkmal am entsprechenden Anlass.

Beschraenkt die Auswahl an einem Anlass auf Eintraege, deren Merkmal zum Anlass passt (z. B. Erntedank-Lied an Erntedank).

**Parameter:**

- `feld` (Pflicht): Kennung des Felds (oder Feld-Pfads), auf das die Regel wirkt.
- `merkmal` (Pflicht): Merkmal des Eintrags, das zum Anlass passen muss.

**Beispiel:**

```json
{
  "baustein": "passend_zum_anlass",
  "feld": "lieder",
  "merkmal": "thema"
}
```

### `verfuegbarkeit`

Feste Verfuegbarkeitsmuster einer Person oder eines Teams beachten.

Beruecksichtigt ein festes zeitliches Muster, wann eine Person ODER ein Team verfuegbar ist (z. B. nur 1. Sonntag im Monat). Das Muster ist entweder ein kurzes Kuerzel wie '1.So' oder ein strukturiertes Objekt, z. B. {'termin_im_monat': 1} (jeder 1. Termin der Reihe im Monat).

**Parameter:**

- `person`: Kennung der Person (alternative zu 'team').
- `team`: Kennung des Teams (alternative zu 'person').
- `muster` (Pflicht): Verfuegbarkeitsmuster: Kurzform-String ('1.So') oder Objekt {'termin_im_monat': n}.

**Beispiel:**

```json
{
  "baustein": "verfuegbarkeit",
  "team": "Gruppe 3",
  "muster": {
    "termin_im_monat": 1
  },
  "stufe": "muss"
}
```

