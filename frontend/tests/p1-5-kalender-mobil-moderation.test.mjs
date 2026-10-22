/**
 * P1-5 — Kalenderansichten mobil und Moderation (Node `--test`).
 *
 * Verhaltenstest fuer die Datums-/Zeitzeile der Moderationskarte (UXK-R11):
 * Das Ende eines Termins muss die Endzeit als UHRZEIT zeigen — frueher stand
 * dort „14:00 – 15.10.“ (Ende als Datum). Das Datum erscheint nur, wenn der
 * Termin an einem anderen Tag endet.
 */
import assert from 'node:assert/strict'
import test from 'node:test'

import { terminZeitText } from '../src/diakonos/components/kronos/moderationskarte.js'

test('UXK-R11: Termin am selben Tag zeigt Anfang und Ende als Uhrzeit', () => {
  const text = terminZeitText({ start: '2026-10-15T14:00:00', end: '2026-10-15T15:00:00', all_day: false })
  assert.match(text, /14:00/)
  assert.match(text, /15:00/)
  // Kein Datum als Endangabe mehr.
  assert.doesNotMatch(text.split('–')[1] || '', /\d{2}\.\d{2}/)
})

test('UXK-R11: Termin ueber Mitternacht nennt am Ende das Datum mit Uhrzeit', () => {
  const text = terminZeitText({ start: '2026-10-15T22:00:00', end: '2026-10-16T01:00:00', all_day: false })
  assert.match(text, /22:00/)
  assert.match(text, /16\.10\./)
  assert.match(text, /01:00/)
})

test('UXK-R11: Ganztagstermin zeigt nur das Datum ohne Uhrzeit', () => {
  const text = terminZeitText({ start: '2026-10-15T00:00:00', end: '2026-10-15T00:00:00', all_day: true })
  assert.match(text, /15\.10\./)
  assert.doesNotMatch(text, /\d{2}:\d{2}/)
})

test('UXK-R11: Serie ueber mehrere Tage nennt erstes und letztes Datum', () => {
  const text = terminZeitText({
    type: 'serie',
    first_start: '2026-10-01T19:00:00',
    last_start: '2026-11-05T19:00:00',
    all_day: false,
  })
  assert.match(text, /01\.10\./)
  assert.match(text, /05\.11\./)
})
