/**
 * FIX-8 — Wächter: keine ungebundenen Bezeichner im SCRIPT (`<script>` /
 * `<script setup>` von `.vue`, dazu `.js`/`.mjs`) unter `frontend/src`.
 *
 * Anlass (Dev-Befund UX2d3a): `MitgliedDetail.vue` rief `useLadeSkelett()`
 * ohne Import auf. Zur Laufzeit warf das einen `ReferenceError`, die Seite
 * war tot. FIX-7 (`fix7-vorlagen-bezeichner.test.mjs`) prüft nur
 * TEMPLATE-Ausdrücke gegen die Skript-Bindungen — ein im Skript vergessener
 * Import ist dort unsichtbar. Dieser Test schließt die Lücke.
 *
 * WARUM KEIN NEUES WERKZEUG (Kartenauflage)
 * -----------------------------------------
 * `frontend/package.json` bringt **kein ESLint** mit; ein `eslint` +
 * `eslint-plugin-vue` als neue devDependency wäre ein schweres Werkzeug samt
 * eigener Konfigurationsfläche, das noch nie im Image gebaut wurde (Regel 13:
 * der Build muss im Frontend-Stage grün sein, sonst bricht die Abnahme).
 * Vorhanden und bereits im Image erprobt sind dagegen:
 *   * `@vue/compiler-sfc` (SFC zerlegen, auch `lang="ts"`) — wie FIX-7,
 *   * `@babel/parser` (AST je Skriptblock) — wie FIX-7.
 * Beides kommt transitiv über `vue` mit (`package-lock.json`: compiler-sfc
 * 3.5.44, parser 7.29.9) und läuft seit FIX-7 im Frontend-Stage. Die
 * Scope-Analyse (welche Namen sind deklariert, welche verwendet) macht
 * `tools/script-bezeichner-kern.mjs` selbst — ein paar Dutzend Zeilen statt
 * einer Plugin-Kette. Vorteil: wir prüfen genau die Regel, die uns getroffen
 * hat, und können sie in eigenen Gegenproben festnageln.
 *
 * Werkzeug: `frontend/tools/script-bezeichner.mjs` (+ `-kern.mjs`,
 * `script-erlaubt.mjs`). Erlaubt-Liste mit Begründung; `*.test.mjs` sind
 * ausgenommen (Node-Lauf, nicht Browser — Grund im Werkzeug).
 *
 * Bekannte Grenze: EINE Menge deklarierter Namen je Datei (bei `.vue`
 * `<script>` + `<script setup>` zusammen), keine echte Scope-Analyse — ein
 * Name, der nur in einer inneren Funktion deklariert ist, gilt dateiweit als
 * gebunden. Ziel ist der vergessene Import, nicht jede Schattierung.
 *
 * Belege (2026-11-05/06, Worktree t_033ea487):
 *   Vor dem Fix meldete das Werkzeug gegen unverändertes `src` 4 Dateien /
 *   5 Namen: `useEventsApi.js: toLocalDateTimeString` (der echte
 *   ReferenceError — `createEvent(start: Date)` warf ihn), `Rahmen.vue:
 *   innerWidth/innerHeight`, `MitgliedHinzufuegenDialog.vue` und
 *   `KalenderImport.vue: Uint8Array` (Klasse 2, ohne globalThis).
 *   Nach dem Fix: 0 Befunde.
 *   Mutationsprobe (zweifach belegt): (a) `useLadeSkelett()` ohne Import →
 *   rot; (b) echter Eingriff in `useEventsApi.js` (Import `alsServerZeit`
 *   entfernt) → `not ok 1 … alsServerZeit@114`, zurückgesetzt → grün.
 *   Im Image: `docker build -f backend/Dockerfile --target frontend` →
 *   exit 0, `# tests 1842 / # fail 0`, dieser Test läuft dort mit.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import * as sfc from '@vue/compiler-sfc'
import {
  AUSGENOMMEN,
  ERLAUBT,
  ERLAUBT_ZUSAMMENGESETZT,
  pruefeBaum,
  pruefeDatei,
  skriptDateien,
  istTestdatei,
  sprichtGlobalThisAn,
} from '../tools/script-bezeichner.mjs'

// `frontend/tests/` → `frontend/`. Im Docker-Build ist `/build/` die Wurzel,
// dort stimmt derselbe Weg (`/build/src`).
const FRONTEND = fileURLToPath(new URL('../', import.meta.url))
const QUELLEN = FRONTEND + 'src'

/** Befundliste als lesbare Meldung. */
function meldung(befunde) {
  return befunde
    .map((b) => {
      if (b.fehler) return `${b.datei}: ${b.fehler}`
      return `${b.datei}: ${b.fehlend.map((f) => `${f.name}@${f.zeile}`).join(', ')}`
    })
    .join('\n')
}

test('alle Skripte unter src sind frei von ungebundenen Bezeichnern', () => {
  const dateien = skriptDateien(QUELLEN)
  // Sicherung gegen stillen Leerlauf: der Baum hat >300 Skripte.
  assert.ok(dateien.length > 300, `zu wenige Skripte gefunden (${dateien.length})`)
  const befunde = pruefeBaum(QUELLEN, sfc, true)
  assert.equal(befunde.length, 0, 'ungebundene Bezeichner im Skript gefunden:\n' + meldung(befunde))
})

test('Gegenprobe: der Originalbefund (useLadeSkelett ohne Import) wird ERKANNT', () => {
  const quelle = `<script setup>
import { ref } from 'vue'
const mitglied = ref(null)
function laden() {
  const zustand = useLadeSkelett()
  return zustand
}
</script>

<template><div>{{ mitglied }}</div></template>
`
  const befund = pruefeDatei('/virtuell/MitgliedDetail.vue', sfc, quelle)
  assert.equal(befund.fehler, null)
  assert.deepEqual(
    befund.fehlend.map((f) => f.name),
    ['useLadeSkelett'],
    'erwartet wird genau der fehlende Import — gebundene Namen nicht',
  )
})

test('Gegenprobe: Mutationsprobe — Import entfernen macht rot, einsetzen grün', () => {
  const datei = QUELLEN + '/diakonos/composables/useLadeSkelett.js'
  const sauber = `<script setup>
import { ref } from 'vue'
import { useLadeSkelett } from '../../composables/useLadeSkelett.js'
const mitglied = ref(null)
const zustand = useLadeSkelett()
</script>

<template><div>{{ zustand }}</div></template>
`
  assert.deepEqual(pruefeDatei('/virtuell/mit.vue', sfc, sauber).fehlend, [], 'mit Import: sauber')

  // Mutation: genau die Import-Zeile entfernen.
  const mutiert = sauber.replace(/^.*useLadeSkelett \} from.*\n/m, '')
  assert.notEqual(mutiert, sauber, 'Mutation hat nicht gegriffen')
  assert.deepEqual(
    pruefeDatei('/virtuell/ohne.vue', sfc, mutiert).fehlend.map((f) => f.name),
    ['useLadeSkelett'],
    'ohne Import muss der Wächter rot werden',
  )
  // Der echte Helfer existiert — der Befund ist damit eindeutig ein Importfehler.
  assert.ok(readFileSync(datei, 'utf8').includes('useLadeSkelett'), 'ladeSkelett.mjs fehlt')
})

test('Gegenprobe (Bestand): useEventsApi/createEvent nutzt einen gebundenen Namen', () => {
  // Befund vor dem Fix: `toLocalDateTimeString` stand nirgends im Skript —
  // `createEvent(title, new Date(), …)` warf ReferenceError. Die Datei ist
  // heute sauber; die Prüfung direkt auf der Datei ist der Beleg.
  const datei = QUELLEN + '/diakonos/composables/useEventsApi.js'
  const befund = pruefeDatei(datei, sfc)
  assert.equal(befund.fehler, null)
  assert.deepEqual(befund.fehlend, [], 'useEventsApi.js hat wieder ungebundene Namen')
  const quelle = readFileSync(datei, 'utf8')
  // Der Name darf nur noch im ERKLAERENDEN Kommentar stehen (dort nennt ihn
  // der Fix), nicht im Code — ein Aufruf waere wieder der ReferenceError.
  const zeilen = quelle.split('\n')
  const codeTreffer = zeilen.filter((z, i) => {
    if (!/toLocalDateTimeString/.test(z)) return false
    const bisZeile = zeilen.slice(0, i + 1).join('\n')
    return !/\/\*[\s\S]*$/.test(bisZeile) && !/^\s*(\/\/|\*)/.test(z)
  })
  assert.deepEqual(codeTreffer, [], 'toLocalDateTimeString steht wieder im Code')
  assert.match(quelle, /import \{[^}]*alsServerZeit[^}]*\} from '\.\/datumZeit\.mjs'/)
})

test('Gegenprobe: Member, Objektschlüssel, Parameter und Hoisting sind KEINE Befunde', () => {
  const quelle = `import { computed } from 'vue'
const basis = { feld: 1 }
const wert = basis.feld
const kopie = { feld: wert, kurz: (a) => a + wert }
function frueh() { return spaeter() }
function spaeter() { return 1 }
try { } catch (fehler) { void fehler }
const [erst, ...rest] = [1, 2, 3]
let { einzeln } = basis
export { wert as anderer }
class Eigene { methode(p) { return p } }
const o = new Eigene().methode(erst + rest.length + einzeln)
void kopie; void frueh; void o; void computed
`
  const befund = pruefeDatei('/virtuell/fein.js', sfc, quelle)
  assert.equal(befund.fehler, null)
  assert.deepEqual(befund.fehlend, [], 'Fehlalarm: ' + befund.fehlend.map((f) => f.name).join(', '))
})

test('Erlaubt-Liste ist begründet (kein stiller Freibrief)', () => {
  for (const [name, grund] of ERLAUBT) {
    assert.equal(typeof grund, 'string', `${name} ohne Begründung`)
    assert.ok(grund.trim().length > 5, `${name}: Begründung zu kurz („${grund}“)`)
  }
  for (const [name, grund] of AUSGENOMMEN) {
    assert.ok(grund.trim().length > 20, `${name}: Ausnahme ohne tragfähigen Grund`)
  }
  // Die Fehlerklasse aus UX2d3a darf NIE als Ausnahme durchgehen.
  for (const name of ['useLadeSkelett', 'toLocalDateTimeString', 'fmtDate']) {
    assert.ok(!ERLAUBT.has(name), `${name} darf keine Ausnahme sein`)
    assert.ok(!ERLAUBT_ZUSAMMENGESETZT.has(name), `${name} darf keine Ausnahme sein`)
  }
  // Projekt-Bibliotheken müssen importiert werden — sie stehen nicht drin.
  for (const name of ['ref', 'computed', 'useRouter', 'useRoute', 'defineStore', 'apiUrl', 'IconPlus']) {
    assert.ok(!ERLAUBT.has(name), `${name} darf keine Ausnahme sein (Import ist Pflicht)`)
  }
  // Vue-Compiler-Makros sind dagegen ausdrücklich erlaubt.
  for (const name of ['defineProps', 'defineEmits', 'defineExpose', 'withDefaults']) {
    assert.ok(ERLAUBT.has(name), `${name} fehlt in der Erlaubt-Liste`)
  }
})

test('Klasse 2: zusammengesetzte Browser-Typen nur mit globalThis', () => {
  // Ohne globalThis → Befund mit Hinweis.
  const ohne = 'const puffer = new Uint8Array(4)\nvoid puffer\n'
  const befund = pruefeDatei('/virtuell/puffer.js', sfc, ohne).fehlend
  assert.deepEqual(befund.map((f) => f.name), ['Uint8Array'])
  assert.match(befund[0].hinweis, /globalThis\.Uint8Array/)
  // Mit globalThis in derselben Datei → sauber (Abhängigkeit sichtbar).
  const mit = 'const puffer = new globalThis.Uint8Array(4)\nconst zweiter = new Uint8Array(2)\nvoid puffer; void zweiter\n'
  assert.deepEqual(pruefeDatei('/virtuell/puffer2.js', sfc, mit).fehlend, [])
  assert.equal(sprichtGlobalThisAn(mit, 'Uint8Array'), true)
  assert.equal(sprichtGlobalThisAn(ohne, 'Uint8Array'), false)
})

test('Testdateien sind ausgenommen (Grund im Werkzeug hinterlegt)', () => {
  assert.equal(istTestdatei('src/diakonos/composables/p21-sitzung.test.mjs'), true)
  assert.equal(istTestdatei('src/diakonos/composables/useApi.js'), false)
  assert.deepEqual(pruefeDatei('/virtuell/p21-sitzung.test.mjs', sfc, 'Buffer.from("x")\n').fehlend, [])
})

test('Syntaxfehler werden gemeldet, nicht verschluckt', () => {
  const befund = pruefeDatei('/virtuell/kaputt.js', sfc, 'function (\n')
  assert.ok(befund.fehler, 'Syntaxfehler muss als Fehler auftauchen')
  assert.match(befund.fehler, /Syntaxfehler/)
})

test('Gegenprobe: Klassenfeld-Initialisierer werden geprüft (static s = zzz)', () => {
  const quelle = 'class K { static s = zzz; t = 1 }\nvoid K\n'
  const befund = pruefeDatei('/virtuell/klasse.js', sfc, quelle)
  assert.deepEqual(befund.fehlend.map((f) => f.name), ['zzz'])
})

test('Gegenprobe: <script> und <script setup> teilen EINE Namensmenge', () => {
  const quelle = `<script>
const K = 42
export default { name: 'Zwei' }
</script>
<script setup>
import { ref } from 'vue'
const wert = ref(K)
void wert
</script>
<template><p>x</p></template>
`
  const befund = pruefeDatei('/virtuell/Zwei.vue', sfc, quelle)
  assert.equal(befund.fehler, null)
  assert.deepEqual(befund.fehlend, [], 'Fehlalarm: ' + befund.fehlend.map((f) => f.name).join(', '))
  // Gegenprobe: ohne die Deklaration in <script> wird K gemeldet.
  const ohne = quelle.replace('const K = 42\n', '')
  assert.deepEqual(pruefeDatei('/virtuell/Zwei2.vue', sfc, ohne).fehlend.map((f) => f.name), ['K'])
})
