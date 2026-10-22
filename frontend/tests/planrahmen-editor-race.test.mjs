import { readFileSync } from 'node:fs'
import assert from 'node:assert/strict'
import * as vue from 'vue'

// Tatsächliches script setup mit Vue-Reaktivität; nur API-Grenze verzögern.
const requests = []
const props = vue.reactive({ modelValue: false, plan: 'p', termin: { id: 't' }, feldPfad: 'a',
  slots: ['a', 'b', 'text'].map(id => ({ feld_pfad: id, art: id === 'text' ? 'text' : 'person', feld: { id } })), eintraege: [] })
globalThis.__raceVue = vue
globalThis.defineProps = () => props
globalThis.defineEmits = () => () => {}
globalThis.__raceApi = { feldKandidaten: (p, t, f) => new Promise((resolve, reject) => requests.push({ p, t, f, resolve, reject })) }
let code = readFileSync(new URL('../src/diakonos/components/planrahmen/PrEditor.vue', import.meta.url), 'utf8').split('<script setup>')[1].split('</script>')[0]
code = code.replace(/import[^\n]+from[^\n]+\n/g, '')
code = `const {ref,computed,watch} = globalThis.__raceVue; const onMounted=()=>{}; const onUnmounted=()=>{}; const inject=()=>null; const usePlanrahmen=()=>globalThis.__raceApi; const datumText=x=>x; const wertText=x=>x; const fehlerMeldungen=e=>[{meldung:e.message}]; const feldGehoertZu=(a,b)=>a===b; const anzahlBereich=a=>({min:0,max:2});\n` + code
code += '\nexport {zielPfad,kandidatenListe,kandidatenLaedt,kandidatenFehler};'
const m = await import('data:text/javascript;base64,' + Buffer.from(code).toString('base64'))
const tick = async () => { await vue.nextTick(); await vue.nextTick() }
const reply = (r, id) => r.resolve({ kandidaten: [{ kennung: id, name: id }] })
props.modelValue = true
await tick()
const old = requests.splice(0)
m.zielPfad.value = 'b'
await tick()
reply(requests.shift(), 'b')
await tick()
old.forEach(r => reply(r, 'a'))
await tick()
assert.equal(m.kandidatenListe.value[0].kennung, 'b', 'Umgekehrte Antwortreihenfolge')

m.zielPfad.value = 'a'
await tick()
const textOld = requests.shift()
m.zielPfad.value = 'text'
await tick()
assert.equal(m.kandidatenLaedt.value, false, 'Textfeld wartet nicht auf alte Kandidaten')
reply(textOld, 'a')
await tick()
assert.deepEqual(m.kandidatenListe.value, [])

m.zielPfad.value = 'a'
await tick()
const closed = requests.shift()
props.modelValue = false
await tick()
assert.equal(m.kandidatenLaedt.value, false)
props.modelValue = true
await tick()
const reopened = requests.splice(0)
closed.reject(new Error('Veralteter Fehler'))
await tick()
assert.deepEqual(m.kandidatenFehler.value, [], 'Alte Fehler dürfen nicht neuen Dialog treffen')
assert.equal(m.kandidatenLaedt.value, true, 'Altes finally darf neuen Ladezustand nicht löschen')
reopened.forEach(r => reply(r, 'neu'))
await tick()
assert.equal(m.kandidatenListe.value[0].kennung, 'neu')

props.termin = { id: 'anderer-termin' }
await tick()
const other = requests.splice(0)
assert.ok(other.length, 'Terminwechsel lädt passende Kandidaten')
props.plan = 'anderer-plan'
await tick()
other.forEach(r => reply(r, 'alter-termin'))
await tick()
assert.deepEqual(m.kandidatenListe.value, [])
assert.equal(m.kandidatenLaedt.value, true)
requests.splice(0).forEach(r => reply(r, 'anderer-plan'))
await tick()
assert.equal(m.kandidatenListe.value[0].kennung, 'anderer-plan')
console.log('Editor-Race: Feld/Text/Schließen/Neuöffnen/Termin/Plan und veraltete Fehler/finally bestanden')
