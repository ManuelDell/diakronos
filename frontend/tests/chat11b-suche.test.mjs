/**
 * CHAT-11b — Suche in Nachrichten: Oberfläche (Vue 3, Frontend). Karte t_fdbd4d76.
 *
 * Grundlage ist die echte Antwortform von `chat.nachrichten_suchen`
 * (CHAT-11a, `backend/src/diakronos_app/api/chat.py`, Docstring + Tests):
 *
 *   { treffer: [ { gespraech: {name, art, titel}, nachricht, zeit,
 *                  absender, ausschnitt: {vor, treffer, nach} } ],
 *     mehr: <bool>, vor: <kennung|None>, limit: <Zahl> }
 *
 * Nichts davon ist nachgebaut: die Attrappen unten benutzen genau diese Felder
 * (so, wie sie `test_chat11a_suche.py` prüft — `gespraech.art` = `'gruppe'`,
 * `ausschnitt` mit drei Textteilen, `vor` = Kennung der letzten Zeile).
 *
 * Geprüft wird VERHALTEN, nicht Quelltext — Ausnahme ist die EINE Zusage, die
 * sich nur im Quelltext zeigt: kein `v-html` (der Ausschnitt darf niemals als
 * HTML eingesetzt werden). Sie steht als eigener Fall mit <script> im Text.
 *
 *   A  Regeln ohne DOM (`composables/nachrichtenTreffer.mjs`): Zeilen aus der
 *      Serverantwort, Ausschnitt als drei TEXT-Teile, Blättern über `vor`,
 *      überholte Antworten (`darfFragen`), Sprung-Regel (Seiten, „weg“,
 *      „aufgeben“), Tasten der Trefferliste.
 *   B  ChatSuche.vue gemountet: Abschnitt „In Nachrichten“ ab 2 Zeichen,
 *      entprellt, Markierung per <mark> (auch bei „<script>“ im Text),
 *      „Weitere Treffer“ lädt über `vor`, überholte Antwort wird verworfen,
 *      Escape schließt den Abschnitt.
 *   C  ChatTreffer.vue gemountet: Pfeiltasten bewegen, Enter öffnet,
 *      aria-live meldet die Trefferzahl, keine Treffer → ruhiger Satz.
 *   D  Nachrichten.vue gemountet: Sprung lädt ältere Seiten nach (≤ 10) und
 *      hebt hervor; gelöschte Nachricht → ruhiger Hinweis; die Suche im
 *      Gespräch schickt `gespraech=<kennung>`, Escape schließt sie.
 *
 * Lauf (eine Datei je Aufruf, TZ=Europe/Berlin):
 *   TMPDIR=$(mktemp -d) TZ=Europe/Berlin node --test tests/chat11b-suche.test.mjs
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
  'sessionStorage', 'location', 'URLSearchParams', 'PopStateEvent', 'HashChangeEvent',
  'AbortController', 'AbortSignal']) {
  globalThis[schluessel] = dom.window[schluessel]
}
globalThis.requestAnimationFrame = dom.window.requestAnimationFrame
  || ((fn) => setTimeout(() => fn(Date.now()), 0))
globalThis.CSS = dom.window.CSS || { escape: (s) => String(s) }
Object.defineProperty(dom.window.document, 'hidden', { configurable: true, get: () => false })
Object.defineProperty(dom.window.document, 'visibilityState', { configurable: true, get: () => 'visible' })

const VUE_URL = import.meta.resolve('vue')
const SRC_ROOT = new URL('../src/', import.meta.url)
const SRC = new URL('../src/diakonos/', import.meta.url)

const TMP = mkdtempSync(join(tmpdir(), 'chat11b-'))
test.after(() => rmSync(TMP, { recursive: true, force: true }))

const T = await import(new URL('composables/nachrichtenTreffer.mjs', SRC).href)

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

/** Mounten mit Horcher für die Ereignisse der Komponente. */
async function mounten(baustein, props = {}, { horcher = null, propNamen = null, vertreter = null } = {}) {
  let vertreten = null
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
      // Die INSTANZ des geprüften Bauteils — nicht die des Wrappers
      // (`getCurrentInstance()` im `setup` IST der Wrapper; `expose` käme so
      // nie heraus, und `defineExpose` wäre von außen unsichtbar).
      let kind = null
      Vue.onMounted(() => {
        const kandidat = innerProps.refKasten
        if (kandidat) kandidat.value = kind
      })
      seite = Vue.getCurrentInstance()
      const eigene = Vue.ref({ ...innerProps.p })
      globalThis.__PROP_SETZEN = globalThis.__PROP_SETZEN || {}
      globalThis.__PROP_SETZEN[kennung] = (name, wert) => {
        eigene.value = { ...eigene.value, [name]: wert }
      }
      // Die Horcher entstehen EINMAL im `setup` — stünden sie in der
      // Render-Fassung, bekäme das Kind bei jedem Render neue Rückrufe (und
      // damit eine neue Komponente: der Zustand ginge verloren).
      const rueckrufe = Object.fromEntries(
        namen.map((n) => [`on${n[0].toUpperCase()}${n.slice(1)}`, (x) => melde(n, x)]),
      )
      const kinderRef = typeof vertreter === 'function'
        ? (r) => { vertreten = r; vertreter(r) }
        : null
      return () => Vue.h(baustein, {
        ...(kinderRef ? { ref: kinderRef } : {}),
        ...eigene.value,
        ...rueckrufe,
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
  return {
    host, app, abbaum, warnungen,
    instanz: () => seite,
    // Die INSTANZ des geprüften Bauteils — nicht die des Wrappers:
    // `expose()` in `<script setup>` legt die Werte auf das Proxy-Ziel
    // (`ctx`), und nur dort sind sie zu holen.
    exposed: () => (vertreten
      ? (vertreten.ctx && typeof vertreten.ctx.springen === 'function' ? vertreten.ctx : vertreten)
      : null),
    Vue,
    setze: (n, w) => globalThis.__PROP_SETZEN[kennung](n, w),
  }
}

/** Eine Uhr mit Terminen — der Entpreller bekommt sie hinein. */
function uhrAttrappe() {
  let kennung = 0
  const termine = new Map()
  return {
    timer: (fn, ms) => { kennung += 1; termine.set(kennung, { fn, ms }); return kennung },
    timerAus: (id) => { termine.delete(id) },
    offen: () => termine.size,
    async feuern() {
      const faellig = [...termine.values()]
      termine.clear()
      for (const t of faellig) t.fn()
      await warte(8)
    },
  }
}

// ════════════════════════════════════════════════════════════════════════════
// Die Serverantwort — Felder WÖRTLICH wie `nachrichten_suchen` (CHAT-11a)
// ════════════════════════════════════════════════════════════════════════════

const GESPRAECH_CHOR = { name: 'CHAT-2', art: 'gruppe', titel: 'Chor' }
const GESPRAECH_DIREKT = { name: 'CHAT-9', art: 'direkt', titel: 'Bert Beispiel' }

/** Ein Treffer, wie der Server ihn baut (`_suchseite` → `treffer.append`). */
function treffer({ nachricht, zeit = '2026-11-18 09:12:00', absender = 'Anna Beispiel',
  gespraech = GESPRAECH_CHOR, vor = '… Probe am ', fund = 'Samstag', nach = ' um zehn.' }) {
  return { gespraech, nachricht, zeit, absender, ausschnitt: { vor, treffer: fund, nach } }
}

/** Eine Seite, wie der Server sie liefert (`{treffer, mehr, vor, limit}`). */
function seite(zeilen, { mehr = false, vor = null, limit = 20 } = {}) {
  return { treffer: zeilen, mehr, vor: vor ?? (zeilen.length ? zeilen[zeilen.length - 1].nachricht : null), limit }
}

// ════════════════════════════════════════════════════════════════════════════
// A · Regeln ohne DOM
// ════════════════════════════════════════════════════════════════════════════

test('CHAT-11b/A: Grenzen und Texte stehen an EINER Stelle', () => {
  assert.equal(T.TREFFER_MIN_ZEICHEN, 2, 'ab 2 Zeichen — wie Personen und der Server')
  assert.equal(T.ABSCHNITT_NACHRICHTEN, 'In Nachrichten')
  assert.equal(T.WEG_TEXT, 'Diese Nachricht gibt es nicht mehr.')
  assert.equal(T.SPRUNG_MAX_SEITEN, 10)
  assert.equal(T.darfTrefferFragen('a'), false)
  assert.equal(T.darfTrefferFragen('  a  '), false, 'getrimmt gezählt')
  assert.equal(T.darfTrefferFragen('ab'), true)
  assert.equal(T.darfTrefferFragen('Öl'), true, 'zwei Zeichen bleiben zwei Zeichen')
  assert.equal(T.trefferzahlText(1), '1 Treffer')
  assert.equal(T.trefferzahlText(3), '3 Treffer')
  assert.equal(T.trefferAnsage({ anzahl: 0 }), '', 'keine Ansage über null Treffer')
  assert.equal(T.trefferAnsage({ anzahl: 1 }), '1 Treffer in den Nachrichten')
})

test('CHAT-11b/A: aus der Serverantwort werden Zeilen — Ausschnitt in DREI Textteilen', () => {
  const jetzt = new Date(2026, 10, 18, 12, 0, 0)
  const zeile = T.trefferZeile(treffer({ nachricht: 'CHAT-N-1' }), jetzt)
  assert.equal(zeile.nachricht, 'CHAT-N-1')
  assert.equal(zeile.gespraech, 'CHAT-2')
  assert.equal(zeile.art, 'gruppe')
  assert.equal(zeile.titel, 'Chor')
  assert.equal(zeile.absender, 'Anna Beispiel')
  assert.equal(zeile.zeit, '09:12', 'heute → Uhrzeit wie in der Gesprächsliste')
  assert.deepEqual(zeile.teile, { vor: '… Probe am ', treffer: 'Samstag', nach: ' um zehn.' })
  // Der ganze Ausschnitt ist Text — die drei Teile aneinandergehängt ergeben ihn.
  assert.equal(T.ausschnittText(zeile.teile), '… Probe am Samstag um zehn.')

  // Ohne Nachrichten-Kennung gibt es keine Zeile (kein geratenes Ziel).
  assert.equal(T.trefferZeile({ absender: 'X', ausschnitt: {} }), null)

  // Ein Tag älter → „gestern“, danach das Datum (dieselbe Regel wie `listenZeit`).
  assert.equal(T.trefferZeile(treffer({ nachricht: 'N', zeit: '2026-11-17 09:00:00' }), jetzt).zeit, 'gestern')
  assert.equal(T.trefferZeile(treffer({ nachricht: 'N', zeit: '2026-11-02 09:00:00' }), jetzt).zeit, '02.11.')
})

test('CHAT-11b/A: fehlende Ausschnitt-Teile sind leer, kein „undefined“', () => {
  assert.deepEqual(T.ausschnittTeile(null), { vor: '', treffer: '', nach: '' })
  assert.deepEqual(T.ausschnittTeile({ vor: 'a', nach: 'b' }), { vor: 'a', treffer: '', nach: 'b' })
  assert.deepEqual(T.ausschnittTeile({ treffer: null }), { vor: '', treffer: '', nach: '' })
})

test('CHAT-11b/A: „mehr“ gilt nur mit Anker — sonst stünde ein Knopf ohne Ziel', () => {
  const a = T.trefferAusAntwort(seite([treffer({ nachricht: 'N-1' })], { mehr: true, vor: 'N-1' }))
  assert.equal(a.mehr, true)
  assert.equal(a.vor, 'N-1')
  assert.equal(a.zeilen.length, 1)
  const b = T.trefferAusAntwort({ treffer: [treffer({ nachricht: 'N-1' })], mehr: true, vor: null })
  assert.equal(b.mehr, false, 'ohne `vor` kein Blättern')
  const c = T.trefferAusAntwort({ treffer: [], mehr: false, vor: null })
  assert.deepEqual(c.zeilen, [])
  // Müll-Antworten sind keine Ausnahme.
  assert.deepEqual(T.trefferAusAntwort(null).zeilen, [])
  assert.deepEqual(T.trefferAusAntwort({}).mehr, false)
})

test('CHAT-11b/A: Blättern über `vor` — ohne Doppelungen', () => {
  const seite1 = T.trefferAusAntwort(seite([treffer({ nachricht: 'N-3' }), treffer({ nachricht: 'N-2' })],
    { mehr: true, vor: 'N-2' }))
  const seite2 = T.trefferAusAntwort(seite([treffer({ nachricht: 'N-1' })], { mehr: false, vor: 'N-1' }))
  const alle = T.seiteAnhaengen(seite1.zeilen, seite2.zeilen)
  assert.deepEqual(alle.map((z) => z.nachricht), ['N-3', 'N-2', 'N-1'])
  // Dieselbe Zeile noch einmal (kommt per Keyset nicht vor) — sie bleibt einmal.
  const doppelt = T.seiteAnhaengen(alle, seite2.zeilen)
  assert.deepEqual(doppelt.map((z) => z.nachricht), ['N-3', 'N-2', 'N-1'])
})

test('CHAT-11b/A: die Parameter EINES Abrufs — `vor` und `gespraech` nur wenn gefragt', () => {
  assert.deepEqual(T.frageParameter('Samstag'), { q: 'Samstag' }, 'NICHT kleingeschrieben')
  assert.deepEqual(T.frageParameter('  Samstag  '), { q: 'Samstag' }, 'nur getrimmt')
  assert.deepEqual(T.frageParameter('Samstag', { gespraech: 'CHAT-9' }), { q: 'Samstag', gespraech: 'CHAT-9' })
  assert.deepEqual(T.frageParameter('Maßnahme', { vor: 'N-7' }), { q: 'Maßnahme', vor: 'N-7' },
    'NICHT gefaltet — der Server stammt selbst')
  assert.deepEqual(T.frageParameter('Öl', { gespraech: '  ' }), { q: 'Öl' }, 'leeres Gespräch ist „alle“')
  // Review R1/2: „Müller“ MUSS unverändert hinaus — gefaltet („mueller“) fände
  // PostgreSQL mit `websearch_to_tsquery('german', …)` nichts.
  assert.equal(T.frageParameter('Müller').q, 'Müller')
})

test('CHAT-11b/A: überholte Antworten (`darfFragen`) und laufende Nummern', () => {
  // Falt-gleich zählt, alles andere nicht.
  assert.equal(T.darfFragen('Anna ', 'anna'), true)
  assert.equal(T.darfFragen('ann', 'anna'), false)
  // Ein LEERES Feld ist keine neue Frage: die Antwort auf den letzten Begriff
  // bleibt gültig (`istAktuell` allein sagte hier immer „nein“).
  assert.equal(T.darfFragen('anna', ''), true)
  assert.equal(T.darfFragen('anna', '   '), true)

  const nr = T.laufNummer()
  const erste = nr.neu()
  assert.equal(nr.gilt(erste), true)
  const zweite = nr.neu()
  assert.equal(nr.gilt(erste), false, 'die ältere Antwort zählt nicht mehr')
  assert.equal(nr.gilt(zweite), true)
  nr.abbrechen()
  assert.equal(nr.gilt(zweite), false, 'nach dem Abbruch zählt keine laufende Antwort')
  assert.equal(nr.stand(), 3)
})

test('CHAT-11b/A: Sprung — so lange ältere Seiten, bis die Nachricht da ist (≤ 10)', () => {
  const vorhanden = [{ ident: 'N-1' }, { ident: 'N-2' }]
  assert.equal(T.naechsterSprung({ nachricht: 'N-2', vorhanden }), 'da')
  assert.equal(T.naechsterSprung({ nachricht: 'N-9', vorhanden, aelterMoeglich: true, seiten: 0 }), 'weiter')
  assert.equal(T.naechsterSprung({ nachricht: 'N-9', vorhanden, aelterMoeglich: true, seiten: 9 }), 'weiter')
  assert.equal(T.naechsterSprung({ nachricht: 'N-9', vorhanden, aelterMoeglich: true, seiten: 10 }), 'aufgeben')
  // Kein Weg mehr nach oben: es gibt die Nachricht nicht (mehr).
  assert.equal(T.naechsterSprung({ nachricht: 'N-9', vorhanden, aelterMoeglich: false }), 'weg')
  assert.equal(T.naechsterSprung({ nachricht: '', vorhanden }), 'weg')
  assert.equal(T.naechsterSprung({ nachricht: 'N-9', vorhanden: [], aelterMoeglich: true, seiten: 0 }), 'weiter')
  assert.equal(T.sprungAnker(vorhanden), 'N-1', 'Anker ist die ÄLTESTE bekannte Nachricht')
  assert.equal(T.sprungAnker([]), '')
})

test('CHAT-11b/A (R1/5): JEDER Ladeversuch zählt — auch der leere Verlauf endet nach 10', () => {
  const ziel = { nachricht: 'N-9', vorhanden: [], gespraech: 'CHAT-2', offen: 'CHAT-2' }
  // Leerer Verlauf: erst die neueste Seite holen ('laden'), und das zählt.
  const erster = T.sprungSchritt({ ...ziel, seiten: 0 })
  assert.equal(erster.schritt, 'laden')
  assert.equal(erster.seiten, 1, 'der Ladeversuch der neuesten Seite zählt mit')
  // Der Server antwortet LEER: der nächste Schritt lädt wieder — bis 10.
  assert.equal(T.sprungSchritt({ ...ziel, seiten: 9 }).schritt, 'laden')
  assert.equal(T.sprungSchritt({ ...ziel, seiten: 9 }).seiten, 10)
  assert.equal(T.sprungSchritt({ ...ziel, seiten: 10 }).schritt, 'weg',
    'bei 10 Versuchen ist Schluss — auch im leeren Verlauf keine Endlosschleife')
  // Mit Verlauf: 'weiter' zählt ebenfalls.
  const mitVerlauf = { ...ziel, vorhanden: [{ ident: 'N-1' }] }
  assert.equal(T.sprungSchritt({ ...mitVerlauf, seiten: 3 }).schritt, 'weiter')
  assert.equal(T.sprungSchritt({ ...mitVerlauf, seiten: 3 }).seiten, 4)
  assert.equal(T.sprungSchritt({ ...mitVerlauf, seiten: 9 }).seiten, 10)
  // Gefunden gewinnt immer.
  assert.equal(T.sprungSchritt({ ...ziel, nachricht: 'N-1', vorhanden: [{ ident: 'N-1' }], seiten: 9 }).schritt, 'da')
})

test('CHAT-11b/A (R1/1): anderes Gespräch offen → nichts laden (kein Fremdverlauf)', () => {
  const basis = { nachricht: 'N-9', vorhanden: [{ ident: 'N-1' }], gespraech: 'CHAT-2', seiten: 0 }
  assert.equal(T.sprungSchritt({ ...basis, offen: 'CHAT-5' }).schritt, 'wechsel',
    'ein anderes Gespräch ist offen — Seiten des ALTEN Gesprächs dürfen nicht geladen werden')
  assert.equal(T.sprungSchritt({ ...basis, offen: 'CHAT-2' }).schritt, 'weiter')
  // Noch keines offen: der Sprung muss auf die Adresse WARTEN, bevor er lädt —
  // hier ist „noch keines offen“ dasselbe Zeichen wie „ein anderes ist offen“
  // (`'' !== 'CHAT-2'`); der Aufrufer wartet in `sprungBereit` davor.
  assert.equal(T.sprungSchritt({ ...basis, offen: '' }).schritt, 'wechsel')
})

test('CHAT-11b-2 (R1/3): `aelterStand` — ein frisch geöffnetes Gespräch kennt seinen Stand noch nicht', async () => {
  const L = await import(new URL('composables/nachrichtenLogik.mjs', SRC).href)
  // Bisheriger Stand vorhanden: die neueste Seite (`null`) ändert ihn NICHT —
  // sonst schaltete jeder Poll das Nachladen wieder an.
  assert.equal(L.aelterStand(true, null), true)
  assert.equal(L.aelterStand(false, null), false)
  // Noch KEIN Stand (frisch geöffnet): die volle neueste Seite heißt „oben geht
  // es weiter“, eine kürzere ist der Anfang.
  assert.equal(L.aelterStand(null, null, L.SEITE), true,
    'ein voller Verlauf (50 Zeilen) hat ältere Seiten')
  assert.equal(L.aelterStand(null, null, L.SEITE + 3), true)
  assert.equal(L.aelterStand(null, null, L.SEITE - 1), false,
    'eine kürzere Seite ist der Anfang des Verlaufs')
  assert.equal(L.aelterStand(null, null, 0), false)
  // Eine Aussage des Servers gilt immer.
  assert.equal(L.aelterStand(null, false), false)
  assert.equal(L.aelterStand(false, true), true)
})

test('CHAT-11b/A: Sprungziel über `chat.nachricht_kontext` — keine geratene Kennung', async () => {
  const adresse = (g) => `#/nachrichten/${encodeURIComponent(g)}`
  const gefragt = []
  const eins = await T.sprungZiel('CHAT-N-42', async (n) => {
    gefragt.push(n)
    return { gespraech: 'CHAT-R7' }
  }, adresse)
  assert.deepEqual(gefragt, ['CHAT-N-42'], 'gefragt wird die NACHRICHT')
  assert.deepEqual(eins, { art: 'gespraech', gespraech: 'CHAT-R7', nachricht: 'CHAT-N-42', adresse: '#/nachrichten/CHAT-R7' })

  // Unbekannt/gelöscht/fremd: der Server sagt nichts → keine Auskunft.
  assert.deepEqual(await T.sprungZiel('X', async () => null, adresse), { art: 'weg', nachricht: 'X' })
  assert.deepEqual(await T.sprungZiel('X', async () => { throw new Error('404') }, adresse), { art: 'nichts', nachricht: 'X' })
  assert.deepEqual(await T.sprungZiel('', async () => ({}), adresse), { art: 'nichts' })
})

test('CHAT-11b/A: Tasten der Trefferliste', () => {
  const taste = (key, extra = {}) => T.trefferTaste({ key, anzahl: 3, ...extra })
  assert.equal(taste('ArrowDown'), 'weiter')
  assert.equal(taste('ArrowUp'), 'zurueck')
  assert.equal(taste('Enter'), 'oeffnen')
  assert.equal(taste('Escape'), 'schliessen')
  assert.equal(taste('Tab'), null, 'die Tabulatortaste gehört dem Feld')
  assert.equal(taste('Enter', { isComposing: true }), null, 'eine IME-Eingabe behält Enter')
  assert.equal(T.trefferTaste({ key: 'Enter', anzahl: 0 }), null, 'ohne Treffer öffnet Enter nichts')
  assert.equal(T.trefferTaste({ key: 'Escape', anzahl: 0 }), 'schliessen', 'schließen geht immer')
  // Umlauf wie im Hausmenü.
  assert.equal(T.naechsteTrefferStelle(2, 1, 3), 0)
  assert.equal(T.naechsteTrefferStelle(0, -1, 3), 2)
  assert.equal(T.naechsteTrefferStelle(0, 1, 0), 0)
  assert.equal(T.optionKennung('liste', 2), 'liste-treffer-2')
  assert.equal(T.optionKennung('liste', null), null)
})

// ════════════════════════════════════════════════════════════════════════════
// B · ChatSuche.vue gemountet
// ════════════════════════════════════════════════════════════════════════════

function sucheAttrappen(ordner, { personen = [], trefferSeiten = () => seite([]), fehler = null } = {}) {
  const { api, session } = netzAttrappe(ordner, '__SUCH11B')
  globalThis.__SUCH11B_PERSONEN = personen
  globalThis.__SUCH11B_TREFFER = trefferSeiten
  globalThis.__SUCH11B_FEHLER = fehler
  return { api, session }
}

function netzAttrappe(ordner, praefix) {
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

async function sucheMontieren({ begriff = '', personen = [], trefferSeiten = () => seite([]) } = {}) {
  const ordner = join(TMP, 'suche-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  const { api, session } = sucheAttrappen(ordner, { personen, trefferSeiten })
  const aufrufe = []
  globalThis.__SUCH11B_PUSH = (eintrag) => aufrufe.push(eintrag)
  globalThis.__SUCH11B_SERVER = async (aufruf) => {
    if (/personen_suchen$/.test(String(aufruf?.methode))) return { treffer: personen, limit: 20 }
    if (/nachrichten_suchen$/.test(String(aufruf?.methode))) return trefferSeiten(aufruf.parameter)
    return {}
  }
  dom.window.location.hash = '#/nachrichten/suche?q=x'
  const U = (rel) => pathToFileURL(SRC.pathname + rel).href
  umleitung.clear()
  umleitung.set(U('composables/useApi.js'), pathToFileURL(api).href)
  umleitung.set(U('composables/useSession.js'), pathToFileURL(session).href)

  const uhr = uhrAttrappe()
  const gemeldet = []
  const mod = (await import(pathToFileURL(baum('components/chat/ChatSuche.vue', { frisch: true, ordner })).href)).default
  const gemountet = await mounten(mod, {
    gespraeche: [], startBegriff: begriff, timer: uhr.timer, timerAus: uhr.timerAus,
  }, { horcher: (art, wert) => gemeldet.push({ art, wert }), propNamen: ['sucht', 'springen'] })
  return { ...gemountet, aufrufe, uhr, gemeldet }
}

async function suchTippen(host, wert) {
  const feld = host.querySelector('input#chat-suche')
  assert.ok(feld, 'das Suchfeld steht im DOM')
  feld.value = wert
  feld.dispatchEvent(new dom.window.Event('input', { bubbles: true }))
  await warte(8)
}

const abschnittTitel = (host) => [...host.querySelectorAll('.dk-chat-suchergebnis h3.dk-chat-abschnitt-titel')]
  .map((h) => h.textContent.trim())

test('CHAT-11b/B: der Abschnitt „In Nachrichten“ erscheint ab 2 Zeichen', async () => {
  const s = await sucheMontieren({ trefferSeiten: () => seite([treffer({ nachricht: 'CHAT-N-1' })]) })
  assert.deepEqual(abschnittTitel(s.host), [], 'ohne Eingabe kein Abschnitt')

  await suchTippen(s.host, 'a')
  await s.uhr.feuern()
  assert.deepEqual(abschnittTitel(s.host), [], 'bei EINEM Zeichen wird nichts gefragt und nichts gezeigt')
  assert.equal(s.aufrufe.filter((a) => /nachrichten_suchen$/.test(a.methode)).length, 0,
    'unter 2 Zeichen geht KEIN Abruf hinaus')

  await suchTippen(s.host, 'sa')
  await s.uhr.feuern()
  assert.ok(abschnittTitel(s.host).includes('In Nachrichten'), 'ab 2 Zeichen steht der Abschnitt da')
  assert.equal(s.aufrufe.filter((a) => /nachrichten_suchen$/.test(a.methode)).length, 1, 'EIN Abruf')
  const anruf = s.aufrufe.find((a) => /nachrichten_suchen$/.test(a.methode))
  const { signal, ...parameter } = anruf.parameter
  assert.deepEqual(parameter, { q: 'sa' }, 'q gefaltet, ohne `gespraech`, ohne `vor`')
  assert.ok(signal, 'der Abruf bekommt ein Abbruch-Signal (ein laufender Abruf wird abgebrochen)')
  s.abbaum()
})

test('CHAT-11b/B: MARKIERUNG als Text — <mark>, kein v-html; „<script>“ bleibt Text', async () => {
  const zeilen = [treffer({ nachricht: 'CHAT-N-1', vor: 'Probe am ', fund: 'Samstag', nach: ' um zehn.' })]
  const s = await sucheMontieren({ trefferSeiten: () => seite(zeilen) })
  await suchTippen(s.host, 'samstag')
  await s.uhr.feuern()
  await rendern(4)

  const marken = s.host.querySelectorAll('.dk-treffer-ausschnitt mark')
  assert.equal(marken.length, 1, 'genau EINE Markierung')
  assert.equal(marken[0].textContent, 'Samstag', 'markiert ist der gefundene Text')
  assert.equal(s.host.querySelector('.dk-treffer-ausschnitt').textContent, 'Probe am Samstag um zehn.',
    'die drei Teile stehen zusammenhängend im Text')
  s.abbaum()

  // DERSELBE Fall mit HTML im Ausschnitt: der Text bleibt Text — es entsteht
  // KEIN <script>-Element, und der Quelltext enthält kein `v-html`.
  const boese = [treffer({
    nachricht: 'CHAT-N-2', vor: 'Achtung ', fund: '<script>alert(1)</script>', nach: ' und Ende',
  })]
  const b = await sucheMontieren({ trefferSeiten: () => seite(boese) })
  await suchTippen(b.host, 'achtung')
  await b.uhr.feuern()
  await rendern(4)
  assert.equal(b.host.querySelectorAll('script').length, 0, 'kein <script>-Element im DOM')
  assert.match(b.host.querySelector('.dk-treffer-ausschnitt').textContent, /<script>alert\(1\)<\/script>/,
    'der Text mit „<script>“ ist SICHTBAR und unverändert')
  const quelle = readFileSync(new URL('components/chat/ChatSuche.vue', SRC), 'utf8')
    + readFileSync(new URL('components/chat/ChatTreffer.vue', SRC), 'utf8')
  assert.doesNotMatch(quelle, /v-html/, 'kein v-html in den Trefferflächen')
  b.abbaum()
})

test('CHAT-11b/B: „Weitere Treffer“ lädt über `vor` die nächste Seite', async () => {
  const seite1 = seite([treffer({ nachricht: 'N-3' }), treffer({ nachricht: 'N-2' })], { mehr: true, vor: 'N-2' })
  const seite2 = seite([treffer({ nachricht: 'N-1' })], { mehr: false, vor: 'N-1' })
  const s = await sucheMontieren({
    trefferSeiten: (p) => (p && p.vor ? seite2 : seite1),
  })
  await suchTippen(s.host, 'samstag')
  await s.uhr.feuern()
  await rendern(4)
  assert.equal(s.host.querySelectorAll('.dk-treffer-zeile').length, 2)
  const knopf = [...s.host.querySelectorAll('.dk-treffer-mehr')]
  assert.equal(knopf.length, 1, '„Weitere Treffer“ steht da, solange `mehr` gilt')

  knopf[0].dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }))
  await warte(12)
  await rendern(4)
  const abrufe = s.aufrufe.filter((a) => /nachrichten_suchen$/.test(a.methode))
  assert.equal(abrufe.length, 2)
  const { signal, ...geblaettert } = abrufe[1].parameter
  assert.deepEqual(geblaettert, { q: 'samstag', vor: 'N-2' }, 'geblättert wird über `vor`')
  assert.ok(signal, 'auch das Blättern hängt an einem Abruf mit Signal')
  assert.equal(s.host.querySelectorAll('.dk-treffer-zeile').length, 3, 'die neue Seite hängt HINTEN an')
  assert.equal(s.host.querySelectorAll('.dk-treffer-mehr').length, 0, 'ohne `mehr` kein Knopf')
  s.abbaum()
})

test('CHAT-11b/B: eine überholte Antwort wird verworfen', async () => {
  let loeseLangsam = null
  const s = await sucheMontieren({
    trefferSeiten: (p) => {
      if (String(p?.q) === 'sa') {
        // Die Antwort auf „sa“ bleibt hängen, bis der Test sie freigibt.
        return new Promise((loese) => { loeseLangsam = () => loese(seite([treffer({ nachricht: 'ALT' })], { vor: 'ALT' })) })
      }
      return seite([treffer({ nachricht: 'NEU' })], { vor: 'NEU' })
    },
  })
  await suchTippen(s.host, 'sa')
  await s.uhr.feuern()
  await suchTippen(s.host, 'sam')
  await s.uhr.feuern()
  await warte(10)
  await rendern(4)
  const texte = [...s.host.querySelectorAll('.dk-treffer-zeile')].map((z) => z.textContent)
  assert.equal(texte.length, 1, 'nur die Zeilen der JÜNGSTEN Frage')
  // Die alte Antwort kommt JETZT zu spät — sie darf nichts mehr schreiben.
  if (loeseLangsam) loeseLangsam()
  await warte(14)
  await rendern(4)
  assert.equal(s.host.querySelectorAll('.dk-treffer-zeile').length, 1,
    'die überholte Antwort hat nichts überschrieben')
  s.abbaum()
})

test('CHAT-11b/B: keine Treffer → ein ruhiger Satz (und der EINE Leerzustand nicht doppelt)', async () => {
  const s = await sucheMontieren({ trefferSeiten: () => seite([]) })
  await suchTippen(s.host, 'xyz')
  await s.uhr.feuern()
  await rendern(4)
  const ruhig = s.host.querySelector('.dk-treffer-leer')
  assert.ok(ruhig, 'der ruhige Satz steht da')
  assert.match(ruhig.textContent, /Keine Nachricht enthält diesen Begriff\./)
  s.abbaum()
})

// ════════════════════════════════════════════════════════════════════════════
// C · ChatTreffer.vue gemountet — Tastatur und Ansage
// ════════════════════════════════════════════════════════════════════════════

test('CHAT-11b/C: Pfeiltasten bewegen, Enter öffnet, Escape schließt, aria-live sagt die Zahl', async () => {
  const zeilen = [
    T.trefferZeile(treffer({ nachricht: 'N-3' })),
    T.trefferZeile(treffer({ nachricht: 'N-2' })),
  ]
  const gemeldet = []
  const mod = (await import(pathToFileURL(baum('components/chat/ChatTreffer.vue', { frisch: true })).href)).default
  const m = await mounten(mod, { zeilen, sichtbar: true, aktiv: 0 },
    { horcher: (art, wert) => gemeldet.push({ art, wert }), propNamen: ['waehlen', 'mehr', 'aktiv', 'schliessen'] })
  await rendern(2)

  const liste = m.host.querySelector('[role="listbox"]')
  assert.ok(liste, 'die Treffer stehen als Listbox da')
  assert.equal(liste.getAttribute('aria-activedescendant'), 'dk-chat-treffer-liste-treffer-0')
  const ansage = m.host.querySelector('[aria-live]')
  assert.match(ansage.textContent, /2 Treffer in den Nachrichten/, 'die Zahl wird angesagt')

  liste.dispatchEvent(new dom.window.KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }))
  await warte(4)
  assert.deepEqual(gemeldet.filter((g) => g.art === 'aktiv').map((g) => g.wert), [1], '↓ bewegt weiter')

  m.setze('aktiv', 1)
  await warte(6)
  liste.dispatchEvent(new dom.window.KeyboardEvent('keydown', { key: 'Enter', bubbles: true }))
  await warte(6)
  const gewaehlt = gemeldet.filter((g) => g.art === 'waehlen')
  assert.equal(gewaehlt.length, 1, 'Enter öffnet den GEWÄHLTEN Treffer')
  assert.equal(gewaehlt[0].wert.nachricht, 'N-2')

  liste.dispatchEvent(new dom.window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
  await warte(4)
  assert.equal(gemeldet.filter((g) => g.art === 'schliessen').length, 1, 'Escape schließt')
  m.abbaum()
})

test('CHAT-11b/C: ohne Treffer kein „Weitere“, leer steht der ruhige Satz', async () => {
  const mod = (await import(pathToFileURL(baum('components/chat/ChatTreffer.vue', { frisch: true })).href)).default
  const m = await mounten(mod, { zeilen: [], sichtbar: true, mehr: true })
  await rendern(2)
  assert.equal(m.host.querySelector('.dk-treffer-mehr'), null, 'ohne Zeilen kein Blätterknopf')
  assert.match(m.host.textContent, /Keine Nachricht enthält diesen Begriff\./)
  m.abbaum()

  // Zugemacht (Escape in der Suche): der Abschnitt steht gar nicht da.
  const z = await mounten(mod, { zeilen: [], sichtbar: false })
  await rendern(2)
  assert.equal(z.host.querySelector('.dk-treffer'), null, 'nicht sichtbar → kein Abschnitt')
  z.abbaum()
})

// ════════════════════════════════════════════════════════════════════════════
// D · Die Seite „Nachrichten“ gemountet — Sprung und Suche im Gespräch
// ════════════════════════════════════════════════════════════════════════════

const GESPRAECH_ZIEL = {
  name: 'CHAT-2', art: 'gruppe', gruppe: 'Chor', untergruppe: null,
  titel: 'Chor', teilnehmer: 0, stumm: false, geoeffnet: true,
  ungelesen: 0, letzte_nachricht: 'Hallo', letzte_am: '2026-11-18T10:00:00', darf_senden: true,
}

/** Eine Nachrichtenzeile des Verlaufs (`chat.verlauf`). */
let zeitZaehler = 0
function verlaufsZeile(name, { text = 'Hallo', am = null } = {}) {
  // Fortlaufende Zeitstempel: „ältere Seite“ heißt wirklich älter (die Seite
  // sortiert endgültig nach Zeit, `vor` ist die ÄLTESTE Kennung der Seite).
  zeitZaehler += 1
  const stempel = am || new Date(Date.UTC(2026, 10, 18, 10, 0, 0) + zeitZaehler * 60000).toISOString()
  return { name, gespraech: 'CHAT-2', text, autor: 'M-1', eigene: false, erstellt_am: stempel }
}

/**
 * Die Seite mit Attrappen mounten.
 *
 * `verlauf` ist der Verlauf, den der Server KENNT (neueste Seite). `seiten`
 * beschreibt, was `vor=<anker>` zurückgibt: jeder Aufruf bekommt den Anker
 * und liefert die Seite davor — so wird das Nachladen ZÄHLBAR.
 */
async function seite11b({
  hash = '#/nachrichten/CHAT-2',
  verlauf = [verlaufsZeile('N-3'), verlaufsZeile('N-2')],
  aelterSeiten = {},
  kontext = () => ({ gespraech: 'CHAT-2', art: 'gruppe', titel: 'Chor' }),
} = {}) {
  const ordner = join(TMP, 'seite-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  const aufrufe = []
  const api = join(ordner, 'api.mjs')
  writeFileSync(api, [
    'export async function apiCall(methode, parameter) {',
    '  globalThis.__PUSH11B({ art: "POST", methode, parameter })',
    '  return globalThis.__SERVER11B({ methode, parameter })',
    '}',
    'export async function apiGet(methode, parameter) {',
    '  globalThis.__PUSH11B({ art: "GET", methode, parameter })',
    '  return globalThis.__SERVER11B({ methode, parameter })',
    '}',
    'export const apiUrl = (p) => "https://pruefstand.invalid/" + p',
    'export class AuditConfirmationRequired extends Error {}',
    'export const pruefeSitzungsAntwort = () => false',
    'export const apiAntwortPruefen = async () => ({ message: {} })',
  ].join('\n'))
  const session = join(ordner, 'session.mjs')
  writeFileSync(session, [
    `import { ref } from '${VUE_URL}'`,
    'export function useSession() {',
    '  return { mitglied: ref({ name: "M-0" }), istMitgliederverwaltung: ref(false),',
    '    istAdministrator: ref(false), roles: ref([]) }',
    '}',
  ].join('\n'))
  const U = (rel) => pathToFileURL(SRC.pathname + rel).href
  umleitung.clear()
  umleitung.set(U('composables/useApi.js'), pathToFileURL(api).href)
  umleitung.set(U('composables/useSession.js'), pathToFileURL(session).href)

  globalThis.__PUSH11B = (e) => aufrufe.push(e)
  globalThis.__SERVER11B = async ({ methode, parameter }) => {
    const kurz = String(methode).split('.').pop()
    if (kurz === 'meine_gespraeche') return { gespraeche: [GESPRAECH_ZIEL] }
    if (kurz === 'verlauf') {
      if (parameter?.vor) {
        const seite0 = aelterSeiten[String(parameter.vor)]
        // Der Server schickt bei einer älteren Seite `richtung: 'vor'`
        return { richtung: 'vor', nachrichten: seite0?.nachrichten ?? [] }
      }
      return { richtung: 'neueste', nachrichten: verlauf }
    }
    if (kurz === 'nachricht_kontext') return kontext(parameter?.nachricht)
    if (kurz === 'nachrichten_suchen') return globalThis.__SUCHE11B(parameter)
    if (kurz === 'lesestand_setzen') return { ungelesen: 0 }
    if (kurz === 'meine_sperren') return { sperren: [] }
    return {}
  }
  globalThis.__SUCHE11B = () => seite([])
  dom.window.__DIakonosBOOT = { roles: ['Mitglied'], is_admin: false, module_sichtbar: ['chat'] }
  dom.window.location.hash = hash
  dom.window.matchMedia = (abfrage) => ({
    media: String(abfrage), matches: false,
    addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {},
  })
  const mod = (await import(pathToFileURL(baum('pages/Nachrichten.vue', { ordner, frisch: true })).href)).default
  let vertreten = null
  const m = await mounten(mod, {}, { vertreter: (r) => { vertreten = r } })
  // `nextTick` läuft über die Warteschlange — die muss bedient werden, sonst
  // bleibt der Aufbau (und danach jeder Sprung) stehen.
  for (let i = 0; i < 15; i += 1) { await warte(8); await rendern(4) }
  return { ...m, aufrufe, vertreten: () => vertreten }
}

/** Der Such-Abschnitt fragt erst nach `ENTPRELLUNG_MS` (echter Timer). */
const sucheTippen11b = async (host, wert) => {
  const feld = host.querySelector('input#chat-suche')
  assert.ok(feld, 'das Suchfeld steht im DOM')
  feld.value = wert
  feld.dispatchEvent(new dom.window.Event('input', { bubbles: true }))
  await warte(20)
  await new Promise((loese) => setTimeout(loese, 420))
  await warte(20)
  await rendern(4)
}

const klick11b = (el) => {
  assert.ok(el, 'das Element steht im DOM')
  el.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true, cancelable: true }))
}

const zeilenImVerlauf = (host) => [...host.querySelectorAll('.dk-chat-verlaufsliste .dk-chat-beitrag')]
  .map((li) => li.getAttribute('data-name'))

/** Der Anker einer Seite ist ihre ÄLTESTE Kennung. */
const aelteste = (seite0) => String(seite0.vor || seite0.nachrichten[0]?.name || '')

test('CHAT-11b/D: der Sprung holt ältere Seiten nach (≤ 10) und hebt die Nachricht hervor', async () => {
  // N-1 liegt drei Seiten zurück. Der Server liefert je Anker eine VOLLE Seite
  // (50 Zeilen, SEITE = 50) mit ÄLTEREN Zeitstempeln — so wächst der Verlauf
  // bei jedem Nachladen rückwärts, egal welche Kennung der Anker trägt.
  let zaehler = 0
  const s = await seite11b({
    verlauf: [verlaufsZeile('N-4', { am: new Date(Date.UTC(2026, 10, 18, 12, 0, 0)).toISOString() })],
    aelterSeiten: {},
  })
  // Die Attrappe wird nach dem Aufbau ersetzt: sie antwortet auf JEDEN Anker.
  globalThis.__SERVER11B = async ({ methode, parameter }) => {
    const kurz = String(methode).split('.').pop()
    if (kurz === 'meine_gespraeche') return { gespraeche: [GESPRAECH_ZIEL] }
    if (kurz === 'verlauf') {
      if (!parameter?.vor) return { richtung: 'neueste', nachrichten: [verlaufsZeile('N-4', { am: new Date(Date.UTC(2026, 10, 18, 12, 0, 0)).toISOString() })] }
      zaehler += 1
      // Seite 1 und 2: je 50 Zeilen; Seite 3 enthält N-1.
      const stunde = 11 - zaehler
      const zeilen = zaehler <= 2
        ? Array.from({ length: 50 }, (_, i) => verlaufsZeile(`Q${zaehler}-${i}`, { am: new Date(Date.UTC(2026, 10, 18, Math.max(0, stunde), i % 60, i % 60)).toISOString() }))
        : [verlaufsZeile('N-1', { am: new Date(Date.UTC(2026, 10, 18, 7, 0, 0)).toISOString() }),
          ...Array.from({ length: 49 }, (_, i) => verlaufsZeile(`Q3-${i}`, { am: new Date(Date.UTC(2026, 10, 18, 6, 0, i % 60)).toISOString() }))]
      return { richtung: 'vor', nachrichten: zeilen }
    }
    if (kurz === 'nachricht_kontext') return { gespraech: 'CHAT-2', art: 'gruppe', titel: 'Chor' }
    if (kurz === 'nachrichten_suchen') return seite([treffer({ nachricht: 'N-1' })])
    if (kurz === 'lesestand_setzen') return { ungelesen: 0 }
    if (kurz === 'meine_sperren') return { sperren: [] }
    return {}
  }
  await warte(20)

  // Der Weg ist der der Karte: Suchfeld tippen, Treffer anklicken. Ein Klick
  // ist es, weil der Sprung erst `nachricht_kontext` braucht (kein Link).
  await sucheTippen11b(s.host, 'samstag')
  const zeile = s.host.querySelector('.dk-treffer-zeile')
  assert.ok(zeile, 'der Treffer steht im Abschnitt „In Nachrichten“')
  klick11b(zeile)
  const warten = exposed(s.exposed()).sprungFertig()
  for (let i = 0; i < 40; i += 1) { await warte(4); await rendern(2) }
  await warten
  await rendern(4)

  const kontext = s.aufrufe.filter((a) => /nachricht_kontext$/.test(a.methode))
  assert.deepEqual(kontext.map((a) => a.parameter), [{ nachricht: 'N-1' }],
    'genau EINE Kontext-Abfrage, mit der Nachricht')
  const vorAbrufe = s.aufrufe.filter((a) => /verlauf$/.test(a.methode) && a.parameter?.vor)
  assert.equal(vorAbrufe.length, 3,
    'ältere Seiten werden nachgeladen, bis die Nachricht da ist: '
    + JSON.stringify(vorAbrufe.map((a) => a.parameter.vor))
    + ' | stand ' + JSON.stringify(exposed(s.exposed()).sprungStand()))
  assert.ok(zeilenImVerlauf(s.host).includes('N-1'), 'die Nachricht steht jetzt im Verlauf')
  const markiert = s.host.querySelector('.dk-chat-sprungziel')
  assert.ok(markiert, 'die gefundene Nachricht ist kurz hervorgehoben')
  assert.equal(markiert.getAttribute('data-name'), 'N-1')
  assert.equal(s.host.querySelector('.dk-chat-sprungweg'), null, 'kein „gibt es nicht mehr“')
  s.abbaum()
})

test('CHAT-11b/D: höchstens 10 Seiten — danach der ruhige Hinweis', async () => {
  // Ein Verlauf, der die gesuchte Nachricht NIE enthält: jede ältere Seite ist
  // voll und immer älter — es ginge also endlos weiter.
  const s = await seite11b({ verlauf: [verlaufsZeile('N-9')] })
  let zaehler = 0
  globalThis.__SERVER11B = async ({ methode, parameter }) => {
    const kurz = String(methode).split('.').pop()
    if (kurz === 'meine_gespraeche') return { gespraeche: [GESPRAECH_ZIEL] }
    if (kurz === 'verlauf') {
      if (!parameter?.vor) return { richtung: 'neueste', nachrichten: [verlaufsZeile('N-9', { am: new Date(Date.UTC(2026, 10, 18, 12, 0, 0)).toISOString() })] }
      zaehler += 1
      const zeilen = Array.from({ length: 50 }, (_, i) => verlaufsZeile(`W${zaehler}-${i}`, {
        am: new Date(Date.UTC(2026, 10, 18, 0, Math.max(0, 55 - zaehler), i % 60)).toISOString(),
      }))
      return { richtung: 'vor', nachrichten: zeilen }
    }
    if (kurz === 'nachricht_kontext') return { gespraech: 'CHAT-2', art: 'gruppe', titel: 'Chor' }
    if (kurz === 'nachrichten_suchen') return seite([treffer({ nachricht: 'GIBTS-NICHT' })])
    if (kurz === 'lesestand_setzen') return { ungelesen: 0 }
    if (kurz === 'meine_sperren') return { sperren: [] }
    return {}
  }
  await warte(20)

  await sucheTippen11b(s.host, 'samstag')
  klick11b(s.host.querySelector('.dk-treffer-zeile'))
  const wartenVier = exposed(s.exposed()).sprungFertig()
  for (let i = 0; i < 60; i += 1) { await warte(4); await rendern(2) }
  await wartenVier
  await rendern(4)

  const vorAbrufe = s.aufrufe.filter((a) => /verlauf$/.test(a.methode) && a.parameter?.vor)
  assert.equal(vorAbrufe.length, T.SPRUNG_MAX_SEITEN, 'genau 10 Seiten, nicht mehr')
  const hinweis = s.host.querySelector('.dk-chat-sprungweg')
  assert.ok(hinweis, 'danach steht der ruhige Satz da')
  assert.match(hinweis.textContent, /Diese Nachricht gibt es nicht mehr\./)
  s.abbaum()
})

test('CHAT-11b/D: gelöschte Nachricht → Gespräch öffnen und den ruhigen Hinweis zeigen', async () => {
  const s = await seite11b({
    verlauf: [verlaufsZeile('N-3')],
    // Der Server sagt zu dieser Kennung NICHTS (gelöscht → 404; `erwaehnungZiel`
    // antwortet dann mit dem Bereich).
    kontext: () => { throw Object.assign(new Error('nicht gefunden'), { status: 404 }) },
  })
  await warte(20)
  globalThis.__SUCHE11B = () => seite([treffer({ nachricht: 'N-WEG' })])
  await sucheTippen11b(s.host, 'samstag')
  klick11b(s.host.querySelector('.dk-treffer-zeile'))
  const wartenWeg = exposed(s.exposed()).sprungFertig()
  for (let i = 0; i < 30; i += 1) { await warte(4); await rendern(2) }
  await wartenWeg
  await rendern(4)
  const hinweis = s.host.querySelector('.dk-chat-sprungweg')
  assert.ok(hinweis, 'der Hinweis steht da')
  assert.match(hinweis.textContent, /Diese Nachricht gibt es nicht mehr\./)
  assert.equal(hinweis.getAttribute('role'), 'status', 'ruhig, keine Alarmfarbe')
  s.abbaum()
})

test('CHAT-11b/D: die Suche im Gespräch schickt `gespraech` — Escape schließt sie', async () => {
  const s = await seite11b({ verlauf: [verlaufsZeile('N-3')] })
  await warte(20)
  const gefragt = []
  globalThis.__SUCHE11B = (parameter) => {
    gefragt.push(parameter)
    return seite([treffer({ nachricht: 'N-2', vor: 'Hallo ', fund: 'Samstag', nach: '!' })], { vor: 'N-2' })
  }

  // Der Kopf trägt den Such-Knopf (Lupe, aria-label) — er öffnet das Feld.
  const knopf = [...s.host.querySelectorAll('button')]
    .find((b) => b.getAttribute('aria-label') === 'Im Gespräch suchen')
  assert.ok(knopf, 'der Such-Knopf steht im Gesprächskopf')
  assert.equal(knopf.getAttribute('aria-expanded'), 'false')
  klick11b(knopf)
  await warte(8)
  await rendern(4)
  const feld = s.host.querySelector('#chat-gespraech-suche')
  assert.ok(feld, 'das Suchfeld steht unter dem Kopf da')
  assert.equal(knopf.getAttribute('aria-expanded'), 'true')

  feld.value = 'samstag'
  feld.dispatchEvent(new dom.window.Event('input', { bubbles: true }))
  // Entprellt wie die vorhandene Suche (`ENTPRELLUNG_MS` = 300 ms) — hier
  // läuft der ECHTE Timer, also wird auch echt gewartet.
  await warte(20)
  await new Promise((loese) => setTimeout(loese, 420))
  await warte(20)
  await rendern(4)
  assert.equal(gefragt.length, 1, 'EIN Abruf nach der Ruhezeit')
  const { signal, ...parameter } = gefragt[0]
  assert.deepEqual(parameter, { q: 'samstag', gespraech: 'CHAT-2' },
    'die Suche hängt am GESPRÄCH (gespraech=<kennung>)')
  assert.ok(signal, 'auch hier gibt es ein Abbruch-Signal (R1/7)')
  const liste = s.host.querySelector('#dk-gespraech-treffer')
  assert.ok(liste, 'die Treffer stehen als Liste unter dem Kopf')
  assert.equal(liste.querySelectorAll('li').length, 1)
  assert.match(liste.textContent, /Samstag/, 'der Ausschnitt steht da')

  // Escape schließt Liste und Feld.
  feld.dispatchEvent(new dom.window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }))
  await warte(8)
  await rendern(4)
  assert.equal(s.host.querySelector('#chat-gespraech-suche'), null, 'Escape schließt die Suche')
  assert.equal(s.host.querySelector('#dk-gespraech-treffer'), null, 'die Liste ist weg')
  s.abbaum()
})

test('CHAT-11b/D: die Trefferliste im Gespräch lässt sich mit Pfeilen bedienen', async () => {
  const s = await seite11b({ verlauf: [verlaufsZeile('N-5')] })
  await warte(20)
  globalThis.__SUCHE11B = () => seite([
    treffer({ nachricht: 'N-4' }), treffer({ nachricht: 'N-3' }),
  ])
  exposed(s.exposed()).gespraechSuche.umschalten()
  await warte(10)
  await rendern(2)
  exposed(s.exposed()).gespraechSuche.tippen('samstag')
  await new Promise((loese) => setTimeout(loese, 420))
  await warte(20)
  await rendern(4)

  const feld = s.host.querySelector('#chat-gespraech-suche')
  assert.equal(feld.getAttribute('aria-activedescendant'), 'dk-gespraech-treffer-treffer-0')
  feld.dispatchEvent(new dom.window.KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true, cancelable: true }))
  await warte(8)
  await rendern(4)
  assert.equal(exposed(s.exposed()).gespraechSucheStand().aktiv, 1, '↓ bewegt in der Liste')
  assert.equal(s.host.querySelector('#chat-gespraech-suche').getAttribute('aria-activedescendant'),
    'dk-gespraech-treffer-treffer-1')
  s.abbaum()
})

/** Die exponierte Fläche EINER montierten Seite (`defineExpose`). */
function exposed(vertreter) {
  assert.ok(vertreter, 'die montierte Seite hat einen Vertreter (Instanz des Kindes)')
  // Vue 3: `expose(...)` in `<script setup>` schreibt die Werte auf das
  // Proxy-ZIEL des Bauteil-Kontexts — nicht auf den Proxy selbst.
  const ziel = vertreter.ctx || vertreter
  assert.equal(typeof ziel.springen, 'function',
    'die Seite legt `springen` offen (`defineExpose`) — Schlüssel: ' + Object.keys(ziel).join(','))
  return ziel
}

// ════════════════════════════════════════════════════════════════════════════
// E · Review R1 — die Nachbesserungen vom 20.11. (Sprung, Blättern, Suche)
// ════════════════════════════════════════════════════════════════════════════

/** Ein zweites Gespräch (Runde), damit „ein ANDERES ist offen“ prüfbar ist. */
const GESPRAECH_ANDERES = {
  name: 'CHAT-5', art: 'runde', gruppe: null, untergruppe: null,
  titel: 'Runde am Dienstag', teilnehmer: 3, stumm: false, geoeffnet: true,
  ungelesen: 0, letzte_nachricht: 'Hallo', letzte_am: '2026-11-18T09:00:00', darf_senden: true,
}

/**
 * Die Seite mit ZWEI Gesprächen mounten, deren `nachricht_kontext` eine
 * Nachricht nach `CHAT-2` legt. Die Verlaufsattrappe antwortet je Gespräch mit
 * einer eigenen neuesten Seite; `aelter` sagt, ob es ältere Seiten gibt.
 */
async function seiteZwei({ hash, aelter = false, zaehleVor = null, neueste = null, seiten = null, vorHalten = null } = {}) {
  const ordner = join(TMP, 'zwei-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  const aufrufe = []
  const api = join(ordner, 'api.mjs')
  writeFileSync(api, [
    'export async function apiCall(methode, parameter) {',
    '  globalThis.__PUSH2G({ art: "POST", methode, parameter })',
    '  return globalThis.__SERVER2G({ methode, parameter })',
    '}',
    'export async function apiGet(methode, parameter) {',
    '  globalThis.__PUSH2G({ art: "GET", methode, parameter })',
    '  return globalThis.__SERVER2G({ methode, parameter })',
    '}',
    'export const apiUrl = (p) => "https://pruefstand.invalid/" + p',
    'export class AuditConfirmationRequired extends Error {}',
    'export const pruefeSitzungsAntwort = () => false',
    'export const apiAntwortPruefen = async () => ({ message: {} })',
  ].join('\n'))
  const session = join(ordner, 'session.mjs')
  writeFileSync(session, [
    `import { ref } from '${VUE_URL}'`,
    'export function useSession() {',
    '  return { mitglied: ref({ name: "M-0" }), istMitgliederverwaltung: ref(false),',
    '    istAdministrator: ref(false), roles: ref([]) }',
    '}',
  ].join('\n'))
  const U = (rel) => pathToFileURL(SRC.pathname + rel).href
  umleitung.clear()
  umleitung.set(U('composables/useApi.js'), pathToFileURL(api).href)
  umleitung.set(U('composables/useSession.js'), pathToFileURL(session).href)

  globalThis.__PUSH2G = (e) => aufrufe.push(e)
  globalThis.__SERVER2G = async ({ methode, parameter }) => {
    const kurz = String(methode).split('.')[1] || ''
    if (kurz === 'meine_gespraeche') return { gespraeche: [GESPRAECH_ZIEL, GESPRAECH_ANDERES] }
    if (kurz === 'verlauf') {
      const g = String(parameter?.gespraech || '')
      const seite0 = globalThis.__SEITEN2G(g)
      if (parameter?.vor) {
        if (zaehleVor) zaehleVor(g, parameter.vor)
        // Ältere Seite: nur wenn `aelter` — sonst leer (Anfang erreicht).
        const zeilen = aelter && seite0.aeltere ? seite0.aeltere(parameter.vor) : []
        if (vorHalten) await vorHalten(g, parameter.vor)
        return { richtung: 'vor', nachrichten: zeilen }
      }
      return { richtung: 'neueste', nachrichten: seite0.neueste }
    }
    if (kurz === 'nachricht_kontext') return globalThis.__KONTEXT2G(parameter?.nachricht)
    if (kurz === 'nachrichten_suchen') return globalThis.__SUCHE2G(parameter)
    if (kurz === 'lesestand_setzen') return { ungelesen: 0 }
    if (kurz === 'meine_sperren') return { sperren: [] }
    return {}
  }
  globalThis.__SUCHE2G = () => seite([])
  globalThis.__KONTEXT2G = () => ({ gespraech: 'CHAT-2', art: 'gruppe', titel: 'Chor' })
  globalThis.__SEITEN2G = (g) => ({
    neueste: neueste ? neueste(g) : [verlaufsZeile(`NEU-${g}`)],
    aeltere: seiten ? (anker) => seiten(g, anker) : () => [],
  })
  // Am HANDY prüfen, wo es heißt „Handy“ (R1/4); sonst Desktop.
  const handy = globalThis.__HANDY === true
  dom.window.__DIakonosBOOT = { roles: ['Mitglied'], is_admin: false, module_sichtbar: ['chat'] }
  dom.window.location.hash = hash
  dom.window.matchMedia = (abfrage) => ({
    media: String(abfrage), matches: handy && /max-width/.test(String(abfrage)),
    addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {},
  })
  const mod = (await import(pathToFileURL(baum('pages/Nachrichten.vue', { ordner, frisch: true })).href)).default
  let vertreten = null
  const m = await mounten(mod, {}, { vertreter: (r) => { vertreten = r } })
  for (let i = 0; i < 15; i += 1) { await warte(8); await rendern(4) }
  return { ...m, aufrufe, vertreten: () => vertreten }
}

/** Auf einen Sprung warten — begrenzt: der Sprung endet, sobald er entschieden hat. */
async function sprungAbwarten(s, runden = 20) {
  const warten = exposed(s.exposed()).sprungFertig()
  for (let i = 0; i < runden; i += 1) { await warte(4); await rendern(2) }
  await warten
  await rendern(4)
}

test('CHAT-11b/E (R1/1): Sprung aus der LISTE (ohne offenes Gespräch, hashchange kommt später)', async () => {
  // Kein Gespräch offen: die Liste steht, erst der Sprung öffnet eines.
  const s = await seiteZwei({ hash: '#/nachrichten' })
  // Der Server kennt zu CHAT-2 genau EINE Nachricht — N-ALT liegt weiter oben
  // und ist nicht mehr da. Gesucht wird trotzdem N-ALT, damit der Weg
  // „öffnen → nachladen → Hinweis“ vollständig durchlaufen wird.
  exposed(s.exposed()).springen({ nachricht: 'N-ALT' })
  // Der `hashchange` des Browsers kommt als eigener Task — hier echt abwarten.
  await warte(20)
  await sprungAbwarten(s)

  assert.equal(dom.window.location.hash, '#/nachrichten/CHAT-2', 'das Gespräch ist über die Adresse geöffnet')
  assert.ok(zeilenImVerlauf(s.host).includes('NEU-CHAT-2'),
    'der Verlauf des ZIELS ist geladen: ' + JSON.stringify(zeilenImVerlauf(s.host)))
  // Es wurde also GEWARTET (richtiges Gespräch geladen) und nicht geraten:
  // kein gespräch des alten Zustands, keine Seiten eines fremden Verlaufs.
  // CHAT-11b-2: Der Sprung überlebt das Öffnen — danach wird im RICHTIGEN
  // Gespräch nachgeladen (bis zur Seitengrenze), nie in einem fremden.
  const vorAbrufe = s.aufrufe.filter((a) => /verlauf$/.test(a.methode) && a.parameter?.vor)
  assert.ok(vorAbrufe.length > 0,
    'nach dem Öffnen wird im Zielgespräch nachgeladen (CHAT-11b-2): '
    + JSON.stringify(vorAbrufe.map((a) => a.parameter.vor)))
  assert.deepEqual([...new Set(vorAbrufe.map((a) => a.parameter.gespraech))], ['CHAT-2'],
    'und zwar NUR im Zielgespräch')
  assert.equal(s.host.querySelector('.dk-chat-sprungziel'), null,
    'N-ALT ist nicht da — also nichts hervorgehoben')
  // Der Hinweis „Diese Nachricht gibt es nicht mehr.“ ist hier RICHTIG (es gibt
  // keine ältere Seite mehr) — er beweist, dass im ZIEL nachgeladen wurde:
  // vorher kam er schon beim Öffnen, ohne einen einzigen `vor`-Abruf.
  const hinweis = s.host.querySelector('.dk-chat-sprungweg')
  assert.ok(hinweis, 'nach dem vergeblichen Nachladen steht der ruhige Satz da')
  assert.match(hinweis.textContent, /Diese Nachricht gibt es nicht mehr\./)
  s.abbaum()
})

test('CHAT-11b/E (R1/1): Sprung, während ein ANDERES Gespräch offen ist', async () => {
  const s = await seiteZwei({ hash: '#/nachrichten/CHAT-5' })
  await warte(20)
  const vorAbrufe = () => s.aufrufe.filter((a) => /verlauf$/.test(a.methode) && a.parameter?.vor)
  const vorher = vorAbrufe().length

  exposed(s.exposed()).springen({ nachricht: 'N-ALT' })
  await warte(20)
  await sprungAbwarten(s)

  assert.equal(dom.window.location.hash, '#/nachrichten/CHAT-2', 'das ZIEL ist geöffnet')
  const nachher = vorAbrufe().slice(vorher)
  const fremd = nachher.filter((a) => String(a.parameter?.gespraech || '') !== 'CHAT-2')
  assert.deepEqual(fremd.map((a) => a.parameter.gespraech), [],
    'keine Seite des ALTEN Gesprächs (CHAT-5) wurde nachgeladen')
  // Der Verlauf zeigt das Ziel — es gibt dort nichts Älteres, also steht der
  // ruhige Hinweis — und zwar GENAU EINMAL (kein zweiter aus dem Verlauf des
  // ALTEN Gesprächs, der jetzt nicht mehr dasteht).
  const hinweise = [...s.host.querySelectorAll('.dk-chat-sprungweg')]
  const imVerlauf = [...s.host.querySelectorAll('.dk-chat-verlauf')]
    .flatMap((k) => [...k.querySelectorAll('.dk-chat-sprungweg')])
  assert.ok(imVerlauf.length <= 1, 'höchstens EIN Hinweis (dieselbe Stelle, nur einmal)')
  assert.ok(hinweise.length >= 1, 'irgendwo steht der ruhige Hinweis')
  assert.match(hinweise[0].textContent, /Diese Nachricht gibt es nicht mehr\./)
  // Und die Nachricht, die es gibt, ist im ZIEL geladen.
  assert.ok(zeilenImVerlauf(s.host).includes('NEU-CHAT-2'), 'der Verlauf des Ziels steht da')
  s.abbaum()
})

test('CHAT-11b/E (R1/6): „Diese Nachricht gibt es nicht mehr.“ steht auch in der Listenansicht', async () => {
  const s = await seiteZwei({ hash: '#/nachrichten' })
  await warte(20)
  // Unbekannt/kein Recht: der Server sagt nichts, es wird KEIN Gespräch geöffnet.
  globalThis.__KONTEXT2G = () => ({})
  exposed(s.exposed()).springen({ nachricht: 'WEG-1' })
  await warte(20)
  await sprungAbwarten(s)

  assert.equal(dom.window.location.hash, '#/nachrichten', 'kein geratenes Ziel')
  const hinweis = s.host.querySelector('.dk-chat-sprungweg')
  assert.ok(hinweis, 'der Hinweis steht in der Liste (nicht nur im Verlauf)')
  assert.match(hinweis.textContent, /Diese Nachricht gibt es nicht mehr\./)
  assert.equal(hinweis.getAttribute('role'), 'status', 'ruhig, keine Alarmfarbe')
  s.abbaum()
})

test('CHAT-11b/E (R1/4): am Handy schließt der Sprung die Suche (der Verlauf ist danach sichtbar)', async () => {
  globalThis.__HANDY = true
  try {
    const s = await seiteZwei({ hash: '#/nachrichten/suche?q=samstag&offen=CHAT-5' })
    await warte(20)
    const seite0 = exposed(s.exposed())
    assert.equal(seite0.sucheStand().offen, true, 'die Suche ist offen')

    seite0.springen({ nachricht: 'N-ALT' })
    await warte(20)
    await sprungAbwarten(s)

    assert.equal(exposed(s.exposed()).sucheStand().offen, false, 'der Sprung schließt die Suche')
    assert.equal(dom.window.location.hash, '#/nachrichten/CHAT-2', 'die Adresse ist die des Gesprächs')
    // Die Suchspalte ist NICHT mehr die sichtbare: der Verlauf steht da.
    const spalte = s.host.querySelector('.dk-chat-verlauf-spalte')
    assert.ok(spalte, 'die Verlaufsspalte steht im DOM')
    s.abbaum()
  } finally {
    globalThis.__HANDY = false
  }
})

test('CHAT-11b/B (R1/3): „Weitere Treffer“ — die Liste bleibt stehen, Fehler auf Seite 2 löscht Seite 1 nicht', async () => {
  const seite1 = seite([treffer({ nachricht: 'N-3' }), treffer({ nachricht: 'N-2' })], { mehr: true, vor: 'N-2' })
  let halte = null
  const s = await sucheMontieren({
    trefferSeiten: (p) => {
      if (p && p.vor) {
        if (halte) return new Promise((loese, ablehnen) => { halte = () => ablehnen(new Error('Netz weg')) })
        return seite([treffer({ nachricht: 'N-1' })], { mehr: false, vor: 'N-1' })
      }
      return seite1
    },
  })
  await suchTippen(s.host, 'samstag')
  await s.uhr.feuern()
  await rendern(4)
  assert.equal(s.host.querySelectorAll('.dk-treffer-zeile').length, 2)

  // Blättern anhalten: die Liste darf NICHT durch ein Skelett ersetzt werden.
  halte = true
  klick11b(s.host.querySelector('.dk-treffer-mehr'))
  await warte(6)
  await rendern(4)
  assert.equal(s.host.querySelectorAll('.dk-treffer-zeile').length, 2,
    'während des Blätterns stehen die gelesenen Zeilen weiter da')
  assert.equal(s.host.querySelector('.dk-skelett, [class*="skelett"]'), null, 'kein Skelett über der Liste')
  const knopf = s.host.querySelector('.dk-treffer-mehr')
  assert.ok(knopf, 'der Knopf bleibt da (Fokus bleibt, er zeigt das Laden)')
  halte()
  await warte(14)
  await rendern(4)

  assert.equal(s.host.querySelectorAll('.dk-treffer-zeile').length, 2,
    'ein Fehler auf Seite 2 löscht Seite 1 NICHT')
  assert.match(s.host.querySelector('.dk-treffer-fehler').textContent, /Netz weg/,
    'der Fehler steht ruhig darunter (der Satz des Servers)')
  s.abbaum()
})

test('CHAT-11b/B (R1/2): „Müller“ geht UNVERÄNDERT hinaus', async () => {
  const s = await sucheMontieren({ trefferSeiten: () => seite([]) })
  await suchTippen(s.host, 'Müller')
  await s.uhr.feuern()
  const anruf = s.aufrufe.find((a) => /nachrichten_suchen$/.test(a.methode))
  const { signal, ...parameter } = anruf.parameter
  assert.deepEqual(parameter, { q: 'Müller' }, 'kein „mueller“, kein „müller“ — der Server stammt selbst')
  s.abbaum()
})

test('CHAT-11b/B (R1/8): das Suchfeld bedient die Trefferliste wie eine Combobox', async () => {
  const zeilen = [treffer({ nachricht: 'N-3' }), treffer({ nachricht: 'N-2' })]
  const s = await sucheMontieren({ trefferSeiten: () => seite(zeilen) })
  await suchTippen(s.host, 'samstag')
  await s.uhr.feuern()
  await rendern(4)

  const feld = s.host.querySelector('input#chat-suche')
  assert.equal(feld.getAttribute('role'), 'combobox')
  assert.equal(feld.getAttribute('aria-controls'), 'dk-chat-treffer-liste',
    'das Feld zeigt auf DIESELBE Liste')
  assert.equal(feld.getAttribute('aria-activedescendant'), 'dk-chat-treffer-liste-treffer-0')

  feld.dispatchEvent(new dom.window.KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true, cancelable: true }))
  await warte(6)
  await rendern(2)
  assert.equal(feld.getAttribute('aria-activedescendant'), 'dk-chat-treffer-liste-treffer-1',
    '↓ bewegt die Auswahl im FELD')

  feld.dispatchEvent(new dom.window.KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true }))
  await warte(6)
  const gesprungen = s.gemeldet.filter((g) => g.art === 'springen')
  assert.equal(gesprungen.length, 1, 'Enter öffnet den gewählten Treffer')
  assert.equal(gesprungen[0].wert.nachricht, 'N-2')
  s.abbaum()
})

// ════════════════════════════════════════════════════════════════════════════
// F · CHAT-11b-2 — der Sprung in ein ANDERES Gespräch (positiv)
// ════════════════════════════════════════════════════════════════════════════

/** Ein Zeitstempel so-und-so viele Minuten vor dem festen Bezugspunkt. */
const vorMinuten = (n) => new Date(Date.UTC(2026, 10, 18, 12, 0, 0) - n * 60000).toISOString()

/**
 * Ein Verlauf um `von..bis` Minuten vor 12:00 — je Seite `SEITE_ANZAHL` volle
 * Zeilen (der Sprung läuft über `vor=<älteste Kennung>`).
 */
const SEITE_ANZAHL = 50
function seiteAb(bis) {
  return Array.from({ length: SEITE_ANZAHL }, (_, i) => verlaufsZeile(`S${bis - i}`, { am: vorMinuten(bis - i) }))
}

/** Der Sprung: Tippen/Klick nicht nötig — die Seite legt `springen` offen. */
async function springenUndWarten(s, nachricht, runden = 60) {
  exposed(s.exposed()).springen({ nachricht })
  await warte(20)
  await sprungAbwarten(s, runden)
}

/** Wie der Sprung geendet hat — für die Fehlermeldung. */
const sprungLage = (s) => JSON.stringify({
  stand: exposed(s.exposed()).sprungStand(),
  markiert: s.host.querySelector('.dk-chat-sprungziel')?.getAttribute('data-name') || null,
  hinweis: s.host.querySelector('.dk-chat-sprungweg')?.textContent?.trim() || null,
  zeilen: zeilenImVerlauf(s.host).slice(0, 3),
})

test('CHAT-11b-2 (A): Sprung aus der LISTE, Ziel auf der neuesten Seite → hervorgehoben, kein Hinweis', async () => {
  // Kein Gespräch offen: die Liste steht, erst der Sprung öffnet CHAT-2.
  const s = await seiteZwei({ hash: '#/nachrichten' })
  await springenUndWarten(s, 'NEU-CHAT-2')

  assert.equal(dom.window.location.hash, '#/nachrichten/CHAT-2', 'das Ziel ist geöffnet')
  assert.ok(zeilenImVerlauf(s.host).includes('NEU-CHAT-2'), 'der Verlauf des Ziels steht da')
  const markiert = s.host.querySelector('.dk-chat-sprungziel')
  assert.ok(markiert, 'die Zielnachricht ist hervorgehoben: ' + sprungLage(s))
  assert.equal(markiert.getAttribute('data-name'), 'NEU-CHAT-2')
  assert.equal(s.host.querySelector('.dk-chat-sprungweg'), null,
    'kein „Diese Nachricht gibt es nicht mehr.“ — ' + sprungLage(s))
  s.abbaum()
})

test('CHAT-11b-2 (B): Sprung, während ein ANDERES Gespräch offen ist → hervorgehoben, kein Hinweis', async () => {
  const s = await seiteZwei({ hash: '#/nachrichten/CHAT-5' })
  await warte(20)
  await springenUndWarten(s, 'NEU-CHAT-2')

  assert.equal(dom.window.location.hash, '#/nachrichten/CHAT-2', 'das ZIEL ist geöffnet')
  const markiert = s.host.querySelector('.dk-chat-sprungziel')
  assert.ok(markiert, 'die Zielnachricht ist hervorgehoben: ' + sprungLage(s))
  assert.equal(markiert.getAttribute('data-name'), 'NEU-CHAT-2')
  assert.equal(s.host.querySelector('.dk-chat-sprungweg'), null, 'kein Hinweis — ' + sprungLage(s))
  // Keine Seite des ALTEN Gesprächs wurde nachgeladen.
  const fremd = s.aufrufe.filter((a) => /verlauf$/.test(a.methode) && a.parameter?.vor
    && String(a.parameter.gespraech) !== 'CHAT-2')
  assert.deepEqual(fremd.map((a) => a.parameter.gespraech), [], 'nur im Zielgespräch nachgeladen')
  s.abbaum()
})

test('CHAT-11b-2 (C): Ziel auf einer ÄLTEREN Seite → genau so viele `vor`-Seiten wie nötig', async () => {
  // Seite 1 (neueste) = S50..S1; Seite 2 = S100..S51; Seite 3 = S150..S101 —
  // gesucht wird S101, also GENAU zwei Seiten zurück.
  const s = await seiteZwei({
    hash: '#/nachrichten',
    aelter: true,
    neueste: (g) => (g === 'CHAT-2' ? seiteAb(50) : [verlaufsZeile(`NEU-${g}`, { am: vorMinuten(900) })]),
    seiten: (g, anker) => {
      if (g !== 'CHAT-2') return []
      const n = Number(String(anker).replace(/\D/g, '')) || 0
      return seiteAb(Math.min(200, n + SEITE_ANZAHL))
    },
  })
  await springenUndWarten(s, 'S101', 80)

  const markiert = s.host.querySelector('.dk-chat-sprungziel')
  assert.ok(markiert, 'die Zielnachricht ist hervorgehoben: ' + sprungLage(s))
  assert.equal(markiert.getAttribute('data-name'), 'S101')
  assert.equal(s.host.querySelector('.dk-chat-sprungweg'), null, 'kein Hinweis — ' + sprungLage(s))
  const vorAbrufe = s.aufrufe.filter((a) => /verlauf$/.test(a.methode) && a.parameter?.vor)
  assert.equal(vorAbrufe.length, 2,
    'genau ZWEI ältere Seiten (S50→S1, dann S100→S51): '
    + JSON.stringify(vorAbrufe.map((a) => a.parameter.vor)) + ' | ' + sprungLage(s))
  assert.deepEqual(vorAbrufe.map((a) => a.parameter.vor), ['S50', 'S100'],
    'die Anker sind die jeweils ÄLTESTE bekannte Kennung')
  assert.ok(zeilenImVerlauf(s.host).includes('S101'), 'die Nachricht steht im Verlauf')
  s.abbaum()
})

test('CHAT-11b-2 (2): ein laufendes Nachladen verbraucht die Seitengrenze NICHT', async () => {
  // Das ZWEITE Nachladen hängt 30 Ticks — langsames Netz. Der Sprung darf
  // darauf warten (ohne zu zählen) und danach weiterkommen.
  let gezaehlt = 0
  let haengen = 0
  const s = await seiteZwei({
    hash: '#/nachrichten',
    aelter: true,
    neueste: (g) => (g === 'CHAT-2' ? seiteAb(50) : [verlaufsZeile(`NEU-${g}`, { am: vorMinuten(900) })]),
    seiten: (g, anker) => {
      if (g !== 'CHAT-2') return []
      const n = Number(String(anker).replace(/\D/g, '')) || 0
      return seiteAb(Math.min(300, n + SEITE_ANZAHL))
    },
    vorHalten: async (g, anker) => {
      if (g !== 'CHAT-2') return
      gezaehlt += 1
      if (gezaehlt !== 2) return
      haengen = 30
      // 30 Ticks „Netz“: die Antwort kommt erst nach 30 echten Tasks.
      for (let i = 0; i < 30; i += 1) { haengen -= 1; await new Promise((loese) => setTimeout(loese, 0)) }
    },
  })
  // S2 liegt hinter der hängenden Seite: Seite 2 = S100..S51, Seite 3 = S150..
  await springenUndWarten(s, 'S2', 200)

  assert.equal(haengen, 0, 'die Attrappe hat wirklich gehangen')
  const markiert = s.host.querySelector('.dk-chat-sprungziel')
  assert.ok(markiert, 'der Sprung gelingt nach dem Warten: ' + sprungLage(s))
  assert.equal(markiert.getAttribute('data-name'), 'S2')
  assert.equal(s.host.querySelector('.dk-chat-sprungweg'), null,
    'KEIN falscher Hinweis, obwohl das Netz 30 Ticks hing — ' + sprungLage(s))
  s.abbaum()
})

test('CHAT-11b-2 (3): der Sprung wartet auf die Adresse — mit eigener Decke, still', async () => {
  const s = await seiteZwei({ hash: '#/nachrichten/CHAT-5' })
  await warte(20)
  // Das Ziel steht fest (CHAT-2), aber der `hashchange` des Browsers kommt
  // nicht an: `offeneKennung` bleibt auf CHAT-5, die ECHTE Adresse bleibt
  // ebenfalls CHAT-5 (jsdom gibt `location` nicht zum Ersetzen heraus). Genau
  // dort steht `sprungBereit` — und muss nach `SPRUNG_ADRESSE_MS` ohne Hinweis
  // aufgeben, statt ewig zu warten.
  globalThis.__KONTEXT2G = () => ({ gespraech: 'CHAT-2', art: 'gruppe', titel: 'Chor' })
  const Seite0 = exposed(s.exposed())
  const start = Date.now()
  Seite0.springen({ nachricht: 'NEU-CHAT-2' })
  const warten = Seite0.sprungFertig()
  // Genug Zeit für die Decke (5 s) — aber begrenzt: der Sprung MUSS enden.
  for (let i = 0; i < 900; i += 1) {
    await warte(2)
    await rendern(1)
    if (Date.now() - start > 8000) break
  }
  const fertig = await Promise.race([warten.then(() => true),
    new Promise((loese) => setTimeout(() => loese(false), 3000))])
  await rendern(2)
  assert.equal(fertig, true, 'der Sprung endet nach der Decke, statt zu hängen')
  assert.ok(Date.now() - start < 12000, 'und zwar in der Frist')
  assert.equal(s.host.querySelector('.dk-chat-sprungweg'), null,
    'ein Abbruch über die Decke ist STILL — kein Hinweis: ' + sprungLage(s))
  s.abbaum()
})

test('CHAT-11b-2 (Glocke): der Weg der Erwähnungs-Glocke springt positiv zur Nachricht', async () => {
  // Die Glocke (AppTopbar) führt über `erwaehnungZiel` → `nachricht_kontext` ins
  // GESPRÄCH; den Sprung dorthin macht DIESELBE Seite (`springen`). Hier wird
  // der Zielpfad der Glocke nachgefahren: Kennung der NACHRICHT, Kontext → CHAT-2.
  const s = await seiteZwei({ hash: '#/nachrichten' })
  let gefragt = null
  globalThis.__KONTEXT2G = (nachricht) => {
    gefragt = nachricht
    return { gespraech: 'CHAT-2', art: 'gruppe', titel: 'Chor' }
  }
  await springenUndWarten(s, 'NEU-CHAT-2')

  assert.equal(gefragt, 'NEU-CHAT-2', 'die Glocke trägt die Kennung der NACHRICHT')
  assert.equal(dom.window.location.hash, '#/nachrichten/CHAT-2', 'der Kontext führt ins Gespräch')
  const markiert = s.host.querySelector('.dk-chat-sprungziel')
  assert.ok(markiert, 'die Nachricht ist hervorgehoben: ' + sprungLage(s))
  assert.equal(markiert.getAttribute('data-name'), 'NEU-CHAT-2')
  assert.equal(s.host.querySelector('.dk-chat-sprungweg'), null, 'kein Hinweis — ' + sprungLage(s))
  s.abbaum()
})

test('CHAT-11b-2 (Handy): gelungener Sprung aus anderem Gespräch → Suche zu, Verlauf da, Ziel hervorgehoben', async () => {
  globalThis.__HANDY = true
  try {
    const s = await seiteZwei({ hash: '#/nachrichten/suche?q=samstag&offen=CHAT-5' })
    await warte(20)
    assert.equal(exposed(s.exposed()).sucheStand().offen, true, 'die Suche ist offen')
    await springenUndWarten(s, 'NEU-CHAT-2')

    assert.equal(exposed(s.exposed()).sucheStand().offen, false, 'der Sprung schließt die Suche')
    assert.equal(dom.window.location.hash, '#/nachrichten/CHAT-2', 'die Adresse ist die des Gesprächs')
    assert.ok(s.host.querySelector('.dk-chat-verlauf-spalte'), 'die Verlaufsspalte steht da')
    const markiert = s.host.querySelector('.dk-chat-sprungziel')
    assert.ok(markiert, 'das Ziel ist hervorgehoben: ' + sprungLage(s))
    assert.equal(markiert.getAttribute('data-name'), 'NEU-CHAT-2')
    assert.equal(s.host.querySelector('.dk-chat-sprungweg'), null, 'kein Hinweis — ' + sprungLage(s))
    s.abbaum()
  } finally {
    globalThis.__HANDY = false
  }
})

test('CHAT-11b-2 (Abbruch): ein WECHSEL in ein DRITTES Gespräch bricht den Sprung still ab', async () => {
  const s = await seiteZwei({ hash: '#/nachrichten/CHAT-5', aelter: true })
  await warte(20)
  // Der Sprung will nach CHAT-2, die Seite ist aber schon wieder woanders.
  exposed(s.exposed()).springen({ nachricht: 'NEU-CHAT-2' })
  dom.window.location.hash = '#/nachrichten/CHAT-5'
  await warte(10)
  await sprungAbwarten(s, 40)
  const stand = exposed(s.exposed()).sprungStand()
  assert.equal(stand.nachricht, '', 'der Sprung ist abgebrochen (kein Ziel mehr)')
  assert.equal(s.host.querySelector('.dk-chat-sprungweg'), null, 'und das STILL — ohne Hinweis')
  s.abbaum()
})

// ════════════════════════════════════════════════════════════════════════════
// G · R1 (Review Opus, 21.11.) — Wechsel WÄHREND des Nachladens, fremder Lauf,
//     Nachladen durch Scrollen, Abbau
// ════════════════════════════════════════════════════════════════════════════

/** Eine Zusage, die von außen gelöst wird (hängende Netzantwort). */
function tor() {
  let loese = null
  let abgelehnt = null
  const offen = new Promise((l, a) => { loese = l; abgelehnt = a })
  offen.catch(() => {})
  return { offen, loese: (x) => loese(x), ablehnen: (e) => abgelehnt(e) }
}

test('CHAT-11b-2 (R1/1): Wechsel in ein DRITTES Gespräch WÄHREND des Nachladens → still, kein Hinweis', async () => {
  const haengt = tor()
  let ankerVor = []
  const s = await seiteZwei({
    hash: '#/nachrichten',
    aelter: true,
    neueste: (g) => (g === 'CHAT-2' ? seiteAb(50) : [verlaufsZeile(`NEU-${g}`, { am: vorMinuten(900) })]),
    seiten: (g, anker) => {
      if (g !== 'CHAT-2') return []
      const n = Number(String(anker).replace(/\D/g, '')) || 0
      return seiteAb(Math.min(200, n + SEITE_ANZAHL))
    },
    // Die ERSTE ältere Seite in CHAT-2 hängt, bis der Test das Tor öffnet.
    vorHalten: (g, anker) => {
      if (g !== 'CHAT-2' || ankerVor.length) return null
      ankerVor.push(anker)
      return haengt.offen
    },
  })
  await warte(20)

  exposed(s.exposed()).springen({ nachricht: 'S101' })
  await warte(20)
  // Der Sprung hat CHAT-2 geöffnet und wartet jetzt im ersten `vor` …
  for (let i = 0; i < 40 && !ankerVor.length; i += 1) { await warte(4); await rendern(2) }
  assert.ok(ankerVor.length, 'das erste Nachladen in CHAT-2 läuft')

  // … und die lesende Person wechselt in ein DRITTES Gespräch.
  dom.window.location.hash = '#/nachrichten/CHAT-5'
  await warte(20)
  await rendern(4)
  haengt.loese({})
  await sprungAbwarten(s, 60)

  const hinweise = [...s.host.querySelectorAll('.dk-chat-sprungweg')]
  assert.deepEqual(hinweise.map((h) => h.textContent.trim()), [],
    'KEIN „Diese Nachricht gibt es nicht mehr.“ im fremden Gespräch: ' + sprungLage(s))
  assert.equal(s.host.querySelector('.dk-chat-sprungziel'), null, 'und nichts hervorgehoben')
  assert.equal(exposed(s.exposed()).sprungStand().nachricht, '', 'der Sprung ist still beendet')
  const fremd = s.aufrufe.filter((a) => /verlauf$/.test(a.methode) && a.parameter?.vor
    && String(a.parameter.gespraech) !== 'CHAT-2')
  assert.deepEqual(fremd.map((a) => a.parameter.gespraech), [], 'keine Seite eines fremden Verlaufs')
  assert.equal(ankerVor.length, 1, 'nach dem Wechsel wurde in CHAT-2 NICHTS weiter nachgeladen')
  s.abbaum()
})

test('CHAT-11b-2 (R1/2): ein Nachladen des ALTEN Gesprächs blockiert den Sprung im neuen nicht', async () => {
  const haengt = tor()
  let fremdGehaengt = false
  const s = await seiteZwei({
    hash: '#/nachrichten/CHAT-5',
    aelter: true,
    neueste: (g) => (g === 'CHAT-2' ? seiteAb(50) : [verlaufsZeile(`NEU-${g}`, { am: vorMinuten(900) })]),
    seiten: (g, anker) => {
      if (g !== 'CHAT-2') return []
      const n = Number(String(anker).replace(/\D/g, '')) || 0
      return seiteAb(Math.min(200, n + SEITE_ANZAHL))
    },
    vorHalten: (g) => {
      if (g === 'CHAT-2') return null
      fremdGehaengt = true
      return haengt.offen
    },
  })
  await warte(20)
  // Nachladen durch SCROLLEN im offenen CHAT-5 — hängt.
  exposed(s.exposed()).aeltereLaden()
  await warte(10)
  assert.equal(fremdGehaengt, true, 'das Nachladen in CHAT-5 hängt')

  // Jetzt der Sprung nach CHAT-2, Ziel auf einer älteren Seite.
  exposed(s.exposed()).springen({ nachricht: 'S101' })
  await warte(20)
  await sprungAbwarten(s, 80)

  const markiert = s.host.querySelector('.dk-chat-sprungziel')
  assert.ok(markiert, 'der Sprung gelingt trotz des fremden Laufs: ' + sprungLage(s))
  assert.equal(markiert.getAttribute('data-name'), 'S101')
  assert.equal(s.host.querySelector('.dk-chat-sprungweg'), null, 'kein falscher Hinweis — ' + sprungLage(s))
  const vorAbrufe = s.aufrufe.filter((a) => /verlauf$/.test(a.methode) && a.parameter?.vor)
  const inZiel = vorAbrufe.filter((a) => String(a.parameter.gespraech) === 'CHAT-2')
  assert.equal(inZiel.length, 2, 'in CHAT-2 wurden die nötigen Seiten geholt: '
    + JSON.stringify(vorAbrufe.map((a) => [a.parameter.gespraech, a.parameter.vor])))
  assert.deepEqual(inZiel.map((a) => a.parameter.vor), ['S50', 'S100'])
  haengt.loese({})
  await warte(20)
  s.abbaum()
})

test('CHAT-11b-2 (R1/3): in einem frisch geöffneten Gespräch lädt SCROLLEN ältere Seiten', async () => {
  // Der Verlauf ist VOLL (50 Zeilen) — es gibt also ältere Seiten, auch wenn die
  // neueste Seite selbst nichts darüber sagt (`aelterStand`).
  const s = await seiteZwei({
    hash: '#/nachrichten/CHAT-2',
    aelter: true,
    neueste: (g) => (g === 'CHAT-2' ? seiteAb(50) : [verlaufsZeile(`NEU-${g}`, { am: vorMinuten(900) })]),
    seiten: (g, anker) => {
      if (g !== 'CHAT-2') return []
      const n = Number(String(anker).replace(/\D/g, '')) || 0
      return seiteAb(Math.min(200, n + SEITE_ANZAHL))
    },
  })
  await warte(20)
  assert.equal(zeilenImVerlauf(s.host).length, SEITE_ANZAHL, 'der volle Verlauf steht da')

  // Am Anfang des Verlaufs angekommen → ältere Seite holen.
  const kasten = s.host.querySelector('.dk-chat-verlauf .dk-chat-nachrichten')
  assert.ok(kasten, 'der Verlauf hat seinen eigenen Scrollkasten')
  kasten.scrollTop = 0
  kasten.dispatchEvent(new dom.window.Event('scroll', { bubbles: false }))
  for (let i = 0; i < 30; i += 1) { await warte(4); await rendern(2) }

  const vorAbrufe = s.aufrufe.filter((a) => /verlauf$/.test(a.methode) && a.parameter?.vor)
  assert.deepEqual(vorAbrufe.map((a) => a.parameter.vor), ['S50'],
    'Scrollen nach oben lädt `vor` — OHNE dass erst ein Sprung nötig wäre')
  assert.ok(zeilenImVerlauf(s.host).includes('S100'), 'die älteren Zeilen stehen jetzt im Verlauf')
  s.abbaum()
})

test('CHAT-11b-2 (R1/5): Abbau mitten im Nachladen → der Sprung endet still, nichts schreibt mehr', async () => {
  const haengt = tor()
  let ankerVor = []
  const s = await seiteZwei({
    hash: '#/nachrichten',
    aelter: true,
    neueste: (g) => (g === 'CHAT-2' ? seiteAb(50) : [verlaufsZeile(`NEU-${g}`, { am: vorMinuten(900) })]),
    seiten: (g, anker) => {
      if (g !== 'CHAT-2') return []
      const n = Number(String(anker).replace(/\D/g, '')) || 0
      return seiteAb(Math.min(200, n + SEITE_ANZAHL))
    },
    vorHalten: (g, anker) => {
      if (g !== 'CHAT-2' || ankerVor.length) return null
      ankerVor.push(anker)
      return haengt.offen
    },
  })
  await warte(20)
  exposed(s.exposed()).springen({ nachricht: 'S101' })
  const fertig = exposed(s.exposed()).sprungFertig()
  for (let i = 0; i < 40 && !ankerVor.length; i += 1) { await warte(4); await rendern(2) }
  assert.ok(ankerVor.length, 'das Nachladen läuft')

  // Die Seite wird abgebaut, WÄHREND die Antwort noch aussteht.
  s.abbaum()
  haengt.loese({})
  const ende = await Promise.race([fertig.then(() => true),
    new Promise((loese) => setTimeout(() => loese(false), 3000))])
  assert.equal(ende, true, 'der Wartende wird beim Abbau aufgelöst (kein hängendes Promise)')
  await warte(20)
  s.abbaum()
})

// ════════════════════════════════════════════════════════════════════════════
// H · CHAT-11b-3 — Klick auf einen Suchtreffer IM Gespräch springt wieder,
//     und ein neuer Sprung wird nach einem stillen Abbruch nicht verschluckt
// ════════════════════════════════════════════════════════════════════════════

/** Die Gesprächssuche öffnen und `samstag` tippen (echte Entprellzeit). */
async function gespraechSucheFuellen(s) {
  const knopf = [...s.host.querySelectorAll('button')]
    .find((b) => b.getAttribute('aria-label') === 'Im Gespräch suchen')
  assert.ok(knopf, 'der Such-Knopf steht im Gesprächskopf')
  if (s.host.querySelector('#chat-gespraech-suche') === null) {
    klick11b(knopf)
    await warte(8)
    await rendern(4)
  }
  const feld = s.host.querySelector('#chat-gespraech-suche')
  assert.ok(feld, 'das Suchfeld der Gesprächssuche steht da')
  feld.value = 'samstag'
  feld.dispatchEvent(new dom.window.Event('input', { bubbles: true }))
  await warte(20)
  await new Promise((loese) => setTimeout(loese, 420))
  await warte(20)
  await rendern(4)
  const zeilen = [...s.host.querySelectorAll('#dk-gespraech-treffer li')]
  assert.ok(zeilen.length, 'die Trefferliste steht da')
  return { feld, zeilen }
}

/**
 * CHAT-11b-3/1 (HOCH): Ein KLICK auf einen Treffer der Gesprächssuche hebt die
 * Zielnachricht hervor — auch wenn sie auf einer ÄLTEREN Seite liegt. Der
 * Aufruf `sprungAusfuehren()` ohne Laufnummer machte `sprungGilt(undefined)`
 * immer falsch: nichts wurde geladen, nichts hervorgehoben, und das Ziel blieb
 * verwaist stehen.
 */
test('CHAT-11b-3/1: KLICK auf einen Treffer der Gesprächssuche springt zur Nachricht (ältere Seite)', async () => {
  const s = await seiteZwei({
    hash: '#/nachrichten/CHAT-2',
    aelter: true,
    neueste: (g) => (g === 'CHAT-2'
      ? [verlaufsZeile('N-4', { am: vorMinuten(1) })]
      : [verlaufsZeile(`NEU-${g}`, { am: vorMinuten(900) })]),
    seiten: (g, anker) => {
      if (g !== 'CHAT-2') return []
      const n = Number(String(anker).replace(/\D/g, '')) || 0
      return seiteAb(Math.min(200, n + SEITE_ANZAHL))
    },
  })
  globalThis.__SUCHE2G = () => seite([treffer({ nachricht: 'S101' })])
  await warte(20)

  const { zeilen } = await gespraechSucheFuellen(s)
  klick11b(zeilen[0])
  const warten = exposed(s.exposed()).sprungFertig()
  for (let i = 0; i < 60; i += 1) { await warte(4); await rendern(2) }
  await warten
  await rendern(4)

  assert.ok(zeilenImVerlauf(s.host).includes('S101'),
    'die Nachricht der älteren Seite steht im Verlauf: ' + JSON.stringify(zeilenImVerlauf(s.host).slice(0, 3)))
  const markiert = s.host.querySelector('.dk-chat-sprungziel')
  assert.ok(markiert, 'die Zielnachricht ist hervorgehoben: ' + sprungLage(s))
  assert.equal(markiert.getAttribute('data-name'), 'S101')
  assert.equal(s.host.querySelector('.dk-chat-sprungweg'), null, 'kein Hinweis — ' + sprungLage(s))
  assert.equal(exposed(s.exposed()).sprungStand().nachricht, '',
    'das Ziel ist eingelöst und NICHT verwaist stehen geblieben')
  const vorAbrufe = s.aufrufe.filter((a) => /verlauf$/.test(a.methode) && a.parameter?.vor
    && String(a.parameter.gespraech) === 'CHAT-2')
  assert.ok(vorAbrufe.length >= 2, 'ältere Seiten wurden geholt: '
    + JSON.stringify(vorAbrufe.map((a) => a.parameter.vor)))
  s.abbaum()
})

/**
 * CHAT-11b-3/1 (PFLICHT-Teil 2): dasselbe über ENTER — die Tastatur der
 * Trefferliste nimmt denselben Weg (`gespraechTrefferTaste` → `waehlen`).
 */
test('CHAT-11b-3/1: ENTER auf einem Treffer der Gesprächssuche springt zur Nachricht', async () => {
  const s = await seiteZwei({
    hash: '#/nachrichten/CHAT-2',
    aelter: true,
    neueste: (g) => (g === 'CHAT-2'
      ? [verlaufsZeile('N-4', { am: vorMinuten(1) })]
      : [verlaufsZeile(`NEU-${g}`, { am: vorMinuten(900) })]),
    seiten: (g, anker) => {
      if (g !== 'CHAT-2') return []
      const n = Number(String(anker).replace(/\D/g, '')) || 0
      return seiteAb(Math.min(200, n + SEITE_ANZAHL))
    },
  })
  globalThis.__SUCHE2G = () => seite([treffer({ nachricht: 'S101' })])
  await warte(20)

  const { feld } = await gespraechSucheFuellen(s)
  feld.dispatchEvent(new dom.window.KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true }))
  const warten = exposed(s.exposed()).sprungFertig()
  for (let i = 0; i < 60; i += 1) { await warte(4); await rendern(2) }
  await warten
  await rendern(4)

  const markiert = s.host.querySelector('.dk-chat-sprungziel')
  assert.ok(markiert, 'ENTER hebt die Zielnachricht hervor: ' + sprungLage(s))
  assert.equal(markiert.getAttribute('data-name'), 'S101')
  assert.equal(s.host.querySelector('.dk-chat-sprungweg'), null, 'kein Hinweis — ' + sprungLage(s))
  s.abbaum()
})

/**
 * CHAT-11b-3/2 (MITTEL): Nach einem STILLEN Abbruch (Wechsel in ein drittes
 * Gespräch, während die `vor`-Antwort noch hängt) ist ein neuer Sprung nicht
 * mehr verschluckt. Vorher blieb die Sperre (`sprungLaeuft`) true, bis die
 * hängende Antwort kam — ein neuer Sprung tat in dieser Zeit nichts.
 */
test('CHAT-11b-3/2: neuer Sprung nach stillem Abbruch startet sofort, die späte Antwort ändert nichts', async () => {
  const haengt = tor()
  const ankerVor = []
  const kontexte = []
  const s = await seiteZwei({
    hash: '#/nachrichten',
    aelter: true,
    neueste: (g) => (g === 'CHAT-2'
      ? [verlaufsZeile('S1', { am: vorMinuten(1) })]
      : [verlaufsZeile(`NEU-${g}`, { am: vorMinuten(900) })]),
    seiten: (g, anker) => {
      if (g !== 'CHAT-2') return []
      const n = Number(String(anker).replace(/\D/g, '')) || 0
      return seiteAb(Math.min(200, n + SEITE_ANZAHL))
    },
    // Die ERSTE ältere Seite in CHAT-2 hängt, bis der Test das Tor öffnet.
    vorHalten: (g, anker) => {
      if (g !== 'CHAT-2' || ankerVor.length) return null
      ankerVor.push(anker)
      return haengt.offen
    },
  })
  await warte(20)
  globalThis.__KONTEXT2G = (nachricht) => {
    kontexte.push(nachricht)
    return { gespraech: 'CHAT-2', art: 'gruppe', titel: 'Chor' }
  }

  // 1. Sprung: Ziel S2 liegt hinter der hängenden Seite.
  exposed(s.exposed()).springen({ nachricht: 'S2' })
  for (let i = 0; i < 40 && !ankerVor.length; i += 1) { await warte(4); await rendern(2) }
  assert.ok(ankerVor.length, 'der erste Sprung hängt im `vor`-Abruf')
  assert.equal(kontexte.length, 1, 'die Kontext-Abfrage des ersten Sprungs ist durch')

  // 2. Die lesende Person wechselt in ein DRITTES Gespräch — der Sprung endet
  //    STILL, seine Antwort steht aber noch aus.
  dom.window.location.hash = '#/nachrichten/CHAT-5'
  await warte(20)
  await rendern(4)
  assert.equal(exposed(s.exposed()).sprungStand().nachricht, '', 'der erste Sprung ist still beendet')

  // 3. Neuer Sprung zurück nach CHAT-2 — er darf NICHT verschluckt werden.
  exposed(s.exposed()).springen({ nachricht: 'S1' })
  // Begrenzt warten: verschluckt der alte Stand den zweiten Sprung, löst
  // `sprungFertig` nie auf — die Prüfung soll dann ROT melden, nicht hängen.
  await Promise.race([
    exposed(s.exposed()).sprungFertig(),
    new Promise((loese) => setTimeout(loese, 2000)),
  ])
  for (let i = 0; i < 80; i += 1) { await warte(4); await rendern(2) }
  await rendern(4)

  assert.equal(kontexte.length, 2,
    'der zweite Sprung hat `nachricht_kontext` ERNEUT abgerufen (nicht verschluckt): '
    + JSON.stringify(kontexte))
  const markiert = s.host.querySelector('.dk-chat-sprungziel')
  assert.ok(markiert, 'der zweite Sprung gelingt trotz hängender Antwort des ersten: ' + sprungLage(s))
  assert.equal(markiert.getAttribute('data-name'), 'S1')

  // 4. Jetzt kommt die späte Antwort des ERSTEN Laufs — sie ändert nichts.
  haengt.loese({})
  for (let i = 0; i < 30; i += 1) { await warte(4); await rendern(2) }
  await rendern(4)
  assert.equal(s.host.querySelector('.dk-chat-sprungziel')?.getAttribute('data-name'), 'S1',
    'die späte Antwort des ersten Laufs ändert die Hervorhebung nicht: ' + sprungLage(s))
  assert.equal(s.host.querySelector('.dk-chat-sprungweg'), null,
    'und sie schreibt keinen Hinweis: ' + sprungLage(s))
  assert.equal(exposed(s.exposed()).sprungStand().nachricht, '', 'kein verwaistes Ziel')
  s.abbaum()
})
