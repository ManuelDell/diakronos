import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { test } from 'node:test'
import * as helpers from '../src/diakonos/components/planrahmen/editor.mjs'

const source = readFileSync(new URL('../src/diakonos/pages/planrahmen/PlantypEditor.vue', import.meta.url), 'utf8')
function editor() {
  const calls = []
  const context = { ...helpers, setTimeout, clearTimeout,
    ref: value => ({ value }), computed: f => ({ get value() { return f() } }),
    watch() {}, onMounted() {}, onUnmounted() {}, defineEmits: () => () => {}, defineExpose() {},
    getRouteParam: () => 'neu', onBeforeEach: () => () => {}, showToast() {},
    fehlerMeldungen: e => [{ meldung: e.message }], jsonPruefen: helpers.jsonUebernehmen,
    window: { sessionStorage: { getItem: () => null, removeItem() {} }, addEventListener() {}, removeEventListener() {} },
    usePlanrahmen: () => ({ plantypSpeichern: async d => { calls.push(d); return {} }, plantypVersionenListe: async () => [], bedarf: async () => [] }),
  }
  vm.createContext(context)
  vm.runInContext(source.split('<script setup>')[1].split('</script>')[0].replace(/^import .*\n/gm, ''), context)
  const run = code => vm.runInContext(code, context)
  run("definition.value={id:'chorplan',name:'Alter Stand'}; gueltigAb.value='2026-07-01'; kommentar.value='Neue Version'")
  return { calls, run }
}

test('Ungültiges sichtbares JSON sperrt Speichern und sendet niemals die alte Definition', async () => {
  const { calls, run } = editor()
  run("jsonTextRoh.value='{kaputt'; jsonUebernehmen()")
  assert.equal(run('speichernPflichtenOk.value'), false)
  await run('speichern()')
  assert.equal(calls.length, 0)
  assert.equal(run('jsonTextRoh.value'), '{kaputt')
  assert.match(run('speichernFehler.value[0].meldung'), /JSON/)
  assert.match(source, /:disabled="speichert \|\| !!jsonFehler"/)
})

test('Korrigiertes JSON lässt sich als neue Definition speichern', async () => {
  const { calls, run } = editor()
  run("jsonTextRoh.value='{kaputt'; jsonUebernehmen(); jsonTextRoh.value=JSON.stringify({id:'chorplan',name:'Korrigiert'}); jsonUebernehmen()")
  assert.equal(run('speichernPflichtenOk.value'), true)
  await run('speichern()')
  assert.equal(calls.length, 1)
  assert.equal(calls[0].name, 'Korrigiert')
})
