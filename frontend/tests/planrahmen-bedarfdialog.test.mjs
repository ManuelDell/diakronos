import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

// BedarfDialog: Gruppen, Schlüssel, Emits und Reset — ohne Template, ohne node_modules.
const beobachter = []
const emisse = []
globalThis.__bdVue = {
  ref: (v) => ({ value: v }),
  computed: (f) => (typeof f === 'function'
    ? { get value() { return f() } }
    : { get value() { return f.get() }, set value(v) { f.set(v) } }),
  watch: (src, cb) => beobachter.push({ src, cb }),
}
globalThis.__bdProps = { modelValue: false, bedarf: [], busy: false, fortsetzenText: '' }
globalThis.defineProps = () => globalThis.__bdProps
globalThis.defineEmits = () => (...args) => emisse.push(args)
globalThis.defineExpose = () => {}

let code = readFileSync(new URL('../src/diakonos/components/planrahmen/BedarfDialog.vue', import.meta.url), 'utf8')
code = code.split('<script setup>')[1].split('</script>')[0]
code = code.replace(/import[^\n]+from[^\n]+\n/g, '')
code = `const { ref, computed, watch } = globalThis.__bdVue\n` + code
code += '\nexport { offen, uebersprungen, merkmale, sammlungen, rollen, offeneEintraege, schluessel, einstufungText, einstufungKlasse, einrichten, ueberspringen, alleUeberspringen, fortsetzen, schliessen };'
const m = await import('data:text/javascript;base64,' + Buffer.from(code).toString('base64'))

// ── Gruppierung: nur einstufung !== 'ok' wird gezeigt ──────────────────────
globalThis.__bdProps.bedarf = [
  { art: 'merkmal', kennung: 'klavier', abdeckung: '1 Personen mit klavier', detail: '', einstufung: 'eingeschraenkt' },
  { art: 'merkmal', kennung: 'kuerzel', abdeckung: '5 Personen mit kuerzel', detail: '', einstufung: 'ok' },
  { art: 'sammlung', kennung: 'bibelarbeiten', abdeckung: 'Sammlung bibelarbeiten ist leer', detail: '', einstufung: 'blockiert_automatik' },
  { art: 'rolle', kennung: 'saenger', abdeckung: '2 Personen erfuellen Rolle saenger', detail: '', einstufung: 'eingeschraenkt' },
  { art: 'rolle', kennung: 'leiter', abdeckung: '3 Personen erfuellen Rolle leiter', detail: '', einstufung: 'ok' },
]
assert.deepEqual(m.merkmale.value.map((e) => e.kennung), ['klavier'], "'ok'-Merkmale werden nicht aufgelistet")
assert.deepEqual(m.sammlungen.value.map((e) => e.kennung), ['bibelarbeiten'])
assert.deepEqual(m.rollen.value.map((e) => e.kennung), ['saenger'])

// ── Schlüssel art+kennung: gleiche Kennung, verschiedene Art ───────────────
assert.equal(m.schluessel({ art: 'merkmal', kennung: 'x' }), 'merkmal:x')
assert.equal(m.schluessel({ art: 'sammlung', kennung: 'x' }), 'sammlung:x')
assert.notEqual(m.schluessel({ art: 'merkmal', kennung: 'x' }), m.schluessel({ art: 'sammlung', kennung: 'x' }))

// ── Einrichten: Emit mit Eintrag und Schließen ─────────────────────────────
globalThis.__bdProps.modelValue = true
const merkmalX = globalThis.__bdProps.bedarf[0]
m.einrichten(merkmalX)
assert.deepEqual(emisse.at(-2), ['einrichten', merkmalX], 'Einrichten sendet den Bedarfseintrag')
assert.deepEqual(emisse.at(-1), ['update:modelValue', false], 'Dialog schließt danach')

// ── Überspringen: merkmal:x bleibt sammlung:x unberührt ───────────────────
emisse.length = 0
const sammlungX = globalThis.__bdProps.bedarf[2]
globalThis.__bdProps.bedarf = [
  { ...sammlungX, art: 'merkmal' }, sammlungX,
]
m.ueberspringen({ art: 'merkmal', kennung: 'bibelarbeiten' })
assert.deepEqual(emisse.at(-1), ['ueberspringen', { art: 'merkmal', kennung: 'bibelarbeiten' }])
assert.deepEqual(m.offeneEintraege.value.map((e) => e.kennung), ['bibelarbeiten'],
  'Übersprungene merkmal:bibelarbeiten löscht nicht sammlung:bibelarbeiten')
m.ueberspringen(sammlungX)
assert.deepEqual(m.offeneEintraege.value, [], 'Nach beiden Überspringen ist nichts mehr offen')
assert.deepEqual([...m.uebersprungen.value], ['merkmal:bibelarbeiten', 'sammlung:bibelarbeiten'])

// ── Alle überspringen: jeder offene Eintrag einmal, dann Schließen ────────
emisse.length = 0
m.uebersprungen.value = new Set()
const offenVorher = m.offeneEintraege.value.length
m.alleUeberspringen()
const skips = emisse.filter(([n]) => n === 'ueberspringen')
assert.equal(skips.length, offenVorher, 'Pro offenem Merkmal/Sammlung genau ein Emit')
assert.deepEqual(emisse.at(-1), ['update:modelValue', false])

// ── Fortsetzen: schließt und sendet 'fortsetzen' ───────────────────────────
emisse.length = 0
globalThis.__bdProps.fortsetzenText = 'Trotzdem Plan anlegen'
m.fortsetzen()
assert.deepEqual(emisse, [['update:modelValue', false], ['fortsetzen']])

// ── Reset bei Öffnung und bei neuer Bedarfsliste ───────────────────────────
emisse.length = 0
m.uebersprungen.value = new Set()
m.ueberspringen(sammlungX)
assert.equal(m.uebersprungen.value.size, 1)
const oeffnen = beobachter.find((b) => b.src() === true || typeof b.src === 'function')
assert.ok(beobachter.length >= 2, 'Watches auf modelValue und bedarf registriert')
beobachter[0].cb(true)   // Dialog öffnen
assert.equal(m.uebersprungen.value.size, 0, 'Beim Öffnen ist alles wieder offen')
m.ueberspringen(sammlungX)
assert.equal(m.uebersprungen.value.size, 1)
beobachter[1].cb([])     // Neue Bedarfsliste
assert.equal(m.uebersprungen.value.size, 0, 'Neue Bedarfsliste setzt Überspringungen zurück')

// ── Einstufungs-Texte ──────────────────────────────────────────────────────
assert.equal(m.einstufungText('ok'), 'Ausreichend')
assert.equal(m.einstufungText('eingeschraenkt'), 'Unvollständig')
assert.equal(m.einstufungText('blockiert_automatik'), 'Automatik eingeschränkt', 'Niemals „blockiert“ — die Automatik wird nur eingeschränkt')
assert.equal(m.einstufungKlasse('eingeschraenkt'), 'dk-badge-warning')
void oeffnen

console.log('Planrahmen-BedarfDialog: Gruppierung, Schlüssel, Einrichten/Überspringen/Fortsetzen und Reset bestanden')
