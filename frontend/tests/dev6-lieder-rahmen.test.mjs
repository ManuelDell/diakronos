/**
 * DEV-6 — Lieder in der Plan-Tabelle unterscheidbar machen
 * (Befund DMB-45e5dfcda737).
 *
 * Befund: In einer Zelle standen mehrere Lieder nur durch `margin-top: 3px`
 * getrennt, ohne Rahmen — sie fielen zu einem Textblock zusammen. Gewuenscht
 * (Manuel): kleine Rahmen um jedes Lied.
 *
 * Der Test prueft die Entscheidungslogik (welche Spalte ist eine Lied-Spalte,
 * welche Zeile bekommt einen Rahmen) und die Umsetzung in PrTabelle.vue:
 * Rahmenklasse mit Design-Tokens (kein harter Farbwert), fuer Desktop-Zeilen
 * UND fuer die mobilen Karten (< 640 px).
 *
 * Lauf: node --test (siehe backend/Dockerfile Stage 1).
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { istLiedSpalte, zellZeilen, LIEDER_SAMMLUNG } from '../src/diakonos/components/planrahmen/lied-rahmen.mjs'

const HIER = dirname(fileURLToPath(import.meta.url))
const TABELLE = readFileSync(
  join(HIER, '..', 'src', 'diakonos', 'components', 'planrahmen', 'PrTabelle.vue'), 'utf8')

// ── Spaltenerkennung ───────────────────────────────────────────────────────

test('DEV-6 · eintrag-Feld der Sammlung „lieder" ist eine Lied-Spalte', () => {
  assert.equal(LIEDER_SAMMLUNG, 'lieder')
  assert.equal(istLiedSpalte({ feld: { art: 'eintrag', sammlung: 'lieder' } }), true)
})

test('DEV-6 · andere Sammlung ist KEINE Lied-Spalte', () => {
  assert.equal(istLiedSpalte({ feld: { art: 'eintrag', sammlung: 'bibelarbeiten' } }), false)
})

test('DEV-6 · Personen-, Team- und Auswahlfelder bleiben ohne Rahmen', () => {
  for (const art of ['person', 'personen', 'team', 'auswahl', 'zahl', 'datum', 'zeitraum']) {
    assert.equal(istLiedSpalte({ feld: { art } }), false, `art ${art} darf keine Lied-Spalte sein`)
  }
})

test('DEV-6 · Gruppen- und Anlass-Spalten sind keine Lied-Spalten', () => {
  assert.equal(istLiedSpalte({ feld: { art: 'gruppe', inhalt: [] } }), false)
  assert.equal(istLiedSpalte({ feld: null, format: '{lied.titel}' }), false, 'ohne Deklaration kein Rahmen')
  assert.equal(istLiedSpalte(null), false)
})

test('DEV-6 · Textfeld mit Lied-Formatvorlage gilt als Lied-Spalte', () => {
  // gottesdienstablauf.json: "lied": "{nr} {lied.anzeige}{lied.titel: {lied.titel}}"
  assert.equal(istLiedSpalte({
    feld: { art: 'text' },
    format: '{nr} {lied.anzeige}{lied.titel: {lied.titel}}',
  }), true)
  assert.equal(istLiedSpalte({ feld: { art: 'text' }, format: '{team.name}' }), false)
  assert.equal(istLiedSpalte({ feld: { art: 'text' } }), false)
})

test('DEV-6 · weitere Liedsammlungen lassen sich zusteuern', () => {
  assert.equal(istLiedSpalte({ feld: { art: 'eintrag', sammlung: 'chorlieder' } }), false)
  assert.equal(istLiedSpalte(
    { feld: { art: 'eintrag', sammlung: 'chorlieder' } },
    { liederSammlungen: ['chorlieder'] }), true)
})

// ── Zeilen mit Rahmen ──────────────────────────────────────────────────────

test('DEV-6 · jede Liedzeile einer Liedzelle wird gerahmt', () => {
  const zeilen = zellZeilen([{ text: 'JN 1297' }, { text: 'WH S. 150' }, { text: 'Kopie' }], true)
  assert.deepEqual(zeilen.map((z) => z.gerahmt), [true, true, true])
  assert.deepEqual(zeilen.map((z) => z.text), ['JN 1297', 'WH S. 150', 'Kopie'])
})

test('DEV-6 · in einer normalen Zelle wird nichts gerahmt', () => {
  assert.deepEqual(zellZeilen([{ text: 'D. Krüger' }], false).map((z) => z.gerahmt), [false])
})

test('DEV-6 · leerer Wert bekommt keinen Rahmen', () => {
  const zeilen = zellZeilen([{ text: '–' }, { text: '' }, { text: 'JN 7' }], true)
  assert.deepEqual(zeilen.map((z) => z.gerahmt), [false, false, true])
})

test('DEV-6 · fehlende Liste bleibt leer (kein Absturz)', () => {
  assert.deepEqual(zellZeilen(null, true), [])
  assert.deepEqual(zellZeilen(undefined, false), [])
})

// ── Umsetzung in PrTabelle.vue ─────────────────────────────────────────────

test('DEV-6 · PrTabelle kennzeichnet Liedzeilen (Desktop und Mobil)', () => {
  assert.match(TABELLE, /class="pr-tabelle-instanz"/, 'Desktop-Zeile der Instanzen vorhanden')
  assert.match(TABELLE, /'pr-tabelle-instanz--rahmen':/, 'Desktop-Zeile bekommt die Rahmenklasse')
  assert.match(TABELLE, /pr-tabelle-karte-zeile pr-tabelle-instanz-text/, 'mobiles Kartenfeld vorhanden')
  assert.match(TABELLE, /'pr-tabelle-instanz-text--rahmen':/, 'mobile Zeile bekommt die Rahmenklasse')
  assert.match(TABELLE, /istLiedSpalte/, 'Spaltenerkennung wird benutzt')
})

test('DEV-6 · der Rahmen nutzt Design-Tokens, keine harten Farben', () => {
  const stil = TABELLE.slice(TABELLE.indexOf('<style'))
  // Die gemeinsame Regel nennt beide Rahmenklassen (Desktop + Mobil).
  const gemeinsam = [...stil.matchAll(/\.pr-tabelle-instanz--rahmen,?\s*\n?\.pr-tabelle-instanz-text--rahmen\s*\{[^}]*\}/g)]
    .map((m) => m[0])
  assert.equal(gemeinsam.length, 1, 'genau eine Rahmen-Regel für beide Klassen')
  for (const regel of gemeinsam) {
    assert.match(regel, /border:\s*1px solid var\(--dk-/, 'Rahmen aus einem Design-Token')
    assert.match(regel, /border-radius:\s*var\(--/, 'Radius aus einem Design-Token')
    assert.match(regel, /background:\s*var\(--dk-/, 'Fläche aus einem Design-Token')
    assert.doesNotMatch(regel, /#[0-9a-fA-F]{3,8}\b/, 'kein harter Farbwert (hex)')
    assert.doesNotMatch(regel, /rgba?\(/, 'kein harter Farbwert (rgb)')
    assert.doesNotMatch(regel, /oklch\(|hsl\(/, 'kein harter Farbwert (oklch/hsl)')
  }
  // Der Abstand zwischen den Instanzen bleibt erhalten.
  assert.match(stil, /\.pr-tabelle-instanz \+ \.pr-tabelle-instanz\s*\{[^}]*margin-top:\s*4px/)
})

console.log('DEV-6 Lieder mit Rahmen: 13 Prüfungen bestanden')
