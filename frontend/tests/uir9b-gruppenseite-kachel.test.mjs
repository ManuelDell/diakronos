/**
 * UI-R9b — Nachweise am ECHTEN Bauteil (Mount im jsdom, keine Quelltext-Muster).
 *
 * Geprüft wird, was die Folgekarte verlangt:
 *
 *   1. GRUPPENSEITE (GruppeDetail.vue) nutzt die Felder aus
 *      `get_gruppe_detail`: Kästchen aktiv nur bei `darf_abhaken`, „⋯“-Menü nur
 *      bei `darf_bearbeiten` mit „Zuweisung ändern“/„Löschen“, `zugewiesen_name`
 *      sichtbar — ohne zweiten Abruf der Aufgabenliste.
 *   2. KACHEL „Meine Aufgaben“ (MeineAufgabenWidget.vue): Leerzustand steht
 *      UNTER dem Knopf „Eigene Aufgabe“; der Knopf erscheint nur bei
 *      `darf_anlegen === true` aus `get_meine_aufgaben` (nicht aus dem Boot).
 *   3. KEIN SPRUNG beim Abhaken: nach dem Abhaken steht KEIN Skelett im DOM
 *      (weder `dk-widget-skeleton` noch `DkSkelett`) und der Fokus ist
 *      definiert (nächste Zeile bzw. Einklapp-Knopf).
 *   4. ZUGÄNGLICHE NAMEN: `aria-label` steht am `<input>` (nicht am `<label>`),
 *      das Personen-Auswahlfeld markiert die Zuweisung mit `aria-pressed` und
 *      sperrt „Zuweisung aufheben“, wenn niemand zugewiesen ist.
 *
 * Aufbau wie in den vorhandenen Mount-Tests (a10/a11): die SFC werden mit
 * `vue/compiler-sfc` übersetzt, Kind-Bauteile bleiben in ihren eigenen Dateien,
 * `apiCall` wird über ein Stellvertreter-Modul ersetzt (kein Netz).
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
  // Manche Namen sind in Node nur lesbar (navigator) — dann über defineProperty.
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

// Nur der Takt wird ersetzt (wie a10): ein Prüfintervall hielte den Prozess
// sonst am Leben.
const echterInterval = globalThis.setInterval
globalThis.setInterval = (fn, ms, ...rest) => {
  if (!ms) return echterInterval(fn, ms, ...rest)
  return { unref() {}, ref() {}, [Symbol.toPrimitive]: () => 0 }
}

const Vue = await import('vue')

// ── Stellvertreter: `apiCall` ohne Netz + `showToast` ohne Meldungsstapel ───
const TMP = mkdtempSync(join(tmpdir(), 'uir9b-'))
const STUB = join(TMP, 'stubs')
mkdirSync(STUB, { recursive: true })
writeFileSync(join(STUB, 'api.mjs'), `
// Zustand über "process": die Testdatei und dieses Modul laufen in GETRENNTEN
// Kontexten (globalThis ist dort NICHT dasselbe Objekt), process ist es.
// Nur so sehen Test und geprüftes Bauteil dieselbe Aufrufliste und dieselben
// Antworten.
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
// Sammel-Integration (UI-R9c + UI-R5b): GruppeDetail bindet das Termin-Formular
// samt Kalender-Store ein, der diese Helfer aus useApi importiert. Ohne Netz
// werden sie hier nur bereitgestellt (die Aufgaben-Tests rufen sie nicht).
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
// Die Personenauswahl ERSETZT das echte `usePersonenWahl.js` — deshalb bringt
// der Stellvertreter denselben Zustand mit (`personenWahl`), damit der Dialog
// ohne Server prüfbar ist.
writeFileSync(join(STUB, 'personenwahl.mjs'), `
import { shallowRef } from '${import.meta.resolve('vue')}'
process.__PERSONENWAHL ||= { personenWahl: shallowRef(null), fragen: [] }
export const personenWahl = process.__PERSONENWAHL.personenWahl
export const fragen = process.__PERSONENWAHL.fragen
export function waehlePerson(frage) { fragen.push(frage); return Promise.resolve(null) }
export function personenWahlAntwort(wert) { personenWahl.value = null; return typeof wert === 'string' ? wert : null }
`)

/**
 * Welche Quelldatei wird durch welchen Stellvertreter ersetzt?
 *
 * Schlüssel ist die Datei ohne Endung: der Import im Bauteil lautet
 * `../composables/useApi.js`, die Ersetzung greift also auf `…/useApi` — mit
 * Endung im Schlüssel traf sie nie und der Test hätte das echte Netz gerufen.
 */
/**
 * Der Router wird ERSETZT: die Seite fragt ihn nach der Kennung aus der Adresse
 * (`getRouteParam`) und hängt an `onBeforeEach`. Im Betrieb füllt das der
 * Routenwechsel; im Test steht der Wert fest — sonst liefe die Seite auf einen
 * `resolveRoute`, der im jsdom ggf. weiterleitet und nichts lädt.
 */
writeFileSync(join(STUB, 'router.mjs'), `
const kennung = process.__ROUTE_ID || ''
const wechsler = []
export function getRouteParam(schluessel) { return schluessel === 'id' ? kennung : undefined }
export function getRouteParams() { return { id: kennung } }
export function onBeforeEach(fn) { wechsler.push(fn); return () => { const i = wechsler.indexOf(fn); if (i >= 0) wechsler.splice(i, 1) } }
export const __wechsler = wechsler
export function navigate() {}
// Sammel-Integration (UI-R9c + UI-R1c): GruppeDetail liest den Reiter aus
// \`currentHash\` (Übersicht vs. Einstellungen). Hier immer die Übersicht.
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

/**
 * Stellvertreter auch dann, wenn der Import mit `.js`/`.mjs`/`.vue` endet: der
 * Pfad wird EINMAL ohne Endung geprüft (Anhängen half nicht — der Import endet
 * auf `.js`, der Schlüssel nicht).
 */
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
    // Auch die KINDER durch die Stellvertreter-Tabelle schicken: sonst holt
    // sich z. B. das Widget das echte `useApi` (und damit das Netz).
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
/** Die ECHTE Uhr (nicht `warten`): für verzögerte Stellvertreter-Antworten. */
const echtSetTimeout = globalThis.setTimeout
/**
 * Warten auf eine Bedingung. Die Schritte sind ABSICHTLICH nicht 0 ms: Vue
 * leert seine Auftragswarteschlange über `Promise`-Mikrotasks, die Antwort des
 * Servers kommt über `setTimeout` — mit reinen `setTimeout(0)`-Runden gewann
 * immer die Uhr und die Prüfung sah die (fertige) Antwort nie.
 */
const TAKT = 10
async function warten(bedingung, versuche = 60) {
  for (let i = 0; i < versuche; i += 1) {
    if (bedingung()) return true
    await new Promise((loese) => setTimeout(loese, TAKT))
  }
  return bedingung()
}

const api = await import(pathToFileURL(join(STUB, 'api.mjs')).href)
const personenwahlStub = await import(pathToFileURL(join(STUB, 'personenwahl.mjs')).href)

/**
 * Der hüllenfreie Zustand einer Bauteil-Instanz: bei `<script setup>` ist es
 * `setupState`, bei der Options-API das `data`-Proxy. Die Hülle trägt nur `p`.
 */
function eigenerZustand(instanz) {
  const setup = instanz && instanz.setupState
  if (setup && Object.keys(setup).some((k) => k !== 'p')) return setup
  const daten = instanz?.proxy?.$data
  if (daten && Object.keys(daten).length) return daten
  return null
}

/**
 * Nur die einfachen Werte eines Zustands (boolean, Liste) — Zähler für die
 * Prüfungen. Getter der Options-API werden gelesen, Fehler dabei ignoriert.
 */
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
 * Mountet ein Bauteil mit Eigenschaften in ein eigenes Host-Element.
 *
 * `bauteile` ersetzt Kind-Bauteile, die im jsdom nicht laufen (Router-Seiten
 * bauen ihre Umgebung selbst) — der Platzhalter zeichnet nur seine Attribute.
 */
async function mounten(datei, eigenschaften = {}, bauteile = {}) {
  const bauteil = (await import(pathToFileURL(kompilieren(join(SRC, datei))).href)).default
  const host = document.createElement('div')
  document.body.appendChild(host)
  const warnungen = []
  const eigenschaftenRef = Vue.ref({ ...eigenschaften })
  const app = Vue.createApp({
    setup: () => ({ p: eigenschaftenRef }),
    render() {
      // Die Platzhalter stehen als Eigenschaften der äußeren App: ein Bauteil,
      // das seine Kinder in `components` ODER in `$options.components` auflöst
      // (GruppeDetail: Options-API), findet sie so — genau wie im Betrieb.
      return Vue.h(bauteil, eigenschaftenRef.value)
    },
  })
  for (const [name, bauteilOderObjekt] of Object.entries(bauteile)) {
    app.component(name, bauteilOderObjekt)
  }
  app.config.warnHandler = (meldung) => warnungen.push(meldung)
  app.config.errorHandler = (fehler) => warnungen.push(String(fehler && fehler.stack ? fehler.stack : fehler))
  app.mount(host)
  await tick()
  return {
    host,
    app,
    warnungen,
    neu: async (neue) => { eigenschaftenRef.value = { ...eigenschaftenRef.value, ...neue }; await tick() },
    /**
     * Der Zustand der gemounteten Seite (UI-R9c): nur so ist `loading` einer
     * Seite WIRKLICH prüfbar — ein Skelett im DOM kann fehlen, obwohl die
     * Seite lädt (`useLadeSkelett` zeigt erst nach 300 ms). Liefert ein leeres
     * Objekt, wenn kein Bauteil mit eigenem Setup gefunden wird.
     */
    zustand: () => {
      let instanz = app._instance
      // Die Host-App liefert nur `p` — weiter bis zum ersten Bauteil mit
      // eigenem Zustand (`setupState`, bei der Options-API die `data`-Bindings).
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

/**
 * Platzhalter für Seitenhüllen (`DkSkelett`, `DkHint`, …): zeichnet nur seine
 * Attribute, KEINE Kinder. Im jsdom bliebe sonst dauerhaft ein Marker stehen —
 * und die Prüfung „kein Skelett nach dem Abhaken“ wäre blind.
 */
const PLATZHALTER = {
  props: ['text', 'form', 'anzahl', 'variant'],
  template: `<div :class="['platzhalter', 'platzhalter-' + (form || variant || 'x')]"
                  :aria-label="text || undefined"></div>`,
}

// ── Beispieldaten (Form von `get_meine_aufgaben` / `get_gruppe_detail`) ─────
const GRUPPENSEITE_FELDER = ['name', 'titel', 'erledigt', 'faellig', 'erstellt_von', 'zugewiesen_an',
  'zugewiesen_name', 'darf_abhaken', 'darf_bearbeiten']

/**
 * Eine Zeile der GRUPPENSEITE — genau die Felder, die `_aufgaben_ausliefern`
 * OHNE `mit_gruppe` schickt (UI-R9c). Fremde Felder werden verworfen: sonst
 * prüfte der Test gegen Daten, die der Server nie liefert.
 */
const gruppenseiteAufgabe = (extra = {}) => {
  const roh = {
    name: 'AUF-1', titel: 'Noten kopieren', erledigt: false, faellig: null,
    erstellt_von: 'M-REB', zugewiesen_an: null, zugewiesen_name: null,
    darf_abhaken: false, darf_bearbeiten: false, ...extra,
  }
  return Object.fromEntries(GRUPPENSEITE_FELDER.map((f) => [f, roh[f]]))
}

/** Eine Zeile der KACHEL — `get_meine_aufgaben` schickt zusätzlich Gruppe/eigene/gruppe_name. */
const aufgabe = (extra = {}) => ({
  name: 'AUF-1', titel: 'Noten kopieren', erledigt: false, faellig: null,
  erstellt_von: 'M-REB', zugewiesen_an: null, zugewiesen_name: null,
  darf_abhaken: false, darf_bearbeiten: false, ...extra,
})

// ══════════════════════════════════════════════════════════════════════════
// 1 · DkCheckbox — der Name gehört aufs Kästchen (input), nicht aufs <label>
// ══════════════════════════════════════════════════════════════════════════
test('DkCheckbox: `ariaLabel` steht am input, ohne Angabe gar kein Attribut', async () => {
  const mit = await mounten('components/ui/DkCheckbox.vue', { label: 'Nur ein Text', ariaLabel: '„Noten kopieren“ erledigt' })
  const input = mit.host.querySelector('input[type="checkbox"]')
  assert.equal(input.getAttribute('aria-label'), '„Noten kopieren“ erledigt')
  assert.equal(input.closest('label').getAttribute('aria-label'), null,
    'das <label> darf den Namen NICHT tragen (dort liest ihn kein Vorleseprogramm am Kästchen)')
  assert.ok(txt(mit.host).includes('Nur ein Text'))
  mit.weg()

  const ohne = await mounten('components/ui/DkCheckbox.vue', { label: 'Nur ein Text' })
  assert.equal(ohne.host.querySelector('input[type="checkbox"]').getAttribute('aria-label'), null)
  ohne.weg()
})

// ══════════════════════════════════════════════════════════════════════════
// 2 · GruppeDetail — Rechte-Felder aus EINER Antwort, kein Sprung beim Abhaken
// ══════════════════════════════════════════════════════════════════════════
const GRUPPE = (aufgaben) => ({
  success: true,
  is_member: true,
  gruppe: {
    name: 'GRU-1', gruppenname: 'Chor', status: 'Aktiv', beschreibung: 'Singt.',
    treffpunkt: 'Saal', treffzeit: '19:00', dienstbereich: null,
  },
  untergruppen: [],
  mitglieder: [],
  verantwortliche: [],
  aufgaben,
  ankuendigungen: [],
  wiki_artikel: [],
})

/**
 * Ein Aufruf der SEITE: Adresse setzen, mounten, warten.
 *
 * `antworten` ist eine Funktion, die den aktuellen Stand liefert (nach dem
 * Abhaken antwortet der Server anders) — so kommt jeder Abruf frisch.
 */
async function gruppenseite(aufgabenStand) {
  api.setzeAntworten({
    get_gruppe_detail: () => GRUPPE(aufgabenStand()),
    get_gruppe_termine: () => ({ termine: [] }),
  })
  process.__ROUTE_ID = 'GRU-1'
  const gemountet = await mounten('pages/GruppeDetail.vue', {}, {
    // Seitenhüllen (Skelett, Hinweis) zeichnen nur ihre Attribute — sonst bliebe
    // im jsdom dauerhaft ein Marker stehen und die Skelett-Prüfung wäre blind.
    DkSkelett: PLATZHALTER,
    DkHint: PLATZHALTER,
    // Die Verantwortlichen-Karte lädt ihre eigene Liste; sie ist nicht
    // Gegenstand dieser Karte.
    VerantwortlicheKarte: PLATZHALTER,
  })
  const da = await warten(() => !!gemountet.host.querySelector('.grup-aufgabe'))
  assert.ok(da, `Gruppenseite zeigt keine Aufgabe (Aufrufe: ${api.aufrufe.map(([m]) => m).join(', ')})`)
  return gemountet
}

test('Gruppenseite: Kästchen aktiv nur mit `darf_abhaken`, `⋯`-Menü nur mit `darf_bearbeiten`', async () => {
  const gemountet = await gruppenseite(() => [
    gruppenseiteAufgabe({ name: 'A-1', titel: 'Noten kopieren', darf_abhaken: true, darf_bearbeiten: true }),
    gruppenseiteAufgabe({ name: 'A-2', titel: 'Stühle stellen', darf_abhaken: false, darf_bearbeiten: false }),
  ])
  const { host, weg } = gemountet
  const kaestchen = [...host.querySelectorAll('.grup-aufgabe input[type="checkbox"]')]
  assert.equal(kaestchen.length, 2, 'je Zeile ein Kästchen')
  assert.equal(kaestchen[0].disabled, false, 'darf_abhaken=true → tippbar')
  assert.equal(kaestchen[1].disabled, true, 'darf_abhaken=false → gesperrt')
  // Grund für die Sperre steht am Kästchen (Zugänglicher Name).
  assert.equal(kaestchen[0].getAttribute('aria-label'), '„Noten kopieren“ erledigt')
  assert.equal(kaestchen[0].closest('label').getAttribute('aria-label'), null,
    'der Name hängt wieder am <label> statt am <input>')
  // Menü: nur die Zeile mit `darf_bearbeiten`.
  assert.equal(host.querySelectorAll('.dk-ui-aktionen-ausloeser').length, 1)
  weg()
})

test('Gruppenseite: „⋯“-Menü bietet NUR „Zuweisung ändern“ und „Löschen“', async () => {
  // UI-R9c: `get_gruppe_detail` schickt kein `gruppe`/`untergruppe` je Aufgabe
  // — der Eintrag „Zur Gruppe …“ war auf der eigenen Gruppenseite ohnehin ein
  // Link auf sich selbst und faktisch abgeschaltet.
  const gemountet = await gruppenseite(() => [
    gruppenseiteAufgabe({ name: 'A-1', titel: 'Noten kopieren', darf_bearbeiten: true }),
  ])
  const ausloeser = gemountet.host.querySelector('.dk-ui-aktionen-ausloeser')
  ausloeser.click()
  const offen = await warten(() => !!document.querySelector('.dk-ui-aktionen-menue'))
  assert.ok(offen, 'Menü öffnet sich nicht')
  const eintraege = [...document.querySelectorAll('.dk-ui-aktionen-menue .dk-ui-aktionen-eintrag')]
  const texte = eintraege.map((e) => txt(e.querySelector('.dk-ui-aktionen-text')))
  assert.deepEqual(texte, ['Zuweisung ändern', 'Löschen'],
    `unerwartete Menüpunkte: ${texte.join(' | ')}`)
  gemountet.weg()
})

test('Gruppenseite: `zugewiesen_name` steht an der Zeile — ohne zweiten Abruf', async () => {
  const gemountet = await gruppenseite(() => [
    gruppenseiteAufgabe({ name: 'A-1', titel: 'Noten kopieren', zugewiesen_an: 'M-MIRA', zugewiesen_name: 'Miriam Saenger' }),
  ])
  assert.match(txt(gemountet.host), /Zugewiesen an Miriam Saenger/)
  assert.deepEqual(api.aufrufe.filter(([m]) => m.endsWith('get_aufgaben')), [],
    'die Aufgabenliste wurde ein ZWEITES Mal geholt')
  gemountet.weg()
})

test('Gruppenseite: nach dem Abhaken kein Skelett, Fokus auf der nächsten Zeile', async () => {
  // UI-R9c — der Befund aus UI-R9b war NICHT belegt: der Stellvertreter
  // antwortete sofort, `loading` kippte in derselben Mikrotask zurück, und
  // `useLadeSkelett` (300 ms Verzögerung) sah nie etwas. Ein Rückfall auf
  // `fetchGruppe()` wäre GRÜN geblieben.
  //
  // Hier prüft der Test deshalb die Ursache statt des Symptoms: WÄHREND die
  // Nachlade-Antwort noch unterwegs ist, darf weder `loading` gesetzt sein
  // noch ein Skelett im DOM stehen — genau das unterscheidet `nachladenStill`
  // von `fetchGruppe`. (echter `loading`-Wert, keine Attrappe: er hängt am
  // Ladeskelett der Seite, s. `skelettSichtbar`.)
  let stand = [
    gruppenseiteAufgabe({ name: 'A-1', titel: 'Noten kopieren', darf_abhaken: true }),
    gruppenseiteAufgabe({ name: 'A-2', titel: 'Stühle stellen', darf_abhaken: true }),
  ]
  const gemountet = await gruppenseite(() => stand)
  // Für diese Prüfung zählt der Zustand NACH dem Abhaken, nicht der Erstaufbau.
  assert.equal(gemountet.host.querySelector('.platzhalter-zeilen, .dk-skelett'), null,
    'schon der Erstaufbau zeigt ein Skelett — der Test wäre blind')

  let skelettWaehrend = false
  let aufgabenWaehrend = null
  let standWaehrend = null
  api.setzeAntworten({
    get_gruppe_detail: () => {
      // Der Abruf kommt JETZT vom Bauteil — hier ist der Moment, in dem ein
      // volles Neuladen sein Skelett zeigt.
      aufgabenWaehrend = gemountet.host.querySelector('.grup-aufgabe[data-aufgabe="A-1"]') !== null
      skelettWaehrend = !!gemountet.host.querySelector('.platzhalter-zeilen, .dk-skelett')
      standWaehrend = { ...gemountet.zustand() }
      return new Promise((loese) => echtSetTimeout(() => loese(GRUPPE(stand)), 20))
    },
    get_gruppe_termine: () => ({ termine: [] }),
    toggle_aufgabe: ({ aufgabe_id }) => {
      stand = stand.map((a) => (a.name === aufgabe_id ? { ...a, erledigt: true } : a))
      return { success: true, erledigt: true }
    },
  })

  const kaestchen = gemountet.host.querySelector('.grup-aufgabe[data-aufgabe="A-1"] input[type="checkbox"]')
  kaestchen.focus()
  kaestchen.checked = true
  kaestchen.dispatchEvent(new Event('change', { bubbles: true }))
  // Erst die verzögerte Stellvertreter-Antwort zustellen (sie hängt am ECHTEN
  // Timer, nicht an `warten`), dann warten, bis `toggleAufgabe` WIRKLICH fertig
  // ist: `aufgabeLaeuft` wird am Ende des `finally` geleert, in derselben
  // Mikrotask setzt der Code den Fokus. Nur auf das Verschwinden der Zeile zu
  // warten war zu früh (unter Last blieb dadurch `document.body` fokussiert).
  await new Promise((loese) => echtSetTimeout(loese, 40))
  const gewechselt = await warten(() => gemountet.zustand().aufgabeLaeuft !== 'A-1'
    && !gemountet.host.querySelector('.grup-aufgabe[data-aufgabe="A-1"]'), 60)

  assert.ok(gewechselt, 'die abgehakte Zeile blieb in der offenen Liste stehen')
  // Der Ausleser muss greifen, sonst prüft der Test nichts.
  assert.equal(typeof standWaehrend?.loading, 'boolean',
    `Zustand der Seite nicht lesbar (Schlüssel: ${Object.keys(standWaehrend || {}).join(', ')})`)
  assert.equal(standWaehrend.loading, false,
    'während des Nachladens lief die Ladeanzeige — das ist `fetchGruppe()`, nicht `nachladenStill()`')
  assert.equal(standWaehrend.skelettSichtbar, false,
    'während des Nachladens lief die Ladeanzeige — das ist `fetchGruppe()`, nicht `nachladenStill()`')
  assert.equal(skelettWaehrend, false, 'während des Nachladens stand ein Skelett im DOM')
  // Der Fokus wird am Ende von `toggleAufgabe` gesetzt; `aufgabeLaeuft` wird
  // davor (im `finally`) geleert. Deshalb hier auf den Fokus warten statt ihn
  // sofort abzulesen — unter Last lag sonst ein Takt dazwischen.
  const fokusDa = await warten(() => !!document.activeElement?.closest?.('.grup-aufgabe'), 40)
  const zustandJetzt = gemountet.zustand()
  const aktiv = document.activeElement
  const zeile = aktiv?.closest?.('.grup-aufgabe')
  assert.ok(fokusDa, `der Fokus liegt auf ${aktiv?.tagName}.${aktiv?.className}`
    + ` (Zustand: ${JSON.stringify({ aufgabeLaeuft: zustandJetzt.aufgabeLaeuft, anzahl: zustandJetzt.aufgaben?.length })})`)
  assert.equal(zeile.getAttribute('data-aufgabe'), 'A-2', 'der Fokus sitzt nicht auf der nächsten offenen Zeile')
  gemountet.weg()
})

test('Gruppenseite: letztes Kästchen abgehakt → Fokus auf dem Einklapp-Knopf', async () => {
  let stand = [gruppenseiteAufgabe({ name: 'A-1', titel: 'Noten kopieren', darf_abhaken: true })]
  const gemountet = await gruppenseite(() => stand)
  api.setzeAntworten({
    get_gruppe_detail: () => GRUPPE(stand),
    get_gruppe_termine: () => ({ termine: [] }),
    toggle_aufgabe: () => { stand = stand.map((a) => ({ ...a, erledigt: true })); return { success: true, erledigt: true } },
  })
  const kaestchen = gemountet.host.querySelector('.grup-aufgabe[data-aufgabe="A-1"] input[type="checkbox"]')
  kaestchen.focus()
  kaestchen.checked = true
  kaestchen.dispatchEvent(new Event('change', { bubbles: true }))
  // UI-R9c: erst warten, bis `aufgabeLaeuft` wieder leer ist — der Fokus wird
  // am Ende von `toggleAufgabe` gesetzt, nicht wenn die Zeile verschwindet.
  const fertig = await warten(() => gemountet.zustand().aufgabeLaeuft !== 'A-1'
    && !!gemountet.host.querySelector('.grup-aufgaben-einklappen'), 60)
  assert.ok(fertig, 'das Abhaken lief nicht zu Ende')
  const knopfDa = !!gemountet.host.querySelector('.grup-aufgaben-einklappen')
  assert.ok(knopfDa, 'der Einklapp-Knopf der erledigten Aufgaben fehlt')
  const aktiv = document.activeElement
  assert.ok(aktiv?.classList?.contains('grup-aufgaben-einklappen'),
    `der Fokus liegt auf ${aktiv?.tagName}.${aktiv?.className}`)
  assert.match(txt(aktiv), /1 erledigte Aufgabe anzeigen/)
  assert.equal(aktiv.tagName, 'BUTTON', 'der Einklapp-Knopf ist kein Knopf der Bibliothek')
  // UI-R9c (WCAG 2.5.3): kein abweichendes aria-label — der zugängliche Name
  // ist der sichtbare Text, und der schaltet beim Klick um.
  assert.equal(aktiv.getAttribute('aria-label'), null,
    'der Knopf trägt wieder ein aria-label, das dem sichtbaren Text widerspricht')
  aktiv.click()
  await warten(() => /ausblenden/.test(txt(aktiv)), 20)
  assert.equal(txt(aktiv), '1 erledigte Aufgabe ausblenden', 'der sichtbare Text schaltet nicht um')
  assert.equal(aktiv.getAttribute('aria-expanded'), 'true')
  gemountet.weg()
})

// ══════════════════════════════════════════════════════════════════════════
// 2 · Kachel „Meine Aufgaben“ — Leerzustand, Knopf, kein Sprung
// ══════════════════════════════════════════════════════════════════════════
async function kachel(antwort) {
  api.setzeAntworten({ get_meine_aufgaben: antwort })
  const gemountet = await mounten('components/widgets/MeineAufgabenWidget.vue')
  const fertig = await warten(() => !gemountet.host.querySelector('.dk-widget-skeleton')
    && (!!gemountet.host.querySelector('.ma-liste') || !!gemountet.host.querySelector('.ma-muted')))
  assert.ok(fertig, 'Kachel wurde nicht fertig geladen')
  return gemountet
}

test('Kachel leer + darf_anlegen → Knopf „Eigene Aufgabe“, Leertext darunter, KEIN Leer-Block der Karte', async () => {
  const { host, weg } = await kachel({ success: true, data: [], darf_anlegen: true })
  const knopf = [...host.querySelectorAll('button')].find((b) => /Eigene Aufgabe/.test(txt(b)))
  assert.ok(knopf, 'Knopf „Eigene Aufgabe“ fehlt bei leerer Liste')
  assert.equal(host.querySelector('.dk-widget-empty'), null,
    'Karte zeigt den Leer-Block — dort verschwindet der Knopf')
  const leer = [...host.querySelectorAll('p')].find((p) => /Keine Aufgaben\./.test(txt(p)))
  assert.ok(leer, 'Leertext fehlt')
  assert.equal(knopf.compareDocumentPosition(leer) & 4, 4, 'Leertext steht nicht NACH dem Knopf')
  weg()
})

test('Kachel leer + darf_anlegen=false → kein Knopf, aber der Leertext', async () => {
  const { host, weg } = await kachel({ success: true, data: [], darf_anlegen: false })
  assert.equal([...host.querySelectorAll('button')].find((b) => /Eigene Aufgabe/.test(txt(b))), undefined)
  assert.match(txt(host), /Keine Aufgaben\./)
  // UI-R9c: ohne Recht verspricht der Text auch kein Anlegen.
  assert.ok(!txt(host).includes('legst du hier an'),
    'der Leertext verspricht „Eigene Aufgabe“ anlegen, obwohl der Knopf fehlt')
  assert.match(txt(host), /Gruppenaufgaben erscheinen hier/)
  weg()
})

test('Kachel: „Eigene Aufgabe“ entscheidet der SERVER, nicht das Boot-Objekt', async () => {
  const vorher = globalThis.__DIakonosBOOT
  globalThis.__DIakonosBOOT = { ...vorher, module_sichtbar: ['aufgaben'] }
  window.__DIakonosBOOT = globalThis.__DIakonosBOOT
  const { host, weg } = await kachel({ success: true, data: [], darf_anlegen: false })
  assert.equal([...host.querySelectorAll('button')].find((b) => /Eigene Aufgabe/.test(txt(b))), undefined,
    'die alte Herleitung aus `module_sichtbar` ist wieder da')
  globalThis.__DIakonosBOOT = vorher
  window.__DIakonosBOOT = vorher
  weg()
})

test('Kachel gefüllt: eigene + zugewiesene Aufgabe, Gruppen-Link mit NAMEN, erledigte eingeklappt', async () => {
  // UI-R9c: der Server schickt `gruppe_name` (R-12k) — die Kachel zeigte die
  // Kennung („UG-2“). Kennung ≠ Name ist Pflicht, sonst prüft der Test nichts.
  const { host, weg } = await kachel({
    success: true,
    darf_anlegen: true,
    data: [
      aufgabe({ name: 'A-1', titel: 'Eigene Sache', eigene: true, gruppe_name: null, darf_abhaken: true }),
      aufgabe({ name: 'A-2', titel: 'Für den Chor', gruppe: 'GRU-1', untergruppe: 'UG-2',
        gruppe_name: 'Sopranstimmen', zugewiesen_name: 'Ich Selbst', darf_abhaken: true }),
      aufgabe({ name: 'A-3', titel: 'Schon fertig', eigene: true, gruppe_name: null, erledigt: true,
        darf_abhaken: true }),
    ],
  })
  const text = txt(host)
  assert.match(text, /Eigene Sache/)
  assert.match(text, /Für den Chor/)
  assert.match(text, /Zugewiesen an Ich Selbst/)
  const link = host.querySelector('.ma-link')
  assert.ok(link, 'Link zur Gruppe fehlt')
  assert.equal(txt(link), 'Sopranstimmen', 'Link nennt nicht `gruppe_name` vom Server')
  assert.equal(link.getAttribute('href'), '#/gruppe/UG-2', 'die Kennung gehört nur in die Adresse')
  assert.match(text, /1 erledigte Aufgabe anzeigen/)
  assert.ok(!text.includes('Schon fertig'), 'erledigte Aufgabe steht aufgeklappt da')
  // Der Name des Kästchens steht am input.
  const input = host.querySelector('.ma-zeile input[type="checkbox"]')
  assert.equal(input.getAttribute('aria-label'), '„Eigene Sache“ erledigt')
  weg()
})

test('Kachel: ohne `gruppe_name` (alter Server) steht kein leerer Link da', async () => {
  // Fail-closed-Leertext: `null` bei eigenen Aufgaben heißt „nichts anzeigen“ —
  // die Kennung ist KEIN Ersatz mehr (sie war der Fehler).
  const { host, weg } = await kachel({
    success: true, darf_anlegen: true,
    data: [aufgabe({ name: 'A-1', titel: 'Für den Chor', gruppe: 'GRU-1', untergruppe: 'UG-2',
      gruppe_name: null, zugewiesen_name: 'Ich Selbst', darf_abhaken: true })],
  })
  const link = host.querySelector('.ma-link')
  assert.ok(link, 'der Link zur Gruppe fehlt ganz')
  assert.equal(txt(link), '')
  assert.equal(link.getAttribute('href'), '#/gruppe/UG-2')
  assert.ok(!txt(host).includes('UG-2'), 'die Kennung steht als Text in der Kachel')
  weg()
})

test('Kachel: nach dem Abhaken kein Skelett, die Zeile bleibt stehen', async () => {
  let erledigt = false
  api.setzeAntworten({
    get_meine_aufgaben: () => ({
      success: true, darf_anlegen: true,
      data: [aufgabe({ name: 'A-1', titel: 'Noten kopieren', darf_abhaken: true, erledigt })],
    }),
    toggle_aufgabe: () => { erledigt = true; return { success: true, erledigt: true } },
  })
  const gemountet = await mounten('components/widgets/MeineAufgabenWidget.vue')
  await warten(() => !!gemountet.host.querySelector('.ma-zeile input[type="checkbox"]'))
  let skelettGesehen = false
  const beobachter = new MutationObserver(() => {
    if (gemountet.host.querySelector('.dk-widget-skeleton')) skelettGesehen = true
  })
  beobachter.observe(gemountet.host, { childList: true, subtree: true })

  const kaestchen = gemountet.host.querySelector('.ma-zeile input[type="checkbox"]')
  kaestchen.checked = true
  kaestchen.dispatchEvent(new Event('change', { bubbles: true }))
  await warten(() => !!gemountet.host.querySelector('.ma-erledigt'), 60)
  beobachter.disconnect()

  assert.equal(skelettGesehen, false, 'Skelett blitzte beim Abhaken auf')
  const text = txt(gemountet.host)
  assert.match(text, /1 erledigte Aufgabe anzeigen/, 'die abgehakte Zeile steht nicht unter „erledigt“')
  gemountet.weg()
})

test('Kachel: „Nichts offen“ nur, wenn wirklich nichts offen ist', async () => {
  // UI-R9c: Die Bedingung war vertauscht — die Meldung stand, wenn AUFgaben
  // offen waren, und fehlte, wenn alles erledigt war.
  const nurOffen = await kachel({
    success: true, darf_anlegen: true,
    data: [aufgabe({ name: 'A-1', titel: 'Noten kopieren', darf_abhaken: true })],
  })
  assert.ok(!txt(nurOffen.host).includes('Nichts offen'),
    'offene Aufgabe da, trotzdem steht „Nichts offen“')
  assert.equal(nurOffen.host.querySelector('.ma-muted'), null)
  nurOffen.weg()

  const nurErledigt = await kachel({
    success: true, darf_anlegen: true,
    data: [aufgabe({ name: 'A-2', titel: 'Schon fertig', eigene: true, erledigt: true, darf_abhaken: true })],
  })
  assert.match(txt(nurErledigt.host), /Nichts offen — gute Arbeit\./,
    'nur erledigte Aufgaben, aber die Meldung fehlt')
  nurErledigt.weg()
})

test('Kachel: nach dem Abhaken landet der Fokus NICHT auf <body> — nächste Zeile bzw. Einklapp-Knopf', async () => {
  // UI-R9c: die abgehakte Zeile verschwindet, der Fokus fiel auf <body> —
  // für Vorleseprogramme und Tastatur war die Stelle danach weg.
  let erledigt = { 'A-1': false, 'A-2': false }
  const daten = () => [
    aufgabe({ name: 'A-1', titel: 'Noten kopieren', eigene: true, darf_abhaken: true, erledigt: erledigt['A-1'] }),
    aufgabe({ name: 'A-2', titel: 'Stühle stellen', eigene: true, darf_abhaken: true, erledigt: erledigt['A-2'] }),
  ]
  api.setzeAntworten({
    get_meine_aufgaben: () => ({ success: true, darf_anlegen: true, data: daten() }),
    toggle_aufgabe: ({ aufgabe_id }) => {
      erledigt = { ...erledigt, [aufgabe_id]: true }
      return { success: true, erledigt: true }
    },
  })
  const gemountet = await mounten('components/widgets/MeineAufgabenWidget.vue')
  await warten(() => gemountet.host.querySelectorAll('.ma-zeile input[type="checkbox"]').length === 2)

  const kaestchen = gemountet.host.querySelector('.ma-zeile input[type="checkbox"]')
  kaestchen.focus()
  kaestchen.checked = true
  kaestchen.dispatchEvent(new Event('change', { bubbles: true }))
  const weiter = await warten(() => gemountet.host.querySelectorAll('.ma-liste .ma-zeile .ma-titel').length === 1
    && document.activeElement !== document.body, 60)
  assert.ok(weiter, `der Fokus blieb auf ${document.activeElement?.tagName}`)
  const aktiv = document.activeElement
  const zeile = aktiv?.closest?.('.ma-zeile')
  assert.ok(zeile, 'der Fokus liegt nicht in einer Aufgabenzeile')
  assert.equal(txt(zeile.querySelector('.ma-titel')), 'Stühle stellen', 'der Fokus sitzt nicht auf der nächsten offenen Zeile')

  // Letztes Kästchen: danach gibt es keine offene Zeile mehr — Ziel ist der
  // Knopf „Erledigte anzeigen“.
  const letztes = gemountet.host.querySelector('.ma-zeile input[type="checkbox"]')
  letztes.focus()
  letztes.checked = true
  letztes.dispatchEvent(new Event('change', { bubbles: true }))
  const amKnopf = await warten(() => /erledigte Aufgabe/.test(txt(document.activeElement || {})), 60)
  assert.ok(amKnopf, `der Fokus liegt auf ${document.activeElement?.tagName}.${document.activeElement?.className}`)
  assert.match(txt(document.activeElement), /2 erledigte Aufgaben anzeigen/)
  gemountet.weg()
})

// ══════════════════════════════════════════════════════════════════════════
// 3 · PersonenWahl — aktuelle Zuweisung markiert, „Aufheben“ nur wenn nötig
// ══════════════════════════════════════════════════════════════════════════
test('PersonenWahl: aria-pressed an der aktuellen Person, „Aufheben“ gesperrt ohne Zuweisung', async () => {
  // Derselbe Zustand, den auch der Dialog liest (Stellvertreter-Modul).
  const dialogModul = await import(pathToFileURL(join(STUB, 'personenwahl.mjs')).href)
  dialogModul.personenWahl.value = {
    titel: 'Zuweisung ändern',
    optionen: [{ value: 'M-MIRA', label: 'Miriam Saenger' }, { value: 'M-SAM', label: 'Samuel Saenger' }],
    aktuell: 'M-SAM',
  }
  // Der Dialog liegt in einem Teleport am <body> — er steht NICHT im Host.
  const mit = await mounten('components/PersonenWahlDialog.vue')
  const da = await warten(() => !!document.querySelector('.pw-zeile button'))
  assert.ok(da, 'Personen-Dialog wurde nicht gezeichnet')
  const knoepfe = [...document.querySelectorAll('.pw-zeile button')]
  assert.equal(knoepfe.length, 2)
  assert.deepEqual(knoepfe.map((k) => k.getAttribute('aria-pressed')), ['false', 'true'])
  const aufheben = [...document.querySelectorAll('.dk-ui-dialog button')].find((b) => /Zuweisung aufheben/.test(txt(b)))
  assert.ok(aufheben, 'Knopf „Zuweisung aufheben“ fehlt')
  assert.equal(aufheben.disabled, false, 'aufheben muss möglich sein — es IST jemand zugewiesen')
  mit.weg()

  dialogModul.personenWahl.value = {
    titel: 'Zuweisung ändern',
    optionen: [{ value: 'M-MIRA', label: 'Miriam Saenger' }],
    aktuell: '',
  }
  const ohne = await mounten('components/PersonenWahlDialog.vue')
  await warten(() => !!document.querySelector('.dk-ui-dialog button'))
  const gesperrt = [...document.querySelectorAll('.dk-ui-dialog button')].find((b) => /Zuweisung aufheben/.test(txt(b)))
  assert.ok(gesperrt, 'Knopf „Zuweisung aufheben“ fehlt')
  assert.equal(gesperrt.disabled, true, 'niemand zugewiesen → „Aufheben“ muss gesperrt sein')
  assert.equal(gesperrt.getAttribute('title'), 'Zurzeit ist niemand zugewiesen')
  ohne.weg()
  dialogModul.personenWahl.value = null
})