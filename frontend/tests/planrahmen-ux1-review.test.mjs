import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import * as vue from 'vue'
import * as klartext from '../src/diakonos/components/planrahmen/klartext.mjs'

// Echtes script setup: API nur an der Grenze ersetzen, echte Zielauswahl prüfen.
test('Bearbeiten benennt jede Liedinstanz eindeutig und wählt das geklickte Ziel', async () => {
  const definition = { felder: [{ id: 'lieder', name: 'Lied', art: 'eintrag', inhalt: [{ id: 'dirigent', name: 'Dirigent', art: 'person' }] }] }
  const slots = Array.from({ length: 3 }, (_, i) => ({ feld_pfad: `lieder[${i}].dirigent`, art: 'person', feld: definition.felder[0].inhalt[0] }))
  const props = vue.reactive({ modelValue: false, plan: 'p', termin: { id: 't' }, feldPfad: 'lieder', slots, definition, eintraege: [] })
  const calls = []
  globalThis.__ux1 = { vue, klartext, props, api: { feldKandidaten: async (p, t, f) => { calls.push(f); return { kandidaten: [] } } } }
  let code = readFileSync(new URL('../src/diakonos/components/planrahmen/PrEditor.vue', import.meta.url), 'utf8').split('<script setup>')[1].split('</script>')[0]
  code = code.replace(/import[^\n]+from[^\n]+\n/g, '')
  code = `const {ref,computed,watch}=globalThis.__ux1.vue; const onMounted=()=>{}; const onUnmounted=()=>{}; const inject=()=>null; const {feldInfo,meldungsKurz,kandidatenHinweise}=globalThis.__ux1.klartext; const defineProps=()=>globalThis.__ux1.props; const defineEmits=()=>()=>{}; const usePlanrahmen=()=>globalThis.__ux1.api; const datumText=x=>x; const wertText=x=>x; const fehlerMeldungen=e=>[{meldung:e.message}]; const feldGehoertZu=(a,b)=>a===b||a.startsWith(b+'[')||a.startsWith(b+'.'); const anzahlBereich=a=>({min:0,max:2});\n` + code
  code += '\nexport {unterZiele,zielPfad};'
  const m = await import('data:text/javascript;base64,' + Buffer.from(code).toString('base64'))
  props.modelValue = true
  await vue.nextTick()
  assert.deepEqual(m.unterZiele.value.map(u => u.name), ['Lied 1 · Dirigent', 'Lied 2 · Dirigent', 'Lied 3 · Dirigent'])
  for (const slot of slots) {
    props.modelValue = false
    await vue.nextTick()
    props.feldPfad = slot.feld_pfad
    props.modelValue = true
    await vue.nextTick()
    assert.equal(m.zielPfad.value, slot.feld_pfad)
    assert.equal(calls.at(-1), slot.feld_pfad)
  }
  props.modelValue = false
  await vue.nextTick()
})
