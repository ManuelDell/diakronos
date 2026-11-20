/**
 * CHAT-6-UI-3 — Prüfseite „Chat“: Handy-Zeile und Merker (Vue 3, Frontend).
 *
 * Karte t_1f9d399f. Geprüft wird VERHALTEN (gemountet, mit Netzattrappe):
 *
 *   A  Merker (`composables/chatPruefRecht.mjs`): der EINSTIEG liest
 *      `get_session_info().chat_moderieren` — ohne Recht geht KEIN
 *      `chat.meldungen_liste` hinaus; mit Recht genau EINE Liste für die
 *      Zahl. Ein Netz-/5xx-Fehler wird nicht als „geprüft“ gemerkt (die
 *      Sitzung versucht es wieder), ein 403 auf die Liste nimmt das Recht
 *      zurück.
 *   B  Handy-Zeile „Meldungen aus dem Chat“ (`KalenderPruefZeile.vue` mit
 *      Props `ziel`/`ariaText`): href = `MELDUNGEN_ADRESSE`
 *      (`#/kalender/pruefen?reiter=chat`), aria-label nennt die Zeile samt
 *      Zahl („Meldungen aus dem Chat (3) — öffnen“). Die A10-Zeile behält
 *      Ziel und Vorlesetext (Default). Am Desktop gibt es die zweite Zeile
 *      nicht — dort steht der Reiter.
 *   C  Unbekannte Zahl ist KEINE 0: `Kalender.vue` reicht `null` durch,
 *      `KronosTopbar.chatZahl` nimmt `[Number, null]`, der Reiter zeigt dann
 *      keine Zahl (auch bei einer bekannten 0 nicht).
 *
 * Lauf (eine Datei je Aufruf, TZ=Europe/Berlin):
 *   TMPDIR=$(mktemp -d) TZ=Europe/Berlin node --test tests/chat6ui3-handy-zeile-merker.test.mjs
 */
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
  const abbaum = () => {
    try { app.unmount() } catch { /* egal */ }
    try { host.remove() } catch { /* egal */ }
  }
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
// A · Merker: Einstieg über `chat_moderieren`, Liste NUR mit Recht
// ════════════════════════════════════════════════════════════════════════════

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

test('CHAT-6-UI-3/A: ohne Recht fragt der Einstieg KEINE Liste', async () => {
  const { mod, aufrufe, sicht } = await merkerMit(() => ({ chat_moderieren: false }))
  const lage = await mod.pruefen()
  assert.equal(lage.recht, false)
  assert.equal(lage.zahl, null, 'keine erfundene 0')
  assert.deepEqual(aufrufe.map((a) => a.methode),
    ['diakronos.kronos.api.permissions.get_session_info'],
    'ein Normalnutzer löst KEINEN meldungen_liste-Aufruf aus')
  assert.equal(sicht.geprueft.value, true)
})

test('CHAT-6-UI-3/A: mit Recht EINE Liste, danach merkt die Sitzung', async () => {
  const { mod, aufrufe, sicht } = await merkerMit(() => ({ chat_moderieren: true }))
  // Die Liste liefert die Zahl — der Test antwortet je Methode.
  globalThis.__MERKER_SERVER = ({ methode }) => (String(methode).endsWith('get_session_info')
    ? { chat_moderieren: true }
    : { meldungen: [], offen: 2 })
  await mod.pruefen()
  await mod.pruefen()
  await mod.pruefen()
  const listen = aufrufe.filter((a) => a.methode === 'chat.meldungen_liste')
  assert.equal(listen.length, 1, 'genau EIN Listen-Abruf für die Zahl')
  assert.deepEqual(listen[0].parameter, { stand: 'offen' })
  assert.equal(sicht.zahl.value, 2)
})

test('CHAT-6-UI-3/A: Netz-/5xx beim Einstieg wird NICHT als „geprüft“ gemerkt', async () => {
  const { mod, aufrufe, sicht } = await merkerMit(() => { throw fehler(503, 'Der Server antwortet gerade nicht.') })
  const lage = await mod.pruefen()
  assert.equal(lage.recht, null, 'ein Serverfehler ist keine Rechtelage')
  assert.equal(sicht.geprueft.value, false, 'die Sitzung darf es später erneut versuchen')
  assert.match(lage.fehler, /Server|antwortet/)
  assert.equal(aufrufe.filter((a) => a.methode === 'chat.meldungen_liste').length, 0,
    'ohne Rechtelage keine Liste')
})

test('CHAT-6-UI-3/A: 403 auf die LISTE nimmt das Recht zurück', async () => {
  const { mod, sicht } = await merkerMit(({ methode }) => {
    if (String(methode).endsWith('get_session_info')) return { chat_moderieren: true }
    throw fehler(403, 'Kein Zugriff')
  })
  const lage = await mod.pruefen()
  assert.equal(lage.recht, false, 'die harte Antwort der Liste gilt')
  assert.equal(sicht.zahl.value, null)
})

// ════════════════════════════════════════════════════════════════════════════
// B · Handy-Zeile „Meldungen aus dem Chat“: href und aria-label
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

/**
 * Boot-Objekt mit Kalender-Recht. A10 liest `can_moderate` aus dem BOOT
 * (nicht aus der Sitzungs-Antwort): ohne diesen Schlüssel stünde weder die
 * Termin-Zeile noch der Reiter „Zu prüfen“.
 */
const BOOT_MODERATOR = {
  roles: ['Moderator'], is_admin: false, can_moderate: true,
  module_sichtbar: ['kalender', 'chat'],
}

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

async function kalenderMontieren({ server = {}, handy = false, boot = null } = {}) {
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
    if (kurz === 'get_session_info') return { can_moderate: true, chat_moderieren: true }
    if (kurz === 'getModerationCount' || kurz === 'get_moderation_count') return { count: 0 }
    // A10: `pruefZeilenLaden` holt die goldenen Punkte — ohne diese Antwort
    // wirft `mitAntwort` und der Aufbau bricht ab (`efehl` statt Zeilen).
    if (kurz === 'get_kanban_board_data') return { vorschlaege: [], konflikte: [] }
    if (kurz === 'meldungen_liste') return { meldungen: [], offen: 0 }
    if (kurz === 'get_kalender_verwaltung') return {}
    if (kurz === 'get_current_user_context') return {}
    if (kurz === 'get_accessible_calendars') return []
    if (kurz === 'get_calendar_events') return []
    if (kurz === 'meine_gespraeche') return { gespraeche: [] }
    return {}
  }
  dom.window.__DIakonosBOOT = boot || { roles: ['Moderator'], is_admin: false, module_sichtbar: ['kalender', 'chat'] }
  dom.window.location.hash = '#/kalender'
  handyAbfrage(handy)

  const merker = await import(pathToFileURL(
    baum('composables/chatPruefRecht.mjs', { frisch: true, ordner }),
  ).href)
  merker.zuruecksetzen()

  const mod = (await import(pathToFileURL(baum('pages/Kalender.vue', { frisch: true, ordner })).href)).default
  const gemountet = await mounten(mod, {})
  await rendern(6)
  await warte(16)
  await rendern(6)
  return { ...gemountet, aufrufe, merker }
}

/** Die Chat-Zeile in der Handy-Lage (Text „Meldungen aus dem Chat“). */
const chatZeile = (host) => [...host.querySelectorAll('.dk-pruefzeile')]
  .find((e) => /Meldungen aus dem Chat/.test(e.textContent))

test('CHAT-6-UI-3/B: Chat-Zeile führt in den CHAT-Zweig, nicht in die Terminliste', async () => {
  const s = await kalenderMontieren({
    handy: true,
    server: {
      get_session_info: () => ({ can_moderate: true, chat_moderieren: true }),
      meldungen_liste: () => ({ meldungen: [], offen: 3 }),
    },
  })
  const zeile = chatZeile(s.host)
  assert.ok(zeile, 'die Zeile steht am Handy')
  assert.equal(zeile.getAttribute('href'), '#/kalender/pruefen?reiter=chat',
    'Ziel ist MELDUNGEN_ADRESSE (Chat-Zweig der Tafel)')
  assert.notEqual(zeile.getAttribute('href'), '#/kalender/pruefen', 'NICHT die Terminliste')
  assert.equal(zeile.getAttribute('aria-label'), 'Meldungen aus dem Chat (3) — öffnen',
    'der Vorlesetext nennt die Chat-Zeile samt Zahl')
  s.abbaum()
})

test('CHAT-6-UI-3/B: die Termin-Zeile behält Ziel und Vorlesetext (Default)', async () => {
  // `can_moderate` steht im Boot-Objekt (A10); der Kalender-Admin offene
  // Vorschläge bei `getModerationCount` (bekannte Zahl 2).
  const s = await kalenderMontieren({
    handy: true,
    boot: BOOT_MODERATOR,
    server: {
      get_session_info: () => ({ can_moderate: true, chat_moderieren: true }),
      get_moderation_count: () => ({ count: 2 }),
    },
  })
  const zeilen = [...s.host.querySelectorAll('.dk-pruefzeile')]
    .filter((e) => /Von Gruppen eingetragen/.test(e.textContent))
  assert.equal(zeilen.length >= 1, true, 'die A10-Zeile steht: ' + zeilen.length)
  assert.equal(zeilen[0].getAttribute('href'), '#/kalender/pruefen')
  assert.equal(zeilen[0].getAttribute('aria-label'), 'Zu prüfen (2) · Von Gruppen eingetragen — Prüfliste öffnen')
  s.abbaum()
})

test('CHAT-6-UI-3/B: am Desktop keine zweite Zeile — der Reiter steht am Kopf', async () => {
  const s = await kalenderMontieren({
    handy: false,
    boot: BOOT_MODERATOR,
    server: {
      get_session_info: () => ({ can_moderate: true, chat_moderieren: true }),
      meldungen_liste: () => ({ meldungen: [], offen: 2 }),
    },
  })
  assert.equal(chatZeile(s.host), undefined, 'am Desktop keine Handy-Zeile')
  const chat = s.host.querySelector('[data-reiter="chat"]')
  assert.ok(chat, 'der Chat-Reiter steht am Kopf')
  assert.equal(chat.getAttribute('href'), '#/kalender/pruefen?reiter=chat')
  s.abbaum()
})

test('CHAT-6-UI-3/C: unbekannte Zahl ist KEINE 0 — der Reiter zeigt keine Zahl', async () => {
  const s = await kalenderMontieren({
    handy: false,
    boot: BOOT_MODERATOR,
    server: {
      get_session_info: () => ({ can_moderate: true, chat_moderieren: true }),
      meldungen_liste: () => { throw fehler(500, 'Der Server antwortet gerade nicht.') },
    },
  })
  const chat = s.host.querySelector('[data-reiter="chat"]')
  assert.ok(chat, 'das Recht steht — der Reiter steht')
  assert.equal(chat.querySelector('.kal-reiter-zahl'), null,
    'ohne bekannte Zahl steht keine im Reiter: ' + chat.textContent.trim())
  assert.doesNotMatch(chat.textContent, /0/, 'nie eine erfundene 0')
  assert.equal(s.merker.useChatPruefRecht().zahl.value, null)
  s.abbaum()
})

test('CHAT-6-UI-3/C: mit 0 offenen Meldungen bleibt der Reiter ohne Zahl', async () => {
  const s = await kalenderMontieren({
    handy: false,
    boot: BOOT_MODERATOR,
    server: {
      get_session_info: () => ({ can_moderate: true, chat_moderieren: true }),
      meldungen_liste: () => ({ meldungen: [], offen: 0 }),
    },
  })
  const chat = s.host.querySelector('[data-reiter="chat"]')
  assert.ok(chat)
  assert.equal(chat.querySelector('.kal-reiter-zahl'), null)
  s.abbaum()
})

// ════════════════════════════════════════════════════════════════════════════
// D · Review R1: Boot-Flag statt eigenem Sitzungs-Abruf (SOLL 1)
// ════════════════════════════════════════════════════════════════════════════

/** Boot-Objekt MIT (oder ohne) `chat_moderieren` — der neue Weg. */
const bootMit = (chat) => ({
  roles: ['Moderator'], is_admin: false, can_moderate: false,
  chat_moderieren: chat, module_sichtbar: ['kalender', 'chat'],
})

test('CHAT-6-UI-3/D: Normalnutzer — Boot sagt nein, KEIN get_session_info, keine Liste', async () => {
  const s = await kalenderMontieren({ handy: true, boot: bootMit(false) })
  const methoden = s.aufrufe.map((a) => a.methode)
  assert.equal(methoden.filter((m) => String(m).endsWith('get_session_info')).length, 0,
    'kein eigener get_session_info-Abruf beim Kalender-Aufbau: ' + methoden.join(', '))
  assert.equal(methoden.filter((m) => m === 'chat.meldungen_liste').length, 0,
    'ohne Chat-Recht keine Liste (und keine Zahl)')
  assert.equal(chatZeile(s.host), undefined, 'ohne Recht keine Chat-Zeile')
  assert.equal(s.merker.useChatPruefRecht().recht.value, false, 'der Merker kennt das Nein aus dem Boot')
  s.abbaum()
})

test('CHAT-6-UI-3/D: mit Chat-Recht aus dem Boot EINE Liste — ohne get_session_info', async () => {
  const s = await kalenderMontieren({
    handy: true,
    boot: bootMit(true),
    server: { meldungen_liste: () => ({ meldungen: [], offen: 4 }) },
  })
  const methoden = s.aufrufe.map((a) => a.methode)
  assert.equal(methoden.filter((m) => String(m).endsWith('get_session_info')).length, 0,
    'kein eigener get_session_info-Abruf: ' + methoden.join(', '))
  const listen = s.aufrufe.filter((a) => a.methode === 'chat.meldungen_liste')
  assert.equal(listen.length, 1, 'genau EIN Listen-Abruf für die Zahl')
  const zeile = chatZeile(s.host)
  assert.ok(zeile, 'die Chat-Zeile steht')
  assert.equal(zeile.getAttribute('aria-label'), 'Meldungen aus dem Chat (4) — öffnen')
  s.abbaum()
})
