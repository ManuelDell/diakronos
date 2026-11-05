import assert from 'node:assert/strict'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'

// Echt ausgeführter Router mit Browser-/Vue-Randobjekten, keine Source-RegEx-Assertion.
let source = readFileSync(new URL('../src/diakonos/router.js', import.meta.url), 'utf8')
source = source.replace(/^import .*$/gm, '').replace(/import\([^)]*\)/g, 'Promise.resolve({default: "Seite"})')
  // ON-3b: die Leitungsregel (einrichtungLeitung.mjs) wird durch
  // feste Rückgaben ersetzt — dieser Lauf prueft den Router selbst.
  .replace("import * as einrichtungLeitung from './einrichtungLeitung.mjs'",
      "({ EINRICHTUNG_ROUTE: '#/einrichtung', EINRICHTUNG_ZIEL_NACH_ABSCHLUSS: '#/einstellungen', " +
      "einrichtungGesehen: () => false, einrichtungsWeiterleitung: () => null, " +
      "einrichtungSeiteErlaubt: (b) => !b || b.is_admin === true })")
  .replace(/^export \{.*\}$/gm, '').replace(/^export /gm, '')
source += '\nglobalThis.router = {onBeforeEach, getRouteParams, currentHash, currentPageName};'
let hashchange
const window = {
  location: {hash: '#/dienste/vorlagen/chorplan', replace(hash) {this.hash = hash}},
  __DIakonosBOOT: {is_admin: true},
  addEventListener(event, fn) {if (event === 'hashchange') hashchange = fn},
}
window.history = {replaceState(_state, _title, hash) {window.location.hash = hash}}
const context = {window, console, setzeFenstertitel() {}, ref: value => ({value}), shallowRef: value => ({value}), computed: fn => ({get value() {return fn()}})}
vm.createContext(context)
vm.runInContext(source, context)
const {router} = context
const off = router.onBeforeEach(() => false)
// Eine ANDERE Adresse setzen: eine identische gilt sonst als „dieselbe Route“
// und der hashchange-Handler wird vom Browser gar nicht ausgelöst.
window.location.hash = '#/dienste/vorlagen/musikteams'
hashchange()
assert.equal(window.location.hash, '#/dienste/vorlagen/chorplan')
assert.equal(router.getRouteParams().id, 'chorplan')
assert.equal(router.currentHash.value, window.location.hash)
off()
// Eigene Adresse nach dem Abbruch (der Router hat den Hash bereits zurückgesetzt).
window.location.hash = '#/dienste/vorlagen/neu'
await new Promise(r => setTimeout(r, 0))
hashchange()
await new Promise(r => setTimeout(r, 0))
assert.equal(router.getRouteParams().id, 'neu')
assert.equal(router.currentHash.value, window.location.hash)
// Bestehende Gast-Weiterleitung darf der neue Abbruchschutz nicht überschreiben.
window.__DIakonosBOOT = {mitglied: {status:'Gast'}}
window.location.hash = '#/dienste/dienstplaene'
hashchange()
assert.equal(window.location.hash, '#/')
window.__DIakonosBOOT = {is_admin:true}
window.location.hash = '#/dienste/dienstplaene/plan/plan-id'
hashchange()
assert.equal(router.currentPageName.value, 'PlanrahmenPlan')
assert.equal(router.getRouteParams().id, 'plan-id')
console.log('Routenabbruch bewahrt URL und Parameter; Guards sind abmeldbar; Gast-Redirect bleibt erhalten')
