/**
 * CHAT-N3 — Nachrichten: die Handy-Lage EINMAL statt je Blase (Vue 3).
 *
 * Befund: `ChatBlase.vue` rief `useHandyLage()` selbst auf — bei 200
 * Nachrichten hingen 200 `matchMedia`-Beobachter (plus 200 `resize`-Horcher)
 * am Fenster. Umgesetzt:
 *
 *   A  Nur noch EINE Stelle fragt: `pages/Nachrichten.vue` ruft
 *      `useHandyLage()` genau EINMAL und gibt `istHandyLage` als Prop
 *      `handyLage` an jede Blase; `ChatBlase.vue` importiert das Composable
 *      nicht mehr (und hat keine eigene Lagequelle).
 *   B  Verhalten unverändert, aber am PROP: `handyLage=true` → „＋“ + „⋯“
 *      (kein Einzelknopf), `handyLage=false` → die Aktionszeile mit den
 *      Symbolknöpfen. Gleiches Menü wie vorher (`DkAktionen`), gleiche
 *      Ereignisse.
 *   C  Auf der gemounteten SEITE (Handy-Lage über `matchMedia`) steht das
 *      Menü an jeder Nachricht, am Desktop nur die Knöpfe.
 *   D  Die Prop ist REAKTIV: schaltet die Seite die Lage um (Handy ↔
 *      Desktop), rendert die Blase um („⋯“-Menü ↔ Aktionszeile).
 *
 * Lauf (eine Datei je Aufruf, TZ=Europe/Berlin):
 *   TMPDIR=$(mktemp -d) TZ=Europe/Berlin node --test tests/chatn3-handylage-prop.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync, mkdtempSync, writeFileSync, rmSync, mkdirSync, statSync } from 'node:fs'
import { join, dirname, resolve, basename } from 'node:path'
import { tmpdir } from 'node:os'
import { pathToFileURL } from 'node:url'
import test from 'node:test'
import { SeitenAbbau } from './helpers/seitenAbbau.mjs'
import { JSDOM } from 'jsdom'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'

// ── Browser-Attrappe ───────────────────────────────────────────────────────
const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
for (const schluessel of ['window', 'document', 'Node', 'Element', 'HTMLElement', 'Event',
  'MouseEvent', 'SVGElement', 'CSS', 'CustomEvent', 'FormData', 'HTMLInputElement',
  'HTMLSelectElement', 'HTMLTextAreaElement', 'requestAnimationFrame', 'getComputedStyle',
  'MutationObserver', 'KeyboardEvent', 'FocusEvent', 'Document', 'ShadowRoot',
  'HTMLAnchorElement', 'HTMLButtonElement', 'HTMLDivElement', 'localStorage',
  'sessionStorage', 'location']) {
  globalThis[schluessel] = dom.window[schluessel]
}
globalThis.requestAnimationFrame = dom.window.requestAnimationFrame
  || ((fn) => setTimeout(() => fn(Date.now()), 0))
Object.defineProperty(dom.window.document, 'hidden', { configurable: true, get: () => false })
Object.defineProperty(dom.window.document, 'visibilityState', { configurable: true, get: () => 'visible' })

const VUE_URL = import.meta.resolve('vue')
const SRC_ROOT = new URL('../src/', import.meta.url)
const SRC = new URL('../src/diakonos/', import.meta.url)

const TMP = mkdtempSync(join(tmpdir(), 'chatn3-'))
test.after(() => rmSync(TMP, { recursive: true, force: true }))

// ── SFC → ES-Modul ─────────────────────────────────────────────────────────
const cache = new Map()
const umleitung = new Map()

function aufgeloest(abs) {
  for (const k of [abs, abs + '.mjs', abs + '.js', abs + '/index.mjs']) {
    try { if (statSync(k).isFile()) return k } catch { /* weiter */ }
  }
  throw new Error('nicht gefunden: ' + abs)
}

function baum(seite, { frisch = false, ordner = null } = {}) {
  const unterordner = ordner || join(TMP, 'baum-' + Math.random().toString(36).slice(2))
  const NEU = frisch ? new Map() : cache
  const zielFuer = (quellDatei) => {
    const relativ = resolve(quellDatei).slice(resolve(SRC_ROOT.pathname, '../').length)
    const ziel = join(unterordner, relativ.replace(/[\\/]/g, '_') + '.mjs')
    mkdirSync(dirname(ziel), { recursive: true })
    return ziel
  }
  const uebersetzen = (abs) => {
    if (NEU.has(abs)) return NEU.get(abs)
    const quellDatei = aufgeloest(abs)
    const quanten = []
    if (quellDatei.endsWith('.vue')) {
      const filename = basename(quellDatei)
      const { descriptor, errors } = parse(readFileSync(quellDatei, 'utf8'), { filename })
      assert.deepEqual(errors, [], filename + ': SFC-Struktur')
      const script = compileScript(descriptor, { id: filename })
      const tpl = compileTemplate({
        source: descriptor.template.content, filename, id: filename,
        compilerOptions: { bindingMetadata: script.bindings },
      })
      assert.deepEqual(tpl.errors.map(String), [], filename + ': Vorlage')
      let code = script.content.replace(/\nexport default /, '\nconst __sfc__ = ')
      code += '\n' + tpl.code.replace(/^export function render/m, 'function render')
      code += '\n__sfc__.render = render\nexport default __sfc__\n'
      code = code.replace(/defineAsyncComponent\(\(\) => import\([^)]*\)\)/g,
        'defineAsyncComponent(() => Promise.resolve({ render: () => null }))')
      quanten.push(code)
    } else {
      quanten.push(readFileSync(quellDatei, 'utf8'))
    }
    const code = quanten.join('\n').replace(
      /from\s+['"]([^'"]+)['"]/g,
      (ganz, spec) => {
        if (spec === 'vue') return `from '${VUE_URL}'`
        if (spec.startsWith('.')) {
          const zielAbs = aufgeloest(resolve(dirname(quellDatei), spec))
          const url = pathToFileURL(zielAbs).href
          if (umleitung.has(url)) return `from '${umleitung.get(url)}'`
          return `from '${pathToFileURL(uebersetzen(zielAbs)).href}'`
        }
        if (spec.startsWith('node:')) return ganz
        return `from '${spec}'`
      },
    )
    const ziel = zielFuer(quellDatei)
    writeFileSync(ziel, code)
    NEU.set(abs, ziel)
    return ziel
  }
  return uebersetzen(new URL(seite, SRC).pathname)
}

const tick = () => new Promise((loese) => setTimeout(loese, 0))
const warte = async (n = 8) => { for (let i = 0; i < n; i += 1) await tick() }

/**
 * FE-ABBAU: JEDE Montage meldet ihren Abbau hier an, und `afterEach` baut
 * alles ab, was noch steht — auch nach einem ROTEN `assert`. Vorher stand
 * `s.abbaum()` als letzte Zeile im Test: eine geworfene Zusage ließ die Seite
 * stehen, ihr Takt (10 s, plant sich neu) hielt die Ereignisschleife offen und
 * der FE-Teststep im Build hing (FE-HAENGER, 4ce2d6b2).
 */
const seitenAbbau = new SeitenAbbau()
test.afterEach(() => seitenAbbau.alle())

async function mounten(baustein, props = {}, { ereignisse = [] } = {}) {
  const Vue = await import('vue')
  const host = document.createElement('div')
  document.body.appendChild(host)
  const warnungen = []
  const merker = {}
  for (const name of ereignisse) merker[name] = []
  const app = Vue.createApp({
    components: { Seite: baustein },
    data: () => ({ p: props }),
    methods: Object.fromEntries(ereignisse.map((n) => [n, function (wert) { merker[n].push(wert) }])),
    template: `<Seite v-bind="p" ${ereignisse.map((n) => `@${n}="${n}"`).join(' ')} />`,
  })
  app.config.warnHandler = (m) => warnungen.push(m)
  app.config.errorHandler = (e) => warnungen.push(String(e && e.message))
  const vm = app.mount(host)
  await warte(12)
  const abbaum = seitenAbbau.anmelden(() => {
    try { app.unmount() } catch { /* egal */ }
    try { host.remove() } catch { /* egal */ }
  })
  return { host, app, warnungen, vm, abbaum, merker }
}

/**
 * Ein Klick, wie ihn jsdom versteht.
 */
function klick(el) {
  assert.ok(el, 'das Zielelement steht im DOM')
  el.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }))
}

/**
 * Handy-Lage: `matchMedia` beantwortet die EINE Abfrage der App
 * (`HANDY_LAGE_ABFRAGE`, GROBER Zeiger + schmal bzw. flach-quer). Der Zähler
 * merkt sich, wie oft NACH DER ABFRAGE gefragt wurde — CHAT-N3 will genau
 * EINE Quelle.
 */
const abfragen = { handy: false, rufe: [] }
function handyAbfrage(handy) {
  abfragen.handy = handy
  abfragen.rufe = []
  dom.window.matchMedia = (abfrage) => {
    abfragen.rufe.push(String(abfrage))
    return {
      media: String(abfrage),
      matches: handy === true && /pointer:\s*coarse/.test(String(abfrage)),
      addEventListener: () => {}, removeEventListener: () => {},
      addListener: () => {}, removeListener: () => {},
    }
  }
}

// ── Proben ─────────────────────────────────────────────────────────────────

/** Eine Nachricht, wie `_zeile` sie liefert (nur die hier zählenden Felder). */
function zeile(name, text, { am = '2026-11-18 10:00:00', eigene = false, autor = 'Anna Beispiel', ...rest } = {}) {
  return {
    name, ident: name, id: name, text, eigene, autor, erstellt_am: am, zeit: '10:00',
    bearbeitet: false, geloescht: false, geloescht_grund: null, reaktionen: [],
    antwort_auf: null, antwort_auf_text: null, gelesen_von: eigene ? 0 : null, ...rest,
  }
}

const GESPRAECHE = [{ name: 'CHAT-1', art: 'gruppe', gruppe: 'chor', untergruppe: null,
  titel: 'Chor', geoeffnet: true, ungelesen: 0, teilnehmer: 24,
  letzte_nachricht: 'Guten Morgen', letzte_am: '2026-11-18 10:01:00', stumm: false }]

async function blaseMontieren(nachricht, props = {}) {
  const mod = (await import(pathToFileURL(baum('components/chat/ChatBlase.vue', { frisch: true })).href)).default
  return mounten(mod, { nachricht, ...props }, { ereignisse: ['reaktion', 'antworten', 'bearbeiten', 'loeschen'] })
}

/** Die Seite mounten: Netz und Sitzung als Attrappe, Handy-Lage via `matchMedia`. */
async function seiteMontieren({ handy = false, nachrichten = null } = {}) {
  const ordner = join(TMP, 'seite-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  const api = join(ordner, 'api.mjs')
  writeFileSync(api, [
    'export async function apiCall(methode, parameter) {',
    '  return globalThis.__L_SERVER({ methode, parameter })',
    '}',
    'export const apiGet = apiCall',
    "export const apiUrl = (p) => 'https://pruefstand.invalid/' + p",
    'export class AuditConfirmationRequired extends Error {}',
    'export const pruefeSitzungsAntwort = () => false',
    'export const apiAntwortPruefen = async () => ({ message: {} })',
  ].join('\n'))
  const session = join(ordner, 'session.mjs')
  writeFileSync(session, [
    `import { ref } from '${VUE_URL}'`,
    'export function useSession() {',
    "  return { istTester: ref(false), devmodeAn: ref(false), mitglied: ref({ name: 'M-1' }),",
    "    istAdmin: ref(false), istGast: ref(false), fullName: ref(''),",
    "    rollen: ref([]), abmelden: async () => {}, sitzungPruefen: async () => {} }",
    '}',
  ].join('\n'))

  const zeilen = nachrichten || [
    zeile('N-1', 'Guten Morgen', { am: '2026-11-18 10:00:00', autor: 'Anna Beispiel' }),
    zeile('N-2', 'Hallo Anna', { am: '2026-11-18 10:01:00', eigene: true }),
  ]
  globalThis.__L_SERVER = ({ methode }) => {
    const kurz = String(methode).split('.').pop()
    if (kurz === 'meine_gespraeche') return { gespraeche: GESPRAECHE.map((g) => ({ ...g })) }
    if (kurz === 'verlauf') return { gespraech: 'CHAT-1', richtung: 'neueste',
      nachrichten: zeilen.map((n) => ({ ...n })) }
    if (kurz === 'lesestand_setzen') return { ungelesen: 0 }
    return {}
  }
  dom.window.__DIakonosBOOT = { roles: ['Mitglied'], is_admin: false, module_sichtbar: ['chat'] }
  dom.window.location.hash = '#/nachrichten/CHAT-1'

  handyAbfrage(handy)

  const U = (rel) => pathToFileURL(SRC.pathname + rel).href
  umleitung.clear()
  umleitung.set(U('composables/useApi.js'), pathToFileURL(api).href)
  umleitung.set(U('composables/useSession.js'), pathToFileURL(session).href)

  const mod = await import(pathToFileURL(baum('pages/Nachrichten.vue', { frisch: true, ordner })).href)
  const { host, app, warnungen, vm, abbaum } = await mounten(mod.default, {})
  await warte(14)
  void app; void vm
  return { host, warnungen, abbaum }
}

const LANGE = (rels, datei) => readFileSync(new URL(rels, SRC), 'utf8')
/** Der Skriptteil einer SFC (ab `<script`). */
const SKRIPT = (rels) => {
  const ganz = LANGE(rels, rels)
  return ganz.slice(ganz.indexOf('<script'))
}

/**
 * Der Skriptteil OHNE Kommentare. Die Kommentare NENNEN bzw. BELEGEN den
 * Umbau (`useHandyLage()`, `matchMedia`) — sie sind kein Aufruf. Geprüft wird
 * nur ausführbarer Code: Blockkommentare und ganze `//`-Zeilen fallen weg,
 * `//` mitten in einer Zeile (z. B. in einer Adresse) bleibt stehen.
 */
const CODE = (rels) => SKRIPT(rels)
  .replace(/\/\*[\s\S]*?\*\//g, '')
  .split('\n')
  .filter((z) => !/^\s*\/\//.test(z))
  .join('\n')

// ══ A · EINE Quelle: die Seite fragt, die Blase nicht ═════════════════════

test('CHAT-N3/A: ChatBlase importiert `useHandyLage` NICHT mehr — die Lage ist eine Prop', () => {
  const skript = CODE('components/chat/ChatBlase.vue')
  assert.doesNotMatch(skript, /useHandyLage/, 'kein Import und kein Aufruf des Composables in der Blase')
  assert.doesNotMatch(skript, /handyLage\.mjs/, 'auch kein Import der Datei')
  // Die Prop steht mit Boolean-Typ und Standard false (Desktop).
  assert.match(skript, /handyLage:\s*\{\s*type:\s*Boolean,\s*default:\s*false\s*\}/,
    'Prop `handyLage` (Boolean, default false)')
  // Und die Blase hängt keine eigenen Fenster-Horcher mehr auf.
  assert.doesNotMatch(skript, /matchMedia/, 'kein eigenes matchMedia in der Blase')
  assert.doesNotMatch(skript, /addEventListener\(\s*'resize'/, 'kein eigener resize-Horcher in der Blase')
})

test('CHAT-N3/A: Nachrichten.vue fragt `useHandyLage()` genau EINMAL und reicht die Lage an die Blase', () => {
  const skript = CODE('pages/Nachrichten.vue')
  const importe = [...skript.matchAll(/import\s*\{[^}]*useHandyLage[^}]*\}\s*from/g)]
  assert.equal(importe.length, 1, 'genau ein Import von useHandyLage')
  const aufrufe = [...skript.matchAll(/useHandyLage\s*\(/g)]
  assert.equal(aufrufe.length, 1, 'genau EIN Aufruf: ' + aufrufe.length)
  assert.match(skript, /const\s*\{\s*istHandyLage\s*\}\s*=\s*useHandyLage\(\)/, 'die Seite hält `istHandyLage`')

  // Die Blase bekommt die Lage — im Skript der Seite (Vorlage + Skript der SFC).
  const ganz = LANGE('pages/Nachrichten.vue')
  const blaseTag = /<ChatBlase[\s\S]*?>/g
  const treffer = [...ganz.matchAll(blaseTag)]
  assert.equal(treffer.length, 1, 'die Seite bindet ChatBlase an genau EINER Stelle ein')
  assert.match(treffer[0][0], /:handy-lage="istHandyLage"/, 'die Blase bekommt `handyLage` aus der Seite')
})

test('CHAT-N3/A: die Blase bekommt KEINE Lage mehr aus dem Fenster — der Prop-Wert entscheidet', async () => {
  // `matchMedia` behauptet „Handy" — ohne Prop bleibt die Blase am Desktop,
  // mit `handyLage: true` ist sie am Handy: der Prop allein entscheidet.
  handyAbfrage(true)
  const ohne = await blaseMontieren(zeile('N-1', 'Guten Morgen'), { bearbeitbar: false })
  await warte(6)
  assert.ok([...ohne.host.querySelectorAll('button')].some((b) => b.getAttribute('aria-label') === 'Antworten'),
    'ohne Prop: die Antworten stehen als Einzelknopf (Desktop)')
  assert.equal(ohne.host.querySelector('.dk-ui-aktionen-ausloeser'), null, 'ohne Prop kein „⋯“')
  ohne.abbaum()

  handyAbfrage(false)
  const mit = await blaseMontieren(zeile('N-1', 'Guten Morgen'), { bearbeitbar: false, handyLage: true })
  await warte(6)
  assert.ok(mit.host.querySelector('.dk-ui-aktionen-ausloeser'),
    'mit handyLage=true steht das „⋯“ da, obwohl das Fenster Desktop meldet')
  mit.abbaum()
})

// ══ B · Verhalten unverändert — nur am Prop ════════════════════════════════

test('CHAT-N3/B: handyLage=true → „＋“ und „⋯“ (keine Einzelknöpfe), Ereignisse unverändert', async () => {
  const s = await blaseMontieren(
    zeile('N-2', 'Hallo Anna', { eigene: true, bearbeitbar: true, am: new Date().toISOString() }),
    { bearbeitbar: true, handyLage: true },
  )
  await warte(6)
  const aktionen = s.host.querySelector('.dk-chat-aktionen')
  const namen = [...aktionen.querySelectorAll('button')].map((b) => b.getAttribute('aria-label'))
  assert.equal(namen.length, 2, 'nur zwei Knöpfe am Handy: ' + namen.join(', '))
  assert.ok(namen.includes('Reaktion setzen'), 'das „＋“ bleibt eigener Knopf')
  assert.ok(namen.some((n) => /^Aktionen für die Nachricht/.test(String(n))), 'und das „⋯“-Menü')
  assert.equal(aktionen.querySelector('.dk-ui-aktionen-ausloeser').getAttribute('aria-haspopup'), 'menu')

  klick(s.host.querySelector('.dk-ui-aktionen-ausloeser'))
  await warte(6)
  const eintraege = [...document.querySelectorAll('.dk-ui-aktionen-eintrag')]
  assert.deepEqual(eintraege.map((e) => e.textContent.trim()), ['Antworten', 'Bearbeiten', 'Löschen'],
    'dieselben erlaubten Aktionen im Menü')
  klick(eintraege[0])
  await warte(6)
  assert.equal(s.merker.antworten.length, 1, 'der Eintrag meldet `antworten`')
  assert.equal(s.merker.antworten[0].ident, 'N-2', 'mit der Nachricht der Blase')
  s.abbaum()
})

test('CHAT-N3/B: handyLage=false → die Aktionszeile mit Symbolknöpfen, kein Menü', async () => {
  const s = await blaseMontieren(
    zeile('N-2', 'Hallo Anna', { eigene: true, bearbeitbar: true, am: new Date().toISOString() }),
    { bearbeitbar: true, handyLage: false },
  )
  await warte(6)
  const aktionen = s.host.querySelector('.dk-chat-aktionen')
  const namen = [...aktionen.querySelectorAll('button')].map((b) => b.getAttribute('aria-label'))
  for (const erwartet of ['Reaktion setzen', 'Antworten', 'Bearbeiten', 'Löschen']) {
    assert.ok(namen.includes(erwartet), `am Desktop steht „${erwartet}“ als eigener Knopf: ` + namen.join(', '))
  }
  assert.equal(aktionen.querySelector('.dk-ui-aktionen-ausloeser'), null, 'kein „⋯“ am Desktop')
  klick([...aktionen.querySelectorAll('button')].find((b) => b.getAttribute('aria-label') === 'Löschen'))
  await warte(4)
  assert.equal(s.merker.loeschen.length, 1, 'der Knopf meldet `loeschen`')
  s.abbaum()
})

// ══ C · Auf der Seite: eine Abfrage, Menü an JEDER Nachricht ═══════════════

test('CHAT-N3/C: am Handy steht das Menü an jeder Nachricht — und die Seite fragt EINMAL', async () => {
  const s = await seiteMontieren({ handy: true })
  const blasen = [...s.host.querySelectorAll('.dk-chat-beitrag')]
  assert.ok(blasen.length >= 2, 'der Verlauf hat Nachrichten')
  for (const b of blasen) {
    assert.ok(b.querySelector('.dk-ui-aktionen-ausloeser'), 'jede Blase trägt das „⋯“ am Handy')
    assert.equal([...b.querySelectorAll('.dk-chat-aktionen button')]
      .some((k) => k.getAttribute('aria-label') === 'Antworten'), false,
    'und keine Einzelknöpfe daneben')
  }
  // Die eine Abfrage der Seite (matchMedia fragt `useHandyLage()` beim Aufbau
  // zweimal: Wert lesen + Beobachter) — NICHT je Blase. Vor dem Umbau wären
  // es mindestens 2 + 2 × Nachrichten.
  const rufe = abfragen.rufe.filter((a) => /pointer:\s*coarse/.test(a))
  assert.ok(rufe.length <= 4,
    `die Handy-Abfrage läuft einmal für die Seite, nicht je Blase (${rufe.length} Aufrufe bei ${blasen.length} Blasen)`)
  s.abbaum()
})

test('CHAT-N3/C: am Desktop bleiben die Symbolknöpfe an jeder Nachricht', async () => {
  const s = await seiteMontieren({ handy: false })
  const blasen = [...s.host.querySelectorAll('.dk-chat-beitrag')]
  assert.ok(blasen.length >= 2)
  for (const b of blasen) {
    assert.equal(b.querySelector('.dk-ui-aktionen-ausloeser'), null, 'kein „⋯“ am Desktop')
    assert.ok([...b.querySelectorAll('button')].some((k) => k.getAttribute('aria-label') === 'Antworten'),
      'die Aktionszeile steht da')
  }
  s.abbaum()
})

// ══ D · Reaktiv: Umschalten der Prop rendert um ═══════════════════════════

test('CHAT-N3/D: die Prop ist reaktiv — handyLage true→false schaltet „⋯“-Menü ↔ Aktionszeile', async () => {
  const mod = (await import(pathToFileURL(baum('components/chat/ChatBlase.vue', { frisch: true })).href)).default
  // Die Lage kommt von der Seite und kann sich ändern (Drehen des Geräts):
  // ein reaktiver Wrapper schaltet die Blase um — Renderfunktion statt
  // Zeichenkette, damit der Laufzeit-Compiler hier nichts zu tun hat.
  const Vue = await import('vue')
  const handy = Vue.ref(true)
  const nachricht = zeile('N-2', 'Hallo Anna', { eigene: true, bearbeitbar: true, am: new Date().toISOString() })
  const host = document.createElement('div')
  document.body.appendChild(host)
  const warnungen = []
  // Einmal eingehaengt und dauerhaft am Baum: Vue muss beim Umschalten
  // bestehende Kinder ersetzen (genau der Weg, der vorher je Blase fehlte).
  const app = Vue.createApp({
    render: () => Vue.h('div', [
      Vue.h('div', { class: 'platzhalter' }),
      Vue.h(mod, { nachricht, bearbeitbar: true, handyLage: handy.value }),
    ]),
  })
  app.config.warnHandler = (m) => warnungen.push(m)
  app.config.errorHandler = (e) => warnungen.push(String(e && e.message))
  app.mount(host)
  await warte(10)

  const aktionen = () => host.querySelector('.dk-chat-aktionen')
  const labels = () => [...aktionen().querySelectorAll('button')].map((b) => b.getAttribute('aria-label'))

  // Start: Handy — Menü, keine Einzelknöpfe.
  assert.ok(aktionen(), 'die Blase ist gerendert')
  assert.ok(aktionen().querySelector('.dk-ui-aktionen-ausloeser'), 'handyLage=true: das „⋯“ steht da — ' + labels().join(', '))

  // Umschalten: Desktop — die Aktionszeile steht da, kein Menü-Auslöser.
  handy.value = false
  await warte(10)
  assert.equal(aktionen().querySelector('.dk-ui-aktionen-ausloeser'), null,
    'handyLage=false: das „⋯“ ist weg')
  for (const erwartet of ['Reaktion setzen', 'Antworten', 'Bearbeiten', 'Löschen']) {
    assert.ok(labels().includes(erwartet), `und „${erwartet}“ steht als Einzelknopf: ` + labels().join(', '))
  }

  // Und zurück: Handy — das Menü kommt wieder, die Einzelknöpfe gehen.
  handy.value = true
  await warte(10)
  assert.ok(aktionen().querySelector('.dk-ui-aktionen-ausloeser'), 'zurück auf Handy: das „⋯“ ist wieder da')
  assert.equal(labels().some((n) => n === 'Antworten'), false,
    'die Einzelknöpfe sind wieder im Menü: ' + labels().join(', '))
  assert.equal(warnungen.length, 0, 'keine Warnung: ' + warnungen.join(' | '))

  try { app.unmount() } catch { /* egal */ }
  try { host.remove() } catch { /* egal */ }
})
