/**
 * UX3h5 — Einstellungen: Lade- und Speicher-Tests nachreichen.
 *
 * Die Karte (aus dem Review von UX3h4) verlangt drei Dinge, die der
 * UX3h3-Test nicht abdeckte:
 *
 *   1. MOUNT-Tests „Server liefert Wert → Feld zeigt Wert“ für
 *      Datensicherung (Uhrzeit, Aufbewahrungstage), Datenschutz-Texte,
 *      Einstellungen/Registrierung und Anmeldung (Auswahlfeld der Rollen
 *      samt Zuordnungen).
 *   2. „Nach Speichern → Speichern-Knopf inaktiv“ für ALLE UX3h3-Seiten.
 *      Bisher prüfte das nur Gemeinde (ux3h3-… ~:345); Anmeldung,
 *      DatenschutzTexte, Datensicherung, Mailversand und Registrierung
 *      fehlten.
 *   3. `pages/Registrierung.vue`: die DkSelect in Zeile ~228 ist die
 *      Auswahl „Anmeldeformular“ (neuer Link). Vorher standen dort
 *      `value`/`onInput` aus DkField als DURCHREICH-Attribute —
 *      DkSelect nimmt aber `modelValue`, `value` gewinnt beim Binden und
 *      überschreibt die Auswahl. Jetzt: saubere Bindung (`:wert` /
 *      `@update:wert` bzw. `v-model`), `emptyValue` bleibt respektiert.
 *
 * VERFAHREN (wie ux3h3-speichern-nur-wenn-geaendert.test.mjs): echte Seiten
 * aus dem Quellbaum, per Vue-Compiler als ES-Modul neben den Baum gelegt,
 * `apiCall` über den Übersetzer auf eine Attrappe umgebogen — kein Netz,
 * keine Attrappe im Quellbaum. Die Seiten laufen mit ihren ECHTEN
 * Composables, damit die Kette Laden → Stand → Speichern gemessen wird.
 *
 * Lauf: node --test tests/ux3h5-einstellungen-laden-speichern.test.mjs  (cwd = frontend/)
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, mkdirSync, mkdtempSync, writeFileSync, rmSync, statSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, dirname, resolve, basename } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { JSDOM } from 'jsdom'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'

// ── DOM zuerst (Vue greift beim Import schon auf `document` zu) ────────────
const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
for (const schluessel of ['window', 'document', 'Node', 'Element', 'HTMLElement', 'Event',
  'MouseEvent', 'SVGElement', 'CSS', 'CustomEvent', 'FormData', 'HTMLInputElement',
  'HTMLSelectElement', 'HTMLTextAreaElement', 'requestAnimationFrame',
  'getComputedStyle', 'MutationObserver', 'KeyboardEvent', 'FocusEvent',
  'Document', 'ShadowRoot']) {
  globalThis[schluessel] = dom.window[schluessel]
}
globalThis.requestAnimationFrame = dom.window.requestAnimationFrame
  || ((fn) => setTimeout(() => fn(Date.now()), 0))

const Vue = await import('vue')
const VUE_URL = import.meta.resolve('vue')
const SRC_ROOT = new URL('../src/', import.meta.url)
const SRC = new URL('../src/diakonos/', import.meta.url)

const TMP = mkdtempSync(join(tmpdir(), 'ux3h5-'))
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

// ── SFC → ES-Modul (Verfahren aus ux3h3/ux2f2b, generisch für alle Tiefen) ─
const cache = new Map()
const umleitung = new Map([
  [pathToFileURL(SRC_ROOT.pathname + 'diakonos/composables/useApi.js').href,
    pathToFileURL(apiDatei).href],
])

function aufgeloest(abs) {
  const kandidaten = [abs, abs + '.mjs', abs + '.js', abs + '/index.mjs']
  for (const k of kandidaten) {
    try { if (statSync(k).isFile()) return k } catch { /* weiter */ }
  }
  throw new Error('nicht gefunden: ' + abs)
}

/**
 * Kommentare ausblenden (Inhalt wird durch Leerzeichen ersetzt, Zeichenzahl
 * bleibt) — sonst hält der Umschreiber ein Import-BEISPIEL im Kommentar
 * (`// import { x } from './selbst.mjs'`) für einen echten Import.
 *
 * Der Durchlauf ist ein kleiner Zustandsautomat, weil `/` im Quelltext drei
 * Bedeutungen hat: Kommentar (`//`, `/*`), Division und Regex-Literal
 * (`/\\/api/`). Ohne die Regex-Erkennung würde `//` INNERHALB eines Regex als
 * Zeilenkommentar gelesen und die restliche Zeile gelöscht → der umgeschriebene
 * Code wäre kaputt („Invalid regular expression: missing /“).
 */
function ohneKommentare(text) {
  let ergebnis = ''
  let i = 0
  // Nach diesen Zeichen beginnt ein Regex-Literal, nach allen anderen eine
  // Division. Grobe, für Quelltext ausreichende Heuristik.
  const vorRegex = /[=(,:[!&|?{};+\-*%<>~^]$/
  while (i < text.length) {
    const z = text[i]
    const naechstes = text[i + 1]
    if (z === '/' && naechstes === '/') {
      while (i < text.length && text[i] !== '\n') { ergebnis += ' '; i += 1 }
      continue
    }
    if (z === '/' && naechstes === '*') {
      ergebnis += '  '
      i += 2
      while (i < text.length && !(text[i] === '*' && text[i + 1] === '/')) {
        ergebnis += text[i] === '\n' ? '\n' : ' '
        i += 1
      }
      if (i < text.length) { ergebnis += '  '; i += 2 }
      continue
    }
    if (z === "'" || z === '"' || z === '`') {
      let j = i + 1
      while (j < text.length && text[j] !== z) {
        if (text[j] === '\\') j += 1
        j += 1
      }
      const bis = Math.min(j + 1, text.length)
      ergebnis += text.slice(i, bis)
      i = bis
      continue
    }
    if (z === '/' && vorRegex.test(ergebnis.replace(/\s+$/, '').slice(-1))) {
      // Regex-Literal bis zum unescapten `/` außerhalb einer Zeichenklasse.
      let j = i + 1
      let inKlasse = false
      while (j < text.length && text[j] !== '\n') {
        const c = text[j]
        if (c === '\\') { j += 2; continue }
        if (c === '[') inKlasse = true
        else if (c === ']') inKlasse = false
        else if (c === '/' && !inKlasse) { j += 1; break }
        j += 1
      }
      ergebnis += text.slice(i, j)
      i = j
      continue
    }
    ergebnis += z
    i += 1
  }
  return ergebnis
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

  // Eintrag VOR dem Ersetzen setzen: der Umschreiber steigt rekursiv in die
  // Importe ab — ohne Eintrag läuft ein Selbst-Import oder ein Zyklus
  // (A → B → A) endlos in die Tiefe („Maximum call stack size exceeded“).
  cache.set(abs, ziel)

  // Nur im Code suchen, nicht in Kommentaren (Import-Beispiele in der Doku).
  const code = ohneKommentare(quanten.join('\n')).replace(
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
      // Fremdpaket (z. B. `qrcode-generator`): im Quellbaum auflösen, damit
      // die Kopie unter TMP es findet (dort gibt es kein `node_modules`).
      try {
        return `from '${import.meta.resolve(spec, pathToFileURL(quellDatei).href)}'`
      } catch {
        return `from '${spec}'`
      }
    },
  )
  writeFileSync(ziel, code)
  return ziel
}

const tick = () => new Promise((loese) => setTimeout(loese, 0))
const warte = async (n = 6) => { for (let i = 0; i < n; i += 1) await tick() }

function tippen(element, wert) {
  element.value = wert
  element.dispatchEvent(new window.Event('input', { bubbles: true }))
}
/** Auswahlfeld bedienen: `input` UND `change` (DkSelect hört auf `change`). */
function waehlen(element, wert) {
  element.value = wert
  element.dispatchEvent(new window.Event('change', { bubbles: true }))
  element.dispatchEvent(new window.Event('input', { bubbles: true }))
}

async function mounten(baustein, eigenschaften = {}) {
  const host = document.createElement('div')
  document.body.appendChild(host)
  const warnungen = []
  const app = Vue.createApp({
    components: { Seite: baustein },
    template: '<Seite v-bind="eigenschaften" />',
    data: () => ({ eigenschaften }),
  })
  app.config.warnHandler = (m) => warnungen.push(m)
  app.config.errorHandler = (e) => warnungen.push(String(e && e.message))
  const vm = app.mount(host)
  await warte(10)
  host.__vm = vm
  return { host, app, vm, warnungen }
}

/** Der „Speichern“-Knopf der Seite. */
function speichernKnopf(host) {
  return [...host.querySelectorAll('button')]
    .find((b) => /^\s*Speichern/.test((b.textContent || '').trim()))
}

/** Absenden — im jsdom der verlässliche Weg (Submit am Formular). */
function absenden(host) {
  const formular = host.querySelector('form')
  assert.ok(formular, 'Formular fehlt')
  formular.dispatchEvent(new window.Event('submit', { bubbles: true, cancelable: true }))
}

/**
 * Die Zusage der Karte: nach erfolgreichem Speichern ist der Knopf wieder
 * gesperrt (und `aria-disabled` zurück). Geprüft an EINER Seite.
 */
async function pruefeNachSpeichern(host, seite, apiEnde) {
  const knopf = speichernKnopf(host)
  assert.ok(knopf, seite + ': kein „Speichern“-Knopf gefunden')
  assert.equal(knopf.disabled, false, seite + ': Knopf muss vor dem Speichern offen sein')
  absenden(host)
  await warte(30)
  assert.ok(aufrufe.some((a) => String(a.methode).endsWith(apiEnde)),
    seite + ': Speichern rief ' + apiEnde + ' nicht: ' + aufrufe.map((a) => a.methode).join(', '))
  const nachher = speichernKnopf(host)
  assert.equal(nachher.disabled, true, seite + ': nach dem Speichern → wieder gesperrt')
  assert.equal(nachher.getAttribute('aria-disabled'), 'true',
    seite + ': nach dem Speichern → aria-disabled fehlt (Vorlesehilfe sagt sonst „bedienbar“)')
}

// ══════════════════════════════════════════════════════════════════════════
// Antworten des Servers (Musterhausen-Form)
// ══════════════════════════════════════════════════════════════════════════

const ANTWORTEN = {
  gemeinde_get_einstellungen: {
    gemeindename: 'Musterhausen', kurzname: 'MH', kontakt_email: 'buero@example.org',
    oeffentliche_adresse: 'https://musterhausen.example.org', willkommenstext: 'Willkommen',
    link_laufzeit_tage: 30, link_max_anmeldungen: 0, module: [], strasse: 'Kirchplatz 1',
    plz: '74072', ort: 'Heilbronn', telefon: '', website: '', zeitzone: 'Europe/Berlin',
    zeitzone_hinweis: '', logo_vorhanden: false,
  },
  // Rollen wie der Server sie liefert (Administrator-Rollen zuerst) — eine
  // davon steht NICHT in der festen Liste der Oberfläche und ist deshalb die
  // Sonde für „Auswahlfeld zeigt die Zuordnung des Servers“.
  anmeldung_get_einstellungen: {
    oidc_aktiv: true, unbekannte_nutzer: 'als_gast_anlegen', admin_ueber_gruppen: false,
    rollen: ['System Manager', 'Mitgliederadministrator', 'Mitglied', 'Ressourcenmoderator'],
    rollen_zuordnung: [
      { gruppe: 'musik-leitung', rolle: 'Mitgliederadministrator', idx: 1 },
      { gruppe: 'kirchenvorstand', rolle: 'Mitglied', idx: 2 },
    ],
  },
  datenschutz_get_texte: {
    einwilligung: 'Einwilligungstext', datenschutzerklaerung: 'Erklaerung',
    aufbewahrung: 'Aufbewahrung', veroeffentlicht: true, version: 3,
    veroeffentlichte_version: 3,
  },
  sicherung_get: {
    einstellungen: { automatisch: true, uhrzeit: '04:15', aufbewahrung_tage: 21 },
    sicherungen: [], ablage: { benutzbar: true, hinweis: '', vorhanden: 0 },
  },
  sicherung_einstellungen_speichern: { einstellungen: { automatisch: true, uhrzeit: '04:15', aufbewahrung_tage: 21 } },
  sicherung_speichern: { einstellungen: { automatisch: true, uhrzeit: '04:15', aufbewahrung_tage: 21 } },
  gemeinde_setze_linkvorgaben: { link_laufzeit_tage: 30, link_max_anmeldungen: 0 },
  mailversand_get: {
    einstellungen: { host: 'mail.example.org', port: 587, sicherheit: 'starttls',
      benutzername: 'buero@example.org', absender: 'buero@example.org',
      absender_name: 'Musterhausen', timeout: 15, passwort_gesetzt: true,
      eingerichtet: true, geaendert: '2026-10-01T10:00' },
  },
  meine_adresse: 'ich@example.org',
  get_anmeldeformulare: { formulare: [] },
  get_wartende_konten: { konten: [] },
}

function antwortFuer(methode) {
  const kurz = String(methode).split('.').pop()
  const daten = ANTWORTEN[kurz]
  if (!daten) return { message: {} }
  return { message: daten }
}

function zuruecksetzen() {
  aufrufe.length = 0
  antwort = (methode) => antwortFuer(methode)
  document.body.innerHTML = ''
  globalThis.window.__DIakonosBOOT = { roles: ['System Manager'], is_admin: true }
}

/** Feld über seinen LABEL-Text finden (die id vergibt DkField je Instanz). */
function feldMitLabel(host, muster, auswahl = 'input, textarea') {
  return [...host.querySelectorAll(auswahl)].find((i) => {
    const label = host.querySelector(`label[for="${CSS.escape(i.id)}"]`)
    return label && muster.test(label.textContent.trim())
  })
}

// ══════════════════════════════════════════════════════════════════════════
// 1 · mount: „Server liefert Wert → Feld zeigt Wert“
// ══════════════════════════════════════════════════════════════════════════

test('UX3h5/1: Datensicherung — Uhrzeit und Aufbewahrungstage zeigen die Serverwerte', async () => {
  zuruecksetzen()
  const mod = await import(pathToFileURL(kompilieren(new URL('pages/einstellungen/Datensicherung.vue', SRC).pathname)).href)
  const { host, warnungen } = await mounten(mod.default)
  await warte(10)
  const zeit = host.querySelector('input[type="time"]')
  assert.ok(zeit, 'Uhrzeit-Feld fehlt. Warnungen: ' + warnungen.slice(0, 2).join(' | '))
  assert.equal(zeit.value, '04:15', 'Uhrzeit zeigt den geladenen Wert nicht')
  const tage = feldMitLabel(host, /aufbewahren für/i)
  assert.ok(tage, 'Feld „Sicherungen aufbewahren für“ fehlt')
  assert.equal(String(tage.value), '21', 'Aufbewahrungstage zeigen den geladenen Wert nicht')
  const haken = host.querySelector('input[type="checkbox"]')
  assert.equal(haken.checked, true, '„Täglich automatisch sichern“ zeigt den geladenen Wert nicht')
  // Und der Beweis, dass der Wert aus der ANTWORT kommt: der nächste Lauf
  // nennt die geladene Uhrzeit (nicht den Vorgabewert 03:00).
  assert.match(host.textContent, /04:15 Uhr/, 'nächster Lauf nennt nicht die geladene Uhrzeit')
})

test('UX3h5/1: DatenschutzTexte — alle drei Texte zeigen die Serverwerte', async () => {
  zuruecksetzen()
  const mod = await import(pathToFileURL(kompilieren(new URL('pages/einstellungen/DatenschutzTexte.vue', SRC).pathname)).href)
  const { host, warnungen } = await mounten(mod.default)
  await warte(10)
  const felder = [...host.querySelectorAll('textarea')]
  assert.equal(felder.length, 3, 'drei Texte erwartet. Warnungen: ' + warnungen.slice(0, 2).join(' | '))
  assert.deepEqual(felder.map((f) => f.value),
    ['Einwilligungstext', 'Erklaerung', 'Aufbewahrung'], 'Texte zeigen die geladenen Werte nicht')
  const haken = host.querySelector('input[type="checkbox"]')
  assert.equal(haken.checked, true, 'Veröffentlichungs-Haken zeigt den geladenen Wert nicht')
  assert.match(host.textContent, /Fassung 3/, 'Fassungszähler zeigt den geladenen Wert nicht')
})

test('UX3h5/1: Registrierung — Gültigkeitsdauer und Höchstzahl zeigen die Serverwerte', async () => {
  zuruecksetzen()
  const mod = await import(pathToFileURL(kompilieren(new URL('pages/einstellungen/Registrierung.vue', SRC).pathname)).href)
  const { host, warnungen } = await mounten(mod.default)
  await warte(10)
  const dauer = feldMitLabel(host, /Gültigkeitsdauer/i)
  assert.ok(dauer, 'Feld „Gültigkeitsdauer (Tage)“ fehlt. Warnungen: ' + warnungen.slice(0, 2).join(' | '))
  assert.equal(String(dauer.value), '30', 'Gültigkeitsdauer zeigt den geladenen Wert nicht')
  const hoechst = feldMitLabel(host, /Höchstzahl Anmeldungen/i)
  assert.ok(hoechst, 'Feld „Höchstzahl Anmeldungen“ fehlt')
  assert.equal(String(hoechst.value), '0', 'Höchstzahl zeigt den geladenen Wert nicht')
})

test('UX3h5/1: Anmeldung — Modus, Haken und die Zuordnungen des Servers', async () => {
  zuruecksetzen()
  const mod = await import(pathToFileURL(kompilieren(new URL('pages/einstellungen/Anmeldung.vue', SRC).pathname)).href)
  const { host, warnungen } = await mounten(mod.default)
  await warte(10)
  // Modus: der geladene Wert „als_gast_anlegen“ ist der gewählte Radio-Knopf.
  const radios = [...host.querySelectorAll('input[type="radio"]')]
  assert.equal(radios.length, 3, 'Modus-Auswahl fehlt. Warnungen: ' + warnungen.slice(0, 2).join(' | '))
  assert.deepEqual(radios.map((r) => r.checked), [false, true, false],
    'Modus-Radio zeigt nicht den geladenen Wert „als_gast_anlegen“')
  // Haken: `admin_ueber_gruppen: false` → nicht gesetzt.
  const haken = host.querySelector('input[type="checkbox"]')
  assert.equal(haken.checked, false, 'Haken „Verwaltungsrollen über Gruppen“ zeigt nicht den Serverwert')
  // Zuordnungen: zwei Zeilen, Gruppe UND Auswahlfeld der Rollen.
  const gruppen = [...host.querySelectorAll('input:not([type])')].map((i) => i.value)
  assert.deepEqual(gruppen, ['musik-leitung', 'kirchenvorstand'],
    'Gruppen der geladenen Zuordnungen stehen nicht in den Feldern')
  const auswahl = [...host.querySelectorAll('select')]
  assert.equal(auswahl.length, 2, 'zwei Rollen-Auswahlfelder erwartet')
  assert.deepEqual(auswahl.map((s) => s.value), ['Mitgliederadministrator', 'Mitglied'],
    'Rollen-Auswahl zeigt die geladenen Zuordnungen nicht')
  // Die Auswahl trägt die Serverliste (auch eine Rolle, die NUR der Server
  // kennt) und steht auf dem geladenen Wert.
  const optionen = [...auswahl[0].querySelectorAll('option')].map((o) => o.value)
  for (const rolle of ['System Manager', 'Mitgliederadministrator', 'Mitglied', 'Ressourcenmoderator']) {
    assert.ok(optionen.includes(rolle), 'Rolle „' + rolle + '“ fehlt in der Auswahl')
  }
  // Ein leerer Platzhalter ist gewählt-fähig, aber nicht die Auswahl.
  assert.ok(optionen.includes(''), '„Bitte wählen“ fehlt in der Auswahl')
})

// ══════════════════════════════════════════════════════════════════════════
// 2 · „Nach Speichern → Speichern-Knopf inaktiv“ für ALLE UX3h3-Seiten
// ══════════════════════════════════════════════════════════════════════════

test('UX3h5/2: Anmeldung — nach dem Speichern ist „Speichern“ wieder gesperrt', async () => {
  zuruecksetzen()
  const mod = await import(pathToFileURL(kompilieren(new URL('pages/einstellungen/Anmeldung.vue', SRC).pathname)).href)
  const { host } = await mounten(mod.default)
  await warte(10)
  const radios = [...host.querySelectorAll('input[type="radio"]')]
  radios[2].checked = true
  radios[2].dispatchEvent(new window.Event('change', { bubbles: true }))
  await warte(4)
  await pruefeNachSpeichern(host, 'Anmeldung', 'anmeldung_speichern')
})

test('UX3h5/2: DatenschutzTexte — nach dem Speichern ist „Speichern“ wieder gesperrt', async () => {
  zuruecksetzen()
  const mod = await import(pathToFileURL(kompilieren(new URL('pages/einstellungen/DatenschutzTexte.vue', SRC).pathname)).href)
  const { host } = await mounten(mod.default)
  await warte(10)
  const felder = [...host.querySelectorAll('textarea')]
  tippen(felder[1], 'Erklaerung, neu')
  await warte(4)
  await pruefeNachSpeichern(host, 'DatenschutzTexte', 'datenschutz_speichern')
})

test('UX3h5/2: Datensicherung — nach dem Speichern ist „Speichern“ wieder gesperrt', async () => {
  zuruecksetzen()
  const mod = await import(pathToFileURL(kompilieren(new URL('pages/einstellungen/Datensicherung.vue', SRC).pathname)).href)
  const { host } = await mounten(mod.default)
  await warte(10)
  const zeit = host.querySelector('input[type="time"]')
  tippen(zeit, '05:00')
  await warte(4)
  // Welchen Endpunkt die Seite ruft, steht im Composable — geprüft wird, dass
  // ein Sicherungs-Endpunkt zum Speichern gerufen wurde.
  await pruefeNachSpeichern(host, 'Datensicherung', 'sicherung_einstellungen_speichern')
})

test('UX3h5/2: Mailversand — nach dem Speichern ist „Speichern“ wieder gesperrt', async () => {
  zuruecksetzen()
  const mod = await import(pathToFileURL(kompilieren(new URL('pages/einstellungen/Mailversand.vue', SRC).pathname)).href)
  const { host } = await mounten(mod.default)
  await warte(10)
  const hostFeld = [...host.querySelectorAll('input')].find((i) => i.value === 'mail.example.org')
  assert.ok(hostFeld, 'Server-Feld fehlt')
  tippen(hostFeld, 'mail2.example.org')
  await warte(4)
  await pruefeNachSpeichern(host, 'Mailversand', 'mailversand_speichern')
})

test('UX3h5/2: Registrierung — nach dem Speichern ist „Speichern“ wieder gesperrt', async () => {
  zuruecksetzen()
  const mod = await import(pathToFileURL(kompilieren(new URL('pages/einstellungen/Registrierung.vue', SRC).pathname)).href)
  const { host } = await mounten(mod.default)
  await warte(10)
  const dauer = feldMitLabel(host, /Gültigkeitsdauer/i)
  tippen(dauer, '60')
  await warte(4)
  await pruefeNachSpeichern(host, 'Registrierung', 'gemeinde_setze_linkvorgaben')
})

// ══════════════════════════════════════════════════════════════════════════
// 3 · Registrierung.vue — DkSelect richtig gebunden (Auswahl „Anmeldeformular“)
// ══════════════════════════════════════════════════════════════════════════

test('UX3h5/3: Registrierung.vue — DkSelect bekommt keinen `value`/`onInput`-Durchreicher', () => {
  const text = readFileSync(new URL('pages/Registrierung.vue', SRC).pathname, 'utf8')
  const treffer = [...text.matchAll(/<DkSelect\b[^>]*>/gs)]
  assert.ok(treffer.length >= 3, 'DkSelect-Aufrufe in Registrierung.vue fehlen (' + treffer.length + ')')
  for (const [tag] of treffer) {
    assert.doesNotMatch(tag, /v-bind="feld\.feldProps"/,
      'DkSelect mit `v-bind="feld.feldProps"`: `value` überschreibt `modelValue` — Auswahl zeigt den Serverwert nicht')
    assert.doesNotMatch(tag, /(^|\s):value=|\svalue=/,
      'DkSelect mit `value`: DkSelect bindet `modelValue` (kein `value`)')
    assert.doesNotMatch(tag, /@input=|\sonInput=/,
      'DkSelect mit `input`-Zuhörer: DkSelect meldet `update:modelValue` bei `change`')
  }
})

test('UX3h5/3: Registrierung.vue — „Anmeldeformular“ am Link zeigt die geladene Auswahl und meldet die Wahl', async () => {
  zuruecksetzen()
  // Ein vorhandenes Formular, damit es im Auswahlfeld etwas zu wählen gibt.
  ANTWORTEN.get_anmeldeformulare = {
    formulare: [
      { name: 'formular-1', bezeichnung: 'Standard-Anmeldung' },
      { name: 'formular-2', bezeichnung: 'Gemeindefest' },
    ],
  }
  antwort = (methode) => {
    const kurz = String(methode).split('.').pop()
    if (kurz === 'get_anmeldeformulare') return { message: ANTWORTEN.get_anmeldeformulare }
    return antwortFuer(methode)
  }
  const mod = await import(pathToFileURL(kompilieren(new URL('pages/Registrierung.vue', SRC).pathname)).href)
  // UX3j (Entwurf A3): Der Unterbereich kommt aus der ADRESSE und wird als
  // Eigenschaft übergeben (`#/personen/anfragen/links`) — die Seite bringt
  // keinen eigenen Umschalter mehr mit. „Neuer Link“ steht im Seitenkopf des
  // Rahmens; hier wird dieselbe Funktion direkt gerufen (defineExpose).
  const { host, warnungen, vm } = await mounten(mod.default, { unterbereich: 'links' })
  await warte(30)
  const neuLink = [...host.querySelectorAll('button')]
    .find((b) => /Neuer Link/.test((b.textContent || '').trim()))
  if (neuLink) {
    neuLink.dispatchEvent(new window.MouseEvent('click', { bubbles: true }))
  } else {
    // Ohne Rahmen-Kopf: die bereitgestellte Funktion öffnet denselben Dialog.
    // (Der Seiten-Proxy liegt über der Komponenten-Kette, nicht am Wurzelknoten.)
    const proxy = vm.$refs?.Seite ?? vm.$.subTree?.component?.proxy
    assert.ok(proxy && typeof proxy.linkOeffnen === 'function', 'linkOeffnen fehlt (defineExpose)',
      'Warnungen: ' + warnungen.slice(0, 2).join(' | '))
    proxy.linkOeffnen()
  }
  await warte(15)

  // Das Auswahlfeld steht im Dialog bei „Anmeldeformular“.
  // Der Dialog wird per `Teleport` an `body` gehängt — dort suchen, nicht im
  // Wurzelelement der Seite. DkSelect bietet die Optionen als `value`/`label`
  // an; jsdom liefert am `<option>` keinen Textinhalt, deshalb über `value`.
  const auswahl = [...document.body.querySelectorAll('select')]
    .find((s) => [...s.querySelectorAll('option')].some((o) => o.value === 'formular-2'))
  assert.ok(auswahl, 'Auswahlfeld „Anmeldeformular“ fehlt im Dialog „Neuer Link“')

  // Auswahl ändern → DkSelect meldet `update:modelValue`, die Wahl bleibt
  // stehen (vorher überschrieb der durchgereichte `value` sie sofort).
  waehlen(auswahl, 'formular-2')
  await warte(6)
  assert.equal(auswahl.value, 'formular-2', 'die gewählte Option bleibt nicht stehen')
  // Gegenprobe: zurücksetzen auf „Keines“ (emptyValue) hält ebenfalls.
  waehlen(auswahl, '')
  await warte(6)
  assert.equal(auswahl.value, '', 'die leere Auswahl (emptyValue) bleibt nicht stehen')
})

// ══════════════════════════════════════════════════════════════════════════
// 4 · Wächter: ALLE UX3h3-Seiten haben jetzt einen Speicher-Nachweis
// ══════════════════════════════════════════════════════════════════════════

test('UX3h5/4: jeder UX3h3-Speicherknopf hat einen Nachweis „nach Speichern gesperrt“', async () => {
  const seiten = [
    'Gemeinde', 'Anmeldung', 'DatenschutzTexte', 'Datensicherung', 'Mailversand', 'Registrierung',
  ]
  // (a) In DIESER Datei: je Seite ein Test mit `pruefeNachSpeichern`.
  const eigenerText = readFileSync(fileURLToPath(import.meta.url), 'utf8')
  for (const seite of seiten.filter((s) => s !== 'Gemeinde')) {
    assert.match(eigenerText, new RegExp(`pruefeNachSpeichern\\(host, '${seite}'`),
      `Test „nach Speichern gesperrt“ für ${seite} fehlt`)
  }
  // (b) Gemeinde steht im UX3h3-Test (er wird nicht doppelt geführt) — dort
  // muss die Zusage weiter stehen.
  const ux3h3 = readFileSync(join(dirname(fileURLToPath(import.meta.url)),
    'ux3h3-speichern-nur-wenn-geaendert.test.mjs'), 'utf8')
  assert.match(ux3h3, /nach dem Speichern → wieder gesperrt/,
    'Gemeinde: Nachweis „nach Speichern gesperrt“ fehlt im UX3h3-Test')
  // (c) Und jede dieser Seiten hat auch einen Lade-Nachweis (Punkt 1).
  for (const seite of ['Datensicherung', 'DatenschutzTexte', 'Registrierung', 'Anmeldung']) {
    assert.match(eigenerText, new RegExp(`UX3h5/1: ${seite}`, 'i'),
      `Lade-Test „Server liefert Wert → Feld zeigt Wert“ für ${seite} fehlt`)
  }
})

// ══════════════════════════════════════════════════════════════════════════
// 5 · Werkzeug: Import-Umschreiber ohne Endlosrekursion
// ══════════════════════════════════════════════════════════════════════════

/**
 * MT-3c: Der Umschreiber suchte die Modulangabe über den GANZEN Dateitext,
 * also auch über Kommentare, und setzte den Cache-Eintrag erst NACH dem
 * rekursiven Abstieg. Ein Import-Beispiel im Kommentar oder ein Zyklus
 * (A → B → A) lief deshalb endlos in die Tiefe („Maximum call stack size
 * exceeded“) — so brach MT-3 den Build.
 *
 * Geprüft: eine Hilfsdatei mit Import-Beispielen in Zeilen- und
 * Blockkommentaren (auch auf sich selbst) und ein Zyklus A → B → A lassen
 * sich laden und liefern ihre Werte.
 */
test('UX3h5/5: Import-Beispiele in Kommentaren und ein Zyklus A→B→A laden ohne Rekursion', async () => {
  const huelle = join(SRC_ROOT.pathname, 'zyklusprobe-mt3c')
  mkdirSync(huelle, { recursive: true })
  const a = join(huelle, 'a.mjs')
  const b = join(huelle, 'b.mjs')

  writeFileSync(a, [
    '// Beispiel: import { ay } from "./a.mjs"  (Selbst-Import im Kommentar)',
    '/* Und als Block:',
    "   import { ay } from './a.mjs'",
    '   import { by } from "./b.mjs"',
    ' */',
    "const pfad = 'http://example.invalid/a' // „//“ in einer Zeichenkette",
    "import { by } from './b.mjs'",
    'export const ay = 1',
    'export const text = pfad',
  ].join('\n'))
  writeFileSync(b, [
    "// import { ay } from './a.mjs'",
    "import { ay } from './a.mjs'",
    'export const by = () => ay + 1',
  ].join('\n'))

  const zielA = kompilieren(a)
  const modul = await import(pathToFileURL(zielA).href)
  assert.equal(modul.ay, 1, 'A lädt')
  assert.equal(modul.text, 'http://example.invalid/a',
    'das „//“ in einer Zeichenkette wurde nicht als Kommentar behandelt')

  const zielB = kompilieren(b)
  const modulB = await import(pathToFileURL(zielB).href)
  assert.equal(modulB.by(), 2, 'B lädt und sieht A (Zyklus A→B→A aufgelöst)')
  assert.notEqual(zielA, zielB, 'B hat eine eigene Kopie')
  assert.equal(cache.get(a), zielA, 'Cache-Eintrag zeigt auf die Ausgabe von A')
  assert.equal(cache.get(b), zielB, 'Cache-Eintrag zeigt auf die Ausgabe von B')

  // Nur für diesen Lauf angelegte Hilfsdateien wieder wegräumen.
  rmSync(huelle, { recursive: true, force: true })
})

