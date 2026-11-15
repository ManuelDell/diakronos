/**
 * UI-R3j (MUSS 1) — das `nachladen`-Promise der Verwaltungsseite darf nicht auf
 * SICH SELBST warten.
 *
 * DER FALL (Verhalten, am ECHTEN Bauteil in jsdom gemessen):
 * Die jüngste Ladung der Seite wird von einem ANDEREN Besitzer des geteilten
 * Laders überholt — im Betrieb ist das `pages/Kalender.vue`, die schon im
 * Aufbau `aktuellerSatz()` ruft („Kalender verwalten“ wechseln, während ein
 * Löschen der Verwaltungsseite noch nachlädt).
 *
 * Am UI-R3i-Stand ist `juengsteLadung` dann das EIGENE Promise, und der
 * Überholt-Zweig wartet auf `juengsteLadung.ende` — das ist es selbst. Das
 * Promise löst nie auf: Toast und „Rückgängig“ erscheinen nie, `busy` der
 * Fläche bleibt gesetzt und (wäre die Seite noch gemountet) bliebe `laedt`
 * auf `true` — die Seite bliebe leer.
 *
 *   J1  STILLE Ladung (`nachladen`): `aktuellerSatz()` während der Ladung →
 *       das Promise löst auf (spätestens 300 ms nach der Antwort), `laedt` ist
 *       frei, die Antwort dieses Besuchs steht im Bild.
 *   J2  NICHT-STILLE Ladung (der Weg von `onMounted`, hier direkt `laden()`):
 *       dasselbe — das Promise löst auf, und die überholte Antwort schreibt das
 *       Bild nicht (die Zeile des vorigen Stands bleibt stehen).
 *
 * Rot→grün ist am VERHALTEN belegt (Lauf gegen den UI-R3i-Stand 3cde3a8c:
 * J1 und J2 laufen in die 300-ms-Grenze und werden rot).
 *
 * Lauf (cwd = frontend/, EINE Datei pro Aufruf):
 *   TMPDIR=$(mktemp -d) NODE_OPTIONS=--max-old-space-size=2048 \
 *     TZ=Europe/Berlin node --test --test-timeout=60000 tests/uir3j-nachladen-selbst.test.mjs
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

globalThis.__uiR3jMock = async (methode, args) => {
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
    wert = await globalThis.__uiR3jMock(methode, args)
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
const TMP = mkdtempSync(join(tmpdir(), 'uir3j-'))
const cache = new Map()
const VUE_URL = import.meta.resolve('vue')

mkdirSync(join(TMP, 'shim'), { recursive: true })
const SHIM = join(TMP, 'shim', 'useApi.mock.mjs')
writeFileSync(SHIM,
  `export * from ${JSON.stringify(new URL('../src/diakonos/composables/useApi.js', import.meta.url).href)}\n`
  + 'export const apiCall = (methode, args) => globalThis.__uiR3jMock(methode, args)\n'
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
  modul.__setzeApiAufruf((methode, args) => globalThis.__uiR3jMock(methode, args))
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

/** Ein offenes Promise mit Zeitgrenze abwarten — rot, wenn es hängt. */
async function loestAuf(p, grenzeMs = 300) {
  return Promise.race([
    Promise.resolve(p).then(() => 'aufgeloest', () => 'abgelehnt'),
    ms(grenzeMs).then(() => 'haengt'),
  ])
}

// ══════════════════════════════════════════════════════════════════════════
// J1 · Stille Ladung (nachladen) — der fremde Besuch überholt sie (MUSS 1)
// ══════════════════════════════════════════════════════════════════════════

test('UI-R3j/J1: überholt ein FREMDER Besuch die jüngste stille Ladung, löst `nachladen` auf — `laedt` ist frei, die Antwort steht im Bild', async () => {
  const { geteilt, host, app, seite, spaet } = await seiteMitSchleusen()

  // Die stille Ladung der Seite (der Weg der Fläche nach einem Löschen).
  const nach = seite.nachladen()
  await warte(6)
  assert.equal(spaet.length, 1, `"nachladen" muss gefragt haben (${spaet.length})`)

  // WÄHREND sie läuft, beginnt ein ANDERER Besitzer einen Besuch — im Betrieb
  // `pages/Kalender.vue` in ihrem Aufbau (`aktuellerSatz()`, UI-R3g). Damit ist
  // die eigene Ladung nicht mehr die jüngste: `juengsteLadung` ist das eigene
  // Promise, und der Überholt-Zweig wartete bisher auf sich selbst.
  geteilt.aktuellerSatz()

  // Die Antwort der Ladung kommt an.
  spaet[0](mitRecht('Nach', { titel: 'Neue Zeile', gruppe: 'G-Chor' }))
  const lage = await loestAuf(nach, 300)
  assert.equal(lage, 'aufgeloest',
    '`nachladen` löst nach seiner Antwort nicht auf, wenn ein fremder Besuch die Ladung überholt hat '
      + '(der Überholt-Zweig wartet auf das eigene Promise) — Toast und „Rückgängig“ blieben aus, '
      + '`busy` der Fläche bliebe gesetzt')
  assert.equal(seite.laedt, false,
    '`laedt` steht nach der Antwort noch auf true — die Seite bliebe leer')

  app.unmount()
  host.remove()
})

// ══════════════════════════════════════════════════════════════════════════
// J2 · Nicht-stille Ladung (der Weg von onMounted) — derselbe Fall (MUSS 1)
// ══════════════════════════════════════════════════════════════════════════

test('UI-R3j/J2: auch die NICHT-stille Ladung (der Weg von `onMounted`) löst auf, wenn ein fremder Besuch sie überholt', async () => {
  const { geteilt, host, app, seite, spaet } = await seiteMitSchleusen()

  // Nicht-stiller Weg: dieselbe Funktion wie `onMounted` — sie setzt `laedt`.
  const nichtStill = seite.laden()
  await warte(6)
  assert.equal(spaet.length, 1, `die nicht-stille Ladung muss gefragt haben (${spaet.length})`)

  geteilt.aktuellerSatz()
  spaet[0](mitRecht('Neu', { titel: 'Neue Zeile', gruppe: 'G-Chor' }))
  const lage = await loestAuf(nichtStill, 300)
  assert.equal(lage, 'aufgeloest',
    'die nicht-stille Ladung löst nicht auf, wenn ein fremder Besuch sie überholt hat')
  // Der Wartezustand der Seite bleibt bis zur jüngsten Antwort stehen (das ist
  // Absicht: `laedt` gehört dieser Ladung, und die überholte setzt nichts). Sie
  // darf also NOCH laden — entscheidend ist, dass das Promise aufgelöst ist und
  // die überholte Ladung keinen eigenen Fehler/keine eigene Antwort behauptet.
  assert.equal(seite.laedt, true,
    'Vorbedingung: die nicht-stille Ladung gilt schon als fertig (der Fall misst sonst nichts)')
  assert.equal(String(seite.fehler || ''), '',
    'die überholte Ladung hat einen Fehler gesetzt')

  app.unmount()
  host.remove()
})
