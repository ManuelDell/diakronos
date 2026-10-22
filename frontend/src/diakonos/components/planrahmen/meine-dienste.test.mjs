/**
 * P1-11 — Reproduktionstests zur Mitglieder-Sicht „Meine Dienste".
 *
 * Deckt die Befunde des Pakets P1-11 ab, soweit sie reine Anzeigelogik sind:
 *   OP-CHOR-7  Lied/Uhrzeit/Mitwirkende statt „Solo — Du bist eingeteilt".
 *   OP-HANDY-18 Konflikthinweis bei gemeldeter Abwesenheit.
 *
 * Lauf: node --test (siehe backend/Dockerfile Stage 1).
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { feldName, rollenText, mitwirkendeText, istKonflikt, ohneDubletten, kachelEintraege } from './meine-dienste.mjs'

test('Feldname zeigt die Rolle, nicht den internen Pfad (OP-CHOR-7)', () => {
  assert.equal(feldName('lieder[1].solo'), 'Solo')
  assert.equal(feldName('lieder[0].dirigent'), 'Dirigent')
  assert.equal(feldName('einueben'), 'Einueben')
  assert.equal(feldName(''), 'Dienst')
  assert.equal(feldName('gd:leitung'), 'Leitung')
})

test('Mitwirkende werden als „Rolle: Name" gelesen (OP-CHOR-7)', () => {
  assert.equal(
    mitwirkendeText([
      { rolle: 'dirigent', name: 'D. Krüger' },
      { rolle: 'klavier', name: 'I. Beispiel' },
      { rolle: 'solo', name: 'O. Braun' },
    ]),
    'Dirigent: D. Krüger · Klavier: I. Beispiel · Solo: O. Braun',
  )
})

test('Unbekannte Rollen bleiben roh, leere Liste ergibt leeren Text', () => {
  assert.equal(rollenText('obergruppe'), 'obergruppe')
  assert.equal(mitwirkendeText([]), '')
  assert.equal(mitwirkendeText(null), '')
})

test('Konflikthinweis nur bei tatsaechlich gemeldeter Abwesenheit (OP-HANDY-18)', () => {
  assert.equal(istKonflikt({ abwesend: true }), true)
  assert.equal(istKonflikt({ abwesend: false }), false)
  assert.equal(istKonflikt({}), false)
  assert.equal(istKonflikt(null), false)
})

// ── P1-11b Befund 4: Dashboard-Kachel ohne Doppelzaehlung ──────────────────

test('Kachel fuehrt beide Quellen zusammen und entfernt Dubletten (Befund 4)', () => {
  const plan = [
    { titel: 'Chorprobe', sort: '2026-11-15T19:00', art: 'Einsatz', rolle: 'Solo' },
  ]
  // Derselbe Einsatz liegt auch im alten Kronos-Modell (Titel + Zeitpunkt gleich).
  const alt = [
    { titel: 'Chorprobe', sort: '2026-11-15T19:00', art: 'Einsatz', rolle: 'Solo' },
    { titel: 'Einsingen', sort: '2026-11-14T18:00', art: 'Vorbereitung', rolle: '' },
  ]
  const zusammen = kachelEintraege(plan, alt)
  assert.equal(zusammen.length, 2, JSON.stringify(zusammen))
  assert.deepEqual(zusammen.map((e) => e.titel), ['Einsingen', 'Chorprobe'])
  // Bei Gleichstand gewinnt der Plan-Rahmen (er steht vorn).
  assert.equal(zusammen[1].art, 'Einsatz')
})

test('Kachel zaehlt verschiedene Einsaetze weiterhin vollstaendig', () => {
  const plan = [
    { titel: 'Chorprobe', sort: '2026-11-15T19:00' },
    { titel: 'Chorprobe', sort: '2026-11-22T19:00' },   // anderer Termin
  ]
  const alt = [{ titel: 'Chorprobe', sort: '2026-11-15T19:00' }]
  assert.equal(kachelEintraege(plan, alt).length, 2)
  assert.equal(ohneDubletten([]).length, 0)
  assert.equal(ohneDubletten(null).length, 0)
})
