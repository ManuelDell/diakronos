/**
 * UX2e5 — Laufender Test mit der ECHTEN Bibliothek: „⋯" je Termin in der
 * Terminliste, robust gegen jedes Neuladen.
 *
 * WARUM MIT jsdom UND DER ECHTEN @event-calendar/build: Der Befund aus UX2e3
 * trat nur mit dem echten Raster auf (nach `refetchEvents()` baut die
 * Bibliothek ihre Zeilen neu; ein Doppel zeigt das nicht). Der Test hängt das
 * Bauteil KronosCalendar.vue deshalb mit `@event-calendar/build` aus
 * node_modules ein — so, wie es im Betrieb läuft.
 *
 * Geprüft wird:
 *   A. Liste mit 3 Terminen an einem Tag + 1 ganztägigen Termin → je Termin
 *      GENAU EIN Knopf, direkt hinter SEINER Zeile (Geschwister im `.ec-day`),
 *      im `article` steht kein Knopf.
 *   B. `refetchEvents()` mit denselben Daten → unverändert (kein Knopf zu viel,
 *      keine Waisen).
 *   C. Termin gelöscht → sein Knopf ist fort, keine Waise.
 *   D. Termin hinzugefügt/umsortiert → die Zuordnung stimmt (Knopf hinter der
 *      richtigen Zeile, `data-event-id` = Termin-Kennung).
 *   E. Ansichtswechsel → 0 Knöpfe übrig, kein ResizeObserver je Knopf.
 *   F. Ein Klick auf „⋯" öffnet das Menü; „Ansehen" meldet den richtigen Termin
 *      an die Seite (`terminAktion`).
 *
 * Lauf: node --test tests/ux2e5-terminliste-aktionen.test.mjs   (cwd = frontend/)
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, mkdtempSync, writeFileSync } from 'node:fs'
import { join, basename, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

/* ── jsdom zuerst, damit die Bibliothek und Vue ein DOM vorfinden ──────── */
let JSDOM
try {
  ({ JSDOM } = await import('jsdom'))
} catch {
  console.log('[ux2e5] übersprungen: kein jsdom vorhanden (Mount-Test braucht ein DOM)')
  process.exit(0)
}
const dom = new JSDOM('<!doctype html><html><head></head><body></body></html>', {
  pretendToBeVisual: true,
  runScripts: 'outside-only',
  url: 'http://localhost/',
})
const W = dom.window
for (const k of ['window', 'document', 'Node', 'Element', 'HTMLElement', 'SVGElement', 'Event',
  'MouseEvent', 'KeyboardEvent', 'CustomEvent', 'navigator', 'location', 'localStorage',
  'sessionStorage', 'getComputedStyle', 'requestAnimationFrame', 'cancelAnimationFrame',
  'HTMLDivElement', 'Text', 'Comment', 'DocumentFragment', 'FocusEvent']) {
  if (W[k]) Object.defineProperty(globalThis, k, { value: W[k], configurable: true, writable: true })
}
// Die Bibliothek rechnet mit `Date`-Objekten ihres FENSTERS (`e instanceof
// Date` gegen das Date von jsdom) — deshalb gilt hier das Date aus jsdom.
globalThis.Date = W.Date
W.matchMedia = W.matchMedia || (() => ({
  matches: false, addListener() {}, removeListener() {},
  addEventListener() {}, removeEventListener() {},
}))

/* ── ResizeObserver zählen: es darf KEINEN je Knopf geben ──────────────── */
let beobachterAnzahl = 0
const RO = class {
  constructor() { beobachterAnzahl += 1 }
  observe() {} unobserve() {} disconnect() {}
}
W.ResizeObserver = RO
globalThis.ResizeObserver = RO

/**
 * Die ECHTE Bibliothek @event-calendar/build — normal `importiert`, wie im
 * Betrieb (Vite bündelt sie ebenfalls als Modul; ein `eval` im jsdom-Fenster
 * hätte für sich genommen schon zwei Vue-Laufzeiten erzeugt, und die
 * Bibliothek zeichnet dann BEI JEDEM INHALTSTÜCK in den Inhalt statt in den
 * Rahmen). Der Bündel-Datei ist es gleich: sie belegt nur ein globales
 * `EventCalendar` (UMD) — nach dem Laden steht es auf `globalThis`.
 *
 * Die Bibliothek muss VOR Vue laufen: sie lädt ihre eigene Svelte-Laufzeit,
 * deren Element-Erkennung `nodeName.includes('-')` verlangt — mit jsdoms
 * `HTMLElement` global (statt `Element`) bricht sie dort ab.
 *
 * Außerdem misst sie beim Aufbau die Seite
 * (ResizeObserver einer noch leeren, künstlichen Wurzel). Mit dem, was jsdom
 * vorher als `window`/`document` ablegt, findet sie ihre Rahmen-Klasse
 * (`.ec-event-body`) nicht und zeichnet deshalb in jedes Inhaltsstück statt
 * in den Rahmen — dann steht der Termin-Titel NICHT im `article`, sondern in
 * einem eigenen Knoten daneben.
 */
globalThis.window = W
globalThis.document = W.document
globalThis.HTMLElement = W.HTMLElement
globalThis.Element = W.Element
// Wie das Bündel sein Ergebnis abgibt, hängt davon ab, ob der Loader die
// Datei als Modul (dann `export default`, ESM) oder als Skript (dann
// `var EventCalendar = …` im globalen Objekt) behandelt: das Bündel ist NICHT
// als ESM gekennzeichnet. Beide Wege werden bedient.
const EC_PFAD = new URL('../node_modules/@event-calendar/build/dist/event-calendar.min.js',
  import.meta.url).pathname
let WECHT = null
try {
  const EC_NS = await import(pathToFileURL(EC_PFAD).href)
  WECHT = EC_NS.default || EC_NS
} catch {
  WECHT = null
}
if (!WECHT || typeof WECHT.create !== 'function') {
  W.eval(readFileSync(EC_PFAD, 'utf8'))
  WECHT = W.EventCalendar || globalThis.EventCalendar
}
assert.ok(WECHT && typeof WECHT.create === 'function', 'die echte Bibliothek ist geladen')

/* ── SFC-Uebersetzer (Vorlage: tests/ux2e4-…) ──────────────────────────── */
const Vue = await import('vue')
const { parse, compileScript, compileTemplate } = await import('vue/compiler-sfc')
const TMP = mkdtempSync(join(require_tmpdir(), 'ux2e5-echt-'))
function require_tmpdir() {
  return process.env.TMPDIR || '/tmp'
}
const cache = new Map()
const VUE_URL = import.meta.resolve('vue')
const QUELLE = new URL('../src/diakonos/components/kronos/KronosCalendar.vue', import.meta.url)

function sfc(abs) {
  if (cache.has(abs)) return cache.get(abs)
  const filename = basename(abs)
  const { descriptor } = parse(readFileSync(abs, 'utf8'), { filename })
  const script = compileScript(descriptor, { id: filename })
  const template = compileTemplate({
    source: descriptor.template.content,
    filename,
    id: filename,
    compilerOptions: { bindingMetadata: script.bindings },
  })
  let code = script.content.replace(/\nexport default /, '\nconst __sfc__ = ')
    + '\n' + template.code.replace(/^export function render/m, 'function render')
    + '\n__sfc__.render = render\nexport default __sfc__\n'
  code = code.replace(/from\s+['"]vue['"]/g, `from '${VUE_URL}'`)
  code = code.replace(/from\s+['"](\.[^'"]+)['"]/g, (_t, pfad) => {
    const zielAbs = resolve(abs, '..', pfad)
    return zielAbs.endsWith('.vue')
      ? `from '${pathToFileURL(sfc(zielAbs)).href}'`
      : `from '${pathToFileURL(zielAbs).href}'`
  })
  const ziel = resolve(TMP, filename + cache.size + '.mjs')
  writeFileSync(ziel, code)
  cache.set(abs, ziel)
  return ziel
}

/**
 * KronosCalendar.vue, aber OHNE das Stylesheet der Bibliothek und mit dem
 * schon geladenen `EventCalendar` des Fensters (ein zweites Laden des Bündels
 * würde zwei verschiedene Bibliotheks-Instanzen erzeugen).
 */
function ladeKalender() {
  let code = readFileSync(sfc(QUELLE.pathname), 'utf8')
  assert.match(code, /from\s+'@event-calendar\/build'/, 'das Bauteil holt die Bibliothek')
  const bruecke = 'data:text/javascript,' + encodeURIComponent(
    'const C = globalThis.__EC_ECHT; export default C; export const create = C.create;')
  code = code.replace(/from\s+'@event-calendar\/build'/g, `from ${JSON.stringify(bruecke)}`)
  code = code.replace(/import\s+'@event-calendar\/build\/dist\/event-calendar\.min\.css'/g, '')
  const ziel = resolve(TMP, 'kalender-echt.mjs')
  writeFileSync(ziel, code)
  return ziel
}
globalThis.__EC_ECHT = WECHT

/* ── Server-Ersatz: dieselben Adressen, die das Bauteil fragt ──────────── */
let TERMINE = []
let holen = 0
globalThis.fetch = async (adresse) => {
  const url = String(adresse)
  holen += 1
  // `dkDaten` ist der Weg, den `apiAntwortPruefen` liest (ohne Body-Parsen).
  const antwort = (message) => ({ ok: true, status: 200, dkDaten: { message } })
  if (url.includes('get_calendar_events')) return antwort(JSON.parse(JSON.stringify(TERMINE)))
  return antwort([])
}

const tick = (ms = 40) => new Promise((r) => setTimeout(r, ms))

/**
 * REVIEW UX2e5/1: Nach der letzten Prüfung wird das jsdom-Fenster GESCHLOSSEN.
 * Sonst hält der Prozess offen: die Bibliothek (vue-router in der Seite) legt
 * beim Mount einen Abräum-Timer von jsdom an (`pretendToBeVisual`), und die
 * Bibliothek beobachtet das Fenster weiter. Ein `node --test` ohne
 * `--test-force-exit` bliebe dann für immer stehen — genau das ließ den
 * Image-Build in der Node-Testzeile hängen, obwohl alle Fälle grün waren.
 * `window.close()` stoppt alle Timer des Fensters (jsdom, `stopAllTimers`),
 * damit endet die Datei in wenigen Sekunden.
 */
test.after(() => {
  try { dom.window.close() } catch { /* schon zu */ }
})

function termin(id, titel, start, ende, extra = {}) {
  return { id, title: titel, start, end: ende, backgroundColor: '#3355aa', extendedProps: { id, name: id, ...extra } }
}

async function kalenderMit(terme, { view = 'listWeek', viewMode = 'edit' } = {}) {
  TERMINE = terme
  holen = 0
  beobachterAnzahl = 0
  const KronosCalendar = (await import(pathToFileURL(ladeKalender()).href + '?v=' + Math.random())).default
  const meldungen = []
  const app = Vue.createApp({
    components: { KronosCalendar },
    template: '<KronosCalendar ref="kal" :viewMode="viewMode" @terminAktion="merken" />',
    data: () => ({ viewMode }),
    methods: { merken(ereignis) { meldungen.push(ereignis) } },
  })
  app.config.warnHandler = () => {}
  app.config.errorHandler = (e) => { console.log('[fehler]', String(e?.message || e)) }
  const host = document.createElement('div')
  host.style.height = '900px'
  document.body.appendChild(host)
  const wurzel = app.mount(host)
  const vm = wurzel.$refs.kal
  await tick(120)
  vm.changeView(view, new Date('2026-11-04T12:00:00'))
  await tick(150)
  // Aufräumen: ein Kalender je Test (die Bibliothek hängt an window/globalen
  // Zuhörern; zwei gleichzeitig würden sich gegenseitig neu zeichnen).
  const schliessen = () => { try { app.unmount() } catch { /* schon weg */ } host.remove() }
  return { app, close: schliessen, vm, host, meldungen, wurzel }
}

/** Der Zeitraum eines Tages mit den erwarteten Terminen. */
const TAG = '2026-11-04'
function dreiPlusGanztags(mehr = []) {
  return [
    termin('t1', 'Chorprobe', `${TAG}T09:00:00`, `${TAG}T10:00:00`),
    termin('t2', 'Jugendkreis', `${TAG}T12:00:00`, `${TAG}T13:00:00`),
    termin('t3', 'Hauskreis Süd', `${TAG}T19:00:00`, `${TAG}T20:00:00`),
    termin('t4', 'Gemeindefest', TAG, TAG, { allDay: true }),
    ...mehr,
  ]
}

const knopfSel = '.kronos-liste-aktionen-halter .dk-ui-aktionen-ausloeser'

/** Prüft die Kernforderung: genau ein Knopf je Zeile, direkt dahinter, gleiche Lage. */
function pruefeZuordnung(wo) {
  const zeilen = Array.from(document.querySelectorAll('.ec-list .ec-day article.ec-event'))
  assert.ok(zeilen.length > 0, `${wo}: die Liste zeigt Zeilen`)
  const knoepfe = Array.from(document.querySelectorAll(knopfSel))
  assert.equal(knoepfe.length, zeilen.length,
    `${wo}: je Termin genau ein „⋯" (${zeilen.length} Zeilen, ${knoepfe.length} Knöpfe)`)
  for (const zeile of zeilen) {
    const id = zeile.getAttribute('data-event-id')
    assert.ok(id, `${wo}: die Zeile trägt ihre Termin-Kennung`)
    const nachbar = zeile.nextElementSibling
    assert.ok(nachbar?.classList?.contains('kronos-liste-aktionen-halter'),
      `${wo}: direkt hinter Zeile ${id} steht der „⋯"-Halter (nicht: ${nachbar?.className})`)
    assert.equal(nachbar.parentElement, zeile.parentElement,
      `${wo}: Knopf und Zeile liegen in derselben Ebene (Geschwister)`)
    assert.equal(nachbar.getAttribute('data-termin'), id,
      `${wo}: der Knopf gehört zu SEINER Zeile (${id})`)
    const knopf = nachbar.querySelector('.dk-ui-aktionen-ausloeser')
    assert.ok(knopf, `${wo}: der Halter enthält den „⋯"-Auslöser`)
    assert.match(knopf.getAttribute('aria-label') || '', /^Aktionen für /,
      `${wo}: der Knopf ist beschriftet (Vorlesehilfe)`)
    assert.equal(zeile.querySelector('button'), null,
      `${wo}: im article steht KEIN Knopf (kein verschachteltes Bedienelement)`)
  }
  // Keine Waisen: jeder Halter hat eine Zeile davor.
  for (const halter of document.querySelectorAll('.kronos-liste-aktionen-halter')) {
    const davor = halter.previousElementSibling
    assert.ok(davor?.matches('article.ec-event'), `${wo}: kein Waisen-Knopf ohne Zeile`)
  }
}

/* ── A · Grundlage: ein Knopf je Termin, direkt hinter seiner Zeile ────── */
test('UX2e5 · Liste: je Termin genau ein „⋯" direkt hinter seinem Artikel', async () => {
  const { close } = await kalenderMit(dreiPlusGanztags())
  pruefeZuordnung('frisch geladen')
  // Der ganztägige Termin steht in derselben Tagesliste.
  const ganztags = Array.from(document.querySelectorAll('.ec-list article.ec-event'))
    .find((z) => z.getAttribute('data-event-id') === 't4')
  assert.ok(ganztags, 'der ganztägige Termin ist in der Liste')
  assert.ok(ganztags.nextElementSibling?.classList.contains('kronos-liste-aktionen-halter'),
    'auch der ganztägige Termin hat seinen Knopf')
  close()
})

/* ── B · Neuladen mit denselben Daten ändert nichts ───────────────────── */
test('UX2e5 · refetchEvents (gleiche Daten): unverändert, keine Doppel-Knöpfe', async () => {
  const { close, vm } = await kalenderMit(dreiPlusGanztags())
  const vorher = document.querySelectorAll(knopfSel).length
  vm.refetchEvents(); await tick(150)
  pruefeZuordnung('nach dem 1. Neuladen')
  vm.refetchEvents(); await tick(150)
  pruefeZuordnung('nach dem 2. Neuladen')
  assert.equal(document.querySelectorAll(knopfSel).length, vorher,
    'die Zahl der Knöpfe bleibt gleich')
  assert.ok(holen >= 2, 'die Liste hat wirklich neu geladen')
  close()
})

/* ── C · Löschen: sein Knopf ist fort, keine Waise ────────────────────── */
test('UX2e5 · Termin gelöscht: sein „⋯" ist weg, keine Waise', async () => {
  const { close, vm } = await kalenderMit(dreiPlusGanztags())
  TERMINE = TERMINE.filter((t) => t.id !== 't2')
  vm.refetchEvents(); await tick(150)
  pruefeZuordnung('nach dem Löschen')
  assert.equal(document.querySelector('article[data-event-id="t2"]'), null, 'der Termin ist fort')
  const kennungen = Array.from(document.querySelectorAll('.kronos-liste-aktionen-halter'))
    .map((h) => h.getAttribute('data-termin'))
  assert.ok(!kennungen.includes('t2'), 'kein Knopf des gelöschten Termins (keine Waise)')
  assert.deepEqual(kennungen.sort(), ['t1', 't3', 't4'], 'die übrigen Knöpfe bleiben')
  close()
})

/* ── D · Hinzufügen und Umsortieren: die Zuordnung stimmt ─────────────── */
test('UX2e5 · Termin hinzugefügt/umsortiert: Knopf bleibt bei seiner Zeile', async () => {
  const { close, vm } = await kalenderMit(dreiPlusGanztags())
  // Neu: früher Termin (muss in der Liste nach oben rutschen).
  TERMINE = dreiPlusGanztags([termin('t0', 'Frühgebet', `${TAG}T06:00:00`, `${TAG}T06:30:00`)])
  vm.refetchEvents(); await tick(150)
  pruefeZuordnung('nach dem Hinzufügen')
  // Umsortieren: „Hauskreis Süd" wandert an den Anfang des Tages.
  TERMINE = TERMINE.map((t) => (t.id === 't3'
    ? { ...t, start: `${TAG}T05:00:00`, end: `${TAG}T05:30:00` }
    : t))
  vm.refetchEvents(); await tick(150)
  pruefeZuordnung('nach dem Umsortieren')
  // Konkret: der Knopf hinter t3 gehört zu t3 — im DOM und im Menü.
  const zeileT3 = document.querySelector('article[data-event-id="t3"]')
  assert.equal(zeileT3.nextElementSibling.getAttribute('data-termin'), 't3',
    'der Knopf hinter „Hauskreis Süd" ist der von „Hauskreis Süd"')
  close()
})

/* ── E · Ansichtswechsel: nichts bleibt übrig ─────────────────────────── */
test('UX2e5 · Ansichtswechsel: 0 Knöpfe, kein Beobachter je Knopf', async () => {
  const { close, vm } = await kalenderMit(dreiPlusGanztags())
  // Die Bibliothek setzt JE KALENDER einen Beobachter (nicht je Knopf). Ein
  // Wechsel darf keinen JE KNOPF hinzufügen; die Bibliothek selbst darf sich
  // beim Aufbau eines neuen Rasters neu einrichten.
  const vorherBeobachter = beobachterAnzahl
  const knopfZahl = document.querySelectorAll(knopfSel).length
  assert.ok(knopfZahl >= 4, 'für die Probe stehen mehrere Knöpfe in der Liste')
  vm.changeView('dayGridMonth'); await tick(150)
  assert.equal(document.querySelectorAll('.kronos-liste-aktionen-halter').length, 0,
    'im Monatsraster steht kein „⋯"')
  assert.equal(document.querySelectorAll('.ec .dk-ui-aktionen-ausloeser').length, 0,
    'und kein Auslöser')
  vm.changeView('listWeek', new Date('2026-11-04T12:00:00')); await tick(200)
  pruefeZuordnung('zurück in der Liste')
  // Je Knopf (4 Termine) entstünde bei „ein Beobachter je Knopf" ein viel
  // größerer Zuwachs; die Bibliothek selbst richtet beim neuen Raster
  // höchstens einen ein.
  assert.ok(beobachterAnzahl - vorherBeobachter < 4,
    `kein Beobachter je Knopf (+${beobachterAnzahl - vorherBeobachter})`)
  close()
})

/* ── F · Menü: Klick öffnet, „Ansehen" meldet den richtigen Termin ────── */
test('UX2e5 · „⋯" öffnet das Menü und meldet den Termin der Zeile', async () => {
  const { close, meldungen } = await kalenderMit(dreiPlusGanztags())
  const zeileT1 = document.querySelector('article[data-event-id="t1"]')
  const knopf = zeileT1.nextElementSibling.querySelector('.dk-ui-aktionen-ausloeser')
  knopf.click()
  await tick(120)
  const menue = document.querySelector('.dk-ui-aktionen-menue')
  assert.ok(menue, 'das Menü ist offen')
  assert.deepEqual(
    Array.from(menue.querySelectorAll('.dk-ui-aktionen-text')).map((e) => e.textContent.trim()),
    ['Bearbeiten', 'Ansehen', 'Löschen'],
    'die Einträge stehen in dieser Reihenfolge (Gefährliches zuletzt)',
  )
  const eintraege = Array.from(menue.querySelectorAll('.dk-ui-aktionen-eintrag'))
  // Ein echter Mausklick (jsdom: `HTMLElement.click()` ohne `cancelable`
  // erzeugt ein Ereignis, das sich nicht abbrechen lässt).
  eintraege.find((e) => e.textContent.trim() === 'Ansehen')
    .dispatchEvent(new window.MouseEvent('click', { bubbles: true, cancelable: true }))
  await tick(120)
  assert.equal(meldungen.length, 1,
    `die Seite bekommt genau eine Meldung (${meldungen.length})`)
  assert.equal(meldungen[0].key, 'ansehen', 'der Eintrag kommt als „ansehen" an')
  assert.equal(meldungen[0].terminId, 't1', 'und zwar für DIESEN Termin')
  assert.equal(meldungen[0].termin.title, 'Chorprobe', 'mit Titel aus der Zeile')
  close()
})

/* ── G · Speicher/Neuladen: kein Rahmen bleibt zurück ────────────────────
 * REVIEW UX2e5/2: Bei jedem Neuladen baut die Bibliothek ihre Zeilen neu. Der
 * Halter der alten Zeile hing danach nicht mehr am Dokument, sein Vue-Rahmen
 * (samt Menü-Zuhörern) blieb aber gemerkt — nach ein paar Neuladen sammelten
 * sich Rahmen an. Geprüft: 3× hin/zurück (jedes Blättern lädt neu) und ein
 * Ansichtswechsel → Zahl der Rahmen == Zahl der sichtbaren Termine.
 */
test('UX2e5 · 3× blättern + Ansichtswechsel: kein „⋯"-Rahmen bleibt übrig', async () => {
  const { close, vm } = await kalenderMit(dreiPlusGanztags())
  for (let i = 0; i < 3; i += 1) {
    vm.next(); await tick(150)
    vm.prev(); await tick(150)
  }
  vm.refetchEvents(); await tick(150)
  const sichtbar = document.querySelectorAll('.ec-list .ec-day article.ec-event').length
  pruefeZuordnung('nach 3× blättern')
  assert.equal(vm.anzahlRahmen(), sichtbar,
    `je sichtbarem Termin genau ein Rahmen (${vm.anzahlRahmen()} Rahmen, ${sichtbar} Termine)`)
  // Ansichtswechsel und zurück: die Rahmen der Liste sind weg, danach wieder
  // genau einer je Termin (kein Altbestand).
  vm.changeView('dayGridMonth'); await tick(150)
  assert.equal(vm.anzahlRahmen(), 0, 'im Monatsraster hängt kein Rahmen')
  vm.changeView('listWeek', new Date('2026-11-04T12:00:00')); await tick(200)
  const wieder = document.querySelectorAll('.ec-list .ec-day article.ec-event').length
  pruefeZuordnung('zurück in der Liste')
  assert.equal(vm.anzahlRahmen(), wieder,
    `nach dem Zurückwechseln je Termin genau ein Rahmen (${vm.anzahlRahmen()} / ${wieder})`)
  close()
})

/* ── H · Ansehen-Modus: das Menü bietet nur „Ansehen" ────────────────────
 * REVIEW UX2e5/3: Ohne Schreibrecht ist „Ansehen" die einzige Handlung — wie
 * beim Klick auf die Zeile (onEventClick in Kalender.vue).
 */
test('UX2e5 · Ansehen-Modus: im Menü steht nur „Ansehen"', async () => {
  const { close, meldungen } = await kalenderMit(dreiPlusGanztags(), { viewMode: 'view' })
  const zeile = document.querySelector('article[data-event-id="t1"]')
  assert.ok(zeile, 'die Zeile steht in der Liste')
  zeile.nextElementSibling.querySelector('.dk-ui-aktionen-ausloeser').click()
  await tick(120)
  const menue = document.querySelector('.dk-ui-aktionen-menue')
  assert.ok(menue, 'das Menü ist offen')
  assert.deepEqual(
    Array.from(menue.querySelectorAll('.dk-ui-aktionen-text')).map((e) => e.textContent.trim()),
    ['Ansehen'],
    'nur „Ansehen" — kein Bearbeiten, kein Löschen',
  )
  const eintrag = menue.querySelector('.dk-ui-aktionen-eintrag')
  eintrag.dispatchEvent(new window.MouseEvent('click', { bubbles: true, cancelable: true }))
  await tick(120)
  assert.equal(meldungen.length, 1, 'die Seite bekommt genau eine Meldung')
  assert.equal(meldungen[0].key, 'ansehen', 'und zwar „ansehen"')
  assert.equal(meldungen[0].terminId, 't1', 'für den Termin der Zeile')
  close()
})

/* ── I · Bearbeiten-Modus: das Menü bietet alle drei Einträge ──────────── */
test('UX2e5 · Bearbeiten-Modus: Menü mit Bearbeiten, Ansehen, Löschen', async () => {
  const { close } = await kalenderMit(dreiPlusGanztags())
  const zeile = document.querySelector('article[data-event-id="t1"]')
  zeile.nextElementSibling.querySelector('.dk-ui-aktionen-ausloeser').click()
  await tick(120)
  const menue = document.querySelector('.dk-ui-aktionen-menue')
  assert.deepEqual(
    Array.from(menue.querySelectorAll('.dk-ui-aktionen-text')).map((e) => e.textContent.trim()),
    ['Bearbeiten', 'Ansehen', 'Löschen'],
    'alle drei Einträge (Gefährliches zuletzt)',
  )
  close()
})

/* ── J · Löschen meldet „Löschen" samt Termin-Datensatz ─────────────────
 * REVIEW UX2e5/4: Gelöscht wird in Kalender.vue direkt (Papierkorb +
 * Rückgängig), NICHT über den Bearbeiten-Dialog. Das Widget muss dafür den
 * vollständigen Datensatz mitliefern — inklusive `name` (Server-Kennung).
 */
test('UX2e5 · „Löschen" meldet den Termin samt Server-Kennung', async () => {
  const { close, meldungen } = await kalenderMit(dreiPlusGanztags())
  const zeile = document.querySelector('article[data-event-id="t3"]')
  zeile.nextElementSibling.querySelector('.dk-ui-aktionen-ausloeser').click()
  await tick(120)
  const eintrag = Array.from(document.querySelectorAll('.dk-ui-aktionen-eintrag'))
    .find((e) => e.textContent.trim() === 'Löschen')
  eintrag.dispatchEvent(new window.MouseEvent('click', { bubbles: true, cancelable: true }))
  await tick(120)
  assert.equal(meldungen.length, 1, 'genau eine Meldung')
  assert.equal(meldungen[0].key, 'loeschen', 'der Eintrag kommt als „loeschen" an')
  // Die Server-Kennung reist in `extendedProps.name` (so liefert sie der
  // Server in `get_calendar_events`, und so liest sie `Kalender.vue`).
  assert.equal(meldungen[0].termin.extendedProps?.name, 't3',
    'mit Server-Kennung (`extendedProps.name`) — ohne sie kann die Seite nicht löschen')
  assert.equal(meldungen[0].termin.title, 'Hauskreis Süd', 'und mit dem Titel der Zeile')
  close()
})

/* ── K · Trefferfläche: der „⋯" liegt NICHT über dem Termin ──────────────
 * BEFUND der Browser-Abnahme (07.11.): Der Auslöser füllte mit `width: 100%`
 * die ganze Zeilenbreite. Ein Klick auf den TERMIN traf damit das „⋯"; die
 * Bibliothek bekam den Klick nicht und öffnete stattdessen „Neuer Termin".
 * Der Test hält die Regel am Quelltext fest (jsdom rechnet kein Layout, die
 * gemessene Gegenprobe steht in der Browser-Abnahme): Der Auslöser in der
 * Terminliste ist quadratisch (--control-h, bei pointer: coarse 44 px) und
 * sitzt rechts — nicht über der Zeile.
 */
test('UX2e5 · „⋯"-Auslöser in der Liste: quadratische Trefferfläche, nicht zeilenbreit', () => {
  const quelle = readFileSync(new URL('../src/diakonos/components/kronos/KronosCalendar.vue',
    import.meta.url), 'utf8')
  const regel = quelle.match(/:deep\(\.ec-list \.kronos-liste-aktionen-halter \.dk-ui-aktionen-ausloeser\) \{([^}]*)\}/)
  assert.ok(regel, 'die Regel für den Auslöser in der Liste steht im Bauteil')
  const rumpf = regel[1]
  assert.match(rumpf, /width:\s*var\(--control-h\)/, 'Breite = Klickfläche (--control-h)')
  assert.match(rumpf, /height:\s*var\(--control-h\)/, 'Höhe = Klickfläche (--control-h)')
  assert.match(rumpf, /margin-left:\s*auto/, 'rechtsbündig in der Zeile')
  assert.ok(!/width:\s*100%/.test(rumpf),
    'NICHT zeilenbreit — sonst liegt der Auslöser über dem Termin und schluckt dessen Klicks')
  // Am Handy (pointer: coarse) 44 px — die Vorgabe der Klickflächen.
  const grob = quelle.match(/@media \(pointer: coarse\) \{[\s\S]*?ausloeser\) \{([^}]*)\}/)
  assert.ok(grob, 'die Regel für Zeigegeräte steht im Bauteil')
  assert.match(grob[1], /width:\s*44px/, 'am Handy 44 px breit')
  assert.match(grob[1], /height:\s*44px/, 'am Handy 44 px hoch')
})
