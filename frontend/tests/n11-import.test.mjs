/**
 * N11 — Reiter Import: Rechenregeln der Oberflaeche.
 *
 * Prueft die reine Logik aus `components/mitglieder/importPruefung.mjs`:
 * Trennzeichen-Erkennung, Spaltenzuordnung, Pflichtspalten, Statusworte,
 * Quoting der Muster-Datei. Diese Datei laeuft ohne vue/Pakete (nur node:test),
 * damit sie im Docker-Build (Stage 1) und lokal gleich funktioniert.
 */
import test from 'node:test'
import assert from 'node:assert/strict'

import {
  IMPORT_FELDER,
  csvZelle,
  datenzeilen,
  dublettenGrund,
  erkenneSpalten,
  ersteZeile,
  fehlendePflichtspalten,
  musterCsv,
  statusWort,
  zeilenName,
  zerlegeZeile,
} from '../src/diakonos/components/mitglieder/importPruefung.mjs'

test('Trennzeichen: Semikolon bei deutscher Excel-Datei, Komma sonst', () => {
  assert.equal(ersteZeile('Vorname;Nachname;E-Mail\nAnna;A;a@b.de').trenner, ';')
  assert.equal(ersteZeile('Vorname,Nachname,E-Mail').trenner, ',')
  // Gleichstand -> Semikolon (deutscher Normalfall)
  assert.equal(ersteZeile('a;b,c').trenner, ';')
})

test('Kopfzeile: BOM und CRLF werden entfernt', () => {
  const { kopf, trenner } = ersteZeile('\ufeffVorname;Nachname\r\nAnna;A\r\n')
  assert.equal(trenner, ';')
  assert.deepEqual(kopf, ['Vorname', 'Nachname'])
})

test('Zellen: umschliessende Anfuehrungszeichen und "" werden aufgeloest', () => {
  assert.deepEqual(zerlegeZeile('"Anna; Maria";Beispiel', ';'), ['Anna; Maria', 'Beispiel'])
  assert.deepEqual(zerlegeZeile('"Er sagte ""Hallo"""', ';'), ['Er sagte "Hallo"'])
  // Nicht umschliessendes Zeichen bleibt stehen
  assert.deepEqual(zerlegeZeile('Anna "M.";Beispiel', ';'), ['Anna "M."', 'Beispiel'])
})

test('Datenzeilen zaehlen ohne Kopfzeile und ohne Leerzeilen', () => {
  assert.equal(datenzeilen('Vorname;Nachname\nA;B\nC;D\n'), 2)
  assert.equal(datenzeilen('Vorname;Nachname\n'), 0)
  assert.equal(datenzeilen(''), 0)
})

test('Spaltenzuordnung erkennt gaengige Kopfzeilen (auch gross/klein)', () => {
  const zuordnung = erkenneSpalten(['Vorname', 'NACHNAME', 'E-Mail', 'Tel.', 'Telefonnummer'])
  assert.equal(zuordnung.vorname, 'Vorname')
  assert.equal(zuordnung.nachname, 'NACHNAME')
  assert.equal(zuordnung.email, 'E-Mail')
  assert.equal(zuordnung.telefon, 'Telefonnummer')
  // "Tel." ist keine bekannte Kopfzeile — nichts erraten.
  assert.equal(zuordnung.tel, undefined)
})

test('Spaltenzuordnung erkennt Straße/Strasse und Geburtsdatum', () => {
  assert.equal(erkenneSpalten(['Straße']).strasse, 'Straße')
  assert.equal(erkenneSpalten(['Strasse']).strasse, 'Strasse')
  assert.equal(erkenneSpalten(['Geburtsdatum']).geburtstag, 'Geburtsdatum')
  assert.equal(erkenneSpalten(['Geburtstag']).geburtstag, 'Geburtstag')
})

test('Pflichtspalten: Vorname und Nachname muessen zugeordnet sein', () => {
  assert.deepEqual(fehlendePflichtspalten({}), ['Vorname', 'Nachname'])
  assert.deepEqual(fehlendePflichtspalten({ vorname: 'Vorname' }), ['Nachname'])
  assert.deepEqual(fehlendePflichtspalten({ vorname: 'V', nachname: 'N' }), [])
  // E-Mail ist NICHT Pflicht (Kartenvorgabe: Namen ohne E-Mail sind erlaubt)
  assert.equal(IMPORT_FELDER.find(f => f.feld === 'email').pflicht, false)
})

test('Statusworte und Dublettengruende sind deutsch und ohne Fachbegriffe', () => {
  assert.equal(statusWort('neu'), 'Neu')
  assert.equal(statusWort('dublette'), 'Möglich doppelt')
  assert.equal(statusWort('fehler'), 'Fehler')
  assert.match(dublettenGrund({ grund: 'email' }), /E-Mail-Adresse/)
  assert.match(dublettenGrund({ grund: 'name_in_datei' }), /mehrfach in der Datei/)
  assert.equal(dublettenGrund(null), '')
})

test('Zeilenname faellt auf die Zeilennummer zurueck', () => {
  assert.equal(zeilenName({ zeile: 3, felder: { vorname: 'Anna', nachname: 'A' } }), 'Anna A')
  assert.equal(zeilenName({ zeile: 3, felder: {} }), 'Zeile 3')
})

test('csvZelle quotet Semikolon, Anfuehrungszeichen und Zeilenumbruch', () => {
  assert.equal(csvZelle('Anna'), 'Anna')
  assert.equal(csvZelle('Chor; Kinder'), '"Chor; Kinder"')
  assert.equal(csvZelle('Er sagte "Hallo"'), '"Er sagte ""Hallo"""')
  assert.equal(csvZelle('Zeile1\nZeile2'), '"Zeile1\nZeile2"')
  assert.equal(csvZelle(null), '')
})

test('Muster-Datei: Kopfzeile, Beispielzeile, Telefon mit Plus unveraendert', () => {
  const csv = musterCsv()
  const zeilen = csv.replace(/^\ufeff/, '').trim().split('\r\n')
  assert.equal(zeilen.length, 2)
  assert.deepEqual(zeilen[0].split(';'),
    ['Vorname', 'Nachname', 'E-Mail', 'Telefon', 'Geburtsdatum', 'Straße', 'PLZ', 'Ort'])
  // N11b: Die Muster-Datei ist eine Vorlage mit festen Beispieldaten; das
  // `+` der Telefonnummer bleibt hier unveraendert (kein Formelzeichen-Ziel,
  // der Import akzeptiert beide Formen). Der echte Export entschaerft.
  assert.ok(zeilen[1].includes('+49 711 123456'), zeilen[1])
  assert.ok(!zeilen[1].includes("'+49"), zeilen[1])
})

test('Muster-Datei ist ohne Spaltenzuordnung lesbar (dieselben Kopfzeilen)', () => {
  const { kopf } = ersteZeile(musterCsv())
  const zuordnung = erkenneSpalten(kopf)
  assert.deepEqual(fehlendePflichtspalten(zuordnung), [])
  assert.equal(zuordnung.email, 'E-Mail')
  assert.equal(zuordnung.telefon, 'Telefon')
})
