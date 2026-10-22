import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { test } from 'node:test'
import * as helpers from '../src/diakonos/components/planrahmen/editor.mjs'

const source = readFileSync(new URL('../src/diakonos/components/planrahmen/PrTermineEditor.vue', import.meta.url), 'utf8')
function editor(termine = {}) {
  const context = { ...helpers, ref: value => ({ value }), computed: f => ({ get value() { return f() } }), watch() {}, defineProps: () => ({ termine, kontext: {} }),
                  // REST-1: PrTermineEditor meldet sich beim Feiertagskatalog an
                  // (Lebenszyklus-Haken). Im Testlauf ohne Vue sind sie leer.
                  onMounted() {}, onBeforeUnmount() {}, beiFeiertagskatalog: () => () => {} }
  vm.createContext(context)
  vm.runInContext(source.split('<script setup>')[1].split('</script>')[0].replace(/^import .*\n/gm, ''), context)
  return { termine, run: code => vm.runInContext(code, context) }
}
test('Eigene Feiertage hinzufügen ist explizit, idempotent und entfernt keinen bestehenden Schlüssel', () => {
  const { termine, run } = editor()
  run("eigenerFeiertag.value='osterdienstag'; eigenerFeiertagHinzufuegen()")
  assert.equal(JSON.stringify(termine.feiertage), '["osterdienstag"]')
  run("eigenerFeiertag.value='osterdienstag'; eigenerFeiertagHinzufuegen()")
  assert.equal(JSON.stringify(termine.feiertage), '["osterdienstag"]')
  run("eigenerFeiertag.value='  '; eigenerFeiertagHinzufuegen()")
  assert.equal(JSON.stringify(termine.feiertage), '["osterdienstag"]')
  assert.doesNotMatch(source, /feiertagToggle\(eigenerFeiertag, \$event.target.checked\)/)
})
test('Eigene Feiertage können gezielt entfernt werden, andere bleiben bestehen', () => {
  const { termine, run } = editor({ feiertage: ['ostermontag', 'osterdienstag'] })
  run("feiertagToggle('osterdienstag', false)")
  assert.equal(JSON.stringify(termine.feiertage), '["ostermontag"]')
  assert.match(source, /@click="feiertagToggle\(k, false\)"/)
})
