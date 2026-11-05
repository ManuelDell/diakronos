/**
 * FIX-7b — Zeitzeile der Termin-Detailansicht (`KronosEventView`).
 *
 * Befund aus der Browser-Abnahme (2026-11-05): die frisch geladene
 * Detailansicht eines abgelehnten Termins zeigte
 * „Invalid Date Invalid Date – Invalid Date“, weil die Komponente
 * `element_start`/`element_end` las, die Antwort von `get_mein_termin` aber
 * `start`/`end` liefert.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { terminZeitZeile } from '../src/diakonos/components/kronos/terminZeitZeile.mjs'

const QUELLE = readFileSync(
  new URL('../src/diakonos/components/kronos/KronosEventView.vue', import.meta.url),
  'utf8',
)

test('FIX-7b · Detailantwort von get_mein_termin ergibt lesbaren Text (kein „Invalid Date“)', () => {
  const termin = {
    name: 'gottesdienst-2026-11-08',
    title: 'Gottesdienst',
    start: '2026-11-08 10:00:00',
    end: '2026-11-08 11:30:00',
    all_day: false,
  }
  const text = terminZeitZeile(termin)
  assert.ok(!/Invalid/i.test(text), `unerwarteter Text: ${text}`)
  assert.match(text, /08\.11\.2026|8\. Nov/)
  assert.match(text, /10:00/)
  assert.match(text, /11:30/)
})

test('FIX-7b · Kalender-Felder (element_start/element_end) gehen weiterhin', () => {
  const text = terminZeitZeile({ element_start: '2026-11-08 10:00:00', element_end: '2026-11-08 11:30:00' })
  assert.ok(!/Invalid/i.test(text))
  assert.match(text, /10:00/)
})

test('FIX-7b · Ganztags und fehlende Werte', () => {
  const ganz = terminZeitZeile({ start: '2026-11-08', all_day: true })
  assert.match(ganz, /Ganztägig/)
  assert.equal(terminZeitZeile(null), '—')
  assert.equal(terminZeitZeile({}), '—')
  assert.equal(terminZeitZeile({ start: 'kein-datum' }), '—')
})

test('FIX-7b · die Komponente nutzt den Helfer statt eigener Feldnamen', () => {
  assert.match(QUELLE, /import \{ terminZeitZeile \} from '\.\/terminZeitZeile\.mjs'/)
  assert.match(QUELLE, /terminZeitZeile\(event\)/)
  // Die alten, falschen Feldnamen stehen nicht mehr in der Komponente.
  assert.ok(
    !/event\.element_start/.test(QUELLE),
    'KronosEventView liest wieder direkt `element_start`',
  )
})
