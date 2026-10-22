import { test } from 'node:test'
import assert from 'node:assert/strict'
import { kandidatenZiel } from './klartext.mjs'

test('Neue optionale Vorschlagsfelder nutzen einen vorhandenen Platz derselben Liste für Namen', () => {
  const t = { id: 't', plantyp_version: 'v' }
  const defs = new Map([['v', { felder: [{ id: 'lieder', art: 'eintrag', sammlung: 'lieder' }, { id: 'einueben', art: 'eintrag', sammlung: 'lieder' }] }]])
  const slots = new Map([['t', [{ feld_pfad: 'lieder[0]', art: 'eintrag', sammlung: 'lieder' }]]])
  assert.deepEqual(kandidatenZiel('t', 'einueben[0]', [t], defs, slots), { termin: 't', pfad: 'lieder[0]' })
})
test('Fehlende aktive Plätze werden nicht mit einem erfundenen API-Pfad abgefragt', () => {
  assert.equal(kandidatenZiel('t', 'einueben[0]', [], new Map(), new Map()), null)
})
