/**
 * ICAL-1 — ganztägiges Ende: EINE Regel an jeder Grenze.
 *
 * Diakronos speichert das Ende ganztägiger Termine EINSCHLIESSLICH
 * (Formular: „7.–8.“ = zwei Tage, eintägig Ende == Beginn). Alles, was mit
 * der Außenwelt oder mit einer FullCalendar-artigen Bibliothek spricht, zählt
 * AUSSCHLIESSEND (RFC 5545 / Google / event-calendar):
 *
 *     Diakronos    7. .. 8.     7. .. 7.
 *     iCal/Google  DTSTART 7., DTEND 9.     DTSTART 7., DTEND 8.
 *     Monatsraster start 7.,  end 9.        start 7.,  end 8.
 *
 * Befund beim Bau dieser Karte: der Monatsraster zeigte den Termin 7.–8. NUR
 * am 7. — die Bibliothek liest `end` ausschließend (FullCalendar-Doku:
 * „end of 2018-09-03 → spans through 2018-09-02“). Deshalb gibt es jetzt an
 * JEDER Grenze genau eine Umrechnung und nirgends eine zweite.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

import { endeFuerKalender, tageDazwischen, zeitraumText } from '../src/diakonos/composables/datumZeit.mjs'
import { terminZeitText } from '../src/diakonos/composables/bf1Anzeige.js'

const hier = dirname(fileURLToPath(import.meta.url))
const lies = (rel) => readFileSync(resolve(hier, '..', rel), 'utf8')


// ─────────────────────────────────────────────────────────────────────────────
// Die Umrechnung für den Kalender (+1 Tag, nur ganztägig)
// ─────────────────────────────────────────────────────────────────────────────

test('zweitägig ganztägig: aus end 8. wird 9. (Bibliothek zeigt 7. und 8.)', () => {
  assert.equal(endeFuerKalender('2026-11-08 00:00:00', true), '2026-11-09 00:00:00')
})

test('eintägig ganztägig: aus end 7. wird 8.', () => {
  assert.equal(endeFuerKalender('2026-11-07 00:00:00', true), '2026-11-08 00:00:00')
})

test('über den Monats-/Jahreswechsel', () => {
  assert.equal(endeFuerKalender('2026-12-31 00:00:00', true), '2027-01-01 00:00:00')
  assert.equal(endeFuerKalender('2026-02-28', true), '2026-03-01')
})

test('Termin MIT Uhrzeit bleibt unverändert', () => {
  assert.equal(endeFuerKalender('2026-11-07 10:30:00', false), null)
})

test('ohne Ende bleibt „kein Ende“ (Bibliothek nimmt den Beginn)', () => {
  assert.equal(endeFuerKalender(null, true), null)
  assert.equal(endeFuerKalender('', true), null)
})

test('unlesbares Ende wird nicht erfunden', () => {
  assert.equal(endeFuerKalender('kaputt', true), null)
})


// ─────────────────────────────────────────────────────────────────────────────
// Der Kalender benutzt genau diese Umrechnung — und keine eigene
// ─────────────────────────────────────────────────────────────────────────────

test('Kalender rechnet mit endeFuerKalender, nicht selbst', () => {
  const quelle = lies('src/diakonos/components/kronos/KronosCalendar.vue')
  const zeilen = quelle.split('\n')
  const von = zeilen.findIndex((z) => z.includes('const processedEvents'))
  const bis = zeilen.findIndex((z) => z.includes('successCallback(processedEvents)'))
  assert.ok(von > 0 && bis > von, 'Sendeweg gefunden')
  const block = zeilen.slice(von, bis).join('\n')
  assert.ok(block.includes('endeFuerKalender(ev.end, ev.allDay)'),
    'Der Sendeweg nutzt die gemeinsame Umrechnung')
  assert.ok(!/addDays|setDate|\.setUTCDate\(/.test(block),
    'Keine zweite Tagesarithmetik im Sendeweg')
})


// ─────────────────────────────────────────────────────────────────────────────
// Die Anzeige-Texte zählen weiter einschließend (menschliche Sicht)
// ─────────────────────────────────────────────────────────────────────────────

test('zweitägiger Termin zählt zwei Tage', () => {
  assert.equal(tageDazwischen('2026-11-07', '2026-11-08'), 1)
  assert.equal(zeitraumText('2026-11-07', '2026-11-08'), '2 Tage (Sa.–So.)')
})

test('eintägiger Termin nennt keinen Zeitraum', () => {
  assert.equal(zeitraumText('2026-11-07', '2026-11-07'), '')
})

test('eintägiger Ganztagstermin ist als solcher benannt', () => {
  assert.equal(terminZeitText('2026-11-07 00:00:00', '2026-11-07 00:00:00', true),
    'Sa., 07.11. · ganztägig')
})

test('mehrtägiger Ganztagstermin nennt BEIDE Tage', () => {
  assert.equal(terminZeitText('2026-11-07 00:00:00', '2026-11-08 00:00:00', true),
    'Sa., 07.11. – So., 08.11. · ganztägig')
})

test('Termin mit Uhrzeit zeigt die Beginnzeit', () => {
  assert.equal(terminZeitText('2026-11-07 09:00:00', '2026-11-07 10:30:00', false),
    'Sa., 07.11. · 09:00 Uhr')
})


// ─────────────────────────────────────────────────────────────────────────────
// Genau eine Umrechnung je Grenze (Gegenprobe zur Backend-Seite)
// ─────────────────────────────────────────────────────────────────────────────

test('Export, Import und Anzeige rechnen je genau einmal um', () => {
  const exportQuelle = lies('../backend/src/diakronos_app/caldav/ical.py')
  assert.equal((exportQuelle.match(/timedelta\(days=1\)/g) || []).length, 1,
    'Export: genau EIN +1 Tag (ganztags)')

  const importQuelle = lies('../backend/src/diakronos_app/api/kronos/google_import.py')
  assert.equal((importQuelle.match(/- timedelta\(days=1\)/g) || []).length, 2,
    'Import: genau ZWEI −1 Tag (API-JSON und ICS-Dauer)')

  const anzeige = lies('src/diakonos/composables/datumZeit.mjs')
  assert.equal((anzeige.match(/setUTCDate\(d\.getUTCDate\(\) \+ 1\)/g) || []).length, 1,
    'Anzeige: genau EIN +1 Tag (endeFuerKalender)')
})

test('das Backend liefert das gespeicherte Ende unverändert', () => {
  const quelle = lies('../backend/src/diakronos_app/api/kronos/calendar_get.py')
  assert.match(quelle, /"end": str\(end\) if end else None,/)
  // Der Grenzfall Mitternacht wird nur für die Überlappungsprüfung um 1 s
  // zurückgenommen — die ausgelieferten Daten bleiben unverändert.
  assert.match(quelle, /e = e - timedelta\(seconds=1\)/)
})
