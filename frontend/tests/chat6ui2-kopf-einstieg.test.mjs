/**
 * CHAT-6-UI-2 — Prüfseite „Chat“: Kopf und Einstieg (Vue 3, Frontend).
 *
 * Karte t_e3fd5e96, Review R2. Geprüft wird VERHALTEN (gemountet, mit
 * Netzattrappe), nicht nur ein Klassenmuster:
 *
 *   A  Merker (`composables/chatPruefRecht.mjs`): EINE Frage je Sitzung, ein
 *      zweiter Aufruf hängt sich an die laufende an, `frisch` fragt erneut,
 *      ein 403 merkt „nein“, ein Netz-/Serverfehler merkt GAR NICHTS (kein
 *      Recht, keine Zahl) und `merken()` nimmt die Antwort der Prüfseite an.
 *      CHAT-6-UI-3: Der EINSTIEG liest `get_session_info().chat_moderieren`;
 *      die Liste wird NUR mit Recht geholt — und genau einmal.
 *   B  Kalender.vue: mit Chat-Recht steht der Reiter „Chat“ samt Zahl am Kopf,
 *      MIT 403 steht er nicht — und der Server wird beim Rendern NICHT erneut
 *      gefragt (die Seite fragt einmal beim Aufbau).
 *   C  Moderation.vue, MUSS 1: auf der GANZEN Prüfseite ist `pruefTafel`
 *      gesetzt — „Monat/Woche/Liste“ sind LINKS in den Kalender, „Heute“,
 *      ‹ › und die Kalender-Auswahl stehen dort NICHT (auch im Chat-Zweig
 *      nicht: der Fall „nur Chat-Recht“ ist der Beweis).
 *   D  SOLL 1/2: der unerreichbare `!canModerate`-Block ist weg (der Chat
 *      steht genau einmal), und der Handy-Rückweg „‹ Termine“ erscheint nur
 *      mit Kalender-Recht.
 *   E  SOLL 3: Netz-/Serverfehler beim ersten Laden → Fehlerseite mit
 *      role="alert" und „Erneut versuchen“; ein 403 ist KEIN solcher Fehler.
 *   F  SOLL 4/5: erledigt/verworfen werden genau EINMAL geholt (auch bei
 *      leerer Liste), und ein 403 dabei nimmt das Chat-Recht NICHT weg.
 *
 * Lauf (eine Datei je Aufruf, TZ=Europe/Berlin):
 *   TMPDIR=$(mktemp -d) TZ=Europe/Berlin node --test tests/chat6ui2-kopf-einstieg.test.mjs
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
  'sessionStorage', 'location', 'URLSearchParams', 'PopStateEvent', 'HashChangeEvent']) {
  globalThis[schluessel] = dom.window[schluessel]
}
globalThis.requestAnimationFrame = dom.window.requestAnimationFrame
  || ((fn) => setTimeout(() => fn(Date.now()), 0))
Object.defineProperty(dom.window.document, 'hidden', { configurable: true, get: () => false })
Object.defineProperty(dom.window.document, 'visibilityState', { configurable: true, get: () => 'visible' })

const VUE_URL = import.meta.resolve('vue')
const SRC_ROOT = new URL('../src/', import.meta.url)
const SRC = new URL('../src/diakonos/', import.meta.url)

const TMP = mkdtempSync(join(tmpdir(), 'chat6ui2-'))
test.after(() => rmSync(TMP, { recursive: true, force: true }))

const M = await import(new URL('components/chat/meldung.mjs', SRC).href)

// ── SFC → ES-Modul (dieselbe Bauart wie chat6-meldung-ui.test.mjs) ─────────
const cache = new Map()
const umleitung = new Map()

const VUE_SCHIM = join(TMP, 'vue-schim.mjs')
writeFileSync(VUE_SCHIM, [
  `export * from '${VUE_URL}'`,
  'export function nextTick(fn) {',
  '  const p = globalThis.__NAECHSTER_TAKT()',
  '  return fn ? p.then(fn) : p',
  '}',
].join('\n'))

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
    const wurzel = resolve(SRC_ROOT.pathname)
    const voll = resolve(quellDatei)
    const relativ = voll.startsWith(wurzel) ? 'x' + voll.slice(wurzel.length) : voll
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
        if (spec === 'vue') return `from '${quellDatei.endsWith('.vue') ? VUE_SCHIM : VUE_URL}'`
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

const tickWarteschlange = []
globalThis.__NAECHSTER_TAKT = () => new Promise((loese) => { tickWarteschlange.push(loese) })
async function rendern(n = 6) {
  for (let i = 0; i < n; i += 1) {
    const offen = tickWarteschlange.splice(0, tickWarteschlange.length)
    if (!offen.length) { await tick(); continue }
    for (const loese of offen) loese()
    await tick()
  }
}

/**
 * FE-ABBAU: JEDE Montage meldet ihren Abbau hier an, und `afterEach` baut
 * alles ab, was noch steht — auch nach einem ROTEN `assert`. Vorher stand
 * `s.abbaum()` als letzte Zeile im Test: eine geworfene Zusage ließ die Seite
 * stehen, ihr Takt (10 s, plant sich neu) hielt die Ereignisschleife offen und
 * der FE-Teststep im Build hing (FE-HAENGER, 4ce2d6b2).
 */
const seitenAbbau = new SeitenAbbau()
test.afterEach(() => seitenAbbau.alle())

async function mounten(baustein, props = {}, { propNamen = null } = {}) {
  const Vue = await import('vue')
  const host = document.createElement('div')
  document.body.appendChild(host)
  const warnungen = []
  const gemeldet = []
  const Wrapper = {
    props: { p: { type: Object, default: () => ({}) } },
    setup(innerProps) {
      const eigene = Vue.ref({ ...innerProps.p })
      const namen = propNamen || []
      return () => Vue.h(baustein, {
        ...eigene.value,
        ...Object.fromEntries(namen.map((n) => [`on${n[0].toUpperCase()}${n.slice(1)}`, (x) => gemeldet.push({ n, x })])),
      })
    },
  }
  const app = Vue.createApp({ render: () => Vue.h(Wrapper, { p: props }) })
  app.config.warnHandler = (m) => warnungen.push(m)
  app.config.errorHandler = (e) => warnungen.push(String(e && e.message))
  app.mount(host)
  await warte(10)
  const abbaum = seitenAbbau.anmelden(() => {
    try { app.unmount() } catch { /* egal */ }
    try { host.remove() } catch { /* egal */ }
  })
  return { host, app, warnungen, gemeldet, abbaum }
}

const texte = (host, auswahl) => [...host.querySelectorAll(auswahl)].map((e) => e.textContent.trim())
const knopfMit = (host, muster) => [...host.querySelectorAll('button')]
  .find((b) => muster.test(b.textContent) || muster.test(String(b.getAttribute('aria-label') || '')))

function handyAbfrage(handy) {
  dom.window.matchMedia = (abfrage) => ({
    media: String(abfrage),
    matches: handy === true && /pointer:\s*coarse/.test(String(abfrage)),
    addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {},
  })
}

/** Fehler, wie `apiCall` sie wirft (status + exc_type). */
function fehler(status, text = 'kaputt') {
  return Object.assign(new Error(text), { status })
}

// ════════════════════════════════════════════════════════════════════════════
// A · Regeln + Merker (ohne DOM-Mount)
// ════════════════════════════════════════════════════════════════════════════

test('CHAT-6-UI-2/A: nur ein 403 heißt „keine Rechte“', () => {
  assert.equal(M.keineRechte(fehler(403)), true)
  assert.equal(M.keineRechte({ status: 403 }), true)
  assert.equal(M.keineRechte(fehler(500)), false, 'Serverfehler ist keine Rechtelage')
  assert.equal(M.keineRechte(new TypeError('Netz weg')), false, 'Netzfehler ist keine Rechtelage')
  assert.equal(M.keineRechte(null), false)
  assert.equal(M.keineRechte(undefined), false)
})

/** Der Merker mit einer ersetzten API — je Fall frisch geladen. */
async function merkerMit(server) {
  const ordner = join(TMP, 'merker-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  const api = join(ordner, 'api.mjs')
  writeFileSync(api, [
    'export async function apiCall(methode, parameter) {',
    '  globalThis.__MERKER_PUSH({ methode, parameter })',
    '  return globalThis.__MERKER_SERVER({ methode, parameter })',
    '}',
    'export const apiGet = apiCall',
    'export const apiUrl = (p) => "https://pruefstand.invalid/" + p',
    'export class AuditConfirmationRequired extends Error {}',
  ].join('\n'))
  umleitung.clear()
  umleitung.set(pathToFileURL(SRC.pathname + 'composables/useApi.js').href, pathToFileURL(api).href)
  const aufrufe = []
  globalThis.__MERKER_PUSH = (eintrag) => aufrufe.push(eintrag)
  globalThis.__MERKER_SERVER = server
  const mod = await import(pathToFileURL(
    baum('composables/chatPruefRecht.mjs', { frisch: true, ordner }),
  ).href)
  mod.zuruecksetzen()
  return { mod, aufrufe, sicht: mod.useChatPruefRecht() }
}

test('CHAT-6-UI-2/A: Merker fragt EINMAL, teilt die laufende Anfrage, merkt die Antwort', async () => {
  const { mod, aufrufe, sicht } = await merkerMit(({ methode }) => (
    String(methode).endsWith('get_session_info')
      ? { can_moderate: false, chat_moderieren: true }
      : { meldungen: [], offen: 3 }))
  assert.equal(sicht.recht.value, null, 'ohne Frage ist der Stand unbekannt')
  assert.equal(sicht.zahl.value, null, 'keine erfundene 0')
  assert.equal(sicht.geprueft.value, false)

  const [a, b] = await Promise.all([mod.pruefen(), mod.pruefen()])
  assert.equal(aufrufe.length, 2,
    'EINE Sitzungsfrage und EINE Listenfrage — geteilt: ' + aufrufe.map((u) => u.methode).join(','))
  assert.equal(a.recht, true)
  assert.deepEqual(b, a)
  assert.equal(sicht.zahl.value, 3, 'die Zahl kommt aus derselben Antwort')
  const liste = aufrufe.filter((u) => u.methode === 'chat.meldungen_liste')
  assert.equal(liste.length, 1)
  assert.deepEqual(liste[0].parameter, { stand: 'offen' }, 'die EINE Frage der Karte')

  // Danach: kein Abruf bei jedem Rendern — der Merker gilt.
  await mod.pruefen()
  await mod.pruefen()
  assert.equal(aufrufe.length, 2, 'weitere Fragen lesen den Merker')

  // `frisch` fragt erneut (die Prüfseite entscheidet über IHRE Antwort).
  globalThis.__MERKER_SERVER = ({ methode }) => (
    String(methode).endsWith('get_session_info')
      ? { can_moderate: false, chat_moderieren: true }
      : { meldungen: [], offen: 5 })
  const neu = await mod.pruefen({ frisch: true })
  assert.equal(aufrufe.filter((u) => u.methode === 'chat.meldungen_liste').length, 2)
  assert.equal(neu.zahl, 5)
})

test('CHAT-6-UI-2/A: 403 merkt „nein“, Netz-/Serverfehler merkt GAR NICHTS', async () => {
  const nein = await merkerMit(() => { throw fehler(403, 'Kein Zugriff') })
  const lage = await nein.mod.pruefen()
  assert.equal(lage.recht, false, '403 ist die Antwort „nein“')
  assert.equal(nein.sicht.zahl.value, null)
  assert.equal(nein.aufrufe.length, 1, 'ohne Recht KEIN Listen-Abruf')

  const kaputt = await merkerMit(() => { throw fehler(503, 'Der Server antwortet gerade nicht.') })
  const fehl = await kaputt.mod.pruefen()
  assert.equal(fehl.recht, null, 'ein Serverfehler ist KEINE Rechtelage')
  assert.equal(kaputt.sicht.zahl.value, null)
  assert.match(fehl.fehler, /Server|antwortet/, 'der Klartext steht bereit')
  assert.equal(kaputt.sicht.geprueft.value, false,
    'ein Fehler ist KEINE Antwort — der nächste Aufruf versucht es wieder')
  assert.equal(kaputt.aufrufe.length, 1)
  await kaputt.mod.pruefen()
  assert.equal(kaputt.aufrufe.length, 2, 'der zweite Versuch geht hinaus — kein Dauerblock')
})

test('CHAT-6-UI-3/A: ohne `chat_moderieren` kein Listen-Abruf, keine Zahl', async () => {
  const { mod, aufrufe, sicht } = await merkerMit(() => ({ can_moderate: true, chat_moderieren: false }))
  const lage = await mod.pruefen()
  assert.equal(lage.recht, false, 'der Einstieg sagt „nein“')
  assert.equal(lage.zahl, null, 'ohne Recht keine Zahl')
  assert.equal(sicht.geprueft.value, true, 'die Antwort ist gemerkt')
  assert.deepEqual(aufrufe.map((a) => a.methode), [
    'diakronos.kronos.api.permissions.get_session_info',
  ], 'NUR die Sitzungsfrage — die Liste wird gar nicht gefragt')
})

test('CHAT-6-UI-3/A: die Zahl kommt EINMAL aus der Liste, ein Fehler dort lässt sie unbekannt', async () => {
  const gut = await merkerMit(({ methode }) => (
    String(methode).endsWith('get_session_info')
      ? { can_moderate: false, chat_moderieren: true }
      : { meldungen: [], offen: 7 }))
  assert.equal((await gut.mod.pruefen()).zahl, 7)
  assert.deepEqual(gut.aufrufe.map((a) => a.methode), [
    'diakronos.kronos.api.permissions.get_session_info',
    'chat.meldungen_liste',
  ])

  const kaputt = await merkerMit(({ methode }) => {
    if (String(methode).endsWith('get_session_info')) return { can_moderate: true, chat_moderieren: true }
    throw fehler(500, 'Der Server antwortet gerade nicht.')
  })
  const lage = await kaputt.mod.pruefen()
  assert.equal(lage.recht, true, 'das Recht steht — nur die Zahl fehlt')
  assert.equal(lage.zahl, null, 'keine erfundene 0')
  assert.match(lage.fehler, /Server|antwortet/)
})

test('CHAT-6-UI-2/A: merken() nimmt die Antwort der Prüfseite an', async () => {
  const { mod, sicht } = await merkerMit(() => ({ can_moderate: false, chat_moderieren: true }))
  mod.merken({ recht: true, zahl: 7 })
  assert.equal(sicht.recht.value, true)
  assert.equal(sicht.zahl.value, 7)
  // Eine unbekannte Zahl bleibt „unbekannt“, nicht 0.
  mod.merken({ zahl: null })
  assert.equal(sicht.zahl.value, null)
  // Eine Entscheidung auf 0: der Reiter verliert seine Zahl.
  mod.merken({ recht: true, zahl: 0 })
  assert.equal(sicht.zahl.value, 0)
})

// ════════════════════════════════════════════════════════════════════════════
// B · Kalender.vue — der Reiter „Chat“ am Kopf (MUSS 2)
// ════════════════════════════════════════════════════════════════════════════

function apiAttrappe(ordner, praefix) {
  const api = join(ordner, 'api.mjs')
  writeFileSync(api, [
    'export async function apiCall(methode, parameter) {',
    `  globalThis.${praefix}_PUSH({ methode, parameter })`,
    `  return globalThis.${praefix}_SERVER({ methode, parameter })`,
    '}',
    'export const apiGet = apiCall',
    "export const apiUrl = (p) => 'https://pruefstand.invalid/' + p",
    'export class AuditConfirmationRequired extends Error {}',
    'export const pruefeSitzungsAntwort = () => false',
    'export const apiAntwortPruefen = async () => ({ message: {} })',
    'export function mitAntwort(wert) { return wert }',
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
  return { api, session }
}

const GESPRAECHE = [{
  name: 'CHAT-1', art: 'gruppe', gruppe: 'chor', untergruppe: null, titel: 'Chor',
  geoeffnet: true, ungelesen: 0, teilnehmer: 9, letzte_nachricht: 'Hallo',
  letzte_am: '2026-11-18 10:00:00', darf_senden: true,
}]

// Die Kalender-Seite zieht eine Reihe schwerer Bausteine bzw. Module, die im
// Node-Prüfstand nicht ladbar sind (Kalender-Bibliothek, Sortable, Router,
// Seiten-Zustände). Sie werden durch Attrappen ersetzt — geprüft wird der
// KOPF (welche Reiter, welche Zahl, wie oft gefragt wird), nicht das Raster.
const STUMPFE = {
  'components/kronos/KronosCalendar.vue': [
    `import { defineComponent, h } from '${VUE_URL}'`,
    'export default defineComponent({',
    "  name: 'KronosCalendar',",
    '  setup(_, { expose }) {',
    '    expose({ prev: () => {}, next: () => {}, today: () => {}, changeView: () => {},',
    '      refetchEvents: () => {}, gotoDate: () => {}, neuZuordnen: () => {} })',
    "    return () => h('div', { class: 'raster-attrappe' })",
    '  },',
    '})',
  ].join('\n'),
  'composables/useEventsApi.js': [
    'export const getMeinTermin = async () => null',
    'export const getEvents = async () => []',
  ].join('\n'),
  'composables/papierkorb.mjs': [
    'export const papierkorbMeldung = (titel) => `${titel} in den Papierkorb gelegt.`',
    'export const wiederherstellen = async () => ({})',
  ].join('\n'),
  'composables/useRueckgaengigAktion.js': [
    `import { ref } from '${VUE_URL}'`,
    'export function useRueckgaengigAktion() {',
    '  return { mitRueckgaengig: async () => {}, stapel: ref([]) }',
    '}',
  ].join('\n'),
  'router.js': [
    'export function navigate(ziel) { globalThis.__NAVIGIERT = ziel }',
    'export const aktuellerPfad = () => ({ pfad: "" })',
  ].join('\n'),
  'composables/useToast.js': [
    'export function showToast() {}',
    'export const toasts = { add: () => {} }',
  ].join('\n'),
  'composables/useBereichskopf.js': [
    'export function setzeRollenMarke() {}',
    'export function setzeBereichstitel() {}',
  ].join('\n'),
}

async function kalenderMontieren({ server = {}, handy = false } = {}) {
  const ordner = join(TMP, 'kal-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  const { api, session } = apiAttrappe(ordner, '__KAL')
  const U2 = (rel) => pathToFileURL(SRC.pathname + rel).href
  umleitung.clear()
  umleitung.set(U2('composables/useApi.js'), pathToFileURL(api).href)
  umleitung.set(U2('composables/useSession.js'), pathToFileURL(session).href)
  for (const [rel, quelle] of Object.entries(STUMPFE)) {
    const ziel = join(ordner, rel.replace(/[\\/]/g, '_') + '.mjs')
    writeFileSync(ziel, quelle)
    umleitung.set(U2(rel), pathToFileURL(ziel).href)
  }

  const aufrufe = []
  globalThis.__KAL_PUSH = (eintrag) => aufrufe.push(eintrag)
  globalThis.__KAL_SERVER = ({ methode, parameter }) => {
    const kurz = String(methode).split('.').pop()
    if (server && typeof server[kurz] === 'function') return server[kurz](parameter)
    // CHAT-6-UI-3: Die Kalender-Seite liest `chat_moderieren` aus derselben
    // Antwort — hier wie im Server BEIDE Felder, sonst wäre der Chat-Reiter
    // in jedem Fall aus.
    if (kurz === 'get_session_info') return { can_moderate: true, chat_moderieren: true }
    if (kurz === 'getModerationCount') return { count: 0 }
    if (kurz === 'meldungen_liste') return { meldungen: [], offen: 0 }
    if (kurz === 'get_kalender_verwaltung') return {}
    if (kurz === 'get_current_user_context') return {}
    if (kurz === 'get_accessible_calendars') return []
    if (kurz === 'get_calendar_events') return []
    if (kurz === 'get_kanban_board_data') return { vorschlaege: [], konflikte: [] }
    if (kurz === 'meine_gespraeche') return { gespraeche: GESPRAECHE.map((g) => ({ ...g })) }
    return {}
  }
  dom.window.__DIakonosBOOT = { roles: ['Moderator'], is_admin: false, module_sichtbar: ['kalender', 'chat'] }
  dom.window.location.hash = '#/kalender'
  handyAbfrage(handy)

  // Der Chat-Merker ist ein MODULSTAND — er überlebt den Testlauf. Jeder Fall
  // beginnt deshalb mit einem frischen Modul (`frisch: true`).
  const merkerDatei = baum('composables/chatPruefRecht.mjs', { frisch: true, ordner })
  const merker = await import(pathToFileURL(merkerDatei).href)
  merker.zuruecksetzen()

  const mod = (await import(pathToFileURL(baum('pages/Kalender.vue', { frisch: true, ordner })).href)).default
  const gemountet = await mounten(mod, {})
  await rendern(6)
  await warte(16)
  await rendern(6)
  return { ...gemountet, aufrufe, merker }
}

test('CHAT-6-UI-2/B: mit Chat-Recht steht der Reiter „Chat“ samt Zahl am Kopf', async () => {
  const s = await kalenderMontieren({
    server: {
      get_session_info: () => ({ can_moderate: true, chat_moderieren: true }),
      meldungen_liste: () => ({ meldungen: [], offen: 4 }),
    },
  })
  const reiter = [...s.host.querySelectorAll('.kal-reiter-punkt')].map((e) => ({
    id: e.getAttribute('data-reiter'), text: e.textContent.replace(/\s+/g, ' ').trim(),
  }))
  const chat = reiter.find((r) => r.id === 'chat')
  assert.ok(chat, 'der Reiter „Chat“ steht am Kalender-Kopf: ' + reiter.map((r) => r.text).join(' | '))
  assert.match(chat.text, /^Chat/, 'mit Namen')
  assert.match(chat.text, /4$/, 'und der Zahl der offenen Meldungen')
  const punkt = s.host.querySelector('[data-reiter="chat"]')
  assert.equal(punkt.tagName, 'A', 'eigene Seite → Link')
  assert.equal(punkt.getAttribute('href'), '#/kalender/pruefen?reiter=chat', 'die EINE Adresse')

  // Der Merker hat die Zahl übernommen — die Prüfseite zeigt sie ohne neuen Abruf.
  assert.equal(s.merker.useChatPruefRecht().recht.value, true)
  assert.equal(s.merker.useChatPruefRecht().zahl.value, 4)

  // Beim Rendern wird NICHT erneut gefragt: genau EIN Abruf beim Aufbau.
  const abrufe = s.aufrufe.filter((a) => a.methode === 'chat.meldungen_liste')
  assert.equal(abrufe.length, 1, 'ein Abruf je Seitenaufbau, keiner beim Rendern')
  s.abbaum()
})

test('CHAT-6-UI-2/B: mit 403 gibt es KEINEN Reiter „Chat“', async () => {
  const s = await kalenderMontieren({
    server: { get_session_info: () => ({ can_moderate: true, chat_moderieren: false }) },
  })
  const ids = [...s.host.querySelectorAll('.kal-reiter-punkt')].map((e) => e.getAttribute('data-reiter'))
  assert.ok(!ids.includes('chat'), 'ohne Recht kein Reiter: ' + ids.join(' | '))
  assert.equal(s.merker.useChatPruefRecht().recht.value, false, 'das 403 ist gemerkt')
  s.abbaum()
})

test('CHAT-6-UI-2/B: ein Serverfehler nimmt den Reiter nicht weg — wenn der Merker ihn kennt', async () => {
  // Erste Antwort (Merker) „ja“, danach scheitert ein späterer Abruf: der
  // Reiter bleibt, denn ein Fehler ist keine Rechtelage.
  const s = await kalenderMontieren({
    server: {
      get_session_info: () => {
        throw fehler(500, 'Der Server antwortet gerade nicht.')
      },
    },
  })
  assert.equal(s.merker.useChatPruefRecht().recht.value, null,
    'ein gescheiterter ERSTER Abruf merkt kein Recht')
  const ids = [...s.host.querySelectorAll('.kal-reiter-punkt')].map((e) => e.getAttribute('data-reiter'))
  assert.ok(!ids.includes('chat'), 'ohne Antwort kein geratener Reiter')
  s.abbaum()
})

// ════════════════════════════════════════════════════════════════════════════
// C–F · Moderation.vue — Kopf, Einstieg, Fehler, Abrufe
// ════════════════════════════════════════════════════════════════════════════

function meldungForm(überschreiben = {}) {
  return {
    name: 'M-1',
    stand: 'offen',
    grund: 'beleidigung',
    freitext: null,
    erstellt_am: '2026-11-18 09:00:00',
    gespraech_titel: 'Direktnachricht',
    nachricht: {
      name: 'DM-5', text: 'Du bist doof', autor: 'Anna A.',
      erstellt_am: '2026-11-18 08:59:00', geloescht_am: null, text_entfernt: false,
    },
    vorgeschichte: [],
    ...überschreiben,
  }
}

async function moderationMontieren({ server = {}, hash = '#/kalender/pruefen', handy = false, merkerVorher = null } = {}) {
  const ordner = join(TMP, 'mod-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  const { api, session } = apiAttrappe(ordner, '__MOD')
  const U2 = (rel) => pathToFileURL(SRC.pathname + rel).href
  // Die Termin-Tafel zieht `sortablejs` (im Node-Prüfstand nicht installiert);
  // im Chat-Zweig wird sie nicht gezeichnet. Attrappe wie in CHAT-6-UI.
  const boardStub = join(ordner, 'board-stub.mjs')
  writeFileSync(boardStub, [
    `import { defineComponent, h } from '${VUE_URL}'`,
    'export default defineComponent({',
    "  name: 'ModerationBoard',",
    '  setup(_, { expose }) {',
    '    expose({ getStagingIds: () => [], reloadBoard: async () => {} })',
    "    return () => h('div', { class: 'board-attrappe' })",
    '  },',
    '})',
  ].join('\n'))
  umleitung.clear()
  umleitung.set(U2('composables/useApi.js'), pathToFileURL(api).href)
  umleitung.set(U2('composables/useSession.js'), pathToFileURL(session).href)
  umleitung.set(U2('components/kronos/ModerationBoard.vue'), pathToFileURL(boardStub).href)

  const aufrufe = []
  globalThis.__MOD_PUSH = (eintrag) => aufrufe.push(eintrag)
  globalThis.__MOD_SERVER = ({ methode, parameter }) => {
    const kurz = String(methode).split('.').pop()
    if (server && typeof server[kurz] === 'function') return server[kurz](parameter)
    if (kurz === 'get_session_info') return { can_moderate: true, chat_moderieren: true }
    if (kurz === 'getModerationCount') return { count: 0 }
    if (kurz === 'meldungen_liste') return { meldungen: [], offen: 0 }
    return {}
  }
  dom.window.__DIakonosBOOT = { roles: ['Moderator'], is_admin: false, module_sichtbar: ['kalender', 'chat'] }
  dom.window.location.hash = hash
  handyAbfrage(handy)

  const merker = await import(pathToFileURL(
    baum('composables/chatPruefRecht.mjs', { frisch: true, ordner }),
  ).href)
  merker.zuruecksetzen()
  if (merkerVorher) merker.merken(merkerVorher)

  const mod = (await import(pathToFileURL(baum('pages/Moderation.vue', { frisch: true, ordner })).href)).default
  const gemountet = await mounten(mod, {}, { propNamen: ['entschieden'] })
  await rendern(6)
  await warte(16)
  await rendern(6)
  return { ...gemountet, aufrufe, merker }
}

const reiterIds = (host) => [...host.querySelectorAll('.kal-reiter-punkt')]
  .map((e) => ({ id: e.getAttribute('data-reiter'), tag: e.tagName, href: e.getAttribute('href') }))

test('CHAT-6-UI-2/C (MUSS 1): nur Chat-Recht → keine Kalender-Werkzeuge, Ansichten als LINKS', async () => {
  // Der Fall, den die Karte nennt: KEIN Kalender-Recht (`can_moderate` false),
  // Chat-Recht ja. Vorher hing `pruefTafel` an `!zeigeChat && canModerate` —
  // hier war es also `false`, und der Kopf zeigte Kalender-Auswahl, „Heute“,
  // ‹ › und Monat/Woche/Liste als UMSCHALTER (tote Knöpfe).
  const s = await moderationMontieren({
    server: {
      get_session_info: () => ({ can_moderate: false, chat_moderieren: true }),
      meldungen_liste: ({ stand }) => (stand === 'offen'
        ? { meldungen: [meldungForm()], offen: 1 }
        : { meldungen: [], offen: 1 }),
    },
  })
  // Die Kopfzeile steht auf der Tafel — kein Kalender-Werkzeug mehr.
  for (const auswahl of ['.header-right', '.todaybutton', '.prev-month', '.next-month',
    '.kalender-auswahl-btn', '[data-kalender-ausloeser]']) {
    assert.equal(s.host.querySelector(auswahl), null, `${auswahl} gehört nicht auf die Prüfseite`)
  }
  assert.equal(knopfMit(s.host, /^Heute$/), undefined, '„Heute“ fehlt (auch mit aria-label)')
  // „Monat/Woche/Liste“ sind LINKS zurück in den Kalender — keine Umschalter.
  const reiter = reiterIds(s.host)
  for (const id of ['monat', 'woche', 'liste']) {
    const punkt = reiter.find((r) => r.id === id)
    assert.ok(punkt, `„${id}“ steht in der Leiste`)
    assert.equal(punkt.tag, 'A', `„${id}“ ist ein Link, kein toter Umschalter`)
    assert.equal(punkt.href, `#/kalender?ansicht=${id}`, `„${id}“ führt in den Kalender`)
  }
  // Und der Chat steht da (die Seite ist offen, kein „Zugriff verweigert“).
  assert.equal(s.host.querySelector('.mod-zustand--verweigert'), null)
  assert.ok(s.host.querySelector('.dk-mpanel'), 'die Meldungen stehen da')
  s.abbaum()
})

test('CHAT-6-UI-2/C (MUSS 1): auch mit beiden Rechten sind die Ansichten LINKS', async () => {
  const s = await moderationMontieren({
    server: { meldungen_liste: () => ({ meldungen: [], offen: 0 }) },
  })
  const reiter = reiterIds(s.host)
  for (const id of ['monat', 'woche', 'liste']) {
    const punkt = reiter.find((r) => r.id === id)
    assert.equal(punkt.tag, 'A', `„${id}“ ist auf der ganzen Prüfseite ein Link`)
  }
  // Die TERMINE-Tafel steht (can_moderate true, Chat nicht gewählt).
  assert.equal(knopfMit(s.host, /Alle freigeben/) !== undefined, true, 'die Tafel ist da')
  s.abbaum()
})

test('CHAT-6-UI-2/D (SOLL 1): der Chat steht genau EINMAL — kein zweiter, toter Zweig', async () => {
  const quelle = readFileSync(new URL('../src/diakonos/pages/Moderation.vue', import.meta.url), 'utf8')
  const vorlage = quelle.slice(0, quelle.indexOf('<script'))
  assert.equal((vorlage.match(/<ChatMeldungen/g) || []).length, 1,
    'eine Meldungsliste, nicht zwei (der `v-if="!canModerate"`-Block ist weg)')
  assert.doesNotMatch(vorlage, /v-if="!canModerate"/, 'der unerreichbare Zweig ist entfernt')

  // Verhalten: mit Termine-Recht und gewähltem Chat-Reiter steht die Liste EINMAL.
  const s = await moderationMontieren({
    hash: '#/kalender/pruefen?reiter=chat',
    server: { meldungen_liste: () => ({ meldungen: [meldungForm()], offen: 1 }) },
  })
  assert.equal(s.host.querySelectorAll('.dk-mpanel').length, 1, 'eine Liste, kein Duplikat')
  s.abbaum()
})

test('CHAT-6-UI-2/D (SOLL 2): „‹ Termine“ am Handy nur mit Kalender-Recht', async () => {
  // Ohne Kalender-Recht: der Chat ist die Seite, aber der Rückweg auf die
  // Termine-Tafel wäre ein toter Weg — er fehlt.
  const ohne = await moderationMontieren({
    handy: true,
    server: {
      get_session_info: () => ({ can_moderate: false, chat_moderieren: true }),
      meldungen_liste: () => ({ meldungen: [meldungForm()], offen: 1 }),
    },
  })
  const rueckwege = () => texte(ohne.host, '.dk-moderation-mobile-back')
  assert.ok(!rueckwege().includes('Termine'),
    'ohne Kalender-Recht kein „‹ Termine“: ' + rueckwege().join(' | '))
  ohne.abbaum()

  // Mit beiden Rechten und gewähltem Chat-Reiter: der Rückweg steht da.
  const mit = await moderationMontieren({
    handy: true,
    hash: '#/kalender/pruefen?reiter=chat',
    server: { meldungen_liste: () => ({ meldungen: [meldungForm()], offen: 1 }) },
  })
  assert.ok(texte(mit.host, '.dk-moderation-mobile-back').includes('Termine'),
    'mit Kalender-Recht führt „‹ Termine“ zurück')
  mit.abbaum()
})

test('CHAT-6-UI-2/E (SOLL 3): Netzfehler beim ersten Laden → Fehlerseite mit „Erneut versuchen“', async () => {
  let versuche = 0
  const s = await moderationMontieren({
    server: {
      get_session_info: () => {
        versuche += 1
        if (versuche === 1) throw fehler(503, 'Der Server antwortet gerade nicht.')
        return { can_moderate: true, chat_moderieren: true }
      },
      meldungen_liste: () => { throw fehler(503, 'Der Server antwortet gerade nicht.') },
    },
  })
  // NICHT die Sperrseite: der Fehler ist keine Rechtelage.
  assert.doesNotMatch(s.host.textContent, /Zugriff verweigert/,
    'ein Serverfehler ist kein „Zugriff verweigert“')
  const alarm = s.host.querySelector('[role="alert"]')
  assert.ok(alarm, 'die Fehlerseite meldet sich an (role="alert")')
  assert.match(alarm.textContent, /Server|antwortet|Verbindung/, 'im Klartext: ' + alarm.textContent.trim())
  const erneut = knopfMit(s.host, /Erneut versuchen/)
  assert.ok(erneut, '„Erneut versuchen“ steht da')
  assert.equal(erneut.classList.contains('dk-ui-btn'), true, 'als DkButton, keine Eigenklasse')

  // Der Knopf wiederholt BEIDE Abrufe — jetzt mit Antwort.
  erneut.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true, cancelable: true }))
  await rendern(6)
  await warte(16)
  await rendern(6)
  assert.ok(versuche >= 2, 'der zweite Versuch fragt den Server erneut')
  assert.equal(s.host.querySelector('[role="alert"]') === null
    || !/Gerade nicht erreichbar/.test(s.host.textContent), true,
  'die Fehlerseite ist weg, sobald eine Antwort da ist')
  s.abbaum()
})

test('CHAT-6-UI-2/E (SOLL 3): ein 403 ist KEIN Fehler — Moderator sieht seine Tafel', async () => {
  const s = await moderationMontieren({
    server: {
      get_session_info: () => ({ can_moderate: true, chat_moderieren: true }),
      meldungen_liste: () => { throw fehler(403, 'Kein Zugriff') },
    },
  })
  assert.equal(s.host.querySelector('[role="alert"]'), null, 'kein Fehleralarm')
  assert.doesNotMatch(s.host.textContent, /Gerade nicht erreichbar/, 'keine Fehlerseite')
  assert.ok(knopfMit(s.host, /Alle freigeben/), 'die Termine-Tafel steht')
  const ids = reiterIds(s.host).map((r) => r.id)
  assert.ok(!ids.includes('chat'), 'ohne Chat-Recht kein Reiter')
  s.abbaum()
})

test('CHAT-6-UI-2/F (SOLL 4): erledigt/verworfen werden genau EINMAL geholt, auch bei leerer Liste', async () => {
  const s = await moderationMontieren({
    hash: '#/kalender/pruefen?reiter=chat',
    server: {
      meldungen_liste: ({ stand }) => (stand === 'offen'
        ? { meldungen: [meldungForm()], offen: 1 }
        : { meldungen: [], offen: 1 }),
    },
  })
  const staende = () => s.aufrufe.filter((a) => a.methode === 'chat.meldungen_liste')
    .map((a) => a.parameter?.stand)
  assert.deepEqual(staende(), ['offen'], 'beim Laden nur die Arbeitsliste')

  // Aufklappen: holt erledigt + verworfen.
  const schalter = knopfMit(s.host, /Erledigte Meldungen/)
  assert.ok(schalter, 'der Umschalter steht da')
  schalter.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true, cancelable: true }))
  await rendern(6)
  await warte(12)
  assert.deepEqual(staende().slice(1).sort(), ['erledigt', 'verworfen'])

  // Die erledigte Liste ist LEER. Nochmal klicken → KEIN weiterer Abruf.
  const zu = knopfMit(s.host, /Erledigte ausblenden/)
  if (zu) {
    zu.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true, cancelable: true }))
    await rendern(4)
    await warte(6)
  }
  const wieder = knopfMit(s.host, /Erledigte Meldungen/)
  assert.ok(wieder, 'der Umschalter ist wieder da')
  wieder.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true, cancelable: true }))
  await rendern(6)
  await warte(12)
  assert.equal(staende().length, 3,
    'kein Wiederholabruf bei leerer Liste: ' + staende().join(','))
  s.abbaum()
})

test('CHAT-6-UI-2/F (SOLL 5): ein 403 bei erledigt/verworfen nimmt das Chat-Recht NICHT weg', async () => {
  const s = await moderationMontieren({
    hash: '#/kalender/pruefen?reiter=chat',
    server: {
      meldungen_liste: ({ stand }) => {
        if (stand === 'offen') return { meldungen: [meldungForm()], offen: 1 }
        throw fehler(403, 'Kein Zugriff')
      },
    },
  })
  const schalter = knopfMit(s.host, /Erledigte Meldungen/)
  assert.ok(schalter)
  schalter.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true, cancelable: true }))
  await rendern(6)
  await warte(12)

  // Die Liste steht weiterhin — der Reiter ist nicht verschwunden.
  assert.ok(s.host.querySelector('.dk-mpanel'), 'die Meldungsliste bleibt')
  assert.ok(s.host.querySelector('[data-reiter="chat"]'), 'der Reiter „Chat“ bleibt')
  assert.doesNotMatch(s.host.textContent, /Zugriff verweigert/,
    'ein 403 im zweiten Abschnitt sperrt die Seite nicht')
  // Der Hinweis steht im Abschnitt (role="alert" der Liste).
  const hinweis = s.host.querySelector('.dk-mpanel [role="alert"], .dk-mpanel-fehler')
  assert.ok(hinweis, 'der Fehlerhinweis steht im Abschnitt')
  assert.equal(s.merker.useChatPruefRecht().recht.value, true,
    'der Merker bleibt auf „darf moderieren“')
  s.abbaum()
})

test('CHAT-6-UI-3/D (MUSS 1): ein „nein“ der Sitzungs-Antwort schreibt den Merker', async () => {
  // Review R1: Seit der Einstieg aus `get_session_info` kommt, gab es keinen
  // 403 der Liste mehr, der den Merker auf „nein“ setzte — der Kalender hätte
  // den Reiter weiter gezeigt. Der Merker steht vorher bewusst auf „darf“.
  const s = await moderationMontieren({
    server: {
      get_session_info: () => ({ can_moderate: true, chat_moderieren: false }),
    },
    merkerVorher: { recht: true, zahl: 2 },
  })
  const sicht = s.merker.useChatPruefRecht()
  assert.equal(sicht.recht.value, false, 'die Antwort „nein“ steht im geteilten Merker')
  assert.equal(sicht.zahl.value, null, 'ohne Recht keine Zahl')
  assert.equal(s.aufrufe.filter((a) => a.methode === 'chat.meldungen_liste').length, 0,
    'ohne Chat-Recht kein Listen-Abruf')
  s.abbaum()
})

test('CHAT-6-UI-3/D (MUSS 1): ein Netzfehler schreibt NICHTS in den Merker', async () => {
  // Ein Fehler ist keine Antwort „nein“ — sonst verlöre die Sitzung das Recht
  // wegen eines Aussetzers. Der Merker bleibt auf seinem vorigen „darf“.
  const s = await moderationMontieren({
    server: {
      get_session_info: () => { throw fehler(503, 'Der Server antwortet gerade nicht.') },
    },
  })
  assert.equal(s.merker.useChatPruefRecht().recht.value, null,
    'kein „nein“ aus einem Fehler — der Merker bleibt unentschieden')
  s.abbaum()
})
