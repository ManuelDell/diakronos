import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'

const source = fs.readFileSync(new URL('../src/diakonos/components/kronos/KronosSidebar.vue', import.meta.url), 'utf8')
const mounted = source.match(/onMounted\(([\s\S]*?)\);\s*<\/script>/)[1]
// Nacharbeit UX3i-N2 Punkt 7: Die Rollenprüfung kommt jetzt aus
// `kalenderRechte.mjs` (EINE Stelle) und wird im VM-Kontext als Import
// bereitgestellt — dieselbe Funktion, die die Komponente importiert.
const { istKalenderAdmin, kalenderVerwaltungSichtbar } = await import('../src/diakonos/components/kronos/kalenderRechte.mjs')

// OP-ADMIN-10: „Kalender verwalten“ haengt an DERSELBEN Rolle wie der Import.
// Der Test prueft deshalb BEIDE Schalter je Rolle — vorher gab es nur
// `showImport`, und ein zusaetzlicher Schalter waere unbemerkt geblieben.
// UI-R3: Der Import bleibt bei der Admin-Rolle; „Verwalten“ gilt zusätzlich
// für alle, denen der Server Kalender zum Anlegen gibt. Je Rolle wird deshalb
// die Serverantwort von `get_kalender_verwaltung` gestellt.
for (const [roles, visible, serverAntwort] of [
  [['Kalenderadministrator'], true, null],
  [['Administrator'], true, null],
  [['System Manager'], false, null],
  [['Mitglied'], false, { kalender: [], anlegen_gruppen: [] }],
  // UI-R3: eine Gruppenleitung darf anlegen, obwohl sie keine Admin-Rolle hat.
  [['Mitglied'], true, { kalender: [], anlegen_gruppen: ['G-Chor'], darf_gemeinde_kalender: false }],
]) {
  // Import bleibt bei der Admin-Rolle (unabhängig von der Serverantwort).
  const importSichtbar = ['Kalenderadministrator', 'Administrator']
    .some((r) => roles.includes(r))
  test(`sidebar retains role visibility ${roles.join(',')}${!importSichtbar && visible ? ' (Server erlaubt Anlegen)' : ''}`, async () => {
    const context = {
      window: {},
      showImport: { value: false },
      zeigeVerwalten: { value: false },
      // K-A: die Liste der eigenen abgelehnten Termine — der Aufbau der Leiste
      // darf davon nicht abhaengen. Der Rumpf ruft `ladeAbgelehnteTermine`.
      abgelehnteTermine: { value: [] },
      ladeAbgelehnteTermine: async () => {},
      // Punkt 7: die gemeinsame Rollenprüfung (Import der Komponente).
      istKalenderAdmin,
      kalenderVerwaltungSichtbar,
      apiCall: async method => {
        if (String(method).includes('kalender_verwaltung.get_kalender_verwaltung')) {
          if (!serverAntwort) {
            // Der Server verweigert ohne Recht: 403 wie im Betrieb.
            throw Object.assign(new Error('HTTP 403'), { status: 403 })
          }
          return serverAntwort
        }
        assert.equal(method, 'diakronos.diakonos.api.session.get_current_user_context')
        return { roles, user: '' }
      },
    }
    vm.createContext(context)
    await vm.runInContext(`(${mounted})()`, context)
    assert.equal(context.showImport.value, importSichtbar,
      'Import hängt weiter an der Admin-Rolle')
    assert.equal(context.zeigeVerwalten.value, visible,
      'Verwalten hängt am Serverrecht (Admin UND Anlegeorte)')
  })
}
