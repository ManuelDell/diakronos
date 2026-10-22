import assert from 'node:assert/strict'
import { liedAnzeige, istKopie, liedBadge, QUELLEN } from './lied-anzeige.mjs'

// Kopie: keine Nummer, kein "Nr." — nur "Kopie".
assert.equal(liedAnzeige({ quelle: 'kopie' }), 'Kopie')
assert.equal(liedAnzeige({ quelle: 'kopie', buch: 'IGNORIERT', nummer: '99' }), 'Kopie')
assert.equal(istKopie({ quelle: 'kopie' }), true)
assert.equal(istKopie({ quelle: 'buch', nummer: '12' }), false)

// Buch mit Nummer: "JN 1297" (kein "Nr."-Praefix).
assert.equal(liedAnzeige({ quelle: 'buch', buch: 'JN', nummer: '1297' }), 'JN 1297')
// Alias gesangbuch_nummer (Psalmos-Feld).
assert.equal(liedAnzeige({ quelle: 'buch', buch: 'JN', gesangbuch_nummer: '1297' }), 'JN 1297')

// Buch nur mit Seite: "WH S. 150".
assert.equal(liedAnzeige({ quelle: 'buch', buch: 'WH', seite: '150' }), 'WH S. 150')

// Buch ohne Nummer/Seite: nur der Buchname.
assert.equal(liedAnzeige({ quelle: 'buch', buch: 'WH' }), 'WH')

// Nummer hat Vorrang vor Seite.
assert.equal(liedAnzeige({ quelle: 'buch', buch: 'JN', nummer: '7', seite: '3' }), 'JN 7')

// Ohne Angabe / leer: nichts (Aufrufer zeigt den Titel).
assert.equal(liedAnzeige({ quelle: 'ohne' }), '')
assert.equal(liedAnzeige({}), '')
assert.equal(liedAnzeige({ quelle: 'buch' }), '')
assert.equal(liedBadge({ quelle: 'ohne' }), '')

// Fehlende Quelle aber vorhandene Nummer: keine Anzeige (kein "Nr." erfinden).
assert.equal(liedAnzeige({ nummer: '42' }), '')

// Die drei Quellen stehen zur Auswahl.
assert.deepEqual(QUELLEN.map((q) => q.wert), ['buch', 'kopie', 'ohne'])

console.log('Lied-Anzeige (LN1): 15 Prüfungen bestanden')
