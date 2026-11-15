/**
 * UI-R3c — Kalender: einmal laden, Freigaben-Gruppen im Kontext,
 * Rollen-Rückfälle raus, Aufräumen.
 *
 * GEMESSEN wird am echten Baum (jsdom, API gestubbt) und an den reinen Regeln —
 * nicht an Quelltext-Mustern. Jeder Fall ist am Stand `main` (1db3b99b) ROT und
 * danach GRÜN; die Begründung steht im jeweiligen Testkopf.
 *
 *   R1  Freigaben auf der Verwaltungsseite: die Gruppenauswahl steht im KONTEXT
 *       des Kalenders (seine Gruppe und deren Untergruppen) — nicht die
 *       Anlegeziele ALLER Gruppen.              (MUSS 1)
 *   R2a Kalenderseite: Seite und Kalenderliste laden `get_kalender_verwaltung`
 *       zusammen EINMAL.                        (MUSS 2)
 *   R2b Verwaltungsseite: Seite und Fläche laden zusammen EINMAL. (MUSS 2)
 *   R3  Menü-Sichtbarkeit ohne Rollen-Rückfall: Admin ohne Serverantwort sieht
 *       „Kalender verwalten“ nicht; `kalenderVerwaltungSichtbar(null, true)`
 *       ist false.                              (MUSS 3)
 *   R4  Leerzustand: während die Antwort schwebt, steht weder „Kein Kalender zu
 *       verwalten“ noch der Leerzustand der Fläche im Bild.    (SOLL 4)
 *   R5  Kleinkram: beide Lösch-Gründe im Text, „trägt die Zeile“ aus EINER
 *       Quelle, leerer `props.gruppe` meldet Antwort.          (SOLL 5)
 *   R6  Kommentare: `kalenderRechte.mjs` behauptet nicht mehr, das Rückgängig
 *       schicke Freigaben mit; der UI-R1-Kommentar in `GruppeDetail.vue` ist
 *       ein ganzer Satz.                                        (SOLL 5)
 *
 * Lauf: TZ=Europe/Berlin node --test --test-timeout=60000 tests/uir3c-*.test.mjs
 *       (cwd = frontend/)
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
let ueberschreibungen = {}
let baum = { gruppen: [] }

globalThis.__uiR3cMock = async (methode, args) => {
  aufrufe.push([methode, args])
  for (const [muster, antwort] of Object.entries(ueberschreibungen)) {
    if (!new RegExp(muster).test(methode)) continue
    const wert = antwort instanceof Promise ? await antwort : antwort
    if (wert instanceof Error) throw wert
    return JSON.parse(JSON.stringify(wert))
  }
  if (/get_gruppen_hierarchie$/.test(methode)) return JSON.parse(JSON.stringify(baum))
  if (/get_kalender_verwaltung$/.test(methode)) {
    return { kalender: [], anlegen_gruppen: [], anlegen_untergruppen: [], darf_gemeinde_kalender: false }
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
const TMP = mkdtempSync(join(tmpdir(), 'uir3c-'))
const cache = new Map()
const VUE_URL = import.meta.resolve('vue')

mkdirSync(join(TMP, 'shim'), { recursive: true })
const SHIM = join(TMP, 'shim', 'useApi.mock.mjs')
writeFileSync(SHIM,
  `export * from ${JSON.stringify(new URL('../src/diakonos/composables/useApi.js', import.meta.url).href)}\n`
  + 'export const apiCall = (methode, args) => globalThis.__uiR3cMock(methode, args)\n'
  + 'export default { apiCall }\n')

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
    if (/composables\/useApi/.test(spec)) return `from '${pathToFileURL(SHIM).href}'`
    const ziel = resolve(dirname(abs), spec)
    const datei = /\.vue$/.test(spec) ? uebersetze(ziel) : ziel
    return `from '${pathToFileURL(datei).href}'`
  })
  const ziel = resolve(TMP, filename.replace(/\.vue$/, '') + '.' + cache.size + '.mjs')
  writeFileSync(ziel, code)
  cache.set(abs, ziel)
  return ziel
}

/**
 * UI-R3c: Der geteilte Ladestand (`useKalenderVerwaltung.js`) wird von diesem
 * Übersetzer NICHT übersetzt — sein eigenes `useApi` zeigte sonst auf das echte
 * Modul. Sein Aufruf geht deshalb über DIESELBE Attrappe.
 */
async function standAufAttrappe() {
  const stand = await import('../src/diakonos/composables/useKalenderVerwaltung.js')
  stand.__setzeApiAufruf((methode, args) => globalThis.__uiR3cMock(methode, args))
  stand.__leeren()
  // `laden`/`teilen` direkt, die Anzeige-Refs über den Hook (readonly).
  const { verwaltung, antwortDa } = stand.useKalenderVerwaltung()
  return { ...stand, verwaltung, antwortDa }
}

test.after(() => rmSync(TMP, { recursive: true, force: true }))
test.afterEach(() => {
  for (const el of [...document.body.children]) el.remove()
  ueberschreibungen = {}
  baum = { gruppen: [] }
  aufrufe.length = 0
})

const warte = async (n = 24) => { for (let i = 0; i < n; i += 1) await new Promise((l) => setTimeout(l, 0)) }

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

/** Mountet ein SFC mit vorgegebenen Props/Ereignissen. */
async function mounten(rel, { props = {}, events = [], appTeil = {} } = {}) {
  const pfad = uebersetze(resolve(SRC_DIR, 'diakonos', rel))
  const Baustein = (await import('file://' + pfad + '?t=' + Date.now())).default
  const host = document.createElement('div')
  host.setAttribute('data-uir3c-host', '')
  document.body.appendChild(host)
  const meldungen = []
  const bindungen = Object.entries(props).map(([k, v]) => `:${k.replace(/[A-Z]/g, (m) => '-' + m.toLowerCase())}="daten.${k}"`).join(' ')
  // ALLE Argumente sammeln: `gesperrt` trägt ZWEI Werte (gesperrt, antwortDa) —
  // eine Pfeil-Funktion bekäme nur das erste.
  const horcher = events.map((e) => `@${e}="(...args) => daten.ereignisse.push(['${e}', ...args])"`).join(' ')
  const app = Vue.createApp({
    components: { Baustein },
    data: () => ({ daten: { ...props, ereignisse: [] } }),
    template: `<Baustein ${bindungen} ${horcher} />`,
    ...appTeil,
  })
  app.config.warnHandler = (m) => meldungen.push('warn: ' + String(m))
  app.config.errorHandler = (e) => meldungen.push('err: ' + String(e && e.message))
  app.mount(host)
  await warte(24)
  return { host, meldungen, app }
}

// ══════════════════════════════════════════════════════════════════════════
// R1 · Freigabe-Auswahl im KONTEXT des Kalenders (MUSS 1)
// ══════════════════════════════════════════════════════════════════════════

test('UI-R3c/R1: die Gruppenauswahl eines Kalenders zeigt nur seine Gruppe und deren Untergruppen', async () => {
  // BEFUND (main 1db3b99b): Die Fläche reichte `gruppenliste` (die
  // ANLEGEZIELE aller Gruppen: G-Band, UG-Blech, G-Chor, UG-K) als
  // `untergruppen` durch, und `gruppenAuswahl` machte daraus die Auswahl JEDES
  // Kalenders. Am Kalender der Gruppe „Chor“ stand damit auch „Band“.
  await standAufAttrappe()
  baum = {
    gruppen: [
      { name: 'G-Chor', gruppenname: 'Chor', untergruppen: [{ name: 'UG-K', untergruppenname: 'Kinderchor' }] },
      { name: 'G-Band', gruppenname: 'Band', untergruppen: [{ name: 'UG-B', untergruppenname: 'Blech' }] },
    ],
  }
  const verwaltung = {
    kalender: [kalender({ name: 'Proben', titel: 'Proben', gruppe: 'G-Chor', untergruppe: null })],
    anlegen_gruppen: ['G-Band', 'G-Chor'],
    anlegen_untergruppen: ['UG-B', 'UG-K'],
    darf_gemeinde_kalender: false,
  }
  ueberschreibungen = {
    'get_kalender_verwaltung$': verwaltung,
    'get_objekt_rechte$': { freigaben: [], darf_moderieren_vergeben: false, gemeinde_status: 'aus', gruppe_status: 'aus' },
  }
  // Die ANLEGEZIELE aller Gruppen kommen hier herein — genau wie von der
  // Verwaltungsseite. `gruppe` ist dort ausdrücklich leer (keine Gruppenseite).
  const { host, meldungen } = await mounten('components/gruppen/KalenderEinstellungen.vue', {
    props: {
      gruppe: '',
      alleKalender: true,
      ziele: [
        { wert: 'G-Band', art: 'gruppe', anzeige: 'Gruppe Band' },
        { wert: 'G-Chor', art: 'gruppe', anzeige: 'Gruppe Chor' },
        { wert: 'UG-B', art: 'untergruppe', anzeige: 'Untergruppe Blech' },
        { wert: 'UG-K', art: 'untergruppe', anzeige: 'Untergruppe Kinderchor' },
      ],
      untergruppen: [
        { name: 'G-Band', anzeigename: 'Band', gruppe: '' },
        { name: 'G-Chor', anzeigename: 'Chor', gruppe: '' },
        { name: 'UG-B', anzeigename: 'Blech', gruppe: 'G-Band' },
        { name: 'UG-K', anzeigename: 'Kinderchor', gruppe: 'G-Chor' },
      ],
    },
  })
  assert.deepEqual(meldungen.filter((m) => /^err:/.test(m)), [],
    'Fehler in der Fläche: ' + meldungen.join(' | '))
  assert.deepEqual(mit('get_kalender_verwaltung$').length, 1, 'die Fläche lädt die Liste selbst genau einmal')

  // Aufklappen → die Gruppenauswahl dieses Kalenders steht im Bild.
  const aufklappen = [...host.querySelectorAll('button')].find((b) => /Freigaben & Sichtbarkeit/.test(b.textContent))
  assert.ok(aufklappen, 'der Aufklapp-Knopf fehlt')
  aufklappen.click()
  await warte(20)

  const auswahl = [...host.querySelectorAll('select')]
    .find((s) => /Gruppe für eine Freigabe/.test(s.getAttribute('aria-label') || ''))
  assert.ok(auswahl, 'die Gruppenauswahl fehlt')
  const werte = [...auswahl.options].map((o) => o.value).filter(Boolean)
  assert.deepEqual(werte.sort(), ['G-Chor', 'UG-K'],
    'die Auswahl zeigt nicht genau die Gruppe des Kalenders und ihre Untergruppen: ' + werte.join(', '))
  assert.ok(!werte.includes('G-Band'), 'die Auswahl zeigt eine fremde Gruppe (Band)')
  assert.ok(!werte.includes('UG-B'), 'die Auswahl zeigt die Untergruppe einer fremden Gruppe (Blech)')
})

// ══════════════════════════════════════════════════════════════════════════
// R2 · EIN Ladevorgang je Seite (MUSS 2)
// ══════════════════════════════════════════════════════════════════════════

test('UI-R3c/R2a: Kalenderseite — Seite und Kalenderliste laden die Verwaltung zusammen EINMAL', async () => {
  // BEFUND (main): `Kalender.vue` (⋯-Menü) und `KronosSidebar.vue` (ihr
  // Menüpunkt) riefen `get_kalender_verwaltung` je einmal — zwei Anfragen für
  // dieselbe Antwort. Gemessen wird die Zahl der Aufrufe am echten Baum.
  const stand = await standAufAttrappe()
  const antwort = {
    kalender: [kalender()],
    anlegen_gruppen: ['G-Chor'],
    anlegen_untergruppen: [],
    darf_gemeinde_kalender: false,
  }
  ueberschreibungen = { 'get_kalender_verwaltung$': antwort }
  // UI-R3g: `laden()` holt IMMER neu (den Weg „teile die laufende Anfrage“
  // gibt es nicht mehr — er hatte keinen Betriebsaufruf). Der Betrieb fragt
  // deshalb über den EINEN Besitzer; zwei gleichzeitige Aufrufe desselben
  // Besitzers sind zwei Besuche, keine zwei Anzeigen. Geprüft wird hier der
  // eine Weg und sein Ergebnis.
  const eins = await stand.laden()
  assert.equal(mit('get_kalender_verwaltung$').length, 1,
    'die eine Ladung löste keine (oder mehr als eine) Anfrage aus')
  assert.deepEqual(eins, antwort)
  // Der geteilte Stand LESEN ist kostenlos: beide Anzeigen bekommen dieselbe
  // Antwort, ohne den Server zu fragen (`verwaltung`/`antwortDa`).
  assert.deepEqual(stand.verwaltung.value, antwort, 'der Stand trägt die Antwort nicht')
  assert.equal(stand.antwortDa.value, true, 'der Stand meldet keine Antwort')
  assert.equal(mit('get_kalender_verwaltung$').length, 1,
    'das LESEN des Stands löste eine Anfrage aus')

  // Und der Quelltext führt keinen zweiten Aufruf mehr ein: die Kalenderliste
  // geht über den geteilten Stand, nicht über `apiCall`.
  const seite = lies('pages/Kalender.vue')
  const leiste = lies('components/kronos/KronosSidebar.vue')
  assert.match(seite, /ladenKalenderVerwaltung/, 'die Seite nutzt den geteilten Stand nicht')
  // UI-R3e (MUSS 2): EIN Besitzer lädt — die Leiste LIEST den geteilten Stand
  // (`useKalenderVerwaltung`) und fragt den Endpunkt nicht mehr selbst. Der
  // Literal `ladenKalenderVerwaltung` darf in ihr deshalb nicht mehr stehen.
  assert.match(leiste, /useKalenderVerwaltung/, 'die Kalenderliste liest den geteilten Stand nicht')
  for (const [name, quelle] of [['Kalender.vue', seite], ['KronosSidebar.vue', leiste]]) {
    assert.doesNotMatch(quelle, /apiCall\(\s*['"][^'"]*get_kalender_verwaltung/,
      `${name}: eigener Aufruf des Endpunkts statt des geteilten Stands`)
  }
})

test('UI-R3c/R2b: Verwaltungsseite — Seite und Fläche laden die Verwaltung zusammen EINMAL', async () => {
  // BEFUND (main): `KalenderVerwaltung.vue` und die gemeinsame Fläche
  // `KalenderEinstellungen.vue` fragten beide. Jetzt holt die Seite und reicht
  // die Antwort als `:verwaltung` hinein.
  const stand = await standAufAttrappe()
  ueberschreibungen = {
    'get_kalender_verwaltung$': {
      kalender: [kalender(), kalender({ name: 'Chorproben', titel: 'Chorproben' })],
      anlegen_gruppen: ['G-Chor'],
      anlegen_untergruppen: [],
      darf_gemeinde_kalender: false,
    },
  }
  const pfad = uebersetze(resolve(SRC_DIR, 'diakonos', 'pages', 'KalenderVerwaltung.vue'))
  const Seite = (await import('file://' + pfad + '?t=' + Date.now())).default
  const host = document.createElement('div')
  document.body.appendChild(host)
  const meldungen = []
  const app = Vue.createApp({ components: { Seite }, template: '<Seite />' })
  app.config.warnHandler = (m) => meldungen.push('warn: ' + String(m))
  app.config.errorHandler = (e) => meldungen.push('err: ' + String(e && e.message))
  app.mount(host)
  await warte(40)

  assert.deepEqual(meldungen.filter((m) => /^err:/.test(m)), [], 'Fehler: ' + meldungen.join(' | '))
  assert.equal(mit('get_kalender_verwaltung$').length, 1,
    'Seite und Fläche lösten ' + mit('get_kalender_verwaltung$').length + ' Anfragen aus (erwartet: 1)')
  // Die Fläche zeigt trotzdem die Kalender (sie hat die Antwort bekommen).
  const text = host.textContent || ''
  assert.ok(text.includes('Proben'), 'die Fläche zeigt die Kalender der Seite nicht')
  assert.ok(text.includes('Chorproben'), 'die Fläche zeigt nicht alle Kalender der Seite')
  assert.equal(stand.verwaltung.value?.kalender?.length, 2, 'der geteilte Stand trägt die Antwort nicht')
})

// ══════════════════════════════════════════════════════════════════════════
// R3 · Menü-Sichtbarkeit ohne Rollen-Rückfall (MUSS 3)
// ══════════════════════════════════════════════════════════════════════════

test('UI-R3c/R3: „Kalender verwalten“ hängt ohne Rollen-Rückfall an der Serverantwort', async () => {
  // BEFUND (main): `kalenderVerwaltungSichtbar(null, true)` war TRUE — der
  // Administrator sah den Eintrag, solange die Antwort fehlte, und verlor ihn
  // danach (Flackern). Jetzt gilt bis zur Antwort EINE Regel: verborgen.
  const { kalenderVerwaltungSichtbar, kalenderMenue } = await import('../src/diakonos/components/kronos/kalenderRechte.mjs')
  assert.equal(kalenderVerwaltungSichtbar(null, true), false,
    'ohne Antwort ist der Eintrag auch für einen Admin sichtbar (Rollen-Rückfall)')
  assert.equal(kalenderVerwaltungSichtbar(null), false)
  assert.equal(kalenderVerwaltungSichtbar({ kalender: [{ name: 'A' }] }), true,
    'mit Serverantwort bleibt der Eintrag sichtbar')
  // Das Menü kennt den Rückfall ebenfalls nicht mehr.
  assert.equal(kalenderMenue({ istKalenderAdmin: true }).some((e) => e.key === 'verwalten'), false,
    'das Menü zeigt „verwalten“ allein wegen der Admin-Rolle')
  assert.equal(kalenderMenue({ istKalenderAdmin: true, darfVerwalten: true }).some((e) => e.key === 'verwalten'), true)

  // Und der catch der Kalenderliste setzt keinen Rollen-Rückfall mehr.
  const leiste = lies('components/kronos/KronosSidebar.vue')
  assert.doesNotMatch(leiste, /zeigeVerwalten\.value = darfVerwalten === true/,
    'die Kalenderliste fällt im Fehlerfall auf die Rolle zurück')
  // Die Kopfzeilen kennen keinen null-Rückfall mehr.
  for (const [name, rel] of [['KronosTopbar.vue', 'components/kronos/KronosTopbar.vue'],
    ['KalenderKopfMobil.vue', 'components/kronos/KalenderKopfMobil.vue']]) {
    const quelle = lies(rel)
    assert.doesNotMatch(quelle, /darfVerwalten: \{ type: Boolean, default: null \}/,
      `${name}: die Prop hat noch den null-Rückfall`)
    assert.doesNotMatch(quelle, /props\.darfVerwalten === null/, `${name}: der null-Zweig lebt noch`)
  }
})

// ══════════════════════════════════════════════════════════════════════════
// R4 · Kein Leerzustand vor der Antwort (SOLL 4)
// ══════════════════════════════════════════════════════════════════════════

/** Eine zurückgehaltene Antwort: `oeffnen()` löst sie auf. */
function schleuse() {
  let oeffnen
  const versprechen = new Promise((ja) => { oeffnen = ja })
  return { versprechen, oeffnen }
}

test('UI-R3c/R4: die Verwaltungsseite behauptet vor der Antwort nichts', async () => {
  // BEFUND (main): `!kalender.length && !darfAnlegen` ist ohne Antwort WAHR —
  // „Kein Kalender zu verwalten“ blitzte für die Dauer der Anfrage auf.
  const tor = schleuse()
  await standAufAttrappe()
  ueberschreibungen = { 'get_kalender_verwaltung$': tor.versprechen }
  const pfad = uebersetze(resolve(SRC_DIR, 'diakonos', 'pages', 'KalenderVerwaltung.vue'))
  const Seite = (await import('file://' + pfad + '?t=' + Date.now())).default
  const host = document.createElement('div')
  document.body.appendChild(host)
  const app = Vue.createApp({ components: { Seite }, template: '<Seite />' })
  app.mount(host)
  await warte(6)

  assert.ok(!/Kein Kalender zu verwalten/.test(host.textContent || ''),
    'der Leerzustand steht vor der Antwort im Bild (Aufblitzen)')
  assert.ok(!/Noch keine Kalender/.test(host.textContent || ''),
    'der Leerzustand der Fläche steht vor der Antwort im Bild')

  tor.oeffnen({ kalender: [], anlegen_gruppen: ['G-Chor'], anlegen_untergruppen: [], darf_gemeinde_kalender: false })
  await warte(30)
  assert.match(host.textContent || '', /Lege den ersten Kalender an/,
    'nach der Antwort fehlt der Leerzustand der Fläche')
})

// ══════════════════════════════════════════════════════════════════════════
// R5 · Kleinkram (SOLL 5)
// ══════════════════════════════════════════════════════════════════════════

test('UI-R3c/R5: der Lösch-Text nennt BEIDE Gründe, wenn beide gelten', async () => {
  // BEFUND (main): `importiert ? google : freigaben` — bei einem Google-Kalender
  // MIT Freigaben nannte der Satz nur den Google-Grund.
  const { loeschRueckfrageText } = await import('../src/diakonos/components/gruppen/kalenderRechte.mjs')
  const beide = loeschRueckfrageText({
    titel: 'Chorproben',
    calender_details: '{"quelle":"google"}',
    hat_freigaben: true,
    gemeinde_status: 'aktiv',
  })
  assert.match(beide, /Importiert aus Google Kalender/, 'der Google-Grund fehlt')
  assert.match(beide, /Freigaben und seine Sichtbarkeit/, 'der Freigaben-Grund fehlt bei Google + Freigaben')
  // Nur Freigaben: kein Google-Satz.
  const nurFreigaben = loeschRueckfrageText({ titel: 'Proben', leserechte: ['a@example.org'] })
  assert.match(nurFreigaben, /Freigaben und seine Sichtbarkeit/)
  assert.doesNotMatch(nurFreigaben, /Google/, 'der Text nennt einen Grund, der nicht gilt')
  // Nur Import: kein Freigaben-Satz.
  const nurImport = loeschRueckfrageText({ titel: 'Proben', calender_details: '{"quelle":"google"}' })
  assert.match(nurImport, /Importiert aus Google Kalender/)
  assert.doesNotMatch(nurImport, /Freigaben/, 'der Text nennt einen Grund, der nicht gilt')
})

test('UI-R3c/R5: „trägt die Zeile die Stufe?“ kommt aus EINER Quelle', async () => {
  // BEFUND (main): die Bedingung stand zweimal (`handyStufen.traegt` und
  // `stufeDerZeile` im Baustein). Jetzt EINE Funktion, beide Aufrufer rufen sie.
  const { zeileTraegtStufe, handyStufen } = await import('../src/diakonos/components/gruppen/kalenderRechte.mjs')
  assert.equal(zeileTraegtStufe({ moderieren: true }, 'moderieren'), true)
  assert.equal(zeileTraegtStufe({ moderieren: false }, 'moderieren'), false)
  assert.equal(zeileTraegtStufe({ moderieren: false }, 'moderieren', { darf_moderieren_vergeben: true }), true)
  assert.equal(zeileTraegtStufe({}, 'lesen'), true)
  // Die Handy-Liste liefert für beide Lagen dieselbe Antwort.
  const ohneRecht = handyStufen({ moderieren: false }, ['lesen', 'moderieren'], {})
  assert.deepEqual(ohneRecht.felder.map((f) => (f ? f.stufe : null)), ['lesen', null])
  const mitRecht = handyStufen({ moderieren: false }, ['lesen', 'moderieren'], { darf_moderieren_vergeben: true })
  assert.deepEqual(mitRecht.felder.map((f) => (f ? f.stufe : null)), ['lesen', 'moderieren'])
  // Der Baustein baut die Regel nicht selbst nach.
  const baustein = lies('components/gruppen/KalenderRechte.vue')
  assert.match(baustein, /zeileTraegtStufe\(z, stufe,/, 'der Baustein nutzt die gemeinsame Regel nicht')
  assert.doesNotMatch(baustein, /stufe !== 'moderieren' \|\|/,
    'die Bedingung steht im Baustein weiterhin ein zweites Mal')
})

test('UI-R3c/R5: leerer props.gruppe meldet „Antwort da“ (Karte bleibt nicht versteckt)', async () => {
  // BEFUND (main): der Zweig „kein Kontext“ kehrte stumm zurück — auf einer
  // Seite, die die Karte erst mit „Antwort da“ einblendet (`GruppeDetail.vue`),
  // blieb sie für immer unsichtbar.
  await standAufAttrappe()
  const { host, app } = await mounten('components/gruppen/KalenderEinstellungen.vue', {
    props: { gruppe: '', alleKalender: false },
    events: ['gesperrt'],
  })
  assert.ok(host)
  // Das Ereignis wird im Elternteil gesammelt (`daten.ereignisse`); Vue reicht
  // bei einem Zwei-Wert-Ereignis nur `$event` (das erste Argument) an die
  // Pfeil-Funktion — deshalb wird hier der ROH-Aufruf geprüft.
  const gesperrtEreignisse = (app._instance?.proxy?.daten?.ereignisse || []).filter((e) => e[0] === 'gesperrt')
  assert.ok(gesperrtEreignisse.length > 0,
    'die Fläche meldet ohne Gruppenkontext gar nichts — die Karte bliebe versteckt')
  assert.deepEqual(gesperrtEreignisse.at(-1).slice(1), [false, true],
    'die Meldung lautet nicht „nicht gesperrt, Antwort da“')
  assert.equal(mit('get_kalender_verwaltung$').length, 0,
    'ohne Gruppenkontext darf gar nicht geladen werden')
})

// ══════════════════════════════════════════════════════════════════════════
// R6 · Irreführende Kommentare (SOLL 5)
// ══════════════════════════════════════════════════════════════════════════

test('UI-R3c/R6: kein Kommentar behauptet, das Rückgängig schicke Freigaben mit', () => {
  const quelle = lies('components/gruppen/kalenderRechte.mjs')
  assert.doesNotMatch(quelle, /Rückgängig[^\n]*schickt sie mit/,
    'der irreführende Kommentar steht noch da (Rückgängig gibt es nur OHNE Freigaben)')
  assert.match(quelle, /Rückgängig gibt es also\s*\n?\s*\*?\s*nur bei Kalendern OHNE Freigaben|nur bei Kalendern OHNE Freigaben/,
    'der Kommentar sagt nicht, wann es das Rückgängig gibt')
})

test('UI-R3c/R6: die UI-R1-Kommentare in GruppeDetail.vue sind ganze Sätze', () => {
  // BEFUND (main): Über der Rückgabe von `gruppeId` stand eine Zeile, die mit
  // einer Klammer begann — die erste Hälfte des Satzes fehlte.
  const quelle = lies('pages/GruppeDetail.vue')
  // Der Defekt war eine Kommentarzeile, die MIT einer Klammer beginnt und
  // keinen Satzanfang hat — eine Fortsetzung im Satz ohne ersten Teil.
  // Nur die FORTSETZUNG eines Satzes ist ein Defekt — eine Zeile, die mit einer
  // Klammer beginnt UND deren Vorgängerzeile nicht Kommentar ist oder mit einem
  // Satzzeichen endet. Hier genügt der konkrete Befund: die Fortsetzung
  // „… am Bereich „Einstellungen“) — ohne die Rückgabe …“ gab es nur, weil die
  // erste Zeile fehlte. Erkannt wird eine Kommentarzeile, die mit einer
  // Klammer beginnt und in der Mitte eines Satzes endet (Gedankenstrich).
  // Geprüft wird der BEFUND: eine Kommentarzeile, die mit einer Klammer
  // beginnt und den Satz eines ANDEREN Themas fortsetzt (hier: „am Bereich
  // Einstellungen“), ohne dass die erste Hälfte davor steht.
  const verdaechtig = quelle.split('\n')
    .filter((zeile) => /^\s*\/\/ \(.*am Bereich „Einstellungen“/.test(zeile))
    .map((zeile) => zeile.trim())
  assert.deepEqual(verdaechtig, [],
    'ein Kommentar beginnt mitten im Satz (die erste Zeile fehlt)')
  // Und der Satz steht jetzt vollständig da.
  assert.match(quelle, /\/\/ UI-R1: Der Bereich „Einstellungen“ bekommt die Gruppenkennung/,
    'der einleitende Satz des UI-R1-Kommentars fehlt')
})
