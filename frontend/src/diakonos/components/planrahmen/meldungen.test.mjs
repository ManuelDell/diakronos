import { test } from 'node:test'
import assert from 'node:assert/strict'
import { terminMeldungen, meldungsGruppen } from './meldungen.mjs'

test('Terminmeldungen behalten den Feldkontext und bündeln doppelte Verstöße', () => {
  const m = { baustein: 'vorher_geuebt', stufe: 'sollte', meldung: 'Noch nicht geübt' }
  const entries = [{ termin: 'a', feld_pfad: 'lieder[0]', meldungen: [m, m] }, { termin: 'b', feld_pfad: 'lieder[0]', meldungen: [m] }]
  assert.deepEqual(terminMeldungen(entries, 'a'), [{ ...m, termin: 'a', feld_pfad: 'lieder[0]' }])
})
test('Regeln aus Bewertungsmeldungen gruppieren statt technischer Codes', () => {
  const g = meldungsGruppen([{ stufe: 'sollte', code: 'regel_verletzt', bewertung: { baustein: 'vorher_geuebt' }, meldung: 'Bitte üben' }])
  assert.equal(g.gruppen[0].regel, 'vorher_geuebt')
  assert.equal(g.anzahl.warnung, 1)
})
