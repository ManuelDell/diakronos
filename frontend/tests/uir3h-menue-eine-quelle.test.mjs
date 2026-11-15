/**
 * UI-R3h (MUSS 1, MUSS 2, SOLL 3, MUSS 6) — Kalendermenü: EINE Quelle für
 * „Kalender verwalten“, eine überholte Ladung ändert nichts, tote Reste weg.
 *
 * Gemessen wird am ECHTEN Bauteil und an der ECHTEN Seite (jsdom, Server-
 * Attrappe), nicht am Quelltext-Regulärausdruck — außer dort, wo ausdrücklich
 * „kein zweiter Weg“ belegt werden soll.
 *
 *   R1  Die Leiste hört NUR auf die Prop, sobald sie gesetzt ist: `false` von
 *       der Seite heißt „kein Eintrag“, auch wenn der geteilte Stand `true`
 *       sagt. Ohne Prop (Leiste allein gemountet) gilt der geteilte Stand.
 *   R2  Zwei schnelle Änderungen auf der Verwaltungsseite: das Promise der
 *       überholten Ladung bleibt OFFEN, bis die JÜNGSTE Antwort da ist (und die
 *       alte Zeile weg ist) — UI-R3i: am Verhalten gemessen, nicht an `typeof`.
 *   R3  Ein Recht, das nach einem 403 im vorigen Besuch neu vergeben wird,
 *       steht erst mit der Antwort DIESES Besuchs im Bild. Bei UI-R3i ist der
 *       Fall nach `tests/uir3h-restpunkte.test.mjs` (S5, an der echten
 *       Kalenderseite) gewandert.
 *   S3  Tote Reste: `useKalenderVerwaltungSicht`, `laufende`, `saet`.
 *
 * Lauf (cwd = frontend/, EINE Datei pro Aufruf):
 *   TMPDIR=$(mktemp -d) NODE_OPTIONS=--max-old-space-size=2048 \
 *     TZ=Europe/Berlin node --test --test-timeout=60000 tests/uir3h-menue-eine-quelle.test.mjs
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, mkdtempSync, writeFileSync, rmSync, mkdirSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve, dirname, basename } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { JSDOM } from 'jsdom'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'

const TESTS_DIR = dirname(fileURLToPath(import.meta.url))
const SRC_DIR = resolve(TESTS_DIR, '..', 'src')
const lies = (rel) => readFileSync(resolve(SRC_DIR, 'diakonos', rel), 'utf8')

// ── jsdom zuerst, dann Vue ────────────────────────────────────────────────
const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
for (const schluessel of ['window', 'document', 'Node', 'Element', 'HTMLElement', 'Event',
  'MouseEvent', 'SVGElement', 'CSS', 'CustomEvent', 'HTMLInputElement',
  'HTMLSelectElement', 'HTMLTextAreaElement', 'requestAnimationFrame',
  'getComputedStyle', 'MutationObserver', 'KeyboardEvent', 'FocusEvent',
  'Document', 'ShadowRoot', 'HTMLButtonElement', 'sessionStorage', 'localStorage',
  'Location', 'History', 'PopStateEvent', 'HashChangeEvent', 'Navigator', 'NodeList']) {
  if (dom.window[schluessel] !== undefined) globalThis[schluessel] = dom.window[schluessel]
}
globalThis.requestAnimationFrame = (cb) => setTimeout(() => cb(Date.now()), 0)
globalThis.cancelAnimationFrame = (id) => clearTimeout(id)
Object.defineProperty(globalThis.window, 'innerWidth', { value: 1440, configurable: true })
Object.defineProperty(globalThis.window, 'matchMedia', {
  configurable: true,
  value: () => ({ matches: false, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {} }),
})

// ── Server-Attrappe ───────────────────────────────────────────────────────
const aufrufe = []
/** Überschreibungen: Muster (RegExp-Quelle) → Antwort | Fehler | Funktion. */
let ueberschreibungen = {}
let baum = { gruppen: [] }

globalThis.__uiR3hMock = async (methode, args) => {
  aufrufe.push([methode, args])
  for (const [muster, antwort] of Object.entries(ueberschreibungen)) {
    if (!new RegExp(muster).test(methode)) continue
    const wert = typeof antwort === 'function' ? await antwort() : await antwort
    if (wert instanceof Error) throw wert
    return JSON.parse(JSON.stringify(wert))
  }
  if (/get_gruppen_hierarchie$/.test(methode)) return JSON.parse(JSON.stringify(baum))
  if (/get_kalender_verwaltung$/.test(methode)) return leerVerwaltung()
  if (/get_objekt_rechte$/.test(methode)) return { freigaben: [] }
  if (/get_current_user_context$/.test(methode)) return { roles: [], user: '' }
  if (/get_accessible_calendars$/.test(methode)) return []
  if (/get_moderation_count$/.test(methode)) return { count: 0 }
  return { success: true }
}

globalThis.fetch = async (url, optionen = {}) => {
  const methode = String(url || '').replace(/^.*\/api\/method\//, '')
  let args = {}
  try { args = JSON.parse(optionen.body || '{}') } catch { args = {} }
  aufrufe.push([methode, args])
  let wert
  try {
    wert = await globalThis.__uiR3hMock(methode, args)
  } catch (err) {
    return {
      ok: false,
      status: Number(err?.status) || 500,
      headers: { get: () => 'application/json' },
      json: async () => ({ exc: String(err?.message || 'Fehler') }),
      text: async () => JSON.stringify({ exc: String(err?.message || 'Fehler') }),
    }
  }
  return {
    ok: true,
    status: 200,
    headers: { get: () => 'application/json' },
    json: async () => ({ message: wert }),
    text: async () => JSON.stringify({ message: wert }),
  }
}

const mit = (muster) => aufrufe.filter(([m]) => new RegExp(muster).test(m))

// ── SFC-Übersetzer ────────────────────────────────────────────────────────
const Vue = await import('vue')
const TMP = mkdtempSync(join(tmpdir(), 'uir3h-'))
const cache = new Map()
const VUE_URL = import.meta.resolve('vue')

mkdirSync(join(TMP, 'shim'), { recursive: true })
const SHIM = join(TMP, 'shim', 'useApi.mock.mjs')
writeFileSync(SHIM,
  `export * from ${JSON.stringify(new URL('../src/diakonos/composables/useApi.js', import.meta.url).href)}\n`
  + 'export const apiCall = (methode, args) => globalThis.__uiR3hMock(methode, args)\n'
  + 'export default { apiCall }\n')

const ERSATZ = new Map([
  ['@event-calendar/build',
    'export const create = () => ({ setOption(){}, render(){}, destroy(){}, addEvent(){}, '
    + 'removeEventById(){}, updateSize(){}, next(){}, prev(){}, today(){}, gotoDate(){}, '
    + 'changeView(){}, getEvents(){ return [] }, setEvents(){}, getOption(){ return undefined }, '
    + 'on(){}, off(){}, unselect(){} })\n'
    + 'export default { create: () => ({}), setOption(){}, render(){}, destroy(){} }\n'],
  ['@event-calendar/build/dist/event-calendar.min.css', ''],
])

function fremdesModul(spec) {
  if (!ERSATZ.has(spec)) return null
  const datei = resolve(TMP, 'ersatz-' + spec.replace(/[^a-z0-9]+/gi, '-') + '.mjs')
  if (!cache.has(datei)) {
    writeFileSync(datei, ERSATZ.get(spec) + '\n')
    cache.set(datei, datei)
  }
  return datei
}

function uebersetze(abs) {
  if (cache.has(abs)) return cache.get(abs)
  const filename = basename(abs)
  const { descriptor, errors } = parse(readFileSync(abs, 'utf8'), { filename })
  assert.deepEqual(errors, [], filename + ': SFC-Struktur')
  const script = compileScript(descriptor, { id: filename })
  const tpl = compileTemplate({
    source: descriptor.template.content,
    filename,
    id: filename,
    compilerOptions: { bindingMetadata: script.bindings },
  })
  assert.deepEqual(tpl.errors.map(String), [], filename + ': Vorlage')
  let code = script.content.replace(/\nexport default /, '\nconst __sfc__ = ')
  code += '\n' + tpl.code.replace(/^export function render/m, 'function render')
  code += '\n__sfc__.render = render\nexport default __sfc__\n'
  code = code.replace(/from\s+['"]([^'"]+)['"]/g, (voll, spec) => {
    if (/^vue/.test(spec)) return `from '${VUE_URL}'`
    if (/useApi(\.js)?$/.test(spec)) return `from '${pathToFileURL(SHIM).href}'`
    if (!spec.startsWith('.')) {
      const ersatz = fremdesModul(spec)
      return ersatz ? `from '${pathToFileURL(ersatz).href}'` : voll
    }
    const ziel = resolve(dirname(abs), spec)
    const datei = /\.vue$/.test(spec) ? uebersetze(ziel) : ziel
    return `from '${pathToFileURL(datei).href}'`
  })
  code = code.replace(/^import\s+['"]([^'"]+)['"];?$/gm, (ganz, spec) => {
    const ersatz = fremdesModul(spec)
    return ersatz ? `import '${pathToFileURL(ersatz).href}';` : ganz
  })
  const ziel = resolve(TMP, filename.replace(/\.vue$/, '') + '.' + cache.size + '.mjs')
  writeFileSync(ziel, code)
  cache.set(abs, ziel)
  return ziel
}

async function baustein(rel) {
  const pfad = uebersetze(resolve(SRC_DIR, 'diakonos', rel))
  return (await import('file://' + pfad)).default
}

/** Der geteilte Ladestand — sein Aufruf geht über DIESELBE Attrappe. */
async function stand() {
  const modul = await import('../src/diakonos/composables/useKalenderVerwaltung.js')
  modul.__setzeApiAufruf((methode, args) => globalThis.__uiR3hMock(methode, args))
  return modul
}

test.after(() => rmSync(TMP, { recursive: true, force: true }))
test.afterEach(async () => {
  const { bestaetigungAntwort } = await import('../src/diakonos/composables/useBestaetigen.js')
  for (let i = 0; i < 8; i += 1) {
    bestaetigungAntwort(false)
    await new Promise((l) => setTimeout(l, 0))
  }
  for (const el of [...document.body.children]) el.remove()
  ueberschreibungen = {}
  baum = { gruppen: [] }
  aufrufe.length = 0
})

const warte = async (n = 24) => { for (let i = 0; i < n; i += 1) await new Promise((l) => setTimeout(l, 0)) }

/** Eine zurückgehaltene Antwort: `oeffnen(wert)` löst sie auf. */
function schleuse() {
  let oeffnen
  const versprechen = new Promise((ja) => { oeffnen = ja })
  return { versprechen, oeffnen }
}

/**
 * Ist ein Promise noch offen? (`false` heißt: aufgelöst oder abgelehnt.) Der
 * Zeitgeber hält die Ereignisschleife am Leben — ohne ihn beendet
 * `node --test` den Lauf, bevor der Zustand gelesen ist.
 */
function offen(p, ms = 20) {
  const lage = { offen: true }
  Promise.resolve(p).then(() => { lage.offen = false }, () => { lage.offen = false })
  return new Promise((ja) => setTimeout(() => ja(lage.offen), ms))
}

const leerVerwaltung = () => ({
  kalender: [], anlegen_gruppen: [], anlegen_untergruppen: [], darf_gemeinde_kalender: false,
})

/** Ein Kalender, wie `get_kalender_verwaltung` ihn liefert. */
function kalender(extra = {}) {
  return {
    name: 'Proben',
    titel: 'Proben',
    farbe: '#3366cc',
    gruppe: 'G-Chor',
    untergruppe: null,
    selbstverwaltet: false,
    calender_details: '',
    standard_gruppe_lesen: true,
    gemeinde_status: 'aus',
    gruppe_status: 'aus',
    ...extra,
  }
}

/** Antwort, die „Verwalten“ sichtbar macht (`kalenderVerwaltungSichtbar`). */
function mitRecht(name = 'Proben', extra = {}) {
  return {
    kalender: [kalender({ name, titel: name, ...extra })],
    anlegen_gruppen: ['G-Chor'], anlegen_untergruppen: [], darf_gemeinde_kalender: false,
  }
}

async function programm(vorlage, { daten = {}, teile = {}, host = null } = {}) {
  const ziel = host || document.createElement('div')
  if (!host) document.body.appendChild(ziel)
  const meldungen = []
  const app = Vue.createApp({
    components: teile,
    data: () => ({ daten }),
    template: vorlage,
  })
  app.config.warnHandler = (m) => meldungen.push('warn: ' + String(m))
  app.config.errorHandler = (e) => meldungen.push('err: ' + String(e && e.message))
  app.mount(ziel)
  await warte(24)
  return { host: ziel, app, meldungen }
}

/** „Kalender verwalten“ als gerenderter Knopf (oder undefined). */
const verwaltenKnopf = (host) => [...host.querySelectorAll('button, a')]
  .find((el) => /^\s*Kalender verwalten\s*$/.test(el.textContent || ''))

// ══════════════════════════════════════════════════════════════════════════
// R1 · Die Prop ist die EINE Quelle, sobald sie gesetzt ist (MUSS 1)
// ══════════════════════════════════════════════════════════════════════════

test('UI-R3h/R1: die Leiste hört auf die Prop — `false` von der Seite heißt „kein Eintrag“, auch wenn der geteilte Stand `true` sagt', async () => {
  // BEFUND (UI-R3g-Stand): `props.darfVerwalten === true || gehoertZu(besuch)`
  // — zwei Quellen. Sagte die Seite (Besitzer des Endpunkts) ausdrücklich
  // `false`, während der geteilte Stand noch eine Antwort mit Recht trug,
  // stand „Kalender verwalten“ trotzdem im Bild.
  const geteilt = await stand()
  geteilt.__leeren()
  // Vorbedingung: der geteilte Stand trägt das Recht aus dem Satz, zu dem
  // auch die Leiste gehört (der Besuch ist derselbe — so wie nach einem
  // Seitenwechsel ohne neue Anfrage).
  geteilt.__setzeApiAufruf(async () => mitRecht('Proben 2'))
  const satz = geteilt.aktuellerSatz()
  await geteilt.laden()
  assert.equal(geteilt.gehoertZu(satz), true,
    'Vorbedingung: der geteilte Stand gilt für diesen Besuch (sonst misst der Fall nichts)')
  geteilt.__setzeApiAufruf((methode, args) => globalThis.__uiR3hMock(methode, args))

  const Leiste = await baustein('components/kronos/KronosSidebar.vue')

  // (a) OHNE Prop (Leiste allein gemountet): der geteilte Stand zählt.
  const allein = await programm('<Leiste :open="false" />', { teile: { Leiste } })
  assert.ok(verwaltenKnopf(allein.host),
    'ohne Prop fehlt „Kalender verwalten“ (der geteilte Stand ist die Quelle): '
      + (allein.host.textContent || '').replace(/\s+/g, ' ').slice(0, 200))
  allein.app.unmount()
  allein.host.remove()

  // (b) Die Seite gibt ausdrücklich `false` — der geteilte Stand sagt `true`.
  const nein = await programm('<Leiste :open="false" :darf-verwalten="false" />', { teile: { Leiste } })
  assert.equal(verwaltenKnopf(nein.host), undefined,
    'die Prop `false` wird von der zweiten Quelle (geteilter Stand) überstimmt: „Kalender verwalten“ steht im Bild: '
      + (nein.host.textContent || '').replace(/\s+/g, ' ').slice(0, 200))
  nein.app.unmount()
  nein.host.remove()

  // (c) Und `true` von der Seite steht auch dann, wenn der geteilte Stand
  //     (für diesen Besuch) nichts hergibt — die Prop ist die Auskunft.
  const ja = await programm('<Leiste :open="false" :darf-verwalten="true" />', { teile: { Leiste } })
  assert.ok(verwaltenKnopf(ja.host), 'die Prop `true` erzeugt keinen Eintrag')
  ja.app.unmount()
  ja.host.remove()
})

// ══════════════════════════════════════════════════════════════════════════
// R2 · Eine überholte Ladung ändert nichts auf der Verwaltungsseite (MUSS 2)
// ══════════════════════════════════════════════════════════════════════════

/** Die Rückgängig-Meldungen im Dokument (unten links). */
const rueckgaengigMeldungen = () => [...document.querySelectorAll('.diakonos-toast--undo')]
  .filter((t) => /Rückgängig/.test(t.textContent || ''))

test('UI-R3h/R2: zwei überlappende Nachladungen — das Promise der älteren löst erst mit der JÜNGSTEN Antwort auf, und die Fläche behält bis dahin die alte Liste', async () => {
  // BEFUND (UI-R3g-Stand): `laden()` wies nur den geteilten STAND ab; für die
  // ÄLTERE Antwort lief der Rest weiter und setzte `laedt`/`antwortDaEigene`.
  // Die Fläche galt damit als fertig geladen, obwohl die jüngste Liste noch
  // unterwegs war — die gelöschte Zeile stand dabei noch im Bild.
  //
  // UI-R3i (MUSS 2): Der Fall ist ein VERHALTENSTEST. Gemessen wird am Promise
  // von `nachladen()` und am gerenderten Bild — nicht an `typeof`-Prüfungen
  // oder am Quelltext. Er war am UI-R3h-Stand (7ccfdd0d) rot: dort löste das
  // Promise der überholten Ladung mit der alten Antwort auf.
  //
  // Gemessen wird das an der echten Seite mit GESTEUERTER Reihenfolge: die
  // beiden Nachladungen werden über `nachladen()` der Seite gestartet (nicht
  // über Klicks, die ihre Reihenfolge nicht festlegen); die Antworten kommen
  // in der Reihenfolge „ältere zuerst, jüngste danach“.
  const geteilt = await stand()
  geteilt.__leeren()

  let gezaehlt = 0
  const spaet = []
  ueberschreibungen = {
    'get_kalender_verwaltung$': () => {
      gezaehlt += 1
      if (gezaehlt === 1) return mitRecht('Chor', { titel: 'Chorproben' })
      const tor = schleuse()
      spaet.push(tor.oeffnen)
      return tor.versprechen
    },
  }

  const Seite = await baustein('pages/KalenderVerwaltung.vue')
  const { host, app, meldungen } = await programm('<Seite />', { teile: { Seite } })
  await warte(40)
  assert.deepEqual(meldungen.filter((m) => /^err/.test(m)), [], 'Fehler: ' + meldungen.join(' | '))
  assert.ok(host.querySelector('[data-kalender="Chor"]'), 'Vorbedingung: die Zeile „Chorproben“ fehlt')

  /**
   * Der Stand der Seite — `setupState` ist ein Ref-PROXY, dort liest sich ein
   * `ref` schon ungewrappt (`laedt` = `true`/`false`, nicht `{ value }`).
   */
  const instanz = () => {
    const lauf = (vnode, treffer = []) => {
      if (!vnode) return treffer
      if (typeof vnode.type === 'object' && vnode.type?.__name === 'KalenderVerwaltung' && vnode.component) treffer.push(vnode.component)
      if (vnode.component) lauf(vnode.component.subTree, treffer)
      if (Array.isArray(vnode.children)) for (const k of vnode.children) lauf(k, treffer)
      return treffer
    }
    return lauf(host._vnode.component.subTree)[0]?.setupState || null
  }
  const seite = instanz()
  assert.ok(seite && typeof seite.nachladen === 'function', 'Vorbedingung: `nachladen` der Seite fehlt')

  // Änderung A (älter) und Änderung B (jünger) — beide hängen am Server.
  const a = seite.nachladen().catch(() => undefined)
  await warte(4)
  const b = seite.nachladen().catch(() => undefined)
  await warte(4)
  assert.equal(spaet.length, 2, `beide Nachladungen müssen gefragt haben (${spaet.length})`)

  // Die ÄLTERE Antwort (A) kommt an, die jüngste fehlt noch.
  spaet[0]({ kalender: [kalender({ name: 'Alt' })], anlegen_gruppen: [], anlegen_untergruppen: [], darf_gemeinde_kalender: false })
  await warte(20)
  assert.equal(host.querySelector('[data-kalender="Alt"]'), null,
    'die ÜBERHOLTE Antwort hat ihre Zeile doch ins Bild geschrieben')
  assert.ok(host.querySelector('[data-kalender="Chor"]'),
    'die ÜBERHOLTE Antwort hat die Fläche aus dem Wartezustand genommen: die alte Zeile '
      + '„Chorproben“ ist schon weg, obwohl die jüngste Antwort noch fehlt: '
      + (host.textContent || '').replace(/\s+/g, ' ').slice(0, 200))
  assert.equal(host.querySelectorAll('[data-kalender]').length, 1,
    'die Fläche zeigt nach der ÜBERHOLTEN Antwort nicht mehr genau die alte Liste: '
      + [...host.querySelectorAll('[data-kalender]')].map((e) => e.getAttribute('data-kalender')).join(','))

  // DIE Zusage dieser Karte, AM VERHALTEN gemessen: Solange die jüngste Ladung
  // unterwegs ist, ist das Promise der überholten Ladung OFFEN — die Fläche
  // wartet also (kein Toast, kein „Rückgängig“, `busy` bleibt gesetzt).
  assert.equal(await offen(a, 20), true,
    'das Promise der überholten Nachladung hat mit der ALTEN Antwort aufgelöst — die Fläche meldet '
      + 'Toast/„Rückgängig“, während die jüngste Liste noch unterwegs ist')

  // Die JÜNGERE Antwort (B): sie übernimmt und schließt ab — jetzt ist die
  // Verwaltung wirklich leer, und A hat aufgelöst.
  spaet[1](leerVerwaltung())
  const ergebnis = await Promise.race([
    Promise.all([a, b]).then(() => 'aufgeloest'),
    new Promise((ja) => setTimeout(() => ja('haengt'), 500)),
  ])
  assert.equal(ergebnis, 'aufgeloest',
    'nach der jüngsten Antwort löst nicht jedes der beiden Promises auf (die Fläche hinge)')
  await warte(20)
  assert.equal(host.querySelectorAll('[data-kalender]').length, 0,
    'nach der jüngsten Antwort steht noch eine Kalenderzeile im Bild: '
      + (host.textContent || '').replace(/\s+/g, ' ').slice(0, 240))
  assert.match(host.textContent || '', /Kein Kalender zu verwalten/,
    'nach der jüngsten Antwort fehlt der Leerzustand: '
      + (host.textContent || '').replace(/\s+/g, ' ').slice(0, 240))
  app.unmount()
  host.remove()
})
