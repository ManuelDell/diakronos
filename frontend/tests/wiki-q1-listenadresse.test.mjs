/**
 * WIKI-Q-1 — Wiki-Liste: Suche und Kategorie aus der Adresse halten beim
 * Aufbau.
 *
 * BEFUND (Nebenbefund MT-7c): `listenZustandUebernehmen()` setzt zuerst
 * `activeCategory='all'` und `searchQuery=''` und übernimmt DANN `kategorie`
 * und `q` aus dem Hash; der Watch auf `[activeCategory, searchQuery]` schreibt
 * jede Änderung sofort per `adresseImVerlaufSetzen(listenAdresse())` zurück in
 * die Adresse. Verdacht: `?q=`/`?kategorie=` geht beim Aufbau verloren.
 *
 * Geprüft wird das VERHALTEN der ECHTEN Seite: `pages/Wiki.vue` wird in jsdom
 * gemountet (SFC über `vue/compiler-sfc`), die API ist gestubbt, die Adresse
 * ist der echte jsdom-Verlauf. Ersetzt sind NUR die Darstellungs-Bausteine
 * aus `components/ui/*` durch schlichte Attrappen (Knopf mit Klasse + Text,
 * Eingabefeld, Gerüst) — ihr echtes Styling/Verhalten ist hier nicht
 * Gegenstand; die Logik der Seite (Zustand, Watch, API-Aufruf, Adresse)
 * läuft unverändert.
 *
 *   1  `#/wiki?kategorie=technik&q=Beamer` beim Aufbau → Suchfeld „Beamer“,
 *      Chip „Technik“ aktiv (aria-pressed), Adresse unverändert, Listen-API
 *      MIT `search=Beamer` und `kategorie=technik` aufgerufen. Der Stub
 *      antwortet ASYNCHRON (wie der Server); danach gilt dasselbe noch.
 *   2  „‹ zurück“ (Merker, MT-7b) → die Liste startet mit Suche und Kategorie.
 *   3  Kategorie, die es nicht (mehr) gibt: nicht aktiv gesetzt, `q=` bleibt,
 *      und die Adresse nennt danach den wirklichen Filter (`kategorie=all`) —
 *      nie einen Filter, der gar nicht greift.
 *   4  Gegenprobe: ein absichtlich kaputter Watch (setzt zurück, schreibt
 *      asynchron den Ruhezustand in die Adresse) wird ROT — die Prüfung ist
 *      also nicht blind.
 *
 * Läuft ohne Browser (`node --test`), braucht `node_modules` (vue, jsdom).
 */
import assert from 'node:assert/strict'
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath, pathToFileURL } from 'node:url'

import { compileScript, compileTemplate, parse } from 'vue/compiler-sfc'

const HIER = path.dirname(fileURLToPath(import.meta.url))
const FRONTEND = path.resolve(HIER, '..')
const SRC = path.join(FRONTEND, 'src')

// ── Ersatz für die Darstellungs-Bausteine (components/ui/*.vue) ────────────
// Nur Anzeige: Knopf mit Klassen und Text, Eingabefeld, leerer Rahmen.
const ATTRAPPEN = {
  DkPageHeader: `<div class="attrappe-pageheader"><span>{{ title }}</span><slot name="actions" /></div>`,
  DkButton: `<button type="button" :class="$attrs.class"><slot /></button>`,
  DkBadge: `<span class="attrappe-badge"><slot /></span>`,
  DkCard: `<div class="attrappe-card"><slot /></div>`,
  DkDialog: `<div class="attrappe-dialog"><slot /><slot name="footer" /></div>`,
  DkField: `<div class="attrappe-field"><slot /></div>`,
  DkSelect: `<select class="attrappe-select"></select>`,
  DkEmpty: `<div class="attrappe-empty">{{ title }}</div>`,
  DkAktionen: `<span class="attrappe-aktionen"></span>`,
}

// ── SFC übersetzen (Muster: mt7b-lese-unterseiten.test.mjs) ────────────────
let AUSGABE = null
const geschrieben = new Set()

function ziel(abs) {
  const rel = path.relative(SRC, abs).replace(/\.(vue|js|mjs)$/, '.mjs')
  const datei = path.join(AUSGABE, 'src', rel)
  mkdirSync(path.dirname(datei), { recursive: true })
  return datei
}

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

/** Ist das ein Bauteil aus `components/ui/`, das die Attrappe ersetzt? */
function attrappeFuer(abs) {
  const rel = path.relative(SRC, abs).split(path.sep).join('/')
  if (!rel.startsWith('diakonos/components/ui/')) return null
  return ATTRAPPEN[path.basename(abs, '.vue')] || null
}

function bauteilSchreiben(abs) {
  if (geschrieben.has(abs)) return
  geschrieben.add(abs)
  const id = path.basename(abs, '.vue').replace(/\W/g, '_')
  const datei = ziel(abs)
  writeFileSync(datei, 'export default {}\n', 'utf8')

  const quelle = attrappeFuer(abs)
  if (quelle) {
    // Vorlage ohne Skript: die Attrappe nimmt keine Eigenschaften an, was sie
    // braucht (`title`, `class`) liest Vue aus den durchgereichten Attributen.
    const tpl = compileTemplate({
      id, filename: abs, source: quelle, compilerOptions: { mode: 'module' },
    })
    assert.equal(tpl.errors.length, 0, `${id}: Attrappe nicht kompilierbar: ${tpl.errors.join(', ')}`)
    const ohneExport = tpl.code.replace(/export function render/, 'function render')
    writeFileSync(datei, `import { ${attrappeImporte(ohneExport)} } from 'vue'\n${ohneExport}\n`
      + 'export default { name: "Attrappe", inheritAttrs: true, render }\n', 'utf8')
    return
  }

  const { descriptor } = parse(readFileSync(abs, 'utf8'), { filename: abs })
  const skript = compileScript(descriptor, { id, inlineTemplate: true })
  let code = skript.content
  const hoisted = (t) => t.replace(/\b_hoisted_(\d+)\b/g, (_, n) => `_h${id}_${n}`)
  code = hoisted(code)
  const renderImSkript = /_createCommentVNode|_createElementVNode|_createBlock/.test(code)
  if (!renderImSkript) {
    const tpl = compileTemplate({
      id,
      filename: abs,
      source: descriptor.template.content,
      compilerOptions: { bindingMetadata: skript.bindings, mode: 'module' },
    })
    assert.equal(tpl.errors.length, 0, `${id}: Vorlage nicht kompilierbar: ${tpl.errors.join(', ')}`)
    const ohneExport = hoisted(tpl.code.replace(/export function render/, 'function render'))
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
    code = `import { ${[...importe].join(', ')} } from 'vue'\n${hoisted(rumpf)}`
      + '\n__bauteil.render = render\nexport default __bauteil\n'
  }
  code = code.split('\n').map((zeile) => {
    const m = /^(\s*(?:(?:import|export)\b[^'"]*?from\s+|\}?\s*from\s+))(['"])(\.\.?\/[^'"]+)\2/.exec(zeile)
    if (!m) return zeile
    const neu = pfadUmschreiben(abs, m[3])
    return neu ? `${m[1]}${m[2]}${neu}${m[2]}${zeile.slice(m[0].length)}` : zeile
  }).join('\n')
  writeFileSync(datei, code, 'utf8')
}

/** Die von Vue gebrauchten Helfer einer übersetzten Vorlage einsammeln. */
function attrappeImporte(code) {
  const namen = new Set()
  const bekannte = ['createElementBlock', 'createElementVNode', 'createTextVNode', 'createCommentVNode',
    'toDisplayString', 'openBlock', 'renderSlot', 'createBlock', 'Fragment', 'createVNode', 'resolveComponent']
  for (const name of bekannte) {
    if (new RegExp(`\\b${name}\\b`).test(code)) namen.add(name)
  }
  return [...namen].join(', ')
}

function modulSchreiben(abs) {
  if (geschrieben.has(abs)) return
  geschrieben.add(abs)
  const zeilen = readFileSync(abs, 'utf8').split('\n')
  const code = zeilen.map((zeile) => {
    const m = /^(\s*(?:(?:import|export)\b[^'"]*?from\s+|\}?\s*from\s+))(['"])(\.\.?\/[^'"]+)\2/.exec(zeile)
    if (!m) return zeile
    const zielPfad = pfadUmschreiben(abs, m[3])
    if (!zielPfad) return zeile
    return `${m[1]}${m[2]}${zielPfad}${m[2]}${zeile.slice(m[0].length)}`
  }).join('\n')
  writeFileSync(ziel(abs), code, 'utf8')
}

// ── fetch wie der Server ───────────────────────────────────────────────────
function antwort(daten, status = 200) {
  const text = JSON.stringify(daten)
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => text,
    json: async () => JSON.parse(text),
    headers: { get: () => 'application/json' },
  }
}

const WIKI_ARTIKEL = [
  { id: 'A-1', title: 'Beamer', category: 'technik', tags: ['beamer'], author: 'Cara', updatedAt: '2026-11-10', excerpt: 'Anleitung' },
  { id: 'A-2', title: 'Beamer-Kabel', category: 'technik', tags: ['beamer'], author: 'Cara', updatedAt: '2026-11-09', excerpt: 'HDMI' },
]

/**
 * Die Abfrageparameter eines API-Aufrufs — `useApi.js` schickt sie je nach
 * Form als Abfrageteil der Adresse ODER als JSON im Body.
 */
function parameter(url, optionen) {
  const teile = new URLSearchParams(String(url).split('?')[1] || '')
  let koerper = {}
  try { koerper = optionen?.body ? JSON.parse(optionen.body) : {} } catch { koerper = {} }
  const lies = (name) => teile.get(name) ?? (koerper?.[name] !== undefined ? String(koerper[name]) : null)
  return { search: lies('search'), kategorie: lies('kategorie') }
}

function fetchAttrappe(aufrufe, lage = {}) {
  return async (url, optionen = {}) => {
    const adresse = String(url)
    aufrufe.push(adresse)
    if (adresse.includes('get_wiki_artikel_liste')) {
      const p = parameter(adresse, optionen)
      aufrufe.push(`wiki-liste:search=${p.search ?? ''}|kategorie=${p.kategorie ?? ''}`)
      if (lage.verzoegerungMs) await new Promise((r) => setTimeout(r, lage.verzoegerungMs))
      return antwort({ message: WIKI_ARTIKEL })
    }
    if (adresse.includes('get_wiki_artikel_detail')) {
      return antwort({ message: { ...WIKI_ARTIKEL[0], content: '<p>Anleitung</p>' } })
    }
    if (adresse.includes('get_session_info')) return antwort({ message: { roles: [] } })
    return antwort({ message: {} })
  }
}

let DOKUMENT = null
async function dokument(hash) {
  if (!DOKUMENT) {
    const { JSDOM } = await import('jsdom')
    const dom = new JSDOM('<!doctype html><html><head></head><body></body></html>', {
      url: `http://localhost/diakronos/${hash}`,
      pretendToBeVisual: true,
    })
    const { window } = dom
    globalThis.window = window
    globalThis.document = window.document
    globalThis.localStorage = window.localStorage
    globalThis.sessionStorage = window.sessionStorage
    globalThis.HTMLElement = window.HTMLElement
    globalThis.SVGElement = window.SVGElement
    globalThis.Element = window.Element
    globalThis.Node = window.Node
    globalThis.Document = window.Document
    globalThis.getComputedStyle = window.getComputedStyle.bind(window)
    globalThis.requestAnimationFrame = (fn) => setTimeout(() => fn(Date.now()), 0)
    globalThis.cancelAnimationFrame = (id) => clearTimeout(id)
    window.__DIakonosBOOT = { basePath: '/diakronos', csrf_token: 'test-token', roles: [], modules: [] }
    DOKUMENT = window
  }
  DOKUMENT.document.body.innerHTML = ''
  DOKUMENT.history.replaceState(null, '', `/diakronos/${hash}`)
  return DOKUMENT
}

/** Die Wiki-Liste mounten; `fetch` zählt alle Aufrufe in `aufrufe`. */
async function mounten(window, lage = {}) {
  const aufrufe = []
  window.fetch = globalThis.fetch = fetchAttrappe(aufrufe, lage)
  const baum = mkdtempSync(path.join(FRONTEND, '.kanban-wikiq1-'))
  AUSGABE = baum
  geschrieben.clear()
  bauteilSchreiben(path.join(SRC, 'diakonos/pages/Wiki.vue'))
  const modul = await import(pathToFileURL(ziel(path.join(SRC, 'diakonos/pages/Wiki.vue'))).href
    + `?v=${Date.now()}${Math.random()}`)
  const { createApp, h, nextTick } = await import('vue')
  const knoten = window.document.createElement('div')
  window.document.body.appendChild(knoten)
  // Renderfehler dürfen NICHT verschluckt werden: sie werden gesammelt und
  // lassen den Test scheitern (sonst prüfte er einen leeren Baum).
  const fehler = []
  const app = createApp({ render: () => h(modul.default) })
  app.config.warnHandler = () => {}
  app.config.errorHandler = (err) => { fehler.push(err) }
  app.mount(knoten)
  const warten = async (runden = 14, ms = 40) => {
    for (let i = 0; i < runden; i += 1) {
      await new Promise((r) => setTimeout(r, ms))
      await nextTick()
    }
  }
  await warten()
  assert.deepEqual(fehler.map((e) => e?.message), [], 'beim Rendern der Wiki-Liste trat ein Fehler auf')
  return {
    app, aufrufe, window, baum,
    body: window.document.body,
    texte: () => (window.document.body.textContent || '').replace(/\s+/g, ' ').trim(),
    aufraeumen: () => { app.unmount(); rmSync(baum, { recursive: true, force: true }) },
    warten,
  }
}

/** Das Suchfeld der Seite (Platzhalter „Wiki durchsuchen…“). */
function suchfeld(body) {
  return [...body.querySelectorAll('input')]
    .find((el) => /durchsuchen/i.test(`${el.getAttribute('placeholder') || ''} ${el.getAttribute('aria-label') || ''}`))
}

/** Der Chip mit dieser Beschriftung (DkFilterChips), null wenn es ihn nicht gibt. */
function chip(body, label) {
  return [...body.querySelectorAll('.dk-ui-chips button')]
    .find((el) => (el.textContent || '').trim().startsWith(label)) || null
}

/** Der Listen-Aufruf (Markierung aus `fetchAttrappe`). */
function listenAufruf(aufrufe) {
  return aufrufe.find((u) => u.startsWith('wiki-liste:')) || ''
}

// ═══════════════════════════════════════════════════════════════════════════
// 1 — Aufbau mit `?kategorie=&q=` (Antwort asynchron wie beim Server)
// ═══════════════════════════════════════════════════════════════════════════
test('WIKI-Q-1 · 1: Aufbau mit `?kategorie=technik&q=Beamer` hält Suche, Kategorie, Adresse und Abfrage', async () => {
  const window = await dokument('#/wiki?kategorie=technik&q=Beamer')
  const seite = await mounten(window, { verzoegerungMs: 120 })
  try {
    // Der Baum muss stehen — sonst wäre jede Zusicherung unten leer.
    assert.ok(seite.body.querySelector('.dk-ui-chips'), 'die Chip-Zeile der Kategorie ist nicht gerendert (leerer Baum)')
    const feld = suchfeld(seite.body)
    assert.ok(feld, 'Suchfeld der Wiki-Liste fehlt')
    assert.equal(feld.value, 'Beamer',
      `das Suchfeld steht auf „${feld.value}“ statt auf „Beamer“ — ?q= ging beim Aufbau verloren`)

    const technik = chip(seite.body, 'Technik')
    assert.ok(technik, 'Chip „Technik“ fehlt')
    assert.equal(technik.getAttribute('aria-pressed'), 'true',
      'die Kategorie aus ?kategorie=technik ist nach dem Aufbau NICHT aktiv')
    assert.equal(chip(seite.body, 'Alle')?.getAttribute('aria-pressed'), 'false',
      '„Alle“ ist aktiv, obwohl ?kategorie=technik in der Adresse steht')

    const adresse = decodeURIComponent(String(window.location.hash || ''))
    assert.equal(adresse, '#/wiki?kategorie=technik&q=Beamer',
      `die Adresse wurde beim Aufbau umgeschrieben: „${adresse}“`)

    const aufruf = listenAufruf(seite.aufrufe)
    assert.match(aufruf, /search=Beamer/,
      `die Listen-API wurde ohne search=Beamer aufgerufen (${aufruf})`)
    assert.match(aufruf, /kategorie=technik/,
      `die Listen-API wurde ohne kategorie=technik aufgerufen (${aufruf})`)

    // Nach dem Laden (die Antwort kam) — Zustand und Adresse unverändert.
    await seite.warten(6, 40)
    assert.equal(suchfeld(seite.body).value, 'Beamer',
      'nach dem Laden der Liste ist das Suchfeld leer — der Filter ging verloren')
    assert.equal(chip(seite.body, 'Technik')?.getAttribute('aria-pressed'), 'true',
      'nach dem Laden ist die Kategorie nicht mehr aktiv')
    assert.equal(decodeURIComponent(String(window.location.hash || '')),
      '#/wiki?kategorie=technik&q=Beamer',
      `nach dem Laden steht in der Adresse „${window.location.hash}“ statt des Aufrufs`)
  } finally { seite.aufraeumen() }
})

// ── 2 — der Weg über den Merker („‹ zurück“ aus MT-7b) ─────────────────────
test('WIKI-Q-1 · 2: „‹ zurück“ startet die Liste mit Suche UND Kategorie', async () => {
  const { rueckwegMerken, rueckwegVergessen } = await import('../src/diakonos/composables/zurueckWege.mjs')
  rueckwegVergessen()
  rueckwegMerken('#/wiki?kategorie=technik&q=Beamer', '#/wiki', 'A-1')
  const window = await dokument('#/wiki?kategorie=technik&q=Beamer')
  const seite = await mounten(window)
  try {
    assert.equal(suchfeld(seite.body).value, 'Beamer',
      'nach „‹ zurück“ ist das Suchfeld leer')
    assert.equal(chip(seite.body, 'Technik')?.getAttribute('aria-pressed'), 'true',
      'nach „‹ zurück“ ist die Kategorie nicht aktiv')
    assert.match(listenAufruf(seite.aufrufe), /search=Beamer/,
      'nach „‹ zurück“ fragt die Liste den Server ohne Suche')
  } finally { seite.aufraeumen(); rueckwegVergessen() }
})

// ── 3 — Kategorie, die es nicht gibt ──────────────────────────────────────
test('WIKI-Q-1 · 3: unbekannte Kategorie — „Alle“ aktiv, `q=` bleibt, Adresse nennt den wirkenden Filter', async () => {
  const window = await dokument('#/wiki?kategorie=unbekannt&q=Beamer')
  const seite = await mounten(window)
  try {
    assert.equal(suchfeld(seite.body).value, 'Beamer',
      'das Suchfeld verliert ?q=, wenn ?kategorie= unbekannt ist')
    assert.equal(chip(seite.body, 'Alle')?.getAttribute('aria-pressed'), 'true',
      'eine unbekannte Kategorie darf „Alle“ nicht verdrängen')
    assert.equal(chip(seite.body, 'Unbekannt'), null,
      'für eine unbekannte Kategorie wurde ein Chip erfunden')
    // Kein Filter, der nicht greift: `activeCategory` steht auf 'all', und die
    // Adresse sagt dasselbe (der Watch schreibt den WIRKENDEN Stand).
    assert.equal(decodeURIComponent(String(window.location.hash || '')),
      '#/wiki?kategorie=all&q=Beamer',
      `die Adresse nennt einen Filter, der nicht wirkt: „${window.location.hash}“`)
    assert.match(listenAufruf(seite.aufrufe), /search=Beamer/,
      'die Liste fragt den Server ohne Suche')
  } finally { seite.aufraeumen() }
})
