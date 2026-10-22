import test from 'node:test'
import assert from 'node:assert/strict'
import { erststartSchritte } from './erststart.mjs'

// UX C2: durchnummerierte Schritte mit Erledigt-Haken.
test('Erststart nummeriert 1/2/3 und markiert erledigte Schritte', () => {
  const leer = erststartSchritte({ hinweise: ['Wer dirigiert?'], angelegt: false, veroeffentlicht: false })
  assert.deepEqual(leer.map(s => s.nummer), [1, 2, 3])
  assert.deepEqual(leer.map(s => s.erledigt), [false, false, false])
  const teil = erststartSchritte({ hinweise: [], angelegt: true, veroeffentlicht: false })
  assert.deepEqual(teil.map(s => s.erledigt), [true, true, false])
  const fertig = erststartSchritte({ hinweise: [], angelegt: true, veroeffentlicht: true })
  assert.deepEqual(fertig.map(s => s.erledigt), [true, true, true])
})

test('Schritt 1 gilt erst als erledigt, wenn keine Angaben fehlen', () => {
  assert.equal(erststartSchritte({ hinweise: ['x'] })[0].erledigt, false)
  assert.equal(erststartSchritte({ hinweise: [] })[0].erledigt, true)
})
