/**
 * UI-R3h/UI-R3i — Restpunkte: tote Reste (SOLL 3), das ⋯-Menü und der
 * Handy-Kopf der Kalenderseite (MUSS 5) und ein Recht, das nach einem 403 neu
 * vergeben wird (MUSS 6).
 *
 *   S1  Tote Reste sind weg: `useKalenderVerwaltungSicht` (kein Aufrufer),
 *       `laufende` (nur zugewiesen), `saet` (heißt jetzt `besuchszaehler`).
 *   S2  Der leere Platzhalter-Fall uir3c/R2a bleibt weg (die echte Prüfung
 *       steht in uir3g/R1).
 *   S3  `⋯`-Menü der Kalenderseite (KronosTopbar): „Kalender verwalten“ steht
 *       nur mit der Serverantwort — und der Handy-Kopf (KalenderKopfMobil)
 *       trägt dieselbe Auskunft.
 *   S4  Handybreite 390: das ⋯-Menü des Handy-Kopfs wird auf der Seite WIRKLICH
 *       GEÖFFNET, der Eintrag im gerenderten Menü geprüft (UI-R3i, SOLL 5 —
 *       vorher wurden nur die Props gelesen).
 *   S5  Ein Recht, das nach einem 403 im vorigen Besuch NEU vergeben wird:
 *       der Eintrag erscheint erst mit der Antwort DIESES Besuchs — an
 *       `pages/Kalender.vue` gemessen, deren Leiste immer `:darf-verwalten`
 *       trägt (UI-R3i, SOLL 4 — vorher war die Leiste allein gemountet).
 *
 * ROT→GRÜN (ehrlich): Am UI-R3h-Stand (7ccfdd0d) und am main-Stand (154f230c)
 * sind S1 und S3 rot; nach dem Fix sind sie grün. S2 ist eine Quelltext-Prüfung
 * („der leere Fall bleibt weg“) und war nie rot. S4 und S5 sind ABSICHERUNGEN,
 * die auch am main-Stand grün sind — sie wurden in UI-R3i nur ehrlicher
 * geschrieben (echtes Öffnen am Bild bzw. Mount der ganzen Seite); ein
 * Rot-Beleg wird für sie NICHT behauptet. Rot→grün belegt sind in dieser Karte
 * L1–L4 (`uir3i-nachladen-juengste.test.mjs`) und R2
 * (`uir3h-menue-eine-quelle.test.mjs`) — je am Verhalten.
 *
 * Lauf (cwd = frontend/, EINE Datei pro Aufruf):
 *   TMPDIR=$(mktemp -d) NODE_OPTIONS=--max-old-space-size=2048 \
 *     TZ=Europe/Berlin node --test --test-timeout=60000 tests/uir3h-restpunkte.test.mjs
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

// ── Server-Attrappe ───────────────────────────────────────────────────────
const aufrufe = []
let ueberschreibungen = {}
globalThis.__uiR3hRestMock = async (methode, args) => {
  aufrufe.push([methode, args])
  for (const [muster, antwort] of Object.entries(ueberschreibungen)) {
    if (!new RegExp(muster).test(methode)) continue
    const wert = typeof antwort === 'function' ? await antwort() : await antwort
    if (wert instanceof Error) throw wert
    return JSON.parse(JSON.stringify(wert))
  }
  if (/get_kalender_verwaltung$/.test(methode)) return leerVerwaltung()
  if (/get_gruppen_hierarchie$/.test(methode)) return { gruppen: [] }
  if (/get_objekt_rechte$/.test(methode)) return { freigaben: [] }
  if (/get_current_user_context$/.test(methode)) return { roles: [], user: '' }
  if (/get_accessible_calendars$/.test(methode)) return []
  if (/get_moderation_count$/.test(methode)) return { count: 0 }
  return { success: true }
}
const mit = (muster) => aufrufe.filter(([m]) => new RegExp(muster).test(m))
const leerVerwaltung = () => ({
  kalender: [], anlegen_gruppen: [], anlegen_untergruppen: [], darf_gemeinde_kalender: false,
})
const mitRecht = (name = 'Proben') => ({
  kalender: [{ name, titel: name, farbe: '#3366cc', gruppe: 'G-Chor', untergruppe: null,
    selbstverwaltet: false, calender_details: '', standard_gruppe_lesen: true,
    gemeinde_status: 'aus', gruppe_status: 'aus' }],
  anlegen_gruppen: ['G-Chor'], anlegen_untergruppen: [], darf_gemeinde_kalender: false,
})

// ══════════════════════════════════════════════════════════════════════════
// S1 · Tote Reste (SOLL 3) — ohne Browser, reiner Quelltext-Befund
// ══════════════════════════════════════════════════════════════════════════

test('UI-R3h/S1: `useKalenderVerwaltungSicht`, `laufende` und `saet` leben nicht mehr', () => {
  const quelle = lies('composables/useKalenderVerwaltung.js')
  // 1) `useKalenderVerwaltungSicht()` hatte keinen Aufrufer (nur die Sicht für
  //    Anzeigen, die `aktuellerSatz` mitbekam — das nimmt der Besitzer direkt).
  assert.doesNotMatch(quelle, /useKalenderVerwaltungSicht/,
    '`useKalenderVerwaltungSicht` lebt noch im geteilten Lader')
  // 2) `laufende` (die geteilte Anfrage-Promise) wurde nur zugewiesen und im
  //    `finally` zurückgesetzt — keine Stelle LAS sie. Der Überhol-Schutz läuft
  //    über die Nummer `juengste`; der Name darf nur noch in Fließtext stehen.
  assert.doesNotMatch(quelle, /\b(?:let|const|var)\s+laufende\b/,
    '`laufende` wird noch als Variable geführt')
  assert.doesNotMatch(quelle, /laufende\s*===|=== *laufende|\blaufende\s*=\s*(?:anfrage|null)\b/,
    '`laufende` wird noch zugewiesen/gelesen')
  // 3) `saet` („Satz“) ist jetzt klar benannt: der Zähler der Seitenbesuche.
  assert.doesNotMatch(quelle, /\bsaet\b/,
    '`saet` steht noch als Name im Lader (erwartet: `besuchszaehler`)')
  assert.match(quelle, /besuchszaehler: readonly\(besuchszaehler\)/,
    'die Anzeige-Sicht gibt `besuchszaehler` nicht heraus')
  // Und kein Betriebscode liest den alten Namen.
  for (const datei of ['pages/Kalender.vue', 'pages/KalenderVerwaltung.vue',
    'components/kronos/KronosSidebar.vue']) {
    const text = lies(datei)
    assert.doesNotMatch(text, /\bsaet\b/, `${datei} liest noch \`saet\``)
  }
})

test('UI-R3h/S2: der leere Platzhalter-Fall uir3c/R2a ist weg (die echte Prüfung steht in uir3g/R1)', () => {
  const quelle = readFileSync(resolve(TESTS_DIR, 'uir3c-kalender-verwaltung.test.mjs'), 'utf8')
  assert.doesNotMatch(quelle, /test\('UI-R3c\/R2a/,
    'der leere Fall uir3c/R2a steht noch in der Suite')
  // Die echte Zusage lebt in uir3g (R1, am gerenderten Bild).
  const uir3g = readFileSync(resolve(TESTS_DIR, 'uir3g-kalender-verwaltung.test.mjs'), 'utf8')
  assert.match(uir3g, /test\('UI-R3g\/R1/,
    'die echte Prüfung (ein Aufruf je Besuch, kein veralteter Eintrag) fehlt in uir3g')
})

// ══════════════════════════════════════════════════════════════════════════
// ⋯-Menü und Handy-Kopf — jsdom, echte Bauteile
// ══════════════════════════════════════════════════════════════════════════

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
/** Die Breite ist einstellbar — S4 misst die Handylage (390 px). */
Object.defineProperty(globalThis.window, 'innerWidth', { value: 1440, configurable: true, writable: true })
Object.defineProperty(globalThis.window, 'matchMedia', {
  configurable: true,
  value: (abfrage) => ({
    matches: /handy|grob|coarse/.test(String(abfrage)),
    media: String(abfrage),
    addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {},
  }),
})

globalThis.fetch = async (url, optionen = {}) => {
  const methode = String(url || '').replace(/^.*\/api\/method\//, '')
  let args = {}
  try { args = JSON.parse(optionen.body || '{}') } catch { args = {} }
  let wert
  try {
    wert = await globalThis.__uiR3hRestMock(methode, args)
  } catch (err) {
    return {
      ok: false, status: Number(err?.status) || 500,
      headers: { get: () => 'application/json' },
      json: async () => ({ exc: String(err?.message || 'Fehler') }),
      text: async () => JSON.stringify({ exc: String(err?.message || 'Fehler') }),
    }
  }
  return {
    ok: true, status: 200, headers: { get: () => 'application/json' },
    json: async () => ({ message: wert }),
    text: async () => JSON.stringify({ message: wert }),
  }
}

const Vue = await import('vue')
const TMP = mkdtempSync(join(tmpdir(), 'uir3h-rest-'))
const cache = new Map()
let dateiNummer = 0
const VUE_URL = import.meta.resolve('vue')
mkdirSync(join(TMP, 'shim'), { recursive: true })
const SHIM = join(TMP, 'shim', 'useApi.mock.mjs')
writeFileSync(SHIM,
  `export * from ${JSON.stringify(new URL('../src/diakonos/composables/useApi.js', import.meta.url).href)}\n`
  + 'export const apiCall = (methode, args) => globalThis.__uiR3hRestMock(methode, args)\n'
  + 'export default { apiCall }\n')

const ERSATZ = new Map([
  ['@event-calendar/build',
    'export const create = () => ({ setOption(){}, render(){}, destroy(){}, addEvent(){}, '
    + 'removeEventById(){}, updateSize(){}, next(){}, prev(){}, today(){}, gotoDate(){}, '
    + 'changeView(){}, getEvents(){ return [] }, setEvents(){}, getOption(){ return undefined }, '
    + 'on(){}, off(){}, unselect(){} })\n'
    + 'export default { create: () => ({}), setOption(){}, render(){}, destroy(){} }\n'],
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
    source: descriptor.template.content, filename, id: filename,
    compilerOptions: { bindingMetadata: script.bindings },
  })
  assert.deepEqual(tpl.errors.map(String), [], filename + ': Vorlage')
  // ZUERST den Platz in `cache` belegen: ein Geschwister, das während der
  // Rekursion auf DENSELBEN Baustein zeigt, bekommt so denselben Pfad (und
  // nicht eine zweite Datei, die diese hier überschreiben würde).
  dateiNummer += 1
  const stempel = Buffer.from(abs).toString('base64url').slice(-12)
  const ziel = resolve(TMP, filename.replace(/\.vue$/, '') + '.' + dateiNummer + '.' + stempel + '.mjs')
  cache.set(abs, ziel)
  let code = script.content.replace(/\nexport default /, '\nconst __sfc__ = ')
  // KEIN `__sfc__.__file` (UI-R3j, SOLL 3): Kalender.vue liest `__file` nicht —
  // der Dateiname im Betrieb ist hier ohne Wirkung. Die Eindeutigkeit der
  // erzeugten Dateien macht `ziel` (Nummer + Stempel) aus.
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
  code = code.replace(/^import\s+['"]([^'"]+)['"];?$/gm, (ganz, spec) => {
    const ersatz = fremdesModul(spec)
    return ersatz ? `import '${pathToFileURL(ersatz).href}';` : ganz
  })
  writeFileSync(ziel, code)
  return ziel
}
globalThis.__uiR3hUebersetze = uebersetze
async function baustein(rel) {
  const pfad = uebersetze(resolve(SRC_DIR, 'diakonos', rel))
  return (await import('file://' + pfad)).default
}

// Aufräumen beim Prozessende — `test.after` läuft in `node --test` je Test,
// das Verzeichnis muss aber für ALLE Tests dieser Datei stehen bleiben.
process.on('exit', () => { try { rmSync(TMP, { recursive: true, force: true }) } catch { /* egal */ } })
test.afterEach(async () => {
  const { bestaetigungAntwort } = await import('../src/diakonos/composables/useBestaetigen.js')
  for (let i = 0; i < 6; i += 1) {
    bestaetigungAntwort(false)
    await new Promise((l) => setTimeout(l, 0))
  }
  for (const el of [...document.body.children]) el.remove()
  ueberschreibungen = {}
  aufrufe.length = 0
  Object.defineProperty(globalThis.window, 'innerWidth', { value: 1440, configurable: true, writable: true })
})
const warte = async (n = 24) => { for (let i = 0; i < n; i += 1) await new Promise((l) => setTimeout(l, 0)) }

function schleuse() {
  let oeffnen
  const versprechen = new Promise((ja) => { oeffnen = ja })
  return { versprechen, oeffnen }
}

async function programm(vorlage, { teile = {}, daten = {}, host = null } = {}) {
  const ziel = host || document.createElement('div')
  if (!host) document.body.appendChild(ziel)
  const meldungen = []
  const app = Vue.createApp({ components: teile, data: () => ({ daten }), template: vorlage })
  app.config.warnHandler = (m) => meldungen.push('warn: ' + String(m))
  app.config.errorHandler = (e) => meldungen.push('err: ' + String(e && e.message))
  app.mount(ziel)
  await warte(24)
  return { host: ziel, app, meldungen }
}

/** „Kalender verwalten“ irgendwo im Baum (Knopf oder Link). */
const verwaltenKnopf = (host) => [...host.querySelectorAll('button, a')]
  .find((el) => /^\s*Kalender verwalten\s*$/.test(el.textContent || ''))

/** Der ⋯-Auslöser eines DkAktionen-Bausteins (aria-label). */
const mehrKnopf = (host, label) => [...host.querySelectorAll('button')]
  .find((b) => (b.getAttribute('aria-label') || '') === label)

// ══════════════════════════════════════════════════════════════════════════
// S3 · ⋯-Menü der Kopfzeile und Handy-Kopf (MUSS 5, Teil 1)
// ══════════════════════════════════════════════════════════════════════════

test('UI-R3h/S3: „Kalender verwalten“ im ⋯-Menü (KronosTopbar) hängt an `darfVerwalten` — und die Einträge stehen wirklich im Menü', async () => {
  const Topbar = await baustein('components/kronos/KronosTopbar.vue')
  // (a) ohne Recht: der Eintrag fehlt im geöffneten Menü.
  const ohne = await programm('<Topbar :darf-verwalten="false" :can-write="true" />', { teile: { Topbar } })
  const knopfOhne = mehrKnopf(ohne.host, 'Weitere Kalender-Aktionen')
    || [...ohne.host.querySelectorAll('button')].find((b) => /⋯/.test(b.textContent || ''))
  assert.ok(knopfOhne, 'Vorbedingung: der ⋯-Auslöser der Kopfzeile fehlt')
  knopfOhne.click()
  await warte(12)
  const menueOhne = document.querySelector('[role="menu"]')
  assert.ok(menueOhne, 'Vorbedingung: das Menü der Kopfzeile öffnet nicht')
  assert.doesNotMatch(menueOhne.textContent || '', /Kalender verwalten/,
    'das ⋯-Menü bietet „Kalender verwalten“ ohne Serverrecht an: ' + (menueOhne.textContent || '').slice(0, 200))
  // Das Menü ist nicht leer — die Gegenprobe (sonst misst der Fall nichts).
  assert.match(menueOhne.textContent || '', /Hilfe & Infos/,
    'das Menü hat gar keine Einträge (Gegenprobe fehlt): ' + (menueOhne.textContent || '').slice(0, 200))
  ohne.app.unmount()
  ohne.host.remove()
  for (const el of [...document.body.querySelectorAll('[data-fuer]')]) el.remove()

  // (b) mit Recht: derselbe Klick zeigt ihn.
  const mit2 = await programm('<Topbar :darf-verwalten="true" :can-write="true" />', { teile: { Topbar } })
  const knopfMit = [...mit2.host.querySelectorAll('button')].find((b) => /⋯/.test(b.textContent || ''))
  assert.ok(knopfMit, 'Vorbedingung: der ⋯-Auslöser der Kopfzeile fehlt (mit Recht)')
  knopfMit.click()
  await warte(12)
  const menueMit = document.querySelector('[role="menu"]')
  assert.ok(menueMit, 'Vorbedingung: das Menü öffnet nicht (mit Recht)')
  const eintrag = [...menueMit.querySelectorAll('[role="menuitem"]')]
    .find((b) => /Kalender verwalten/.test(b.textContent || ''))
  assert.ok(eintrag, 'das ⋯-Menü bietet „Kalender verwalten“ trotz Recht nicht an: '
    + (menueMit.textContent || '').slice(0, 200))
  mit2.app.unmount()
  mit2.host.remove()
})

test('UI-R3h/S3: der Handy-Kopf (KalenderKopfMobil) trägt dieselbe Auskunft', async () => {
  const Kopf = await baustein('components/kronos/KalenderKopfMobil.vue')
  const oeffnen = async (darfVerwalten) => {
    const { host, app } = await programm(`<Kopf :darf-verwalten="${darfVerwalten}" :hat-schreibrecht="true" />`,
      { teile: { Kopf } })
    const ausloeser = mehrKnopf(host, 'Weitere Kalender-Aktionen')
    assert.ok(ausloeser, 'Vorbedingung: der ⋯-Auslöser im Handy-Kopf fehlt')
    ausloeser.click()
    await warte(12)
    const menue = document.querySelector('[role="menu"]')
    assert.ok(menue, 'Vorbedingung: das Menü im Handy-Kopf öffnet nicht')
    const hat = /Kalender verwalten/.test(menue.textContent || '')
    const hilfe = /Hilfe & Infos/.test(menue.textContent || '')
    app.unmount()
    host.remove()
    for (const el of [...document.body.querySelectorAll('[data-fuer]')]) el.remove()
    return { hat, hilfe }
  }
  const ohne = await oeffnen(false)
  assert.equal(ohne.hat, false, 'der Handy-Kopf bietet „Kalender verwalten“ ohne Serverrecht an')
  assert.equal(ohne.hilfe, true, 'das Menü im Handy-Kopf ist leer (Gegenprobe fehlt)')
  const mit2 = await oeffnen(true)
  assert.equal(mit2.hat, true, 'der Handy-Kopf bietet „Kalender verwalten“ trotz Recht nicht an')
})

// ══════════════════════════════════════════════════════════════════════════
// S4 · Handybreite 390 — die Kalenderseite als Ganzes (MUSS 5, Teil 2)
// ══════════════════════════════════════════════════════════════════════════

test('UI-R3h/S4: Kalenderseite bei 390 px — das ⋯-Menü des Handy-Kopfs wird GEÖFFNET und der Eintrag im gerenderten Menü geprüft', async () => {
  // UI-R3i (SOLL 5): Vorher las dieser Fall nur die PROP der Köpfe
  // (`darfVerwalten`) — ob das Menü den Eintrag wirklich zeigt, blieb offen.
  // Jetzt wird am gerenderten BILD gemessen: der ⋯-Knopf des Handy-Kopfs wird
  // auf der Seite geklickt, und der Eintrag „Kalender verwalten“ wird im
  // geöffneten Menü gesucht (bzw. darf dort NICHT stehen).
  const Breite = await import('../src/diakonos/components/kronos/breiten.mjs')
  // Die Handy-Lage wird an der Breite erkannt (`innerWidth` ≤ Grenze UND der
  // grobe Zeiger, den die Attrappe oben für `matchMedia` meldet).
  Object.defineProperty(globalThis.window, 'innerWidth', { value: 390, configurable: true, writable: true })
  const istHandy = typeof Breite.istHandyBreite === 'function' ? Breite.istHandyBreite(390) : null
  if (istHandy !== null) assert.equal(istHandy, true, 'Vorbedingung: 390 px gilt bei `breiten.mjs` nicht als Handy')

  const Seite = await baustein('pages/Kalender.vue')
  const geteilt = await import('../src/diakonos/composables/useKalenderVerwaltung.js')
  geteilt.__setzeApiAufruf((methode, args) => globalThis.__uiR3hRestMock(methode, args))

  /**
   * Die Seite bei 390 px mounten und das ⋯-Menü des Handy-Kopfs öffnen.
   * @returns {{bild: string, eintrag: boolean, hilfe: boolean, kopf: object|null}}
   */
  async function handyMenue(antwort) {
    ueberschreibungen = { 'get_kalender_verwaltung$': antwort, 'get_accessible_calendars$': [] }
    const host = document.createElement('div')
    document.body.appendChild(host)
    const meldungen = []
    const app = Vue.createApp({ components: { Seite }, template: '<Seite />' })
    app.config.warnHandler = (m) => meldungen.push('warn: ' + String(m))
    app.config.errorHandler = (e) => meldungen.push('err: ' + String(e && e.message))
    app.mount(host)
    await warte(40)
    assert.deepEqual(meldungen.filter((m) => /^err:/.test(m)), [], 'Fehler: ' + meldungen.join(' | '))

    // Der Handy-Kopf MUSS im Bild sein — sonst misst der Fall den Desktop.
    const kopfVnode = (() => {
      const treffer = []
      const lauf = (vnode) => {
        if (!vnode) return
        const name = typeof vnode.type === 'object' ? (vnode.type?.__name || vnode.type?.name) : null
        if (name === 'KalenderKopfMobil' && vnode.component) treffer.push(vnode.component)
        if (vnode.component) lauf(vnode.component.subTree)
        if (Array.isArray(vnode.children)) for (const k of vnode.children) lauf(k)
      }
      lauf(host._vnode.component.subTree)
      return treffer[0] || null
    })()
    assert.ok(kopfVnode, 'Vorbedingung: bei 390 px fehlt der Handy-Kopf (`KalenderKopfMobil`) ganz')

    const ausloeser = mehrKnopf(host, 'Weitere Kalender-Aktionen')
      || [...host.querySelectorAll('button')].find((b) => /⋯/.test(b.textContent || ''))
    assert.ok(ausloeser, 'Vorbedingung: der ⋯-Auslöser im Handy-Kopf fehlt im Bild')
    ausloeser.click()
    await warte(16)
    const menue = document.querySelector('[role="menu"]')
    assert.ok(menue, 'das ⋯-Menü des Handy-Kopfs öffnet auf der Seite nicht')
    const text = menue.textContent || ''
    const ergebnis = {
      bild: text.replace(/\s+/g, ' ').trim().slice(0, 300),
      eintrag: [...menue.querySelectorAll('[role="menuitem"]')]
        .some((b) => /^\s*(?:.*\s)?Kalender verwalten\s*$/.test(b.textContent || '') || /Kalender verwalten/.test(b.textContent || '')),
      hilfe: /Hilfe & Infos/.test(text),
      kopf: kopfVnode.props,
    }
    app.unmount()
    host.remove()
    for (const el of [...document.body.querySelectorAll('[data-fuer]')]) el.remove()
    return ergebnis
  }

  // (a) Mit Recht: der Eintrag steht im WIRKLICH GEÖFFNETEN Menü.
  const mit = await handyMenue(mitRecht('Handy-Kalender'))
  assert.equal(mit.kopf?.darfVerwalten, true,
    `der Handy-Kopf bekommt bei 390 px nicht „darfVerwalten“ von der Seite (${String(mit.kopf?.darfVerwalten)})`)
  assert.equal(mit.eintrag, true,
    'das ⋯-Menü des Handy-Kopfs bietet „Kalender verwalten“ trotz Recht nicht an — Inhalt: ' + mit.bild)
  // Gegenprobe: das Menü ist nicht leer (sonst misst der Fall nichts).
  assert.equal(mit.hilfe, true, 'das ⋯-Menü des Handy-Kopfs hat gar keine Einträge — Inhalt: ' + mit.bild)

  // (b) Ohne Recht (403): derselbe Weg, kein Eintrag.
  const ohne = await handyMenue(Object.assign(
    new Error('Nur Kalenderverantwortliche dürfen Kalender verwalten.'), { status: 403 }))
  assert.equal(ohne.kopf?.darfVerwalten, false,
    `der Handy-Kopf trägt nach dem 403 nicht „darfVerwalten = false“ (${String(ohne.kopf?.darfVerwalten)})`)
  assert.equal(ohne.eintrag, false,
    'das ⋯-Menü des Handy-Kopfs bietet „Kalender verwalten“ ohne Serverrecht an — Inhalt: ' + ohne.bild)
  assert.equal(ohne.hilfe, true, 'das ⋯-Menü des Handy-Kopfs ist im 403-Fall leer (Gegenprobe fehlt) — Inhalt: ' + ohne.bild)
})

// ══════════════════════════════════════════════════════════════════════════
// S5 · Ein Recht, das nach einem 403 NEU vergeben wird (MUSS 6)
// ══════════════════════════════════════════════════════════════════════════

test('UI-R3h/S5: nach einem 403 im vorigen Besuch erscheint „Kalender verwalten“ erst mit der Antwort DIESES Besuchs — an der echten Kalenderseite gemessen', async () => {
  // UI-R3i (SOLL 4): Gemountet wird die SEITE (`pages/Kalender.vue`), nicht die
  // Leiste allein. Im Betrieb trägt die Leiste immer `:darf-verwalten` von der
  // Seite — ein Einzel-Mount der Leiste (ohne Prop) prüft einen Fall, den es
  // dort nicht gibt: die Leiste liest dann den geteilten Stand direkt, und der
  // Satz des Seitenbesuchs (UI-R3g) kommt gar nicht ins Spiel.
  //
  // Gemessen wird das GERENDERTE BILD: der Eintrag „Kalender verwalten“ in der
  // Seitenleiste. Ablauf:
  //   Besuch 1 — der Server sperrt (403): kein Eintrag.
  //   Besuch 2 — das Recht ist neu vergeben, die Antwort hängt: VOR ihr kein
  //              Eintrag, NACH ihr der Eintrag.
  const geteilt = await import('../src/diakonos/composables/useKalenderVerwaltung.js')
  geteilt.__setzeApiAufruf((methode, args) => globalThis.__uiR3hRestMock(methode, args))
  geteilt.__leeren()

  const Seite = await baustein('pages/Kalender.vue')
  const sperre = () => Object.assign(
    new Error('Nur Kalenderverantwortliche dürfen Kalender verwalten.'), { status: 403 })

  // ── Besuch 1: 403 — die Seite zeigt den Eintrag nicht. ──────────────────
  ueberschreibungen = {
    'get_kalender_verwaltung$': sperre,
    'get_accessible_calendars$': [],
    'get_events$|get_events_feed$|get_termine$': [],
  }
  const erster = await programm('<Seite />', { teile: { Seite } })
  assert.ok(verwaltenKnopf(erster.host) === undefined,
    'Vorbedingung: nach dem 403 steht der Eintrag (der Fall misst nichts): '
      + (erster.host.textContent || '').replace(/\s+/g, ' ').slice(0, 200))
  // Die Gegenprobe: die Leiste ist wirklich da (sonst wäre „kein Eintrag“ trivial).
  assert.match(erster.host.textContent || '', /Hilfe & Infos/,
    'die Seitenleiste ist gar nicht im Bild (Gegenprobe fehlt): '
      + (erster.host.textContent || '').replace(/\s+/g, ' ').slice(0, 200))
  erster.app.unmount()
  erster.host.remove()
  for (const el of [...document.body.querySelectorAll('[data-fuer]')]) el.remove()

  // ── Besuch 2: das Recht ist inzwischen vergeben — die Antwort hängt. ────
  const tor = schleuse()
  let gefragt = 0
  ueberschreibungen = {
    'get_kalender_verwaltung$': () => { gefragt += 1; return tor.versprechen },
    'get_accessible_calendars$': [],
    'get_events$|get_events_feed$|get_termine$': [],
  }
  const zweiter = await programm('<Seite />', { teile: { Seite } })
  await warte(20)
  assert.equal(gefragt, 1,
    `der Besuch muss den Endpunkt GENAU EINMAL fragen — gefragt: ${gefragt} `
      + '(mehr als einmal: ein zweiter Weg zum selben Endpunkt je Seitenbesuch)')
  // VOR der Antwort: kein Eintrag — der 403 des vorigen Besuchs trägt nicht mehr.
  assert.equal(verwaltenKnopf(zweiter.host), undefined,
    'der Eintrag steht schon VOR der Antwort dieses Besuchs (aus dem Stand des vorigen): '
      + (zweiter.host.textContent || '').replace(/\s+/g, ' ').slice(0, 200))

  tor.oeffnen(mitRecht('Neu vergeben'))
  await warte(40)
  assert.ok(verwaltenKnopf(zweiter.host),
    'nach der Antwort dieses Besuchs (Recht neu vergeben) fehlt „Kalender verwalten“ in der Leiste: '
      + (zweiter.host.textContent || '').replace(/\s+/g, ' ').slice(0, 300))
  zweiter.app.unmount()
  zweiter.host.remove()
})
