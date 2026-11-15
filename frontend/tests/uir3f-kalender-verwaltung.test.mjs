/**
 * UI-R3f — Kalenderverwaltung: Besitzer laden FRISCH, kein Dauer-Cache
 * (Folge UI-R3e, nur frontend/).
 *
 * GEMESSEN wird am echten Baum (jsdom, Server-Attrappe). Jeder Fall nennt im
 * Kopf den Zustand am UI-R3e-Stand (`796c1f0c`), an dem er ROT ist.
 *
 *   R1  Verwaltungsseite: geteilter Stand steht auf „Alt“, der Server liefert
 *       „Neu“ — genau EIN Aufruf, „Neu“ steht im Bild, vorher kein
 *       Leerzustand.                                            (MUSS 1a)
 *   R2  Kalenderseite + Leiste: genau EIN Aufruf je Seitenbesuch, „Verwalten“
 *       folgt der NEUEN Antwort — auch true → false.            (MUSS 1b)
 *   R3  403 auf der Verwaltungsseite: der Zweig `gesperrt` wird angezeigt
 *       (nicht der Fehlersatz, nicht der Leerzustand).            (SOLL 2)
 *   R4  Löschen mit Rückfrage (Google-Import): erst die frischen Daten, DANN
 *       der Toast „gelöscht“.                                     (SOLL 3)
 *   R5  Der ungenutzte `zuruecksetzenFallsLeer` ist weg (oder benutzt). (MUSS 1)
 *
 * Lauf (cwd = frontend/, EINE Datei pro Aufruf):
 *   TMPDIR=$(mktemp -d) NODE_OPTIONS=--max-old-space-size=2048 \
 *     TZ=Europe/Berlin node --test --test-timeout=60000 tests/uir3f-kalender-verwaltung.test.mjs
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

globalThis.__uiR3fMock = async (methode, args) => {
  aufrufe.push([methode, args])
  for (const [muster, antwort] of Object.entries(ueberschreibungen)) {
    if (!new RegExp(muster).test(methode)) continue
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
const TMP = mkdtempSync(join(tmpdir(), 'uir3f-'))
const cache = new Map()
const VUE_URL = import.meta.resolve('vue')

mkdirSync(join(TMP, 'shim'), { recursive: true })
const SHIM = join(TMP, 'shim', 'useApi.mock.mjs')
writeFileSync(SHIM,
  `export * from ${JSON.stringify(new URL('../src/diakonos/composables/useApi.js', import.meta.url).href)}\n`
  + 'export const apiCall = (methode, args) => globalThis.__uiR3fMock(methode, args)\n'
  + 'export default { apiCall }\n')

/**
 * Fremde Pakete, die die Kalender-Seite zieht und die es hier nicht gibt:
 * die Kalender-Bibliothek braucht Maße und Layout. `KronosCalendar.vue` liest
 * `_EC.default?.create` und fällt ohne `create` auf „keine Bibliothek“ zurück.
 */
const ERSATZ = new Map([
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
    if (/useApi(\.js)?$/.test(spec)) return `from '${pathToFileURL(SHIM).href}'`
    if (!spec.startsWith('.')) {
      const ersatz = fremdesModul(spec)
      return ersatz ? `from '${pathToFileURL(ersatz).href}'` : voll
    }
    const ziel = resolve(dirname(abs), spec)
    const datei = /\.vue$/.test(spec) ? uebersetze(ziel) : ziel
    return `from '${pathToFileURL(datei).href}'`
  })
  // Auch Importe OHNE `from` (`import 'paket/stil.css'`) auf die Attrappe legen.
  code = code.replace(/^import\s+['"]([^'"]+)['"];?$/gm, (ganz, spec) => {
    const ersatz = fremdesModul(spec)
    return ersatz ? `import '${pathToFileURL(ersatz).href}';` : ganz
  })
  const ziel = resolve(TMP, filename.replace(/\.vue$/, '') + '.' + cache.size + '.mjs')
  writeFileSync(ziel, code)
  cache.set(abs, ziel)
  return ziel
}

/** Der geteilte Ladestand — sein Aufruf geht über DIESELBE Attrappe. */
async function stand() {
  const modul = await import('../src/diakonos/composables/useKalenderVerwaltung.js')
  modul.__setzeApiAufruf((methode, args) => globalThis.__uiR3fMock(methode, args))
  return modul
}

test.after(() => rmSync(TMP, { recursive: true, force: true }))
test.afterEach(async () => {
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
// R1 · Verwaltungsseite lädt beim Mount FRISCH (MUSS 1a)
// ══════════════════════════════════════════════════════════════════════════

test('UI-R3f/R1: geteilter Stand „Alt“, Server „Neu“ — die Verwaltungsseite holt EINMAL frisch und zeigt „Neu“', async () => {
  // BEFUND (UI-R3e-Stand): `laden()` ohne `frisch` gibt bei `antwortDa` sofort
  // den GETEILTEN Stand zurück — die Seite zeigt die alte Liste (gelöschte
  // Kalender mit aktivem Löschen-Knopf), und `get_kalender_verwaltung` wird
  // auf diesem Seitenbesuch gar nicht gefragt.
  const geteilt = await stand()
  geteilt.__leeren()
  geteilt.teilen({
    kalender: [kalender({ name: 'Alt', titel: 'Alte Liste' })],
    anlegen_gruppen: ['G-Chor'], anlegen_untergruppen: [], darf_gemeinde_kalender: false,
  })
  assert.equal(geteilt.useKalenderVerwaltung().antwortDa.value, true, 'Vorbedingung: geteilter Stand gefüllt')

  const tor = schleuse()
  ueberschreibungen = {
    'get_kalender_verwaltung$': () => tor.versprechen,
  }
  const Seite = await baustein('pages/KalenderVerwaltung.vue')
  const { host, meldungen } = await programm('<Seite />', { teile: { Seite } })
  await warte(40)
  assert.deepEqual(meldungen.filter((m) => /^err:/.test(m)), [], 'Fehler: ' + meldungen.join(' | '))

  // Genau EINE Anfrage — der Besitzer lädt, die Fläche liest mit.
  assert.equal(mit('get_kalender_verwaltung$').length, 1,
    'die Verwaltungsseite fragte ' + mit('get_kalender_verwaltung$').length + ' mal (erwartet: 1 frisch)')

  // Vor der Antwort: kein Leerzustand, keine alte Zeile im Bild.
  const vorher = host.textContent || ''
  assert.ok(!/Kein Kalender zu verwalten/.test(vorher), 'Leerzustand vor der Antwort im Bild: ' + vorher.slice(0, 200))
  assert.ok(!/Noch keine Kalender/.test(vorher), 'Leerzustand der Fläche vor der Antwort im Bild')
  assert.ok(!/Alte Liste/.test(vorher), 'die ALTE Liste steht im Bild, obwohl frisch geladen wird')

  tor.oeffnen({
    kalender: [kalender({ name: 'Neu', titel: 'Neue Liste' })],
    anlegen_gruppen: ['G-Chor'], anlegen_untergruppen: [], darf_gemeinde_kalender: false,
  })
  await warte(60)
  assert.match(host.textContent || '', /Neue Liste/, 'die frische Antwort steht nicht im Bild: ' + (host.textContent || '').slice(0, 300))
  assert.ok(!/Alte Liste/.test(host.textContent || ''), 'die alte Zeile steht weiter im Bild')
  assert.ok(host.querySelector('[data-kalender="Neu"]'), 'die Zeile „Neu“ fehlt')
  assert.equal(host.querySelector('[data-kalender="Alt"]'), null, 'die gelöschte Zeile „Alt“ steht noch da')
  // Und der geteilte Stand trägt jetzt den frischen Stand.
  assert.deepEqual(geteilt.useKalenderVerwaltung().verwaltung.value?.kalender?.map((k) => k.name), ['Neu'])
})

// ══════════════════════════════════════════════════════════════════════════
// R2 · Kalenderseite + Leiste: EIN frischer Ladevorgang je Seitenbesuch (MUSS 1b)
// ══════════════════════════════════════════════════════════════════════════

test('UI-R3f/R2: Kalenderseite lädt frisch, die Leiste liest — EIN Aufruf, „Verwalten“ folgt der neuen Antwort (true → false)', async () => {
  // BEFUND (UI-R3e-Stand): `Kalender.vue` rief `laden()` ohne `frisch`. War
  // der geteilte Stand schon da (Seitenwechsel innerhalb der SPA), ging KEINE
  // Anfrage raus — „Kalender verwalten“ blieb auf dem alten Recht stehen,
  // auch wenn es inzwischen genommen war.
  //
  // Nachgestellt wird der ECHTE Ablauf: der geteilte Stand steht auf „darf
  // verwalten“ (Seite A), dann wird die Kalenderseite besucht — sie lädt
  // frisch, die Leiste mountet dazu und liest nur.
  const geteilt = await stand()
  geteilt.__leeren()
  geteilt.teilen({
    kalender: [kalender({ name: 'Alt', titel: 'Alte Liste' })],
    anlegen_gruppen: ['G-Chor'], anlegen_untergruppen: [], darf_gemeinde_kalender: false,
  })
  assert.equal(geteilt.useKalenderVerwaltung().verwaltung.value?.kalender?.length, 1,
    'Vorbedingung: der geteilte Stand trägt das alte Recht')

  // Der Server gibt dieser Person jetzt NICHTS mehr zu verwalten (Recht
  // genommen) — „Verwalten“ muss deshalb verschwinden.
  ueberschreibungen = {
    'get_kalender_verwaltung$': { kalender: [], anlegen_gruppen: [], anlegen_untergruppen: [], darf_gemeinde_kalender: false },
    'get_current_user_context$': { roles: ['Mitglied'], user: 'bea' },
    'get_accessible_calendars$': [],
  }
  const Leiste = await baustein('components/kronos/KronosSidebar.vue')
  const leiste = await programm('<Leiste :open="false" />', { teile: { Leiste } })
  await warte(40)
  // Vorbedingung: die Leiste liest den ALTEN Stand (Eintrag da, Recht noch nicht geholt).
  assert.match(leiste.host.textContent || '', /Kalender verwalten/,
    'Vorbedingung: die Leiste zeigt den Eintrag aus dem geteilten Stand nicht')

  // Jetzt der Seitenbesuch: EIN frischer Aufruf (der Besitzer), die Leiste
  // liest den reaktiven Stand mit — das genommene Recht nimmt den Eintrag weg.
  aufrufe.length = 0
  const seiteStand = await geteilt.laden({ frisch: true })
  await warte(20)
  assert.equal(mit('get_kalender_verwaltung$').length, 1,
    'der Seitenbesuch löste ' + mit('get_kalender_verwaltung$').length + ' Anfragen aus (erwartet: 1 frisch)')
  assert.deepEqual(seiteStand?.kalender, [], 'die frische Antwort wurde nicht übernommen')
  assert.doesNotMatch(leiste.host.textContent || '', /Kalender verwalten/,
    'die Leiste zeigt „Kalender verwalten“ trotz genommenem Recht')

  // Zweiter Seitenbesuch: wieder genau EIN frischer Aufruf (kein Dauer-Cache)
  // — jetzt gibt der Server das Recht wieder.
  aufrufe.length = 0
  ueberschreibungen = {
    'get_kalender_verwaltung$': { kalender: [], anlegen_gruppen: ['G-Chor'], anlegen_untergruppen: [], darf_gemeinde_kalender: false },
  }
  await geteilt.laden({ frisch: true })
  await warte(20)
  assert.equal(mit('get_kalender_verwaltung$').length, 1,
    'zweiter Seitenbesuch: ' + mit('get_kalender_verwaltung$').length + ' Anfragen (erwartet: 1 frisch)')
  assert.match(leiste.host.textContent || '', /Kalender verwalten/,
    'nach der neuen Antwort fehlt „Kalender verwalten“ (Recht gegeben)')
})

test('UI-R3f/R2b: Kalender.vue verlangt beim Aufbau eine FRISCHE Antwort (nicht den geteilten Stand)', async () => {
  // Die Seite ist der Besitzer des Endpunkts; ihr Aufbau muss `frisch` sagen,
  // sonst gibt der geteilte Lader bei vorhandener Antwort sofort den ALTEN
  // Stand zurück und „Verwalten“ bleibt stehen (UI-R3e-Stand: `laden()`).
  const quelle = lies('pages/Kalender.vue')
  const aufruf = quelle.match(/async function kalenderVerwaltungLaden\(\)[\s\S]*?\n\}/)
  assert.ok(aufruf, '`kalenderVerwaltungLaden` fehlt in pages/Kalender.vue')
  assert.match(aufruf[0], /ladenKalenderVerwaltung\(\{\s*frisch:\s*true\s*\}\)/,
    'pages/Kalender.vue lädt beim Aufbau nicht frisch: ' + aufruf[0].replace(/\s+/g, ' ').slice(0, 300))

  // Und gemessen: derselbe Aufruf (frisch) holt bei vorhandener Antwort NEU —
  // genau eine Anfrage, der Stand ist danach der frische.
  const geteilt = await stand()
  geteilt.__leeren()
  geteilt.teilen({ kalender: [kalender({ name: 'Alt', titel: 'Alte Liste' })] })
  ueberschreibungen = {
    'get_kalender_verwaltung$': { kalender: [kalender({ name: 'Neu', titel: 'Neue Liste' })] },
  }
  const stand2 = await geteilt.laden({ frisch: true })
  assert.equal(mit('get_kalender_verwaltung$').length, 1, 'die frische Ladung löste keine Anfrage aus')
  assert.deepEqual(stand2?.kalender?.map((k) => k.name), ['Neu'], 'die frische Ladung lieferte den alten Stand')
})

// ══════════════════════════════════════════════════════════════════════════
// R3 · 403: der Zweig `gesperrt` wird angezeigt (SOLL 2)
// ══════════════════════════════════════════════════════════════════════════

test('UI-R3f/R3: 403 auf der Verwaltungsseite zeigt „Kein Kalender zu verwalten“ (nicht den Fehlersatz)', async () => {
  // BEFUND (UI-R3e-Stand): `listeHolen` reichte die Antwort erneut durch
  // `teilen(antwort)`. Bei 403 gibt `laden()` `null` zurück, `teilen(null)`
  // setzt `sperrt` wieder auf false — der Zweig `gesperrt` war damit tot und
  // die Seite zeigte den allgemeinen Fehlersatz.
  const geteilt = await stand()
  geteilt.__leeren()
  ueberschreibungen = {
    'get_kalender_verwaltung$': Object.assign(new Error('Nur Kalenderverantwortliche dürfen Kalender verwalten.'), { status: 403 }),
  }
  const Seite = await baustein('pages/KalenderVerwaltung.vue')
  const { host, meldungen } = await programm('<Seite />', { teile: { Seite } })
  await warte(60)
  assert.deepEqual(meldungen.filter((m) => /^err:/.test(m)), [], 'Fehler: ' + meldungen.join(' | '))
  assert.equal(mit('get_kalender_verwaltung$').length, 1,
    'die Verwaltungsseite fragte ' + mit('get_kalender_verwaltung$').length + ' mal (erwartet: 1)')
  const text = host.textContent || ''
  assert.match(text, /Kein Kalender zu verwalten/, 'der Zweig „gesperrt“ fehlt: ' + text.slice(0, 300))
  assert.ok(!/konnten nicht geladen werden/.test(text), 'statt der Auskunft steht der Fehlersatz da: ' + text.slice(0, 300))
  // Der geteilte Stand trägt die Lage: „gesperrt“ — vor UI-R3f setzte
  // `teilen(null)` es wieder auf false (der Zweig war damit tot).
  assert.equal(geteilt.useKalenderVerwaltung().sperrt.value, true,
    'der geteilte Stand kennt das 403 nach der Antwort der Seite nicht mehr (teilen(null) hat `sperrt` zurückgesetzt)')
  assert.equal(geteilt.useKalenderVerwaltung().fehler.value, '',
    'ein 403 ist eine Lage, kein Fehler — es steht ein Fehlertext im Stand')
})

// ══════════════════════════════════════════════════════════════════════════
// R4 · Löschen mit Rückfrage: erst die frischen Daten, dann der Toast (SOLL 3)
// ══════════════════════════════════════════════════════════════════════════

test('UI-R3f/R4: Google-Kalender löschen — der Toast „gelöscht“ kommt erst NACH den frischen Daten', async () => {
  // BEFUND (UI-R3e-Stand): im Rückfrage-Zweig (Google-Import) stand
  // `showToast(...)` VOR `await kontextNachladen()` — die Meldung meldete das
  // Löschen, während die Zeile mit aktivem Löschen-Knopf noch dastand.
  const geteilt = await stand()
  geteilt.__leeren()
  // Der Kalender hat `calender_details` (Google-Import) und Freigaben → die
  // Rückfrage ist Pflicht (`vollstaendig('kalender', k)` ist false).
  const seite = {
    kalender: [
      kalender({ name: 'Google', titel: 'Google-Import', calender_details: 'abc123', hat_freigaben: true }),
      kalender({ name: 'Chor', titel: 'Chorproben' }),
    ],
  }
  const frisch = { kalender: [kalender({ name: 'Chor', titel: 'Chorproben' })] }
  const tor = schleuse()
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
  assert.ok(host.querySelector('[data-kalender="Google"]'), 'Vorbedingung: die Zeile „Google-Import“ fehlt')

  const karte = host.querySelector('[data-kalender="Google"]')
  const loeschen = [...karte.querySelectorAll('button')].find((b) => /^Löschen$/.test(b.textContent || ''))
  assert.ok(loeschen, 'Vorbedingung: der Löschen-Knopf fehlt')
  loeschen.click()
  await warte(20)

  // Die Rückfrage bejahen.
  const { bestaetigungAntwort } = await import('../src/diakonos/composables/useBestaetigen.js')
  bestaetigungAntwort(true)
  await warte(30)
  assert.equal(mit('delete_kalender$').length, 1, 'gesendet wurde nicht gelöscht')

  // Die frischen Daten hängen noch — der Toast darf NICHT da sein.
  const toast = () => [...document.querySelectorAll('.diakonos-toast')]
    .find((t) => /Google-Import/.test(t.textContent || '') && /gelöscht/.test(t.textContent || ''))
  assert.equal(toast(), undefined,
    'der Toast meldet das Löschen, während die Liste noch den alten Stand zeigt')
  assert.ok(host.querySelector('[data-kalender="Google"]'), 'Vorbedingung: die Zeile sollte noch dastehen')

  tor.oeffnen(frisch)
  await warte(60)
  assert.equal(host.querySelector('[data-kalender="Google"]'), null, 'nach den frischen Daten steht die gelöschte Zeile noch da')
  assert.ok(toast(), 'nach den frischen Daten fehlt die Meldung zum Löschen')
})

// ══════════════════════════════════════════════════════════════════════════
// R5 · `zuruecksetzenFallsLeer` ist weg (oder benutzt) (MUSS 1)
// ══════════════════════════════════════════════════════════════════════════

test('UI-R3f/R5: der ungenutzte `zuruecksetzenFallsLeer` lebt nicht mehr', () => {
  // BEFUND (UI-R3e-Stand): die Funktion stand im geteilten Lader, wurde aber
  // von keiner Anzeige gerufen — toter Weg.
  const quelle = lies('composables/useKalenderVerwaltung.js')
  const benutzt = [...quelle.matchAll(/zuruecksetzenFallsLeer/g)].length
  if (/\bexport function zuruecksetzenFallsLeer/.test(quelle)) {
    assert.ok(benutzt > 1, '`zuruecksetzenFallsLeer` ist exportiert und nirgends benutzt')
  } else {
    assert.doesNotMatch(quelle, /zuruecksetzenFallsLeer/, '`zuruecksetzenFallsLeer` lebt noch')
  }
})
