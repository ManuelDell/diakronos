import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { test } from 'node:test'
import { setImmediate as tick } from 'node:timers/promises'
import { ref, reactive, shallowRef, computed, watch, nextTick, effectScope } from 'vue'
import * as helpers from '../src/diakonos/components/planrahmen/editor.mjs'

function harness(pageName = 'Plan', hash = '#/planrahmen/plan/plan-a', erlaubt = true) {
  const scope = effectScope()
  let hashchange
  const window = {
    location: { hash },
    sessionStorage: { getItem: () => null, removeItem() {} },
    removeEventListener() {},
    __DIakonosBOOT: { is_admin: true },
    addEventListener(event, fn) { if (event === 'hashchange') hashchange = fn },
  }
  const calls = []
  const pending = []
  const imports = []
  const context = { ...helpers, jsonPruefen: helpers.jsonUebernehmen,
    window, console, ref, reactive, shallowRef, computed, watch,
    // P3-4b/B1: Fenstertitel liegt in fenstertitel.js (importfrei).
    setzeFenstertitel() {},
    lazyImport: () => new Promise((resolve, reject) => imports.push({ resolve, reject })),
    onUnmounted() {}, onMounted() {}, provide() {}, defineEmits: () => () => {}, defineExpose() {},
    defineProps: () => ({ plantyp: '', plan: '' }), setTimeout: () => 0, clearTimeout() {},
    cacheLeeren() {}, showToast() {},
    fehlerMeldungen: e => [e.message],
    usePlanrahmen: () => ({
      schemaHolen: async () => ({}), kochbuchListe: async () => [], bedarf: async () => [],
      einrichtenRechte: async () => ({ darf_anlegen: erlaubt }),
      plantypenListe: async () => ['chorplan', 'musikteams'].map(schluessel => ({ schluessel, darf_plantyp_bearbeiten: erlaubt })),
      plantypPruefen: async () => ({ gueltig: true }),
      plantypVersionenListe: id => { calls.push(['versionen', id]); return new Promise(resolve => pending.push(resolve)) },
      stammdatenHolen: (typ, id) => { calls.push(['stammdaten', typ, id]); return new Promise(resolve => pending.push(resolve)) },
      planHolen: id => { calls.push(['plan', id]); return new Promise(resolve => pending.push(resolve)) },
      terminStruktur: async (id, termin) => { calls.push(['struktur', id, termin]); return {} },
    }),
  }
  vm.createContext(context)
  let router = readFileSync(new URL('../src/diakonos/router.js', import.meta.url), 'utf8')
  router = router.replace(/^import .*$/gm, '').replace(/import\([^)]*\)/g, 'lazyImport()')
    .replace(/^export \{.*\}$/gm, '').replace(/^export /gm, '')
  vm.runInContext(router, context)
  const page = readFileSync(new URL(`../src/diakonos/pages/planrahmen/${pageName}.vue`, import.meta.url), 'utf8')
  scope.run(() => vm.runInContext(page.split('<script setup>')[1].split('</script>')[0].replace(/^import .*\n/gm, ''), context))
  const run = code => vm.runInContext(code, context)
  return { calls, pending, imports, run, stop: () => scope.stop(),
    async go(hash) { window.location.hash = hash; hashchange(); await nextTick() },
  }
}

test('Plan → Editor startet keine Plan-Abfrage mit Plantyp-Kennung vor dem Unmount', async () => {
  const h = harness()
  try {
    await h.go('#/planrahmen/einrichten/chorplan')
    assert.deepEqual(h.calls, [['plan', 'plan-a']])
    h.pending[0]({ plan: { id: 'plan-a' }, termine: [{ id: 't1', plantyp_version: 'v1' }] })
    await nextTick(); await nextTick()
    assert.equal(h.run('planDaten.value'), null)
    assert.equal(h.calls.length, 1)
    await h.run('neuLaden()')
    assert.equal(h.calls.length, 1)
  } finally { h.stop() }
})

test('Echter Plan-ID-Wechsel und Reload bleiben möglich; alte Antworten werden verworfen', async () => {
  const h = harness()
  try {
    await h.go('#/planrahmen/plan/plan-b')
    assert.deepEqual(h.calls, [['plan', 'plan-a'], ['plan', 'plan-b']])
    h.pending[0]({ plan: { id: 'plan-a' }, termine: [] })
    h.pending[1]({ plan: { id: 'plan-b' }, termine: [] })
    await nextTick(); await nextTick()
    assert.equal(h.run('plan.value.id'), 'plan-b')
    const reload = h.run('neuLaden()')
    assert.deepEqual(h.calls[2], ['plan', 'plan-b'])
    h.pending[2]({ plan: { id: 'plan-b' }, termine: [] })
    await reload
    assert.equal(h.run('laden.value'), false)
  } finally { h.stop() }
})

test('Verweigerter Vorlagenzugriff erzeugt keine ungespeicherten Änderungen', async () => {
  const h = harness('PlantypEditor', '#/planrahmen/einrichten/neu', false)
  try {
    await tick()
    assert.equal(h.run('dirty.value'), false)
    assert.equal(h.run('darfVorlageBearbeiten.value'), false)
    assert.equal(h.run('seitenFehler.value.length'), 1)
    await h.go('#/') // window.confirm fehlt absichtlich: es darf nicht aufgerufen werden.
    assert.equal(h.run('currentPageName.value'), 'Home')
  } finally { h.stop() }
})

test('Editor → Plan lädt weder Versionen der Plan-ID noch eine neue Definition', async () => {
  const h = harness('PlantypEditor', '#/planrahmen/einrichten/chorplan')
  try {
    await tick()
    assert.deepEqual(h.calls, [['versionen', 'chorplan']])
    await h.go('#/planrahmen/plan/plan-a')
    h.pending[0]([{ definition: { id: 'chorplan', name: 'Veraltet' } }])
    await nextTick(); await nextTick()
    assert.deepEqual(h.calls, [['versionen', 'chorplan']])
    assert.notEqual(h.run('definition.value.name'), 'Veraltet')
  } finally { h.stop() }
})

test('Plan → Editor → Plan vor Lazy-Unmount veröffentlicht niemals alte Editor-Parameter', async () => {
  const h = harness()
  try {
    await h.go('#/planrahmen/einrichten/chorplan')
    await h.go('#/planrahmen/plan/plan-b')
    assert.deepEqual(h.calls, [['plan', 'plan-a'], ['plan', 'plan-b']])
    h.pending[0]({ plan: { id: 'plan-a' }, termine: [] })
    h.pending[1]({ plan: { id: 'plan-b' }, termine: [] })
    await nextTick(); await nextTick()
    assert.equal(h.run('plan.value.id'), 'plan-b')
  } finally { h.stop() }
})

test('Editor → Plan → Editor vor Lazy-Unmount veröffentlicht niemals alte Plan-Parameter', async () => {
  const h = harness('PlantypEditor', '#/planrahmen/einrichten/chorplan')
  try {
    await tick()
    await h.go('#/planrahmen/plan/plan-a')
    await h.go('#/planrahmen/einrichten/musikteams')
    await tick()
    assert.deepEqual(h.calls, [['versionen', 'chorplan'], ['versionen', 'musikteams']])
    h.pending[0]([{ definition: { id: 'chorplan', name: 'Veraltet' } }])
    h.pending[1]([{ definition: { id: 'musikteams', name: 'Aktuell' } }])
    await tick()
    assert.equal(h.run('definition.value.name'), 'Aktuell')
  } finally { h.stop() }
})

test('Verspäteter Lazy-Import und Importfehler überschreiben nicht die zurückgekehrte Seite', async () => {
  const h = harness()
  try {
    await h.go('#/planrahmen/einrichten/chorplan')
    await h.go('#/planrahmen/plan/plan-b')
    h.imports[2].resolve({ default: 'AktuellerPlan' })
    await tick()
    h.imports[1].resolve({ default: 'VeralteterEditor' })
    h.imports[0].reject(new Error('Veralteter Importfehler'))
    await tick()
    assert.equal(h.run('currentComponent.value'), 'AktuellerPlan')
  } finally { h.stop() }
})

test('Stammdaten → Editor sendet keine kontextlose Anfrage', async () => {
  const h = harness('Stammdaten', '#/planrahmen/stammdaten/chorplan')
  try {
    assert.deepEqual(h.calls, [['stammdaten', 'chorplan', null]])
    await h.go('#/planrahmen/einrichten/chorplan')
    h.pending[0]({ definition: { id: 'chorplan' } })
    await nextTick(); await nextTick()
    assert.deepEqual(h.calls, [['stammdaten', 'chorplan', null]])
    assert.equal(h.run('daten.value'), null)
  } finally { h.stop() }
})
