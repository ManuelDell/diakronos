import test from 'node:test'
import assert from 'node:assert/strict'
import {
  entwurfKern, bereinigen, ENTWURF_TTL_MS, ENTWURF_PRAEFIX, SENSIBLE_FELDER,
} from './useEntwurf.js'

/** Minimaler In-Memory-Storage für die Tests. */
function speicherFabrik() {
  const daten = new Map()
  return {
    getItem: (k) => (daten.has(k) ? daten.get(k) : null),
    setItem: (k, v) => { daten.set(k, String(v)) },
    removeItem: (k) => { daten.delete(k) },
    _daten: daten,
  }
}

test('speichert und lädt einen Entwurf pro Benutzer + Zweck', () => {
  const s = speicherFabrik()
  const a = entwurfKern({ speicher: s, benutzer: () => 'a@test' })
  const b = entwurfKern({ speicher: s, benutzer: () => 'b@test' })
  a.speichern('neuer-plan', { titel: 'Chor 2026' })
  assert.deepEqual(a.lade('neuer-plan'), { titel: 'Chor 2026' })
  // Anderer Benutzer sieht den Entwurf nicht (eigener Schlüsselraum).
  assert.equal(b.lade('neuer-plan'), null)
  // Anderer Zweck teilt sich den Speicher nicht.
  assert.equal(a.lade('plantyp-editor'), null)
})

test('Schlüssel tragen Präfix, Benutzer und Zweck', () => {
  const s = speicherFabrik()
  const k = entwurfKern({ speicher: s, benutzer: () => 'a@test' })
  assert.equal(k.schluessel('neuer-plan'), `${ENTWURF_PRAEFIX}a@test:neuer-plan`)
})

test('nach 14 Tagen gilt ein Entwurf als abgelaufen und wird verworfen', () => {
  const s = speicherFabrik()
  let jetzt = 1_000_000_000_000
  const k = entwurfKern({ speicher: s, benutzer: () => 'a', jetzt: () => jetzt })
  k.speichern('x', { titel: 'alt' })
  jetzt += ENTWURF_TTL_MS + 1
  assert.equal(k.lade('x'), null)
  assert.equal(k.info('x'), null)
  // Auch physisch entfernt — kein Grusel im Speicher.
  assert.equal(s.getItem(k.schluessel('x')), null)
})

test('innerhalb von 14 Tagen bleibt der Entwurf erhalten', () => {
  const s = speicherFabrik()
  let jetzt = 1_000_000_000_000
  const k = entwurfKern({ speicher: s, benutzer: () => 'a', jetzt: () => jetzt })
  k.speichern('x', { titel: 'jung' })
  jetzt += ENTWURF_TTL_MS - 1
  assert.deepEqual(k.lade('x'), { titel: 'jung' })
})

test('info liefert Zeit und Titel für „fortsetzen / verwerfen"', () => {
  const s = speicherFabrik()
  const k = entwurfKern({ speicher: s, benutzer: () => 'a', jetzt: () => 42 })
  k.speichern('neuer-plan', { titel: 'Chor 2026' }, { titel: 'Chor 2026' })
  assert.deepEqual(k.info('neuer-plan'), { zeit: 42, titel: 'Chor 2026' })
})

test('entfernen löscht den Entwurf', () => {
  const s = speicherFabrik()
  const k = entwurfKern({ speicher: s, benutzer: () => 'a' })
  k.speichern('x', { a: 1 })
  k.entfernen('x')
  assert.equal(k.lade('x'), null)
})

test('leere Eingaben werden nicht als Entwurf gesichert (löschen)', () => {
  const s = speicherFabrik()
  const k = entwurfKern({ speicher: s, benutzer: () => 'a' })
  k.speichern('x', { titel: 'da' })
  // Leer sichern entfernt den vorhandenen Entwurf (z. B. nach erfolgreichem Speichern).
  k.sichern('x', '')
  assert.equal(k.lade('x'), null)
  assert.equal(k.sichern('x', null), false)
  assert.equal(k.sichern('x', []), false)
  assert.equal(k.sichern('x', {}), false)
})

test('ein gesperrter Speicher unterbricht die Bedienung nicht', () => {
  const kaputt = {
    getItem: () => { throw new Error('gesperrt') },
    setItem: () => { throw new Error('voll') },
    removeItem: () => { throw new Error('gesperrt') },
  }
  const k = entwurfKern({ speicher: kaputt, benutzer: () => 'a' })
  assert.equal(k.speichern('x', { a: 1 }), false)
  assert.equal(k.lade('x'), null)
  assert.doesNotThrow(() => k.entfernen('x'))
})

test('ohne Speicher (privater Modus) läuft alles still weiter', () => {
  const k = entwurfKern({ speicher: null, benutzer: () => 'a' })
  assert.equal(k.speichern('x', { a: 1 }), false)
  assert.equal(k.lade('x'), null)
})

test('kaputter Speicherinhalt wird ignoriert statt zu werfen', () => {
  const s = speicherFabrik()
  const k = entwurfKern({ speicher: s, benutzer: () => 'a' })
  s.setItem(k.schluessel('x'), '{nicht json')
  assert.equal(k.lade('x'), null)
})

test('sensible Felder werden nie persistiert', () => {
  const s = speicherFabrik()
  const k = entwurfKern({ speicher: s, benutzer: () => 'a' })
  k.speichern('x', {
    titel: 'Freizeit',
    abwesenheiten: [{ mitglied: 'm1', grund: 'krank' }],
    detail: { abwesenheitsgrund: 'privat' },
  })
  const roh = s.getItem(k.schluessel('x'))
  assert.ok(!roh.includes('krank'), 'Abwesenheitsgrund darf nicht im Speicher stehen')
  assert.ok(!roh.includes('privat'), 'geschachtelter Grund darf nicht im Speicher stehen')
  assert.deepEqual(k.lade('x'), { titel: 'Freizeit', abwesenheiten: [{ mitglied: 'm1' }], detail: {} })
})

test('bereinigen kopiert und entfernt sensible Felder rekursiv', () => {
  const eingang = { a: 1, grund: 'x', liste: [{ grund: 'y', b: 2 }] }
  const ausgang = bereinigen(eingang)
  assert.deepEqual(ausgang, { a: 1, liste: [{ b: 2 }] })
  // Original unangetastet.
  assert.deepEqual(eingang, { a: 1, grund: 'x', liste: [{ grund: 'y', b: 2 }] })
  assert.ok(SENSIBLE_FELDER.includes('grund'))
})
