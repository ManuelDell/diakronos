# Baustein `kalender` — Diakronos: Kalender

**Was er zeigt:** Monats- oder Listenansicht der freigegebenen Termine aus
Diakronos. Ein Klick auf einen Termin öffnet die Einzelheiten (Zeit, Ort,
Beschreibung, Anmelde-Link).

**Datenquelle (BS-1b, L2):**
`GET {Diakronos-Adresse}/website/oeffentlich/termine?von&bis&limit&kalender&kategorie&gruppe`
→ `{"message": [ … ]}`. Genutzt werden nur die Felder der Positivliste:
`id, titel, beginn, ende, ganztaegig, beschreibung, ort, kategorie, farbe,
anmeldung_url`. Es wird nichts davon gespeichert; der Abruf läuft im Browser
des Besuchers.

**Felder**

| Feld | Bedeutung |
|---|---|
| Überschrift | Titel über dem Kalender |
| Diakronos-Adresse | absolute Adresse der Diakronos-Installation (aus dem Installer vorbelegt) |
| Startansicht | „Monatsansicht“ oder „Listenansicht“ |
| Zwischen Monat und Liste umschalten | blendet die beiden Umschaltknöpfe ein |
| Kalender-Kennungen | Slugs, kommagetrennt; leer = alle freigegebenen |
| Kategorie-Kennung | optional |
| Gruppen-Kürzel | optional |
| Wochenstart | „Montag“ (Vorgabe) oder „Sonntag“ |
| Farben aus den Kalendern übernehmen | färbt den Streifen je Termin (nur wenn der Kalender eine gültige Farbe liefert) |
| Texte | Beschriftungen, Lade-/Leer-/Fehlertext, „ganztägig“, „Zur Anmeldung“, „weitere“ |

**Verhalten**

* **Vor / Heute / Weiter** verschieben den gezeigten Monat (in beiden
  Ansichten); „Heute“ springt auf den laufenden Monat.
* **Zeitzone:** alle Tages- und Uhrzeitangaben in `Europe/Berlin`, nie in der
  Zeitzone des Browsers; ganztägige Termine zeigen „ganztägig“ statt „00:00“.
* **Wochenstart** ist ein Feld: Montag (deutsche Vorgabe) oder Sonntag. Das
  Raster beginnt am Wochenstart vor oder am 1. und zeigt volle Wochen.
* **Mobil** (unter 40 em ≈ 640 px) erscheint statt des Rasters die Liste —
  ein 7-Spalten-Raster ist bei 390 px unlesbar. Die Umschaltung bleibt, die
  Liste gilt dort auch bei gewählter Monatsansicht. Ermittelt wird das im
  Browser über `matchMedia`; die Umschaltung ist **kein CSS des Blocks**:
  Primo gibt Block-Stile in eigener Reihenfolge aus (und schreibt Selektoren
  um), deshalb hängt sie am `hidden`-Attribut — das wirkt unabhängig davon.
* **Raster-Gliederung:** eine `<tr>` je Woche, darin sieben `<td>` (ein
  `<table>` ohne `tr` würde der Browser fremd anordnen). Je Zelle höchstens
  drei Termine, der Rest als „+n weitere“; der Zeitzusatz über der Zelle
  zählt nur, wenn gekürzt wurde.
* **Klick und Tastatur:** jeder Termin ist ein Knopf (`type="button"`, Name
  aus Datum + Zeit + Titel). Enter/Leertaste öffnen das Detail, Escape
  schließt es und setzt den Fokus zurück auf den auslösenden Termin; beim
  Öffnen wandert der Fokus auf die Detail-Überschrift.
* **Anmelde-Link:** eine relative Adresse aus der Lese-API (`/diakonos/gast?…`)
  bekommt die Diakronos-Basisadresse davor; ein Pfadanfang, den die Basis
  schon trägt, wird nicht verdoppelt (wie `anmeldung` aus BS-2c).
* **Abruf:** immer der volle gezeigte Monat (`von`/`bis` = 1. bis letzter Tag),
  nicht das Raster — sonst lägen Randtage doppelt oder gar nicht im Fenster.
  Beim schnellen Blättern zählt nur die Antwort des jüngsten Abrufs; die
  Breitenumschaltung lädt nicht neu.
* **Kein externes Programm:** Kalenderrechnung (Monatsraster, Wochenstart,
  Schaltjahre, Zeitzonenwechsel) steht schlank im Block selbst; keine
  Kalender-Bibliothek, kein CDN.
* **Barrierearm:** echtes `<table>` mit `caption` und `scope`, Termine sind
  Knöpfe mit gesprochenem Namen (Datum, Zeit, Titel), sichtbarer Fokus,
  `aria-live` für Ladezustand und Detail, Tastaturbedienung.

**Freigabe (G1):** Der Block zeigt nur, was in Diakronos freigegeben ist —
die Lese-API antwortet sonst leer. Es gibt keine „alle Termine“-Ansicht am
Freigabeprinzip vorbei.
