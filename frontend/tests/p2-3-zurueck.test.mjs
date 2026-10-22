/**
 * P2-3 · OP-HANDY-7 — Zurück-Taste/-Geste schließt Fenster.
 *
 * Befund: Das Termin-Fenster blieb nach „Zurück“ offen und blockierte Taps,
 * das „Mehr“-Blatt blieb offen (die Route wechselte dahinter), der Foto-Dialog
 * im Profil verließ die Seite ganz.
 *
 * Getestet wird der reine Fensterstapel (fensterstapel.mjs) — dieselbe Logik,
 * die useZurueckSchliesst an `history.pushState`/`popstate` bindet. So bleibt
 * der Test ohne Vue und ohne DOM lauffähig (wie die übrigen .mjs-Tests).
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { Fensterstapel } from '../src/diakonos/composables/fensterstapel.mjs'

test('OP-HANDY-7 · Öffnen legt genau einen Eintrag an', () => {
  const s = new Fensterstapel()
  const marke = s.oeffnen()
  assert.equal(typeof marke, 'number')
  assert.equal(s.tiefe(), 1)
  assert.ok(s.enthaelt(marke))
})

test('OP-HANDY-7 · Zurück (popstate) schließt das oberste Fenster', () => {
  const s = new Fensterstapel()
  s.oeffnen()
  assert.deepEqual(s.zurueckGehen(), { schliessen: true })
  assert.equal(s.tiefe(), 0)
})

test('OP-HANDY-7 · Schließen über ✕ verbraucht den eigenen Eintrag', () => {
  const s = new Fensterstapel()
  const marke = s.oeffnen()
  assert.deepEqual(s.schliessen(marke), { verbrauchen: true })
  assert.equal(s.tiefe(), 0)
})

test('OP-HANDY-7 · Schließen ohne eigenen Eintrag verbraucht nichts', () => {
  const s = new Fensterstapel()
  assert.deepEqual(s.schliessen(null), { verbrauchen: false })
})

test('OP-HANDY-7 · gestapelte Fenster: Zurück schließt nur das oberste', () => {
  const s = new Fensterstapel()
  s.oeffnen()
  s.oeffnen()
  assert.equal(s.tiefe(), 2)
  assert.deepEqual(s.zurueckGehen(), { schliessen: true })
  assert.equal(s.tiefe(), 1, 'nur ein Fenster schließen')
})

test('OP-HANDY-7 · kein Fenster offen: Zurück gehört nicht uns', () => {
  const s = new Fensterstapel()
  assert.deepEqual(s.zurueckGehen(), { schliessen: false })
})
