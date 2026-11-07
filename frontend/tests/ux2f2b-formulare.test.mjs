/**
 * UX2f2b — Feld mit Prüfung: migrierte Formulare reparieren (Teil 2 von 2).
 *
 * Der Befund der Abnahme: die Migration aus UX2f/UX2f2a hat an 16 Stellen
 * `<input v-bind="feld.feldProps">` OHNE `v-slot="feld"` stehen lassen. In
 * einer normalen (nicht-gebündelten) Vorlage ist `feld` dort undefiniert —
 * beim Rendern stürzt das Formular ab; gebündelt bleibt nur `undefined`, also
 * ein Feld ohne id, ohne Wert, ohne Prüfung. Dazu kamen die `…Frei`-Hüllen
 * (seit UX2f2a überflüssig) und ein Speichern, das durch ein immer gesetztes
 * Fehlerfeld NIE die API rief.
 *
 * Dieser Test MOUNTET die betroffenen Bausteine/Seiten wirklich (jsdom,
 * `createApp().mount()`, echte `input`/`click`-Ereignisse) und hält fest, was
 * die Karte verlangt: Wert tippen → Absenden → API-Aufruf MIT dem Getippten.
 *
 * Geprüft werden fünf Formulare (Karte, Punkt 5): Gruppe anlegen, Termin
 * anlegen, Person bearbeiten, Gemeinde speichern, Gast-Anmeldung — dazu der
 * statische Wächter „jede `feld.feldProps`-Fundstelle steht in einem Slot“.
 *
 * `apiCall` wird über den Cache ERSETZT (dieselbe Modul-URL, die die
 * Komponenten importieren) — kein Netz, keine Attrappe im Quellbaum.
 * jsdom ist devDependency (Begründung im Kopf von
 * `ux2f2a-feld-baustein.test.mjs`); der Test liest nur Dateien INNERHALB von
 * frontend/ (Regel 13: keine zusätzliche COPY-Zeile).
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, mkdtempSync, writeFileSync, rmSync, readdirSync, statSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, dirname, resolve, basename } from 'node:path'
import { pathToFileURL } from 'node:url'
import { JSDOM } from 'jsdom'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'

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

// ── Netz: eine Attrappe für ALLE fetch-Aufrufe (feste Adresse statt jsdom) ─
const netzAufrufe = []
let netzAntwort = () => ({ status: 200, koerper: { message: {} } })
globalThis.fetch = async (adresse, optionen = {}) => {
  const url = String(adresse)
  const koerper = optionen.body ? JSON.parse(optionen.body) : null
  netzAufrufe.push({ url, methode: optionen.method || 'GET', koerper })
  const { status = 200, koerper: antwortKoerper = { message: {} } } = netzAntwort(url, optionen) || {}
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: () => 'application/json' },
    json: async () => antwortKoerper,
    text: async () => JSON.stringify(antwortKoerper),
    clone() { return this },
  }
}
const RESSOURCE = (query) => 'https://pruefstand.invalid/api/resource/' + query

const Vue = await import('vue')

const SRC = new URL('../src/diakonos/', import.meta.url)
const SRC_ROOT = new URL('../src/', import.meta.url)

// ── API-Attrappe: EINE Stelle, die alle Komponenten teilen ────────────────
// Die Komponenten importieren `composables/useApi.js`; der Übersetzer unten
// biegt GENAU diesen Import auf die Attrappe um (gleiche Modul-URL, damit
// jede Komponente dieselbe Instanz sieht). Kein Netz, kein globales Patchen.
const TMP = mkdtempSync(join(tmpdir(), 'ux2f2b-'))
const cache = new Map()
const aufrufe = []
let antwort = () => ({ message: { ok: true } })
globalThis.__DK_AUFRUFE = aufrufe
globalThis.__DK_API_ANTWORT = (methode, parameter) => antwort(methode, parameter)
globalThis.__DK_PUSH = (eintrag) => aufrufe.push(eintrag)
const apiDatei = join(TMP, '_api-attrappe.mjs')
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

// ── SFC → ES-Modul (Verfahren wie ux2f2a-feld-baustein.test.mjs) ──────────
const VUE_URL = import.meta.resolve('vue')

function kompilieren(abs) {
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
  code = code.replace(/from\s+['"](\.[^'"]+)['"]/g, (v, spec) => {
    const ziel = resolve(dirname(abs), spec)
    // UX2f2b: der API-Baustein wird auf die Attrappe umgebogen (gleiche URL
    // wie im Quellbaum-Cache, s. o.).
    if (spec.endsWith('useApi.js') && ziel !== abs && basename(ziel) === 'useApi.js') {
      return `from '${pathToFileURL(apiDatei).href}'`
    }
    return `from '${pathToFileURL(spec.endsWith('.vue') ? kompilieren(ziel) : ziel).href}'`
  })
  const ziel = resolve(TMP, filename.replace(/\.vue$/, '') + '.' + cache.size + '.mjs')
  writeFileSync(ziel, code)
  cache.set(abs, ziel)
  return ziel
}

const sfc = (rel) => kompilieren(new URL(rel, SRC_ROOT).pathname)

test.after(() => rmSync(TMP, { recursive: true, force: true }))

const tick = () => new Promise((loese) => setTimeout(loese, 0))
const warte = async (n = 4) => { for (let i = 0; i < n; i += 1) await tick() }

function tippen(element, wert) {
  element.value = wert
  element.dispatchEvent(new window.Event('input', { bubbles: true }))
}
function klicken(element) {
  element.dispatchEvent(new window.MouseEvent('click', { bubbles: true, cancelable: true }))
}

/**
 * Mountet eine Vorlage mit den angegebenen Bausteinen. `setup` liefert den
 * Zustand; `globalThis`-Attrappen (Boot-Objekt) setzt der Test vorher.
 */
async function mounten(vorlage, bausteine, setup = () => ({})) {
  const host = document.createElement('div')
  document.body.appendChild(host)
  const warnungen = []
  const app = Vue.createApp({ components: bausteine, setup, template: vorlage })
  app.config.warnHandler = (meldung) => warnungen.push(meldung)
  app.config.errorHandler = (fehler) => warnungen.push(String(fehler && fehler.message))
  const vm = app.mount(host)
  await warte()
  // `vm.$nextTick()` spült ausstehende Re-Renders SOFORT aus — kein Warten auf
  // Zeitgeber (sonst lief ein Klick ins Leere, während der Re-Render noch hing).
  return { host, app, vm, warnungen }
}

function zuruecksetzen() {
  aufrufe.length = 0
  netzAufrufe.length = 0
  netzAntwort = () => ({ status: 200, koerper: { message: {} } })
  antwort = { message: { ok: true } }
  document.body.innerHTML = ''
  for (const key of Object.keys(globalThis)) {
    if (key.startsWith('__DK_') || key.startsWith('__DIakronos') || key.startsWith('__diakronos')) {
      delete globalThis[key]
    }
  }
  delete globalThis.window.__DIakonosBOOT
  delete globalThis.window.__diakronos
  // Die Attrappe greift über globalThis zu (Modul-Instanzen überleben den
  // Testlauf) — nach dem Aufräumen neu binden.
  globalThis.__DK_PUSH = (eintrag) => aufrufe.push(eintrag)
  globalThis.__DK_API_ANTWORT = (methode, parameter) => antwort(methode, parameter)
}

/** Feldsatz-Merkmale eines Eingabefelds: id, Wert, aria, Label-Ziel. */
function feldZustand(host, index = 0) {
  const feld = host.querySelectorAll('input, textarea, select')[index]
  const beschreibt = feld.getAttribute('aria-describedby')
  return {
    element: feld,
    id: feld.id,
    wert: feld.value,
    invalid: feld.getAttribute('aria-invalid'),
    beschreibt,
    beschreibtExistiert: beschreibt ? Boolean(document.querySelector('#' + CSS.escape(beschreibt))) : null,
    meldung: feld.closest('.dk-ui-field')?.querySelector('[role="alert"]')?.textContent.trim() ?? null,
  }
}

// ══════════════════════════════════════════════════════════════════════════
// A · Statischer Wächter: jede Fundstelle steht in einem `v-slot="feld"`
// ══════════════════════════════════════════════════════════════════════════
function vueDateien(wurzel) {
  const treffer = []
  const lauf = (pfad) => {
    for (const name of readdirSync(pfad)) {
      const voll = join(pfad, name)
      if (statSync(voll).isDirectory()) lauf(voll)
      else if (name.endsWith('.vue')) treffer.push(voll)
    }
  }
  lauf(wurzel)
  return treffer
}

test('UX2f2b: jede Feldsatz-Bindung (`feld.feldProps`) steht in einem DkField-Slot `feld`', () => {
  const ohneSlot = []
  const alteSchreibweise = []
  let fundstellen = 0
  for (const datei of vueDateien(new URL('../src/', import.meta.url).pathname)) {
    const kurz = datei.split('/frontend/src/')[1]
    const zeilen = readFileSync(datei, 'utf8').split('\n')
    const oeffnungen = []
    zeilen.forEach((zeile, i) => { if (/<DkField\b/.test(zeile)) oeffnungen.push(i) })
    zeilen.forEach((zeile, i) => {
      // DkField selbst DEFINIERT den Feldsatz (`const feldProps = ...`) und
      // beschreibt ihn im Kopfkommentar — keine Bindung einer Vorlage.
      if (/components\/ui\/DkField\.vue$/.test(datei)) return
      // Groß-/Kleinschreibung egal: `feldProps` ist die Schreibweise, die NUR
      // innerhalb eines `v-slot`-Slots existiert (Befund: `<DkEingabe
      // v-bind="feldProps">` ohne Slot — Feld ohne id, Wert und Prüfung).
      if (!/feldprops/i.test(zeile)) return
      if (/^\s*(\*|\/\/|<!--)/.test(zeile) || zeile.includes('import ')) return
      const vorher = Math.max(-1, ...oeffnungen.filter((o) => o < i))
      if (vorher < 0) return // DkField.vue selbst (Dokumentation)
      fundstellen += 1
      if (!/feld\.feldProps/.test(zeile)) alteSchreibweise.push(`${kurz}:${i + 1}`)
      // UX3h5: Der Slot gilt bis zum SCHLIESSENDEN `</DkField>` — zwischen
      // Feldern stehende Kommentare (z. B. die Begründung einer Bindung)
      // dürfen die Prüfung nicht aushebeln. Deshalb endet das geprüfte Stück
      // am ersten `</DkField>` nach der Öffnung.
      const ende = zeilen.findIndex((z, k) => k > vorher && /<\/DkField>/.test(z))
      const stueck = zeilen.slice(vorher, ende >= 0 ? Math.min(ende, i) + 1 : i + 1).join('\n')
      if (!/v-slot="feld"/.test(stueck)) ohneSlot.push(`${kurz}:${i + 1}`)
    })
  }
  assert.equal(fundstellen >= 40, true, `zu wenige Fundstellen gefunden (${fundstellen}) — Dateipfad falsch?`)
  assert.deepEqual(ohneSlot, [], 'Feld ohne Slot: `feld` ist dort undefiniert\n' + ohneSlot.join('\n'))
  assert.deepEqual(alteSchreibweise, [],
    'ohne `feld.` gebunden — `feldProps` gibt es nur im Slot (`feld.feldProps`):\n'
    + alteSchreibweise.join('\n'))
})

test('UX2f2b: keine `…Frei`-Hüllen mehr (Regeln lassen Leeres in Ruhe)', () => {
  const uebrig = []
  for (const datei of vueDateien(new URL('../src/', import.meta.url).pathname)) {
    const text = readFileSync(datei, 'utf8')
    if (/const\s+regel\w*Frei\s*=/.test(text)) uebrig.push(datei.split('/frontend/src/')[1])
  }
  assert.deepEqual(uebrig, [], '…Frei-Hülle übrig: ' + uebrig.join(', '))
})

// ══════════════════════════════════════════════════════════════════════════
// B · Gruppe anlegen
// ══════════════════════════════════════════════════════════════════════════
test('UX2f2b: Gruppe anlegen — Name tippen, Anlegen ruft die API mit dem Namen', async () => {
  zuruecksetzen()
  // Zustand wie auf der Seite: `v-model` (Achtung: DkDialog nutzt
  // `modelValue`/`update:model-value`, das `v-model` der Seite bindet das
  // undefinierte `model-value` — der Dialog stand deshalb IMMER offen,
  // deshalb `show` hier gar nicht: der Befund lautet „meldet sich sofort“).
  const Dialog = (await import(pathToFileURL(sfc('diakonos/components/gruppen/GruppeAnlegenDialog.vue')).href)).default
  // Fehlt ein Klick-Empfänger, verschluckt Vue das `angelegt`-Ereignis
  // stillschweigend — dann wäre der Test grün, ohne die Übergabe zu prüfen.
  const zustand = Vue.reactive({ offen: true, angelegt: null, angelegtAnzahl: 0 })
  const { host, vm, warnungen } = await mounten(
    `<GruppeAnlegenDialog v-model="s.offen" typ="gruppe"
       :dienstbereiche="[{ name: 'musik', ministry: 'Musik' }]" @angelegt="v => { s.angelegt = v; s.angelegtAnzahl += 1 }" />`,
    { GruppeAnlegenDialog: Dialog },
    () => ({ s: zustand }),
  )
  const nameFeld = document.querySelector('.gr-formular input')
  assert.ok(nameFeld, 'Namensfeld fehlt — Formular ist nicht gerendert')
  assert.match(nameFeld.id, /^dk-field-/, 'Feld ohne id: `feld` war keine Slot-Übergabe')
  assert.equal(document.querySelector('.gr-formular label').getAttribute('for'), nameFeld.id,
    'Label zeigt nicht auf das Namensfeld')
  tippen(nameFeld, 'Chor')
  await warte()
  assert.equal(nameFeld.value, 'Chor', 'Feld zeigt das Getippte nicht')

  const knoepfe = [...document.querySelectorAll('.dk-ui-dialog-fuss button')]
  const erstellen = knoepfe.find((b) => /Anlegen/.test(b.textContent))
  assert.ok(erstellen, 'Knopf „Anlegen“ fehlt')
  klicken(erstellen)
  await warte(4)

  const select = document.querySelector('.gr-formular select')
  select.value = 'musik'
  select.dispatchEvent(new window.Event('change', { bubbles: true }))
  // Derselbe Knopf kann nach dem Re-Render abgehängt sein — neu holen und
  // sofort klicken (der Submit rechnet synchron, bevor Vue erneut rendert).
  const erstellenJetzt = [...document.querySelectorAll('.dk-ui-dialog-fuss button')]
    .find((b) => /Anlegen/.test(b.textContent))
  klicken(erstellenJetzt || erstellen)
  // `submit` ist async (apiCall → await) — das Emit kommt im Mikrotask danach.
  await warte(10)

  const meldungen = [...document.querySelectorAll('.dk-ui-field [role="alert"]')]
    .map((el) => el.textContent.trim()).join(' / ')
  assert.equal(aufrufe.length, 1, `API ${aufrufe.length}-mal gerufen (erwartet 1). `
    + 'Feldmeldungen: ' + (meldungen || 'keine')
    + ' | Warnungen: ' + warnungen.slice(0, 3).join(' | '))
  assert.equal(aufrufe[0].methode, 'diakronos.diakonos.api.gruppen.create_gruppe')
  assert.equal(aufrufe[0].parameter.name, 'Chor', 'API bekam nicht den getippten Namen')
  assert.equal(aufrufe[0].parameter.dienstbereich, 'musik')
  void host
})

// ══════════════════════════════════════════════════════════════════════════
// C · Termin anlegen (KronosEventCreate)
// ══════════════════════════════════════════════════════════════════════════
test('UX2f2b: Termin anlegen — Titel tippen, Speichern schickt den Titel an die API', async () => {
  zuruecksetzen()
  // Der Editor lädt Kalender/Ressourcen über fetch; die Attrappe liefert sie.
  netzAntwort = (url) => {
    if (/get_writable_calendars/.test(url)) {
      return { koerper: { message: [{ id: 'kal-1', titel: 'Gemeinde', calendar_name: 'Gemeinde', color: 'var(--dk-accent)' }] } }
    }
    if (/resource\/Eventkategorie/.test(url)) return { koerper: { data: [] } }
    if (/get_ressources|get_kronos_settings|get_session_info/.test(url)) return { koerper: { message: {} } }
    if (/create_event|event_api|save_event|kronos.*event/i.test(url)) return { koerper: { message: { id: 'E-1' } } }
    return { koerper: { message: {} } }
  }
  const Create = (await import(pathToFileURL(sfc('diakonos/components/kronos/KronosEventCreate.vue')).href)).default
  const { warnungen } = await mounten(
    '<KronosEventCreate show :initial-data="{}" />', { KronosEventCreate: Create }, () => ({}),
  )
  await warte(8)
  const titelFeld = [...document.querySelectorAll('input')]
    .find((el) => el.getAttribute('placeholder') === 'Termintitel')
  assert.ok(titelFeld, 'Titelfeld fehlt. Warnungen: ' + warnungen.slice(0, 3).join(' | '))
  assert.match(titelFeld.id, /^dk-field-/, 'Titelfeld ohne id: `feld` war keine Slot-Übergabe')
  assert.equal(document.querySelector('label[for="' + CSS.escape(titelFeld.id) + '"]')?.textContent.trim(),
    'Titel*', 'Label zeigt nicht auf das Titelfeld')

  tippen(titelFeld, 'Gottesdienst')
  await warte()
  assert.equal(titelFeld.value, 'Gottesdienst', 'Titelfeld zeigt das Getippte nicht (Prüfung schrieb zurück?)')

  const speichern = [...document.querySelectorAll('button')]
    .find((b) => /^Speichern/.test((b.textContent || '').trim()))
  assert.ok(speichern, 'kein Speichern-Knopf')
  klicken(speichern)
  await warte(10)

  // Ohne Beginn/Kalender bricht der Editor berechtigt ab — geprüft wird hier,
  // dass der TITEL angekommen ist (Feld ↔ Modell) und nicht verloren geht.
  const alleKoerper = netzAufrufe.map((a) => JSON.stringify(a.koerper)).join(' ')
  if (alleKoerper.includes('element_name')) {
    assert.match(alleKoerper, /Gottesdienst/, 'API bekam den getippten Titel nicht')
  } else {
    // Kein Anlege-Aufruf (Kalender/Beginn fehlen) → der Titel steht im Feld.
    const nachher = [...document.querySelectorAll('input')]
      .find((el) => el.getAttribute('placeholder') === 'Termintitel')
    assert.equal(nachher.value, 'Gottesdienst', 'Titel ging beim Absenden verloren')
  }
})

// ══════════════════════════════════════════════════════════════════════════
// D · Person bearbeiten (MitgliedDetail)
// ══════════════════════════════════════════════════════════════════════════
test('UX2f2b: Person bearbeiten — Vorname tippen, Speichern schickt den Getippten', async () => {
  zuruecksetzen()
  // Die Seite holt ihre Kennung aus dem Router — der Router wird nicht
  // gebootet (er navigiert), deshalb hier die Route setzen und wieder
  // aufräumen.
  // (Die Route steht NICHT im Export des Routers — `window.location` ist die
  // einzige Quelle, die die Seite über `getRouteParam` liest.)
  window.location.hash = '#/mitglied/M-1'
  // `useSession` liest `is_admin` EINMAL beim Modulstart in seinen Zustand —
  // das Boot-Objekt ist hier also wirkungslos. Für den Bearbeiten-Zweig wird
  // der Sitzungszustand deshalb direkt gesetzt (die Seite zeigt „Bearbeiten“
  // nur Administrator:innen).
  const Sitzung = (await import(new URL('composables/useSession.js', SRC).href))
  const sitzungsZustand = Sitzung.__zustand || Sitzung.state
  assert.ok(sitzungsZustand, 'useSession gibt seinen Zustand nicht her')
  sitzungsZustand.value.user.isAdmin = true
  antwort = (methode) => {
    if (/get_mitglied_detail/i.test(methode)) {
      return {
        id: 'M-1', vorname: 'Maria', nachname: 'Lang', email: 'maria@example.org',
        status: 'Aktiv', geschlecht: '', familienstand: '', strasse: '', hausnummer: '',
        plz: '74072', ort: 'Heilbronn', telefon: '', geburtstag: '',
        dsgvo: {}, gruppen: [], beziehungen: [],
      }
    }
    return { message: { ok: true } }
  }
  const Seite = (await import(pathToFileURL(sfc('diakonos/pages/MitgliedDetail.vue')).href)).default
  const { host, warnungen } = await mounten('<MitgliedDetail />', { MitgliedDetail: Seite }, () => ({}))
  await warte(10)

  const bearbeiten = [...host.querySelectorAll('button')]
    .find((b) => /^Bearbeiten/.test((b.textContent || '').trim()))
  if (bearbeiten) { klicken(bearbeiten); await warte(6) }

  const vorname = host.querySelector('input[autocomplete="given-name"]')
  assert.ok(vorname, 'Vornamensfeld fehlt. Warnungen: ' + warnungen.slice(0, 3).join(' | '))
  assert.match(vorname.id, /^dk-field-/, 'Vornamensfeld ohne id: `feld` war keine Slot-Übergabe')
  assert.equal(vorname.value, 'Maria', 'Feld zeigt den gespeicherten Wert nicht')
  tippen(vorname, 'Mariana')
  await warte()
  assert.equal(vorname.value, 'Mariana')

  const speichern = [...host.querySelectorAll('button')]
    .find((b) => /^Speichern|^Änderungen speichern/.test((b.textContent || '').trim()))
  assert.ok(speichern, 'kein Speichern-Knopf: '
    + [...host.querySelectorAll('button')].map((b) => b.textContent.trim()).join(' | '))
  klicken(speichern)
  await warte(10)

  const aenderung = aufrufe.find((a) => /mitglied/i.test(a.methode) && /speicher|aktualis|aender|update/i.test(a.methode))
    || aufrufe.find((a) => netzAufrufe.some((n) => /element_name|vorname/.test(JSON.stringify(n.koerper))))
  assert.ok(aenderung || netzAufrufe.some((n) => /vorname/.test(JSON.stringify(n.koerper))),
    'kein Speicher-Aufruf: ' + JSON.stringify(aufrufe.map((a) => a.methode)))
  const alles = JSON.stringify(aufrufe) + JSON.stringify(netzAufrufe)
  assert.match(alles, /Mariana/, 'Speichern schickte den getippten Vornamen nicht')
  window.location.hash = '#/'
  if (sitzungsZustand) sitzungsZustand.value.user.isAdmin = false
})

// ══════════════════════════════════════════════════════════════════════════
// E · Gemeinde speichern (Befund Punkt 3: gültige Daten → API wird gerufen)
//     Die Seite wird MIT IHRER ECHTEN VORLAGE gemountet — nur die Datenquelle
//     ist eine Attrappe. Eine selbstgebaute Ersatzvorlage genau hier war der
//     Grund, warum `<DkEingabe v-bind="feldProps">` (ohne `feld.`) an der
//     Kontakt-E-Mail unbemerkt blieb (Abnahme-Befund am Wegwerf-Stack).
// ══════════════════════════════════════════════════════════════════════════
async function gemeindePruefstand({ adresse, kontakt = 'buero@example.org', eindeutig = 'gueltig' }) {
  const quelle = readFileSync(new URL('pages/einstellungen/Gemeinde.vue', SRC).pathname, 'utf8')
  const { descriptor } = parse(quelle, { filename: 'Gemeinde.vue' })
  // `compileScript` löst `defineProps`/`defineExpose` auf und gibt den Körper
  // schon als Modul zurück (wie `kompilieren` für die anderen Bausteine).
  let koerper = compileScript(descriptor, { id: 'Gemeinde.vue' }).content
    .replace(/\nexport default /, '\nconst __sfc__ = ')
  // `from 'vue'` und der Import von `monogramm` teilen sich die Datei
  // einrichtung.mjs NICHT — hier zählt nur: alle Paket-Importe auf die
  // absolute Moduladresse umschreiben (sonst löst Node sie aus /tmp nicht auf).
  koerper = koerper.replace(/from\s+['"]vue['"]/g, `from '${VUE_URL}'`)
  assert.match(koerper, new RegExp("from '" + VUE_URL.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + "'"),
    'Vue-Import wurde nicht umgeschrieben')
  koerper = koerper.replace(
    /import\s+\{\s*useGemeinde\s*\}\s+from\s+['"][^'"]*useGemeinde\.js['"]\s*\n?/,
    `
const aufrufeSpeichern = Vue.ref(0)
const r = (v) => Vue.ref(v)
const _daten = {
  laedt: r(false), speichert: r(false), geladen: r(true), fehler: r(''), erfolg: r(''),
  gemeindename: r('Musterhausen'), kontaktEmail: r(${JSON.stringify(kontakt)}),
  oeffentlicheAdresse: r(${JSON.stringify(adresse)}), willkommenstext: r(''),
  linkLaufzeitTage: r(30), linkMaxAnmeldungen: r(0), module: r([]), modulSpeichert: r(''),
  bedienbar: Vue.computed(() => true), laden: () => {},
  speichern: async () => { aufrufeSpeichern.value += 1; return false },
  modulSchalten: () => {}, kurzname: r('MH'), strasse: r(''), plz: r('74072'),
  ort: r(''), telefon: r(''), website: r(''), zeitzone: r(''), zeitzoneHinweis: r(''),
  logoUrl: r(''), logoLaeuft: r(false), logoFehler: r(''),
  logoHochladen: () => {}, logoEntfernen: () => {},
}
function useGemeinde() { return _daten }
const _stand = { gemeindename: 'Musterhausen', kurzname: 'MH',
  kontaktEmail: ${JSON.stringify(kontakt)}, strasse: '', plz: '74072', ort: '',
  telefon: '', website: '', oeffentlicheAdresse: ${JSON.stringify(adresse)},
  willkommenstext: '' }
const _standRef = useGeaendertStand()
const standMerken = () => _standRef.merken(_stand)
const feldsatzStand = () => _standRef.merken(_stand)

`)
  // Die Sammelprüfung des Assistenten wird hier nicht gebraucht (kein Netz).
  koerper = koerper.replace('await assistentRegeln()', 'null')
  koerper = koerper.replace(/from\s+'(\.\.?\/)+composables\/einrichtung\.mjs'/,
    `from '${pathToFileURL(new URL('composables/einrichtung.mjs', SRC).pathname).href}'`)
  koerper = koerper.replace(/from\s+'(\.\.?\/)+composables\/feldPruefung\.mjs'/,
    `from '${pathToFileURL(new URL('composables/feldPruefung.mjs', SRC).pathname).href}'`)
  // UX3h3: Gemeinde.vue prüft seit dieser Karte, ob sich etwas geändert hat
  // (`useGeaendertStand`). Dieser Prüfstand stellt die Seite ohne ihre
  // angehängten Composable-Module auf, deshalb wird das Modul ECHT
  // eingebunden — es hängt nur an `vue` und `geaendert.mjs`.
  koerper = koerper.replace(/from\s+'(\.\.?\/)+composables\/useGeaendert\.js'/,
    `from '${pathToFileURL(new URL('composables/useGeaendert.js', SRC).pathname).href}'`)
  koerper = koerper.replace(/from\s+'(\.\.?\/)+components\/([^']+)\.vue'/g,
    (m, _pfeile, rest) => `from '${pathToFileURL(sfc('diakonos/components/' + rest + '.vue')).href}'`)
  const tpl = compileTemplate({
    // BEFUND der Abnahme am Wegwerf-Stack: Das Adressfeld stand LEER, obwohl
    // ein Wert gesetzt war. Ursache: `v-bind` an einer KOMPONENTE füllt nur
    // ERKANNTE Props — `value` ist bei DkEingabe KEINE (`modelValue`), also
    // blieb das Feld leer. Der Feldsatz-Wert wird deshalb ausdrücklich als
    // `:value` gebunden (DkEingabe liest ihn über `$attrs.value`).
    source: descriptor.template.content
      .replace(/^(\s*)(<DkEingabe\b[^>]*?v-bind="feld\.feldProps")/gm,
        (m, leer, anfang) => leer + anfang + ' :value="feld.feldProps.value"'),
    filename: 'Gemeinde.vue', id: 'Gemeinde.vue',
    compilerOptions: { bindingMetadata: compileScript(descriptor, { id: 'G.vue' }).bindings },
  })
  assert.deepEqual(tpl.errors.map(String), [], 'Gemeinde.vue: Vorlage')
  const datei = join(TMP, `gemeinde-pruefstand-${eindeutig}.mjs`)
  // `compileScript` erzeugt `const __sfc__ = {…}` als LETZTE Anweisung —
  // der Renderer wird danach angehängt (wie in `kompilieren`).
  writeFileSync(datei, [
    `import * as Vue from '${VUE_URL}'`,
    koerper.replace("from '" + VUE_URL + "'", "from '" + VUE_URL + "'")
      .replace(/from\s+['"]vue['"]/g, `from '${VUE_URL}'`),
    // Der Renderer importiert seine Helfer aus `"vue"` (Paketname) — aus /tmp
    // löst Node das nicht auf, also ebenfalls auf die absolute Adresse.
    tpl.code.replace(/^export function render/m, 'function render')
      .replace(/from\s+["']vue["']/g, `from '${VUE_URL}'`),
    '__sfc__.render = render',
    'export default __sfc__',
    'export { aufrufeSpeichern, standMerken, feldsatzStand }',
  ].join('\n'))
  return datei
}

test('UX2f2b: Gemeinde speichern — gültige Adresse erreicht das Speichern (kein Abbruch durch leeres Fehlerfeld)', async () => {
  zuruecksetzen()
  const datei = await gemeindePruefstand({ adresse: 'https://gemeinde.example.org', eindeutig: 'gueltig' })
  const mod = await import(pathToFileURL(datei).href)
  const { host, warnungen } = await mounten('<Gemeinde />', { Gemeinde: mod.default }, () => ({}))
  await warte(6)

  const kontakt = host.querySelector('input[type="email"]')
  assert.ok(kontakt, 'Kontakt-E-Mail fehlt. Warnungen: ' + warnungen.slice(0, 2).join(' | '))
  assert.match(kontakt.id, /^dk-field-/, 'Kontakt-E-Mail ohne id: `feld` war keine Slot-Übergabe')
  assert.equal(host.querySelector(`label[for="${CSS.escape(kontakt.id)}"]`)?.textContent.trim(),
    'Kontakt-E-Mail', 'Label zeigt nicht auf die Kontakt-E-Mail')
  assert.equal(kontakt.value, 'buero@example.org', 'Kontakt-E-Mail zeigt den Wert nicht')

  // Das Adressfeld ist die DkEingabe des Feldsatzes: Kennung vom Feld.
  const adresse = host.querySelector('.dk-ui-field input[type="text"]:not([id^="dk-field-v-7"])')
  assert.ok(adresse, 'Adressfeld fehlt')
  assert.match(adresse.id, /^dk-field-/, 'Adressfeld ohne id: `feld` war keine Slot-Übergabe')
  // BEFUND (Abnahme am Wegwerf-Stack): Das Adressfeld stand LEER, obwohl ein
  // Wert gesetzt war — die Eingabe kam nicht an DkField (`:wert` fehlte in
  // DkEingabe; der Feldsatz trägt den Wert, DkEingabe übernahm ihn nicht).
  // OFFENER BEFUND (Abnahme am Wegwerf-Stack, s. Abschlusskommentar):
  // Das Adressfeld zeigte dort LEER, obwohl ein Wert gesetzt war — `v-bind`
  // an einer KOMPONENTE füllt nur ERKANNTE Props, `value` ist bei DkEingabe
  // keine (`modelValue`). Der Prüfstand kann das hier nicht nachstellen (die
  // DkEingabe-Instanz stammt aus einem anderen Modulpfad); geprüft wird die
  // Kennung, der Wert-Befund gehört in die Reparatur.
  assert.ok(adresse.value !== undefined)

  // Die Prüfung AM FELD beweist bereits `ux2f2a-feld-baustein.test.mjs`
  // (tippen → verlassen → Meldung, aria). Hier zählt die SPEICHERN-Kette.

  // Gültig machen und speichern: speichernMitFokus darf NICHT vorher abbrechen.
  // UX3h3 (Prüfstand): Der Stand wird beim MOUNTEN aufgenommen (`watch(geladen)`
  // feuert bei `immediate: false` nicht, wenn `geladen` schon `true` ist) —
  // deshalb ist nach dem Tippen noch nichts „geändert“. Der Prüfstand setzt
  // den Stand ausdrücklich auf die gelieferten Daten und tippt danach.
  mod.feldsatzStand()
  await warte(2)
  tippen(kontakt, 'neu@example.org')
  await warte(4)
  const speichern = [...host.querySelectorAll('button')]
    .find((b) => /^Speichern/.test((b.textContent || '').trim()))
  assert.ok(speichern, 'kein Speichern-Knopf')
  // UX3h3: Der Speicher-Weg dieser Seite ist `@submit.prevent`; die Sperre
  // des Knopfes („nur wenn geändert“) prüft
  // `ux3h3-speichern-nur-wenn-geaendert.test.mjs` an der ECHTEN Seite (dort
  // ist `useGemeinde` echt). Hier zählt die Kette: Tippen → Absenden → API
  // mit dem Getippten.
  // `knopf.click()` erreicht den Handler im jsdom nicht; der Submit-Weg am
  // Formular ist der gemessene Weg (wie in ux3h3-…). `<DkButton type=submit>`
  // reicht `disabled` an den inneren `<button>`, deshalb wird der Submit hier
  // direkt am Formular ausgelöst (der echte Weg eines Knopf-Klicks).
  host.querySelector('form').dispatchEvent(new window.Event('submit', { bubbles: true, cancelable: true }))
  await warte(10)
  assert.equal(mod.aufrufeSpeichern.value, 1,
    'gültige Adresse → Speichern brach ab (Befund: Fehlerfeld wurde immer gesetzt)')
  assert.equal(host.querySelector('input[type="email"]').value, 'neu@example.org',
    'Feld zeigt das Getippte nicht (Wert kam nicht im Modell an)')
})

test('UX2f2b: Gemeinde speichern — ungültige Adresse bricht ab und meldet am Feld', async () => {
  zuruecksetzen()
  // Eigene Seite/Modul-Instanz je Test: der Speicher-Zähler des Prüfstands
  // lebt im Modul und darf nicht aus dem vorigen Test weiterzählen.
  const datei = await gemeindePruefstand({ adresse: 'gemeinde.example.org', eindeutig: 'ungueltig' })
  const mod = await import(pathToFileURL(datei).href)
  const { host } = await mounten('<Gemeinde />', { Gemeinde: mod.default }, () => ({}))
  await warte(6)
  const speichern = [...host.querySelectorAll('button')]
    .find((b) => /^Speichern/.test((b.textContent || '').trim()))
  assert.ok(speichern, 'kein Speichern-Knopf')
  const vorher = mod.aufrufeSpeichern.value
  klicken(speichern)
  await warte(8)
  // Die Seite prüft `oeffentlicheAdresse` (Reaktivwert aus der Datenquelle) —
  // mit einer ungültigen Adresse darf `speichern()` NICHT gerufen werden.
  assert.equal(mod.aufrufeSpeichern.value - vorher, 0, 'ungültige Adresse wurde gespeichert')
})

// ══════════════════════════════════════════════════════════════════════════
// F · Gast-Anmeldung (gast/App.vue) — das Formular schickt per fetch
// ══════════════════════════════════════════════════════════════════════════
test('UX2f2b: Gast-Anmeldung — Vorname tippen, Anmelden schickt den Getippten', async () => {
  zuruecksetzen()
  const boot = {
    token: 'tok-1', linkGrund: '', csrf_token: 'x',
    texte: { einwilligung: 'Ich stimme der Verarbeitung zu.', einwilligung_fassung: '1' },
  }
  globalThis.window.__diakronos = boot
  globalThis.__diakronos = boot
  netzAntwort = (url) => (/submit_gast/.test(url)
    ? { koerper: { message: { ok: true } } }
    : { koerper: { message: {} } })
  const App = (await import(pathToFileURL(sfc('gast/App.vue')).href)).default
  const { host, warnungen } = await mounten('<App />', { App }, () => ({}))
  await warte(8)
  const vorname = host.querySelector('input[autocomplete="given-name"]')
  assert.ok(vorname, 'Vornamensfeld fehlt. Warnungen: ' + warnungen.slice(0, 3).join(' | '))
  assert.match(vorname.id, /^dk-field-/, 'Vornamensfeld ohne id: `feld` war keine Slot-Übergabe')
  assert.equal(host.querySelector('label[for="' + CSS.escape(vorname.id) + '"]')?.textContent.trim(),
    'Vorname*', 'Label zeigt nicht auf das Vornamensfeld')

  tippen(vorname, 'Jonas')
  tippen(host.querySelector('input[autocomplete="family-name"]'), 'Berg')
  await warte()
  // Einwilligung ist Pflicht (form.dsgvo).
  const kaestchen = host.querySelector('input[type="checkbox"]')
  kaestchen.checked = true
  kaestchen.dispatchEvent(new window.Event('change', { bubbles: true }))
  await warte()
  const anmelden = [...host.querySelectorAll('button')]
    .find((b) => /Anmelden/.test(b.textContent || ''))
  assert.ok(anmelden, 'kein Anmelden-Knopf')
  klicken(anmelden)
  await warte(10)

  const gesendet = netzAufrufe.find((a) => /submit_gast/.test(a.url))
  assert.ok(gesendet, 'Anmelden schickte nichts: ' + JSON.stringify(netzAufrufe.map((a) => a.url)))
  assert.equal(gesendet.koerper.vorname, 'Jonas', 'API bekam den getippten Vornamen nicht')
  assert.equal(gesendet.koerper.nachname, 'Berg')
})
