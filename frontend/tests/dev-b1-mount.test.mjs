/**
 * DEV-B1 · Mount-Test: Termin anlegen/bearbeiten mit Schreibrecht.
 *
 * Befund DMB-da438eb70703 + DMB-734e07deb09b (Demo, 09.11.): Beide Dialoge
 * meldeten „Du hast auf keinen Kalender Schreibrecht“, obwohl
 * `get_writable_calendars` Kalender lieferte. Ursache: die Kategorie-Abfrage
 * trug Backslashes in der Adresse (417), und weil alle Abrufe in
 * `Promise.all` standen, riss der Fehler die Kalenderliste mit.
 *
 * Dieser Test rendert die ECHTEN Bauteile (`vue/compiler-sfc` übersetzt
 * Vorlage + `<script setup>`; `@vitejs/plugin-vue` ist im Testprozess nicht
 * vollständig auflösbar). Die übersetzten Module entstehen im Temp-Ordner
 * unter demselben Unterpfad wie die Quelle (`src/…`) und importieren `vue`
 * über den ECHTEN `node_modules`-Ordner des Frontends — nicht über eine Kopie
 * und nicht über den Quellbaum (dort würde nichts geschrieben).
 *
 * Geprüft wird am gerenderten DOM (jsdom, `fetch`-Attrappe wie der Server):
 *   1. Mit Schreibrecht: die Kalenderauswahl ist GEFÜLLT, kein Rechte-Hinweis.
 *   2. Die Kategorie-Abfrage geht OHNE Backslash raus (der Server würde sonst
 *      417 antworten — genau der Befund).
 *   3. Fällt ein Nebenabruf aus (Kategorien 500), bleiben die Kalender da.
 *   4. Fällt `get_writable_calendars` aus, steht der LADE-Fehler — NICHT
 *      „kein Schreibrecht“.
 *   5. Ohne Schreibrecht (leere Liste): Recht-Hinweis, keine Kalenderauswahl.
 *
 * Läuft in der Node-Testliste (`tests/dev-b1-mount.test.mjs`), ohne Browser.
 */
import assert from 'node:assert/strict'
import { mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath, pathToFileURL } from 'node:url'

import { compileScript, compileTemplate, parse } from 'vue/compiler-sfc'

const HIER = path.dirname(fileURLToPath(import.meta.url))
const FRONTEND = path.resolve(HIER, '..')
const SRV = path.join(FRONTEND, 'src')
const KRONOS = path.join(SRV, 'diakonos/components/kronos')

// ── jsdom als Dokument ─────────────────────────────────────────────────────

function dokumentBauen() {
  return import('jsdom').then(({ JSDOM }) => {
    const dom = new JSDOM('<!doctype html><html><head></head><body></body></html>', {
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
    globalThis.getComputedStyle = window.getComputedStyle.bind(window)
    globalThis.requestAnimationFrame = (fn) => setTimeout(() => fn(Date.now()), 0)
    globalThis.cancelAnimationFrame = (id) => clearTimeout(id)
    window.__DIakonosBOOT = { basePath: '/diakonos', csrf_token: 'test-token' }
    return window
  })
}

// ── .vue/.js → ES-Module in einem Temp-Baum ────────────────────────────────
//
// `vue` wird relativ vom Temp-Baum aufgelöst: der Baum liegt unter
// `<frontend>/.kanban-<zufall>/src/…` — einen Ordner TIEFER als `frontend/`,
// damit Node `frontend/node_modules` findet, ohne dass dort etwas geschrieben
// wird. Der Ordner wird am Prozessende entfernt.

// Der Grundordner entsteht erst beim ersten Render (sonst bleibt ein leerer
// `.kanban-dev-b1-…`-Ordner stehen, wenn kein Test laeuft).
let AUSGABE = null
const geschrieben = new Set()

function ziel(abs) {
  const rel = path.relative(SRV, abs).replace(/\.(vue|js|mjs)$/, '.mjs')
  const datei = path.join(AUSGABE, 'src', rel)
  mkdirSync(path.dirname(datei), { recursive: true })
  return datei
}

/** Relativer Import → umgeschriebener Pfad im Temp-Baum. */
function pfadUmschreiben(abs, pfad) {
  const zielAbs = path.resolve(path.dirname(abs), pfad)
  if (!/\.(vue|js|mjs)$/.test(pfad)) return null
  if (pfad.endsWith('.vue')) {
    bauteilSchreiben(zielAbs)
    return pfad.replace(/\.vue$/, '.mjs')
  }
  modulSchreiben(zielAbs)
  return pfad.replace(/\.(js|mjs)$/, '.mjs')
}

function bauteilSchreiben(abs) {
  if (geschrieben.has(abs)) return
  geschrieben.add(abs)
  const id = path.basename(abs, '.vue').replace(/\W/g, '_')
  const datei = ziel(abs)
  // Zyklen: Platzhalter VOR dem Abstieg, damit ein Rueckverweis eine Datei findet.
  writeFileSync(datei, 'export default {}\n', 'utf8')

  const { descriptor } = parse(readFileSync(abs, 'utf8'), { filename: abs })
  const skript = compileScript(descriptor, { id, inlineTemplate: true })
  let code = skript.content
  // `inlineTemplate` hängt die Vorlage an; die eingefrorenen Knoten heißen
  // `_hoisted_1` usw. und kollidieren mit denen des Skripts („already been
  // declared“) — je Bauteil eindeutig umbenennen.
  // Auch der `export function render`-Zweig unten steht im selben Modul — die
  // Namen muessen dort ebenfalls eindeutig sein (sonst „already been declared“).
  // Auch der Vorlagen-Renderer nutzt `_hoisted_*` — er steht im ERSTEN Zweig
  // bereits im Skript, im zweiten kommt er aus `compileTemplate`. Nur wenn er
  // im Skript FEHLT, wird er unten angehängt und braucht neue Namen.
  const renderImSkript = /_createCommentVNode|_createElementVNode|_createBlock/.test(code)
  const stamm = id
  const hoistedUmschreiben = (t) => t.replace(/\b_hoisted_(\d+)\b/g, (_, n) => `_h${stamm}_${n}`)
  code = hoistedUmschreiben(code)
  if (!renderImSkript) {
    const tpl = compileTemplate({
      id,
      filename: abs,
      source: descriptor.template.content,
      compilerOptions: { bindingMetadata: skript.bindings, mode: 'module' },
    })
    assert.equal(tpl.errors.length, 0, `${id}: Vorlage nicht kompilierbar: ${tpl.errors.join(', ')}`)
    const ohneExport = hoistedUmschreiben(tpl.code.replace(/export function render/, 'function render'))
    // Der Skriptteil wird NUR als Rumpf übernommen: die `vue`-Importe und die
    // EINGEFRORENEN Konstanten (`_hoisted_*`) stehen schon im Renderer.
    const importe = new Set()
    const rest = []
    for (const zeile of `${ohneExport}\n${skript.content}`.split('\n')) {
      if (/^import\s*\{.*\}\s*from\s*["']vue["']\s*;?$/.test(zeile.trim())) {
        for (const n of zeile.slice(zeile.indexOf('{') + 1, zeile.indexOf('}')).split(',')) {
          if (n.trim()) importe.add(n.trim())
        }
        continue
      }
      if (/^const _hoisted_\d+\b/.test(zeile.trim())) continue
      rest.push(zeile)
    }
    const rumpf = rest.join('\n')
      .replace(/\bexport const /g, 'const ')
      .replace(/export default /g, 'const __bauteil = ')
    code = `import { ${[...importe].join(', ')} } from 'vue'\n${hoistedUmschreiben(rumpf)}`
      + '\n__bauteil.render = render\nexport default __bauteil\n'
  }
  code = code.replace(/from\s+'((?:\.\.?\/)[^']+)'/g, (ganz, pfad) => {
    const neu = pfadUmschreiben(abs, pfad)
    return neu ? ganz.replace(pfad, neu) : ganz
  })
  writeFileSync(datei, code, 'utf8')
}

function modulSchreiben(abs) {
  if (geschrieben.has(abs)) return
  geschrieben.add(abs)
  let code = readFileSync(abs, 'utf8')
  code = code.replace(/from\s+'((?:\.\.?\/)[^']+)'/g, (ganz, pfad) => {
    const neu = pfadUmschreiben(abs, pfad)
    return neu ? ganz.replace(pfad, neu) : ganz
  })
  writeFileSync(ziel(abs), code, 'utf8')
}

// ── fetch-Attrappe, die sich wie der Server verhält ────────────────────────

function antwort(daten, status = 200) {
  const textInhalt = JSON.stringify(daten)
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => textInhalt,
    json: async () => JSON.parse(textInhalt),
    headers: { get: () => 'application/json' },
  }
}

/**
 * Wie der echte Server: ist `fields` kein gültiges JSON-Array aus bekannten
 * Feldnamen (z. B. wegen Backslashes), kommt 417 zurueck.
 */
function fetchAttrappe(aufrufe, { kalender = null, kategorienFehler = false } = {}) {
  return async (url) => {
    const adresse = String(url)
    aufrufe.push(adresse)
    if (adresse.includes('get_writable_calendars')) {
      if (kalender === 'fehler') return antwort({ exc: 'Serverfehler' }, 500)
      return antwort({
        message: kalender ?? [{ name: 'Gottesdienst', calendar_name: 'Gottesdienst', color: '#123456' }],
      })
    }
    if (adresse.includes('get_session_info')) return antwort({ message: { roles: [] } })
    if (adresse.includes('get_ressources')) return antwort({ message: { types: [], resources: [] } })
    if (adresse.includes('get_kronos_settings')) return antwort({ message: {} })
    if (adresse.includes('/api/resource/Eventkategorie')) {
      if (kategorienFehler) return antwort({ exc: 'kaputt' }, 500)
      const feld = new URL('http://x' + adresse).searchParams.get('fields')
      let liste
      try {
        liste = JSON.parse(feld ?? 'null')
      } catch {
        liste = null
      }
      if (!Array.isArray(liste) || liste.some((f) => String(f).includes('\\'))) {
        return antwort({ exception: 'frappe.exceptions.ValidationError: unbekanntes Feld' }, 417)
      }
      return antwort({ data: [{ name: 'EK-1', event_category_name: 'Gottesdienst' }] })
    }
    return antwort({ message: {} })
  }
}

let DOKUMENT = null

/**
 * EIN Dokument für den ganzen Lauf: `Teleport to="body"` löst sein Ziel beim
 * ersten Rendern auf — ein zweites jsdom-Fenster würde den Dialog in ein
 * fremdes, nicht angeschautes Dokument hängen.
 */
async function dokument() {
  if (!DOKUMENT) DOKUMENT = await dokumentBauen()
  DOKUMENT.document.body.innerHTML = ''
  return DOKUMENT
}

async function rendern(bauteil, props, optionen = {}) {
  const window = await dokument()
  const aufrufe = []
  window.fetch = globalThis.fetch = fetchAttrappe(aufrufe, optionen)
  // Jeder Aufruf bekommt einen FRISCHEN Temp-Baum: Module werden je Pfad nur
  // EINMAL geladen — sonst sähe der zweite Test den Vue-Zustand des ersten.
  const lauf = mkdtempSync(path.join(FRONTEND, '.kanban-dev-b1-'))
  if (!AUSGABE) AUSGABE = lauf
  geschrieben.clear()
  bauteilSchreiben(path.join(KRONOS, bauteil))
  const datei = ziel(path.join(KRONOS, bauteil))
  if (process.env.DEVB1_DEBUG) {
    // Diagnose: bleibt ein `_hoisted_` stehen, zeigen wir die Datei.
    for (const pfad of walk(AUSGABE)) {
      const inhalt = readFileSync(pfad, 'utf8')
      if (/_hoisted_/.test(inhalt)) console.log('HOISTED in', path.relative(AUSGABE, pfad))
    }
  }
  const modul = await import(pathToFileURL(datei).href + `?v=${Date.now()}${Math.random()}`)
  const bauteilKlasse = modul.default
  assert.ok(bauteilKlasse && typeof bauteilKlasse === 'object', 'Bauteil nicht geladen')

  const { createApp, h, nextTick } = await import('vue')
  const knoten = window.document.createElement('div')
  window.document.body.appendChild(knoten)
  const app = createApp({ render: () => h(bauteilKlasse, props ?? {}) })
  app.config.warnHandler = () => {}
  app.mount(knoten)
  for (let i = 0; i < 8; i += 1) {
    await new Promise((r) => setTimeout(r, 0))
    await nextTick()
  }
  return { window, aufrufe, app, body: window.document.body, baum: lauf }
}

function walk(ordner) {
  const out = []
  for (const name of readdirSync(ordner, { withFileTypes: true })) {
    const abs = path.join(ordner, name.name)
    if (name.isDirectory()) out.push(...walk(abs))
    else out.push(abs)
  }
  return out
}

function kalenderOptionen(body) {
  const select = [...body.querySelectorAll('select.dk-ui-select')]
    .find((s) => [...s.options].some((o) => o.value === 'Gottesdienst'))
  if (!select) return null
  return [...select.options].map((o) => o.value).filter((v) => v !== '')
}

function text(body) {
  return (body.textContent || '').replace(/\s+/g, ' ').trim()
}

// ── Anlegen-Dialog ─────────────────────────────────────────────────────────

test('DEV-B1: „Termin anlegen“ zeigt mit Schreibrecht eine GEFÜLLTE Kalenderauswahl', async () => {
  const { body, aufrufe, app, baum } = await rendern('KronosEventCreate.vue', { show: true })
  try {
    const optionen = kalenderOptionen(body)
    assert.ok(optionen, 'Kalender-Auswahlfeld nicht gefunden')
    assert.deepEqual(optionen, ['Gottesdienst'], 'Kalenderauswahl ist leer — der Befund ist zurück')
    assert.ok(!/kein Kalender mit Schreibrecht freigegeben/.test(text(body)),
      'falscher Rechte-Hinweis trotz Schreibrecht')
    assert.ok(!/konnte nicht geladen werden/.test(text(body)), 'Lade-Fehler trotz Erfolg gemeldet')

    const kategorien = aufrufe.filter((u) => u.includes('/api/resource/Eventkategorie'))
    assert.equal(kategorien.length, 1, `Kategorie-Abfrage ${kategorien.length}x`)
    assert.ok(!kategorien[0].includes('\\'), `Backslash in der Adresse: ${kategorien[0]}`)
    const felder = JSON.parse(new URL('http://x' + kategorien[0]).searchParams.get('fields'))
    assert.deepEqual(felder, ['name', 'event_category_name'])
  } finally { app.unmount(); rmSync(baum, { recursive: true, force: true }) }
})

test('DEV-B1: ein ausgefallener Nebenabruf (Kategorien 500) nimmt die Kalender NICHT mit', async () => {
  const { body, app, baum } = await rendern('KronosEventCreate.vue', { show: true }, { kategorienFehler: true })
  try {
    assert.deepEqual(kalenderOptionen(body), ['Gottesdienst'],
      'Kalenderliste fiel mit einem fremden Abruf aus (Promise.all statt allSettled)')
    assert.ok(!/kein Kalender mit Schreibrecht freigegeben/.test(text(body)))
  } finally { app.unmount(); rmSync(baum, { recursive: true, force: true }) }
})

test('DEV-B1: scheitert get_writable_calendars, steht der LADE-Fehler — nicht „kein Schreibrecht“', async () => {
  const { body, app, baum } = await rendern('KronosEventCreate.vue', { show: true }, { kalender: 'fehler' })
  try {
    const inhalt = text(body)
    assert.match(inhalt, /Kalenderliste konnte nicht geladen werden/, 'Lade-Fehler wird nicht benannt')
    assert.ok(!/Du kannst derzeit keine Termine anlegen/.test(inhalt),
      'der Lade-Fehler behauptet weiterhin „kein Schreibrecht“')
  } finally { app.unmount(); rmSync(baum, { recursive: true, force: true }) }
})

test('DEV-B1: ohne Schreibrecht (leere Liste) bleibt der Rechte-Hinweis', async () => {
  const { body, app, baum } = await rendern('KronosEventCreate.vue', { show: true }, { kalender: [] })
  try {
    assert.match(text(body), /Du kannst derzeit keine Termine anlegen/)
    // Mit leerer Liste gibt es keine Kalender-Optionen — das Feld zeigt nur den
    // Platzhalter „Bitte wählen“ (der Helfer findet dann kein passendes Feld).
    const optionen = kalenderOptionen(body)
    assert.ok(optionen === null || optionen.length === 0,
      `Kalenderauswahl zeigt trotz fehlendem Recht Einträge: ${JSON.stringify(optionen)}`)
  } finally { app.unmount(); rmSync(baum, { recursive: true, force: true }) }
})

// ── Bearbeiten-Dialog ──────────────────────────────────────────────────────

const TERMIN = {
  id: 'EV-1',
  name: 'EV-1',
  title: 'Gottesdienst',
  start: '2026-11-15T10:00:00',
  end: '2026-11-15T11:00:00',
  calendar: 'Gottesdienst',
  allDay: false,
}

test('DEV-B1: „Termin bearbeiten“ zeigt mit Schreibrecht die Kalenderauswahl', async () => {
  const { body, aufrufe, app, baum } = await rendern('KronosEventEdit.vue', { show: true, event: TERMIN })
  try {
    assert.deepEqual(kalenderOptionen(body), ['Gottesdienst'], 'Kalenderauswahl leer — Befund zurück')
    assert.ok(!/konnte nicht geladen werden/.test(text(body)))
    assert.ok(aufrufe.some((u) => u.includes('get_writable_calendars')))
    const kategorien = aufrufe.filter((u) => u.includes('/api/resource/Eventkategorie'))
    assert.equal(kategorien.length, 1)
    assert.ok(!kategorien[0].includes('\\'), `Backslash in der Adresse: ${kategorien[0]}`)
  } finally { app.unmount(); rmSync(baum, { recursive: true, force: true }) }
})

test('DEV-B1: Bearbeiten-Dialog nennt einen Kalender-Ladefehler als solchen', async () => {
  const { body, app, baum } = await rendern('KronosEventEdit.vue', { show: true, event: TERMIN }, { kalender: 'fehler' })
  try {
    assert.match(text(body), /Kalenderliste konnte nicht geladen werden/)
  } finally { app.unmount(); rmSync(baum, { recursive: true, force: true }) }
})

// Nach JEDEM Render wird der Temp-Baum abgeräumt (Modul-Cache bleibt beim
// Pfad — der nächste Test bekommt ohnehin einen neuen).
process.on('exit', () => { if (AUSGABE) rmSync(AUSGABE, { recursive: true, force: true }) })
