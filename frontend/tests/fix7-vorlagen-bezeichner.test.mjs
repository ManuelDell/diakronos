/**
 * FIX-7 — Wächter: keine ungebundenen Template-Bezeichner in `.vue`-Dateien.
 *
 * Befund: `ModerationCard.vue` rief im Template `fmtDate(…)`, die Funktion
 * stand aber nirgends im `<script setup>`. Vue prüft das nicht — beim Rendern
 * bricht der Ausdruck mit „Property "fmtDate" was accessed during render but
 * is not defined" ab, die Zeile bleibt leer. Eine Quelle war die
 * App-Datei selbst (`showAbgelehntView`/`abgelehnterTermin`, daneben
 * `KronosEventView` ohne Import).
 *
 * Dieser Test kompiliert JEDE `.vue` unter `frontend/src` mit
 * `@vue/compiler-sfc`, sammelt die Ausdrücke des Templates und meldet jeden
 * freien Namen, der weder im Skript gebunden noch in der Erlaubt-Liste des
 * Werkzeugs (`tools/vorlagen-bezeichner.mjs`) begründet ist.
 *
 * Werkzeug: `frontend/tools/vorlagen-bezeichner.mjs`
 *   ERLAUBT enthält Sprache, Vue-Globals (`$emit`, `$attrs`, …), die
 *   vue-router-Globals (`$router`, `$route`). Global registrierte Komponenten
 *   gibt es nicht (kein app.component). Jeder Eintrag trägt seinen Grund.
 *
 * Belege (2026-11-05):
 *   - Vor dem Fix meldete das Werkzeug drei Stellen; nach dem Fix keine.
 *   - Gegenprobe unten: eine künstliche Datei mit `fmtDate` muss auffallen.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import * as sfc from '@vue/compiler-sfc'
import * as babel from '@babel/parser'
import {
  ERLAUBT,
  KOMPONENTEN_ERLAUBT,
  pruefeBaum,
  pruefeKomponenten,
  pruefeKomponentenBaum,
  pruefeQuelle,
  vueDateien,
  freieNamen,
  sammleSkriptBindings,
} from '../tools/vorlagen-bezeichner.mjs'

// `frontend/tests/` → `frontend/`. Im Docker-Build ist `/build/` die Wurzel,
// dort stimmt derselbe Weg (`/build/src`).
const FRONTEND = fileURLToPath(new URL('../', import.meta.url))
const QUELLEN = FRONTEND + 'src'

test('alle .vue unter src sind frei von ungebundenen Template-Bezeichnern', () => {
  const dateien = vueDateien(QUELLEN)
  // Sicherung gegen einen stillen Leerlauf: der Baum hat >100 Komponenten.
  assert.ok(dateien.length > 100, `zu wenige .vue gefunden (${dateien.length})`)

  const befunde = pruefeBaum(QUELLEN, sfc, babel, true)
  const meldung = befunde
    .map((b) => {
      if (b.fehler) return `${b.datei}: ${b.fehler}`
      return `${b.datei}: ${b.fehlend.map((f) => f.name).join(', ')}`
    })
    .join('\n')
  assert.equal(befunde.length, 0, 'ungebundene Template-Bezeichner gefunden:\n' + meldung)
})

test('Erlaubt-Liste ist begründet (kein stiller Freibrief)', () => {
  for (const [name, grund] of ERLAUBT) {
    assert.equal(typeof grund, 'string', `${name} ohne Begründung`)
    assert.ok(grund.trim().length > 5, `${name}: Begründung zu kurz („${grund}“)`)
  }
  // Die Vue- und Router-Globals sind ausdrücklich dabei.
  for (const name of ['$emit', '$attrs', '$slots', '$props', '$router', '$route']) {
    assert.ok(ERLAUBT.has(name), `${name} fehlt in der Erlaubt-Liste`)
  }
  // ModerationCard.vue:97-Befund darf NICHT als Ausnahme durchgehen.
  assert.ok(!ERLAUBT.has('fmtDate'), 'fmtDate darf keine Ausnahme sein')
  assert.ok(!ERLAUBT.has('showAbgelehntView'), 'showAbgelehntView darf keine Ausnahme sein')
})

test('Gegenprobe: ein ungebundenes Template-Bezeichner wird ERKANNT', () => {
  const quelle = `<template>
  <div>
    <span v-for="ev in liste" :key="ev.id">{{ fmtDate(ev.start, ev.all_day) }}</span>
    <span>{{ mischung(1, 2) }}</span>
    <span>{{ gebunden }}</span>
  </div>
</template>

<script setup>
import { ref } from 'vue'
const gebunden = ref(0)
const liste = ref([])
function mischung(a, b) { return a - b }
</script>
`
  const { fehlend, fehler } = pruefeQuelle(quelle, 'gegenprobe.vue', sfc, babel)
  assert.equal(fehler, null)
  assert.deepEqual(
    fehlend.map((f) => f.name),
    ['fmtDate'],
    'erwartet wird genau der ungebundene Name — gebundene und lokale Namen nicht',
  )
})

test('Gegenprobe: der Originalbefund (ModerationCard) wird ERKANNT', () => {
  // Die Zeile, die vor dem Fix in ModerationCard.vue stand (ohne die
  // spätere Korrektur) — als eigene Datei, damit der Test auch dann etwas
  // prüft, wenn die Komponente selbst längst geheilt ist.
  const quelle = `<template>
  <ul>
    <li v-for="ev in item.konflikt_events" :key="ev.id">
      {{ fmtDate(ev.start, ev.all_day) }}
      <button @click.stop="$emit('resolve-conflict', ev)">Auflösen</button>
    </li>
  </ul>
</template>

<script setup>
import { ref } from 'vue'
const item = ref({ konflikt_events: [] })
</script>
`
  const { fehlend } = pruefeQuelle(quelle, 'befund.vue', sfc, babel)
  assert.deepEqual(fehlend.map((f) => f.name), ['fmtDate'])
})

test('Gegenprobe: die reparierte Moderationskarte ist sauber und nutzt den Helfer', () => {
  const datei = QUELLEN + '/diakonos/components/kronos/ModerationCard.vue'
  const quelle = readUtf8(datei)
  const { fehlend, fehler } = pruefeQuelle(quelle, datei, sfc, babel)
  assert.equal(fehler, null)
  assert.deepEqual(fehlend, [], 'ModerationCard hat noch ungebundene Namen')
  // Der Konfliktzeile steht die Formatierung aus dem vorhandenen Helfer zur
  // Verfügung — kein zweites, handgeschriebenes Datumsformat.
  assert.match(quelle, /\{\{\s*datumZeitText\(ev\.start, ev\.all_day\)\s*\}\}/)
  assert.match(quelle, /function datumZeitText\(/)
  assert.match(quelle, /import \{ terminZeitText \} from '\.\/moderationskarte\.js'/)
  assert.ok(!/\{\{\s*fmtDate\(/.test(quelle), 'fmtDate ist zurück')
})

test('App.vue bringt keinen Kalender-Dialog mehr mit (Detail liegt in Kalender.vue)', () => {
  // Nur die CODE-Zeilen zaehlen — der Kommentar erklaert den Befund und nennt
  // die Namen absichtlich.
  const app = readUtf8(QUELLEN + '/diakonos/App.vue').replace(/<!--[\s\S]*?-->/g, '')
  assert.ok(!/showAbgelehntView/.test(app), 'showAbgelehntView steht wieder in App.vue')
  assert.ok(!/abgelehnterTermin/.test(app), 'abgelehnterTermin steht wieder in App.vue')
  assert.ok(!/<KronosEventView/.test(app), 'KronosEventView steht wieder in App.vue')
  // Und in der Kalender-Seite ist der Weg vollständig: Seitenleiste meldet
  // den Klick, die Seite laedt den Termin und oeffnet die Detailansicht.
  const kalender = readUtf8(QUELLEN + '/diakonos/pages/Kalender.vue')
  assert.match(kalender, /@ablehnungClick="zeigeAbgelehntenTermin"/)
  assert.match(kalender, /const showAbgelehntView = ref\(false\)/)
  assert.match(kalender, /const abgelehnterTermin = ref\(null\)/)
  assert.match(kalender, /v-model:show="showAbgelehntView"/)
})

test('FIX-7 · Kalenderliste ist auf dem Desktop erreichbar (gemessener Befund)', () => {
  // Im Browser (1366 px) hatte `.kronos-sidebar-inpage` sichtbare Breite 0:
  // `open` kommt nur vom Umschalter, der am Desktop `display: none` ist. Die
  // Seite klappt die Liste deshalb beim Betreten auf und bei einem Klick auf
  // einen abgelehnten Termin erneut (Sicherung).
  const kalender = readUtf8(QUELLEN + '/diakonos/pages/Kalender.vue')
  // UX3i: Am Desktop oeffnet die Liste sich NICHT mehr von selbst — „Meine
  // Kalender“ ist dort ein Popover am Knopf „Kalender“ (Entwurf A4); die
  // Leiste gehoert zum Handy-Betrieb und zu „Hilfe & Infos“. Die Seite
  // schliesst sie beim Betreten ausdruecklich und oeffnet sie weiterhin fuer
  // den eigenen abgelehnten Termin (Sicherung unten).
  // DEV-B6 (Nacharbeit 10.11.): „Desktop“ heißt jetzt die Handy-Lage der App
  // (`useHandyLage()`), nicht mehr die nackte 721-px-Breite — ein 702-px-Laptop
  // mit Maus ist Desktop und die Liste bleibt dort zu (Auswahl im Popover).
  assert.match(kalender, /onMounted\(\(\) => \{ if \(!istHandyLage\.value\) kronosSidebar\.zu\(\) \}\)/,
    'am Desktop bleibt die Liste zu (Auswahl im Popover)')
  assert.match(kalender, /hilfeOeffnen/, '„Hilfe & Infos“ erreicht die Erklaerung der Leiste')
  // UX3i (Review 07.11.): Die eigenen abgelehnten Termine sind am Desktop
  // über das ⋯-Menü erreichbar; die Sicherung über die Leiste ist entfallen
  // (sie öffnete die ausgeblendete Liste als Overlay über dem Raster).
  assert.match(kalender, /abgelehnteListeOeffnen/, '„Abgelehnte Termine“ hängt am ⋯-Menü')
  assert.match(kalender, /get_meine_abgelehnten_termine/, 'dieselbe Abfrage wie in der Leiste')
  assert.match(kalender, /showAbgelehntView\.value = true/, 'die Detailansicht öffnet weiterhin')
})

test('Skript-Bindungen werden an der obersten Ebene gelesen (kein Freibrief)', () => {
  const code = `import { ref } from 'vue'
const aussen = ref(0)
function hilfe() { const innen = 1; return innen }
if (true) { const nurImBlock = 2 }
`
  const namen = sammleSkriptBindings(code, babel)
  assert.ok(namen.has('ref'))
  assert.ok(namen.has('aussen'))
  assert.ok(namen.has('hilfe'))
  assert.ok(!namen.has('innen'), 'lokale Variable gilt faelschlich als Template-Bindung')
  assert.ok(!namen.has('nurImBlock'), 'Blockvariable gilt faelschlich als Template-Bindung')
})

test('freieNamen: Member-Zugriffe und Schluesselwoerter sind keine freien Namen', () => {
  const ok = babel.parseExpression('a.b + c + typeof d + (e?.f || 0)', { plugins: ['jsx'] })
  assert.deepEqual([...freieNamen(ok)].sort(), ['a', 'c', 'e'])
  // `typeof` prueft nur den Typ und ist kein Verweis auf den Namen.
  const typ = babel.parseExpression('typeof zaehler === "number"', { plugins: ['jsx'] })
  assert.deepEqual([...freieNamen(typ)], [])
})

/** Kleiner Helfer: Datei als UTF-8 lesen. */
function readUtf8(pfad) {
  return readFileSync(pfad, 'utf8')
}

// ══════════════════════════════════════════════════════════════════════════
// UX2d3c — Komponenten im Template muessen aufgeloest sein (DkSkelett-Fall)
// ══════════════════════════════════════════════════════════════════════════
test('UX2d3c · jede im Template benutzte Komponente ist importiert/registriert', () => {
  const dateien = vueDateien(QUELLEN)
  assert.ok(dateien.length > 100, `zu wenige .vue gefunden (${dateien.length})`)

  const befunde = pruefeKomponentenBaum(QUELLEN, sfc, babel, true)
  const meldung = befunde
    .map((b) => {
      if (b.fehler) return `${b.datei}: ${b.fehler}`
      return `${b.datei}: ${b.fehlend.map((f) => `${f.name} (Zeile ${f.zeile})`).join(', ')}`
    })
    .join('\n')
  assert.equal(
    befunde.length,
    0,
    'Komponente im Template benutzt, aber im Skript nicht aufgeloest ' +
      '(Vue rendert sie dann still als unbekanntes Element):\n' + meldung,
  )
})

test('UX2d3c · die Ausnahmen fuer Komponenten sind begruendet', () => {
  assert.ok(KOMPONENTEN_ERLAUBT.size > 0, 'Ausnahmen-Liste ist leer')
  for (const [name, grund] of KOMPONENTEN_ERLAUBT) {
    assert.equal(typeof grund, 'string', `${name} ohne Begruendung`)
    assert.ok(grund.trim().length > 5, `${name}: Begruendung zu kurz („${grund}“)`)
  }
  // Der Befund selbst darf keine Ausnahme sein — sonst waere der Waechter blind.
  assert.ok(!KOMPONENTEN_ERLAUBT.has('DkSkelett'), 'DkSkelett darf keine Ausnahme sein')
})

test('UX2d3c · Gegenprobe: fehlender Import wird ERKANNT', () => {
  // Genau der Befund aus LoeschantraegeListe.vue / Ressourcen.vue.
  const quelle = `<template>
  <DkCard title="Liste">
    <DkSkelett v-if="laedt" form="zeilen" :anzahl="3" text="Laden" />
    <DkEmpty v-else title="Nichts da" />
    <DkButton @click="x">Los</DkButton>
  </DkCard>
</template>

<script setup>
import { ref } from 'vue'
import DkCard from '../ui/DkCard.vue'
import DkEmpty from '../ui/DkEmpty.vue'
import DkButton from '../ui/DkButton.vue'
const laedt = ref(true)
function x() {}
</script>
`
  const { fehlend, fehler } = pruefeKomponenten(quelle, 'gegenprobe.vue', sfc, babel)
  assert.equal(fehler, null)
  assert.deepEqual(fehlend.map((f) => f.name), ['DkSkelett'])
})

test('UX2d3c · Gegenprobe: Import, defineAsyncComponent und Selbstbezug gelten als aufgeloest', () => {
  const quelle = `<template>
  <div>
    <DkSkelett />
    <Spaeter />
    <EigeneSache />
    <Teleport to="body"><span>x</span></Teleport>
  </div>
</template>

<script setup>
import { defineAsyncComponent } from 'vue'
import DkSkelett from '../ui/DkSkelett.vue'
const Spaeter = defineAsyncComponent(() => import('./Spaeter.vue'))
</script>
`
  // `EigeneSache` existiert nicht — der Selbstbezug wird ueber den Dateinamen geprueft.
  const befund = pruefeKomponenten(quelle, 'EigeneSache.vue', sfc, babel)
  assert.equal(befund.fehler, null)
  assert.deepEqual(befund.fehlend.map((f) => f.name), [], 'erlaubte Wege wurden nicht erkannt')
})

test('UX2d3c · Gegenprobe: Options-API `components: { … }` zaehlt als Registrierung', () => {
  const quelle = `<template>
  <div><AlteKarte /></div>
</template>

<script>
import AlteKarte from './AlteKarte.vue'
export default { components: { AlteKarte } }
</script>
`
  const befund = pruefeKomponenten(quelle, 'mit-options.vue', sfc, babel)
  assert.deepEqual(befund.fehlend.map((f) => f.name), [])
})
