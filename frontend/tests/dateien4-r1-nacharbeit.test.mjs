/**
 * DATEIEN-4/R1 — Review-Runde 1 zur Gruppendateien-Oberfläche (Karte t_217e855b).
 *
 * Die Befunde des Operators, jeder als eigener Fall:
 *
 *   1 (HOCH) Der Direktlink `#/gruppe/<id>/dateien` bleibt stehen. Bis der
 *     Server geantwortet hat, ist „Reiter zu“ keine Auskunft, sondern nur
 *     „noch nicht gefragt“ — der Rückfall auf die Übersicht darf erst NACH
 *     der Antwort greifen (`dateienGeprueft`). Gegenprobe: antwortet die
 *     Liste mit einem Fehler, führt der Rückfall tatsächlich zur Übersicht.
 *   2 GruppenDateien.vue: kein `TEXTE.unbekannt` mehr (existiert nicht) —
 *     `aktionsfehler('hochladen', antwort)`.
 *   3 Die Einstellungskarte „Dateien“ steht nur, wenn das Modul offen ist.
 *   4 Der unsichtbare Dateifeld-Knopf zeigt seinen Tastaturfokus.
 *   5 Kein `--warn-text` (Token gibt es nicht) — `--warn`.
 *   6 Bilder bieten zusätzlich „Öffnen“ (neuer Reiter, ohne download).
 *
 *   ux2d3a: „Dateien werden geladen …“ stand als Satz im Bild (der Wächter
 *     war rot) — der Ladezustand zeigt jetzt nur den Spinner, die Auskunft
 *     steht im `aria-label`.
 *
 * Lauf: TMPDIR=$(mktemp -d) node --test tests/dateien4-r1-nacharbeit.test.mjs
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

// Umleitungen im Blick behalten: JSDOMs `location` ist nicht ersetzbar, aber
// `location.replace('#…')`/`hash = …` feuert `hashchange` und ändert `hash`.
// Genau das prüft der Rückfall — die Fälle unten lesen `W.location.hash` und
// sammeln jedes `hashchange`-Ziel.
const umleitungen = []
W.addEventListener('hashchange', () => { umleitungen.push(String(W.location.hash)) })

const echterInterval = globalThis.setInterval
globalThis.setInterval = (fn, ms, ...rest) => (ms ? { unref() {}, ref() {}, [Symbol.toPrimitive]: () => 0 } : echterInterval(fn, ms, ...rest))

const Vue = await import('vue')

// ── Stellvertreter: `apiCall` ohne Netz ────────────────────────────────────
const TMP = mkdtempSync(join(tmpdir(), 'dateien4r1-'))
const STUB = join(TMP, 'stubs')
mkdirSync(STUB, { recursive: true })
writeFileSync(join(STUB, 'api.mjs'), `
process.__API41 ||= { aufrufe: [], antworten: {}, uploads: [], uploadAntwort: null }
const speicher = process.__API41
export const aufrufe = speicher.aufrufe
export const uploads = speicher.uploads
export function setzeAntworten(neu) { speicher.antworten = { ...neu } }
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
process.__TOAST41 ||= []
export const toasts = process.__TOAST41
export function showToast(text, art) { process.__TOAST41.push([text, art]) }
`)
writeFileSync(join(STUB, 'bestaetigen.mjs'), `
process.__BEST41 ||= { fragen: [], antwort: true }
export const fragen = process.__BEST41.fragen
export async function bestaetigen(frage) {
  process.__BEST41.fragen.push(frage)
  return process.__BEST41.antwort
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
  // Nur .vue sind Einzeldatei-Bauteile — .js/.mjs (Composables, Texttabellen)
  // gehen unverändert über den Dateipfad.
  if (!String(abs).endsWith('.vue')) {
    const datei = pathToFileURL(abs).href
    cache.set(abs, datei)
    return datei
  }
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
async function warten(bedingung, versuche = 100) {
  for (let i = 0; i < versuche; i += 1) {
    if (bedingung()) return true
    await new Promise((loese) => setTimeout(loese, TAKT))
  }
  return bedingung()
}

const api = await import(pathToFileURL(join(STUB, 'api.mjs')).href)
process.__API41 ||= { aufrufe: [], antworten: {}, uploads: [], uploadAntwort: null }
const API41 = process.__API41

async function mounten(datei, eigenschaften = {}, bauteile = {}) {
  const bauteil = (await import(pathToFileURL(kompilieren(join(SRC, datei))).href)).default
  const host = document.createElement('div')
  document.body.appendChild(host)
  const warnungen = []
  const app = Vue.createApp({
    setup: () => ({}),
    render() { return Vue.h(bauteil, eigenschaften) },
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

const DETAIL_ANTWORT = {
  is_member: true,
  gruppe: { name: 'GRU-1', gruppenname: 'Chor', status: 'Aktiv', beschreibung: '', treffpunkt: '', treffzeit: '' },
  untergruppen: [], mitglieder: [], verantwortliche: [],
  aufgaben: [], ankuendigungen: [], wiki_artikel: [],
  rechte: { verwalten: true, rollen: true, aufgabe_anlegen: true, ankuendigung_anlegen: true, wiki_anlegen: true },
}

const Platzhalter = { template: '<div class="platzhalter"><slot /></div>' }

/** GruppeDetail mit dem Reiter, der im Hash steht. */
async function detailSeite({ hash = '#/gruppe/GRU-1', dateienAntwort = listeAntwort({}) } = {}) {
  process.__ROUTE_ID = 'GRU-1'
  api.setzeAntworten({
    get_gruppe_detail: DETAIL_ANTWORT,
    get_gruppe_termine: { termine: [] },
    get_accessible_calendars: [],
    liste: dateienAntwort,
    papierkorb: new Error('403'),
    einstellungen: { werte: { dateien_hochladen_alle: true, dateien_anpinnen_alle: false }, darf_aendern: true },
  })
  const router = await import(pathToFileURL(join(STUB, 'router.mjs')).href)
  router.currentHash.value = hash
  try { W.location.hash = hash } catch (_) { /* egal */ }
  // Die eigene Adress-Setzung ist kein Befund.
  umleitungen.length = 0
  const bauteile = {}
  for (const n of ['DkPageHeader', 'DkButton', 'DkBadge', 'DkField', 'DkSelect', 'DkCheckbox',
    'DkTable', 'DkEmpty', 'DkHint', 'MitgliedAuswahl', 'DkAktionen', 'DkReiter', 'DkSkelett',
    'KronosEventCreate', 'GruppenEinstellungen', 'DkBestaetigung', 'GruppenDateien',
    'GruppenDateiEinstellungen']) {
    bauteile[n] = Platzhalter
  }
  return mounten('pages/GruppeDetail.vue', {}, bauteile)
}

/** Karten-Titel der Seite. */
function kartenTitel(seite) {
  return [...seite.host.querySelectorAll('.dk-ui-card-titel')].map((e) => e.textContent.trim())
}

function zuruecksetzen() {
  API41.aufrufe.length = 0
  process.__TOAST41 ||= []
  process.__TOAST41.length = 0
  api.setzeAntworten({})
  api.setzeUploadAntwort(null)
  umleitungen.length = 0
  // Ausgangslage je Fall: die Adresse, die der Fall setzt (siehe `detailSeite`).
  W.location.hash = ''
}

// ════════════════════════════════════════════════════════════════════════════
// 1 (HOCH) · der Direktlink auf den Datei-Reiter springt NICHT zurück
// ════════════════════════════════════════════════════════════════════════════

test('DATEIEN-4/R1-1: Direktlink #/gruppe/<id>/dateien bleibt stehen und zeigt die Datei-Karte', async () => {
  zuruecksetzen()
  const s = await detailSeite({
    hash: '#/gruppe/GRU-1/dateien',
    dateienAntwort: listeAntwort({ dateien: [dateiZeile('GDT-1')] }),
  })
  await warten(() => API41.aufrufe.some(([m]) => String(m).endsWith('.liste')))
  // Nach der Antwort noch ein paar Takte: der Rückfall-Watch hätte hier
  // zugeschlagen, wenn er die „ungeprüfte“ Zeit falsch deutet.
  await new Promise((l) => setTimeout(l, 150))
  assert.equal(W.location.hash, '#/gruppe/GRU-1/dateien',
    `kein Rückfall bei gültigem Direktlink (Adresse jetzt: „${W.location.hash}“)`)

  assert.ok(kartenTitel(s).includes('Dateien dieser Gruppe'),
    `die Datei-Karte steht (Titel: ${kartenTitel(s).join(', ')})`)
  s.abbaum()
})

test('DATEIEN-4/R1-1: Gegenprobe — antwortet die Liste mit einem Fehler, führt der Rückfall zur Übersicht', async () => {
  zuruecksetzen()
  const s = await detailSeite({
    hash: '#/gruppe/GRU-1/dateien',
    dateienAntwort: new Error('Kein Zugriff'),
  })
  await warten(() => W.location.hash === '#/gruppe/GRU-1')
  assert.equal(W.location.hash, '#/gruppe/GRU-1',
    `Rückfall auf die Übersicht dieser Gruppe (tatsächlich: „${W.location.hash}“)`)
  s.abbaum()
})

test('DATEIEN-4/R1-1: vor der Antwort steht kein Rückfall (die Frage läuft noch)', async () => {
  zuruecksetzen()
  // Die Liste antwortet erst, wenn der Test es erlaubt.
  let loese
  const tor = new Promise((r) => { loese = r })
  api.setzeAntworten({
    get_gruppe_detail: DETAIL_ANTWORT,
    get_gruppe_termine: { termine: [] },
    get_accessible_calendars: [],
    liste: async () => { await tor; return listeAntwort({ dateien: [] }) },
    papierkorb: new Error('403'),
    einstellungen: { werte: {}, darf_aendern: false },
  })
  const router = await import(pathToFileURL(join(STUB, 'router.mjs')).href)
  router.currentHash.value = '#/gruppe/GRU-1/dateien'
  try { W.location.hash = '#/gruppe/GRU-1/dateien' } catch (_) { /* egal */ }
  process.__ROUTE_ID = 'GRU-1'
  const bauteile = {}
  for (const n of ['DkPageHeader', 'DkButton', 'DkBadge', 'DkField', 'DkSelect', 'DkCheckbox',
    'DkTable', 'DkEmpty', 'DkHint', 'MitgliedAuswahl', 'DkAktionen', 'DkReiter', 'DkSkelett',
    'KronosEventCreate', 'GruppenEinstellungen', 'DkBestaetigung', 'GruppenDateien',
    'GruppenDateiEinstellungen']) bauteile[n] = Platzhalter
  const s = await mounten('pages/GruppeDetail.vue', {}, bauteile)
  await warten(() => API41.aufrufe.some(([m]) => String(m).endsWith('.liste')))
  await new Promise((l) => setTimeout(l, 120))
  assert.equal(W.location.hash, '#/gruppe/GRU-1/dateien', 'solange die Antwort fehlt: kein Rückfall')
  loese()
  await new Promise((l) => setTimeout(l, 120))
  assert.equal(W.location.hash, '#/gruppe/GRU-1/dateien', 'gültige Antwort: der Reiter bleibt stehen')
  s.abbaum()
})

test('DATEIEN-4/R1-1: `dateienGeprueft` steht erst nach der Antwort auf wahr', async () => {
  const quelle = readFileSync(join(SRC, 'pages/GruppeDetail.vue'), 'utf8')
  assert.match(quelle, /const dateienGeprueft = ref\(false\)/, 'eigener „geprüft“-Merker')
  assert.match(quelle, /finally \{\s*\n\s*dateienGeprueft\.value = true/, 'im finally auf wahr')
  // Der Rückfall hängt an BEIDEN Quellen (geprüft + offen).
  assert.match(quelle, /dateienGeprueft, dateienOffen\]/, 'beide Merker sind Watch-Quellen')
  assert.match(quelle, /if \(!geprueft \|\| offen\) return/, 'Rückfall nur bei geprüft && !offen')
})

// ════════════════════════════════════════════════════════════════════════════
// 2-6 · die kleinen Befunde
// ════════════════════════════════════════════════════════════════════════════

test('DATEIEN-4/R1-2: kein TEXTE.unbekannt (gibt es nicht) — aktionsfehler statt Erfindung', () => {
  const quelle = readFileSync(join(SRC, 'components/gruppen/GruppenDateien.vue'), 'utf8')
  assert.ok(!quelle.includes('TEXTE.unbekannt'), 'kein erfundenes Textfeld')
  assert.match(quelle, /aktionsfehler\('hochladen', antwort\)/)
})

test('DATEIEN-4/R1-3: die Einstellungskarte „Dateien“ steht nur bei offenem Modul', () => {
  const quelle = readFileSync(join(SRC, 'pages/GruppeDetail.vue'), 'utf8')
  assert.match(quelle, /<DkCard v-if="dateienOffen" title="Dateien"/,
    'Karte an `dateienOffen` gebunden')
})

test('DATEIEN-4/R1-4: der unsichtbare Dateifeld-Knopf zeigt den Tastaturfokus', () => {
  const quelle = readFileSync(join(SRC, 'components/gruppen/GruppenDateien.vue'), 'utf8')
  assert.match(quelle, /\.gd-hochladen-knopf:focus-within\s*\{[^}]*outline: var\(--ring-breite\) solid var\(--focus-ring\)/,
    'Fokusring über :focus-within, nur Tokens')
  assert.match(quelle, /\.gd-hochladen-knopf:focus-within\s*\{[^}]*outline-offset: var\(--sp-1\)/,
    'Fokusabstand als Token')
  assert.ok(!quelle.includes('--warn-text'), 'kein Token, das es nicht gibt')
  assert.match(quelle, /\.gd-ende \{ color: var\(--warn\); \}/, 'vorhandenes Warn-Token')
})

test('DATEIEN-4/R1-5/6: Bilder bieten zusätzlich „Öffnen“ (neuer Reiter, ohne download)', async () => {
  zuruecksetzen()
  api.setzeAntworten({
    liste: listeAntwort({
      dateien: [
        dateiZeile('GDT-BILD', { dateiname: 'Plakat.png', mime: 'image/png' }),
        dateiZeile('GDT-PDF', { dateiname: 'Protokoll.pdf', mime: 'application/pdf' }),
      ],
    }),
    papierkorb: new Error('403'),
  })
  const s = await mounten('components/gruppen/GruppenDateien.vue', { gruppe: 'GRU-1' })
  await warten(() => s.host.querySelectorAll('[data-datei]').length > 0)
  const bild = s.host.querySelector('[data-datei="GDT-BILD"]')
  const pdf = s.host.querySelector('[data-datei="GDT-PDF"]')
  const links = (el) => [...(el ? el.querySelectorAll('a') : [])]
  const oeffnen = links(bild).filter((a) => a.getAttribute('target') === '_blank')
  assert.equal(oeffnen.length, 1, 'das Bild hat genau einen Öffnen-Link')
  assert.equal(oeffnen[0].getAttribute('rel'), 'noopener')
  assert.equal(oeffnen[0].hasAttribute('download'), false, 'Öffnen lädt NICHT herunter')
  assert.match(oeffnen[0].getAttribute('href'), /datei\?name=GDT-BILD/)
  assert.equal(links(bild).filter((a) => a.hasAttribute('download')).length, 1,
    'Herunterladen bleibt daneben')
  assert.equal(links(pdf).filter((a) => a.getAttribute('target') === '_blank').length, 0,
    'ein PDF bekommt KEIN Öffnen (nur Bilder)')
  s.abbaum()
})

test('DATEIEN-4/R1-ux2d3a: der Ladezustand behauptet keinen Satz mehr im Bild', async () => {
  zuruecksetzen()
  let loese
  const tor = new Promise((r) => { loese = r })
  api.setzeAntworten({ liste: async () => { await tor; return listeAntwort({ dateien: [] }) } })
  const s = await mounten('components/gruppen/GruppenDateien.vue', { gruppe: 'GRU-1' })
  await new Promise((l) => setTimeout(l, 80))
  const text = s.text()
  assert.ok(!/werden geladen/.test(text), `kein Ladeprosatext (Bild: „${text.trim().slice(0, 80)}“)`)
  loese()
  await warten(() => s.host.querySelector('[data-dateiliste]') !== null || s.text().includes('Noch keine Dateien'))
  s.abbaum()
})
