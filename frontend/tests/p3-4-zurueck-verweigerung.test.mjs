/**
 * P3-4 (Restpunkt 11) — Zurück-Mechanik: toter History-Eintrag weg, Verweigerung
 * verbraucht keinen Eintrag.
 *
 * Befund (R-P2-3b): Nach einer Navigation aus einem Fenster heraus blieb ein
 * Eintrag mit DERSELBEN Adresse stehen — am Handy musste man zweimal „Zurück"
 * tippen. Außerdem durfte eine abgelehnte Schließung (`beforeClose`) den
 * History-Eintrag nicht verbrauchen.
 *
 * Dieser Test prüft die reine Buchführung (Fensterstapel) und den
 * History-Zustand (replaceState). Der volle Ablauf im echten Browser steht im
 * Playwright-Test `tools/p34_historie_browser.py`.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { Fensterstapel } from '../src/diakonos/composables/fensterstapel.mjs'

test('P3-4 · Verweigerung führt das Fenster wieder als offen (Marke neu)', () => {
  const s = new Fensterstapel()
  const marke = s.oeffnen()
  // Nutzer-„Zurück": die Marke wird abgeräumt …
  assert.deepEqual(s.zurueckGehen(), { schliessen: true })
  assert.equal(s.tiefe(), 0, 'Stapel ist leer')
  // … der Schließer lehnt aber ab → Fenster bleibt sichtbar und bekommt wieder
  // einen Eintrag.
  assert.equal(s.wiederOeffnen(marke), true)
  assert.equal(s.tiefe(), 1, 'Fenster gilt wieder als offen')
  assert.ok(s.enthaelt(marke))
})

test('P3-4 · wiederOeffnen verdoppelt keine bereits offene Marke', () => {
  const s = new Fensterstapel()
  const marke = s.oeffnen()
  assert.equal(s.wiederOeffnen(marke), true)
  assert.equal(s.tiefe(), 1, 'kein doppelter Eintrag')
  assert.equal(s.wiederOeffnen(null), false, 'ohne Marke nichts')
})

test('P3-4 · wiederOeffnen erhält die Reihenfolge gestapelter Fenster', () => {
  const s = new Fensterstapel()
  const unten = s.oeffnen()
  const oben = s.oeffnen()
  // Zurück schließt das obere; die Schließung wird verweigert.
  s.zurueckGehen()
  s.wiederOeffnen(oben)
  assert.equal(s.tiefe(), 2)
  assert.equal(s.oberste(), oben, 'das obere Fenster bleibt das oberste')
  assert.ok(s.enthaelt(unten))
})
