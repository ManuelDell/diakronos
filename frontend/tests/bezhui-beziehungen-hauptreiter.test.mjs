/**
 * BEZH-UI — Beziehungen ohne eigenen Reiter, im Hauptreiter der Person;
 * Selbstpflege im Haushalt (Befund Manuel, 17.11.2026; Review waveton:
 * „die Liste steckt hinter einem Klick — das ist ein versteckter Reiter“).
 *
 * Die Server-Seite ist fertig (`api.beziehungen` -> `rechte.darf_beziehung`,
 * `mitglieder.get_mitglied_detail` liefert `permissions.beziehungen_pflegen`
 * und `permissions.beziehungen_alle`). Dieser Test haelt fest, was die
 * Oberflaeche daraus macht — am ECHTEN `MitgliedDetail.vue` montiert
 * (jsdom + `@vue/compiler-sfc`, `fetch` als Attrappe), nicht als
 * Quelltext-Regex:
 *
 *  1. Der Reiter „Details“ zeigt Namen UND Art der Beziehungen SOFORT, ohne
 *     Klick, waehrend „Persönliche Daten“ sichtbar bleibt; kein Reiter
 *     „Beziehungen“; ohne Beziehungen der kurze Leertext.
 *  2. Im Bearbeiten-Modus bleibt „Persönliche Daten“ sichtbar — die
 *     Beziehungs-Karte verdeckt nichts.
 *  3. Eintragen/Entfernen-Knoepfe NUR nach
 *     `permissions.beziehungen_pflegen === true` (true/false beides geprueft).
 *  4. Ohne `beziehungen_alle` steht ueber der Auswahl der Haushalts-Hinweis;
 *     eine leere Auswahl zeigt denselben Hinweis statt eines leeren Kastens.
 *  5. Der Serverfehler „anderer Haushalt“ (403) kommt verstaendlich an.
 */
import assert from 'node:assert/strict'
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, symlinkSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { dirname, resolve } from 'node:path'
import test from 'node:test'
import { fileURLToPath, pathToFileURL } from 'node:url'

import { compileScript, parse } from 'vue/compiler-sfc'

/**
 * jsdom EINMAL holen und merken. Der Import ist der teuerste Schritt des
 * Laufs (~15–20 s Modulaufloesung); er wird vor dem Test gerechnet, damit
 * der Test selbst nicht ins Zeitfenster des Modulladens faellt.
 */
let _jsdom = null
async function jsdomLaden() {
  if (!_jsdom) _jsdom = await import('jsdom')
  return _jsdom
}

const HIER = dirname(fileURLToPath(import.meta.url))
const FRONTEND = resolve(HIER, '..')
const SRV = path.join(FRONTEND, 'src')
const DETAIL = path.join(SRV, 'diakonos/pages/MitgliedDetail.vue')

const lies = (abs) => readFileSync(abs, 'utf8')

const HAUSHALT_HINWEIS = 'Du kannst Personen aus deinem Haushalt (gleiche Anschrift) eintragen.'
// Importe eines Quelltexts umschreiben: Zielpfad aufloesen (auch ohne Endung)
// und auf `.mjs` setzen. Eine STELLE fuer `.vue`-Dateien und `.js`-Module —
// sonst laufen zwei Fassungen der Regel auseinander.
const IMPORT_MUSTER = /(?:from\s+|import\s*\()(['"])(\.\.?\/[^'"\n]+)\1/g
function importeUmschreiben(code, verzeichnis, beiTreffer) {
  return code.replace(IMPORT_MUSTER, (ganz, q, pfad) => {
    const basis = path.resolve(verzeichnis, pfad)
    const endung = ['.vue', '.js', '.mjs'].find(e => existsSync(basis + e))
    const mitEndung = endung ? basis + endung : (existsSync(basis) ? basis : null)
    if (!mitEndung) return ganz
    const neuPfad = (endung ? pfad + endung : pfad).replace(/\.(vue|js)$/, '.mjs')
    beiTreffer(mitEndung, neuPfad)
    return ganz.replace(q + pfad + q, q + neuPfad + q)
  })
}
const text = (el) => (el?.textContent || '').replace(/\s+/g, ' ').trim()
const knopf = (el, teil) => [...el.querySelectorAll('button')].find(b => text(b).includes(teil))
const warte = (ms = 60) => new Promise((r) => setTimeout(r, ms))

// ═══ 1. Mount-Helfer: die echte Detailseite (wie dev-b4a, nur Seite) ═══════

/**
 * `.vue`-Bauteil bzw. JS-Modul als `.mjs` neben seinen Quellbaum schreiben:
 * nur IMPORTE werden umgeschrieben, das Ziel liegt unter demselben Weg
 * ab `src/`. Kandidaten, die es nicht gibt (Beispiele in Kommentaren),
 * bleiben unberuehrt.
 *
 * Die .mjs-Dateien lagen zuerst flach unter `diakonos/pages/` — dann zeigten
 * die relativen Importe (`../ui/x.mjs`) ins Leere. Der Baum spiegelt deshalb
 * `src/` exakt (`diakonos/pages/`, `diakonos/composables/`, …), nur die
 * Endung ist `.mjs`; die Import-Pfade bleiben unveraendert gueltig.
 */
function bauteilSchreiben(abs, ausgabe, wache = new Set()) {
  if (wache.has(abs)) return
  wache.add(abs)
  const rel = path.relative(SRV, abs)
  let code
  if (abs.endsWith('.vue')) {
    const { descriptor } = parse(lies(abs), { filename: abs })
    assert.ok(descriptor.script || descriptor.scriptSetup, `${path.basename(abs)}: kein Skript`)
    code = compileScript(descriptor, { id: path.basename(abs), inlineTemplate: true }).content
  } else {
    code = lies(abs)
  }
  // Ergaenzungslose Importe (`'./useSession'`) behalten ihre Form — die
  // Endung muss im Temp-Baum `.mjs` sein, wie bei den `.js`-Importen.
  const baum = importeUmschreiben(code, path.dirname(abs), (zielAbs) => {
    bauteilSchreiben(zielAbs, ausgabe, wache)
  })
  const zielDatei = path.join(ausgabe, rel.replace(/\.(vue|js|mjs)$/, '.mjs'))
  mkdirSync(path.dirname(zielDatei), { recursive: true })
  writeFileSync(zielDatei, baum, 'utf8')
}

/** Detailantwort des Servers: eine Person mit Beziehungen. */
function detailAntwort({ beziehungen = [], pflegen = false, alle = false } = {}) {
  // Frappe-Form: `apiCall` gibt `data.message` weiter (die Seite liest
  // `response?.data ?? response` und `response?.permissions`).
  return {
    message: {
      success: true,
      permissions: { beziehungen_pflegen: pflegen, beziehungen_alle: alle },
      data: {
        name: 'M-anna',
        vorname: 'Anna',
        nachname: 'Beispiel',
        status: 'Mitglied',
        beziehungen,
        dsgvo: {
          datenschutz: true, datenschutz_datum: '2026-01-02',
          foto: false, foto_datum: null,
          werbung: false, werbung_datum: null,
        },
      },
    },
  }
}

/**
 * Die ECHTE Detailseite montieren. `fetch` antwortet wie der Server (ein
 * `apiCall` -> POST `/api/method/<pfad>`); `auswahl` beantwortet
 * `get_beziehungen_auswahl`, alles andere die Detailantwort.
 */
async function rendern({ pflegen = false, alle = false, beziehungen = [], auswahl = [], eintragenFehler = null } = {}) {
  const { JSDOM } = await jsdomLaden()
  const dom = new JSDOM('<!doctype html><html><body></body></html>', {
    url: 'http://localhost/diakronos/',
    pretendToBeVisual: true,
  })
  const { window } = dom
  globalThis.window = window
  globalThis.document = window.document
  globalThis.localStorage = window.localStorage
  globalThis.HTMLElement = window.HTMLElement
  globalThis.SVGElement = window.SVGElement
  globalThis.Element = window.Element
  globalThis.Node = window.Node
  globalThis.Event = window.Event
  globalThis.MouseEvent = window.MouseEvent
  globalThis.getComputedStyle = window.getComputedStyle.bind(window)
  window.__DIakonosBOOT = {
    basePath: '/diakronos',
    csrf_token: 'test-token',
    // Mitgliederverwaltung: nur damit „Bearbeiten“ erscheint (`canEdit`) —
    // die Beziehungs-Knoepfe haengen NICHT daran, sondern am Server-Flag.
    is_admin: true,
    ist_mitgliederverwaltung: true,
  }

  const rufe = []
  const gemeldet = []
  window.fetch = async (adresse, optionen = {}) => {
    const pfad = String(adresse)
    let rumpf = {}
    try { rumpf = JSON.parse(optionen.body || '{}') } catch { /* egal */ }
    rufe.push({ pfad, rumpf })
    const antwort = (daten) => ({
      ok: true,
      status: 200,
      headers: { get: () => 'application/json' },
      // `apiCall` liest `message` (Frappe-Form) und `datenVon` bevorzugt das
      // schon geparste Feld `dkDaten` — beides wird hier bedient.
      dkDaten: daten,
      json: async () => daten,
      text: async () => JSON.stringify(daten),
    })
    if (pfad.includes('mitglieder.get_mitglied_detail')) {
      return antwort(detailAntwort({ beziehungen, pflegen, alle }))
    }
    if (pfad.includes('beziehungen.get_beziehungen_auswahl')) {
      return antwort({ message: { success: true, data: auswahl } })
    }
    if (pfad.includes('beziehungen.add_beziehung')) {
      if (eintragenFehler) throw eintragenFehler
      return antwort({ message: { success: true, data: {} } })
    }
    return antwort({ message: { success: true, data: {} } })
  }
  globalThis.fetch = window.fetch

  // Meldungen mitschreiben: die App-Toasts haengen an `showToast`.
  const zeitgeber = new Set()
  const setTimeoutOriginal = globalThis.setTimeout
  globalThis.setTimeout = (fn, ms, ...rest) => {
    const t = setTimeoutOriginal((...a) => { zeitgeber.delete(t); fn(...a) }, ms, ...rest)
    zeitgeber.add(t)
    return t
  }

  const ausgabe = mkdtempSync(path.join(tmpdir(), 'bezhui-'))
  bauteilSchreiben(DETAIL, ausgabe)
  symlinkSync(path.join(FRONTEND, 'node_modules'), path.join(ausgabe, 'node_modules'), 'dir')

  const { createApp, nextTick } = await import('vue')
  const modul = await import(pathToFileURL(
    path.join(ausgabe, path.relative(SRV, DETAIL).replace(/\.vue$/, '.mjs')),
  ).href)
  const ziel = window.document.createElement('div')
  window.document.body.appendChild(ziel)
  // Die Mitglieds-ID holt die Seite vom Router (`getRouteParam('id',
  // 'MitgliedDetail')`). Dessen Wert `acceptedRoute` startet beim Laden des
  // Moduls mit der DAMALIGEN Adresse (hier: die Personen-Liste) und wird nur
  // ueber `hashchange` nachgezogen.
  //
  // Reihenfolge: ERST den Adresswechsel anstossen (ein `hashchange`-Ereignis,
  // das noch niemand hoert), DANN das Router-Modul laden. Es liest den Hash
  // beim Start und kennt die Person sofort; die SEITE holt `getRouteParam`
  // aus DIESER Fassung, weil sie ihren Router-Import auf denselben Weg zeigt
  // (gleiches Modul, gleicher Zustand). Erst danach wird montiert — so laedt
  // `onMounted` die Person wirklich.
  window.location.hash = '#/mitglied/M-anna'
  await import(
    pathToFileURL(path.join(ausgabe, 'diakonos/router.mjs')).href
    + '?bezhui=' + path.basename(ausgabe)
  )
  await warte(150)

  const app = createApp(modul.default)
  app.config.warnHandler = () => {}
  app.mount(ziel)
  await warte(150)
  await nextTick()
  await warte(150)
  // Toasts liegen ausserhalb des Mount-Punkts: aus dem Dokument lesen.
  const toasts = () => [...window.document.querySelectorAll('[class*="toast"]')]
    .map(el => text(el)).filter(Boolean)
  return { window, ziel, rufe, gemeldet, toasts, app, nextTick, ausgabe, zeitgeber }
}

/** Abbau NACH dem Unmount: erst warten, dann das Temp-Verzeichnis loeschen. */
async function abbauen(ctx) {
  try { ctx.app.unmount() } catch { /* schon weg */ }
  ctx.zeitgeber?.forEach((t) => clearTimeout(t))
  await warte(80)
  try { ctx.window?.close?.() } catch { /* jsdom */ }
  try { rmSync(ctx.ausgabe, { recursive: true, force: true }) } catch { /* egal */ }
}

// ═══ 2. Quelltext-Waechter: kein Reiter, keine Zusammenfassung ════════════

test('BEZH-UI: kein Reiter „Beziehungen“ und kein Aufklapp-Zustand mehr', () => {
  const quelle = lies(DETAIL)
  const stelle = quelle.match(/const tabs = computed\(\(\) => \{[\s\S]*?\n\}\)/)
  assert.ok(stelle, 'Reiterliste vorhanden')
  assert.ok(!/key: 'beziehungen'/.test(stelle[0]),
    'die Reiterliste kennt keinen Eintrag „beziehungen“ mehr')
  // Der fruehere Aufklapp-Zustand („Ansehen“-Knopf, Zusammenfassung,
  // „Zurück zu den persönlichen Daten“) ist ersatzlos weg.
  assert.ok(!/beziehungenAuf/.test(quelle), 'kein Aufklapp-Zustand mehr')
  assert.ok(!/Zurück zu den persönlichen Daten/.test(quelle), 'kein Zurück-Weg mehr')
  assert.ok(!/md-abschnitt/.test(quelle), 'keine Zusammenfassung „N Beziehungen eingetragen“')
})

test('BEZH-UI: die Flags kommen aus der Detailantwort (permissions)', () => {
  const quelle = lies(DETAIL)
  assert.match(quelle, /setzeBeziehungsRechte\(response\?\.permissions\)/,
    'die Seite liest `permissions` der Serverantwort')
  const fn = quelle.match(/function setzeBeziehungsRechte\(perms\) \{[\s\S]*?\n\}/)
  assert.ok(fn, 'setzeBeziehungsRechte vorhanden')
  assert.match(fn[0], /perms\?\.beziehungen_pflegen === true/,
    'genau `=== true` — kein Wahrheitswert aus fremden Feldern')
  assert.match(fn[0], /perms\?\.beziehungen_alle === true/)
  // Die Karte haengt am Hauptreiter, NICHT an einem Flag oder einer Rolle.
  const baustein = quelle.match(/<MitgliedBeziehungen[\s\S]*?\/>/)
  assert.ok(baustein, 'Baustein eingebunden')
  assert.match(baustein[0], /:bearbeitbar="beziehungenPflegen"/,
    'Knoepfe nach dem SERVER-Flag beziehungen_pflegen')
  assert.match(baustein[0], /:alle="beziehungenAlle"/,
    'Haushalts-Lage aus dem Server-Flag beziehungen_alle')
  assert.ok(!/istMitgliederverwaltung\.value && .*beziehungen/i.test(quelle),
    'kein Rollenraten fuer die Beziehungs-Knoepfe')
})

// ═══ 3. Mount: Liste im Hauptreiter, ohne Klick ════════════════════════════

const BEZIEHUNGEN = [
  { name: 'MBZ-1', beziehung_zu: 'M-bruno', beziehung_zu_name: 'Bruno Beispiel', beziehungstyp: 'Kind' },
  { name: 'MBZ-2', beziehung_zu: 'M-carla', beziehung_zu_name: 'Carla Beispiel', beziehungstyp: 'Ehepartner' },
]

test('BEZH-UI: Details zeigt Namen + Art der Beziehungen OHNE Klick', async () => {
  const ctx = await rendern({ beziehungen: BEZIEHUNGEN })
  const inhalt = text(ctx.ziel)
  assert.match(inhalt, /Bruno Beispiel/, 'Name der Beziehung ohne Klick')
  assert.match(inhalt, /Kind/, 'Art der Beziehung ohne Klick')
  assert.match(inhalt, /Carla Beispiel/)
  assert.match(inhalt, /Ehepartner/)
  assert.match(inhalt, /2 Beziehungen/, 'die Karte nennt die Anzahl')
  // „Persönliche Daten“ bleibt daneben stehen (keine Verdraengung).
  assert.match(inhalt, /Persönliche Daten/, '„Persönliche Daten“ bleibt sichtbar')
  assert.match(inhalt, /Anna Beispiel/, 'und zeigt die Stammdaten')
  // Kein Reiter „Beziehungen“ in der Reiterleiste.
  const reiter = [...ctx.ziel.querySelectorAll('[role="tab"], .dk-tab, button')]
    .map(b => text(b))
  assert.ok(!reiter.includes('Beziehungen'), 'kein Reiter „Beziehungen“')
  await abbauen(ctx)
})

test('BEZH-UI: ohne Beziehungen der kurze Leertext, ohne „Ansehen“-Knopf', async () => {
  const ctx = await rendern({ beziehungen: [] })
  const inhalt = text(ctx.ziel)
  assert.match(inhalt, /Keine Beziehungen eingetragen\./)
  assert.ok(!knopf(ctx.ziel, 'Ansehen'), 'kein Aufklapp-Knopf')
  assert.ok(!knopf(ctx.ziel, 'Öffnen'), 'kein Aufklapp-Knopf')
  assert.ok(!knopf(ctx.ziel, 'Beziehung eintragen'),
    'ohne beziehungen_pflegen auch kein Eintragen-Knopf')
  await abbauen(ctx)
})

test('BEZH-UI: Bearbeiten-Modus verdeckt die persönlichen Daten NICHT', async () => {
  const ctx = await rendern({ beziehungen: BEZIEHUNGEN, pflegen: true })
  const bearbeiten = knopf(ctx.ziel, 'Bearbeiten')
  assert.ok(bearbeiten, '„Bearbeiten“ (Mitgliederverwaltung) vorhanden')
  bearbeiten.dispatchEvent(new globalThis.MouseEvent('click', { bubbles: true }))
  await ctx.nextTick()
  await warte()

  const inhalt = text(ctx.ziel)
  assert.match(inhalt, /Persönliche Daten/, 'die Daten-Karte bleibt im Bearbeiten-Modus')
  assert.match(inhalt, /Vorname/, 'das Formular ist offen')
  assert.match(inhalt, /Bruno Beispiel/, 'die Beziehungen stehen weiterhin da')
  assert.ok(knopf(ctx.ziel, 'Speichern'), 'Speichern-Knopf sichtbar')
  await abbauen(ctx)
})

// ═══ 4. Knöpfe nach Flag, Haushalts-Hinweis ════════════════════════════════

test('BEZH-UI: ohne beziehungen_pflegen KEINE Eintragen/Entfernen-Knoepfe', async () => {
  const ctx = await rendern({ beziehungen: BEZIEHUNGEN, pflegen: false })
  const inhalt = text(ctx.ziel)
  assert.match(inhalt, /Bruno Beispiel/, 'die Liste ist auch ohne Recht sichtbar')
  assert.ok(!knopf(ctx.ziel, 'Beziehung eintragen'), 'kein „Beziehung eintragen“ ohne Flag')
  assert.ok(!knopf(ctx.ziel, 'Entfernen'), 'kein „Entfernen“ ohne Flag')
  await abbauen(ctx)
})

test('BEZH-UI: mit beziehungen_pflegen erscheinen Eintragen und Entfernen', async () => {
  const ctx = await rendern({ beziehungen: BEZIEHUNGEN, pflegen: true, alle: true })
  assert.ok(knopf(ctx.ziel, 'Beziehung eintragen'), '„Beziehung eintragen“ mit Flag')
  assert.ok(knopf(ctx.ziel, 'Entfernen'), '„Entfernen“ mit Flag')
  await abbauen(ctx)
})

test('BEZH-UI: ohne beziehungen_alle — Haushalts-Hinweis, auch bei leerer Auswahl', async () => {
  const ctx = await rendern({ beziehungen: [], pflegen: true, alle: false, auswahl: [] })
  const eintragen = knopf(ctx.ziel, 'Beziehung eintragen')
  assert.ok(eintragen, 'Eintragen-Knopf vorhanden')
  eintragen.dispatchEvent(new globalThis.MouseEvent('click', { bubbles: true }))
  await ctx.nextTick()
  await warte()

  const inhalt = text(ctx.ziel)
  assert.ok(inhalt.includes(HAUSHALT_HINWEIS), 'Hinweis auf den eigenen Haushalt')
  assert.match(inhalt, /Andere Beziehungen trägt die Mitgliederverwaltung ein\./)
  assert.ok(knopf(ctx.ziel, 'Abbrechen'), 'das Formular ist offen')
  await abbauen(ctx)
})

test('BEZH-UI: mit beziehungen_alle KEIN Haushalts-Hinweis (Verwaltung waehlt alle)', async () => {
  const ctx = await rendern({ beziehungen: [], pflegen: true, alle: true, auswahl: [] })
  const eintragen = knopf(ctx.ziel, 'Beziehung eintragen')
  eintragen.dispatchEvent(new globalThis.MouseEvent('click', { bubbles: true }))
  await ctx.nextTick()
  await warte()
  assert.ok(!text(ctx.ziel).includes(HAUSHALT_HINWEIS),
    'die Verwaltung bekommt keinen Haushalts-Hinweis')
  await abbauen(ctx)
})

// ═══ 5. Serverfehler: anderer Haushalt (403) verstaendlich ═════════════════

test('BEZH-UI: Serverfehler „anderer Haushalt“ kommt als Klartext an', async () => {
  const ctx = await rendern({
    beziehungen: [],
    pflegen: true,
    alle: false,
    auswahl: [{ mitglied: 'M-fremd', name: 'Fremde Person', in_beziehung: false }],
    eintragenFehler: Object.assign(
      new Error('Selbst eintragen lassen sich nur Personen aus deinem Haushalt '
        + '(gleiche Anschrift). Andere Beziehungen trägt die Mitgliederverwaltung ein.'),
      { status: 403, exc_type: 'PermissionError' },
    ),
  })
  const eintragen = knopf(ctx.ziel, 'Beziehung eintragen')
  eintragen.dispatchEvent(new globalThis.MouseEvent('click', { bubbles: true }))
  await ctx.nextTick()
  const eingabe = ctx.ziel.querySelector('.dk-ma-input')
  assert.ok(eingabe, 'Personensuche vorhanden')
  eingabe.dispatchEvent(new globalThis.MouseEvent('click', { bubbles: true }))
  await ctx.nextTick()
  await warte(400)
  await ctx.nextTick()
  const eintrag = [...ctx.ziel.querySelectorAll('.dk-ma-eintrag')]
    .find(e => text(e).includes('Fremde Person'))
  assert.ok(eintrag, 'die Fremde Person steht in der Auswahl')
  eintrag.dispatchEvent(new globalThis.MouseEvent('mousedown', { bubbles: true }))
  await ctx.nextTick()
  knopf(ctx.ziel, 'Eintragen').dispatchEvent(new globalThis.MouseEvent('click', { bubbles: true }))
  await warte(150)

  const meldung = ctx.toasts().join(' ')
  assert.ok(meldung, 'die Seite meldet den Fehler (Toast)')
  assert.match(meldung, /nur Personen aus deinem Haushalt/,
    'der Klartext des Servers kommt an (kein „HTTP 403“)')
  await abbauen(ctx)
})

// ═══ 6. Testliste (Build) ══════════════════════════════════════════════════

test('BEZH-UI: der Test laeuft im Image-Build (frontend/tests/testliste.txt)', () => {
  const liste = lies(path.join(FRONTEND, 'tests', 'testliste.txt'))
  const muster = liste.split('\n').map(z => z.trim()).filter(z => z && !z.startsWith('#'))
  assert.ok(muster.some(m => m === 'tests/bezhui-*.test.mjs'),
    'Muster tests/bezhui-*.test.mjs fehlt in frontend/tests/testliste.txt')
})
