/**
 * UI-R3e — Belege: die Kalenderverwaltung mit gewachsener Freigabe-Auswahl.
 *
 * Warum kein laufender Stack: die Betriebs-Images (`diakronos-standalone-*`,
 * `:latest`, `:betrieb`) enthalten den UI-R3e-Stand nicht, und ein eigener
 * `vite build` ist auf dieser Karte verboten (Speichergrenze). Dieser
 * Generator übersetzt die ECHTEN Vue-Dateien mit dem SFC-Compiler, mountet sie
 * in jsdom (Server-Antworten aus Attrappen) und schreibt FERTIGES HTML + CSS.
 * Ein Browser (`ui-r3e-screens.mjs`) macht daraus die Bilder.
 *
 * Lagen dieser Karte (Kartenpunkt 8):
 *   gruppenkalender  Freigabe-Auswahl eines GRUPPEN-Kalenders: seine Gruppe und
 *                    ALLE ihre Untergruppen — auch ohne Anlegerecht       → „gruppenkalender“
 *   gemeinde         Freigabe-Auswahl eines GEMEINDE-Kalenders: alle Gruppen
 *                    des Baums                                            → „gemeinde“
 *   wechsel          die Seite direkt nach dem Aufbau: ihre FRISCHE Antwort
 *                    schwebt noch (der geteilte Stand ist schon gefüllt) —
 *                    KEIN Leerzustand                                     → „wechsel“
 *
 * Aufruf (cwd = frontend/, node_modules nötig):
 *   TMPDIR=$(mktemp -d) NODE_OPTIONS=--max-old-space-size=2048 \
 *     node tools/uir3e-belege.mjs /root/.hermes/scratch/diakronos-uiux/ui-r3e
 */
import { JSDOM } from 'jsdom'
import { readFileSync, mkdtempSync, writeFileSync, mkdirSync } from 'node:fs'
import { join, resolve, dirname, basename } from 'node:path'
import { tmpdir } from 'node:os'
import { pathToFileURL } from 'node:url'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'

const ZIEL = process.argv[2] || '/ausgabe'
mkdirSync(ZIEL, { recursive: true })

// ── Der Gruppenbaum (Hierarchie-Attrappe) ─────────────────────────────────
const BAUM = {
  gruppen: [
    { name: 'G-Chor', gruppenname: 'Chor', untergruppen: [
      { name: 'UG-Kinderchor', untergruppenname: 'Kinderchor' },
      { name: 'UG-Jugendchor', untergruppenname: 'Jugendchor' },
    ] },
    { name: 'G-Band', gruppenname: 'Band', untergruppen: [
      { name: 'UG-Blech', untergruppenname: 'Blech' },
    ] },
  ],
}

const KALENDER = [
  {
    // Gemeinde-Kalender: KEINE Gruppe → die Auswahl zeigt den ganzen Baum.
    name: 'Gemeindeleben', titel: 'Gemeindeleben', farbe: '#1c2850',
    gruppe: null, untergruppe: null, selbstverwaltet: false, calender_details: '',
    standard_gruppe_lesen: true, gemeinde_status: 'aus', gruppe_status: 'aus',
  },
  {
    // Gruppenkalender: „Chor“ mit beiden Untergruppen.
    name: 'Chorproben', titel: 'Chorproben', farbe: '#2266aa',
    gruppe: 'G-Chor', untergruppe: null, selbstverwaltet: true, calender_details: '',
    standard_gruppe_lesen: false, gemeinde_status: 'aus', gruppe_status: 'aus',
  },
]

/**
 * Die Anlegeziele sind hier ABSICHTLICH ENG: nur die Gruppe „Band“ — kein
 * Untergruppen-Recht, keine Gemeinde. Genau daran scheiterte die Auswahl vor
 * UI-R3e (sie kam aus den Anlegezielen). `darf_gemeinde_kalender: false`.
 */
const VERWALTUNG = {
  kalender: KALENDER,
  farbe_standard: '#2266aa',
  darf_gemeinde_kalender: false,
  anlegen_gruppen: ['G-Band'],
  anlegen_untergruppen: [],
}

const aufrufe = []
let verwaltung = VERWALTUNG
/** Für die Lage „wechsel“: die Antwort der SEITE wird zurückgehalten. */
let verwaltungAntwort = () => verwaltung
globalThis.__belegMock = async (methode, args) => {
  aufrufe.push([methode, args])
  if (/get_gruppen_hierarchie$/.test(methode)) return BAUM
  if (/get_kalender_verwaltung$/.test(methode)) return verwaltungAntwort()
  if (/get_objekt_rechte$/.test(methode)) {
    return {
      typ: 'kalender', objekt: args?.objekt, gruppe: 'G-Chor', untergruppe: null,
      standard_gruppe_lesen: true, gemeinde_status: 'aus', gruppe_status: 'aus',
      darf_moderieren_vergeben: false, freigaben: [],
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
// Der geteilte Ladestand ist ein MODULZUSTAND — er überlebt eine Lage. Er wird
// deshalb über DENSELBEN Weg angesprochen wie die Seiten (Attrappe) und
// zwischen den Lagen geleert.
const STAND = await import('../src/diakonos/composables/useKalenderVerwaltung.js')
STAND.__setzeApiAufruf((m, a) => globalThis.__belegMock(m, a))

const TMP = mkdtempSync(join(tmpdir(), 'uir3e-belege-'))
const cache = new Map()
const VUE_URL = import.meta.resolve('vue')
mkdirSync(join(TMP, 'shim'), { recursive: true })
const SHIM = join(TMP, 'shim', 'useApi.mock.mjs')
writeFileSync(SHIM, `export * from ${JSON.stringify(new URL('../src/diakonos/composables/useApi.js', import.meta.url).href)}\n`
  + 'export const apiCall = (m, a) => globalThis.__belegMock(m, a)\nexport default { apiCall }\n')

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
  const script = compileScript(descriptor, { id, scopeId: `data-v-${id}`, inlineTemplate: false })
  const tpl = compileTemplate({
    source: descriptor.template.content, filename, id,
    compilerOptions: { bindingMetadata: script.bindings, scopeId: `data-v-${id}` },
  })
  if (tpl.errors.length) throw new Error(filename + ': ' + tpl.errors.map(String).join(' '))
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
    if (/useApi(\.js)?$/.test(spec)) return `from '${pathToFileURL(SHIM).href}'`
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

/** Eine Lage rendern: Seite mounten, optional klicken, HTML zurückgeben. */
async function rendere({ seite, verwaltungAntwort: antwort, klick = null, vorher = null }) {
  verwaltung = VERWALTUNG
  verwaltungAntwort = antwort || (() => verwaltung)
  for (const alt of (globalThis.__belegApps || [])) {
    try { alt.unmount() } catch { /* schon weg */ }
  }
  globalThis.__belegApps = []
  for (const el of [...document.body.children]) el.remove()
  // Geteilter Stand LEER starten: jede Lage ist ein frischer Aufbau.
  STAND.__leeren()
  if (vorher) await vorher()
  const Fehler = []
  const Baustein = (await import('file://' + uebersetze(resolve('src/diakonos/pages', seite)) + '?t=' + Date.now())).default
  const host = document.createElement('div')
  host.className = 'beleg-flaeche'
  document.body.appendChild(host)
  const app = Vue.createApp({ components: { Baustein }, template: '<Baustein />' })
  app.config.errorHandler = (e) => Fehler.push(String(e && e.message))
  app.config.warnHandler = (m) => Fehler.push('warn: ' + m)
  app.mount(host)
  ;(globalThis.__belegApps ||= []).push(app)
  await warte()
  if (klick) await klick(host)
  await warte()
  // Den SICHTBAREN Zustand sichern: nur die Kinder des Hosts — die
  // `body`-Kopie behielte Knoten einer FRÜHEREN Lage (deren App zwar
  // abgebaut, deren DOM aber schon gesichert war).
  return { html: mitWerten(host), fehler: Fehler }
}

/** `value`/`checked` am lebenden Baum in Attribute übernehmen (s. UI-R3d). */
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
  // Auswahlfelder: die gewählte Zeile trägt `selected` (sonst zeigt der Browser
  // wieder die erste Option).
  for (const el of wurzel.querySelectorAll('select')) {
    const gewaehlt = el.querySelector('option[selected]')
    if (!gewaehlt && el.value) {
      const treffer = [...el.options].find((o) => o.value === el.value)
      if (treffer) treffer.setAttribute('selected', '')
    }
  }
  return wurzel.innerHTML
}

/** Klappt den Kalender `name` auf und wählt die Gruppe `gruppe` in der Auswahl. */
function aufklappenUndWaehlen(name, gruppe) {
  return async (host) => {
    const karte = host.querySelector(`[data-kalender="${name}"]`)
    if (!karte) throw new Error('Karte ' + name + ' fehlt')
    const auf = knopf(karte, 'Freigaben & Sichtbarkeit')
    if (!auf) throw new Error('Aufklapp-Knopf fehlt an ' + name)
    auf.click()
    await warte(20)
    // Die Optionen für den Textbeleg markieren (das Bild zeigt das Feld zu).
    optionenInHtml(host, name)
    const wahl = document.querySelector(
      `[data-kalender="${name}"] select[aria-label="Gruppe für eine Freigabe wählen"]`)
    if (!wahl) throw new Error('die Gruppenauswahl fehlt an ' + name)
    if (gruppe) {
      wahl.value = gruppe
      wahl.dispatchEvent(new Event('change', { bubbles: true }))
      await warte(6)
    }
  }
}

/**
 * Die Auswahl OFFEN in den Beleg schreiben: alle Optionen mit `selected`
 * erscheinen im HTML, damit der Textbeleg die Einträge nennt (das Bild zeigt
 * ein geschlossenes Auswahlfeld).
 */
function optionenInHtml(host, name) {
  const karte = host.querySelector(`[data-kalender="${name}"]`)
  const wahl = karte && karte.querySelector('select[aria-label="Gruppe für eine Freigabe wählen"]')
  if (!wahl) throw new Error('die Gruppenauswahl fehlt an ' + name)
  for (const o of wahl.options) {
    if (!o.value) continue
    o.setAttribute('data-gruppe', o.value)
  }
  return [...wahl.options].map((o) => o.value).filter(Boolean)
}

const meldungen = {}
function merke(name, ergebnis, extra = {}) {
  meldungen[name] = { ...ergebnis, ...extra }
  if (ergebnis.fehler.length) console.error(name, 'FEHLER:', ergebnis.fehler)
}

// ── 1. Gruppenkalender: Gruppe + ALLE Untergruppen (ohne Anlegerecht dort) ─
{
  const lage = await rendere({
    seite: 'KalenderVerwaltung.vue',
    klick: aufklappenUndWaehlen('Chorproben', 'UG-Kinderchor'),
  })
  const gruppen = new JSDOM(`<div>${lage.html}</div>`).window.document
    .querySelectorAll('[data-kalender="Chorproben"] option[data-gruppe]')
  merke('gruppenkalender', lage, { gruppen: [...gruppen].map((o) => o.getAttribute('data-gruppe')).sort() })
}

// ── 2. Gemeinde-Kalender: alle Gruppen des Baums ──────────────────────────
{
  const lage = await rendere({
    seite: 'KalenderVerwaltung.vue',
    klick: aufklappenUndWaehlen('Gemeindeleben', 'G-Band'),
  })
  const gruppen = new JSDOM(`<div>${lage.html}</div>`).window.document
    .querySelectorAll('[data-kalender="Gemeindeleben"] option[data-gruppe]')
  merke('gemeinde', lage, { gruppen: [...gruppen].map((o) => o.getAttribute('data-gruppe')).sort() })
}

// ── 3. Seite direkt nach dem Wechsel: FRISCHE Antwort schwebt noch ────────
// Der geteilte Stand ist gefüllt (wie nach der Kalenderseite); die Seite lädt
// beim Aufbau frisch (UI-R3f), und genau diese frische Antwort ist noch nicht
// da. „Kein Kalender zu verwalten“ darf NICHT im Bild stehen; belegt wird der
// Bildschirm in diesem Moment.
{
  let freigeben
  const tor = new Promise((ja) => { freigeben = ja })
  const lage = await rendere({
    seite: 'KalenderVerwaltung.vue',
    verwaltungAntwort: () => tor,
    vorher: async () => {
      // Genau der Betriebsweg: die Verwaltungsliste ist schon geteilt.
      STAND.teilen(VERWALTUNG)
    },
  })
  const text = new JSDOM(lage.html).window.document.body.textContent
  const leerzustand = /Kein Kalender zu verwalten/.test(text)
    || /Noch keine Kalender/.test(text)
  merke('wechsel', { ...lage, fehler: [...lage.fehler, ...(leerzustand ? ['Leerzustand vor der Antwort im Bild'] : [])] },
    { leerzustand })
  freigeben(VERWALTUNG)
}

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
<title>UI-R3e — ${name}</title>
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
  console.log(name, '→', ergebnis.fehler.length ? 'FEHLER' : 'ok', '|', text.slice(0, 160))
}
console.log('fertig:', ZIEL)
