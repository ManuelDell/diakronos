/**
 * CHAT-10b — Benachrichtigungen aufs Gerät (Web-Push): Service Worker,
 * Anmeldung in den Einstellungen, Abmelden beim Logout.
 *
 * Geprüft wird VERHALTEN, in vier Abschnitten:
 *
 *   A  Die Regeln (`pages/einstellungen/benachrichtigungen.mjs`, ohne DOM):
 *      die Sätze, der Zustand (Server aus / Browser kann nicht / verweigert /
 *      an / aus), die Schlüssel-Umrechnung Base64url → `Uint8Array` (auch der
 *      ungültige Fall) und die Fähigkeitsfrage.
 *   B  `Benachrichtigungen.vue` gemountet (echte `apiCall`/`apiGet`-Attrappen,
 *      Attrappen für `navigator.serviceWorker`, `PushManager`, `Notification`):
 *      `aktiv: false` → ruhiger Satz ohne Schalter; Browser kann es nicht →
 *      Satz; verweigert → Satz statt Frage; Schalter an → `requestPermission`
 *      NUR nach dem Klick, `subscribe` mit dem Schlüssel, POST `push.anmelden`;
 *      Schalter aus → `unsubscribe` und POST `push.abmelden`.
 *   C  `public/sw.js` als Modul in einer `vm` mit `self`-Attrappe: `push`
 *      zeigt NUR `titel`/`text`, eine ungültige Nutzlast ergibt die neutrale
 *      Meldung, `notificationclick` akzeptiert nur `#/nachrichten`-Ziele
 *      (`javascript:…` und `https://evil.example` ⇒ `#/nachrichten`), öffnet
 *      nie eine fremde Herkunft und fasst keine Anfrage an (kein `fetch`).
 *   D  Die Einbindung: Abschnitt in `pages/Einstellungen.vue` ohne
 *      Verwaltungsstufe, Adresse im Router, kein Admin-Wächter, Stichworte
 *      der Suche — und beim Abmelden (`useAbmelden.js`) geht
 *      `push.abmelden` VOR dem Logout hinaus, Fehler werden verworfen.
 *
 * Lauf (cwd = frontend/):  TZ=Europe/Berlin node --test tests/chat10b-push.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync, mkdtempSync, writeFileSync, rmSync, mkdirSync, statSync } from 'node:fs'
import { join, dirname, resolve, basename } from 'node:path'
import { tmpdir } from 'node:os'
import { pathToFileURL } from 'node:url'
import test from 'node:test'
import { SeitenAbbau } from './helpers/seitenAbbau.mjs'
import vm from 'node:vm'
import { JSDOM } from 'jsdom'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'

// ── Browser-Attrappe (wie in den übrigen gemounteten Tests) ────────────────
const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
for (const schluessel of ['window', 'document', 'Node', 'Element', 'HTMLElement', 'Event',
  'MouseEvent', 'SVGElement', 'CSS', 'CustomEvent', 'FormData', 'HTMLInputElement',
  'HTMLSelectElement', 'HTMLTextAreaElement', 'requestAnimationFrame', 'getComputedStyle',
  'MutationObserver', 'KeyboardEvent', 'FocusEvent', 'Document', 'ShadowRoot',
  'HTMLAnchorElement', 'HTMLButtonElement', 'HTMLDivElement', 'localStorage',
  'sessionStorage', 'location', 'URLSearchParams', 'PopStateEvent']) {
  globalThis[schluessel] = dom.window[schluessel]
}
globalThis.requestAnimationFrame = dom.window.requestAnimationFrame
  || ((fn) => setTimeout(() => fn(Date.now()), 0))
Object.defineProperty(dom.window.document, 'hidden', { configurable: true, get: () => false })
Object.defineProperty(dom.window.document, 'visibilityState', { configurable: true, get: () => 'visible' })

const VUE_URL = import.meta.resolve('vue')
const SRC_ROOT = new URL('../src/', import.meta.url)
const SRC = new URL('../src/diakonos/', import.meta.url)
const lies = (p) => readFileSync(new URL(p, SRC), 'utf8')
const FRONTEND = new URL('../', import.meta.url)

const TMP = mkdtempSync(join(tmpdir(), 'chat10b-'))
test.after(() => rmSync(TMP, { recursive: true, force: true }))

/** Quelltext ohne Kommentare — Prüfungen am Code, nicht an Erklärungen. */
function ohneKommentare(text) {
  return text
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/^\s*\/\/.*$/gm, '')
}

// ════════════════════════════════════════════════════════════════════════════
// A · Die Regeln (ohne DOM)
// ════════════════════════════════════════════════════════════════════════════
const B = await import(new URL('pages/einstellungen/benachrichtigungen.mjs', SRC).href)

test('CHAT-10b/A: die Sätze sagen, was passiert — ohne Fachjargon', () => {
  assert.equal(B.PUSH_TITEL, 'Benachrichtigungen aufs Gerät')
  assert.equal(B.PUSH_SCHALTER, 'Auf diesem Gerät benachrichtigen')
  assert.equal(B.PUSH_SERVER_AUS,
    'Auf diesem Server sind Benachrichtigungen aufs Gerät nicht eingerichtet.')
  assert.equal(B.PUSH_BROWSER_FEHLT, 'Dieser Browser unterstützt das nicht.')
  assert.match(B.PUSH_VERWEIGERT, /Berechtigung|erlauben|Einstellungen des Browsers/i)
  assert.equal(B.PUSH_INHALTSSATZ,
    'Die Benachrichtigung zeigt nur, in welchem Gespräch etwas Neues ist — nie den Inhalt.')
  // iPhone-Satz: EIN sachlicher Satz, kein Werbetext.
  assert.match(B.PUSH_IPHONE_HINWEIS, /Home-Bildschirm/)
  assert.equal(B.PUSH_IPHONE_HINWEIS.split('.').filter((t) => t.trim()).length, 1)
  // „Push“ ist ein Wort der Technik — in KEINEM sichtbaren Text.
  const sichtbar = [B.PUSH_TITEL, B.PUSH_EINLEITUNG, B.PUSH_SCHALTER, B.PUSH_SERVER_AUS,
    B.PUSH_BROWSER_FEHLT, B.PUSH_VERWEIGERT, B.PUSH_INHALTSSATZ, B.PUSH_IPHONE_HINWEIS,
    B.PUSH_FEHLER_AUS, B.PUSH_FEHLER_EIN].join(' ')
  assert.doesNotMatch(sichtbar, /\bPush\b/i)
  assert.doesNotMatch(sichtbar, /VAPID|Subscription|Subskription|\bAPI\b/i)
  // R1, Punkt 6: EINE Fehlerformulierung beim Anschalten — `PUSH_SERVER_WEG`
  // ist derselbe Satz, keine dritte Variante.
  assert.equal(B.PUSH_SERVER_WEG, B.PUSH_FEHLER_EIN)
})

test('CHAT-10b/A: der Zustand folgt der Reihenfolge Server – Browser – Berechtigung – Abo', () => {
  // Server kennt keine Schlüssel: das schlägt alles andere.
  assert.equal(B.zustand({ serverAktiv: false, browserKann: false }), 'server_aus')
  assert.equal(B.zustand({ serverAktiv: false, berechtigung: 'denied' }), 'server_aus')
  // Browser kann es nicht.
  assert.equal(B.zustand({ serverAktiv: true, browserKann: false }), 'browser_aus')
  // Gesperrt: auch mit Abonnement bleibt es „verweigert“ (kein Schalter).
  assert.equal(B.zustand({ serverAktiv: true, berechtigung: 'denied', abonniert: true, serverAn: true }), 'verweigert')
  // Schalter: „an“ NUR, wenn Abo UND Server es kennt.
  assert.equal(B.zustand({ serverAktiv: true, berechtigung: 'granted', abonniert: true, serverAn: true }), 'an')
  assert.equal(B.zustand({ serverAktiv: true, berechtigung: 'granted', abonniert: true, serverAn: false }), 'aus')
  assert.equal(B.zustand({ serverAktiv: true, berechtigung: 'granted', abonniert: false }), 'aus')
  assert.equal(B.zustand(), 'server_aus')
  // Der Schalter erscheint nur in den beiden Schaltzuständen.
  assert.equal(B.schalterSichtbar('an'), true)
  assert.equal(B.schalterSichtbar('aus'), true)
  for (const z of ['server_aus', 'browser_aus', 'verweigert']) {
    assert.equal(B.schalterSichtbar(z), false, z + ' darf keinen Schalter zeigen')
  }
})

test('CHAT-10b/A: Base64url wird zu einem echten Schlüssel — Ungültiges wird abgelehnt', () => {
  // 65 Bytes, beginnend mit 0x04 = der unkomprimierte P-256-Punkt.
  const roh = new Uint8Array(65)
  roh[0] = 4
  for (let i = 1; i < 65; i += 1) roh[i] = i
  let bin = ''
  for (const b of roh) bin += String.fromCharCode(b)
  const standard = Buffer.from(bin, 'binary').toString('base64')
  const urlForm = standard.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')

  const bytes = B.schluesselBytes(urlForm)
  assert.ok(bytes instanceof Uint8Array)
  assert.equal(bytes.length, 65)
  assert.equal(bytes[0], 4)
  assert.deepEqual([...bytes], [...roh], 'derselbe Schlüssel, Byte für Byte')
  // Beide Formen ergeben dasselbe — die Auffüllung darf fehlen ODER stimmen.
  assert.deepEqual([...B.schluesselBytes(standard)], [...roh])
  // Standardform hat EIN Füllzeichen; die Base64url-Form mit genau diesem
  // Füllzeichen ergibt denselben Schlüssel.
  const urlMitFuellung = standard.replace(/\+/g, '-').replace(/\//g, '_')
  assert.deepEqual([...B.schluesselBytes(urlMitFuellung)], [...roh])
  // Falsche Auffüllung (zu viele Zeichen) ist KEIN gültiger Schlüssel.
  assert.equal(B.schluesselBytes(urlForm + '=='), null)

  // Nichts, was kein Schlüssel sein kann.
  assert.equal(B.schluesselBytes(''), null)
  assert.equal(B.schluesselBytes(null), null)
  assert.equal(B.schluesselBytes('kein base64!!'), null)
  assert.equal(B.schluesselBytes('AAAA'), null, 'zu kurz')
  // Falscher erster Punkt (0x05 statt 0x04) ist kein VAPID-Schlüssel.
  const falsch = new Uint8Array(roh)
  falsch[0] = 5
  const falschB64 = Buffer.from(falsch).toString('base64').replace(/\+/g, '-').replace(/\//g, '_')
  assert.equal(B.schluesselBytes(falschB64), null)
})

test('CHAT-10b/A: die Fähigkeitsfrage verlangt Service Worker, Benachrichtigungen und PushManager', () => {
  const voll = {
    navigator: { serviceWorker: { register() {} } },
    Notification: { requestPermission() {} },
    PushManager: function PushManager() {},
  }
  assert.equal(B.browserKannPush(voll), true)
  assert.equal(B.browserKannPush({ ...voll, PushManager: undefined }), false, 'ohne PushManager: nein')
  assert.equal(B.browserKannPush({ ...voll, Notification: undefined }), false, 'ohne Benachrichtigungen: nein')
  assert.equal(B.browserKannPush({ ...voll, navigator: {} }), false, 'ohne Service Worker: nein')
  assert.equal(B.browserKannPush({}), false)
  assert.equal(B.browserKannPush(null), false)

  // iPhone-Erkennung (nur für den Hinweis) — ohne Angabe keine Behauptung.
  assert.equal(B.istIphone({ navigator: { userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0)' } }), true)
  // Ein iPad im Desktop-Modus meldet sich als „Macintosh“ — er wird NICHT
  // erkannt (Touch-Fähigkeit ist im Haus kein Kriterium, FIX-6): dann bleibt
  // der Satz aus, statt auf einem Mac zu erscheinen.
  assert.equal(B.istIphone({ navigator: { userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)' } }), false)
  assert.equal(B.istIphone({ navigator: { userAgent: 'Mozilla/5.0 (X11; Linux x86_64)' } }), false)
  assert.equal(B.istIphone({}), false)
})

// ════════════════════════════════════════════════════════════════════════════
// B · Benachrichtigungen.vue gemountet
// ════════════════════════════════════════════════════════════════════════════

// ── SFC → ES-Modul ─────────────────────────────────────────────────────────
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
  for (const k of [abs, abs + '.mjs', abs + '.js', abs + '/index.mjs', abs + '/index.js']) {
    try { if (statSync(k).isFile()) return k } catch { /* weiter */ }
  }
  throw new Error('nicht gefunden: ' + abs)
}

function baum(seite, { ordner = null } = {}) {
  const unterordner = ordner || join(TMP, 'baum-' + Math.random().toString(36).slice(2))
  const NEU = new Map()
  const zielFuer = (quellDatei) => {
    const relativ = resolve(quellDatei).slice(resolve(SRC_ROOT.pathname, '..').length)
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

function mounten(baustein) {
  return import('vue').then(async (Vue) => {
    const host = document.createElement('div')
    document.body.appendChild(host)
    const warnungen = []
    const app = Vue.createApp({ render: () => Vue.h(baustein) })
    app.config.warnHandler = (m) => warnungen.push(m)
    app.config.errorHandler = (e) => warnungen.push(String(e && e.message))
    app.mount(host)
    await warte(10)
    return {
      host, app, warnungen,
      abbaum: seitenAbbau.anmelden(() => {
        try { app.unmount() } catch { /* egal */ }
        try { host.remove() } catch { /* egal */ }
      }),
    }
  })
}

/** Ein Klick, wie ihn der Browser auslöst. */
function klick(el) {
  assert.ok(el, 'das Element steht im DOM')
  el.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true, cancelable: true }))
}

const knopfMitText = (host, muster) => [...host.querySelectorAll('*')]
  .find((e) => muster.test(e.textContent.trim()) && e.children.length === 0)

/**
 * Browser-Attrappen für Push.
 *
 * `pushManager.subscribe` liefert ein Abo mit `toJSON()` — genau die Form, die
 * die Seite liest (`endpoint` + `keys.p256dh/auth`). Jeder Aufruf wird
 * mitgeschrieben, damit der Test PRÜFEN kann, was hinausging.
 *
 * WIE DER BROWSER WIRKLICH IST (Review R1, Punkt 2): Nach `register()` ist der
 * Worker NICHT sofort aktiv. `registrierung.active` ist deshalb `null`, bis
 * die Attrappe ihn (asynchron) aktiviert; `serviceWorker.ready` löst in
 * demselben Moment auf. `subscribe` wirft, solange kein aktiver Worker da ist
 * — genau wie der Browser („no active Service Worker“).
 */
function browserUmgebung({
  berechtigung = 'default', abo = null, abnehmen = 'granted', subscribeFehler = null,
  aktiviereVonSelbst = true, aktivierungsTakt = 2,
} = {}) {
  const rufe = []
  const registrierung = { pushManager: null, active: null, installing: null, waiting: null }
  const meldung = {
    permission: berechtigung,
    requestPermission: async () => {
      rufe.push('requestPermission')
      meldung.permission = abnehmen
      return abnehmen
    },
  }
  const bestehend = abo
  let bereitLoesen = null
  const bereit = new Promise((loese) => { bereitLoesen = loese })

  /** Den Worker aktivieren (wie der Browser nach dem Installieren). */
  function aktiviere() {
    registrierung.active = { state: 'activated', addEventListener() {} }
    registrierung.installing = null
    bereitLoesen(registrierung)
    rufe.push('aktiviert')
  }
  /** Ein Worker, der noch nicht aktiv ist, aber auf `activated` wechselt. */
  function installiere() {
    const zuhoerer = []
    registrierung.installing = {
      state: 'installing',
      addEventListener: (art, fn) => { if (art === 'statechange') zuhoerer.push(fn) },
    }
    if (!aktiviereVonSelbst) return
    setTimeout(() => {
      registrierung.installing.state = 'activated'
      aktiviere()
      zuhoerer.forEach((fn) => fn())
    }, aktivierungsTakt)
  }

  registrierung.pushManager = {
    getSubscription: async () => bestehend,
    subscribe: async (optionen) => {
      if (!registrierung.active) throw new Error('no active Service Worker')
      rufe.push({ subscribe: optionen })
      if (subscribeFehler) throw subscribeFehler
      return {
        endpoint: 'https://fcm.googleapis.com/wp/abc',
        toJSON: () => ({
          endpoint: 'https://fcm.googleapis.com/wp/abc',
          keys: { p256dh: 'p256dh-wert', auth: 'auth-wert' },
        }),
        unsubscribe: async () => { rufe.push('unsubscribe'); return true },
      }
    },
  }
  const serviceWorker = {
    ready: bereit,
    getRegistration: async () => (bestehend || rufe.some((r) => r && r.register) ? registrierung : null),
    register: async (pfad, optionen) => {
      rufe.push({ register: { pfad, scope: optionen && optionen.scope } })
      installiere()
      return registrierung
    },
  }
  return {
    serviceWorker, meldung, rufe, registrierung, aktiviere,
    istAktiv: () => Boolean(registrierung.active),
  }
}

/** Den globalen Browser für die Seite aufbauen (und danach zurückbauen). */
function setzeBrowser({ kann = true, sw = null, ...rest } = {}) {
  const env = sw || browserUmgebung(rest)
  const alterNavigator = globalThis.navigator
  const alteMeldung = globalThis.Notification
  const alterPush = globalThis.PushManager
  const nav = { userAgent: 'Mozilla/5.0 (X11; Linux x86_64)' }
  if (kann) nav.serviceWorker = env.serviceWorker
  Object.defineProperty(globalThis, 'navigator', { configurable: true, value: nav })
  if (kann) {
    globalThis.Notification = env.meldung
    globalThis.PushManager = function PushManager() {}
  } else {
    delete globalThis.Notification
    delete globalThis.PushManager
  }
  return {
    env,
    zurueck: () => {
      Object.defineProperty(globalThis, 'navigator', { configurable: true, value: alterNavigator })
      if (alteMeldung === undefined) delete globalThis.Notification
      else globalThis.Notification = alteMeldung
      if (alterPush === undefined) delete globalThis.PushManager
      else globalThis.PushManager = alterPush
    },
  }
}

/** Die Seite mit apiCall/apiGet-Attrappen montieren. */
async function seiteMontieren({ server = {}, browser = {} } = {}) {
  const ordner = join(TMP, 'seite-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  const api = join(ordner, 'api.mjs')
  writeFileSync(api, [
    'export async function apiCall(methode, parameter) {',
    '  globalThis.__PUSH_PUSH({ art: "call", methode, parameter })',
    '  return globalThis.__PUSH_SERVER({ art: "call", methode, parameter })',
    '}',
    'export async function apiGet(methode, parameter) {',
    '  globalThis.__PUSH_PUSH({ art: "get", methode, parameter })',
    '  return globalThis.__PUSH_SERVER({ art: "get", methode, parameter })',
    '}',
  ].join('\n'))
  const U2 = (rel) => pathToFileURL(SRC.pathname + rel).href
  umleitung.clear()
  umleitung.set(U2('composables/useApi.js'), pathToFileURL(api).href)

  const aufrufe = []
  globalThis.__PUSH_PUSH = (e) => aufrufe.push(e)
  globalThis.__PUSH_SERVER = ({ methode }) => {
    const kurz = String(methode).split('.').pop()
    if (typeof server[kurz] === 'function') return server[kurz]({ methode })
    if (kurz === 'schluessel') return { aktiv: true, public_key: TEST_SCHLUESSEL }
    if (kurz === 'anmelden') return { aktiv: true, angemeldet: true }
    if (kurz === 'abmelden') return { aktiv: true, abgemeldet: true }
    return {}
  }

  const b = setzeBrowser(browser)
  const mod = (await import(pathToFileURL(baum('pages/einstellungen/Benachrichtigungen.vue', { ordner })).href)).default
  const s = await mounten(mod)
  await rendern(6)
  await warte(14)
  await rendern(6)
  return { ...s, aufrufe, browser: b.env, zurueck: b.zurueck }
}

/** Ein gültiger VAPID-Schlüssel (65 Bytes, 0x04 …) als Base64url. */
const TEST_SCHLUESSEL = (() => {
  const roh = Buffer.alloc(65, 7)
  roh[0] = 4
  return roh.toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
})()

const checkbox = (host) => host.querySelector('input[type="checkbox"]')

test('CHAT-10b/B: `aktiv: false` zeigt den ruhigen Satz — und KEINEN Schalter', async () => {
  const s = await seiteMontieren({ server: { schluessel: () => ({ aktiv: false }) } })
  assert.match(s.host.textContent, /Benachrichtigungen aufs Gerät/, 'die Überschrift steht da')
  assert.match(s.host.textContent, /Auf diesem Server sind Benachrichtigungen aufs Gerät nicht eingerichtet\./)
  assert.equal(checkbox(s.host), null, 'ohne Server-Schlüssel kein Schalter')
  // Der Inhaltssatz steht trotzdem — er ist die Zusage des Abschnitts.
  assert.match(s.host.textContent, /nie den Inhalt/)
  // Und es wurde NICHT gefragt und nicht angemeldet.
  assert.deepEqual(s.browser.rufe, [], 'ohne Server-Schlüssel wird nichts gefragt oder abonniert')
  assert.equal(s.aufrufe.filter((a) => a.art === 'get').length, 1, 'genau EIN Schlüsselabruf')
  assert.equal(s.aufrufe[0].methode, 'diakronos_app.api.push.schluessel')
  assert.equal(s.warnungen.length, 0, s.warnungen.join(' | '))
  s.abbaum()
  s.zurueck()
})

test('CHAT-10b/B: dieser Browser kann es nicht -> Satz statt Schalter (mit iPhone-Hinweis)', async () => {
  const s = await seiteMontieren({ browser: { kann: false } })
  assert.match(s.host.textContent, /Dieser Browser unterstützt das nicht\./)
  assert.equal(checkbox(s.host), null, 'ohne Service Worker kein Schalter')
  assert.doesNotMatch(s.host.textContent, /Home-Bildschirm/, 'auf einem Linux-Desktop kein iPhone-Satz')
  s.abbaum()
  s.zurueck()
})

test('CHAT-10b/B: verweigert -> Satz statt Frage (kein erneutes Fragen)', async () => {
  const s = await seiteMontieren({
    browser: { berechtigung: 'denied', abo: null },
  })
  assert.match(s.host.textContent, /gesperrt/)
  assert.match(s.host.textContent, /Einstellungen des Browsers/)
  assert.equal(checkbox(s.host), null, 'bei „verweigert“ kein Schalter')
  assert.deepEqual(s.browser.rufe, [], 'bei „verweigert“ wird NICHT gefragt')
  s.abbaum()
  s.zurueck()
})

test('CHAT-10b/B: Schalter an -> requestPermission, subscribe mit Schlüssel, POST push.anmelden', async () => {
  const s = await seiteMontieren({ browser: { berechtigung: 'default', abo: null } })
  const box = checkbox(s.host)
  assert.ok(box, 'der Schalter steht da')
  assert.equal(box.checked, false, 'ohne Abonnement ist der Schalter aus')
  assert.equal(s.browser.rufe.includes('requestPermission'), false,
    'beim Öffnen wird NICHT gefragt — erst nach dem Klick')

  klick(box)
  for (let i = 0; i < 40 && !s.aufrufe.some((a) => /anmelden$/.test(a.methode)); i += 1) {
    await warte(3)
    await rendern(3)
  }

  const reihenfolge = s.browser.rufe.map((r) => (typeof r === 'string' ? r : Object.keys(r)[0]))
  assert.deepEqual(reihenfolge.slice(0, 4), ['requestPermission', 'register', 'aktiviert', 'subscribe'],
    'erst fragen, dann Worker holen + aktiv werden lassen, dann abonnieren: ' + JSON.stringify(reihenfolge))
  const reg = s.browser.rufe.find((r) => r && r.register)
  assert.equal(reg.register.pfad, '/sw.js', 'der Worker liegt an der Wurzel')
  // Der Scope ist das App-Verzeichnis — dort öffnet ein Klick das Gespräch.
  assert.equal(reg.register.scope, '/diakonos')

  const sub = s.browser.rufe.find((r) => r && r.subscribe).subscribe
  assert.equal(sub.userVisibleOnly, true, 'ohne sichtbare Meldung kein Abonnement')
  assert.ok(sub.applicationServerKey instanceof Uint8Array)
  assert.equal(sub.applicationServerKey.length, 65, 'der echte VAPID-Schlüssel (65 Bytes)')
  assert.equal(sub.applicationServerKey[0], 4)

  const anmeldung = s.aufrufe.filter((a) => /anmelden$/.test(a.methode)).at(-1)
  assert.ok(anmeldung, 'push.anmelden wurde gerufen')
  assert.equal(anmeldung.art, 'call', 'POST über apiCall')
  assert.equal(anmeldung.methode, 'diakronos_app.api.push.anmelden')
  assert.deepEqual(anmeldung.parameter, {
    endpoint: 'https://fcm.googleapis.com/wp/abc',
    p256dh: 'p256dh-wert',
    auth: 'auth-wert',
  })
  await rendern(4)
  assert.equal(checkbox(s.host).checked, true, 'der Schalter steht jetzt auf an')
  s.abbaum()
  s.zurueck()
})

test('CHAT-10b/B: das ERSTE Einschalten klappt mit EINEM Klick (Worker wird erst aktiv)', async () => {
  // Review R1, Punkt 2: nach `register()` ist der Worker nicht aktiv —
  // `subscribe` scheitert dann mit „no active Service Worker“. Die Seite muss
  // auf den aktiven Worker warten (ready/statechange) und DANN abonnieren.
  const s = await seiteMontieren({ browser: { berechtigung: 'default', abo: null } })
  const box = checkbox(s.host)
  assert.ok(box, 'der Schalter steht da')
  assert.equal(s.browser.istAktiv(), false, 'vor dem Klick gibt es keinen aktiven Worker')

  klick(box)
  for (let i = 0; i < 60 && !s.aufrufe.some((a) => /anmelden$/.test(a.methode)); i += 1) {
    await warte(3)
    await rendern(3)
  }

  const reihenfolge = s.browser.rufe.map((r) => (typeof r === 'string' ? r : Object.keys(r)[0]))
  assert.ok(reihenfolge.includes('aktiviert'), 'der Worker wurde aktiv: ' + JSON.stringify(reihenfolge))
  assert.ok(reihenfolge.indexOf('aktiviert') < reihenfolge.indexOf('subscribe'),
    'erst aktiv, dann abonnieren: ' + JSON.stringify(reihenfolge))
  const anmeldung = s.aufrufe.filter((a) => /anmelden$/.test(a.methode)).at(-1)
  assert.ok(anmeldung, 'push.anmelden wurde gerufen — kein „no active Service Worker“')
  await rendern(4)
  assert.equal(checkbox(s.host).checked, true, 'der Schalter steht auf an')
  assert.doesNotMatch(s.host.textContent, /konnte nicht angemeldet werden/,
    'kein Fehlertext beim ersten Einschalten')
  s.abbaum()
  s.zurueck()
})

test('CHAT-10b/B: Schalter aus -> unsubscribe und POST push.abmelden', async () => {
  const abo = {
    endpoint: 'https://fcm.googleapis.com/wp/abc',
    toJSON: () => ({ endpoint: 'https://fcm.googleapis.com/wp/abc', keys: { p256dh: 'p', auth: 'a' } }),
    unsubscribe: async () => { rufeUnsub(); return true },
  }
  let unsub = 0
  function rufeUnsub() { unsub += 1 }
  const s = await seiteMontieren({ browser: { berechtigung: 'granted', abo } })
  const box = checkbox(s.host)
  assert.ok(box, 'der Schalter steht da')
  assert.equal(box.checked, true, 'ein bestehendes Abo, das der Server kennt, ist „an“')

  klick(box)
  for (let i = 0; i < 40 && !s.aufrufe.some((a) => /abmelden$/.test(a.methode)); i += 1) {
    await warte(3)
    await rendern(3)
  }
  assert.equal(unsub, 1, 'das Abonnement im Browser wurde verworfen')
  const abmeldung = s.aufrufe.filter((a) => /abmelden$/.test(a.methode)).at(-1)
  assert.ok(abmeldung, 'push.abmelden wurde gerufen')
  assert.equal(abmeldung.art, 'call', 'POST über apiCall')
  assert.deepEqual(abmeldung.parameter, { endpoint: 'https://fcm.googleapis.com/wp/abc' })
  await rendern(4)
  assert.equal(checkbox(s.host).checked, false, 'der Schalter steht jetzt auf aus')
  s.abbaum()
  s.zurueck()
})

test('CHAT-10b/B: ein bestehendes Abo wird beim Öffnen beim Server nachgemeldet (ohne Frage)', async () => {
  const abo = {
    endpoint: 'https://fcm.googleapis.com/wp/abc',
    toJSON: () => ({ endpoint: 'https://fcm.googleapis.com/wp/abc', keys: { p256dh: 'p', auth: 'a' } }),
    unsubscribe: async () => true,
  }
  const s = await seiteMontieren({ browser: { berechtigung: 'granted', abo } })
  const anmeldung = s.aufrufe.filter((a) => /anmelden$/.test(a.methode)).at(-1)
  assert.ok(anmeldung, 'anmelden ist idempotent und meldet den Gerätestand nach')
  assert.deepEqual(anmeldung.parameter, {
    endpoint: 'https://fcm.googleapis.com/wp/abc', p256dh: 'p', auth: 'a',
  })
  assert.equal(s.browser.rufe.includes('requestPermission'), false, 'beim Öffnen wird NICHT gefragt')
  assert.equal(s.browser.rufe.some((r) => r && r.subscribe), false, 'beim Öffnen wird NICHT abonniert')
  s.abbaum()
  s.zurueck()
})

// ════════════════════════════════════════════════════════════════════════════
// C · public/sw.js in einer vm mit `self`-Attrappe
// ════════════════════════════════════════════════════════════════════════════
const SW_QUELLE = readFileSync(new URL('public/sw.js', FRONTEND), 'utf8')

/** Den Worker laden: `self` ist die Attrappe, Ereignisse werden gesammelt. */
function workerLaden() {
  const gezeigt = []
  const fokus = []
  const geoeffnet = []
  const zuhoerer = {}
  const self = {
    location: { origin: 'https://gemeinde.example.org' },
    registration: {
      // Der Geltungsbereich, den `Benachrichtigungen.vue` setzt (App-Verzeichnis).
      scope: 'https://gemeinde.example.org/diakonos/',
      showNotification: async (titel, optionen) => { gezeigt.push({ titel, optionen }) },
    },
    clients: {
      matchAll: async () => fenster,
      openWindow: async (url) => { geoeffnet.push(url); return {} },
      claim: async () => { uebernommen += 1 },
    },
    Notification: {},
    addEventListener: (art, fn) => { zuhoerer[art] = fn },
  }
  let fenster = []
  let uebernommen = 0
  const kontext = vm.createContext({
    self,
    Promise,
    JSON,
    String,
    Number,
    Object,
    Array,
    // Für die Herkunftsprüfung im Klick (`new URL(f.url)`).
    URL,
    // Ein ECHTER Fehler aus dieser Welt: `json()` wirft ihn SYNCHRON, und der
    // Worker muss ihn als Fehler erkennen (wie im Browser).
    Error: new Error('probe').constructor,
    console,
    // `fetch` gibt es bewusst NICHT: der Worker fasst keine Anfrage an.
  })
  vm.runInContext(SW_QUELLE, kontext, { filename: 'sw.js' })

  return {
    zuhoerer, gezeigt, geoeffnet, fokus,
    uebernommen: () => uebernommen,
    setzeFenster: (liste) => { fenster = liste },
    /**
     * Ein `push`-Ereignis auslösen und auf die Zusage warten.
     *
     * `PushMessageData.json()` ist im Browser SYNCHRON und wirft bei kaputtem
     * Inhalt sofort — die Attrappe tut genau das (R0-Attrappe gab ein
     * Versprechen zurück und verdeckte den Fehler).
     */
    async push(daten) {
      const offen = []
      let waitUntilGerufen = 0
      zuhoerer.push({
        data: daten === undefined
          ? null
          : {
            json: () => {
              if (daten instanceof globalThis.Error) throw daten
              return daten
            },
          },
        waitUntil: (p) => { waitUntilGerufen += 1; offen.push(p) },
      })
      assert.equal(waitUntilGerufen, 1, 'waitUntil wird SOFORT gerufen (sonst endet der Worker)')
      for (const p of offen) assert.ok(p && typeof p.then === 'function', 'waitUntil bekommt ein Versprechen')
      await Promise.all(offen)
      return offen
    },
    /** Ein `notificationclick`-Ereignis auslösen. */
    async klick(ziel) {
      const offen = []
      zuhoerer.notificationclick({
        notification: { data: ziel === undefined ? undefined : { ziel }, close() {} },
        waitUntil: (p) => offen.push(p),
      })
      await Promise.all(offen)
      return offen
    },
  }
}

test('CHAT-10b/C: push zeigt NUR titel und text — und das geprüfte Ziel', async () => {
  const w = workerLaden()
  await w.push({ titel: 'Neue Nachricht im Chor', text: 'Es gibt etwas Neues in „Chor“.', ziel: '#/nachrichten/Chor' })
  assert.equal(w.gezeigt.length, 1)
  assert.equal(w.gezeigt[0].titel, 'Neue Nachricht im Chor')
  assert.equal(w.gezeigt[0].optionen.body, 'Es gibt etwas Neues in „Chor“.')
  // `deepEqual` scheitert hier an den Prototypen des vm-Kontexts — die Werte
  // werden einzeln verglichen, das prüft dasselbe.
  assert.equal(w.gezeigt[0].optionen.data.ziel, '#/nachrichten/Chor')
  assert.equal(w.gezeigt[0].optionen.tag, '#/nachrichten/Chor', 'der tag bündelt je Gespräch')

  // Zusatzfelder werden NICHT angezeigt: der Worker nimmt nur die drei.
  w.gezeigt.length = 0
  await w.push({ titel: 'T', text: 'X', ziel: '#/nachrichten/A', inhalt: 'GEHEIM', absender: 'Anna' })
  const opts = w.gezeigt[0].optionen
  assert.doesNotMatch(JSON.stringify(opts), /GEHEIM|Anna/, 'nur titel/text/ziel — kein Inhalt, kein Absender')

  // Werte als Text: eine Zahl wird zur Zeichenkette, kein Objekt wird gezeigt.
  w.gezeigt.length = 0
  await w.push({ titel: 42, text: { boese: true }, ziel: '#/nachrichten/A' })
  assert.equal(w.gezeigt[0].titel, '42')
  assert.equal(w.gezeigt[0].optionen.body, 'Es gibt etwas Neues.')
})

test('CHAT-10b/C: unbrauchbare Nutzlast -> neutrale Meldung ohne Ziel', async () => {
  for (const kaputt of [new Error('kein JSON'), null, {}, 'text']) {
    const w = workerLaden()
    await w.push(kaputt)
    assert.equal(w.gezeigt.length, 1, String(kaputt))
    assert.equal(w.gezeigt[0].titel, 'Neue Nachricht')
    assert.equal(w.gezeigt[0].optionen.data.ziel, '', 'ohne brauchbares Ziel kein Ziel')
  }
  // Gültiges JSON, aber ohne die Felder: ebenfalls neutral.
  const w = workerLaden()
  await w.push({ andere: 'form' })
  assert.equal(w.gezeigt[0].titel, 'Neue Nachricht')
})

test('CHAT-10b/C: notificationclick nimmt NUR #/nachrichten-Ziele', async () => {
  const boese = [
    'javascript:alert(1)',
    'https://evil.example/phish',
    '//evil.example/phish',
    '#/einstellungen',
    '#/nachrichten/../../evil',
    '',
    undefined,
  ]
  // Achtung: `undefined` heißt „kein Ziel in den Daten“ — der Klick-Helfer
  // übergibt dann `data: undefined` und der Worker fällt auf die Liste zurück.
  for (const ziel of boese) {
    const w = workerLaden()
    w.setzeFenster([])
    await w.klick(ziel)
    assert.equal(w.geoeffnet.length, 1, `Ziel ${JSON.stringify(ziel)}`)
    assert.equal(w.geoeffnet[0], 'https://gemeinde.example.org/diakonos#/nachrichten',
      `Ziel ${JSON.stringify(ziel)} darf NICHT geöffnet werden`)
    assert.equal(new URL(w.geoeffnet[0]).origin, 'https://gemeinde.example.org')
  }

  // Das echte Ziel wird geöffnet — an der eigenen Herkunft, nicht an einer fremden.
  const w = workerLaden()
  w.setzeFenster([])
  await w.klick('#/nachrichten/Chor')
  assert.equal(w.geoeffnet.length, 1)
  assert.equal(w.geoeffnet[0], 'https://gemeinde.example.org/diakonos#/nachrichten/Chor')

  // Ein Unterpfad der Nachrichten ist ebenfalls erlaubt.
  const w2 = workerLaden()
  w2.setzeFenster([])
  await w2.klick('#/nachrichten/suche')
  assert.equal(w2.geoeffnet.length, 1)
  assert.equal(w2.geoeffnet[0], 'https://gemeinde.example.org/diakonos#/nachrichten/suche')
})

test('CHAT-10b/C: notificationclick nimmt ein offenes Fenster DERSELBEN Herkunft', async () => {
  const w = workerLaden()
  const navigiert = []
  const fremd = { url: 'https://evil.example/x', focus: async () => { throw new Error('fremdes Fenster!') }, navigate: async () => {} }
  const eigen = {
    url: 'https://gemeinde.example.org/diakonos',
    focus: async () => { w.fokus.push('eigen') },
    navigate: async (url) => { navigiert.push(url) },
  }
  w.setzeFenster([fremd, eigen])
  await w.klick('#/nachrichten/Chor')
  assert.equal(w.fokus.length, 1, 'nur das eigene Fenster wird in den Vordergrund geholt')
  assert.equal(navigiert.length, 1)
  assert.equal(navigiert[0], 'https://gemeinde.example.org/diakonos#/nachrichten/Chor')
  assert.equal(w.geoeffnet.length, 0, 'kein zweites Fenster')
})

test('CHAT-10b/C: nur ein Fenster der App-SEITE wird genommen (R1, Punkt 5)', async () => {
  // Ein Fenster derselben Herkunft, aber NICHT der App (Website/Verwaltung)
  // darf nicht zur App umgeleitet werden — es wird gar nicht erst genommen.
  const fremdeSeite = {
    url: 'https://gemeinde.example.org/',
    focus: async () => { throw new Error('falsche Seite fokussiert') },
    navigate: async () => { throw new Error('falsche Seite navigiert') },
  }
  const w = workerLaden()
  w.setzeFenster([fremdeSeite])
  await w.klick('#/nachrichten/Chor')
  assert.equal(w.geoeffnet.length, 1, 'stattdessen wird die App-Seite geöffnet')
  assert.equal(w.geoeffnet[0], 'https://gemeinde.example.org/diakonos#/nachrichten/Chor')

  // Ein ähnlich aussehender Pfad (`/diakonos-alt`) ist NICHT die App.
  const aehnlich = {
    url: 'https://gemeinde.example.org/diakonos-alt/start',
    focus: async () => { throw new Error('falscher Pfad fokussiert') },
    navigate: async () => { throw new Error('falscher Pfad navigiert') },
  }
  const w2 = workerLaden()
  w2.setzeFenster([aehnlich])
  await w2.klick('#/nachrichten/Chor')
  assert.equal(w2.geoeffnet[0], 'https://gemeinde.example.org/diakonos#/nachrichten/Chor')

  // Ein offenes Fenster MIT Unterpfad der App wird genommen.
  const navigiert = []
  const unterpfad = {
    url: 'https://gemeinde.example.org/diakonos#/kalender',
    focus: async () => {},
    navigate: async (url) => { navigiert.push(url) },
  }
  const w3 = workerLaden()
  w3.setzeFenster([unterpfad])
  await w3.klick('#/nachrichten/Chor')
  assert.deepEqual(navigiert, ['https://gemeinde.example.org/diakonos#/nachrichten/Chor'])
  assert.equal(w3.geoeffnet.length, 0, 'kein zweites Fenster')
})

test('CHAT-10b/C: `activate` übernimmt die offene Seite (clients.claim)', async () => {
  const w = workerLaden()
  assert.ok(w.zuhoerer.activate, 'der Worker hat einen activate-Zuhörer')
  const offen = []
  w.zuhoerer.activate({ waitUntil: (p) => offen.push(p) })
  assert.equal(offen.length, 1, 'waitUntil wird gerufen')
  await Promise.all(offen)
  assert.equal(w.uebernommen(), 1, 'clients.claim() wurde gerufen')
})

test('CHAT-10b/C: der Worker behandelt KEINE Anfragen (kein fetch, kein Cache)', () => {
  const w = workerLaden()
  assert.deepEqual(Object.keys(w.zuhoerer).sort(), ['activate', 'notificationclick', 'push'])
  assert.equal('fetch' in w.zuhoerer, false, 'kein fetch-Zuhörer')
  // Auch im Quelltext keine Zwischenspeicher-Schnittstelle.
  assert.doesNotMatch(SW_QUELLE, /caches\.|caches\b|importScripts|indexedDB/)
})

test('CHAT-10b/C: die Datei liegt in public/ — vite kopiert sie nach dist/sw.js', () => {
  assert.ok(statSync(new URL('public/sw.js', FRONTEND)).isFile())
  const vite = readFileSync(new URL('vite.config.mjs', FRONTEND), 'utf8')
  // Kein eigener `publicDir` — dann gilt der Vite-Standard `public/`.
  assert.doesNotMatch(ohneKommentare(vite), /publicDir\s*:/,
    'ein eigener publicDir würde public/sw.js nicht nach dist kopieren')
})

// ════════════════════════════════════════════════════════════════════════════
// D · Einbindung: Einstellungen, Router, Suche, Abmelden
// ════════════════════════════════════════════════════════════════════════════

test('CHAT-10b/D: der Abschnitt steht in den Einstellungen — OHNE Verwaltungsstufe', () => {
  const seite = ohneKommentare(lies('pages/Einstellungen.vue'))
  const eintrag = seite.match(/\{[^}]*id:\s*'benachrichtigungen'[\s\S]*?\}/)
  assert.ok(eintrag, 'der Abschnitt fehlt in `abschnitte`')
  assert.match(eintrag[0], /label:\s*'Benachrichtigungen aufs Gerät'/)
  assert.match(eintrag[0], /seite:\s*'EinstellungenBenachrichtigungen'/)
  assert.match(eintrag[0], /inhalt:\s*BENACHRICHTIGUNGEN/)
  assert.doesNotMatch(eintrag[0], /verwaltung\s*:/,
    'jede angemeldete Person sieht den Abschnitt — keine Verwaltungsstufe')
  assert.match(seite, /import\('\.\/einstellungen\/Benachrichtigungen\.vue'\)/)
})

test('CHAT-10b/D: Adresse und Seitenname im Router — und KEIN Admin-Wächter', () => {
  const router = lies('router.js')
  assert.match(router, /EinstellungenBenachrichtigungen:\s*\(\)\s*=>\s*import\('\.\/pages\/Einstellungen\.vue'\)/)
  assert.match(router, /'#\/einstellungen\/benachrichtigungen':\s*'EinstellungenBenachrichtigungen'/)
  // Der Wächter ist die EINE Stelle (`verwaltungsStufeSeite`) — der Name darf
  // in keiner der beiden Mengen stehen.
  const admin = router.match(/const ADMIN_ONLY_PAGES = new Set\(\[([\s\S]*?)\]\)/)
  const personen = router.match(/const PERSONEN_VERWALTUNG_PAGES = new Set\(\[([\s\S]*?)\]\)/)
  assert.doesNotMatch(ohneKommentare(admin[1]), /EinstellungenBenachrichtigungen/)
  assert.doesNotMatch(ohneKommentare(personen[1]), /EinstellungenBenachrichtigungen/)
})

test('CHAT-10b/D: die Suche findet den Abschnitt — ohne erfundene Stichworte', async () => {
  const suche = await import(new URL('pages/einstellungen/suche.mjs', SRC).href)
  assert.ok(Array.isArray(suche.STICHWORTE.benachrichtigungen))
  assert.ok(suche.STICHWORTE.benachrichtigungen.length >= 3)
  // „Push“ ist KEIN Stichwort: das Wort steht im Abschnitt nicht.
  assert.equal(suche.STICHWORTE.benachrichtigungen.some((w) => /push/i.test(w)), false)
  // Jedes Stichwort kommt im Abschnitt (Seite oder Sätze) wirklich vor.
  const seite = lies('pages/einstellungen/Benachrichtigungen.vue')
    + lies('pages/einstellungen/benachrichtigungen.mjs')
  const heu = seite.toLowerCase()
  const fehlend = suche.STICHWORTE.benachrichtigungen
    .filter((wort) => !heu.includes(wort.toLowerCase()))
  assert.deepEqual(fehlend, [], 'Stichwort ohne Fundstelle: ' + fehlend.join(', '))
})

test('CHAT-10b/D: beim Abmelden geht push.abmelden VOR dem Logout — Fehler werden verworfen', () => {
  const quelle = ohneKommentare(lies('composables/useAbmelden.js'))
  // Reihenfolge im Rumpf von `abmelden()`: erst Benachrichtigungen, dann Logout.
  const rumpf = quelle.slice(quelle.indexOf('export async function abmelden()'))
  const posBench = rumpf.indexOf('benachrichtigungenAbmelden()')
  const posLogout = rumpf.indexOf("post(mitBasis('/logout'))")
  assert.ok(posBench > 0 && posLogout > 0)
  assert.ok(posBench < posLogout, 'push.abmelden muss VOR dem Logout laufen')
  // Der Abmelde-Aufruf ist der push-Endpunkt, still (try/catch).
  const hilfe = quelle.slice(quelle.indexOf('export async function benachrichtigungenAbmelden'))
  assert.match(hilfe, /diakronos_app\.api\.push\.abmelden/)
  assert.match(hilfe, /endpoint/)
  assert.match(hilfe, /catch/)
})

// ── Abmelden auch wirklich ausgeführt (Node, fetch-Attrappe) ───────────────
async function abmeldenMit(abo, { fetchHaengt = false, abbruchMerken = null } = {}) {
  const store = { length: 0, key: () => null, getItem: () => null, setItem() {}, removeItem() {}, clear() {} }
  const fenster = {
    __DIakonosBOOT: { csrf_token: 'csrf-test' },
    localStorage: store,
    sessionStorage: store,
    location: { href: '/ausgangslage' },
    navigator: {
      serviceWorker: {
        getRegistration: async () => ({
          pushManager: { getSubscription: async () => abo },
        }),
      },
    },
  }
  globalThis.window = fenster
  const aufgerufen = []
  globalThis.fetch = async (url, opt) => {
    aufgerufen.push({ url, koerper: opt?.body ? JSON.parse(opt.body) : null })
    if (abbruchMerken && opt?.signal) abbruchMerken(opt.signal)
    if (fetchHaengt && String(url).includes('push.abmelden')) {
      // Ein Aufruf, der NIE antwortet (und den Abbruch auch nicht beachtet).
      return new Promise(() => {})
    }
    return {
      status: 200, ok: true,
      headers: { get: () => null },
      clone() { return this },
      async json() { return { message: { redirect: '/login?sso=0' } } },
    }
  }
  const modul = await import(new URL('composables/useAbmelden.js', SRC).href + '?t=' + Math.random())
  const start = Date.now()
  const ergebnis = await modul.abmelden()
  const gedauert = Date.now() - start
  delete globalThis.fetch
  return { ergebnis, aufgerufen, gedauert, modul }
}

test('CHAT-10b/D: abmelden() meldet das Gerät beim Server ab und dann die Sitzung', async () => {
  let entwichen = false
  const abo = {
    toJSON: () => ({ endpoint: 'https://fcm.googleapis.com/wp/abc' }),
    unsubscribe: async () => { entwichen = true; return true },
  }
  const { ergebnis, aufgerufen } = await abmeldenMit(abo)
  assert.equal(ergebnis.ok, true)
  const pfade = aufgerufen.map((a) => a.url)
  assert.deepEqual(pfade, ['/api/method/diakronos_app.api.push.abmelden', '/logout'],
    'erst die Benachrichtigung, dann die Sitzung: ' + JSON.stringify(pfade))
  assert.deepEqual(aufgerufen[0].koerper, { endpoint: 'https://fcm.googleapis.com/wp/abc' })
  // Review R1, Punkt 4: auch das Abonnement IM BROWSER wird verworfen, damit
  // ein geteiltes Gerät nach dem Abmelden keine Meldungen mehr zeigt.
  assert.equal(entwichen, true, 'unsubscribe() wird beim Abmelden gerufen')
})

test('CHAT-10b/D: ohne Abonnement geht KEIN zusätzlicher Aufruf hinaus', async () => {
  const { aufgerufen } = await abmeldenMit(null)
  assert.deepEqual(aufgerufen.map((a) => a.url), ['/logout'])
})

test('CHAT-10b/D: ein hängender push-Aufruf hält das Abmelden NICHT auf (≤ 1,5 s)', async () => {
  // Review R1, Punkt 3: der Vorgang ist auf 1500 ms gedeckelt. Ein Aufruf, der
  // nie antwortet, darf den Logout nicht blockieren.
  let signal = null
  const abo = {
    toJSON: () => ({ endpoint: 'https://fcm.googleapis.com/wp/abc' }),
    unsubscribe: async () => true,
  }
  const { ergebnis, aufgerufen, gedauert, modul } = await abmeldenMit(abo, {
    fetchHaengt: true,
    abbruchMerken: (s) => { signal = s },
  })
  assert.equal(ergebnis.ok, true, 'das Abmelden gelingt trotz hängendem Aufruf')
  assert.ok(gedauert < 1500 + 500, `nach ${gedauert} ms (Deckel 1500 ms)`)
  assert.equal(aufgerufen.at(-1).url, '/logout', 'die Sitzung wird trotzdem beendet')
  assert.equal(modul.FRIST_MS, 1500, 'der Deckel steht als Zahl in der Datei')
  assert.ok(signal, 'der Aufruf bekommt ein Abbruch-Signal (AbortController)')
  assert.equal(signal.aborted, true, 'nach Ablauf der Frist wird abgebrochen')
})

test('CHAT-10b/D: ein Fehler beim Abmelden hält das Abmelden nicht auf', async () => {
  const store = { length: 0, key: () => null, getItem: () => null, setItem() {}, removeItem() {}, clear() {} }
  const verworfen = []
  globalThis.window = {
    __DIakonosBOOT: { csrf_token: 'csrf-test' },
    localStorage: store, sessionStorage: store, location: { href: '/ausgangslage' },
    navigator: {
      serviceWorker: {
        getRegistration: async () => ({
          pushManager: {
            getSubscription: async () => ({
              toJSON: () => ({ endpoint: 'https://x.example/y' }),
              unsubscribe: async () => { verworfen.push('unsubscribe'); return true },
            }),
          },
        }),
      },
    },
  }
  const aufgerufen = []
  globalThis.fetch = async (url, opt) => {
    aufgerufen.push(url)
    if (String(url).includes('push.abmelden')) throw new Error('Netz weg')
    return {
      status: 200, ok: true, headers: { get: () => null },
      clone() { return this }, async json() { return { message: { redirect: '/login?sso=0' } } },
    }
  }
  const modul = await import(new URL('composables/useAbmelden.js', SRC).href + '?t=' + Math.random())
  const ergebnis = await modul.abmelden()
  delete globalThis.fetch
  assert.equal(ergebnis.ok, true, 'das Abmelden gelingt trotz Push-Fehler')
  assert.equal(aufgerufen.at(-1), '/logout', 'die Sitzung wird trotzdem beendet')
  // Auch wenn der SERVER den Aufruf nicht bekommt: das Abonnement im Browser
  // wird verworfen, damit das Gerät keine Meldungen der alten Person zeigt.
  assert.deepEqual(verworfen, ['unsubscribe'])
})
