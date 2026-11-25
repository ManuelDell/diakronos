/**
 * BEF-UMFRAGE — Chat-Umfrage: Fehlermeldung nach erfolgreicher Abstimmung.
 *
 * Befund DMB-525e1b2d4a0a: Nach dem Abstimmen stand an der Karte dauerhaft
 * „Das hat gerade nicht geklappt …“ (p.dk-umfrage-fehler). Ursache:
 * `umfrageFehlerSetzen(name, null)` sollte ZURÜCKSETZEN, lief aber durch
 * `fehlertext(null)` — und der Katalog liefert dafür den Standardtext.
 *
 * Geprüft wird das VERHALTEN an der gemounteten Seite Nachrichten.vue:
 *
 *   A  Erfolgreiches `chat.umfrage_abstimmen` → KEIN `.dk-umfrage-fehler`.
 *   B  400 beim Abstimmen → genau einer, mit lesbarem Satz; ein zweiter,
 *      erfolgreicher Versuch räumt ihn wieder weg (Zurücksetzen wirkt).
 *   C  Erfolgreiches `chat.umfrage_schliessen` → KEIN `.dk-umfrage-fehler`.
 *   D  Gegenprobe ohne Netz: `fehlertext(null)` liefert weiter den
 *      Standardtext (der Katalog ist unverändert — repariert wird der
 *      Aufrufer, nicht der Text).
 *   E  Kein weiterer Aufrufer mit demselben Muster: `FehlerSetzen(…, null)`
 *      steht in Nachrichten.vue nur dort, wo die Hilfsfunktion das leere
 *      Argument als Zurücksetzen versteht.
 *
 * Lauf (TZ=Europe/Berlin):
 *   TZ=Europe/Berlin node --test --test-timeout=120000 tests/bef-umfrage-fehler-zuruecksetzen.test.mjs
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

const TMP = mkdtempSync(join(tmpdir(), 'bef-umfrage-'))
test.after(() => rmSync(TMP, { recursive: true, force: true }))

// ── SFC → ES-Modul (wie in den Chat-Tests) ─────────────────────────────────
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

async function mounten(baustein, props = {}) {
  const Vue = await import('vue')
  const host = document.createElement('div')
  document.body.appendChild(host)
  const warnungen = []
  const Wrapper = {
    props: { p: { type: Object, default: () => ({}) } },
    setup(innerProps) {
      return () => Vue.h(baustein, { ...innerProps.p })
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
  return { host, app, warnungen, abbaum }
}

/** Ein Klick, wie ihn der Browser auslöst (Knöpfe sind echte <button>). */
function klick(el) {
  assert.ok(el, 'das Element steht im DOM')
  el.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true, cancelable: true }))
}

const texte = (host, auswahl) => [...host.querySelectorAll(auswahl)].map((e) => e.textContent.trim())

// ── Prüfstand der Seite ────────────────────────────────────────────────────

function apiAttrappe(ordner) {
  const api = join(ordner, 'api.mjs')
  writeFileSync(api, [
    'export async function apiCall(methode, parameter) {',
    '  globalThis.__BEF_PUSH({ methode, parameter })',
    '  return globalThis.__BEF_SERVER({ methode, parameter })',
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
  return { api, session }
}

/** Eine Umfrage, wie der Server sie liefert (offene Form, änderbar). */
function umfrageForm(ueberschreiben = {}) {
  return {
    name: 'chat-umfrage-1',
    gespraech: 'CHAT-1',
    frage: 'Wann proben wir?',
    mehrfach: false,
    anonym: false,
    frist_am: null,
    geschlossen_am: null,
    geschlossen_von: null,
    offen: true,
    stimmen_gesamt: 2,
    abgegeben: 2,
    hinweis: null,
    abgestimmt: false,
    eigene_stimme: null,
    darf_schliessen: true,
    optionen: [
      { nummer: 1, text: 'Samstag', stimmen: 2, namen: [] },
      { nummer: 2, text: 'Sonntag', stimmen: 0, namen: [] },
    ],
    ...ueberschreiben,
  }
}

const GESPRAECHE = [
  { name: 'CHAT-1', art: 'gruppe', gruppe: 'leitung', untergruppe: null, titel: 'Leitung',
    geoeffnet: true, ungelesen: 0, teilnehmer: 4, letzte_nachricht: 'Hallo',
    letzte_am: '2026-11-18 10:00:00', darf_senden: true },
]

function verlaufMit(umfrage) {
  return {
    gespraech: 'CHAT-1',
    richtung: 'neueste',
    nachrichten: [
      { name: 'CHAT-1-N2', gespraech: 'CHAT-1', text: 'Wann proben wir?', eigene: false,
        autor: 'Anna Beispiel', erstellt_am: '2026-11-18 09:05:00', umfrage },
    ],
  }
}

async function seiteMontieren({ server = {}, umfrage = umfrageForm() } = {}) {
  const ordner = join(TMP, 'seite-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  const { api, session } = apiAttrappe(ordner)
  const U2 = (rel) => pathToFileURL(SRC.pathname + rel).href
  umleitung.clear()
  umleitung.set(U2('composables/useApi.js'), pathToFileURL(api).href)
  umleitung.set(U2('composables/useSession.js'), pathToFileURL(session).href)

  const aufrufe = []
  globalThis.__BEF_PUSH = (eintrag) => aufrufe.push(eintrag)
  globalThis.__BEF_SERVER = ({ methode, parameter }) => {
    const kurz = String(methode).split('.').pop()
    if (server && typeof server[kurz] === 'function') return server[kurz](parameter)
    if (kurz === 'meine_gespraeche') return { gespraeche: GESPRAECHE.map((g) => ({ ...g })) }
    if (kurz === 'verlauf') return verlaufMit(umfrage)
    if (kurz === 'lesestand_setzen') return { ungelesen: 0 }
    return {}
  }
  dom.window.__DIakonosBOOT = { roles: ['Mitglied'], is_admin: false, module_sichtbar: ['chat'] }
  dom.window.location.hash = '#/nachrichten/CHAT-1'

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
  const abraeumen = () => {
    for (const t of gestartet) { try { clearTimeout(t); clearInterval(t) } catch { /* egal */ } }
  }
  const abbaumVorher = gemountet.abbaum
  gemountet.abbaum = () => { abbaumVorher(); abraeumen() }
  await rendern(6)
  await warte(14)
  await rendern(6)
  return { ...gemountet, aufrufe }
}

/** In der Karte die Antwort 1 wählen und „Abstimmen“ klicken. */
async function abstimmen(s) {
  const radios = [...s.host.querySelectorAll('.dk-umfrage input[type="radio"]')]
  assert.equal(radios.length, 2, 'die Karte bietet die Antworten an')
  radios[0].checked = true
  radios[0].dispatchEvent(new dom.window.Event('change', { bubbles: true }))
  await rendern()
  const knopf = [...s.host.querySelectorAll('.dk-umfrage button')]
    .find((b) => /Abstimmen|Stimme ändern/.test(b.textContent))
  assert.ok(knopf, 'der Abstimm-Knopf steht da')
  klick(knopf)
  await rendern(8)
  await warte(14)
  await rendern(6)
}

// ════════════════════════════════════════════════════════════════════════════
// A · Erfolgreiches Abstimmen setzt KEINE Meldung
// ════════════════════════════════════════════════════════════════════════════

test('BEF-UMFRAGE/A: nach erfolgreichem Abstimmen steht keine Fehlermeldung an der Karte', async () => {
  const stand = umfrageForm({
    abgestimmt: true, eigene_stimme: [1], abgegeben: 1, stimmen_gesamt: 1,
    optionen: [{ nummer: 1, text: 'Samstag', stimmen: 1, namen: ['Anna A.'] },
      { nummer: 2, text: 'Sonntag', stimmen: 0, namen: [] }],
  })
  const s = await seiteMontieren({ server: { umfrage_abstimmen: () => stand } })
  assert.equal(s.host.querySelector('.dk-umfrage-fehler'), null, 'vor dem Abstimmen nichts zu melden')
  await abstimmen(s)
  const ruf = s.aufrufe.filter((a) => /umfrage_abstimmen$/.test(a.methode)).at(-1)
  assert.ok(ruf, 'der Server wurde gefragt')
  // DAS ist der Befund: der Fehlerkasten darf nach dem Erfolg NICHT stehen.
  const meldung = s.host.querySelector('.dk-umfrage-fehler')
  assert.equal(meldung, null, 'kein „Das hat gerade nicht geklappt …“ nach dem Erfolg')
  assert.doesNotMatch(s.host.querySelector('.dk-umfrage').textContent,
    /nicht geklappt|Versuche es in einem Moment/, 'auch nicht als Fließtext')
  // Der neue Stand steht trotzdem da (die Karte lebt weiter).
  assert.match(s.host.querySelector('.dk-umfrage').textContent, /Du hast abgestimmt/)
  assert.deepEqual(texte(s.host, '.dk-umfrage .dk-umfrage-zahl'), ['1', '0'])
  s.abbaum()
})

// ════════════════════════════════════════════════════════════════════════════
// B · Ein echter Fehler (400) steht — und ein späterer Erfolg räumt ihn weg
// ════════════════════════════════════════════════════════════════════════════

test('BEF-UMFRAGE/B: 400 beim Abstimmen wird gemeldet, der nächste Erfolg räumt die Meldung weg', async () => {
  let versuch = 0
  const stand = umfrageForm({
    abgestimmt: true, eigene_stimme: [1], abgegeben: 3, stimmen_gesamt: 3,
    optionen: [{ nummer: 1, text: 'Samstag', stimmen: 3, namen: [] },
      { nummer: 2, text: 'Sonntag', stimmen: 0, namen: [] }],
  })
  const s = await seiteMontieren({
    server: {
      umfrage_abstimmen: () => {
        versuch += 1
        if (versuch === 1) {
          const fehler = new Error('Für diese Umfrage haben Sie bereits abgestimmt.')
          fehler.status = 400
          throw fehler
        }
        return stand
      },
    },
  })
  // 1. Versuch: der Server sagt „nein“ → die Meldung steht (Gegenprobe zum Befund).
  await abstimmen(s)
  const meldung = s.host.querySelector('.dk-umfrage-fehler')
  assert.ok(meldung, 'ein echter Fehler wird angezeigt')
  assert.equal(meldung.getAttribute('role'), 'alert', 'und vorgelesen')
  assert.ok(meldung.textContent.trim().length > 0, 'mit einem lesbaren Satz')

  // 2. Versuch: der Server sagt „ja“ → die Meldung ist WEG (Zurücksetzen wirkt).
  await abstimmen(s)
  assert.equal(s.host.querySelector('.dk-umfrage-fehler'), null,
    'der zurückgesetzte Eintrag erscheint nach dem Erfolg nicht wieder')
  s.abbaum()
})

// ════════════════════════════════════════════════════════════════════════════
// C · Erfolgreiches Schließen setzt KEINE Meldung
// ════════════════════════════════════════════════════════════════════════════

test('BEF-UMFrage/C: nach erfolgreichem Schließen steht keine Fehlermeldung an der Karte', async () => {
  const geschlossen = umfrageForm({
    offen: false, geschlossen_am: '2026-11-18 10:30:00', geschlossen_von: 'anna@x.org',
    darf_schliessen: false,
  })
  const s = await seiteMontieren({ server: { umfrage_schliessen: () => geschlossen } })
  const knopf = [...s.host.querySelectorAll('.dk-umfrage button')]
    .find((b) => /Umfrage schließen/.test(b.textContent))
  assert.ok(knopf, 'der Schließen-Knopf steht da')
  klick(knopf)
  await rendern(8)
  await warte(14)
  await rendern(6)
  assert.ok(s.aufrufe.some((a) => /umfrage_schliessen$/.test(a.methode)), 'der Server wurde gefragt')
  assert.equal(s.host.querySelector('.dk-umfrage-fehler'), null,
    'kein „Das hat gerade nicht geklappt …“ nach dem Schließen')
  assert.match(s.host.querySelector('.dk-umfrage').textContent, /geschlossen/)
  s.abbaum()
})

// ════════════════════════════════════════════════════════════════════════════
// D · Der Katalog bleibt, wie er ist — repariert wird der Aufrufer
// ════════════════════════════════════════════════════════════════════════════

test('BEF-UMFrage/D: fehlertext(null) liefert weiter den Standardtext (Ursache benannt)', async () => {
  const F = await import(new URL('shared/fehlertexte.js', SRC_ROOT).href)
  const text = F.fehlertext(null)
  assert.equal(typeof text, 'string')
  assert.match(text, /nicht geklappt/, 'der Katalogtext selbst ist unverändert')
  // Genau deshalb darf der Aufrufer bei „zurücksetzen“ NICHT durch fehlertext gehen.
  const quelle = readFileSync(new URL('../src/diakonos/pages/Nachrichten.vue', import.meta.url), 'utf8')
  const rumpf = quelle.slice(quelle.indexOf('function umfrageFehlerSetzen'),
    quelle.indexOf('function umfrageUebernehmen'))
  assert.match(rumpf, /if \(!fehler\)/, 'die Hilfsfunktion kennt jetzt den leeren Fall')
  assert.doesNotMatch(rumpf.slice(0, rumpf.indexOf('if (!fehler)')),
    /fehlertext\(/, 'vor dem Zurücksetzen wird kein Text gebaut')
})

// ════════════════════════════════════════════════════════════════════════════
// E · Keine zweite Stelle mit demselben Muster
// ════════════════════════════════════════════════════════════════════════════

test('BEF-UMFRAGE/E: kein weiterer Aufrufer setzt mit null den Standardtext', () => {
  const quelle = readFileSync(new URL('../src/diakonos/pages/Nachrichten.vue', import.meta.url), 'utf8')
  // Jede Hilfsfunktion, die auf „leer = zurücksetzen“ hört, hat den Zweig.
  const hilfen = [...quelle.matchAll(/function (\w*[Ff]ehlerSetzen)\(([^)]*)\)\s*\{/g)]
  assert.ok(hilfen.length >= 2, 'die Hilfsfunktionen stehen in der Datei')
  for (const treffer of hilfen) {
    const [, name, kopf] = treffer
    const rumpf = quelle.slice(treffer.index, quelle.indexOf('\n}', treffer.index))
    // `fehlerSetzen(name, text)` (ChatMeldungen) nimmt Klartext — hier steht sie nicht.
    assert.match(rumpf, /if \(!\w+\)/, name + ': leeres Argument heißt Zurücksetzen')
    assert.doesNotMatch(rumpf, /fehlertext\(\s*(?:null|undefined|'')\s*\)/, name + ': kein fehlertext(null)')
    assert.ok(kopf.endsWith(', fehler'), name + ': der Fehler ist der letzte Parameter')
  }
  // Und es gibt keine Stelle, die eine Hilfsfunktion mit `null` ruft und einen
  // Text erwartet: alle `FehlerSetzen(…, null)`-Aufrufe sind Zurücksetzungen.
  const aufrufe = [...quelle.matchAll(/(\w*[Ff]ehlerSetzen)\(([^)]*)\)/g)]
    .filter((m) => /,\s*null\s*$/.test(m[2]))
  assert.ok(aufrufe.length >= 3, 'die Zurücksetz-Aufrufe stehen in der Datei')
  for (const m of aufrufe) {
    assert.equal(m[2].split(',').length, 2, m[0] + ': zwei Argumente (Name, null)')
  }
  // components/chat/* kennt kein `fehlertext(…, null)` als Meldung.
  const karte = readFileSync(new URL('../src/diakonos/components/chat/ChatUmfrage.vue', import.meta.url), 'utf8')
  assert.doesNotMatch(karte, /fehlertext\(/, 'die Karte baut keinen eigenen Fehlertext')
})
