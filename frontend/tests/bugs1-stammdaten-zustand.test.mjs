/**
 * BUG-S1 — Stammdaten: ein Ladefehler (oder eine Adresse ohne Plantyp) darf
 * NIE das Lade-Skelett stehen lassen.
 *
 * Befund (Manuel, 12.11.): `#/dienste/vorlagen/-/stammdaten/kindergottesdienst`
 * zeigte dauerhaft das Skelett. Der Router las die Marke „-“ als Plantyp, die
 * Abfrage scheiterte — und in `ladenStarten` stand der Ausstieg „kein Plantyp,
 * kein Plan“ VOR `laden.value = false`, sodass `laden` für immer `true` blieb.
 *
 * Führt den ECHTEN Skriptteil der Seite mit einem Vue-Ersatz aus (Muster:
 * tests/planrahmen-stammdaten.test.mjs) und prüft den Ladezustand sowie den
 * Plantyp, der tatsächlich angefragt wird.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

let hash = '#/'
globalThis.__b1Window = { location: { get hash() { return hash } } }
globalThis.__b1Vue = {
  ref: (v) => ({ value: v }),
  reactive: (o) => o,
  computed: (f) => (typeof f === 'function' ? { get value() { return f() } } : f),
  watch: () => {},
  onMounted: () => {},
  onUnmounted: () => {},
}
globalThis.__b1Routen = {}
globalThis.defineProps = () => ({ plantyp: '', plan: '' })

const aufrufe = []
let antwort = { definition: { name: 'Kindergottesdienst', merkmale: {}, sammlungen: [] }, personen: [] }
globalThis.__b1Api = {
  planHolen: async (plan) => { aufrufe.push({ name: 'planHolen', plan }); return {} },
  stammdatenHolen: async (plantyp, plan) => {
    aufrufe.push({ name: 'stammdatenHolen', plantyp, plan })
    if (antwort instanceof Error) throw antwort
    return antwort
  },
  bedarf: async () => [],
  merkmalePflegen: async () => ({}),
  sammlungPflegen: async () => ({ eintraege: [], gruppe_id: 'g1' }),
}

let code = readFileSync(new URL('../src/diakonos/pages/planrahmen/Stammdaten.vue', import.meta.url), 'utf8')
code = code.split('<script setup>')[1].split('</script>')[0]
code = code.replace(/^import[\s\S]*?from[^\n]+\n/gm, '')
code = `const { ref, reactive, computed, watch, onMounted, onUnmounted } = globalThis.__b1Vue
const useLadeSkelett = (laedt) => ({ skelettSichtbar: laedt })
const usePlanrahmen = () => globalThis.__b1Api
const useHandyHinweis = () => ({ geschlossen: () => false, schliessen: () => true })
const hinweisZeigen = () => false
function istHandyHinweisLage() { return false }
function handyHinweisLage() { return { grob: false, breite: 1366, hoehe: 800 } }
const getRouteParam = (key) => globalThis.__b1Routen[key]
const showToast = () => {}
const fehlerMeldungen = (e) => [{ pfad: '', code: String(e?.status || ''), meldung: e?.message || 'Fehler', hinweis: '', stufe: 'fehler' }]
const datumText = (x) => x
` + readFileSync(new URL('../src/diakonos/pages/planrahmen/stammdaten-geschlecht.mjs', import.meta.url), 'utf8') + code
code += `\nexport { ladenStarten, laden, seitenFehler, daten, geladenerTyp, ktxPlantyp, planIdGeladen };`
const seite = await import('data:text/javascript;base64,' + Buffer.from(code).toString('base64'))

// Browser-Fenster der Seite (Hash-Kontext) umstellen. Die Seite liest
// `window.location.hash` (Router-Muster: globale `window`), der Zugriff auf die
// Route kommt über den Ersatz `getRouteParam`.
const setzeHash = (neu) => {
  hash = neu
  globalThis.window = { location: { get hash() { return hash } } }
}
setzeHash('#/')

// ── A: Die Adresse aus dem Befund fragt den ECHTEN Plantyp an ──────────────
{
  setzeHash('#/dienste/vorlagen/-/stammdaten/kindergottesdienst')
  globalThis.__b1Routen = { marke: 'kindergottesdienst' } // Route führt die Marke als Parameter
  aufrufe.length = 0
  antwort = { definition: { name: 'Kindergottesdienst', merkmale: {}, sammlungen: [] }, personen: [] }
  await seite.ladenStarten()
  assert.deepEqual(aufrufe[0], { name: 'stammdatenHolen', plantyp: 'kindergottesdienst', plan: null },
    'die Marke „-“ darf NICHT als Plantyp angefragt werden')
  assert.equal(seite.ktxPlantyp.value, 'kindergottesdienst')
  assert.equal(seite.laden.value, false, 'nach dem Laden kein Skelett')
  assert.deepEqual(seite.seitenFehler.value, [])
}

// ── B: Alte Reihenfolge (Plantyp vorne, „-“ hinten) bleibt lesbar ──────────
{
  setzeHash('#/dienste/vorlagen/chorplan/stammdaten/-')
  globalThis.__b1Routen = {}
  aufrufe.length = 0
  await seite.ladenStarten()
  assert.deepEqual(aufrufe[0], { name: 'stammdatenHolen', plantyp: 'chorplan', plan: null },
    'auch die alte Reihenfolge liefert den echten Plantyp')
}

// ── C: Ladefehler → Meldung statt Skelett ─────────────────────────────────
{
  setzeHash('#/dienste/vorlagen/-/stammdaten/gibtesnicht')
  globalThis.__b1Routen = {}
  aufrufe.length = 0
  antwort = Object.assign(new Error('Diese Planvorlage wurde nicht gefunden.'), { status: 404 })
  await seite.ladenStarten()
  assert.equal(seite.laden.value, false, 'Ladefehler beendet den Ladezustand (kein ewiges Skelett)')
  assert.ok(seite.seitenFehler.value.length >= 1, 'der Fehler wird gemeldet')
  assert.equal(seite.daten.value, null)
}

// ── D: Adresse OHNE Plantyp/Plan → Hinweis statt Skelett ───────────────────
{
  setzeHash('#/dienste/vorlagen/-/stammdaten/-')
  globalThis.__b1Routen = {}
  aufrufe.length = 0
  antwort = { definition: { name: 'X', merkmale: {}, sammlungen: [] }, personen: [] }
  await seite.ladenStarten()
  assert.equal(seite.ktxPlantyp.value, '', 'der Platzhalter „-“ ist kein Plantyp')
  assert.equal(aufrufe.length, 0, 'ohne Plantyp wird nichts angefragt')
  assert.equal(seite.laden.value, false, 'auch ohne Plantyp endet der Ladezustand — kein ewiges Skelett')
  assert.equal(seite.daten.value, null, 'Leerzustand „Keine Planvorlage ausgewählt“ wird sichtbar')
}

// ── E: Ein Fehler aus einem früheren Lauf bleibt nicht stehen ──────────────
{
  setzeHash('#/dienste/vorlagen/-/stammdaten/chorplan')
  globalThis.__b1Routen = {}
  antwort = { definition: { name: 'Chorplan', merkmale: {}, sammlungen: [] }, personen: [] }
  await seite.ladenStarten()
  assert.deepEqual(seite.seitenFehler.value, [], 'nach erfolgreichem Laden keine alte Meldung mehr')
  assert.equal(seite.laden.value, false)
  assert.ok(seite.daten.value, 'Daten stehen')
}

// ── F: Der alte Fehlerzustand wird beim Wechsel nicht mitgeschleppt ────────
{
  setzeHash('#/dienste/vorlagen/-/stammdaten/gibtesnicht')
  globalThis.__b1Routen = {}
  antwort = Object.assign(new Error('nicht gefunden'), { status: 404 })
  await seite.ladenStarten()
  assert.ok(seite.seitenFehler.value.length >= 1)
  setzeHash('#/dienste/vorlagen/-/stammdaten/-')
  globalThis.__b1Routen = {}
  await seite.ladenStarten()
  assert.deepEqual(seite.seitenFehler.value, [], 'Wechsel auf eine Adresse ohne Typ räumt die alte Meldung weg')
  assert.equal(seite.laden.value, false)
}

console.log('BUG-S1 Stammdaten: Fehler/Leerzustand statt ewiges Skelett: bestanden')
