/**
 * UI-R2d/P9 · Auf dem Handy liegen Kästchen und Wort wirklich nebeneinander.
 *
 * BEFUND beim Abnehmen (Playwright, 390 px, Konten aus ui-r2d-daten.py): In der
 * Handy-Zeile standen Kästchen und Wort **36 px** auseinander, obwohl das
 * äußere `.kr-stufe-feld` nur `gap: var(--sp-2)` (8 px) zusagt.
 *
 * Ursache: `@media (pointer: coarse)` in `diakonos/index.css` gibt JEDEM
 * `label:has(> input[type="checkbox"])` `min-width: var(--control-h)` (44 px)
 * und `gap: var(--sp-2)`. Das Kästchen sitzt im INNEREN `<label>` des
 * DkCheckbox — also greift die Regel dort: seine 44-px-Mindestbreite wird als
 * gap zwischen Kästchen (16 px) und folgendem Inhalt verteilt (44 − 16 + 8).
 * jsdom rechnet kein Layout; deshalb hält dieser Test die QUELLE fest:
 *
 *   1. `KalenderRechte.vue` hebt die geerbte Mindestbreite/den gap der inneren
 *      DkCheckbox-Reihe innerhalb eines Stufenfeldes auf.
 *   2. Die Aufhebung steht im `<style scoped>` DIESER Komponente (kein
 *      Umbau der globalen Trefferflächen-Regel — die 44-px-Fläche bleibt).
 *   3. Das äußere Label umschließt Kästchen UND Wort (Trefferfläche unverändert).
 *
 * Lauf: TZ=Europe/Berlin node --test tests/uir2d-stufen-abstand.test.mjs  (cwd = frontend/)
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const TESTS_DIR = dirname(fileURLToPath(import.meta.url))
const SRC_DIR = resolve(TESTS_DIR, '..', 'src')
const RECHTE = readFileSync(resolve(SRC_DIR, 'diakonos', 'components', 'gruppen', 'KalenderRechte.vue'), 'utf8')
const INDEX_CSS = readFileSync(resolve(SRC_DIR, 'diakonos', 'index.css'), 'utf8')

/** Nur der `<style>`-Block (der `<template>`-Teil enthält keine Regeln). */
function stilVon(quelle) {
  const treffer = quelle.match(/<style[^>]*>([\s\S]*?)<\/style>/)
  assert.ok(treffer, 'kein <style>-Block in KalenderRechte.vue')
  return treffer[1]
}

test('UI-R2d/P9: das Stufenfeld hebt Mindestbreite und gap der inneren Kästchen-Reihe auf', () => {
  const stil = stilVon(RECHTE)
  // Die Regel muss die INNERE Reihe treffen (`.dk-ui-checkbox` im Stufenfeld).
  const regel = stil.match(/\.kr-stufe-feld\s+\.dk-ui-checkbox\s*\{([^}]*)\}/)
  assert.ok(regel, 'die Regel `.kr-stufe-feld .dk-ui-checkbox { … }` fehlt — '
    + 'dann verteilt die 44-px-Mindestbreite aus index.css wieder 36 px zwischen Kästchen und Wort')
  const rumpf = regel[1]
  assert.match(rumpf, /min-width:\s*0/, 'die geerbte min-width (44 px) wird nicht zurückgesetzt')
  assert.match(rumpf, /gap:\s*0/, 'der geerbte gap verteilt die Mindestbreite weiter zwischen Kästchen und Wort')
})

test('UI-R2d/P9: die globale Trefferflächen-Regel bleibt unangetastet', () => {
  // Der Fix gehört in die Komponente, NICHT in die globale Handy-Regel: sonst
  // verlören alle Kästchen der App ihre 44-px-Fläche.
  assert.match(INDEX_CSS, /label:has\(> input\[type="checkbox"\]\)/,
    'die Trefferflächen-Regel fehlt in index.css — dann ist der Befund anders zu bewerten')
  assert.match(INDEX_CSS, /min-height:\s*var\(--control-h\)/,
    'die Mindesthöhe der Trefferfläche ist verschwunden')
})

test('UI-R2d/P9: das äußere Label umschließt Kästchen UND Wort', () => {
  // Trefferfläche bleibt die volle Zeile: ein Klick auf das Wort schaltet um.
  const vorlage = RECHTE.match(/<label v-if="feld" class="kr-stufe-feld">([\s\S]*?)<\/label>/)
  assert.ok(vorlage, 'das Stufen-Label fehlt')
  assert.match(vorlage[1], /<DkCheckbox/, 'im Stufen-Label steht kein Kästchen')
  assert.match(vorlage[1], /\.kr-stufe-wort|kr-stufe-wort/, 'im Stufen-Label steht kein Wort')
})
