import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const text = readFileSync(new URL('../src/diakonos/components/planrahmen/LiederPflege.vue', import.meta.url), 'utf8')
test('Tagpflege bietet Entfernen und Umbenennen in App-Fenstern an', () => {
  assert.doesNotMatch(text, /window\.(?:confirm|prompt)\(/)
  assert.match(text, /await bestaetigen\(/)
  assert.match(text, /v-model="umbenennenOffen"/)
  assert.match(text, /v-model="umbenennenWert"/)
  assert.match(text, /@submit\.prevent="umbenennenSpeichern"/)
})
