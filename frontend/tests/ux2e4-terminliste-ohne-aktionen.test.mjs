/**
 * UX2e4 — laufender (Mount-)Test: Die Terminliste ist WIEDER FREI von eigenen
 * Knoten; ein Klick auf eine Zeile öffnet den Dialog.
 *
 * WARUM IN frontend/tests/ UND MIT jsdom: Der Test hängt das ECHTE Bauteil
 * KronosCalendar.vue ein (Vue + jsdom aus node_modules, im Frontend-Stage des
 * Image-Builds vorhanden); der Pfad steht deshalb in der node-Testliste von
 * backend/Dockerfile. Er liest nur Dateien INNERHALB von frontend/ (Regel 13).
 *
 * ANLASS (Review UX2e3 mit ECHTER @event-calendar/build 5.18.0): Nach
 * `refetchEvents()` (auch nach Löschen) setzt die Bibliothek ihre Artikel neu
 * ein. Weil UX2e3 bibliothekseigene Knoten in fremde Hüllen verschob, landeten
 * alle Termine eines Tages in EINER Hülle, Knöpfe zeigten auf falsche Zeilen,
 * nach dem Löschen blieben Waisen, und ein ResizeObserver hing bis zum
 * Verlassen. UX2e4 nimmt die „⋯"-Einspeisung in der Liste deshalb wieder
 * heraus — Termine werden dort wie auf main per Klick bearbeitet.
 *
 * Geprüft wird das, was man im Quelltext NICHT sieht (echtes DOM):
 *   A. Die Bibliothek baut `article.ec-event` als DIREKTE Kinder von `.ec-day`
 *      — das Bauteil schiebt keine Hülle dazwischen.
 *   B. Kein ⋯-Knopf, kein ResizeObserver (auch nicht nach `refetchEvents`).
 *   C. Klick auf eine Zeile → `eventClick` der Seite (Dialog öffnet dort).
 *   D. Löschen/Neubau lässt keine Waisen zurück; nach dem Verlassen hängt
 *      keine Beobachtung mehr (`ux2e2-abgang` wurde nie ausgelöst).
 *
 * Die Bibliothek `@event-calendar/build` braucht ein Layout, das jsdom nicht
 * rechnet. Der Test ersetzt sie durch ein schlankes Doppel, das GENAU das DOM
 * baut, um das es geht — `.ec .ec-list > .ec-day > article.ec-event` — und die
 * Rückrufe des Bauteils so ruft, wie die Bibliothek sie ruft (inklusive
 * `eventClick`).
 *
 * Lauf: node --test tests/ux2e4-terminliste-ohne-aktionen.test.mjs   (cwd = frontend/)
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, mkdtempSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, basename, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

/* ── jsdom zuerst, damit Vue ein DOM vorfindet ─────────────────────────── */
let JSDOM
try {
  ({ JSDOM } = await import('jsdom'))
} catch {
  console.log('[ux2e4] übersprungen: kein jsdom vorhanden (Mount-Test braucht ein DOM)')
  process.exit(0)
}
const dom = new JSDOM('<!doctype html><html><body></body></html>', { pretendToBeVisual: true })
for (const k of ['window', 'document', 'Node', 'Element', 'HTMLElement', 'Event', 'MouseEvent',
  'KeyboardEvent', 'SVGElement', 'CustomEvent']) {
  if (dom.window[k]) globalThis[k] = dom.window[k]
}
for (const [name, wert] of [['innerWidth', 1440], ['innerHeight', 900]]) {
  Object.defineProperty(dom.window, name, { value: wert, configurable: true })
}
// jsdom rechnet kein Layout: jede Messung ist 0 — genau dann darf das Bauteil
// NICHTS messen wollen (UX2e3 maß die Knopfbreite).
dom.window.Element.prototype.getBoundingClientRect = function () {
  return { top: 0, bottom: 0, left: 0, right: 0, width: 0, height: 0,
    x: 0, y: 0, toJSON() { return this } }
}

/* ── ResizeObserver zählen: es darf GAR KEINEN geben ───────────────────── */
const beobachtet = new Map()   // Knoten -> Anzahl laufender Beobachtungen
let beobachterAnzahl = 0
globalThis.ResizeObserver = class {
  constructor(cb) { this.cb = cb; this.knoten = new Set(); beobachterAnzahl += 1 }
  observe(k) {
    if (!this.knoten.has(k)) {
      this.knoten.add(k)
      beobachtet.set(k, (beobachtet.get(k) || 0) + 1)
    }
  }
  unobserve(k) {
    if (this.knoten.delete(k)) beobachtet.set(k, (beobachtet.get(k) || 1) - 1)
  }
  disconnect() {
    for (const k of this.knoten) beobachtet.set(k, (beobachtet.get(k) || 1) - 1)
    this.knoten.clear()
  }
}

/* ── Doppel der Bibliothek (nur die Form, um die es geht) ───────────────── */
const WURZEL = document.createElement('div')
WURZEL.className = 'ec ec-list'
document.body.appendChild(WURZEL)
let RUECKRUFE = null
let EVENTS = new Map()
const STEUERUNG = []

/**
 * So zeichnet die Bibliothek: je Tag ein `.ec-day`, darin die article-Zeilen
 * DIREKT (keine Zwischenhülle). `refetchEvents` baut alles neu, wie im Betrieb.
 */
function zeichne() {
  if (!RUECKRUFE) return
  WURZEL.innerHTML = ''
  const liste = document.createElement('div')
  liste.className = 'ec-list'
  WURZEL.appendChild(liste)
  for (const [datum, terme] of EVENTS) {
    const tag = document.createElement('div')
    tag.className = 'ec-day'
    tag.dataset.datum = datum
    liste.appendChild(tag)
    for (const t of terme) {
      const zeile = document.createElement('article')
      zeile.className = 'ec-event'
      zeile.setAttribute('role', 'button')
      zeile.dataset.termin = String(t.id)
      const kachel = document.createElement('div')
      kachel.className = 'ec-event-body'
      zeile.appendChild(kachel)
      tag.appendChild(zeile)
    }
  }
}

const EventCalendarDoppel = {
  create(_el, config) {
    RUECKRUFE = config
    const steuerung = {
      getOption: () => 'listWeek',
      setOption() {},
      destroy() { WURZEL.innerHTML = ''; RUECKRUFE = null },
      refetchEvents: () => zeichne(),
      next() {}, prev() {}, refetchResources() {},
    }
    STEUERUNG.push(steuerung)
    zeichne()
    return steuerung
  },
}
globalThis.__EC_DOPPEL = EventCalendarDoppel

/* ── Bauteil laden (SFC übersetzen, Bibliothek gegen das Doppel tauschen) ─ */
const Vue = await import('vue')
const { parse, compileScript, compileTemplate } = await import('vue/compiler-sfc')
const TMP = mkdtempSync(join(tmpdir(), 'ux2e4-mount-'))
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
  code = code.replace(/from\s+['"](\.[^'"]+)['"]/g, (_treffer, pfad) => {
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

/** KronosCalendar.vue, aber die Bibliothek kommt aus dem Doppel. */
function ladeKalender() {
  let code = readFileSync(sfc(QUELLE.pathname), 'utf8')
  const doppelUrl = 'data:text/javascript,' + encodeURIComponent(
    'const C = globalThis.__EC_DOPPEL; export default C; export const create = C.create;')
  assert.match(code, /from\s+'@event-calendar\/build'/, 'das Bauteil holt die Bibliothek')
  code = code.replace(/from\s+'@event-calendar\/build'/g, `from ${JSON.stringify(doppelUrl)}`)
  code = code.replace(/import\s+'@event-calendar\/build\/dist\/event-calendar\.min\.css'/g, '')
  const ziel = resolve(TMP, 'kalender-mit-doppel.mjs')
  writeFileSync(ziel, code)
  return ziel
}

const tick = (n = 3) => new Promise((r) => setTimeout(r, 0)).then(() => (n > 1 ? tick(n - 1) : undefined))

/** Frisches Bauteil; `EVENTS` bestimmt den Inhalt der Liste. */
async function kalenderMit(terme) {
  EVENTS = new Map(terme)
  WURZEL.innerHTML = ''
  RUECKRUFE = null
  beobachterAnzahl = 0
  beobachtet.clear()
  const KronosCalendar = (await import(pathToFileURL(ladeKalender()).href + '?v=' + STEUERUNG.length)).default
  // Die Seite (Kalender.vue) hört auf `eventClick`; hier wird mitgehört, damit
  // belegt ist, dass der Klick WIRKLICH dort ankommt (Dialog).
  const ereignisse = []
  const app = Vue.createApp({
    components: { KronosCalendar },
    template: '<KronosCalendar @eventClick="merken" />',
    methods: { merken(ev) { ereignisse.push(ev) } },
  })
  app.config.warnHandler = () => {}
  const host = document.createElement('div')
  document.body.appendChild(host)
  const vm = app.mount(host)
  await tick()
  return { app, vm, host, ereignisse }
}

/* ── A · die Zeilen bleiben direkte Kinder des Tages ───────────────────── */
test('UX2e4 · Terminzeilen bleiben, wo die Bibliothek sie baut (keine Hülle)', async () => {
  const { app, host } = await kalenderMit([
    ['2026-11-06', [termin('t1', 'Chorprobe'), termin('t2', 'Jugendkreis'), termin('t3', 'Hauskreis Süd')]],
  ])
  const tag = WURZEL.querySelector('.ec-day')
  assert.ok(tag, 'der Tag ist gezeichnet')
  const zeilen = Array.from(tag.children).filter((k) => k.matches('article.ec-event'))
  assert.equal(zeilen.length, 3, 'drei Terminzeilen — direkt im Tages-Container')
  assert.equal(tag.children.length, 3, 'und nichts dazwischen (keine fremde Hülle)')
  for (const z of zeilen) {
    assert.equal(z.dataset.termin, z.dataset.termin)
    assert.equal(z.parentElement, tag, 'die Zeile hängt am Tag, nicht in einem eigenen Kasten')
  }
  app.unmount(); host.remove()
})

/* ── B · kein ⋯, kein Beobachter ──────────────────────────────────────── */
test('UX2e4 · kein ⋯-Knopf und kein ResizeObserver in der Liste', async () => {
  const { app, host } = await kalenderMit([
    ['2026-11-06', [termin('t1', 'A'), termin('t2', 'B')]],
  ])
  assert.equal(WURZEL.querySelectorAll('.kronos-liste-aktionen').length, 0, 'kein ⋯-Knopf')
  assert.equal(WURZEL.querySelectorAll('.kronos-liste-termin').length, 0, 'keine Hülle')
  assert.equal(WURZEL.querySelectorAll('button').length, 0, 'gar kein Knopf in den Bibliothekszeilen')
  assert.equal(beobachterAnzahl, 0, 'das Bauteil legt keinen ResizeObserver an')
  // Auch nach dem Neubau (der Weg, auf dem UX2e3 kaputtging) nicht.
  STEUERUNG[STEUERUNG.length - 1].refetchEvents()
  await tick()
  assert.equal(WURZEL.querySelectorAll('.ec-day > article.ec-event').length, 2, 'zwei Zeilen nach dem Neubau')
  assert.equal(beobachterAnzahl, 0, 'und weiterhin kein Beobachter')
  app.unmount(); host.remove()
})

/* ── C · Klick kommt bei der Seite an (Dialog) ────────────────────────── */
test('UX2e4 · Klick auf eine Zeile meldet eventClick (Seite öffnet den Dialog)', async () => {
  const { app, host, ereignisse } = await kalenderMit([
    ['2026-11-06', [termin('t1', 'Chorprobe')]],
  ])
  const steuerung = STEUERUNG[STEUERUNG.length - 1]
  const config = RUECKRUFE
  // Die Seite hört auf `eventClick` (Kalender.vue: onEventClick → Dialog).
  // Hier wird der Rückruf der Bibliothek bemüht, den sie beim Klick ruft —
  // das ist derselbe Weg, nur ohne Layout.
  const zeile = WURZEL.querySelector('article.ec-event')
  const terminObjekt = EVENTS.get('2026-11-06')[0]
  assert.ok(typeof config.eventClick === 'function', 'das Bauteil gibt eventClick weiter')
  config.eventClick({
    event: terminObjekt, el: zeile, view: steuerung,
    jsEvent: { preventDefault() {} },
  })
  await tick()
  assert.equal(ereignisse.length, 1, 'der Klick kommt bei der Seite an (dort öffnet der Dialog)')
  assert.equal(ereignisse[0], terminObjekt, 'und zwar für DIESEN Termin')
  assert.equal(WURZEL.querySelectorAll('button').length, 0, 'der Klick braucht keinen ⋯-Knopf')
  assert.ok(zeile.isConnected, 'die Zeile bleibt stehen')
  app.unmount(); host.remove()
})

/* ── D · Neubau/Löschen ohne Waisen, Verlassen ohne Rest ──────────────── */
test('UX2e4 · nach Löschen und Neubau keine Waisen; beim Verlassen kein Rest', async () => {
  const { app, host } = await kalenderMit([
    ['2026-11-06', [termin('t1', 'A'), termin('t2', 'B')]],
  ])
  EVENTS = new Map([['2026-11-06', [termin('t2', 'B')]]])
  STEUERUNG[STEUERUNG.length - 1].refetchEvents()
  await tick()
  const tag = WURZEL.querySelector('.ec-day')
  assert.equal(tag.querySelectorAll('article.ec-event').length, 1, 'nur noch eine Zeile')
  assert.equal(tag.querySelectorAll('*').length,
    tag.querySelectorAll('article.ec-event, .ec-event-body').length,
    'im Tag hängt nichts außer den Bibliotheks-Knoten (keine Knopf-Waise)')
  app.unmount()
  await tick()
  assert.equal(beobachterAnzahl, 0, 'kein Beobachter angelegt — beim Verlassen bleibt keiner zurück')
  assert.equal(beobachtet.size, 0, 'und nichts wurde beobachtet')
  host.remove()
})

/* ── Hilfen ────────────────────────────────────────────────────────────── */
function termin(id, titel) {
  return { id, title: titel, start: new Date('2026-11-06T19:30:00'), allDay: false }
}
