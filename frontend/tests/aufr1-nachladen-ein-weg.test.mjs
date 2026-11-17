/**
 * AUFR-1 — Nachweise am ECHTEN Bauteil (jsdom-Mount, kein Quelltext-Muster).
 *
 * Die Karte räumt zwei Stellen auf; geprüft wird das VERHALTEN:
 *
 *   1. EIN Abruf: Nach dem Abhaken einer Aufgabe holt `GruppeDetail.vue`
 *      `get_gruppe_detail` GENAU EINMAL — nicht mehr zweimal (Seite +
 *      `nachladenStill`). Dazu: keine Termin-Abfrage (`get_gruppe_termine`),
 *      keine Kalender-Abfrage (`get_accessible_calendars`) und kein Skelett,
 *      während die Antwort noch unterwegs ist.
 *   2. Fehlschlag beim stillen Nachladen: die Liste bleibt stehen, es gibt
 *      KEIN Fehlerbanner und KEINE Meldung (die Aktion selbst war erfolgreich).
 *   3. `rechte` aus der Nachlade-Antwort wird übernommen: nimmt der Server
 *      `aufgabe_anlegen` beim Nachladen weg (true → false), ist der Knopf
 *      „Aufgabe anlegen“ danach weg. Vorher übernahm `nachladenStill` nur
 *      `aufgaben`/`mitglieder` — das entzogene Recht blieb stehen.
 *
 * Aufbau wie in uir9b/uir9d: die SFC werden mit `vue/compiler-sfc` übersetzt,
 * `apiCall` läuft über ein Stellvertreter-Modul (kein Netz).
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

// ── Browser-Ersatz: jsdom, dann Vue + Bauteile laden ────────────────────────
const dom = new JSDOM('<!doctype html><html><body></body></html>', {
  url: 'http://localhost/',
  pretendToBeVisual: true,
})
const { window: W } = dom
for (const name of ['window', 'document', 'HTMLElement', 'Element', 'Node', 'SVGElement',
  'HTMLInputElement', 'HTMLButtonElement', 'Text', 'Comment', 'DocumentFragment',
  'getComputedStyle', 'requestAnimationFrame', 'cancelAnimationFrame', 'MutationObserver',
  'CustomEvent', 'Event', 'MouseEvent', 'KeyboardEvent', 'localStorage', 'sessionStorage']) {
  if (W[name] === undefined) continue
  try {
    globalThis[name] = W[name]
  } catch (_) {
    Object.defineProperty(globalThis, name, { value: W[name], configurable: true, writable: true })
  }
}
if (W.navigator) {
  try {
    Object.defineProperty(globalThis, 'navigator', { value: W.navigator, configurable: true })
  } catch (_) { /* Node-Behelf bleibt */ }
}
globalThis.window = W
W.__DIakonosBOOT = { csrf_token: 'x', modules: ['aufgaben'], user_email: 'ich@example.org' }
globalThis.matchMedia = () => ({ matches: false, addListener() {}, removeListener() {},
  addEventListener() {}, removeEventListener() {} })
W.matchMedia = globalThis.matchMedia
Element.prototype.scrollIntoView = function () {}

// Nur der Takt wird ersetzt (wie uir9b): ein Prüfintervall hielte den Prozess
// sonst am Leben.
const echterInterval = globalThis.setInterval
globalThis.setInterval = (fn, ms, ...rest) => {
  if (!ms) return echterInterval(fn, ms, ...rest)
  return { unref() {}, ref() {}, [Symbol.toPrimitive]: () => 0 }
}

const Vue = await import('vue')

// ── Stellvertreter: `apiCall` ohne Netz + Meldungen mitschreiben ────────────
const TMP = mkdtempSync(join(tmpdir(), 'aufr1-'))
const STUB = join(TMP, 'stubs')
mkdirSync(STUB, { recursive: true })
// Zustand über "process": die Testdatei und das Bauteil laufen in GETRENNTEN
// Modulkontexten — `process` ist beiden gemeinsam.
// Wie im Betrieb (`useApi.js`: `return message`) liefert `apiCall` die NUTZLAST
// der Antwort, nicht das Umschlagobjekt `{ message: … }`.
writeFileSync(join(STUB, 'api.mjs'), `
process.__API_STUB ||= { aufrufe: [], antworten: {} }
const speicher = process.__API_STUB
export const aufrufe = speicher.aufrufe
export function setzeAntworten(neu) { speicher.antworten = { ...neu } }
function auspacken(wert) {
  if (wert && typeof wert === 'object' && 'message' in wert && Object.keys(wert).length === 1) {
    return wert.message
  }
  return wert
}
export async function apiCall(methode, args) {
  aufrufe.push([methode, args])
  const kurz = String(methode).split('.').pop()
  const antworten = speicher.antworten
  const wert = typeof antworten[kurz] === 'function' ? antworten[kurz](args) : antworten[kurz]
  if (wert instanceof Error) throw wert
  return wert === undefined ? { success: true } : auspacken(wert)
}
export class AuditConfirmationRequired extends Error {}
export async function apiAntwortPruefen(res) { return res && typeof res.json === 'function' ? res.json() : res }
export function pruefeSitzungsAntwort() {}
export function mitAntwort(wert) { return wert }
export async function apiGet(methode, args) { return apiCall(methode, args) }
`)
writeFileSync(join(STUB, 'toast.mjs'), `
process.__TOASTS ||= []
export const toasts = process.__TOASTS
export function showToast(text, art) { toasts.push([text, art]) }
`)
writeFileSync(join(STUB, 'bestaetigen.mjs'), `
export async function bestaetigen() { return true }
`)
writeFileSync(join(STUB, 'personenwahl.mjs'), `
import { shallowRef } from '${import.meta.resolve('vue')}'
process.__PERSONENWAHL ||= { personenWahl: shallowRef(null), fragen: [] }
export const personenWahl = process.__PERSONENWAHL.personenWahl
export const fragen = process.__PERSONENWAHL.fragen
export function waehlePerson(frage) { fragen.push(frage); return Promise.resolve(null) }
export function personenWahlAntwort(wert) { personenWahl.value = null; return typeof wert === 'string' ? wert : null }
`)
// Der Router wird ERSETZT: die Seite fragt ihn nach der Kennung aus der Adresse.
writeFileSync(join(STUB, 'router.mjs'), `
const kennung = process.__ROUTE_ID || ''
const wechsler = []
export function getRouteParam(schluessel) { return schluessel === 'id' ? kennung : undefined }
export function getRouteParams() { return { id: kennung } }
export function onBeforeEach(fn) { wechsler.push(fn); return () => { const i = wechsler.indexOf(fn); if (i >= 0) wechsler.splice(i, 1) } }
export const __wechsler = wechsler
export function navigate() {}
export const currentHash = { value: '#/gruppe/' + kennung }
`)

const STELLVERTRETER = new Map([
  [join(SRC, 'router'), join(STUB, 'router.mjs')],
  [join(SRC, 'composables/useApi'), join(STUB, 'api.mjs')],
  [join(SRC, 'composables/useToast'), join(STUB, 'toast.mjs')],
  [join(SRC, 'composables/useBestaetigen'), join(STUB, 'bestaetigen.mjs')],
  [join(SRC, 'composables/usePersonenWahl'), join(STUB, 'personenwahl.mjs')],
])

const cache = new Map()
const VUE_URL = import.meta.resolve('vue')

/** Stellvertreter auch dann, wenn der Import mit `.js`/`.mjs`/`.vue` endet. */
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
    if (!spec.startsWith('.')) return v // Paket-Import bleibt
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
const echtSetTimeout = globalThis.setTimeout
const TAKT = 10
async function warten(bedingung, versuche = 80) {
  for (let i = 0; i < versuche; i += 1) {
    if (bedingung()) return true
    await new Promise((loese) => setTimeout(loese, TAKT))
  }
  return bedingung()
}

const api = await import(pathToFileURL(join(STUB, 'api.mjs')).href)
const toastStub = await import(pathToFileURL(join(STUB, 'toast.mjs')).href)

function eigenerZustand(instanz) {
  const setup = instanz && instanz.setupState
  if (setup && Object.keys(setup).some((k) => k !== 'p')) return setup
  const daten = instanz?.proxy?.$data
  if (daten && Object.keys(daten).length) return daten
  return null
}

function leseZustand(zustand) {
  const stand = {}
  for (const name of Object.keys(zustand)) {
    if (name === 'p') continue
    let v
    try {
      v = zustand[name]
      if (typeof v === 'function') continue
      if (v && typeof v === 'object' && 'value' in v) v = v.value
    } catch (_) { continue }
    if (typeof v === 'boolean') stand[name] = v
    else if (Array.isArray(v)) stand[name] = v
  }
  return stand
}

async function mounten(datei, eigenschaften = {}, bauteile = {}) {
  const bauteil = (await import(pathToFileURL(kompilieren(join(SRC, datei))).href)).default
  const host = document.createElement('div')
  document.body.appendChild(host)
  const eigenschaftenRef = Vue.ref({ ...eigenschaften })
  const app = Vue.createApp({
    setup: () => ({ p: eigenschaftenRef }),
    render: () => Vue.h(bauteil, eigenschaftenRef.value),
  })
  for (const [name, bauteilOderObjekt] of Object.entries(bauteile)) {
    app.component(name, bauteilOderObjekt)
  }
  const warnungen = []
  app.config.warnHandler = (meldung) => warnungen.push(meldung)
  app.config.errorHandler = (fehler) => warnungen.push(String(fehler && fehler.stack ? fehler.stack : fehler))
  app.mount(host)
  await tick()
  return {
    host,
    app,
    warnungen,
    zustand: () => {
      let instanz = app._instance
      const gesehen = new Set()
      while (instanz && !gesehen.has(instanz)) {
        gesehen.add(instanz)
        const kandidat = eigenerZustand(instanz)
        if (kandidat) return leseZustand(kandidat)
        instanz = instanz.subTree?.component
      }
      return {}
    },
    weg: () => { try { app.unmount() } catch (_) { /* weg */ } host.remove() },
  }
}

const txt = (el) => (el ? (el.textContent || '').replace(/\s+/g, ' ').trim() : '')

/** Platzhalter für Seitenhüllen: zeichnet nur seine Attribute, KEINE Kinder. */
const PLATZHALTER = {
  props: ['text', 'form', 'anzahl', 'variant'],
  template: `<div :class="['platzhalter', 'platzhalter-' + (form || variant || 'x')]"
                  :aria-label="text || undefined"></div>`,
}

// ── Beispieldaten ──────────────────────────────────────────────────────────
/** Eine Zeile der Gruppenseite — nur die Felder aus `_aufgaben_ausliefern`. */
const aufgabe = (extra = {}) => ({
  name: 'A-1', titel: 'Noten kopieren', erledigt: false, faellig: null,
  erstellt_von: 'M-REB', zugewiesen_an: null, zugewiesen_name: null,
  darf_abhaken: false, darf_bearbeiten: false, ...extra,
})

/** Antwort von `get_gruppe_detail` — `rechte` wie `_rechte_der_einheit` im Backend. */
const gruppeAntwort = ({ aufgaben = [], rechte = {}, mitglieder = [] } = {}) => ({
  success: true,
  is_member: true,
  gruppe: {
    name: 'GRU-1', gruppenname: 'Chor', status: 'Aktiv', beschreibung: 'Singt.',
    treffpunkt: 'Saal', treffzeit: '19:00', dienstbereich: null,
  },
  untergruppen: [],
  mitglieder,
  verantwortliche: [],
  aufgaben,
  ankuendigungen: [],
  wiki_artikel: [],
  rechte: {
    verwalten: false, rollen: false, aufgabe_anlegen: false,
    ankuendigung_anlegen: false, wiki_anlegen: false, ...rechte,
  },
})

/**
 * Die Seite aufbauen. `antwort` darf eine Funktion sein — so antwortet jeder
 * Abruf mit dem AKTUELLEN Stand (nach dem Abhaken anders).
 */
async function gruppenseite(antwort) {
  const naechste = () => (typeof antwort === 'function' ? antwort() : antwort)
  api.setzeAntworten({
    get_gruppe_detail: naechste,
    get_gruppe_termine: () => ({ termine: [] }),
    get_accessible_calendars: () => [],
  })
  process.__ROUTE_ID = 'GRU-1'
  const gemountet = await mounten('pages/GruppeDetail.vue', {}, {
    DkSkelett: PLATZHALTER,
    DkHint: PLATZHALTER,
  })
  const da = await warten(() => !!gemountet.host.querySelector('.grup-aufgabe'))
  assert.ok(da, `Gruppenseite zeigt keine Aufgabe (Aufrufe: ${api.aufrufe.map(([m]) => m).join(', ')})`)
  return gemountet
}

const kurz = (m) => String(m).split('.').pop()
const zaehle = (name) => api.aufrufe.filter(([m]) => kurz(m) === name).length
const knopf = (host, label) => [...host.querySelectorAll('button')]
  .find((b) => b.getAttribute('aria-label') === label)

/** Abhaken über das Kästchen der Zeile (wie im Betrieb). */
function abhaken(host, name = 'A-1') {
  const kaestchen = host.querySelector(`.grup-liste .grup-aufgabe[data-aufgabe="${name}"] input[type="checkbox"]`)
  assert.ok(kaestchen, `Kästchen der Zeile ${name} fehlt`)
  kaestchen.focus()
  kaestchen.checked = true
  kaestchen.dispatchEvent(new Event('change', { bubbles: true }))
  return kaestchen
}

// ══════════════════════════════════════════════════════════════════════════
// 1 · Nach dem Abhaken: EIN `get_gruppe_detail`, keine Termine, kein Skelett
// ══════════════════════════════════════════════════════════════════════════
test('AUFR-1 · 1: Abhaken → genau EIN `get_gruppe_detail`, keine Termin-/Kalender-Abfrage, kein Skelett', async () => {
  let stand = [
    aufgabe({ name: 'A-1', titel: 'Noten kopieren', darf_abhaken: true }),
    aufgabe({ name: 'A-2', titel: 'Stühle stellen', darf_abhaken: true }),
  ]
  const gemountet = await gruppenseite(() => gruppeAntwort({ aufgaben: stand, rechte: { aufgabe_anlegen: true } }))
  const { host, weg, zustand } = gemountet
  // Grundstand: der Erstaufbau hat EINMAL geladen, Termine EINMAL geholt.
  assert.equal(zaehle('get_gruppe_detail'), 1, 'der Erstaufbau lädt mehr als einmal')

  // Ab hier zählt nur, was NACH dem Abhaken passiert.
  const vorher = api.aufrufe.length
  let skelettWaehrend = false
  let ladenWaehrend = null
  api.setzeAntworten({
    get_gruppe_detail: () => {
      // Der Nachlade-Abruf läuft JETZT — hier zeigte ein volles Neuladen sein
      // Skelett und setzte `loading`.
      skelettWaehrend = !!host.querySelector('.platzhalter-zeilen, .dk-skelett')
      ladenWaehrend = zustand().loading
      return new Promise((loese) => echtSetTimeout(() => loese(
        gruppeAntwort({ aufgaben: stand, rechte: { aufgabe_anlegen: true } }),
      ), 30))
    },
    get_gruppe_termine: () => ({ termine: [] }),
    get_accessible_calendars: () => [],
    toggle_aufgabe: ({ aufgabe_id }) => {
      stand = stand.map((a) => (a.name === aufgabe_id ? { ...a, erledigt: true } : a))
      return { success: true, erledigt: true }
    },
  })

  abhaken(host, 'A-1')
  const fertig = await warten(() => zustand().aufgabeLaeuft !== 'A-1'
    && !host.querySelector('.grup-liste .grup-aufgabe[data-aufgabe="A-1"]'), 120)
  assert.ok(fertig, 'das Abhaken lief nicht zu Ende')
  // Der Stellvertreter antwortet verzögert — noch einen Takt nachfassen.
  await new Promise((loese) => echtSetTimeout(loese, 60))

  const nachher = api.aufrufe.slice(vorher).map(([m]) => kurz(m))
  assert.equal(nachher.filter((m) => m === 'get_gruppe_detail').length, 1,
    `nach dem Abhaken wurde ${nachher.filter((m) => m === 'get_gruppe_detail').length}x geladen `
    + `(Aufrufe: ${nachher.join(', ')}) — das zweite Laden ist der Rest von \`nachladenStill\``)
  assert.equal(nachher.filter((m) => m === 'get_gruppe_termine').length, 0,
    `beim Abhaken wurden Termine geholt (Aufrufe: ${nachher.join(', ')})`)
  assert.equal(nachher.filter((m) => m === 'get_accessible_calendars').length, 0,
    `beim Abhaken wurde die Kalenderliste geholt (Aufrufe: ${nachher.join(', ')})`)

  // Kein Skelett, keine Ladeanzeige während des Nachladens.
  assert.equal(typeof ladenWaehrend, 'boolean',
    'der Zustand der Seite war nicht lesbar — der Test wäre blind')
  assert.equal(ladenWaehrend, false,
    'während des Nachladens lief die Ladeanzeige (`loading`) — der stille Weg ist verloren')
  assert.equal(skelettWaehrend, false, 'während des Nachladens stand ein Skelett im DOM')
  assert.equal(host.querySelector('.grup-aufgabe[data-aufgabe="A-1"]'), null,
    'die abgehakte Zeile steht noch in der offenen Liste')

  // Der Fokus (UI-R9d) ist unverändert gesetzt: nächste offene Zeile.
  const fokusDa = await warten(() => !!document.activeElement?.closest?.('.grup-aufgabe'), 40)
  assert.ok(fokusDa, `der Fokus liegt auf ${document.activeElement?.tagName}`)
  assert.equal(document.activeElement.closest('.grup-aufgabe').getAttribute('data-aufgabe'), 'A-2',
    'der Fokus sitzt nicht auf der nächsten offenen Zeile')
  weg()
})

// ══════════════════════════════════════════════════════════════════════════
// 2 · Fehlschlag beim stillen Nachladen: Liste bleibt, keine Meldung
// ══════════════════════════════════════════════════════════════════════════
test('AUFR-1 · 2: stilles Nachladen scheitert → Liste bleibt stehen, kein Fehlerbanner, keine Meldung', async () => {
  const stand = [
    aufgabe({ name: 'A-1', titel: 'Noten kopieren', darf_abhaken: true }),
    aufgabe({ name: 'A-2', titel: 'Stühle stellen', darf_abhaken: true }),
  ]
  const gemountet = await gruppenseite(() => gruppeAntwort({ aufgaben: stand, rechte: { aufgabe_anlegen: true } }))
  const { host, weg, zustand } = gemountet
  toastStub.toasts.length = 0

  api.setzeAntworten({
    // Ein Fehlschlag, wie ihn der Server schickt: ein Fachsatz, den der
    // Fehlerkatalog unverändert durchreicht — so ist die Prüfung „keine
    // Meldung" nicht auf einen Katalogtext angewiesen.
    get_gruppe_detail: () => new Error('Die Verbindung wurde unterbrochen.'),
    get_gruppe_termine: () => ({ termine: [] }),
    get_accessible_calendars: () => [],
    toggle_aufgabe: () => ({ success: true, erledigt: true }),
  })

  abhaken(host, 'A-1')
  const fertig = await warten(() => zustand().aufgabeLaeuft !== 'A-1', 120)
  assert.ok(fertig, 'das Abhaken lief nicht zu Ende')
  await new Promise((loese) => echtSetTimeout(loese, 60))

  // Die Aktion selbst hat funktioniert: die Zeile ist umgeschaltet …
  assert.equal(zustand().loading, false, 'die Ladeanzeige lief — das wäre der volle Weg, nicht der stille')
  // … und die übrige Liste steht weiterhin (kein Zusammenfall der Seite).
  assert.ok(host.querySelector('.grup-aufgabe[data-aufgabe="A-2"]'),
    'die offene Liste ist nach dem gescheiterten Nachladen weg')
  assert.ok(host.querySelector('.grup-datenzeile'), 'die Gruppendaten sind nach dem Fehlschlag weg')
  assert.equal(host.querySelector('.platzhalter-zeilen, .dk-skelett'), null, 'es steht ein Skelett im DOM')
  // Keine Meldung: weder der Fehlerhinweis der Seite noch ein Toast.
  assert.doesNotMatch(txt(host), /unterbrochen|nicht geladen|Laden fehlgeschlagen/,
    `die Seite zeigt eine Fehlermeldung: „${txt(host).slice(0, 200)}“`)
  assert.deepEqual(toastStub.toasts, [],
    `es wurde eine Meldung gezeigt: ${JSON.stringify(toastStub.toasts)}`)
  weg()
})

// ══════════════════════════════════════════════════════════════════════════
// 3 · `rechte` aus der Nachlade-Antwort wird übernommen
// ══════════════════════════════════════════════════════════════════════════
test('AUFR-1 · 3: entzogenes `aufgabe_anlegen` aus der Nachlade-Antwort blendet den Knopf aus', async () => {
  const stand = [aufgabe({ name: 'A-1', titel: 'Noten kopieren', darf_abhaken: true })]
  // Erstaufbau: der Server erlaubt das Anlegen → der Knopf steht.
  let anlegen = true
  const gemountet = await gruppenseite(() => gruppeAntwort({ aufgaben: stand, rechte: { aufgabe_anlegen: anlegen } }))
  const { host, weg, zustand } = gemountet
  assert.ok(knopf(host, 'Aufgabe anlegen'),
    'der Knopf fehlt schon nach dem Erstaufbau — der Test wäre blind')

  // Nach dem Abhaken sagt der Server NEIN (Recht entzogen).
  anlegen = false
  api.setzeAntworten({
    get_gruppe_detail: () => gruppeAntwort({ aufgaben: stand, rechte: { aufgabe_anlegen: anlegen } }),
    get_gruppe_termine: () => ({ termine: [] }),
    get_accessible_calendars: () => [],
    toggle_aufgabe: () => ({ success: true, erledigt: true }),
  })

  abhaken(host, 'A-1')
  const fertig = await warten(() => zustand().aufgabeLaeuft !== 'A-1', 120)
  assert.ok(fertig, 'das Abhaken lief nicht zu Ende')
  await warten(() => knopf(host, 'Aufgabe anlegen') === undefined, 40)
  assert.equal(knopf(host, 'Aufgabe anlegen'), undefined,
    'der Knopf steht noch, obwohl die Nachlade-Antwort `aufgabe_anlegen: false` sagt '
    + '(das stille Nachladen übernimmt `rechte` nicht)')
  weg()
})

// ══════════════════════════════════════════════════════════════════════════
// 4 · Gegenprobe: die offene Detail-Bearbeitung bleibt offen
// ══════════════════════════════════════════════════════════════════════════
test('AUFR-1 · 4: beim stillen Nachladen bleibt die geöffnete Detail-Bearbeitung offen (keine Rückfrage)', async () => {
  const stand = [aufgabe({ name: 'A-1', titel: 'Noten kopieren', darf_abhaken: true })]
  const gemountet = await gruppenseite(() => gruppeAntwort({
    aufgaben: stand, rechte: { verwalten: true, aufgabe_anlegen: true },
  }))
  const { host, weg, zustand } = gemountet

  const bearbeiten = knopf(host, 'Details bearbeiten')
  assert.ok(bearbeiten, '„Details bearbeiten“ fehlt (Server sagt `verwalten: true`)')
  bearbeiten.click()
  const offen = await warten(() => !!host.querySelector('.grup-formular textarea'), 40)
  assert.ok(offen, 'die Detail-Bearbeitung öffnet nicht')

  api.setzeAntworten({
    get_gruppe_detail: () => gruppeAntwort({ aufgaben: stand, rechte: { verwalten: true, aufgabe_anlegen: true } }),
    get_gruppe_termine: () => ({ termine: [] }),
    get_accessible_calendars: () => [],
    toggle_aufgabe: () => ({ success: true, erledigt: true }),
  })
  abhaken(host, 'A-1')
  const fertig = await warten(() => zustand().aufgabeLaeuft !== 'A-1', 120)
  assert.ok(fertig, 'das Abhaken lief nicht zu Ende')

  assert.equal(zustand().editingDesc, true, 'die geöffnete Bearbeitung wurde beim stillen Nachladen geschlossen')
  assert.ok(host.querySelector('.grup-formular textarea'), 'das Bearbeiten-Formular ist aus dem DOM verschwunden')
  weg()
})
