import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const text = readFileSync(new URL('../src/diakonos/components/planrahmen/LiederPflege.vue', import.meta.url), 'utf8')
test('Tagpflege bietet Entfernen und Umbenennen in App-Fenstern an', () => {
  assert.doesNotMatch(text, /window\.(?:confirm|prompt)\(/)
  // UX2c (C1): „Entfernen“ ist endgültig (Zuordnungen der Lieder gehen mit) —
  // die Rückfrage läuft jetzt über den EINEN Endgültig-Dialog mit Frage und
  // konkreter Folge statt über die Ein-Zeilen-Rückfrage.
  assert.match(text, /<DkEndgueltig/)
  assert.match(text, /Der Wert verschwindet endgültig/)
  assert.match(text, /v-model="umbenennenOffen"/)
  assert.match(text, /v-model="umbenennenWert"/)
  assert.match(text, /@submit\.prevent="umbenennenSpeichern"/)
})
