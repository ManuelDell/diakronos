import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
const root = new URL('../', import.meta.url)
function router(boot) {
    let code = readFileSync(new URL('router.js', root), 'utf8')
        .replace(/^import .*$/gm, '').replace(/import\([^)]*\)/g, 'Promise.resolve({default:"Seite"})')
        .replace(/^export \{.*\}$/gm, '').replace(/^export /gm, '')
    code += '\nglobalThis.gehe = resolveRoute;'
    const window = { __DIakonosBOOT: boot, location: { hash: '#/', replace(hash) { this.hash = hash } }, addEventListener() {} }
    window.history = { replaceState(_s, _t, hash) { window.location.hash = hash } }
    const c = vm.createContext({ window, console, setzeFenstertitel() {}, ref: value => ({value}), shallowRef: value => ({value}), computed: fn => ({get value(){return fn()}}) })
    vm.runInContext(code, c)
    return { window, gehe(hash) { window.location.hash = hash; c.gehe(); return window.location.hash } }
}
test('UXM-001: Verwaltungsseiten verweigern Direktaufruf für Mitglieder', () => {
    const r = router({mitglied:{status:'Mitglied'}})
    for (const hash of ['#/mitglieder/uebersicht', '#/mitglieder/anfragen', '#/einstellungen', '#/einstellungen/anmeldung', '#/dev-befunde']) assert.equal(r.gehe(hash), '#/')
})
test('Dev-Befunde bleiben für berechtigte Tester bei aktivem Dev-Modus erreichbar', () => {
    const r = router({mitglied:{status:'Mitglied'}, devmode:true, ist_tester:true})
    assert.equal(r.gehe('#/dev-befunde'), '#/dev-befunde')
})
test('OP-UI-17: Vorlagen-Editor prüft Serverrecht vor dem Laden der Vorlage', () => {
    const code = readFileSync(new URL('pages/planrahmen/PlantypEditor.vue', root), 'utf8')
    assert.match(code, /t\.darf_plantyp_bearbeiten === true/)
    assert.match(code, /v-if="darfVorlageBearbeiten && !laden"/)
    assert.ok(code.indexOf('if (!erlaubt) throw') < code.indexOf("window.sessionStorage.getItem('pr-editor-vorlage')"))
})
