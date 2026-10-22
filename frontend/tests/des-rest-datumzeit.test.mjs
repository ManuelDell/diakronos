/**
 * OP-UI-20 · DkDatumZeit — Datum und Uhrzeit überall gleich (Standard S8).
 *
 * Befund: vier Eingabearten und ein sichtbarer ISO-Wert „2026-12-30 00:00“.
 * Geprüft wird hier die Logik des Bausteins (deutsche Anzeige, ISO im Modell,
 * Vorschlag 19:00–20:00, Wochenbeginn Montag, unvollständige Angaben).
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  zerlegeDatumZeit, baueDatumZeit, datumDeutsch, zeitDeutsch, wochentag,
  vorschau, endeAusBeginn, vorschlagBeginn, pruefeZeitraum, istDatum,
  monatName, VORSCHLAG_BEGINN,
} from '../src/diakonos/composables/datumZeit.mjs'

test('OP-UI-20 · Serverformate werden verstanden (Leerzeichen und T)', () => {
  assert.deepEqual(zerlegeDatumZeit('2026-12-30 19:00'), { datum: '2026-12-30', zeit: '19:00' })
  assert.deepEqual(zerlegeDatumZeit('2026-12-30T19:00:00'), { datum: '2026-12-30', zeit: '19:00' })
  assert.deepEqual(zerlegeDatumZeit('2026-12-30T09:05'), { datum: '2026-12-30', zeit: '09:05' })
})

test('OP-UI-20 · ein reines Datum erfindet keine 00:00-Uhrzeit', () => {
  // Genau das zeigte der Befund als ISO „2026-12-30 00:00“ im Termin-Dialog.
  assert.deepEqual(zerlegeDatumZeit('2026-12-30'), { datum: '2026-12-30', zeit: '' })
})

test('OP-UI-20 · Unlesbares ergibt leere Felder statt NaN', () => {
  for (const wert of ['', null, undefined, 'morgen', '30.12.2026', '2026-13']) {
    assert.deepEqual(zerlegeDatumZeit(wert), { datum: '', zeit: '' })
  }
})

test('OP-UI-20 · Modellwert bleibt das Serverformat', () => {
  assert.equal(baueDatumZeit('2026-12-30', '19:00'), '2026-12-30 19:00')
  assert.equal(baueDatumZeit('2026-12-30', '9:5'), '2026-12-30 09:05')
  assert.equal(baueDatumZeit('2026-12-30', ''), '2026-12-30')
  // Ohne gültiges Datum entsteht kein Wert (der Server würde ihn ablehnen).
  assert.equal(baueDatumZeit('', '19:00'), '')
  assert.equal(baueDatumZeit('30.12.2026', '19:00'), '')
})

test('OP-UI-20 · deutsch angezeigt, unabhängig von der Browsersprache', () => {
  assert.equal(datumDeutsch('2026-12-30'), '30.12.2026')
  assert.equal(zeitDeutsch('19:00'), '19:00 Uhr')
  assert.equal(zeitDeutsch('9:05'), '09:05 Uhr')
  assert.equal(datumDeutsch(''), '')
})

test('OP-UI-20 · Wochentag stimmt (30.12.2026 ist ein Mittwoch)', () => {
  assert.deepEqual(wochentag('2026-12-30'), { lang: 'Mittwoch', kurz: 'Mi.' })
  assert.deepEqual(wochentag('2026-10-19'), { lang: 'Montag', kurz: 'Mo.' })
  assert.deepEqual(wochentag(''), { lang: '', kurz: '' })
})

test('OP-UI-20 · Vorschau nennt Tag, Datum und Zeit', () => {
  assert.equal(vorschau('2026-12-30', '19:00', '20:00'), 'Mi., 30.12.2026, 19:00–20:00 Uhr')
  assert.equal(vorschau('2026-12-30', '19:00'), 'Mi., 30.12.2026, 19:00 Uhr')
  assert.equal(vorschau('2026-12-30', ''), 'Mi., 30.12.2026')
  assert.equal(vorschau('', '19:00'), '')
})

test('OP-UI-20 · Vorschlag ist 19:00–20:00 (S8)', () => {
  assert.equal(VORSCHLAG_BEGINN, '19:00')
  assert.equal(vorschlagBeginn(), '19:00')
  assert.equal(endeAusBeginn('19:00'), '20:00')
})

test('OP-UI-20 · angeklickte Stunde schlägt den Vorschlag', () => {
  assert.equal(vorschlagBeginn(9), '09:00')
  assert.equal(vorschlagBeginn(0), '00:00')
  assert.equal(vorschlagBeginn(23), '23:00')
  // Unsinn fällt auf den Standard zurück.
  assert.equal(vorschlagBeginn(24), '19:00')
  assert.equal(vorschlagBeginn('x'), '19:00')
})

test('OP-UI-20 · Ende über Mitternacht wird gekappt, nicht negativ', () => {
  assert.equal(endeAusBeginn('23:30'), '23:59')
  assert.equal(endeAusBeginn(''), '')
})

test('OP-UI-20 · Zeitraum wird verständlich geprüft', () => {
  assert.equal(pruefeZeitraum('19:00', '20:00'), '')
  assert.equal(pruefeZeitraum('19:00', '18:00'), 'Das Ende liegt vor dem Beginn.')
  assert.equal(pruefeZeitraum('19:00', '19:00'), 'Beginn und Ende sind gleich — der Termin hätte keine Dauer.')
  assert.equal(pruefeZeitraum('', '20:00'), '')
})

test('OP-UI-20 · Kalendertage werden geprüft (31.02. gibt es nicht)', () => {
  assert.equal(istDatum('2026-12-30'), true)
  assert.equal(istDatum('2026-02-31'), false)
  assert.equal(istDatum('2026-13-01'), false)
  assert.equal(istDatum(''), false)
})

test('OP-UI-20 · Monatsnamen sind deutsch', () => {
  assert.equal(monatName(12), 'Dezember')
  assert.equal(monatName(3), 'März')
  assert.equal(monatName(13), '')
})

// ── OP-UI-20, vierte Eingabeart: Treffzeit als Wochenrhythmus ───────────────

import {
  normiereWochentag, normiereUhrzeit, baueTreffzeit, anzeigeTreffzeit,
  zerlegeTreffzeit, sprechTreffzeit, WOCHENTAGE,
} from '../src/diakonos/composables/treffzeit.mjs'

test('OP-UI-20 · Treffzeit: Wochentag in allen üblichen Schreibweisen', () => {
  for (const wert of ['Montag', 'montag', 'Mo', 'Mo.', 'montags']) {
    assert.equal(normiereWochentag(wert), 'Montag', wert)
  }
  assert.equal(normiereWochentag('Di 19:30'), 'Dienstag')
  assert.equal(normiereWochentag('Sonnabend'), 'Samstag')
  assert.equal(normiereWochentag('nach Absprache'), '')
  assert.equal(WOCHENTAGE.length, 7)
})

test('OP-UI-20 · Treffzeit: Uhrzeit in allen üblichen Schreibweisen', () => {
  assert.equal(normiereUhrzeit('19:30'), '19:30')
  assert.equal(normiereUhrzeit('19.30'), '19:30')
  assert.equal(normiereUhrzeit('19:30 Uhr'), '19:30')
  assert.equal(normiereUhrzeit('9'), '09:00')
  assert.equal(normiereUhrzeit('24:00'), '')
  assert.equal(normiereUhrzeit(''), '')
})

test('OP-UI-20 · Treffzeit: altes Freitextfeld wird einheitlich zusammengesetzt', () => {
  assert.equal(baueTreffzeit('Dienstag', '19:30'), 'Dienstag 19:30')
  assert.equal(baueTreffzeit('Dienstag', ''), 'Dienstag')
  assert.equal(baueTreffzeit('', '19:30'), '19:30')
  assert.equal(baueTreffzeit('', ''), '')
})

test('OP-UI-20 · Treffzeit: Altschreibweisen werden angezeigt, nicht verworfen', () => {
  assert.equal(anzeigeTreffzeit('Di 19.30'), 'Dienstag 19:30')
  assert.equal(anzeigeTreffzeit('dienstags 19:30 Uhr'), 'Dienstag 19:30')
  // Was kein Rhythmus ist, bleibt unangetastet.
  assert.equal(anzeigeTreffzeit('nach Absprache'), 'nach Absprache')
  assert.equal(anzeigeTreffzeit(''), '')
})

test('OP-UI-20 · Treffzeit: Zerlegung und Sprechtext', () => {
  assert.deepEqual(zerlegeTreffzeit('Dienstag 19:30'), { wochentag: 'Dienstag', zeit: '19:30', rest: '' })
  assert.equal(sprechTreffzeit('Dienstag 19:30'), 'Dienstag, 19:30 Uhr')
  assert.equal(sprechTreffzeit('nach Absprache'), 'nach Absprache')
})

// ── OP-UI-20: Verdrahtung im Organigramm (Wochentag + Uhrzeit statt Freitext) ─

test('OP-UI-20 · Organigramm: Treffzeit kommt aus zwei Feldern', async () => {
  const { readFileSync } = await import('node:fs')
  const quelle = readFileSync(
    new URL('../src/diakonos/components/gruppen/OrganigrammAnsicht.vue', import.meta.url), 'utf8')
  // Wochentag als Auswahl, Uhrzeit als Zeitfeld — kein freies Textfeld mehr.
  assert.match(quelle, /aria-label="Wochentag"/)
  assert.match(quelle, /type="time"/)
  assert.ok(!/placeholder="z\.B\. Dienstag 19:30"/.test(quelle), 'Freitext-Treffzeit ist zurück')
  // Gespeichert wird weiterhin der Text — bestehende Werte bleiben gültig.
  assert.match(quelle, /treffzeitAusFeldern\(\)/)
  assert.match(quelle, /baueTreffzeit\(treffzeitTag\.value, treffzeitUhr\.value\)/)
})
