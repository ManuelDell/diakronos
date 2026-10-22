/**
 * REST-1 (4) — Glocke: „gelesen“ nur, wenn die Liste noch zu sehen ist.
 *
 * Board-Befund R1: `toggleListe` markierte nach dem Laden als gelesen, auch
 * wenn das Panel zwischenzeitlich geschlossen wurde — die Nachrichten waren
 * damit ungesehen weg. Der Wettlauf wird hier ohne Browser nachgestellt.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { darfAlsGelesenMarkieren } from '../src/diakonos/composables/glocke.mjs'

const lage = (teile = {}) => ({
    offen: true, anfrage: 1, oeffnung: 1,
    eintraege: [{ name: 'NL-1', read: 0 }], fehler: '',
    ...teile,
})

test('offenes Panel mit geladener Liste wird als gelesen markiert', () => {
    assert.equal(darfAlsGelesenMarkieren(lage()), true)
})

test('inzwischen geschlossen: NICHT als gelesen markieren', () => {
    assert.equal(darfAlsGelesenMarkieren(lage({ offen: false })), false,
        'geschlossenes Panel darf nichts als gesehen verbuchen')
})

test('Antwort einer alten Öffnung: NICHT als gelesen markieren', () => {
    assert.equal(darfAlsGelesenMarkieren(lage({ anfrage: 1, oeffnung: 2 })), false)
})

test('Fehlschlag oder leere Antwort: NICHT als gelesen markieren', () => {
    assert.equal(darfAlsGelesenMarkieren(lage({ eintraege: null })), false)
    assert.equal(darfAlsGelesenMarkieren(lage({ fehler: 'Netzfehler' })), false)
})

test('leere Liste ist in Ordnung (nichts zu markieren)', () => {
    assert.equal(darfAlsGelesenMarkieren(lage({ eintraege: [] })), true)
})
