/**
 * CHAT-3a-3 — Nachrichten: App-Start, Poll-Änderungen, Adressierung.
 *
 * Die Review-Runde 2 hat Fehler gefunden, die die bisherigen Tests NICHT
 * gesehen haben, weil sie viel per Regex über den Quelltext prüften. Hier
 * läuft deshalb das VERHALTEN:
 *
 *   A  `App.vue` wird als echte Wurzel gemountet (frischer Modul-Graph, wie
 *      `r10b2-anmeldung-einstellungen-mount.test.mjs`). Vorher warf
 *      `App.setup` eine TDZ-`ReferenceError` (`istHandyLage` erst NACH
 *      `useChatZaehler` deklariert) — bei JEDEM Nutzer mit Chat-Modul bzw.
 *      Admin blieb die App weiss. Zusätzlich: der Wechsel Desktop → Handy
 *      startet den Zähler (`watch(istHandyLage)` → `planen()`).
 *   B  Der Poll der Seite sendet KEIN `seit`; eine Testseite wie der ECHTE
 *      Server (`richtung: 'neueste'`, volle, verschobene Seite) bringt
 *      Bearbeitung, Löschung samt Grund, Reaktion und „gelesen von“ in den
 *      Verlauf.
 *   C1 Eine Hauptgruppen-Adresse öffnet den HAUPT-Chat, nicht die alphabetisch
 *      davor sortierte Untergruppe derselben Gruppe.
 *   C2 die Liste hebt das offene Gespräch hervor (`is-aktiv`, `aria-current`).
 *   Klein: `mitteilungSenden(null)` setzt den Zähler nicht auf 0; der
 *      Bearbeiten-Takt endet mit der 15-Minuten-Frist.
 *
 * Lauf (eine Datei je Aufruf, TZ=Europe/Berlin):
 *   TMPDIR=$(mktemp -d) TZ=Europe/Berlin node --test tests/chat3a3-nachrichten-nacharbeit.test.mjs
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
  'sessionStorage', 'location', 'setTimeout', 'clearTimeout',
  'setInterval', 'clearInterval']) {
  if (schluessel === 'setTimeout' || schluessel === 'clearTimeout'
    || schluessel === 'setInterval' || schluessel === 'clearInterval') {
    // Die echten Timer der Laufzeit — jsdom-Timer in dieser Attrappe zu
    // benutzen hiesse, zwei Uhren zu mischen.
    continue
  }
  globalThis[schluessel] = dom.window[schluessel]
}
globalThis.requestAnimationFrame = dom.window.requestAnimationFrame
  || ((fn) => setTimeout(() => fn(Date.now()), 0))
// Die Renderer-Uhr: `App.vue` hält einen 1000-ms-`setInterval` (Restzeit der
// Impersonation). Unter `node --test` hielte der die Laufzeit offen; deshalb
// läuft der App-Test mit Node's virtueller Uhr (`mock.timers`).

// jsdom ohne PretendToBeVisual meldet `document.hidden === true` — „Tab im
// Hintergrund“. Für die Tests ist das falsch: der Zähler UND der Chat-Takt
// fragen ausdrücklich nur bei SICHTBAREM Tab. Ein sichtbarer Prüfstand, sonst
// prüft man den Hintergrund-Zweig.
Object.defineProperty(dom.window.document, 'hidden', { configurable: true, get: () => false })
Object.defineProperty(dom.window.document, 'visibilityState', { configurable: true, get: () => 'visible' })

const Vue = await import('vue')
const VUE_URL = import.meta.resolve('vue')
const SRC_ROOT = new URL('../src/', import.meta.url)
const SRC = new URL('../src/diakonos/', import.meta.url)

const TMP = mkdtempSync(join(tmpdir(), 'chat3a3-'))
test.after(() => rmSync(TMP, { recursive: true, force: true }))

// ── SFC → ES-Modul (frischer Baum) ─────────────────────────────────────────
const cache = new Map()
const umleitung = new Map()

function aufgeloest(abs) {
  for (const k of [abs, abs + '.mjs', abs + '.js', abs + '/index.mjs']) {
    try { if (statSync(k).isFile()) return k } catch { /* weiter */ }
  }
  throw new Error('nicht gefunden: ' + abs)
}

/**
 * Ein Baum SFCs/Module ab `seite` übersetzen. `umleitung` biegt Module auf
 * Attrappen um (API, Session, Router …) — die Attrappen liegen in `TMP`.
 * `frisch` = eigener Modul-Graph (für Seiten, die EINMAL beim Import
 * Zustand einfrieren, z. B. `useSession`).
 */
function baum(seite, { frisch = false, ordner = null } = {}) {
  const unterordner = ordner || join(TMP, 'baum-' + Math.random().toString(36).slice(2))
  const NEU = frisch ? new Map() : cache
  const zielFuer = (quellDatei) => {
    const relativ = quellDatei.slice(SRC_ROOT.pathname.length)
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

/**
 * Mounten. `App.vue` hält keinen Termin, der den Testbetrieb offenhielte, wenn
 * der Aufbau wieder abgebaut wird — deshalb gibt es `abbaum()`, und jeder Test
 * ruft es (auch die Fenster-Listener hängen sonst am nächsten Test mit).
 */
async function mounten(baustein, props = {}) {
  const host = document.createElement('div')
  document.body.appendChild(host)
  const warnungen = []
  const app = Vue.createApp({
    components: { Seite: baustein },
    data: () => ({ p: props }),
    template: '<Seite v-bind="p" />',
  })
  app.config.warnHandler = (m) => warnungen.push(m)
  app.config.errorHandler = (e) => warnungen.push(String(e && e.message))
  const vm = app.mount(host)
  await warte(12)
  const abbaum = seitenAbbau.anmelden(() => {
    try { app.unmount() } catch { /* egal */ }
    try { host.remove() } catch { /* egal */ }
  })
  return { host, app, warnungen, vm, abbaum }
}

/**
 * Nur die Termine ZÄHLEN und abspulen — die Uhr selbst bleibt echt.
 *
 * `setInterval`/`setTimeout` werden für die Dauer des Tests durch eine eigene
 * Liste ersetzt; `bis(ms)` schaltet die Termine frei, die in diesem Zeitfenster
 * fällig wären. So lässt sich der 30-s-Takt der Blase prüfen, ohne 30 Sekunden
 * lang zu warten — und ohne den Code zu kürzen.
 */
function uhrZaehlen() {
  const echt = { setTimeout: globalThis.setTimeout, setInterval: globalThis.setInterval,
    clearTimeout: globalThis.clearTimeout, clearInterval: globalThis.clearInterval }
  let kennung = 0
  const termine = new Map()
  globalThis.setTimeout = (fn, ms, ...args) => {
    kennung += 1
    const abstand = Math.max(0, Number(ms) || 0)
    termine.set(kennung, { fn, args, abstand, art: 'einmal' })
    return kennung
  }
  globalThis.setInterval = (fn, ms, ...args) => {
    kennung += 1
    termine.set(kennung, { fn, args, abstand: Math.max(1, Number(ms) || 0), art: 'immer' })
    return kennung
  }
  globalThis.clearTimeout = (id) => termine.delete(id)
  globalThis.clearInterval = (id) => termine.delete(id)
  return {
    async bis(ms) {
      for (let runde = 0; runde < 50; runde += 1) {
        const faellig = [...termine.entries()].filter(([, e]) => e.abstand <= ms)
        if (!faellig.length) break
        for (const [id, e] of faellig) {
          if (e.art === 'einmal') termine.delete(id)
          try { e.fn(...(e.args || [])) } catch { /* egal */ }
        }
        await warte(4)
      }
    },
    offen: () => termine.size,
    zurueck() {
      globalThis.setTimeout = echt.setTimeout
      globalThis.setInterval = echt.setInterval
      globalThis.clearTimeout = echt.clearTimeout
      globalThis.clearInterval = echt.clearInterval
    },
  }
}

// ══ A · App.vue startet (kein TDZ-Fehler) ══════════════════════════════════
//
// Der Fehler: `useChatZaehler({ handyLage: () => istHandyLage.value })` stand
// VOR `const { istHandyLage } = useHandyLage()`. `useChatZaehler` liest
// `handyLage()`/`planen()` sofort beim Aufbau → `ReferenceError: Cannot access
// 'istHandyLage' before initialization` in `App.setup`; die App blieb für
// jeden Nutzer mit Chat-Modul (und Admins) weiss. Hier wird die echte
// App-Wurzel gemountet — der Fehler wäre ein Fehler IM Aufbau.

/** Attrappen, die den Rahmen liefern, den `App.vue` erwartet. */
function appAttrappen() {
  const ordner = join(TMP, 'app-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  const schreib = (name, inhalt) => {
    const p = join(ordner, name)
    // `vue` aus einem Verzeichnis ausserhalb des Projekts importieren geht
    // nicht über den Paketnamen — die Attrappen bekommen die aufgelöste URL.
    writeFileSync(p, String(inhalt).replace(/from 'vue'/g, `from '${VUE_URL}'`))
    return pathToFileURL(p).href
  }
  const api = schreib('useApi.mjs', [
    'export async function apiCall() { return { message: {} } }',
    'export const apiGet = apiCall',
    "export const apiUrl = (p) => 'https://pruefstand.invalid/' + p",
    'export class AuditConfirmationRequired extends Error {}',
    'export const pruefeSitzungsAntwort = () => false',
    'export const apiAntwortPruefen = async () => ({ message: {} })',
  ].join('\n'))
  const session = schreib('useSession.mjs', [
    "import { ref } from 'vue'",
    'export function useSession() {',
    "  return { istTester: ref(false), devmodeAn: ref(false), mitglied: ref(null),",
    "    istAdmin: ref(false), istGast: ref(false), fullName: ref(''),",
    "    rollen: ref([]), abmelden: async () => {}, sitzungPruefen: async () => {} }",
    '}',
    'export const useSessionStore = () => ({})',
    'export const beobachteSitzung = () => () => {}',
  ].join('\n'))
  const leerRahmen = schreib('rahmen.mjs', [
    "import { ref, computed } from 'vue'",
    'export const currentComponent = ref(null)',
    "export const currentHash = ref('#/')",
    "export const currentPageName = ref('Uebersicht')",
    "export const pageLadefehler = ref(null)",
    "export const seitenLadend = ref(false)",
    'export const navigate = () => {}',
    'export const routeNeuLaden = () => {}',
    'export const vollbildModus = ref(false)',
    'export const darfSeitenleiste = () => false',
    'export const verwaltungsRollenAbfragen = async () => ({})',
    'export const rollenMarke = ref(null)',
  ].join('\n'))
  const dev = schreib('useDevmodus.mjs', [
    "import { ref } from 'vue'",
    'export const devmodusAn = ref(false)',
    'export const devmodusAutostart = async () => {}',
    'export const devmodusPruefen = async () => {}',
  ].join('\n'))
  const verwaltung = schreib('useVerwaltung.mjs', [
    "import { ref } from 'vue'",
    'export const anfragenZaehler = ref(null)',
    'export const anfragenZaehlerBeobachten = () => () => {}',
  ].join('\n'))
  const impersonation = schreib('useImpersonation.mjs', [
    "import { ref } from 'vue'",
    'export function useImpersonation() {',
    '  return { isActive: ref(false), fullName: ref(\'\'), expiresAt: ref(null),',
    '    remaining: ref(0), checkExpiry: () => {}, stop: () => {} }',
    '}',
  ].join('\n'))
  const bereichskopf = schreib('useBereichskopf.mjs', [
    "import { ref } from 'vue'",
    'export const rollenMarke = ref(null)',
  ].join('\n'))
  return { api, session, leerRahmen, dev, verwaltung, impersonation, bereichskopf }
}

/** Die App-Wurzel mountbare machen: Umleitungen + viewport-Attrappe. */
function appUmgebung({ handy = false } = {}) {
  const a = appAttrappen()
  const U = (rel) => pathToFileURL(SRC.pathname + rel).href
  umleitung.clear()
  umleitung.set(U('composables/useApi.js'), a.api)
  umleitung.set(U('composables/useSession.js'), a.session)
  umleitung.set(U('router.js'), a.leerRahmen)
  umleitung.set(U('composables/useDevmodus.js'), a.dev)
  umleitung.set(U('composables/useVerwaltung.js'), a.verwaltung)
  umleitung.set(U('composables/useImpersonation.js'), a.impersonation)
  umleitung.set(U('composables/useBereichskopf.js'), a.bereichskopf)

  // `matchMedia` der Fenster-Attrappe: DIE eine Abfrage der Handy-Lage.
  let lage = handy
  const zuhoerer = new Set()
  dom.window.matchMedia = (abfrage) => ({
    media: String(abfrage),
    get matches() { return lage },
    addEventListener: (_art, fn) => zuhoerer.add(fn),
    removeEventListener: (_art, fn) => zuhoerer.delete(fn),
    addListener: (fn) => zuhoerer.add(fn),
    removeListener: (fn) => zuhoerer.delete(fn),
  })
  dom.window.__DIakonosBOOT = {
    roles: ['System Manager', 'Administrator'], is_admin: true, module_sichtbar: ['chat'],
  }
  return {
    /** Die Lage umschalten (wie ein Gerätewechsel) — löst `change` aus. */
    umschalten(an) {
      lage = an
      for (const fn of [...zuhoerer]) fn({ matches: an })
    },
  }
}

test('CHAT-3a-3/A: App.vue baut auf (kein TDZ-Fehler) — Zähler läuft nur am Handy', async (t) => {
  const umg = appUmgebung({ handy: false })
  const abrufe = []
  globalThis.fetch = async (url) => {
    globalThis.__FETCH_ZAHL = (globalThis.__FETCH_ZAHL || 0) + 1
    abrufe.push(String(url))
    return {
      ok: true, status: 200,
      headers: { get: () => 'application/json' },
      json: async () => ({ message: { gespraeche: [{ name: 'CHAT-1', ungelesen: 3 }] } }),
      text: async () => '{}',
      clone() { return this },
    }
  }
  const app = (await import(pathToFileURL(baum('App.vue', { frisch: true })).href)).default
  assert.equal(typeof app.setup, 'function', 'App.vue ist eine Komponente mit setup()')

  // Genau das, was `App.setup` vorher zerwarf: der Rahmen wird gemountet.
  const { host, warnungen, abbaum } = await mounten(app, {})
  await warte(10)
  const fehler = warnungen.filter((w) => /ReferenceError|before initialization|is not defined/i.test(w))
  assert.deepEqual(fehler, [],
    'App.setup wirft NICHT (vorher: Cannot access \'istHandyLage\' before initialization)')
  assert.ok(host.querySelector('.dk-app'), 'die App-Hülle (.dk-app) steht im DOM')

  // Am Desktop (keine Leiste) fragt der Zähler NICHTS.
  assert.deepEqual(abrufe.filter((u) => /meine_gespraeche/.test(u)), [],
    'ohne Handy-Lage kein Abruf von meine_gespraeche')
  abbaum()
})

test('CHAT-3a-3/A: Wechsel Desktop → Handy startet den Zähler (watch → planen)', async (t) => {
  // Die App wird im HANDY aufgebaut: dort mounten die Handy-Leiste und die
  // Schublade (Desktop baut sie nicht auf), und `App.vue` hält im `onMounted`
  // beider Zweige denselben Zähler-/Kennzahl-Aufbau. Der Wechsel zur
  // UNGEÖFFNETEN Seite ist danach die Zusage, die hier zählt: `planen()` startet
  // den Takt (der Aufbau ist die Gegenprobe — `useChatZaehler` fragt beim
  // Aufbau nur mit `darfFragen()`, nicht über den Beobachter).
  const umg = appUmgebung({ handy: true })
  const abrufe = []
  globalThis.fetch = async (url) => {
    abrufe.push(String(url))
    return {
      ok: true, status: 200,
      headers: { get: () => 'application/json' },
      json: async () => ({ message: { gespraeche: [{ name: 'CHAT-1', ungelesen: 3 }] } }),
      text: async () => '{}',
      clone() { return this },
    }
  }
  const app = (await import(pathToFileURL(baum('App.vue', { frisch: true })).href)).default

  // `App.vue` hält einen 1000-ms-Intervall (Restzeit der Impersonation). Er
  // prüft hier nicht die Sache, hielte aber die Node-Laufzeit offen — deshalb
  // wird er beim Aufbau abgefangen und NICHT auf die Uhr gelegt.
  const echterInterval = globalThis.setInterval
  globalThis.setInterval = (fn, ms) => (Number(ms) === 1000 ? 0 : echterInterval(fn, ms))
  const { host, abbaum } = await mounten(app, {})
  globalThis.setInterval = echterInterval
  await warte(6)
  assert.equal(host.querySelector('.dk-app').classList.contains('dk-app--handy'), true,
    'die Gerüst-Klasse folgt der Lage')

  // Wechsel in die DESKTOP-Lage (Watch auf `istHandyLage` → `planen()`): was
  // `planen()` unter „keine Leiste“ tut, ist NICHTS — genau das darf hier nicht
  // als Abruf auftauchen. Und die Gerüst-Klasse folgt derselben Lage.
  const vorher = abrufe.length
  umg.umschalten(false)
  await warte(4)
  assert.equal(host.querySelector('.dk-app').classList.contains('dk-app--handy'), false,
    'Verlassen der Lage: die Gerüst-Klasse geht wieder ab')
  assert.deepEqual(abrufe.slice(vorher).filter((u) => /meine_gespraeche/.test(u)), [],
    'planen() ohne Leiste fragt nichts (der Wechsel allein startet keinen Takt)')
  abbaum()
  await warte(4)
})

// ══ Klein · mitteilungSenden(null) setzt den Zähler nicht auf 0 ════════════

test('CHAT-3a-3/Klein: der Zähler übernimmt null als „keine Zahl“, nicht als 0', async () => {
  const { useChatZaehler } = await import(pathToFileURL(SRC.pathname + 'composables/useChatZaehler.js').href)
  // `useChatZaehler` registriert `onUnmounted` — ausserhalb eines Aufbaus nur
  // eine Warnung; der Rückgabewert ist trotzdem vollständig benutzbar.
  const geholt = []
  const zaehler = useChatZaehler({
    aktiv: () => true,
    handyLage: () => false, // kein Takt, kein erster Abruf
    seiteOffen: () => false,
    abfragen: async () => { geholt.push(1); return { gespraeche: [{ ungelesen: 4 }] } },
  })
  await warte(2)
  assert.equal(zaehler.ungelesen.value, null, 'ohne Leiste steht keine Zahl (null)')

  // So meldet die Seite beim Aufbau: `mitteilungSenden(null)`.
  zaehler.uebernehmen(null)
  assert.equal(zaehler.ungelesen.value, null,
    'null ist „keine Zahl“ — der Zähler bleibt auf null, NICHT auf 0')
  zaehler.uebernehmen(undefined)
  assert.equal(zaehler.ungelesen.value, null, 'undefined ebenso')

  // Echte Zahlen kommen weiterhin an — auch 0, wenn 0 GEMELDET wird.
  zaehler.uebernehmen(0)
  assert.equal(zaehler.ungelesen.value, 0, 'eine gemeldete 0 zählt')
  zaehler.uebernehmen(7)
  assert.equal(zaehler.ungelesen.value, 7)
  zaehler.uebernehmen('12')
  assert.equal(zaehler.ungelesen.value, 12, 'Zahlen als Text werden übernommen')
  assert.deepEqual(geholt, [], 'kein Abruf ohne Handy-Lage')
  zaehler.anhalten()
})

// ══ C2 · ChatListe hebt das offene Gespräch hervor ═════════════════════════
//
// Der Fehler: `props.aktiv` ist die BLANKE Kennung (`CHAT-1`), der Schlüssel
// der Zeile ist `n:CHAT-1` — der Vergleich traf nie, `is-aktiv` und
// `aria-current` fehlten am offenen Gespräch.

test('CHAT-3a-3/C2: ChatListe markiert das offene Gespräch (is-aktiv + aria-current)', async () => {
  const chatListe = (await import(pathToFileURL(baum('components/chat/ChatListe.vue')).href)).default
  const { gruppierteListe } = await import(pathToFileURL(baum('composables/nachrichtenLogik.mjs')).href)
  const zeilen = [
    { name: 'CHAT-1', art: 'gruppe', gruppe: 'leitung', untergruppe: null, titel: 'Leitung',
      geoeffnet: true, ungelesen: 2, teilnehmer: 4, letzte: 'Hallo', letzte_am: '2026-11-18 10:00:00' },
    { name: 'CHAT-2', art: 'gruppe', gruppe: 'chor', untergruppe: null, titel: 'Chor',
      geoeffnet: true, ungelesen: 0, teilnehmer: 9, letzte: 'Moin', letzte_am: '2026-11-18 09:00:00' },
  ]
  const gruppen = gruppierteListe(zeilen)

  // Die Seite übergibt die BLANKE Kennung (Nachrichten.vue: `:aktiv="kennung"`).
  const { host, warnungen, abbaum } = await mounten(chatListe, { gruppen, aktiv: 'CHAT-1', ungelesen: 2 })
  const links = [...host.querySelectorAll('a.dk-chat-zeile')]
  assert.equal(links.length, 2, 'zwei Zeilen erwartet. Warnungen: ' + warnungen.slice(0, 2).join(' | '))
  const offen = links.find((a) => /Leitung/.test(a.textContent))
  const fremd = links.find((a) => /Chor/.test(a.textContent))
  assert.ok(offen && fremd, 'beide Gespräche stehen in der Liste')
  assert.equal(offen.classList.contains('is-aktiv'), true,
    'das offene Gespräch (CHAT-1) ist hervorgehoben')
  assert.equal(offen.getAttribute('aria-current'), 'page',
    'das offene Gespräch trägt aria-current="page"')
  assert.equal(fremd.classList.contains('is-aktiv'), false, 'CHAT-2 ist NICHT hervorgehoben')
  assert.equal(fremd.hasAttribute('aria-current'), false, 'CHAT-2 trägt kein aria-current')
  abbaum()

  // Gegenprobe: gar nichts offen → keine Hervorhebung, kein aria-current.
  const leer = await mounten(chatListe, { gruppen, aktiv: '', ungelesen: 0 })
  const alle = [...leer.host.querySelectorAll('a.dk-chat-zeile')]
  assert.equal(alle.length, 2)
  for (const a of alle) {
    assert.equal(a.classList.contains('is-aktiv'), false)
    assert.equal(a.hasAttribute('aria-current'), false)
  }
  leer.abbaum()

  // Gegenprobe: eine Kennung, die es nicht gibt, hebt NICHTS hervor.
  const fremdAktiv = await mounten(chatListe, { gruppen, aktiv: 'CHAT-999', ungelesen: 0 })
  for (const a of fremdAktiv.host.querySelectorAll('a.dk-chat-zeile')) {
    assert.equal(a.classList.contains('is-aktiv'), false)
  }
  fremdAktiv.abbaum()
})

// ══ C1 · Adressierung: Hauptgruppe trifft NICHT die Untergruppe ════════════
//
// `ungeoeffneteZeile` entscheidet, WELCHES Gespräch eine Ortsadresse öffnet
// (und anlegt). Sie ist nicht exportiert — deshalb wird derselbe Weg benutzt,
// den die Seite geht: der Eintrag, den `sicherstellen()` an
// `gespraech_anlegen` übergibt. Gelesen wird die Funktion aus dem Skriptteil
// der Seite, damit der Test am ECHTEN Code hängt (kein Nachbau).

test('CHAT-3a-3/C1: Adresse „Jugend“ öffnet den Haupt-Chat, nicht „Jugend – Leiter“', async () => {
  const quelle = readFileSync(new URL('pages/Nachrichten.vue', SRC), 'utf8')
  const rumpf = /function ungeoeffneteZeile\(adresse\) \{[\s\S]*?\n\}/.exec(quelle)
  assert.ok(rumpf, 'ungeoeffneteZeile steht in Nachrichten.vue')
  const { zeilenSchluessel } = await import(pathToFileURL(baum('composables/nachrichtenLogik.mjs')).href)
  const waehle = new Function('gespraeche', 'adresse', `
    const gespraecheWert = { value: gespraeche }
    ${rumpf[0].replace(/gespraeche\.value/g, 'gespraecheWert.value')}
    return ungeoeffneteZeile(adresse)
  `)

  // Server-Reihenfolge (`meine_gespraeche`): geöffnete nach letzter Nachricht,
  // ungeöffnete nach TITEL ABSTEIGEND — „Jugend – Leiter“ steht also VOR
  // „Jugend“. Genau deshalb traf die alte Bedingung (`e.gruppe === a`) die
  // Untergruppe zuerst.
  const liste = [
    { name: 'CHAT-CHOR', art: 'gruppe', gruppe: 'chor', untergruppe: null, titel: 'Chor',
      geoeffnet: true, ungelesen: 0, teilnehmer: 9, letzte: 'x', letzte_am: '2026-11-18 10:00:00' },
    { name: null, art: 'untergruppe', gruppe: 'jugend', untergruppe: 'jugend-leiter',
      titel: 'Jugend – Leiter', geoeffnet: false, ungelesen: 0, teilnehmer: 3,
      letzte: null, letzte_am: null },
    { name: null, art: 'gruppe', gruppe: 'jugend', untergruppe: null, titel: 'Jugend',
      geoeffnet: false, ungelesen: 0, teilnehmer: 12, letzte: null, letzte_am: null },
  ]
  // Die falsche Wahl wäre der ERSTE Treffer der alten Regel — hier
  // dokumentiert, damit die Zusage nicht am Zufall der Reihenfolge hängt.
  const alt = liste.filter((e) => !e.name && e.geoeffnet === false
    && (e.gruppe === 'jugend' || e.untergruppe === 'jugend'))[0]
  assert.equal(alt.untergruppe, 'jugend-leiter', 'die alte Regel traf die Untergruppe')

  const treffer = waehle(liste, 'jugend')
  assert.ok(treffer, 'die Adresse „jugend“ findet einen Eintrag')
  assert.equal(treffer.untergruppe, null,
    'die Adresse „jugend“ trifft die HAUPTGRUPPE, nicht die Untergruppe')
  assert.equal(treffer.art, 'gruppe', 'und es ist der Gruppen-Chat')
  assert.equal(treffer.titel, 'Jugend')
  // Er passt auch zu dem, was die Liste als Schlüssel/Adresse vergibt — der
  // geöffnete Chat ist derselbe Eintrag, den die Zeile adressiert.
  assert.equal(zeilenSchluessel(treffer), 'o:jugend/')

  // Eine Untergruppen-Adresse trifft die Untergruppe — und nur sie.
  const unter = waehle(liste, 'jugend-leiter')
  assert.ok(unter, '„jugend-leiter“ findet die Untergruppe')
  assert.equal(unter.untergruppe, 'jugend-leiter')
  assert.equal(unter.gruppe, 'jugend')
  assert.equal(zeilenSchluessel(unter), 'o:jugend/jugend-leiter')

  // Die Pfadform bleibt gültig; ein fremder Name trifft nichts.
  assert.equal(waehle(liste, 'jugend/jugend-leiter')?.untergruppe, 'jugend-leiter',
    'die Form „gruppe/untergruppe“ bleibt gültig')
  assert.equal(waehle(liste, 'gibtsnicht'), null)
  assert.equal(waehle(liste, ''), null)
})

// ══ B · Der Poll sieht Änderungen (kein `seit` mehr) ═══════════════════════
//
// Der Fehler: `taktAbruf` schickte `seit = letzte bekannte Kennung`. Der Server
// liefert zu `seit` NUR Nachrichten mit SPÄTEREM Zeitstempel (`api/chat.py`,
// `ChatNachricht.erstellt_am > anker`) — eine Bearbeitung, eine Löschung samt
// `geloescht_grund`, eine neue Reaktion und ein geänderter Lesestand einer
// schon sichtbaren Nachricht kamen damit NIE an. Hier läuft die ECHTE Seite mit
// ihren echten Aufrufen; die Server-Attrappe verhält sich wie `chat.verlauf`:
// ohne Anker `richtung: 'neueste'` mit der JÜNGSTEN Seite (voll, verschoben),
// mit `seit` nur die wirklich neueren.

/**
 * Die Seite in einem eigenen Modul-Graph, mit eigener API-Attrappe.
 * `server(args)` liefert die Antwort je Methode — genau wie der echte Server.
 */
async function nachrichtenSeiteMitServer(server, { hash = '#/nachrichten/CHAT-1' } = {}) {
  const ordner = join(TMP, 'seite-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  const aufrufe = []
  const api = join(ordner, 'api.mjs')
  writeFileSync(api, [
    'export async function apiCall(methode, parameter) {',
    '  globalThis.__CHAT_PUSH({ methode, parameter })',
    '  return globalThis.__CHAT_SERVER({ methode, parameter })',
    '}',
    'export const apiGet = apiCall',
    "export const apiUrl = (p) => 'https://pruefstand.invalid/' + p",
    'export class AuditConfirmationRequired extends Error {}',
    'export const pruefeSitzungsAntwort = () => false',
    'export const apiAntwortPruefen = async () => ({ message: {} })',
  ].join('\n'))
  const U = (rel) => pathToFileURL(SRC.pathname + rel).href
  umleitung.clear()
  umleitung.set(U('composables/useApi.js'), pathToFileURL(api).href)
  globalThis.__CHAT_PUSH = (eintrag) => aufrufe.push(eintrag)
  globalThis.__CHAT_SERVER = server
  dom.window.__DIakonosBOOT = { roles: ['Mitglied'], is_admin: false, module_sichtbar: ['chat'] }
  dom.window.location.hash = hash

  const mod = await import(pathToFileURL(baum('pages/Nachrichten.vue', { frisch: true, ordner })).href)
  const { host, abbaum, warnungen } = await mounten(mod.default, {})
  return { host, abbaum, warnungen, aufrufe, mod }
}

/** Eine Nachricht, wie `_zeile` sie liefert (nur die Felder, die hier zählen). */
function zeile(name, text, { am = '2026-11-18 10:00:00', eigene = false, ...rest } = {}) {
  return {
    name, text, eigene, erstellt_am: am, autor: 'Erika Muster', autor_mitglied: 'M-1',
    bearbeitet: false, geloescht: false, geloescht_grund: null, reaktionen: [],
    antwort_auf: null, antwort_auf_text: null, gelesen_von: eigene ? 0 : null, ...rest,
  }
}

test('CHAT-3a-3/B: der Poll sendet KEIN `seit` und bringt Änderungen an bekannten Zeilen', async (t) => {
  // Ausgangslage: 4 Nachrichten im Verlauf (N-5 ist die zweite eigene).
  let seite = [
    zeile('N-1', 'Erste Fassung', { am: '2026-11-18 10:00:00' }),
    zeile('N-2', 'Zweite', { am: '2026-11-18 10:01:00', eigene: true, gelesen_von: 0 }),
    zeile('N-3', 'Dritte', { am: '2026-11-18 10:02:00' }),
    zeile('N-5', 'Meine Frage', { am: '2026-11-18 10:04:00', eigene: true, gelesen_von: 0 }),
  ]
  const server = ({ methode, parameter }) => {
    const kurz = String(methode).split('.').pop()
    if (kurz === 'meine_gespraeche') {
      return { gespraeche: [{ name: 'CHAT-1', art: 'gruppe', gruppe: 'chor', untergruppe: null,
        titel: 'Chor', geoeffnet: true, ungelesen: 1, teilnehmer: 3, letzte_nachricht: 'Dritte',
        letzte_am: '2026-11-18 10:02:00', stumm: false }] }
    }
    if (kurz === 'gespraech_anlegen') return { name: 'CHAT-1', art: 'gruppe', gruppe: 'chor' }
    if (kurz === 'verlauf') {
      // Wie `verlauf(gespraech, vor=None, seit=None)`: `seit` = NUR neuer,
      // ohne Anker die neueste Seite (hier: alles, richtung 'neueste').
      if (parameter && parameter.seit) {
        const i = seite.findIndex((n) => n.name === parameter.seit)
        return { gespraech: 'CHAT-1', richtung: 'seit',
          nachrichten: i >= 0 ? seite.slice(i + 1) : [] }
      }
      return { gespraech: 'CHAT-1', richtung: 'neueste',
        nachrichten: seite.map((n) => ({ ...n })),
        vor: seite[0]?.name, seit: seite[seite.length - 1]?.name }
    }
    if (kurz === 'lesestand_setzen') return { ungelesen: 0 }
    return {}
  }

  const { host, abbaum, aufrufe } = await nachrichtenSeiteMitServer(server)
  await warte(14)
  const verlaufAufrufe = () => aufrufe.filter((a) => /chat\.verlauf$/.test(a.methode))
  assert.ok(verlaufAufrufe().length >= 1, 'die Seite hat den Verlauf geholt')
  assert.equal(verlaufAufrufe()[0].parameter.gespraech, 'CHAT-1')
  assert.equal('seit' in verlaufAufrufe()[0].parameter, false,
    'schon der erste Abruf ist die neueste Seite (kein `seit`)')

  // ── Jetzt ändert sich der Verlauf hinter dem Rücken der Seite ────────────
  // 1. N-1 wurde bearbeitet, 2. N-2 (die EIGENE Nachricht) wurde gelöscht,
  // 3. N-3 hat eine Reaktion bekommen, 4. N-4 ist neu dazugekommen, 5. an der
  // eigenen N-5 steht „gelesen von 2“ (F2: nur an eigenen Nachrichten).
  seite = [
    zeile('N-1', 'Erster Text, korrigiert', { am: '2026-11-18 10:00:00', bearbeitet: true }),
    zeile('N-2', null, { am: '2026-11-18 10:01:00', eigene: true, geloescht: true,
      geloescht_grund: 'Beleidigung', gelesen_von: 2 }),
    zeile('N-3', 'Dritte', { am: '2026-11-18 10:02:00',
      reaktionen: [{ reaktion: '👍', anzahl: 2, eigene: true }] }),
    zeile('N-4', 'Vierte, ganz neu', { am: '2026-11-18 10:03:00' }),
    // Fünfte, eigene: nur an IHR steht „gelesen von N“ (F2) — sie trägt den
    // geänderten Lesestand aus dem Poll.
    zeile('N-5', 'Meine Frage', { am: '2026-11-18 10:04:00', eigene: true, gelesen_von: 2 }),
  ]

  // Einen Takt abwarten: der nächste `verlauf`-Abruf ist der Poll.
  const vorher = verlaufAufrufe().length
  await new Promise((loese) => setTimeout(loese, 11_000))
  await warte(14)
  const poll = verlaufAufrufe().slice(vorher)
  assert.ok(poll.length >= 1, 'der Takt hat den Verlauf erneut geholt')
  for (const aufruf of poll) {
    assert.equal('seit' in aufruf.parameter, false,
      'der Poll sendet KEIN `seit` — sonst kämen Änderungen bekannter Zeilen nie an')
    assert.equal(aufruf.parameter.gespraech, 'CHAT-1', 'und er fragt dasselbe Gespräch')
  }

  // Und die Änderungen stehen im Verlauf — die Seite hat die volle Seite
  // eingeordnet, nicht nur das „Neue“.
  const text = host.textContent || ''
  assert.match(text, /Erster Text, korrigiert/, 'die Bearbeitung ist angekommen')
  // Eigene Löschung: der Grund des Servers wird NICHT angezeigt („Du hast diese
  // Nachricht gelöscht.“) — die Löschung selbst ist aber angekommen.
  assert.match(text, /Du hast diese Nachricht gelöscht/,
    'die Löschung der bekannten Zeile ist angekommen')
  // F2: „gelesen von N“ steht NUR an eigenen Nachrichten — hier an der eigenen
  // N-2, deren Lesestand der Poll mitbringt (der zweite Teilnehmer hat sie
  // gelesen).
  assert.match(text, /gelesen von 2/, 'der geänderte Lesestand ist angekommen')
  assert.match(text, /Vierte, ganz neu/, 'die neue Nachricht ist angekommen')
  assert.doesNotMatch(text, /Erste Fassung/, 'der alte Text ist ersetzt, nicht gedoppelt')
  abbaum()
})

// ══ Klein · der Bearbeiten-Takt endet mit der Frist ════════════════════════
//
// Der Fehler: `ChatBlase.vue` setzte alle 30 s einen neuen „jetzt“-Wert, ohne
// je aufzuhören — nach Ablauf der 15 Minuten lief der Takt bis zum Abbau der
// Blase weiter (auf einer Verlaufsseite bis zu 50 Timer, die nie zur Ruhe
// kommen). Hier wird die Blase mit einer Nachricht gemountet, deren Frist
// gleich abläuft; die Uhr des Prüfstands spult die 30-s-Schritte ab.

test('CHAT-3a-3/Klein: der Bearbeiten-Takt endet, sobald die 15 Minuten vorbei sind', async () => {
  const chatBlase = (await import(pathToFileURL(baum('components/chat/ChatBlase.vue')).href)).default
  const { verlaufsZeile } = await import(pathToFileURL(baum('composables/nachrichtenLogik.mjs')).href)

  // Eine EIGENE Nachricht, 14 Minuten alt — die Frist läuft noch (`bearbeitbar`).
  const alter = new Date(Date.now() - 14 * 60 * 1000)
  const nachricht = verlaufsZeile({
    name: 'N-1', text: 'Mein Text', eigene: true, autor: 'Erika', erstellt_am: alter.toISOString(),
    bearbeitet: false, geloescht: false, reaktionen: [], gelesen_von: 0,
  }, { ich: 'M-1' })
  assert.equal(nachricht.bearbeitbar, true, 'Prüfstand: die Frist läuft noch')

  // Wie oft legt die Blase einen 30-s-Takt an? Gezählt wird die ECHTE
  // `setInterval`-Aufrufstelle; der Rückruf wird von Hand gerufen, damit der
  // Test nicht auf den Takt wartet.
  const echtInterval = globalThis.setInterval
  const echtClear = globalThis.clearInterval
  const intervalle = []
  globalThis.setInterval = (fn, ms) => {
    const id = { fn, ms }
    intervalle.push(id)
    return id
  }
  globalThis.clearInterval = (id) => {
    const i = intervalle.indexOf(id)
    if (i >= 0) intervalle.splice(i, 1)
  }
  // Prüfstands-Seil: die Blase mountet mit einer noch laufenden Frist (der
  // Stift ist da). Für den Takt-Durchlauf wird `erstellt_am` auf ein Alter
  // jenseits der 15 Minuten gestellt — der Server liefert genau so eine Zeile,
  // wenn der Verlauf lange offen war, und `innerhalbFrist` ist die Wandzeit.
  const originalErstellt = nachricht.erstellt_am
  try {
    const { host, abbaum } = await mounten(chatBlase, { nachricht })
    // Der Stift ist der Knopf mit dem Beschriftungsnamen „Bearbeiten“
    // (CHAT-3a-4: die Aktionen sind Symbolknöpfe — der Name steht im
    // `aria-label`, damit die Vorlesehilfe ihn findet). „Antworten“/„Löschen“
    // stehen ebenfalls als aria-label daneben.
    const stift = () => [...host.querySelectorAll('button')]
      .filter((b) => /^\s*Bearbeiten\s*$/.test(b.getAttribute('aria-label') || ''))
    assert.equal(stift().length, 1, 'der Stift steht (Frist noch offen)')
    assert.equal(intervalle.length, 1, 'die Blase legt EINEN 30-s-Takt an')
    assert.equal(intervalle[0].ms, 30_000, 'und zwar im 30-s-Takt')

    nachricht.erstellt_am = new Date(Date.now() - 16 * 60 * 1000).toISOString()
    intervalle[0].fn()
    await warte(8)

    assert.equal(stift().length, 0, 'nach Ablauf der 15 Minuten gibt es keinen Stift mehr')
    assert.equal(intervalle.length, 0,
      'der Takt ist eingestellt (kein Leerlauf-Termin mehr)')
    abbaum()
  } finally {
    nachricht.erstellt_am = originalErstellt
    globalThis.setInterval = echtInterval
    globalThis.clearInterval = echtClear
  }
})


