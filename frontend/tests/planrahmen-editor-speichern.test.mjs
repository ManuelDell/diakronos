import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { test } from 'node:test'
import * as helpers from '../src/diakonos/components/planrahmen/editor.mjs'
// UX-C3a: die Seite lädt die Abschnitts-Regeln selbst (Sprungleiste) —
// im vm-Kontext stehen sie wie die übrigen Importe vorn (letzte gewinnt).
import * as abschnitte from '../src/diakonos/components/planrahmen/abschnitte.mjs'

const source = readFileSync(new URL('../src/diakonos/pages/planrahmen/PlantypEditor.vue', import.meta.url), 'utf8')
function editor() {
  const calls = []
  const context = { ...helpers, ...abschnitte, setTimeout, clearTimeout,
    ref: value => ({ value }), computed: f => ({ get value() { return f() } }),
    watch() {}, onMounted() {}, onUnmounted() {}, defineEmits: () => () => {}, defineExpose() {},
    // UX2d3a: Ladeplatzhalter — hier nicht Gegenstand des Tests.
    useLadeSkelett: laedt => ({ skelettSichtbar: laedt }),
    getRouteParam: () => 'neu', onBeforeEach: () => () => {}, showToast() {},
    fehlerMeldungen: e => [{ meldung: e.message }], jsonPruefen: helpers.jsonUebernehmen,
    window: { sessionStorage: { getItem: () => null, removeItem() {} }, addEventListener() {}, removeEventListener() {} },
    usePlanrahmen: () => ({ plantypSpeichern: async d => { calls.push(d); return {} }, plantypVersionenListe: async () => [], bedarf: async () => [] }),
    // PLAN-M1: Hinweis am Handy — hier nicht Gegenstand des Tests.
    useHandyHinweis: () => ({ geschlossen: () => false, schliessen() { return true }, setzen() {} }),
    hinweisZeigen: () => false, istSchmal: () => false,
    // DEV-B6: die Seiten fragen die Handy-Lage ueber diese beiden
    // Exporte ab (Desktop-Lage: nie Handy, Hinweis aus).
    istHandyHinweisLage: () => false,
    handyHinweisLage: () => ({ grob: false, breite: 1366, hoehe: 800 }),
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
