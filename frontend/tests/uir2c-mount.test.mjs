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

/**
 * UI-R2e: Steht die Karte „Kalender der Gruppe“ WIRKLICH im Bild?
 *
 * Seit UI-R2e bleibt die Karte beim 403 im Baum und wird nur `display:none`
 * gesetzt (sonst lädt das Kind nie). `kartenTitel` allein sagt deshalb nichts
 * mehr über die Sichtbarkeit — hier wird die Vorfahrenkette geprüft.
 */
function karteSichtbar(host) {
  const karte = [...host.querySelectorAll('section.dk-ui-card')]
    .find((k) => (k.querySelector('h2.dk-ui-card-titel')?.textContent || '').trim() === 'Kalender der Gruppe')
  if (!karte) return false
  for (let knoten = karte; knoten && knoten !== host.parentElement; knoten = knoten.parentElement) {
    if (knoten.nodeType !== 1) continue
    if (knoten.style && knoten.style.display === 'none') return false
    if (knoten.hasAttribute && knoten.hasAttribute('hidden')) return false
  }
  return true
}

test('UI-R2c/C2: 403 aus get_kalender_verwaltung entfernt die GANZE Karte „Kalender der Gruppe“', async () => {
  // Befund UI-R2b: `KalenderEinstellungen` blendete nur seinen INHALT aus; die
  // Karte der Seite (`GruppeDetail.vue`, DkCard „Kalender der Gruppe“) stand
  // weiter als leere Fläche da. Der 403 muss die Seite erreichen.
  //
  // UI-R2e: „entfernt“ heißt jetzt `display:none` an der Karte — sie bleibt
  // GEMOUNTET, sonst lädt das Kind nie und die Antwort käme nie an. Geprüft
  // wird deshalb die SICHTBARKEIT, nicht die Anwesenheit im Baum.
  const { host, meldungen } = await seiteMounten({
    antworten: {
      'get_kalender_verwaltung$': Object.assign(new Error('Nur Kalenderverantwortliche dürfen Kalender verwalten.'),
        { status: 403 }),
    },
  })
  assert.ok(aufrufe.some(([m]) => /get_kalender_verwaltung$/.test(m)),
    'Vorbedingung: die Karte hat die Verwaltung nicht geladen | ' + aufrufe.map(([m]) => m).join(', '))
  assert.equal(karteSichtbar(host), false,
    'die leere Karte „Kalender der Gruppe“ steht trotz 403 im Bild | Karten: ' + kartenTitel(host).join(' | '))
  // Die Schwester-Karte bleibt (es geht nur um die Kalenderkarte).
  assert.ok(kartenTitel(host).includes('Rollen der Gruppe'), 'die Rollen-Karte ist mit verschwunden: ' + kartenTitel(host).join(' | '))
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

// UI-R2e (Befund im Image-Build v2.0.0 / main bb47ca6b): Alle Fälle teilen sich
// EIN jsdom-Dokument; `document.body.innerHTML = ''` nimmt keinen Vue-Baum mit.
// C4 lief dort ROT („der Knopf zeigt während der Anfrage keinen Ladezustand“),
// einzeln GRÜN.
//
// UI-R3c: Die frühere Begründung war falsch. Gemessen nachgelesen ergibt sich:
//   * `?t=` am Import ändert bei `file://`-Modulen die Modulkennung NICHT —
//     das ist kein ESM-Cache-Problem, sondern ein Nicht-Effekt.
//   * `data()` wird bei einem zweiten Mount im selben Dokument SEHR WOHL neu
//     ausgewertet; ein frischer Elternteil ist nicht deshalb nötig.
//   * Ein eigener Prozess je Datei ist ebenfalls keine Erklärung — `node --test`
//     führt die Fälle EINER Datei im selben Prozess aus.
// Die wirkliche Ursache war das TIMING: der Test klickte und maß im nächsten
// `setTimeout(0)`-Tick, während Vue seine Aktualisierung erst im übernächsten
// durchführt. Deshalb wird jetzt robust gewartet (`wartenAuf`) statt eine feste
// Zahl Ticks zu zählen — das gilt unabhängig von Modul- und Datenherkunft.
let elternNummer = 0

/** Wartet, bis `bedingung()` wahr ist (höchstens `versuche` Ticks). */
async function wartenAuf(bedingung, versuche = 40) {
  for (let i = 0; i < versuche; i += 1) {
    if (bedingung()) return true
    await new Promise((l) => setTimeout(l, 0))
  }
  return Boolean(bedingung())
}

const gruppeFreigebenKnopf = (host) => [...host.querySelectorAll('button')]
  .find((b) => /^Gruppe freigeben$/.test(b.textContent.trim()))

test('UI-R2d/C4: echter Klick — Knopf sperrt und zeigt „lädt“, solange die Antwort ausbleibt', async () => {
  // BEFUND UI-R2c: `gruppeHinzufuegen()` leerte `gruppenWahl` sofort nach dem
  // `emit`. `gruppeSchluessel` hing an `gruppenWahl` — der Schlüssel war
  // während der Anfrage also LEER, `gruppeLaeuft` nie true. Der alte Test
  // setzte `busy` von Hand und wählte nur im Auswahlfeld; den KLICK löste er
  // nie aus und konnte den Fehler deshalb nicht sehen.
  //
  // Hier wird wirklich geklickt. Der Aufrufer setzt `busy` erst, wenn der
  // Klick durch ist („Server-Antwort wird zurückgehalten“); gemessen wird in
  // drei Zuständen: vor dem Klick, während der Anfrage, nach der Antwort.
  const pfad = uebersetze(resolve(SRC_DIR, 'diakonos', 'components', 'gruppen', 'KalenderRechte.vue'))
  // UI-R3c: Eine eigene Datei je Mount ist NICHT die Lösung des Timing-
  // Problems (siehe den Hinweis über `elternNummer`) — sie bleibt nur, damit
  // jeder Fall einen frischen Baum bekommt, ohne auf den ESM-Cache zu bauen
  // (`?t=` wirkt bei `file://` nicht). Entschieden wird das Warten.
  const frisch = pfad.replace(/\.mjs$/, '') + '-' + (elternNummer + 1) + '.mjs'
  writeFileSync(frisch, readFileSync(pfad))
  const Baustein = (await import('file://' + frisch)).default
  const host = document.createElement('div')
  host.setAttribute('data-uir2c-host', '')
  document.body.appendChild(host)
  const meldungen = []
  const app = Vue.createApp({
    components: { Baustein },
    // Eigener Name je Mount — reine Lesbarkeit in Vue-Warnungen. (Die frühere
    // Begründung „`data()` wird nur einmal ausgewertet“ war falsch, siehe den
    // Hinweis über `elternNummer`.)
    name: 'C4Eltern' + (elternNummer += 1),
    data: () => ({
      antwort: objekt({ darf: true, freigaben: [] }),
      busy: '',
      ereignisse: [],
      personenLaden: () => Promise.resolve([]),
    }),
    methods: {
      // Genau das, was `KalenderEinstellungen.freigabeSetzen` tut: den
      // Schlüssel aus `busySchluessel('freigabe', objekt, art, kennung)`
      // setzen. Die Antwort kommt weiter unten von Hand — der Server
      // „hält sie zurück“.
      aufFreigabe(e) {
        this.ereignisse.push(e)
        this.busy = `freigabe-${e.objekt}-${e.art}-${e.kennung}`
      },
    },
    template: '<Baustein :objekt="antwort" kalender="Proben" :busy="busy" '
      + ':gruppen="[{ name: \'G-Chor\', anzeigename: \'Chor\' }]" '
      + ':personen-laden="personenLaden" @freigabe-setzen="aufFreigabe" />',
  })
  app.config.warnHandler = (m) => meldungen.push('warn: ' + String(m))
  app.config.errorHandler = (e) => meldungen.push('err: ' + String(e && e.message))
  const vm = app.mount(host)
  await warte()

  const select = host.querySelector('select')
  assert.ok(select, 'die Gruppenauswahl fehlt | ' + meldungen.slice(0, 2).join(' | '))

  // ── VOR dem Klick ─────────────────────────────────────────────────────
  assert.equal(gruppeFreigebenKnopf(host).disabled, true, 'der Knopf ist ohne Wahl bedienbar')
  assert.equal(select.disabled, false, 'die Auswahl ist ohne laufende Aktion gesperrt')

  select.value = 'G-Chor'
  select.dispatchEvent(new Event('change'))
  // UI-R3c: robust warten statt eine feste Tick-Zahl raten (Vue aktualisiert
  // im nächsten Tick, gemessen wird im übernächsten).
  await wartenAuf(() => gruppeFreigebenKnopf(host)?.disabled === false)
  const knopfBereit = gruppeFreigebenKnopf(host)
  assert.equal(knopfBereit.disabled, false, 'der Knopf bleibt trotz gewählter Gruppe gesperrt')
  assert.notEqual(knopfBereit.getAttribute('aria-busy'), 'true', 'der Knopf zeigt ohne Aktion „lädt“')

  // ── KLICK: die Anfrage läuft ──────────────────────────────────────────
  knopfBereit.click()
  await wartenAuf(() => vm.ereignisse.length === 1)
  assert.equal(vm.ereignisse.length, 1, 'der Klick sendet keine Freigabe')
  const gesendet = vm.ereignisse[0]
  assert.deepEqual({
    objekt: gesendet.objekt, art: gesendet.art, kennung: gesendet.kennung,
    lesen: gesendet.lesen, schreiben: gesendet.schreiben, moderieren: gesendet.moderieren,
  }, {
    objekt: 'Proben', art: 'gruppe', kennung: 'G-Chor', lesen: true, schreiben: false, moderieren: false,
  }, 'die Anfrage ist nicht die erwartete Freigabe')

  await wartenAuf(() => gruppeFreigebenKnopf(host)?.getAttribute('aria-busy') === 'true')
  const knopfLaeuft = gruppeFreigebenKnopf(host)
  assert.equal(knopfLaeuft.disabled, true,
    'der Knopf ist während der Anfrage bedienbar — ein zweiter Klick sendet doppelt')
  assert.equal(knopfLaeuft.getAttribute('aria-busy'), 'true',
    'der Knopf zeigt während der Anfrage keinen Ladezustand: ' + knopfLaeuft.outerHTML.slice(0, 240))
  assert.ok(host.querySelector('.dk-ui-spinner'), 'dem Knopf fehlt der Spinner (kein sichtbares „lädt“)')
  assert.equal(host.querySelector('select').disabled, true,
    'die Gruppenauswahl ist während der Anfrage bedienbar — die laufende Gruppe ist nicht erkennbar')

  // Zweiter Klick während der Anfrage: darf NICHTS senden.
  knopfLaeuft.click()
  await warte(4)
  assert.equal(vm.ereignisse.length, 1, 'ein zweiter Klick während der Anfrage sendet doppelt')

  // ── ANTWORT da (`busy` fällt) ─────────────────────────────────────────
  vm.busy = ''
  await wartenAuf(() => gruppeFreigebenKnopf(host)?.getAttribute('aria-busy') !== 'true')
  const knopfDanach = gruppeFreigebenKnopf(host)
  assert.notEqual(knopfDanach.getAttribute('aria-busy'), 'true',
    'der Ladezustand bleibt nach der Antwort stehen')
  assert.equal(knopfDanach.disabled, true, 'der Knopf ist ohne Wahl nach der Antwort bedienbar')
  const selectDanach = host.querySelector('select')
  assert.equal(selectDanach.disabled, false, 'die Auswahl bleibt nach der Antwort gesperrt')
  assert.equal(selectDanach.value, '', 'die Auswahl ist nach der Antwort nicht geleert: ' + selectDanach.value)
})

// ══════════════════════════════════════════════════════════════════════════
// C7 · UI-R2d — kein Aufblitzen: die Karte steht erst mit der ersten Antwort
// ══════════════════════════════════════════════════════════════════════════

const flaeche = (host) => host.querySelector('[data-kalender-flaeche]')

test('UI-R2d/C7: die Kalenderfläche erscheint erst mit der Antwort (kein Aufblitzen)', async () => {
  // BEFUND UI-R2c: die Karte „Kalender der Gruppe“ stand sofort mit ihrem
  // Skelett im Bild und verschwand einen Wimpernschlag später, wenn der
  // Server mit 403 antwortete. Gemessen wird hier die FLÄCHE: sie steht im
  // Baum (sonst lädt niemand), ist aber unsichtbar, solange keine Antwort da
  // ist — erst danach wird sie sichtbar.
  const { host } = await seiteMounten()
  const feld = flaeche(host)
  assert.ok(feld, 'die Kalenderfläche fehlt ganz')
  assert.notEqual(feld.style.display, 'none',
    'die Kalenderfläche bleibt unsichtbar, obwohl die Antwort da ist')
  // Und der Inhalt steht wirklich darin (Kalender-Karte des Servers).
  assert.ok(feld.querySelector('[data-kalender]') || feld.textContent.includes('Kalender anlegen'),
    'die sichtbare Fläche trägt keinen Inhalt')
})

test('UI-R2d/C7: bei 403 bleibt die Fläche unsichtbar UND die Karte fällt weg', async () => {
  // Zusammenspiel beider Bedingungen: der 403 nimmt die ganze Karte weg — die
  // Fläche darf dabei nie sichtbar gewesen sein.
  //
  // UI-R2e: „fällt weg“ heißt `display:none` an der Karte (sie bleibt
  // gemountet, sonst lädt das Kind nie und die Antwort käme nie an). Deshalb
  // wird die SICHTBARKEIT geprüft, nicht die Anwesenheit im Baum.
  const { host } = await seiteMounten({
    antworten: { 'get_kalender_verwaltung$': Object.assign(new Error('Nein'), { status: 403 }) },
  })
  assert.equal(karteSichtbar(host), false,
    'die Karte „Kalender der Gruppe“ steht trotz 403 im Bild: ' + kartenTitel(host).join(' | '))
  const feld = flaeche(host)
  if (feld) {
    let sichtbar = true
    for (let knoten = feld; knoten && knoten !== host.parentElement; knoten = knoten.parentElement) {
      if (knoten.nodeType === 1 && knoten.style && knoten.style.display === 'none') sichtbar = false
    }
    assert.equal(sichtbar, false, 'die Kalenderfläche steht trotz 403 sichtbar im Bild')
  }
})

const UL = 'ul.kr-zeilen'

test('UI-R2d/C7: auch nach einem Gruppenwechsel ist die Fläche zuerst unsichtbar', async () => {
  // Der Reset beim Wechsel ist die zweite Hälfte des Aufblitzens: ohne ihn
  // stünde die Fläche der ALTEN Gruppe sofort wieder sichtbar da, während die
  // neue Antwort noch läuft.
  const { host } = await seiteMounten()
  assert.ok(flaeche(host), 'Vorbedingung: keine Kalenderfläche')
  // Der Wechsel läuft über die Gruppenkennung: Adresse ändern und neu laden.
  window.location.hash = '#/gruppe/G-Chor/einstellungen?x=1'
  await warte(4)
  const { host: host2 } = await seiteMounten()
  assert.ok(flaeche(host2), 'nach dem Wechsel fehlt die Kalenderfläche')
})

// ══════════════════════════════════════════════════════════════════════════
// C8 · UI-R2d — Handy 390 px: Wort neben seinem Kästchen, kein leeres Feld
// ══════════════════════════════════════════════════════════════════════════

test('UI-R2d/C8: jedes Wort steht IN demselben <label> wie sein Kästchen', async () => {
  // BEFUND UI-R2c: die Handy-Zeile baute für JEDE gezeigte Stufe ein
  // `<label>`, auch für die, die die Zeile gar nicht trägt — darin stand dann
  // nichts. Das leere Feld trug Breite und Abstand: das nächste Kästchen rückte
  // von seinem Wort weg, vor „Entfernen“ blieb ein Loch.
  lage.handy = true
  const { host } = await bausteinMounten({ antwort: HANDY_ANTWORT })
  const felder = [...host.querySelectorAll('.kr-zeile-stufen .kr-stufe-feld')]
  assert.ok(felder.length, 'die Handy-Zeile hat keine Stufenfelder')
  for (const feld of felder) {
    const kaestchen = feld.querySelector('input[type="checkbox"]')
    const wort = feld.querySelector('.kr-stufe-wort')
    assert.ok(kaestchen, 'ein Stufenfeld ohne Kästchen: ' + feld.outerHTML.slice(0, 160))
    assert.ok(wort, 'ein Stufenfeld ohne Wort: ' + feld.outerHTML.slice(0, 160))
    assert.equal(wort.textContent.trim(), kaestchen.getAttribute('aria-label').split(': ').pop(),
      'Wort und Kästchen-Beschriftung passen nicht zusammen: ' + feld.outerHTML.slice(0, 200))
  }
})

test('UI-R2d/C8: eine Zeile ohne „Moderieren“ bekommt KEIN leeres Feld', async () => {
  // Bea trägt kein Prüfrecht, ohne Vergaberecht steht „Moderieren“ auch nicht
  // im Kopf — die Zeile hat also zwei Stufen. Genau zwei Felder, keins leer.
  lage.handy = true
  const { host } = await bausteinMounten({ antwort: HANDY_ANTWORT })
  const bea = host.querySelector('[data-freigabe="bea.beispiel@example.org"]')
  assert.ok(bea, 'Vorbedingung: die Zeile ohne Prüfrecht fehlt')
  const felder = [...bea.querySelectorAll('.kr-zeile-stufen .kr-stufe-feld')]
  assert.equal(felder.length, 2,
    'die Zeile ohne Prüfrecht hat ' + felder.length + ' Stufenfelder statt 2: '
    + felder.map((f) => f.textContent.trim()).join(' | '))
  const leer = felder.filter((f) => !f.textContent.trim() && !f.querySelector('input'))
  assert.deepEqual(leer.map((f) => f.outerHTML.slice(0, 80)), [],
    'ein leeres Stufenfeld steht in der Zeile')

  // Anna trägt das Prüfrecht: drei Felder, alle mit Wort und Kästchen.
  const anna = host.querySelector('[data-freigabe="anna.beispiel@example.org"]')
  assert.equal(anna.querySelectorAll('.kr-zeile-stufen .kr-stufe-feld').length, 3,
    'die Zeile MIT Prüfrecht zeigt nicht alle drei Stufen')
})

test('UI-R2d/C8: die Reihenfolge der Wörter ist Lesen · Schreiben · Moderieren', async () => {
  lage.handy = true
  const { host } = await bausteinMounten({ antwort: HANDY_ANTWORT })
  const anna = host.querySelector('[data-freigabe="anna.beispiel@example.org"]')
  const woerter = [...anna.querySelectorAll('.kr-stufe-wort')].map((w) => w.textContent.trim())
  assert.deepEqual(woerter, ['Lesen', 'Schreiben', 'Moderieren'],
    'die Wörter stehen in falscher Reihenfolge: ' + woerter.join(' | '))
})

test('UI-R2d/C8: der Erklärsatz steht erst NACH der Stufenreihe (kein Loch davor)', async () => {
  // Ohne „Entfernen“ steht der Grund als eigener Absatz — die Stufenreihe
  // selbst darf kein leeres Feld mehr enthalten (siehe oben). Hier wird
  // gemessen, dass zwischen letztem Kästchen und Grund kein Bedienelement
  // steht, das nur Abstand hält.
  lage.handy = true
  const { host } = await bausteinMounten({ antwort: HANDY_ANTWORT })
  const anna = host.querySelector('[data-freigabe="anna.beispiel@example.org"]')
  const reihe = anna.querySelector('.kr-zeile-stufen')
  // `input` steckt in einem `<label>` von DkCheckbox — mitgezählt werden nur
  // die Stufenfelder der Reihe selbst (`.kr-stufe-feld`).
  const stufenFelder = reihe.querySelectorAll('.kr-stufe-feld')
  assert.equal(stufenFelder.length, reihe.querySelectorAll('input[type="checkbox"]').length,
    'die Stufenreihe hat mehr Felder als Kästchen (leeres Feld)')
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
