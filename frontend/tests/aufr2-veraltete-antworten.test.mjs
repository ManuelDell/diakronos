/**
 * AUFR-2 — Nachweise am ECHTEN Bauteil (jsdom-Mount, kein Quelltext-Muster).
 *
 * `fetchGruppe` prüfte nicht, ob eine Antwort noch zur aktuellen Anfrage
 * gehört. Ablauf: abhaken (stilles Nachladen läuft) und sofort die
 * (Unter-)Gruppe wechseln — kommt die ÄLTERE Antwort zuletzt an, zeigte die
 * Seite die ALTE Gruppe samt `rechte` (falsche Knöpfe!). Seit AUFR-1
 * überschreibt das stille Nachladen die ganze Seite, das Ausmaß ist also
 * größer; für `nachladen()` nach anderen Aktionen bestand es vorher.
 *
 * Geprüft wird das VERHALTEN:
 *
 *   1. Zwei überlappende Läufe: Gruppe A und Gruppe B sind gleichzeitig
 *      unterwegs, B kommt zuerst an, A danach. Die Seite zeigt B — Daten UND
 *      `rechte` (`aufgabe_anlegen` von B = true, von A = false → Knopf bleibt).
 *   2. Die ALTE Antwort scheitert nach dem Wechsel: kein Fehlerbanner, keine
 *      Meldung; Seite B steht.
 *   3. Gleiches Bild für `ladeMeineKalender`: die Kalenderliste der alten
 *      Gruppe kommt nach dem Wechsel → sie schreibt nichts (kein „+ Termin“
 *      aus fremder Kalenderlage).
 *   4. Gegenprobe: EIN Ladevorgang ohne Überholen lädt unverändert (Daten,
 *      Rechte, kein Fehler).
 *
 * Aufbau wie in aufr1: die SFC werden mit `vue/compiler-sfc` übersetzt,
 * `apiCall` läuft über ein Stellvertreter-Modul (kein Netz). Der Router wird
 * ersetzt und erlaubt dem Test, die Kennung zu WECHSELN — genau der Fall, in
 * dem die alte Instanz noch lebt (App.vue baut sie erst beim Eintreffen des
 * neuen Seitenbündels neu; bis dahin laufen ihre Antworten weiter).
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

// Nur der Takt wird ersetzt (wie aufr1): ein Prüfintervall hielte den Prozess
// sonst am Leben.
const echterInterval = globalThis.setInterval
globalThis.setInterval = (fn, ms, ...rest) => {
  if (!ms) return echterInterval(fn, ms, ...rest)
  return { unref() {}, ref() {}, [Symbol.toPrimitive]: () => 0 }
}

const Vue = await import('vue')

// ── Stellvertreter: `apiCall` ohne Netz + Meldungen mitschreiben ────────────
const TMP = mkdtempSync(join(tmpdir(), 'aufr2-'))
const STUB = join(TMP, 'stubs')
mkdirSync(STUB, { recursive: true })
// Zustand über „process“: die Testdatei und das Bauteil laufen in GETRENNTEN
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
// Der Router wird ERSETZT: die Seite fragt ihn nach der Kennung aus der
// Adresse. AUFR-2 braucht den WECHSEL: `setzeRoute()` stellt die Kennung um,
// die laufende Instanz liest sie über `gruppeId` neu — genau der Fall
// „Antwort trifft nach dem Wechsel ein“.
// Wie im echten Router (`acceptedRoute` ist ein `ref`) liegt die Kennung in
// einem `ref`: nur so ist `gruppeId` (ein `computed` über `getRouteParam`)
// reaktiv — eine einfache Modulvariable würde von Vue nicht verfolgt.
writeFileSync(join(STUB, 'router.mjs'), `
import { ref } from '${import.meta.resolve('vue')}'
const zustand = (process.__ROUTE ||= { id: ref(''), hashRef: ref('#/gruppe/') })
export function getRouteParam(schluessel) { return schluessel === 'id' ? zustand.id.value : undefined }
export function getRouteParams() { return { id: zustand.id.value } }
export function onBeforeEach() { return () => {} }
export function navigate() {}
export const currentHash = zustand.hashRef
export function setzeRoute(id) { zustand.id.value = id; zustand.hashRef.value = '#/gruppe/' + id }
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
async function warten(bedingung, versuche = 100) {
  for (let i = 0; i < versuche; i += 1) {
    if (bedingung()) return true
    await new Promise((loese) => setTimeout(loese, TAKT))
  }
  return bedingung()
}

const api = await import(pathToFileURL(join(STUB, 'api.mjs')).href)
const toastStub = await import(pathToFileURL(join(STUB, 'toast.mjs')).href)
const routerStub = await import(pathToFileURL(join(STUB, 'router.mjs')).href)

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

/**
 * Ein EINZELNER Wert aus dem Setup — auch `null` und Text. `leseZustand`
 * lässt absichtlich alles weg, was weder Boolean noch Liste ist; für
 * „kein Fehler“ (`error === null`) und „keine Meldung“ braucht der Test den
 * Wert selbst.
 */
function wertVon(app, name) {
  let instanz = app._instance
  const gesehen = new Set()
  while (instanz && !gesehen.has(instanz)) {
    gesehen.add(instanz)
    const setup = instanz.setupState
    if (setup && name in setup) {
      const v = setup[name]
      return (v && typeof v === 'object' && 'value' in v) ? v.value : v
    }
    instanz = instanz.subTree?.component
  }
  return undefined
}

/** Alle gebauten Apps dieser Datei — `raeumeAuf()` baut sie vor dem nächsten
 *  Test ab. Ohne das bliebe eine Instanz aus einem gescheiterten Test am Leben
 *  und lüde beim nächsten Routenwechsel mit (ihr Watcher zeigt auf die dann
 *  aktuelle Kennung). */
const offeneApps = []

function raeumeAuf() {
  for (const { app, host } of offeneApps.splice(0)) {
    try { app.unmount() } catch (_) { /* schon weg */ }
    try { host.remove() } catch (_) { /* schon weg */ }
  }
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
  offeneApps.push({ app, host })
  return {
    host,
    app,
    warnungen,
    wert: (name) => wertVon(app, name),
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
    weg: () => {
      const i = offeneApps.findIndex((e) => e.app === app)
      if (i >= 0) offeneApps.splice(i, 1)
      try { app.unmount() } catch (_) { /* weg */ }
      host.remove()
    },
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
/** Antwort von `get_gruppe_detail` — `rechte` wie `_rechte_der_einheit`. */
const gruppeAntwort = ({ name = 'GRU-1', gruppenname = 'Chor', aufgaben = [], rechte = {} } = {}) => ({
  success: true,
  is_member: true,
  gruppe: {
    name, gruppenname, status: 'Aktiv',
    beschreibung: `Beschreibung von ${gruppenname}`,
    treffpunkt: `Treffpunkt ${gruppenname}`, treffzeit: '19:00', dienstbereich: null,
  },
  untergruppen: [],
  mitglieder: [],
  verantwortliche: [],
  aufgaben,
  ankuendigungen: [],
  wiki_artikel: [],
  rechte: {
    verwalten: false, rollen: false, aufgabe_anlegen: false,
    ankuendigung_anlegen: false, wiki_anlegen: false, ...rechte,
  },
})

/** Aufgabe so, wie sie im Aufgaben-Kästchen verwendbar ist (`darf_abhaken`). */
const aufgabe = (extra = {}) => ({
  name: 'A-1', titel: 'Noten kopieren', erledigt: false, faellig: null,
  erstellt_von: 'M-REB', zugewiesen_an: null, zugewiesen_name: null,
  darf_abhaken: true, darf_bearbeiten: false, ...extra,
})

/** Ein Promise, das der Test von Hand auflöst (kontrollierte Reihenfolge). */
function kontrolliert() {
  let loese
  let breche
  const versprechen = new Promise((gut, schlecht) => { loese = gut; breche = schlecht })
  return { versprechen, loese: (wert) => loese(wert), breche: (fehler) => breche(fehler) }
}

const kurz = (m) => String(m).split('.').pop()
/**
 * Aufrufe einer Methode zählen — optional nur für EINE Gruppe. Die Tests
 * laufen in einem Prozess; ohne die Kennung zählte ein Test die (späten)
 * Antworten seines Vorgängers mit.
 */
const zaehle = (name, gruppe) => api.aufrufe.filter(([m, a]) => kurz(m) === name
  && (gruppe === undefined || (a && a.gruppe_id === gruppe))).length
const knopf = (host, label) => [...host.querySelectorAll('button')]
  .find((b) => b.getAttribute('aria-label') === label)

/** Die Seite aufbauen — `antworten` ist das Antwortverzeichnis des Stellvertreters. */
async function gruppenseite(antworten, id = 'GRU-1') {
  // Erst ALLES abbauen, was ein früherer Test stehen ließ: sonst hinge sein
  // Watcher an der neuen Kennung und lüde mit.
  raeumeAuf()
  await new Promise((loese) => setTimeout(loese, 20))
  api.setzeAntworten(antworten)
  api.aufrufe.length = 0
  toastStub.toasts.length = 0
  routerStub.setzeRoute(id)
  const gemountet = await mounten('pages/GruppeDetail.vue', {}, {
    DkSkelett: PLATZHALTER,
    DkHint: PLATZHALTER,
  })
  // Der Wechsel auf die Startkennung ist selbst ein Routenwechsel — die
  // Zählung beginnt deshalb NACH dem Aufbau (siehe `zaehle`).
  return gemountet
}

/** Warten, bis die Seite steht (Gruppenname im Kopf bzw. Fehlerhinweis). */
async function seiteDa(gemountet, versuche = 100) {
  return warten(() => {
    const z = gemountet.zustand()
    return z.loading === false && (!!gemountet.host.querySelector('.grup-datenzeile')
      || !!gemountet.host.querySelector('.platzhalter-err')
      || z.error != null)
  }, versuche)
}

// ══════════════════════════════════════════════════════════════════════════
// 1 · Überholte Antwort schreibt nichts: die Seite zeigt die NEUE Gruppe
// ══════════════════════════════════════════════════════════════════════════
test('AUFR-2 · 1: überholte Antwort (Gruppe A) kommt nach der neueren (B) an → Seite zeigt B, Knopf bleibt', async () => {
  const a = kontrolliert()
  const b = kontrolliert()
  const gemountet = await gruppenseite({
    // Zwei gleichzeitige Läufe: A ist der ERSTE (älter), B der zweite.
    get_gruppe_detail: ({ gruppe_id } = {}) => (gruppe_id === 'GRU-A' ? a.versprechen : b.versprechen),
    get_gruppe_termine: () => ({ termine: [] }),
    get_accessible_calendars: () => [],
  }, 'GRU-A')
  const { host, weg, zustand, wert } = gemountet
  // Beim Aufbau läuft der Ladevorgang für A — er wird NICHT beantwortet,
  // sondern vom Wechsel überholt.
  assert.equal(zaehle('get_gruppe_detail', 'GRU-A'), 1, 'der Erstaufbau lädt nicht genau einmal')

  // Wechsel auf B: die zweite Anfrage geht raus.
  routerStub.setzeRoute('GRU-B')
  const zweite = await warten(() => zaehle('get_gruppe_detail', 'GRU-B') === 1, 40)
  assert.ok(zweite, `der Wechsel löst keinen zweiten Ladevorgang aus (Aufrufe: ${api.aufrufe.map(([m]) => kurz(m)).join(', ')})`)

  // Die NEUERE Antwort (B) kommt zuerst: B darf es anlegen (Knopf steht).
  b.loese(gruppeAntwort({ name: 'GRU-B', gruppenname: 'Bläser', rechte: { aufgabe_anlegen: true } }))
  const bDa = await warten(() => txt(host.querySelector('.grup-datenwert')) !== ''
    && txt(host).includes('Bläser'), 60)
  assert.ok(bDa, `Gruppe B steht nicht auf der Seite (Text: „${txt(host).slice(0, 160)}“)`)
  assert.ok(knopf(host, 'Aufgabe anlegen'), 'der Knopf fehlt schon nach der Antwort von B — der Test wäre blind')

  // Jetzt kommt die ÄLTERE Antwort (A) — mit anderem Recht (false).
  a.loese(gruppeAntwort({ name: 'GRU-A', gruppenname: 'Chor', rechte: { aufgabe_anlegen: false } }))
  await new Promise((loese) => echtSetTimeout(loese, 80))

  const text = txt(host)
  assert.match(text, /Bläser/, 'die Seite zeigt nicht mehr die Gruppe B')
  assert.doesNotMatch(text, /Chor/, `die überholte Antwort von A hat die Seite überschrieben: „${text.slice(0, 200)}“`)
  assert.ok(knopf(host, 'Aufgabe anlegen'),
    'der Knopf „Aufgabe anlegen“ ist verschwunden — die überholte Antwort von A hat `rechte` überschrieben')
  assert.equal(zustand().loading, false, 'die Ladeanzeige blieb hängen')
  assert.equal(wert('error'), null, `die Seite zeigt einen Fehler: ${JSON.stringify(wert('error'))}`)
  weg()
})

// ══════════════════════════════════════════════════════════════════════════
// 2 · Überholte FEHLERANTWORT meldet nichts
// ══════════════════════════════════════════════════════════════════════════
test('AUFR-2 · 2: ältere Antwort scheitert nach dem Wechsel → kein Fehlerbanner, keine Meldung', async () => {
  const a = kontrolliert()
  const b = kontrolliert()
  const gemountet = await gruppenseite({
    get_gruppe_detail: ({ gruppe_id } = {}) => (gruppe_id === 'GRU-F' ? a.versprechen : b.versprechen),
    get_gruppe_termine: () => ({ termine: [] }),
    get_accessible_calendars: () => [],
  }, 'GRU-F')
  const { host, weg, zustand, wert } = gemountet
  toastStub.toasts.length = 0

  routerStub.setzeRoute('GRU-G')
  await warten(() => zaehle('get_gruppe_detail', 'GRU-G') === 1, 40)
  b.loese(gruppeAntwort({ name: 'GRU-G', gruppenname: 'Bläser', rechte: { aufgabe_anlegen: true } }))
  await warten(() => txt(host).includes('Bläser'), 60)
  assert.ok(txt(host).includes('Bläser'), 'Gruppe B steht nicht auf der Seite')

  // Die alte Anfrage scheitert — mit einem Fachsatz, den der Fehlerkatalog
  // unverändert durchreicht.
  a.breche(new Error('Die Verbindung wurde unterbrochen.'))
  await new Promise((loese) => echtSetTimeout(loese, 80))

  assert.equal(wert('error'), null,
    `die überholte Fehlerantwort hat den Fehlerhinweis der Seite gesetzt: ${JSON.stringify(wert('error'))}`)
  assert.doesNotMatch(txt(host), /unterbrochen|nicht geladen|Laden fehlgeschlagen/,
    `die Seite zeigt eine Fehlermeldung: „${txt(host).slice(0, 200)}“`)
  assert.deepEqual(toastStub.toasts, [],
    `es wurde eine Meldung gezeigt: ${JSON.stringify(toastStub.toasts)}`)
  assert.match(txt(host), /Bläser/, 'die Seite der neuen Gruppe ist verschwunden')
  assert.ok(host.querySelector('.grup-datenzeile'), 'der Inhalt der neuen Gruppe steht nicht mehr')
  weg()
})

// ══════════════════════════════════════════════════════════════════════════
// 3 · Auch die Kalenderliste der verlassenen Seite schreibt nichts
// ══════════════════════════════════════════════════════════════════════════
test('AUFR-2 · 3: Rauchtest: späte Kalenderliste nach dem Wechsel stört die Seite nicht', async () => {
  // Gruppe A: Detail antwortet sofort, die Kalenderliste hängt — sie trifft
  // erst nach dem Wechsel ein.
  const kalenderA = kontrolliert()
  const gruppeA = gruppeAntwort({ name: 'GRU-C', gruppenname: 'Chor', rechte: { aufgabe_anlegen: true } })
  const gemountet = await gruppenseite({
    get_gruppe_detail: ({ gruppe_id } = {}) => (gruppe_id === 'GRU-C' ? gruppeA : null),
    get_gruppe_termine: () => ({ termine: [] }),
    get_accessible_calendars: () => kalenderA.versprechen,
  }, 'GRU-C')
  const { host, weg, zustand, wert } = gemountet
  // A ist geladen, die Kalenderliste noch nicht: kein „+ Termin“-Knopf.
  const aDa = await warten(() => txt(host).includes('Chor'), 60)
  assert.ok(aDa, 'Gruppe A steht nicht auf der Seite')
  assert.equal(knopf(host, 'Termin anlegen'), undefined,
    'der Termin-Knopf steht, obwohl die Kalenderliste noch unterwegs ist — der Test wäre blind')

  // Wechsel auf B: B hat KEINEN beschreibbaren Kalender (leere Liste sofort).
  api.setzeAntworten({
    get_gruppe_detail: ({ gruppe_id } = {}) => (gruppe_id === 'GRU-E'
      ? gruppeAntwort({ name: 'GRU-E', gruppenname: 'Bläser' })
      : null),
    get_gruppe_termine: () => ({ termine: [] }),
    get_accessible_calendars: () => [],
  })
  routerStub.setzeRoute('GRU-E')
  const bDa = await warten(() => txt(host).includes('Bläser'), 80)
  assert.ok(bDa, 'Gruppe B steht nicht auf der Seite')
  assert.equal(knopf(host, 'Termin anlegen'), undefined, 'Gruppe B hat einen Kalender, obwohl sie keinen hat')

  // Jetzt kommt die Kalenderliste der ALTEN Seite (A) an.
  kalenderA.loese([{ name: 'K-A', color: '#123456', write: true, gruppe: 'GRU-C', untergruppe: null }])
  await new Promise((loese) => echtSetTimeout(loese, 80))

  assert.equal(knopf(host, 'Termin anlegen'), undefined,
    'die überholte Kalenderliste hat „+ Termin“ auf der Seite von B eingeschaltet '
    + '(die Kalenderlage gehört zu A)')
  assert.match(txt(host), /Bläser/, 'die Seite zeigt nicht mehr Gruppe B')
  assert.equal(wert('error'), null, 'die Kalenderantwort hat einen Fehler gesetzt')
  weg()
})

// ══════════════════════════════════════════════════════════════════════════
// 4 · Gegenprobe: ein einzelner Ladevorgang lädt unverändert
// ══════════════════════════════════════════════════════════════════════════
test('AUFR-2 · 4: einzelner Ladevorgang unverändert (Daten, Rechte, kein Fehler)', async () => {
  // Eigene Kennung: die Tests laufen in einem Prozess, ein früherer Lauf mit
  // derselben Gruppe würde mitgezählt.
  const gemountet = await gruppenseite({
    get_gruppe_detail: () => gruppeAntwort({
      name: 'GRU-D',
      gruppenname: 'Chor',
      aufgaben: [aufgabe()],
      rechte: { aufgabe_anlegen: true, ankuendigung_anlegen: true },
    }),
    get_gruppe_termine: () => ({ termine: [] }),
    get_accessible_calendars: () => [],
  }, 'GRU-D')
  const { host, weg, zustand, wert } = gemountet
  // `seiteDa` wartet auf das ENDE des ersten Ladevorgangs — eine gleichzeitig
  // laufende Route (Kennung aus dem vorigen Test) ist dann ebenfalls fertig.
  const da = await seiteDa(gemountet)
  assert.ok(da, `die Seite wurde nicht fertig geladen (Aufrufe: ${api.aufrufe.map(([m]) => kurz(m)).join(', ')})`)
  // Ab hier darf KEINE weitere Ladung mehr dazukommen — das ist die Aussage
  // „ein einzelner Ladevorgang“.
  const stand = zaehle('get_gruppe_detail', 'GRU-D')
  await new Promise((loese) => echtSetTimeout(loese, 80))
  assert.equal(zaehle('get_gruppe_detail', 'GRU-D'), stand,
    'nach dem fertigen Aufbau lädt die Seite die Gruppe noch einmal')

  assert.match(txt(host), /Chor/, 'der Gruppenname fehlt')
  assert.equal(host.querySelectorAll('.grup-aufgabe').length, 1, 'die Aufgabe fehlt')
  assert.ok(knopf(host, 'Aufgabe anlegen'), 'der Knopf „Aufgabe anlegen“ fehlt (Recht war gesetzt)')
  assert.ok(knopf(host, 'Ankündigung anlegen'), 'der Knopf „Ankündigung anlegen“ fehlt (Recht war gesetzt)')
  assert.equal(zustand().loading, false, 'die Ladeanzeige blieb hängen')
  assert.equal(wert('geladen'), true, '`geladen` blieb aus')
  assert.equal(wert('error'), null, 'die Seite meldet einen Fehler')
  assert.deepEqual(toastStub.toasts, [], `es wurde eine Meldung gezeigt: ${JSON.stringify(toastStub.toasts)}`)
  weg()
})
