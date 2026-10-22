import test from 'node:test'
import assert from 'node:assert/strict'
import { suchNormal, passtZurSuche, terminZeitText, terminAnzeige } from './bf1Anzeige.js'

// ── J) Suche ohne Ruecksicht auf Gross-/Kleinschreibung und Umlaute ──────────

test('suchNormal: Kleinschreibung, Umlaute und ss', () => {
  assert.equal(suchNormal('MÜLLER'), 'mueller')
  assert.equal(suchNormal('Weiß'), 'weiss')
  assert.equal(suchNormal('  Ärger  '), 'aerger')
  assert.equal(suchNormal(null), '')
})

test('passtZurSuche: egal ob gross/klein getippt', () => {
  const m = { name: 'Anna Müller', email: 'Anna.Mueller@example.org' }
  assert.ok(passtZurSuche(m, 'müller'))
  assert.ok(passtZurSuche(m, 'MÜLLER'))
  assert.ok(passtZurSuche(m, 'mueller'))
  assert.ok(passtZurSuche(m, 'anna.mueller@'))
  assert.ok(passtZurSuche(m, ''))          // leere Suche passt immer
  assert.ok(!passtZurSuche(m, 'bernhard'))
})

test('passtZurSuche: Umlaut und Ersatzschreibweise sind gleichwertig', () => {
  assert.ok(passtZurSuche({ name: 'Jörg Weiß' }, 'joerg'))
  assert.ok(passtZurSuche({ name: 'Jörg Weiß' }, 'weiss'))
  assert.ok(passtZurSuche({ name: 'Jörg Weiß' }, 'JÖRG'))
})

// ── G) Kachel: Zeit- und Termin-Anzeige ohne interne ID ──────────────────────

test('terminZeitText: Uhrzeit-Termin', () => {
  const t = terminZeitText('2026-10-02 15:00', '2026-10-02 16:00')
  assert.match(t, /15:00 Uhr/)
  assert.match(t, /02\.10\./)
})

test('terminZeitText: ganztägig', () => {
  assert.match(terminZeitText('2026-10-03 00:00', '2026-10-04 00:00'), /ganztägig/)
})

test('terminZeitText: ohne Start', () => {
  assert.equal(terminZeitText(null, null), 'Zeit unbekannt')
})

// K10: Mehrtägige Termine nennen den Tagesbereich, das all_day-Kennzeichen
// kommt vom Server (kein Raten aus 00:00).
test('terminZeitText: mehrtägig nennt beide Tage', () => {
  const t = terminZeitText('2026-10-14 10:00', '2026-10-16 12:00')
  assert.match(t, /14\.10\./)
  assert.match(t, /16\.10\./)
})

test('terminZeitText: all_day=true wird ganztägig genannt', () => {
  // Echtes Ganztages-Element mit abweichender Endzeit: ohne das Kennzeichen
  // würde es als Uhrzeit-Termin erscheinen.
  assert.match(terminZeitText('2026-10-03 08:00', '2026-10-03 09:00', true), /ganztägig/)
})

test('terminZeitText: all_day mehrtägig nennt Tagesbereich', () => {
  const t = terminZeitText('2026-10-03 00:00', '2026-10-05 00:00', true)
  assert.match(t, /ganztägig/)
  assert.match(t, /03\.10\./)
  assert.match(t, /05\.10\./)
})

test('terminAnzeige: nennt Titel/Zeit/Ort und KEINE interne ID', () => {
  const a = terminAnzeige({
    name: 'EL000493',
    element_name: 'Bibelstunde',
    element_start: '2026-10-02 18:00',
    element_end: '2026-10-02 19:00',
    ressource: 'Gemeindehaus',
    element_calendar: 'KAL-PUB',
  })
  assert.equal(a.titel, 'Bibelstunde')
  assert.equal(a.ort, 'Gemeindehaus')
  // Die interne ID darf nur als technischer Schluessel (Vue :key) vorkommen,
  // nie in einem sichtbaren Feld.
  const sichtbar = [a.titel, a.zeit, a.ort, a.calendar].join(' ')
  assert.ok(!sichtbar.includes('EL000493'), 'interne ID darf nicht angezeigt werden')
  assert.equal(a.schluessel, 'EL000493')
})

test('terminAnzeige: faellt auf den Kalender zurueck, wenn kein Ort', () => {
  const a = terminAnzeige({ name: 'EL-9', element_name: 'Chor', element_start: '2026-10-02 18:00', element_calendar: 'Musik' })
  assert.equal(a.ort, 'Musik')
})
