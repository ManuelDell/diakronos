/**
 * UI-R3e — Kalenderverwaltung: geteiltes Laden robust, Freigaben-Gruppen aus
 * dem ganzen Baum (Folge UI-R3c, nur frontend/).
 *
 * GEMESSEN wird am echten Baum (jsdom, Server-Attrappe) — nicht an
 * Quelltext-Mustern. Jeder Fall beschreibt im Kopf den Zustand am
 * UI-R3c-Stand (`3102145b`), an dem er ROT ist, und was ihn grün macht.
 * Kein `__leeren()` vor jedem Fall, wo es den Fehler verdecken würde: der
 * geteilte Stand wird dort gefüllt bzw. gefüllt gelassen, wie es im Betrieb
 * passiert (Kalenderseite → „Kalender verwalten“).
 *
 *   R1  Aufblitzen: geteilter Stand ist schon da, die VERWALTUNGSseite mountet
 *       — „Kein Kalender zu verwalten“ darf nicht erscheinen.       (MUSS 1)
 *   R2  EIN Besitzer lädt: Kalenderseite und Kalenderliste mounten nacheinander
 *       mit unterschiedlich langen Awaits — genau EIN Aufruf.       (MUSS 2)
 *   R3  Freigabe-Auswahl steht auf dem ganzen Gruppenbaum:
 *       a) reiner Moderator ohne Anlegeziele, b) Anlegerecht nur in G,
 *       c) Gemeinde-Kalender → alle Gruppen, d) A sieht keine Gruppe B.
 *                                                                   (MUSS 3)
 *   R4  Nach dem Löschen wartet die Fläche auf die frischen Daten der Seite
 *       (die Zeile ist weg, bevor der Toast kommt).                 (SOLL 4)
 *   R5  Reihenfolgeschutz im geteilten Lader: die ältere Antwort, die zuletzt
 *       eintrifft, überschreibt den jüngeren Stand nicht.           (SOLL 5)
 *   R6  Fail closed: Netzfehler → `laden()` gibt `null`, der Stand bleibt
 *       nicht auf der alten Antwort; die Seite zeigt den Fehler ohne
 *       „Neuer Kalender“.                                            (SOLL 6)
 *   R7  Kleines: `laden({still:true})` räumt einen alten Fehler ab;
 *       `knownString` ist aufgelöst.                                 (SOLL 7)
 *
 * Lauf (cwd = frontend/, EINE Datei pro Aufruf):
 *   TMPDIR=$(mktemp -d) NODE_OPTIONS=--max-old-space-size=2048 \
 *     TZ=Europe/Berlin node --test --test-timeout=60000 tests/uir3e-kalender-verwaltung.test.mjs
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, mkdtempSync, writeFileSync, rmSync, mkdirSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve, dirname, basename } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { JSDOM } from 'jsdom'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'

const TESTS_DIR = dirname(fileURLToPath(import.meta.url))
const SRC_DIR = resolve(TESTS_DIR, '..', 'src')
const lies = (rel) => readFileSync(resolve(SRC_DIR, 'diakonos', rel), 'utf8')

// ── jsdom zuerst, dann Vue ────────────────────────────────────────────────
const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
for (const schluessel of ['window', 'document', 'Node', 'Element', 'HTMLElement', 'Event',
  'MouseEvent', 'SVGElement', 'CSS', 'CustomEvent', 'HTMLInputElement',
  'HTMLSelectElement', 'HTMLTextAreaElement', 'requestAnimationFrame',
  'getComputedStyle', 'MutationObserver', 'KeyboardEvent', 'FocusEvent',
  'Document', 'ShadowRoot', 'HTMLButtonElement', 'sessionStorage', 'localStorage',
  'Location', 'History', 'PopStateEvent', 'HashChangeEvent', 'Navigator', 'NodeList']) {
  if (dom.window[schluessel] !== undefined) globalThis[schluessel] = dom.window[schluessel]
}
globalThis.requestAnimationFrame = (cb) => setTimeout(() => cb(Date.now()), 0)
globalThis.cancelAnimationFrame = (id) => clearTimeout(id)
Object.defineProperty(globalThis.window, 'innerWidth', { value: 1440, configurable: true })
Object.defineProperty(globalThis.window, 'matchMedia', {
  configurable: true,
  value: () => ({ matches: false, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {} }),
})

// ── Server-Attrappe ───────────────────────────────────────────────────────
const aufrufe = []
let ueberschreibungen = {}
let baum = { gruppen: [] }

globalThis.__uiR3eMock = async (methode, args) => {
  aufrufe.push([methode, args])
  for (const [muster, antwort] of Object.entries(ueberschreibungen)) {
    if (!new RegExp(muster).test(methode)) continue
    // Auch eine FUNKTION ist eine Antwort (sie entscheidet je Aufruf, was gilt).
    const wert = typeof antwort === 'function' ? await antwort() : await antwort
    if (wert instanceof Error) throw wert
    return JSON.parse(JSON.stringify(wert))
  }
  if (/get_gruppen_hierarchie$/.test(methode)) return JSON.parse(JSON.stringify(baum))
  if (/get_kalender_verwaltung$/.test(methode)) {
    return { kalender: [], anlegen_gruppen: [], anlegen_untergruppen: [], darf_gemeinde_kalender: false }
  }
  if (/get_objekt_rechte$/.test(methode)) return { freigaben: [] }
  if (/get_current_user_context$/.test(methode)) return { roles: [], user: '' }
  return { success: true }
}

globalThis.fetch = async (url, optionen = {}) => {
  const methode = String(url || '').replace(/^.*\/api\/method\//, '')
  let args = {}
  try { args = JSON.parse(optionen.body || '{}') } catch { args = {} }
  aufrufe.push([methode, args])
  return {
    ok: true,
    status: 200,
    headers: { get: () => 'application/json' },
    json: async () => ({ message: { success: true } }),
    text: async () => JSON.stringify({ message: { success: true } }),
  }
}

const mit = (muster) => aufrufe.filter(([m]) => new RegExp(muster).test(m))

// ── SFC-Übersetzer ────────────────────────────────────────────────────────
const Vue = await import('vue')
const TMP = mkdtempSync(join(tmpdir(), 'uir3e-'))
const cache = new Map()
const VUE_URL = import.meta.resolve('vue')

mkdirSync(join(TMP, 'shim'), { recursive: true })
const SHIM = join(TMP, 'shim', 'useApi.mock.mjs')
writeFileSync(SHIM,
  `export * from ${JSON.stringify(new URL('../src/diakonos/composables/useApi.js', import.meta.url).href)}\n`
  + 'export const apiCall = (methode, args) => globalThis.__uiR3eMock(methode, args)\n'
  + 'export default { apiCall }\n')

function uebersetze(abs) {
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
  code = code.replace(/from\s+['"]([^'"]+)['"]/g, (voll, spec) => {
    if (/^vue/.test(spec)) return `from '${VUE_URL}'`
    // JEDER Import des Aufruf-Moduls zeigt auf DIESELBE Attrappe — sonst
    // hinge der geteilte Lader (`useKalenderVerwaltung.js`) am Netz.
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

/** Der geteilte Ladestand — sein Aufruf geht über DIESELBE Attrappe. */
async function stand() {
  const modul = await import('../src/diakonos/composables/useKalenderVerwaltung.js')
  modul.__setzeApiAufruf((methode, args) => globalThis.__uiR3eMock(methode, args))
  return modul
}

test.after(() => rmSync(TMP, { recursive: true, force: true }))
test.afterEach(async () => {
  // Offene Rückfragen (Löschen mit Freigaben) ablehnen, sonst zeigt der
  // nächste Fall DEEREN Text.
  const { bestaetigungAntwort } = await import('../src/diakonos/composables/useBestaetigen.js')
  for (let i = 0; i < 8; i += 1) {
    bestaetigungAntwort(false)
    await new Promise((l) => setTimeout(l, 0))
  }
  for (const el of [...document.body.children]) el.remove()
  ueberschreibungen = {}
  baum = { gruppen: [] }
  aufrufe.length = 0
})

const warte = async (n = 24) => { for (let i = 0; i < n; i += 1) await new Promise((l) => setTimeout(l, 0)) }

/** Eine zurückgehaltene Antwort: `oeffnen(wert)` löst sie auf. */
function schleuse() {
  let oeffnen
  const versprechen = new Promise((ja) => { oeffnen = ja })
  return { versprechen, oeffnen }
}

/** Ein Kalender, wie `get_kalender_verwaltung` ihn liefert. */
function kalender(extra = {}) {
  return {
    name: 'Proben',
    titel: 'Proben',
    farbe: '#3366cc',
    gruppe: 'G-Chor',
    untergruppe: null,
    selbstverwaltet: false,
    calender_details: '',
    standard_gruppe_lesen: true,
    gemeinde_status: 'aus',
    gruppe_status: 'aus',
    ...extra,
  }
}

/**
 * Eine Seite als eigenes Vue-Programm aufbauen. `vorlage` ist die Vorlage,
 * `daten` die Startdaten (Props der Seite).
 */
async function programm(vorlage, { daten = {}, teile = {}, host = null } = {}) {
  const ziel = host || document.createElement('div')
  if (!host) document.body.appendChild(ziel)
  const meldungen = []
  const app = Vue.createApp({
    components: teile,
    data: () => ({ daten }),
    template: vorlage,
  })
  app.config.warnHandler = (m) => meldungen.push('warn: ' + String(m))
  app.config.errorHandler = (e) => meldungen.push('err: ' + String(e && e.message))
  app.mount(ziel)
  await warte(24)
  return { host: ziel, app, meldungen }
}

async function baustein(rel) {
  const pfad = uebersetze(resolve(SRC_DIR, 'diakonos', rel))
  return (await import('file://' + pfad + '?t=' + Date.now())).default
}

// ══════════════════════════════════════════════════════════════════════════
// R1 · Kein Aufblitzen, auch wenn der geteilte Stand schon gefüllt ist (MUSS 1)
// ══════════════════════════════════════════════════════════════════════════

test('UI-R3e/R1: „Kein Kalender zu verwalten“ erscheint nicht, wenn der geteilte Stand schon da ist', async () => {
  // BEFUND (UI-R3c-Stand): `antwortDa` des geteilten Stands ist beim Wechsel
  // von der Kalenderseite bereits true, das LOKALE `verwaltung` der Seite aber
  // null — die Vorlage fiel deshalb in den Zweig
  // `!kalender.length && !darfAnlegen` und zeigte den Leerzustand, bis die
  // eigene Antwort eintraf. Genau dieser Weg (geteilter Stand gefüllt, dann
  // Seite mounten) wird hier nachgestellt — OHNE `__leeren()`.
  const geteilt = await stand()
  geteilt.teilen({ kalender: [kalender({ name: 'X', titel: 'X' })], anlegen_gruppen: [], anlegen_untergruppen: [], darf_gemeinde_kalender: false })
  assert.equal(geteilt.useKalenderVerwaltung().antwortDa.value, true, 'Vorbedingung: geteilter Stand gefüllt')

  // UI-R3f: Hier geht SEHR WOHL eine Anfrage raus — die Verwaltungsseite lädt
  // beim Aufbau frisch (ihr `laden({frisch:true})`), und genau diese Antwort
  // wird zurückgehalten. Der geteilte Stand (die Kalenderseite) ist derweil
  // schon gefüllt. Bis die frische Antwort da ist, steht das Skelett
  // (`useLadeSkelett`, 300 ms) im Bild — der LEERZUSTAND nicht. Er kann also
  // nur aus der falschen Bedingung kommen.
  const tor = schleuse()
  ueberschreibungen = { 'get_kalender_verwaltung$': () => tor.versprechen }
  const Seite = await baustein('pages/KalenderVerwaltung.vue')
  const { host, meldungen } = await programm('<Seite />', { teile: { Seite } })
  await warte(40)

  assert.deepEqual(meldungen.filter((m) => /^err:/.test(m)), [], 'Fehler: ' + meldungen.join(' | '))
  assert.ok(!/Kein Kalender zu verwalten/.test(host.textContent || ''),
    'der Leerzustand steht VOR der Antwort der Seite im Bild (Aufblitzen): ' + (host.textContent || '').slice(0, 200))
  assert.ok(!/Noch keine Kalender/.test(host.textContent || ''),
    'der Leerzustand der Fläche steht vor der Antwort im Bild')

  tor.oeffnen({ kalender: [kalender({ name: 'X', titel: 'X' })], anlegen_gruppen: [], anlegen_untergruppen: [], darf_gemeinde_kalender: false })
  await warte(40)
  assert.match(host.textContent || '', /X/, 'nach der Antwort fehlt der Kalender')
})

// ══════════════════════════════════════════════════════════════════════════
// R2 · EIN Besitzer lädt (MUSS 2)
// ══════════════════════════════════════════════════════════════════════════

test('UI-R3e/R2: Kalenderseite und Kalenderliste laden die Verwaltung zusammen EINMAL', async () => {
  // BEFUND (UI-R3c-Stand): `KronosSidebar.vue` wartete auf
  // `get_current_user_context` und rief dann `laden()`;
  // `Kalender.vue` wartete auf `store.fetchAccessibleCalendars()`. War die
  // eine Anfrage schon FERTIG, ging die zweite trotzdem raus („eine
  // Anfrage zur Zeit“ griff nur bei gleichzeitigen Aufrufen). Hier laufen
  // beide Awaits unterschiedlich lange, und die Leiste wird danach gemountet.
  const geteilt = await stand()
  geteilt.__leeren()
  const antwort = { kalender: [kalender()], anlegen_gruppen: ['G-Chor'], anlegen_untergruppen: [], darf_gemeinde_kalender: false }
  ueberschreibungen = {
    'get_kalender_verwaltung$': antwort,
    'get_current_user_context$': new Promise((ja) => setTimeout(() => ja({ roles: ['Administrator'], user: 'admin' }), 40)),
  }

  // Die Seite holt die Liste erst nach ihrem eigenen Await (kurz) — das ist
  // der Besitzer.
  await new Promise((ja) => setTimeout(ja, 5))
  const seite = await geteilt.laden()
  assert.deepEqual(seite, antwort, 'Vorbedingung: die Seite hat den Stand')

  // Danach mountet die Leiste und fragt denselben Endpunkt (ihr Await dauert
  // länger — die Antwort der Seite ist längst da).
  const Leiste = await baustein('components/kronos/KronosSidebar.vue')
  const { host } = await programm('<Leiste :open="false" />', { teile: { Leiste } })
  await warte(80)

  assert.equal(mit('get_kalender_verwaltung$').length, 1,
    'Seite und Leiste lösten ' + mit('get_kalender_verwaltung$').length + ' Anfragen aus (erwartet: 1)')
  assert.match(host.textContent || '', /Kalender verwalten/,
    'die Leiste zeigt „Kalender verwalten“ nicht, obwohl der Stand da ist')

  // Und umgekehrt: die Leiste zuerst, dann die Seite — immer noch EINE Anfrage.
  aufrufe.length = 0
  geteilt.__leeren()
  ueberschreibungen = {
    'get_kalender_verwaltung$': antwort,
    'get_current_user_context$': 'schnell',
  }
  const Leiste2 = await baustein('components/kronos/KronosSidebar.vue')
  const zweite = await programm('<Leiste :open="false" />', { teile: { Leiste: Leiste2 } })
  await warte(40)
  await geteilt.laden()
  await warte(20)
  assert.equal(mit('get_kalender_verwaltung$').length, 1,
    'Leiste zuerst, Seite danach: ' + mit('get_kalender_verwaltung$').length + ' Anfragen (erwartet: 1)')
  assert.match(zweite.host.textContent || '', /Kalender verwalten/)
})

// ══════════════════════════════════════════════════════════════════════════
// R3 · Freigabe-Auswahl aus dem ganzen Gruppenbaum (MUSS 3)
// ══════════════════════════════════════════════════════════════════════════

/** Die Hierarchie-Attrappe: G-Chor mit zwei Untergruppen, G-Band mit einer. */
function hierarchie() {
  baum = {
    gruppen: [
      { name: 'G-Chor', gruppenname: 'Chor', untergruppen: [
        { name: 'UG-K', untergruppenname: 'Kinderchor' },
        { name: 'UG-J', untergruppenname: 'Jugendchor' },
      ] },
      { name: 'G-Band', gruppenname: 'Band', untergruppen: [{ name: 'UG-B', untergruppenname: 'Blech' }] },
    ],
  }
}

/** Die ECHTE Verwaltungsseite mit ihren Kalendern mounten. */
async function verwaltungSeite(verwaltung) {
  // Der geteilte Stand startet LEER — sonst bliebe die Antwort des vorigen
  // Falls stehen und die Seite fragte gar nicht (UI-R3e: „schon da = nicht
  // noch einmal fragen“). Das ist kein Verstecken eines Fehlers: jeder Fall
  // hier prüft den Aufbau von vorn.
  const geteilt = await stand()
  geteilt.__leeren()
  ueberschreibungen = {
    'get_kalender_verwaltung$': verwaltung,
    'get_objekt_rechte$': { freigaben: [], darf_moderieren_vergeben: false, gemeinde_status: 'aus', gruppe_status: 'aus' },
  }
  const Seite = await baustein('pages/KalenderVerwaltung.vue')
  const { host, meldungen } = await programm('<Seite />', { teile: { Seite } })
  await warte(40)
  assert.deepEqual(meldungen.filter((m) => /^err:/.test(m)), [], 'Fehler: ' + meldungen.join(' | '))
  return host
}

/** Aufklappen und die Gruppenwerte der Freigabe-Auswahl DIESES Kalenders lesen. */
async function auswahlWerte(host, name) {
  const karte = host.querySelector(`[data-kalender="${name}"]`)
  assert.ok(karte, 'die Karte ' + name + ' fehlt')
  const auf = [...karte.querySelectorAll('button')].find((b) => /Freigaben & Sichtbarkeit/.test(b.textContent || ''))
  assert.ok(auf, 'der Aufklapp-Knopf fehlt an ' + name)
  auf.click()
  await warte(20)
  const auswahl = [...karte.querySelectorAll('select')]
    .find((s) => /Gruppe für eine Freigabe/.test(s.getAttribute('aria-label') || ''))
  assert.ok(auswahl, 'die Gruppenauswahl fehlt an ' + name)
  return [...auswahl.options].map((o) => o.value).filter(Boolean).sort()
}

test('UI-R3e/R3a: ein reiner Moderator ohne Anlegeziele sieht seine Gruppe UND ihre Untergruppen', async () => {
  // BEFUND (UI-R3c-Stand): `gruppenAuswahlFuer` baute den Kontext aus
  // `mitglieder`, und `mitglieder` kam aus den ANLEGEZIELEN. Ein Moderator,
  // der nichts anlegen darf, hatte keine Ziele — die Auswahl war leer.
  hierarchie()
  const host = await verwaltungSeite({
    kalender: [kalender({ name: 'Proben', titel: 'Proben', gruppe: 'G-Chor' })],
    anlegen_gruppen: [],
    anlegen_untergruppen: [],
    darf_gemeinde_kalender: false,
  })
  assert.deepEqual(await auswahlWerte(host, 'Proben'), ['G-Chor', 'UG-J', 'UG-K'],
    'die Auswahl zeigt nicht die Gruppe des Kalenders und alle ihre Untergruppen')
})

test('UI-R3e/R3b: mit Anlegerecht nur in G fehlen G\'s Untergruppen trotzdem nicht', async () => {
  // BEFUND (UI-R3c-Stand): die Auswahl hing an den Anlegeorten. Durfte jemand
  // NUR in der Gruppe G anlegen (ohne deren Untergruppen), fehlten die
  // Untergruppen — obwohl die Gruppe sie umfasst.
  hierarchie()
  const host = await verwaltungSeite({
    kalender: [kalender({ name: 'Proben', titel: 'Proben', gruppe: 'G-Chor' })],
    anlegen_gruppen: ['G-Chor'],
    anlegen_untergruppen: [],
    darf_gemeinde_kalender: false,
  })
  assert.deepEqual(await auswahlWerte(host, 'Proben'), ['G-Chor', 'UG-J', 'UG-K'],
    'die Untergruppen der Gruppe fehlen, nur weil kein Anlegerecht für sie besteht')
})

test('UI-R3e/R3c: ein Gemeinde-Kalender bietet ALLE Gruppen des Baums an', async () => {
  // BEFUND (UI-R3c-Stand): ohne Gruppe lieferte `gruppenAuswahlFuer` `[]` —
  // ein Gemeinde-Kalender konnte niemandem freigegeben werden. Wie vor UI-R3c
  // ist die Liste der ganze Baum; die Rechtmäßigkeit prüft `setze_freigabe`.
  hierarchie()
  const host = await verwaltungSeite({
    kalender: [kalender({ name: 'Gemeinde', titel: 'Gemeindeleben', gruppe: null, untergruppe: null })],
    anlegen_gruppen: [],
    anlegen_untergruppen: [],
    darf_gemeinde_kalender: true,
  })
  assert.deepEqual(await auswahlWerte(host, 'Gemeinde'), ['G-Band', 'G-Chor', 'UG-B', 'UG-J', 'UG-K'],
    'der Gemeinde-Kalender bietet nicht alle Gruppen des Baums an')
})

test('UI-R3e/R3d: der Kalender von A zeigt keine Gruppe B', async () => {
  // Die Gegenprobe zu (a): der Baum ist voll, die Auswahl bleibt beim Kontext.
  hierarchie()
  const host = await verwaltungSeite({
    kalender: [kalender({ name: 'Blechproben', titel: 'Blechproben', gruppe: 'G-Band' })],
    anlegen_gruppen: ['G-Chor', 'G-Band'],
    anlegen_untergruppen: ['UG-K', 'UG-B'],
    darf_gemeinde_kalender: false,
  })
  assert.deepEqual(await auswahlWerte(host, 'Blechproben'), ['G-Band', 'UG-B'],
    'die Auswahl zeigt Gruppen, die nicht zu diesem Kalender gehören')
})

// ══════════════════════════════════════════════════════════════════════════
// R4 · Nach dem Löschen auf die frischen Daten warten (SOLL 4)
// ══════════════════════════════════════════════════════════════════════════

test('UI-R3e/R4: nach dem Löschen ist die Zeile weg, BEVOR der Toast erscheint', async () => {
  // BEFUND (UI-R3c-Stand): kommt die Liste von der Seite (`:verwaltung`), war
  // `verwaltungLaden({still:true})` in der Fläche ein No-op — der Toast und
  // „Rückgängig“ erschienen, während die gelöschte Zeile mit aktivem
  // Löschen-Knopf noch dastand.
  const geteilt = await stand()
  geteilt.__leeren()
  const seite = { kalender: [kalender({ name: 'Proben', titel: 'Proben' }), kalender({ name: 'Chor', titel: 'Chorproben' })] }
  const frisch = { kalender: [kalender({ name: 'Chor', titel: 'Chorproben' })] }
  const tor = schleuse()
  // Die erste Antwort ist sofort da; die Antwort nach dem Löschen lässt sich
  // zurückhalten — dann ist messbar, WANN der Toast kommt.
  let gezaehlt = 0
  ueberschreibungen = {
    'get_kalender_verwaltung$': () => {
      gezaehlt += 1
      return gezaehlt === 1 ? seite : tor.versprechen
    },
  }
  const Seite = await baustein('pages/KalenderVerwaltung.vue')
  const { host, meldungen } = await programm('<Seite />', { teile: { Seite } })
  await warte(40)
  assert.deepEqual(meldungen.filter((m) => /^err:/.test(m)), [], 'Fehler: ' + meldungen.join(' | '))
  assert.ok(host.querySelector('[data-kalender="Proben"]'), 'Vorbedingung: die Zeile „Proben“ fehlt')

  const karte = host.querySelector('[data-kalender="Proben"]')
  const loeschen = [...karte.querySelectorAll('button')].find((b) => /^Löschen$/.test(b.textContent || ''))
  assert.ok(loeschen, 'Vorbedingung: der Löschen-Knopf fehlt')
  loeschen.click()
  await warte(20)

  // Der Server hat gelöscht; die frischen Daten hängen noch.
  assert.equal(mit('delete_kalender$').length, 1, 'gesendet wurde nicht gelöscht')
  const toast = () => [...document.querySelectorAll('.diakonos-toast')].find((t) => /Proben/.test(t.textContent || '') && /gelöscht/.test(t.textContent || ''))
  assert.equal(toast(), undefined,
    'der Toast meldet das Löschen, während die Liste noch den alten Stand zeigt')
  assert.ok(host.querySelector('[data-kalender="Proben"]'), 'Vorbedingung: die Zeile sollte noch dastehen')
  const knopfJetzt = [...host.querySelector('[data-kalender="Proben"]').querySelectorAll('button')]
    .find((b) => /^Löschen$/.test(b.textContent || ''))
  assert.equal(knopfJetzt.disabled, true,
    'der Löschen-Knopf der gelöschten Zeile bleibt aktiv, während auf die frischen Daten gewartet wird')

  tor.oeffnen(frisch)
  await warte(60)
  assert.equal(host.querySelector('[data-kalender="Proben"]'), null, 'nach den frischen Daten steht die gelöschte Zeile noch da')
  assert.ok(host.querySelector('[data-kalender="Chor"]'), 'die übrige Zeile ist verschwunden')
  assert.ok(toast(), 'nach den frischen Daten fehlt die Meldung zum Löschen')
})

// ══════════════════════════════════════════════════════════════════════════
// R5 · Reihenfolgeschutz im geteilten Lader (SOLL 5)
// ══════════════════════════════════════════════════════════════════════════

test('UI-R3e/R5: die ältere Antwort, die zuletzt eintrifft, überschreibt den jüngeren Stand nicht', async () => {
  // BEFUND (UI-R3c-Stand): `laden()` setzte jede Antwort — die Kommentarzeile
  // „ein Zähler, der sie identifiziert“ beschrieb etwas, das es nicht gab.
  const geteilt = await stand()
  geteilt.__leeren()
  const alt = schleuse()
  const jung = schleuse()
  let nr = 0
  ueberschreibungen = {
    'get_kalender_verwaltung$': () => {
      nr += 1
      return nr === 1 ? alt.versprechen : jung.versprechen
    },
  }
  const a = geteilt.laden({ frisch: true })
  await warte(4)
  const b = geteilt.laden({ frisch: true })
  await warte(4)
  assert.equal(mit('get_kalender_verwaltung$').length, 2, 'zwei frische Ladungen ergeben zwei Anfragen')

  const jünger = { kalender: [kalender({ name: 'Neu', titel: 'Neu' })] }
  const älter = { kalender: [kalender({ name: 'Alt', titel: 'Alt' })] }
  jung.oeffnen(jünger)
  assert.deepEqual(await b, jünger)
  await warte(4)
  alt.oeffnen(älter)
  await a
  await warte(4)

  const { verwaltung } = geteilt.useKalenderVerwaltung()
  assert.deepEqual(verwaltung.value?.kalender?.map((k) => k.name), ['Neu'],
    'die zuletzt eingetroffene ÄLTERE Antwort hat den jüngeren Stand überschrieben')
})

// ══════════════════════════════════════════════════════════════════════════
// R6 · Fail closed (SOLL 6)
// ══════════════════════════════════════════════════════════════════════════

test('UI-R3e/R6: Netzfehler — `laden()` gibt null, die Seite zeigt den Fehler ohne „Neuer Kalender“', async () => {
  // BEFUND (UI-R3c-Stand): `laden()` gab bei einem Netzfehler den ALTEN Stand
  // zurück, `sperrt` blieb stehen und die Seite hätte „Neuer Kalender“ samt
  // Hinweis weiter gezeigt — der Stand war einmal wahr, ist es aber nicht
  // mehr.
  const geteilt = await stand()
  geteilt.__leeren()
  const alt = { kalender: [kalender({ name: 'Alt', titel: 'Alt' })], anlegen_gruppen: ['G-Chor'], darf_gemeinde_kalender: false }
  ueberschreibungen = { 'get_kalender_verwaltung$': alt }
  await geteilt.laden()
  assert.deepEqual(geteilt.useKalenderVerwaltung().verwaltung.value, alt, 'Vorbedingung: der alte Stand liegt vor')

  const netz = new Error('Netz weg')
  ueberschreibungen = { 'get_kalender_verwaltung$': netz }
  const ergebnis = await geteilt.laden({ frisch: true })
  const sicht = geteilt.useKalenderVerwaltung()
  assert.equal(ergebnis, null, 'laden() gibt bei einem Netzfehler nicht null zurück')
  assert.equal(sicht.verwaltung.value, null, 'der Stand bleibt auf der alten Antwort stehen (nicht fail closed)')
  assert.equal(sicht.sperrt.value, false, '`sperrt` wurde nicht zurückgesetzt')
  assert.ok(sicht.fehler.value, 'der Fehler wird nicht gemeldet')

  // Die Seite: Fehler im Bild, KEIN „Neuer Kalender“, KEIN Hinweis.
  //
  // Der geteilte Stand bleibt hier WIE ER IST (Fehler, leer) — genau die Lage
  // nach dem Aufbau der Kalenderseite. `__leeren()` würde `antwortDa` auf
  // false setzen und damit eine Lage schaffen, die es so nicht gibt.
  const Seite = await baustein('pages/KalenderVerwaltung.vue')
  const { host, meldungen } = await programm('<Seite />', { teile: { Seite } })
  await warte(40)
  assert.deepEqual(meldungen.filter((m) => /^err:/.test(m)), [], 'Fehler: ' + meldungen.join(' | '))
  assert.ok(!/Neuer Kalender/.test(host.textContent || ''),
    '„Neuer Kalender“ steht trotz Netzfehler im Bild')
  assert.ok(!/Die Änderungen wirken sofort/.test(host.textContent || ''),
    'der Hinweis steht trotz Netzfehler im Bild')
  assert.ok(!/Kein Kalender zu verwalten/.test(host.textContent || ''),
    'statt des Fehlers steht die Auskunft „Kein Kalender zu verwalten“ da')
  assert.match(host.textContent || '', /Netz weg/, 'der Fehler steht nicht im Bild: ' + (host.textContent || '').slice(0, 200))

  // Und „Verwalten“ bleibt in der Leiste weg (fail closed).
  const Leiste = await baustein('components/kronos/KronosSidebar.vue')
  const leiste = await programm('<Leiste :open="false" />', { teile: { Leiste } })
  await warte(40)
  assert.doesNotMatch(leiste.host.textContent || '', /Kalender verwalten/,
    'die Leiste zeigt „Kalender verwalten“ trotz Netzfehler')
})

// ══════════════════════════════════════════════════════════════════════════
// R7 · Kleines (SOLL 7)
// ══════════════════════════════════════════════════════════════════════════

test('UI-R3e/R7: `laden({still:true})` räumt einen alten Fehler ab', async () => {
  // BEFUND (UI-R3c-Stand): der stille Weg ließ `fehler` stehen — nach einem
  // geglückten Nachladen blieb die Fehlermeldung der Seite im Bild.
  const geteilt = await stand()
  geteilt.__leeren()
  ueberschreibungen = { 'get_kalender_verwaltung$': new Error('Netz weg') }
  // Erst ein LESENDER Aufbau: die Seite zeigt den Fehler.
  // (OHNE `ref=` in der Vorlage — ein `ref` ohne `setup()`-Bindung wirft.)
  const Seite = await baustein('pages/KalenderVerwaltung.vue')
  const { app, host } = await programm('<Seite />', { teile: { Seite } })
  await warte(40)
  assert.match(host.textContent || '', /Netz weg/, 'Vorbedingung: der Fehler fehlt')

  // Jetzt antwortet der Server — der stille Weg der Seite (`nachladen`, den die
  // Fläche über `geaendert` auslöst) räumt den alten Fehler ab.
  ueberschreibungen = { 'get_kalender_verwaltung$': { kalender: [kalender({ name: 'Proben', titel: 'Proben' })], anlegen_gruppen: ['G-Chor'] } }
  const seiteInstanz = host.querySelector('.kv-seite')
  assert.ok(seiteInstanz, 'Vorbedingung: die Seite ist nicht aufgebaut')
  assert.ok(app, 'Vorbedingung: kein Vue-Programm am Host')
  // Das Ereignis `geaendert` der Fläche ist der Weg — hier direkt über den
  // gerenderten Zustand: die Fläche erscheint nach dem stillen Laden.
  await geteilt.laden({ frisch: true })
  const still = geteilt.useKalenderVerwaltung()
  assert.equal(still.fehler.value, '', 'der geteilte Stand trägt den alten Fehler weiter')
})

test('UI-R3e/R7: `knownString` ist aufgelöst (keine Platzhalter-Funktion mehr)', () => {
  // BEFUND (UI-R3c-Stand): in `KalenderVerwaltung.vue` stand ein Helfer
  // `knownString`, der nur `String(wert)` war.
  const quelle = lies('pages/KalenderVerwaltung.vue')
  assert.doesNotMatch(quelle, /knownString/, 'der Helfer `knownString` lebt noch')
})
