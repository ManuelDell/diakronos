import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'

const source = fs.readFileSync(new URL('../src/diakonos/components/kronos/KronosSidebar.vue', import.meta.url), 'utf8')
const mounted = source.match(/onMounted\(([\s\S]*?)\);\s*<\/script>/)[1]

// OP-ADMIN-10: „Kalender verwalten“ haengt an DERSELBEN Rolle wie der Import.
// Der Test prueft deshalb BEIDE Schalter je Rolle — vorher gab es nur
// `showImport`, und ein zusaetzlicher Schalter waere unbemerkt geblieben.
for (const [roles, visible] of [[['Kalenderadministrator'], true], [['Administrator'], true], [['System Manager'], false], [['Mitglied'], false]]) {
  test(`sidebar retains role visibility ${roles.join(',')}`, async () => {
    const context = {
      window: {},
      showImport: { value: false },
      zeigeVerwalten: { value: false },
      // K-A: die Liste der eigenen abgelehnten Termine — der Aufbau der Leiste
      // darf davon nicht abhaengen. Der Rumpf ruft `ladeAbgelehnteTermine`.
      abgelehnteTermine: { value: [] },
      ladeAbgelehnteTermine: async () => {},
      apiCall: async method => {
        assert.equal(method, 'diakronos.diakonos.api.session.get_current_user_context')
        return { roles }
      },
    }
    vm.createContext(context)
    await vm.runInContext(`(${mounted})()`, context)
    assert.equal(context.showImport.value, visible)
    assert.equal(context.zeigeVerwalten.value, visible,
      'Der Verwaltungs-Eintrag muss dieselbe Rollenschranke tragen wie der Import')
  })
}
