/**
 * UI-R5b · „+ Termin“: Direktschreiber legen direkt an (Punkt 1).
 *
 * Die Regel selbst steht in `ui-r5-gruppen-termin.test.mjs` (reine Funktion
 * `statusFuerKalender`). HIER wird der ECHTE Dialog gerendert (wie
 * `dev-b1-mount.test.mjs`) und der Rumpf der Speicher-Anfrage angeschaut:
 *
 *   * Kalender mit `direkt === true`  → `status: 'Festgelegt'` im Payload —
 *     für `create_event` UND `create_series`.
 *   * `direkt === false` / Feld fehlt → KEIN `status` (der Server legt dann
 *     „Vorschlag“ an; die Oberfläche behauptet nichts anderes).
 *   * Auf einer Gruppenseite (Vorgabe aus `get_accessible_calendars`) gilt
 *     dasselbe — die Seite und der Kalender teilen EIN Formular.
 *   * Der Kalenderhinweis „N Kalender stehen zur Auswahl …“ steht IM Dialog
 *     über der Kalenderwahl (Teleport!) und verschwindet mit der Auswahl.
 *
 * Ohne Browser, ohne Server: `fetch` ist eine Attrappe wie im Betrieb.
 */
import assert from 'node:assert/strict'
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath, pathToFileURL } from 'node:url'

import { compileScript, compileTemplate, parse } from 'vue/compiler-sfc'

const HIER = path.dirname(fileURLToPath(import.meta.url))
const FRONTEND = path.resolve(HIER, '..')
const SRV = path.join(FRONTEND, 'src')
const KRONOS = path.join(SRV, 'diakonos/components/kronos')

// ── jsdom als Dokument (ein Dokument je Lauf, Teleport-Ziel bleibt stabil) ──

let DOKUMENT = null

async function dokument() {
  if (!DOKUMENT) {
    const { JSDOM } = await import('jsdom')
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
    DOKUMENT = window
  }
  DOKUMENT.document.body.innerHTML = ''
  return DOKUMENT
}

// ── .vue/.js → ES-Module in einem Temp-Baum (wie `dev-b1-mount.test.mjs`) ──

let AUSGABE = null
const geschrieben = new Set()
// Der Temp-Baum lebt im `frontend/`-Ordner (damit `node_modules` gefunden
// wird) und wird am Prozessende entfernt — auch wenn ein Test rot endet.
const BAUM = mkdtempSync(path.join(FRONTEND, '.kanban-uir5b-'))
process.on('exit', () => { try { rmSync(BAUM, { recursive: true, force: true }) } catch { /* egal */ } })

function ziel(abs) {
  const rel = path.relative(SRV, abs).replace(/\.(vue|js|mjs)$/, '.mjs')
  const datei = path.join(AUSGABE, 'src', rel)
  mkdirSync(path.dirname(datei), { recursive: true })
  return datei
}

function pfadUmschreiben(abs, pfad) {
  if (!/\.(vue|js|mjs)$/.test(pfad)) return null
  const zielAbs = path.resolve(path.dirname(abs), pfad)
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
  writeFileSync(datei, 'export default {}\n', 'utf8')

  const { descriptor } = parse(readFileSync(abs, 'utf8'), { filename: abs })
  const skript = compileScript(descriptor, { id, inlineTemplate: true })
  let code = skript.content
  const renderImSkript = /_createCommentVNode|_createElementVNode|_createBlock/.test(code)
  const hoistedUmschreiben = (t) => t.replace(/\b_hoisted_(\d+)\b/g, (_, n) => `_h${id}_${n}`)
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

// ── fetch-Attrappe: Serverliste + Speichern wie im Betrieb ─────────────────

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
 * `vorgabe` = Kalender der Gruppenseite (`get_accessible_calendars`), sonst
 * liefert `get_writable_calendars` die Liste (Kalenderseite).
 * `gespeichert` sammelt den Rumpf jeder Speicher-Anfrage.
 */
function fetchAttrappe({ vorgabe = null, schreibbar = [] }, gespeichert) {
  return async (url, optionen = {}) => {
    const adresse = String(url)
    if (adresse.includes('create_event') || adresse.includes('create_series')) {
      gespeichert.push({ methode: adresse.split('.').pop(), rumpf: JSON.parse(optionen.body || '{}') })
      return antwort({
        message: { success: true, status: 'Festgelegt', name: 'EV-1' },
      })
    }
    if (adresse.includes('check_resource_conflict')) return antwort({ message: { has_conflict: false } })
    if (adresse.includes('get_accessible_calendars')) return antwort({ message: vorgabe ?? schreibbar })
    if (adresse.includes('get_writable_calendars')) return antwort({ message: schreibbar })
    if (adresse.includes('get_session_info')) return antwort({ message: { roles: [] } })
    if (adresse.includes('get_ressources')) return antwort({ message: { types: [], resources: [] } })
    if (adresse.includes('get_kronos_settings')) return antwort({ message: {} })
    if (adresse.includes('get_rollen_erklaerung')) return antwort({ message: { stufen_titel: {} } })
    if (adresse.includes('/api/resource/Eventkategorie')) return antwort({ data: [] })
    return antwort({ message: {} })
  }
}

async function rendern(optionen = {}) {
  const window = await dokument()
  const gespeichert = []
  window.fetch = globalThis.fetch = fetchAttrappe(optionen, gespeichert)
  if (!AUSGABE) AUSGABE = BAUM
  geschrieben.clear()
  bauteilSchreiben(path.join(KRONOS, 'KronosEventCreate.vue'))
  const datei = ziel(path.join(KRONOS, 'KronosEventCreate.vue'))
  const modul = await import(pathToFileURL(datei).href + `?v=${Date.now()}${Math.random()}`)
  const klasse = modul.default
  assert.ok(klasse && typeof klasse === 'object', 'Formular nicht geladen')

  const { createApp, h, nextTick } = await import('vue')
  const knoten = window.document.createElement('div')
  window.document.body.appendChild(knoten)
  const app = createApp({ render: () => h(klasse, optionen.props ?? { show: true }) })
  app.config.warnHandler = () => {}
  app.mount(knoten)
  const tick = async (n = 10) => {
    for (let i = 0; i < n; i += 1) {
      await new Promise((r) => setTimeout(r, 0))
      await nextTick()
    }
  }
  await tick()
  return { window, app, gespeichert, body: window.document.body, baum: BAUM, tick }
}

// ── Bedienung des echten Dialogs ──────────────────────────────────────────

function kalenderWaehlen(body, name) {
  const select = [...body.querySelectorAll('select.dk-ui-select')]
    .find((s) => [...s.options].some((o) => o.value === name))
  assert.ok(select, `Kalenderauswahl ohne Option ${name}`)
  select.value = name
  select.dispatchEvent(new (globalThis.window.Event)('change', { bubbles: true }))
  return select
}

function titelSetzen(body, text) {
  const feld = body.querySelector('input[placeholder="Termintitel"]')
  assert.ok(feld, 'Titelfeld nicht gefunden')
  feld.value = text
  feld.dispatchEvent(new (globalThis.window.Event)('input', { bubbles: true }))
}

function serienHaekchen(body) {
  // Zwei Kästchen im Dialog: „Ganztägig“ (Tab 1) und „Serientermin“ (Tab 2).
  // Beide Tabs stehen im DOM (`v-show`), das Serien-Kästchen hat die Beschriftung.
  const label = [...body.querySelectorAll('label.dk-ui-checkbox')]
    .find((l) => /Serientermin/.test(l.textContent || ''))
  assert.ok(label, 'Serien-Kästchen nicht gefunden')
  const input = label.querySelector('input[type="checkbox"]')
  assert.ok(input, 'Serien-Kästchen ohne Eingabe')
  input.click()
  return input
}

async function speichern(body, tick) {
  const knopf = [...body.querySelectorAll('button')].find((b) => /^Speichern$/.test((b.textContent || '').trim()))
  assert.ok(knopf, 'Speichern-Knopf nicht gefunden')
  knopf.click()
  await tick(16)
}

const CHOR = {
  name: 'chorkal', title: 'Chor', write: true, direkt: true, stufen: ['gruppe'],
  pruefstufen: ['gruppe'], gruppe: 'chor', untergruppe: null,
}
const SOPRAN = {
  name: 'sopran-kal', title: 'Sopran', write: true, direkt: true, stufen: [],
  pruefstufen: [], gruppe: 'chor', untergruppe: 'sopran',
}
const SOPRAN_OFFEN = {
  name: 'sopran-offen', title: 'Sopran öffentlich', write: true, direkt: false,
  stufen: ['gruppe'], pruefstufen: ['gruppe'], gruppe: 'chor', untergruppe: 'sopran',
}

// ── Punkt 1: status im Payload ────────────────────────────────────────────

test('UI-R5b: direkt === true → create_event schickt status „Festgelegt“', async () => {
  const { body, app, gespeichert, baum, tick } = await rendern({ schreibbar: [CHOR] })
  try {
    kalenderWaehlen(body, 'chorkal')
    titelSetzen(body, 'Chorprobe')
    await tick(2)
    await speichern(body, tick)
    assert.equal(gespeichert.length, 1, 'keine Speicher-Anfrage abgesetzt')
    assert.equal(gespeichert[0].methode, 'create_event')
    assert.equal(gespeichert[0].rumpf.status, 'Festgelegt',
      'Direktschreiber-Kalender schickt keinen status — der Server legt nur einen Vorschlag an')
  } finally { app.unmount(); rmSync(baum, { recursive: true, force: true }) }
})

test('UI-R5b: direkt === true → create_series schickt status „Festgelegt“', async () => {
  const { body, app, gespeichert, baum, tick } = await rendern({ schreibbar: [CHOR] })
  try {
    kalenderWaehlen(body, 'chorkal')
    titelSetzen(body, 'Chorprobe wöchentlich')
    serienHaekchen(body)
    await tick(3)
    // Wiederholung + Serienende wie im Betrieb wählen. Die Wiederholung steht
    // im DOM (`v-show`), das Serienende füllt das Formular aus dem Vorschlag.
    const wiederholung = [...body.querySelectorAll('.diakronos-modal select.dk-ui-select')]
      .find((s) => [...s.options].some((o) => o.value === 'weekly'))
    assert.ok(wiederholung, 'Wiederholungsfeld nicht gefunden')
    wiederholung.value = 'weekly'
    wiederholung.dispatchEvent(new (globalThis.window.Event)('change', { bubbles: true }))
    await tick(3)
    // Das Serienende ist ein Datumsfeld (`type="date"`) ohne Vorschlag.
    const serie = [...body.querySelectorAll('.diakronos-modal input[type="date"]')].pop()
    assert.ok(serie, 'Serienende nicht gefunden')
    serie.value = '2027-12-31'
    serie.dispatchEvent(new (globalThis.window.Event)('input', { bubbles: true }))
    serie.dispatchEvent(new (globalThis.window.Event)('change', { bubbles: true }))
    await tick(3)
    await speichern(body, tick)
    assert.equal(gespeichert.length, 1, `keine Speicher-Anfrage abgesetzt (${body.textContent.slice(-300)})`)
    assert.equal(gespeichert[0].methode, 'create_series', 'Serie ging als Einzeltermin raus')
    assert.equal(gespeichert[0].rumpf.status, 'Festgelegt',
      'Serie eines Direktschreiber-Kalenders schickt keinen status')
  } finally { app.unmount(); rmSync(baum, { recursive: true, force: true }) }
})

test('UI-R5b: direkt === false → KEIN status im Payload (Server entscheidet)', async () => {
  const { body, app, gespeichert, baum, tick } = await rendern({ vorgabe: [SOPRAN_OFFEN], props: { show: true, kalenderVorgabe: [SOPRAN_OFFEN] } })
  try {
    kalenderWaehlen(body, 'sopran-offen')
    titelSetzen(body, 'Sopranprobe')
    await tick(2)
    await speichern(body, tick)
    assert.equal(gespeichert.length, 1, 'keine Speicher-Anfrage abgesetzt')
    assert.ok(!('status' in gespeichert[0].rumpf),
      `status wurde geschickt, obwohl der Kalender prüft: ${JSON.stringify(gespeichert[0].rumpf.status)}`)
  } finally { app.unmount(); rmSync(baum, { recursive: true, force: true }) }
})

test('UI-R5b: fehlendes `direkt` (alter Server) → KEIN status', async () => {
  const ALT = { name: 'altkal', calendar_name: 'Alt', write: true }
  const { body, app, gespeichert, baum, tick } = await rendern({ schreibbar: [ALT] })
  try {
    kalenderWaehlen(body, 'altkal')
    titelSetzen(body, 'Alter Kalender')
    await tick(2)
    await speichern(body, tick)
    assert.equal(gespeichert.length, 1, 'keine Speicher-Anfrage abgesetzt')
    assert.ok(!('status' in gespeichert[0].rumpf), 'status ohne Auskunft des Servers erfunden')
  } finally { app.unmount(); rmSync(baum, { recursive: true, force: true }) }
})

test('UI-R5b: Gruppenseite — der gewählte Kalender entscheidet, nicht die Seite', async () => {
  // Dieselbe Vorgabe wie auf der Untergruppenseite: ein Direktschreiber-Kalender
  // und ein geprüfter. Beide Wege müssen aus EINEM Formular richtig sein.
  const vorgabe = [SOPRAN, SOPRAN_OFFEN]
  const props = { show: true, kalenderVorgabe: vorgabe }

  const direkt = await rendern({ vorgabe, props })
  try {
    kalenderWaehlen(direkt.body, 'sopran-kal')
    titelSetzen(direkt.body, 'Sopran direkt')
    await direkt.tick(2)
    await speichern(direkt.body, direkt.tick)
    assert.equal(direkt.gespeichert[0]?.rumpf.status, 'Festgelegt',
      'Direktschreiber-Kalender der Gruppenseite legt nicht direkt an')
  } finally { direkt.app.unmount(); rmSync(direkt.baum, { recursive: true, force: true }) }

  const geprueft = await rendern({ vorgabe, props })
  try {
    kalenderWaehlen(geprueft.body, 'sopran-offen')
    titelSetzen(geprueft.body, 'Sopran geprüft')
    await geprueft.tick(2)
    await speichern(geprueft.body, geprueft.tick)
    assert.ok(!('status' in (geprueft.gespeichert[0]?.rumpf || {})),
      'geprüfter Kalender der Gruppenseite schickt „Festgelegt“')
  } finally { geprueft.app.unmount(); rmSync(geprueft.baum, { recursive: true, force: true }) }
})

// ── Punkt 2: Kalenderhinweis im Dialog ────────────────────────────────────

test('UI-R5b: „N Kalender stehen zur Auswahl“ steht im Dialog und verschwindet mit der Wahl', async () => {
  const vorgabe = [SOPRAN, SOPRAN_OFFEN]
  const { body, app, baum, tick } = await rendern({ vorgabe, props: { show: true, kalenderVorgabe: vorgabe } })
  try {
    const hinweis = body.querySelector('[data-ui-r5b="kalender-wahl"]')
    assert.ok(hinweis, 'Kalenderhinweis fehlt im Dialog')
    // Der Dialog wird per Teleport ans <body>-Ende gehängt — genau deshalb war
    // der Satz auf der Seite dahinter unsichtbar. Hier steht er IM Dialog.
    assert.ok(body.querySelector('.diakronos-modal')?.contains(hinweis),
      'Hinweis steht außerhalb des Dialogs')
    assert.match((hinweis.textContent || '').replace(/\s+/g, ' '), /2 Kalender stehen zur Auswahl/)
    // Über der Kalenderwahl: der Hinweis kommt im Dokument VOR dem Feld.
    const wahl = [...body.querySelectorAll('.diakronos-modal select.dk-ui-select')]
      .find((s) => [...s.options].some((o) => o.value === 'sopran-kal'))
    assert.ok(wahl, 'Kalenderfeld fehlt')
    assert.ok(hinweis.compareDocumentPosition(wahl) & 4, 'Hinweis steht NACH der Kalenderwahl')

    kalenderWaehlen(body, 'sopran-kal')
    await tick(3)
    assert.equal(body.querySelector('[data-ui-r5b="kalender-wahl"]'), null,
      'Hinweis bleibt trotz getroffener Wahl stehen')
  } finally { app.unmount(); rmSync(baum, { recursive: true, force: true }) }
})

test('UI-R5b: ein EINZELNER Kalender → kein Auswahl-Hinweis (nichts zu wählen)', async () => {
  const { body, app, baum } = await rendern({ schreibbar: [CHOR] })
  try {
    assert.equal(body.querySelector('[data-ui-r5b="kalender-wahl"]'), null,
      'Hinweis trotz nur einem Kalender')
  } finally { app.unmount(); rmSync(baum, { recursive: true, force: true }) }
})
