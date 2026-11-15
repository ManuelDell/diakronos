/**
 * UI-R3d — Belege: die geänderten Kalender-Oberflächen STANDSICHER rendern.
 *
 * Warum nicht am laufenden Stack: die Betriebs-Images (`diakronos-standalone-*`,
 * `:latest`, `:betrieb`) enthalten den UI-R3d-Stand nicht. Eine eigene
 * Vorschau wäre ein `vite build` — das verbietet diese Karte (Speichergrenze).
 *
 * Dieser Generator übersetzt die ECHTEN Vue-Dateien mit dem SFC-Compiler
 * (wie `tests/uir3b-verwaltung.test.mjs`), mountet sie in jsdom, füllt sie mit
 * Server-Antworten aus Attrappen und schreibt FERTIGES HTML + CSS. Ein Browser
 * macht daraus die Bilder (`ui-r3d-screens.mjs`) — kein Build.
 *
 * Gerendert werden die vier Lagen dieser Karte:
 *   liste         Liste mit Gemeinde- UND Gruppenkalender              → „liste“
 *   rueckgaengig  Löschen + Rückgängig-Meldung                         → „rueckgaengig“
 *   freigaben     Bestätigungsdialog bei einem Kalender MIT Freigaben  → „freigaben“
 *   bearbeiten    Bearbeiten-Dialog, Name sichtbar vorbelegt           → „bearbeiten“
 *
 * WICHTIG (Kartenpunkt 11): Beim Serialisieren werden die `value`-Properties
 * der Formularfelder als ATTRIBUTE übernommen — sonst stünde im HTML kein
 * vorbelegter Name, und ein Bild ohne den Namen wäre kein Beleg dafür.
 *
 * Aufruf (cwd = frontend/, node_modules nötig):
 *   TMPDIR=/tmp node tools/uir3d-belege.mjs /ausgabe
 */
import { JSDOM } from 'jsdom'
import { readFileSync, mkdtempSync, writeFileSync, mkdirSync } from 'node:fs'
import { join, resolve, dirname, basename } from 'node:path'
import { tmpdir } from 'node:os'
import { pathToFileURL } from 'node:url'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'

const ZIEL = process.argv[2] || '/ausgabe'
mkdirSync(ZIEL, { recursive: true })

// ── Mittel der Belege (Server-Antworten) ──────────────────────────────────
const KALENDER = [
  {
    // Gemeinde-Kalender: KEINE Gruppe → der Meta-Text nennt nur „Gemeinde“.
    name: 'Gemeindeleben', titel: 'Gemeindeleben', farbe: '#1c2850',
    gruppe: null, untergruppe: null, selbstverwaltet: false, calender_details: '',
    standard_gruppe_lesen: true, gemeinde_status: 'aus', gruppe_status: 'aus',
    leserechte: [], schreibrechte: [], moderatoren: [],
  },
  {
    name: 'Chorproben', titel: 'Chorproben', farbe: '#2266aa',
    gruppe: 'G-Chor', untergruppe: null, selbstverwaltet: true, calender_details: '',
    standard_gruppe_lesen: false, gemeinde_status: 'aus', gruppe_status: 'aus',
    leserechte: [], schreibrechte: [], moderatoren: [],
  },
  {
    name: 'Kinderchor-Proben', titel: 'Kinderchor-Proben', farbe: '#7a4f9e',
    gruppe: 'G-Chor', untergruppe: 'UG-Kinderchor', selbstverwaltet: false, calender_details: '',
    standard_gruppe_lesen: true, gemeinde_status: 'aus', gruppe_status: 'aus',
    leserechte: [], schreibrechte: [], moderatoren: [],
  },
]

/** Dieselbe Liste, aber ein Kalender MIT Freigaben → Rückfrage statt Rückgängig. */
const KALENDER_MIT_FREIGABEN = KALENDER.map((k) => (k.name === 'Kinderchor-Proben'
  ? { ...k, leserechte: ['Mitglied'], moderatoren: ['anna.beispiel@example.org'] }
  : k))

const VERWALTUNG = {
  kalender: KALENDER,
  rollen: [],
  farbe_standard: '#2266aa',
  darf_gemeinde_kalender: true,
  anlegen_gruppen: ['G-Chor', 'G-Jugend'],
  anlegen_untergruppen: ['UG-Kinderchor'],
}
const VERWALTUNG_FREIGABEN = { ...VERWALTUNG, kalender: KALENDER_MIT_FREIGABEN }

const BAUM = {
  gruppen: [
    { name: 'G-Chor', gruppenname: 'Chor', untergruppen: [{ name: 'UG-Kinderchor', untergruppenname: 'Kinderchor' }] },
    { name: 'G-Jugend', gruppenname: 'Jugend', untergruppen: [] },
  ],
}

const aufrufe = []
let verwaltung = VERWALTUNG
globalThis.__belegMock = async (methode, args) => {
  aufrufe.push([methode, args])
  if (/get_gruppen_hierarchie$/.test(methode)) return BAUM
  if (/get_kalender_verwaltung$/.test(methode)) return verwaltung
  if (/get_objekt_rechte$/.test(methode)) {
    return {
      typ: 'kalender', objekt: args?.objekt, gruppe: 'G-Chor', untergruppe: null,
      standard_gruppe_lesen: true, gemeinde_status: 'aus', gruppe_status: 'aus',
      darf_moderieren_vergeben: true,
      freigaben: [
        { benutzer: 'anna.beispiel@example.org', gruppe: null, name: 'Anna Beispiel', lesen: true, schreiben: true, moderieren: true },
        { benutzer: null, gruppe: 'G-Chor', name: 'Chor', lesen: true, schreiben: false, moderieren: false },
      ],
    }
  }
  return { success: true }
}
globalThis.fetch = async () => ({
  ok: true, status: 200, headers: { get: () => 'application/json' },
  json: async () => ({ message: {} }), text: async () => '{}',
})

// ── Browser-Ersatz ────────────────────────────────────────────────────────
const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
for (const k of ['window', 'document', 'Node', 'Element', 'HTMLElement', 'Event', 'MouseEvent',
  'SVGElement', 'CSS', 'CustomEvent', 'HTMLInputElement', 'HTMLSelectElement',
  'HTMLTextAreaElement', 'requestAnimationFrame', 'getComputedStyle', 'MutationObserver',
  'KeyboardEvent', 'FocusEvent', 'Document', 'ShadowRoot', 'HTMLButtonElement',
  'sessionStorage', 'localStorage', 'Location', 'History', 'PopStateEvent',
  'HashChangeEvent', 'Navigator', 'NodeList']) {
  if (dom.window[k] !== undefined) globalThis[k] = dom.window[k]
}
globalThis.requestAnimationFrame = (cb) => setTimeout(() => cb(Date.now()), 0)
globalThis.cancelAnimationFrame = (id) => clearTimeout(id)
Object.defineProperty(globalThis.window, 'innerWidth', { value: 1440, configurable: true })
Object.defineProperty(globalThis.window, 'matchMedia', {
  configurable: true,
  value: () => ({ matches: false, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {} }),
})

const Vue = await import('vue')
const TMP = mkdtempSync(join(tmpdir(), 'uir3d-belege-'))
const cache = new Map()
const VUE_URL = import.meta.resolve('vue')
mkdirSync(join(TMP, 'shim'), { recursive: true })
const SHIM = join(TMP, 'shim', 'useApi.mock.mjs')
writeFileSync(SHIM, `export * from ${JSON.stringify(new URL('../src/diakonos/composables/useApi.js', import.meta.url).href)}\n`
  + 'export const apiCall = (m, a) => globalThis.__belegMock(m, a)\nexport default { apiCall }\n')

// Die Rückfrage (`useBestaetigen`) ist EIN Modulzustand mit Warteschlange. Damit
// eine im vorigen Bild offen gebliebene Frage nicht im nächsten Bild steht,
// laufen ALLE Bausteine über diese eine Instanz — und der Beleg-Generator
// leert sie zwischen den Lagen (`zuruecksetzen`).
const BESTAETIGEN_ZIEL = new URL('../src/diakonos/composables/useBestaetigen.js', import.meta.url).href
const BESTAETIGEN_SHIM = join(TMP, 'shim', 'useBestaetigen.mjs')
writeFileSync(BESTAETIGEN_SHIM,
  `export * from ${JSON.stringify(BESTAETIGEN_ZIEL)}\n`
  + `import { bestaetigungAntwort } from ${JSON.stringify(BESTAETIGEN_ZIEL)}\n`
  + 'export function __leeren() {\n'
  + '  const vorher = globalThis.__belegOffeneFragen || 0\n'
  + '  for (let i = 0; i < 12; i += 1) bestaetigungAntwort(false)\n'
  + '  return vorher\n'
  + '}\n')

const STILE = []
function bisId(filename) {
  let h = 0
  for (const z of filename) h = (h * 31 + z.charCodeAt(0)) >>> 0
  return h.toString(36)
}

function uebersetze(abs) {
  if (cache.has(abs)) return cache.get(abs)
  const filename = basename(abs)
  const { descriptor, errors } = parse(readFileSync(abs, 'utf8'), { filename })
  if (errors.length) throw new Error(filename + ': ' + errors.map(String).join(' '))
  const id = bisId(filename)
  // `scopeId` MUSS in beiden Aufrufen stehen: `compileScript` hängt sonst
  // KEIN `data-v-…` an die Elemente, und `compileTemplate` gibt es an die
  // gerenderten Knoten.
  const script = compileScript(descriptor, { id, scopeId: `data-v-${id}`, inlineTemplate: false })
  const tpl = compileTemplate({
    source: descriptor.template.content, filename, id,
    compilerOptions: { bindingMetadata: script.bindings, scopeId: `data-v-${id}` },
  })
  if (tpl.errors.length) throw new Error(filename + ': ' + tpl.errors.map(String).join(' '))
  // `<style scoped>`: der Compiler setzt je Element ein `data-v-<id>`; die
  // Regeltexte der Bausteine gehören deshalb mit ins Dokument (rekursiv).
  for (const stil of (descriptor.styles || [])) {
    if (!stil.content || !stil.content.trim()) continue
    const koerper = stil.scoped
      ? stil.content.replace(/(^|\})\s*([^{}@]+)\{/g, (v, davor, selektoren) => {
        const teile = selektoren.split(',').map((sel) => (sel.trim() ? sel.trim() + `[data-v-${id}]` : sel.trim()))
        return `${davor} ${teile.join(', ')} {`
      })
      : stil.content
    STILE.push(koerper)
  }
  let code = script.content.replace(/\nexport default /, '\nconst __sfc__ = ')
  code += '\n' + tpl.code.replace(/^export function render/m, 'function render')
  code += '\n__sfc__.render = render\n__sfc__.__scopeId = ' + JSON.stringify(`data-v-${id}`)
  code += '\nexport default __sfc__\n'
  code = code.replace(/from\s+['"]([^'"]+)['"]/g, (voll, spec) => {
    if (/^vue/.test(spec)) return `from '${VUE_URL}'`
    if (/composables\/useApi/.test(spec)) return `from '${pathToFileURL(SHIM).href}'`
    // Alle Bausteine teilen EINE Rückfrage-Instanz (siehe oben).
    if (/composables\/useBestaetigen/.test(spec)) return `from '${pathToFileURL(BESTAETIGEN_SHIM).href}'`
    const ziel = resolve(dirname(abs), spec)
    const datei = /\.vue$/.test(spec) ? uebersetze(ziel) : ziel
    return `from '${pathToFileURL(datei).href}'`
  })
  const ziel = resolve(TMP, filename.replace(/\.vue$/, '') + '.' + cache.size + '.mjs')
  writeFileSync(ziel, code)
  cache.set(abs, ziel)
  return ziel
}

const warte = async (n = 40) => { for (let i = 0; i < n; i += 1) await new Promise((l) => setTimeout(l, 0)) }
const knopf = (wurzel, muster) => [...wurzel.querySelectorAll('button')]
  .find((b) => new RegExp(muster).test(b.textContent || ''))

/**
 * Kartenpunkt 11: Der HTML-Serialisierer schreibt den GETIPPTEN oder
 * VORBELEGTEN Wert eines Feldes NICHT als Attribut (`value` steht nur, wenn
 * das Template ihn schreibt). Für den Beleg „Name ist vorbelegt“ werden die
 * `value`-Properties deshalb VOR dem Serialisieren in Attribute übernommen —
 * am LEBENDEN Baum (ein Umweg über `innerHTML` verlöre die Properties, weil
 * neu geparste Felder ihren Wert aus dem Attribut lesen). Gleiches für
 * `checked`.
 *
 * @param {Document|Element} wurzel  lebender Knoten (`document.body`)
 * @returns {string} HTML mit übernommenen Attributen
 */
function mitWerten(wurzel) {
  for (const el of wurzel.querySelectorAll('input, textarea, select')) {
    if (el.tagName === 'INPUT') {
      if (el.type === 'checkbox' || el.type === 'radio') {
        if (el.checked) el.setAttribute('checked', '')
        else el.removeAttribute('checked')
      } else if (el.value !== '') {
        el.setAttribute('value', el.value)
      } else {
        el.removeAttribute('value')
      }
    } else if (el.tagName === 'TEXTAREA') {
      el.textContent = el.value
    }
  }
  return wurzel.innerHTML
}

/** Eine Lage rendern: Seite mounten, optional klicken, HTML zurückgeben. */
async function rendere({ seite, pfad = null, props = {}, verwaltungAntwort, klick = null }) {
  verwaltung = verwaltungAntwort
  // Die vorige Lage ABBAUEN, nicht nur ihr DOM entfernen: ein noch laufender
  // App-Baum mit `DkBestaetigung` würde die geteilte `bestaetigung`-Ref weiter
  // rendern — zwei Lagen stünden übereinander im Bild.
  for (const alt of (globalThis.__belegApps || [])) {
    try { alt.unmount() } catch { /* schon weg */ }
  }
  globalThis.__belegApps = []
  for (const el of [...document.body.children]) el.remove()
  // Die Rückfrage ist EIN Modulzustand mit Warteschlange — eine im vorigen Bild
  // offen gebliebene Frage stünde sonst im nächsten Bild (die Shim-Instanz ist
  // dieselbe, die alle Bausteine importieren).
  const { __leeren } = await import(pathToFileURL(BESTAETIGEN_SHIM).href)
  for (let i = 0; i < 4; i += 1) {
    __leeren()
    await new Promise((l) => setTimeout(l, 0))
  }
  for (const el of [...document.body.children]) el.remove()
  const Fehler = []
  const Datei = pfad ? resolve(pfad) : resolve('src/diakonos/pages', seite)
  const Baustein = (await import('file://' + uebersetze(Datei) + '?t=' + Date.now())).default
  const Bestaetigung = (await import('file://'
    + uebersetze(resolve('src/diakonos/components/ui/DkBestaetigung.vue')) + '?t=' + Date.now())).default
  const host = document.createElement('div')
  host.className = 'beleg-flaeche'
  document.body.appendChild(host)
  const app = Vue.createApp({
    components: { Baustein, Bestaetigung },
    data: () => ({ props }),
    template: '<Bestaetigung /><Baustein v-bind="props" />',
  })
  app.config.errorHandler = (e) => Fehler.push(String(e && e.message))
  app.config.warnHandler = (m) => Fehler.push('warn: ' + m)
  app.mount(host)
  let appInstanz = app
  ;(globalThis.__belegApps ||= []).push(appInstanz)
  await warte()
  if (klick) await klick(host)
  await warte()
  // Ein Dialog aus einer FRÜHEREN Lage wäre ein falsches Bild — laut abbrechen.
  const dialoge = [...document.querySelectorAll('.dk-ui-dialog')].length
  if (dialoge > 1) Fehler.push(`${dialoge} Dialoge gleichzeitig offen`)
  return { html: mitWerten(document.body), fehler: Fehler }
}

const meldungen = {}
function merke(name, ergebnis) {
  meldungen[name] = ergebnis
  if (ergebnis.fehler.length) console.error(name, 'FEHLER:', ergebnis.fehler)
}

// ── 1. Liste mit Gemeinde- UND Gruppenkalender ────────────────────────────
merke('liste', await rendere({ seite: 'KalenderVerwaltung.vue', verwaltungAntwort: VERWALTUNG }))

// ── 2. Rückgängig-Meldung nach dem Löschen ────────────────────────────────
// `Chorproben` hat keine Freigaben und Sichtbarkeit `aus` → sofort löschen
// und „Rückgängig“ anbieten (Punkt 1b).
merke('rueckgaengig', await rendere({
  seite: 'KalenderVerwaltung.vue',
  verwaltungAntwort: VERWALTUNG,
  klick: async (host) => {
    const zeile = host.querySelector('[data-kalender="Chorproben"]')
    const b = knopf(zeile || host, '^Löschen$')
    if (!b) throw new Error('„Löschen“ nicht gefunden')
    b.click()
  },
}))

// ── 3. Bestätigungsdialog bei einem Kalender MIT Freigaben ────────────────
merke('freigaben', await rendere({
  seite: 'KalenderVerwaltung.vue',
  verwaltungAntwort: VERWALTUNG_FREIGABEN,
  klick: async (host) => {
    const zeile = host.querySelector('[data-kalender="Kinderchor-Proben"]')
    const b = knopf(zeile || host, '^Löschen$')
    if (!b) throw new Error('„Löschen“ nicht gefunden')
    b.click()
  },
}))

// ── 4. Bearbeiten-Dialog mit SICHTBAR vorbelegtem Namen ───────────────────
merke('bearbeiten', await rendere({
  seite: 'KalenderVerwaltung.vue',
  verwaltungAntwort: VERWALTUNG,
  klick: async (host) => {
    const zeile = host.querySelector('[data-kalender="Kinderchor-Proben"]')
    const b = knopf(zeile || host, '^Bearbeiten$')
    if (!b) throw new Error('„Bearbeiten“ nicht gefunden')
    b.click()
  },
}))

// ── Schreiben: EIN Dokument je Lage (CSS kommt mit) ───────────────────────
const BASIS = resolve('src/diakonos')
function css(datei, gesehen = new Set()) {
  const abs = resolve(BASIS, datei)
  if (gesehen.has(abs)) return ''
  gesehen.add(abs)
  return readFileSync(abs, 'utf8').replace(/@import\s+['"]([^'"]+)['"];?/g, (voll, ziel) => {
    if (/^https?:/.test(ziel)) return ''
    try { return css(ziel, gesehen) } catch { return '' }
  })
}
const CSS = [
  readFileSync(resolve('src/layer-reihenfolge.css'), 'utf8'),
  css('index.css'),
].join('\n')

for (const [name, ergebnis] of Object.entries(meldungen)) {
  const html = `<!doctype html>
<html lang="de" data-theme="hell">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>UI-R3d — ${name}</title>
<style>${CSS}</style>
<style>${STILE.join('\n')}</style>
<style>
  body { margin: 0; padding: 24px; background: var(--bg); color: var(--text); }
  .beleg-flaeche { max-width: 1100px; margin: 0 auto; }
</style>
</head>
<body>
${ergebnis.html}
</body>
</html>`
  writeFileSync(join(ZIEL, `lage-${name}.html`), html)
  const text = new JSDOM(ergebnis.html).window.document.body.textContent
    .replace(/\s+/g, ' ').trim()
  writeFileSync(join(ZIEL, `lage-${name}.txt`), text)
  console.log(name, '→', ergebnis.fehler.length ? 'FEHLER' : 'ok', '|', text.slice(0, 140))
}
console.log('fertig:', ZIEL)
