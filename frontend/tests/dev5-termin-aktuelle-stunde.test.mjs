/**
 * DEV-5 · Neuer Termin: Beginn = aktuelle Uhrzeit, auf die nächste volle
 * Stunde gerundet (Befund DMB-a47d9d08b72c, Rest).
 *
 * Bisher war der Vorschlag fest 19:00 (`VORSCHLAG_BEGINN`), egal wie spät es
 * war. Gewünscht: Der Beginn ist die nächste volle Stunde der Browserzeit,
 * das Ende liegt eine Stunde später. Wird ein Termin aus einem angeklickten
 * Kalendertag/-slot angelegt, gilt weiterhin der angeklickte Tag/Slot.
 *
 * Rot vor der Änderung, grün danach.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  vorschlagBeginn, vorschlagZeitraum, endeAusBeginn, VORSCHLAG_BEGINN,
} from '../src/diakonos/composables/datumZeit.mjs'

/** Fester Zeitpunkt als „jetzt" — Ortszeit, damit der Test überall gilt. */
const jetzt = (j, mon, t, h, mi) => new Date(j, mon - 1, t, h, mi, 0, 0)

// ── vorschlagBeginn: nächste volle Stunde ──────────────────────────────────

test('DEV-5 · 14:20 → 15:00 (nächste volle Stunde, aufgerundet)', () => {
  assert.equal(vorschlagBeginn(jetzt(2026, 10, 22, 14, 20)), '15:00')
})

test('DEV-5 · genau auf der vollen Stunde bleibt stehen (14:00 → 14:00)', () => {
  assert.equal(vorschlagBeginn(jetzt(2026, 10, 22, 14, 0)), '14:00')
})

test('DEV-5 · 14:59 → 15:00, 14:01 → 15:00', () => {
  assert.equal(vorschlagBeginn(jetzt(2026, 10, 22, 14, 59)), '15:00')
  assert.equal(vorschlagBeginn(jetzt(2026, 10, 22, 14, 1)), '15:00')
})

test('DEV-5 · 23:30 → nächster Tag 00:00 (Tageswechsel gemeldet)', () => {
  assert.equal(vorschlagBeginn(jetzt(2026, 10, 22, 23, 30)), '00:00')
  // Der Merker sagt, dass die Uhrzeit in den Folgetag rutscht.
  const v = vorschlagZeitraum(jetzt(2026, 10, 22, 23, 30), '2026-10-22')
  assert.equal(v.beginn, '00:00')
  assert.equal(v.datum, '2026-10-23', 'Datum muss auf den Folgetag wandern')
  assert.equal(v.endeDatum, '2026-10-23')
  assert.equal(v.ende, '01:00')
})

test('DEV-5 · 23:00 auf der Stunde → 23:00–00:00 am selben Tag', () => {
  const v = vorschlagZeitraum(jetzt(2026, 10, 22, 23, 0), '2026-10-22')
  assert.equal(v.datum, '2026-10-22')
  assert.equal(v.beginn, '23:00')
  // Ende 1 h später: Mitternacht ist der Folgetag.
  assert.equal(v.ende, '00:00')
  assert.equal(v.endeDatum, '2026-10-23')
})

// ── angeklickter Tag/Slot hat Vorrang ──────────────────────────────────────

test('DEV-5 · angeklickter Tag bleibt, nur die Uhrzeit kommt von jetzt', () => {
  const v = vorschlagZeitraum(jetzt(2026, 10, 22, 14, 20), '2026-11-08')
  assert.equal(v.datum, '2026-11-08')
  assert.equal(v.beginn, '15:00')
  assert.equal(v.endeDatum, '2026-11-08')
  assert.equal(v.ende, '16:00')
})

test('DEV-5 · angeklickter Slot schlägt die gerundete Uhrzeit', () => {
  const v = vorschlagZeitraum(jetzt(2026, 10, 22, 14, 20), '2026-11-08', '19:30')
  assert.equal(v.datum, '2026-11-08')
  assert.equal(v.beginn, '19:30', 'Slot-Zeit gilt unverändert')
  assert.equal(v.ende, '20:30')
  assert.equal(v.endeDatum, '2026-11-08')
})

test('DEV-5 · ohne angeklickten Tag gilt der Tag von jetzt', () => {
  const v = vorschlagZeitraum(jetzt(2026, 10, 22, 9, 5), '')
  assert.equal(v.datum, '2026-10-22')
  assert.equal(v.beginn, '10:00')
  assert.equal(v.ende, '11:00')
})

// ── unverändert: Ende = Beginn + 1 h ───────────────────────────────────────

test('DEV-5 · Ende bleibt eine Stunde nach dem Beginn', () => {
  assert.equal(endeAusBeginn(vorschlagBeginn(jetzt(2026, 10, 22, 14, 20))), '16:00')
  assert.equal(VORSCHLAG_BEGINN, '19:00', 'Altkonstante bleibt (Rückfall/Anzeige)')
})
