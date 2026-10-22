import assert from 'node:assert/strict'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'

// Echt ausgeführter Router mit Browser-/Vue-Randobjekten, keine Source-RegEx-Assertion.
let source = readFileSync(new URL('../src/diakonos/router.js', import.meta.url), 'utf8')
source = source.replace(/^import .*$/gm, '').replace(/import\([^)]*\)/g, 'Promise.resolve({default: "Seite"})')
  .replace(/^export \{.*\}$/gm, '').replace(/^export /gm, '')
source += '\nglobalThis.router = {onBeforeEach, getRouteParams, currentHash, currentPageName};'
let hashchange
const window = {
  location: {hash: '#/planrahmen/einrichten/chorplan', replace(hash) {this.hash = hash}},
  __DIakonosBOOT: {is_admin: true},
  addEventListener(event, fn) {if (event === 'hashchange') hashchange = fn},
}
window.history = {replaceState(_state, _title, hash) {window.location.hash = hash}}
const context = {window, console, setzeFenstertitel() {}, ref: value => ({value}), shallowRef: value => ({value}), computed: fn => ({get value() {return fn()}})}
vm.createContext(context)
vm.runInContext(source, context)
const {router} = context
const off = router.onBeforeEach(() => false)
window.location.hash = '#/planrahmen/einrichten/neu'
hashchange()
assert.equal(window.location.hash, '#/planrahmen/einrichten/chorplan')
assert.equal(router.getRouteParams().id, 'chorplan')
assert.equal(router.currentHash.value, window.location.hash)
off()
window.location.hash = '#/planrahmen/einrichten/neu'
hashchange()
assert.equal(router.getRouteParams().id, 'neu')
assert.equal(router.currentHash.value, window.location.hash)
// Bestehende Gast-Weiterleitung darf der neue Abbruchschutz nicht überschreiben.
window.__DIakonosBOOT = {mitglied: {status:'Gast'}}
window.location.hash = '#/planrahmen'
hashchange()
assert.equal(window.location.hash, '#/')
window.__DIakonosBOOT = {is_admin:true}
window.location.hash = '#/planrahmen/plan/plan-id'
hashchange()
assert.equal(router.currentPageName.value, 'PlanrahmenPlan')
assert.equal(router.getRouteParams().id, 'plan-id')
console.log('Routenabbruch bewahrt URL und Parameter; Guards sind abmeldbar; Gast-Redirect bleibt erhalten')
