/**
 * P1-3 — Kalender: Fenster-Filter und Historie (Node `--test`).
 *
 * Quelltext-Waechter fuer die Befunde des Nachtberichts, deren Ursache im
 * Frontend liegt:
 *
 *   BLD-R6 / BF1b-K2  Der Tages-Dialog nennt bei mehrtägigen und ganztägigen
 *                     Terminen den Tagesbereich statt zweier Uhrzeiten und
 *                     zeigt nie „Invalid Date“.
 *   BF1b-W5           Die Serien-Anzahl kommt aus EINER Abfrage (der Dialog
 *                     darf nicht je Serie einzeln nachfragen).
 *   BLD-R5            Das Startdatum fuer „Alle nachfolgenden löschen“ geht als
 *                     reiner ISO-Tag (`YYYY-MM-DD`) an den Server — ein
 *                     Zeitstempel löste dort einen unbehandelten 500er aus.
 *   P1-5c (4/K3)      Nur 00:00–00:00 (bzw. `all_day`) ist „Ganztägig“; ein
 *                     Termin 14:00–14:00 zeigt seine Uhrzeit. Die Logik ist
 *                     jetzt eine Funktion (`dayEventLabel.mjs`) und wird hier
 *                     WIRKLICH ausgefuehrt statt nur per Regex im Quelltext.
 *
 * Die Serverseite (Datumspruefung in `api/kronos/series.py`) sichern die
 * pytest-Tests `backend/tests/test_p1_3_kalender_fenster.py::test_r5_*` ab;
 * hier bleiben nur die Frontend-Quellen.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import { formatTimeRange, istOhneUhrzeit } from '../src/diakonos/components/kronos/dayEventLabel.mjs'

const root = new URL('../src/diakonos/', import.meta.url)
const lies = (p) => readFileSync(new URL(p, root), 'utf8')

const DIALOG = lies('components/kronos/KronosDayEventsDialog.vue')
const SERIES = lies('components/kronos/KronosSeriesDialog.vue')

// ── BF1b-K2: mehrtägige und ganztägige Termine im Tages-Dialog ──────────────

test('P1-3: der Dialog nutzt die geteilte Beschriftungsfunktion', () => {
  // P1-5c/K3: Die Logik liegt nicht mehr im Dialog, sondern ist importierbar
  // (und damit ausfuehrbar testbar).
  assert.match(DIALOG, /import \{ formatTimeRange \} from '\.\/dayEventLabel\.mjs'/)
})

test('P1-3: ganztägige Mehrtägige heissen „Ganztägig“ mit Tagesbereich', () => {
  // Vorher stand dort „28.10. 00:00 – 29.10. 00:00“ — für einen ganztägigen
  // Termin eine Uhrzeit, die es nicht gibt.
  assert.equal(
    formatTimeRange({ start: '2026-10-28 00:00:00', end: '2026-10-29 00:00:00', allDay: true }),
    'Ganztägig 28.10. – 29.10.',
  )
})

test('P1-3: Bestandsdaten 00:00–00:00 ohne all_day-Flag gelten als ganztägig', () => {
  // BLD-R6: „Jugendhauskreis“ steht im Betriebsdatenbestand als 00:00–00:00
  // OHNE `all_day`. Solche Termine duerfen nicht als „00:00 – 00:00“ erscheinen.
  assert.equal(
    formatTimeRange({ start: '2026-10-28 00:00:00', end: '2026-10-28 00:00:00', allDay: false }),
    'Ganztägig',
  )
})

test('P1-5c (4): ein Termin 14:00–14:00 zeigt die Uhrzeit, nicht „Ganztägig“', () => {
  // ROT vor der Behebung: die Bedingung `start.getTime() === end.getTime()`
  // galt fuer JEDE Laenge-0-Spanne. `create_event` setzt `end = start`, ein
  // Punkttermin um 14:00 wurde damit faelschlich als „Ganztägig“ beschriftet.
  assert.equal(
    formatTimeRange({ start: '2026-10-28 14:00:00', end: '2026-10-28 14:00:00', allDay: false }),
    '14:00 – 14:00',
  )
  // Und die reine Regel direkt:
  assert.equal(
    istOhneUhrzeit(false, new Date('2026-10-28T14:00:00'), new Date('2026-10-28T14:00:00')),
    false,
  )
  assert.equal(
    istOhneUhrzeit(false, new Date('2026-10-28T00:00:00'), new Date('2026-10-28T00:00:00')),
    true,
  )
})

test('P1-3: mehrtägige Termine MIT Uhrzeit nennen beide Tage', () => {
  assert.equal(
    formatTimeRange({ start: '2026-10-28 14:00:00', end: '2026-10-29 16:30:00', allDay: false }),
    '28.10. 14:00 – 29.10. 16:30',
  )
})

test('P1-3: Termin ohne Ende zeigt keine „Invalid Date“', () => {
  // `ev.allDay` ohne Ende -> „Ganztägig“, sonst nur die Startzeit.
  assert.equal(
    formatTimeRange({ start: '2026-10-28 09:30:00', end: null, allDay: false }),
    '09:30',
  )
  assert.equal(formatTimeRange({ start: '2026-10-28 00:00:00', end: null, allDay: true }), 'Ganztägig')
  assert.equal(formatTimeRange({ start: null, end: null, allDay: false }), '')
})

// ── BLD-R5: Startdatum der Serien-Loeschung ────────────────────────────────

test('P1-3: „Alle nachfolgenden löschen“ sendet nur den ISO-Tag', () => {
  assert.match(
    SERIES,
    /from_date: String\(eventData\.value\.element_start \|\| ''\)\.slice\(0, 10\)/
  )
})
