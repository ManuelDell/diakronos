import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

let text = readFileSync(new URL('../src/diakonos/composables/useMitglieder.js', import.meta.url), 'utf8')
text = text.replace("import { ref, computed, watch } from 'vue'", `const ref = value => ({value}); const computed = fn => ({get value(){return fn()}}); const watch = () => {}`)
text = text.replace("import { apiCall } from './useApi.js'", 'const apiCall = (...args) => globalThis.__mitgliederApi(...args)')
// UX2g: den Fehlerkatalog als echte Umsetzung bereitstellen (der Test lädt das
// Modul als data:-URL — ein relativer Import ginge dort nicht auf).
text = text.replace("import { aktionsfehler } from '../../shared/fehlertexte.js'",
  'const aktionsfehler = (...a) => globalThis.__aktionsfehler(...a)')
const mod = await import('data:text/javascript;base64,' + Buffer.from(text).toString('base64'))
// UX2g: die echte Umsetzung des Katalogs — der Test betrachtet den Fehlertext
// nicht, braucht aber dieselbe Funktion wie im Betrieb.
globalThis.__aktionsfehler = (await import('../src/shared/fehlertexte.js')).aktionsfehler
test('Persönliche Daten werden beim Verlassen maskiert, auch bei später Serverantwort', async () => {
  const liste = mod.useMitglieder()
  liste.persoenlicheDaten.value = true
  let antwort
  globalThis.__mitgliederApi = () => new Promise(resolve => { antwort = resolve })
  const laden = liste.reload()
  mod.persoenlicheDatenZuruecksetzen()
  antwort({data:[{name:'m1',email:'privat@example.org',telefonnummer:'privat',geburtstag:'2000-01-01',wohnort:'privat'}],total:1})
  await laden
  assert.equal(liste.persoenlicheDaten.value, false)
  assert.equal(liste.mitglieder.value[0].email, null)
  assert.equal(liste.mitglieder.value[0].wohnort, null)
})
test('Gruppen-Auswahl-Ref ist mit dem Template verbunden', () => {
  const quelle = readFileSync(new URL('../src/diakonos/pages/GruppeDetail.vue', import.meta.url), 'utf8')
  assert.match(quelle.slice(quelle.lastIndexOf('return {')), /\bmitgliedAuswahl\b/)
})
