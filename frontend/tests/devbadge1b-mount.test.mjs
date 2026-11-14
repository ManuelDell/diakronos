/**
 * DEVBADGE-1b — Mount-Wächter: `dk-app--dev` hängt am SICHTBAREN Dev-Eintrag
 * (Review Opus, Punkt 3: die Quelltext-Regexe allein konnten Befund 1 nicht
 * fangen, weil sie die Klasse nie im gerenderten DOM geprüft haben).
 *
 * Dieser Test MOUNTET die echte `App.vue` (jsdom + @vue/compiler-sfc, Muster
 * `tests/dev-b6-handy-leiste-nur-touch.test.mjs`) mit Attrappen für Server,
 * Router und Dev-Zustand und misst das gerenderte DOM:
 *
 *   1. Ohne Dev-Berechtigung (Server aus / kein Tester):
 *      KEINE Klasse `dk-app--dev`, kein `.dk-topbar-dev`, kein `.dk-dev-start`.
 *   2. Knopf sichtbar am Handy: Klasse da, Knopf im Kopf-Slot
 *      (`.dk-topbar-dev .dk-dev-start`), kein schwebender Zweit-Knopf.
 *   3. Knopf sichtbar am Desktop: Klasse da, Knopf schwebend (nicht im Kopf).
 *   4. Knopf sichtbar in `#/einrichtung` (Vollbild ohne Kopfzeile): Klasse da,
 *      Knopf schwebend — der Dev-Einstieg fehlt dort NICHT (Review Punkt 3).
 *   5. LAUFENDE Dev-Sitzung (`devmodusAn`): keine Klasse — dann gibt es keinen
 *      Dev-Eintrag in Kopf/unten rechts (Review Punkt 2).
 *
 * Die Messung ist der eigentliche Wächter: eine künftige Änderung, die die
 * Klasse an `devmodusVerfuegbar` oder an den laufenden Rahmen hängt, wird hier
 * rot — egal, wie der Quelltext daneben aussieht.
 */
import { JSDOM } from 'jsdom'

function fakeWindows({ breite = 1024, hoehe = 768, grob = false } = {}) {
  const dom = new JSDOM('<!doctype html><body></body>', { url: 'http://x/#/', pretendToBeVisual: true })
  const fenster = dom.window
  Object.defineProperty(fenster, 'innerWidth', { value: breite, writable: false, configurable: true })
  Object.defineProperty(fenster, 'innerHeight', { value: hoehe, writable: false, configurable: true })
  fenster.matchMedia = (abfrage) => ({
    matches: passt(abfrage, { breite, hoehe, grob }), media: abfrage,
    addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {},
  })
  return { dom, fenster }
}

/** Löst die Media-Queries der App so auf, wie der Browser es täte. */
function passt(abfrage, { breite, hoehe, grob }) {
  const teile = abfrage.split(',').map((t) => t.trim())
  return teile.some((t) => {
    const pruefungen = []
    for (const m of t.matchAll(/\(([a-z-]+):\s*([^)]+)\)/g)) pruefungen.push([m[1], m[2].trim()])
    for (const m of t.matchAll(/\(([a-z-]+)\)\s*$/g)) pruefungen.push([m[1], null])
    const w = (name, wert) => {
      switch (name) {
        case 'pointer': return wert === 'coarse' ? grob : !grob
        case 'hover': return wert === 'hover' ? !grob : grob
        case 'min-width': return breite >= parseInt(wert, 10)
        case 'max-width': return breite <= parseInt(wert, 10)
        case 'min-height': return hoehe >= parseInt(wert, 10)
        case 'max-height': return hoehe <= parseInt(wert, 10)
        case 'orientation': return wert === 'landscape' ? breite > hoehe : breite <= hoehe
        default: return false
      }
    }
    return pruefungen.length > 0 && pruefungen.every(([n, v]) => w(n, v))
  })
}

const { dom: startDom } = fakeWindows()
for (const k of ['Node', 'Element', 'HTMLElement', 'SVGElement', 'Event', 'MouseEvent',
  'navigator', 'location', 'getComputedStyle', 'requestAnimationFrame', 'cancelAnimationFrame',
  'localStorage', 'sessionStorage', 'DocumentFragment', 'Text', 'Comment', 'HTMLAnchorElement']) {
  try { globalThis[k] = startDom.window[k] } catch { /* manche gibt es nicht */ }
}
globalThis.window = startDom.window
globalThis.document = startDom.window.document
globalThis.requestAnimationFrame ||= (f) => setTimeout(f, 0)

import { readFileSync, writeFileSync, mkdtempSync, rmSync } from 'node:fs'
import { join, dirname, resolve, basename } from 'node:path'
import { pathToFileURL } from 'node:url'
import assert from 'node:assert/strict'
import test from 'node:test'

const { parse, compileScript, compileTemplate } = await import('vue/compiler-sfc')
const TMP = mkdtempSync(join(process.cwd(), '.zz-devbadge1b-'))
process.on('exit', () => { try { rmSync(TMP, { recursive: true, force: true }) } catch { /* egal */ } })
const SRC = resolve('src')

// ── Attrappen an den Grenzen ──────────────────────────────────────────────
// `devZustand` ist der EINE Schalter, den die Fälle unten umlegen: er
// beschreibt, was der Server meldet und ob eine Sitzung läuft.
const STUBS = {
  [resolve(SRC, 'diakonos/router.js')]: resolve(TMP, 'router.mjs'),
  [resolve(SRC, 'diakonos/composables/useSession.js')]: resolve(TMP, 'useSession.mjs'),
  [resolve(SRC, 'diakonos/composables/useDevmodus.js')]: resolve(TMP, 'useDevmodus.mjs'),
  [resolve(SRC, 'diakonos/composables/useImpersonation.js')]: resolve(TMP, 'useImpersonation.mjs'),
}
const zustandDatei = resolve(TMP, 'devZustand.mjs')
writeFileSync(zustandDatei, `
import { ref } from 'vue'
// t(f) = Server erlaubt den Dev-Modus UND Nutzer ist berechtigt;
// an(f) = eine Dev-Sitzung läuft.
export const zustand = {
  tester: ref(false),
  serverDev: ref(false),
  an: ref(false),
  handy: ref(false),
  hash: ref('#/'),
}
`)
writeFileSync(STUBS[resolve(SRC, 'diakonos/router.js')], `
import { ref, shallowRef } from 'vue'
import { zustand } from '${pathToFileURL(zustandDatei).href}'
export const currentComponent = shallowRef(null)
export const currentHash = zustand.hash
export const currentPageName = ref('Home')
export const pageLadefehler = ref(null)
export const seitenLadend = ref(false)
export function navigate() {}
export function routeNeuLaden() {}
export function getRouteParam() { return '' }
export function onBeforeEach() { return () => {} }
`)
writeFileSync(STUBS[resolve(SRC, 'diakonos/composables/useSession.js')], `
import { ref } from 'vue'
import { zustand } from '${pathToFileURL(zustandDatei).href}'
const leer = ref(null)
const name = ref('Manuela Prüferin')
export function useSession() {
  return { user: ref({ fullname: 'Manuela Prüferin', email: 'pruefer@example.org' }),
    mitglied: leer, isAdmin: ref(true), hasMitglied: ref(true), istGast: ref(false),
    istTester: zustand.tester, istMitgliederverwaltung: ref(true), devmodeAn: zustand.serverDev, istSystemManager: ref(true),
    rollen: ref(['Administrator']), anzeigeName: name, modules: ref({}) }
}
`)
writeFileSync(STUBS[resolve(SRC, 'diakonos/composables/useDevmodus.js')], `
import { ref } from 'vue'
import { zustand } from '${pathToFileURL(zustandDatei).href}'
export const devmodusAn = zustand.an
export const devmodusVerfuegbar = ref(false)
export const devmodusKuerzel = ref('Strg+Shift+F')
export const sttVerfuegbar = ref(false)
export const devmodusApi = { anfragen: async () => [], befund: async () => ({}) }
export function wunschSetzen() {}
export function wunschLesen() { return null }
export function zustandSetzen() {}
export function bildUrl(p) { return String(p || '') }
export function fehlerZeilen() { return [] }
export async function devmodusAutostart() {}
export async function devmodusPruefen() {}
`)
writeFileSync(STUBS[resolve(SRC, 'diakonos/composables/useImpersonation.js')], `
export function useImpersonation() {
  return { isActive: { value: false }, fullName: { value: '' }, expiresAt: { value: 0 },
    checkExpiry() {}, stop() {} }
}
`)

const cache = new Map()
let n = 0
function compile(abs) {
  if (STUBS[abs]) return STUBS[abs]
  if (cache.has(abs)) return cache.get(abs)
  const z = resolve(TMP, basename(abs) + (n++) + '.mjs')
  cache.set(abs, z)
  let c
  if (abs.endsWith('.vue')) {
    const filename = basename(abs)
    const { descriptor } = parse(readFileSync(abs, 'utf8'), { filename })
    const s = compileScript(descriptor, { id: filename, inlineTemplate: false })
    const t = compileTemplate({
      source: descriptor.template.content, filename, id: filename,
      compilerOptions: { bindingMetadata: s.bindings },
    })
    c = s.content.replace(/\nexport default /, '\nconst __sfc__ = ')
      + '\n' + t.code.replace(/^export function render/m, 'function render')
      + '\n__sfc__.render = render\nexport default __sfc__\n'
  } else c = readFileSync(abs, 'utf8')
  writeFileSync(z, rewrite(c, dirname(abs)))
  return z
}
function rewrite(code, fromDir) {
  return code.replace(/(from\s+|import\s*\(\s*)(['"])([^'"]+)\2/g, (all, pre, q, spec) => {
    if (spec === 'vue') return `${pre}'${import.meta.resolve(spec)}'`
    if (!spec.startsWith('.')) return all
    return `${pre}'${pathToFileURL(compile(resolve(fromDir, spec))).href}'`
  }).replace(/^import\s+['"][^'"]+\.css['"];?$/gm, '')
}

const Vue = await import('vue')
const App = (await import(pathToFileURL(compile(resolve(SRC, 'diakonos/App.vue'))).href + '?' + Date.now())).default
const { zustand } = await import(pathToFileURL(zustandDatei).href)
const tick = (ms = 0) => new Promise((r) => setTimeout(r, ms))
async function ruhig(ms = 40) { await tick(ms); await Vue.nextTick(); await tick(ms) }

/**
 * Setzt den Dev-Zustand, mountet die App in EINER Lage und liefert DOM-Kennzahlen.
 * `lage`: { breite, hoehe, grob } — Handy = grob (Zeiger) UND schmal (DEV-B6).
 */
async function mounte({ breite = 1024, hoehe = 768, grob = false } = {}, vorher = {}) {
  zustand.tester.value = !!vorher.tester
  zustand.serverDev.value = !!vorher.serverDev
  zustand.an.value = !!vorher.an
  zustand.hash.value = vorher.hash || '#/'

  const { fenster } = fakeWindows({ breite, hoehe, grob })
  fenster.localStorage.setItem('dk-theme', 'light')
  fenster.__DIakonosBOOT = { user_email: 'pruefer@example.org' }
  globalThis.window = fenster
  globalThis.document = fenster.document
  for (const k of ['Node', 'Element', 'HTMLElement', 'SVGElement', 'Event', 'MouseEvent',
    'navigator', 'location', 'getComputedStyle', 'localStorage', 'sessionStorage',
    'DocumentFragment', 'Text', 'Comment', 'HTMLAnchorElement']) {
    try { globalThis[k] = fenster[k] } catch { /* egal */ }
  }
  const host = fenster.document.createElement('div')
  fenster.document.body.appendChild(host)
  const app = Vue.createApp(App)
  const warns = []
  app.config.warnHandler = (m) => warns.push(String(m).slice(0, 200))
  app.mount(host)
  await ruhig(80)
  const appEl = host.querySelector('.dk-app')
  const ergebnis = {
    warns,
    klasseDev: !!appEl && appEl.classList.contains('dk-app--dev'),
    klasseHandy: !!appEl && appEl.classList.contains('dk-app--handy'),
    kopfPlatz: !!host.querySelector('.dk-topbar-dev'),
    knopfImKopf: !!host.querySelector('.dk-topbar-dev .dk-dev-start'),
    knopfSchwebend: !!host.querySelector('.dk-app > .dk-dev-start') || !!host.querySelector(':scope > .dk-dev-start'),
    knoepfe: host.querySelectorAll('.dk-dev-start').length,
    topbar: !!host.querySelector('.dk-topbar'),
    ende() { try { app.unmount() } catch { /* egal */ } host.remove() },
  }
  // Der schwebende Knopf steht AUSSERHALB von `.dk-app` (Wurzel-Ebene) —
  // deshalb am Host messen, nicht am Gerüst.
  ergebnis.knopfSchwebend = Array.from(host.children).some(
    (k) => k.classList?.contains('dk-dev-start'))
  return ergebnis
}

const HANDY = { breite: 390, hoehe: 844, grob: true }
const DESKTOP = { breite: 1440, hoehe: 900, grob: false }
const EINRICHTUNG = '#/einrichtung'

test('DEVBADGE-1b · M1: ohne Dev-Berechtigung gibt es weder Klasse noch Dev-Eintrag', async () => {
  for (const [lage, name] of [[HANDY, 'Handy'], [DESKTOP, 'Desktop']]) {
    const d = await mounte(lage, { tester: false, serverDev: false })
    try {
      assert.equal(d.klasseDev, false, `${name}: keine Klasse dk-app--dev`)
      assert.equal(d.kopfPlatz, false, `${name}: kein Kopf-Platz (.dk-topbar-dev)`)
      assert.equal(d.knoepfe, 0, `${name}: kein Dev-Knopf (.dk-dev-start)`)
    } finally { d.ende() }
  }
  // Server erlaubt, Nutzer NICHT berechtigt (und umgekehrt): ebenfalls nichts.
  for (const [tester, server] of [[false, true], [true, false]]) {
    const d = await mounte(HANDY, { tester, serverDev: server })
    try {
      assert.equal(d.klasseDev, false, `Tester=${tester}/Server=${server}: keine Klasse`)
      assert.equal(d.knoepfe, 0, `Tester=${tester}/Server=${server}: kein Knopf`)
    } finally { d.ende() }
  }
})

test('DEVBADGE-1b · M2: Knopf am Handy → Klasse da, Knopf im Kopf-Slot', async () => {
  const d = await mounte(HANDY, { tester: true, serverDev: true })
  try {
    assert.equal(d.klasseHandy, true, 'Handy-Lage aktiv (Voraussetzung der Messung)')
    assert.equal(d.klasseDev, true, 'Klasse `dk-app--dev` gesetzt')
    assert.equal(d.kopfPlatz, true, 'Kopf-Platz vorhanden')
    assert.equal(d.knopfImKopf, true, 'Knopf steht im Kopf-Slot')
    assert.equal(d.knopfSchwebend, false, 'kein schwebender Zweit-Knopf am Handy')
    assert.equal(d.knoepfe, 1, 'genau EIN Dev-Knopf')
  } finally { d.ende() }
})

test('DEVBADGE-1b · M3: Knopf am Desktop → Klasse da, Knopf schwebend (nicht im Kopf)', async () => {
  const d = await mounte(DESKTOP, { tester: true, serverDev: true })
  try {
    assert.equal(d.klasseHandy, false, 'Desktop hat keine Handy-Lage')
    assert.equal(d.klasseDev, true, 'Klasse `dk-app--dev` gesetzt (Abzeichen unten rechts)')
    assert.equal(d.kopfPlatz, false, 'kein Kopf-Platz am Desktop')
    assert.equal(d.knopfSchwebend, true, 'Knopf schwebt unten rechts')
    assert.equal(d.knoepfe, 1, 'genau EIN Dev-Knopf')
  } finally { d.ende() }
})

test('DEVBADGE-1b · M4: Knopf in #/einrichtung (Vollbild ohne Kopfzeile) → schwebend, erreichbar', async () => {
  const d = await mounte(HANDY, { tester: true, serverDev: true, hash: EINRICHTUNG })
  try {
    assert.equal(d.klasseDev, true, 'Klasse gesetzt (Knopf ist sichtbar)')
    assert.equal(d.topbar, false, 'Vollbild: keine Kopfzeile (Voraussetzung)')
    assert.equal(d.knopfSchwebend, true, 'Knopf ist die schwebende Form (Review Punkt 3)')
    assert.equal(d.knoepfe, 1, 'genau EIN Dev-Knopf — der Einstieg fehlt am Handy nicht')
  } finally { d.ende() }
})

test('DEVBADGE-1b · M5: laufende Dev-Sitzung → KEINE Klasse (kein Dev-Eintrag sichtbar)', async () => {
  for (const [lage, name] of [[HANDY, 'Handy'], [DESKTOP, 'Desktop']]) {
    const d = await mounte(lage, { tester: true, serverDev: true, an: true })
    try {
      assert.equal(d.knoepfe, 0, `${name}: laufende Sitzung hat keinen Einschaltknopf (Voraussetzung)`)
      assert.equal(d.klasseDev, false,
        `${name}: keine Klasse — sonst verschöben sich Kopf-Rand/Plakette/FAB ohne sichtbaren Eintrag`)
    } finally { d.ende() }
  }
})
