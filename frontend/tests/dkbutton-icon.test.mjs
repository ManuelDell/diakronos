import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'

// DS3 · Regression: DkButton mit Icon darf den Text nicht überlagern.
// Der Knopf ist ein Flex-Container; das Label umschließt Icon UND Text und
// hält sie nebeneinander (Icon im #icon-Slot oder im Standard-Slot).
const quelle = readFileSync(new URL('../src/diakonos/components/ui/DkButton.vue', import.meta.url), 'utf8')

test('DkButton-Label hält Icon und Text nebeneinander', () => {
  // Label ist ein Flex-Container (Icons rutschen sonst über/durch den Text).
  const labelRegel = quelle.match(/\.dk-ui-btn-label\s*\{([^}]*)\}/)
  assert.ok(labelRegel, 'Regel .dk-ui-btn-label vorhanden')
  const regeln = labelRegel[1].replace(/\s+/g, ' ')
  assert.match(regeln, /display:\s*inline-flex/, '.dk-ui-btn-label ist inline-flex')
  assert.match(regeln, /align-items:\s*center/, '.dk-ui-btn-label richtet Icon und Text mittig aus')
  // BEF-DESIGN-1: der Abstand kommt aus der Skala (--sp-2), nicht mehr aus
  // einem festen 7-px-Wert (SSOT, Wächter ux1a).
  assert.match(regeln, /gap:\s*var\(--sp-\d\)/, '.dk-ui-btn-label hat Abstand zwischen Icon und Text (Token)')
  // BEF-DESIGN-1: kein Umbruch mehr — „+ Neuer Beitrag“ stand sonst mit dem
  // Symbol darüber und abgeschnittener Beschriftung da.
  assert.match(regeln, /white-space:\s*nowrap/, '.dk-ui-btn-label bricht NICHT um')
})

test('DkButton-Icons werden nie gestaucht', () => {
  assert.match(quelle, /:deep\(svg\)\s*\{\s*flex:\s*none/, 'kein flex-shrink für Icons')
})

test('DkButton kompiliert mit Icon im Standard-Slot', () => {
  const vorlage = `<DkButton variant="primary"><svg width="14" height="14"></svg> Importieren</DkButton>`
  const sfc = `<template>${vorlage}</template><script setup>import DkButton from './DkButton.vue'</script>`
  const { descriptor, errors } = parse(sfc, { filename: 'DkButtonIcon.test.vue' })
  assert.deepEqual(errors, [], 'SFC-Struktur')
  const script = compileScript(descriptor, { id: 'DkButtonIcon.test.vue' })
  const template = compileTemplate({
    source: descriptor.template.content,
    filename: 'DkButtonIcon.test.vue',
    id: 'DkButtonIcon.test.vue',
    compilerOptions: { bindingMetadata: script.bindings || {} },
  })
  assert.deepEqual(template.errors.map(e => e.message || String(e)), [], 'Vorlage kompiliert')
})
