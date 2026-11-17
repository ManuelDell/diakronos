/**
 * UI-R9d — Nachweise am ECHTEN Bauteil (jsdom-Mount, kein Quelltext-Muster).
 *
 * Geprüft wird, was die Karte verlangt:
 *
 *   1. GRUPPENSEITE (GruppeDetail.vue): „Aufgabe anlegen“ hängt am
 *      Server-Flag `aufgabe_anlegen`, „Ankündigung“ an `ankuendigung_anlegen`
 *      — NICHT an der Client-Regel `canManage` (isAdmin oder in
 *      `verantwortliche`). Zwei Gegenproben: wer laut Client-Regel
 *      Verantwortlicher ist, aber vom Server `false` bekommt, sieht keinen
 *      Knopf; wer NICHT Verantwortlicher ist, aber `true` bekommt (z. B. MV
 *      mit Recht), sieht ihn.
 *   2. FOKUS nach dem Abhaken: gesucht wird in der Liste DIESER Seite, nicht
 *      im ganzen Dokument. Mit aufgeklappter Liste „erledigt“ landet der Fokus
 *      trotzdem in der offenen Liste.
 *   3. KACHEL (MeineAufgabenWidget.vue): Fokus per Kennung (`data-aufgabe`)
 *      statt per Titel — zwei gleich benannte Aufgaben.
 *   4. Wiederöffnen: danach liegt der Fokus auf der wieder offenen Zeile,
 *      nicht auf `<body>` (Kachel und Gruppenseite).
 *   5. Gruppen-Link ohne `gruppe_name`: sinnvoller Text statt eines leeren
 *      Links (die Kennung der Aufgabe), Ziel bleibt die Gruppe.
 *
 * Aufbau wie in uir9b (dieselbe Übersetzung der SFC mit `vue/compiler-sfc`,
 * `apiCall` über ein Stellvertreter-Modul — kein Netz).
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, mkdtempSync, writeFileSync, rmSync, mkdirSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, dirname, resolve, basename } from 'node:path'
import { pathToFileURL, fileURLToPath } from 'node:url'
import { JSDOM } from 'jsdom'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'
import { gruppenLinkText } from '../src/diakonos/composables/aufgaben.mjs'

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

// Nur der Takt wird ersetzt (wie a10/uir9b): ein Prüfintervall hielte den
// Prozess sonst am Leben.
const echterInterval = globalThis.setInterval
globalThis.setInterval = (fn, ms, ...rest) => {
  if (!ms) return echterInterval(fn, ms, ...rest)
  return { unref() {}, ref() {}, [Symbol.toPrimitive]: () => 0 }
}

const Vue = await import('vue')

// ── Stellvertreter: `apiCall` ohne Netz + `showToast` ohne Meldungsstapel ───
const TMP = mkdtempSync(join(tmpdir(), 'uir9d-'))
const STUB = join(TMP, 'stubs')
mkdirSync(STUB, { recursive: true })
writeFileSync(join(STUB, 'api.mjs'), `
// Zustand über "process": die Testdatei und dieses Modul laufen in GETRENNTEN
// Kontexten (globalThis ist dort NICHT dasselbe Objekt), process ist es.
process.__API_STUB ||= { aufrufe: [], antworten: {} }
const speicher = process.__API_STUB
export const aufrufe = speicher.aufrufe
export function setzeAntworten(neu) { speicher.antworten = { ...neu } }
export async function apiCall(methode, args) {
  aufrufe.push([methode, args])
  const kurz = String(methode).split('.').pop()
  const antworten = speicher.antworten
  const wert = typeof antworten[kurz] === 'function' ? antworten[kurz](args) : antworten[kurz]
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
process.__PERSONENWAHL ||= { personenWahl: shallowRef(null), fragen: [] }
export const personenWahl = process.__PERSONENWAHL.personenWahl
export const fragen = process.__PERSONENWAHL.fragen
export function waehlePerson(frage) { fragen.push(frage); return Promise.resolve(null) }
export function personenWahlAntwort(wert) { personenWahl.value = null; return typeof wert === 'string' ? wert : null }
`)
// Der Router wird ERSETZT: die Seite fragt ihn nach der Kennung aus der
// Adresse (`getRouteParam`) und hängt an `onBeforeEach`.
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
async function warten(bedingung, versuche = 60) {
  for (let i = 0; i < versuche; i += 1) {
    if (bedingung()) return true
    await new Promise((loese) => setTimeout(loese, TAKT))
  }
  return bedingung()
}

const api = await import(pathToFileURL(join(STUB, 'api.mjs')).href)

/**
 * Der hüllenfreie Zustand einer Bauteil-Instanz (wie uir9b): bei
 * `<script setup>` ist es `setupState`, bei der Options-API das `data`-Proxy.
 */
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
    // UI-R9d: der Zustand der INNERSTEN Bauteil-Instanz als Proxy — für Fälle,
    // die sich nicht über einen Klick erreichen lassen (z. B. der Rückfall in
    // `fokusNachAbhaken`). Nur lesend/aufrufend benutzt, nie zum Setzen.
    intern: (() => {
      let instanz = app._instance
      const gesehen = new Set()
      while (instanz && !gesehen.has(instanz)) {
        gesehen.add(instanz)
        const kandidat = eigenerZustand(instanz)
        if (kandidat) return instanz.proxy
        instanz = instanz.subTree?.component
      }
      return app._instance?.proxy || null
    })(),
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
/** Eine Zeile der GRUPPENSEITE — nur die Felder aus `_aufgaben_ausliefern`. */
const gruppenseiteAufgabe = (extra = {}) => ({
  name: 'AUF-1', titel: 'Noten kopieren', erledigt: false, faellig: null,
  erstellt_von: 'M-REB', zugewiesen_an: null, zugewiesen_name: null,
  darf_abhaken: false, darf_bearbeiten: false, ...extra,
})

/** Eine Zeile der KACHEL — `get_meine_aufgaben` schickt zusätzlich `eigene`/`gruppe_name`. */
const kachelAufgabe = (extra = {}) => ({
  name: 'AUF-1', titel: 'Noten kopieren', erledigt: false, faellig: null,
  erstellt_von: 'M-REB', zugewiesen_an: null, zugewiesen_name: null,
  darf_abhaken: false, darf_bearbeiten: false, ...extra,
})

/**
 * Die Antwort von `get_gruppe_detail`. `rechte` sind GENAU die vier Felder aus
 * `_rechte_der_einheit` im Backend.
 */
const gruppeAntwort = ({ aufgaben = [], rechte = {}, mitglieder = [], verantwortliche = [] } = {}) => ({
  success: true,
  is_member: true,
  gruppe: {
    name: 'GRU-1', gruppenname: 'Chor', status: 'Aktiv', beschreibung: 'Singt.',
    treffpunkt: 'Saal', treffzeit: '19:00', dienstbereich: null,
  },
  untergruppen: [],
  mitglieder,
  verantwortliche,
  aufgaben,
  ankuendigungen: [],
  wiki_artikel: [],
  rechte: { verwalten: false, rollen: false, aufgabe_anlegen: false, ankuendigung_anlegen: false, ...rechte },
})

async function gruppenseite(antwort) {
  api.setzeAntworten({
    get_gruppe_detail: () => (typeof antwort === 'function' ? antwort() : antwort),
    get_gruppe_termine: () => ({ termine: [] }),
  })
  process.__ROUTE_ID = 'GRU-1'
  const gemountet = await mounten('pages/GruppeDetail.vue', {}, {
    DkSkelett: PLATZHALTER,
    DkHint: PLATZHALTER,
    VerantwortlicheKarte: PLATZHALTER,
  })
  const da = await warten(() => !!gemountet.host.querySelector('.grup-datenzeile'))
  assert.ok(da, `Gruppenseite zeigt keine Details (Aufrufe: ${api.aufrufe.map(([m]) => m).join(', ')})`)
  return gemountet
}

const knopf = (host, label) => [...host.querySelectorAll('button')]
  .find((b) => b.getAttribute('aria-label') === label)

// ══════════════════════════════════════════════════════════════════════════
// 1 · Gruppenseite: Knöpfe nach SERVER-Rechten, nicht nach `canManage`
// ══════════════════════════════════════════════════════════════════════════
test('Gruppenseite: Verantwortlicher laut Client-Regel, Server sagt NEIN → kein „Aufgabe anlegen“/„Ankündigung“', async () => {
  // `canManage` liest `isAdmin` ODER die `verantwortliche`-Liste (E-Mail).
  // Der Server sagt für BEIDE Anlege-Rechte `false` (z. B. Modul gesperrt,
  // Stufe entzogen). Die Knöpfe dürfen trotzdem nicht erscheinen.
  const gemountet = await gruppenseite({
    verantwortliche: [{ name: 'Ich Selbst', email: 'ich@example.org' }],
    mitglieder: [{ mitglied: 'M-ICH', vollstaendiger_name: 'Ich Selbst', rolle: 'Leiter', status: 'Aktiv' }],
    rechte: { verwalten: true, rollen: false, aufgabe_anlegen: false, ankuendigung_anlegen: false },
  })
  const { host, weg } = gemountet
  assert.equal(knopf(host, 'Aufgabe anlegen'), undefined,
    'der Knopf hängt noch an der Client-Regel `canManage` statt an `aufgabe_anlegen`')
  assert.equal(knopf(host, 'Ankündigung anlegen'), undefined,
    'der Knopf hängt noch an der Client-Regel `canManage` statt an `ankuendigung_anlegen`')
  // Gegenprobe: die Seite ist wirklich die des Verantwortlichen — die
  // Mitglieder-Verwaltung (weiter an `canManage`) steht.
  assert.ok(txt(host).includes('Ich Selbst'), 'die Seite zeigt nicht den Verantwortlichen — der Test wäre blind')
  weg()
})

test('Gruppenseite: NICHT Verantwortlicher, Server sagt JA → „Aufgabe anlegen“ ist da', async () => {
  // Ein MV einer Untergruppe: nicht in `verantwortliche` der Gruppe, aber der
  // Server erlaubt das Anlegen (`aufgabe_anlegen: true`).
  const gemountet = await gruppenseite({
    verantwortliche: [],
    mitglieder: [{ mitglied: 'M-MV', vollstaendiger_name: 'Maria Vertretung', rolle: 'Mitglied', status: 'Aktiv' }],
    rechte: { verwalten: false, rollen: false, aufgabe_anlegen: true, ankuendigung_anlegen: true },
  })
  const { host, weg } = gemountet
  assert.ok(knopf(host, 'Aufgabe anlegen'), 'der Server erlaubt `aufgabe_anlegen`, der Knopf fehlt')
  assert.ok(knopf(host, 'Ankündigung anlegen'), 'der Server erlaubt `ankuendigung_anlegen`, der Knopf fehlt')
  // Er öffnet auch das Formular (kein toter Knopf).
  knopf(host, 'Aufgabe anlegen').click()
  assert.ok(await warten(() => !!host.querySelector('.grup-formular input[placeholder="Was ist zu tun?"]'), 20),
    'der Knopf öffnet das Anlege-Formular nicht')
  weg()
})

test('Gruppenseite: fehlendes `rechte`-Feld (alter Server) → beide Knöpfe zu (fail closed)', async () => {
  const gemountet = await gruppeOhneRechte()
  const { host, weg } = gemountet
  assert.equal(knopf(host, 'Aufgabe anlegen'), undefined)
  assert.equal(knopf(host, 'Ankündigung anlegen'), undefined)
  weg()
})

test('Gruppenseite: fehlendes `rechte`-Feld → auch „Details bearbeiten“ und die Mitgliederpflege zu', async () => {
  const gemountet = await gruppeOhneRechte()
  const { host, weg } = gemountet
  assert.equal(knopf(host, 'Details bearbeiten'), undefined,
    '„Details bearbeiten“ erscheint ohne `rechte` (nicht fail closed)')
  assert.equal(mitgliederVerwaltung(host), null,
    'die Mitglieder-Verwaltung erscheint ohne `rechte` (nicht fail closed)')
  weg()
})

/**
 * Antwort OHNE `rechte` — der alte Server. Der Nutzer IST laut Client-Regel
 * Verantwortlicher (`verantwortliche` + `isAdmin`), damit der Fall auf `main`
 * wirklich rot ist: dort hing alles an `canManage`.
 */
async function gruppeOhneRechte() {
  const antwort = gruppeAntwort({
    mitglieder: [{ mitglied: 'M-ICH', vollstaendiger_name: 'Ich Selbst' }],
    verantwortliche: [{ name: 'Ich Selbst', email: 'ich@example.org' }],
  })
  delete antwort.rechte
  return gruppenseite(antwort)
}

// ── F2 · „Verwalten“ (Beschreibung, Mitgliederpflege) hängt am Server-Flag ──
/**
 * Die Mitglieder-VERWALTUNGskarte: sie trägt das Suchfeld von
 * `MitgliedAuswahl` (`.dk-ma-input`). Die Übersichtskarte hat keins — dort
 * stehen nur Namen. So unterscheidet der Test Pflege von Anzeige.
 */
const mitgliederVerwaltung = (host) => {
  const feld = host.querySelector('.grup-breit .dk-ma-input')
  return feld ? feld.closest('.grup-breit') : null
}

test('Gruppenseite: HV der Hauptgruppe auf der UG-Seite (nicht in `verantwortliche`), Server `verwalten: true` → „Details bearbeiten“ und Mitgliederpflege da', async () => {
  // Genau der Fall, an dem `canManage` ZU ENG war: die Verantwortlichen der
  // UNTERGRUPPE sind leer, der Server erlaubt `verwalten` trotzdem (HV/MV der
  // Obergruppe). `update_untergruppe` und die Mitgliederpflege prüfen
  // `_darf(VERWALTEN, …)` — also muss die Fläche an `rechte.verwalten` hängen.
  const gemountet = await gruppenseite({
    verantwortliche: [],
    mitglieder: [{ mitglied: 'M-HV', vollstaendiger_name: 'Hanna Hauptgruppe', rolle: 'Leiter', status: 'Aktiv' }],
    rechte: { verwalten: true },
  })
  const { host, weg } = gemountet
  assert.ok(knopf(host, 'Details bearbeiten'),
    '„Details bearbeiten“ fehlt, obwohl der Server `verwalten: true` sagt (hängt noch an `canManage`)')
  assert.ok(mitgliederVerwaltung(host),
    'die Mitglieder-Verwaltung fehlt, obwohl der Server `verwalten: true` sagt (hängt noch an `canManage`)')
  // Der Knopf ist nicht tot: er öffnet das Bearbeiten-Formular.
  knopf(host, 'Details bearbeiten').click()
  assert.ok(await warten(() => !!host.querySelector('.grup-formular textarea'), 20),
    'der Knopf öffnet das Bearbeiten-Formular nicht')
  weg()
})

test('Gruppenseite: Verantwortlicher laut Client-Regel, Server `verwalten: false` → KEIN „Details bearbeiten“, KEINE Mitgliederpflege', async () => {
  const gemountet = await gruppenseite({
    verantwortliche: [{ name: 'Ich Selbst', email: 'ich@example.org' }],
    mitglieder: [{ mitglied: 'M-ICH', vollstaendiger_name: 'Ich Selbst', rolle: 'Leiter', status: 'Aktiv' }],
    rechte: { verwalten: false, aufgabe_anlegen: true },
  })
  const { host, weg } = gemountet
  assert.equal(knopf(host, 'Details bearbeiten'), undefined,
    '„Details bearbeiten“ hängt noch an der Client-Regel `canManage` statt an `rechte.verwalten`')
  assert.equal(mitgliederVerwaltung(host), null,
    'die Mitglieder-Verwaltung hängt noch an der Client-Regel `canManage` statt an `rechte.verwalten`')
  // Gegenprobe: die Seite ist die des Verantwortlichen — die NAMEN stehen
  // (Übersichtskarte), nur die Pflege fehlt.
  assert.ok(txt(host).includes('Ich Selbst'), 'die Seite zeigt nicht den Verantwortlichen — der Test wäre blind')
  weg()
})

// ══════════════════════════════════════════════════════════════════════════
// 2 · Fokus nach dem Abhaken: nur in der EIGENEN Liste
// ══════════════════════════════════════════════════════════════════════════
test('Gruppenseite: erledigte Liste aufgeklappt → der Fokus landet TROTZDEM in der offenen Liste', async () => {
  // Die aufgeklappte Liste „erledigt“ steht UNTER der offenen. Die alte Suche
  // über `document` fand die Zeile der nächsten offenen Aufgabe zwar auch —
  // aber sie nahm die ERSTE Zeile mit dieser Kennung im ganzen Dokument. Hier
  // liegt im Dokument eine Fremdzeile VOR dem Bauteil (eine zweite Fläche mit
  // derselben Kennung, z. B. ein zweites Aufgaben-Bauteil): nur die Suche im
  // EIGENEN Bauteil trifft noch die richtige.
  let stand = [
    gruppenseiteAufgabe({ name: 'A-1', titel: 'Noten kopieren', darf_abhaken: true }),
    gruppenseiteAufgabe({ name: 'A-2', titel: 'Stühle stellen', darf_abhaken: true }),
    gruppenseiteAufgabe({ name: 'A-ALT', titel: 'Schon fertig', erledigt: true, darf_abhaken: true }),
  ]
  const gemountet = await gruppenseite(() => gruppeAntwort({ aufgaben: stand, rechte: { aufgabe_anlegen: true } }))
  // Der Stellvertreter liest den BEWEGLICHEN Stand: `toggle_aufgabe` schaltet
  // um, `get_gruppe_detail` (Seite und stilles Nachladen) liefert ihn danach.
  // Eigene Antworttabelle NACH dem Aufbau — `gruppenseite` hat eigene gesetzt.
  api.setzeAntworten({
    get_gruppe_detail: () => gruppeAntwort({ aufgaben: stand }),
    get_gruppe_termine: () => ({ termine: [] }),
    get_accessible_calendars: () => ({ kalender: [] }),
    toggle_aufgabe: ({ aufgabe_id }) => {
      stand = stand.map((a) => (a.name === aufgabe_id ? { ...a, erledigt: true } : a))
      return { success: true, erledigt: true }
    },
  })
  const { host, weg, zustand } = gemountet
  // Erledigte Liste aufklappen (sie zeigt A-ALT).
  const einklappen = host.querySelector('.grup-aufgaben-einklappen')
  assert.ok(einklappen, 'Einklapp-Knopf der erledigten Aufgaben fehlt')
  einklappen.click()
  assert.ok(await warten(() => !!host.querySelector('.grup-aufgaben-erledigt .grup-aufgabe[data-aufgabe="A-ALT"]'), 20),
    'die erledigte Liste klappt nicht auf')

  // Diagnose: was passiert beim Klick?
  // Eine FREMDE Zeile mit derselben Kennung VOR der Seite (anderes Bauteil).
  const fremd = document.createElement('div')
  fremd.className = 'grup-fremd'
  fremd.innerHTML = '<ul><li class="grup-aufgabe" data-aufgabe="A-2"><input type="checkbox"></li></ul>'
  document.body.insertBefore(fremd, document.body.firstChild)

  try {
    const kaestchen = host.querySelector('.grup-liste .grup-aufgabe[data-aufgabe="A-1"] input[type="checkbox"]')
    kaestchen.focus()
    kaestchen.checked = true
    kaestchen.dispatchEvent(new Event('change', { bubbles: true }))
    const gewechselt = await warten(() => !host.querySelector('.grup-liste .grup-aufgabe[data-aufgabe="A-1"]')
      || zustand().aufgabeLaeuft !== 'A-1' && api.aufrufe.some(([m]) => String(m).endsWith('toggle_aufgabe')), 90)
    assert.ok(gewechselt, 'das Abhaken lief nicht zu Ende: ' + JSON.stringify({ laeuft: zustand().aufgabeLaeuft, offen: [...host.querySelectorAll('.grup-liste .grup-aufgabe')].map(z=>z.getAttribute('data-aufgabe')), aufrufe: api.aufrufe.map(([m])=>String(m).split('.').pop()) }))
    await new Promise((loese) => echtSetTimeout(loese, 100))
    assert.ok(document.activeElement?.closest?.('.grup-liste .grup-aufgabe'),
      `der Fokus liegt auf ${document.activeElement?.tagName}`)
    const aktiv = document.activeElement
    assert.equal(aktiv.closest('.grup-aufgabe').getAttribute('data-aufgabe'), 'A-2',
      'der Fokus sitzt nicht auf der nächsten offenen Zeile')
    assert.ok(host.contains(aktiv), 'der Fokus sitzt in einer FREMDEN Zeile (Suche über das ganze Dokument)')
    assert.equal(fremd.contains(aktiv), false, 'der Fokus folgte der Fremdzeile außerhalb des Bauteils')
    // Gegenprobe: die aufgeklappte erledigte Liste stand wirklich offen.
    assert.ok(host.querySelector('.grup-aufgaben-erledigt .grup-aufgabe[data-aufgabe="A-ALT"]'))
  } finally {
    fremd.remove()
    weg()
  }
})

// ══════════════════════════════════════════════════════════════════════════
// 3 · Kachel: Fokus per Kennung, nicht per Titel
// ══════════════════════════════════════════════════════════════════════════
async function kachel(antwort) {
  api.setzeAntworten({ get_meine_aufgaben: () => (typeof antwort === 'function' ? antwort() : antwort) })
  const gemountet = await mounten('components/widgets/MeineAufgabenWidget.vue')
  const fertig = await warten(() => !gemountet.host.querySelector('.dk-widget-skeleton')
    && (!!gemountet.host.querySelector('.ma-liste') || !!gemountet.host.querySelector('.ma-muted')))
  assert.ok(fertig, 'Kachel wurde nicht fertig geladen')
  return gemountet
}

test('Kachel: zwei Aufgaben mit GLEICHEM Titel → der Fokus trifft die richtige Zeile (Kennung)', async () => {
  // A-1 und A-2 heißen beide „Noten kopieren“. Die alte Suche verglich den
  // `aria-label` („„Noten kopieren“ erledigt“) — sie traf immer die ERSTE
  // Zeile. Nach dem Abhaken von A-1 muss der Fokus auf A-2 liegen.
  let erledigt = { 'A-1': false, 'A-2': false }
  const daten = () => [
    kachelAufgabe({ name: 'A-1', titel: 'Noten kopieren', eigene: true, darf_abhaken: true, erledigt: erledigt['A-1'] }),
    kachelAufgabe({ name: 'A-2', titel: 'Noten kopieren', eigene: true, darf_abhaken: true, erledigt: erledigt['A-2'] }),
  ]
  api.setzeAntworten({
    get_meine_aufgaben: () => ({ success: true, darf_anlegen: true, data: daten() }),
    toggle_aufgabe: ({ aufgabe_id }) => {
      erledigt = { ...erledigt, [aufgabe_id]: true }
      return { success: true, erledigt: true }
    },
  })
  const gemountet = await mounten('components/widgets/MeineAufgabenWidget.vue')
  await warten(() => gemountet.host.querySelectorAll('.ma-liste .ma-zeile').length === 2)

  const kaestchen = gemountet.host.querySelector('.ma-liste .ma-zeile[data-aufgabe="A-1"] input[type="checkbox"]')
  assert.ok(kaestchen, 'die Zeile trägt keine Kennung (`data-aufgabe`) — der Fokus kann sie nicht unterscheiden')
  kaestchen.focus()
  kaestchen.checked = true
  kaestchen.dispatchEvent(new Event('change', { bubbles: true }))
  // Auf den ZustAND warten (A-1 ist aus der offenen Liste, A-2 steht), dann
  // auf den FOKUS: der Fokus-Auftrag des Kästchens steht in jsdom hinter den
  // Timer-Runden von `warten`, ein `warten` auf den Fokus wäre also blind.
  const weiter = await warten(() => !gemountet.host.querySelector('.ma-liste .ma-zeile[data-aufgabe="A-1"]')
    && !!gemountet.host.querySelector('.ma-liste .ma-zeile[data-aufgabe="A-2"]')
    && gemountet.zustand().busy !== 'A-1', 60)
  assert.ok(weiter, 'das Abhaken lief nicht zu Ende')
  const fokusDa = await warten(() => document.activeElement !== document.body
    && typeof document.activeElement?.closest === 'function', 40)
  assert.ok(fokusDa, 'der Fokus blieb auf <body>')
  const aktiv = document.activeElement

  const zeile = aktiv?.closest?.('.ma-zeile')
  assert.ok(zeile, 'der Fokus liegt nicht in einer Aufgabenzeile')
  assert.equal(zeile.getAttribute('data-aufgabe'), 'A-2',
    'der Fokus sitzt auf der falschen (gleich benannten) Zeile — die Suche geht noch über den Titel')
  gemountet.weg()
})

// ══════════════════════════════════════════════════════════════════════════
// 4 · Wiederöffnen: Fokus auf der wieder offenen Zeile, nicht auf <body>
// ══════════════════════════════════════════════════════════════════════════
test('Kachel: Wiederöffnen einer erledigten Aufgabe → Fokus auf der wieder offenen Zeile', async () => {
  let erledigt = { 'A-1': false, 'A-2': false }
  const daten = () => [
    kachelAufgabe({ name: 'A-1', titel: 'Noten kopieren', eigene: true, darf_abhaken: true, erledigt: erledigt['A-1'] }),
    kachelAufgabe({ name: 'A-2', titel: 'Stühle stellen', eigene: true, darf_abhaken: true, erledigt: erledigt['A-2'] }),
  ]
  api.setzeAntworten({
    get_meine_aufgaben: () => ({ success: true, darf_anlegen: true, data: daten() }),
    toggle_aufgabe: ({ aufgabe_id }) => {
      erledigt = { ...erledigt, [aufgabe_id]: !erledigt[aufgabe_id] }
      return { success: true, erledigt: erledigt[aufgabe_id] }
    },
  })
  const gemountet = await mounten('components/widgets/MeineAufgabenWidget.vue')
  await warten(() => gemountet.host.querySelectorAll('.ma-liste .ma-zeile').length === 2)
  const { host, weg } = gemountet

  // A-2 abhaken → es liegt in der erledigten Liste.
  const kaestchen = host.querySelector('.ma-liste .ma-zeile[data-aufgabe="A-2"] input[type="checkbox"]')
  kaestchen.focus()
  kaestchen.checked = true
  kaestchen.dispatchEvent(new Event('change', { bubbles: true }))
  await warten(() => !!host.querySelector('.ma-liste-erledigt .ma-zeile[data-aufgabe="A-2"]'), 60)

  // Erledigte aufklappen und A-2 wieder öffnen.
  const knopfErledigt = [...host.querySelectorAll('button')].find((b) => /erledigte Aufgabe/.test(txt(b)))
  assert.ok(knopfErledigt, 'Knopf „erledigte Aufgabe anzeigen“ fehlt')
  knopfErledigt.click()
  const aufgeklappt = await warten(() => !!host.querySelector('.ma-liste-erledigt .ma-zeile[data-aufgabe="A-2"]'), 20)
  assert.ok(aufgeklappt, 'die erledigte Liste klappt nicht auf')
  const wieder = host.querySelector('.ma-liste-erledigt .ma-zeile[data-aufgabe="A-2"] input[type="checkbox"]')
  wieder.focus()
  wieder.checked = false
  wieder.dispatchEvent(new Event('change', { bubbles: true }))

  const offenDa = await warten(() => !!host.querySelector('.ma-liste:not(.ma-liste-erledigt) .ma-zeile[data-aufgabe="A-2"]')
    && host.querySelector('.ma-liste:not(.ma-liste-erledigt) .ma-zeile[data-aufgabe="A-2"] input[type="checkbox"]').disabled === false, 60)
  assert.ok(offenDa, 'die Aufgabe steht nicht wieder in der offenen Liste')
  // Der Fokus-Auftrag des Kästchens steht in jsdom hinter den Timer-Runden:
  // erst den Zustand abwarten, dann EINE Pause der echten Uhr, dann prüfen.
  await new Promise((loese) => echtSetTimeout(loese, 100))
  const zeile = document.activeElement?.closest?.('.ma-zeile')
  assert.notEqual(document.activeElement, document.body, 'der Fokus blieb auf <body>')
  assert.ok(zeile, 'der Fokus liegt nicht in einer Aufgabenzeile')
  assert.equal(zeile.getAttribute('data-aufgabe'), 'A-2', 'der Fokus sitzt nicht auf der wieder geöffneten Zeile')
  assert.ok(host.querySelector('.ma-liste:not(.ma-liste-erledigt)').contains(zeile),
    'die wieder geöffnete Zeile steht nicht in der offenen Liste')
  weg()
})

test('Gruppenseite: Wiederöffnen einer erledigten Aufgabe → Fokus auf der wieder offenen Zeile', async () => {
  let stand = [
    gruppenseiteAufgabe({ name: 'A-1', titel: 'Noten kopieren', darf_abhaken: true }),
    gruppenseiteAufgabe({ name: 'A-ALT', titel: 'Schon fertig', erledigt: true, darf_abhaken: true }),
  ]
  const gemountet = await gruppenseite(() => gruppeAntwort({ aufgaben: stand }))
  api.setzeAntworten({
    get_gruppe_detail: () => gruppeAntwort({ aufgaben: stand }),
    get_gruppe_termine: () => ({ termine: [] }),
    toggle_aufgabe: ({ aufgabe_id }) => {
      stand = stand.map((a) => (a.name === aufgabe_id ? { ...a, erledigt: !a.erledigt } : a))
      const z = stand.find((a) => a.name === aufgabe_id)
      return { success: true, erledigt: z.erledigt }
    },
  })
  const { host, weg, zustand } = gemountet
  const einklappen = host.querySelector('.grup-aufgaben-einklappen')
  assert.ok(einklappen, 'Einklapp-Knopf fehlt')
  einklappen.click()
  assert.ok(await warten(() => !!host.querySelector('.grup-aufgaben-erledigt .grup-aufgabe[data-aufgabe="A-ALT"]'), 20),
    'die erledigte Liste klappt nicht auf')

  const wieder = host.querySelector('.grup-aufgaben-erledigt .grup-aufgabe[data-aufgabe="A-ALT"] input[type="checkbox"]')
  wieder.focus()
  wieder.checked = false
  wieder.dispatchEvent(new Event('change', { bubbles: true }))
  const offenDa = await warten(() => zustand().aufgabeLaeuft !== 'A-ALT'
    && !!host.querySelector('.grup-liste .grup-aufgabe[data-aufgabe="A-ALT"]'), 60)
  assert.ok(offenDa, 'die Aufgabe steht nicht wieder in der offenen Liste')
  await new Promise((loese) => echtSetTimeout(loese, 100))
  assert.notEqual(document.activeElement, document.body, 'der Fokus blieb auf <body>')
  const zeile = document.activeElement?.closest?.('.grup-aufgabe')
  assert.ok(zeile, 'der Fokus liegt nicht in einer Aufgabenzeile')
  assert.equal(zeile.getAttribute('data-aufgabe'), 'A-ALT', 'der Fokus sitzt nicht auf der wieder geöffneten Zeile')
  weg()
})

// ══════════════════════════════════════════════════════════════════════════
// 5 · Link ohne `gruppe_name`
// ══════════════════════════════════════════════════════════════════════════
test('gruppenLinkText: Name, sonst fester Text, nie leer und ohne rohe Kennung', () => {
  assert.equal(gruppenLinkText({ name: 'AUF-1', gruppe: 'GRU-1', gruppe_name: 'Chor' }), 'Chor')
  // UI-R9d (Review F5): der Link führt zur GRUPPE — ohne Namen steht dort ein
  // fester, lesbarer Text, KEINE Kennung der Aufgabe.
  assert.equal(gruppenLinkText({ name: 'AUF-1', gruppe: 'GRU-1', untergruppe: 'UG-2' }), 'Gruppe öffnen')
  assert.equal(gruppenLinkText({ gruppe: 'GRU-1' }), 'Gruppe öffnen')
  assert.equal(gruppenLinkText(null), 'Gruppe öffnen')
  assert.equal(gruppenLinkText({ name: 'AUF-1', gruppe_name: '   ' }), 'Gruppe öffnen')
  for (const a of [{ name: 'AUF-1', gruppe: 'GRU-1' }, null, { name: 'AUF-1', gruppe_name: ' ' }]) {
    const text = gruppenLinkText(a)
    assert.ok(text && text.trim(), 'der Linktext ist leer')
    assert.equal(/AUF-1|GRU-1/.test(text), false, `der Linktext zeigt eine rohe Kennung: ${text}`)
  }
})

test('Kachel: Aufgabe ohne `gruppe_name` → Link hat einen LESBAREN Text, Ziel bleibt die Gruppe', async () => {
  const gemountet = await kachel({
    success: true, darf_anlegen: true,
    data: [kachelAufgabe({ name: 'A-1', titel: 'Für den Chor', gruppe: 'GRU-1', untergruppe: 'UG-2',
      gruppe_name: null, zugewiesen_name: 'Ich Selbst', darf_abhaken: true })],
  })
  const link = gemountet.host.querySelector('.ma-link')
  assert.ok(link, 'der Link zur Gruppe fehlt ganz')
  assert.equal(txt(link), 'Gruppe öffnen', 'der Link hat keinen lesbaren Text')
  assert.equal(link.getAttribute('aria-label'), 'Gruppe öffnen', 'der Link hat keinen zugänglichen Namen')
  // Die Kennung der Aufgabe darf NICHT im sichtbaren Text stehen (rohe Kennung).
  assert.equal(txt(link).includes('A-1'), false, 'der Linktext zeigt die rohe Kennung der Aufgabe')
  assert.equal(link.getAttribute('href'), '#/gruppe/UG-2', 'das Ziel des Links ist nicht mehr die Gruppe')
  gemountet.weg()
})

test('Kachel: zwei Aufgaben ohne `gruppe_name` → gleich benannte Links bleiben unterscheidbar (title)', async () => {
  const gemountet = await kachel({
    success: true, darf_anlegen: true,
    data: [
      kachelAufgabe({ name: 'A-1', titel: 'Eins', gruppe: 'GRU-1', gruppe_name: null, darf_abhaken: true }),
      kachelAufgabe({ name: 'A-2', titel: 'Zwei', gruppe: 'GRU-1', gruppe_name: null, darf_abhaken: true }),
    ],
  })
  const links = [...gemountet.host.querySelectorAll('.ma-link')]
  assert.equal(links.length, 2)
  assert.deepEqual(links.map(txt), ['Gruppe öffnen', 'Gruppe öffnen'])
  const titel = links.map((l) => l.getAttribute('title'))
  assert.deepEqual(titel, ['Aufgabe A-1', 'Aufgabe A-2'],
    'gleich benannte Links tragen keinen unterscheidenden `title` (Kennung)')
  gemountet.weg()
})

test('Kachel: Aufgabe MIT `gruppe_name` → Link nennt weiter den Gruppennamen', async () => {
  const gemountet = await kachel({
    success: true, darf_anlegen: true,
    data: [kachelAufgabe({ name: 'A-1', titel: 'Für den Chor', gruppe: 'GRU-1', untergruppe: 'UG-2',
      gruppe_name: 'Sopranstimmen', darf_abhaken: true })],
  })
  const link = gemountet.host.querySelector('.ma-link')
  assert.ok(link)
  assert.equal(txt(link), 'Sopranstimmen')
  assert.equal(link.getAttribute('href'), '#/gruppe/UG-2')
  gemountet.weg()
})

// ══════════════════════════════════════════════════════════════════════════
// F1 · Kachel: die LETZTE offene Aufgabe abgehakt → Fokus auf den
//      Erledigt-Knopf (nicht auf <body>; der Knopf ist ein DkButton-Bauteil)
// ══════════════════════════════════════════════════════════════════════════
test('Kachel: letzte offene Aufgabe abgehakt → Fokus auf dem Erledigt-Knopf, nicht auf <body>', async () => {
  // `erledigtKnopf` ist eine `DkButton`-Instanz — die hat kein `focus()`, erst
  // ihr Element (`$el`). Ohne das blieb der Fokus auf `<body>`: Tastatur und
  // Vorleseprogramm verloren die Stelle.
  let erledigt = false
  const daten = () => [
    kachelAufgabe({ name: 'A-1', titel: 'Noten kopieren', eigene: true, darf_abhaken: true, erledigt }),
    kachelAufgabe({ name: 'A-ALT', titel: 'Längst fertig', eigene: true, darf_abhaken: true, erledigt: true }),
  ]
  api.setzeAntworten({
    get_meine_aufgaben: () => ({ success: true, darf_anlegen: true, data: daten() }),
    toggle_aufgabe: () => { erledigt = true; return { success: true, erledigt: true } },
  })
  const gemountet = await mounten('components/widgets/MeineAufgabenWidget.vue')
  const { host, weg, zustand } = gemountet
  assert.ok(await warten(() => !!host.querySelector('.ma-liste .ma-zeile[data-aufgabe="A-1"]')), 'die offene Zeile fehlt')

  const kaestchen = host.querySelector('.ma-liste .ma-zeile[data-aufgabe="A-1"] input[type="checkbox"]')
  kaestchen.focus()
  kaestchen.checked = true
  kaestchen.dispatchEvent(new Event('change', { bubbles: true }))
  const durch = await warten(() => !host.querySelector('.ma-liste .ma-zeile[data-aufgabe="A-1"]')
    && zustand().busy !== 'A-1', 60)
  assert.ok(durch, 'das Abhaken lief nicht zu Ende')
  await new Promise((loese) => echtSetTimeout(loese, 100))

  const aktiv = document.activeElement
  assert.notEqual(aktiv, document.body, 'der Fokus blieb auf <body> (Knopf-Instanz ohne `focus()`)')
  const knopfErledigt = [...host.querySelectorAll('button')].find((b) => /erledigte Aufgabe/.test(txt(b)))
  assert.ok(knopfErledigt, 'der Erledigt-Knopf fehlt')
  assert.equal(aktiv, knopfErledigt, `der Fokus liegt auf ${aktiv?.tagName} statt auf dem Erledigt-Knopf`)
  weg()
})

// ══════════════════════════════════════════════════════════════════════════
// F3 · Gruppenseite: Wiederöffnen ohne Ziel → Rückfall, nicht <body>
// ══════════════════════════════════════════════════════════════════════════
test('Gruppenseite: Wiederöffnen der LETZTEN erledigten Aufgabe → Fokus auf der wieder offenen Zeile (nicht <body>)', async () => {
  // Nach dem Wiederöffnen ist die erledigte Liste leer — der Einklapp-Knopf
  // verschwindet. Der frühere Fallback griff nur beim Abhaken, der Fokus fiel
  // auf `<body>`.
  let stand = [
    gruppenseiteAufgabe({ name: 'A-ALT', titel: 'Schon fertig', erledigt: true, darf_abhaken: true }),
  ]
  const gemountet = await gruppenseite(() => gruppeAntwort({ aufgaben: stand }))
  api.setzeAntworten({
    get_gruppe_detail: () => gruppeAntwort({ aufgaben: stand }),
    get_gruppe_termine: () => ({ termine: [] }),
    toggle_aufgabe: ({ aufgabe_id }) => {
      stand = stand.map((a) => (a.name === aufgabe_id ? { ...a, erledigt: !a.erledigt } : a))
      return { success: true, erledigt: stand.find((a) => a.name === aufgabe_id).erledigt }
    },
  })
  const { host, weg, zustand } = gemountet
  const einklappen = host.querySelector('.grup-aufgaben-einklappen')
  assert.ok(einklappen, 'Einklapp-Knopf fehlt')
  einklappen.click()
  assert.ok(await warten(() => !!host.querySelector('.grup-aufgaben-erledigt .grup-aufgabe[data-aufgabe="A-ALT"]'), 20),
    'die erledigte Liste klappt nicht auf')

  const wieder = host.querySelector('.grup-aufgaben-erledigt .grup-aufgabe[data-aufgabe="A-ALT"] input[type="checkbox"]')
  wieder.focus()
  wieder.checked = false
  wieder.dispatchEvent(new Event('change', { bubbles: true }))
  assert.ok(await warten(() => zustand().aufgabeLaeuft !== 'A-ALT'
    && !!host.querySelector('.grup-liste .grup-aufgabe[data-aufgabe="A-ALT"]'), 60),
  'die Aufgabe steht nicht wieder in der offenen Liste')
  await new Promise((loese) => echtSetTimeout(loese, 100))
  assert.notEqual(document.activeElement, document.body, 'der Fokus blieb auf <body>')
  const zeile = document.activeElement?.closest?.('.grup-aufgabe')
  assert.ok(zeile, `der Fokus liegt auf ${document.activeElement?.tagName} statt in der Aufgabenzeile`)
  assert.equal(zeile.getAttribute('data-aufgabe'), 'A-ALT')
  weg()
})

test('Gruppenseite: fokusNachAbhaken ohne offene Zielzeile → Rückfall Einklapp-Knopf, nicht <body>', async () => {
  // Den Rückfall gibt es NUR in der Funktion `fokusNachAbhaken` — sie wird über
  // ein Abhaken erreicht. Der Klick selbst ist hier nicht durchführbar (das
  // Kästchen ist gesperrt), deshalb wird die Funktion direkt mit einer Zeile
  // gerufen, deren Kästchen es im Baum nicht gibt: kein Ziel in der Liste →
  // der Fokus muss auf einem definierten Platz landen.
  const stand = [
    gruppenseiteAufgabe({ name: 'A-1', titel: 'Noten kopieren', darf_abhaken: false }),
    gruppenseiteAufgabe({ name: 'A-ALT', titel: 'Schon fertig', erledigt: true, darf_abhaken: false }),
  ]
  const gemountet = await gruppenseite(() => gruppeAntwort({ aufgaben: stand }))
  const { host, weg, intern } = gemountet
  assert.ok(typeof intern?.fokusNachAbhaken === 'function',
    'die Seite gibt `fokusNachAbhaken` nicht her — der Rückfall ist nicht prüfbar')

  // 1. Wiederöffnen, Zeile nicht (mehr) in der offenen Liste → Einklapp-Knopf.
  intern.fokusNachAbhaken({ name: 'A-WEG', erledigt: false })
  const knopfErledigt = host.querySelector('.grup-aufgaben-einklappen')
  assert.ok(knopfErledigt, 'Einklapp-Knopf der erledigten Aufgaben fehlt')
  assert.notEqual(document.activeElement, document.body,
    'ohne offene Zielzeile blieb der Fokus auf <body> (Rückfall fehlt)')
  assert.equal(document.activeElement, knopfErledigt,
    `der Fokus liegt auf ${document.activeElement?.tagName} statt auf dem Einklapp-Knopf`)

  // 2. Ohne erledigte Aufgaben (der Knopf ist dann weg) → Aufgaben-Überschrift.
  document.activeElement.blur()
  document.body.focus?.()
  intern.fokusNachAbhaken({ name: 'A-AUCH-WEG', erledigt: false })
  // DES-1: die Zahl „3 offen“ steht als Unterzeile im Kartenkopf — der
  // Fokusanker ist das leere `span.grup-fokusanker` an ihrer Stelle.
  const ueberschrift = host.querySelector('.grup-fokusanker')
  assert.ok(ueberschrift, 'die Aufgaben-Überschrift fehlt')
  assert.ok(ueberschrift.hasAttribute('tabindex'),
    'die Aufgaben-Überschrift ist nicht fokussierbar (kein `tabindex`) — der Rückfall kann nicht greifen')
  // DES-1b (Review 4): WEDER `aria-label` am rollenlosen span (unzulässig,
  // Review 6) NOCH `role="status"` (falsche Rolle: der Anker meldet nichts,
  // Review 4). Der Name kommt aus einem sichtbar-versteckten Text INNEN —
  // derselbe Zahltext wie die Unterzeile („3 offen“).
  assert.equal(ueberschrift.getAttribute('aria-label'), null,
    'der Fokusanker trägt noch ein `aria-label` (an einem rollenlosen span unzulässig)')
  assert.equal(ueberschrift.getAttribute('role'), null,
    'der Fokusanker trägt noch eine Rolle (`role="status"` ist hier falsch)')
  const versteckt = ueberschrift.querySelector('.dk-nur-vorlesen')
  assert.ok(versteckt, 'der Fokusanker hat keinen sichtbar-versteckten Text als Namen')
  const name = txt(versteckt)
  assert.match(name, /offen|Aufgaben/,
    `der Fokusanker hat keinen sprechenden Namen (versteckter Text: „${name}“)`)
  // Der Name ist derselbe Zahltext wie die Karten-Unterzeile (eine Quelle).
  assert.equal(name, txt(host.querySelector('.grup-fokusanker .dk-nur-vorlesen')))
  weg()
})
