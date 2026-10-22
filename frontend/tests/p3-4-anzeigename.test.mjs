/**
 * P3-4 (OP-HANDY-25) — Begrüßung und Avatar zeigen den gepflegten Vornamen,
 * nicht den Kontonamen.
 *
 * Befund: Begrüßung und Avatar lasen `user.fullname` (= `user.full_name`). Im
 * Test-/Altbestand ist das nur das E-Mail-Präfix („mitglied"), während der
 * Personenname in der Mitgliederzeile steht. Geprüft wird die reine Regel in
 * `anzeigename.mjs` — `useSession` bindet sie nur an die reaktiven Quellen.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { anzeigename, ersterName, initialen } from '../src/diakonos/composables/anzeigename.mjs'

test('OP-HANDY-25 · Vorname des Mitglieds hat Vorrang vor dem Kontonamen', () => {
  assert.equal(
    anzeigename({ vorname: 'Lea', nachname: 'Sommer' }, 'mitglied'),
    'Lea')
})

test('OP-HANDY-25 · ohne Mitglied: erster Namensteil, nie die E-Mail', () => {
  assert.equal(anzeigename(null, 'jonas@test.local'), 'jonas')
  assert.ok(!anzeigename(null, 'jonas@test.local').includes('@'))
})

test('OP-HANDY-25 · voller Anzeigename ohne Mitglied: Vorname bleibt vorn', () => {
  assert.equal(anzeigename(null, 'Jonas Berger'), 'Jonas')
})

test('OP-HANDY-25 · leerer Mitgliedsvorname fällt auf den Kontonamen zurück', () => {
  assert.equal(anzeigename({ vorname: '   ', nachname: 'Klein' }, 'Ruth Klein'), 'Ruth')
})

test('OP-HANDY-25 · leerer Anzeigename ergibt leeren Text (kein Absturz)', () => {
  assert.equal(ersterName(''), '')
  assert.equal(anzeigename(null, ''), '')
})

test('OP-HANDY-25 · Initialen aus Vor- und Nachnamen des Mitglieds', () => {
  assert.equal(initialen({ vorname: 'Lea', nachname: 'Sommer' }, 'mitglied'), 'LS')
  assert.equal(initialen(null, 'mitglied'), 'MI', 'ohne Mitglied: zwei Zeichen des Kontonamens')
  assert.equal(initialen(null, 'Jonas Berger'), 'JB')
  assert.equal(initialen(null, ''), 'U', 'leer → Ersatzbuchstabe')
})
