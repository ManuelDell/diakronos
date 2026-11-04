# Baustein `termine-liste` — Diakronos: Nächste Termine

**Zweck.** Zeigt die Termine aus Diakronos, die dort für die Website
freigegeben sind. Erscheint ein Termin nicht, fehlt in Diakronos eine Freigabe
(Kalender freigegeben **und** Termin im Status „Festgelegt“ **und**, bei einem
Kalender mit der Einschränkung „nur öffentliche Kategorien“, eine öffentliche
Terminart). Freigaben: Diakronos → Website → Website-Freigaben.

## Felder

| Feld | Typ | Vorgabe | Bedeutung |
|---|---|---|---|
| Überschrift | Text | „Nächste Termine“ | Überschrift des Abschnitts; leer = keine Überschrift |
| Diakronos-Adresse | Text | *gesetzt vom Installer* | Öffentliche Adresse der Diakronos-Installation, z. B. `https://gemeinde.example/diakronos`. **Muss absolut sein** (Schema `https://`). Setzt der Installer beim Einspielen. |
| Darstellung | Auswahl | „Komfortabel“ | `Komfortabel` (untereinander), `Kompakt` (eine Zeile je Termin), `Karten` (Raster, ab 640 px zweispaltig) |
| Anzahl der Termine | Zahl | 5 | 1–50 |
| Zeitraum in Tagen | Zahl | 90 | 1–400; Fenster ab heute |
| Kalender-Kennungen | Text | leer | Kommagetrennt, z. B. `gottesdienste,gruppen`. Leer = alle freigegebenen Kalender |
| Kategorie-Kennung | Text | leer | Eine Terminart-Kennung; wirkt nur, wenn die Terminart in Diakronos öffentlich ist |
| Gruppen-Kürzel | Text | leer | Kürzel einer freigegebenen Gruppe |
| Ort anzeigen | Schalter | an | Raum/Saal unter dem Titel anzeigen |
| Adresse für „Alle Termine“ | Text | leer | Absolut oder leer. Leer = kein Link |
| Beschriftung des Links | Text | „Alle Termine“ | |
| Text, wenn keine Termine anstehen | Text | „Zurzeit sind keine Termine angekündigt.“ | |
| Text, wenn die Termine nicht geladen werden können | Text | „Die Termine sind derzeit nicht abrufbar …“ | Auch bei fehlender Diakronos-Adresse |

## Datenquelle

`GET {Diakronos-Adresse}/website/oeffentlich/termine?von=…&bis=…&limit=…&kalender=…&kategorie=…&gruppe=…`

Antwort: `{"message": [ {id, titel, beginn, ende, ganztaegig, beschreibung, ort,
kategorie, gruppe, farbe, anmeldung_url}, … ]}`. Der Baustein nutzt nur
`id`, `titel`, `beginn`, `ende`, `ganztaegig`, `ort`, `kategorie`,
`anmeldung_url` — es kommen keine Personendaten, keine internen Kennungen und
keine Adressen an den Browser (Feld-Positivliste der API, G1).

Der Abruf läuft **im Browser des Besuchers** (client-seitig, CORS für die
Website-Herkunft). Damit teilen sich alle Besucher keine Diakronos-Ratenbremse.

## Verhalten

* Ohne JavaScript bzw. vor dem Laden zeigt der Block „Termine werden geladen …“.
  Er ist damit **nicht** suchmaschinenlesbar — so ist der Entwurf (BS-0 F4).
* Zeitlimit 8 s; danach erscheint der Fehlertext im Block.
* Datum und Uhrzeit werden in `Europe/Berlin` und in der Schreibweise `de-DE`
  ausgegeben („Sa., 08.11. · 10:00 – 11:30“), unabhängig von der
  Browsersprache. Ganztägige Termine zeigen „ganztägig“ statt „00:00“.
* Ein `anmeldung_url` wird nur als Link ausgegeben, wenn er mit `http://` oder
  `https://` beginnt.
* Gestaltung ausschließlich über `--dk-*` (Site-Stile überschreiben sie):
  `--dk-farbe-text`, `--dk-farbe-gedaempft`, `--dk-farbe-akzent`,
  `--dk-farbe-flaeche`, `--dk-farbe-ueberschrift`, `--dk-farbe-rahmen`,
  `--dk-farbe-warnung`, `--dk-schrift`, `--dk-schrift-ueberschrift`,
  `--dk-groesse-text`, `--dk-groesse-klein`, `--dk-groesse-ueberschrift`,
  `--dk-abstand`, `--dk-abstand-klein`, `--dk-rahmen-radius`,
  `--dk-rahmen-breite`.
* **Nicht** im Block deklariert, nur gelesen — wer die Tokens setzt, setzt sie
  in den Site-Stilen (`:root`), nicht in einem Baustein (BS-0 F5).
