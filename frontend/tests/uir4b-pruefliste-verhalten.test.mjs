/**
 * UI-R4b — Verhaltenstests statt Quelltext-Muster.
 *
 * Ein Review (Opus) hat zu Recht bemängelt, dass „nach jedem Entscheid neu
 * laden“ nur als Regex geprüft war: ein Umbau auf `if (letzteMeldung.weiter)
 * await loadBoard()` hätte den Test NICHT rot gemacht. Diese Datei mountet
 * deshalb die ECHTE Tafel (`ModerationBoard.vue`) in jsdom, ersetzt nur die
 * Datenschicht (`api/kanbanApi.js`) und schaut, was tatsächlich passiert:
 *
 *   1. Freigabe in der Vorschlags-Spalte → Server wird gerufen, Toast kommt,
 *      und das Brett lädt NEU (Zähler der Server-Abfrage steigt).
 *   2. Gegenprobe zum alten Fehler: auch wenn die Antwort „es wartet weiter“
 *      sagt (`new_status: 'Vorschlag'`), wird neu geladen.
 *   3. Konflikt-Spalte: es gibt KEINEN Freigeben-Knopf; der Serverweg ohne
 *      `ueberschneidung: 1` wird nicht aufgerufen (DEV-7b nicht umgangen).
 *   4. Verweigerung (403) an der Karte: der Text steht auf dem Bildschirm und
 *      die Tafel lädt neu.
 *   5. Stufen-Titel: `get_rollen_erklaerung` wird EINMAL geladen, auch bei
 *      mehreren Karten (Punkt 7b).
 *
 * Lauf: node --test tests/uir4b-pruefliste-verhalten.test.mjs   (cwd = frontend/)
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, mkdtempSync, writeFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, dirname, resolve, basename } from 'node:path'
import { pathToFileURL } from 'node:url'
import { JSDOM } from 'jsdom'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'

// ── DOM zuerst (Vue greift beim Import auf `document` zu) ─────────────────
const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
for (const schluessel of ['window', 'document', 'Node', 'Element', 'HTMLElement', 'Event',
  'MouseEvent', 'SVGElement', 'CSS', 'getComputedStyle', 'MutationObserver']) {
  globalThis[schluessel] = dom.window[schluessel]
}
const Vue = await import('vue')

const HIER = dirname(new URL(import.meta.url).pathname)
const SRC = resolve(HIER, '..', 'src', 'diakonos')
/** Quelle einer Datei unter `src/diakonos` lesen (Quelltext-Prüfungen). */
const lies = (rel) => readFileSync(join(SRC, rel), 'utf8')
/**
 * Wie `lies`, aber ohne Kommentare — damit ein Feldname, der in einer
 * Erklärung („das Feld gibt es hier nicht“) vorkommt, keinen Treffer vortäuscht.
 */
const liegtOhneKommentare = (rel) => lies(rel)
  .replace(/\/\*[\s\S]*?\*\//g, '')
  .split('\n').map((z) => z.replace(/(^|[^:])\/\/.*$/, '$1')).join('\n')

// ── SFC → ES-Modul ────────────────────────────────────────────────────────
// TMP liegt ABSICHTLICH unter `frontend/` (nicht im System-Temp): die
// übersetzten Module importieren echte Pakete (`sortablejs`, `jsdom` …), und
// die löst Node nur auf, wenn der Pfad unter dem Projekt mit `node_modules`
// liegt. In einem Beitrag außerhalb (z. B. /tmp) schlägt der Import fehl.
const TMP = mkdtempSync(join(HIER, '..', '.uir4b-tmp-'))
const cache = new Map()
const VUE_URL = import.meta.resolve('vue')
const attrappen = new Map()

function attrappe(name, code) {
  const ziel = join(TMP, `${name}.mjs`)
  writeFileSync(ziel, code)
  attrappen.set(name, pathToFileURL(ziel).href)
}

function kompilieren(abs) {
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
  code = code.replace(/from\s+['"]([^'"]+)['"]/g, (voll, spec) => {
    if (!spec.startsWith('.')) return voll
    const name = basename(spec)
    const ziel = resolve(dirname(abs), spec)
    if (attrappen.has(name)) return `from '${attrappen.get(name)}'`
    // JEDE relative Abhängigkeit geht durch `kompilieren` — nur so bekommt
    // auch `freigabeStufenReaktiv.mjs` seine Kopie je „Seite“ (Modul-Merker).
    return `from '${pathToFileURL(spec.endsWith('.vue') ? kompilieren(ziel) : ziel).href}'`
  })
  const ziel = resolve(TMP, filename.replace(/\.vue$/, '') + '.' + cache.size + '.mjs')
  writeFileSync(ziel, code)
  cache.set(abs, ziel)
  return ziel
}

const tick = () => new Promise((loese) => setTimeout(loese, 0))
const warte = (ms) => new Promise((loese) => setTimeout(loese, ms))

function text(host) {
  return host.textContent.replace(/\s+/g, ' ').trim()
}

async function mounten(Komponente, props = {}) {
  const host = document.createElement('div')
  document.body.appendChild(host)
  const warnungen = []
  const app = Vue.createApp(Komponente, props)
  app.config.warnHandler = (meldung) => warnungen.push(meldung)
  const vm = app.mount(host)
  await tick()
  return { host, app, vm, warnungen }
}

// ══════════════════════════════════════════════════════════════════════════
// Attrappen der Datenschicht
// ══════════════════════════════════════════════════════════════════════════
/** Lage der Server-Antworten; jeder Aufruf wird gezählt. */
const lage = {
  brettAufrufe: 0,
  titelAufrufe: 0,
  freigaben: [],
  konfliktAufrufe: 0,
  brett: { vorschlaege: [], konflikte: [], staging: [], notifications: {}, abgelehnt: [] },
  freigabeAntwort: { id: 'EV-1', new_status: 'Festgelegt', action: 'festlegen', offen: [], naechste_stufe: null },
  freigabeFehler: null,
}

attrappe('kanbanApi.js', `
export async function getBoardData() {
  globalThis.__uir4bBrettAufruf()
  return globalThis.__uir4bBrett()
}
export async function saveStagingState() { return { ok: true } }
export async function getRessources() { return { resources: [], types: [] } }
export async function resolveConflict(id, action, edits) {
  globalThis.__uir4bFreigabe(id, action, edits || {})
  const fehler = globalThis.__uir4bFreigabeFehler()
  if (fehler) throw fehler
  return globalThis.__uir4bFreigabeAntwort()
}
export async function getConflictPartner() { return null }
export async function getModerationCount() { return { count: 0 } }
export async function updateSeriesBatchFast() { return { ok: true } }
export async function deleteSeriesBatchFast() { return { ok: true } }
`)

attrappe('useApi.js', `
export class AuditConfirmationRequired extends Error {}
const warte = (ms) => new Promise((l) => setTimeout(l, ms))
export async function apiCall(endpunkt) {
  globalThis.__uir4bAlleApi = (globalThis.__uir4bAlleApi || 0) + 1
  const pfad = String(endpunkt)
  if (pfad.includes('get_rollen_erklaerung')) {
    globalThis.__uir4bTitelAufruf()
    // Der Test kann die Antwort anhalten (__uir4bTitelTor) — damit ist die
    // Reihenfolge 'Antraege vor Titeln' deterministisch. Und er kann sie leer
    // lassen (__uir4bOhneTitel): dann kommen KEINE Namen an.
    if (globalThis.__uir4bTitelTor) await globalThis.__uir4bTitelTor
    if (globalThis.__uir4bOhneTitel) return { stufen_titel: {} }
    return { stufen_titel: {
      untergruppe: 'Untergruppe', gruppe: 'Gruppe', gemeinde: 'Alle Mitglieder der Gemeinde' } }
  }
  if (pfad.includes('get_offene_sichtbarkeits_antraege')) {
    return { antraege: globalThis.__uir4bAntraege || [] }
  }
  if (pfad.includes('entscheide_sichtbarkeit')) {
    globalThis.__uir4bEntscheidAufrufe = (globalThis.__uir4bEntscheidAufrufe || 0) + 1
    return globalThis.__uir4bEntscheidAntwort || {}
  }
  return {}
}
export async function apiAntwortPruefen(r) { return r }
export const navigate = () => {}
`)

// Dieselbe Titel-Antwort wie in der Attrappe — für direkte Ladeaufrufe im Test.
globalThis.__uir4bEchteApi = async (pfad) => {
  if (!String(pfad).includes('get_rollen_erklaerung')) return {}
  globalThis.__uir4bTitelAufruf()
  return { stufen_titel: {
    untergruppe: 'Untergruppe', gruppe: 'Gruppe', gemeinde: 'Alle Mitglieder der Gemeinde' } }
}

attrappe('useToast.js', `
export const showToast = (nachricht, typ, aktion) => globalThis.__uir4bToast(nachricht, typ, aktion)
`)

globalThis.__uir4bBrettAufruf = () => { lage.brettAufrufe += 1 }
globalThis.__uir4bBrett = () => JSON.parse(JSON.stringify(lage.brett))
// Zählt über den ganzen Lauf: jeder der vier Titel-Aufrufe eines Tests IST ein
// Aufruf — auch wenn die Attrappe je Seite neu geladen wird.
globalThis.__uir4bTitelAufrufe = 0
globalThis.__uir4bAlleApi = 0
globalThis.__uir4bTitelAufruf = () => { lage.titelAufrufe += 1; globalThis.__uir4bTitelAufrufe += 1 }
globalThis.__uir4bFreigabe = (id, action, edits) => { lage.freigaben.push({ id, action, edits }) }
globalThis.__uir4bFreigabeFehler = () => lage.freigabeFehler
globalThis.__uir4bFreigabeAntwort = () => ({ ...lage.freigabeAntwort })
globalThis.__uir4bToasts = []
globalThis.__uir4bToast = (nachricht, typ, aktion) => {
  globalThis.__uir4bToasts.push({ nachricht, typ, aktion })
}

function zuruecksetzen() {
  globalThis.__uir4bAntraege = []
  globalThis.__uir4bEntscheidAntwort = {}
  globalThis.__uir4bEntscheidAufrufe = 0
  globalThis.__uir4bTitelTor = null
  globalThis.__uir4bOhneTitel = false
  lage.brettAufrufe = 0
  lage.titelAufrufe = 0
  lage.freigaben = []
  lage.freigabeFehler = null
  lage.freigabeAntwort = { id: 'EV-1', new_status: 'Festgelegt', action: 'festlegen', offen: [], naechste_stufe: null }
  globalThis.__uir4bToasts = []
}

/** Ein Vorschlag, den der Aufrufer auf der Gruppenstufe prüfen darf. */
function vorschlag(id = 'EV-1', extra = {}) {
  return {
    id, type: 'event', title: 'Chorprobe', start: '2026-11-20 18:00:00', end: '2026-11-20 19:00:00',
    all_day: false, calendar: 'chor', calendar_title: 'Chor', calendar_color: '#336699',
    status: 'Vorschlag', stufe: 'gruppe', darf_pruefen: true, ...extra,
  }
}

function konflikt(id = 'EV-K') {
  return {
    id, type: 'event', title: 'Chorprobe (Konflikt)', start: '2026-11-20 18:00:00',
    end: '2026-11-20 19:00:00', all_day: false, calendar: 'chor', calendar_title: 'Chor',
    calendar_color: '#336699', status: 'Konflikt', stufe: 'gruppe', darf_pruefen: true,
  }
}

/** Zählt die Knöpfe einer Karte mit der Beschriftung „Freigeben“. */
function freigebenKnoepfe(host) {
  return [...host.querySelectorAll('.dk-mcard-freigeben')]
}

/**
 * Die Tafel als frische „Seite“: eigener Zwischenspeicher (eigener
 * Modulgraph). Sonst behielte `freigabeStufenReaktiv.mjs` seinen
 * „schon geladen“-Merker aus der vorherigen Prüfung — genau das ist ja die
 * Seiten-Lebensdauer, die hier geprüft werden soll.
 */
async function tafel() {
  cache.clear()
  return (await import(
    pathToFileURL(kompilieren(join(SRC, 'components/kronos/ModerationBoard.vue'))).href
  )).default
}

test.after(() => {
  rmSync(TMP, { recursive: true, force: true })
  // Jeder Seiten-Durchlauf bekommt eigene übersetzte Module; die räumt der
  // Test am Ende mit ab (sonst bleibt `frontend/.uir4b-tmp-*` liegen).
  for (const name of readdirSync(join(HIER, '..'))) {
    if (name.startsWith('.uir4b-tmp-')) rmSync(join(HIER, '..', name), { recursive: true, force: true })
  }
})

// ══════════════════════════════════════════════════════════════════════════
// 1 · Freigabe und Neuladen
// ══════════════════════════════════════════════════════════════════════════
test('UI-R4b · Freigabe im Vorschlag lädt das Brett danach NEU (Verhalten, kein Regex)', async () => {
  zuruecksetzen()
  lage.brett = {
    vorschlaege: [vorschlag()], konflikte: [], staging: [], notifications: {}, abgelehnt: [],
  }
  const Tafel = await tafel()
  const { host, warnungen } = await mounten(Tafel)
  await warte(30)

  const knopf = freigebenKnoepfe(host)[0]
  assert.ok(knopf, 'in der Vorschlags-Spalte fehlt der Freigeben-Knopf')
  const vorher = lage.brettAufrufe

  knopf.click()
  await warte(60)

  assert.equal(lage.freigaben.length, 1, 'der Server wurde nicht gerufen')
  assert.deepEqual(lage.freigaben[0], { id: 'EV-1', action: 'festlegen', edits: {} },
    'Freigabe ohne Konflikt-Dialog darf KEIN ueberschneidung senden')
  assert.equal(lage.brettAufrufe, vorher + 1, 'nach dem Entscheid wurde NICHT neu geladen')
  const toast = globalThis.__uir4bToasts.at(-1)
  assert.ok(toast, 'keine Rückmeldung nach der Freigabe')
  assert.equal(toast.nachricht, 'Termin freigegeben.')
  assert.deepEqual(warnungen, [], 'Vue-Warnungen beim Zeichnen')
})

test('UI-R4b · Gegenprobe: auch eine Zwischenstufe lädt neu (früher blieb die Karte stehen)', async () => {
  zuruecksetzen()
  // Der Server sagt „Vorschlag bleibt, wartet auf gemeinde“ — die Kette kann
  // die Gruppenstufe überspringen (untergruppe → gemeinde).
  lage.freigabeAntwort = {
    id: 'EV-1', new_status: 'Vorschlag', action: 'festlegen',
    offen: ['gemeinde'], naechste_stufe: 'gemeinde',
  }
  lage.brett = {
    vorschlaege: [vorschlag()], konflikte: [], staging: [], notifications: {}, abgelehnt: [],
  }
  const Tafel = await tafel()
  const { host } = await mounten(Tafel)
  await warte(30)

  const vorher = lage.brettAufrufe
  freigebenKnoepfe(host)[0].click()
  await warte(60)

  assert.equal(lage.brettAufrufe, vorher + 1,
    'bei „wartet weiter“ muss ebenfalls neu geladen werden')
  const toast = globalThis.__uir4bToasts.at(-1)
  // UI-R4c (Punkt 1): der Servertitel steht als STUFE im Satz — nicht als
  // Empfänger („geht jetzt an Alle Mitglieder der Gemeinde“ las sich wie die
  // bereits erteilte Freigabe für alle).
  assert.equal(toast.nachricht,
    'Stufe freigegeben — der Termin geht jetzt an die Freigabe der Stufe „Alle Mitglieder der Gemeinde“.')
  assert.equal(toast.typ, 'warning', 'eine Zwischenstufe ist kein grüner Haken')
})

// ══════════════════════════════════════════════════════════════════════════
// 2 · Konfliktspalte: kein direkter Freigeben-Knopf
// ══════════════════════════════════════════════════════════════════════════
test('UI-R4b · in der Konflikt-Spalte gibt es KEINEN direkten Freigeben-Knopf', async () => {
  zuruecksetzen()
  lage.brett = {
    vorschlaege: [], konflikte: [konflikt()], staging: [], notifications: {}, abgelehnt: [],
  }
  const Tafel = await tafel()
  const { host } = await mounten(Tafel)
  await warte(30)

  const karten = [...host.querySelectorAll('.dk-mcard')].map(e => e.dataset.id)
  assert.deepEqual(karten, ['EV-K'], 'die Konfliktkarte fehlt')
  assert.equal(freigebenKnoepfe(host).length, 0,
    'Freigeben ohne Konflikt-Dialog darf es in der Konflikt-Spalte NICHT geben')
  assert.equal(lage.freigaben.length, 0, 'kein Serveraufruf ohne Dialog')
  assert.equal(lage.brettAufrufe, 1, 'auch ohne Knopf wird das Brett geladen')
})

// ══════════════════════════════════════════════════════════════════════════
// 3 · Verweigerung (403) sichtbar + Neuladen
// ══════════════════════════════════════════════════════════════════════════
test('UI-R4b · 403 zeigt den Text an der Karte UND lädt neu', async () => {
  zuruecksetzen()
  const satz = 'Dieser Termin wartet noch auf die Freigabe durch Alle Mitglieder der Gemeinde.'
  lage.freigabeFehler = Object.assign(new Error(satz), { status: 403, message: satz })
  lage.brett = {
    vorschlaege: [vorschlag()], konflikte: [], staging: [], notifications: {}, abgelehnt: [],
  }
  const Tafel = await tafel()
  const { host } = await mounten(Tafel)
  await warte(30)

  const vorher = lage.brettAufrufe
  freigebenKnoepfe(host)[0].click()
  await warte(60)

  const sichtbar = text(host)
  assert.match(sichtbar, /wartet noch auf die Freigabe/, 'der Servertext steht nicht auf der Karte')
  assert.equal(lage.brettAufrufe, vorher + 1, 'nach einer Verweigerung wurde nicht neu geladen')
  const toast = globalThis.__uir4bToasts.at(-1)
  assert.equal(toast.typ, 'error', 'eine Verweigerung ist eine Fehlermeldung')
})

// ══════════════════════════════════════════════════════════════════════════
// 4 · Stufen-Titel: EINMAL je Seite
// ══════════════════════════════════════════════════════════════════════════
test('UI-R4b · der gemeinsame Lader holt die Titel EINMAL je Seite', async () => {
  // Vier Karten rufen `stufenTitelEinmalLaden` — es geht EINE Abfrage hinaus.
  const Reaktiv = await import(
    pathToFileURL(join(SRC, 'components/kronos/freigabeStufenReaktiv.mjs')).href
  )
  let abfragen = 0
  const apiCall = async (pfad) => {
    if (!String(pfad).includes('get_rollen_erklaerung')) return {}
    abfragen += 1
    await warte(10)   // Antwort kommt später: alle vier rufen vorher an
    return { stufen_titel: { untergruppe: 'Untergruppe', gruppe: 'Gruppe',
      gemeinde: 'Alle Mitglieder der Gemeinde' } }
  }
  Reaktiv.stufenTitelMerkerLeeren()
  // Vier gleichzeitige Aufrufe wie vier Karten einer Seite.
  const stand = await Promise.all([
    Reaktiv.stufenTitelEinmalLaden(apiCall),
    Reaktiv.stufenTitelEinmalLaden(apiCall),
    Reaktiv.stufenTitelEinmalLaden(apiCall),
    Reaktiv.stufenTitelEinmalLaden(apiCall),
  ])
  assert.equal(abfragen, 1, `get_rollen_erklaerung wurde ${abfragen}× geladen — je Seite genau EINMAL`)
  assert.equal(stand[0].gruppe, 'Gruppe', 'die Titel kommen an')
  // Und danach (weitere Karten derselben Seite) lädt er NICHT erneut.
  await Reaktiv.stufenTitelEinmalLaden(apiCall)
  assert.equal(abfragen, 1, 'weitere Karten laden nicht erneut')
})

// ══════════════════════════════════════════════════════════════════════════
// 5 · Freigabe-Anträge: Toast und Stufe kommen aus der Antwort
// ══════════════════════════════════════════════════════════════════════════
/** Die Anträge-Karte als frische „Seite“ (eigener Modulgraph, s. tafel()). */
async function antraegeKarte() {
  cache.clear()
  return (await import(
    pathToFileURL(kompilieren(join(SRC, 'components/kronos/ModerationAntraege.vue'))).href
  )).default
}

/** Ein Antrag, der auf der Gruppenstufe entschieden wird (Ziel: Gemeinde). */
const ANTRAG = {
  typ: 'kalender', objekt: 'chor-kg', stufe: 'gruppe', titel: 'Chorproben',
  gruppe: 'chor', gruppe_name: 'Chor', untergruppe_name: 'Sopran', ziel: 'gemeinde',
}

test('UI-R4b · Antrag auf Gruppenstufe meldet „geht jetzt an die Gemeinde-Moderation“', async () => {
  zuruecksetzen()
  globalThis.__uir4bAntraege = [ANTRAG]
  // ECHTE Antwortform von `entscheide_sichtbarkeit` (rechte/verwaltung.py):
  // {success, gruppe_status, gemeinde_status} — kein naechste_stufe/offen.
  globalThis.__uir4bEntscheidAntwort = {
    success: true, gruppe_status: 'aktiv', gemeinde_status: 'beantragt',
  }
  const Karte = await antraegeKarte()
  const { host } = await mounten(Karte)
  await warte(60)

  const knopf = [...host.querySelectorAll('button')].find(b => /Annehmen/.test(b.textContent))
  assert.ok(knopf, '„Annehmen“ fehlt')
  knopf.click()
  await warte(60)

  const toast = globalThis.__uir4bToasts.at(-1)
  assert.ok(toast, 'kein Toast nach dem Annehmen')
  // Der alte Text behauptete „für alle Mitglieder der Gemeinde“.
  assert.doesNotMatch(toast.nachricht, /für alle Mitglieder der Gemeinde/,
    'die Gemeinde-Freigabe ist noch NICHT erteilt')
  assert.match(toast.nachricht, /geht jetzt an die Freigabe der Stufe „Alle Mitglieder der Gemeinde“/)
  assert.doesNotMatch(toast.nachricht, /geht jetzt an Alle Mitglieder der Gemeinde/,
    'der Titel ist eine Stufe, kein Empfänger')
  assert.equal(toast.typ, 'warning', 'eine Zwischenstufe ist kein grüner Haken')
})

test('UI-R4b · Antrag mit „nichts mehr offen“ meldet die Freigabe', async () => {
  zuruecksetzen()
  globalThis.__uir4bAntraege = [{ ...ANTRAG, ziel: 'gruppe' }]
  // Ziel „gruppe“ erreicht = gruppe_status „aktiv“ (die echte Antwortform).
  globalThis.__uir4bEntscheidAntwort = {
    success: true, gruppe_status: 'aktiv', gemeinde_status: 'aus',
  }
  const Karte = await antraegeKarte()
  const { host } = await mounten(Karte)
  await warte(60)

  ;[...host.querySelectorAll('button')].find(b => /Annehmen/.test(b.textContent)).click()
  await warte(60)

  const toast = globalThis.__uir4bToasts.at(-1)
  assert.match(toast.nachricht, /^Freigegeben:/)
  assert.equal(toast.typ, 'success')
})

test('UI-R4b · der Toast erfindet KEINE Serverfelder (ziel_erreicht/naechste_stufe gibt es hier nicht)', async () => {
  // Gegenprobe zum Befund: `entscheide_sichtbarkeit` liefert nur
  // gruppe_status/gemeinde_status. Ein Toast, der auf erfundene Felder baut,
  // meldete bei ziel=gemeinde fälschlich „Freigegeben“.
  zuruecksetzen()
  globalThis.__uir4bAntraege = [ANTRAG]   // ziel = gemeinde
  // Gemeinde steht noch auf „beantragt“ — also NICHT freigegeben.
  globalThis.__uir4bEntscheidAntwort = {
    success: true, gruppe_status: 'aktiv', gemeinde_status: 'beantragt',
  }
  const Karte = await antraegeKarte()
  const { host } = await mounten(Karte)
  await warte(60)
  ;[...host.querySelectorAll('button')].find(b => /Annehmen/.test(b.textContent)).click()
  await warte(60)

  const toast = globalThis.__uir4bToasts.at(-1)
  assert.doesNotMatch(toast.nachricht, /^Freigegeben:/,
    '„beantragt“ ist keine Freigabe — trotz success:true')
  assert.equal(toast.typ, 'warning')

  // Und die Quelle nennt das erfundene Feld nirgends mehr (Kommentare zählen
  // nicht — dort STEHT der Name als Erklärung, warum er nicht benutzt wird).
  assert.doesNotMatch(liegtOhneKommentare('components/kronos/ModerationAntraege.vue'), /ziel_erreicht/,
    '`ziel_erreicht` gibt es auf dem Server nicht — nicht behaupten')
})

test('UI-R4b · „Stufe: …“ zeichnet nach, wenn die Titel erst nach den Anträgen kommen', async () => {
  // Der Befund: kamen die Anträge VOR den Stufen-Titeln, blieb „Stufe: —“
  // stehen. Geprüft wird die Zeichnung selbst — ein computed mit derselben
  // Zeilen-Regel wie `ModerationAntraege.vue`, das den REAKTIVEN Namensgeber
  // benutzt. Ohne `stufenNameReaktiv` bliebe „—“ stehen.
  const F = await import(
    pathToFileURL(join(SRC, 'components/kronos/freigabeStufen.mjs')).href
  )
  const R = await import(
    pathToFileURL(join(SRC, 'components/kronos/freigabeStufenReaktiv.mjs')).href
  )
  const antrag = { typ: 'kalender', objekt: 'chor-kg', stufe: 'gruppe', titel: 'Chorproben' }

  // Frischer Seitenstand: die Ablage ist ein Modul-Singleton (alle Bauteile
  // einer Seite teilen sie) — hier startet sie leer.
  R.titelStand.value = {}
  F.stufenTitel.wert = {}

  const host = document.createElement('div')
  document.body.appendChild(host)
  const app = Vue.createApp({
    setup() {
      const antraege = Vue.ref([antrag])
      // GENAU die Zeile aus ModerationAntraege.vue.
      const zeilen = Vue.computed(() => F.antragZeilen(antraege.value, R.stufenNameReaktiv))
      return { zeilen }
    },
    template: '<ul><li v-for="z in zeilen" :key="z.objekt">{{ z.stufeText }}</li></ul>',
  })
  app.mount(host)

  // Titel noch nicht da: neutral, aber KEIN dauerhaftes „—“ im Datenmodell.
  assert.equal(text(host).trim(), F.STUFE_UNBEKANNT, 'ohne Titel steht der neutrale Platzhalter')

  // Jetzt treffen die Server-Titel ein — die Zeile zieht VON SELBST nach.
  await R.stufenTitelLaden(async (pfad) => {
    if (!String(pfad).includes('get_rollen_erklaerung')) return {}
    return { stufen_titel: {
      untergruppe: 'Untergruppe', gruppe: 'Gruppe', gemeinde: 'Alle Mitglieder der Gemeinde' } }
  })
  await Vue.nextTick()
  assert.equal(text(host).trim(), 'Gruppe', 'der Servertitel fehlt nach der Antwort')
  app.unmount()
})

// ══════════════════════════════════════════════════════════════════════════
// 6 · UI-R4c (Punkt 3): die Schranke im Freigeben-Weg greift WIRKLICH
// ══════════════════════════════════════════════════════════════════════════
test('UI-R4c · Konfliktkarte in der Vorschlags-Spalte: kein Knopf und kein Serveraufruf', async () => {
  // Vorher stand die Schranke auf `item?.column === 'konflikte'` — ein Feld,
  // das KEINE Karte trägt. Sie war nie wahr. Hier steht der Konflikt bewusst
  // in der Vorschlags-Spalte (Status „Konflikt“, `darf_pruefen`): weder der
  // Knopf noch der Freigabe-Weg dürfen ihn ohne Dialog freigeben.
  zuruecksetzen()
  lage.brett = {
    vorschlaege: [konflikt('EV-K2')], konflikte: [], staging: [], notifications: {}, abgelehnt: [],
  }
  const Tafel = await tafel()
  const { host } = await mounten(Tafel)
  await warte(30)

  assert.equal(freigebenKnoepfe(host).length, 0,
    'eine Konfliktkarte bekommt KEINEN direkten Freigeben-Knopf (nur der Dialog setzt ueberschneidung: 1)')
  assert.equal(lage.freigaben.length, 0, 'kein Serveraufruf ohne Konflikt-Dialog')
})

test('UI-R4c · `istKonfliktEintrag` prüft Status und Konflikt-IDs, nicht das Feld `column`', async () => {
  const F = await import(
    pathToFileURL(join(SRC, 'components/kronos/freigabeStufen.mjs')).href
  )
  const einzel = { id: 'EV-1', status: 'Vorschlag', stufe: 'gruppe', darf_pruefen: true }
  // Ein gesetztes `column` ändert NICHTS (das Feld gibt es am Item nicht).
  assert.equal(F.istKonfliktEintrag({ ...einzel, column: 'konflikte' }), false,
    '`column` am Item ist keine Auskunft')
  assert.equal(F.istKonfliktEintrag({ ...einzel, status: 'Konflikt' }), true)
  assert.equal(F.istKonfliktEintrag({ ...einzel, status: '' }, ['EV-1']), true,
    'ohne Status entscheidet die ID im konflikte-Feld der Antwort')
  assert.equal(F.istKonfliktEintrag(einzel, ['EV-1']), false,
    'ein Vorschlag (Status „Vorschlag“) bleibt freigebbar')
  assert.equal(F.istKonfliktEintrag({ ...einzel, status: '' }, ['EV-2']), false)
  // Serienkarte: `has_konflikt` bzw. eine enthaltene Termin-ID im Konfliktfeld.
  const serie = { type: 'serie', id: 'SER-1', has_konflikt: false,
    event_ids: ['EV-7', 'EV-8'], events: [{ id: 'EV-7' }, { id: 'EV-8' }] }
  assert.equal(F.istKonfliktEintrag(serie), false)
  assert.equal(F.istKonfliktEintrag({ ...serie, has_konflikt: true }), true)
  assert.equal(F.istKonfliktEintrag(serie, ['EV-8']), true)
  assert.equal(F.istKonfliktEintrag(null), false)
})

// ══════════════════════════════════════════════════════════════════════════
// 7 · UI-R4c (Punkt 2): ohne geladene Titel steht kein „—“ im Toast
// ══════════════════════════════════════════════════════════════════════════
test('UI-R4c · Antrag ohne Stufen-Titel meldet „die nächste Stufe“ statt „—“', async () => {
  // Gegenprobe zum Befund: `zielStufeName` gab den neutralen Platzhalter
  // `STUFE_UNBEKANNT` („—“) durch → Toast „… geht jetzt an —.“. Hier antwortet
  // `get_rollen_erklaerung` ohne Titel (kalte Antwort), die Anträge sind aber
  // da; die Stufe muss dann unbenannt bleiben.
  zuruecksetzen()
  globalThis.__uir4bAntraege = [ANTRAG]
  globalThis.__uir4bEntscheidAntwort = {
    success: true, gruppe_status: 'aktiv', gemeinde_status: 'beantragt',
  }
  // Frische „Seite“ mit leerem Titelstand — es treffen KEINE Namen ein.
  globalThis.__uir4bOhneTitel = true
  // Die Ablage ist ein Modul-Singleton: vor dem Mount leeren, damit kein Titel
  // aus einem früheren Test stehen bleibt (genau der Zustand „noch nichts da“).
  const Reaktiv = await import(
    pathToFileURL(join(SRC, 'components/kronos/freigabeStufenReaktiv.mjs')).href
  )
  Reaktiv.titelStand.value = {}
  // Der Lader schreibt in den Stand GESPIEGELTEN Moduls derselben Seite (die
  // übersetzten Bauteile importieren `freigabeStufenReaktiv.mjs` über ihren
  // eigenen Pfad). Darum zählt hier der gemerkte Ladevorgang: er darf keinen
  // Namen liefern, und der Stand bleibt leer.
  const Karte = await antraegeKarte()
  const { host } = await mounten(Karte)
  await warte(60)

  // Zustand VOR dem Klick: kein Stufentitel geladen (nur der Platzhalter).
  await Vue.nextTick()
  assert.equal(text(host).includes('Stufe: —'), false,
    'ohne Titel steht gar keine Stufe an der Zeile (kein Dauer-„—“)')

  ;[...host.querySelectorAll('button')].find(b => /Annehmen/.test(b.textContent)).click()
  await warte(60)

  const toast = globalThis.__uir4bToasts.at(-1)
  assert.ok(toast, 'kein Toast nach dem Annehmen')
  assert.doesNotMatch(toast.nachricht, /an —/, 'der Platzhalter („—“) steht im Toast')
  assert.match(toast.nachricht, /geht jetzt an die nächste Stufe\./,
    'ohne Namen bleibt der Satz ohne Stufe')
  assert.equal(toast.typ, 'warning')
})
