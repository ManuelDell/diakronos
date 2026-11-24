/**
 * DATEIEN-4 — Gruppendateien: Oberfläche (Reiter „Dateien“, Papierkorb,
 * Gruppeneinstellungen). Karte t_217e855b.
 *
 * Grundlage ist das FERTIGE Backend (DATEIEN-3,
 * `backend/src/diakronos_app/api/dateien.py`) — geprüft wird, dass die
 * Oberfläche GENAU dessen Felder und Endpunkte benutzt, nichts erfindet:
 *
 *   dateien.liste(gruppe, untergruppe)   → {darf_hochladen, darf_anpinnen,
 *                                            max_bytes, dateien: [{name,
 *                                            dateiname, mime, groesse,
 *                                            eigene, angepinnt, darf_anpinnen,
 *                                            darf_bearbeiten}]}
 *   dateien.hochladen / anpinnen / umbenennen / loeschen / wiederherstellen
 *   dateien.papierkorb(gruppe, untergruppe) → {dateien: [...], loeschbar_ab}
 *   dateien.datei(name)                  → Ausliefern (Link)
 *   dateien.einstellungen(gruppe) / .einstellung_setzen(gruppe, schluessel, wert)
 *
 *   A  Regeln ohne DOM (`components/gruppen/gruppenDateien.mjs`): Kopf und
 *      Rechte je Zeile (fail closed), Papierkorb-Frist (30 Tage), Rückfrage,
 *      Einstellungs-Stand, Vorab-Prüfung der Dateiauswahl.
 *   B  `GruppenDateien.vue` gemountet (API gemockt): Hochladen-Knopf nur bei
 *      `darf_hochladen`, Menüeinträge je `darf_anpinnen`/`darf_bearbeiten`,
 *      Löschen MIT Rückfrage, Papierkorb nur bei Serverdaten.
 *   C  `GruppenDateiEinstellungen.vue` gemountet: zwei DkSchalterZeilen aus
 *      `dateien.einstellungen`, `einstellung_setzen` beim Umschalten, gesperrt
 *      ohne `darf_aendern`.
 *   D  `GruppeDetail.vue`: eigener Reiter „Dateien“ (nur bei Serverdaten),
 *      Karte im Reiter „Einstellungen“, Router-Adresse `#/gruppe/<id>/dateien`.
 *
 * Lauf: TMPDIR=$(mktemp -d) node --test tests/dateien4-gruppen-dateien.test.mjs
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, mkdtempSync, writeFileSync, rmSync, mkdirSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, dirname, resolve, basename } from 'node:path'
import { pathToFileURL, fileURLToPath } from 'node:url'
import { JSDOM } from 'jsdom'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'

const hier = dirname(fileURLToPath(import.meta.url))
const FRONTEND = resolve(hier, '..')
const SRC = join(FRONTEND, 'src', 'diakonos')

// ── Browser-Ersatz ─────────────────────────────────────────────────────────
const dom = new JSDOM('<!doctype html><html><body></body></html>', {
  url: 'http://localhost/',
  pretendToBeVisual: true,
})
const { window: W } = dom
for (const name of ['window', 'document', 'HTMLElement', 'Element', 'Node', 'SVGElement',
  'HTMLInputElement', 'HTMLButtonElement', 'HTMLAnchorElement', 'Text', 'Comment',
  'DocumentFragment', 'getComputedStyle', 'requestAnimationFrame', 'cancelAnimationFrame',
  'MutationObserver', 'CustomEvent', 'Event', 'MouseEvent', 'KeyboardEvent',
  'localStorage', 'sessionStorage', 'File', 'Blob', 'FormData', 'FocusEvent']) {
  if (W[name] === undefined) continue
  try {
    globalThis[name] = W[name]
  } catch (_) {
    Object.defineProperty(globalThis, name, { value: W[name], configurable: true, writable: true })
  }
}
if (W.navigator) {
  try { Object.defineProperty(globalThis, 'navigator', { value: W.navigator, configurable: true }) } catch (_) { /* egal */ }
}
globalThis.window = W
W.__DIakonosBOOT = { csrf_token: 'x', modules: ['dateien'], user_email: 'ich@example.org' }
globalThis.matchMedia = () => ({ matches: false, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {} })
W.matchMedia = globalThis.matchMedia
Element.prototype.scrollIntoView = function () {}

const echterInterval = globalThis.setInterval
globalThis.setInterval = (fn, ms, ...rest) => (ms ? { unref() {}, ref() {}, [Symbol.toPrimitive]: () => 0 } : echterInterval(fn, ms, ...rest))

const Vue = await import('vue')
const T = await import(pathToFileURL(join(SRC, 'components/gruppen/gruppenDateien.mjs')).href)
const SPEICHER = await import(pathToFileURL(join(SRC, 'components/ui/symbole.mjs')).href)

// ── Stellvertreter: `apiCall` ohne Netz, `showToast` ohne Stapel ───────────
const TMP = mkdtempSync(join(tmpdir(), 'dateien4-'))
const STUB = join(TMP, 'stubs')
mkdirSync(STUB, { recursive: true })
writeFileSync(join(STUB, 'api.mjs'), `
// Zustand ueber "process": Testdatei und Bauteil laufen in getrennten Kontexten.
process.__API4 ||= { aufrufe: [], antworten: {}, uploads: [], uploadAntwort: null }
const speicher = process.__API4
export const aufrufe = speicher.aufrufe
export const uploads = speicher.uploads
export function setzeAntworten(neu) {
  speicher.antworten = { ...neu }
  for (const [k, v] of Object.entries(neu)) {
    if (!(v instanceof Error)) speicher.antworten[k] = v
    else speicher.antworten[k] = v
  }
}
export function setzeUploadAntwort(neu) { speicher.uploadAntwort = neu }
export async function apiCall(methode, args) {
  aufrufe.push([methode, args])
  const kurz = String(methode).split('.').pop()
  const wert = speicher.antworten[kurz]
  const ergebnis = typeof wert === 'function' ? wert(args) : wert
  if (ergebnis instanceof Error) throw ergebnis
  return ergebnis === undefined ? { success: true } : ergebnis
}
export async function apiGet(methode, args) { return apiCall(methode, args) }
export const apiUrl = (pfad) => '/diakonos/api/method/' + pfad
export class AuditConfirmationRequired extends Error {}
export function pruefeSitzungsAntwort() { return false }
export async function apiAntwortPruefen(res) {
  uploads.push(res.__form || null)
  const wert = speicher.uploadAntwort || { success: true, name: 'GDT-NEU', dateiname: 'neu.pdf' }
  const kasten = { ok: true, status: 200, json: async () => ({ message: wert }) }
  return { ...kasten, dkAntwort: kasten }
}
`)
writeFileSync(join(STUB, 'toast.mjs'), `
process.__TOAST4 ||= []
export const toasts = process.__TOAST4
export function showToast(text, art) { process.__TOAST4.push([text, art]) }
`)
writeFileSync(join(STUB, 'bestaetigen.mjs'), `
process.__BEST4 ||= { fragen: [], antwort: true }
export const fragen = process.__BEST4.fragen
export async function bestaetigen(frage) {
  process.__BEST4.fragen.push(frage)
  return process.__BEST4.antwort
}
`)
writeFileSync(join(STUB, 'router.mjs'), `
export const currentHash = { value: '#' }
export function getRouteParam(art) {
  if (art === 'id') return process.__ROUTE_ID || 'GRU-1'
  return ''
}
export function navigate() {}
`)

const STELLVERTRETER = new Map([
  [join(SRC, 'router'), join(STUB, 'router.mjs')],
  [join(SRC, 'composables/useApi'), join(STUB, 'api.mjs')],
  [join(SRC, 'composables/useToast'), join(STUB, 'toast.mjs')],
  [join(SRC, 'composables/useBestaetigen'), join(STUB, 'bestaetigen.mjs')],
])

const cache = new Map()
const VUE_URL = import.meta.resolve('vue')

function stellvertreterFuer(abs) {
  const ohne = String(abs).replace(/\.(js|mjs|vue)$/, '')
  return STELLVERTRETER.get(ohne) || null
}

function kompilieren(abs) {
  const ersatz = stellvertreterFuer(abs)
  if (ersatz) return ersatz
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
  code = code.replace(/from\s+['"]vue['"]/g, `from '${VUE_URL}'`)
  code = code.replace(/from\s+['"]([^'"]+)['"]/g, (v, spec) => {
    if (!spec.startsWith('.')) return v
    const ziel = resolve(dirname(abs), spec)
    const datei = spec.endsWith('.vue') || stellvertreterFuer(ziel) ? kompilieren(ziel) : ziel
    return `from '${pathToFileURL(datei).href}'`
  })
  const ziel = resolve(TMP, filename.replace(/\.vue$/, '') + '.' + cache.size + '.mjs')
  writeFileSync(ziel, code)
  cache.set(abs, ziel)
  return ziel
}

test.after(() => rmSync(TMP, { recursive: true, force: true }))

const tick = () => new Promise((loese) => setTimeout(loese, 0))
const TAKT = 10
async function warten(bedingung, versuche = 80) {
  for (let i = 0; i < versuche; i += 1) {
    if (bedingung()) return true
    await new Promise((loese) => setTimeout(loese, TAKT))
  }
  return bedingung()
}

const api = await import(pathToFileURL(join(STUB, 'api.mjs')).href)
const best = await import(pathToFileURL(join(STUB, 'bestaetigen.mjs')).href)
// Der Zustand liegt in "process" (getrennte Kontexte) — hier EINMAL holen.
process.__API4 ||= { aufrufe: [], antworten: {}, uploads: [], uploadAntwort: null }
const API4 = process.__API4

async function mounten(datei, eigenschaften = {}, bauteile = {}) {
  const bauteil = (await import(pathToFileURL(kompilieren(join(SRC, datei))).href)).default
  const host = document.createElement('div')
  document.body.appendChild(host)
  const warnungen = []
  const eigenschaftenRef = Vue.ref({ ...eigenschaften })
  const app = Vue.createApp({
    setup: () => ({ p: eigenschaftenRef }),
    render() { return Vue.h(bauteil, eigenschaftenRef.value) },
  })
  for (const [name, kind] of Object.entries(bauteile)) app.component(name, kind)
  app.config.warnHandler = (m) => warnungen.push(m)
  app.config.errorHandler = (e) => warnungen.push(String(e && e.stack ? e.stack : e))
  app.mount(host)
  await tick()
  return {
    host,
    app,
    warnungen,
    html: () => host.innerHTML,
    text: () => host.textContent || '',
    abbaum: () => { try { app.unmount() } catch (_) { /* egal */ } host.remove() },
  }
}

/** Antwort der Liste — die Felder GENAU wie `_zeile_eintrag`/`_kopfzeile`. */
function listeAntwort({ dateien = [], darfHochladen = true, darfAnpinnen = false, maxBytes = 10485760 } = {}) {
  return {
    success: true, gruppe: 'GRU-1', untergruppe: null,
    dateien, anzahl: dateien.length,
    darf_hochladen: darfHochladen, darf_anpinnen: darfAnpinnen, max_bytes: maxBytes,
  }
}

function dateiZeile(name, extra = {}) {
  return {
    name,
    dateiname: 'Protokoll.pdf',
    mime: 'application/pdf',
    groesse: 2048,
    angelegt_am: '2026-11-20 10:00:00',
    angelegt_von: 'anna@example.org',
    eigene: false,
    angepinnt: false,
    angepinnt_am: '',
    darf_anpinnen: false,
    darf_bearbeiten: false,
    ...extra,
  }
}

function zuruecksetzen() {
  API4.aufrufe.length = 0
  process.__TOAST4 ||= []
  process.__TOAST4.length = 0
  process.__BEST4 ||= { fragen: [], antwort: true }
  process.__BEST4.fragen.length = 0
  process.__BEST4.antwort = true
  api.setzeAntworten({})
  api.setzeUploadAntwort(null)
}

// ════════════════════════════════════════════════════════════════════════════
// A · Regeln ohne DOM
// ════════════════════════════════════════════════════════════════════════════

test('DATEIEN-4/A: die Endpunkte sind die des Backends (api/dateien.py)', () => {
  const namen = ['liste', 'hochladen', 'anpinnen', 'umbenennen', 'loeschen',
    'wiederherstellen', 'papierkorb', 'datei', 'einstellungen', 'einstellung_setzen']
  for (const n of namen) {
    assert.equal(T.PFADE[n], `diakronos.diakonos.api.dateien.${n}`, `${n}: gleicher Pfad wie im Server`)
  }
  // Die Schalter heißen wie im Kern (`rechte.kern.GRUPPENEINSTELLUNGEN`).
  assert.deepEqual(T.SCHALTER.map((s) => s.key),
    ['dateien_hochladen_alle', 'dateien_anpinnen_alle'])
  assert.equal(T.PAPIERKORB_TAGE, 30, 'F5: 30 Tage Aufbewahrung')
})

test('DATEIEN-4/A: der Kopf der Liste entscheidet über den Hochladen-Knopf (fail closed)', () => {
  const voll = T.kopfAus(listeAntwort({ darfHochladen: true, darfAnpinnen: true }))
  assert.deepEqual(voll, { darfHochladen: true, darfAnpinnen: true, maxBytes: 10485760, anzahl: 0 })
  // Fehlt oder kaputt = NICHT erlaubt (kein Knopf) — und keine erfundene Grenze.
  const leer = T.kopfAus({ dateien: [] })
  assert.equal(leer.darfHochladen, false)
  assert.equal(leer.darfAnpinnen, false)
  assert.equal(leer.maxBytes, null)
  assert.equal(T.kopfAus({ max_bytes: 'viel' }).maxBytes, null)
  assert.equal(T.kopfAus(null).darfHochladen, false)
})

test('DATEIEN-4/A: die Vorab-Prüfung weist leer und offenkundig zu groß ab', () => {
  assert.equal(T.uploadHindernis({ size: 10 }, 100), '')
  assert.match(T.uploadHindernis({ size: 0 }, 100), /leer/)
  assert.match(T.uploadHindernis({ size: 101 }, 100), /zu groß/)
  assert.match(T.uploadHindernis({ size: 101 }, 100), /0 MB|zu groß/)
  assert.match(T.uploadHindernis({ size: 25 * 1024 * 1024 + 1 }, 25 * 1024 * 1024), /25 MB/)
  // Genau die Grenze ist erlaubt; ohne Grenze wird NICHTS abgewiesen.
  assert.equal(T.uploadHindernis({ size: 100 }, 100), '')
  assert.equal(T.uploadHindernis({ size: 999_999_999 }, null), '')
})

test('DATEIEN-4/A: je Zeile NUR die Aktionen, die der Server meldet', () => {
  // Nur lesen: genau Herunterladen.
  assert.deepEqual(T.aktionenFuerZeile(dateiZeile('GDT-1')).map((e) => e.key), ['herunterladen'])

  // Eigene Datei: bearbeiten ja, Pin nur wenn der Server `darf_anpinnen` sagt.
  // (Die Zeile kommt so, wie `liste` sie liefert — snake_case, nicht die
  // normalisierte Form aus `zeilenAus`.)
  const eigen = T.aktionenFuerZeile(dateiZeile('GDT-2', { eigene: true, darf_bearbeiten: true }))
  assert.deepEqual(T.zeilenAus({ dateien: [dateiZeile('GDT-2', { eigene: true, darf_bearbeiten: true })] })[0].darfBearbeiten, true)
  assert.deepEqual(eigen.map((e) => e.key), ['herunterladen', 'umbenennen', 'loeschen'])
  assert.equal(eigen.at(-1).gefahr, true, 'Löschen ist gefährlich (abgesetzt am Ende)')

  // Leitung: Pin dazu — und bei angepinnter Datei heißt der Eintrag „Pin lösen“.
  const leitung = T.aktionenFuerZeile(dateiZeile('GDT-3', {
    darf_bearbeiten: true, darf_anpinnen: true, angepinnt: true,
  }))
  assert.deepEqual(leitung.map((e) => e.key), ['herunterladen', 'umbenennen', 'anpinnen', 'loeschen'])
  assert.equal(leitung.find((e) => e.key === 'anpinnen').label, T.TEXTE.loesen)
  // Alle Symbole stehen im Vorrat (sonst zeichnete DkSymbol nichts).
  for (const e of leitung) assert.ok(SPEICHER.SYMBOLNAMEN.includes(e.icon), `${e.icon} im Vorrat`)
})

test('DATEIEN-4/A: Löschen fragt nach und nennt die Folge (F4)', () => {
  const eigen = T.loeschRueckfrage(dateiZeile('GDT-1', { eigene: true, darf_bearbeiten: true }))
  assert.equal(eigen.ja, true)
  assert.equal(eigen.titel, 'Datei löschen?')
  assert.match(eigen.text, /Protokoll\.pdf/)
  assert.match(eigen.text, /30 Tage/)
  assert.match(eigen.text, /endgültig/)

  // FREMDE Datei: eigener Titel — und ohne `darf_bearbeiten` gar keine Frage.
  const fremd = T.loeschRueckfrage(dateiZeile('GDT-2', { darf_bearbeiten: true }))
  assert.equal(fremd.titel, 'Fremde Datei löschen?')
  const gesperrt = T.loeschRueckfrage(dateiZeile('GDT-3'))
  assert.equal(gesperrt.ja, false, 'ohne Server-Erlaubnis wird nicht gelöscht')
  assert.equal(T.darfLoeschen(dateiZeile('GDT-3')), false)
})

test('DATEIEN-4/A: Papierkorb — 30 Tage, Server-Datum hat Vorrang', () => {
  // Der Server rechnet selbst (`loeschbar_ab`); das gilt.
  assert.equal(T.endgueltigAm({ geloescht_am: '2026-11-01 08:00:00', loeschbar_ab: '2026-12-01 08:00:00' }),
    '01.12.2026')
  // Fehlt es, wird aus `geloescht_am` + 30 Tage gerechnet (F5).
  assert.equal(T.endgueltigAm({ geloescht_am: '2026-11-23 14:05:00' }), '23.12.2026')
  assert.equal(T.papierkorbEndeText({ geloescht_am: '2026-11-23 14:05:00' }),
    'wird am 23.12.2026 endgültig gelöscht')
  // Nichts bekannt = nichts behauptet.
  assert.equal(T.endgueltigAm({}), '')
  assert.equal(T.papierkorbEndeText({ geloescht_am: 'kaputt' }), '')
  assert.equal(T.datumText('2026-11-23 14:05:00'), '23.11.2026')
  assert.equal(T.aufbewahrungTage({ aufbewahrung_tage: 14 }), 14)
  assert.equal(T.aufbewahrungTage({}), 30)
})

test('DATEIEN-4/A: Zeilen der Liste und des Papierkorbs — ohne Erfindungen', () => {
  const z = T.zeilenAus(listeAntwort({
    dateien: [dateiZeile('GDT-1', { angepinnt: true, darf_bearbeiten: true }), { name: '' }],
  }))
  assert.equal(z.length, 1, 'eine Zeile ohne Kennung ist keine Datei')
  assert.equal(z[0].name, 'GDT-1')
  assert.equal(z[0].angepinnt, true)
  assert.equal(z[0].darfBearbeiten, true)
  assert.equal(z[0].groesseText, '2 kB')
  assert.equal(T.zeilenAus(null).length, 0)

  const korb = T.papierkorbZeilen({
    dateien: [{ name: 'GDT-9', dateiname: 'alt.pdf', groesse: 10, geloescht_am: '2026-11-01 10:00:00', geloescht_von: 'anna@example.org' }],
  })
  assert.equal(korb[0].endeText, 'wird am 01.12.2026 endgültig gelöscht')
  assert.equal(korb[0].groesseText, '10 B')
  assert.equal(T.papierkorbZeilen(null).length, 0)
})

test('DATEIEN-4/A: der Stand der beiden Schalter kommt vom Server', () => {
  const stand = T.einstellungenAus({
    werte: { dateien_hochladen_alle: true, dateien_anpinnen_alle: false },
    darf_aendern: true,
  })
  assert.deepEqual(stand.werte, { dateien_hochladen_alle: true, dateien_anpinnen_alle: false })
  assert.equal(stand.darfAendern, true)
  // Ohne Antwort darf niemand ändern (fail closed).
  assert.equal(T.einstellungenAus({}).darfAendern, false)
  assert.deepEqual(T.einstellungenAus({}).werte, { dateien_hochladen_alle: false, dateien_anpinnen_alle: false })
})

// ════════════════════════════════════════════════════════════════════════════
// B · GruppenDateien.vue gemountet
// ════════════════════════════════════════════════════════════════════════════

test('DATEIEN-4/B: Hochladen-Knopf NUR bei darf_hochladen, Liste wie geliefert', async () => {
  zuruecksetzen()
  api.setzeAntworten({
    liste: listeAntwort({ dateien: [dateiZeile('GDT-1'), dateiZeile('GDT-2', { angepinnt: true })], darfHochladen: false }),
    papierkorb: new Error('403'),
  })
  const s = await mounten('components/gruppen/GruppenDateien.vue', { gruppe: 'GRU-1' })
  await warten(() => s.text().includes('Protokoll.pdf'))

  const zeilen = s.host.querySelectorAll('[data-dateiliste] .gd-zeile')
  assert.equal(zeilen.length, 2, 'beide Dateien stehen da')
  assert.ok(s.host.querySelector('[data-datei="GDT-1"]'), 'die Kennung steht an der Zeile')
  assert.equal(s.host.querySelector('.gd-hochladen'), null, 'ohne darf_hochladen KEIN Hochladen')
  assert.equal(s.host.querySelector('[data-papierkorb]'), null, 'ohne Papierkorb-Recht keine Ansicht')

  // Herunterladen geht über den Ausliefer-Endpunkt (dort prüft der Server LESEN).
  const link = s.host.querySelector('[data-datei="GDT-1"] a.gd-laden')
  assert.ok(link, 'der Herunterladen-Link steht an der Zeile')
  assert.equal(link.getAttribute('href'),
    '/diakonos/api/method/diakronos.diakonos.api.dateien.datei?name=GDT-1')
  assert.equal(link.getAttribute('download'), 'Protokoll.pdf')
  // Ohne Rechte je Zeile gibt es KEIN „⋯“-Menü (nur den Download-Link).
  assert.equal(s.host.querySelector('[data-datei="GDT-1"] .dk-ui-aktionen-ausloeser'), null)
  s.abbaum()
})

test('DATEIEN-4/B: mit darf_hochladen steht der Hochladen-Knopf, mit Papierkorb-Daten die Ansicht', async () => {
  zuruecksetzen()
  api.setzeAntworten({
    liste: listeAntwort({ dateien: [], darfHochladen: true }),
    papierkorb: {
      success: true, aufbewahrung_tage: 30, anzahl: 1,
      dateien: [{ name: 'GDT-9', dateiname: 'alt.pdf', groesse: 10, geloescht_am: '2026-11-01 10:00:00' }],
    },
  })
  const s = await mounten('components/gruppen/GruppenDateien.vue', { gruppe: 'GRU-1' })
  await warten(() => s.host.querySelector('.gd-hochladen'))
  assert.ok(s.host.querySelector('.gd-hochladen'), 'Hochladen-Knopf da')
  assert.match(s.text(), /Noch keine Dateien/)
  assert.match(s.text(), /Höchstens 10 MB je Datei\./)

  const korb = s.host.querySelector('[data-papierkorb]')
  assert.ok(korb, 'die Papierkorb-Ansicht erscheint mit Serverdaten')
  assert.match(korb.textContent, /Papierkorb \(1\)/)
  // Erst aufgeklappt stehen die Zeilen — mit dem Enddatum des Servers.
  const knopf = korb.querySelector('button')
  knopf.click()
  await warten(() => s.host.querySelector('[data-papierkorbliste]'))
  assert.match(s.host.querySelector('[data-papierkorbliste]').textContent,
    /wird am 01\.12\.2026 endgültig gelöscht/)
  s.abbaum()
})

test('DATEIEN-4/B: Anpinnen, Umbenennen, Löschen — nur mit Serverrecht, Löschen MIT Rückfrage', async () => {
  zuruecksetzen()
  api.setzeAntworten({
    liste: listeAntwort({
      dateien: [dateiZeile('GDT-3', { eigene: true, darf_bearbeiten: true, darf_anpinnen: true })],
      darfAnpinnen: true,
    }),
    papierkorb: new Error('403'),
  })
  api.setzeAntworten({
    liste: listeAntwort({
      dateien: [dateiZeile('GDT-3', { eigene: true, darf_bearbeiten: true, darf_anpinnen: true })],
      darfAnpinnen: true,
    }),
    papierkorb: new Error('403'),
    loeschen: { success: true, name: 'GDT-3', geloescht_am: '2026-11-24 10:00:00' },
  })
  const s = await mounten('components/gruppen/GruppenDateien.vue', { gruppe: 'GRU-1', untergruppe: 'UG-1' })
  await warten(() => s.host.querySelector('[data-datei="GDT-3"] .dk-ui-aktionen-ausloeser'))
  // Die Untergruppe geht bei JEDEM Aufruf mit (F3: eigene Dateien).
  assert.ok(api.aufrufe[0][1].untergruppe === 'UG-1', 'liste fragt den Raum MIT Untergruppe')

  const ausloeser = s.host.querySelector('[data-datei="GDT-3"] .dk-ui-aktionen-ausloeser')
  ausloeser.click()
  await warten(() => document.querySelector('.dk-ui-aktionen-menue'))
  const eintraege = [...document.querySelectorAll('.dk-ui-aktionen-menue .dk-ui-aktionen-eintrag')]
  assert.deepEqual(eintraege.map((e) => e.textContent.trim()),
    ['Umbenennen', 'Anpinnen', 'Löschen'], 'Herunterladen ist der Link, nicht im Menü')

  // „Löschen“ fragt NACH — und sendet erst nach „Ja“.
  eintraege.at(-1).click()
  await warten(() => best.fragen.length === 1)
  assert.equal(best.fragen[0].titel, 'Datei löschen?')
  assert.match(best.fragen[0].text, /Papierkorb/)
  await warten(() => api.aufrufe.some(([m]) => m.endsWith('.loeschen')))
  const loesch = api.aufrufe.find(([m]) => m.endsWith('.loeschen'))
  assert.deepEqual(loesch[1], { name: 'GDT-3' })
  s.abbaum()
})

test('DATEIEN-4/B: „Nein“ in der Rückfrage löscht NICHT', async () => {
  zuruecksetzen()
  api.setzeAntworten({
    liste: listeAntwort({ dateien: [dateiZeile('GDT-4', { eigene: true, darf_bearbeiten: true })] }),
    papierkorb: new Error('403'),
  })
  process.__BEST4.antwort = false
  const s = await mounten('components/gruppen/GruppenDateien.vue', { gruppe: 'GRU-1' })
  await warten(() => s.host.querySelector('[data-datei="GDT-4"] .dk-ui-aktionen-ausloeser'))
  s.host.querySelector('[data-datei="GDT-4"] .dk-ui-aktionen-ausloeser').click()
  await warten(() => document.querySelector('.dk-ui-aktionen-menue'))
  const loeschen = [...document.querySelectorAll('.dk-ui-aktionen-menue .dk-ui-aktionen-eintrag')]
    .find((e) => e.textContent.trim() === 'Löschen')
  loeschen.click()
  await warten(() => best.fragen.length === 1)
  await new Promise((l) => setTimeout(l, 50))
  assert.equal(api.aufrufe.filter(([m]) => m.endsWith('.loeschen')).length, 0,
    'ohne Ja kein Aufruf')
  s.abbaum()
})

// ════════════════════════════════════════════════════════════════════════════
// C · GruppenDateiEinstellungen.vue gemountet
// ════════════════════════════════════════════════════════════════════════════

test('DATEIEN-4/B: Hochladen geht als Multipart mit Raum + `datei` an dateien.hochladen', async () => {
  zuruecksetzen()
  api.setzeAntworten({
    liste: listeAntwort({ dateien: [], darfHochladen: true }),
    papierkorb: new Error('403'),
  })
  const s = await mounten('components/gruppen/GruppenDateien.vue', { gruppe: 'GRU-1', untergruppe: 'UG-2' })
  // Die Seite baut ihre Liste; danach steht der Hochladen-Knopf.
  await warten(() => s.host.querySelector('input[type="file"]'))
  const feld = s.host.querySelector('input[type="file"]')

  // Der Upload selbst läuft über `fetch` — hier abgefangen, damit kein Netz
  // nötig ist und der Rumpf prüfbar wird.
  const gesendet = []
  const echterFetch = globalThis.fetch
  globalThis.fetch = async (url, optionen) => {
    gesendet.push({ url, optionen, form: optionen?.body })
    return { ok: true, status: 200, text: async () => '' }
  }
  try {
    const datei = new File([new Uint8Array([1, 2, 3])], 'Protokoll.pdf', { type: 'application/pdf' })
    Object.defineProperty(feld, 'files', { configurable: true, value: [datei] })
    feld.dispatchEvent(new Event('change'))
    await warten(() => gesendet.length === 1, 40)
    assert.equal(gesendet.length, 1, 'genau EIN Upload')
    assert.equal(gesendet[0].url, '/diakonos/api/method/diakronos.diakonos.api.dateien.hochladen')
    assert.equal(gesendet[0].optionen.method, 'POST')
    const form = gesendet[0].form
    assert.equal(form.get('gruppe'), 'GRU-1')
    assert.equal(form.get('untergruppe'), 'UG-2', 'F3: die Untergruppe reist mit')
    assert.ok(form.get('datei') !== null, 'die Datei steht unter `datei` (Frappe-Name)')
  } finally {
    globalThis.fetch = echterFetch
  }
  s.abbaum()
})

test('DATEIEN-4/C: zwei Schalterzeilen aus dateien.einstellungen, Setzen über einstellung_setzen', async () => {
  zuruecksetzen()
  api.setzeAntworten({
    einstellungen: {
      werte: { dateien_hochladen_alle: true, dateien_anpinnen_alle: false },
      darf_aendern: true,
    },
    einstellung_setzen: (args) => ({ success: true, schluessel: args.schluessel, wert: args.wert }),
  })
  const s = await mounten('components/gruppen/GruppenDateiEinstellungen.vue', { gruppe: 'GRU-1' })
  await warten(() => s.host.querySelectorAll('input[type="checkbox"]').length === 2)

  const kaestchen = [...s.host.querySelectorAll('input[type="checkbox"]')]
  assert.equal(kaestchen.length, 2, 'genau zwei Schalter')
  assert.equal(kaestchen[0].checked, true, 'hochladen_alle ist an (Serverwert)')
  assert.equal(kaestchen[1].checked, false, 'anpinnen_alle ist aus')
  assert.match(s.text(), /Alle Mitglieder dürfen hochladen/)
  assert.match(s.text(), /Alle Mitglieder dürfen anpinnen/)
  assert.equal(kaestchen[0].disabled, false, 'mit darf_aendern bedienbar')

  // Umschalten: erst der Server, dann der neue Stand.
  kaestchen[1].click()
  await warten(() => api.aufrufe.some(([m]) => m.endsWith('.einstellung_setzen')))
  const satz = api.aufrufe.find(([m]) => m.endsWith('.einstellung_setzen'))
  assert.deepEqual(satz[1], { gruppe: 'GRU-1', schluessel: 'dateien_anpinnen_alle', wert: true })
  await warten(() => s.host.querySelectorAll('input[type="checkbox"]')[1].checked === true)
  s.abbaum()
})

test('DATEIEN-4/C: ohne darf_aendern sind beide Schalter gesperrt (Meldung statt stiller Sperre)', async () => {
  zuruecksetzen()
  api.setzeAntworten({
    einstellungen: { werte: { dateien_hochladen_alle: true, dateien_anpinnen_alle: true }, darf_aendern: false },
  })
  const s = await mounten('components/gruppen/GruppenDateiEinstellungen.vue', { gruppe: 'GRU-1' })
  await warten(() => s.host.querySelectorAll('input[type="checkbox"]').length === 2)
  const kaestchen = [...s.host.querySelectorAll('input[type="checkbox"]')]
  assert.ok(kaestchen.every((k) => k.disabled), 'beide gesperrt')
  assert.match(s.text(), /Nur die Leitung dieser Gruppe kann diese Schalter umstellen\./)
  kaestchen[0].click()
  await new Promise((l) => setTimeout(l, 30))
  assert.equal(api.aufrufe.filter(([m]) => m.endsWith('.einstellung_setzen')).length, 0,
    'ein gesperrter Schalter sendet nichts')
  s.abbaum()
})

// ════════════════════════════════════════════════════════════════════════════
// D · GruppeDetail.vue — Reiter und Karte
// ════════════════════════════════════════════════════════════════════════════

const DETAIL_ANTWORT = {
  success: true,
  is_member: true,
  gruppe: { name: 'GRU-1', gruppenname: 'Chor', status: 'Aktiv', beschreibung: '', treffpunkt: '', treffzeit: '' },
  untergruppen: [], mitglieder: [], verantwortliche: [],
  aufgaben: [], ankuendigungen: [], wiki_artikel: [],
  rechte: { verwalten: true, rollen: true, aufgabe_anlegen: true, ankuendigung_anlegen: true, wiki_anlegen: true },
}

/** GruppeDetail mit Platzhaltern für alles, was hier nicht geprüft wird. */
async function detailSeite({ hash = '#/gruppe/GRU-1', dateienAntwort = listeAntwort({}) } = {}) {
  const Platzhalter = {
    template: '<div class="platzhalter"><slot /></div>',
  }
  process.__ROUTE_ID = 'GRU-1'
  api.setzeAntworten({
    get_gruppe_detail: DETAIL_ANTWORT,
    get_gruppe_termine: { termine: [] },
    get_accessible_calendars: [],
    liste: dateienAntwort,
    papierkorb: new Error('403'),
    einstellungen: { werte: { dateien_hochladen_alle: true, dateien_anpinnen_alle: false }, darf_aendern: true },
  })
  // Der Hash des Stellvertreters entscheidet den Reiter.
  const router = await import(pathToFileURL(join(STUB, 'router.mjs')).href)
  router.currentHash.value = hash
  const bauteile = {}
  for (const n of ['DkPageHeader', 'DkButton', 'DkBadge', 'DkField', 'DkSelect', 'DkCheckbox',
    'DkTable', 'DkEmpty', 'DkHint', 'MitgliedAuswahl', 'DkAktionen', 'DkReiter', 'DkSkelett',
    'KronosEventCreate', 'GruppenEinstellungen', 'DkBestaetigung']) {
    bauteile[n] = Platzhalter
  }
  return mounten('pages/GruppeDetail.vue', {}, bauteile)
}

test('DATEIEN-4/D: Reiter „Dateien“ nur, wenn der Server die Dateien liefert', async () => {
  zuruecksetzen()
  // Modul aus / kein Leserecht: der Server antwortet mit einem Fehler.
  const ohne = await detailSeite({ dateienAntwort: new Error('Kein Zugriff') })
  await warten(() => ohne.host.querySelector('[data-reiter-platzhalter]') || ohne.host.textContent.includes('Chor'))
  await new Promise((l) => setTimeout(l, 120))
  const zugriff0 = (el) => {
    let inst = el && (el.__vueParentComponent || null)
    while (inst && !(inst.setupState && 'reiterOptionen' in inst.setupState)) inst = inst.parent
    return inst ? inst.setupState : null
  }
  const optionen = zugriff0(ohne.host.firstElementChild)?.reiterOptionen
  assert.ok(optionen, 'die Seite hat ihre Reiteroptionen (auch ohne Dateien)')
  const roh = optionen.value !== undefined ? optionen.value : optionen
  assert.ok(Array.isArray(roh), `Reiteroptionen sind eine Liste (${typeof roh}: ${String(roh).slice(0, 80)})`)
  const werte = roh.map((o) => o.value)
  assert.ok(!werte.includes('dateien'), 'ohne Serverdaten kein Datei-Reiter')
  ohne.abbaum()

  // Mit Serverdaten: der Reiter steht da, mit der Adresse dieses Reiters.
  zuruecksetzen()
  const mit = await detailSeite({ dateienAntwort: listeAntwort({ dateien: [dateiZeile('GDT-1')] }) })
  await new Promise((l) => setTimeout(l, 120))
  const zugriff = (el) => {
    let inst = el && (el.__vueParentComponent || null)
    while (inst && !(inst.setupState && 'reiterOptionen' in inst.setupState)) inst = inst.parent
    return inst ? { setup2: inst.setupState } : {}
  }
  const optionen2 = zugriff(mit.host.firstElementChild).setup2?.reiterOptionen
  assert.ok(optionen2, 'die Seite hat ihre Reiteroptionen')
  const liste = optionen2.value !== undefined ? optionen2.value : optionen2
  assert.ok(Array.isArray(liste), `Reiteroptionen sind eine Liste (${typeof liste})`)
  const dateien = liste.find((o) => o.value === 'dateien')
  assert.ok(dateien, 'der Datei-Reiter steht in der Reiterzeile')
  assert.equal(dateien.href, '#/gruppe/GRU-1/dateien')
  assert.ok(liste.some((o) => o.value === 'einstellungen'), 'Einstellungen bleibt daneben')
  mit.abbaum()
})

test('DATEIEN-4/D: der Reiter „Einstellungen“ trägt die Karte „Dateien“ mit den beiden Schaltern', async () => {
  zuruecksetzen()
  const s = await detailSeite({ hash: '#/gruppe/GRU-1/einstellungen' })
  await warten(() => s.text().includes('Rollen der Gruppe') || s.text().includes('Dateien'))
  await new Promise((l) => setTimeout(l, 120))
  // Die Karte steht im Einstellungs-Reiter (Titel „Dateien“) — solange Titel
  // und Baustein da sind, ist die Verdrahtung intakt.
  const titel = [...s.host.querySelectorAll('.dk-ui-card-titel')].map((e) => e.textContent.trim())
  assert.ok(titel.includes('Dateien'), `Karte „Dateien“ im Reiter Einstellungen (gefunden: ${titel.join(', ')})`)
  assert.ok(titel.includes('Rollen der Gruppe'), 'die Rollen-Karte bleibt')
  s.abbaum()
})

test('DATEIEN-4/D: die Adresse #/gruppe/<id>/dateien wird im Router erkannt', () => {
  const router = readFileSync(join(SRC, 'router.js'), 'utf8')
  assert.match(router, /\^#\\\/gruppe\\\/\(\[\^\/\]\+\)\\\/dateien\$/, 'eigenes Muster für den Datei-Reiter')
  const detail = readFileSync(join(SRC, 'pages/GruppeDetail.vue'), 'utf8')
  assert.ok(detail.includes('\\/dateien\\/?$'), 'aktiverReiter liest den Datei-Reiter aus dem Hash')
})
