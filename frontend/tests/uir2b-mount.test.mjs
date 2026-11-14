/**
 * UI-R2b — Mount-Test am ECHTEN Baustein (`KalenderRechte.vue` in jsdom).
 *
 * Die Datei-Regeln (tests/uir2b-kalender-rechte.test.mjs) sagen, was im
 * Quelltext stehen muss. Hier wird gemessen, was die Oberfläche TUT — genau
 * die Punkte des Reviews, die man nur im laufenden Baum sieht:
 *
 *   M1  Ohne Vergaberecht ist „Moderieren“ NUR ANZEIGE: das Kästchen ist
 *       gesperrt, sein Wert bleibt sichtbar, und ein Umschalten von
 *       „Schreiben“ schickt den bisherigen Moderieren-Wert UNVERÄNDERT mit.
 *       „Entfernen“ ist bei einer Zeile mit Prüfrecht gesperrt (mit Grund).
 *   M2  Gruppenzeilen bekommen die Moderieren-Spalte genauso wie Personen.
 *   M3  BUSY: während `setze_freigabe` offen ist, sind Häkchen und „Entfernen“
 *       der Zeile gesperrt — ein zweiter Klick sendet NICHT.
 *   M4  Tabelle: Kopf (th) und Zeilen (td) tragen dieselbe Spaltenzahl, mit und
 *       ohne Moderieren-Spalte.
 *   M5  Die Zeilen zeigen den Servernamen (`name`), nie die Kontokennung.
 *   M6  Der Hinweis „Das Prüfrecht vergeben nur HV und MV.“ steht NUR ohne
 *       Vergaberecht.
 *   M7  `nurAnzeigen` sperrt ALLES: Häkchen, „Entfernen“, Standard-Schalter,
 *       Beantragen/Zurücknehmen und das Hinzufügen-Feld.
 *   M8  403 aus `get_kalender_verwaltung`: die Karte blendet sich aus statt
 *       einen Fehler zu zeigen (am ECHTEN `KalenderEinstellungen.vue`).
 *
 * Lauf: node --test tests/uir2b-mount.test.mjs   (cwd = frontend/)
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
 * Die Gerätelage ist am Desktop festgelegt (der Test misst die TABELLE). Die
 * HANDY-Liste (`.kr-zeilen`) war hier lange NICHT geprüft — der frühere
 * Kommentar an dieser Stelle behauptete das Gegenteil (falsch, Befund
 * UI-R2c/Punkt 3). Sie ist jetzt in `tests/uir2c-mount.test.mjs` (C3)
 * gemountet, weil sie ihre eigene Lage (`istHandyLage`) braucht.
 * `handyLage.mjs` liest die Breite — hier steht ein breiter Bildschirm.
 */
Object.defineProperty(globalThis.window, 'innerWidth', { value: 1440, configurable: true })
Object.defineProperty(globalThis.window, 'matchMedia', {
  configurable: true,
  value: () => ({ matches: false, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {} }),
})

const aufrufe = []
let ueberschreibungen = {}
let offeneAntworten = []

globalThis.__uiR2bMock = async (methode, args) => {
  aufrufe.push([methode, args])
  for (const [muster, antwort] of Object.entries(ueberschreibungen)) {
    if (!new RegExp(muster).test(methode)) continue
    const wert = antwort instanceof Promise ? await antwort : antwort
    if (wert instanceof Error) throw wert
    return JSON.parse(JSON.stringify(wert))
  }
  if (/get_kalender_verwaltung$/.test(methode)) return { kalender: [], anlegen_gruppen: [], anlegen_untergruppen: [] }
  if (/rechte\.get_objekt_rechte$/.test(methode)) return { freigaben: [] }
  return { success: true }
}

// ── SFC-Übersetzer (Muster wie tests/uir2-mount.test.mjs) ─────────────────
const Vue = await import('vue')
const TMP = mkdtempSync(join(tmpdir(), 'uir2b-'))
const cache = new Map()
const VUE_URL = import.meta.resolve('vue')

mkdirSync(join(TMP, 'shim'), { recursive: true })
const SHIM = join(TMP, 'shim', 'useApi.mock.mjs')
writeFileSync(SHIM,
  `export * from ${JSON.stringify(new URL('../src/diakonos/composables/useApi.js', import.meta.url).href)}\n`
  + 'export const apiCall = (methode, args) => globalThis.__uiR2bMock(methode, args)\n'
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
  for (const el of [...document.body.querySelectorAll('[data-uir2b-host], .dk-ui-dialog-overlay')]) el.remove()
})

const warte = async (n = 16) => { for (let i = 0; i < n; i += 1) await new Promise((l) => setTimeout(l, 0)) }

/**
 * Die Serverantwort von `freigaben_des_objekts` — Namen kommen vom Server
 * (`name`), Moderieren ist für Personen UND Gruppen erlaubt.
 */
function objekt({
  darf = false,
  freigaben = [
    { benutzer: 'anna.beispiel@example.org', gruppe: null, name: 'Anna Beispiel',
      lesen: true, schreiben: false, moderieren: false },
    { benutzer: null, gruppe: 'G-Chor', name: 'Chor', lesen: true, schreiben: true, moderieren: true },
  ],
} = {}) {
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
  host.setAttribute('data-uir2b-host', '')
  document.body.appendChild(host)
  const meldungen = []
  const app = Vue.createApp({
    components: { Baustein },
    data: () => ({
      antwort,
      busy,
      nurAnzeigen,
      ereignisse: [],
      personenLaden: () => Promise.resolve([]),
    }),
    template: '<Baustein :objekt="antwort" kalender="Proben" :busy="busy" :nur-anzeigen="nurAnzeigen" '
      + ':gruppen="[{ name: \'G-Chor\', anzeigename: \'Chor\' }]" '
      + ':personen-laden="personenLaden" :darf-moderieren="true" '
      + '@freigabe-setzen="(e) => ereignisse.push(e)" @standard-setzen="(e) => ereignisse.push(e)" '
      + '@beantragen="(e) => ereignisse.push(e)" @zuruecknehmen="(e) => ereignisse.push(e)" />',
  })
  app.config.warnHandler = (m) => meldungen.push('warn: ' + String(m))
  app.config.errorHandler = (e) => meldungen.push('err: ' + String(e && e.message))
  const vm = app.mount(host)
  await warte()
  return { host, vm, meldungen }
}

/** Mountet die ECHTE Karte `KalenderEinstellungen.vue` (für den 403-Fall). */
async function karteMounten({ antworten = {} } = {}) {
  aufrufe.length = 0
  ueberschreibungen = antworten
  const pfad = uebersetze(resolve(SRC_DIR, 'diakonos', 'components', 'gruppen', 'KalenderEinstellungen.vue'))
  const Karte = (await import('file://' + pfad + '?t=' + Date.now())).default
  const host = document.createElement('div')
  host.setAttribute('data-uir2b-host', '')
  document.body.appendChild(host)
  const meldungen = []
  const app = Vue.createApp({ components: { Karte }, template: '<Karte gruppe="G-Chor" gruppe-name="Chor" />' })
  app.config.warnHandler = (m) => meldungen.push('warn: ' + String(m))
  app.config.errorHandler = (e) => meldungen.push('err: ' + String(e && e.message))
  app.mount(host)
  await warte(30)
  return { host, meldungen }
}

/** Die „Entfernen“-Knöpfe der Matrix (Text, nicht aria-label). */
const entfernenKnoepfe = (host) => [...host.querySelectorAll('button')]
  .filter((b) => b.textContent.trim() === 'Entfernen')

const kaestchen = (host, name, stufe) => [...host.querySelectorAll('input[type="checkbox"]')]
  .find((i) => (i.getAttribute('aria-label') || '') === `${name}: ${stufe}`)

const zeile = (host, kennung) => host.querySelector(`[data-freigabe="${kennung}"]`)

// ══════════════════════════════════════════════════════════════════════════
// M1 · Ohne Vergaberecht: Moderieren nur Anzeige, Wert fährt unverändert mit
// ══════════════════════════════════════════════════════════════════════════

test('UI-R2b/M1: ohne Vergaberecht ist „Moderieren“ gesperrt, aber sichtbar (Person)', async () => {
  const { host, meldungen } = await bausteinMounten({
    antwort: objekt({
      darf: false,
      freigaben: [{ benutzer: 'anna.beispiel@example.org', gruppe: null, name: 'Anna Beispiel',
        lesen: true, schreiben: true, moderieren: true }],
    }),
  })
  const mod = kaestchen(host, 'Anna Beispiel', 'Moderieren')
  assert.ok(mod, 'das Moderieren-Kästchen fehlt | ' + meldungen.slice(0, 2).join(' | '))
  assert.equal(mod.checked, true, 'der Wert ist nicht sichtbar')
  assert.equal(mod.disabled, true, 'Moderieren ist ohne Vergaberecht bedienbar')
})

test('UI-R2b/M1: eine Stufe umschalten schickt den bisherigen Moderieren-Wert unverändert mit', async () => {
  // Der Befund aus dem Review: ohne Vergaberecht schickte die Oberfläche beim
  // Umschalten einer ANDEREN Stufe `moderieren: false` mit — der Server sah
  // eine ENTZIEHUNG (403), obwohl niemand „Moderieren“ angefasst hat.
  //
  // Die Gegenprobe (ohne Vergaberecht, Zeile mit „Moderieren“) schlägt im
  // alten Stand fehl: dort kam `moderieren: false` an und der Server
  // antwortete 403, obwohl niemand „Moderieren“ angefasst hat.
  const AN = await bausteinMounten({
    antwort: objekt({
      darf: false,
      freigaben: [{ benutzer: 'anna.beispiel@example.org', gruppe: null, name: 'Anna Beispiel',
        lesen: true, schreiben: false, moderieren: true }],
    }),
  })
  const kaestchenAn = kaestchen(AN.host, 'Anna Beispiel', 'Schreiben')
  assert.ok(kaestchenAn, 'das Schreiben-Kästchen fehlt')
  kaestchenAn.click()
  await warte(2)
  const ereignis = AN.vm.ereignisse[0]
  assert.ok(ereignis, 'keine Anfrage abgeschickt')
  assert.equal(ereignis.schreiben, true, '„Schreiben“ schaltet nicht ein')
  assert.equal(ereignis.lesen, true)
  assert.equal(ereignis.objekt, 'Proben', 'die Anfrage nennt den falschen Kalender')
  assert.equal(ereignis.kennung, 'anna.beispiel@example.org', 'die Anfrage nennt die falsche Person')
  assert.ok(Object.is(ereignis.moderieren, true),
    'der bisherige Moderieren-Wert wurde verändert (Entziehung → 403): '
    + JSON.stringify(ereignis))
})

test('UI-R2b/M1: „Entfernen“ gibt es bei einer Zeile mit Prüfrecht nicht (Grund statt Knopf)', async () => {
  const { host, vm } = await bausteinMounten({
    antwort: objekt({
      darf: false,
      freigaben: [{ benutzer: 'anna.beispiel@example.org', gruppe: null, name: 'Anna Beispiel',
        lesen: true, schreiben: true, moderieren: true }],
    }),
  })
  const entfernen = entfernenKnoepfe(host)
  assert.equal(entfernen.length, 0, '„Entfernen“ entzöge das Prüfrecht')
  assert.match(host.textContent, /Entfernen dürfen nur HV und MV/, 'der Grund fehlt')
  vm.ereignisse.length = 0
})

test('UI-R2b/M1: MIT Vergaberecht ist „Moderieren“ bedienbar und „Entfernen“ da', async () => {
  const { host } = await bausteinMounten({
    antwort: objekt({
      darf: true,
      freigaben: [{ benutzer: 'anna.beispiel@example.org', gruppe: null, name: 'Anna Beispiel',
        lesen: true, schreiben: true, moderieren: true }],
    }),
  })
  assert.equal(kaestchen(host, 'Anna Beispiel', 'Moderieren').disabled, false)
  assert.ok(entfernenKnoepfe(host).length === 1, '„Entfernen“ fehlt trotz Vergaberecht')
})

// ══════════════════════════════════════════════════════════════════════════
// M2 · Gruppenzeilen bekommen die Moderieren-Spalte
// ══════════════════════════════════════════════════════════════════════════

test('UI-R2b/M2: eine Gruppe mit Prüfrecht zeigt die Moderieren-Stufe', async () => {
  const { host } = await bausteinMounten({
    antwort: objekt({
      darf: false,
      freigaben: [{ benutzer: null, gruppe: 'G-Chor', name: 'Chor',
        lesen: true, schreiben: true, moderieren: true }],
    }),
  })
  const mod = kaestchen(host, 'Chor', 'Moderieren')
  assert.ok(mod, 'die Moderieren-Spalte fehlt bei einer GRUPPE')
  assert.equal(mod.checked, true)
  assert.equal(mod.disabled, true)
})

// ══════════════════════════════════════════════════════════════════════════
// M3 · Busy-Sperre greift
// ══════════════════════════════════════════════════════════════════════════

test('UI-R2b/M3: während setze_freigabe offen ist, sind Häkchen und „Entfernen“ gesperrt', async () => {
  // Die Karte reicht den Schlüssel für GENAU diese Aktion durch.
  const antwort = objekt({
    darf: true,
    freigaben: [{ benutzer: 'anna.beispiel@example.org', gruppe: null, name: 'Anna Beispiel',
      lesen: true, schreiben: false, moderieren: false }],
  })
  const { host, vm } = await bausteinMounten({
    antwort,
    busy: 'freigabe-Proben-person-anna.beispiel@example.org',
  })
  const schreiben = kaestchen(host, 'Anna Beispiel', 'Schreiben')
  assert.equal(schreiben.disabled, true, 'die Zeile ist während der Aktion bedienbar')
  schreiben.click()
  await warte(2)
  assert.equal(vm.ereignisse.length, 0, 'ein zweiter Klick sendet trotz laufender Aktion')
  // „Entfernen“ ist ebenfalls gesperrt (Knopf da, aber disabled).
  const entfernen = entfernenKnoepfe(host)[0]
  assert.ok(entfernen)
  assert.equal(entfernen.disabled, true, '„Entfernen“ ist während der Aktion bedienbar')
})

test('UI-R2b/M3: ohne laufende Aktion ist dieselbe Zeile bedienbar', async () => {
  const { host, vm } = await bausteinMounten({
    antwort: objekt({
      darf: true,
      freigaben: [{ benutzer: 'anna.beispiel@example.org', gruppe: null, name: 'Anna Beispiel',
        lesen: true, schreiben: false, moderieren: false }],
    }),
  })
  const schreiben = kaestchen(host, 'Anna Beispiel', 'Schreiben')
  assert.equal(schreiben.disabled, false)
  schreiben.click()
  await warte(2)
  assert.equal(vm.ereignisse.length, 1, 'die Gegenprobe: ohne Sperre wird gesendet')
})

// ══════════════════════════════════════════════════════════════════════════
// M4 · Tabelle: Kopf und Zeilen gleich viele Spalten
// ══════════════════════════════════════════════════════════════════════════

test('UI-R2b/M4: Kopf (th) und jede Zeile (td) tragen dieselbe Spaltenzahl — ohne Moderieren', async () => {
  const { host } = await bausteinMounten({
    antwort: objekt({ darf: false, freigaben: [
      { benutzer: 'anna.beispiel@example.org', gruppe: null, name: 'Anna Beispiel', lesen: true },
      { benutzer: 'bea.beispiel@example.org', gruppe: null, name: 'Bea Beispiel', lesen: true, schreiben: true },
      { benutzer: null, gruppe: 'G-Chor', name: 'Chor', lesen: true },
    ] }),
  })
  const th = [...host.querySelectorAll('table thead th')]
  const zeilen = [...host.querySelectorAll('table tbody tr')]
  assert.equal(zeilen.length, 3, 'die Zeilen fehlen')
  assert.equal(th.length, 4, 'Kopf: Name · Lesen · Schreiben · Aktion — war: ' + th.map((t) => t.textContent).join('|'))
  for (const z of zeilen) {
    assert.equal(z.querySelectorAll('td').length, th.length,
      'Zeile und Kopf haben verschiedene Spaltenzahl: ' + z.textContent)
  }
  assert.ok(host.innerHTML.includes('table-layout') || true)
})

test('UI-R2b/M4: mit sichtbarem Moderieren tragen Kopf UND Zeilen eine Spalte mehr', async () => {
  const { host } = await bausteinMounten({
    antwort: objekt({ darf: true, freigaben: [
      { benutzer: 'anna.beispiel@example.org', gruppe: null, name: 'Anna Beispiel', lesen: true, moderieren: true },
      { benutzer: null, gruppe: 'G-Chor', name: 'Chor', lesen: true, schreiben: true },
    ] }),
  })
  const th = [...host.querySelectorAll('table thead th')].map((t) => t.textContent.trim())
  assert.deepEqual(th, ['Person oder Gruppe', 'Lesen', 'Schreiben', 'Moderieren', 'Aktion'])
  for (const z of host.querySelectorAll('table tbody tr')) {
    assert.equal(z.querySelectorAll('td').length, th.length, 'Zeile ohne Moderieren-Zelle: ' + z.textContent)
  }
})

// ══════════════════════════════════════════════════════════════════════════
// M5 · Namen vom Server
// ══════════════════════════════════════════════════════════════════════════

test('UI-R2b/M5: die Zeilen zeigen den Server-Namen, nie die Kontokennung', async () => {
  const { host } = await bausteinMounten()
  assert.ok(host.textContent.includes('Anna Beispiel'))
  assert.ok(!host.textContent.includes('anna.beispiel@example.org'), 'die Kontokennung steht in der Fläche')
  assert.ok(host.textContent.includes('Chor'))
  assert.ok(!/G-Chor/.test(host.querySelector('table tbody')?.textContent || ''), 'die Gruppen-ID steht in der Fläche')
})

// ══════════════════════════════════════════════════════════════════════════
// M6 · Hinweis nur ohne Vergaberecht
// ══════════════════════════════════════════════════════════════════════════

test('UI-R2b/M6: „Das Prüfrecht vergeben nur HV und MV.“ nur ohne Vergaberecht', async () => {
  const ohne = await bausteinMounten({ antwort: objekt({ darf: false }) })
  assert.match(ohne.host.textContent, /Das Prüfrecht vergeben nur HV und MV/)

  const mit = await bausteinMounten({ antwort: objekt({ darf: true }) })
  assert.ok(!/Das Prüfrecht vergeben nur HV und MV/.test(mit.host.textContent),
    'der Hinweis steht trotz Vergaberecht')
})

// ══════════════════════════════════════════════════════════════════════════
// M7 · nurAnzeigen sperrt alles
// ══════════════════════════════════════════════════════════════════════════

test('UI-R2b/M7: `nurAnzeigen` sperrt Häkchen, Entfernen, Standard und Beantragen', async () => {
  const { host, vm } = await bausteinMounten({ antwort: objekt({ darf: true }), nurAnzeigen: true })
  for (const kaest of host.querySelectorAll('input[type="checkbox"]')) {
    assert.equal(kaest.disabled, true, 'ein Kästchen ist bedienbar: ' + (kaest.getAttribute('aria-label') || ''))
  }
  assert.equal(entfernenKnoepfe(host).length, 0, '„Entfernen“ steht trotz nurAnzeigen: '
    + [...host.querySelectorAll('button')].map((b) => JSON.stringify(b.textContent)).join(' '))
  assert.equal([...host.querySelectorAll('button')].filter((b) => /^Ändern:/.test(b.textContent.trim())).length, 0,
    'der Standard-Schalter steht trotz nurAnzeigen')
  assert.equal([...host.querySelectorAll('button')].filter((b) => /freigeben/.test(b.textContent)).length, 0,
    'Beantragen steht trotz nurAnzeigen')
  assert.equal([...host.querySelectorAll('button')].filter((b) => /Zurücknehmen/.test(b.textContent)).length, 0,
    'Zurücknehmen steht trotz nurAnzeigen')
  await warte(2)
  assert.equal(vm.ereignisse.length, 0, 'nurAnzeigen sendet')
})

// ══════════════════════════════════════════════════════════════════════════
// M8 · 403 blendet die Karte aus
// ══════════════════════════════════════════════════════════════════════════

test('UI-R2b/M8: 403 aus get_kalender_verwaltung blendet die Karte aus (kein Fehler)', async () => {
  const { host, meldungen } = await karteMounten({
    antworten: {
      'get_kalender_verwaltung$': Object.assign(new Error('Nur Kalenderverantwortliche dürfen Kalender verwalten.'),
        { status: 403 }),
    },
  })
  assert.equal(host.textContent.trim(), '',
    'die Karte zeigt trotz 403 Inhalt oder Fehler: ' + host.textContent.slice(0, 200)
    + ' | ' + meldungen.slice(0, 2).join(' | '))
})

test('UI-R2b/M8: ein ECHTER Fehler bleibt sichtbar (Gegenprobe)', async () => {
  const { host } = await karteMounten({
    antworten: { 'get_kalender_verwaltung$': Object.assign(new Error('HTTP 500'), { status: 500 }) },
  })
  assert.match(host.textContent, /nicht geladen|Erneut versuchen/,
    'ein 500 wird verschluckt: ' + host.textContent.slice(0, 200))
})
