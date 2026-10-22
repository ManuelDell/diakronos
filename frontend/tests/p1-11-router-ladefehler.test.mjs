/**
 * P1-11 — Router: ein fehlgeschlagenes Nachladen endet NICHT im ewigen Spinner.
 *
 * Reproduktion des Dev-Befunds vom 16.10.: `#/planrahmen/meine-dienste` zeigte
 * dauerhaft „Wird geladen…". Ursache war `resolveRoute`: schlug der dynamische
 * Import fehl, setzte der catch-Zweig nur `currentComponent = null` — die App
 * blieb im Ladezustand. Der Router muss den Fehler melden statt zu schweigen.
 *
 * Läuft den ECHTEN Router in einer vm aus (Muster: tests/n0-navigation.test.mjs).
 */
import assert from 'node:assert/strict'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'

const root = new URL('../src/diakonos/', import.meta.url)
const lies = p => readFileSync(new URL(p, root), 'utf8')

function routerAusfuehren({ hash = '#/', ladeFehler = false } = {}) {
  let source = lies('router.js')
  source = source.replace(/^import .*$/gm, '')
    .replace(/import\([^)]*\)/g,
      ladeFehler ? 'Promise.reject(new Error("Chunk 404"))' : 'Promise.resolve({default: "Seite"})')
    .replace(/^export \{.*\}$/gm, '').replace(/^export /gm, '')
  source += '\nglobalThis.router = {currentComponent, pageLadefehler, routeNeuLaden, currentPageName};'
  let hashchange
  const window = {
    location: { hash, replace(h) { this.hash = h } },
    __DIakonosBOOT: { is_admin: true },
    addEventListener(event, fn) { if (event === 'hashchange') hashchange = fn },
  }
  window.history = { replaceState(_s, _t, h) { window.location.hash = h } }
  const context = { window, console, setzeFenstertitel() {},
    ref: value => ({ value }),
    shallowRef: value => ({ value }),
    computed: fn => ({ get value() { return fn() } }) }
  vm.createContext(context)
  vm.runInContext(source, context)
  return { window, router: context.router }
}

// Fehlerfreies Laden: nach dem nächsten Tick steht die Seite, kein Fehler.
{
  const h = routerAusfuehren({ hash: '#/planrahmen/meine-dienste' })
  await new Promise(r => setTimeout(r, 0))
  assert.equal(h.router.currentComponent.value, 'Seite')
  assert.equal(h.router.pageLadefehler.value, null)
}

// Fehlgeschlagenes Laden: KEIN ewiger Spinner — die Seite bleibt null, der
// Router meldet eine verstaendliche Meldung mit Wiederholen-Pfad.
{
  const h = routerAusfuehren({ hash: '#/planrahmen/meine-dienste', ladeFehler: true })
  await new Promise(r => setTimeout(r, 0))
  assert.equal(h.router.currentComponent.value, null)
  const fehler = h.router.pageLadefehler.value
  assert.ok(fehler, 'Der Router muss den Ladefehler melden')
  assert.equal(fehler.pageName, 'PlanrahmenDienste')
  assert.match(fehler.meldung, /nicht geladen/)
  assert.ok(fehler.hinweis)
}

// „Nochmal versuchen" setzt den Fehler zurück.
{
  const h = routerAusfuehren({ hash: '#/planrahmen/meine-dienste', ladeFehler: true })
  await new Promise(r => setTimeout(r, 0))
  assert.ok(h.router.pageLadefehler.value)
  h.router.routeNeuLaden()
  assert.equal(h.router.pageLadefehler.value, null)
}
