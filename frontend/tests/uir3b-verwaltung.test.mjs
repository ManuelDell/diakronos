/**
 * UI-R3b — Mount-Tests der Kalenderverwaltung am ECHTEN Baum (jsdom).
 *
 * Die Karte verlangt Messungen, keine Quelltext-Muster: „Bearbeiten/Löschen
 * zurück“ (Punkt 1), „Neuer Kalender auch ohne Kalender“ (Punkt 2), „EIN
 * Anlege-Knopf und EIN Hinweis“ (Punkt 3), Texte im Modus `alleKalender`
 * (Punkt 4). Hier wird geklickt, getippt und gesendet — geprüft wird, was die
 * Oberfläche WIRKLICH ruft.
 *
 *   M1  Bearbeiten: Dialog öffnet mit Titel, Farbe und Häkchen dieses
 *       Kalenders; Umbenennen sendet `update_kalender` mit Name, neuem Titel,
 *       Farbe und `selbstverwaltet` — und mit NICHTS sonst (keine Alt-Rechte).
 *   M2  Farbe ändern sendet die neue Farbe im selben Weg.
 *   M3  Löschen läuft sofort (`delete_kalender` mit `bestaetigt: 1`) und meldet
 *       sich am Rückgängig-Stapel an (`mitRueckgaengig` → Meldung „Rückgängig“).
 *   M4  Ein Kalender aus dem Google-Import (`calender_details`) fragt VORHER
 *       nach und löscht erst nach „Löschen“ im Rückfrage-Dialog.
 *   M5  403 beim Ändern/Löschen: der Satz des Servers steht in der Fläche bzw.
 *       im Dialog — keine erfundene Rolle, keine stille Tat.
 *   M6  Die SEITE mit leerer Liste und Anlegerecht: „Neuer Kalender“ öffnet den
 *       Dialog der Fläche (vor UI-R3b war `flaeche` null — der Klick tat nichts).
 *   M7  Modus `alleKalender`: KEIN zweiter Anlege-Knopf und KEIN zweiter Hinweis
 *       auf der Seite; die Gruppenseite behält ihren eigenen Knopf.
 *   M8  Leerzustand im Modus `alleKalender` spricht nicht von „dieser Gruppe“.
 *
 * UI-R3d (diese Karte):
 *   M9  „Rückgängig“ nach dem Löschen stellt den Kalender MIT seiner Zuordnung
 *       wieder her (`gruppe`, `untergruppe`, `standard_gruppe_lesen`) — ohne
 *       diese Angaben antwortet der Server HV/MV/GL mit 403 (Gemeinde-Kalender)
 *       und der Kalender wäre endgültig weg.
 *   M10 Ein Kalender MIT Freigaben oder Sichtbarkeit bekommt die Rückfrage
 *       statt „Rückgängig“ — diese Dinge kämen nicht zurück.
 *   M11 Ist der Kalender wieder da, holt auch die SEITE ihre Daten neu
 *       (`verwaltung`, nicht nur die Liste der Fläche).
 *
 * Lauf: node --test tests/uir3b-verwaltung.test.mjs   (cwd = frontend/)
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

// ── jsdom zuerst, dann Vue (Muster wie tests/uir2-mount.test.mjs) ─────────
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
/** Antwort von `get_gruppen_hierarchie` (Seite) bzw. leer. */
let baum = { gruppen: [] }

globalThis.__uiR3bMock = async (methode, args) => {
  aufrufe.push([methode, args])
  for (const [muster, antwort] of Object.entries(ueberschreibungen)) {
    if (!new RegExp(muster).test(methode)) continue
    const wert = antwort instanceof Promise ? await antwort : antwort
    if (wert instanceof Error) throw wert
    return JSON.parse(JSON.stringify(wert))
  }
  if (/get_gruppen_hierarchie$/.test(methode)) return JSON.parse(JSON.stringify(baum))
  if (/get_kalender_verwaltung$/.test(methode)) {
    return { kalender: [], anlegen_gruppen: [], anlegen_untergruppen: [], darf_gemeinde_kalender: false }
  }
  if (/rechte\.get_objekt_rechte$/.test(methode)) return { freigaben: [] }
  return { success: true }
}

/**
 * Der Rückgängig-Weg (`rueckgängigWeg.wiederherstellen`) ruft den Endpunkt
 * ÜBER `fetch` — nicht über `apiCall` (das Modul bleibt ohne Netz ladbar,
 * `useApi` kommt erst bei Gebrauch dazu). Für den Klick-Test hier wird
 * `fetch` mitgehört, damit die Gegenrichtung dieselbe Liste füllt.
 */
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
const letzter = (muster) => mit(muster).at(-1)?.[1]

// ── SFC-Übersetzer ────────────────────────────────────────────────────────
const Vue = await import('vue')
const TMP = mkdtempSync(join(tmpdir(), 'uir3b-'))
const cache = new Map()
const VUE_URL = import.meta.resolve('vue')

mkdirSync(join(TMP, 'shim'), { recursive: true })
const SHIM = join(TMP, 'shim', 'useApi.mock.mjs')
writeFileSync(SHIM,
  `export * from ${JSON.stringify(new URL('../src/diakonos/composables/useApi.js', import.meta.url).href)}\n`
  + 'export const apiCall = (methode, args) => globalThis.__uiR3bMock(methode, args)\n'
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
test.afterEach(async () => {
  // UI-R3d: Die Rückfrage (`useBestaetigen`) ist EIN Modulzustand mit einer
  // Warteschlange — sie überlebt den Test. Bliebe eine Frage offen, zeigte der
  // nächste Test DEEREN Text, statt seine eigene zu stellen. Deshalb am Ende
  // jeder Prüfung: offene Fragen ablehnen (wie „Abbrechen“), dann aufräumen.
  const { bestaetigungAntwort } = await import('../src/diakonos/composables/useBestaetigen.js')
  for (let i = 0; i < 8; i += 1) {
    bestaetigungAntwort(false)
    await new Promise((l) => setTimeout(l, 0))
  }
  // Dialoge und Meldungen werden in den `<body>` teleportiert und überleben
  // das Entfernen des Hosts.
  for (const el of [...document.body.children]) el.remove()
  ueberschreibungen = {}
  baum = { gruppen: [] }
  aufrufe.length = 0
})

const warte = async (n = 24) => { for (let i = 0; i < n; i += 1) await new Promise((l) => setTimeout(l, 0)) }

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

/** Mountet die ECHTE gemeinsame Fläche. */
async function flaecheMounten({
  verwaltung = { kalender: [kalender()], anlegen_gruppen: ['G-Chor'] },
  props = { alleKalender: true },
  dialoge = false,
} = {}) {
  aufrufe.length = 0
  ueberschreibungen = { 'get_kalender_verwaltung$': verwaltung }
  const pfad = uebersetze(resolve(SRC_DIR, 'diakonos', 'components', 'gruppen', 'KalenderEinstellungen.vue'))
  const Baustein = (await import('file://' + pfad + '?t=' + Date.now())).default
  // Die globale Rückfrage (`DkBestaetigung` in App.vue) — nur wo sie gebraucht wird.
  const Bestaetigung = dialoge
    ? (await import('file://' + uebersetze(resolve(SRC_DIR, 'diakonos', 'components', 'ui', 'DkBestaetigung.vue'))
      + '?t=' + Date.now())).default
    : null
  const host = document.createElement('div')
  host.setAttribute('data-uir3b-host', '')
  document.body.appendChild(host)
  const meldungen = []
  const ereignisse = []
  const app = Vue.createApp({
    components: Bestaetigung ? { Baustein, Bestaetigung } : { Baustein },
    data: () => ({
      props,
      ereignisse,
      ziele: props.ziele || [{ wert: 'G-Chor', art: 'gruppe', anzeige: 'Gruppe Chor' }],
    }),
    template: (Bestaetigung ? '<Bestaetigung />' : '')
      + '<Baustein :gruppe="props.gruppe || \'\'" :untergruppe="props.untergruppe || \'\'" '
      + ':gruppe-name="props.gruppeName || \'\'" :untergruppe-name="props.untergruppeName || \'\'" '
      + ':alle-kalender="props.alleKalender !== false" :ziele="ziele" :untergruppen="[]" '
      + '@geaendert="ereignisse.push(\'geaendert\')" @gesperrt="ereignisse.push(\'gesperrt\')" />',
  })
  app.config.warnHandler = (m) => meldungen.push('warn: ' + String(m))
  app.config.errorHandler = (e) => meldungen.push('err: ' + String(e && e.message))
  app.mount(host)
  await warte()
  return { host, meldungen, ereignisse }
}

/** Mountet die ECHTE Seite `KalenderVerwaltung.vue`. */
async function seiteMounten({ verwaltung = { kalender: [kalender()], anlegen_gruppen: ['G-Chor'] } } = {}) {
  aufrufe.length = 0
  ueberschreibungen = { 'get_kalender_verwaltung$': verwaltung }
  const pfad = uebersetze(resolve(SRC_DIR, 'diakonos', 'pages', 'KalenderVerwaltung.vue'))
  const Seite = (await import('file://' + pfad + '?t=' + Date.now())).default
  const host = document.createElement('div')
  host.setAttribute('data-uir3b-host', '')
  document.body.appendChild(host)
  const meldungen = []
  const app = Vue.createApp({ components: { Seite }, template: '<Seite />' })
  app.config.warnHandler = (m) => meldungen.push('warn: ' + String(m))
  app.config.errorHandler = (e) => meldungen.push('err: ' + String(e && e.message))
  app.mount(host)
  await warte(40)
  return { host, meldungen }
}

/** Eine Schaltfläche nach sichtbarem Text (innerhalb von `wurzel`). */
function knopf(wurzel, muster) {
  return [...wurzel.querySelectorAll('button')].find((b) => new RegExp(muster).test(b.textContent || ''))
}

/** Dialog nach Titel (Vue teleportiert in den `<body>`).
 *
 * UI-R3d: die JÜNGSTE Fundstelle — ein Dialog eines früheren Tests kann im
 * `<body>` zurückbleiben und trägt denselben `aria-label` („Kalender
 * löschen“). Der erste Treffer wäre dann der falsche. */
function dialog(titel) {
  return [...document.querySelectorAll('.dk-ui-dialog')]
    .filter((d) => new RegExp(titel).test(d.getAttribute('aria-label') || ''))
    .at(-1)
}

/** Absende-Knopf eines Formulars (`form="…"` steht im Fuß des Dialogs). */
function absenden(formId) {
  return [...document.querySelectorAll(`button[form="${formId}"]`)].at(-1)
}

/** Wert in ein Feld schreiben, wie ein Tastendruck (löst v-model aus). */
async function tippen(el, wert) {
  const setter = Object.getOwnPropertyDescriptor(globalThis.HTMLInputElement.prototype, 'value').set
  setter.call(el, wert)
  el.dispatchEvent(new globalThis.Event('input', { bubbles: true }))
  await warte(6)
}

// ── M1/M2: Bearbeiten ─────────────────────────────────────────────────────
test('UI-R3b/M1: Bearbeiten ändert Titel, Farbe und selbstverwaltet per update_kalender', async () => {
  const { host, meldungen, ereignisse } = await flaecheMounten()
  const bearbeitenKnopf = knopf(host, '^Bearbeiten$')
  assert.ok(bearbeitenKnopf, 'Vorbedingung: „Bearbeiten“ fehlt an der Kalenderzeile')
  bearbeitenKnopf.click()
  await warte(12)

  const dlg = dialog('bearbeiten')
  assert.ok(dlg, 'der Bearbeiten-Dialog öffnet nicht')
  const titelFeld = dlg.querySelector('input.dk-ui-eingabe')
  assert.equal(titelFeld.value, 'Proben', 'der Dialog zeigt nicht den Titel dieses Kalenders')
  assert.equal(dlg.querySelector('input[type=color]').value, '#3366cc',
    'der Dialog zeigt nicht die Farbe dieses Kalenders')
  assert.equal(dlg.querySelector('input[type=checkbox]').checked, false,
    'das Häkchen „selbstverwaltet“ spiegelt nicht den Stand der Zeile')
  assert.match(dlg.textContent, /Selbstverwaltet/, 'das Häkchen „selbstverwaltet“ fehlt')

  await tippen(titelFeld, 'Chorproben')
  dlg.querySelector('input[type=checkbox]').checked = true
  dlg.querySelector('input[type=checkbox]').dispatchEvent(new globalThis.Event('change', { bubbles: true }))
  dlg.querySelector('input[type=color]').value = '#cc3366'
  dlg.querySelector('input[type=color]').dispatchEvent(new globalThis.Event('input', { bubbles: true }))
  await warte(6)

  const speichern = absenden('ke-form-bearbeiten')
  assert.ok(speichern, 'der Knopf „Speichern“ fehlt')
  speichern.click()
  await warte(30)

  const aenderung = mit('update_kalender$')
  assert.equal(aenderung.length, 1, 'update_kalender wurde nicht genau einmal gerufen')
  assert.deepEqual(aenderung[0][1], {
    name: 'Proben',
    titel: 'Chorproben',
    farbe: '#cc3366',
    selbstverwaltet: 1,
  }, 'die Änderung schickt nicht genau Titel, Farbe und selbstverwaltet')
  assert.equal(aenderung[0][1].leserechte, undefined,
    'die Änderung schickt die Alt-Rechte mit — sie würden still überschrieben')
  assert.equal(aenderung[0][1].moderatoren, undefined, 'die Änderung schickt Moderatoren mit')
  assert.equal(dialog('bearbeiten'), undefined, 'der Dialog bleibt nach dem Speichern offen')
  // UI-R2e: die Fläche meldet bei jedem Laden `gesperrt` — hier zählt nur die
  // Benachrichtigung der Seite über die Änderung.
  assert.deepEqual(ereignisse.filter((e) => e === 'geaendert'), ['geaendert'],
    'die Seite wird über die Änderung nicht benachrichtigt')
  assert.deepEqual(meldungen.filter((m) => /^err:/.test(m)), [], 'Fehler beim Speichern: ' + meldungen.join(' | '))
})

test('UI-R3b/M2: nur die Farbe ändern sendet den unveränderten Titel mit', async () => {
  const { host } = await flaecheMounten()
  knopf(host, '^Bearbeiten$').click()
  await warte(12)
  const dlg = dialog('bearbeiten')
  const farbe = dlg.querySelector('input[type=color]')
  farbe.value = '#226600'
  farbe.dispatchEvent(new globalThis.Event('input', { bubbles: true }))
  await warte(6)
  absenden('ke-form-bearbeiten').click()
  await warte(30)

  const anfrage = letzter('update_kalender$')
  assert.equal(anfrage.farbe, '#226600', 'die neue Farbe geht nicht mit')
  assert.equal(anfrage.titel, 'Proben', 'der Titel muss unverändert mitgehen (der Server ändert sonst nichts)')
  assert.equal(anfrage.selbstverwaltet, 0, '„selbstverwaltet“ geht mit dem Stand der Zeile mit')
})

// ── M3/M4/M5: Löschen ─────────────────────────────────────────────────────
test('UI-R3b/M3: Löschen läuft sofort, sendet bestaetigt:1 und meldet sich am Stapel an', async () => {
  const { host, ereignisse } = await flaecheMounten()
  const loeschen = knopf(host, '^Löschen$')
  assert.ok(loeschen, 'Vorbedingung: „Löschen“ fehlt an der Kalenderzeile')
  loeschen.click()
  await warte(30)

  assert.equal(dialog('löschen'), undefined,
    'eine Rückfrage steht vor einer umkehrbaren Aktion (Prinzip I2)')
  const anfrage = letzter('delete_kalender$')
  assert.deepEqual(anfrage, { name: 'Proben', bestaetigt: 1 },
    'delete_kalender wird nicht mit Bestätigung gerufen')
  // UI-R2e: `gesperrt` meldet die Fläche bei jedem Laden — hier zählt, dass
  // die Seite nach dem Löschen nachlädt. UI-R3d: nach dem Löschen ist es GENAU
  // EIN Ruf; das zweite `geaendert` kommt erst, wenn „Rückgängig“ den Kalender
  // zurückgebracht hat (Punkt 2).
  assert.equal(ereignisse.filter((e) => e === 'geaendert').length, 1,
    'die Seite lädt nach dem Löschen nicht nach')

  // UX2c/C2: die Löschung ist am Rückgängig-Stapel angemeldet.
  const meldung = [...document.querySelectorAll('.diakonos-toast--undo')]
    .find((t) => /Kalender „Proben“ gelöscht/.test(t.textContent || ''))
  assert.ok(meldung, 'die Rückgängig-Meldung fehlt nach dem Löschen')
  assert.ok(knopf(meldung, 'Rückgängig'), 'die Meldung hat keinen „Rückgängig“-Knopf')
})

test('UI-R3b/M3: „Rückgängig“ legt den Kalender mit seinen Angaben neu an', async () => {
  const { host } = await flaecheMounten({ verwaltung: { kalender: [kalender({ selbstverwaltet: true })] } })
  knopf(host, '^Löschen$').click()
  await warte(30)
  const meldung = [...document.querySelectorAll('.diakonos-toast--undo')]
    .find((t) => /Kalender „Proben“ gelöscht/.test(t.textContent || ''))
  assert.ok(meldung, 'Vorbedingung: die Rückgängig-Meldung fehlt')
  const zurueck = knopf(meldung, 'Rückgängig')
  assert.ok(zurueck, 'Vorbedingung: der „Rückgängig“-Knopf fehlt')

  zurueck.click()
  await warte(120)
  // Die Gegenrichtung ist `create_kalender` mit den Angaben der Zeile.
  // `rueckgängigWeg` ruft den vollen whitelist-Namen (mit Modulpräfix).
  const neu = mit('kalender_verwaltung\\.create_kalender$')
  assert.equal(neu.length, 1, '„Rückgängig“ legt den Kalender nicht neu an')
  assert.equal(neu[0][1].titel, 'Proben')
  assert.equal(neu[0][1].farbe, '#3366cc')
  assert.equal(neu[0][1].selbstverwaltet, true, 'der Kalender käme ohne „selbstverwaltet“ zurück')
  // UI-R3d/a: OHNE die Zuordnung antwortet der Server HV/MV/GL mit 403
  // („Gemeinde-Kalender legen Admin und Kalender-Moderation an.“) — der
  // Kalender wäre danach endgültig weg.
  assert.equal(neu[0][1].gruppe, 'G-Chor',
    'die Gegenrichtung schickt die Gruppe nicht mit — der Kalender käme als Gemeinde-Kalender zurück')
  assert.equal(neu[0][1].standard_gruppe_lesen, true,
    'die Gegenrichtung schickt `standard_gruppe_lesen` nicht mit')
  assert.equal(neu[0][1].untergruppe, undefined,
    'eine Zeile ohne Untergruppe schickt keine Untergruppe mit')
})

test('UI-R3d/M9: „Rückgängig“ stellt die Zuordnung einer UNTERGRUPPE wieder her', async () => {
  const zeile = kalender({ name: 'Kinderchor-Proben', titel: 'Kinderchor-Proben', gruppe: 'G-Chor', untergruppe: 'U-Kinder', standard_gruppe_lesen: false })
  const { host } = await flaecheMounten({ verwaltung: { kalender: [zeile] } })
  knopf(host, '^Löschen$').click()
  await warte(30)
  const meldung = [...document.querySelectorAll('.diakonos-toast--undo')]
    .find((t) => /Kinderchor-Proben/.test(t.textContent || ''))
  assert.ok(meldung, 'Vorbedingung: die Rückgängig-Meldung fehlt')
  knopf(meldung, 'Rückgängig').click()
  await warte(120)

  const neu = mit('kalender_verwaltung\\.create_kalender$')
  assert.equal(neu.length, 1, '„Rückgängig“ legt den Kalender nicht neu an')
  assert.equal(neu[0][1].gruppe, 'G-Chor', 'die Gruppe geht verloren')
  assert.equal(neu[0][1].untergruppe, 'U-Kinder', 'die Untergruppe geht verloren')
  assert.equal(neu[0][1].standard_gruppe_lesen, false,
    'die Antwort der Frage „alle Gruppenmitglieder lesen?“ geht verloren')
})

test('UI-R3d/M9: die reine Abbildung schickt Zuordnung und Standard-Lesen mit', async () => {
  const { abbildung } = await import('../src/diakonos/composables/rueckgaengigWeg.mjs')
  // Genau die Form, die `alleKalenderZeilen` liefert (nach dem Löschen).
  const befehl = abbildung('kalender', {
    name: 'Proben', titel: 'Proben', farbe: '#3366cc',
    gruppe: 'G-Chor', untergruppe: null, selbstverwaltet: false,
    calender_details: '', standard_gruppe_lesen: true,
    gemeinde_status: 'aus', gruppe_status: 'aus',
  })
  assert.equal(befehl.args.gruppe, 'G-Chor')
  assert.equal(befehl.args.standard_gruppe_lesen, true)
  assert.ok(!('untergruppe' in befehl.args) || befehl.args.untergruppe === null,
    'ohne Untergruppe wird keine erfunden')
})

test('UI-R3b/M3b: die Gegenrichtung dieser Zeile ist vollständig (vollstaendig/abbildung)', async () => {
  const { abbildung, vollstaendig } = await import('../src/diakonos/composables/rueckgaengigWeg.mjs')
  const zeile = {
    name: 'Proben', titel: 'Proben', farbe: '#3366cc', selbstverwaltet: true,
    calender_details: '', gruppe: 'G-Chor', untergruppe: null,
  }
  assert.equal(vollstaendig('kalender', zeile), true)
  const befehl = abbildung('kalender', zeile)
  assert.equal(befehl.aufruf, 'diakronos.kronos.api.kalender_verwaltung.create_kalender')
  assert.equal(befehl.args.titel, 'Proben')
  assert.equal(befehl.args.selbstverwaltet, true)
  // Ein Google-Import ist NICHT vollständig zurückholbar.
  const importiert = { ...zeile, calender_details: '{"quelle":"google"}' }
  assert.equal(vollstaendig('kalender', importiert), false)
})

test('UI-R3d/M10: ein Kalender MIT Freigaben bekommt die Rückfrage statt „Rückgängig“', async () => {
  const { host, ereignisse } = await flaecheMounten({
    verwaltung: {
      kalender: [kalender({ leserechte: ['Mitglied'], moderatoren: ['maria@example.org'] })],
      anlegen_gruppen: ['G-Chor'],
    },
    dialoge: true,
  })
  knopf(host, '^Löschen$').click()
  await warte(30)

  // Kein sofortiges Löschen: erst die Rückfrage (diese Dinge kämen nicht zurück).
  assert.equal(mit('delete_kalender$').length, 0,
    'ein Kalender mit Freigaben wird ohne Rückfrage gelöscht — die Freigaben wären weg')
  const frage = dialog('Kalender löschen')
  assert.ok(frage, 'die Rückfrage fehlt bei einem Kalender mit Freigaben')
  assert.doesNotMatch(frage.textContent, /Importiert aus Google Kalender/,
    'die Rückfrage nennt einen Google-Import, den es hier nicht gibt')
  assert.match(frage.textContent, /Freigaben/,
    'die Rückfrage sagt nicht, was verloren geht: ' + (frage.textContent || '').slice(0, 200))

  knopf(frage, '^Löschen$').click()
  await warte(30)
  assert.equal(letzter('delete_kalender$')?.name, 'Proben', 'nach der Bestätigung wird nicht gelöscht')
  // Und KEIN Rückgängig-Angebot für etwas, das nicht vollständig zurückkommt.
  assert.equal([...document.querySelectorAll('.diakonos-toast--undo')]
    .filter((t) => /Proben/.test(t.textContent || '')).length, 0,
  'für einen Kalender mit Freigaben wird „Rückgängig“ angeboten')
  assert.equal(ereignisse.filter((e) => e === 'geaendert').length, 1,
    'die Seite lädt nach dem bestätigten Löschen nicht nach')
})

test('UI-R3d/M10: Sichtbarkeit (nicht „aus“) ist ebenso nicht wiederherstellbar', async () => {
  const { abbildung, vollstaendig } = await import('../src/diakonos/composables/rueckgaengigWeg.mjs')
  const grund = {
    name: 'Proben', titel: 'Proben', farbe: '#3366cc', selbstverwaltet: false,
    calender_details: '', gruppe: 'G-Chor', untergruppe: null,
    leserechte: [], schreibrechte: [], moderatoren: [],
    gemeinde_status: 'aus', gruppe_status: 'aus',
  }
  assert.equal(vollstaendig('kalender', grund), true, 'ein schlichter Kalender ist umkehrbar')
  assert.equal(vollstaendig('kalender', { ...grund, leserechte: ['Mitglied'] }), false,
    'ein Leserecht kommt über create_kalender nicht zurück')
  assert.equal(vollstaendig('kalender', { ...grund, schreibrechte: ['Pfarrer'] }), false,
    'ein Schreibrecht kommt nicht zurück')
  assert.equal(vollstaendig('kalender', { ...grund, moderatoren: ['maria@example.org'] }), false,
    'ein Moderator kommt nicht zurück')
  assert.equal(vollstaendig('kalender', { ...grund, gemeinde_status: 'beantragt' }), false,
    'eine beantragte Sichtbarkeit kommt nicht zurück')
  assert.equal(vollstaendig('kalender', { ...grund, gruppe_status: 'aktiv' }), false,
    'eine aktive Gruppensichtbarkeit kommt nicht zurück')
})

test('UI-R3d/M10: die Fläche fragt bei Freigaben nach (Klick-Test, nicht Quelltext)', async () => {
  const { host } = await flaecheMounten({
    verwaltung: {
      kalender: [kalender({ schreibrechte: ['Pfarrer'], gemeinde_status: 'aktiv' })],
      anlegen_gruppen: ['G-Chor'],
    },
    dialoge: true,
  })
  knopf(host, '^Löschen$').click()
  await warte(30)
  assert.ok(dialog('Kalender löschen'), 'die Rückfrage fehlt trotz Freigaben/Sichtbarkeit')
  assert.equal(mit('delete_kalender$').length, 0, 'ohne Bestätigung wurde gelöscht')
})

// ── M11: die SEITE lädt nach dem Rückgängig neu ───────────────────────────
test('UI-R3d/M11: nach dem Rückgängig holt auch die Seite ihre Daten neu', async () => {
  const { host } = await seiteMounten()
  const vorher = mit('get_kalender_verwaltung$').length
  assert.ok(vorher >= 1, 'Vorbedingung: die Seite hat die Verwaltung nicht geladen')

  knopf(host, '^Löschen$').click()
  await warte(60)
  const nachLoeschen = mit('get_kalender_verwaltung$').length
  assert.ok(nachLoeschen > vorher, 'die Seite lädt nach dem Löschen nicht nach')

  const meldung = [...document.querySelectorAll('.diakonos-toast--undo')]
    .find((t) => /Kalender „Proben“ gelöscht/.test(t.textContent || ''))
  assert.ok(meldung, 'Vorbedingung: die Rückgängig-Meldung fehlt')
  knopf(meldung, 'Rückgängig').click()
  await warte(150)

  assert.equal(mit('kalender_verwaltung\\.create_kalender$').length, 1,
    'Vorbedingung: der Kalender wurde nicht neu angelegt')
  // Das `geaendert` der FLÄCHE holt die Seite nach — sonst stünde in der
  // Zuordnung der Seite weiterhin der gelöschte Stand.
  const seite = mit('get_kalender_verwaltung$')
  assert.ok(seite.length >= nachLoeschen + 2,
    'die Seite lädt ihr `verwaltung` nach dem Rückgängig nicht neu (nur die Fläche lädt)')
})

test('UI-R3b/M4: ein Google-Import-Kalender fragt VOR dem Löschen nach', async () => {
  // Die Rückfrage ist die GLOBALE von `useBestaetigen` (`DkBestaetigung` hängt
  // in `App.vue`); hier wird derselbe Baustein mitgemountet — sonst entstünde
  // die Frage im Nichts.
  const { host, ereignisse } = await flaecheMounten({
    verwaltung: { kalender: [kalender({ calender_details: '{"quelle":"google"}' })], anlegen_gruppen: ['G-Chor'] },
    dialoge: true,
  })
  knopf(host, '^Löschen$').click()
  await warte(30)

  assert.equal(mit('delete_kalender$').length, 0,
    'ein Kalender aus dem Google-Import wird ohne Rückfrage gelöscht — der Vermerk ginge verloren')
  const frage = dialog('Kalender löschen')
  assert.ok(frage, 'die Rückfrage vor dem endgültigen Löschen fehlt')
  assert.match(frage.textContent, /Importiert aus Google Kalender/,
    'die Rückfrage nennt nicht, was verloren geht')

  knopf(frage, '^Löschen$').click()
  await warte(30)
  assert.equal(letzter('delete_kalender$')?.name, 'Proben', 'nach der Bestätigung wird nicht gelöscht')
  assert.deepEqual(ereignisse.filter((e) => e === 'geaendert'), ['geaendert'],
    'die Seite lädt nach dem bestätigten Löschen nicht nach')
})

test('UI-R3b/M4: „Abbrechen“ in der Rückfrage löscht NICHTS', async () => {
  const { host } = await flaecheMounten({
    verwaltung: { kalender: [kalender({ calender_details: '{"quelle":"google"}' })], anlegen_gruppen: ['G-Chor'] },
    dialoge: true,
  })
  knopf(host, '^Löschen$').click()
  await warte(30)
  const frage = dialog('Kalender löschen')
  assert.ok(frage, 'Vorbedingung: die Rückfrage fehlt')
  knopf(frage, '^Abbrechen$').click()
  await warte(30)
  assert.equal(mit('delete_kalender$').length, 0, 'nach „Abbrechen“ wurde trotzdem gelöscht')
})

test('UI-R3b/M5: 403 beim Ändern zeigt den Satz des Servers im Dialog', async () => {
  const { host } = await flaecheMounten()
  ueberschreibungen['update_kalender$'] = Object.assign(
    new Error('HTTP 403'), { status: 403 },
  )
  knopf(host, '^Bearbeiten$').click()
  await warte(12)
  absenden('ke-form-bearbeiten').click()
  await warte(30)

  const offen = dialog('bearbeiten')
  assert.ok(offen, 'der Dialog schließt trotz Fehler (die Eingabe wäre verloren)')
  assert.match(offen.textContent, /nicht ändern/,
    'die Fläche sagt nicht, dass das Recht fehlt: ' + (offen.textContent || '').slice(0, 200))
  assert.doesNotMatch(offen.textContent, /HTTP 403/, 'ein Statuscode steht in der Fläche')
})

test('UI-R3b/M5: 403 beim Löschen nennt die Berechtigung statt eines Codes', async () => {
  const { host } = await flaecheMounten()
  ueberschreibungen['delete_kalender$'] = Object.assign(new Error('HTTP 403'), { status: 403 })
  knopf(host, '^Löschen$').click()
  await warte(30)

  const meldung = [...document.querySelectorAll('.diakonos-toast--error')]
    .map((t) => t.textContent || '').join(' ')
  assert.match(meldung, /nicht löschen/, 'die Fehlermeldung sagt nicht, dass das Recht fehlt: ' + meldung)
  assert.doesNotMatch(meldung, /HTTP 403/, 'ein Statuscode steht in der Meldung')
})

// ── M6: Seite mit leerer Liste ────────────────────────────────────────────
test('UI-R3b/M6: „Neuer Kalender“ öffnet den Dialog auch, wenn es noch KEINEN Kalender gibt', async () => {
  const { host, meldungen } = await seiteMounten({
    verwaltung: { kalender: [], anlegen_gruppen: [], anlegen_untergruppen: [], darf_gemeinde_kalender: true },
  })
  const neu = knopf(host, 'Neuer Kalender')
  assert.ok(neu, 'Vorbedingung: der Anlege-Knopf fehlt auf der Seite')

  neu.click()
  await warte(20)
  const dlg = dialog('Kalender anlegen')
  assert.ok(dlg, 'der Klick öffnet keinen Anlege-Dialog — die Fläche ist ohne Kalender nicht gemountet')
  assert.match(dlg.textContent, /Für alle Mitglieder der Gemeinde/,
    'der Dialog nennt nicht den Ort aus der Serverantwort')
  assert.deepEqual(meldungen.filter((m) => /^err:/.test(m)), [], 'Fehler beim Öffnen: ' + meldungen.join(' | '))
})

test('UI-R3b/M6: ohne Anlegerecht bleibt der Knopf weg (nur die Serverantwort zählt)', async () => {
  const { host } = await seiteMounten({
    verwaltung: { kalender: [], anlegen_gruppen: [], anlegen_untergruppen: [], darf_gemeinde_kalender: false },
  })
  assert.equal(knopf(host, 'Neuer Kalender'), undefined,
    'die Seite bietet Anlegen an, obwohl der Server keinen Ort nennt')
  assert.match(host.textContent, /Kein Kalender zu verwalten/,
    'der Leerzustand ohne Anlegerecht fehlt')
})

// ── M7/M8: EIN Knopf, EIN Hinweis, richtige Texte ─────────────────────────
test('UI-R3b/M7: im Modus alleKalender gibt es genau EINEN Anlege-Knopf und EINEN Hinweis', async () => {
  const { host } = await seiteMounten()
  const anlegeKnoepfe = [...host.querySelectorAll('button')]
    .filter((b) => /Kalender anlegen|Neuer Kalender/.test(b.textContent || ''))
  assert.equal(anlegeKnoepfe.length, 1,
    'die Seite hat ' + anlegeKnoepfe.length + ' Anlege-Knöpfe (A4: genau einer)')
  assert.match(anlegeKnoepfe[0].textContent, /Neuer Kalender/, 'der Knopf der Seite fehlt')
  // Der Hinweis der Fläche gehört dem Ort („diese Gruppe“) — hier steht nur der
  // Hinweis der Seite.
  assert.doesNotMatch(host.textContent, /Hier stehen die Kalender dieser Gruppe/,
    'die Fläche bringt im Modus alleKalender ihren eigenen Hinweis mit')
  assert.match(host.textContent, /wozu er gehört/, 'der Hinweis der Seite fehlt')
})

test('UI-R3b/M7: die Gruppenseite behält ihren eigenen Anlege-Knopf', async () => {
  const { host } = await flaecheMounten({
    verwaltung: { kalender: [kalender()], anlegen_gruppen: ['G-Chor'] },
    props: { alleKalender: false, gruppe: 'G-Chor', gruppeName: 'Chor' },
  })
  assert.ok(knopf(host, 'Kalender anlegen'), 'auf der Gruppenseite fehlt der Anlege-Knopf')
  assert.match(host.textContent, /Hier stehen die Kalender dieser Gruppe/,
    'auf der Gruppenseite fehlt der Hinweis der Fläche')
  // … und Bearbeiten/Löschen bekommt sie durch dieselbe Fläche.
  assert.ok(knopf(host, '^Bearbeiten$'), 'die Gruppenseite bekommt kein „Bearbeiten“')
  assert.ok(knopf(host, '^Löschen$'), 'die Gruppenseite bekommt kein „Löschen“')
})

test('UI-R3b/M8: der Leerzustand im Modus alleKalender spricht nicht von „dieser Gruppe“', async () => {
  const { host } = await seiteMounten({
    verwaltung: { kalender: [], anlegen_gruppen: ['G-Chor'], darf_gemeinde_kalender: true },
  })
  const text = host.textContent || ''
  assert.doesNotMatch(text, /dieser Gruppe/,
    'die Seite nennt „diese Gruppe“, obwohl sie alle Kalender zeigt')
  assert.match(text, /Lege den ersten Kalender an/,
    'der Leerzustand sagt nicht, was zu tun ist')
})

test('UI-R3b/M8: die Gruppenseite nennt weiterhin ihre Gruppe', async () => {
  const { host } = await flaecheMounten({
    verwaltung: { kalender: [], anlegen_gruppen: ['G-Chor'] },
    props: { alleKalender: false, gruppe: 'G-Chor', gruppeName: 'Chor' },
  })
  assert.match(host.textContent, /Lege den ersten Kalender dieser Gruppe an/,
    'die Gruppenseite hat ihren Satz verloren')
})
