/**
 * UX3h3 — Einstellungen: „Speichern nur, wenn geändert“.
 *
 * Die Karte verlangt (je Abschnitt, Vorbild Gestaltung):
 *
 *   1. „Speichern“ ist gesperrt (`disabled` UND `aria-disabled`), solange kein
 *      Feld vom geladenen Stand abweicht;
 *   2. es wird aktiv, sobald getippt wird, und wieder inaktiv, wenn der Wert
 *      auf den geladenen Stand ZURÜCKGEHT (Vergleich, kein „einmal getippt“);
 *   3. nach erfolgreichem Speichern ist es wieder gesperrt;
 *   4. EIN gemeinsames Composable (`useGeaendertStand`, Regel in
 *      `composables/geaendert.mjs`) — keine Kopie je Seite;
 *   5. kein Dialog beim Verlassen mit ungespeicherten Änderungen.
 *
 * Der Test hat zwei Teile:
 *
 *   A · die REGEL direkt (`geaendert.mjs`): Zahlen/Text gleich, Rückweg,
 *       Listen mit leerem Platz, nichts geladen = nichts geändert;
 *   B · die SEITEN wirklich gemountet (jsdom, echte `input`-Ereignisse):
 *       Gemeinde, Anmeldung, Datenschutz-Texte, Datensicherung, Mailversand,
 *       Registrierung — je „gesperrt → tippen → offen → zurück → gesperrt“,
 *       und nach dem Speichern wieder gesperrt.
 *
 * `apiCall` wird über den Übersetzer auf eine Attrappe umgebogen (gleiche
 * Modul-URL wie im Quellbaum) — kein Netz, keine Attrappe im Quellbaum. Die
 * Seiten werden mit ihren ECHTEN Composables gemountet, damit der Test die
 * Kette misst (Laden → Stand → Vergleich), nicht eine nachgebaute.
 *
 * Lauf: node --test tests/ux3h3-speichern-nur-wenn-geaendert.test.mjs  (cwd = frontend/)
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, mkdtempSync, writeFileSync, rmSync, readdirSync, statSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, dirname, resolve, basename } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { JSDOM } from 'jsdom'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'

import { geaenderteFelder, hatSichGeaendert, wertGleich } from '../src/diakonos/composables/geaendert.mjs'

// ── DOM zuerst (Vue greift beim Import schon auf `document` zu) ────────────
const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
for (const schluessel of ['window', 'document', 'Node', 'Element', 'HTMLElement', 'Event',
  'MouseEvent', 'SVGElement', 'CSS', 'CustomEvent', 'FormData', 'HTMLInputElement',
  'HTMLSelectElement', 'HTMLTextAreaElement', 'requestAnimationFrame',
  'getComputedStyle', 'MutationObserver', 'KeyboardEvent', 'FocusEvent']) {
  globalThis[schluessel] = dom.window[schluessel]
}
globalThis.requestAnimationFrame = dom.window.requestAnimationFrame
  || ((fn) => setTimeout(() => fn(Date.now()), 0))

const Vue = await import('vue')
const VUE_URL = import.meta.resolve('vue')
const TESTS_DIR = dirname(fileURLToPath(import.meta.url))
const SRC_ROOT = new URL('../src/', import.meta.url)
const SRC = new URL('../src/diakonos/', import.meta.url)

const TMP = mkdtempSync(join(tmpdir(), 'ux3h3-'))
test.after(() => rmSync(TMP, { recursive: true, force: true }))

// ── API-Attrappe: EINE Stelle, die alle Seiten teilen ─────────────────────
const aufrufe = []
let antwort = () => ({ message: {} })
globalThis.__DK_PUSH = (eintrag) => aufrufe.push(eintrag)
globalThis.__DK_API_ANTWORT = (methode, parameter) => antwort(methode, parameter)
const apiDatei = join(TMP, '_api.mjs')
writeFileSync(apiDatei, [
  'export async function apiCall(methode, parameter) {',
  '  globalThis.__DK_PUSH({ methode, parameter })',
  '  return globalThis.__DK_API_ANTWORT(methode, parameter)',
  '}',
  'export const apiGet = apiCall',
  "export const apiUrl = (pfad) => 'https://pruefstand.invalid/api/method/' + String(pfad).replace(/\\./g, '/')",
  'export class AuditConfirmationRequired extends Error {}',
  'export const pruefeSitzungsAntwort = () => false',
  'export async function apiAntwortPruefen() { return { message: { ok: true } } }',
].join('\n'))

// ── Netz: fetch-Attrappe (Logo/Dokumente laden nicht) ─────────────────────
globalThis.fetch = async () => ({
  ok: true, status: 200,
  headers: { get: () => 'application/json' },
  json: async () => ({ message: {} }),
  text: async () => '{}',
  clone() { return this },
})

// ── SFC → ES-Modul ────────────────────────────────────────────────────────
// Die Quelldateien werden NICHT aus /tmp importiert (dort löst Node `vue`
// nicht auf und relative Importe zeigten ins Leere). Stattdessen wird JEDE
// Datei neben dem echten Baum geschrieben (`TMP/src/…`) und ihre Importe
// werden absolut umgeschrieben — das Verfahren aus
// `ux2f2b-formulare.test.mjs`, nur generisch für alle Tiefen.
import { mkdirSync } from 'node:fs'

const cache = new Map()
const umschreibungen = []
/** Modul-URLs, die eine Umleitung erfahren (gleiche URL für alle Importeure). */
const umleitung = new Map([
  [pathToFileURL(SRC_ROOT.pathname + 'diakonos/composables/useApi.js').href,
    pathToFileURL(apiDatei).href],
])

function aufgeloest(abs) {
  // `.mjs`/`.js`/`.vue` unverändert; ein Import ohne Endung wird ergänzt.
  const kandidaten = [abs, abs + '.mjs', abs + '.js', abs + '/index.mjs']
  for (const k of kandidaten) {
    try { if (statSync(k).isFile()) return k } catch { /* weiter */ }
  }
  throw new Error('nicht gefunden: ' + abs)
}

function kompilieren(abs) {
  if (cache.has(abs)) return cache.get(abs)
  const quellDatei = aufgeloest(abs)
  const relativ = quellDatei.slice(SRC_ROOT.pathname.length)
  const ziel = join(TMP, 'mod', relativ.replace(/[\\/]/g, '_') + '.mjs')
  mkdirSync(dirname(ziel), { recursive: true })
  const quanten = []

  if (quellDatei.endsWith('.vue')) {
    const filename = basename(quellDatei)
    const { descriptor, errors } = parse(readFileSync(quellDatei, 'utf8'), { filename })
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
    quanten.push(code)
  } else {
    quanten.push(readFileSync(quellDatei, 'utf8'))
  }

  // Importe umschreiben: `vue` → absolute Modul-URL; relatives Ziel → das
  // kompilierte bzw. umgeleitete Gegenstück.
  const code = quanten.join('\n').replace(
    /from\s+['"]([^'"]+)['"]/g,
    (ganz, spec) => {
      if (spec === 'vue') return `from '${VUE_URL}'`
      if (spec.startsWith('.')) {
        const zielAbs = aufgeloest(resolve(dirname(quellDatei), spec))
        const url = pathToFileURL(zielAbs).href
        const gerichtet = umleitung.get(url)
        if (gerichtet) return `from '${gerichtet}'`
        return `from '${pathToFileURL(kompilieren(zielAbs)).href}'`
      }
      if (spec.startsWith('node:')) return ganz
      return `from '${spec}'`
    },
  )
  writeFileSync(ziel, code)
  cache.set(abs, ziel)
  return ziel
}

const tick = () => new Promise((loese) => setTimeout(loese, 0))
const warte = async (n = 6) => { for (let i = 0; i < n; i += 1) await tick() }

function tippen(element, wert) {
  element.value = wert
  element.dispatchEvent(new window.Event('input', { bubbles: true }))
}
function umschalten(element, wert) {
  element.checked = wert
  element.dispatchEvent(new window.Event('change', { bubbles: true }))
  element.dispatchEvent(new window.Event('input', { bubbles: true }))
}

async function mounten(baustein) {
  const host = document.createElement('div')
  document.body.appendChild(host)
  const warnungen = []
  const app = Vue.createApp({ components: { Seite: baustein }, template: '<Seite />' })
  app.config.warnHandler = (m) => warnungen.push(m)
  app.config.errorHandler = (e) => warnungen.push(String(e && e.message))
  app.mount(host)
  await warte(10)
  return { host, app, warnungen }
}

/** Der „Speichern“-Knopf der Seite. */
function speichernKnopf(host) {
  return [...host.querySelectorAll('button')]
    .find((b) => /^\s*Speichern/.test((b.textContent || '').trim()))
}

// ══════════════════════════════════════════════════════════════════════════
// A · Die Regel selbst
// ══════════════════════════════════════════════════════════════════════════

test('UX3h3/A: Zahl und ihre Textform sind derselbe Stand (30 ≡ "30")', () => {
  assert.equal(wertGleich(30, '30'), true)
  assert.equal(wertGleich(15, '15.0'), true)
  assert.equal(wertGleich('', 0), false, 'leerer Text ist NICHT die Zahl 0')
  assert.equal(wertGleich(true, 'true'), false, 'Haken und Text sind verschieden')
  assert.equal(wertGleich('a', 'a'), true)
  // Review 07.11.: zwei Texte nie als Zahl angleichen (PLZ, Telefon).
  assert.equal(wertGleich('01067', '1067'), false, 'führende Null ist eine Änderung')
  assert.equal(wertGleich('+49711', '49711'), false, '+ vor der Nummer ist eine Änderung')
  assert.equal(wertGleich(' 5', '5'), false)
  assert.equal(wertGleich('03:00', '03:01'), false)
})

test('UX3h3/A: geänderte Felder — tippen, zurück, nichts geladen', () => {
  const stand = { host: 'mail.example.org', port: 587, automatisch: true }
  assert.deepEqual(geaenderteFelder(stand, { ...stand }), [], 'gleicher Stand = nichts geändert')
  assert.deepEqual(geaenderteFelder(stand, { ...stand, host: 'mail.example.org ' }),
    ['host'], 'geändert wird erkannt (auch ein Leerzeichen am Ende)')
  assert.deepEqual(geaenderteFelder(stand, { ...stand, port: '587' }), [],
    'die Textform derselben Zahl ist keine Änderung')
  assert.deepEqual(geaenderteFelder(stand, { ...stand, port: 465 }), ['port'])
  // Zurückgetippt: derselbe Vergleich, keine „einmal getippt“-Spur.
  assert.deepEqual(geaenderteFelder(stand, { ...stand, port: 465, host: 'x' }), ['host', 'port'])
  assert.deepEqual(geaenderteFelder(stand, { ...stand }), [], 'zurück = wieder nichts geändert')
  assert.equal(hatSichGeaendert(stand, { ...stand }), false)
  assert.equal(hatSichGeaendert(stand, {}), true, 'fehlende Felder sind leer und damit eine Änderung')
})

test('UX3h3/A: Zeilen-Listen — ein leerer Platz ist keine Änderung', () => {
  const stand = { zuordnungen: [{ gruppe: 'musik-leitung', rolle: 'Gruppenleiter' }] }
  assert.deepEqual(geaenderteFelder(stand, { zuordnungen: [
    { gruppe: 'musik-leitung', rolle: 'Gruppenleiter' }, { gruppe: '', rolle: '' },
  ] }), [], 'angehängter leerer Platz („Zuordnung ergänzen“) zählt nicht')
  assert.deepEqual(geaenderteFelder(stand, { zuordnungen: [
    { gruppe: 'musik-leitung', rolle: 'Gruppenleiter' },
  ] }), [], 'und das Entfernen des leeren Platzes auch nicht')
  assert.deepEqual(geaenderteFelder(stand, { zuordnungen: [
    { gruppe: 'musik-leitung', rolle: 'Gruppenleiter' }, { gruppe: 'chor', rolle: 'Gruppenleiter' },
  ] }), ['zuordnungen'], 'ein eingetippter Wert ist eine Änderung')
  assert.deepEqual(geaenderteFelder(stand, { zuordnungen: [] }), ['zuordnungen'],
    'eine GEFÜLLTE Zeile zu entfernen ist eine Änderung')
})

// ══════════════════════════════════════════════════════════════════════════
// B · Die Seiten, wirklich gemountet
// ══════════════════════════════════════════════════════════════════════════

/** Antworten der einzelnen Bereiche (Musterhausen-Form). */
const ANTWORTEN = {
  gemeinde_get_einstellungen: { gemeindename: 'Musterhausen', kurzname: 'MH', kontakt_email: 'buero@example.org',
    oeffentliche_adresse: 'https://musterhausen.example.org', willkommenstext: 'Willkommen',
    link_laufzeit_tage: 30, link_max_anmeldungen: 0, module: [], kurzname_: '', strasse: '',
    plz: '74072', ort: 'Heilbronn', telefon: '', website: '', zeitzone: 'Europe/Berlin',
    zeitzone_hinweis: '', logo_vorhanden: false },
  anmeldung_get_einstellungen: { oidc_aktiv: true, unbekannte_nutzer: 'abweisen',
    admin_ueber_gruppen: false, rollen: ['Gruppenleiter'], rollen_zuordnung: [] },
  datenschutz_get_texte: { einwilligung: 'Einwilligungstext', datenschutzerklaerung: 'Erklaerung',
    aufbewahrung: 'Aufbewahrung', veroeffentlicht: true, version: 3, veroeffentlichte_version: 3 },
  sicherung_get: { einstellungen: { automatisch: true, uhrzeit: '03:00', aufbewahrung_tage: 30 },
    sicherungen: [], ablage: { benutzbar: true, hinweis: '', vorhanden: 0 } },
  mailversand_get: { einstellungen: { host: 'mail.example.org', port: 587, sicherheit: 'starttls',
    benutzername: 'buero@example.org', absender: 'buero@example.org', absender_name: 'Musterhausen',
    timeout: 15, passwort_gesetzt: true, eingerichtet: true, geaendert: '2026-10-01T10:00' },
  meine_adresse: 'ich@example.org' },
  get_anmeldeformulare: { formulare: [] },
  get_wartende_konten: { konten: [] },
}

function antwortFuer(methode) {
  const kurz = String(methode).split('.').pop()
  const daten = ANTWORTEN[kurz]
  if (!daten) return { message: {} }
  if (kurz === 'mailversand_get') return { message: daten }
  return { message: daten }
}

function zuruecksetzen() {
  aufrufe.length = 0
  antwort = (methode) => antwortFuer(methode)
  document.body.innerHTML = ''
  globalThis.window.__DIakonosBOOT = { roles: ['System Manager'], is_admin: true }
}

/** Die drei Zusagen der Karte an EINEM Knopf prüfen. */
async function pruefeAblauf(host, aenderung, zurueck) {
  const knopf = speichernKnopf(host)
  assert.ok(knopf, 'kein „Speichern“-Knopf gefunden')
  assert.equal(knopf.disabled, true, 'frisch geladen → „Speichern“ muss gesperrt sein')
  assert.equal(knopf.getAttribute('aria-disabled'), 'true',
    'frisch geladen → aria-disabled fehlt (Vorlesehilfe sagt sonst „bedienbar“)')
  await aenderung()
  await warte(4)
  assert.equal(knopf.disabled, false, 'nach dem Tippen → „Speichern“ muss offen sein')
  assert.equal(knopf.getAttribute('aria-disabled'), null,
    'nach dem Tippen → aria-disabled muss weg sein')
  await zurueck()
  await warte(4)
  assert.equal(knopf.disabled, true, 'zurückgetippt → „Speichern“ muss wieder gesperrt sein')
  return knopf
}

test('UX3h3/B: Gemeinde — Speichern nur, wenn geändert', async () => {
  zuruecksetzen()
  const mod = await import(pathToFileURL(kompilieren(new URL('pages/einstellungen/Gemeinde.vue', SRC).pathname)).href)
  const { host, warnungen } = await mounten(mod.default)
  await warte(10)
  assert.equal(host.querySelectorAll('input').length > 3, true,
    'Formular nicht gerendert. Warnungen: ' + warnungen.slice(0, 2).join(' | '))
  // Das Feld wird über seinen LABEL-Text gefunden (nicht über den Wert): die
  // id vergibt DkField je Instanz, der Wert kommt erst mit dem Laden.
  const ort = [...host.querySelectorAll('input')].find((i) => {
    const label = host.querySelector(`label[for="${CSS.escape(i.id)}"]`)
    return label && /Ort$/.test(label.textContent.trim())
  })
  assert.ok(ort, 'Ort-Feld mit dem geladenen Wert fehlt')
  // BEFUND (UX3h3, gemessen): Das ORT-Feld zeigt nach dem Laden einen LEEREN
  // Wert, obwohl der Server „Heilbronn“ liefert — `<input v-bind="feld.feldProps"
  // v-model="ort">`: `feldProps` bringt einen `value`-Schlüssel (aus `wert`),
  // und Vue setzt beim Binden `value` NACH dem `v-model`. Bei allen anderen
  // Feldern ist `wert` nicht gesetzt, deshalb fällt es nur hier auf. Das ist
  // NICHT Gegenstand dieser Karte (sie ändert nur, WANN gespeichert werden
  // darf) und gehört als eigene Karte in die Feld-Bausteine.
  // Für diesen Test zählt das Feld, das den geladenen Wert WIRKLICH trägt:
  // die PLZ (auch sie kommt vom Server, ohne Sonderfall im Markup).
  const plzFeld = [...host.querySelectorAll('input')].find((i) => {
    const label = host.querySelector(`label[for="${CSS.escape(i.id)}"]`)
    return label && /^PLZ$/.test(label.textContent.trim())
  })
  assert.ok(plzFeld, 'PLZ-Feld fehlt')
  assert.equal(plzFeld.value, '74072', 'PLZ zeigt den geladenen Wert nicht')
  await pruefeAblauf(host,
    async () => { tippen(plzFeld, '74074') },
    async () => { tippen(plzFeld, '74072') })
  // Speichern: der Knopf ruft `speichern` — danach ist der Stand der neue.
  tippen(plzFeld, '74074')
  await warte(4)
  const knopf = speichernKnopf(host)
  assert.equal(knopf.disabled, false)
  // `knopf.click()` allein erreicht den Handler nicht (im jsdom gemessen) —
  // der Weg im Browser ist der Knopf IM Formular: `requestSubmit()`.
  const formular = host.querySelector('form')
  // Der Submit-Weg direkt am Formular (in jsdom der verlässliche Weg; die
  // Formular-Prüfung des Browsers ist hier ohnehin nicht aktiv).
  formular.dispatchEvent(new window.Event('submit', { bubbles: true, cancelable: true }))
  await warte(30)
  assert.ok(aufrufe.some(a => String(a.methode).endsWith('gemeinde_speichern')),
    'Speichern rief die API nicht: ' + aufrufe.map(a => a.methode).join(', '))
  assert.equal(speichernKnopf(host).disabled, true, 'nach dem Speichern → wieder gesperrt')
})

test('UX3h3/B: Anmeldung — Speichern nur, wenn geändert', async () => {
  zuruecksetzen()
  const mod = await import(pathToFileURL(kompilieren(new URL('pages/einstellungen/Anmeldung.vue', SRC).pathname)).href)
  const { host, warnungen } = await mounten(mod.default)
  await warte(10)
  const radios = [...host.querySelectorAll('input[type="radio"]')]
  assert.ok(radios.length >= 3, 'Modus-Auswahl fehlt. Warnungen: ' + warnungen.slice(0, 2).join(' | '))
  const zweiter = radios[1]
  await pruefeAblauf(host,
    async () => { zweiter.checked = true; zweiter.dispatchEvent(new window.Event('change', { bubbles: true })) },
    async () => { radios[0].checked = true; radios[0].dispatchEvent(new window.Event('change', { bubbles: true })) })
  // Haken „Verwaltungsrollen über Gruppen“ ist ebenfalls eine Änderung.
  const haken = host.querySelector('input[type="checkbox"]')
  assert.ok(haken, 'Haken fehlt')
  umschalten(haken, true)
  await warte(4)
  assert.equal(speichernKnopf(host).disabled, false, 'Haken gesetzt → Knopf offen')
})

test('UX3h3/B: Datenschutz-Texte — Speichern nur, wenn geändert', async () => {
  zuruecksetzen()
  const mod = await import(pathToFileURL(kompilieren(new URL('pages/einstellungen/DatenschutzTexte.vue', SRC).pathname)).href)
  const { host, warnungen } = await mounten(mod.default)
  await warte(10)
  const felder = [...host.querySelectorAll('textarea')]
  assert.equal(felder.length, 3, 'drei Texte erwartet. Warnungen: ' + warnungen.slice(0, 2).join(' | '))
  await pruefeAblauf(host,
    async () => { tippen(felder[1], 'Erklaerung, neu') },
    async () => { tippen(felder[1], 'Erklaerung') })
  // Veröffentlichungs-Haken zählt mit.
  const haken = host.querySelector('input[type="checkbox"]')
  umschalten(haken, false)
  await warte(4)
  assert.equal(speichernKnopf(host).disabled, false, 'Haken geändert → Knopf offen')
})

test('UX3h3/B: Datensicherung — Speichern nur, wenn geändert', async () => {
  zuruecksetzen()
  const mod = await import(pathToFileURL(kompilieren(new URL('pages/einstellungen/Datensicherung.vue', SRC).pathname)).href)
  const { host, warnungen } = await mounten(mod.default)
  await warte(10)
  const zeit = host.querySelector('input[type="time"]')
  assert.ok(zeit, 'Uhrzeit-Feld fehlt. Warnungen: ' + warnungen.slice(0, 2).join(' | '))
  await pruefeAblauf(host,
    async () => { tippen(zeit, '04:30') },
    async () => { tippen(zeit, '03:00') })
})

test('UX3h3/B: Mailversand — Speichern nur, wenn geändert (auch das Passwort zählt)', async () => {
  zuruecksetzen()
  const mod = await import(pathToFileURL(kompilieren(new URL('pages/einstellungen/Mailversand.vue', SRC).pathname)).href)
  const { host, warnungen } = await mounten(mod.default)
  await warte(10)
  const hostFeld = [...host.querySelectorAll('input')].find((i) => i.value === 'mail.example.org')
  assert.ok(hostFeld, 'Server-Feld fehlt. Warnungen: ' + warnungen.slice(0, 2).join(' | '))
  await pruefeAblauf(host,
    async () => { tippen(hostFeld, 'mail2.example.org') },
    async () => { tippen(hostFeld, 'mail.example.org') })
  // Ein eingetipptes Passwort ist eine Änderung, ein leeres nicht.
  const passwort = host.querySelector('input[type="password"]')
  assert.ok(passwort, 'Passwort-Feld fehlt')
  tippen(passwort, 'geheim')
  await warte(4)
  assert.equal(speichernKnopf(host).disabled, false, 'Passwort eingetippt → Knopf offen')
  tippen(passwort, '')
  await warte(4)
  assert.equal(speichernKnopf(host).disabled, true, 'Passwort geleert → wieder gesperrt')
})

test('UX3h3/B: Registrierung — Speichern nur, wenn geändert', async () => {
  zuruecksetzen()
  const mod = await import(pathToFileURL(kompilieren(new URL('pages/einstellungen/Registrierung.vue', SRC).pathname)).href)
  const { host, warnungen } = await mounten(mod.default)
  await warte(10)
  const zahl = host.querySelector('input[type="number"]')
  assert.ok(zahl, 'Zahlenfeld fehlt. Warnungen: ' + warnungen.slice(0, 2).join(' | '))
  await pruefeAblauf(host,
    async () => { tippen(zahl, '60') },
    async () => { tippen(zahl, '30') })
})

// ══════════════════════════════════════════════════════════════════════════
// C · Wächter: EINE Regel, überall benutzt, kein Verlassen-Dialog
// ══════════════════════════════════════════════════════════════════════════

const SEITEN = [
  'pages/einstellungen/Gemeinde.vue',
  'pages/einstellungen/Anmeldung.vue',
  'pages/einstellungen/DatenschutzTexte.vue',
  'pages/einstellungen/Datensicherung.vue',
  'pages/einstellungen/Mailversand.vue',
  'pages/einstellungen/Registrierung.vue',
]

test('UX3h3/C: jede Seite benutzt das gemeinsame Composable, keine eigene Vergleichslogik', () => {
  for (const datei of SEITEN) {
    const text = readFileSync(new URL(datei, SRC).pathname, 'utf8')
    assert.match(text, /from '\.\.\/\.\.\/composables\/useGeaendert\.js'/,
      `${datei}: useGeaendert nicht importiert (Kopie statt EINER Regel)`)
    assert.match(text, /useGeaendertStand\(\)/, `${datei}: kein useGeaendertStand()`)
    assert.match(text, /:disabled="!kannSpeichern"/,
      `${datei}: „Speichern“ ist nicht an „geändert“ gebunden`)
    assert.match(text, /aria-disabled/,
      `${datei}: aria-disabled fehlt (die Karte verlangt es ausdrücklich)`)
    assert.doesNotMatch(text, /JSON\.stringify\([^)]*\)\s*!==\s*JSON\.stringify/,
      `${datei}: eigener JSON-Vergleich statt der gemeinsamen Regel`)
    assert.doesNotMatch(text, /useVerlassenSchutz|beforeRouteLeave|onBeforeUnmount\([^)]*confirm/,
      `${datei}: Verlassen-Dialog ist NICHT Teil dieser Karte`)
  }
  const regel = readFileSync(new URL('composables/geaendert.mjs', SRC).pathname, 'utf8')
  assert.match(regel, /export function geaenderteFelder/, 'die gemeinsame Regel fehlt')
})

test('UX3h3/C: alle „Speichern“-Knöpfe der Einstellungen sind nach der Regel gesperrt', () => {
  // Kein Abschnitt darf beim alten „immer aktiv“ zurückbleiben: der Knopf
  // trägt `:disabled="!kannSpeichern"` — geprüft an ALLEN Seiten, die ein
  // „Speichern“ anbieten (RollenRechte hat keinen Formular-Speichern-Knopf,
  // sondern je Person einen Dialog — dort ist „nichts geändert“ ein anderer
  // Fall und nicht Teil dieser Karte).
  const verzeichnis = new URL('pages/einstellungen/', SRC).pathname
  for (const name of readdirSync(verzeichnis).filter((n) => n.endsWith('.vue'))) {
    const text = readFileSync(join(verzeichnis, name), 'utf8')
    if (!/>\s*Speichern\s*</.test(text) && !/^\s*Speichern\s*$/m.test(text)) continue
    if (name === 'RollenRechte.vue' || name === 'Gestaltung.vue') continue
    assert.match(text, /kannSpeichern/,
      `${name}: „Speichern“ ohne Änderungsprüfung (Karte UX3h3 offen)`)
  }
})
