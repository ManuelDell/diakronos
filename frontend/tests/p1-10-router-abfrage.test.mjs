import assert from 'node:assert/strict'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'

// OP-HANDY-13: Die Liedersuche schreibt den Begriff als `?q=…` in die Adresse.
// Regression (Nachtpruefung P1-10): der Abfrageteil gehoert NICHT zur Route.
// Vorher landete `#/lieder?q=Komm` in keiner Route (`routeMap`-Treffer leer)
// und die Seite fiel still auf 'Home' zurueck — die Suche ging verloren.
// Dieser Test fuehrt den ECHTEN Router in einer VM aus.
let source = readFileSync(new URL('../src/diakonos/router.js', import.meta.url), 'utf8')
source = source.replace(/^import .*$/gm, '').replace(/import\([^)]*\)/g, 'Promise.resolve({default: "Seite"})')
  .replace(/^export \{.*\}$/gm, '').replace(/^export /gm, '')
source += '\nglobalThis.router = {getRouteParams, currentHash, currentPageName, resolveRoute};'

let hashchange
const window = {
  location: { hash: '#/', replace(hash) { this.hash = hash } },
  __DIakonosBOOT: { is_admin: true },
  addEventListener(event, fn) { if (event === 'hashchange') hashchange = fn },
}
window.history = { replaceState(_s, _t, hash) { window.location.hash = hash } }
const context = {
  window, console,
  // P3-4b/B1: Fenstertitel liegt in fenstertitel.js (importfrei) — im vm-Lauf ohne Wirkung.
  setzeFenstertitel() {},
  ref: (value) => ({ value }),
  shallowRef: (value) => ({ value }),
  computed: (fn) => ({ get value() { return fn() } }),
}
vm.createContext(context)
vm.runInContext(source, context)

// Reine Route ohne Abfrageteil bleibt die Liederseite.
window.location.hash = '#/lieder'
hashchange()
assert.equal(context.router.currentPageName.value, 'Lieder', 'Lieder ohne Abfrage')

// Mit `?q=…` muss die Route AUCH die Liederseite sein (kein Home-Fallback).
window.location.hash = '#/lieder?q=Komm'
hashchange()
assert.equal(context.router.currentPageName.value, 'Lieder',
  "Suche aus der Adresse darf nicht auf 'Home' zurueckfallen")
// Der volle Hash bleibt lesbar — Lieder.vue liest `window.location.hash`.
assert.equal(context.router.currentHash.value, '#/lieder?q=Komm',
  'voller Hash (mit Abfrage) bleibt in currentHash')

// Dynamische Route mit Abfrageteil: Parameter muss sauber bleiben.
window.location.hash = '#/lieder/17bdc17e-1?tab=noten'
hashchange()
assert.equal(context.router.currentPageName.value, 'LiedDetail', 'Lied-Detail mit Abfrage')
assert.equal(context.router.getRouteParams().id, '17bdc17e-1', 'id ohne Abfrageteil')

console.log('Abfrageteil (?q=…) trennt Route und Adresse sauber: bestanden')
