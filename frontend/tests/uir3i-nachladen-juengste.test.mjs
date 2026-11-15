/**
 * UI-R3i (MUSS 1) — das `nachladen`-Promise der Verwaltungsseite wartet auf die
 * JÜNGSTE Antwort.
 *
 * Gemessen wird am ECHTEN Bauteil (`pages/KalenderVerwaltung.vue`, jsdom,
 * Server-Attrappe) und an seinem Promise — nicht am Quelltext.
 *
 *   L1  Zwei überlappende Ladungen: das Promise der ÄLTEREN ist 30 ms nach ihrer
 *       Antwort noch OFFEN und löst erst mit der jüngsten auf.
 *   L2  Die jüngste Ladung scheitert: beide Promises lösen auf, `fehler` ist
 *       gesetzt, `laedt` ist frei — nichts hängt (und `busy` der Fläche bleibt
 *       nicht gesetzt).
 *   L3  Drei Ladungen in Folge: alle drei lösen erst mit der dritten auf.
 *   L4  Die echte Fläche (`KalenderEinstellungen` in der Seite): Toast bzw.
 *       „Rückgängig“ erscheinen erst, wenn die jüngste Antwort da ist und die
 *       alte Zeile weg ist.
 *
 * Am Stand UI-R3h (7ccfdd0d) sind L1–L4 ROT — und zwar am Verhalten: der
 * Überholt-Zweig von `laden()` gab `undefined` zurück, das Promise löste sofort
 * auf.
 *
 * Lauf (cwd = frontend/, EINE Datei pro Aufruf):
 *   TMPDIR=$(mktemp -d) NODE_OPTIONS=--max-old-space-size=2048 \
 *     TZ=Europe/Berlin node --test --test-timeout=60000 tests/uir3i-nachladen-juengste.test.mjs
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

globalThis.__uiR3iMock = async (methode, args) => {
  aufrufe.push([methode, args])
  for (const [muster, antwort] of Object.entries(ueberschreibungen)) {
    if (!new RegExp(muster).test(methode)) continue
    const wert = typeof antwort === 'function' ? await antwort() : await antwort
    if (wert instanceof Error) throw wert
    return JSON.parse(JSON.stringify(wert))
  }
  if (/get_gruppen_hierarchie$/.test(methode)) return { gruppen: [] }
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
  let wert
  try {
    wert = await globalThis.__uiR3iMock(methode, args)
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

// ── SFC-Übersetzer ────────────────────────────────────────────────────────
const Vue = await import('vue')
const TMP = mkdtempSync(join(tmpdir(), 'uir3i-'))
const cache = new Map()
const VUE_URL = import.meta.resolve('vue')

mkdirSync(join(TMP, 'shim'), { recursive: true })
const SHIM = join(TMP, 'shim', 'useApi.mock.mjs')
writeFileSync(SHIM,
  `export * from ${JSON.stringify(new URL('../src/diakonos/composables/useApi.js', import.meta.url).href)}\n`
  + 'export const apiCall = (methode, args) => globalThis.__uiR3iMock(methode, args)\n'
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
  modul.__setzeApiAufruf((methode, args) => globalThis.__uiR3iMock(methode, args))
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
  aufrufe.length = 0
})

const warte = async (n = 24) => { for (let i = 0; i < n; i += 1) await new Promise((l) => setTimeout(l, 0)) }
/** Echte Zeit verstreichen lassen (die Karte nennt 30 ms). */
const ms = (n) => new Promise((l) => setTimeout(l, n))

/** Eine zurückgehaltene Antwort: `oeffnen(wert)` löst sie auf. */
function schleuse() {
  let oeffnen
  const versprechen = new Promise((ja) => { oeffnen = ja })
  return { versprechen, oeffnen }
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

function mitRecht(name = 'Proben', extra = {}) {
  return {
    kalender: [kalender({ name, titel: name, ...extra })],
    anlegen_gruppen: ['G-Chor'], anlegen_untergruppen: [], darf_gemeinde_kalender: false,
  }
}

async function programm(vorlage, { teile = {} } = {}) {
  const ziel = document.createElement('div')
  document.body.appendChild(ziel)
  const meldungen = []
  const app = Vue.createApp({ components: teile, template: vorlage })
  app.config.warnHandler = (m) => meldungen.push('warn: ' + String(m))
  app.config.errorHandler = (e) => meldungen.push('err: ' + String(e && e.message))
  app.mount(ziel)
  await warte(24)
  return { host: ziel, app, meldungen }
}

/**
 * Den Stand der Seite lesen. `setupState` ist ein Ref-PROXY, dort liest sich
 * ein `ref` schon ungewrappt (`laedt` = `true`, nicht `{ value }`).
 */
function seitenStand(host) {
  const treffer = []
  const lauf = (vnode) => {
    if (!vnode) return
    if (typeof vnode.type === 'object' && vnode.type?.__name === 'KalenderVerwaltung' && vnode.component) {
      treffer.push(vnode.component.setupState)
    }
    if (vnode.component) lauf(vnode.component.subTree)
    if (Array.isArray(vnode.children)) for (const k of vnode.children) lauf(k)
  }
  lauf(host._vnode.component.subTree)
  return treffer[0] || null
}

/** Die Instanz der gemeinsamen Fläche (`KalenderEinstellungen`) im Baum. */
function flaechenStand(host) {
  const treffer = []
  const lauf = (vnode) => {
    if (!vnode) return
    if (typeof vnode.type === 'object' && vnode.type?.__name === 'KalenderEinstellungen' && vnode.component) {
      treffer.push(vnode.component.setupState)
    }
    if (vnode.component) lauf(vnode.component.subTree)
    if (Array.isArray(vnode.children)) for (const k of vnode.children) lauf(k)
  }
  lauf(host._vnode.component.subTree)
  return treffer[0] || null
}

/**
 * Ist ein Promise noch offen? (`false` heißt: aufgelöst oder abgelehnt.) Der
 * Zustand wird über einen Marker gemerkt; der Zeitgeber hält die Ereignis-
 * schleife währenddessen am Leben (sonst beendet `node --test` den Lauf).
 */
function offen(p, ms2 = 20) {
  const lage = { offen: true }
  Promise.resolve(p).then(() => { lage.offen = false }, () => { lage.offen = false })
  return new Promise((ja) => setTimeout(() => ja(lage.offen), ms2))
}

/** Der Zustand einer Meldung nach der Frist — „steht im Bild“. */
const alleMeldungen = () => [...document.querySelectorAll('.diakonos-toast')]
const rueckgaengigMeldungen = () => [...document.querySelectorAll('.diakonos-toast--undo')]
  .filter((t) => /Rückgängig/.test(t.textContent || ''))

/**
 * Die Seite mit gesteuerten Antworten mounten (Aufbau + erste Antwort sofort).
 * `spaet` sammelt die Löser aller weiteren Anfragen in der Reihenfolge, in der
 * sie beim Server eintreffen.
 */
async function seiteMitSchleusen({ erste = mitRecht('Chor', { titel: 'Chorproben' }) } = {}) {
  const geteilt = await stand()
  geteilt.__leeren()
  let gezaehlt = 0
  const spaet = []
  ueberschreibungen = {
    'get_kalender_verwaltung$': () => {
      gezaehlt += 1
      if (gezaehlt === 1) return erste
      const tor = schleuse()
      // Auch die ANTWORT-Weitergabe hängt an dieser Schleuse: `oeffnen(wert)`
      // gibt die Antwort erst frei, wenn sie hier ausgeleitet wird.
      spaet.push((wert) => { tor.oeffnen(wert) })
      return tor.versprechen
    },
  }
  const Seite = await baustein('pages/KalenderVerwaltung.vue')
  const { host, app, meldungen } = await programm('<Seite />', { teile: { Seite } })
  await warte(40)
  assert.deepEqual(meldungen.filter((m) => /^err/.test(m)), [], 'Fehler: ' + meldungen.join(' | '))
  assert.ok(host.querySelector('[data-kalender="Chor"]'),
    'Vorbedingung: die Zeile „Chorproben“ fehlt: ' + (host.textContent || '').replace(/\s+/g, ' ').slice(0, 200))
  const seite = seitenStand(host)
  assert.ok(seite && typeof seite.nachladen === 'function', 'Vorbedingung: `nachladen` der Seite fehlt')
  return { geteilt, host, app, seite, spaet }
}

// ══════════════════════════════════════════════════════════════════════════
// L1 · Das ältere Promise wartet auf die jüngste Antwort (MUSS 1a)
// ══════════════════════════════════════════════════════════════════════════

test('UI-R3i/L1: das Promise der älteren Nachladung ist 30 ms nach ihrer Antwort noch offen — erst die jüngste Antwort löst es auf', async () => {
  const { host, app, seite, spaet } = await seiteMitSchleusen()

  // `a` mit Fehlerbehandlung anhängen: löst es DOCH auf (der alte Fehler), darf
  // das den Lauf nicht als unbehandelte Ablehnung beenden — die Assertion unten
  // sagt es dann.
  const a = seite.nachladen().catch(() => undefined)
  await warte(4)
  const b = seite.nachladen().catch(() => undefined)
  await warte(4)
  assert.equal(spaet.length, 2, `beide Nachladungen müssen gefragt haben (${spaet.length})`)

  // Die ÄLTERE Antwort (A) kommt an — die jüngste (B) fehlt noch.
  spaet[0](mitRecht('Alt', { titel: 'Alte Zeile' }))
  await warte(20)
  assert.equal(await offen(a, 20), true,
    'das Promise der ÜBERHOLTEN Ladung hat schon aufgelöst, obwohl die jüngste Antwort noch fehlt '
      + '(die Fläche meldet dann Toast/„Rückgängig“, während die alte Zeile im Bild steht)')

  // Und es wartet wirklich: 30 ms später ist es noch offen.
  await ms(30)
  assert.equal(await offen(a, 20), true,
    'das Promise der überholten Ladung ist 30 ms nach der alten Antwort aufgelöst — es wartet nicht auf die jüngste')

  // Die JÜNGSTE Antwort (B): jetzt löst A auf, und die alte Zeile ist weg.
  spaet[1](leerVerwaltung())
  await a
  await b
  await warte(20)
  assert.equal(host.querySelectorAll('[data-kalender]').length, 0,
    'nach der jüngsten Antwort steht noch eine Kalenderzeile im Bild: '
      + [...host.querySelectorAll('[data-kalender]')].map((e) => e.getAttribute('data-kalender')).join(','))
  app.unmount()
  host.remove()
})

// ══════════════════════════════════════════════════════════════════════════
// L2 · Die jüngste Ladung scheitert — nichts hängt (MUSS 1b)
// ══════════════════════════════════════════════════════════════════════════

test('UI-R3i/L2: scheitert die jüngste Ladung, lösen A und B auf, `fehler` ist gesetzt, `laedt` ist frei', async () => {
  const { host, app, seite, spaet } = await seiteMitSchleusen()

  const a = seite.nachladen().catch(() => undefined)
  await warte(4)
  const b = seite.nachladen().catch(() => undefined)
  await warte(4)
  assert.equal(spaet.length, 2, `beide Nachladungen müssen gefragt haben (${spaet.length})`)

  // A kommt an (überholt), B scheitert (eine jüngste Antwort, die `fehler` setzt).
  spaet[0](mitRecht('Alt', { titel: 'Alte Zeile' }))
  await warte(12)
  assert.equal(await offen(a, 12), true, 'Vorbedingung: A wartet nicht auf B (der Fall misst sonst nichts)')
  spaet[1](new Error('Der Server hat nicht geantwortet.'))

  // Beide Promises lösen auf — mit Zeitgrenze gemessen, damit ein Hänger rot wird.
  const ergebnis = await Promise.race([
    Promise.allSettled([a, b]).then(() => 'aufgeloest'),
    ms(500).then(() => 'haengt'),
  ])
  assert.equal(ergebnis, 'aufgeloest',
    'mindestens ein `nachladen`-Promise hängt nach dem Fehlschlag der jüngsten Ladung (busy bliebe gesetzt)')

  assert.match(String(seite.fehler || ''), /\S/,
    'die jüngste Ladung ist gescheitert, aber `fehler` der Seite ist leer')
  assert.equal(seite.laedt, false,
    '`laedt` steht noch auf true, obwohl die jüngste Ladung fertig ist — der Bildschirm bliebe leer')
  app.unmount()
  host.remove()
})

// ══════════════════════════════════════════════════════════════════════════
// L3 · Drei Ladungen in Folge — alle lösen erst mit der dritten auf (MUSS 1c)
// ══════════════════════════════════════════════════════════════════════════

test('UI-R3i/L3: drei überlappende Nachladungen lösen ALLE erst mit der dritten Antwort auf', async () => {
  const { host, app, seite, spaet } = await seiteMitSchleusen()

  const a = seite.nachladen().catch(() => undefined)
  await warte(3)
  const b = seite.nachladen().catch(() => undefined)
  await warte(3)
  const c = seite.nachladen()
  await warte(4)
  assert.equal(spaet.length, 3, `alle drei Nachladungen müssen gefragt haben (${spaet.length})`)

  // A und B kommen an, C fehlt noch — A und B sind überholt.
  spaet[0](mitRecht('A', { titel: 'A' }))
  await warte(6)
  spaet[1](mitRecht('B', { titel: 'B' }))
  await warte(20)
  const lage = { a: await offen(a, 12), b: await offen(b, 12), c: await offen(c, 12) }
  assert.deepEqual(lage, { a: true, b: true, c: true },
    'eine überholte Ladung hat aufgelöst, obwohl die dritte Antwort noch fehlt: ' + JSON.stringify(lage))

  // Die dritte (jüngste) Antwort: jetzt lösen alle auf.
  spaet[2](leerVerwaltung())
  const ergebnis = await Promise.race([
    Promise.all([a, b, c]).then(() => 'aufgeloest'),
    ms(500).then(() => 'haengt'),
  ])
  assert.equal(ergebnis, 'aufgeloest', 'nach der dritten Antwort löst nicht jedes der drei Promises auf')
  await warte(20)
  assert.equal(host.querySelectorAll('[data-kalender]').length, 0,
    'nach der dritten Antwort steht noch eine Kalenderzeile im Bild: '
      + [...host.querySelectorAll('[data-kalender]')].map((e) => e.getAttribute('data-kalender')).join(','))
  app.unmount()
  host.remove()
})

// ══════════════════════════════════════════════════════════════════════════
// L4 · Mit der echten Fläche: Toast/„Rückgängig“ erst mit der jüngsten Antwort
// ══════════════════════════════════════════════════════════════════════════

test('UI-R3i/L4: „Löschen“ in der echten Fläche — Toast und „Rückgängig“ erscheinen erst, wenn die JÜNGSTE Antwort da ist und die alte Zeile weg ist', async () => {
  const { host, app, seite, spaet } = await seiteMitSchleusen({
    erste: mitRecht('Chor', { titel: 'Chorproben', gruppe: 'G-Chor' }),
  })
  const flaeche = flaechenStand(host)
  assert.ok(flaeche && typeof flaeche.entfernen === 'function',
    'Vorbedingung: die gemeinsame Fläche (`KalenderEinstellungen`) steht nicht in der Seite')

  // „Löschen“ der Zeile „Chorproben“ — das Löschen selbst antwortet sofort, die
  // Liste lädt über `nachladen` der SEITE nach (die Fläche wartet darauf).
  ueberschreibungen = { ...ueberschreibungen, 'delete_kalender$': { success: true } }
  const zeile = [...host.querySelectorAll('[data-kalender="Chor"] button')]
    .find((b) => /^\s*Löschen\s*$/.test(b.textContent || ''))
  assert.ok(zeile, 'Vorbedingung: der Löschen-Knopf der Zeile „Chorproben“ fehlt')
  zeile.click()
  await warte(20)
  assert.equal(spaet.length, 1,
    `der Löschvorgang muss EINE Nachladung der Seite auslösen (${spaet.length})`)

  // Zweite Änderung (jünger) auf DIESELBE Liste: die Seite lädt erneut nach —
  // der Löschvorgang der Fläche hängt damit am Promise der JÜNGSTEN Ladung.
  const zwei = seite.nachladen()
  await warte(6)
  assert.equal(spaet.length, 2, `die zweite Nachladung muss gefragt haben (${spaet.length})`)

  // Die Antwort der ERSTEN (überholten) Ladung trägt die ZEILE „Chor“ noch (sie
  // ist älter als das Löschen); die jüngste Antwort fehlt — kein Toast, kein
  // „Rückgängig“. Damit ist belegt, dass die Zeile NICHT zurückkommt: sie
  // verschwindet erst mit der jüngsten Antwort, nicht schon mit der alten.
  spaet[0](mitRecht('Chor', { titel: 'Chorproben', gruppe: 'G-Chor' }))
  await warte(40)
  assert.equal(host.querySelectorAll('[data-kalender]').length, 1,
    'Vorbedingung: die alte Antwort hat die Zeile „Chor“ nicht ins Bild gebracht '
      + '(dann misst der Fall nichts): '
      + [...host.querySelectorAll('[data-kalender]')].map((e) => e.getAttribute('data-kalender')).join(','))
  assert.equal(rueckgaengigMeldungen().length, 0,
    '„Rückgängig“ steht im Bild, obwohl die JÜNGSTE Antwort noch fehlt: '
      + rueckgaengigMeldungen().map((t) => (t.textContent || '').trim()).join(' | '))
  assert.equal(alleMeldungen().filter((t) => /gelöscht/.test(t.textContent || '')).length, 0,
    'der Lösch-Toast steht im Bild, obwohl die JÜNGSTE Antwort noch fehlt')
  assert.equal(Boolean(seite.laedt), false,
    'Vorbedingung: die Seite gilt schon als fertig geladen (der Fall misst sonst nichts)')

  // Die jüngste Antwort: erst jetzt der Toast — und die alte Zeile ist weg.
  spaet[1](leerVerwaltung())
  await zwei
  await warte(40)
  assert.equal(host.querySelectorAll('[data-kalender]').length, 0,
    'nach der jüngsten Antwort steht noch eine Kalenderzeile im Bild')
  assert.equal(String(flaeche.busy || ''), '',
    'die Fläche steht nach der jüngsten Antwort noch auf `busy` („' + String(flaeche.busy) + '“) — busy wäre dauerhaft gesetzt')
  assert.equal(rueckgaengigMeldungen().length, 1,
    'nach der jüngsten Antwort fehlt die Rückgängig-Meldung zum Löschen (gefunden: '
      + alleMeldungen().map((t) => (t.textContent || '').trim().slice(0, 60)).join(' | ') + ')')
  app.unmount()
  host.remove()
})
