# Plan-Rahmen — HTTP-API

Alle Pfade: `/api/method/diakronos.planrahmen.api.<name>`. Alle Aufrufe verlangen
Anmeldung; Guest erhält 401 (`SessionExpired`). Fehlende Objekt- oder Rollenrechte bleiben 403. Schreibende Aufrufe verlangen POST und den bestehenden
`X-Frappe-CSRF-Token` der Sitzung; GET ist 405, fehlender Token 417
`CSRFTokenError`. Kein neuer Authentifizierungsweg, kein Zugriff über Resource-CRUD.
Eine Anfrage ist eine Transaktion: Fehler rollen auch vorausgegangene Teiländerungen zurück.

## Formate

Erfolg: `{"message": <Ergebnis>}`. Datumswerte sind ISO `YYYY-MM-DD`, Zeiten ISO.
IDs sind UUIDs; `plantyp` akzeptiert zusätzlich den stabilen Definitionsschlüssel.
Eintragswerte sind rohe JSON-Werte (Person/Lied/Team = Kennung, Personen = Liste,
Text/Zahl/Datum/Auswahl = entsprechender Wert), nicht `{art, wert}`-Hüllen.
`nur_vorschau` muss ein JSON-Bool sein. `parameter` ist ein JSON-Objekt.

Fachfehler, HTTP 417:

```json
{"message":"Plan-Rahmen-Prüfung fehlgeschlagen.","exc_type":"ValidationError",
 "exception":"ValidationError","meldungen":[{"pfad":"/felder/0/art",
 "code":"schema.enum","meldung":"Unbekannte Feldart.","hinweis":"Referenz beachten.","stufe":"fehler"}]}
```

Plantyp-Prüfmeldungen kommen unverändert aus `pruefung.py`, inklusive Doku-Anker.
`plantyp_pruefen` selbst antwortet 200 mit `gueltig` und `meldungen`; Speichern einer
ungültigen Definition liefert 417. Unberechtigte Objektzugriffe sind 403.

## Lesende Endpunkte (GET oder POST)

| Name | Argumente | Ergebnis |
|---|---|---|
| schema_holen | – | plantyp-1.json mit x-regel-bausteine (Beschreibung und parameter_schema aus Registry) |
| doku_holen | name=REFERENZ | Markdown; REFERENZ, LEITFADEN, KONZEPT, KOCHBUCH, AGENT-ONBOARDING, API |
| kochbuch_liste | – | geprüfte Beispielkennungen |
| kochbuch_holen | name | vollständige geprüfte Definition; nur Kennungen aus kochbuch_liste |
| einrichten_rechte | – | darf_anlegen, bereiche, admin; auch ohne vorhandene Plantypen |
| stammdaten_holen | plantyp, plan? | deklarierte Merkmale, Personen, Gruppen, eigene Sammlungen und Liedmerkmale |
| plantyp_pruefen | definition | gueltig, meldungen |
| plantyp_versionen_liste | plantyp | Versionen inkl. Definition und gueltig_ab |
| plantypen_liste | – | Plantypen mit neuester Definition und Rechte-Flags; **nur berechtigte Planer**, sonst 403 |
| plan_holen | plan | Plan/Termine/Einträge; Mitglieder erhalten nur letzten veröffentlichten Snapshot |
| plan_stand_version | plan | PF1: billiger Versionsstempel (`plan`, `version`, `darf_bearbeiten`) für den Browser-Cache; nur Zähl-/Maximalabfragen über Termine und Einträge |
| feld_kandidaten | plan, termin, feld_pfad | rollengefilterte Kandidaten mit Engine-Bewertung; **nur Plan-Editor**, sonst 403 |
| plaene_liste | – | ausschließlich sichtbare Plantitel/IDs/Status und Stammdaten |
| meine_dienste | – | eigene Personenzuordnungen aus veröffentlichten Snapshots |
| termin_struktur | plan, termin | fixierte Versionsdefinition, für Planer aktive Slots |
| termin_strukturen | plan | PF1: alle Termin-Strukturen in EINEM Aufruf (`{plan, strukturen:[{termin, version, slots}]}`); ersetzt die N+1-Abfolge der Planseite, je Termin identisch zu `termin_struktur` |
| bedarf | plantyp, plan? | Datenabdeckung aus der DB |
| trockenlauf | definition, parameter={}, ab?, wochen=8, seed=0 | Einträge, Bedarf, Meldungen, Verstöße; keine Speicherung |

Dokumente und Schema werden ausschließlich mit `importlib.resources` aus dem
installierten Python-Paket geladen. `doku_holen` erlaubt keine Dateipfade.

`plantypen_liste` liefert pro Plantyp `{id, schluessel, name, bereich, aktiv,
created, modified, letzte_version, darf_plan_anlegen, darf_bearbeiten}`;
`letzte_version` ist die Version mit der höchsten Versionsnummer (`null` ohne
Versionen) und enthält die vollständige Definition. `darf_plan_anlegen` gilt
bei Admin oder Dienstbereichsverantwortung; `darf_bearbeiten` zusätzlich bei
eigener Planverantwortung für mindestens einen Plan dieses Plantyps.
Sichtbarkeit: eigene Bereiche (Admin: alle) **plus** die Plantypen eigener
verantwortlicher Pläne; ohne jede Verantwortung 403.

UI2 ergänzt `darf_plantyp_bearbeiten` (Admin/Bereichsverantwortung, nicht bloße
Planverantwortung). Lesen, Bedarf und plan-eigene Sammlungen einschließlich
ihrer Merkmalwerte erlauben mit eigener Plan-ID auch Planverantwortung.
Gemeindeweite Personen-/Liedmerkmale und Sammlungen benötigen weiterhin
Bereichsverantwortung oder Adminrechte. `darf_globale_stammdaten_bearbeiten`
in `stammdaten_holen` unterscheidet diese Fähigkeiten für die UI. Plan und Plantyp müssen
zusammenpassen. Planbezogene Sammlungen werden ohne Plan-ID nicht ausgeliefert.
Stammdaten umfassen nur deklarierte Merkmale, keine E-Mails oder Abwesenheitsgründe.
Eigene Sammlungseinträge enthalten `kennung`, `titel`, minimierte `daten`,
`reihenfolge`, `aktiv`, `merkmale` (auch inaktive Einträge zur Reaktivierung).
Titelpflege ergänzt vorhandene Daten, ohne verborgene Bestandsattribute zu löschen.

`trockenlauf` erlaubt neue ungespeicherte Definitionen nur für Admin oder
Verantwortliche von `definition.bereich`; bestehende Typen behalten ihren
gespeicherten Rechtescope, Bereichswechsel bleibt Admins vorbehalten.
Die Antwort ergänzt stabile temporäre Termin-IDs, `plantyp_version=probelauf`,
Eintragsverweise `termin` sowie die minimierte `anzeige`-Map für UI1-Ansichten.
Es werden weder Plantypen noch Pläne, Termine, Einträge oder Verlauf gespeichert.

`feld_kandidaten` (Argumente `plan`, `termin`, `feld_pfad`) liefert
`{feld_pfad, art, kandidaten, meldungen}` und verlangt Planbearbeitungsrecht.
Kandidaten je Feldart: `person`/`personen` → Engine-Rollenfilter mit
`{kennung, anzeige, name, vorname, nachname, kuerzel, abwesend, merkmale,
bewertung}`; `team` → `{kennung, anzeige, mitglieder, bewertung}`;
`eintrag` → `{kennung, anzeige, titel, buch, nr, seite, merkmale, bewertung}`;
`auswahl` → deklarierte Werte als String-Liste. `merkmale` enthält ausschließlich
die im Plantyp deklarierten Merkmale. `bewertung` ist die Engine-Regelbewertung
des Slots je Kandidat: `{zulaessig, strafe, meldungen}`; `abwesend` nennt ohne
Grund, ob am Termin eine Abwesenheit liegt. `meldungen` trägt die
Bedarfswarnungen der Engine dieses Feldes (`ok`→`hinweis`,
`eingeschraenkt`→`sollte`, `blockiert_automatik`→`muss`) sowie
`kandidaten.leer` bei leerer Kandidatenmenge. Keine E-Mail-Adressen, keine
Abwesenheitsgründe. Unbekannter `feld_pfad`/fremder Termin → 417.

## Schreibende Endpunkte (nur POST)

`plan_holen` ergänzt den berechtigten Stand um `darf_bearbeiten` und `anzeige`:
eine Kennungsmap ausschließlich für eingeteilte Werte. Personen liefern Name
und Kürzel, Teams ihren Namen, Sammlungseinträge Titel/Buch/Nummer/Seite.
Sammlungseinträge liefern zusätzlich die als Sammlungsmerkmale deklarierten
Attribute direkt als Format-Schlüssel (z.B. `stelle` für `{eintrag.stelle}`),
identisch in `anzeige` und `feld_kandidaten`. Gepflegte Merkmalswerte haben
Vorrang vor freien Stammdatenattributen; nicht deklarierte freie Attribute
werden nicht ausgegeben. Das gilt auch für die Mitgliedsansicht, aber nur
für eingeteilte Sammlungseinträge; keine zusätzlichen Personenmerkmale.
Mitglieder bekommen diese Daten ausschließlich für den veröffentlichten Stand,
keine Kandidaten oder Personenmerkmale. `plaene_liste` liefert zusätzlich
Plantyp/Bereich, Zeitraum und das Bearbeitungsrecht je Plan.

`ablauf_aendern(plan, termin, feld, aktion, element_typ?, element_id?, position?)`
verlangt Planbearbeitungsrecht. Aktionen: `hinzufuegen` (deklarierter Typ, neue
UUID), `verschieben` (stabile ID, nullbasierte Position), `loeschen` (entfernt
auch zugehörige Einträge). Aktive Struktur und Argumente werden geprüft;
Rückgabe `{element_id, ablauf, gruppe_id}`. Eine gemeinsame Verlaufsgruppe
ermöglicht Undo einschließlich gelöschter Einträge. Fremde Elemente/Termine
und ungültige Aktionen liefern strukturierte Fachfehler (417), fehlendes
Bearbeitungsrecht 403. Die Engine wird nicht verändert.

| Name | Argumente | Ergebnis |
|---|---|---|
| plantyp_speichern | definition, gueltig_ab, kommentar? | neue unveränderliche Version |
| plan_anlegen | plantyp, titel, von, bis, parameter={}, verantwortlich? | Plan-ID und Kopfdaten |
| plan_generieren | plan, nur_vorschau=false, seed=0 | diff, meldungen, verstoesse, gruppe_id |
| eintrag_setzen | plan, termin, feld_pfad, wert | fixierter Eintrag, Regelmeldungen, gruppe_id |
| eintrag_loesen | plan, termin, feld_pfad | hebt Fixierung auf; gruppe_id |
| platz_hinzufuegen | plan, termin, feld_pfad | legt optionalen Mehrfachplatz `<feld>[n]` an; feld_pfad, art, gruppe_id |
| undo | plan | rückgängig gemachte und neue Auditgruppe |
| veroeffentlichen | plan | Snapshot gespeichert, Wert-Diff zum letzten veröffentlichten Stand |
| merkmale_pflegen | plantyp, werte, plan? | gruppe_id |
| sammlung_pflegen | plantyp, sammlung, eintraege, plan? | Sammlungseinträge, gruppe_id |
| abwesenheit_melden | mitglied, von, bis, grund='', plantyp?, plan? | Abwesenheit, gruppe_id |
| lied_speichern | plantyp, lied, daten, plan? | Lied umbenennen (titel) bzw. Nummer/Buch/Seite ändern (ST2) |
| lied_material_hinzufuegen | lied, art, dateiname, datei_url, stimme?, beschreibung?, plantyp?, plan? | Material (Noten/Audio/Notensatz) an der Standardfassung (ST2) |
| lied_material_loeschen | lied, material, plantyp?, plan? | entfernt Material (Child-Zeile + Anhang) (ST2) |
| sammlungsmerkmal_werte_pflegen | plantyp, schluessel, aktion, wert, neu?, plan? | Auswahl-/Tag-Werte pflegen (ST2) |

### ST2 — Lieder pflegen

`merkmal_kandidaten(plantyp, schluessel, plan?)` (lesend) liefert die Personen,
die die Rolle eines deklarierten **Listen-Personen-Merkmals** erfüllen — z. B.
`merkmale.lieder.dirigent.rolle = {merkmal: 'dirigent'}` → nur Personen mit
Fähigkeit „dirigiert". Ergebnis `{schluessel, ziel, art, rolle, kandidaten,
hinweis}`; `hinweis` erscheint bei leerer Auswahl („Noch niemand ist als … markiert
— Fähigkeiten pflegen"). Rechte wie `stammdaten_holen`.

`lied_speichern` schreibt ausschließlich die Psalmos-Tabelle `Lied` (eine
Wahrheit): erlaubt sind `titel`, `alternativtitel`, `gesangbuch_nummer`, `buch`,
`seite`, `ccli_nummer`, `notiz`; ein leerer Titel wird abgelehnt. Recht:
Musikverantwortliche (Psalmos) **oder** Bereichs-/Planverantwortliche der
Planvorlage.

Material läuft über zwei Schritte: erst `upload_file` (Multipart; erlaubt jetzt
PDF, Audio mp3/m4a/ogg/wav und Notensatz mscz/mscx/musicxml/mxl; Audio/Notensatz
bis `MAX_UPLOAD_BYTES_AUDIO`), dann `lied_material_hinzufuegen` mit der
gelieferten `file_url`. `art` ∈ `{noten_pdf, audio, musescore, musicxml}` und muss
zur Endung passen; die Dateien werden server- und dateitypgeprüft. Material hängt
an der **Standardfassung** des Liedes (wird bei Bedarf angelegt) und wird über
`/files/<name>` ausgeliefert (Audio inline, abspielbar).

P1-10: `plantyp` ist bei `lied_material_hinzufuegen`/`-loeschen` **optional**.
Mit Plantyp gilt das Planer-Recht, ohne (Aufruf aus dem Lied-Detail) die
Psalmos-Regel (Musikverantwortliche/Admin). Die hochgeladene Datei wird an die
Liedfassung gebunden (`attached_to_doctype='Liedfassung'`), damit sie jede
angemeldete Person öffnen kann (nicht nur der Hochlader). `lied_material_loeschen`
erwartet die Kennung der Material-**Zeile** (`material`), die die Listen-Antwort
als `material` mitliefert (nicht die Anhang-UUID).

`sammlungsmerkmal_werte_pflegen(plantyp, schluessel, aktion, wert, neu?)` pflegt
die gemeindeweiten Auswahl-/Tag-Werte eines Listen-Merkmals (`pr_merkmal.definition`).
`aktion` ∈ `{hinzufuegen, umbenennen, entfernen}`. Umbenennen aktualisiert
vorhandene Zuordnungen; Entfernen löscht die Zuordnungen und meldet `betroffen`
(„wird bei N Liedern verwendet"). Der Plantyp liefert nur Startwerte.

`werte`: Liste aus `{ziel, schluessel, ziel_id, wert}`; Ziel `person` oder
`sammlung:<schluessel>`. Nur deklarierten Merkmale des Plantyps dürfen gepflegt
werden; Schlüssel mit inkompatibler Art werden nicht umgedeutet.

### ST3 — Gruppenbindung, Personenpool, Themen

Eine Plantyp-Version kann über `gruppen` (Liste von Gruppen-Kennungen) und
`inkl_untergruppen` an Diakonos-Gruppen gebunden sein. Ist mindestens eine
Gruppe gebunden, kommen als Personen (Personen-Felder, Rollenfilter,
Stammdaten-Personenmatrix, Fähigkeiten-Pflege, Abwesenheiten) nur noch
Mitglieder dieser Gruppen in Frage — zentral in der Datenquelle, ohne
Bindung unverändert. `stammdaten_holen` liefert dazu `pool` (`gruppen`,
`namen`, `inkl_untergruppen`, `anzahl`) und `darf_vorlage_bearbeiten`
(nur Admin/Bereichsverantwortung — Gruppenverantwortliche dürfen die Vorlage
nicht ändern). Der Personenpool liefert nur Name/Kürzel/Fähigkeiten, keine
Kontaktdaten und keine Abwesenheitsgründe.

Themen-Vereinheitlichung: ein Merkmal der Sammlung `lieder` mit
`quelle='psalmos.kategorie'` (nur `art='auswahl'`) ist eine **Sicht** auf die
Psalmos-Liedkategorien (`liedkategorie` + `lied_kategorie`). Die Werte kommen
aus dem Kategorien-Katalog; die Engine (`passend_zum_anlass`) sieht sie damit
direkt. `sammlungsmerkmal_werte_pflegen` pflegt für solche Merkmale den
Kategorien-Katalog (`hinzufuegen`/`umbenennen`/`entfernen`).
`lied_speichern` akzeptiert zusätzlich `daten.kategorien` (Liste von
Kategorienamen) und setzt damit die Psalmos-Zuordnung `lied_kategorie`.

`sammlung_pflegen`: nur deklarierte eigene Sammlungen, nicht eingebaute Lieder.
Einträge `{id?, daten:{titel,...}, reihenfolge:0, aktiv:true}`. Ohne ID wird
angelegt, mit ID ausschließlich innerhalb derselben Sammlung geändert.
Bei Umfang `plan` ist die konkrete Plan-ID Pflicht; IDs/Einträge anderer Pläne
werden nicht übernommen. Liederstammdaten werden weiterhin in Psalmos gepflegt.

`platz_hinzufuegen(plan, termin, feld_pfad)` verlangt Planbearbeitungsrecht
und legt den nächsten freien Platz eines *optionalen* Mehrfachfelds an
(`anzahl` als Bereich, z. B. `"0..2"`). Der neue Platz `<feld>[n]` ist leer und
von Hand festgelegt; danach ist er über `eintrag_setzen` normal bearbeitbar und
überlebt die Generierung. Eine feste Slotzahl (z. B. `"anzahl": 3`) sowie ein
offenes Ende (`"1..*"`) kennen keine zusätzlichen Plätze. Beim Überschreiten
der Obergrenze (417) wird nichts geschrieben; jede Anlage ist undo-fähig.

Plan-Anlage fixiert pro Termin die gültige Version. Neue Versionen binden nur
bestehende Termine ab `gueltig_ab` um; davor unverändert. Die Termin-Zeitachse wird
bei einem Versionswechsel nicht rückwirkend neu erzeugt. Neue Pläne verwenden
bereits alle gültigen Versionsintervalle. Die neue Struktur erscheint sofort;
Einträge werden erst durch manuelles Bearbeiten oder Generieren angepasst.

Generator läuft nur auf Entwürfen, nie direkt auf veröffentlichten Plänen.
Manuelle Bearbeitung erstellt wieder einen Entwurf, der alte veröffentlichte
Snapshot bleibt für Mitglieder sichtbar. Fixierte Werte überleben jede
Generierung. `nur_vorschau` speichert weder Einträge noch Audit.

Undo arbeitet auf noch aktiven Plan-Verlaufsgruppen, auch wiederholt. Es löscht
keine Plantyp-Versionen und macht die globale Versionsdefinition nicht rückgängig.
Redo ist nicht angeboten. Publikations-Diff bezieht sich auf Feldwerte; noch kein
Benachrichtigungsversand (außerhalb PR4).

## Rechte

Administrator/System Manager: alles. Dienstbereichsverantwortliche: Plantypen und
zugehörige Pläne/Stammdaten. Ein Bereichswechsel verlangt Admin. Planverantwortliche:
eigene Pläne bearbeiten. Angemeldete Mitglieder: veröffentlichte Stände und eigene
Dienste. Eigene Abwesenheiten: angemeldetes eindeutig gebundenes Konto. Fremde
Abwesenheiten: Admin oder Bereichsverantwortung, letztere nur für diesen Plantyp.
ST3: Gruppenverantwortliche einer an die Vorlage gebundenen Gruppe dürfen Pläne
dieser Vorlage anlegen/bearbeiten/veröffentlichen und Person-Fähigkeiten von
Personen des Personenpools pflegen; die Vorlage selbst bleibt Admin/Bereich.
Eine fremde Plantyp-/Plan-ID gibt keine zusätzlichen Rechte.

## Beispiele (Token aus der eigenen Sitzung; niemals protokollieren)

```bash
curl -b cookies.txt -H "X-Frappe-CSRF-Token: $CSRF" -H 'Content-Type: application/json' \
  --data @plantyp-version.json "$URL/api/method/diakronos.planrahmen.api.plantyp_speichern"
# plantyp-version.json: {"definition": <Kochbuch-Definition>, "gueltig_ab":"2026-01-01"}
curl -b cookies.txt -H "X-Frappe-CSRF-Token: $CSRF" -H 'Content-Type: application/json' \
  --data '{"plantyp":"chorplan","titel":"Chorplan 2026","von":"2026-01-01","bis":"2026-12-31"}' \
  "$URL/api/method/diakronos.planrahmen.api.plan_anlegen"
curl -b cookies.txt -H "X-Frappe-CSRF-Token: $CSRF" -H 'Content-Type: application/json' \
  --data '{"plan":"<Plan-ID>","nur_vorschau":true}' \
  "$URL/api/method/diakronos.planrahmen.api.plan_generieren"
```
