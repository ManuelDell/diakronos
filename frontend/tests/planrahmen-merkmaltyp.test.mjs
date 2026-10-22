import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

// MerkmalWert-Eingaben: Art-Logik ohne Template und ohne node_modules.
const emisse = []
globalThis.__mkVue = { computed: (f) => ({ get value() { return f() } }) }
globalThis.__mkProps = { merkmal: null, modelValue: null, personen: [], kompakt: false, readonly: false }
globalThis.defineProps = () => globalThis.__mkProps
// v-model-Nachbildung: das emit-Update fließt zurück ins Model.
globalThis.defineEmits = () => (name, wert) => {
  emisse.push([name, wert])
  if (name === 'update:modelValue') globalThis.__mkProps.modelValue = wert
}
globalThis.defineExpose = () => {}

let code = readFileSync(new URL('../src/diakonos/components/planrahmen/MerkmalWert.vue', import.meta.url), 'utf8')
code = code.split('<script setup>')[1].split('</script>')[0]
code = code.replace(/import[^\n]+from[^\n]+\n/g, '')
code = `const { computed } = globalThis.__mkVue\n` + code
code += '\nexport { tagSetzen, auswahlSetzen, personSetzen, textSetzen, datumSetzen, zahlSetzen, mehrfachToggle, liste, stringWert, sortiertePersonen, setze };'
const m = await import('data:text/javascript;base64,' + Buffer.from(code).toString('base64'))

const letzter = () => emisse[emisse.length - 1]
const wertVon = () => letzter()[1]

// ── Zahl ───────────────────────────────────────────────────────────────────
globalThis.__mkProps.merkmal = { id: 'alter', art: 'zahl' }
m.zahlSetzen('')
assert.deepEqual(letzter(), ['update:modelValue', null], 'Leere Zahl wird zu null')
m.zahlSetzen('42')
assert.equal(wertVon(), 42)

// ── Text ───────────────────────────────────────────────────────────────────
globalThis.__mkProps.merkmal = { id: 'notiz', art: 'text' }
m.textSetzen('   ')
assert.equal(wertVon(), null, 'Nur Leerzeichen wird zu null')
m.textSetzen('Gut geübt')
assert.equal(wertVon(), 'Gut geübt')

// ── Datum ──────────────────────────────────────────────────────────────────
globalThis.__mkProps.merkmal = { id: 'frist', art: 'datum' }
m.datumSetzen('')
assert.equal(wertVon(), null)
m.datumSetzen('2026-12-24')
assert.equal(wertVon(), '2026-12-24', 'ISO-Datum bleibt unverändert')

// ── Tag ────────────────────────────────────────────────────────────────────
globalThis.__mkProps.merkmal = { id: 'klavier', art: 'tag' }
m.tagSetzen(true)
assert.equal(wertVon(), true)
m.tagSetzen(false)
assert.equal(wertVon(), false)

// ── Auswahl (einzel) ───────────────────────────────────────────────────────
globalThis.__mkProps.merkmal = { id: 'stimme', art: 'auswahl', werte: ['Sopran', 'Alt'] }
m.auswahlSetzen('')
assert.equal(wertVon(), null, 'Leere Auswahl wird zu null')
m.auswahlSetzen('Alt')
assert.equal(wertVon(), 'Alt')
m.auswahlSetzen('Bass')
assert.equal(wertVon(), 'Bass', 'Wert wird nicht auf die Liste begrenzt (Server prüft)')

// ── Auswahl mehrfach: additive Liste ───────────────────────────────────────
globalThis.__mkProps.merkmal = { id: 'instrumente', art: 'auswahl', werte: ['Gitarre', 'Bass', ' Orgel'], mehrfach: true }
globalThis.__mkProps.modelValue = ['Gitarre']
m.mehrfachToggle('Bass', true)
assert.deepEqual(wertVon(), ['Gitarre', 'Bass'])
m.mehrfachToggle('Bass', true)
assert.deepEqual(wertVon(), ['Gitarre', 'Bass'], 'Keine Dopplung')
m.mehrfachToggle('Gitarre', false)
assert.deepEqual(wertVon(), ['Bass'])
assert.deepEqual(m.liste.value, ['Bass'], 'liste spiegelt das Model')

// ── Person: Kennung durchreichen ───────────────────────────────────────────
globalThis.__mkProps.merkmal = { id: 'dirigent', art: 'person' }
m.personSetzen('')
assert.equal(wertVon(), null)
m.personSetzen('p1')
assert.equal(wertVon(), 'p1', 'Person wird als Kennung gespeichert')

// ── Person-Dropdown sortiert nach Namen ────────────────────────────────────
globalThis.__mkProps.personen = [
  { id: 'p2', name: 'Bernd B' }, { id: 'p1', name: 'Anna A' }, { id: 'p0', name: '' },
]
assert.deepEqual(m.sortiertePersonen.value.map((p) => p.id), ['p1', 'p2', 'p0'])

// ── stringWert für Datum/Text-Anzeige ──────────────────────────────────────
globalThis.__mkProps.modelValue = 7
assert.equal(m.stringWert.value, '7')
globalThis.__mkProps.modelValue = null
assert.equal(m.stringWert.value, '')

console.log('Planrahmen-MerkmalWert: tag/auswahl/mehrfach/text/zahl/datum/person Eingaben bestanden')
