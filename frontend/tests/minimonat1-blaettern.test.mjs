/**
 * MINIMONAT-1 — Handy-Kalender (Liste, A10): Mini-Monat blättert nicht.
 *
 * Befund (am Code gemessen, vom Review bestätigt): die A10-Liste reichte
 * `@zurueck`/`@vor` an `calendarRef.prev()/next()` weiter — den Halter des
 * RASTERS. Der Raster-Baustein hängt an `v-else` zur Liste, ist in der
 * Listenansicht also NICHT gemountet; `calendarRef` ist dort `null`, und der
 * Tipp tat lautlos nichts. Die Seite rechnet den Monatsschritt deshalb selbst
 * (`schrittMitTag` in `mobilAnsicht.mjs`).
 *
 * Geprüft wird das VERHALTEN an der ECHTEN Seite (`pages/Kalender.vue` in
 * jsdom — dieselbe Technik wie `tests/mt4-abgelehnte-termine.test.mjs`), in
 * der HANDY-Lage und in der Listenansicht, mit gestubbter Termin-API:
 *
 *   1. die Rechnung selbst (`schrittMitTag`, reine Funktion),
 *   2. die Verdrahtung in der Seite (`@zurueck`/`@vor` → `monatZurueck`/`vor`),
 *   3. der Desktop-Mini-Monat bleibt unberührt,
 *   4. der Laufzähler: eine verspätete ALTE Antwort überschreibt den neuen
 *      Zeitraum nicht,
 *   5. gemountet: › lädt GENAU EINMAL die Spanne des nächsten Monats,
 *   6. `@bereit` des Rasters setzt es auf den gewählten Tag (`gotoDate`),
 *   7. kein offscreen-Rest am Rasterhalter.
 *
 * TEST-NACH-1 (13.11.): Hier standen drei Stellen, die NICHT die Seite
 * prüften — ein Quelltext-Regex auf `++ladeNr`, ein Gerüst, das
 * `monatBewegen`/`spanneWechseln`/`mobilTermineLaden` nachbaute, und ein
 * Ersatzmodell des Laufzählers. Sie sind gestrichen: Fall 4 und 5 messen jetzt
 * am Mount der ECHTEN Seite (`pages/Kalender.vue` aus dem Stand nach
 * MINIMONAT-1), in der Handy-Lage, mit gestubbter Termin-API. Gegen
 * `pages/Kalender.vue` aus 4783b3fd ist der Lauf rot (belegt im Bericht der
 * Karte): dort reichte `@vor` an `calendarRef.next()`, und `calendarRef` ist
 * in der Liste null — kein Laden, kein Wechsel.
 *
 * TEST-NACH-1b (13.11.): zwei Nacharbeiten.
 *   * AUFRÄUMEN (A3): Temp-Ordner und Ersatz-Modul entstanden auf
 *     Datei-Ebene und wurden in `test.after` gelöscht — `node:test` führt
 *     `after` aber VOR den Testfällen aus, die es erst danach startet.
 *     Einzeln gestartet (`--test-name-pattern`) scheiterten Fall 4 und 5 mit
 *     `Cannot find module …-ersatz-…/ersatz.mjs`. Jetzt legt
 *     `seiteMounten()` JE LAUF einen eigenen Ordner an (`lfAufbauen`), und der
 *     Fall räumt ihn im Abschlussblock mit `lfAbbauen()` weg.
 *   * FALL 4 prüfte den Wettlauf nicht: `seiteMounten()` setzte den Plan auf
 *     `{termine:[],ms:0}` zurück und die Termine hatten kein Datum — es wurde
 *     `[]` mit `[]` verglichen. Jetzt ist die AUFBAU-Antwort verzögert und
 *     trifft NACH der Blätter-Antwort ein; beide Termine tragen einen `start`
 *     im alten bzw. neuen Zeitraum. Erwartet: der Punkt steht im NEUEN
 *     Zeitraum, der Tag der verspäteten alten Antwort bleibt ohne Punkt.
 *
 * Der Test liest NUR Dateien innerhalb von frontend/ und braucht kein Netz:
 * `fetch` und die Kalender-Bibliothek sind Attrappen.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, mkdtempSync, writeFileSync, rmSync, existsSync, mkdirSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, dirname, resolve, basename } from 'node:path'
import { pathToFileURL, fileURLToPath } from 'node:url'
import { JSDOM } from 'jsdom'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'

const hier = dirname(fileURLToPath(import.meta.url))
const FRONTEND = resolve(hier, '..')
const SRC = join(FRONTEND, 'src', 'diakonos')
const lies = (rel) => readFileSync(join(SRC, rel), 'utf8')
const seite = () => lies('pages/Kalender.vue')

const M = await import(pathToFileURL(join(SRC, 'components/kronos/mobilAnsicht.mjs')).href)

// ══════════════════════════════════════════════════════════════════════════
// 1 · Die Rechnung: Monat UND mitwandernder, geklemmter Tag
// ══════════════════════════════════════════════════════════════════════════
test('MINIMONAT-1 · 1: schrittMitTag blättert Monat und klemmt den Tag', () => {
  // Über die Jahresgrenze, in beide Richtungen.
  assert.deepEqual(M.schrittMitTag('2026-11', '2026-11-13', 1), { monat: '2026-12', tag: '2026-12-13' })
  assert.deepEqual(M.schrittMitTag('2026-12', '2026-12-15', 1), { monat: '2027-01', tag: '2027-01-15' })
  assert.deepEqual(M.schrittMitTag('2026-01', '2026-01-10', -1), { monat: '2025-12', tag: '2025-12-10' })
  // Der Tag darf nie über den Zielmonat hinausragen.
  assert.deepEqual(M.schrittMitTag('2026-01', '2026-01-31', 1), { monat: '2026-02', tag: '2026-02-28' })
  assert.deepEqual(M.schrittMitTag('2026-03', '2026-03-31', -1), { monat: '2026-02', tag: '2026-02-28' })
  assert.deepEqual(M.schrittMitTag('2024-01', '2024-01-31', 1), { monat: '2024-02', tag: '2024-02-29' },
    'Schaltjahr: 29. Februar')
  // Mehrere Monate auf einmal.
  assert.deepEqual(M.schrittMitTag('2026-11', '2026-11-30', 3), { monat: '2027-02', tag: '2027-02-28' })
  // Der Monatsschritt allein bleibt die reine Monatsregel.
  assert.equal(M.monatsSchritt('2026-11', -1), '2026-10')
  assert.equal(M.monatsSchritt('2026-13', 1), '', 'kein Monat 13')
  assert.equal(M.monatsSchritt('2026-11', 0), '2026-11')
  assert.deepEqual(M.schrittMitTag('', '2026-11-13', 1), { monat: '', tag: '' },
    'unbrauchbarer Monat ergibt keine erfundene Antwort')
})

// ══════════════════════════════════════════════════════════════════════════
// 2 · Verdrahtung: das Ereignis kommt an, und die Bibliothek wird nicht mehr
//     bewegt (in der Liste ist sie gar nicht gemountet, `calendarRef` = null)
// ══════════════════════════════════════════════════════════════════════════
test('MINIMONAT-1 · 2: die A10-Liste meldet „zurueck“/„vor“ an die Seite', () => {
  const q = seite()
  const block = q.slice(q.indexOf('<KalenderListeMobil'), q.indexOf('/>', q.indexOf('<KalenderListeMobil')))
  assert.ok(block, 'KalenderListeMobil steht in der Seite')
  assert.match(block, /@zurueck="monatZurueck"/, '‹ → monatZurueck')
  assert.match(block, /@vor="monatVor"/, '› → monatVor')
  assert.ok(!/@zurueck="calendarRef\?\.prev\(\)"/.test(block), 'kein Raster-`prev()` am Mini-Monat')
  assert.ok(!/@vor="calendarRef\?\.next\(\)"/.test(block), 'kein Raster-`next()` am Mini-Monat')
  for (const [name, schritte] of [['monatZurueck', '-1'], ['monatVor', '1']]) {
    const start = q.indexOf(`function ${name}(`)
    const fn = q.slice(start, start + 200)
    assert.ok(fn.startsWith(`function ${name}(`), `${name} ist da`)
    assert.match(fn, new RegExp(`monatBewegen\\(\\s*${schritte}\\s*\\)`), `${name} bewegt um ${schritte} Monat(e)`)
  }
  const start = q.indexOf('function monatBewegen(')
  const bewegen = q.slice(start, start + 1200)
  assert.ok(bewegen.startsWith('function monatBewegen('), 'monatBewegen ist da')
  assert.match(bewegen, /schrittMitTag\(\s*mobilMonat\.value/, 'monatBewegen nutzt die eine Regel')
  assert.match(bewegen, /mobilMonat\.value\s*=/, 'setzt den gezeigten Monat')
  assert.match(bewegen, /gewaehlterTag\.value\s*=/, 'zieht den gewählten Tag mit (Tagesliste passt)')
  assert.ok(!/mobilTermineLaden\(\)/.test(bewegen),
    'monatBewegen lädt NICHT selbst — das spanne-Ereignis lädt den neuen Zeitraum')
  // Keine zweite Monatsrechnung auf der Seite (nur EINE Wahrheit).
  assert.ok(!/getMonth\(\)\s*\+\s*-?1/.test(bewegen), 'kein eigenes Monat-Rechnen neben der Regel')
})

test('MINIMONAT-1 · 3: Desktop-Mini-Monat unberührt (eigene Pfeile, eigenes Ereignis)', () => {
  const desktop = lies('components/kronos/KronosMiniCalendar.vue')
  assert.ok(!/schrittMitTag|monatsSchritt/.test(desktop), 'Desktop kennt die Handy-Regel nicht')
  assert.ok(!/mobilMonat/.test(desktop), 'Desktop liest den Handy-Zustand nicht')
  const q = seite()
  const desktopBlock = q.slice(q.indexOf('<KronosMiniCalendar'), q.indexOf('/>', q.indexOf('<KronosMiniCalendar')))
  assert.ok(!/@zurueck="monatZurueck"/.test(desktopBlock) && !/@vor="monatVor"/.test(desktopBlock),
    'Desktop-Mini-Monat bleibt am Kalender')
  // Die Handy-Liste samt Mini-Monat hängt an der Handy-Lage (nur dort).
  assert.match(q, /<KalenderListeMobil\s+v-if="mobilAnsichtId === 'liste'"/,
    'die Liste gilt nur für die Handy-Listen-Ansicht')
})

// ══════════════════════════════════════════════════════════════════════════
// GEMOUNTET (jsdom): die ECHTE Seite `pages/Kalender.vue` in der Handy-Lage,
// Listenansicht, Termin-API gestubbt. Kein Nachbau der Seite.
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
// HANDY-Lage (DEV-B6: grober Zeiger + schmal) — nur dann baut die Seite die
// A10-Liste mit Mini-Monat.
W.matchMedia = (abfrage) => ({
  matches: /pointer:\s*coarse/.test(String(abfrage)),
  media: abfrage,
  addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {},
})
W.__DIakonosBOOT = { basePath: '/diakronos', csrf_token: 'test-token' }

// ── Attrappen: Netz (Kalender + Termine) und Kalender-Bibliothek ───────────
/** Aufrufe der Terminquelle — je Aufruf Zeitraum und Antwort-Verzögerung. */
let terminAufrufe = []
/**
 * Antwortplan: (vonTag, bisTag, nummer) → { termine, ms } (ms = Verzögerung).
 * `nummer` zählt die Termin-Aufrufe ab dem Mount (1 = erster Aufruf).
 */
let terminPlan = () => ({ termine: [], ms: 0 })
/**
 * Nachträgliche Antworten EINES Laufs: `nummer → { termine }`. Der Plan
 * läuft beim ABSENDEN des Aufrufs; eine schon gestartete, aber noch offene
 * Antwort liest ihren Inhalt erst beim Auflösen hier — so lässt sich eine
 * ÜBERHOLTE Antwort nachträglich mit Daten füllen (Fall 4).
 */
let terminAntworten = new Map()
/**
 * Offene Termin-Anfragen samt ihren Auflösern — DAS Steuerpult für
 * Wettläufe (Fall 4). Jeder Eintrag: `{ nr, von, bis, termin(e) }`; `termin`
 * ist ein von außen auflösbares Promise, das die Antwort ausliefert.
 * `terminAufloesen(nr, termine)` löst genau EINE Anfrage auf; solange nichts
 * aufgelöst wird, hängt die Anfrage (die Seite merkt davon nichts).
 */
let terminOffen = []

function antwort(daten) {
  const text = JSON.stringify({ message: daten })
  return {
    ok: true, status: 200,
    headers: { get: () => 'application/json' },
    text: async () => text,
    json: async () => JSON.parse(text),
  }
}

W.fetch = globalThis.fetch = (url, optionen) => {
  const pfad = String(url && url.url ? url.url : url)
  if (/get_calendar_events/.test(pfad)) {
    let rumpf = {}
    try { rumpf = JSON.parse((optionen && optionen.body) || '{}') } catch { /* leer */ }
    const von = String(rumpf.start_date || '')
    const bis = String(rumpf.end_date || '')
    terminAufrufe.push([von, bis])
    const nr = terminAufrufe.length
    const { termine = [], ms = 0 } = terminPlan(von, bis, nr) || {}
    // STEUERBAR: die Anfrage hängt an einem eigenen Promise, das nur von
    // außen aufgelöst wird (`terminAufloesen`). `terminPlan` darf eine
    // Verzögerung mitgeben (Fall 5: Aufbau vorbei, damit der Mount ruhig
    // ist); Inhalt und Verzögerung werden beim AUFLÖSEN gelesen, nie beim
    // Absenden — so lässt sich eine offene Antwort nachträglich füllen.
    let loese
    const antwortVersprechen = new Promise((ok) => { loese = ok })
    const eintrag = { nr, von, bis, termin: antwortVersprechen }
    terminOffen.push(eintrag)
    const aufloesen = (nachgereicht) => {
      const nachricht = nachgereicht !== undefined ? nachgereicht : termine
      loese(antwort(nachricht))
    }
    if (ms > 0) setTimeout(() => aufloesen(), ms)
    eintrag.aufloesen = aufloesen
    return antwortVersprechen
  }
  return Promise.resolve(antwort([]))
}

/** Der Termin-Aufruf Nr. `nr` (1 = erster ab Mount) im offenen Stapel. */
const terminAnfrage = (nr) => terminOffen.find((a) => a.nr === nr)

/**
 * Anfrage Nr. `nr` auflösen — mit `termine` (Liste) oder mit dem Inhalt aus
 * `terminAntworten` (dann ohne Argument). Löst genau EINE, offene Anfrage.
 */
function terminAufloesen(nr, termine) {
  const anfrage = terminAnfrage(nr)
  assert.ok(anfrage, `Termin-Anfrage ${nr} ist offen (offen: ${terminOffen.filter((a) => !a.erledigt).map((a) => a.nr)})`)
  anfrage.erledigt = true
  anfrage.aufloesen(termine !== undefined ? termine : terminAntworten.get(nr)?.termine)
}

// ── SFC → ES-Module (Temp-Verzeichnis je Mount) ───────────────────────────
/**
 * Arbeitsordner der SFC-Module. Er entsteht in `lfAufbauen()` — also erst im
 * Test, der ihn braucht — und wird im selben Test wieder weggeräumt.
 *
 * TEST-NACH-1b (13.11.): Vorher lagen Ordner und Ersatz-Modul auf Datei-Ebene
 * und wurden in `test.after` gelöscht. `node:test` sammelt aber erst die
 * Testfälle ein und führt sie DANACH aus — `after` lief also VOR dem ersten
 * Fall, und die Import-Adresse des Ersatz-Moduls zeigte ins Leere. Einzeln
 * gestartet (`--test-name-pattern`) waren Fall 4 und 5 deshalb rot
 * (`Cannot find module …-ersatz-…/ersatz.mjs`). Jetzt hat jeder
 * Laufadapter seinen EIGENEN Ordner (kein gemeinsamer Zustand zwischen zwei
 * Fällen) und räumt ihn im Abschlussblock seines Aufrufers weg.
 */
let TMP = ''
const cache = new Map()
/** Kennung, die den Modul-Cache des Prozesses je Mount trennt. */
let lauf = 0
/**
 * Bausteine, die ein Testfall durch eine Attrappe ersetzt (TEST-NACH-1).
 *
 * Der Raster-Mount prüft `@bereit`/`gotoDate` und würde dafür die echte
 * Kalender-Bibliothek laden. Der SFC-Compiler schreibt die Bausteine aber
 * fest in den Renderer (`$setup["KronosCalendar"]`); deshalb bekommt der
 * Renderer in `kompilieren` die Attrappe aus diesem Fach. Das Fach ist ein
 * EIGENES Modul, das `lfAufbauen()` je Laufadapter in dessen Ordner schreibt
 * und `lfAbbauen()` mit dem Ordner entfernt — ein globaler Zustand würde die
 * Attrappe in andere Testfälle tragen.
 */
let ERSATZ_MODUL = ''
const ERSATZ_QUELLE = 'export const KALENDER_ATT = new Proxy({}, { get: (_, name) => globalThis.__KALENDER_ATTRAFFE__?.[name] })\n'
const VUE_URL = import.meta.resolve('vue')

/** Fremde Pakete, die die Seite zieht: die Kalender-Bibliothek als Attrappe. */
const ERSATZ = new Map([
  ['@event-calendar/build', 'export default {}'],
  ['@event-calendar/build/dist/event-calendar.min.css', ''],
])

/** Der Laufadapter, in den `kompilieren` gerade schreibt (`lfAufbauen`). */
let cursor = { ordner: '', platzhalter: new Set(), kennung: '' }

function fremdesModul(spec, ordner) {
  if (!ERSATZ.has(spec)) return null
  const datei = resolve(ordner, 'ersatz-' + spec.replace(/[^a-z0-9]+/gi, '-') + '.mjs')
  if (!cursor.platzhalter.has(datei)) {
    writeFileSync(datei, ERSATZ.get(spec) + '\n')
    cursor.platzhalter.add(datei)
  }
  return datei
}

function kompilieren(abs, ordner = TMP) {
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
  code += '\n__sfc__.render = render\n'
  code += '\nexport default __sfc__\n'
  // Die Attrappe ersetzt die Bindung im Renderer (nicht die Import-Zeile):
  // `_createVNode($setup["KronosCalendar"], …)` bekommt sie aus dem Fach.
  code = code.replace(/\$setup\["KronosCalendar"\]/g,
    '(KALENDER_ATT.KronosCalendar || $setup["KronosCalendar"])')
  code = code.replace(/from\s+['"]vue['"]/g, `from '${VUE_URL}'`)
  // EINMAL laden (feste Adresse): jeder Baustein dieser Datei braucht dieselbe
  // Instanz der Attrappe.
  code = code.replace(/^/m, () =>
    `import { KALENDER_ATT } from '${pathToFileURL(ERSATZ_MODUL).href}'\n`)
  code = code.replace(/from\s+['"]([^'"]+)['"]/g, (voll, spec) => {
    if (spec.startsWith('.')) {
      const ziel = resolve(dirname(abs), spec)
      // Das Ersatz-Modul NICHT umschreiben (es liegt in seinem eigenen Ordner).
      if (ziel === ERSATZ_MODUL) return voll
      return `from '${pathToFileURL(spec.endsWith('.vue') ? kompilieren(ziel, ordner) : ziel).href}'`
    }
    const ersatz = fremdesModul(spec, ordner)
    return ersatz ? `from '${pathToFileURL(ersatz).href}'` : voll
  })
  // Auch Importe OHNE `from` (`import 'paket/stil.css'`) auf die Attrappe legen.
  code = code.replace(/^import\s+['"]([^'"]+)['"];?$/gm, (ganz, spec) => {
    const ersatz = fremdesModul(spec, ordner)
    return ersatz ? `import '${pathToFileURL(ersatz).href}';` : ganz
  })
  const zielDatei = resolve(ordner, filename.replace(/\.\w+$/, '') + '.' + cursor.platzhalter.size + '.mjs')
  writeFileSync(zielDatei, code)
  cache.set(abs, zielDatei)
  return zielDatei
}

/**
 * Ordner ALLER Laufadapter — für das eine Aufräumen beim Prozessende.
 * Der Zuhörer wird EINMAL je Prozess gesetzt (nicht je Mount).
 */
const offeneOrdner = new Set()

/**
 * Einen Laufadapter anlegen: eigener Ordner, eigenes Ersatz-Modul, leerer
 * Modul-Cache. Der Aufrufer räumt ihn mit `lfAbbauen()` im Abschlussblock
 * seines Tests wieder weg — so läuft jeder Fall auch EINZELN.
 */
function lfAufbauen() {
  lauf += 1
  TMP = mkdtempSync(join(tmpdir(), 'minimonat1-'))
  ERSATZ_MODUL = resolve(TMP, 'ersatz.mjs')
  writeFileSync(ERSATZ_MODUL, ERSATZ_QUELLE)
  cache.clear()
  cursor = { ordner: TMP, platzhalter: new Set(), kennung: String(lauf) }
  // Bricht ein Fall mittendrin ab, endet der Prozess irgendwann — dann soll
  // kein Ordner stehenbleiben. EIN Zuhörer für den ganzen Lauf.
  offeneOrdner.add(TMP)
  if (!lfAufbauen.zaehler) {
    lfAufbauen.zaehler = true
    process.once('exit', () => {
      for (const o of offeneOrdner) {
        try { rmSync(o, { recursive: true, force: true }) } catch { /* egal */ }
      }
      offeneOrdner.clear()
    })
  }
  return cursor.kennung
}

/** Laufadapter samt Temp-Ordner entfernen (idempotent). */
function lfAbbauen() {
  cache.clear()
  for (const ordner of [TMP, dirname(ERSATZ_MODUL)]) {
    if (ordner && ordner !== '.') rmSync(ordner, { recursive: true, force: true })
  }
  for (const ordner of [TMP, dirname(ERSATZ_MODUL)]) {
    if (ordner && ordner !== '.') offeneOrdner.delete(ordner)
  }
  TMP = ''
  ERSATZ_MODUL = ''
  cursor = { ordner: '', platzhalter: new Set(), kennung: '' }
}

/**
 * Adresse eines kompilierten SFC-Moduls im Laufadapter `kennung`. Die
 * Kennung (`?lauf=…`) ist nötig, weil der Compiler je Lauf neue Dateien
 * schreibt: ohne sie liefert der Modul-Cache des Prozesses das Modul des
 * ERSTEN Laufs.
 */
function modulUrl(abs, kennung) {
  const datei = kompilieren(abs, TMP)
  return pathToFileURL(datei).href + '?lauf=' + encodeURIComponent(kennung)
}

const Vue = await import('vue')
const tick = () => new Promise((loese) => setTimeout(loese, 0))
const warten = (ms = 60) => new Promise((loese) => setTimeout(loese, ms))

/**
 * Die ECHTE Kalender-Seite montieren (Handy-Lage, Listenansicht).
 *
 * Legt einen eigenen Laufadapter an und gibt ihn als `lf` zurück; der
 * Aufrufer baut ihn im Abschlussblock mit `lfAbbauen()` ab.
 *
 * Die Aufbau-Anfrage der Seite wird SOFORT mit dem Plan-Inhalt beantwortet
 * (`terminPlan` VOR dem Mount setzen, wenn sie etwas tragen soll) und ist
 * damit nicht mehr offen: `terminOffen` enthält nach dem Mount nur noch die
 * Anfragen, die der Fall selbst auslöst (Fall 4).
 */
async function seiteMounten() {
  const lf = { kennung: lfAufbauen() }
  document.body.innerHTML = ''
  terminAufrufe = []
  terminOffen = []
  // `terminPlan` NICHT zurücksetzen: ein Fall setzt ihn VOR dem Mount.
  terminAntworten = new Map()
  const Seite = (await import(modulUrl(join(SRC, 'pages/Kalender.vue'), lf.kennung))).default
  const host = document.createElement('div')
  document.body.appendChild(host)
  const app = Vue.createApp({ components: { Seite }, template: '<Seite />' })
  const warnungen = []
  app.config.warnHandler = (meldung) => warnungen.push(meldung)
  app.config.errorHandler = (fehler) => warnungen.push(String(fehler))
  app.mount(host)
  await tick()
  await warten()
  await tick()
  return { app, host, warnungen, lf }
}

/** Die zwei Pfeile des Mini-Monats in der gezeigten Liste. */
function pfeile() {
  return [...document.body.querySelectorAll('.dk-minimonat-pfeil')]
}

/** Nur die Termin-Aufrufe (die anderen Endpunkte der Seite interessieren nicht). */
const terminAufrufeListe = () => terminAufrufe.slice()

/** Tagesschlüssel `JJJJ-MM-TT` in ORTSZEIT (dieselbe Regel wie die Seite). */
const tagText = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`

/** Die sechs Wochen des Mini-Monats für `monat` (`JJJJ-MM`), wie `miniRaster`. */
function miniSpanne(monat) {
  const zeilen = M.miniRaster(monat)
  return [zeilen[0][0].tag, zeilen[zeilen.length - 1][6].tag]
}

/** Punkte des Mini-Monats: `data-tag` je Zelle MIT Punkt. */
function punktTage() {
  return [...document.body.querySelectorAll('.dk-minimonat-tag')]
    .filter((z) => z.querySelector('.dk-minimonat-punkt'))
    .map((z) => z.getAttribute('data-tag'))
}

/** Titel der Zeilen der Tagesliste (leer = keine Zeile). */
function tagesZeilen() {
  return [...document.body.querySelectorAll('.dk-tagesliste-name')].map((e) => e.textContent.trim())
}

// ══════════════════════════════════════════════════════════════════════════
// 4 · Überholte Antwort verliert (Laufzähler der Terminquelle; ohne Fix rot)
// ══════════════════════════════════════════════════════════════════════════
test('MINIMONAT-1 · 4: verspätete alte Antwort überschreibt den neuen Zeitraum nicht', async () => {
  // ECHTER Wettlauf am MOUNT der Seite: zwei Läufe von `mobilTermineLaden`
  // (aus `pages/Kalender.vue`) sind gleichzeitig unterwegs — der ERSTE mit
  // der Spanne des gezeigten Monats, der ZWEITE mit der des nächsten Monats.
  // Jede Anfrage hängt an einem eigenen, von außen auflösbaren Promise
  // (`terminOffen` / `terminAufloesen`), damit die REIHENFOLGE des Eintreffens
  // Sache des Tests ist: erst die NEUERE Antwort (Termin im neuen Zeitraum),
  // dann die ÄLTERE (Termin an einem Tag, den nur der alte Zeitraum enthält).
  //
  // Geprüft wird am gerenderten DOM: Punkt im Mini-Monat am neuen Tag, KEIN
  // Punkt am alten — und die Tagesliste zeigt nur den neuen Termin. Ohne
  // Laufzähler (`if (nr !== ladeNr) return`) schreibt die zuletzt
  // eintreffende, also die ALTE Antwort, und beides ist falsch.
  //
  // Angestoßen wird ausschließlich über die Seite: zweimal › am Mini-Monat
  // (`monatBewegen`); die Läufe entstehen aus dem `spanne`-Ereignis.
  const heute = new Date()
  const altTag = tagText(heute)
  const naechster = new Date(heute.getFullYear(), heute.getMonth() + 2, 1, 12)
  const neuTag = tagText(naechster)
  const alt = { id: 'ALT', title: 'ALT-Termin', allDay: true, start: altTag, end: altTag }
  const neu = { id: 'NEU', title: 'NEU-Termin', allDay: true, start: neuTag, end: neuTag }
  terminPlan = () => ({ termine: [], ms: 0 })
  let lf = null
  let app = null
  try {
    const r = await seiteMounten()
    app = r.app
    lf = r.lf
    const { host, warnungen } = r
    assert.ok(host.textContent, 'die Seite zeigt die Mobil-Liste')
    // Ausgangslage: der Punkt am heutigen Tag fehlt (Aufbau-Antwort war leer).
    assert.deepEqual(punktTage(), [], 'der Aufbau hat keine Termine geliefert')
    const vorher = terminAufrufeListe().length
    // Monat des Aufbaus (vor dem ersten Blättern) — seine Anfrage 1 deckt den
    // Zeitraum, in dem der ALT-Termin liegt.
    const monatJetzt = document.body.querySelector('.dk-minimonat-titel')?.textContent.trim()
    const [, vor] = pfeile()
    assert.ok(vor, 'der Pfeil › des Mini-Monats fehlt')
    // ERSTER Lauf (nächster Monat) — bleibt offen.
    vor.dispatchEvent(new W.MouseEvent('click', { bubbles: true }))
    await tick()
    await warten(30)
    // ZWEITER Lauf (übernächster Monat) — bleibt ebenfalls offen.
    vor.dispatchEvent(new W.MouseEvent('click', { bubbles: true }))
    await tick()
    await warten(30)
    const neue = terminAufrufeListe().slice(vorher)
    // Genau die Anfragen der beiden Blätter-Schritte — zwei aufeinander-
    // folgende Spannen (die ältere zuerst abgeschickt).
    assert.equal(neue.length, 2, `zwei Blätter-Schritte, zwei Anfragen: ${JSON.stringify(neue)}`)
    const [anfrage1, anfrage2] = [terminAnfrage(terminAufrufeListe().length - 1),
      terminAnfrage(terminAufrufeListe().length)]
    assert.ok(monatJetzt, 'der Mini-Monat trägt einen Monatstitel')
    // Spannen: die ÄLTERE ist die des Monats VOR der jüngeren.
    assert.ok(anfrage1.von < anfrage2.von,
      `die ältere Anfrage deckt den früheren Zeitraum (${anfrage1.von} … ${anfrage2.von})`)
    // Ein Tag, den NUR der alte Zeitraum enthält (für den ALT-Termin).
    const altZeitraum = terminAnfrage(1)
    assert.ok(altTag >= altZeitraum.von && altTag <= altZeitraum.bis,
      `der alte Tag ${altTag} liegt im alten Zeitraum ${altZeitraum.von}…${altZeitraum.bis}`)
    assert.ok(!(altTag >= anfrage2.von && altTag <= anfrage2.bis),
      `der alte Tag ${altTag} liegt NICHT im neuen Zeitraum ${anfrage2.von}…${anfrage2.bis}`)
    // ZUERST die NEUERE Antwort…
    terminAufloesen(anfrage2.nr, [neu])
    await tick()
    await warten(20)
    assert.deepEqual(punktTage(), [neuTag], `Punkt am neuen Tag ${neuTag}`)
    // …dann die ÄLTERE — sie darf NICHTS mehr schreiben.
    terminAufloesen(anfrage1.nr, [alt])
    await tick()
    await warten(60)
    await tick()
    assert.deepEqual(punktTage(), [neuTag],
      `die verspätete alte Antwort hat NICHT geschrieben — ${altTag} bleibt ohne Punkt`)
    // Die Tagesliste bleibt LEER: der gewählte Tag (Tag des zweiten
    // Blätterns) trägt keinen der beiden Termine — die verspätete alte
    // Antwort hat auch dort nichts eingetragen.
    assert.deepEqual(tagesZeilen(), [],
      `die Tagesliste zeigt keinen ALT-Termin (statt ${JSON.stringify(tagesZeilen())})`)
    assert.ok(!document.body.textContent.includes('ALT-Termin'),
      'der alte Termin steht nirgends in der gezeigten Liste')
    assert.deepEqual(warnungen, [], 'Vue meldet kein Problem')
  } finally {
    app?.unmount()
    lfAbbauen()
    delete globalThis.__KALENDER_ATTRAFFE__
  }
})

test('MINIMONAT-1 · 5: › lädt genau EINMAL — für den Zeitraum des nächsten Monats', async () => {
  terminPlan = () => ({ termine: [], ms: 0 })
  const { app, host, warnungen, lf } = await seiteMounten()
  try {
    assert.ok(host.textContent, 'die Seite zeigt die Mobil-Liste')
    const [zurueck, vor] = pfeile()
    assert.ok(zurueck && vor, 'die zwei Pfeile des Mini-Monats fehlen')
    // Der Mini-Monat steht (Knopf „Heute“ in seiner Kopfzeile).
    const startKopf = document.body.textContent.indexOf('Heute') >= 0
    assert.ok(startKopf, 'die Liste steht (Knopf „Heute“ im Mini-Monat)')
    const vorher = terminAufrufeListe().length
    vor.dispatchEvent(new W.MouseEvent('click', { bubbles: true }))
    await warten(120)
    await tick()
    assert.deepEqual(warnungen, [], 'Vue meldet kein Problem')
    const neue = terminAufrufeListe().slice(vorher)
    assert.equal(neue.length, 1, `EIN einziger Aufruf für den neuen Zeitraum (${JSON.stringify(neue)})`)
    const [von, bis] = neue[0]
    // Der nächste Monat (relativ zu heute) gibt den Anker; die Spanne ist die
    // der sechs Wochen des Mini-Monats — Montag vor dem Ersten bis Sonntag
    // nach dem Letzten (dieselbe Regel wie `miniRaster`).
    const heute = new Date()
    const naechster = new Date(heute.getFullYear(), heute.getMonth() + 1, 1, 12)
    const schluessel = `${naechster.getFullYear()}-${String(naechster.getMonth() + 1).padStart(2, '0')}`
    const zwei = (n) => String(n).padStart(2, '0')
    const tag = (d) => `${d.getFullYear()}-${zwei(d.getMonth() + 1)}-${zwei(d.getDate())}`
    const erster = new Date(naechster.getFullYear(), naechster.getMonth(), 1, 12)
    const versatz = (erster.getDay() + 6) % 7            // Mo = 0 … So = 6
    const spannenVon = new Date(erster.getFullYear(), erster.getMonth(), 1 - versatz, 12)
    // Sechs Wochen; die sechste Zeile entfällt, wenn sie keinen Tag des Monats
    // mehr hat (so rechnet `miniRaster`).
    const sechste = new Date(spannenVon.getFullYear(), spannenVon.getMonth(), spannenVon.getDate() + 35, 12)
    const sechsteNoetig = sechste.getMonth() === erster.getMonth()
    const spannenBis = new Date(spannenVon.getFullYear(), spannenVon.getMonth(),
      spannenVon.getDate() + (sechsteNoetig ? 41 : 34), 12)
    assert.equal(von, tag(spannenVon),
      `die Spanne beginnt am Montag vor dem Ersten (${von} statt ${tag(spannenVon)})`)
    assert.equal(bis, tag(spannenBis),
      `die Spanne endet am Sonntag der letzten Rasterzeile (${bis} statt ${tag(spannenBis)})`)
    // Der gezeigte Mini-Monat folgt: der gewählte Tag liegt im nächsten Monat.
    const gewaehlt = document.body.querySelector('.dk-minimonat-tag.is-gewaehlt')
    assert.ok(gewaehlt, 'kein gewählter Tag im Mini-Monat')
    assert.match(gewaehlt.getAttribute('data-tag'), new RegExp(`^${schluessel}-`),
      `der gewählte Tag wandert in den nächsten Monat (${gewaehlt.getAttribute('data-tag')})`)
  } finally {
    app.unmount()
    lfAbbauen()
  }
})

// ══════════════════════════════════════════════════════════════════════════
// 6 · Raster nach dem Umschalten: springt auf den geblätterten Tag
// ══════════════════════════════════════════════════════════════════════════
test('MINIMONAT-1 · 6: `@bereit` des Rasters springt auf den gewählten Tag', async () => {
  terminPlan = () => ({ termine: [], ms: 0 })
  // Der Raster-Baustein wird für diesen Fall durch eine Attrappe ersetzt: sie
  // merkt sich `gotoDate` und meldet `bereit`, sobald sie steht — genau so
  // meldet die Bibliothek im Betrieb. In der LISTE gibt es das Raster nicht
  // (`v-else` zur Liste); erst nach dem Wechsel auf „Monat“ entsteht es.
  const gerufen = []
  globalThis.__KALENDER_ATTRAFFE__ = {
    KronosCalendar: {
      name: 'KronosCalendarAttrappe',
      props: ['selectedCalendars', 'viewMode', 'monatPunkte'],
      // Die Seite hängt Attribute an den Baustein (`monat-punkte`).
      inheritAttrs: false,
      emits: ['bereit'],
      setup(_, { expose, emit }) {
        expose({
          gotoDate: (tag) => gerufen.push(String(tag)),
          prev() {}, next() {}, today() {}, changeView() {}, refetchEvents() {}, neuZuordnen() {},
        })
        setTimeout(() => emit('bereit'), 0)
        return () => Vue.h('div', { class: 'kronos-calendar-attrappe' })
      },
    },
  }
  let lf = null
  let app = null
  try {
    const r = await seiteMounten()
    app = r.app
    lf = r.lf
    const { host, warnungen } = r
    // In der Listenansicht ist KEIN Raster gebaut.
    assert.equal(document.querySelector('.kronos-calendar-attrappe'), null,
      'in der Liste gibt es kein Raster')
    assert.deepEqual(gerufen, [], 'in der Liste gibt es kein Raster (kein gotoDate)')
    const [zurueck, vor] = pfeile()
    assert.ok(zurueck && vor, 'die zwei Pfeile des Mini-Monats fehlen')
    vor.dispatchEvent(new W.MouseEvent('click', { bubbles: true }))
    await warten(60)
    const gewaehlt = document.body.querySelector('.dk-minimonat-tag.is-gewaehlt')
    assert.ok(gewaehlt, 'kein gewählter Tag im Mini-Monat')
    const tag = gewaehlt.getAttribute('data-tag')
    // Umschalten auf „Monat“: jetzt entsteht das Raster, meldet `bereit`, und
    // die Seite springt auf den gewählten (geblätterten) Tag.
    const monatKnopf = document.body.querySelector('[data-ansicht="monat"]')
    assert.ok(monatKnopf, 'Segment „Monat“ fehlt')
    monatKnopf.click()
    await tick()
    await warten(80)
    await tick()
    assert.deepEqual(gerufen, [tag],
      `das Raster springt auf den gewählten Tag ${tag} (gerufen: ${JSON.stringify(gerufen)})`)
    assert.deepEqual(warnungen, [], 'Vue meldet kein Problem')
    host.remove()
  } finally {
    app?.unmount()
    lfAbbauen()
    delete globalThis.__KALENDER_ATTRAFFE__
  }
})

// ══════════════════════════════════════════════════════════════════════════
// 7 · Der tote Raster-Halter-Rest ist weg (in der Liste ist die Bibliothek
//     nicht gemountet — es gibt dort keinen offscreen-Zustand)
// ══════════════════════════════════════════════════════════════════════════
test('MINIMONAT-1 · 7: kein offscreen-Rest am Rasterhalter', () => {
  const q = seite()
  assert.ok(!/offscreen/.test(q), 'keine offscreen-Klasse und keine offscreen-Regel mehr')
  assert.match(q, /<div v-else class="kal-mobil-raster">/, 'das Raster hängt an v-else zur Liste')
})
