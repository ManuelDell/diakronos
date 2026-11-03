/**
 * ICAL-1b — ganztägiges Ende beim ZURÜCKSCHREIBEN.
 *
 * ICAL-1 hat die Anzeige richtiggestellt: der Kalender (event-calendar /
 * FullCalendar, RFC 5545) zählt das Ende ganztägiger Termine AUSSCHLIESSEND,
 * Diakronos speichert es EINSCHLIESSEND — die Anzeige rechnet deshalb +1 Tag
 * (`endeFuerKalender`). Die Rückrichtung fehlte: Ziehen und Größenänderung
 * gaben das ANGEZEIGTE Ende unverändert an `save_event` weiter. Ergebnis:
 * jedes Ziehen/Ändern verlängerte den Termin um einen Tag (Befund ICAL-1b).
 *
 * Hier steht deshalb beides: der Hin- und Rückweg der Umrechnung und der
 * Beweis, dass der Speicherweg (`speicherWerte` in useEventsApi.js) sie
 * benutzt.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

import {
  endeFuerKalender,
  endeAusKalender,
  speicherWerte,
  tageDazwischen,
} from '../src/diakonos/composables/datumZeit.mjs'

const hier = dirname(fileURLToPath(import.meta.url))
const lies = (rel) => readFileSync(resolve(hier, '..', rel), 'utf8')


// ─────────────────────────────────────────────────────────────────────────────
// Die Rückrechnung (−1 Tag, nur ganztägig)
// ─────────────────────────────────────────────────────────────────────────────

test('zweitägig ganztägig: angezeigtes Ende 9. → gespeichert wieder 8.', () => {
  assert.equal(endeAusKalender('2026-11-09 00:00:00', true, '2026-11-07 00:00:00'),
    '2026-11-08 00:00:00')
})

test('eintägig ganztägig: angezeigtes Ende 8. → gespeichert wieder 7.', () => {
  assert.equal(endeAusKalender('2026-11-08 00:00:00', true, '2026-11-07 00:00:00'),
    '2026-11-07 00:00:00')
})

test('nie vor dem Beginn: Ende-Beginn ergibt den Beginn', () => {
  assert.equal(endeAusKalender('2026-11-07 00:00:00', true, '2026-11-07 00:00:00'),
    '2026-11-07 00:00:00')
})

test('über den Monats-/Jahreswechsel', () => {
  assert.equal(endeAusKalender('2027-01-01 00:00:00', true, '2026-12-31 00:00:00'),
    '2026-12-31 00:00:00')
  assert.equal(endeAusKalender('2026-03-01', true, '2026-02-28'), '2026-02-28')
})

test('Termin MIT Uhrzeit bleibt unverändert', () => {
  assert.equal(endeAusKalender('2026-11-07 10:30:00', false, '2026-11-07 09:00:00'),
    '2026-11-07 10:30:00')
})

test('ohne oder mit unlesbarem Ende wird nichts erfunden', () => {
  assert.equal(endeAusKalender('', true, '2026-11-07 00:00:00'), '')
  assert.equal(endeAusKalender(null, true, '2026-11-07 00:00:00'), null)
  assert.equal(endeAusKalender('kaputt', true, '2026-11-07 00:00:00'), 'kaputt')
})


// ─────────────────────────────────────────────────────────────────────────────
// Hin- und Rückweg ergibt dasselbe Ende
// ─────────────────────────────────────────────────────────────────────────────

test('Hin- und Rückweg: eintägig bleibt eintägig', () => {
  const gespeichert = '2026-11-07 00:00:00'
  const angezeigt = endeFuerKalender(gespeichert, true)
  assert.equal(angezeigt, '2026-11-08 00:00:00')
  assert.equal(endeAusKalender(angezeigt, true, gespeichert), gespeichert)
})

test('Hin- und Rückweg: mehrtägig bleibt mehrtägig', () => {
  const gespeichert = '2026-11-08 00:00:00'          // 7.–8. = zwei Tage
  const angezeigt = endeFuerKalender(gespeichert, true)
  assert.equal(dauerTage(gespeichert, angezeigt), 2, 'Anzeige zeigt 7. und 8.')
  assert.equal(endeAusKalender(angezeigt, true, '2026-11-07 00:00:00'), gespeichert)
})

/** Dauer in Tagen: gespeichertes Ende ist EINSCHLIESSEND (Ende == Beginn = 1 Tag). */
function dauerTage(beginn, ende) {
  const diff = tageDazwischen(String(beginn).slice(0, 10), String(ende).slice(0, 10))
  return diff === null ? null : diff + 1
}


// ─────────────────────────────────────────────────────────────────────────────
// Der Speicherweg: Ziehen und Größenänderung
// ─────────────────────────────────────────────────────────────────────────────

/** Ein Termin-Objekt wie aus event-calendar (angezeigte, ausschließende Werte). */
function kalenderTermin(startStr, endStr, extra = {}) {
  const d = (s) => new Date(`${String(s).replace(' ', 'T')}`)
  return {
    id: 'EL-1',
    title: 'Gemeindefest',
    start: d(startStr),
    end: d(endStr),
    allDay: true,
    extendedProps: { element_calendar: 'Gemeinde', status: 'Festgelegt', ...extra },
  }
}

test('Drag eines eintägigen Termins bleibt eintägig (kein +1 Tag)', () => {
  // Angezeigt: ein Tag am 10.11. (Ende ausschließend = 11.11.)
  const w = speicherWerte(kalenderTermin('2026-11-10 00:00:00', '2026-11-11 00:00:00'))
  assert.equal(w.beginn, '2026-11-10 00:00:00')
  assert.equal(w.ende, '2026-11-10 00:00:00',
    'gespeichert einschließlich: Ende == Beginn für einen Tag')
  assert.equal(w.allDay, true)
})

test('Resize von 2 auf 3 Tage speichert 3 Tage', () => {
  // Angezeigt nach dem Ziehen am Rand: 10.11. – 12.11. (Ende ausschließend 13.11.)
  const w = speicherWerte(kalenderTermin('2026-11-10 00:00:00', '2026-11-13 00:00:00'))
  assert.equal(w.ende, '2026-11-12 00:00:00')
  assert.equal(dauerTage(w.beginn, w.ende), 3)
})

test('Verschieben eines mehrtägigen Termins erhält die Dauer', () => {
  // 7.–8. (gespeichert) → angezeigt 7.–9. → um eine Woche geschoben: 14.–16.
  const w = speicherWerte(kalenderTermin('2026-11-14 00:00:00', '2026-11-16 00:00:00'))
  assert.equal(w.beginn, '2026-11-14 00:00:00')
  assert.equal(w.ende, '2026-11-15 00:00:00')
  assert.equal(dauerTage(w.beginn, w.ende), 2, 'Dauer bleibt 2 Tage')
})

test('Termin MIT Uhrzeit wird nicht umgerechnet', () => {
  const t = kalenderTermin('2026-11-10 19:00:00', '2026-11-10 21:00:00')
  t.allDay = false
  const w = speicherWerte(t)
  assert.equal(w.ende, '2026-11-10 21:00:00')
})

test('Serienablösung beim Ziehen leert series_id (wie bisher)', () => {
  const t = kalenderTermin('2026-11-10 00:00:00', '2026-11-11 00:00:00', { series_id: 'SER-1' })
  assert.equal(speicherWerte(t, false).seriesId, 'SER-1')
  assert.equal(speicherWerte(t, true).seriesId, '')
})


// ─────────────────────────────────────────────────────────────────────────────
// Keine zweite Umrechnung im Speicherweg
// ─────────────────────────────────────────────────────────────────────────────

test('updateEvent speichert die Werte aus speicherWerte (kein rohes event.end mehr)', () => {
  const quelle = lies('src/diakonos/composables/useEventsApi.js')
  assert.match(quelle, /const werte = speicherWerte\(event, forceSeriesDetach\)/)
  assert.match(quelle, /element_end:\s+werte\.ende/)
  assert.ok(!/element_end:\s+toLocalDateTimeString\(effectiveEnd\)/.test(quelle),
    'das angezeigte Ende darf nicht mehr unverändert gespeichert werden')
  // Genau EINE Rückrechnung — in endeAusKalender.
  assert.match(quelle, /import \{ speicherWerte \} from '\.\/datumZeit\.mjs'/)
  const dz = lies('src/diakonos/composables/datumZeit.mjs')
  assert.equal((dz.match(/endeAusKalender\(/g) || []).length, 2,
    'datumZeit.mjs: Definition + Aufruf in speicherWerte, nichts sonst')
  assert.equal((dz.match(/setUTCDate\(d\.getUTCDate\(\) - 1\)/g) || []).length, 1,
    'datumZeit.mjs: genau EIN −1 Tag (endeAusKalender)')
})

test('der Kalender selbst rechnet beim Anzeigen weiterhin mit +1 Tag', () => {
  const quelle = lies('src/diakonos/components/kronos/KronosCalendar.vue')
  const zeilen = quelle.split('\n')
  const von = zeilen.findIndex((z) => z.includes('eventDrop:'))
  const bis = zeilen.findIndex((z) => z.includes('select: (info)'))
  const block = zeilen.slice(von, bis).join('\n')
  assert.ok(!/setDate|setUTCDate|addDays|endeFuerKalender/.test(block),
    'die Zieh-/Größen-Handler rechnen nicht selbst — das tut speicherWerte')
  assert.ok(block.includes('eventsApi.updateEvent(info.event'),
    'beide Handler gehen über updateEvent')
})
