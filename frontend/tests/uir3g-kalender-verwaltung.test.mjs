/**
 * UI-R3g — Kalendermenü: kein veralteter „Verwalten“-Eintrag beim erneuten
 * Seitenbesuch (Folge UI-R3f, nur frontend/).
 *
 * GEMESSEN wird an den ECHTEN Seiten (jsdom, Server-Attrappe): eine letzte
 * Attrappe beantwortet `get_kalender_verwaltung` in der REIHENFOLGE der
 * Besuche — Kalender „Alt“, dann „Neu“, dann 403. Der geteilte Stand wird
 * zwischen den Besuchen NICHT zurückgesetzt (das ist der SPA-Wechsel).
 *
 *   R1  Seitenbesuch-Folge Kalender → Verwaltung → Kalender:
 *       genau EIN Aufruf je Besuch; „Verwalten“ steht zu KEINEM Zeitpunkt
 *       veraltet im Bild (MutationObserver über den ganzen Lauf); nie
 *       Leerzustand/Fehlertext; nach dem 403 kein Eintrag.      (MUSS 1+2)
 *   R2  Der Eintrag erscheint erst mit der Antwort DIESES Besuchs — nicht
 *       mit der Antwort des vorigen (Seitenprüfung am gerenderten Bild).
 *                                                               (MUSS 1b)
 *
 * Lauf (cwd = frontend/, EINE Datei pro Aufruf):
 *   TMPDIR=$(mktemp -d) NODE_OPTIONS=--max-old-space-size=2048 \
 *     TZ=Europe/Berlin node --test --test-timeout=60000 tests/uir3g-kalender-verwaltung.test.mjs
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
/**
 * `beauftragungen` beantwortet `get_kalender_verwaltung` in der Reihenfolge der
 * Besuche: Eintrag = Antwort ODER Fehler (`Error` → wird geworfen) ODER
 * `Promise` (zurückgehalten). Ist die Liste abgearbeitet, gilt die letzte
 * Antwort weiter (kein unerwarteter Fehlschlag).
 */
let beauftragungen = []
/** Wie oft `get_kalender_verwaltung` schon gefragt wurde (je Lauf gezählt). */
let verwaltungAnfragen = 0
let baum = { gruppen: [] }
const aufrufe = []
const ersetzt = new Map()

/** Der nächste Auftrag dieser Methode (Eintrag bleibt stehen, wird gezählt). */
function auftrag() {
  const i = Math.min(verwaltungAnfragen, Math.max(beauftragungen.length - 1, 0))
  verwaltungAnfragen += 1
  return beauftragungen.length ? beauftragungen[i] : undefined
}

globalThis.__uiR3gMock = async (methode, args) => {
  aufrufe.push([methode, args])
  for (const [muster, antwort] of ersetzt) {
    if (!new RegExp(muster).test(methode)) continue
    const wert = typeof antwort === 'function' ? await antwort() : await antwort
    if (wert instanceof Error) throw wert
    return JSON.parse(JSON.stringify(wert))
  }
  if (/get_gruppen_hierarchie$/.test(methode)) return JSON.parse(JSON.stringify(baum))
  if (/get_kalender_verwaltung$/.test(methode)) {
    const wert = await auftrag()
    if (wert instanceof Error) throw wert
    if (wert && typeof wert.then === 'function') {
      const gehalten = await wert
      if (gehalten instanceof Error) throw gehalten
      return JSON.parse(JSON.stringify(gehalten ?? leerVerwaltung()))
    }
    return JSON.parse(JSON.stringify(wert ?? leerVerwaltung()))
  }
  if (/get_objekt_rechte$/.test(methode)) return { freigaben: [] }
  if (/get_current_user_context$/.test(methode)) return { roles: [], user: '' }
  return { success: true }
}

globalThis.fetch = async (url, optionen = {}) => {
  const methode = String(url || '').replace(/^.*\/api\/method\//, '')
  let args = {}
  try { args = JSON.parse(optionen.body || '{}') } catch { args = {} }
  aufrufe.push([methode, args])
  return {
    ok: true,
    status: 200,
    headers: { get: () => 'application/json' },
    json: async () => ({ message: { success: true } }),
    text: async () => JSON.stringify({ message: { success: true } }),
  }
}

const mit = (muster) => aufrufe.filter(([m]) => new RegExp(muster).test(m))

// ── SFC-Übersetzer ────────────────────────────────────────────────────────
const Vue = await import('vue')
const TMP = mkdtempSync(join(tmpdir(), 'uir3g-'))
const cache = new Map()
const VUE_URL = import.meta.resolve('vue')

mkdirSync(join(TMP, 'shim'), { recursive: true })
const SHIM = join(TMP, 'shim', 'useApi.mock.mjs')
writeFileSync(SHIM,
  `export * from ${JSON.stringify(new URL('../src/diakonos/composables/useApi.js', import.meta.url).href)}\n`
  + 'export const apiCall = (methode, args) => globalThis.__uiR3gMock(methode, args)\n'
  + 'export default { apiCall }\n')

/**
 * Fremde Pakete, die die Kalenderseite zieht: die Kalender-Bibliothek braucht
 * Maße und Layout. Fehlt sie, wirft `KronosCalendar` beim Aufbau — das ist
 * erlaubt (die Bibliothek ist hier nicht da), es darf nur NICHT die Prüfung
 * verfälschen: die Attrappe liefert deshalb ein leeres, aber vollständiges
 * `create()`-Objekt. Beide Formen (default und benannt) werden bedient.
 */
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
  // Auch Importe OHNE `from` (`import 'paket/stil.css'`) auf die Attrappe legen.
  code = code.replace(/^import\s+['"]([^'"]+)['"];?$/gm, (ganz, spec) => {
    const ersatz = fremdesModul(spec)
    return ersatz ? `import '${pathToFileURL(ersatz).href}';` : ganz
  })
  const ziel = resolve(TMP, filename.replace(/\.vue$/, '') + '.' + cache.size + '.mjs')
  writeFileSync(ziel, code)
  cache.set(abs, ziel)
  return ziel
}

/** Der geteilte Ladestand — sein Aufruf geht über DIESELBE Attrappe. */
async function stand() {
  const modul = await import('../src/diakonos/composables/useKalenderVerwaltung.js')
  modul.__setzeApiAufruf((methode, args) => globalThis.__uiR3gMock(methode, args))
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
  beauftragungen = []
  verwaltungAnfragen = 0
  baum = { gruppen: [] }
  ersetzt.clear()
  aufrufe.length = 0
})

const warte = async (n = 24) => { for (let i = 0; i < n; i += 1) await new Promise((l) => setTimeout(l, 0)) }

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

/** Antwort, die „Verwalten“ sichtbar macht (`kalenderVerwaltungSichtbar`). */
function mitRecht(name) {
  return {
    kalender: [kalender({ name, titel: name })],
    anlegen_gruppen: ['G-Chor'], anlegen_untergruppen: [], darf_gemeinde_kalender: false,
  }
}

function programm(vorlage, { daten = {}, teile = {}, host = null } = {}) {
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
  return { host: ziel, app, meldungen }
}

async function baustein(rel) {
  const pfad = uebersetze(resolve(SRC_DIR, 'diakonos', rel))
  return (await import('file://' + pfad)).default
}

/** „Kalender verwalten“ als gerenderter Knopf (oder null). */
const verwaltenKnopf = (host) => [...host.querySelectorAll('button, a')]
  .find((el) => /^\s*Kalender verwalten\s*$/.test(el.textContent || ''))

/** Was NICHT im Bild stehen darf — Leerzustände, Fehlertexte, fremde Listen. */
const VERBOTEN = [
  [/Kein Kalender zu verwalten/, 'Leerzustand „Kein Kalender zu verwalten“'],
  [/Noch keine Kalender/, 'Leerzustand „Noch keine Kalender“'],
  [/konnten nicht geladen werden/, 'Fehlertext zum Laden'],
  [/Alte Liste/, 'die ALTE Liste'],
]
function pruefeBild(text, wo) {
  for (const [muster, was] of VERBOTEN) {
    assert.doesNotMatch(text, muster, `${wo}: ${was} steht im Bild: ${String(text).replace(/\s+/g, ' ').slice(0, 300)}`)
  }
}

// ══════════════════════════════════════════════════════════════════════════
// R1 · Seitenbesuch-Folge Kalender → Verwaltung → Kalender (MUSS 1+2)
// ══════════════════════════════════════════════════════════════════════════

test('UI-R3g/R1: Kalender → Verwaltung → Kalender — EIN Aufruf je Besuch, kein veralteter „Verwalten“-Eintrag', async () => {
  // BEFUND (UI-R3f-Stand): `Kalender.vue` las `verwaltung` schon beim Aufbau
  // und blendete den Eintrag erst aus, wenn die frische Antwort da war
  // (`aber die frische Anfrage startete erst nach dem Await von
  // `fetchAccessibleCalendars``). `KronosSidebar.vue` las denselben Stand
  // ohne Wissen vom laufenden Besuch. Deshalb stand „Kalender verwalten“ in
  // Leiste und ⋯-Menü, solange die Antwort des VORIGEN Besuchs galt — auch
  // wenn das Recht inzwischen entzogen war.
  const geteilt = await stand()
  geteilt.__leeren()

  // Besuch 1: Kalender „Alt“ (mit Recht) · Besuch 2: Kalender „Proben 2“
  // (mit Recht) · Besuch 3: 403. Der geteilte Stand wird dazwischen NICHT
  // geleert.
  const tor = schleuse()
  beauftragungen = [
    mitRecht('Alt'),
    // Besuch 2 hält seine Antwort zurück (die Promise ist EINMAL gebaut).
    tor.versprechen,
    Object.assign(new Error('Nur Kalenderverantwortliche dürfen Kalender verwalten.'), { status: 403 }),
  ]

  const Seite = await baustein('pages/Kalender.vue')
  const Verwaltung = await baustein('pages/KalenderVerwaltung.vue')

  /** Ein Seitenbesuch: Mounten, alles beobachten, wieder verlassen. */
  async function besuch(name, komponente, vorlage) {
    const { host, app, meldungen } = programm(vorlage, { teile: { Seite: komponente } })
    // Die ERSTEN Bildstände gehören dem vorigen Besuch: Vue montiert hier in
    // einem eigenen Task, der Beobachter wird erst im Leerlauf scharf.
    await warte(2)
    const gesehen = []
    // UI-R3g: Jeder Wechsel NACH dem Aufbau wird festgehalten (Antwort
    // eingetroffen, Seite aufgebaut, altes Bild ersetzt).
    const beobachter = new MutationObserver(() => {
      gesehen.push(host.textContent || '')
    })
    beobachter.observe(host, { childList: true, subtree: true, characterData: true })
    await warte(40)
    gesehen.length = 0
    gesehen.push(host.textContent || '')
    /** Die Beobachtung scharf machen (ab hier wird jeder Bildstand gelesen). */
    const scharfMachen = () => { gesehen.length = 0 }
    return {
      name,
      host,
      meldungen,
      knopf: () => verwaltenKnopf(host),
      text: () => host.textContent || '',
      beobachter,
      gesehen,
      scharf: scharfMachen,
      /**
       * Den Beobachter scharf machen: ab hier wird JEDE Änderung nach dem
       * Rendern gelesen (`gesehen` füllt sich in `lesen()`).
       */
      async lesen(n = 40) {
        await warte(n)
        gesehen.push(host.textContent || '')
        return gesehen
      },
      beenden() {
        beobachter.disconnect()
        app.unmount()
        host.remove()
      },
    }
  }

  // ── Besuch 1: Kalenderseite, Server gibt das Recht ──────────────────────
  const s1 = await besuch('Kalender', Seite, '<Seite />')
  // GENAU eine Anfrage — der Besitzer lädt, die Leiste liest.
  const a1 = verwaltungAnfragen
  assert.equal(a1, 1, `Besuch 1 (Kalender): ${a1} Anfragen (erwartet: 1)`)
  assert.ok(s1.knopf(), `Besuch 1: „Kalender verwalten“ fehlt nach der Antwort: ${s1.text().replace(/\s+/g, ' ').slice(0, 200)}`)
  pruefeBild(s1.text(), 'Besuch 1 nach der Antwort')
  s1.beenden()

  // ── Besuch 2: Verwaltungsseite — ihre Antwort hängt ─────────────────────
  const s2 = await besuch('Verwaltung', Verwaltung, '<Seite />')
  const a2 = verwaltungAnfragen - a1
  assert.equal(a2, 1, `Besuch 2 (Verwaltung): ${a2} Anfragen (erwartet: 1)`)
  // REGRESSION (MUSS 1b): Hier darf der Eintrag der Kalenderseite nicht mehr
  // stehen — solange die Antwort DIESES Besuchs hängt, ist das Recht unbekannt.
  for (const [i, text] of s2.gesehen.entries()) {
    pruefeBild(text, `Besuch 2, Bildstand ${i}`)
    assert.doesNotMatch(text, /Alte Liste/,
      `Besuch 2, Bildstand ${i}: die Liste des vorigen Besuchs steht im Bild: `
        + text.replace(/\s+/g, ' ').slice(0, 300))
  }
  s2.scharf()
  tor.oeffnen(mitRecht('Proben 2'))
  await s2.lesen(60)
  for (const [i, text] of s2.gesehen.entries()) pruefeBild(text, `Besuch 2 nach der Antwort, Bildstand ${i}`)
  pruefeBild(s2.text(), 'Besuch 2 nach der Antwort')
  assert.match(s2.text(), /Proben 2/, 'Besuch 2: die frische Liste fehlt im Bild')
  s2.beenden()

  // ── Besuch 3: Kalenderseite, der Server sperrt (403) ────────────────────
  const a3vorher = verwaltungAnfragen
  // Der Besuch endet mit dem 403 — die Antwort hängt, bis der Beobachter
  // scharf ist: so geht KEIN Bildstand dieses Besuchs verloren.
  const tor3 = schleuse()
  beauftragungen[2] = tor3.versprechen
  const s3 = await besuch('Kalender (403)', Seite, '<Seite />')
  const a3 = verwaltungAnfragen - a3vorher
  assert.equal(a3, 1, `Besuch 3 (Kalender, 403): ${a3} Anfragen (erwartet: 1)`)
  tor3.oeffnen(Object.assign(new Error('Nur Kalenderverantwortliche dürfen Kalender verwalten.'), { status: 403 }))
  await s3.lesen(60)

  // REGRESSION (MUSS 1, der Kern dieser Karte): Zu KEINEM Zeitpunkt dieses
  // Besuchs darf „Kalender verwalten“ aus der Antwort von Besuch 2 stehen.
  // Vor dem Fix stand der Eintrag, bis die frische Antwort eintraf.
  for (const [i, text] of s3.gesehen.entries()) {
    pruefeBild(text, `Besuch 3, Bildstand ${i}`)
    assert.doesNotMatch(text, /Kalender verwalten/,
      `Besuch 3, Bildstand ${i}: „Kalender verwalten“ steht aus dem vorigen Besuch im Bild: `
        + text.replace(/\s+/g, ' ').slice(0, 300))
  }
  assert.equal(s3.knopf(), undefined, 'Besuch 3 nach dem 403: „Kalender verwalten“ steht noch im Bild')
  assert.equal(geteilt.useKalenderVerwaltung().sperrt.value, true, 'der geteilte Stand kennt das 403 nicht')
  s3.beenden()

  assert.equal(geteilt.useKalenderVerwaltung().verwaltung.value, null, 'nach dem 403 trägt der Stand noch eine Liste')
})

// ══════════════════════════════════════════════════════════════════════════
// R2 · Der Eintrag gehört zur Antwort DIESES Besuchs (MUSS 1b)
// ══════════════════════════════════════════════════════════════════════════

test('UI-R3g/R2: die Kalenderseite zeigt „Verwalten“ erst mit der Antwort dieses Besuchs (vorher: alter Stand, keine Unsicherheit)', async () => {
  // BEFUND (UI-R3f-Stand): der geteilte Stand trug die Antwort des vorigen
  // Besuchs; die Kalenderseite zeigte den Eintrag daraus, bis ihre eigene
  // (erst nach `fetchAccessibleCalendars` gestartete) Antwort eintraf.
  // Dieser Fall hält die frische Antwort zurück und prüft das gerenderte Bild
  // VOR und NACH der Antwort — ohne Regex auf den Quelltext.
  const geteilt = await stand()
  geteilt.__leeren()
  // Vorbedingung „der Stand trägt die Antwort des vorigen Besuchs“: ein
  // Besitzer-Weg (Satz + eine Ladung), wie ihn die Kalenderseite nimmt.
  geteilt.__setzeApiAufruf(async () => mitRecht('Proben 2'))
  geteilt.aktuellerSatz()
  await geteilt.laden()
  assert.equal(geteilt.useKalenderVerwaltung().antwortDa.value, true, 'Vorbedingung: geteilter Stand gefüllt')
  geteilt.__setzeApiAufruf((methode, args) => globalThis.__uiR3gMock(methode, args))

  const tor = schleuse()
  beauftragungen = [tor.versprechen, tor.versprechen]

  const Seite = await baustein('pages/Kalender.vue')
  const { host, app, meldungen } = programm('<Seite />', { teile: { Seite } })
  /**
   * Bildstände: der ERSTE nach dem Aufbau, dann an jedem Ruhepunkt (kein
   * Rendern mehr) — gelesen wird nur zwischen den Renderschritten, nie
   * mitten hinein.
   */
  const gesehen = []
  const beobachter = new MutationObserver(() => { geaendert = true })
  let geaendert = false
  beobachter.observe(host, { childList: true, subtree: true, characterData: true })
  await warte(40)
  gesehen.push(host.textContent || '')
  /** Bis zu `n` Runden abwarten, bis das Bild ruhig ist, und es festhalten. */
  async function ruhe(n = 60) {
    for (let runde = 0; runde < n && geaendert; runde += 1) {
      geaendert = false
      await warte(4)
    }
    gesehen.push(host.textContent || '')
    return host.textContent || ''
  }

  assert.equal(verwaltungAnfragen, 1, `die Kalenderseite fragte ${verwaltungAnfragen} mal (erwartet: 1)`)

  // Vor der Antwort: der Eintrag des vorigen Besuchs darf NICHT stehen.
  for (const [i, text] of gesehen.entries()) {
    assert.doesNotMatch(text, /Kalender verwalten/,
      `Bildstand ${i} vor der Antwort: „Kalender verwalten“ steht aus dem alten Stand: `
        + text.replace(/\s+/g, ' ').slice(0, 300))
    pruefeBild(text, `Bildstand ${i} vor der Antwort`)
  }

  // Nach der frischen Antwort (Recht gegeben): der Eintrag steht.
  tor.oeffnen(mitRecht('Proben 2'))
  await ruhe(60)
  assert.ok(verwaltenKnopf(host),
    'nach der frischen Antwort fehlt „Kalender verwalten“: ' + (host.textContent || '').replace(/\s+/g, ' ').slice(0, 300))

  beobachter.disconnect()
  app.unmount()
  host.remove()
  assert.deepEqual(meldungen.filter((m) => /^err:/.test(m)), [], 'Fehler: ' + meldungen.join(' | '))
})
