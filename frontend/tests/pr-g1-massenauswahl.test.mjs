/**
 * PR-G1 (Review): Massenaktion nach Geschlechtsfilter.
 *
 * Manuel wählt „alle sichtbaren" und filtert DANACH auf „Männlich" — dann
 * darf die Massenaktion nur Männer ändern (und die Anzeige „N ausgewählt"
 * muss den sichtbaren Teil zählen). Geprüft wird das am ECHTEN script-setup
 * der Seite (kein Nachbau der Filterlogik): die gemeinsame Rechnung
 * `stammdaten-geschlecht.mjs` wird vorangestellt, Vue kommt als Stub herein
 * (wie tests/planrahmen-stammdaten.test.mjs).
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

// Vue-Stub ohne node_modules: watch sammelt die Rückrufe, damit der Test den
// Filterwechsel wie das echte v-model auslösen kann.
globalThis.__g1Watches = []
globalThis.__g1Vue = {
  ref: (v) => ({ value: v }),
  reactive: (o) => o,
  computed: (f) => ({ get value() { return f() } }),
  watch: (quelle, rueckruf) => { globalThis.__g1Watches.push({ quelle, rueckruf }) },
  onUnmounted: () => {},
  onMounted: () => {},
}
globalThis.__g1Api = null
globalThis.__g1Routen = { plantyp: 'chorplan' }

const definition = {
  plantyp: 'chorplan',
  name: 'Chorplan',
  merkmale: {
    person: [
      { id: 'predigt', name: 'Predigt', art: 'tag' },
      { id: 'moderation', name: 'Moderation', art: 'tag' },
    ],
    bibelarbeiten: [],
  },
  sammlungen: [],
}
const personen = [
  { id: 'm1', name: 'Anton M', kuerzel: 'AM', geschlecht: 'm', gruppen: [], merkmale: {} },
  { id: 'w1', name: 'Berta W', kuerzel: 'BW', geschlecht: 'w', gruppen: [], merkmale: {} },
  { id: 'm2', name: 'Carl M', kuerzel: 'CM', geschlecht: 'Männlich', gruppen: [], merkmale: {} },
  { id: 'o1', name: 'Dora X', kuerzel: 'DX', gruppen: [], merkmale: {} },
]

const aufrufe = []
globalThis.__g1Api = {
  schemaHolen: async () => ({}),
  kochbuchListe: async () => [],
  stammdatenHolen: async () => ({ definition, personen, sammlungen: {}, darf_bearbeiten: true,
    darf_globale_stammdaten_bearbeiten: true }),
  merkmalePflegen: async (typ, werte, plan) => { aufrufe.push({ name: 'merkmalePflegen', werte, plan }); return {} },
  planHolen: async () => ({ plan: {} }),
  terminStruktur: async () => ({}),
}

let code = readFileSync(new URL('../src/diakonos/pages/planrahmen/Stammdaten.vue', import.meta.url), 'utf8')
code = code.split('<script setup>')[1].split('</script>')[0]
// Mehrzeiliger `import { … } from '…'` der Seite: bei Bedarf bis zum
// abschließenden `from '…'` weiterlesen, nicht nur zeilenweise.
code = code.replace(/^import[\s\S]*?from[^\n]+\n/gm, '')
code = `const { ref, reactive, computed, watch, onMounted, onUnmounted } = globalThis.__g1Vue
const useLadeSkelett = (laedt) => ({ skelettSichtbar: laedt })
const usePlanrahmen = () => globalThis.__g1Api
const useHandyHinweis = () => ({ geschlossen: () => false, schliessen: () => true })
const hinweisZeigen = () => false
const istSchmal = () => false
const getRouteParam = (key) => globalThis.__g1Routen[key] || ''
const showToast = () => {}
const fehlerMeldungen = (e) => [e.message]
const datumText = (x) => x
const defineProps = () => ({ plantyp: '', plan: '' })
const defineEmits = () => () => {}
const defineExpose = () => {}
` + readFileSync(new URL('../src/diakonos/pages/planrahmen/stammdaten-geschlecht.mjs', import.meta.url), 'utf8') + code
code += `\nexport { ladenStarten, personenListe, gefiltertePersonen, auswahl, auswahlSichtbar,
  auswahlUmschalten, alleSichtbarenUmschalten, alleSichtbarGewaehlt, suche, gruppeWahl, geschlechtWahl,
  massenMerkmal, massenWert, massenBereit, massenAnwenden, ohneGeschlechtAnzahl };`

const m = await import('data:text/javascript;base64,' + Buffer.from(code).toString('base64'))

await m.ladenStarten()
assert.equal(m.personenListe.value.length, 4, 'Vier Personen aus der Stammdaten-Antwort')

// Alle sichtbaren auswählen, dann auf „Männlich" filtern.
m.alleSichtbarenUmschalten(true)
assert.equal(m.auswahl.value.size, 4, 'Ohne Filter sind alle vier ausgewählt')
m.geschlechtWahl.value = 'm'
// Das echte v-model löst `watch` aus; der Stub ruft die gesammelten Rückrufe
// für die geänderte Quelle auf (Suche/Gruppe/Geschlecht hängen am selben Watch).
for (const { quelle, rueckruf } of globalThis.__g1Watches) {
  const quellen = Array.isArray(quelle) ? quelle : [quelle]
  if (quellen.includes(m.geschlechtWahl)) rueckruf()
}
assert.deepEqual(m.gefiltertePersonen.value.map((p) => p.id), ['m1', 'm2'],
  'Filter „Männlich" zeigt beide Schreibweisen der Angabe')
assert.deepEqual([...m.auswahlSichtbar.value].sort(), ['m1', 'm2'], 'Auswahl auf Sichtbares beschnitten')
assert.equal(m.auswahl.value.size, 2, 'Anzeige „N ausgewählt" zählt nur Sichtbares')
assert.equal(m.alleSichtbarGewaehlt.value, true, 'Alle sichtbaren sind weiter gewählt')

// Massenaktion anwenden: nur die Männer dürfen geschrieben werden.
m.massenMerkmal.value = 'predigt'
m.massenWert.value = true
m.massenBereit.value = true
await m.massenAnwenden()
const schreiben = aufrufe.findLast((a) => a.name === 'merkmalePflegen')
assert.ok(schreiben, 'Massenaktion hat geschrieben')
assert.deepEqual(schreiben.werte.map((w) => w.ziel_id).sort(), ['m1', 'm2'],
  'Nur die sichtbaren Männer bekommen „Predigt" — keine Frau, keine Person ohne Angabe')
assert.ok(schreiben.werte.every((w) => w.schluessel === 'predigt' && w.wert === true))
assert.equal(m.auswahl.value.size, 0, 'Auswahl nach dem Anwenden geleert')

// Zweite Sicherung: selbst wenn die Auswahl (z. B. durch eine spätere
// Antwort) wieder Fremde enthält, schreibt die Aktion nur Sichtbares.
aufrufe.length = 0
m.auswahlUmschalten('w1', true)
m.auswahlUmschalten('m1', true)
assert.equal(m.auswahl.value.size, 2, 'Auswahl enthält eine Nichtsichtbare')
assert.deepEqual([...m.auswahlSichtbar.value], ['m1'], 'Schnittmenge mit den sichtbaren Personen')
m.massenMerkmal.value = 'predigt'
m.massenWert.value = true
m.massenBereit.value = true
await m.massenAnwenden()
const zweite = aufrufe.findLast((a) => a.name === 'merkmalePflegen')
assert.deepEqual(zweite.werte.map((w) => w.ziel_id), ['m1'], 'Auch hier: nur sichtbare Männer')

// Anzahl ohne Angabe für den Hinweis (eine Person ohne Wert).
assert.equal(m.ohneGeschlechtAnzahl.value, 1)

console.log('PR-G1 Massenaktion: Filterwechsel beschneidet die Auswahl, angewendet wird nur Sichtbares')
