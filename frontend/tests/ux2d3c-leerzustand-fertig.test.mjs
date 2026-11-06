/**
 * UX2d3c · Leerzustände fertigstellen — Startseite, Moderation, Datenschutz
 * und Löschantragsliste WIRKLICH gemountet.
 *
 * BEFUND (Review UX2d3b):
 *   - `LoeschantraegeListe.vue` benutzte `<DkSkelett>`, ohne es zu importieren
 *     (Vue rendert dann still ein unbekanntes Element — das Skelett fehlte);
 *   - `Datenschutz.vue` zeigte bei einem Serverfehler „HTTP 500" statt einer
 *     Erklärung, und für die leeren Listen stand ein nackter Satz;
 *   - `Home.vue` blieb bei einem gescheiterten Laden des Layouts LEER;
 *   - der Fehlerzustand der Mitglieder-Übersicht hatte keinen Weg zurück.
 *
 * GEPRÜFT WIRD JE FLÄCHE (wie `ux2d3b-leerzustand-mount.test.mjs`):
 *   1. leere Antwort  → Leerzustand mit Erklärung und nächstem Schritt;
 *   2. Fehler         → Katalogtext (kein „HTTP 500") UND „Erneut versuchen"
 *                       startet einen NEUEN Aufruf (Zähler im Test);
 *   3. während des Ladens (Antwort noch offen) steht KEIN Leerzustand.
 *
 * Aufbau wie im Betrieb: `@vue/compiler-sfc` → echte Komponente →
 * `createApp().mount()` in jsdom. Nur die Datenschicht wird ersetzt; Vue, die
 * Dk-Bausteine und die Vorlagen sind echt.
 *
 * Lauf: node --test tests/ux2d3c-leerzustand-fertig.test.mjs   (cwd = frontend/)
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { existsSync, readFileSync, mkdtempSync, writeFileSync, rmSync, symlinkSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, dirname, resolve, basename } from 'node:path'
import { pathToFileURL, fileURLToPath } from 'node:url'
import { JSDOM } from 'jsdom'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'

// ── DOM zuerst (Vue greift beim Import auf `document` zu) ─────────────────
const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
for (const schluessel of ['window', 'document', 'Node', 'Element', 'HTMLElement', 'Event',
  'MouseEvent', 'SVGElement', 'CSS', 'getComputedStyle', 'MutationObserver']) {
  globalThis[schluessel] = dom.window[schluessel]
}
const Vue = await import('vue')
const Pinia = await import('pinia')

const SRC = new URL('../src/diakonos/', import.meta.url)

// ── SFC → ES-Modul ────────────────────────────────────────────────────────
const TMP = mkdtempSync(join(tmpdir(), 'ux2d3c-'))
// Paket-Importe (`sortablejs`, `pinia`, `vue`) aus dem Zwischenordner auflösen.
symlinkSync(join(dirname(fileURLToPath(import.meta.url)), '..', 'node_modules'), join(TMP, 'node_modules'), 'dir')
const cache = new Map()
const VUE_URL = import.meta.resolve('vue')
const PINIA_URL = import.meta.resolve('pinia')

/** Ersetzte Module: Schlüssel = Dateiname der Attrappe. */
const attrappen = new Map()

function attrappe(name, code) {
  const ziel = join(TMP, `${name}.mjs`)
  writeFileSync(ziel, code)
  attrappen.set(name, pathToFileURL(ziel).href)
}

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
  code = code.replace(/from\s+['"]pinia['"]/g, `from '${PINIA_URL}'`)
  code = code.replace(/from\s+['"](\.[^'"]+)['"]/g, (voll, spec) => {
    const name = basename(spec)
    const ziel = resolve(dirname(abs), spec)
    if (attrappen.has(name)) return `from '${attrappen.get(name)}'`
    if (ziel.endsWith('.vue')) return `from '${pathToFileURL(kompilieren(ziel)).href}'`
    // Relative JS-Importe im Projekt lassen die Endung weg
    // (`from '../stores/dashboardConfig'`) — ESM braucht sie hier.
    const datei = existsSync(ziel) ? ziel : `${ziel}.js`
    return `from '${pathToFileURL(datei).href}'`
  })
  const ziel = resolve(TMP, filename.replace(/\.vue$/, '') + '.' + cache.size + '.mjs')
  writeFileSync(ziel, code)
  cache.set(abs, ziel)
  // UX2d3c: Das kompilierte Modul liegt in TMP (ausserhalb von frontend/) —
  // Paket-Importe wie `sortablejs`/`pinia` wären von dort unauffindbar. Ein
  // `node_modules`-Verweis im Zwischenordner löst sie wie im Projekt auf.
  return ziel
}

async function seite(relativ) {
  const abs = join(SRC.pathname, relativ)
  cache.delete(abs) // je Durchlauf frisch
  return (await import(pathToFileURL(kompilieren(abs)).href + `?v=${Date.now()}`)).default
}

const tick = () => new Promise((loese) => setTimeout(loese, 0))
const warte = (ms) => new Promise((loese) => setTimeout(loese, ms))

async function mounten(Komponente, props = {}) {
  const host = document.createElement('div')
  document.body.appendChild(host)
  const warnungen = []
  const app = Vue.createApp(Komponente, props)
  app.config.warnHandler = (meldung) => warnungen.push(meldung)
  app.use(Pinia.createPinia())
  app.mount(host)
  await tick()
  return { host, app, warnungen }
}

/** Was steht auf dem Bildschirm? */
function text(host) {
  return host.textContent.replace(/\s+/g, ' ').trim()
}

function knopfMitText(host, beschriftung) {
  return [...host.querySelectorAll('button, a')].find(
    (e) => e.textContent.replace(/\s+/g, ' ').trim() === beschriftung,
  )
}

// ── Attrappen der Datenschicht ────────────────────────────────────────────
/**
 * `lage.modus`: 'leer' | 'fehler' | 'offen' (Antwort bleibt aus — „lädt noch")
 * `lage.aufrufe`: Zähler aller Server-Aufrufe (für „Erneut versuchen").
 */
const lage = { modus: 'leer', aufrufe: 0 }

/** Antwort je Modus — zentral, damit jede Seite dasselbe Verhalten sieht. */
function antwort(daten) {
  globalThis.__ux2d3cAufruf()
  if (lage.modus === 'offen') return new Promise(() => {}) // bleibt aus
  if (lage.modus === 'fehler') {
    return Promise.reject(Object.assign(new Error('HTTP 500'), { status: 500 }))
  }
  return Promise.resolve(daten)
}

globalThis.__ux2d3cAufruf = () => { lage.aufrufe += 1 }

// useApi.js: `apiCall(...)` liefert je Endpunkt die passende leere Antwort.
attrappe('useApi.js', `
export class AuditConfirmationRequired extends Error {}
export async function apiCall(endpunkt) {
  globalThis.__ux2d3cAufruf()
  // Die Rechteprüfung der Seite muss auch bei Serverfehlerlage antworten —
  // sonst steht „Zugriff verweigert" statt des echten Fehlers.
  if (String(endpunkt).includes('permissions.get_session_info')) return { can_moderate: true }
  const leer = globalThis.__ux2d3cLeer(endpunkt)
  return globalThis.__ux2d3cAntwort(leer)
}
export async function apiAntwortPruefen(r) {
  if (globalThis.__ux2d3cModus() === 'fehler') {
    throw Object.assign(new Error('HTTP 500'), { status: 500 })
  }
  return r
}
`)

// useLoeschantraege.js: Zählung offener Anträge (Übersicht/Bereich).
attrappe('useLoeschantraege.js', `
export async function offeneAntraegeZaehlen() { return 0 }
export async function antraegeLaden() { return [] }
export async function mailversandStand() { return { eingerichtet: true, darf_aendern: false } }
export async function loeschungFreigeben() { return {} }
export async function antragAblehnen() { return {} }
`)

// sortablejs: nur Drag & Drop — im Test nicht nötig (jsdom ohne Layout).
attrappe('sortablejs', `
export default { create() { return { destroy() {} } } }
`)

// dashboardConfig spricht `fetch` direkt an (`apiFetch`) — auch das läuft über
// den globalen Modus, damit „Erneut versuchen" und Fehlerlage echt sind.
globalThis.fetch = async () => {
  globalThis.__ux2d3cAufruf()
  if (lage.modus === 'offen') return new Promise(() => {})
  if (lage.modus === 'fehler') return { ok: false, status: 500, json: async () => ({ exc: 'HTTP 500' }) }
  return { ok: true, status: 200, json: async () => ({ message: [] }) }
}

// kanbanApi.js: das Moderationsbrett.
attrappe('kanbanApi.js', `
export async function getBoardData() {
  // Wie im Betrieb: getBoardData wirft bei einem Serverfehler (kein leeres
  // Brett) — das Brett muss den Fehler zeigen, nicht "keine Vorschlaege".
  if (globalThis.__ux2d3cModus() === 'fehler') {
    globalThis.__ux2d3cAufruf()
    throw Object.assign(new Error('HTTP 500'), { status: 500, exc_type: 'ServerError' })
  }
  return globalThis.__ux2d3cAntwort({ vorschlaege: [], konflikte: [], staging: [], notifications: {}, abgelehnt: [] })
}
export async function getModerationCount() { return { count: 0 } }
export async function getRessources() { return { resources: [], types: [] } }
export async function saveStagingState() { return {} }
export async function finalizeStagedEvents() { return {} }
export async function getConflictPartner() { return null }
export async function resolveConflict() { return {} }
export async function updateSeriesBatchFast() { return {} }
export async function deleteSeriesBatchFast() { return {} }
`)

globalThis.__ux2d3cLeer = (endpunkt) => {
  const e = String(endpunkt)
  if (e.includes('get_dsgvo_uebersicht')) {
    return { mitglieder: [], stats: { ok: 0, widerrufen: 0, fehlt: 0 } }
  }
  if (e.includes('get_loeschantraege')) return []
  if (e.includes('admin_hub')) {
    return {
      mitglieder: { gesamt: 0, mitglied: 0, gast: 0, passives_mitglied: 0, passiver_gast: 0 },
      dsgvo: { ok: 0, widerrufen: 0, fehlt: 0 },
      anmeldungen: { gesamt: 0, diesen_monat: 0, offen: 0, nach_status: {} },
      links: { aktiv: 0, inaktiv: 0, gesamt_anmeldungen: 0, top: [] },
    }
  }
  if (e.includes('permissions.get_session_info')) return { can_moderate: true }
  if (e.includes('get_user_config')) return []
  return {}
}
globalThis.__ux2d3cAntwort = (daten) => antwort(daten)
globalThis.__ux2d3cModus = () => lage.modus

test.after(() => rmSync(TMP, { recursive: true, force: true }))

// ══════════════════════════════════════════════════════════════════════════
// Löschantragsliste — der Import-Befund und beide Leerzustände
test('UX2d3c · Löschanträge: das Skelett wird aufgelöst (Import vorhanden)', () => {
  const quelle = readFileSync(join(SRC.pathname, 'components/mitglieder/LoeschantraegeListe.vue'), 'utf8')
  assert.match(quelle, /import DkSkelett from '\.\.\/ui\/DkSkelett\.vue'/, 'DkSkelett wird benutzt, aber nicht importiert')
})

test('UX2d3c · Löschanträge: leere Antwort erklärt den Zustand, ohne Fehler', async () => {
  lage.modus = 'leer'
  const Komponente = await seite('components/mitglieder/LoeschantraegeListe.vue')
  const { host, app, warnungen } = await mounten(Komponente, { geladen: true, laedt: false, antraege: [] })
  await warte(20)
  const sichtbar = text(host)
  assert.match(sichtbar, /Keine Löschanträge/, 'Leerzustand fehlt')
  assert.match(sichtbar, /Zurzeit wartet kein Antrag/, 'Erklärung fehlt')
  assert.doesNotMatch(sichtbar, /nicht geladen/, 'Leerzustand wird als Fehler gezeigt')
  // Keine Vue-Warnung über eine unbekannte Komponente (der Import-Befund).
  assert.deepEqual(
    warnungen.filter((w) => /Failed to resolve component/i.test(w)),
    [],
    'Vue konnte eine Komponente nicht auflösen: ' + warnungen.join(' | '),
  )
  app.unmount()
})

test('UX2d3c · Löschanträge: beim Neuladen nach Filterwechsel keine veraltete Leeraussage', async () => {
  // Vorher blieb `geladen` wahr — „Für diese Auswahl gibt es keine Anträge."
  // stand da, bevor die neue Auswahl geantwortet hatte.
  lage.modus = 'leer'
  const Komponente = await seite('components/mitglieder/LoeschantraegeListe.vue')
  const { host, app } = await mounten(Komponente, {
    geladen: true,
    laedt: true,
    antraege: [],
    filter: 'abgelehnt',
  })
  await warte(20)
  const sichtbar = text(host)
  assert.doesNotMatch(sichtbar, /Für diese Auswahl gibt es keine Anträge/, 'veraltete Leeraussage während des Ladens')
  assert.doesNotMatch(sichtbar, /Keine Löschanträge/, 'veralteter Leerzustand während des Ladens')
  app.unmount()
})

// ══════════════════════════════════════════════════════════════════════════
// Datenschutz — Fehlertext aus dem Katalog, „Erneut versuchen" lädt neu
test('UX2d3c · Datenschutz: Fehler nennt eine Erklärung (kein „HTTP 500") und lädt erneut', async () => {
  lage.modus = 'fehler'
  lage.aufrufe = 0
  const Komponente = await seite('pages/mitglieder/Datenschutz.vue')
  const { host, app } = await mounten(Komponente)
  await warte(30)

  const sichtbar = text(host)
  assert.match(sichtbar, /Datenschutz nicht geladen/, 'Fehlerfläche fehlt')
  assert.match(sichtbar, /Der Server antwortet gerade nicht/, 'Katalogtext fehlt')
  assert.doesNotMatch(sichtbar, /HTTP 500/, 'roher Statuscode steht im Bild')

  const vorher = lage.aufrufe
  const knopf = knopfMitText(host, 'Erneut versuchen')
  assert.ok(knopf, 'kein „Erneut versuchen"-Knopf')
  lage.modus = 'leer'
  knopf.dispatchEvent(new window.Event('click', { bubbles: true }))
  await warte(30)
  assert.ok(lage.aufrufe > vorher, '„Erneut versuchen" hat keinen neuen Ladevorgang ausgelöst')
  app.unmount()
})

test('UX2d3c · Datenschutz: leere Gemeinde zeigt Leerzustände mit Erklärung und Weg', async () => {
  lage.modus = 'leer'
  const Komponente = await seite('pages/mitglieder/Datenschutz.vue')
  const { host, app } = await mounten(Komponente)
  await warte(30)
  const sichtbar = text(host)
  assert.match(sichtbar, /Keine offenen Löschanträge/, 'Leerzustand der Anträge fehlt')
  assert.match(sichtbar, /Zurzeit wartet kein Antrag/, 'Erklärung der Anträge fehlt')
  assert.match(sichtbar, /Noch keine Person erfasst/, 'Leerzustand der Einwilligungen fehlt')
  assert.match(sichtbar, /Zu den Personen/, 'nächster Schritt fehlt')
  app.unmount()
})

test('UX2d3c · Datenschutz: während des Ladens steht kein Leerzustand', async () => {
  lage.modus = 'offen'
  const Komponente = await seite('pages/mitglieder/Datenschutz.vue')
  const { host, app } = await mounten(Komponente)
  await warte(20)
  const sichtbar = text(host)
  assert.doesNotMatch(sichtbar, /Keine offenen Löschanträge/, 'Leerzustand während des Ladens')
  assert.doesNotMatch(sichtbar, /Noch keine Person erfasst/, 'Leerzustand während des Ladens')
  app.unmount()
  lage.modus = 'leer'
})

// ══════════════════════════════════════════════════════════════════════════
// Startseite — Fehlerzustand statt leerer Bildschirm, Leerzustand mit Weg
test('UX2d3c · Startseite: gescheitertes Laden zeigt eine Erklärung und lädt erneut', async () => {
  lage.modus = 'fehler'
  lage.aufrufe = 0
  const Komponente = await seite('pages/Home.vue')
  const { host, app } = await mounten(Komponente)
  await warte(40)

  const sichtbar = text(host)
  assert.match(sichtbar, /Übersicht nicht geladen/, 'Fehlerfläche fehlt (Bildschirm war vorher leer)')
  assert.match(sichtbar, /Der Server antwortet gerade nicht/, 'Katalogtext fehlt')

  const vorher = lage.aufrufe
  const knopf = knopfMitText(host, 'Erneut versuchen')
  assert.ok(knopf, 'kein „Erneut versuchen"-Knopf')
  lage.modus = 'leer'
  knopf.dispatchEvent(new window.Event('click', { bubbles: true }))
  await warte(40)
  assert.ok(lage.aufrufe > vorher, '„Erneut versuchen" hat keinen neuen Ladevorgang ausgelöst')
  app.unmount()
})

test('UX2d3c · Startseite: keine sichtbare Karte erklärt sich und bietet die Wege zurück', async () => {
  lage.modus = 'leer'
  const Komponente = await seite('pages/Home.vue')
  const { host, app } = await mounten(Komponente)
  await warte(40)
  const sichtbar = text(host)
  assert.match(sichtbar, /Keine Karten sichtbar/, 'Leerzustand fehlt')
  assert.match(sichtbar, /ausgeblendet/, 'Erklärung fehlt')
  assert.ok(knopfMitText(host, 'Karten einblenden'), 'Weg „Karten einblenden" fehlt')
  assert.ok(knopfMitText(host, 'Standardübersicht'), 'Weg „Standardübersicht" fehlt')
  app.unmount()
})

test('UX2d3c · Startseite: während des Ladens steht kein Leerzustand', async () => {
  lage.modus = 'offen'
  const Komponente = await seite('pages/Home.vue')
  const { host, app } = await mounten(Komponente)
  await warte(20)
  assert.doesNotMatch(text(host), /Keine Karten sichtbar/, 'Leerzustand während des Ladens')
  app.unmount()
  lage.modus = 'leer'
})

// ══════════════════════════════════════════════════════════════════════════
// Mitglieder-Übersicht — Fehler mit Weg zurück statt DkHint ohne Wiederholung
test('UX2d3c · Übersicht: Fehler nennt eine Erklärung und lädt erneut', async () => {
  lage.modus = 'fehler'
  lage.aufrufe = 0
  const Komponente = await seite('pages/mitglieder/Uebersicht.vue')
  const { host, app } = await mounten(Komponente)
  await warte(40)

  const sichtbar = text(host)
  assert.match(sichtbar, /Übersicht nicht geladen/, 'Fehlerfläche fehlt')
  assert.match(sichtbar, /Der Server antwortet gerade nicht/, 'Katalogtext fehlt')
  assert.doesNotMatch(sichtbar, /Unbekannter Fehler|HTTP 500/, 'roher Fehlertext steht im Bild')

  const vorher = lage.aufrufe
  const knopf = knopfMitText(host, 'Erneut versuchen')
  assert.ok(knopf, 'kein „Erneut versuchen"-Knopf')
  lage.modus = 'leer'
  knopf.dispatchEvent(new window.Event('click', { bubbles: true }))
  await warte(40)
  assert.ok(lage.aufrufe > vorher, '„Erneut versuchen" hat keinen neuen Ladevorgang ausgelöst')
  app.unmount()
})

test('UX2d3c · Übersicht: leere Gemeinde zeigt Null-Kacheln, keinen erfundenen Hinweis', async () => {
  lage.modus = 'leer'
  const Komponente = await seite('pages/mitglieder/Uebersicht.vue')
  const { host, app } = await mounten(Komponente)
  await warte(40)
  const sichtbar = text(host)
  assert.match(sichtbar, /Personen/, 'Kacheln fehlen')
  assert.doesNotMatch(sichtbar, /Zu erledigen/, '„Zu erledigen" steht da, obwohl nichts zu tun ist')
  app.unmount()
})

// ══════════════════════════════════════════════════════════════════════════
// Moderation — leeres Brett erklärt sich; ein Fehler wird nicht zu „keine Vorschläge"
test('UX2d3c · Moderation: leeres Brett erklärt beide Spalten', async () => {
  lage.modus = 'leer'
  const Komponente = await seite('pages/Moderation.vue')
  const { host, app } = await mounten(Komponente)
  await warte(40)
  const sichtbar = text(host)
  assert.match(sichtbar, /Zu prüfen/, 'Seitentitel fehlt')
  assert.match(sichtbar, /Keine Vorschläge/, 'Leerzustand der Vorschläge fehlt')
  assert.match(sichtbar, /Es warten gerade keine neuen Terminvorschläge/, 'Erklärung fehlt')
  assert.match(sichtbar, /Keine Konflikte/, 'Leerzustand der Konflikte fehlt')
  app.unmount()
})

test('UX2d3c · Moderation: gescheitertes Laden heißt „nicht geladen", nicht „keine Vorschläge"', async () => {
  lage.modus = 'fehler'
  lage.aufrufe = 0
  const Komponente = await seite('pages/Moderation.vue')
  const { host, app } = await mounten(Komponente)
  await warte(60)
  const sichtbar = text(host)
  assert.match(sichtbar, /Termine nicht geladen/, 'Fehlerzustand des Bretts fehlt')
  assert.match(sichtbar, /Der Server antwortet gerade nicht/, 'Katalogtext fehlt')
  assert.doesNotMatch(sichtbar, /Keine Vorschläge/, 'Fehlerzustand zeigt zusätzlich „Keine Vorschläge“')

  const vorher = lage.aufrufe
  const knopf = knopfMitText(host, 'Erneut versuchen')
  assert.ok(knopf, 'kein „Erneut versuchen"-Knopf')
  lage.modus = 'leer'
  knopf.dispatchEvent(new window.Event('click', { bubbles: true }))
  await warte(60)
  assert.ok(lage.aufrufe > vorher, '„Erneut versuchen" hat keinen neuen Ladevorgang ausgelöst')
  app.unmount()
})
