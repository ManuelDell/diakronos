/**
 * PERF-K1 — Kalender-Start: Desktop-Spalte „Zu prüfen“ bleibt leer.
 *
 * BEFUND (Review des Operators, 17.11.): Mit PERF-K1 wurde die Seite der EINE
 * Besitzer von `get_kanban_board_data` — die Spalte bekommt ihre Zeilen nur
 * noch über `:zeilen` von `pruefIdsLaden`. Gefüllt wurde das aber nur in
 * `mobilTermineLaden` (Handy-Liste) und `nachAenderung`; `onMounted` rief es am
 * DESKTOP nie. Ergebnis: die Spalte blieb nach dem Laden leer.
 *
 * Geprüft wird das VERHALTEN an der ECHTEN Seite (`pages/Kalender.vue`,
 * gemountet in jsdom — dieselbe Technik wie `tests/mt4-abgelehnte-termine`),
 * NICHT ein Quelltext-Muster. Netz und Kalender-Bibliothek sind Attrappen; die
 * Antworten werden je Endpunkt vorgegeben und die Aufrufe gezählt:
 *
 *  1. DESKTOP, Moderator: nach dem Start steht der Vorschlag in der Spalte,
 *     ohne dass jemand etwas ändert — und `get_kanban_board_data` ging GENAU
 *     EINMAL raus (Seite und Spalte teilen sich die Antwort).
 *  2. DESKTOP, ohne Moderationsrecht: die Spalte gibt es nicht, und der
 *     Endpunkt wird gar nicht gefragt (fail closed, kein Aufruf).
 *  3. Der Lesemodus-Schalter im ⋯-Menü lädt die Zeilen der SEITE nach (EIN
 *     Aufruf) — die Spalte zieht mit.
 *  4. Fehlerfall: scheitert der Abruf, leert die Spalte ihre Zeilen und sagt
 *     es — vorher blieb der alte Stand stehen (`pruefZeilen = null` wurde vom
 *     Panel ignoriert), wie `laden()` mit `[]` es zuvor tat.
 *
 * Der Test liest NUR Dateien innerhalb von frontend/ und braucht kein Netz.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, mkdtempSync, writeFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, dirname, resolve, basename } from 'node:path'
import { pathToFileURL, fileURLToPath } from 'node:url'
import { registerHooks } from 'node:module'
import { JSDOM } from 'jsdom'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'

const hier = dirname(fileURLToPath(import.meta.url))
const FRONTEND = resolve(hier, '..')
const SRC = join(FRONTEND, 'src', 'diakonos')
const USE_API = join(SRC, 'composables', 'useApi.js')

// ══════════════════════════════════════════════════════════════════════════
// Die Attrappe für `useApi.js` — EIN Modul für den ganzen Lauf
// ══════════════════════════════════════════════════════════════════════════
// Warum ein Import-Haken statt Umschreiben der Import-Zeilen: die Seite zieht
// `useApi.js` (und damit die halbe Sitzungslogik) über ein Dutzend Wege
// (Seite, Bausteine, `kanbanApi`). Die Attrappe antwortet je Endpunkt aus
// `globalThis.__API_ATTRAPPE__` und zählt die Aufrufe — so misst der Test die
// ECHTE Verdrahtung der Seite, nicht eine nachgebaute.
const TMP = mkdtempSync(join(tmpdir(), 'perfk1-mount-'))
const ERTRAPPE = join(TMP, 'useApi-ertrappe.mjs')
writeFileSync(ERTRAPPE, `
export class AuditConfirmationRequired extends Error {}
// Nur die Wege, die die Kalender-Seite wirklich nimmt; alles andere bleibt
// neutral (kein erfundener Erfolg, kein Absturz).
export async function apiCall(pfad, args) {
  const plan = globalThis.__API_ATTRAPPE__
  plan.aufrufe.push(pfad)
  const antwort = await plan.antwort(pfad, args)
  if (antwort instanceof Error) throw antwort
  return antwort
}
export function apiUrl(pfad) { return '/diakronos/api/method/' + pfad }
export function mitAntwort(wert) { return wert }
export function pruefeSitzungsAntwort(_res, data) { return data }
export async function apiAntwortPruefen(res) {
  const text = await res.text()
  let data = {}
  try { data = JSON.parse(text) } catch { data = {} }
  return data
}
export async function apiGet(pfad, args) { return apiCall(pfad, args) }
export function __mitSitzungsdialog(fn) { return fn }
export default { apiCall }
`)
const ERTRAPPE_URL = pathToFileURL(ERTRAPPE).href

// Der Haken greift für JEDE Auflösung, die auf `useApi.js` zeigt — egal ob
// relativ, absolut oder mit `?lauf=…`-Anhang. Fremde Dateien bleiben
// unberührt (die Rückgabe des Standardwegs wird durchgereicht).
registerHooks({
  resolve(specifier, context, weiter) {
    const ergebnis = weiter(specifier, context)
    const ziel = String(ergebnis?.url || '').split('?')[0]
    if (ziel === pathToFileURL(USE_API).href) return { url: ERTRAPPE_URL, shortCircuit: true }
    return ergebnis
  },
})

// ══════════════════════════════════════════════════════════════════════════
// jsdom als Dokument (DESKTOP: kein grober Zeiger, breit)
// ══════════════════════════════════════════════════════════════════════════
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
// Kein grober Zeiger, keine schmale Lage: die Seite baut den DESKTOP-Block
// (Raster + rechte Spalte), nicht die A10-Handy-Liste.
W.matchMedia = (abfrage) => ({
  matches: false,
  media: abfrage,
  addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {},
})

// ══════════════════════════════════════════════════════════════════════════
// Die Antworten des Servers (nur die Felder, die die Seite liest)
// ══════════════════════════════════════════════════════════════════════════
const KALENDER = [
  // `write` ist das Feld, das `useKronosStore.fetchAccessibleCalendars`
  // weiterreicht und an dem die Seite `hasWriteRight` festmacht — ohne es
  // gäbe es keinen Lesemodus-Schalter im ⋯-Menü.
  { name: 'gruppen', calendar_name: 'Gruppe Nord', calendar_color: '#1d4ed8',
    read: true, write: true },
]
const VORSCHLAG = {
  id: 'EV-V1', name: 'EV-V1', title: 'Jugendabend', element_name: 'Jugendabend',
  start: '2026-11-14 19:00:00', end: '2026-11-14 21:00:00', status: 'Vorschlag',
  element_calendar: 'gruppen', calendar_title: 'Gruppe Nord',
  darf_pruefen: true, ist_vorschlag: true,
}

/** Aufrufe dieses Laufs (Endpunkt-Namen in Absendereihenfolge). */
let aufrufe = []
/** Soll `get_kanban_board_data` scheitern? (Fall 4) */
let boardFehler = false

function antwort(pfad) {
  if (/get_kanban_board_data/.test(pfad)) {
    if (boardFehler) return new Error('Serverfehler (Attrappe)')
    return { vorschlaege: [VORSCHLAG], konflikte: [] }
  }
  // `hasWriteRight` der Seite hängt an `get_writable_calendars` (derselbe
  // Endpunkt, den der Anlage-Dialog fragt) — ohne Antwort kein Schreibrecht.
  if (/get_writable_calendars/.test(pfad)) return KALENDER
  if (/get_accessible_calendars|get_meine_kalender/.test(pfad)) return KALENDER
  if (/get_meine_abgelehnten_termine/.test(pfad)) return []
  if (/get_session_info/.test(pfad)) return { user: 'maria', can_moderate: true, can_write: true }
  if (/get_moderation_count/.test(pfad)) return { count: 1 }
  if (/get_ressources/.test(pfad)) return []
  if (/get_kronos_settings/.test(pfad)) return {}
  if (/Eventkategorie/.test(pfad)) return []
  if (/get_meine_abgelehnten_termine/.test(pfad)) return []
  if (/get_current_user_context/.test(pfad)) {
    return { user: 'maria', roles: ['Mitglied'], ist_admin: false }
  }
  if (/get_kalender_verwaltung/.test(pfad)) return { kalender: [], darf_gemeinde_kalender: false }
  if (/get_rollen_erklaerung/.test(pfad)) {
    return { stufen_titel: {
      untergruppe: 'Untergruppe', gruppe: 'Gruppe',
      gemeinde: 'Alle Mitglieder der Gemeinde',
    } }
  }
  if (/get_calendar_events/.test(pfad)) return []
  return null
}

globalThis.__API_ATTRAPPE__ = {
  antwort: async (pfad) => antwort(pfad),
  get aufrufe() { return aufrufe },
}

// ══════════════════════════════════════════════════════════════════════════
// `window.fetch` — der Weg der KALENDERLISTE (`useKronosStore`) und der
// Termine; dieselbe Aufrufliste, dieselbe Antwortquelle.
// ══════════════════════════════════════════════════════════════════════════
W.fetch = globalThis.fetch = async (url, optionen) => {
  const pfad = String(url && url.url ? url.url : url)
  // Endpunktname ohne Betriebs-Präfix (`/diakronos`): die Seite baut ihre
  // Adressen über `apiUrl` aus `shared/basis.js`.
  const name = (pfad.match(/api\/method\/([\w.]+)/) || [])[1] || pfad
  aufrufe.push(name)
  let daten = antwort(name)
  if (daten instanceof Error) throw daten
  // `get_accessible_calendars` kommt über diesen Weg (nicht über `apiCall`).
  if (!daten && /get_accessible_calendars/.test(name)) daten = KALENDER
  if (!daten) daten = null
  const text = JSON.stringify({ message: daten })
  return {
    ok: true, status: 200,
    headers: { get: () => 'application/json' },
    text: async () => text,
    json: async () => JSON.parse(text),
  }
}


// ── SFC → ES-Module ───────────────────────────────────────────────────────
/** Fremde Pakete ohne Inhalt (die Kalender-Bibliothek braucht Layout). */
const ERSATZ = new Map([
  ['@event-calendar/build', 'export default {}'],
  ['@event-calendar/build/dist/event-calendar.min.css', ''],
  ['@event-calendar/core', 'export default {}'],
])
const cache = new Map()
const VUE_URL = import.meta.resolve('vue')

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
  code = code.replace(/from\s+['"]([^'"]+)['"]/g, (voll, spec) => {
    if (spec.startsWith('.')) {
      const ziel = resolve(dirname(abs), spec)
      return `from '${pathToFileURL(spec.endsWith('.vue') ? kompilieren(ziel) : ziel).href}'`
    }
    const ersatz = fremdesModul(spec)
    return ersatz ? `from '${pathToFileURL(ersatz).href}'` : voll
  })
  code = code.replace(/^import\s+['"]([^'"]+)['"];?$/gm, (ganz, spec) => {
    const ersatz = fremdesModul(spec)
    return ersatz ? `import '${pathToFileURL(ersatz).href}';` : ganz
  })
  // Der Dateiname muss den PFAD tragen: zwei Dateien heißen gleich (`laden.vue`,
  // `index.vue`), und die Adresse ist der Modul-Cache-Schlüssel. Ohne den Pfad
  // liefert Node das Modul der ERSTEN gleichnamigen Datei — im Gegenlauf gegen
  // `main` kam so der Stand des anderen Baums zurück (am 17.11. belegt: der
  // Test war dort grün, obwohl die Datei es nicht sein konnte).
  const kennung = abs.replace(FRONTEND, '').replace(/[^a-z0-9]+/gi, '-')
  const zielDatei = resolve(TMP, kennung + '.' + cache.size + '.mjs')
  writeFileSync(zielDatei, code)
  cache.set(abs, zielDatei)
  return zielDatei
}

test.after(() => rmSync(TMP, { recursive: true, force: true }))

const Vue = await import('vue')
const tick = () => new Promise((loese) => setTimeout(loese, 0))
/** Warten, bis die Startaufrufe (alle Promises der Seite) durch sind. */
const warten = (ms = 150) => new Promise((loese) => setTimeout(loese, ms))

/** Die ECHTE Kalender-Seite montieren. `moderator` = Moderationsrecht. */
async function seiteMounten({ moderator = true } = {}) {
  document.body.innerHTML = ''
  aufrufe = []
  boardFehler = false
  try { W.localStorage.clear() } catch { /* egal */ }
  W.__DIakonosBOOT = {
    basePath: '/diakronos',
    csrf_token: 'test-token',
    can_moderate: moderator,
    is_admin: false,
    user: 'maria',
  }
  const seite = (await import(
    pathToFileURL(kompilieren(join(SRC, 'pages', 'Kalender.vue'))).href + '?fall=' + Math.random()
  )).default
  const host = document.createElement('div')
  document.body.appendChild(host)
  const app = Vue.createApp({ components: { Seite: seite }, template: '<Seite />' })
  const warnungen = []
  app.config.warnHandler = (meldung) => warnungen.push(meldung)
  app.config.errorHandler = (fehler) => warnungen.push(String(fehler))
  app.mount(host)
  await tick()
  await warten()
  await tick()
  return { app, host, warnungen }
}

/** Wie oft ein Endpunkt in diesem Lauf gefragt wurde. */
const zahl = (muster) => aufrufe.filter((p) => muster.test(String(p))).length

/** Die Zeilen, die die Spalte „Zu prüfen“ gerade zeigt. */
function panelZeilen() {
  const panel = document.body.querySelector('.dk-pruef-panel')
  if (!panel) return []
  return [...panel.querySelectorAll('.dk-pruef-panel-zeile')].map((e) => e.textContent)
}

/**
 * Den Lesemodus-Weg des ⋯-Menüs auslösen: Auslöser der Kopfzeile → Eintrag
 * „Bearbeiten …“. Das ist derselbe Weg wie in `ux3i-kalender-a4` (gemountete
 * `KronosTopbar`), nur über die ECHTE Seite.
 */
async function lesemodusSchalten() {
  const ausloeser = document.body.querySelector('.dk-ui-aktionen-ausloeser')
  assert.ok(ausloeser, 'der ⋯-Auslöser der Kopfzeile ist da')
  ausloeser.dispatchEvent(new W.MouseEvent('click', { bubbles: true }))
  await tick()
  const menue = document.body.querySelector('.dk-ui-aktionen-menue')
  assert.ok(menue, 'das ⋯-Menü ist offen')
  const schalter = [...menue.querySelectorAll('.dk-ui-aktionen-eintrag')]
    .find((e) => /Bearbeiten/.test(e.textContent))
  assert.ok(schalter, 'der Lesemodus-Schalter steht im Menü: ' +
    JSON.stringify([...menue.querySelectorAll('.dk-ui-aktionen-eintrag')].map((e) => e.textContent.trim())))
  schalter.dispatchEvent(new W.MouseEvent('click', { bubbles: true }))
  await tick()
  await warten()
}

// ══════════════════════════════════════════════════════════════════════════
// 1 · BLOCKER: Desktop zeigt die Prüf-Zeilen nach dem Start
// ══════════════════════════════════════════════════════════════════════════
test('PERF-K1 (Review) · 1: Desktop-Moderator sieht die Prüf-Zeilen nach dem Start', async () => {
  await seiteMounten({ moderator: true })
  const panel = document.body.querySelector('.dk-pruef-panel')
  assert.ok(panel, 'die Spalte „Zu prüfen“ ist am Desktop da')
  const zeilen = panelZeilen()
  assert.ok(zeilen.length > 0,
    'die Spalte zeigt den offenen Vorschlag nach dem Laden (BLOCKER: sie blieb leer)')
  assert.match(zeilen.join(' '), /Jugendabend/, 'die Zeile trägt den Termin')
  // EINE Antwort, zwei Leser: der Endpunkt ging genau einmal raus.
  assert.equal(zahl(/get_kanban_board_data/), 1,
    `get_kanban_board_data ging ${zahl(/get_kanban_board_data/)}x raus — die Seite ist der EINE Besitzer (PERF-K1)`)
})

// ══════════════════════════════════════════════════════════════════════════
// 2 · Ohne Recht: keine Spalte, kein Aufruf
// ══════════════════════════════════════════════════════════════════════════
test('PERF-K1 (Review) · 2: ohne Moderationsrecht keine Spalte und kein Aufruf', async () => {
  await seiteMounten({ moderator: false })
  assert.equal(document.body.querySelector('.dk-pruef-panel'), null,
    'ohne Recht gibt es keine Spalte (fail closed)')
  assert.equal(zahl(/get_kanban_board_data/), 0,
    'ohne Recht wird der Prüf-Endpunkt gar nicht gefragt')
})

// ══════════════════════════════════════════════════════════════════════════
// 3 · Lesemodus-Wechsel: die SEITE lädt nach, EINE Antwort
// ══════════════════════════════════════════════════════════════════════════
test('PERF-K1 (Review) · 3: der Lesemodus-Schalter lädt die Zeilen EINMAL nach (Seite, nicht Panel)', async () => {
  await seiteMounten({ moderator: true })
  const vorher = zahl(/get_kanban_board_data/)
  assert.equal(vorher, 1, 'Ausgangslage: EIN Startaufruf')
  await lesemodusSchalten()
  assert.equal(zahl(/get_kanban_board_data/), vorher + 1,
    `nach dem Umschalten genau EIN weiterer Aufruf (statt ${zahl(/get_kanban_board_data/)} gesamt)`)
  assert.ok(panelZeilen().length > 0, 'die Spalte zeigt danach weiter ihre Zeilen')
})

// ══════════════════════════════════════════════════════════════════════════
// 4 · Fehlerfall: die Spalte räumt ab, statt den alten Stand zu halten
// ══════════════════════════════════════════════════════════════════════════
test('PERF-K1 (Review) · 4: ein gescheiterter Abruf leert die Zeilen der Spalte', async () => {
  await seiteMounten({ moderator: true })
  assert.ok(panelZeilen().length > 0, 'Ausgangslage: die Zeile steht in der Spalte')
  // Der nächste Abruf scheitert (Netz-/Serverfehler beim Nachladen).
  boardFehler = true
  await lesemodusSchalten()
  assert.equal(panelZeilen().length, 0,
    'der alte Stand bleibt in der Spalte stehen — vorher leerte `laden()` mit []')
})
