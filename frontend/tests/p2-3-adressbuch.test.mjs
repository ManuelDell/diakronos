/**
 * P2-3 · OP-HANDY-19 — „Jemanden aus der Jugend anrufen“ ist möglich.
 *
 * Befund: Im Adressbuch gab es keinen einzigen tel:/mailto:-Link; die Tabelle
 * lief seitlich über (Spalte „Telefon“ außerhalb der Karte).
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { telHref, mailHref, kartenAnsicht } from '../src/diakonos/composables/adressbuch.mjs'

const quelle = readFileSync(new URL('../src/diakonos/pages/Adressbuch.vue', import.meta.url), 'utf8')

test('OP-HANDY-19 · tel:-Link verträgt Schreibweisen aus der Anzeige', () => {
  assert.equal(telHref('0711 123456'), '0711123456')
  assert.equal(telHref('+49 (0)711 / 12-34-56'), '+4907111234 56'.replace(' ', ''))
  assert.equal(telHref('+49 171 1234567'), '+491711234567')
})

test('OP-HANDY-19 · tel:-Link ist leer, wenn es nichts anzurufen gibt', () => {
  assert.equal(telHref(''), '')
  assert.equal(telHref(null), '')
  assert.equal(telHref('—'), '')
})

test('OP-HANDY-19 · mailto:-Link baut auf gültiger Adresse', () => {
  assert.equal(mailHref('anna@example.org'), 'mailto:anna@example.org')
  assert.equal(mailHref('  anna@example.org  '), 'mailto:anna@example.org')
})

test('OP-HANDY-19 · mailto:-Link verweigert offensichtlich kaputte Werte', () => {
  assert.equal(mailHref('anna example.org'), '')
  assert.equal(mailHref(''), '')
  assert.equal(mailHref('a\nb@example.org'), '')
})

test('OP-HANDY-19 · Kartenansicht greift bei Handybreite (bis 720 px)', () => {
  assert.equal(kartenAnsicht(390), true)
  assert.equal(kartenAnsicht(720), true)
  assert.equal(kartenAnsicht(1366), false)
  assert.equal(kartenAnsicht(undefined), false)
})

test('OP-HANDY-19 · die Seite bietet Anruf- und Mail-Verknüpfungen', () => {
  assert.match(quelle, /'tel:' \+ telHref\(m\.telefonnummer\)/, 'Anruf-Link vorhanden')
  assert.match(quelle, /'mailto:' \+ m\.email/, 'Mail-Link vorhanden')
  assert.match(quelle, /ab-karten/, 'Kartenliste vorhanden')
  assert.match(quelle, /ab-tabelle/, 'Tabelle bleibt für den Schreibtisch')
})
