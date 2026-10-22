/**
 * P2-3 · DES-R22 — Dunkelmodus am Handy erreichbar, Systemeinstellung beachtet.
 *
 * Befund: Der Umschalter lag nur in der Seitenleiste (am Handy `display:none`,
 * Knopfbreite 0); der Startwert kam fest aus 'light', die Systemeinstellung
 * (`prefers-color-scheme: dark`) wurde ignoriert.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { startTheme, naechstesTheme, umschalterText, THEME_SCHLUESSEL } from '../src/diakonos/composables/theme.mjs'

function speicherMit(wert) {
  return { getItem: (k) => (k === THEME_SCHLUESSEL ? wert : null) }
}

test('DES-R22 · ohne Wahl folgt das Theme der Systemeinstellung', () => {
  assert.equal(startTheme({ speicher: speicherMit(null), system: 'dark' }), 'dark')
  assert.equal(startTheme({ speicher: speicherMit(null), system: 'light' }), 'light')
})

test('DES-R22 · die bewusste Wahl schlägt die Systemeinstellung', () => {
  assert.equal(startTheme({ speicher: speicherMit('light'), system: 'dark' }), 'light')
  assert.equal(startTheme({ speicher: speicherMit('dark'), system: 'light' }), 'dark')
})

test('DES-R22 · ohne beides bleibt es hell', () => {
  assert.equal(startTheme({ speicher: speicherMit(null), system: null }), 'light')
  assert.equal(startTheme({}), 'light')
})

test('DES-R22 · ein gesperrter Speicher stürzt nicht ab', () => {
  const kaputt = { getItem() { throw new Error('gesperrt') } }
  assert.equal(startTheme({ speicher: kaputt, system: 'dark' }), 'dark')
})

test('DES-R22 · Umschalten wechselt zwischen hell und dunkel', () => {
  assert.equal(naechstesTheme('light'), 'dark')
  assert.equal(naechstesTheme('dark'), 'light')
})

test('DES-R22 · der Umschalter nennt das Ziel', () => {
  assert.equal(umschalterText('light'), 'Dunkel-Modus')
  assert.equal(umschalterText('dark'), 'Hell-Modus')
})
