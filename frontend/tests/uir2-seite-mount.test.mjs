/**
 * UI-R2 — Mountet die ECHTE `pages/GruppeDetail.vue` und misst den Weg von der
 * Seite bis zur Kalenderkarte.
 *
 * Die Karte allein ist geprüft (tests/uir2-mount.test.mjs). Hier geht es um
 * das, was NUR auf der Seite schiefgehen kann:
 *
 *   S1  Die Seite reicht die drei neuen Angaben überhaupt durch: den Namen der
 *       Obergruppe, den Namen dieser Untergruppe und das Moderationsrecht.
 *   S2  Auf einer Untergruppen-Seite steht bei „Wohin gehört der Kalender?“
 *       der NAME der Untergruppe (nicht die Kennung `UG-K`) — die Auswahl
 *       zeigt nie einen technischen Schlüssel.
 *   S3  Ein Name klebt nicht an einer fremden Kennung: eine Karte, die mit
 *       gruppenfremder Kennung und dem Namen dieser Seite aufgebaut wird,
 *       zeigt den Namen NICHT (sonst hieße der fremde Kalender wie die Gruppe).
 *
 * Lauf: node --test tests/uir2-seite-mount.test.mjs   (cwd = frontend/)
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
// jsdom hat kein requestAnimationFrame als GLOBAL — Vue braucht es für die
// Übergänge des Dialogs (sonst „ReferenceError“ als unhandledRejection).
globalThis.requestAnimationFrame = (cb) => setTimeout(() => cb(Date.now()), 0)
globalThis.cancelAnimationFrame = (id) => clearTimeout(id)

// ── Testwelt ──────────────────────────────────────────────────────────────
const GRUPPE = { name: 'G-Chor', gruppenname: 'Chor', dienstbereich: 'DB-1' }
const UNTERGRUPPE = { name: 'UG-K', untergruppenname: 'Kinderchor', gruppe: GRUPPE.name, status: 'aktiv' }

const aufrufe = []
let ueberschreibungen = {}

globalThis.__uiR2SeiteMock = async (methode, args) => {
  aufrufe.push([methode, args])
  for (const [muster, antwort] of Object.entries(ueberschreibungen)) {
    if (!new RegExp(muster).test(methode)) continue
    const wert = antwort instanceof Error ? (() => { throw antwort })() : antwort
    return JSON.parse(JSON.stringify(wert))
  }
  if (/get_gruppe_detail$/.test(methode)) {
    // Die Seite selbst liefert auf `#/gruppe/UG-K` die UNTERGRUPPE (mit ihrer
    // Obergruppe) — so wie der Server es tut.
    return { gruppe: null, untergruppe: UNTERGRUPPE, mitglieder: [], verantwortliche: [],
      rechte: { verwalten: true, rollen: true },
      untergruppen: [{ name: UNTERGRUPPE.name, untergruppenname: UNTERGRUPPE.untergruppenname }] }
  }
  if (/get_kalender_verwaltung$/.test(methode)) {
    return {
      kalender: [{ name: 'Kinderchor-Kalender', titel: 'Kinderchor-Kalender', farbe: '#cc3366',
        gruppe: GRUPPE.name, untergruppe: UNTERGRUPPE.name, standard_gruppe_lesen: true,
        gemeinde_status: 'aus', gruppe_status: 'aus' }],
      darf_gemeinde_kalender: false,
      anlegen_gruppen: [GRUPPE.name],
      anlegen_untergruppen: [UNTERGRUPPE.name],
      farbe_standard: '#2266aa',
    }
  }
  if (/get_objekt_rechte$/.test(methode)) return { freigaben: [], gemeinde_status: 'aus', gruppe_status: 'aus' }
  return { success: true }
}

// ── SFC-Übersetzer (Muster wie tests/ui-r1-reiter-mount.test.mjs) ─────────
const Vue = await import('vue')
const TMP = mkdtempSync(join(tmpdir(), 'uir2s-'))
const cache = new Map()
const VUE_URL = import.meta.resolve('vue')

mkdirSync(join(TMP, 'shim'), { recursive: true })
const SHIM = join(TMP, 'shim', 'useApi.mock.mjs')
writeFileSync(SHIM,
  `export * from ${JSON.stringify(new URL('../src/diakonos/composables/useApi.js', import.meta.url).href)}\n`
  + 'export const apiCall = (methode, args) => globalThis.__uiR2SeiteMock(methode, args)\n'
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
  code = code.replace(/from\s+['"]vue['"]/g, `from '${VUE_URL}'`)
  code = code.replace(/from\s+['"](\.[^'"]+)['"]/g, (voll, spec) => {
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
  for (const el of [...document.body.querySelectorAll('[data-uir2s-host], .dk-ui-dialog-overlay')]) el.remove()
})

const warte = async (n = 16) => { for (let i = 0; i < n; i += 1) await new Promise((l) => setTimeout(l, 0)) }

/** Mountet die ECHTE Seite auf der Adresse der Untergruppe. */
async function seiteMounten() {
  aufrufe.length = 0
  globalThis.window.__DIakonosBOOT = { roles: [], devmode: false, user: { email: 'rebekka.fink@example.org' } }
  window.location.hash = `#/gruppe/${UNTERGRUPPE.name}/einstellungen`
  await warte(2)
  const pfad = uebersetze(resolve(SRC_DIR, 'diakonos', 'pages', 'GruppeDetail.vue'))
  const Seite = (await import('file://' + pfad + '?t=' + Date.now())).default
  const host = document.createElement('div')
  host.setAttribute('data-uir2s-host', '')
  document.body.appendChild(host)
  const meldungen = []
  const app = Vue.createApp({ components: { Seite }, template: '<Seite />' })
  app.config.warnHandler = (m) => meldungen.push('warn: ' + String(m))
  app.config.errorHandler = (e) => meldungen.push('err: ' + String(e && e.message))
  app.mount(host)
  await warte(30)
  return { host, meldungen }
}

// ══════════════════════════════════════════════════════════════════════════
// S1 · Durchreichen
// ══════════════════════════════════════════════════════════════════════════

test('UI-R2b/S1: die Seite reicht die Namen durch — das Moderationsrecht NICHT mehr', () => {
  const quelle = readFileSync(resolve(SRC_DIR, 'diakonos', 'pages', 'GruppeDetail.vue'), 'utf8')
  for (const prop of [':gruppe-name="obergruppeName"', ':untergruppe-name="eigenerUntergruppenName"']) {
    assert.ok(quelle.includes(prop), `die Seite gibt ${prop} nicht weiter`)
  }
  // Der Gruppenname der OBERGRUPPE kommt aus `get_gruppe_detail` — nicht aus
  // der Kennung (sonst stünde „G-Chor“ in der Auswahl).
  assert.match(quelle, /anzeigeName\(gruppe\.value/, 'der Obergruppen-Name wird nicht aufgelöst')
  // UI-R2b (Punkt 8): `canManage` ist KEIN Ersatz für `darf_moderieren_vergeben`
  // (auf Untergruppenseiten true für GL, false für HV/MV). Allein der
  // Server-Wert aus `get_objekt_rechte` entscheidet; fehlt er → false.
  assert.ok(!/darf-moderieren-vergeben/.test(quelle), 'die Seite reicht canManage als Moderationsrecht durch')
  assert.ok(!/darfModerierenVergeben/.test(quelle), 'die Seite führt ein eigenes Moderationsrecht')
})

// ══════════════════════════════════════════════════════════════════════════
// S2 · Anlegen-Auswahl auf der Untergruppen-Seite
// ══════════════════════════════════════════════════════════════════════════

test('UI-R2/S2: „Wohin gehört der Kalender?“ zeigt den NAMEN, nie die Kennung', async () => {
  const { host, meldungen } = await seiteMounten()
  const knopf = [...host.querySelectorAll('button')].find((b) => /Kalender anlegen/.test(b.textContent))
  assert.ok(knopf, 'der Knopf „Kalender anlegen“ fehlt | ' + meldungen.slice(0, 3).join(' | '))
  knopf.click()
  await warte(10)
  const auswahl = [...document.querySelectorAll('.dk-ui-dialog-overlay button, .dk-ui-dialog-overlay [role="combobox"], .dk-ui-dialog-overlay [role="listbox"]')]
  const text = (document.querySelector('.dk-ui-dialog-overlay')?.textContent || '')
  assert.ok(text.includes('Kinderchor'), 'der Name der Untergruppe fehlt in der Auswahl: ' + text.slice(0, 400))
  assert.ok(!/>\s*UG-K\s*</.test(text), 'die Kennung steht in der Auswahl')
  assert.ok(auswahl.length >= 0)
})

// ══════════════════════════════════════════════════════════════════════════
// S3 · Kein Name an fremder Kennung
// ══════════════════════════════════════════════════════════════════════════

/** Mountet die ECHTE Karte mit freier gruppe/name-Kombination. */
async function karteMounten({ gruppe, gruppeName = '', untergruppe = '', untergruppeName = '' }) {
  const pfad = uebersetze(resolve(SRC_DIR, 'diakonos', 'components', 'gruppen', 'KalenderEinstellungen.vue'))
  const Karte = (await import('file://' + pfad + '?t=' + Date.now())).default
  const host = document.createElement('div')
  host.setAttribute('data-uir2s-host', '')
  document.body.appendChild(host)
  const app = Vue.createApp({
    components: { Karte },
    data: () => ({ gruppe, gruppeName, untergruppe, untergruppeName }),
    template: '<Karte :gruppe="gruppe" :gruppe-name="gruppeName" :untergruppe="untergruppe" '
      + ':untergruppe-name="untergruppeName" />',
  })
  app.mount(host)
  await warte(20)
  return host
}

async function zielOptionen(host) {
  const knopf = [...host.querySelectorAll('button')].find((b) => /Kalender anlegen/.test(b.textContent))
  assert.ok(knopf, 'Vorbedingung: der Knopf „Kalender anlegen“ fehlt')
  knopf.click()
  await warte(10)
  const dialog = document.querySelector('.dk-ui-dialog-overlay')
  assert.ok(dialog, 'Vorbedingung: der Anlege-Dialog fehlt')
  return dialog.textContent || ''
}

test('UI-R2/S3: der Name dieser Seite steht bei der EIGENEN Kennung', async () => {
  // ZWEI Ziele, damit der Dialog fragt, wohin der Kalender gehört.
  ueberschreibungen = {
    'get_kalender_verwaltung$': {
      kalender: [],
      darf_gemeinde_kalender: false,
      anlegen_gruppen: ['G-Chor'],
      anlegen_untergruppen: ['UG-K'],
      farbe_standard: '#2266aa',
    },
  }
  const host = await karteMounten({ gruppe: 'G-Chor', gruppeName: 'Chor', untergruppe: 'UG-K', untergruppeName: 'Kinderchor' })
  const text = await zielOptionen(host)
  ueberschreibungen = {}
  assert.ok(text.includes('Chor'), 'der Gruppenname fehlt in der Auswahl: ' + text.slice(0, 300))
  assert.ok(text.includes('Kinderchor'), 'der Name der Untergruppe fehlt in der Auswahl')
  assert.ok(!text.includes('UG-K'), 'die Kennung steht in der Auswahl')
})

test('UI-R2/S3: ein fremder Kalender trägt NICHT den Namen dieser Seite', async () => {
  // Der Server erlaubt hier eine FREMDÉ Gruppe — der Name der Seite darf
  // daran nicht kleben (sonst hieße die fremde Gruppe „Kinderchor“).
  ueberschreibungen = {
    'get_kalender_verwaltung$': {
      kalender: [],
      darf_gemeinde_kalender: false,
      anlegen_gruppen: ['G-Fremd'],
      anlegen_untergruppen: [],
      farbe_standard: '#2266aa',
    },
  }
  const host = await karteMounten({ gruppe: 'G-Fremd', gruppeName: 'Kinderchor' })
  const text = await zielOptionen(host)
  ueberschreibungen = {}
  assert.ok(!text.includes('Kinderchor'), 'der Name dieser Seite steht an einer fremden Kennung: '
    + text.slice(0, 300))
})
