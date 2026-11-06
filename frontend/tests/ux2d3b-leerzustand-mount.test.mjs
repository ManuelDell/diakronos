/**
 * UX2d3b · Leerzustände und Fehlerzustände WIRKLICH gemountet.
 *
 * BEFUND (Review UX2d3a/C und I5): Ob eine Seite „nichts da" behauptet, ob
 * sie einen Fehler nennt und ob „Erneut versuchen" wirklich einen neuen
 * Ladevorgang auslöst, lässt sich am Quelltext nicht beweisen. Deshalb lädt
 * dieser Test die Seiten wie im Betrieb (`vue/compiler-sfc` → echte
 * Komponente → `createApp().mount()` in jsdom), stellt die Server-Antwort und
 * schaut, was auf dem Bildschirm steht.
 *
 * GEPRÜFT WIRD JE SEITE:
 *   1. leere Antwort  → ein Leerzustand ist sichtbar, mit Erklärung und (wo
 *      sinnvoll) einem Primärknopf bzw. einem Weg weiter;
 *   2. Fehler         → der Fehlerzustand nennt eine Meldung UND „Erneut
 *      versuchen" startet einen NEUEN Aufruf (Zähler im Test);
 *   3. während des Ladens steht KEIN Leerzustand (Review Punkt C).
 *
 * WARUM jsdom: Das Projekt hat es für die Feld-Tests schon als devDependency
 * (siehe `ux2f2a-feld-baustein.test.mjs`); es bleibt aus dem Laufzeit-Image
 * heraus, weil der Frontend-Stage `node_modules` nach dem Build verwirft.
 *
 * Die Seiten binden ihre Daten über `apiCall(...)`/Composables an den Server.
 * Der Test ersetzt genau diese Module durch Attrappen — alles andere (Vue,
 * Dk-Komponenten, Vorlage) ist echt.
 *
 * Lauf: node --test tests/ux2d3b-leerzustand-mount.test.mjs   (cwd = frontend/)
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, mkdtempSync, writeFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, dirname, resolve, basename } from 'node:path'
import { pathToFileURL } from 'node:url'
import { JSDOM } from 'jsdom'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'

// ── DOM zuerst (Vue greift beim Import auf `document` zu) ─────────────────
const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
for (const schluessel of ['window', 'document', 'Node', 'Element', 'HTMLElement', 'Event',
  'MouseEvent', 'SVGElement', 'CSS', 'getComputedStyle', 'MutationObserver']) {
  globalThis[schluessel] = dom.window[schluessel]
}
const Vue = await import('vue')

const SRC = new URL('../src/diakonos/', import.meta.url)

// ── SFC → ES-Modul (wie ux2f2a-feld-baustein.test.mjs) ────────────────────
const TMP = mkdtempSync(join(tmpdir(), 'ux2d3b-'))
const cache = new Map()
const VUE_URL = import.meta.resolve('vue')

/** Ersetzte Module: Schlüssel = Dateiname der Attrappe, Wert = Quelltext. */
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
  code = code.replace(/from\s+['"](\.[^'"]+)['"]/g, (voll, spec) => {
    const name = basename(spec)
    const ziel = resolve(dirname(abs), spec)
    if (attrappen.has(name)) return `from '${attrappen.get(name)}'`
    return `from '${pathToFileURL(spec.endsWith('.vue') ? kompilieren(ziel) : ziel).href}'`
  })
  const ziel = resolve(TMP, filename.replace(/\.vue$/, '') + '.' + cache.size + '.mjs')
  writeFileSync(ziel, code)
  cache.set(abs, ziel)
  return ziel
}

async function seite(relativ) {
  const ziel = kompilieren(join(SRC.pathname, relativ))
  // Zwischenspeicher je Durchlauf: jede Seite frisch mounten.
  cache.delete(join(SRC.pathname, relativ))
  return (await import(pathToFileURL(kompilieren(join(SRC.pathname, relativ))).href)).default
}

const tick = () => new Promise((loese) => setTimeout(loese, 0))
const warte = (ms) => new Promise((loese) => setTimeout(loese, ms))

async function mounten(Komponente) {
  const host = document.createElement('div')
  document.body.appendChild(host)
  const warnungen = []
  const app = Vue.createApp(Komponente)
  app.config.warnHandler = (meldung) => warnungen.push(meldung)
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

// ── Attrappen der Datenschicht ─────────────────────────────────────────────
/** Zustand der Server-Antworten; jeder Aufruf zählt (`aufrufe`). */
const lage = { modus: 'leer', aufrufe: 0 }

// useApi.js: `apiCall(...)` liefert je Endpunkt die passende leere Antwort.
attrappe('useApi.js', `
export class AuditConfirmationRequired extends Error {}
export async function apiCall(endpunkt) {
  globalThis.__ux2d3bAufruf(endpunkt)
  const leer = globalThis.__ux2d3bLeer(endpunkt)
  return globalThis.__ux2d3bAntwort(leer)
}
export async function apiAntwortPruefen(r) { return r }
export const navigate = () => {}
`)

// useVerwaltung.js: Kalender-Verwaltung und Kontenliste.
attrappe('useVerwaltung.js', `
export async function kalenderVerwaltungLaden() {
  globalThis.__ux2d3bAufruf('kalenderVerwaltungLaden')
  return globalThis.__ux2d3bAntwort({ kalender: [], rollen: [] })
}
export async function kontenListe() { return [] }
export async function kalenderAnlegen() { return {} }
export async function kalenderAendern() { return {} }
export async function kalenderLoeschen() { return {} }
export function serverFehlerText(e, ersatz) {
  // Wie im Betrieb: der Katalogtext des Fehlers, sonst der Ersatzsatz.
  return e && e.status === 500 ? 'Der Server antwortet gerade nicht. Versuche es in ein paar Minuten noch einmal.' : ersatz
}
`)

// useLoeschantraege.js: Zählung offener Anträge (Übersicht).
attrappe('useLoeschantraege.js', `
export async function offeneAntraegeZaehlen() { return 0 }
`)

globalThis.__ux2d3bAufruf = () => { lage.aufrufe += 1 }
globalThis.__ux2d3bLeer = (endpunkt) => {
  if (String(endpunkt).includes('dienstplan')) return { vorbereitung: [], einsatz: [] }
  if (String(endpunkt).includes('admin_hub')) {
    return {
      mitglieder: { gesamt: 0, mitglied: 0, gast: 0, passives_mitglied: 0, passiver_gast: 0 },
      dsgvo: { ok: 0, widerrufen: 0, fehlt: 0 },
      anmeldungen: { gesamt: 0, diesen_monat: 0, offen: 0, nach_status: {} },
      links: { aktiv: 0, inaktiv: 0, gesamt_anmeldungen: 0, top: [] },
    }
  }
  return {}
}
globalThis.__ux2d3bAntwort = (daten) => {
  if (lage.modus === 'fehler') {
    return Promise.reject(Object.assign(new Error('HTTP 500'), { status: 500 }))
  }
  return Promise.resolve(daten)
}

test.after(() => rmSync(TMP, { recursive: true, force: true }))

// ══════════════════════════════════════════════════════════════════════════
// Dienstplan — Fehlerzustand mit „Erneut versuchen"
test('UX2d3b · Dienstplan: Fehler nennt eine Meldung, „Erneut versuchen" lädt neu', async () => {
  lage.modus = 'fehler'
  lage.aufrufe = 0
  const Komponente = await seite('pages/Dienstplan.vue')
  const { host, app } = await mounten(Komponente)
  await warte(20)

  const sichtbar = text(host)
  assert.match(sichtbar, /Dienstplan nicht geladen/, 'Fehlerzustand fehlt')
  assert.match(
    sichtbar,
    /Der Server antwortet gerade nicht/,
    'Meldung ist keine Erklärung (Katalogtext erwartet)',
  )

  const vorher = lage.aufrufe
  const knopf = knopfMitText(host, 'Erneut versuchen')
  assert.ok(knopf, 'kein „Erneut versuchen"-Knopf')
  knopf.dispatchEvent(new window.Event('click', { bubbles: true }))
  await warte(20)
  assert.equal(lage.aufrufe, vorher + 1, '„Erneut versuchen" hat keinen neuen Ladevorgang ausgelöst')
  app.unmount()
})

test('UX2d3b · Dienstplan: leere Antwort zeigt den ruhigen Zustand, kein Fehler', async () => {
  lage.modus = 'leer'
  const Komponente = await seite('pages/Dienstplan.vue')
  const { host, app } = await mounten(Komponente)
  await warte(20)
  const sichtbar = text(host)
  assert.doesNotMatch(sichtbar, /nicht geladen/, 'leere Antwort wird als Fehler gezeigt')
  assert.match(sichtbar, /Keine anstehende Vorbereitung/, 'Leerzustand fehlt')
  assert.match(sichtbar, /Kein anstehender Einsatz/, 'Leerzustand fehlt')
  app.unmount()
})

// Kalender-Verwaltung — leer → Erklärung + Primärknopf „Neuer Kalender"
test('UX2d3b · KalenderVerwaltung: leerer Bestand erklärt den nächsten Schritt', async () => {
  lage.modus = 'leer'
  const Komponente = await seite('pages/KalenderVerwaltung.vue')
  const { host, app } = await mounten(Komponente)
  await warte(20)
  const sichtbar = text(host)
  assert.match(sichtbar, /Noch keine Kalender/, 'Leerzustand fehlt')
  assert.match(sichtbar, /Lege den ersten Kalender an/, 'Erklärung fehlt')
  assert.ok(knopfMitText(host, 'Neuer Kalender'), 'Primärknopf fehlt')
  app.unmount()
})

test('UX2d3b · KalenderVerwaltung: Fehler nennt eine Meldung statt einer leeren Liste', async () => {
  lage.modus = 'fehler'
  const Komponente = await seite('pages/KalenderVerwaltung.vue')
  const { host, app } = await mounten(Komponente)
  await warte(20)
  const sichtbar = text(host)
  assert.match(sichtbar, /Der Server antwortet gerade nicht/, 'Fehlermeldung fehlt')
  assert.doesNotMatch(sichtbar, /Noch keine Kalender/, 'Fehler wird als Leerzustand gezeigt')
  app.unmount()
})

// Mitglieder-Übersicht — Kennzahlen mit 0, kein toter „Zu erledigen"-Block
test('UX2d3b · Übersicht: leere Gemeinde zeigt Null-Kacheln, keinen erfundenen Hinweis', async () => {
  lage.modus = 'leer'
  const Komponente = await seite('pages/mitglieder/Uebersicht.vue')
  const { host, app } = await mounten(Komponente)
  await warte(20)
  const sichtbar = text(host)
  assert.match(sichtbar, /Personen/, 'Kacheln fehlen')
  assert.doesNotMatch(sichtbar, /Zu erledigen/, '„Zu erledigen" steht da, obwohl nichts zu tun ist')
  app.unmount()
})
