/**
 * R-DES-REST-b B3: Eine eingetragene oder geladene Endzeit eintägiger Termine
 * darf beim Ändern des Beginns nicht auf „Beginn + 1 Stunde“ springen.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { endeAusBeginnMitDatum } from '../src/diakonos/composables/datumZeit.mjs'

test('B3 · eintägig: vorhandene Endzeit bleibt beim Ändern des Beginns', () => {
  assert.equal(endeAusBeginnMitDatum('2026-02-05', '19:00', '2026-02-05', '21:00'), '21:00')
  assert.equal(endeAusBeginnMitDatum('2026-02-05', '19:00', '', '21:00'), '21:00')
})

test('B3 · eintägig: eingetippte Endzeit wird übernommen', () => {
  assert.equal(endeAusBeginnMitDatum('2026-02-26', '19:30', '2026-02-26', '21:30'), '21:30')
})

test('B3 · eintägig: nur ein leeres Ende bekommt den Vorschlag', () => {
  assert.equal(endeAusBeginnMitDatum('2026-02-05', '19:00', '', ''), '20:00')
})

test('B2 bleibt: mehrtägig behält die Endzeit', () => {
  assert.equal(endeAusBeginnMitDatum('2026-02-23', '09:00', '2026-02-25', '00:00'), '00:00')
})
