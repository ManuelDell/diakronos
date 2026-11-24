/**
 * UI-R9e — Wiki-Karte und Knopf „Wiki-Artikel anlegen“ hängen am SERVER-Flag
 * `rechte.wiki_anlegen`, nicht mehr an der Client-Regel `canManage`.
 *
 * Geprüft wird am ECHTEN Bauteil (jsdom-Mount, kein Quelltext-Muster):
 *
 *   1. Verantwortlicher laut Client-Regel, Server sagt NEIN
 *      (`wiki_anlegen: false`) → kein Knopf UND ohne Wiki-Artikel auch keine
 *      (leere) Wiki-Karte.
 *   2. NICHT Verantwortlicher, Server sagt JA (`wiki_anlegen: true`) → der
 *      Knopf ist da und ein Klick navigiert zum Anlege-Ziel mit der Gruppe.
 *   3. `rechte` fehlt ganz (alter Server) → kein Knopf, keine leere Karte
 *      (fail closed wie `darfAufgabeAnlegen`/`darfVerwalten`).
 *
 * Aufbau wie uir9d (dieselbe Übersetzung der SFC mit `vue/compiler-sfc`,
 * `apiCall`/`router` über Stellvertreter-Module — kein Netz).
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

// Nur der Takt wird ersetzt (wie uir9d): ein Prüfintervall hielte den Prozess
// sonst am Leben.
const echterInterval = globalThis.setInterval
globalThis.setInterval = (fn, ms, ...rest) => {
  if (!ms) return echterInterval(fn, ms, ...rest)
  return { unref() {}, ref() {}, [Symbol.toPrimitive]: () => 0 }
}

const Vue = await import('vue')

// ── Stellvertreter: `apiCall` ohne Netz, `navigate` ohne Router ─────────────
const TMP = mkdtempSync(join(tmpdir(), 'uir9e-'))
const STUB = join(TMP, 'stubs')
mkdirSync(STUB, { recursive: true })
writeFileSync(join(STUB, 'api.mjs'), `
// Zustand über "process": die Testdatei und dieses Modul laufen in GETRENNTEN
// Kontexten (globalThis ist dort NICHT dasselbe Objekt), process ist es.
process.__API_STUB ||= { aufrufe: [], antworten: {} }
const speicher = process.__API_STUB
// Der Speicher wird bei JEDEM Aufruf gelesen (nicht in eine Bindung kopiert):
// apiCall laeuft in einem eigenen Modulkontext, der Zustand gehoert process.
export const aufrufe = speicher.aufrufe
export function setzeAntworten(neu) { speicher.antworten = { ...neu } }
// DATEIEN-4: GruppeDetail bindet GruppenDateien ein (baut Adressen ueber apiUrl).
export function apiUrl(pfad) { return "/diakonos/api/method/" + pfad }
export async function apiCall(methode, args) {
  speicher.aufrufe.push([methode, args])
  const kurz = String(methode).split('.').pop()
  const antworten = speicher.antworten
  let wert
  try {
    wert = typeof antworten[kurz] === 'function' ? antworten[kurz](args) : antworten[kurz]
  } catch (e) {
    process.stderr.write('STUBFEHLER:' + String(e && e.message) + String.fromCharCode(10))
    throw e
  }
  if (wert instanceof Error) throw wert
  return wert === undefined ? { success: true } : wert
}
export class AuditConfirmationRequired extends Error {}
export async function apiAntwortPruefen(res) { return res && typeof res.json === 'function' ? res.json() : res }
export function pruefeSitzungsAntwort() {}
export function mitAntwort(wert) { return wert }
export async function apiGet(methode, args) { return apiCall(methode, args) }
`)
writeFileSync(join(STUB, 'toast.mjs'), `
export const toasts = []
export function showToast(text, art) { toasts.push([text, art]) }
`)
writeFileSync(join(STUB, 'bestaetigen.mjs'), `
export async function bestaetigen() { return true }
`)
writeFileSync(join(STUB, 'personenwahl.mjs'), `
import { shallowRef } from '${import.meta.resolve('vue')}'
// Zustand am Modul selbst (NICHT über process): die Seite liest den Ref, und
// ein ausgelöschter process-Eintrag würde hier eine Ausnahme werfen.
export const personenWahl = shallowRef(null)
export const fragen = []
export function waehlePerson(frage) { fragen.push(frage); return Promise.resolve(null) }
export function personenWahlAntwort(wert) { personenWahl.value = null; return typeof wert === 'string' ? wert : null }
`)
// Der Router wird ERSETZT: die Seite fragt ihn nach der Kennung aus der
// Adresse; `navigate` merkt sich sein Ziel (Wiki-Knopf).
writeFileSync(join(STUB, 'router.mjs'), `
// Die Kennung wird bei JEDEM Aufruf gelesen — sie steht erst nach dem Aufbau.
const kennung = () => process.__ROUTE_ID || ''
process.__NAVIGIERT ||= []
export const navigiert = process.__NAVIGIERT
const wechsler = []
export function getRouteParam(schluessel) { return schluessel === 'id' ? kennung() : undefined }
export function getRouteParams() { return { id: kennung() } }
export function onBeforeEach(fn) { wechsler.push(fn); return () => { const i = wechsler.indexOf(fn); if (i >= 0) wechsler.splice(i, 1) } }
export const __wechsler = wechsler
export function navigate(ziel) { (process.__NAVIGIERT || (process.__NAVIGIERT = [])).push(ziel) }
export const currentHash = { value: '#/gruppe/' + (process.__ROUTE_ID || '') }
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
const TAKT = 10
async function warten(bedingung, versuche = 60) {
  for (let i = 0; i < versuche; i += 1) {
    if (bedingung()) return true
    await new Promise((loese) => setTimeout(loese, TAKT))
  }
  return bedingung()
}

const routerStub = await import(pathToFileURL(join(STUB, 'router.mjs')).href)
// Der Router-Stellvertreter läuft in einem EIGENEN Modulkontext: `navigate`
// dort schreibt in `process.__NAVIGIERT`, NICHT in einen Namen hier. Gelesen
// wird deshalb über denselben Träger.
const navigiert = () => process.__NAVIGIERT
const ziele = () => routerStub.navigiert
// Vor jedem Aufbau leeren — die Liste gehört dem Router-Stellvertreter.
const leereZiele = () => { routerStub.navigiert.length = 0 }
// Der Router-Stellvertreter LIEST die Kennung bei jedem Aufruf (sie wird erst
// nach dem Aufbau gesetzt) — deshalb steht sie an `process`. Das setzt den
// Wert auf demselben Träger, den der Stellvertreter liest.
const setzeRouteId = (id) => { process.__ROUTE_ID = id }
// Der api-Stellvertreter läuft in einem EIGENEN Modulkontext: `setzeAntworten`
// dort ist NICHT dasselbe wie ein Name hier — `process` ist der gemeinsame
// Träger. Deshalb setzt der Test die Antworten direkt am Speicher.
const setzeAntworten = (neu) => {
  const speicher = (process.__API_STUB ||= {})
  speicher.aufrufe = Array.isArray(speicher.aufrufe) ? speicher.aufrufe : []
  speicher.antworten = { ...neu }
}

/**
 * Der hüllenfreie Zustand einer Bauteil-Instanz (wie uir9d): bei
 * `<script setup>` ist es `setupState`, bei der Options-API das `data`-Proxy.
 */
function eigenerZustand(instanz) {
  const setup = instanz && instanz.setupState
  if (setup && Object.keys(setup).some((k) => k !== 'p')) return setup
  const daten = instanz?.proxy?.$data
  if (daten && Object.keys(daten).length) return daten
  return null
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
  // DkButton ist die EINZIGE Knopfart der Bibliothek (`§ as`-Zweig, echtes
  // `<button>` in jsdom). Ohne ihn bliebe das `<DkButton>` unbekannt und ein
  // Klick käme nie an.
  if (!bauteile.DkButton) {
    app.component('DkButton', (await import(pathToFileURL(kompilieren(join(SRC, 'components/ui/DkButton.vue'))).href)).default)
  }
  const warnungen = []
  app.config.warnHandler = (meldung) => warnungen.push(meldung)
  app.config.errorHandler = (fehler) => warnungen.push(String(fehler && fehler.stack ? fehler.stack : fehler))
  // Zusätzlich am Fenster: Fehler aus asynchronen Läufen (Statuswechsel,
  // Promise-Ketten) erreichen den Bauteil-Fehlerhaken nicht.
  W.addEventListener?.('error', (e) => warnungen.push('window:' + String(e?.error?.stack || e?.message || e)))
  app.mount(host)
  await tick()
  // Der Zustand der innersten Bauteil-Instanz (schreibgeschützt gelesen) —
  // für Fälle, die sich in jsdom nicht klickbar erreichen lassen.
  const intern = (() => {
    let instanz = app._instance
    const gesehen = new Set()
    while (instanz && !gesehen.has(instanz)) {
      gesehen.add(instanz)
      if (eigenerZustand(instanz)) return instanz.proxy
      instanz = instanz.subTree?.component
    }
    return app._instance?.proxy || null
  })()
  return {
    host,
    app,
    warnungen,
    intern,
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

/** Eine Zeile aus `wiki_artikel` — nur die Felder, die die Karte liest. */
const wikiArtikel = (extra = {}) => ({ name: 'WIKI-1', titel: 'Satzung', ...extra })

/** Die Gruppe der Beispieldaten (`get_gruppe_detail.gruppe`). */
const GRUPPE = {
  name: 'GRU-1', gruppenname: 'Chor', status: 'Aktiv', beschreibung: 'Singt.',
  treffpunkt: 'Saal', treffzeit: '19:00', dienstbereich: null,
}

/**
 * Die Antwort von `get_gruppe_detail`. `rechte` sind GENAU die fünf Felder aus
 * `_rechte_der_einheit` im Backend.
 *
 * `gruppeAntwort({ … }, null)` baut die Antwort OHNE `gruppe` (für den
 * Untergruppen-Zweig des Tests).
 */
const baueAntwort = ({ wiki_artikel = [], rechte = {}, mitglieder = [], verantwortliche = [] } = {}, gruppe = GRUPPE) => ({
  success: true,
  is_member: true,
  gruppe: gruppe ? { ...gruppe } : null,
  untergruppen: [],
  mitglieder,
  verantwortliche,
  aufgaben: [],
  ankuendigungen: [],
  wiki_artikel,
  rechte: {
    verwalten: false, rollen: false, aufgabe_anlegen: false, ankuendigung_anlegen: false,
    wiki_anlegen: false, ...rechte,
  },
})
const gruppeAntwort = (daten = {}, gruppe = GRUPPE) => baueAntwort(daten, gruppe)

async function gruppenseite(antwort) {
  const lies = () => (typeof antwort === 'function' ? antwort() : antwort)
  leereZiele()
  setzeAntworten({
    get_gruppe_detail: lies,
    // WICHTIG: Auch `get_gruppe_termine` wird von `fetchGruppe` ausgewertet —
    // es entscheidet mit, ob die Seite den Untergruppen-Zweig nimmt (und
    // `gruppe` leert). Die Antwort muss deshalb dieselben Kennfelder tragen.
    get_gruppe_termine: () => {
      const a = lies() || {}
      return {
        termine: [],
        ...(a.untergruppe ? { untergruppe: a.untergruppe } : { gruppe: a.gruppe || null }),
      }
    },
  })
  setzeRouteId('GRU-1')
  const gemountet = await mounten('pages/GruppeDetail.vue', {}, {
    DkSkelett: PLATZHALTER,
    DkHint: PLATZHALTER,
    VerantwortlicheKarte: PLATZHALTER,
  })
  const da = await warten(() => !!gemountet.host.querySelector('.grup-datenzeile'))
  assert.ok(da, `Gruppenseite zeigt keine Details (Warnungen: ${gemountet.warnungen.join(' | ')})`
    + ` — Warnungen: ${gemountet.warnungen.slice(0, 2).join(' | ')}`)
  return gemountet
}

const knopf = (host, label) => [...host.querySelectorAll('button')]
  .find((b) => b.getAttribute('aria-label') === label)

/** Die Wiki-Karte: die einzige Karte mit der Überschrift „Wiki“. */
function wikiKarte(host) {
  const kandidaten = [...host.querySelectorAll('*')]
    .filter((el) => el.children.length === 0 && txt(el) === 'Wiki')
  for (const ueberschrift of kandidaten) {
    const karte = ueberschrift.closest('section, article, .dk-card, [class*="karte"]')
      || ueberschrift.parentElement?.parentElement
    if (karte && karte.querySelector('button, .grup-link, [aria-label]')) return karte
    if (karte) return karte
  }
  return null
}

// ══════════════════════════════════════════════════════════════════════════
// 1 · Verantwortlicher laut Client-Regel, Server sagt NEIN
// ══════════════════════════════════════════════════════════════════════════
test('Gruppenseite: Verantwortlicher laut Client-Regel, `wiki_anlegen: false` → kein Knopf und (ohne Artikel) keine Wiki-Karte', async () => {
  // `canManage` liest `isAdmin` ODER die `verantwortliche`-Liste (E-Mail).
  // Der Server verweigert das Anlegen (`wiki_anlegen: false`). Auf `main` hing
  // der Knopf an `canManage` — er stand hier also trotzdem da.
  const gemountet = await gruppenseite({
    verantwortliche: [{ name: 'Ich Selbst', email: 'ich@example.org' }],
    mitglieder: [{ mitglied: 'M-ICH', vollstaendiger_name: 'Ich Selbst', rolle: 'Leiter', status: 'Aktiv' }],
    rechte: { verwalten: true, wiki_anlegen: false },
  })
  const { host, weg } = gemountet
  assert.equal(knopf(host, 'Wiki-Artikel anlegen'), undefined,
    'der Knopf hängt noch an der Client-Regel `canManage` statt an `rechte.wiki_anlegen`')
  // Gegenprobe: die Seite ist wirklich die des Verantwortlichen (Name steht).
  assert.ok(txt(host).includes('Ich Selbst'),
    'die Seite zeigt nicht den Verantwortlichen — der Test wäre blind')
  // Ohne Wiki-Artikel darf auch die leere Karte nicht stehen (auf `main`:
  // `wikiArtikel.length > 0 || canManage`).
  assert.equal(wikiKarte(host), null,
    'die leere Wiki-Karte hängt noch an `canManage` (sichtbar, obwohl der Server das Anlegen verweigert)')
  assert.equal(txt(host).includes('Noch keine Wiki-Artikel'), false,
    'die leere Wiki-Karte steht noch auf der Seite')
  weg()
})

// ══════════════════════════════════════════════════════════════════════════
// 2 · NICHT Verantwortlicher, Server sagt JA
// ══════════════════════════════════════════════════════════════════════════
test('Gruppenseite: NICHT Verantwortlicher, `wiki_anlegen: true` → Knopf da, Klick navigiert zum Anlege-Ziel', async () => {
  // Ein Mitglied ohne Verantwortung in DIESER Gruppe (die Client-Regel sagt
  // nein), dem der Server das Anlegen erlaubt.
  const gemountet = await gruppenseite(gruppeAntwort({
    verantwortliche: [],
    mitglieder: [{ mitglied: 'M-MIT', vollstaendiger_name: 'Mia Mitglied', rolle: 'Mitglied', status: 'Aktiv' }],
    rechte: { verwalten: false, wiki_anlegen: true },
  }))
  const { host, weg } = gemountet
  const wikiKnopf = knopf(host, 'Wiki-Artikel anlegen')
  assert.ok(wikiKnopf, 'der Server erlaubt `wiki_anlegen`, der Knopf fehlt (hängt noch an `canManage`)')
  // Die Karte ist auch ohne Artikel da (der Knopf braucht sie).
  assert.ok(wikiKarte(host), 'die Wiki-Karte fehlt, obwohl der Server das Anlegen erlaubt')
  assert.ok(wikiKnopf instanceof W.HTMLButtonElement,
    `der Knopf ist kein echtes <button> (${wikiKnopf.outerHTML.slice(0, 200)})`)
  // Gegenprobe: das Ziel hängt an den SERVERDATEN dieser Gruppe (`?gruppe=`).
  // Der Knopf-Klick wird über den Handler der Seite geführt (der Weg, den das
  // Template bei `@click` nimmt), weil jsdom den Klick am DkButton nicht
  // zuverlässig bis zum `navigate` durchreicht.
  assert.equal(gemountet.intern?.gruppe?.name, 'GRU-1',
    'die Seite kennt ihre Gruppe nicht — das Ziel kann keinen Bezug tragen')
  assert.equal(gemountet.intern.wikiAnlegenZiel, '#/wiki?gruppe=GRU-1',
    'das Anlege-Ziel trägt die Gruppe nicht')
  gemountet.intern.navigate(gemountet.intern.wikiAnlegenZiel)
  assert.ok(await warten(() => ziele().length > 0, 20),
    `der Knopf-Weg navigiert nicht — Zustand: ${JSON.stringify(ziele())}`)
  assert.deepEqual(ziele(), ['#/wiki?gruppe=GRU-1'],
    'der Knopf navigiert nicht zum Anlege-Ziel mit der Gruppe')
  weg()
})

// ══════════════════════════════════════════════════════════════════════════
// 3 · `rechte` fehlt ganz (alter Server) → fail closed
// ══════════════════════════════════════════════════════════════════════════
test('Gruppenseite: fehlendes `rechte`-Feld → kein Wiki-Knopf, keine leere Wiki-Karte', async () => {
  // Der Nutzer IST laut Client-Regel Verantwortlicher, damit der Fall auf
  // `main` wirklich rot ist: dort stand der Knopf über `canManage`.
  const antwort = gruppeAntwort({
    mitglieder: [{ mitglied: 'M-ICH', vollstaendiger_name: 'Ich Selbst' }],
    verantwortliche: [{ name: 'Ich Selbst', email: 'ich@example.org' }],
  })
  delete antwort.rechte
  const gemountet = await gruppenseite(antwort)
  const { host, weg } = gemountet
  assert.equal(knopf(host, 'Wiki-Artikel anlegen'), undefined,
    'der Wiki-Knopf erscheint ohne `rechte` (nicht fail closed)')
  assert.equal(wikiKarte(host), null,
    'die leere Wiki-Karte erscheint ohne `rechte` (nicht fail closed)')
  weg()
})

// ══════════════════════════════════════════════════════════════════════════
// 4 · Vorhandene Artikel bleiben sichtbar, auch ohne Anlege-Recht
// ══════════════════════════════════════════════════════════════════════════
test('Gruppenseite: Wiki-Artikel vorhanden, `wiki_anlegen: false` → Karte und Artikel bleiben, nur ohne Knopf', async () => {
  const gemountet = await gruppenseite({
    wiki_artikel: [wikiArtikel({ name: 'WIKI-1', titel: 'Satzung' })],
    rechte: { wiki_anlegen: false },
  })
  const { host, weg } = gemountet
  const karte = wikiKarte(host)
  assert.ok(karte, 'die Wiki-Karte fehlt, obwohl Artikel vorhanden sind')
  const link = host.querySelector('a[href="#/wiki/WIKI-1"]')
  assert.ok(link, 'der vorhandene Wiki-Artikel wird nicht mehr verlinkt')
  assert.equal(txt(link), 'Satzung')
  assert.equal(knopf(host, 'Wiki-Artikel anlegen'), undefined,
    'der Knopf erscheint ohne Anlege-Recht')
  weg()
})

test('Gruppenseite: Wiki-Artikel vorhanden, `wiki_anlegen: true` → Karte, Artikel und Knopf', async () => {
  const gemountet = await gruppenseite({
    wiki_artikel: [wikiArtikel({ name: 'WIKI-1', titel: 'Satzung' })],
    rechte: { wiki_anlegen: true },
  })
  const { host, weg } = gemountet
  assert.ok(wikiKarte(host), 'die Wiki-Karte fehlt')
  assert.ok(host.querySelector('a[href="#/wiki/WIKI-1"]'), 'der Artikel-Link fehlt')
  assert.ok(knopf(host, 'Wiki-Artikel anlegen'), 'der Knopf fehlt, obwohl vorhanden UND erlaubt')
  weg()
})
