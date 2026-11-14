/**
 * UI-R2c — Mount-Tests am ECHTEN Baustein (jsdom): Spalten bei GEMISCHTEN
 * Zeilen, die Karte bei 403 auf der Gruppenseite, die Handy-Liste.
 *
 * Jeder Fall misst, was die Oberfläche TUT — nicht, was im Quelltext steht:
 *
 *   C1  GEMISCHTE Zeilen ohne Vergaberecht (eine Zeile MIT, eine OHNE
 *       „Moderieren“): der Kopf trägt „Moderieren“ (weil eine Zeile es trägt),
 *       und JEDE Zeile hat gleich viele Zellen. Die Zelle, die die Zeile nicht
 *       hat, ist leer und trägt KEIN Kästchen.
 *   C2  403 aus `get_kalender_verwaltung` erreicht die SEITE: die ganze Karte
 *       „Kalender der Gruppe“ ist weg (gemountet wird die echte
 *       `pages/GruppeDetail.vue`). Gegenprobe: bei 200 steht die Karte.
 *   C3  HANDY-Lage (`istHandyLage`, nicht Breite): die Liste `.kr-zeilen`
 *       steht statt der Tabelle, „Moderieren“ ohne Recht ist nur Anzeige,
 *       „Entfernen“ ist durch den Erklärsatz ersetzt, und während
 *       `setze_freigabe` offen ist, ist die Zeile gesperrt.
 *
 * Lauf: TZ=Europe/Berlin node --test tests/uir2c-mount.test.mjs   (cwd = frontend/)
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

/**
 * Die Gerätelage kommt AUSSCHLIESSLICH aus `istHandyLage` (matchMedia-Abfrage
 * `HANDY_LAGE_ABFRAGE`), nie aus der Breite. Der Test stellt sie über
 * `matchMedia` ein — genau die Quelle, die die Komponente liest. Ein Umbau der
 * Komponente auf `innerWidth`/CSS-Breite macht die Handy-Fälle damit rot.
 */
const lage = { handy: false }
function matchMediaNachbau(abfrage) {
  const treffer = String(abfrage) === HANDY_LAGE_ABFRAGE
  return {
    media: String(abfrage),
    matches: treffer ? lage.handy : false,
    addEventListener() {},
    removeEventListener() {},
    addListener() {},
    removeListener() {},
  }
}
const { HANDY_LAGE_ABFRAGE } = await import('../src/diakonos/composables/handyLageAbfrage.mjs')
Object.defineProperty(globalThis.window, 'matchMedia', { configurable: true, value: matchMediaNachbau })
Object.defineProperty(globalThis.window, 'innerWidth', { value: 1440, configurable: true })

// ── API-Attrappe ──────────────────────────────────────────────────────────
const aufrufe = []
let ueberschreibungen = {}

globalThis.__uiR2cMock = async (methode, args) => {
  aufrufe.push([methode, args])
  for (const [muster, antwort] of Object.entries(ueberschreibungen)) {
    if (!new RegExp(muster).test(methode)) continue
    const wert = antwort instanceof Promise ? await antwort : antwort
    if (wert instanceof Error) throw wert
    return JSON.parse(JSON.stringify(wert))
  }
  if (/get_kalender_verwaltung$/.test(methode)) {
    return {
      kalender: [{ name: 'Proben', titel: 'Proben', farbe: '#2266aa',
        gruppe: 'G-Chor', untergruppe: null, standard_gruppe_lesen: true,
        gemeinde_status: 'aus', gruppe_status: 'aus' }],
      darf_gemeinde_kalender: false, anlegen_gruppen: ['G-Chor'], anlegen_untergruppen: [],
    }
  }
  if (/get_gruppe_detail$/.test(methode)) {
    return {
      gruppe: { name: 'G-Chor', gruppenname: 'Chor', dienstbereich: 'DB-1' },
      untergruppe: null, mitglieder: [], verantwortliche: [],
      rechte: { verwalten: true, rollen: true },
      untergruppen: [],
    }
  }
  if (/get_objekt_rechte$/.test(methode)) return { freigaben: [] }
  return { success: true }
}

// ── SFC-Übersetzer (Muster wie tests/uir2b-mount.test.mjs) ────────────────
const Vue = await import('vue')
const TMP = mkdtempSync(join(tmpdir(), 'uir2c-'))
const cache = new Map()
const VUE_URL = import.meta.resolve('vue')

mkdirSync(join(TMP, 'shim'), { recursive: true })
const SHIM = join(TMP, 'shim', 'useApi.mock.mjs')
writeFileSync(SHIM,
  `export * from ${JSON.stringify(new URL('../src/diakonos/composables/useApi.js', import.meta.url).href)}\n`
  + 'export const apiCall = (methode, args) => globalThis.__uiR2cMock(methode, args)\n'
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
    if (/composables\/useApi/.test(spec)) return `from '${pathToFileURL(SHIM).href}'`
    const ziel = resolve(dirname(abs), spec)
    const datei = /\.vue$/.test(spec) ? uebersetze(ziel) : ziel
    return `from '${pathToFileURL(datei).href}'`
  })
  const ziel = resolve(TMP, filename.replace(/\.vue$/, '') + '.' + cache.size + '.mjs')
  writeFileSync(ziel, code)
  cache.set(abs, ziel)
  return ziel
}

test.after(() => rmSync(TMP, { recursive: true, force: true }))
test.afterEach(() => {
  lage.handy = false
  for (const el of [...document.body.querySelectorAll('[data-uir2c-host], .dk-ui-dialog-overlay')]) el.remove()
})

const warte = async (n = 16) => { for (let i = 0; i < n; i += 1) await new Promise((l) => setTimeout(l, 0)) }

/** Eine Serverantwort aus `freigaben_des_objekts`. */
function objekt({ darf = false, freigaben = [] } = {}) {
  return {
    typ: 'kalender', objekt: 'Proben', gruppe: 'G-Chor', untergruppe: null,
    standard_gruppe_lesen: true, gemeinde_status: 'aus', gruppe_status: 'aus',
    darf_moderieren_vergeben: darf, freigaben,
  }
}

/** Mountet den ECHTEN Baustein `KalenderRechte.vue`. */
async function bausteinMounten({ antwort = objekt(), busy = '', nurAnzeigen = false } = {}) {
  aufrufe.length = 0
  ueberschreibungen = {}
  const pfad = uebersetze(resolve(SRC_DIR, 'diakonos', 'components', 'gruppen', 'KalenderRechte.vue'))
  const Baustein = (await import('file://' + pfad + '?t=' + Date.now())).default
  const host = document.createElement('div')
  host.setAttribute('data-uir2c-host', '')
  document.body.appendChild(host)
  const meldungen = []
  const app = Vue.createApp({
    components: { Baustein },
    data: () => ({
      antwort, busy, nurAnzeigen, ereignisse: [], personenLaden: () => Promise.resolve([]),
    }),
    template: '<Baustein :objekt="antwort" kalender="Proben" :busy="busy" :nur-anzeigen="nurAnzeigen" '
      + ':gruppen="[{ name: \'G-Chor\', anzeigename: \'Chor\' }]" '
      + ':personen-laden="personenLaden" '
      + '@freigabe-setzen="(e) => ereignisse.push(e)" @standard-setzen="(e) => ereignisse.push(e)" '
      + '@beantragen="(e) => ereignisse.push(e)" @zuruecknehmen="(e) => ereignisse.push(e)" />',
  })
  app.config.warnHandler = (m) => meldungen.push('warn: ' + String(m))
  app.config.errorHandler = (e) => meldungen.push('err: ' + String(e && e.message))
  const vm = app.mount(host)
  await warte()
  return { host, vm, meldungen }
}

/** Mountet die ECHTE Seite `pages/GruppeDetail.vue` auf `#/gruppe/G-Chor/einstellungen`. */
async function seiteMounten({ antworten = {} } = {}) {
  aufrufe.length = 0
  ueberschreibungen = antworten
  globalThis.window.__DIakonosBOOT = { roles: [], devmode: false, user: { email: 'ruth.hv@example.org' } }
  window.location.hash = '#/gruppe/G-Chor/einstellungen'
  await warte(2)
  const pfad = uebersetze(resolve(SRC_DIR, 'diakonos', 'pages', 'GruppeDetail.vue'))
  const Seite = (await import('file://' + pfad + '?t=' + Date.now())).default
  const host = document.createElement('div')
  host.setAttribute('data-uir2c-host', '')
  document.body.appendChild(host)
  const meldungen = []
  const app = Vue.createApp({ components: { Seite }, template: '<Seite />' })
  app.config.warnHandler = (m) => meldungen.push('warn: ' + String(m))
  app.config.errorHandler = (e) => meldungen.push('err: ' + String(e && e.message))
  app.mount(host)
  await warte(40)
  return { host, meldungen }
}

const kaestchen = (host, name, stufe) => [...host.querySelectorAll('input[type="checkbox"]')]
  .find((i) => (i.getAttribute('aria-label') || '') === `${name}: ${stufe}`)

// ══════════════════════════════════════════════════════════════════════════
// C1 · GEMISCHTE Zeilen: eine Zeile mit, eine ohne „Moderieren“, ohne Recht
// ══════════════════════════════════════════════════════════════════════════

const GEMISCHT = objekt({
  darf: false,
  freigaben: [
    { benutzer: 'anna.beispiel@example.org', gruppe: null, name: 'Anna Beispiel',
      lesen: true, schreiben: true, moderieren: true },
    { benutzer: 'bea.beispiel@example.org', gruppe: null, name: 'Bea Beispiel',
      lesen: true, schreiben: false, moderieren: false },
  ],
})

test('UI-R2c/C1: gemischte Zeilen — Kopf und JEDE Zeile tragen gleich viele Spalten', async () => {
  // Befund UI-R2b: der Kopf kommt aus `gezeigteStufen` (Moderieren, wenn
  // IRGENDEINE Zeile es trägt), die Zellen kamen aber aus `stufenDerZeile`
  // (nur wenn DIESE Zeile es trägt oder das Recht besteht). Ergebnis: Kopf 5,
  // Zeilen [5, 4] — die Aktionszelle der zweiten Zeile rutschte unter
  // „Moderieren“.
  const { host, meldungen } = await bausteinMounten({ antwort: GEMISCHT })
  const th = [...host.querySelectorAll('table thead th')]
  const zeilen = [...host.querySelectorAll('table tbody tr')]
  assert.equal(zeilen.length, 2, 'die Zeilen fehlen | ' + meldungen.slice(0, 2).join(' | '))
  assert.equal(th.length, 5,
    'Kopf ohne Moderieren-Spalte, obwohl eine Zeile es trägt: ' + th.map((t) => t.textContent.trim()).join('|'))
  assert.deepEqual(th.map((t) => t.textContent.trim()),
    ['Person oder Gruppe', 'Lesen', 'Schreiben', 'Moderieren', 'Aktion'])
  for (const z of zeilen) {
    assert.equal(z.querySelectorAll('td').length, th.length,
      'Zeile und Kopf haben verschiedene Spaltenzahl: ' + z.textContent.trim())
  }
})

test('UI-R2c/C1: die Zeile OHNE „Moderieren“ hat eine leere Zelle, kein Kästchen', async () => {
  const { host } = await bausteinMounten({ antwort: GEMISCHT })
  const zeilen = [...host.querySelectorAll('table tbody tr')]
  const mit = zeilen.find((z) => z.textContent.includes('Anna Beispiel'))
  const ohne = zeilen.find((z) => z.textContent.includes('Bea Beispiel'))
  assert.ok(mit && ohne, 'Vorbedingung: beide Zeilen fehlen')
  // Anna trägt Moderieren (gesperrt, weil kein Vergaberecht).
  assert.ok(kaestchen(mit, 'Anna Beispiel', 'Moderieren'), 'die Zeile MIT Prüfrecht zeigt kein Moderieren')
  // Bea trägt es nicht: die Zelle ist leer und enthält KEIN Kästchen.
  assert.equal(kaestchen(ohne, 'Bea Beispiel', 'Moderieren'), undefined,
    'die Zeile OHNE Prüfrecht bekommt trotzdem ein Moderieren-Kästchen')
  const zellen = [...ohne.querySelectorAll('td')]
  const moderierenZelle = zellen[3]
  assert.equal((moderierenZelle.querySelectorAll('input').length), 0,
    'in der Moderieren-Zelle der Zeile ohne Prüfrecht steht ein Bedienelement')
  assert.equal(moderierenZelle.textContent.trim() === '' || moderierenZelle.textContent.trim() === '–', true,
    'die leere Zelle trägt Text: ' + JSON.stringify(moderierenZelle.textContent))
})

test('UI-R2c/C1: mit Vergaberecht trägt auch die Zeile ohne Wert ein bedienbares Kästchen', async () => {
  // Gegenprobe: mit Recht ist „Moderieren“ VERGEBBAR — also steht in jeder
  // Zeile ein Kästchen (das ist der Unterschied zu „nur anzeigen“).
  const { host } = await bausteinMounten({ antwort: objekt({
    darf: true,
    freigaben: [
      { benutzer: 'anna.beispiel@example.org', gruppe: null, name: 'Anna Beispiel',
        lesen: true, schreiben: true, moderieren: true },
      { benutzer: 'bea.beispiel@example.org', gruppe: null, name: 'Bea Beispiel',
        lesen: true, schreiben: false, moderieren: false },
    ],
  }) })
  const bea = kaestchen(host, 'Bea Beispiel', 'Moderieren')
  assert.ok(bea, 'ohne Vergaberecht gesperrt, MIT Recht fehlt das Kästchen')
  assert.equal(bea.disabled, false, 'mit Vergaberecht ist Moderieren nicht bedienbar')
  assert.equal(bea.checked, false)
})

test('UI-R2c/C1: auch die Handy-Liste bleibt bei gemischten Zeilen vollständig', async () => {
  lage.handy = true
  const { host } = await bausteinMounten({ antwort: GEMISCHT })
  const zeilen = [...host.querySelectorAll('ul.kr-zeilen > li')]
  assert.equal(zeilen.length, 2, 'die Handy-Liste zeigt nicht beide Zeilen')
  const ohne = zeilen.find((z) => z.textContent.includes('Bea Beispiel'))
  assert.equal(kaestchen(ohne, 'Bea Beispiel', 'Moderieren'), undefined,
    'die Handy-Zeile ohne Prüfrecht zeigt trotzdem „Moderieren“')
})

// ══════════════════════════════════════════════════════════════════════════
// C2 · 403 erreicht die SEITE: die ganze Karte ist weg
// ══════════════════════════════════════════════════════════════════════════

const kartenTitel = (host) => [...host.querySelectorAll('h2.dk-ui-card-titel')]
  .map((h) => h.textContent.trim())

test('UI-R2c/C2: 403 aus get_kalender_verwaltung entfernt die GANZE Karte „Kalender der Gruppe“', async () => {
  // Befund UI-R2b: `KalenderEinstellungen` blendete nur seinen INHALT aus; die
  // Karte der Seite (`GruppeDetail.vue`, DkCard „Kalender der Gruppe“) stand
  // weiter als leere Fläche da. Der 403 muss die Seite erreichen.
  const { host, meldungen } = await seiteMounten({
    antworten: {
      'get_kalender_verwaltung$': Object.assign(new Error('Nur Kalenderverantwortliche dürfen Kalender verwalten.'),
        { status: 403 }),
    },
  })
  assert.ok(aufrufe.some(([m]) => /get_kalender_verwaltung$/.test(m)),
    'Vorbedingung: die Karte hat die Verwaltung nicht geladen | ' + meldungen.slice(0, 3).join(' | '))
  const titel = kartenTitel(host)
  assert.ok(!titel.includes('Kalender der Gruppe'),
    'die leere Karte „Kalender der Gruppe“ steht trotz 403 | Karten: ' + titel.join(' | '))
  // Die Schwester-Karte bleibt (es geht nur um die Kalenderkarte).
  assert.ok(titel.includes('Rollen der Gruppe'), 'die Rollen-Karte ist mit verschwunden: ' + titel.join(' | '))
})

test('UI-R2c/C2: Gegenprobe — bei 200 steht die Karte', async () => {
  const { host } = await seiteMounten()
  const titel = kartenTitel(host)
  assert.ok(titel.includes('Kalender der Gruppe'), 'die Karte fehlt ohne 403: ' + titel.join(' | '))
  assert.ok(titel.includes('Rollen der Gruppe'), 'die Rollen-Karte fehlt: ' + titel.join(' | '))
})

test('UI-R2c/C2: ein ECHTER Fehler (500) lässt die Karte mit Hinweis stehen', async () => {
  // Nur der 403 ist eine Lage („nichts zu zeigen“). Ein Serverfehler ist einer
  // und bleibt sichtbar — sonst verschwände die Karte bei jedem Ausfall.
  const { host } = await seiteMounten({
    antworten: { 'get_kalender_verwaltung$': Object.assign(new Error('HTTP 500'), { status: 500 }) },
  })
  const titel = kartenTitel(host)
  assert.ok(titel.includes('Kalender der Gruppe'), 'die Karte verschwindet auch bei einem 500: ' + titel.join(' | '))
  assert.match(host.textContent, /Kalender nicht geladen|Erneut versuchen/,
    'der 500 wird ohne Hinweis verschluckt')
})

// ══════════════════════════════════════════════════════════════════════════
// C3 · HANDY-Lage: Liste statt Tabelle, Moderieren nur Anzeige, Entfernen
//      durch Erklärung ersetzt, Sperre während setze_freigabe
// ══════════════════════════════════════════════════════════════════════════

const HANDY_ANTWORT = objekt({
  darf: false,
  freigaben: [
    { benutzer: 'anna.beispiel@example.org', gruppe: null, name: 'Anna Beispiel',
      lesen: true, schreiben: true, moderieren: true },
    { benutzer: 'bea.beispiel@example.org', gruppe: null, name: 'Bea Beispiel',
      lesen: true, schreiben: false, moderieren: false },
  ],
})

test('UI-R2c/C3: in Handy-Lage steht die LISTE (ul.kr-zeilen), keine Tabelle', async () => {
  lage.handy = true
  const { host, meldungen } = await bausteinMounten({ antwort: HANDY_ANTWORT })
  assert.ok(host.querySelector('ul.kr-zeilen'), 'die Handy-Liste fehlt | ' + meldungen.slice(0, 2).join(' | '))
  assert.equal(host.querySelectorAll('table').length, 0, 'in Handy-Lage steht zusätzlich die Tabelle')
  assert.equal(host.querySelectorAll('ul.kr-zeilen > li').length, 2, 'die Liste zeigt nicht beide Zeilen')
})

test('UI-R2c/C3: „Moderieren“ ohne Recht ist in der LISTE nur Anzeige (gesperrt, aber sichtbar)', async () => {
  lage.handy = true
  const { host } = await bausteinMounten({ antwort: HANDY_ANTWORT })
  const mod = kaestchen(host, 'Anna Beispiel', 'Moderieren')
  assert.ok(mod, 'die Handy-Zeile zeigt das Prüfrecht nicht')
  assert.equal(mod.checked, true, 'der Wert ist in der Liste nicht sichtbar')
  assert.equal(mod.disabled, true, '„Moderieren“ ist ohne Vergaberecht in der Liste bedienbar')
  // Und das Wort „Moderieren“ steht daneben (die Liste hat keine Kopfzeile).
  const zeile = host.querySelector('[data-freigabe="anna.beispiel@example.org"]')
  assert.match(zeile.textContent, /Moderieren/, 'das Wort zur Stufe fehlt in der Liste')
})

test('UI-R2c/C3: „Entfernen“ ist in der LISTE durch den Erklärsatz ersetzt', async () => {
  lage.handy = true
  const { host } = await bausteinMounten({ antwort: HANDY_ANTWORT })
  const anna = host.querySelector('[data-freigabe="anna.beispiel@example.org"]')
  const bea = host.querySelector('[data-freigabe="bea.beispiel@example.org"]')
  assert.ok(anna && bea, 'Vorbedingung: die Zeilen fehlen')
  // Zeile MIT Prüfrecht, ohne Vergaberecht: kein Knopf, sondern der Grund.
  assert.equal([...anna.querySelectorAll('button')].filter((b) => b.textContent.trim() === 'Entfernen').length, 0,
    'die Handy-Zeile mit Prüfrecht hat „Entfernen“')
  assert.match(anna.textContent, /Entfernen dürfen nur HV und MV/, 'der Grund fehlt in der Liste')
  // Zeile OHNE Prüfrecht: der Knopf ist da.
  assert.equal([...bea.querySelectorAll('button')].filter((b) => b.textContent.trim() === 'Entfernen').length, 1,
    'die Handy-Zeile ohne Prüfrecht hat keinen „Entfernen“-Knopf')
})

test('UI-R2c/C3: während setze_freigabe offen ist, ist die Handy-Zeile gesperrt', async () => {
  lage.handy = true
  const imGang = await bausteinMounten({
    antwort: HANDY_ANTWORT,
    busy: 'freigabe-Proben-person-bea.beispiel@example.org',
  })
  const schreiben = kaestchen(imGang.host, 'Bea Beispiel', 'Schreiben')
  assert.ok(schreiben, 'Vorbedingung: das Schreiben-Kästchen fehlt')
  assert.equal(schreiben.disabled, true, 'die Handy-Zeile ist während der Aktion bedienbar')
  schreiben.click()
  await warte(2)
  assert.equal(imGang.vm.ereignisse.length, 0, 'ein zweiter Klick sendet aus der Liste heraus')

  // Gegenprobe: ohne laufende Aktion ist dieselbe Zeile bedienbar und sendet.
  lage.handy = true
  const frei = await bausteinMounten({ antwort: HANDY_ANTWORT })
  const k2 = kaestchen(frei.host, 'Bea Beispiel', 'Schreiben')
  assert.equal(k2.disabled, false, 'die Handy-Zeile ist ohne laufende Aktion gesperrt')
  k2.click()
  await warte(2)
  assert.equal(frei.vm.ereignisse.length, 1, 'die Gegenprobe: ohne Sperre wird gesendet')
})

test('UI-R2c/C3: am LAPTOP (keine Handy-Lage) bleibt es bei der Tabelle', async () => {
  // Gegenprobe zur Gerätelage: derselbe Baum, `istHandyLage` false.
  lage.handy = false
  const { host } = await bausteinMounten({ antwort: HANDY_ANTWORT })
  assert.equal(host.querySelectorAll('ul.kr-zeilen').length, 0, 'am Laptop steht die Handy-Liste')
  assert.ok(host.querySelector('table tbody tr'), 'am Laptop fehlt die Tabelle')
})

// ══════════════════════════════════════════════════════════════════════════
// C4 · „Gruppe freigeben“ zeigt den Ladezustand (SOLL 5)
// ══════════════════════════════════════════════════════════════════════════

const gruppeFreigebenKnopf = (host) => [...host.querySelectorAll('button')]
  .find((b) => /^Gruppe freigeben$/.test(b.textContent.trim()))

test('UI-R2c/C4: „Gruppe freigeben“ zeigt „lädt“ und ist gesperrt, während die Aktion läuft', async () => {
  // Befund UI-R2b: der Knopf las `freigabe-<kal>-gruppe`; die Karte setzt beim
  // Senden `freigabe-<kal>-gruppe-<kennung>`. Der Schlüssel traf nie — der
  // Knopf war nie im Ladezustand, ein zweiter Klick sendete doppelt.
  aufrufe.length = 0
  ueberschreibungen = {}
  const pfad = uebersetze(resolve(SRC_DIR, 'diakonos', 'components', 'gruppen', 'KalenderRechte.vue'))
  const Baustein = (await import('file://' + pfad + '?t=' + Date.now())).default
  const host = document.createElement('div')
  host.setAttribute('data-uir2c-host', '')
  document.body.appendChild(host)
  const meldungen = []
  const app = Vue.createApp({
    components: { Baustein },
    data: () => ({
      antwort: objekt({ darf: true, freigaben: [] }),
      // GENAU der Schlüssel, den die Karte beim Gruppen-Freigeben setzt.
      busy: 'freigabe-Proben-gruppe-G-Chor',
      ereignisse: [], personenLaden: () => Promise.resolve([]),
    }),
    template: '<Baustein :objekt="antwort" kalender="Proben" :busy="busy" '
      + ':gruppen="[{ name: \'G-Chor\', anzeigename: \'Chor\' }]" '
      + ':personen-laden="personenLaden" @freigabe-setzen="(e) => ereignisse.push(e)" />',
  })
  app.config.warnHandler = (m) => meldungen.push('warn: ' + String(m))
  app.config.errorHandler = (e) => meldungen.push('err: ' + String(e && e.message))
  const vm = app.mount(host)
  await warte()
  const knopf = gruppeFreigebenKnopf(host)
  assert.ok(knopf, 'der Knopf „Gruppe freigeben“ fehlt | ' + meldungen.slice(0, 2).join(' | '))
  // Ohne gewählte Gruppe ist der Knopf zu (keine Kennung = kein Schlüssel).
  assert.equal(knopf.disabled, true, 'Vorbedingung: der Knopf ist ohne Wahl offen')

  // Gruppe wählen: der Schlüssel entsteht jetzt aus der Kennung.
  const select = host.querySelector('select')
  assert.ok(select, 'die Gruppenauswahl fehlt')
  select.value = 'G-Chor'
  select.dispatchEvent(new Event('change'))
  await warte(4)
  const knopf2 = gruppeFreigebenKnopf(host)
  assert.equal(knopf2.disabled, true, 'der Knopf ist während der Aktion bedienbar')
  assert.equal(knopf2.getAttribute('aria-busy'), 'true',
    'der Knopf zeigt keinen Ladezustand (aria-busy fehlt) — der busy-Schlüssel trifft nicht: '
    + knopf2.outerHTML.slice(0, 220))
  vm.busy = ''
  await warte(4)
  assert.notEqual(gruppeFreigebenKnopf(host).getAttribute('aria-busy'), 'true',
    'der Ladezustand bleibt nach dem Ende der Aktion stehen')
})

// ══════════════════════════════════════════════════════════════════════════
// C5 · nurAnzeigen: kein leerer Erklärsatz (SOLL 6)
// ══════════════════════════════════════════════════════════════════════════

test('UI-R2c/C5: mit `nurAnzeigen` steht kein leeres Erklärfeld in der Zeile', async () => {
  lage.handy = false
  const antwort = objekt({
    darf: true,
    freigaben: [{ benutzer: 'anna.beispiel@example.org', gruppe: null, name: 'Anna Beispiel',
      lesen: true, schreiben: false, moderieren: false }],
  })
  const nurLesen = await bausteinMounten({ antwort, nurAnzeigen: true })
  const leer = [...nurLesen.host.querySelectorAll('.kr-grund')]
    .filter((el) => el.textContent.trim() === '')
  assert.deepEqual(leer.map((el) => el.outerHTML), [],
    'ein leeres Erklärfeld steht in der Fläche (nurAnzeigen)')

  // Und in der Handy-Liste ebenso.
  lage.handy = true
  const handy = await bausteinMounten({ antwort, nurAnzeigen: true })
  const leerHandy = [...handy.host.querySelectorAll('.kr-grund')]
    .filter((el) => el.textContent.trim() === '')
  assert.deepEqual(leerHandy.map((el) => el.outerHTML), [],
    'ein leeres Erklärfeld steht in der Handy-Liste (nurAnzeigen)')
})

test('UI-R2c/C5: Gegenprobe — OHNE nurAnzeigen steht der Grund bei gesperrtem Entfernen', async () => {
  const { host } = await bausteinMounten({ antwort: objekt({
    darf: false,
    freigaben: [{ benutzer: 'anna.beispiel@example.org', gruppe: null, name: 'Anna Beispiel',
      lesen: true, schreiben: false, moderieren: true }],
  }) })
  assert.match(host.textContent, /Entfernen dürfen nur HV und MV/,
    'der Grund fehlt, obwohl „Entfernen“ gesperrt ist')
})

// ══════════════════════════════════════════════════════════════════════════
// C6 · „Lesen“ einer moderierenden Zeile (SOLL 4)
// ══════════════════════════════════════════════════════════════════════════

test('UI-R2c/C6: ohne Vergaberecht ist „Lesen“ einer moderierenden Zeile gesperrt', async () => {
  // Der Server setzt bei `moderieren=True` immer `lesen=True` mit (R-12p).
  // Ein bedienbares Lesen-Häkchen nähme also scheinbar etwas weg, was der
  // Server sofort wieder setzt.
  const { host, vm } = await bausteinMounten({ antwort: objekt({
    darf: false,
    freigaben: [{ benutzer: 'anna.beispiel@example.org', gruppe: null, name: 'Anna Beispiel',
      lesen: true, schreiben: false, moderieren: true }],
  }) })
  const lesen = kaestchen(host, 'Anna Beispiel', 'Lesen')
  assert.ok(lesen, 'das Lesen-Kästchen fehlt')
  assert.equal(lesen.disabled, true, '„Lesen“ ist trotz Prüfrecht ohne Vergaberecht bedienbar')
  lesen.click()
  await warte(2)
  assert.equal(vm.ereignisse.length, 0, 'ein Klick auf „Lesen“ sendet trotz Sperre')
})

test('UI-R2c/C6: MIT Vergaberecht bleibt „Lesen“ bedienbar (Gegenprobe)', async () => {
  const { host } = await bausteinMounten({ antwort: objekt({
    darf: true,
    freigaben: [{ benutzer: 'anna.beispiel@example.org', gruppe: null, name: 'Anna Beispiel',
      lesen: true, schreiben: false, moderieren: true }],
  }) })
  assert.equal(kaestchen(host, 'Anna Beispiel', 'Lesen').disabled, false,
    '„Lesen“ ist mit Vergaberecht gesperrt')
})

test('UI-R2c/C6: eine Zeile OHNE Prüfrecht lässt „Lesen“ auch ohne Vergaberecht bedienbar', async () => {
  const { host } = await bausteinMounten({ antwort: objekt({
    darf: false,
    freigaben: [{ benutzer: 'bea.beispiel@example.org', gruppe: null, name: 'Bea Beispiel',
      lesen: true, schreiben: false, moderieren: false }],
  }) })
  assert.equal(kaestchen(host, 'Bea Beispiel', 'Lesen').disabled, false,
    '„Lesen“ einer Zeile ohne Prüfrecht ist gesperrt')
})
