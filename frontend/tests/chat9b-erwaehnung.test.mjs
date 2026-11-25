/**
 * CHAT-9b — Erwähnungen „@Name“ (Vue 3, Frontend). Karte t_736c2a3e.
 *
 * Grundlage ist die Serverform aus CHAT-9a (NICHT nachgebaut, sondern wörtlich
 * benutzt): `chat.senden` nimmt `gespraech, text, antwort_auf, erwaehnt` (Liste
 * von Mitglied-Kennungen), jede Nachrichtenzeile trägt
 * `erwaehnt: [{mitglied, anzeigename}]`, die Glocke heißt `chat_erwaehnung`
 * mit `document_name` = Kennung der NACHRICHT.
 *
 * Geprüft wird VERHALTEN (echte Mounts, API-Attrappe trennt GET und POST):
 *
 *   A  Regeln ohne DOM (`components/chat/erwaehnung.mjs`): „@“ am Wortanfang
 *      öffnet, Filter, Einsetzen, Bereinigung vor dem Senden (nur Kennungen,
 *      deren „@Anzeigename“ noch im Text steht), Hervorhebung als TEXT —
 *      ein Anzeigename mit „<b>“ bleibt Text.
 *   B  Seite gemountet (Runde): „@“ öffnet die Auswahl (Beteiligte aus
 *      `chat.gespraech_mitglieder`), Tippen filtert, ↓/↑ bewegen, Enter
 *      übernimmt, Escape schließt (und sendet NICHT, R1/1: bleibt auch nach
 *      dem `keyup` zu), Senden schickt nur die noch im Text stehenden
 *      Kennungen, ohne Erwähnung geht KEIN/leeres `erwaehnt` hinaus, man
 *      selbst wird nie angeboten, eine IME-Eingabe bedient die Liste nicht.
 *   C  1:1 gemountet: dieselbe Abfrage — die andere Person (voller Name aus
 *      `gespraech_mitglieder`), die eigene fehlt; gesendet und hervorgehoben.
 *   D  Gruppe gemountet: ebenfalls über `gespraech_mitglieder`; scheitert die
 *      Abfrage, bleibt die Auswahl still weg (kein geratener Name).
 *   E  ChatBlase gemountet: Hervorhebung ohne HTML-Einschleusung, eigene
 *      Erwähnung markiert die Blase, fremde Erwähnung nicht.
 *   F  Glockenziel (`composables/glockenziele.mjs`): `chat_erwaehnung` fragt
 *      `chat.nachricht_kontext` und springt ins Gespräch; neutrale Antwort
 *      oder Fehler → Bereich „Nachrichten“; die Meldung behält ihr Ziel.
 *
 * Lauf (eine Datei je Aufruf, TZ=Europe/Berlin):
 *   TMPDIR=$(mktemp -d) TZ=Europe/Berlin node --test tests/chat9b-erwaehnung.test.mjs
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

const TMP = mkdtempSync(join(tmpdir(), 'chat9b-'))
test.after(() => rmSync(TMP, { recursive: true, force: true }))

const E = await import(new URL('components/chat/erwaehnung.mjs', SRC).href)
const ZIELE = await import(new URL('composables/glockenziele.mjs', SRC).href)
// Dieselbe Faltung wie der Server (`suchNormal`) — die Attrappe darf nicht
// großzügiger (oder strenger) suchen als er.
const { suchNormal } = await import(new URL('composables/bf1Anzeige.js', SRC).href)

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

/** Mounten mit Horcher für die Ereignisse der Komponente. */
async function mounten(baustein, props = {}, { horcher = null, propNamen = null } = {}) {
  const Vue = await import('vue')
  const host = document.createElement('div')
  document.body.appendChild(host)
  const warnungen = []
  let seite = null
  const kennung = Math.random().toString(36).slice(2)
  globalThis.__HORCHER = globalThis.__HORCHER || {}
  globalThis.__HORCHER[kennung] = horcher
  const melde = (art, wert) => {
    const h = globalThis.__HORCHER[kennung]
    if (h) h(art, wert)
  }
  const namen = propNamen || []
  const Wrapper = {
    props: { p: { type: Object, default: () => ({}) } },
    setup(innerProps) {
      seite = Vue.getCurrentInstance()
      const eigene = Vue.ref({ ...innerProps.p })
      globalThis.__PROP_SETZEN = globalThis.__PROP_SETZEN || {}
      globalThis.__PROP_SETZEN[kennung] = (name, wert) => {
        eigene.value = { ...eigene.value, [name]: wert }
      }
      return () => Vue.h(baustein, {
        ...eigene.value,
        ...Object.fromEntries(namen.map((n) => [`on${n[0].toUpperCase()}${n.slice(1)}`, (x) => melde(n, x)])),
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
  const propSetzen = (name, wert) => {
    const f = globalThis.__PROP_SETZEN?.[kennung]
    if (!f) return false
    f(name, wert)
    return true
  }
  const offen = () => {
    const kind = seite?.subTree?.component
    const instanz = kind && kind !== seite ? kind : null
    return instanz?.exposed || {}
  }
  return { host, app, warnungen, offen, propSetzen, abbaum }
}

function klick(el) {
  assert.ok(el, 'das Element steht im DOM')
  el.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true, cancelable: true }))
}

function taste(el, key, extra = {}) {
  const ereignis = new dom.window.KeyboardEvent('keydown', {
    key, bubbles: true, cancelable: true, ...extra,
  })
  el.dispatchEvent(ereignis)
  return ereignis
}

function handyAbfrage(handy) {
  dom.window.matchMedia = (abfrage) => ({
    media: String(abfrage),
    matches: handy === true && /pointer:\s*coarse/.test(String(abfrage)),
    addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {},
  })
}

function fehler(status, text = 'kaputt') {
  return Object.assign(new Error(text), { status })
}

// ════════════════════════════════════════════════════════════════════════════
// A · Regeln ohne DOM
// ════════════════════════════════════════════════════════════════════════════

const RUNDE = [
  { mitglied: 'M-1', anzeigename: 'Anna Beispiel' },
  { mitglied: 'M-2', anzeigename: 'Bert Brandner' },
  { mitglied: 'M-3', anzeigename: 'Clara Claus' },
]

test('CHAT-9b/A: „@“ öffnet nur am WORTANFANG, nicht mitten im Wort', () => {
  // Textanfang und Trennzeichen sind ein Wortanfang.
  assert.deepEqual(E.offeneErwaehnung('@', 1), { start: 0, ende: 1, begriff: '' })
  assert.deepEqual(E.offeneErwaehnung('Hallo @An', 9), { start: 6, ende: 9, begriff: 'An' })
  assert.deepEqual(E.offeneErwaehnung('Hallo\n@B', 8), { start: 6, ende: 8, begriff: 'B' })
  assert.deepEqual(E.offeneErwaehnung('(@Ann', 5), { start: 1, ende: 5, begriff: 'Ann' })
  // Kein Wortanfang: eine E-Mail-Adresse und ein Wort mitten drin.
  assert.equal(E.offeneErwaehnung('an@example', 10), null)
  assert.equal(E.offeneErwaehnung('Test@Anna', 9), null)
  // Ein Name ist EIN Wort: das Leerzeichen beendet die Auswahl.
  assert.equal(E.offeneErwaehnung('@Anna B', 7), null)
  // Kein „@“ vor dem Cursor → keine Auswahl.
  assert.equal(E.offeneErwaehnung('Hallo', 5), null)
  assert.equal(E.offeneErwaehnung('', 0), null)
})

test('CHAT-9b/A: Vorschläge filtern am WORTANFANG und lassen MICH weg', () => {
  assert.deepEqual(E.vorschlaege(RUNDE, '').map((m) => m.mitglied), ['M-1', 'M-2', 'M-3'])
  // R1/1: Treffer am WORTANFANG (Vorname/ganzer Name/Nachname beginnt mit q) —
  // dieselbe Regel wie der Server. „an“ trifft „Anna …“, NICHT „Bert
  // Brandner“ (dort steht „an“ mitten im Namen); sortiert wird nicht um.
  assert.deepEqual(E.vorschlaege(RUNDE, 'an').map((m) => m.mitglied), ['M-1'])
  assert.deepEqual(E.vorschlaege(RUNDE, 'brand').map((m) => m.mitglied), ['M-2'],
    'auch der Nachname beginnt mit „brand“')
  assert.deepEqual(E.vorschlaege(RUNDE, 'bran').map((m) => m.mitglied), ['M-2'])
  assert.deepEqual(E.vorschlaege(RUNDE, 'rand').map((m) => m.mitglied), [],
    'mitten im Namen KEIN Treffer — der Server findet ihn auch nicht')
  assert.deepEqual(E.vorschlaege(RUNDE, 'cla').map((m) => m.mitglied), ['M-3'])
  // Ein Zeichen genügt (der Server filtert genauso, R1/1).
  assert.deepEqual(E.vorschlaege(RUNDE, 'b').map((m) => m.mitglied), ['M-1', 'M-2'],
    '„Anna Beispiel“ (Nachname) und „Bert Brandner“')
  assert.deepEqual(E.vorschlaege(RUNDE, 'c').map((m) => m.mitglied), ['M-3'])
  // Umlaute und Groß-/Kleinschreibung (dieselbe Normalisierung wie die Suche).
  assert.deepEqual(E.vorschlaege([{ mitglied: 'M-9', anzeigename: 'Jürgen Müller' }], 'mueller')
    .map((m) => m.mitglied), ['M-9'])
  assert.deepEqual(E.vorschlaege([{ mitglied: 'M-9', anzeigename: 'Jürgen Müller' }], 'juergen')
    .map((m) => m.mitglied), ['M-9'])
  // Nie mich selbst.
  assert.deepEqual(E.vorschlaege(RUNDE, '', { ich: 'M-2' }).map((m) => m.mitglied), ['M-1', 'M-3'])
  // Unsinn im Serverfeld wird nicht angezeigt, nicht geraten.
  assert.deepEqual(E.vorschlaege([{ mitglied: '', anzeigename: 'Ohne Kennung' }, null, RUNDE[0]], '')
    .map((m) => m.mitglied), ['M-1'])
  assert.deepEqual(E.vorschlaege(null, 'a'), [])
})

test('CHAT-9b/A: Auswahl einsetzen — „@Anzeigename “ + Kennung merken', () => {
  const stelle = E.offeneErwaehnung('Hallo @An', 9)
  const lage = E.einsetzen('Hallo @An', stelle, RUNDE[0], [])
  assert.equal(lage.text, 'Hallo @Anna Beispiel ')
  assert.equal(lage.pos, lage.text.length, 'der Cursor steht hinter dem Leerzeichen')
  assert.deepEqual(lage.merker, [{ mitglied: 'M-1', anzeigename: 'Anna Beispiel' }])
  // Zweimal derselbe Name: EIN Merker, kein Duplikat.
  const zweite = E.einsetzen(lage.text + '@Cl', E.offeneErwaehnung(lage.text + '@Cl', lage.text.length + 3),
    RUNDE[2], lage.merker)
  assert.equal(zweite.text, 'Hallo @Anna Beispiel @Clara Claus ')
  assert.deepEqual(zweite.merker.map((m) => m.mitglied), ['M-1', 'M-3'])
  const nochmal = E.einsetzen(zweite.text + '@An', E.offeneErwaehnung(zweite.text + '@An', zweite.text.length + 3),
    RUNDE[0], zweite.merker)
  assert.deepEqual(nochmal.merker.map((m) => m.mitglied), ['M-1', 'M-3'])
  // Ein Name mit Leerraum wird zusammengehalten (er muss auffindbar bleiben).
  const eng = E.einsetzen('@', { start: 0, ende: 1, begriff: '' },
    { mitglied: 'M-7', anzeigename: '  Ute   Beispiel  ' }, [])
  assert.equal(eng.text, '@Ute Beispiel ')
})

test('CHAT-9b/A: vor dem Senden zählen NUR noch im Text stehende Kennungen', () => {
  const merker = [
    { mitglied: 'M-1', anzeigename: 'Anna Beispiel' },
    { mitglied: 'M-2', anzeigename: 'Bert Brandner' },
  ]
  // Beide stehen im Text → beide gehen hinaus (Reihenfolge des Merkers).
  assert.deepEqual(E.auswahlBereinigen('Hallo @Anna Beispiel und @Bert Brandner, bitte lesen', merker),
    ['M-1', 'M-2'])
  // Der Name wurde gelöscht → die Kennung fällt weg.
  assert.deepEqual(E.auswahlBereinigen('Hallo @Anna Beispiel und Bert, bitte lesen', merker), ['M-1'])
  // Der Name wurde VERÄNDERT → die Kennung fällt weg.
  assert.deepEqual(E.auswahlBereinigen('Hallo @Anna Beispiel2 und @Bert Brandner', merker), ['M-2'])
  // Ohne Erwähnung im Text: keine Kennung (leere Liste).
  assert.deepEqual(E.auswahlBereinigen('Hallo zusammen', merker), [])
  assert.deepEqual(E.auswahlBereinigen('Hallo', []), [])
  // „@Annabelle“ ist NICHT die Erwähnung „@Anna Beispiel“ — der Name muss ganz
  // dastehen und an einem Namensende aufhören.
  assert.deepEqual(E.auswahlBereinigen('@Anna Beispiele', merker), [])
  assert.deepEqual(E.auswahlBereinigen('Test@Anna Beispiel', merker), [], 'kein Wortanfang')
  // Mich selbst erwähne ich nie.
  assert.deepEqual(E.auswahlBereinigen('@Anna Beispiel', merker, { ich: 'M-1' }), [])
  // Höchstens 20 zählen (dieselbe Grenze wie der Server).
  const viele = Array.from({ length: 25 }, (_, i) => ({ mitglied: `M-${100 + i}`, anzeigename: `Person${i}` }))
  const text = viele.map((m) => `@${m.anzeigename}`).join(' ')
  const kennungen = E.auswahlBereinigen(text, viele)
  assert.equal(kennungen.length, E.ERWAEHNUNGEN_MAX)
  assert.equal(E.ERWAEHNUNGEN_MAX, 20)
  // Duplikate im Merker zählen einmal.
  assert.deepEqual(E.auswahlBereinigen('@Anna Beispiel', [merker[0], merker[0]]), ['M-1'])
})

test('CHAT-9b/A: Hervorhebung ist TEXT — „<b>“ im Namen bleibt Text', () => {
  const stuecke = E.hervorheben('Hallo @Anna Beispiel, bitte <b>lesen</b>', RUNDE.slice(0, 1))
  assert.deepEqual(stuecke, [
    { text: 'Hallo ', erwaehnung: false, meine: false },
    { text: '@Anna Beispiel', erwaehnung: true, meine: false },
    { text: ', bitte <b>lesen</b>', erwaehnung: false, meine: false },
  ])
  // Ein Name, der wie HTML aussieht: hervorgehoben wird der TEXT, nichts wird
  // ausgeführt (kein v-html — der Baustein setzt jedes Stück als `{{ }}`).
  const boese = E.hervorheben('Hallo @<b>Anna</b>', [{ mitglied: 'M-X', anzeigename: '<b>Anna</b>' }])
  assert.deepEqual(boese[1], { text: '@<b>Anna</b>', erwaehnung: true, meine: false })
  // Nichts Erwähntes im Text → EIN Stück, keine Hervorhebung.
  assert.deepEqual(E.hervorheben('Hallo @Fremd', []),
    [{ text: 'Hallo @Fremd', erwaehnung: false, meine: false }])
  // „@Annalena“ darf von „@Anna“ nicht zerschnitten werden (längster zuerst).
  const lang = E.hervorheben('@Annalena und @Anna',
    [{ mitglied: 'M-1', anzeigename: 'Anna' }, { mitglied: 'M-2', anzeigename: 'Annalena' }])
  assert.deepEqual(lang.filter((s) => s.erwaehnung).map((s) => s.text), ['@Annalena', '@Anna'])
  // Die eigene Erwähnung wird als solche gekennzeichnet.
  const meine = E.hervorheben('@Anna Beispiel', RUNDE.slice(0, 1), { ich: 'M-1' })
  assert.equal(meine[0].meine, true)
  assert.equal(E.binErwaehnt({ erwaehnt: RUNDE.slice(0, 1) }, { ich: 'M-1' }), true)
  assert.equal(E.binErwaehnt({ erwaehnt: RUNDE.slice(1, 2) }, { ich: 'M-1' }), false)
  assert.equal(E.binErwaehnt({ erwaehnt: RUNDE.slice(0, 1) }, { ich: '' }), false, 'ohne Kennung nicht raten')
  assert.equal(E.hervorheben('', RUNDE).length, 0)
})

test('CHAT-9b/A (R1/6): „@Anna“ zählt NICHT, wenn im Text „@Anna Müller“ steht', () => {
  // Längster Name zuerst verbraucht: die Stelle gehört „Anna Müller“.
  const merker = [
    { mitglied: 'M-1', anzeigename: 'Anna' },
    { mitglied: 'M-2', anzeigename: 'Anna Müller' },
  ]
  assert.deepEqual(E.auswahlBereinigen('Hallo @Anna Müller', merker), ['M-2'],
    'nur die längere Person ist gemeint')
  // Stehen beide Namen im Text, zählen beide (jede Stelle einmal).
  assert.deepEqual(E.auswahlBereinigen('@Anna Müller und @Anna', merker), ['M-1', 'M-2'],
    'Reihenfolge bleibt die des Merkers')
  // Der längste zuerst, aber nur EINMAL je Textstelle: „@Anna Müller“ belegt
  // seine Stelle, „@Anna“ fällt weg, wenn keine zweite Stelle da ist.
  assert.deepEqual(E.auswahlBereinigen('Hi @Anna Müller', merker), ['M-2'])
  // Unabhängig von der Reihenfolge im Merker.
  assert.deepEqual(E.auswahlBereinigen('@Anna Müller', [...merker].reverse()), ['M-2'])
})

test('CHAT-9b/A (R1/6): derselbe Anzeigename ersetzt den alten Merker-Eintrag', () => {
  // Zwei Personen mit demselben Anzeigenamen (zwei Konten): wer zuletzt
  // eingesetzt wurde, steht im Merker — kein zweiter Eintrag daneben.
  const erst = E.einsetzen('@', { start: 0, ende: 1, begriff: '' },
    { mitglied: 'M-1', anzeigename: 'Anna Beispiel' }, [])
  const dann = E.einsetzen(`${erst.text}@`, { start: erst.text.length, ende: erst.text.length + 1, begriff: '' },
    { mitglied: 'M-9', anzeigename: 'Anna Beispiel' }, erst.merker)
  assert.deepEqual(dann.merker, [{ mitglied: 'M-9', anzeigename: 'Anna Beispiel' }],
    'EIN Eintrag, die zuletzt gewählte Kennung')
  // Ein anderer Name kommt dazu (kein Ersetzen).
  const dazu = E.einsetzen(`${dann.text}@`, { start: dann.text.length, ende: dann.text.length + 1, begriff: '' },
    { mitglied: 'M-2', anzeigename: 'Bert Brandner' }, dann.merker)
  assert.deepEqual(dazu.merker.map((m) => m.mitglied), ['M-9', 'M-2'])
})

test('CHAT-9b/A (R1/3): IME erkennen und reine Auswahltasten benennen', () => {
  assert.equal(E.istEingabemethode({ isComposing: true }), true)
  assert.equal(E.istEingabemethode({ keyCode: 229 }), true)
  assert.equal(E.istEingabemethode({ key: 'Enter', keyCode: 13 }), false)
  assert.equal(E.istEingabemethode(null), false)
  for (const k of ['Escape', 'ArrowUp', 'ArrowDown', 'Enter', 'Tab']) {
    assert.equal(E.nurAuswahlTaste(k), true, k)
  }
  for (const k of ['a', 'Backspace', ' ', 'Shift']) {
    assert.equal(E.nurAuswahlTaste(k), false, k)
  }
})

test('CHAT-9b/A: Tasten der Auswahl und die Stelle', () => {
  assert.equal(E.auswahlTaste({ key: 'Enter', offen: true, anzahl: 2 }), 'waehlen')
  assert.equal(E.auswahlTaste({ key: 'Enter', offen: false, anzahl: 2 }), 'sonst', 'geschlossen: senden')
  assert.equal(E.auswahlTaste({ key: 'Escape', offen: true, anzahl: 2 }), 'schliessen')
  assert.equal(E.auswahlTaste({ key: 'ArrowDown', offen: true, anzahl: 2 }), 'weiter')
  assert.equal(E.auswahlTaste({ key: 'ArrowUp', offen: true, anzahl: 2 }), 'zurueck')
  assert.equal(E.auswahlTaste({ key: 'Tab', offen: true, anzahl: 2 }), 'waehlen')
  assert.equal(E.auswahlTaste({ key: 'ArrowDown', offen: true, anzahl: 0 }), 'sonst', 'leere Liste frisst nichts')
  assert.equal(E.naechsteStelle(0, -1, 3), 2, 'umlaufend')
  assert.equal(E.naechsteStelle(2, 1, 3), 0)
  assert.equal(E.optionKennung('liste', 2), 'liste-2')
})

// ── CHAT-9b-2: die Auswahl fragt je Namensanfang ────────────────────────────

test('CHAT-9b-2/A: Frage, Schlüssel und Antwort des Servers (Vertrag CHAT-9c-2)', () => {
  // Grenzen an EINER Stelle.
  assert.equal(E.ERWAEHNUNG_ANZAHL, 20)
  assert.equal(E.ERWAEHNUNG_ENTPRELLUNG_MS, 200)
  assert.equal(E.ERWAEHNUNG_Q_MAX, 40)
  // Der Name nach dem „@“ ist die Frage: getrimmt, gekürzt, leer erlaubt.
  assert.equal(E.erwaehnungFrage(''), '', '„@“ allein fragt die ersten 20')
  assert.equal(E.erwaehnungFrage('  An '), 'An')
  assert.equal(E.erwaehnungFrage('x'.repeat(60)), 'x'.repeat(40), 'bis 40 Zeichen')
  assert.equal(E.erwaehnungFrage(null), '')
  // Der Schlüssel trennt Gespräch und Frage und ist falt-gleich.
  assert.equal(E.erwaehnungSchluessel('CHAT-R1', 'Anna'), E.erwaehnungSchluessel('CHAT-R1', 'anna'),
    'Groß-/Kleinschreibung ist dieselbe Frage')
  assert.notEqual(E.erwaehnungSchluessel('CHAT-R1', 'Anna'), E.erwaehnungSchluessel('CHAT-R1', 'ann'))
  assert.notEqual(E.erwaehnungSchluessel('CHAT-R1', ''), E.erwaehnungSchluessel('CHAT-G1', ''),
    'dasselbe leere q in zwei Gesprächen ist NICHT dieselbe Frage')
  // Nur der aktuelle Schlüssel zählt (veraltete Antwort verwerfen).
  assert.equal(E.istAktuelleFrage(E.erwaehnungSchluessel('CHAT-R1', 'An'),
    E.erwaehnungSchluessel('CHAT-R1', 'an')), true)
  assert.equal(E.istAktuelleFrage(E.erwaehnungSchluessel('CHAT-R1', 'An'),
    E.erwaehnungSchluessel('CHAT-R1', 'Ann')), false)
  assert.equal(E.istAktuelleFrage('x', null), false, 'ohne offene Frage zählt nichts')
  // Die Antwort lesen: `mehr` NUR wenn der Server es sagt, Müll fällt weg,
  // ich selbst komme nie vor.
  const gelesen = E.erwaehnungAntwort({
    art: 'runde',
    mitglieder: [
      { mitglied: 'M-1', anzeigename: 'Anna Beispiel' },
      { mitglied: '', anzeigename: 'Ohne Kennung' },
      null,
      { mitglied: 'M-1', anzeigename: 'Anna Beispiel (doppelt)' },
      { mitglied: 'M-9', anzeigename: 'Ich Selbst' },
    ],
    mehr: true,
  }, { ich: 'M-9' })
  assert.deepEqual(gelesen.mitglieder, [{ mitglied: 'M-1', anzeigename: 'Anna Beispiel' }])
  assert.equal(gelesen.mehr, true)
  assert.equal(E.erwaehnungAntwort({ mitglieder: [] }).mehr, false, 'ohne Feld kein „mehr“')
  assert.equal(E.erwaehnungAntwort({ mitglieder: [], mehr: 'ja' }).mehr, false,
    'nur `true` ist ein Ja')
  assert.deepEqual(E.erwaehnungAntwort(null), { mitglieder: [], mehr: false })
  // Der „mehr“-Hinweis (R1/3) ist keine Wahl — er zählt nicht mit.
  assert.equal(E.auswahlAnzahl(RUNDE), 3)
  assert.equal(E.auswahlAnzahl(null), 0)
})

test('CHAT-9b-2/A (R1/2): die gezeigte Antwort hält den letzten Stand — ohne Flackern', () => {
  const an = E.erwaehnungSchluessel('CHAT-R1', 'An')
  const ann = E.erwaehnungSchluessel('CHAT-R1', 'Ann')
  const fremd = E.erwaehnungSchluessel('CHAT-G1', 'An')
  const antworten = { [an]: { mitglieder: [{ mitglied: 'M-1', anzeigename: 'Anna Beispiel' }] } }
  // Antwort zum aktuellen q ist da → sie gilt.
  assert.equal(E.antwortSchluessel(an, ann, antworten), an)
  // Antwort zum aktuellen q fehlt → die ZULETZT beantwortete desselben
  // Gesprächs bleibt stehen (lokal wird darauf gefiltert).
  assert.equal(E.antwortSchluessel(ann, an, antworten), an, 'kein Auf-/Zuklappen beim Weitertippen')
  assert.equal(E.antwortSchluessel(ann, ann, antworten), null,
    'der „zuletzt beantwortete“ ist selbst nicht gemerkt → nichts zu zeigen')
  assert.equal(E.antwortSchluessel(ann, fremd, antworten), null,
    'anderes Gespräch: kein Stand, der hier nicht gilt')
  assert.equal(E.antwortSchluessel(null, an, antworten), null, 'keine Frage → nichts')
  assert.equal(E.antwortSchluessel(an, null, {}), null, 'nichts gemerkt → nichts')
  // Lokal gefiltert wird mit der Wortanfang-Regel des Servers (R1/1).
  assert.deepEqual(E.vorschlaege(antworten[an].mitglieder, 'Ann').map((m) => m.mitglied), ['M-1'])
  assert.deepEqual(E.vorschlaege(antworten[an].mitglieder, 'Anx').map((m) => m.mitglied), [])
})

// ════════════════════════════════════════════════════════════════════════════
// Gemeinsame Probebauten für die Mounts
// ════════════════════════════════════════════════════════════════════════════

const ICH = 'M-9' // die eigene Mitglieds-Kennung in allen Mounts

/** Eine Nachrichtenzeile, wie `_zeile` sie liefert (nur die hier zählenden Felder). */
function zeile(name, text, { eigene = false, autor = 'Anna Beispiel', erwaehnt = [], ...rest } = {}) {
  return {
    name, ident: name, id: name, text, eigene, autor, erstellt_am: '2026-11-18 10:00:00',
    zeit: '10:00', bearbeitet: false, geloescht: false, geloescht_grund: null, reaktionen: [],
    antwort_auf: null, antwortAuf: null, antwortText: '', gelesen_von: eigene ? 0 : null,
    erwaehnt, ...rest,
  }
}

const RUNDE_KOPF = {
  name: 'CHAT-R1', art: 'runde', gruppe: null, untergruppe: null, titel: 'Samstag-Deko',
  mitglied: null, bild: '', teilnehmer: 3, stumm: false, geoeffnet: true, ungelesen: 0,
  letzte_nachricht: 'Hallo', letzte_am: '2026-11-18 10:00:00', darf_senden: true,
  mitglieder: RUNDE,
}

const DIREKT_KOPF = {
  name: 'CHAT-D1', art: 'direkt', gruppe: null, untergruppe: null, titel: 'Bert B.',
  mitglied: 'M-2', bild: '', teilnehmer: 2, stumm: false, geoeffnet: true, ungelesen: 0,
  letzte_nachricht: 'Hallo', letzte_am: '2026-11-18 10:00:00', darf_senden: true,
  // CHAT-9c liefert auch im 1:1 den VOLLEN Namen (nicht den gekürzten `titel`).
  mitglieder: [{ mitglied: 'M-2', anzeigename: 'Bert Brandner' }],
}

const GRUPPE_KOPF = {
  name: 'CHAT-G1', art: 'gruppe', gruppe: 'chor', untergruppe: null, titel: 'Chor',
  mitglied: null, bild: '', teilnehmer: 3, stumm: false, geoeffnet: true, ungelesen: 0,
  letzte_nachricht: 'Hallo', letzte_am: '2026-11-18 10:00:00', darf_senden: true,
  mitglieder: [
    { mitglied: 'M-1', anzeigename: 'Anna Beispiel' },
    { mitglied: 'M-2', anzeigename: 'Bert Brandner' },
    { mitglied: 'M-3', anzeigename: 'Clara Claus' },
    { mitglied: 'M-4', anzeigename: 'Dieter Dorn' },
  ],
}

/**
 * Die Seite „Nachrichten“ mounten. Die Attrappe TRENNT GET und POST (eigene
 * Zähler und eigene Antworten) und liefert die ECHTEN Antwortformen aus
 * CHAT-9a. Die Sende-Antwort trägt dieselbe Erwähnungsliste wie der Verlauf
 * (so wie `chat.senden` sie liefert), ohne dass der Server nachgebaut wird.
 *
 * CHAT-9b-2: Die Attrappe hält den VERTRAG von CHAT-9c-2 ein —
 * `chat.gespraech_mitglieder(gespraech, q, limit)` (GET) →
 * `{art, mitglieder: [{mitglied, anzeigename}], mehr}`. Eine unbekannte/fremde
 * Gesprächskennung WIRFT (404) statt eine Nutzlast zu liefern — wie der Server.
 * `q` filtert die Beteiligten an jedem WORTANFANG des Namens (dieselbe Regel
 * wie der Server, R1/1: gefaltet wie `suchNormal`; Vorname, Nachname oder der
 * ganze Name beginnt mit `q` — „An“ trifft NICHT „Bert Brandner“, „b“ sehr
 * wohl, ein Zeichen genügt). `limit` schneidet ab und setzt `mehr`.
 * `filtert: false` (nur für den Wettlauf-Test) liefert den Server-Vertrag OHNE
 * Filterei: dann entscheidet allein der lokale Filter, was in der Liste steht.
 */
async function seiteMontieren({ kopf = RUNDE_KOPF, nachrichten = [], handy = false,
  mitglieder = null, mitgliederFehler = false, mitgliederAntwort = null,
  mitgliederLangsam = 0, filtert = true } = {}) {
  const ordner = join(TMP, 'seite-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  const api = join(ordner, 'api.mjs')
  writeFileSync(api, [
    'export async function apiCall(methode, parameter) {',
    "  if (typeof globalThis.__SEITE_POST === 'function') return globalThis.__SEITE_POST(methode, parameter)",
    '  return globalThis.__SEITE_SERVER({ methode, parameter, art: "POST" })',
    '}',
    'export async function apiGet(methode, parameter) {',
    '  return globalThis.__SEITE_SERVER({ methode, parameter, art: "GET" })',
    '}',
    "export const apiUrl = (p) => 'https://pruefstand.invalid/' + p",
    'export class AuditConfirmationRequired extends Error {}',
    'export const pruefeSitzungsAntwort = () => false',
    'export const apiAntwortPruefen = async () => ({ message: {} })',
  ].join('\n'))
  const session = join(ordner, 'session.mjs')
  writeFileSync(session, [
    `import { ref } from '${VUE_URL}'`,
    'export function useSession() {',
    '  return { istTester: ref(false), devmodeAn: ref(false),',
    `    mitglied: ref({ name: '${ICH}', vorname: 'Ich', nachname: 'Selbst' }),`,
    "    istAdmin: ref(false), istGast: ref(false), fullName: ref('Ich Selbst'),",
    "    rollen: ref([]), abmelden: async () => {}, sitzungPruefen: async () => {} }",
    '}',
  ].join('\n'))

  const gesendet = []
  const gelesen = []
  const zeilen = nachrichten.map((n) => ({ ...n }))
  // Der Vertrag von CHAT-9c-2: `chat.gespraech_mitglieder(gespraech, q, limit)`
  // (GET) → `{art, mitglieder: [{mitglied, anzeigename}], mehr}`, OHNE die
  // lesende Person. Vorgabe: alle Beteiligten des Kopfes ohne M-9 (mich).
  const bekannte = mitglieder || (Array.isArray(kopf.mitglieder) ? kopf.mitglieder : RUNDE)
  const beteiligteAmServer = bekannte.filter((m) => String(m.mitglied) !== ICH)
  globalThis.__SEITE_POST = null
  globalThis.__SEITE_SERVER = ({ methode, parameter, art }) => {
    const kurz = String(methode).split('.').pop()
    if (art === 'POST') gesendet.push({ methode, parameter })
    else gelesen.push({ methode, parameter })
    if (kurz === 'meine_gespraeche') return { gespraeche: [{ ...kopf }] }
    if (kurz === 'gespraech_mitglieder') {
      if (mitgliederFehler) throw fehler(403, 'kein Zugriff')
      // Unbekannte/fremde Kennung: der Server WIRFT (404) — er liefert keine
      // leere Nutzlast, die wie „niemand da“ aussähe.
      if (String(parameter?.gespraech || '') !== String(kopf.name)) {
        throw fehler(404, 'Gespräch nicht gefunden')
      }
      if (typeof mitgliederAntwort === 'function') return mitgliederAntwort(parameter)
      const q = String(parameter?.q ?? '').trim()
      const limit = Number.isInteger(parameter?.limit) ? parameter.limit : 20
      // R1/1: WORTANFANG wie der Server (CHAT-9c-2) — Vorname, Nachname oder
      // der ganze Name beginnt mit `q`, gefaltet wie `suchNormal`. KEIN
      // Teilwort-Treffer mitten im Namen („an“ trifft NICHT „Bert Brandner“);
      // ein Zeichen genügt („b“ → „Bert Brandner“, „Anna B.“).
      const nadel = suchNormal(q)
      const trifft = (name) => {
        const gefaltet = suchNormal(String(name || ''))
        if (!nadel) return true
        if (gefaltet.startsWith(nadel)) return true
        return gefaltet.split(/\s+/).some((wort) => wort.startsWith(nadel))
      }
      const treffer = beteiligteAmServer.filter((m) => {
        if (!filtert) return true
        return trifft(m.anzeigename)
      })
      const seite = treffer.slice(0, limit)
      const antwort = {
        art: String(kopf.art || ''),
        mitglieder: seite.map((m) => ({ ...m })),
        mehr: treffer.length > seite.length,
      }
      // `mitgliederLangsam`: die Antwort kommt SPÄT (Wettlauf für den Test
      // „veraltete Antwort wird verworfen“).
      if (mitgliederLangsam > 0) {
        return new Promise((loese) => setTimeout(() => loese(antwort), mitgliederLangsam))
      }
      return antwort
    }
    if (kurz === 'verlauf') return { gespraech: kopf.name, richtung: 'neueste', nachrichten: zeilen.map((n) => ({ ...n })) }
    if (kurz === 'lesestand_setzen') return { gespraech: kopf.name, bis: null, ungelesen: 0 }
    if (kurz === 'senden') {
      // Dieselbe Form wie `chat.senden`: die Zeile plus die gespeicherte Liste.
      const neu = zeile('N-NEU', String(parameter?.text || ''), {
        eigene: true,
        autor: 'Ich Selbst',
        erwaehnt: (parameter?.erwaehnt || []).map((k) => bekannte.find((m) => m.mitglied === k)
          || { mitglied: k, anzeigename: `Person ${k}` }),
      })
      zeilen.push(neu)
      return neu
    }
    return {}
  }
  dom.window.__DIakonosBOOT = { roles: ['Mitglied'], is_admin: false, module_sichtbar: ['chat'] }
  dom.window.location.hash = `#/nachrichten/${kopf.name}`
  handyAbfrage(handy)

  const U = (rel) => pathToFileURL(SRC.pathname + rel).href
  umleitung.clear()
  umleitung.set(U('composables/useApi.js'), pathToFileURL(api).href)
  umleitung.set(U('composables/useSession.js'), pathToFileURL(session).href)

  // Die Seite führt einen Chat-Takt (echter Timer): beim Abbau einsammeln,
  // sonst liefe der Prozess nach dem letzten Test ins Zeitlimit.
  const gestartet = new Set()
  const origT = globalThis.setTimeout
  const origI = globalThis.setInterval
  globalThis.setTimeout = (fn, ms) => { const id = origT(fn, ms); gestartet.add(id); return id }
  globalThis.setInterval = (fn, ms) => { const id = origI(fn, ms); gestartet.add(id); return id }
  let gemountet = null
  try {
    const mod = (await import(pathToFileURL(baum('pages/Nachrichten.vue', { frisch: true, ordner })).href)).default
    gemountet = await mounten(mod, {})
  } finally {
    globalThis.setTimeout = origT
    globalThis.setInterval = origI
  }
  const s = gemountet
  const abraeumen = () => { for (const t of gestartet) { try { clearTimeout(t); clearInterval(t) } catch { /* egal */ } } }
  const abbaumVorher = gemountet.abbaum
  const abbaum = () => { abbaumVorher(); abraeumen() }
  await rendern(6)
  await warte(12)
  await rendern(6)
  aktuelleSeite = { ...gemountet, abbaum, gesendet, gelesen }
  return aktuelleSeite
}

/** Die zuletzt gemountete Seite (für `tippenWarten`, das auf ihre Antworten wartet). */
let aktuelleSeite = null

/** Das Eingabefeld der Seite. */
const feld = (host) => host.querySelector('textarea#chat-eingabe')

/**
 * Bis zur Antwort auf den Namensanfang `q` warten — ohne feste Taktzahl.
 * (Der Entpreller wartet 200 ms ECHT; ein Test, der nur Takte zählt, sähe die
 * Antwort nie.) Gesucht wird die Antwort zu GENAU dieser Frage.
 */
async function aufFrage(seite, q, maxMs = 2000) {
  const ende = Date.now() + maxMs
  for (;;) {
    const da = seite.gelesen.some((g) => g.methode === 'chat.gespraech_mitglieder'
      && g.parameter.q === q)
    await warte(4)
    await rendern(4)
    if (da) {
      // Eine Runde mehr: die Antwort in die Oberfläche zu tragen ist ein Versprechen.
      await warte(8)
      await rendern(6)
      return
    }
    if (Date.now() > ende) throw new Error(`keine Antwort zu q=${JSON.stringify(q)}`)
  }
}

/** Genau `ms` Echtzeit verstreichen lassen (Entprellung ist Zeit, nicht Takt). */
const ruhe = (ms) => new Promise((loese) => setTimeout(loese, ms))

/**
 * Tippen im Feld: Wert setzen, Cursor ans Ende, `input` auslösen (das ist der
 * Weg, auf den die Seite horcht — kein geratener Zustand).
 */
async function tippen(host, wert, pos = null) {
  const el = feld(host)
  assert.ok(el, 'das Eingabefeld steht im DOM')
  el.value = wert
  const stelle = pos === null ? wert.length : pos
  if (typeof el.setSelectionRange === 'function') el.setSelectionRange(stelle, stelle)
  el.dispatchEvent(new dom.window.Event('input', { bubbles: true }))
  await rendern()
  return el
}

/**
 * Tippen UND die Antwort auf den neuen Namensanfang abwarten.
 *
 * Die Beteiligten kommen seit CHAT-9b-2 aus dem Server, JE NAMENSANFANG —
 * entprellt. Ein Test, der nach dem Tippen sofort die Liste prüft, sähe die
 * neue Antwort noch nicht; hier wird auf die echte Antwort zu `q` gewartet,
 * nicht auf eine feste Zahl von Takten.
 */
async function tippenWarten(host, wert, pos = null) {
  const el = await tippen(host, wert, pos)
  const stelle = E.offeneErwaehnung(wert, pos === null ? wert.length : pos)
  if (stelle) await aufFrage(aktuelleSeite, stelle.begriff)
  else { await ruhe(260); await rendern(6) }
  return el
}

/**
 * Die Einträge der Auswahl (Namen, in der Reihenfolge der Liste). Die
 * nicht wählbare „mehr“-Zeile zählt mit (ihr Text steht direkt im `<li>`, ohne
 * `.dk-erw-name`) — so prüfbar, ob sie WIRKLICH die letzte Zeile ist.
 */
const auswahlNamen = (host) => [...host.querySelectorAll('.dk-erw-eintrag')]
  .map((e) => (e.querySelector('.dk-erw-name') || e).textContent.trim())

// ════════════════════════════════════════════════════════════════════════════
// B · Seite gemountet: Runde
// ════════════════════════════════════════════════════════════════════════════

test('CHAT-9b/B: „@“ öffnet die Auswahl, Tippen filtert, Enter übernimmt', async () => {
  const s = await seiteMontieren()
  assert.equal(s.warnungen.length, 0, 'keine Vue-Warnung: ' + s.warnungen.join(' | '))

  // Ohne „@“ gibt es keine Auswahl.
  await tippen(s.host, 'Hallo zusammen')
  assert.equal(s.host.querySelector('.dk-erw'), null, 'ohne „@“ keine Liste')

  // „@“ am Wortanfang öffnet sie — mit den Beteiligten außer mir.
  const el = await tippenWarten(s.host, 'Hallo @')
  // Die Quelle ist die EINE Abfrage (GET), nicht der Kopf aus meine_gespraeche.
  // CHAT-9b-2: gefragt wird der NAMENSANFANG (hier leer = „@“ allein) mit
  // fester Anzahl.
  const abfrage = s.gelesen.filter((g) => g.methode === 'chat.gespraech_mitglieder')
  assert.equal(abfrage.length, 1, 'einmal gefragt')
  assert.deepEqual(abfrage[0].parameter, { gespraech: 'CHAT-R1', q: '', limit: 20 })
  assert.equal(s.gesendet.filter((g) => g.methode === 'chat.gespraech_mitglieder').length, 0,
    'die Abfrage ist GET (apiGet), kein POST')
  const liste = s.host.querySelector('.dk-erw')
  assert.ok(liste, 'die Auswahl steht im DOM')
  // CHAT-9b-2 (Entscheidung Operator): KEINE `role="combobox"` am mehrzeiligen
  // Feld (axe-sauber) — die Beziehung Feld→Liste steht über die ARIA-Attribute.
  assert.equal(el.getAttribute('role'), null, 'kein role="combobox" am <textarea>')
  assert.equal(el.getAttribute('aria-haspopup'), 'listbox')
  assert.equal(el.getAttribute('aria-autocomplete'), 'list')
  assert.equal(el.getAttribute('aria-expanded'), 'true')
  assert.equal(el.getAttribute('aria-controls'), 'dk-erwaehnung-liste')
  assert.equal(s.host.querySelector('#dk-erwaehnung-liste').getAttribute('role'), 'listbox')
  assert.deepEqual(auswahlNamen(s.host), ['Anna Beispiel', 'Bert Brandner', 'Clara Claus'],
    'alle Beteiligten — ich selbst (M-9) bin nicht dabei')
  assert.equal(el.getAttribute('aria-activedescendant'), 'dk-erwaehnung-liste-0')
  const optionen = [...s.host.querySelectorAll('.dk-erw-eintrag')]
  assert.equal(optionen[0].getAttribute('role'), 'option')
  assert.equal(optionen[0].getAttribute('aria-selected'), 'true')
  // R1/5: die Trefferzahl wird angesagt (höflich), und der Pfeiltasten-Satz
  // steht im Baustein getrennt für feine Zeiger.
  assert.equal(s.host.querySelector('.dk-chat-eingabe-zeile [aria-live="polite"]').textContent.trim(),
    '3 Namen zur Auswahl')
  assert.match(s.host.querySelector('.dk-erw-hinweis').textContent, /Zum Erwähnen antippen/)
  assert.equal(s.host.querySelector('.dk-erw-mehr'), null, 'nichts verheimlicht: keine mehr-Zeile')

  // Tippen filtert (lokal UND über die neue Frage — die Antwort ist schon da).
  await tippenWarten(s.host, 'Hallo @Ber')
  assert.deepEqual(auswahlNamen(s.host), ['Bert Brandner'])
  // CHAT-9b-2: der neue Namensanfang wird GEFRAGT (nicht mehr die Vollliste).
  const nachTippen = s.gelesen.filter((g) => g.methode === 'chat.gespraech_mitglieder')
  assert.deepEqual(nachTippen.map((g) => g.parameter.q), ['', 'Ber'])
  assert.deepEqual(nachTippen[1].parameter, { gespraech: 'CHAT-R1', q: 'Ber', limit: 20 })

  // Enter übernimmt den aktiven Eintrag — und SENDET NICHT.
  const gesendetVorher = s.gesendet.filter((g) => g.methode === 'chat.senden').length
  const enter = taste(feld(s.host), 'Enter')
  assert.equal(enter.defaultPrevented, true, 'Enter gehört der Auswahl, nicht dem Formular')
  await rendern()
  assert.equal(feld(s.host).value, 'Hallo @Bert Brandner ')
  assert.equal(s.host.querySelector('.dk-erw'), null, 'nach der Auswahl ist die Liste zu')
  assert.equal(s.gesendet.filter((g) => g.methode === 'chat.senden').length, gesendetVorher,
    'die Auswahl sendet nichts')
  s.abbaum()
})

test('CHAT-9b/B: ohne Treffer ist die Auswahl zu (kein aria-activedescendant)', async () => {
  const s = await seiteMontieren()
  await tippenWarten(s.host, '@')
  assert.ok(s.host.querySelector('.dk-erw'), 'die Liste steht')
  // „@xyz“ filtert alles weg: keine Liste im DOM und nichts angekündigt.
  const el = await tippenWarten(s.host, '@xyz')
  assert.equal(s.host.querySelector('.dk-erw'), null, 'kein Treffer, keine Liste')
  assert.equal(el.getAttribute('aria-expanded'), 'false')
  assert.equal(el.getAttribute('aria-haspopup'), 'listbox', 'die Möglichkeit bleibt angesagt')
  assert.equal(el.getAttribute('aria-controls'), null, 'ohne Liste kein aria-controls')
  assert.equal(el.getAttribute('aria-activedescendant'), null,
    'ohne Liste kein aria-activedescendant')
  assert.equal(s.host.querySelector('.dk-chat-eingabe-zeile [aria-live="polite"]').textContent.trim(), '')
  s.abbaum()
})

test('CHAT-9b/B: eine IME-Eingabe bedient die Liste nicht (Enter/Escape gehören ihr)', async () => {
  const s = await seiteMontieren()
  await tippenWarten(s.host, '@')
  const vorher = feld(s.host).getAttribute('aria-activedescendant')
  const enter = taste(feld(s.host), 'Enter', { isComposing: true })
  assert.equal(enter.defaultPrevented, false, 'Enter beim IME bleibt beim Feld (kein Senden)')
  await rendern()
  assert.ok(s.host.querySelector('.dk-erw'), 'die Liste bleibt unberührt offen')
  // … und der Text wurde NICHT eingesetzt (kein „@Name “), nichts gesendet.
  assert.equal(feld(s.host).value, '@')
  assert.equal(feld(s.host).getAttribute('aria-activedescendant'), vorher,
    'die aktive Stelle bleibt, wo sie war')
  assert.equal(s.gesendet.filter((g) => g.methode === 'chat.senden').length, 0)
  s.abbaum()
})

test('CHAT-9b/B: ↓/↑ bewegen, Escape schließt ohne Auswahl und ohne Senden', async () => {
  const s = await seiteMontieren()
  await tippenWarten(s.host, '@')
  const el = feld(s.host)
  assert.equal(el.getAttribute('aria-activedescendant'), 'dk-erwaehnung-liste-0')

  taste(el, 'ArrowDown')
  await rendern()
  assert.equal(feld(s.host).getAttribute('aria-activedescendant'), 'dk-erwaehnung-liste-1')
  assert.equal([...s.host.querySelectorAll('.dk-erw-eintrag')][1].getAttribute('aria-selected'), 'true')
  taste(el, 'ArrowDown')
  await rendern()
  taste(el, 'ArrowDown')
  await rendern()
  assert.equal(feld(s.host).getAttribute('aria-activedescendant'), 'dk-erwaehnung-liste-0',
    'umlaufend nach unten')
  taste(el, 'ArrowUp')
  await rendern()
  assert.equal(feld(s.host).getAttribute('aria-activedescendant'), 'dk-erwaehnung-liste-2',
    'umlaufend nach oben')

  // Escape schließt die Auswahl — der Text bleibt, gesendet wird nichts.
  const escape = taste(feld(s.host), 'Escape')
  assert.equal(escape.defaultPrevented, true)
  await rendern()
  assert.equal(s.host.querySelector('.dk-erw'), null)
  assert.equal(feld(s.host).value, '@')
  assert.equal(feld(s.host).getAttribute('aria-expanded'), 'false')
  assert.equal(s.gesendet.filter((g) => g.methode === 'chat.senden').length, 0)
  s.abbaum()
})

test('CHAT-9b/B (R1/1): Escape bleibt zu — auch nach dem keyup', async () => {
  const s = await seiteMontieren()
  await tippenWarten(s.host, 'Hallo @')
  assert.ok(s.host.querySelector('.dk-erw'), 'die Liste stand offen')

  // Echter Ablauf am Browser: keydown UND keyup. Vorher öffnete das `keyup`
  // die Liste nach dem Escape sofort wieder (`@keyup="erwaehnungPruefen"`).
  const el = feld(s.host)
  const runter = taste(el, 'Escape')
  assert.equal(runter.defaultPrevented, true, 'Escape gehört der Auswahl')
  el.dispatchEvent(new dom.window.KeyboardEvent('keyup', { key: 'Escape', bubbles: true, cancelable: true }))
  await rendern(6)
  assert.equal(s.host.querySelector('.dk-erw'), null, 'nach dem keyup bleibt die Liste ZU')
  assert.equal(el.getAttribute('aria-expanded'), 'false')
  assert.equal(el.value, 'Hallo @', 'der Text bleibt unverändert')

  // Auch ein Klick ins Feld öffnet sie an DIESER Stelle nicht wieder…
  el.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }))
  await rendern(4)
  assert.equal(s.host.querySelector('.dk-erw'), null, 'auch der Klick öffnet nicht wieder')

  // …erst NEUE Eingabe tut es (hinter demselben „@“ weitergetippt).
  await tippenWarten(s.host, 'Hallo @Ber')
  assert.deepEqual(auswahlNamen(s.host), ['Bert Brandner'], 'neue Eingabe öffnet wieder')
  s.abbaum()
})

test('CHAT-9b/B: ↑/↓ im keyup lassen die Liste, wie sie ist', async () => {
  const s = await seiteMontieren()
  await tippenWarten(s.host, '@')
  const el = feld(s.host)
  for (const k of ['ArrowDown', 'ArrowUp']) {
    taste(el, k)
    await rendern()
    el.dispatchEvent(new dom.window.KeyboardEvent('keyup', { key: k, bubbles: true, cancelable: true }))
    await rendern()
    assert.ok(s.host.querySelector('.dk-erw'), `${k}: die Liste bleibt offen`)
  }
  // Tab wählt (das ist seine Aufgabe) — danach steht der Name im Text, und das
  // keyup öffnet keine zweite Liste über dem eingesetzten Namen.
  const tab = taste(el, 'Tab')
  assert.equal(tab.defaultPrevented, true, 'Tab gehört der Auswahl')
  await rendern()
  el.dispatchEvent(new dom.window.KeyboardEvent('keyup', { key: 'Tab', bubbles: true, cancelable: true }))
  await rendern()
  assert.equal(el.value, '@Anna Beispiel ', 'Tab übernimmt den aktiven Eintrag')
  assert.equal(s.host.querySelector('.dk-erw'), null, 'keine zweite Liste nach Tab')
  s.abbaum()
})

test('CHAT-9b/B: Senden schickt nur noch im Text stehende Kennungen', async () => {
  const s = await seiteMontieren()
  // Zwei Erwähnungen einsetzen …
  await tippenWarten(s.host, 'Hallo @')
  taste(feld(s.host), 'Enter') // Anna
  await rendern()
  const zwischen = `${feld(s.host).value}und @`
  await tippen(s.host, zwischen)
  // … den zweiten Eintrag per Tipp wählen (das Handy hat keine Pfeiltasten).
  const zweiter = [...s.host.querySelectorAll('.dk-erw-eintrag')]
    .find((e) => /Clara/.test(e.textContent))
  assert.ok(zweiter, 'Clara steht in der Liste')
  zweiter.dispatchEvent(new dom.window.MouseEvent('mousedown', { bubbles: true, cancelable: true }))
  await rendern()
  assert.equal(feld(s.host).value, 'Hallo @Anna Beispiel und @Clara Claus ')
  await tippen(s.host, `${feld(s.host).value}bitte übernehmen.`)

  klick([...s.host.querySelectorAll('button')].find((b) => /Nachricht senden/.test(b.textContent)))
  await rendern(8)
  const senden = s.gesendet.filter((g) => g.methode === 'chat.senden').pop()
  assert.ok(senden, 'chat.senden wurde gerufen')
  assert.deepEqual(senden.parameter.erwaehnt, ['M-1', 'M-3'],
    'beide Kennungen — in der Reihenfolge der Auswahl')
  assert.equal(senden.parameter.text, 'Hallo @Anna Beispiel und @Clara Claus bitte übernehmen.',
    'der Text bleibt, wie er getippt wurde')
  // Die Antwort des Servers zeigt die Erwähnung: Liste im Merker ist geleert.
  await tippenWarten(s.host, '@')
  klick([...s.host.querySelectorAll('button')].find((b) => /Nachricht senden/.test(b.textContent)))
  await rendern(8)
  s.abbaum()
})

test('CHAT-9b/B: gelöschter Name fällt beim Senden weg — ohne Erwähnung KEIN Feld', async () => {
  const s = await seiteMontieren()
  await tippenWarten(s.host, '@')
  taste(feld(s.host), 'Enter')
  await rendern()
  assert.equal(feld(s.host).value, '@Anna Beispiel ')

  // Den Namen wieder löschen (der Merker bleibt stehen, der Text sagt etwas
  // anderes) — geschickt wird OHNE `erwaehnt`.
  await tippen(s.host, 'Nur ein Text')
  klick([...s.host.querySelectorAll('button')].find((b) => /Nachricht senden/.test(b.textContent)))
  await rendern(8)
  const ohne = s.gesendet.filter((g) => g.methode === 'chat.senden').pop()
  assert.ok(ohne, 'gesendet')
  assert.equal('erwaehnt' in ohne.parameter, false,
    'ohne Erwähnung geht kein Feld hinaus (der Server liest das als „keine“)')

  // Und ein VERÄNDERTER Name ebenso: „@Anna Beispiel2“ ist nicht Anna.
  await tippenWarten(s.host, '@')
  taste(feld(s.host), 'Enter')
  await rendern()
  await tippen(s.host, '@Anna Beispiel2')
  klick([...s.host.querySelectorAll('button')].find((b) => /Nachricht senden/.test(b.textContent)))
  await rendern(8)
  const veraendert = s.gesendet.filter((g) => g.methode === 'chat.senden').pop()
  assert.equal('erwaehnt' in veraendert.parameter, false)
  s.abbaum()
})

test('CHAT-9b/B: das Leerzeichen beendet die Auswahl (kein Namensraten)', async () => {
  const s = await seiteMontieren({ kopf: { ...RUNDE_KOPF, mitglieder: [
    { mitglied: 'M-1', anzeigename: 'Anna Beispiel' },
    { mitglied: 'M-4', anzeigename: 'Anna' },
  ] } })
  await tippenWarten(s.host, '@Anna')
  assert.deepEqual(auswahlNamen(s.host), ['Anna Beispiel', 'Anna'])
  await tippen(s.host, '@Anna ')
  assert.equal(s.host.querySelector('.dk-erw'), null, 'hinter dem Leerzeichen keine Auswahl mehr')
  // Enter sendet jetzt wirklich (die Auswahl ist zu) — mit der Nachricht.
  const el = feld(s.host)
  taste(el, 'Enter')
  await rendern(8)
  const senden = s.gesendet.filter((g) => g.methode === 'chat.senden')
  assert.equal(senden.length, 1, 'Enter ohne offene Auswahl sendet')
  assert.equal('erwaehnt' in senden[0].parameter, false, 'getippter Text allein erwähnt niemanden')
  s.abbaum()
})

// ════════════════════════════════════════════════════════════════════════════
// C · 1:1 — die andere Person, nicht ich
// ════════════════════════════════════════════════════════════════════════════

test('CHAT-9b/C (R1/2): im 1:1 kommt die andere Person aus gespraech_mitglieder', async () => {
  const s = await seiteMontieren({ kopf: DIREKT_KOPF })
  await tippenWarten(s.host, '@')
  // Der VOLLE Name aus der einen Abfrage — nicht der gekürzte `titel` („Bert B.“).
  assert.deepEqual(auswahlNamen(s.host), ['Bert Brandner'])
  assert.equal(s.gelesen.filter((g) => g.methode === 'chat.gespraech_mitglieder')[0].parameter.gespraech,
    'CHAT-D1')
  taste(feld(s.host), 'Enter')
  await rendern()
  assert.equal(feld(s.host).value, '@Bert Brandner ')
  await tippen(s.host, `${feld(s.host).value}schaust du bitte?`)
  klick([...s.host.querySelectorAll('button')].find((b) => /Nachricht senden/.test(b.textContent)))
  await rendern(8)
  const senden = s.gesendet.filter((g) => g.methode === 'chat.senden').pop()
  assert.deepEqual(senden.parameter.erwaehnt, ['M-2'])

  // Die gesendete Zeile trägt die Erwähnung; die Blase hebt sie hervor — und
  // beim EMPFÄNGER (derselbe Name im Serverfeld) ist die eigene Erwähnung
  // markiert. Beides aus der Serverzeile, nichts gerechnet.
  document.body.innerHTML = ''
  const empf = await blaseMontieren(zeile('N-E1', '@Bert Brandner schaust du bitte?', {
    eigene: false, autor: 'Ich Selbst',
    erwaehnt: [{ mitglied: 'M-2', anzeigename: 'Bert Brandner' }],
  }), { ich: 'M-2' })
  const blase = empf.host.querySelector('.dk-chat-blase')
  assert.ok(blase.querySelector('.dk-chat-erwaehnung'), 'beim Empfänger hervorgehoben')
  assert.ok(blase.querySelector('.dk-chat-erwaehnung.is-meine'), 'und als eigene Erwähnung')
  assert.equal(blase.classList.contains('is-erwaehnt'), true, 'die Blase ist markiert')
  empf.abbaum()
  s.abbaum()
})

// ════════════════════════════════════════════════════════════════════════════
// D · Gruppe — dieselbe eine Abfrage; ohne Antwort KEINE Auswahl (nichts geraten)
// ════════════════════════════════════════════════════════════════════════════

test('CHAT-9b/D: in der Gruppe bietet die Auswahl die Mitglieder der Gruppe an', async () => {
  const s = await seiteMontieren({ kopf: GRUPPE_KOPF })
  await tippenWarten(s.host, '@')
  assert.deepEqual(auswahlNamen(s.host),
    ['Anna Beispiel', 'Bert Brandner', 'Clara Claus', 'Dieter Dorn'],
    'die Gruppe kommt aus derselben Abfrage wie 1:1 und Runde')
  await tippenWarten(s.host, '@Di')
  assert.deepEqual(auswahlNamen(s.host), ['Dieter Dorn'], 'gefiltert wie überall')
  taste(feld(s.host), 'Enter')
  await rendern()
  await tippen(s.host, `${feld(s.host).value}kommst du mit?`)
  klick([...s.host.querySelectorAll('button')].find((b) => /Nachricht senden/.test(b.textContent)))
  await rendern(8)
  const senden = s.gesendet.filter((g) => g.methode === 'chat.senden').pop()
  assert.deepEqual(senden.parameter.erwaehnt, ['M-4'])
  assert.equal(senden.parameter.text, '@Dieter Dorn kommst du mit?')
  s.abbaum()
})

test('CHAT-9b/D: scheitert die Abfrage, bleibt die Auswahl still weg', async () => {
  const s = await seiteMontieren({ kopf: GRUPPE_KOPF, mitgliederFehler: true })
  await tippenWarten(s.host, '@')
  assert.equal(s.host.querySelector('.dk-erw'), null,
    'keine Auskunft über die Beteiligten — also keine Liste, kein geratener Name')
  assert.equal(feld(s.host).getAttribute('aria-expanded'), 'false')
  assert.deepEqual(s.warnungen, [], 'kein Lärm: ' + s.warnungen.join(' | '))
  // Der Text bleibt Text, das Senden geht unverändert hinaus.
  klick([...s.host.querySelectorAll('button')].find((b) => /Nachricht senden/.test(b.textContent)))
  await rendern(8)
  const senden = s.gesendet.filter((g) => g.methode === 'chat.senden').pop()
  assert.equal(senden.parameter.text, '@')
  assert.equal('erwaehnt' in senden.parameter, false)
  // Ein Fehler wird NICHT gemerkt: jeder neue Namensanfang wagt eine eigene
  // Abfrage (CHAT-9b-2 — es gibt keinen „dieses Gespräch ist kaputt“-Merker
  // mehr). Die Auswahl bleibt dabei still weg.
  await tippen(s.host, '@x')
  await ruhe(260)
  await rendern(6)
  assert.equal(s.host.querySelector('.dk-erw'), null, 'auch nach der zweiten Frage keine Liste')
  assert.equal(s.gelesen.filter((g) => g.methode === 'chat.gespraech_mitglieder').length, 2,
    'je Namensanfang eine eigene Frage — der alte Fehler blockiert nicht')
  s.abbaum()
})

// ════════════════════════════════════════════════════════════════════════════
// G · CHAT-9b-2: fragen je Namensanfang — Entprellung, Wettlauf, „mehr“, Fehler
// ════════════════════════════════════════════════════════════════════════════

test('CHAT-9b-2/B: Tippen fragt mit q (nicht die Vollliste)', async () => {
  const s = await seiteMontieren()
  await tippenWarten(s.host, 'Hallo @An')
  const fragen = () => s.gelesen.filter((g) => g.methode === 'chat.gespraech_mitglieder')
  assert.deepEqual(fragen().map((g) => g.parameter), [{ gespraech: 'CHAT-R1', q: 'An', limit: 20 }],
    'EINE Frage, mit dem Namen nach dem „@“ — im getippten Wortlaut')
  // R1/1: Treffer am WORTANFANG (wie der Server) — „Anna Beispiel“ beginnt mit
  // „an“, „Bert Brandner“ NICHT. Ein Teilwort mitten im Namen („…Brandner“)
  // zählt nicht; die Liste zeigt nur, was der Server zu dieser Frage sagt.
  assert.deepEqual(auswahlNamen(s.host), ['Anna Beispiel'],
    'Wortanfang: „An“ trifft Anna, nicht „Bert Brandner“')
  // Dieselbe Frage noch einmal (gleiche Zeichen) → KEINE zweite Abfrage
  // (die Antwort ist gemerkt).
  taste(feld(s.host), 'ArrowUp')
  await ruhe(260)
  await rendern(4)
  await tippenWarten(s.host, 'Hallo @An')
  assert.equal(fragen().length, 1, 'gemerkt: dieselbe Frage wird nicht wiederholt')
  s.abbaum()
})

test('CHAT-9b-2/B: zwei schnelle Eingaben ergeben EINE Abfrage (entprellt)', async () => {
  const s = await seiteMontieren()
  await tippenWarten(s.host, 'Hallo @')
  const vorher = s.gelesen.filter((g) => g.methode === 'chat.gespraech_mitglieder').length
  // Zwei Tastendrücke INNERHALB der Entprellzeit (200 ms): nur der letzte zählt.
  await tippen(s.host, 'Hallo @A')
  await tippen(s.host, 'Hallo @An')
  await ruhe(260)
  await rendern(8)
  const nachher = s.gelesen.filter((g) => g.methode === 'chat.gespraech_mitglieder')
  assert.equal(nachher.length - vorher, 1, 'eine Abfrage für beide Eingaben — nicht zwei')
  assert.equal(nachher[nachher.length - 1].parameter.q, 'An', 'gefragt wird der LETZTE Stand')
  s.abbaum()
})

test('CHAT-9b-2/B: eine veraltete Antwort wird verworfen', async () => {
  // Der Server antwortet LANGSAM und ohne eigene Filterei: die Antwort auf „@“
  // (alle drei) trifft NACH der Antwort auf „@C“ ein. Sie darf die Liste
  // nicht überschreiben — zählt nur der aktuelle Namensanfang.
  const s = await seiteMontieren({ filtert: false, mitgliederLangsam: 30 })
  await tippenWarten(s.host, 'Hallo @')
  await tippenWarten(s.host, 'Hallo @C')
  // Warten, bis auch die ERSTE (veraltete) Antwort eingetroffen ist.
  await ruhe(120)
  await rendern(8)
  assert.deepEqual(auswahlNamen(s.host), ['Clara Claus'],
    'veraltete Antwort verworfen: die Liste folgt „C“, nicht dem alten „@“')
  assert.equal(s.host.querySelector('.dk-erw-mehr'), null)
  s.abbaum()
})

test('CHAT-9b-2/B (R1/3): „mehr: true“ steht als Hinweis AUSSERHALB der Listbox', async () => {
  // Der Server kennt 30 Beteiligte, liefert 20 und sagt `mehr: true`.
  const viele = Array.from({ length: 30 }, (_, i) => ({
    mitglied: `M-${100 + i}`, anzeigename: `Person ${String(i + 1).padStart(2, '0')}`,
  }))
  const s = await seiteMontieren({ kopf: { ...GRUPPE_KOPF, mitglieder: viele } })
  await tippenWarten(s.host, '@')
  const zeilen = [...s.host.querySelectorAll('.dk-erw-liste > li')]
  assert.equal(zeilen.length, 20, 'die Listbox enthält NUR Wahlen — kein Hinweis')
  assert.equal([...s.host.querySelectorAll('.dk-erw-liste [role="option"]')]
    .filter((li) => /Weiter tippen/.test(li.textContent)).length, 0,
  'der Hinweis ist keine `option` in der Listbox')
  const hinweis = s.host.querySelector('.dk-erw-mehr')
  assert.ok(hinweis, 'der Hinweis steht im DOM')
  assert.equal(hinweis.tagName, 'P', 'ein Satz, keine Zeile der Listbox')
  assert.equal(hinweis.textContent.trim(), 'Weiter tippen, um mehr Personen zu finden.',
    'die Karte wörtlich')
  assert.equal(hinweis.closest('[role="listbox"]'), null,
    'AUSSERHALB der Listbox (die Listbox zeigt nur Wahlen)')
  assert.equal(hinweis.closest('[role="option"]'), null, 'keine Option, nicht wählbar')
  assert.equal(hinweis.getAttribute('aria-disabled'), null, 'kein ARIA-Rollenrest')
  // Die Liste selbst trägt weiterhin nur die 20 Vorschläge.
  assert.deepEqual(auswahlNamen(s.host), viele.slice(0, 20).map((m) => m.anzeigename))
  // ↑ läuft über die 20 Vorschläge, nicht auf den Hinweis; ein Klick auf den
  // Hinweis setzt nichts ein (er hat keinen Handler).
  const el = feld(s.host)
  taste(el, 'ArrowUp')
  await rendern(4)
  assert.equal(el.getAttribute('aria-activedescendant'), 'dk-erwaehnung-liste-19',
    'die Auswahl endet beim letzten VORSCHLAG')
  hinweis.dispatchEvent(new dom.window.MouseEvent('mousedown', { bubbles: true, cancelable: true }))
  await rendern(4)
  assert.equal(el.value, '@', 'ein Tipp auf den Hinweis setzt nichts ein')
  assert.ok(s.host.querySelector('.dk-erw'), 'und schließt die Auswahl nicht')
  // Enter setzt den AKTIVEN Vorschlag ein — nicht den Hinweis.
  taste(el, 'Enter')
  await rendern(4)
  assert.equal(el.value, '@Person 20 ')
  s.abbaum()
})

test('CHAT-9b-2/B (R1/3): der Hinweis steht auch bei 0 Treffern — ohne leere Listbox', async () => {
  // Ein Gespräch, in dem niemand zu „@Xy“ passt, aber mehr Beteiligte hat als
  // das Limit: der Server antwortet `{mitglieder: [], mehr: true}`. Dann steht
  // KEINE Listbox (nichts zu wählen), sehr wohl aber der Hinweis — sonst
  // dächte die Person, der Name sei unauffindbar.
  const viele = Array.from({ length: 25 }, (_, i) => ({
    mitglied: `M-${200 + i}`, anzeigename: `Person ${String(i + 1).padStart(2, '0')}`,
  }))
  const s = await seiteMontieren({
    kopf: { ...GRUPPE_KOPF, mitglieder: viele },
    mitgliederAntwort: (parameter) => ({
      art: 'gruppe',
      mitglieder: [],
      mehr: String(parameter?.q ?? '').length > 0,
    }),
  })
  await tippenWarten(s.host, '@Xy')
  assert.equal(s.host.querySelector('.dk-erw-liste'), null, 'keine Listbox ohne Treffer')
  assert.equal(feld(s.host).getAttribute('aria-controls'), null,
    'aria-controls zeigt nie auf eine fehlende/leere Listbox')
  assert.equal(feld(s.host).getAttribute('aria-expanded'), 'false')
  const hinweis = s.host.querySelector('.dk-erw-mehr')
  assert.ok(hinweis, 'der Hinweis steht trotzdem da')
  assert.equal(hinweis.textContent.trim(), 'Weiter tippen, um mehr Personen zu finden.')
  assert.equal(hinweis.closest('[role="listbox"]'), null, 'und zwar außerhalb jeder Listbox')
  s.abbaum()
})

test('CHAT-9b-2/B (R1/2): zwischen „@An“ und „@Ann“ bleibt die Liste offen (kein Flackern)', async () => {
  // Die Antwort auf „@Ann“ bleibt AUS (der Server ist langsam / hängt): die
  // Oberfläche darf nicht leer werden — sie zeigt die Liste zu „@An“, lokal
  // auf „Ann“ gefiltert, bis die eigene Antwort da ist.
  const s = await seiteMontieren({
    mitgliederAntwort: (parameter) => {
      const q = String(parameter?.q ?? '')
      // „Ann“ wird BEWUSST nie beantwortet — nur der gehaltene Stand bleibt.
      if (q === 'Ann') return new Promise(() => {})
      const stamm = RUNDE.filter((m) => m.mitglied !== ICH)
      const nadel = suchNormal(q)
      const liste = !nadel ? stamm : stamm.filter((m) => suchNormal(m.anzeigename).split(/\s+/)
        .some((w) => w.startsWith(nadel)) || suchNormal(m.anzeigename).startsWith(nadel))
      return { art: 'runde', mitglieder: liste, mehr: false }
    },
  })
  await tippenWarten(s.host, 'Hallo @An')
  const el = feld(s.host)
  assert.equal(el.getAttribute('aria-expanded'), 'true')
  assert.deepEqual(auswahlNamen(s.host), ['Anna Beispiel'], 'Stand zu „An“')

  // Ein Zeichen mehr: „@Ann“ — die neue Antwort kommt nicht.
  await tippen(s.host, 'Hallo @Ann')
  await ruhe(260) // Entprellung ist durch, die Abfrage läuft (und endet nie)
  await rendern(6)
  assert.equal(el.getAttribute('aria-expanded'), 'true',
    'die Liste bleibt offen — kein Auf-/Zuklappen bei jedem Tastendruck')
  assert.ok(s.host.querySelector('.dk-erw-liste'), 'die Listbox steht weiter im DOM')
  assert.deepEqual(auswahlNamen(s.host), ['Anna Beispiel'],
    'die letzte beantwortete Liste, lokal auf „ann“ gefiltert')
  assert.equal(el.getAttribute('aria-controls'), 'dk-erwaehnung-liste',
    'aria-controls bleibt gültig (die Liste ist da)')
  // Beide Fragen wurden gestellt — gehalten wird die alte, bis die neue kommt.
  assert.deepEqual(s.gelesen.filter((g) => g.methode === 'chat.gespraech_mitglieder')
    .map((g) => g.parameter.q), ['An', 'Ann'])
  s.abbaum()
})

test('CHAT-9b-2/B: Fehler 403 schließt die Auswahl still', async () => {
  const s = await seiteMontieren({ mitgliederFehler: true })
  await tippen(s.host, 'Hallo @An')
  await ruhe(260)
  await rendern(8)
  assert.equal(s.host.querySelector('.dk-erw'), null, 'keine Liste bei 403')
  assert.equal(feld(s.host).getAttribute('aria-expanded'), 'false')
  assert.deepEqual(s.warnungen, [], 'kein Lärm (keine Vue-/Fehlerwarnung): ' + s.warnungen.join(' | '))
  assert.equal(s.host.querySelector('.dk-chat-fehler'), null, 'keine Fehlerzeile unter der Eingabe')
  // Der Text bleibt Text; gesendet wird ohne Erwähnung.
  klick([...s.host.querySelectorAll('button')].find((b) => /Nachricht senden/.test(b.textContent)))
  await rendern(8)
  const senden = s.gesendet.filter((g) => g.methode === 'chat.senden').pop()
  assert.ok(senden, 'die Eingabe funktioniert weiter')
  assert.equal('erwaehnt' in senden.parameter, false)
  s.abbaum()
})

// ════════════════════════════════════════════════════════════════════════════
// E · ChatBlase gemountet: Anzeige
// ════════════════════════════════════════════════════════════════════════════

async function blaseMontieren(nachricht, props = {}) {
  const ordner = join(TMP, 'blase-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  umleitung.clear()
  const mod = (await import(pathToFileURL(baum('components/chat/ChatBlase.vue', { frisch: true, ordner })).href)).default
  return mounten(mod, { nachricht, ...props }, { propNamen: ['melden', 'reaktion', 'antworten', 'bearbeiten', 'loeschen'] })
}

test('CHAT-9b/E: „@Name“ wird hervorgehoben — HTML bleibt Text', async () => {
  document.body.innerHTML = ''
  const s = await blaseMontieren(zeile('N-1', 'Hallo @<b>Anna</b>, bitte lesen', {
    erwaehnt: [{ mitglied: 'M-X', anzeigename: '<b>Anna</b>' }],
  }))
  const blase = s.host.querySelector('.dk-chat-blase')
  assert.ok(blase, 'die Blase steht im DOM')
  // KEIN eingeschleustes Element — der Name bleibt sichtbarer Text.
  assert.equal(blase.querySelector('b'), null, 'kein ausgeführtes HTML aus Nutzertext')
  assert.equal(blase.textContent, 'Hallo @<b>Anna</b>, bitte lesen', 'der Text bleibt vollständig')
  const marke = blase.querySelector('.dk-chat-erwaehnung')
  assert.ok(marke, 'die Erwähnung ist hervorgehoben')
  assert.equal(marke.textContent, '@<b>Anna</b>')
  // Nicht erwähnt: keine Markierung der Blase.
  assert.equal(blase.classList.contains('is-erwaehnt'), false)
  s.abbaum()
})

test('CHAT-9b/E: eine Nachricht, die MICH erwähnt, ist dezent markiert', async () => {
  document.body.innerHTML = ''
  const s = await blaseMontieren(zeile('N-2', 'Hallo @Anna Beispiel', {
    erwaehnt: [{ mitglied: ICH, anzeigename: 'Anna Beispiel' }],
  }), { ich: ICH })
  const blase = s.host.querySelector('.dk-chat-blase')
  assert.equal(blase.classList.contains('is-erwaehnt'), true, 'die Blase trägt die Markierung')
  assert.ok(blase.querySelector('.dk-chat-erwaehnung.is-meine'), 'die eigene Erwähnung ist gekennzeichnet')
  s.abbaum()

  // Erwähnt jemand ANDEREN: keine Markierung der Blase.
  document.body.innerHTML = ''
  const t = await blaseMontieren(zeile('N-3', 'Hallo @Bert Brandner', {
    erwaehnt: [{ mitglied: 'M-2', anzeigename: 'Bert Brandner' }],
  }), { ich: ICH })
  const fremde = t.host.querySelector('.dk-chat-blase')
  assert.equal(fremde.classList.contains('is-erwaehnt'), false)
  assert.equal(fremde.querySelector('.dk-chat-erwaehnung.is-meine'), null)
  assert.ok(fremde.querySelector('.dk-chat-erwaehnung'), 'der andere Name ist trotzdem hervorgehoben')
  t.abbaum()
})

test('CHAT-9b/E: ohne `erwaehnt` in der Zeile bleibt alles gewöhnlicher Text', async () => {
  document.body.innerHTML = ''
  const s = await blaseMontieren(zeile('N-4', 'Hallo @Anna Beispiel'))
  const blase = s.host.querySelector('.dk-chat-blase')
  assert.equal(blase.querySelector('.dk-chat-erwaehnung'), null, '„@…“ ohne Server-Eintrag wird nicht hervorgehoben')
  assert.equal(blase.textContent, 'Hallo @Anna Beispiel')
  assert.equal(blase.classList.contains('is-erwaehnt'), false)
  s.abbaum()
})

test('CHAT-9b/E: die Erwähnung überlebt den Weg durch die Zeile (verlaufsZeile)', async () => {
  const logik = await import(new URL('composables/nachrichtenLogik.mjs', SRC).href)
  const zeileAmServer = {
    name: 'N-5', text: 'Hallo @Anna Beispiel', eigene: false, autor: 'Bert B.',
    erstellt_am: '2026-11-18 10:00:00', erwaehnt: [{ mitglied: ICH, anzeigename: 'Anna Beispiel' }],
  }
  const angezeigt = logik.verlaufsZeile(zeileAmServer, { ich: ICH })
  assert.deepEqual(angezeigt.erwaehnt, zeileAmServer.erwaehnt, 'die Liste wird nicht weggeworfen')
  document.body.innerHTML = ''
  const s = await blaseMontieren(angezeigt, { ich: ICH })
  assert.ok(s.host.querySelector('.dk-chat-blase.is-erwaehnt'), 'die Anzeigezeile trägt die Markierung')
  s.abbaum()
})

// ════════════════════════════════════════════════════════════════════════════
// F · Glockenziel
// ════════════════════════════════════════════════════════════════════════════

test('CHAT-9b/F (R1): die Erwähnungs-Glocke springt über nachricht_kontext ins Gespräch', async () => {
  const glocke = {
    name: 'NL-1', document_type: 'chat_erwaehnung', document_name: 'CHAT-N-42',
    subject: 'Samstag-Deko: Du wurdest erwähnt',
    email_content: 'Du wurdest in einem Gespräch erwähnt.',
  }
  assert.equal(ZIELE.ERWAEHNUNG_ART, 'chat_erwaehnung')
  assert.equal(ZIELE.istChatErwaehnung(glocke), true)

  // Der Server sagt, zu welchem Gespräch die Nachricht gehört (GET).
  const gefragt = []
  const hole = async (methode, parameter) => {
    gefragt.push({ methode, parameter })
    return { gespraech: 'CHAT-R7', art: 'runde', titel: 'Samstag-Deko' }
  }
  assert.equal(await ZIELE.erwaehnungZiel(glocke, hole), '#/nachrichten/CHAT-R7')
  assert.deepEqual(gefragt, [{ methode: 'chat.nachricht_kontext', parameter: { nachricht: 'CHAT-N-42' } }],
    'die Kennung der Nachricht ist die Frage, das Gespräch die Antwort')

  // Vertrag von CHAT-9c-2: unbekannte/fremde Kennung WIRFT (404) — es gibt
  // keine „gefunden: false“-Nutzlast mehr, und `null` kommt auch nicht.
  assert.equal(await ZIELE.erwaehnungZiel(glocke, async () => { throw fehler(404, 'nicht gefunden') }),
    '#/nachrichten', '404 → Bereich, keine geratene Kennung')
  assert.equal(await ZIELE.erwaehnungZiel(glocke, async () => null), '#/nachrichten')
  // Fehler ebenso — und ohne Kennung/ohne Abfrage wird gar nicht gefragt.
  assert.equal(await ZIELE.erwaehnungZiel(glocke, async () => { throw fehler(403, 'nein') }),
    '#/nachrichten')
  assert.equal(await ZIELE.erwaehnungZiel({ document_type: 'chat_erwaehnung' }, hole), '#/nachrichten')
  assert.equal(await ZIELE.erwaehnungZiel(glocke), '#/nachrichten')
  // Die Adresse kodiert die Kennung (kein zerlegter Pfad).
  assert.equal(ZIELE.nachrichtenAdresse('A/B C'), '#/nachrichten/A%2FB%20C')

  // Rückfall über den Betreff (Zeilen ohne `document_type`) — auch im 1:1, wo
  // der Titel „Direktnachricht“ lautet.
  assert.equal(ZIELE.istChatErwaehnung({ subject: 'Direktnachricht: Du wurdest erwähnt' }), true)
  // Die MELDUNG bleibt eine Meldung — eigene Art, eigenes Ziel.
  const meldung = { document_type: 'chat_meldung', document_name: 'M-1', subject: 'Neue Meldung im Chat' }
  assert.equal(ZIELE.istChatErwaehnung(meldung), false, 'eine Meldung ist keine Erwähnung')
  assert.equal(ZIELE.istChatMeldung(meldung), true)
  assert.equal(ZIELE.meldungZiel(), '#/kalender/pruefen?reiter=chat')
  // Alles andere ist keine Erwähnung.
  assert.equal(ZIELE.istChatErwaehnung({ document_type: 'chat_gespraech', subject: 'Chor: 3 neue' }), false)
  assert.equal(ZIELE.istChatErwaehnung(null), false)
  assert.equal(ZIELE.istChatErwaehnung({}), false)
})

test('CHAT-9b/F: die Glockenzeile in der Kopfzeile ist ein Knopf — gemountet', async () => {
  document.body.innerHTML = ''
  const ordner = join(TMP, 'topbar-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  const notif = join(ordner, 'useNotifications.mjs')
  const zeilen = [
    { name: 'NL-1', subject: 'Samstag-Deko: Du wurdest erwähnt', email_content: 'Du wurdest in einem Gespräch erwähnt.',
      document_type: 'chat_erwaehnung', document_name: 'CHAT-N-42', creation: '2026-11-18 09:00:00', read: 0 },
    { name: 'NL-2', subject: 'Irgendwas anderes', email_content: 'Nur Lesetext', document_type: 'sonst', creation: '2026-11-18 08:00:00', read: 0 },
  ]
  writeFileSync(notif, [
    `import { ref } from '${VUE_URL}'`,
    'export function useNotifications() {',
    '  return {',
    `    unreadCount: ref(${zeilen.length}),`,
    `    notifications: ref(${JSON.stringify(zeilen)}),`,
    '    laden: ref(false), fehler: ref(""),',
    '    ladeListe: async () => globalThis.__TOPBAR_ZEILEN(),',
    '    markAsRead: async () => {},',
    '  }',
    '}',
  ].join('\n'))
  const router = join(ordner, 'router.mjs')
  writeFileSync(router, [
    "export function navigate(ziel) { globalThis.__TOPBAR_ZIEL = ziel }",
    "export const currentPageName = { value: 'nachrichten' }",
  ].join('\n'))
  writeFileSync(join(ordner, 'menue.mjs'), [
    'export function krumenZuSeite() { return [] }',
    'export function verwaltungZutreffend() { return false }',
    // CHAT-R2d (Sammel 7): die Kopfzeile kennt den Zurück-Weg der Verwaltung.
    "export const PERSONENVERWALTUNG_BASIS = '#/einstellungen/personenverwaltung'",
    'export const MENUE = []',
    'export const FUSS_EINTRAEGE = []',
    'export const MENUE_EINTRAEGE = []',
    'export function sichtbareEintraege() { return [] }',
  ].join('\n'))
  const U = (rel) => pathToFileURL(SRC.pathname + rel).href
  umleitung.clear()
  umleitung.set(U('composables/useNotifications.js'), pathToFileURL(notif).href)
  umleitung.set(U('router.js'), pathToFileURL(router).href)
  umleitung.set(U('menue.js'), pathToFileURL(join(ordner, 'menue.mjs')).href)
  // Die Kopfzeile fragt `chat.nachricht_kontext` (GET) über `useApi`. Die
  // Attrappe trennt GET und POST und liefert die Antwortform aus CHAT-9c.
  const api = join(ordner, 'api.mjs')
  writeFileSync(api, [
    'export async function apiGet(methode, parameter) {',
    '  globalThis.__TOPBAR_GET = globalThis.__TOPBAR_GET || [];',
    '  globalThis.__TOPBAR_GET.push({ methode, parameter });',
    '  return globalThis.__TOPBAR_KONTEXT(methode, parameter);',
    '}',
    'export async function apiCall() { throw new Error("kein POST erwartet") }',
    'export const apiUrl = (p) => "https://pruefstand.invalid/" + p',
    'export class AuditConfirmationRequired extends Error {}',
    'export const pruefeSitzungsAntwort = () => false',
    'export const apiAntwortPruefen = async () => ({})',
  ].join('\n'))
  umleitung.set(U('composables/useApi.js'), pathToFileURL(api).href)
  globalThis.__TOPBAR_GET = []
  globalThis.__TOPBAR_KONTEXT = async (methode, parameter) => {
    if (methode !== 'chat.nachricht_kontext') return {}
    // Unbekannte/fremde Kennung WIRFT (404) — der Vertrag von CHAT-9c-2.
    if (parameter?.nachricht !== 'CHAT-N-42') throw fehler(404, 'Nachricht nicht gefunden')
    return { gespraech: 'CHAT-R7', art: 'runde', titel: 'Samstag-Deko' }
  }
  globalThis.__TOPBAR_ZEILEN = async () => zeilen
  const mod = (await import(pathToFileURL(baum('components/AppTopbar.vue', { frisch: true, ordner })).href)).default
  // Die Liste ohne Seitenleisten-Zustand zeichnen: `collapsed`/`devKnopf` sind
  // Props der Kopfzeile, das Panel öffnet der Klick auf die Glocke.
  const s = await mounten(mod, { collapsed: false, devKnopf: false })
  // Glocke öffnen.
  const glocke = [...s.host.querySelectorAll('button')].find((b) => /Benachrichtig/i.test(b.getAttribute('aria-label') || b.textContent))
  if (glocke) {
    klick(glocke)
    await rendern(8)
    await warte(10)
  }
  const knopf = [...s.host.querySelectorAll('button')].find((b) => /Erwähnt — zu „Nachrichten“/.test(b.getAttribute('aria-label') || ''))
  assert.ok(knopf, 'die Erwähnung ist ein Knopf (Weg), kein Lesetext\n'
    + 'WARNUNGEN: ' + s.warnungen.join(' | ')
    + '\nDOM: ' + s.host.innerHTML.slice(0, 3000))
  assert.match(knopf.textContent, /Du wurdest erwähnt/)
  assert.match(knopf.textContent, /Nachrichten ›/)
  // Nur die EINE Erwähnungs-Zeile ist ein Weg — die fremde bleibt Lesetext.
  assert.equal([...s.host.querySelectorAll('button')]
    .filter((b) => /Erwähnt — zu/.test(b.getAttribute('aria-label') || '')).length, 1)
  klick(knopf)
  await rendern(8)
  await warte(10)
  await rendern(4)
  assert.equal(globalThis.__TOPBAR_ZIEL, '#/nachrichten/CHAT-R7',
    'der Klick führt ins GESPRÄCH der Nachricht (über nachricht_kontext)')
  assert.deepEqual(globalThis.__TOPBAR_GET,
    [{ methode: 'chat.nachricht_kontext', parameter: { nachricht: 'CHAT-N-42' } }],
    'genau EINE Abfrage, mit der Kennung der Nachricht')
  // Das Panel ist zu (die Meldung ist gelesen) und bleibt geschlossen.
  assert.equal(s.host.querySelector('.dk-notify-panel'), null)
  s.abbaum()
})
