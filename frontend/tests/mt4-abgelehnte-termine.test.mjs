/**
 * MT-4 — Kalender: Fenster „Abgelehnte Termine“ lässt sich nicht schließen.
 *
 * Karte t_d8153327. Befund (Manuel, Live-Test 11.11.): Unter Kalender öffnet
 * das ⋯-Menü der Kopfzeile die Liste der eigenen abgelehnten Termine —
 * schließen ließ sie sich nicht. SOLL dieser Karte: ✕, Escape, Klick auf den
 * Hintergrund und die Zurück-Taste schließen; danach steht der Fokus wieder
 * auf dem Auslöser.
 *
 * URSACHE (im Review gegen `main` nachgestellt): die Seite band das Fenster als
 *     <DkDialog v-if="…" :model-value="true" @schliessen="…">
 * `DkDialog` meldet aber nur `update:modelValue` und `close` — ein Ereignis
 * `schliessen` gibt es nicht, und `:model-value="true"` ist eine feste
 * Zeichenkette, kein Zustand. Damit erreichte KEIN Schließweg die Seite.
 * Behoben in `pages/Kalender.vue` mit `v-model` + `close-on-overlay`.
 *
 * Geprüft wird die ECHTE Seite (`pages/Kalender.vue`, gemountet in jsdom —
 * dieselbe Technik wie `dev-b2-prueftafel-reiter.test.mjs`), nicht ein
 * Quelltext-Muster und kein nachgebautes Gerüst:
 *
 *  1. Öffnen über den echten Weg: ⋯-Knopf der Kopfzeile → Eintrag
 *     „Abgelehnte Termine“ (derselbe Emit `abgelehnteTermine`, den
 *     `KronosTopbar` in der App schickt).
 *  2. ✕ schließt, und das Fenster bleibt zu.
 *  3. Escape schließt, und das Fenster bleibt zu.
 *  4. Klick auf den Hintergrund schließt; ein Klick IM Fenster nicht.
 *  5. Die Zurück-Taste schließt (und verlässt die Seite nicht).
 *  6. Nach dem Schließen steht der Fokus wieder auf dem Auslöser.
 *
 * Dazu ein WÄCHTER über alle Fenster (`DkDialog`-Aufrufe in `src/`): kein
 * Ereignis `@schliessen` und kein `:model-value="true"` ohne Rückweg — dieser
 * Fehler soll nicht ein zweites Mal entstehen.
 *
 * Der Test liest NUR Dateien innerhalb von frontend/ (Regel 13) und braucht
 * kein Netz: `fetch` und die Kalender-Bibliothek sind Attrappen (siehe unten).
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, mkdtempSync, writeFileSync, rmSync, statSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, dirname, resolve, basename } from 'node:path'
import { pathToFileURL, fileURLToPath } from 'node:url'
import { JSDOM } from 'jsdom'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'

const hier = dirname(fileURLToPath(import.meta.url))
const FRONTEND = resolve(hier, '..')
const SRC = join(FRONTEND, 'src', 'diakonos')
const lies = (rel) => readFileSync(join(SRC, rel), 'utf8')

// ── jsdom als Dokument ─────────────────────────────────────────────────────
const dom = new JSDOM('<!doctype html><html><body></body></html>', {
  url: 'http://localhost/diakronos/#/kalender',
  pretendToBeVisual: true,
})
const W = dom.window
globalThis.window = W
globalThis.document = W.document
try { globalThis.navigator = W.navigator } catch { /* Node hat ein eigenes */ }
for (const schluessel of ['Node', 'Element', 'HTMLElement', 'SVGElement', 'Event',
  'MouseEvent', 'KeyboardEvent', 'CustomEvent', 'CSS', 'getComputedStyle',
  'HTMLInputElement', 'HTMLTextAreaElement', 'PopStateEvent', 'MutationObserver',
  'IntersectionObserver', 'ResizeObserver', 'localStorage', 'sessionStorage']) {
  if (W[schluessel]) globalThis[schluessel] = W[schluessel]
}
globalThis.getComputedStyle = W.getComputedStyle.bind(W)
globalThis.requestAnimationFrame = (fn) => W.setTimeout(() => fn(Date.now()), 0)
globalThis.cancelAnimationFrame = (id) => W.clearTimeout(id)
// `matchMedia` fehlt in jsdom — die Seite liest die Handy-Lage darüber.
W.matchMedia = (abfrage) => ({
  matches: false,
  media: abfrage,
  addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {},
})
// jsdom kennt die Zeiger-Abfrage nicht: „kein grober Zeiger“ = Desktop.
W.__DIakonosBOOT = { basePath: '/diakronos', csrf_token: 'test-token' }

// ── Attrappen: Netz und Kalender-Bibliothek ───────────────────────────────
/**
 * Die Seite holt beim Aufbau Boot-Daten, Kalender und Termine. Geprüft wird
 * hier NUR das Fenster — die Attrappe liefert leere, aber gültige Antworten
 * (keine erfundenen Termine im Raster).
 */
const LISTE = [
  { id: 'EV-1', title: 'Herbstfreizeit Jugend', start: '2026-11-07 00:00:00' },
  { id: 'EV-2', title: 'Jugendabend', start: '2026-11-14 19:00:00' },
]
const aufrufe = []
W.fetch = globalThis.fetch = async (url) => {
  const pfad = String(url && url.url ? url.url : url)
  aufrufe.push(pfad)
  const daten = /get_meine_abgelehnten_termine/.test(pfad) ? LISTE : []
  const text = JSON.stringify({ message: daten })
  return {
    ok: true, status: 200,
    headers: { get: () => 'application/json' },
    text: async () => text,
    json: async () => JSON.parse(text),
  }
}

// ── SFC → ES-Module (Temp-Verzeichnis) ────────────────────────────────────
const TMP = mkdtempSync(join(tmpdir(), 'mt4-'))
const cache = new Map()
const VUE_URL = import.meta.resolve('vue')

/** Fremde Pakete, die die Seite zieht und die es hier nicht gibt. */
const ERSATZ = new Map([
  // Die Kalender-Bibliothek braucht Maße und Layout; für das Fenster genügt
  // eine leere Attrappe — sie zeichnet nichts und meldet keine Termine.
  // `KronosCalendar.vue` liest `_EC.default?.create` und fällt ohne
  // `create` auf „keine Bibliothek“ zurück (`EventCalendar = null`).
  ['@event-calendar/build', 'export default {}'],
  ['@event-calendar/build/dist/event-calendar.min.css', ''],
])

function fremdesModul(spec) {
  if (!ERSATZ.has(spec)) return null
  const datei = resolve(TMP, 'ersatz-' + spec.replace(/[^a-z0-9]+/gi, '-') + '.mjs')
  if (!cache.has(datei)) {
    writeFileSync(datei, ERSATZ.get(spec) + '\n')
    cache.set(datei, datei)
  }
  return datei
}

function kompilieren(abs) {
  if (cache.has(abs)) return cache.get(abs)
  const filename = basename(abs)
  const { descriptor, errors } = parse(readFileSync(abs, 'utf8'), { filename })
  assert.deepEqual(errors, [], filename + ': SFC-Struktur')
  const script = compileScript(descriptor, { id: filename.replace(/\W/g, '_') })
  const tpl = compileTemplate({
    source: descriptor.template.content,
    filename,
    id: filename.replace(/\W/g, '_'),
    compilerOptions: { bindingMetadata: script.bindings },
  })
  assert.deepEqual(tpl.errors.map(String), [], filename + ': Vorlage')
  let code = script.content.replace(/\nexport default /, '\nconst __sfc__ = ')
  code += '\n' + tpl.code.replace(/^export function render/m, 'function render')
  code += '\n__sfc__.render = render\nexport default __sfc__\n'
  code = code.replace(/from\s+['"]vue['"]/g, `from '${VUE_URL}'`)
  code = code.replace(/from\s+['"]([^'"]+)['"]/g, (v, spec) => {
    if (spec.startsWith('.')) {
      const ziel = resolve(dirname(abs), spec)
      return `from '${pathToFileURL(spec.endsWith('.vue') ? kompilieren(ziel) : ziel).href}'`
    }
    const ersatz = fremdesModul(spec)
    return ersatz ? `from '${pathToFileURL(ersatz).href}'` : v
  })
  code = ersetzeNackteImporte(code)
  const zielDatei = resolve(TMP, filename.replace(/\.\w+$/, '') + '.' + cache.size + '.mjs')
  writeFileSync(zielDatei, code)
  cache.set(abs, zielDatei)
  return zielDatei
}

/** Auch Importe OHNE `from` (`import 'paket/stil.css'`) auf die Attrappe legen. */
function ersetzeNackteImporte(code) {
  return code.replace(/^import\s+['"]([^'"]+)['"];?$/gm, (ganz, spec) => {
    const ersatz = fremdesModul(spec)
    return ersatz ? `import '${pathToFileURL(ersatz).href}';` : ganz
  })
}

test.after(() => rmSync(TMP, { recursive: true, force: true }))

const Vue = await import('vue')
const tick = () => new Promise((loese) => setTimeout(loese, 0))
/**
 * Abwarten, bis das Fenster wirklich weg ist: `DkDialog` blendet aus
 * (`<Transition>`), der Knoten bleibt also noch einen Übergang lang stehen.
 * Zusätzlich läuft das Verbrauchen des Verlaufseintrags in einem Makrotask.
 */
const warten = (ms = 400) => new Promise((loese) => setTimeout(loese, ms))

/** Die ECHTE Kalender-Seite montieren. */
async function seiteMounten() {
  document.body.innerHTML = ''
  const seite = (await import(pathToFileURL(kompilieren(join(SRC, 'pages/Kalender.vue'))).href)).default
  const host = document.createElement('div')
  document.body.appendChild(host)
  const app = Vue.createApp({ components: { Seite: seite }, template: '<Seite />' })
  const warnungen = []
  app.config.warnHandler = (meldung) => warnungen.push(meldung)
  app.config.errorHandler = (fehler) => warnungen.push(String(fehler))
  app.mount(host)
  await tick()
  await warten()          // Ladevorgänge der Seite abwarten
  await tick()
  await warten()
  return { app, warnungen }
}

/** Das offene Fenster „Abgelehnte Termine“. */
function abgelehntDialog() {
  return [...document.body.querySelectorAll('[role="dialog"]')]
    .find((d) => (d.textContent || '').includes('Abgelehnte Termine'))
}

/** Der ⋯-Knopf der Kalender-Kopfzeile (Auslöser des Menüs). */
function menueKnopf() {
  return [...document.body.querySelectorAll('button[aria-haspopup="menu"]')][0]
}

/**
 * Das Fenster über den ECHTEN Weg öffnen: ⋯-Menü der Kopfzeile → Eintrag
 * „Abgelehnte Termine“. Gibt den Auslöser zurück — dorthin gehört der Fokus
 * nach dem Schließen zurück (`useDialogFokus` merkt ihn sich).
 */
async function oeffnen() {
  const ausloeser = menueKnopf()
  assert.ok(ausloeser, 'Auslöser „⋯“ der Kalender-Kopfzeile fehlt')
  ausloeser.focus()
  ausloeser.click()
  await tick()
  await Vue.nextTick()
  const eintrag = [...document.body.querySelectorAll('[role="menuitem"]')]
    .find((e) => (e.textContent || '').includes('Abgelehnte Termine'))
  assert.ok(eintrag, 'Menüeintrag „Abgelehnte Termine“ fehlt')
  eintrag.click()
  await tick()
  await warten()
  return ausloeser
}

function tasten(ziel, key) {
  const ereignis = new W.KeyboardEvent('keydown', { key, bubbles: true, cancelable: true })
  ;(ziel || document.activeElement || document.body).dispatchEvent(ereignis)
  return ereignis
}

// ══════════════════════════════════════════════════════════════════════════
// 1 · Öffnen über das ⋯-Menü und ✕ schließt (bleibt zu)
// ══════════════════════════════════════════════════════════════════════════
test('MT-4: „Abgelehnte Termine“ öffnet über das ⋯-Menü und das ✕ schließt', async () => {
  const { app, warnungen } = await seiteMounten()
  await oeffnen()
  const dialog = abgelehntDialog()
  assert.ok(dialog, 'Fenster wurde nicht geöffnet')
  assert.match(dialog.textContent || '', /Herbstfreizeit Jugend/, 'Liste ohne Inhalt')

  const schliessen = [...dialog.querySelectorAll('button')]
    .find((b) => b.getAttribute('aria-label') === 'Schließen')
  assert.ok(schliessen, '✕ fehlt im Fensterkopf')
  schliessen.click()
  await warten()
  assert.equal(abgelehntDialog(), undefined, '✕ hat das Fenster NICHT geschlossen')
  await warten(300)
  assert.equal(abgelehntDialog(), undefined, 'Fenster kam nach dem ✕ zurück')
  assert.deepEqual(warnungen, [], 'Vue meldet kein Problem')
  app.unmount()
})

// ══════════════════════════════════════════════════════════════════════════
// 2 · Escape schließt (bleibt zu)
// ══════════════════════════════════════════════════════════════════════════
test('MT-4: Escape schließt „Abgelehnte Termine“', async () => {
  const { app } = await seiteMounten()
  await oeffnen()
  const dialog = abgelehntDialog()
  assert.ok(dialog, 'Fenster wurde nicht geöffnet')

  // Escape am FOKUSSIERTEN Element (der Dialog selbst): so kommt die Taste in
  // der App an. Ein Ereignis auf `document.body` liefe am Tastenfänger vorbei.
  tasten(document.activeElement || dialog, 'Escape')
  await warten()
  assert.equal(abgelehntDialog(), undefined, 'Escape hat das Fenster NICHT geschlossen')
  await warten(300)
  assert.equal(abgelehntDialog(), undefined, 'Fenster kam nach Escape zurück')
  app.unmount()
})

// ══════════════════════════════════════════════════════════════════════════
// 3 · Hintergrund schließt, Klick IM Fenster nicht
// ══════════════════════════════════════════════════════════════════════════
test('MT-4: Klick auf den Hintergrund schließt, Klick im Fenster nicht', async () => {
  const { app } = await seiteMounten()
  await oeffnen()
  let dialog = abgelehntDialog()
  assert.ok(dialog, 'Fenster wurde nicht geöffnet')

  // Klick IN den Dialog (Körper) — hier steht kein Formular, trotzdem darf
  // nicht geschlossen werden: der Hintergrund ist der Auslöser, nicht das Kind.
  const koerper = dialog.querySelector('.dk-ui-dialog-koerper') || dialog
  koerper.dispatchEvent(new W.MouseEvent('mousedown', { bubbles: true }))
  koerper.dispatchEvent(new W.MouseEvent('click', { bubbles: true }))
  await warten(150)
  assert.ok(abgelehntDialog(), 'Klick IM Fenster hat es geschlossen')

  // Druck auf die Fläche dahinter: das Überlagerungselement selbst.
  dialog = abgelehntDialog()
  const overlay = dialog.parentElement
  assert.ok(overlay && overlay !== document.body, 'Überlagerungselement nicht gefunden')
  overlay.dispatchEvent(new W.MouseEvent('mousedown', { bubbles: true }))
  await warten()
  assert.equal(abgelehntDialog(), undefined, 'Klick auf den Hintergrund hat NICHT geschlossen')
  app.unmount()
})

// ══════════════════════════════════════════════════════════════════════════
// 4 · Zurück-Taste schließt (und verlässt die Seite nicht)
// ══════════════════════════════════════════════════════════════════════════
test('MT-4: die Zurück-Taste schließt das Fenster', async () => {
  const { app } = await seiteMounten()
  await oeffnen()
  assert.ok(abgelehntDialog(), 'Fenster wurde nicht geöffnet')
  const adresseVorher = W.location.hash

  W.history.back()
  await tick()
  await warten()

  assert.equal(abgelehntDialog(), undefined, 'Zurück hat das Fenster NICHT geschlossen')
  assert.equal(W.location.hash, adresseVorher, 'Zurück hat die Seite verlassen')
  app.unmount()
})

// ══════════════════════════════════════════════════════════════════════════
// 5 · Fokus steht nach dem Schließen wieder auf dem Auslöser
// ══════════════════════════════════════════════════════════════════════════
test('MT-4: nach dem Schließen steht der Fokus wieder auf dem Auslöser', async () => {
  const { app } = await seiteMounten()
  const ausloeser = await oeffnen()
  const dialog = abgelehntDialog()
  assert.ok(dialog, 'Fenster wurde nicht geöffnet')

  tasten(document.activeElement || dialog, 'Escape')
  await warten()
  assert.equal(abgelehntDialog(), undefined, 'Fenster noch offen')
  assert.equal(document.activeElement, ausloeser,
    'Fokus steht nicht wieder auf dem Auslöser (⋯-Knopf der Kopfzeile)')
  app.unmount()
})

// ══════════════════════════════════════════════════════════════════════════
// 6 · Wächter: kein Fenster ohne Rückweg für seine Schließwege
// ══════════════════════════════════════════════════════════════════════════
/** Alle .vue-Dateien unter src/ (rekursiv). */
function alleVorlagen(ordner = SRC) {
  const treffer = []
  for (const eintrag of readdirSync(ordner)) {
    const pfad = join(ordner, eintrag)
    if (statSync(pfad).isDirectory()) treffer.push(...alleVorlagen(pfad))
    else if (pfad.endsWith('.vue')) treffer.push(pfad)
  }
  return treffer
}

/**
 * Den `<DkDialog …>`-Aufruf lesen: seine Attribute bis zum schließenden `>`.
 * Der Fehler von MT-4 (`:model-value="true"` + `@schliessen`) steckt in genau
 * diesem Ausschnitt.
 */
function dialoegAufrufe(quelle) {
  const aufrufe = []
  const muster = /<DkDialog\b/g
  let treffer
  while ((treffer = muster.exec(quelle)) !== null) {
    // Bis zum `>` der Startmarke (Attribute enthalten keine spitzen Klammern).
    const ende = quelle.indexOf('>', treffer.index)
    if (ende < 0) break
    aufrufe.push(quelle.slice(treffer.index, ende + 1))
  }
  return aufrufe
}

test('MT-4: kein Fenster hört auf ein Ereignis „schliessen“ (DkDialog kennt es nicht)', () => {
  const falsch = []
  for (const datei of alleVorlagen()) {
    const quelle = readFileSync(datei, 'utf8')
    for (const aufruf of dialoegAufrufe(quelle)) {
      if (/@schliessen\b/.test(aufruf)) {
        falsch.push(`${datei.replace(FRONTEND + '/', '')}: ${aufruf.replace(/\s+/g, ' ')}`)
      }
    }
  }
  assert.deepEqual(falsch, [],
    'DkDialog meldet `update:modelValue` und `close` — `@schliessen` erreicht ihn nie')
})

test('MT-4: kein Fenster steht fest auf offen, ohne Rückweg für seine Schließwege', () => {
  const falsch = []
  for (const datei of alleVorlagen()) {
    const quelle = readFileSync(datei, 'utf8')
    for (const aufruf of dialoegAufrufe(quelle)) {
      // `:model-value="true"` ist eine FESTE Zeichenkette: der Dialog kann
      // nicht geschlossen werden, wenn niemand den Wert zurückschreibt.
      if (!/:model-value="true"/.test(aufruf)) {
        // ohne festen Wert zählt nur der Fehlgriff von oben (eigener Test)
        continue
      }
      const rueckweg = /@update:model-value=|v-model=/.test(aufruf)
      const dauerhaft = /:dismissible="false"/.test(aufruf)
      if (!rueckweg && !dauerhaft) {
        falsch.push(`${datei.replace(FRONTEND + '/', '')}: ${aufruf.replace(/\s+/g, ' ')}`)
      }
    }
  }
  assert.deepEqual(falsch, [],
    'fester Modellwert ohne Rückweg — ✕/Escape/Hintergrund können nicht schließen')
})

test('MT-4: die Kalender-Seite führt den Fensterzustand über v-model', () => {
  const quelle = lies('pages/Kalender.vue')
  assert.match(quelle, /<DkDialog\s+v-model="showAbgelehntListe"/,
    'das Fenster hängt am Zustand der Seite (v-model)')
  assert.match(quelle, /close-on-overlay/,
    'Klick auf den Hintergrund schließt (kein Formular im Fenster)')
  assert.doesNotMatch(quelle, /v-if="showAbgelehntListe"/,
    'kein `v-if` — das umging die Rückmeldung des Dialogs')
})
