import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import test from 'node:test'

const root = new URL('../src/diakonos/', import.meta.url)
const lies = (p) => readFileSync(new URL(p, root), 'utf8')

test('Dev-Befunde-Seite ist registriert und die Testsuite ist weg', () => {
  const router = lies('router.js')
  assert.ok(router.includes("./pages/devmodus/Befunde.vue"), 'Dev-Befunde-Seite registriert')
  assert.ok(router.includes("'#/dev-befunde'"))
  assert.ok(!router.includes('testsuite'), 'kein Testsuite-Eintrag mehr im Router')
})

test('alte Testsuite-Dateien sind entfernt', () => {
  for (const datei of ['components/testsuite/Testleiste.vue', 'components/testsuite/logik.mjs',
                       'pages/testsuite/Uebersicht.vue', 'composables/useTestsuite.js']) {
    assert.ok(!existsSync(new URL(datei, root)), `Alte Datei entfernt: ${datei}`)
  }
})

test('neue Dev-Modus-Dateien sind vorhanden', () => {
  for (const datei of ['components/devmodus/Rahmen.vue', 'components/devmodus/BefundDialog.vue',
                       'components/devmodus/logik.mjs', 'components/devmodus/screenshot.mjs',
                       'components/devmodus/sprache.mjs', 'composables/useDevmodus.js',
                       'pages/devmodus/Befunde.vue']) {
    assert.ok(existsSync(new URL(datei, root)), `Neue Datei vorhanden: ${datei}`)
  }
})

test('Sidebar nennt Dev-Befunde (nicht Testsuite)', () => {
  // Seit N0 (S12) steht der Eintrag in der zentralen Menüdefinition; die
  // Seitenleiste liest ihn von dort.
  const nav = lies('components/AppSidebar.vue')
  assert.ok(nav.includes('menue.js'), 'Sidebar nutzt die zentrale Menüdefinition')
  assert.ok(!nav.includes('#/testsuite'))
  const menue = lies('menue.js')
  assert.ok(menue.includes('#/dev-befunde'))
  assert.ok(!menue.includes('#/testsuite'))
})

test('App.vue lädt den Rahmen nur lazy und ohne Testleiste', () => {
  const app = lies('App.vue')
  assert.ok(app.includes("defineAsyncComponent(() => import('./components/devmodus/Rahmen.vue'))"),
    'Rahmen wird dynamisch nachgeladen')
  assert.ok(app.includes('<DevRahmen v-if="devmodusAn" />'))
  assert.ok(!app.includes('Testleiste'), 'Testleiste entfernt')
})

test('Kuerzel ist Strg+Shift+F und der rote Rahmen ist position:fixed', () => {
  const logik = lies('components/devmodus/logik.mjs')
  assert.ok(logik.includes("KUERZEL_TASTE = 'F'"))
  const rahmen = lies('components/devmodus/Rahmen.vue')
  assert.ok(rahmen.includes('position: fixed'))
  assert.ok(rahmen.includes('border: 4px solid #e02424'))
  assert.ok(rahmen.includes('pointer-events: none'))
})

console.log('Dev-Modus-Verdrahtung: bestanden')
