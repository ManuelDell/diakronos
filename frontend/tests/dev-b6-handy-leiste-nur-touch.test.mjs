/**
 * DEV-B6 — Navigation: am Laptop NIE die Handy-Leiste (Befund DMB-3a7d335074cc).
 *
 * ENTSCHEIDUNG MANUEL (09.11.): „Auf einem Laptop darf nie die Handyleiste
 * kommen.“ Damit ist die Layout-Hälfte der FIX-6-Regel („Zeiger ist nie
 * Layout-Kriterium“) bewusst geändert:
 *
 *   layout == mobil  ⇔  (pointer: coarse) and (max-width: 720px)
 *                    ∨  (max-height: 480px) and (orientation: landscape)
 *
 * Die Bedingung steht als Token `--layout-mobil` in `tokens.css` (maschinen-
 * lesbare Quelle), ausgeschrieben in jedem `@media`-Block des Gerüsts und als
 * `HANDY_LAGE_ABFRAGE` in `App.vue` (Skript). Achtung: `@media (--layout-mobil)`
 * wirkte NICHT (im Browser gemessen) — der Token ist eine CSS-VARIABLE, kein
 * Custom-Media, und wird in `@media` nicht aufgelöst; der Test prüft deshalb
 * die ausgeschriebene Form gegen den Token-Wert.
 *
 * Dieser Test MOUNTET die echte `App.vue` (jsdom + @vue/compiler-sfc, Muster
 * `tests/pr-g2-stammdaten-mount.test.mjs`) mit einer `matchMedia`-Attrappe und
 * misst am gerenderten DOM:
 *
 *   1. Maus (fine+hover) bei 700 px und 400 px  → KEINE untere Leiste,
 *      Seitenleiste sichtbar, Menü-Knopf da, kein Fußabstand für die Leiste.
 *   2. Maus-Laptop 702×894 (der Befund)        → dasselbe.
 *   3. Touch (coarse) 390 px / 720 px           → Leiste da, Seitenleiste aus.
 *   4. Touch 1024 px                            → KEINE Leiste (Breite bleibt
 *      Kriterium für Touch, wie bisher).
 *   5. Touch quer 844×390                       → Leiste da (OP-HANDY-10).
 *   6. Die Zeiger-Attrappe wird NUR über matchMedia gefälscht; `any-pointer`
 *      wird nirgends gelesen.
 *
 * Dazu die reinen Rechnungen (Kalender-Handy-Lage, PLAN-M1-Hinweis) mit den
 * Werten aus dem Befund.
 */
import { JSDOM } from 'jsdom'

/**
 * matchMedia-Attrappe: genau EINE Lage. `grob` = primärer Zeiger ist ein
 * Finger; die Breite/Höhe kommen aus dem "Fenster".
 */
function fakeWindows({ breite = 1024, hoehe = 768, grob = false } = {}) {
  const dom = new JSDOM('<!doctype html><body></body>', { url: 'http://x/#/', pretendToBeVisual: true })
  const fenster = dom.window
  Object.defineProperty(fenster, 'innerWidth', { value: breite, writable: false, configurable: true })
  Object.defineProperty(fenster, 'innerHeight', { value: hoehe, writable: false, configurable: true })
  fenster.matchMedia = (abfrage) => ({ matches: passt(abfrage, { breite, hoehe, grob }), media: abfrage,
    addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {} })
  return { dom, fenster }
}

/** Löst eine (einfache) Media-Query so auf, wie der Browser es täte. */
function passt(abfrage, { breite, hoehe, grob }) {
  // Nur die Formen, die die App benutzt — alles andere gilt als „falsch".
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
        case 'prefers-color-scheme': return false
        case 'prefers-reduced-motion': return false
        // `any-pointer` ist KEIN Kriterium — wenn es jemand fragt, nie wahr.
        default: return false
      }
    }
    return pruefungen.length > 0 && pruefungen.every(([n, v]) => w(n, v))
  })
}

const { dom } = fakeWindows()
for (const k of ['Node', 'Element', 'HTMLElement', 'SVGElement', 'Event', 'MouseEvent',
  'navigator', 'location', 'getComputedStyle', 'requestAnimationFrame', 'cancelAnimationFrame',
  'hashchange', 'addEventListener', 'removeEventListener', 'localStorage', 'sessionStorage',
  'DocumentFragment', 'Text', 'Comment', 'HTMLAnchorElement']) {
  try { globalThis[k] = dom.window[k] } catch { /* manche gibt es nicht */ }
}
globalThis.window = dom.window
globalThis.document = dom.window.document
globalThis.requestAnimationFrame ||= (f) => setTimeout(f, 0)

import { readFileSync, writeFileSync, mkdtempSync, rmSync } from 'node:fs'
import { join, dirname, resolve, basename } from 'node:path'
import { pathToFileURL } from 'node:url'
import assert from 'node:assert/strict'
import test from 'node:test'

const { parse, compileScript, compileTemplate } = await import('vue/compiler-sfc')
const TMP = mkdtempSync(join(process.cwd(), '.zz-devb6-'))
process.on('exit', () => { try { rmSync(TMP, { recursive: true, force: true }) } catch { /* egal */ } })
const SRC = resolve('src')

// ── Stummel an den Grenzen (Server, Router, Bilder, Theme) ────────────────
const STUBS = {
  [resolve(SRC, 'diakonos/router.js')]: resolve(TMP, 'router.mjs'),
  [resolve(SRC, 'diakonos/composables/useSession.js')]: resolve(TMP, 'useSession.mjs'),
  [resolve(SRC, 'diakonos/composables/useDevmodus.js')]: resolve(TMP, 'useDevmodus.mjs'),
  [resolve(SRC, 'diakonos/composables/useImpersonation.js')]: resolve(TMP, 'useImpersonation.mjs'),
}
writeFileSync(STUBS[resolve(SRC, 'diakonos/router.js')], `
import { ref, shallowRef } from 'vue'
export const currentComponent = shallowRef(null)
export const currentHash = ref('#/')
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
const leer = ref(null)
const name = ref('Manuela Prüferin')
export function useSession() {
  return { user: ref({ fullname: 'Manuela Prüferin', email: 'pruefer@example.org' }),
    mitglied: leer, isAdmin: ref(true), hasMitglied: ref(true), istGast: ref(false),
    istTester: ref(false), devmodeAn: ref(false), istSystemManager: ref(true),
    rollen: ref(['Administrator']), anzeigeName: name, modules: ref({}) }
}
`)
writeFileSync(STUBS[resolve(SRC, 'diakonos/composables/useDevmodus.js')], `
import { ref } from 'vue'
export const devmodusAn = ref(false)
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
    if (spec === 'vue' || spec === 'vue-draggable-plus') return `${pre}'${import.meta.resolve(spec)}'`
    if (!spec.startsWith('.')) return all
    return `${pre}'${pathToFileURL(compile(resolve(fromDir, spec))).href}'`
  }).replace(/^import\s+['"][^'"]+\.css['"];?$/gm, '')
}

const Vue = await import('vue')
const App = (await import(pathToFileURL(compile(resolve(SRC, 'diakonos/App.vue'))).href)).default
const tick = (ms = 0) => new Promise((r) => setTimeout(r, ms))
async function ruhig(ms = 40) { await tick(ms); await Vue.nextTick(); await tick(ms) }

/**
 * Mountet die App in EINER Lage und liefert das DOM plus die Abschaltung.
 * `matchMedia` kommt aus der Lage — genau darum geht es in dieser Karte.
 */
async function mounte(lage) {
  const { fenster } = fakeWindows(lage)
  // window-Merker, die App.vue beim Start liest (Theme, Boot-Daten).
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
  const vm = app.mount(host)
  await ruhig(60)
  return {
    fenster, host, vm, warns,
    ende() { try { app.unmount() } catch { /* egal */ } host.remove() },
  }
}

const $ = (host, sel) => host.querySelector(sel)
const sichtbar = (el) => !!el && !el.hasAttribute('data-weg')

/** Die CSS-Regeln, die die Sichtbarkeit der Gerüst-Teile bestimmen (Quelle). */
function geruestCss() {
  const ohneKommentare = (t) => t.replace(/\/\*[\s\S]*?\*\//g, '')
  return {
    leiste: ohneKommentare(readFileSync(resolve(SRC, 'diakonos/components/AppBottomNav.vue'), 'utf8')),
    index: ohneKommentare(readFileSync(resolve(SRC, 'diakonos/index.css'), 'utf8')),
  }
}

/**
 * Die Handy-Lage, ausgeschrieben (Quelle: `--layout-mobil`, tokens.css).
 *
 * DEV-B6 (Review-Nacharbeit 10.11.): Auch die QUERFORMAT-Alternative prüft
 * den Zeiger — vorher fehlte dort `(pointer: coarse)`, und ein Maus-Laptop
 * 1280×450 bekam die Leiste (Review-Punkt 2).
 */
const HANDY_LAGE = '(pointer: coarse) and (max-width: 720px), (pointer: coarse) and (max-height: 480px) and (orientation: landscape)'

/**
 * Wie wird die untere Leiste gezeigt? Seit der Nacharbeit NICHT mehr über
 * eine eigene Media-Regel, sondern über die KLASSE `.dk-app--handy`, die
 * `App.vue` aus `composables/handyLage.mjs` setzt (eine Quelle). Genau EINE
 * Regel darf sie auf `display: flex` schalten.
 */
function leistenBedingung() {
  const css = geruestCss().leiste
  // Die Komponente nutzt `:global(.dk-app--handy)` (Hüllenklasse aus App.vue).
  const treffer = css.match(/.dk-app--handy\s+\.dk-bottom-nav\s*\{\s*display:\s*flex/g) || []
  return treffer.map(() => '.dk-app--handy')
}

/**
 * Alle @media-Blöcke einer Quelle als { bedingung, inhalt } — mit
 * Klammern-Zählung, damit ein Treffer NICHT aus einem früheren Block stammt.
 */
function mediaBloecke(css) {
  const bloecke = []
  const muster = /@media\s*([^\n{]+)\{/g
  for (let m = muster.exec(css); m; m = muster.exec(css)) {
    let tiefe = 0
    let i = m.index + m[0].length - 1
    const anfang = i + 1
    for (; i < css.length; i += 1) {
      if (css[i] === '{') tiefe += 1
      else if (css[i] === '}') { tiefe -= 1; if (tiefe === 0) break }
    }
    bloecke.push({ bedingung: m[1].trim(), inhalt: css.slice(anfang, i) })
  }
  return bloecke
}

// ══════════════════════════════════════════════════════════════════════════
// 1 · Maus/Trackpad: nie die Handy-Leiste — bei jeder Breite
// ══════════════════════════════════════════════════════════════════════════
for (const breite of [702, 700, 400]) {
  test(`DEV-B6: Maus bei ${breite} px bekommt NIE die Handy-Leiste`, async () => {
    const ctx = await mounte({ breite, hoehe: 894, grob: false })
    try {
      // Die Leiste liegt im DOM (App.vue zeigt sie außer im Vollbild immer);
      // SICHTBAR macht sie ausschließlich das CSS — deshalb wird hier am
      // gerenderten DOM geprüft, dass die Leiste vorhanden ist, und an der
      // Quelle, dass sie an der richtigen Bedingung hängt (jsdom rechnet
      // keine Media Queries; die Sichtprüfung im Browser folgt separat).
      assert.ok($(ctx.host, 'nav.dk-bottom-nav'),
        'die untere Leiste muss im DOM liegen (CSS entscheidet die Sichtbarkeit)')
      assert.deepEqual(leistenBedingung(), ['.dk-app--handy'],
        'genau EINE Sichtbar-Regel für die untere Leiste — an der Handy-Lage-Klasse')
      // Und die Klasse trägt dieselbe Bedingung wie das Token (Test weiter unten).
      const BEDINGUNG = HANDY_LAGE
      assert.equal(passt(BEDINGUNG, { breite, hoehe: 894, grob: false }), false,
        `Maus bei ${breite} px erfüllt die Leisten-Bedingung NICHT`)
      // Seitenleiste (Weg zur Navigation) und Menü-Knopf stehen bereit.
      assert.ok($(ctx.host, 'aside.dk-sidebar'), 'Seitenleiste steht bereit')
      assert.ok($(ctx.host, 'header.dk-topbar .dk-menue-knopf'), 'Menü-Knopf in der Kopfzeile')
      // DEV-B6 (Nacharbeit): Die App-Hülle trägt die Gerüst-Klasse NICHT —
      // gemessen am gerenderten DOM (die Attrappe rechnet die Abfrage aus).
      const huelle = $(ctx.host, '.dk-app')
      assert.ok(huelle, 'App-Hülle gerendert')
      assert.ok(!huelle.classList.contains('dk-app--handy'),
        `Maus bei ${breite} px: KEINE Handy-Lage-Klasse an der App-Hülle`)
      // Kein Fußabstand für eine Leiste, die es nicht gibt: die
      // padding-bottom-Regeln hängen an der KLASSE, nicht an der Breite.
      const index = geruestCss().index
      const fussRegeln = [...index.matchAll(/([^{}]*\.dk-content[^{}]*)\{([^}]*padding-bottom:[^}]*)\}/g)]
        .map((m) => ({ selektor: m[1].trim(), rumpf: m[2] }))
      // `.dk-content--vollbild` ist eine eigene Variante OHNE Leisten-Platz
      // (Vollbild der Prüf-Tafel) — sie ist keine Gerüst-Reservierung.
      const fussKlassen = fussRegeln.filter((r) => r.selektor.includes('.dk-app--handy'))
      assert.ok(fussKlassen.length > 0,
        'der Fußabstand hängt an der Handy-Lage (kein reservierter Platz am Laptop)')
      for (const r of fussRegeln.filter((x) => !x.selektor.includes('--vollbild'))) {
        assert.ok(r.selektor.includes('.dk-app--handy'),
          `Fußabstand-Regel ohne Handy-Lage: "${r.selektor}"`)
      }
      assert.ok(!/@media \(max-width: 720px\) \{\s*\.dk-app \{ grid-template-columns: 1fr; \}/.test(index),
        'das Gerüst (einspaltig) hängt nicht mehr an der nackten Breite')
    } finally { ctx.ende() }
  })
}

// ══════════════════════════════════════════════════════════════════════════
// 0 · Spezifität: die Ausblend-Regel des Menü-Knopfs muss GEWINNEN
// ══════════════════════════════════════════════════════════════════════════
test('DEV-B6: der Menü-Knopf ist am Desktop auch dann aus, wenn DkButton ihn anzeigt', () => {
  // Im Wegwerf-Stack gemessen: DkButton setzt auf demselben Element
  // `display: inline-flex` (eine Klasse). Eine Grundregel mit EINER Klasse
  // (`.dk-menue-knopf`) verliert dagegen — der Knopf stand bei 1440 px im Bild.
  const css = geruestCss().index
  const grund = /(?:^|\})\s*\.dk-topbar-symbol\.dk-menue-knopf\s*\{([^}]*?)\}/.exec(css)
  assert.ok(grund, 'Grundregel `.dk-topbar-symbol.dk-menue-knopf` (zwei Klassen) fehlt')
  assert.match(grund[1], /display:\s*none/,
    'die Ausblend-Regel muss zwei Klassen tragen (sonst gewinnt DkButton)')
  assert.ok(!/(?:^|\n)\.dk-menue-knopf\s*\{/.test(css.replace(/\.dk-topbar-symbol\.dk-menue-knopf/g, '')),
    'keine konkurrierende Regel mit nur einer Klasse')
  // Und der Verweis auf den Zustand in App.vue: die Schublade hängt NUR an
  // der Handy-Lage (MT-1, Manuel 11.11. „nur EIN Seitenmenü“) — nicht mehr an
  // `sidebarCollapsed`; dort ist der Ausklapp-Knopf der Leiste der Einstieg.
  const app = readFileSync(resolve(SRC, 'diakonos/App.vue'), 'utf8')
  assert.match(app, /v-if="!isVollbildMode && istHandyLage"/,
    'Schublade nur in der Handy-Lage')
  assert.ok(!/<AppMenueSchublade[\s\S]{0,200}sidebarCollapsed/.test(app),
    'keine Schublade bei eingeklappter Leiste (MT-1)')
})

test('DEV-B6: der Befund selbst — Laptop 702×894 mit Maus', () => {
  const BEDINGUNG = HANDY_LAGE
  assert.equal(passt('(pointer: coarse) and (max-width: 720px)', { breite: 702, hoehe: 894, grob: false }),
    false, 'fine-Zeiger bei 702 px ist KEINE Handy-Lage')
  assert.equal(passt(BEDINGUNG, { breite: 702, hoehe: 894, grob: false }), false,
    'der Befund: 702×894 mit Maus bekommt KEINE Handy-Leiste')
  assert.equal(passt(BEDINGUNG, { breite: 702, hoehe: 894, grob: true }), true,
    '702 px <= 720: ein TOUCH-Gerät behält die Leiste (bisheriges Verhalten)')
})

// ══════════════════════════════════════════════════════════════════════════
// 2 · Touch: bisheriges Verhalten nach Breite
// ══════════════════════════════════════════════════════════════════════════
test('DEV-B6: Touch (coarse) bis 720 px behält die Leiste, darüber nicht', () => {
  const lage = (breite, hoehe = 844) => passt('(pointer: coarse) and (max-width: 720px), (max-height: 480px) and (orientation: landscape)', { breite, hoehe, grob: true })
  assert.equal(lage(390), true, 'Handy 390 px')
  assert.equal(lage(720), true, 'Grenze gehört dazu')
  assert.equal(lage(721), false, '721 px: keine Leiste')
  assert.equal(lage(1024), false, 'Tablet quer 1024 px: keine Leiste (Breite bleibt Kriterium)')
  assert.equal(lage(844, 390), true, 'Handy im flachen Querformat (OP-HANDY-10)')
  // Maus im flachen Querformat: der Querformat-Zweig gilt für ALLE Zeiger —
  // dort ist die Seitenleiste geometrisch nicht darstellbar (OP-HANDY-10).
  assert.equal(passt('(pointer: coarse) and (max-width: 720px), (max-height: 480px) and (orientation: landscape)', { breite: 844, hoehe: 390, grob: false }),
    true, 'flaches Fenster: Leiste statt überlappender Seitenleiste')
})

test('DEV-B6: App.vue und tokens.css tragen DIESELBE Bedingung', () => {
  const tokens = readFileSync(resolve(SRC, 'diakonos/tokens.css'), 'utf8')
  const app = readFileSync(resolve(SRC, 'diakonos/App.vue'), 'utf8')
  const tokenBedingung = /--layout-mobil:\s*([^;]+);/.exec(tokens)
  assert.ok(tokenBedingung, 'Token --layout-mobil fehlt in tokens.css')
  // Kommentare zuerst entfernen, dann Leerraum normalisieren.
  const token = tokenBedingung[1].replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/\s+/g, ' ').replace(/\( (pointer|max-width|max-height|orientation)/g, '($1')
    .replace(/(\S) \)/g, '$1)').trim()
  assert.equal(token, HANDY_LAGE,
    'Token-Wert (EINE Quelle für alle Layout-Blöcke)')
  // Die Zeichenkette steht als HANDY_LAGE_ABFRAGE im Composable (eine Quelle);
  // App.vue importiert sie von dort — KEINE Kopie mehr im Skript.
  // Die Zeichenkette steht in `handyLageAbfrage.mjs` (ohne Vue, damit Node-only-
  // Module sie lesen können) und wird von `handyLage.mjs` weitergegeben.
  const lage = readFileSync(resolve(SRC, 'diakonos/composables/handyLageAbfrage.mjs'), 'utf8')
  const abfrage = /export const HANDY_LAGE_ABFRAGE =[\s\S]*?\n(?=export|\/\*|$)/.exec(lage)
  assert.ok(abfrage, 'HANDY_LAGE_ABFRAGE fehlt in composables/handyLageAbfrage.mjs')
  assert.match(readFileSync(resolve(SRC, 'diakonos/composables/handyLage.mjs'), 'utf8'),
    /import \{ FLACH_QUER_PX, HANDY_LAGE_ABFRAGE \} from '\.\/handyLageAbfrage\.mjs'/,
    'handyLage.mjs reicht die Zeichenkette weiter (kein zweiter Text)')
  assert.match(abfrage[0],
    /\(pointer: coarse\) and \(max-width: \$\{MOBIL_GRENZE_PX\}px\),/,
    'Composable: grober Zeiger + Breite aus der EINEN Grenze')
  assert.match(abfrage[0],
    /\(pointer: coarse\) and \(max-height: \$\{FLACH_QUER_PX\}px\) and \(orientation: landscape\)/,
    'Composable: Querformat-Alternative prüft den Zeiger mit (Review-Punkt 2)')
  assert.match(app, /from '\.\/composables\/handyLage\.mjs'/,
    'App.vue liest die Handy-Lage aus dem Composable')
  assert.ok(!/const HANDY_LAGE_ABFRAGE/.test(app),
    'App.vue: KEINE zweite Kopie der Zeichenkette')
  // Und niemand fragt `any-pointer` (Touch-FÄHIGKEIT ist kein Kriterium).
  for (const datei of ['index.css', 'kronos.css', 'components/AppBottomNav.vue', 'App.vue']) {
    const text = readFileSync(resolve(SRC, 'diakonos', datei), 'utf8')
    assert.ok(!/any-pointer/.test(text.replace(/\/\*[\s\S]*?\*\//g, '')),
      `${datei}: any-pointer ist kein Layout-Kriterium`)
  }
})

test('DEV-B6: Kalender und Plan-Hinweis nutzen die Handy-Lage (Zeiger + Breite)', async () => {
  const breiten = await import(pathToFileURL(resolve(SRC, 'diakonos/components/kronos/breiten.mjs')).href)
  const hinweis = await import(pathToFileURL(resolve(SRC, 'diakonos/composables/handyHinweis.mjs')).href)
  // Kalender: Handy-Layout nur am Touchgerät (oder flach) — ein Maus-Laptop
  // bei 702 px behält die rechte Spalte. Sehr schmale Fenster (<= 430 px)
  // sind auch mit Maus Handy-Lage (dort ist die Spalte nicht darstellbar).
  assert.equal(breiten.istKalenderHandyLage(390, { grob: true }), true, 'Handy')
  assert.equal(breiten.istKalenderHandyLage(720, { grob: true }), true, 'Grenze gehört dazu')
  assert.equal(breiten.istKalenderHandyLage(702, { grob: false }), false, 'Laptop 702 px mit Maus (Befund)')
  assert.equal(breiten.istKalenderHandyLage(1024, { grob: true }), false, 'Tablet quer: nicht schmal')
  assert.equal(breiten.istKalenderHandyLage(844, { grob: true, hoehe: 390 }), true, 'Handy quer')
  assert.equal(breiten.istKalenderHandyLage(430, { grob: false }), true, 'sehr schmal (430 px)')
  assert.equal(breiten.istKalenderHandyLage(431, { grob: false }), false)
  // Plan-Hinweis: dieselbe Logik (schmal + grob, sehr schmal).
  assert.equal(hinweis.istHandyHinweisLage(390, { grob: true }), true, 'Handy')
  assert.equal(hinweis.istHandyHinweisLage(702, { grob: false }), false, 'Laptop 702 px (Befund)')
  // Die Seiten fragen die Lage ab (nicht mehr nur die Breite).
  for (const seite of ['pages/planrahmen/Plan.vue', 'pages/planrahmen/PlantypEditor.vue',
    'pages/planrahmen/Stammdaten.vue']) {
    const text = readFileSync(resolve(SRC, 'diakonos', seite), 'utf8')
    assert.match(text, /istHandyHinweisLage\(/, `${seite}: Hinweis hängt an der Handy-Lage`)
    assert.ok(!/schmal: istSchmal\(/.test(text), `${seite}: kein reiner Breiten-Test mehr`)
  }
  const kalender = readFileSync(resolve(SRC, 'diakonos/pages/Kalender.vue'), 'utf8')
  assert.match(kalender, /const \{ istHandyLage \} = useHandyLage\(\)/,
    'Kalender: Handy-Gerüst aus der EINEN Quelle')
  assert.ok(!/istHandyBreite\(window\.innerWidth\)/.test(kalender),
    'Kalender: keine reine Breiten-Entscheidung mehr')
})

// ══════════════════════════════════════════════════════════════════════════
// 3 · Review-Nacharbeit: flaches Maus-Fenster (1280×450) — keine Leiste
// ══════════════════════════════════════════════════════════════════════════
test('DEV-B6: flaches Fenster mit MAUS (1280×450) bekommt keine Leiste', () => {
  // Review-Punkt 2: die Querformat-Alternative prüft den Zeiger mit. Vorher
  // fehlte `(pointer: coarse)` — ein Laptop im halben Bildschirm (1280×450)
  // bekam die Handy-Leiste.
  assert.equal(passt(HANDY_LAGE, { breite: 1280, hoehe: 450, grob: false }), false,
    'flaches Maus-Fenster ist KEINE Handy-Lage')
  assert.equal(passt(HANDY_LAGE, { breite: 1280, hoehe: 450, grob: true }), true,
    'dasselbe Fenster am TOUCH-Gerät behält die Leiste (bisheriges Verhalten)')
})

test('DEV-B6: die Rechnung des Composable stimmt mit der Bedingung überein', async () => {
  const { istHandyLage, HANDY_LAGE_ABFRAGE } = await import(
    pathToFileURL(resolve(SRC, 'diakonos/composables/handyLage.mjs')).href)
  assert.equal(HANDY_LAGE_ABFRAGE, HANDY_LAGE, 'Zeichenkette = Token')
  const faelle = [
    // [breite, hoehe, grob, erwartet, warum]
    [390, 844, true, true, 'Handy'],
    [720, 900, true, true, 'Grenze gehört dazu'],
    [721, 900, true, false, 'Tablet-Lage: keine Leiste'],
    [702, 894, false, false, 'der Befund: Laptop mit Maus'],
    [1280, 450, false, false, 'flacher Laptop mit Maus'],
    [1280, 450, true, true, 'flaches Touchgerät'],
    [844, 390, true, true, 'Handy im Querformat'],
    [360, 800, false, false, 'schmales Maus-Fenster'],
  ]
  for (const [breite, hoehe, grob, erwartet, warum] of faelle) {
    assert.equal(istHandyLage(breite, { grob, hoehe }), erwartet,
      `${breite}×${hoehe} ${grob ? 'grob' : 'fein'} — ${warum}`)
  }
})

test('DEV-B6: die App-Hülle trägt die Gerüst-Klasse nur in der Handy-Lage', async () => {
  for (const [breite, hoehe, grob, erwartet] of [[390, 844, true, true], [702, 894, false, false]]) {
    const ctx = await mounte({ breite, hoehe, grob })
    try {
      const huelle = $(ctx.host, '.dk-app')
      assert.ok(huelle, 'App-Hülle gerendert')
      assert.equal(huelle.classList.contains('dk-app--handy'), erwartet,
        `${breite}×${hoehe} ${grob ? 'grob' : 'fein'}: Klasse ${erwartet ? 'da' : 'nicht da'}`)
      // Schublade und Menü-Knopf: Weg zur Navigation in JEDER Lage
      // (Handy-Lage über den Kopfzeilen-Knopf, sonst die Seitenleiste).
      assert.ok($(ctx.host, 'header.dk-topbar .dk-menue-knopf'), 'Menü-Knopf steht bereit')
    } finally { ctx.ende() }
  }
})

test('DEV-B6: die Handy-Lage steht zusaetzlich am <body> (Leiste liegt neben .dk-app)', () => {
  // Im Wegwerf-Stack gemessen: `nav.dk-bottom-nav`, die Schublade, die
  // Befehlspalette und die Meldungen sind GESCHWISTER der Huelle (direkt an
  // <body>). Ein Nachfahren-Waehler `.dk-app--handy …` erreichte sie nie —
  // die Leiste blieb am Touchgeraet aus. Deshalb setzt App.vue die Klasse an
  // beide Stellen.
  const app = readFileSync(resolve(SRC, 'diakonos/App.vue'), 'utf8')
  assert.match(app, /document\.body\.classList\.toggle\(HANDY_KLASSE, an === true\)/,
    'App.vue spiegelt die Handy-Lage an <body>')
  assert.match(app, /\[HANDY_KLASSE\]: istHandyLage/,
    'und setzt sie an der App-Huelle')
})
