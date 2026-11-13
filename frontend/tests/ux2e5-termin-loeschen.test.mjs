/**
 * UX2e5 — Review-Nacharbeit 07.11.: „Löschen" im „⋯"-Menü eines Termins.
 *
 * WARUM EIGENE DATEI: Die Terminliste (KronosCalendar.vue) meldet nur den
 * Eintrag samt Datensatz (`terminAktion`); was dann passiert, entscheidet die
 * Seite (Kalender.vue). Genau das war der Review-Befund 4: Bei einem
 * EINZELTERMIN öffnete „Löschen" den Bearbeiten-Dialog, statt direkt in den
 * Papierkorb zu gehen (wie im Bearbeiten-Fenster, KronosEventEdit.vue:542).
 *
 * Der Test mountet die ECHTE Kalender.vue in ksdom (jsdom) mit ihren echten
 * Bausteinen und ersetzt nur den Server (`fetch`):
 *   A. Einzeltermin + „Löschen" → EIN Aufruf `event_crud.delete_event` mit der
 *      Server-Kennung; die Seite bietet „Rückgängig" an; der Kalender holt neu
 *      (die Zeile verschwindet ohne Zutun des Nutzers).
 *   B. „Rückgängig" → `event_crud.wiederherstellen_event` mit derselben Kennung.
 *   C. Serientermin + „Löschen" → KEIN Aufruf von `delete_event` (der Umfang
 *      der Serie wird weiterhin im Seriendialog erfragt).
 *   D. ANSEHEN-Modus → das Menü der Liste bietet nur „Ansehen" (Widget), und
 *      ein „Löschen" erreicht keinen Server.
 *
 * Lauf: node --test tests/ux2e5-termin-loeschen.test.mjs   (cwd = frontend/)
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, mkdtempSync, writeFileSync } from 'node:fs'
import { join, basename, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

/* ── jsdom zuerst (Vue und die Seite brauchen ein DOM) ─────────────────── */
let JSDOM
try {
  ({ JSDOM } = await import('jsdom'))
} catch {
  console.log('[ux2e5b] übersprungen: kein jsdom vorhanden (Mount-Test braucht ein DOM)')
  process.exit(0)
}
const dom = new JSDOM('<!doctype html><html><body></body></html>', {
  pretendToBeVisual: true,
  // Das Bündel der Bibliothek belegt ein globales `EventCalendar` (UMD); dafür
  // muss das Fenster Skripte ausführen dürfen (`window.eval`).
  runScripts: 'outside-only',
  url: 'http://localhost/',
})
const W = dom.window
for (const k of ['window', 'document', 'Node', 'Element', 'HTMLElement', 'SVGElement', 'Event',
  'MouseEvent', 'KeyboardEvent', 'CustomEvent', 'navigator', 'location', 'localStorage',
  'sessionStorage', 'getComputedStyle', 'requestAnimationFrame', 'cancelAnimationFrame',
  'HTMLDivElement', 'Text', 'Comment', 'DocumentFragment', 'FocusEvent', 'MutationObserver']) {
  if (W[k]) Object.defineProperty(globalThis, k, { value: W[k], configurable: true, writable: true })
}
globalThis.Date = W.Date
for (const [name, wert] of [['innerWidth', 1440], ['innerHeight', 900]]) {
  Object.defineProperty(W, name, { value: wert, configurable: true })
}
W.matchMedia = W.matchMedia || (() => ({
  matches: true, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {},
}))
globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
W.ResizeObserver = globalThis.ResizeObserver

/**
 * REVIEW UX2e5/1 (dieselbe Ursache wie in ux2e5-terminliste-aktionen): das
 * Fenster wird am Ende GESCHLOSSEN. Sonst hielte jsdom mit
 * `pretendToBeVisual` einen Abräum-Timer offen und `node --test` bliebe ewig
 * stehen (der Grund für den hängenden Image-Build).
 */
test.after(() => {
  try { dom.window.close() } catch { /* schon zu */ }
})

/* ── Die ECHTE Bibliothek (wie im Betrieb) ───────────────────────────────
 * Kalender.vue bringt KronosCalendar.vue mit, und das baut die Bibliothek
 * beim Mount auf. Die Bündel-Datei ist UMD (`var EventCalendar = …`) — hier
 * also über `window.eval` geladen, damit sie EINMAL im jsdom-Fenster landet.
 */
const EC_PFAD = new URL('../node_modules/@event-calendar/build/dist/event-calendar.min.js',
  import.meta.url).pathname
W.eval(readFileSync(EC_PFAD, 'utf8'))
const WECHT = W.EventCalendar
assert.ok(WECHT && typeof WECHT.create === 'function', 'die echte Bibliothek ist geladen')

/* ── Server-Ersatz ─────────────────────────────────────────────────────── */
const AUFRUFE = []
let TERMINE = []
globalThis.fetch = async (adresse, optionen = {}) => {
  const url = String(adresse)
  // `apiCall` schickt JSON, `papierkorb.wiederherstellen`/ältere Aufrufer
  // schicken ein normales Formular (URL-kodiert) — beides lesen.
  const roh = optionen?.body || ''
  let rumpf = {}
  try { rumpf = roh.startsWith('{') ? JSON.parse(roh) : Object.fromEntries(new URLSearchParams(roh)) } catch { rumpf = {} }
  // `url` ist der vollständige Aufrufname (auch Query-Teile): die Methode ist
  // das letzte Segment VOR einem eventuellen `?`.
  const methode = url.split('?')[0].split('/').pop()
  AUFRUFE.push({ methode, rumpf })
  const antwort = (message) => ({ ok: true, status: 200, dkDaten: { message } })
  if (methode.endsWith('get_calendar_events')) return antwort(JSON.parse(JSON.stringify(TERMINE)))
  if (methode.endsWith('delete_event')) {
    return antwort({ success: true, geloescht_am: '2026-11-07 09:00:00', wiederherstellbar_bis: '2026-11-14 09:00:00' })
  }
  if (methode.endsWith('wiederherstellen_event')) return antwort({ success: true })
  // Schreibrecht auf einen Kalender — Voraussetzung für den Bearbeiten-Modus
  // (`hasWriteRight` in Kalender.vue liest genau diese Antwort).
  if (methode.endsWith('get_accessible_calendars')) {
    return antwort([{ name: 'gemeinde', calendar_name: 'Gemeinde', write: true, color: '#3355aa' }])
  }
  return antwort([])
}

/* ── SFC-Übersetzer (wie im Kalender-Test; Vue bleibt EIN Modul) ───────── */
const Vue = await import('vue')
const { parse, compileScript, compileTemplate } = await import('vue/compiler-sfc')
const TMP = mkdtempSync(join(process.env.TMPDIR || '/tmp', 'ux2e5b-'))
const cache = new Map()
const VUE_URL = import.meta.resolve('vue')

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
  // Bare Pakete (@event-calendar/build, weitere) aus dem Worktree auflösen:
  // die erzeugten Module liegen in einem Temp-Verzeichnis, von dort findet
  // Node die node_modules des Frontends nicht. Der Sonderfall der Bibliothek
  // kommt als NAMENSRAUM (`import * as _EC`) — den behandelt das Muster unten
  // mit (`from`, nicht `import … from`).
  code = code.replace(/(\bfrom\s+|\bimport\s+)['"]([^'"./][^'"]*)['"]/g, (treffer, art, paket) => {
    try {
      return `${art}'${import.meta.resolve(paket)}'`
    } catch {
      return treffer
    }
  })
  code = code.replace(/from\s+['"](\.[^'"]+)['"]/g, (_t, pfad) => {
    const zielAbs = resolve(abs, '..', pfad)
    return zielAbs.endsWith('.vue')
      ? `from '${pathToFileURL(sfc(zielAbs)).href}'`
      : `from '${pathToFileURL(zielAbs).href}'`
  })
  // Stylesheets der Bausteine braucht jsdom nicht.
  code = code.replace(/import\s+'[^']+\.css'/g, '')
  const ziel = resolve(TMP, filename + cache.size + '.mjs')
  writeFileSync(ziel, code)
  cache.set(abs, ziel)
  return ziel
}

const tick = (ms = 40) => new Promise((r) => setTimeout(r, ms))

/** Kennungen der Server-Aufrufe in der Reihenfolge, in der sie kamen. */
const aufrufe = (name) => AUFRUFE.filter((a) => a.methode === name || a.methode.endsWith('.' + name))

function termin(id, titel, start, ende, extra = {}) {
  return {
    id,
    title: titel,
    start,
    end: ende,
    allDay: false,
    backgroundColor: '#3355aa',
    extendedProps: { name: id, element_name: titel, id, ...extra },
  }
}

const TAG = '2026-11-04'

/**
 * Mountet die ECHTE Kalender.vue. Der Kalender der Seite ist ein echtes
 * KronosCalendar.vue mit der echten Bibliothek — deshalb liefert der Test die
 * Einträge über `terminAktion` direkt an die Seite, genau wie das Widget.
 */
async function seiteMit(terme, { viewMode = 'edit' } = {}) {
  TERMINE = terme
  AUFRUFE.length = 0
  const Kalender = (await import(pathToFileURL(sfc(new URL(
    '../src/diakonos/pages/Kalender.vue', import.meta.url).pathname)).href
    + '?v=' + Math.random())).default
  const app = Vue.createApp({
    components: { Kalender },
    template: '<Kalender ref="seite" />',
  })
  app.config.warnHandler = () => {}
  app.config.errorHandler = (e) => { console.log('[fehler]', String(e?.message || e)) }
  const host = document.createElement('div')
  host.style.height = '900px'
  document.body.appendChild(host)
  const vm = app.mount(host).$refs.seite
  // Der Kalender-Speicher startet im ANSEHEN-Modus (`viewMode = "view"`); der
  // Umschalter in der Kopfzeile setzt ihn. Für die Lösch-Fälle wird er — wie
  // im Betrieb — über `onViewModeChange` in den Bearbeitungsmodus gestellt.
  await tick(300)
  if (viewMode === 'edit') {
    // Rechte: `onViewModeChange('edit')` prüft `hasWriteRight` — der Stand
    // kommt aus `get_accessible_calendars` (Server-Ersatz oben).
    vm.onViewModeChange('edit')
  }
  await tick(200)
  const close = () => { try { app.unmount() } catch { /* schon weg */ } host.remove() }
  return { app, vm, close, viewMode }
}

/** Der Datensatz, wie ihn das Widget an die Seite meldet (siehe terminAktionenDaten). */
function datenAus(terme, id) {
  const t = terme.find((x) => x.id === id)
  return { ...t, extendedProps: { ...t.extendedProps } }
}

/* ── A · Einzeltermin: „Löschen" geht direkt in den Papierkorb ─────────── */
test('UX2e5b · Einzeltermin „Löschen": delete_event + Rückgängig, ohne Bearbeiten-Dialog', async () => {
  const terme = [termin('t1', 'Chorprobe', `${TAG}T09:00:00`, `${TAG}T10:00:00`)]
  const { vm, close } = await seiteMit(terme)
  await vm.onTerminAktion({ key: 'loeschen', termin: datenAus(terme, 't1') })
  await tick(120)
  const loeschaufrufe = aufrufe('delete_event')
  assert.equal(loeschaufrufe.length, 1, 'genau EIN Löschaufruf')
  assert.equal(loeschaufrufe[0].rumpf.name, 't1', 'mit der Server-Kennung des Termins')
  // REVIEW-Punkt 4: KEIN Bearbeiten-Dialog (der hieße „Termin bearbeiten").
  assert.equal(document.querySelector('[aria-label="Termin bearbeiten"]'), null,
    'der Bearbeiten-Dialog ist NICHT offen')
  // Die Meldung nennt den Papierkorb und bietet „Rückgängig" an.
  const meldung = document.querySelector('.diakonos-toast-container')
  assert.ok(meldung, 'es gibt eine Meldung')
  assert.match(meldung.textContent, /Papierkorb/, 'die Meldung nennt den Papierkorb')
  const zurueck = Array.from(meldung.querySelectorAll('button'))
    .find((b) => b.textContent.trim() === 'Rückgängig')
  assert.ok(zurueck, 'die Meldung bietet „Rückgängig" an')
  close()
})

/* ── B · „Rückgängig" holt genau diesen Termin zurück ──────────────────── */
test('UX2e5b · „Rückgängig" ruft wiederherstellen_event mit derselben Kennung', async () => {
  const terme = [termin('t2', 'Jugendkreis', `${TAG}T12:00:00`, `${TAG}T13:00:00`)]
  const { vm, close } = await seiteMit(terme)
  await vm.onTerminAktion({ key: 'loeschen', termin: datenAus(terme, 't2') })
  await tick(120)
  // Die Meldungen der vorigen Fälle können noch stehen: den Rückgängig-Knopf
  // der JÜNGSTEN Meldung nehmen (Rückgängig-Meldungen stehen 10 s).
  const meldungen = Array.from(document.querySelectorAll('.diakonos-toast-container button'))
    .filter((b) => b.textContent.trim() === 'Rückgängig')
  const zurueck = meldungen[meldungen.length - 1]
  assert.ok(zurueck, 'der Rückgängig-Knopf steht in der Meldung')
  zurueck.dispatchEvent(new window.MouseEvent('click', { bubbles: true, cancelable: true }))
  await tick(150)
  const zurueckAufrufe = aufrufe('wiederherstellen_event')
  assert.equal(zurueckAufrufe.length, 1, 'genau EIN Zurückholen')
  assert.equal(zurueckAufrufe[0].rumpf.name, 't2', 'für denselben Termin')
  close()
})

/* ── C · Serientermin: Umfang bleibt beim Seriendialog ────────────────── */
test('UX2e5b · Serientermin „Löschen": kein delete_event (Umfang fragt der Seriendialog)', async () => {
  const terme = [termin('t3', 'Hauskreis', `${TAG}T19:00:00`, `${TAG}T20:00:00`, { series_id: 'serie-1' })]
  const { vm, close } = await seiteMit(terme)
  await vm.onTerminAktion({ key: 'loeschen', termin: datenAus(terme, 't3') })
  await tick(150)
  assert.equal(aufrufe('delete_event').length, 0,
    'bei einer Serie wird NICHT direkt gelöscht (erst der Umfang im Dialog)')
  const dialog = document.querySelector('[aria-label="Serientermin"]')
  assert.ok(dialog, 'der Seriendialog ist offen (Rückfrage nach dem Umfang)')
  close()
})

/* ── D · ANSEHEN-Modus: „Löschen" erreicht keinen Server ─────────────── */
test('UX2e5b · Ansehen-Modus: „Löschen" öffnet nur die Ansicht', async () => {
  const terme = [termin('t4', 'Gemeindefest', `${TAG}T10:00:00`, `${TAG}T11:00:00`)]
  const { vm, close } = await seiteMit(terme, { viewMode: 'view' })
  // Der Kalender-Speicher (useKronosStore) ist prozessweit EIN Zustand — der
  // vorige Test kann den Bearbeiten-Modus hinterlassen haben. Umschalten über
  // denselben Weg wie die Kopfzeile (`onViewModeChange`).
  vm.onViewModeChange('view')
  await tick(100)
  await vm.onTerminAktion({ key: 'loeschen', termin: datenAus(terme, 't4') })
  await tick(120)
  assert.equal(aufrufe('delete_event').length, 0, 'im Ansehen-Modus wird nichts gelöscht')
  close()
})
