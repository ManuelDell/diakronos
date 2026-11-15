// UI-R3d (Review): Rückgängig nach dem Löschen nur, wenn der Server KEINE Freigabe
// und keinen Gastlink meldet — auch Gruppen- und reine Lesen/Schreiben-Freigaben.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { vollstaendig } from '../src/diakonos/composables/rueckgaengigWeg.mjs'

const basis = { name: 'Chorproben', titel: 'Chorproben', gruppe: 'Chor', leserechte: [], schreibrechte: [], moderatoren: [], gemeinde_status: 'aus', gruppe_status: 'aus' }

test('ohne Freigaben bleibt Rückgängig möglich', () => {
  assert.equal(vollstaendig('kalender', { ...basis, hat_freigaben: false }), true)
})

test('jede Freigabe laut Server verhindert Rückgängig', () => {
  assert.equal(vollstaendig('kalender', { ...basis, hat_freigaben: true }), false)
})
