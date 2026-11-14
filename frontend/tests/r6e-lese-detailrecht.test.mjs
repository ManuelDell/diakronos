/**
 * UI-R6e — Leseseiten: `darf_bearbeiten` DIREKT aus dem Detail, Admin-Menü weg.
 *
 * Karte: Folge zu UI-R6d. Das Backend (R-12l) liefert `darf_bearbeiten` jetzt
 * auch in `get_beitrag_detail` und `get_wiki_artikel_detail`. Damit entfällt
 * der Hilfsweg über den Listeneintrag (`detailMitListe`, `listeEintrag`), und
 * das alte `DkAktionen`-Menü der Leseseiten (an `isAdmin`) muss weg: ein
 * Administrator OHNE Recht sah dort Bearbeiten/Löschen, einer MIT Recht sah
 * sie doppelt.
 *
 * Drei Prüfungen, alle am gerenderten DOM (jsdom, vue/compiler-sfc) bzw. an
 * der echten Quelldatei:
 *
 *   1. WIDERSPRUCH: Liste sagt „ja“, Detail sagt „nein“ → KEINE Knöpfe. Der
 *      Wert kommt aus dem Detail; der frühere Hilfsweg hätte das „ja“ der
 *      Liste durchgereicht. Für BEIDE Leseseiten.
 *   2. Der Beitrags-Leseseite wird die Liste im Test abgeschaltet (geteilter
 *      Link) — mit `darf_bearbeiten` im Detail stehen die Knöpfe trotzdem,
 *      und kein Listen-Aufruf findet statt.
 *   3. Kein Menü mehr: weder `DkAktionen`-Aufruf noch die alte Aktions-Leiste
 *      (`.bt-detail-aktionen`, `.wk-lese-aktionen`) stehen in Vorlage/Klassen,
 *      und im DOM gibt es weder Menü-Auslöser noch „Für Gäste freigeben“ als
 *      Menüeintrag doppelt.
 *
 * Rot-Belege (wörtliche Ausgabe im Kartenkommentar): Bedingung entfernen,
 * Liste unterlegen, Menü zurückholen — jede Probe wird rot.
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

function lies(rel) { return readFileSync(path.join(FRONTEND, rel), 'utf8') }

// ── jsdom ──────────────────────────────────────────────────────────────────
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
    globalThis.sessionStorage = window.sessionStorage
    globalThis.HTMLElement = window.HTMLElement
    globalThis.SVGElement = window.SVGElement
    globalThis.Element = window.Element
    globalThis.Node = window.Node
    globalThis.Document = window.Document
    globalThis.getComputedStyle = window.getComputedStyle.bind(window)
    globalThis.requestAnimationFrame = (fn) => setTimeout(() => fn(Date.now()), 0)
    globalThis.cancelAnimationFrame = (id) => clearTimeout(id)
    window.__DIakonosBOOT = {
      basePath: '/diakronos', csrf_token: 'test-token',
      // Admin-Kennung im Boot: Ein Administrator OHNE Recht ist der Befund dieser
      // Karte — die Rolle steht deshalb im Boot, und die Server-Antwort (Detail:
      // `darf_bearbeiten: false`) entscheidet. Vorher hing das Menü an dieser
      // Kennung und zeigte Bearbeiten/Löschen trotzdem.
      user_email: 'test@example.org', user_fullname: 'Test Person', roles: ['JR-ADMIN'],
      // `isAdmin` kommt im Boot aus `is_admin` (nicht aus `roles`).
      is_admin: true,
    }
    DOKUMENT = window
  }
  DOKUMENT.document.body.innerHTML = ''
  return DOKUMENT
}

// ── .vue/.js → ES-Module in einem Temp-Baum (Muster r6-mount) ──────────────
const geschrieben = new Set()
const BAEUME = []
process.on('exit', () => {
  for (const pfad of BAEUME) { try { rmSync(pfad, { recursive: true, force: true }) } catch { /* weg */ } }
})

function baumAnlegen() {
  const lauf = mkdtempSync(path.join(FRONTEND, '.kanban-r6e-'))
  geschrieben.clear()
  BAEUME.push(lauf)
  return lauf
}

function ziel(ausgabe, abs) {
  const rel = path.relative(SRC, abs).replace(/\.(vue|js|mjs)$/, '.mjs')
  const datei = path.join(ausgabe, 'src', rel)
  mkdirSync(path.dirname(datei), { recursive: true })
  return datei
}

function pfadUmschreiben(ausgabe, abs, pfad) {
  if (!/\.(vue|js|mjs)$/.test(pfad)) return null
  const zielAbs = path.resolve(path.dirname(abs), pfad)
  if (!readFileSafe(zielAbs)) return null
  if (pfad.endsWith('.vue')) {
    bauteilSchreiben(ausgabe, zielAbs)
    return pfad.replace(/\.vue$/, '.mjs')
  }
  modulSchreiben(ausgabe, zielAbs)
  return pfad.replace(/\.(js|mjs)$/, '.mjs')
}

function readFileSafe(abs) {
  try { return readFileSync(abs, 'utf8') } catch { return null }
}

function bauteilSchreiben(ausgabe, abs) {
  if (geschrieben.has(abs)) return
  geschrieben.add(abs)
  const id = path.basename(abs, '.vue').replace(/\W/g, '_')
  const datei = ziel(ausgabe, abs)
  writeFileSync(datei, 'export default {}\n', 'utf8')

  const { descriptor } = parse(readFileSync(abs, 'utf8'), { filename: abs })
  const skript = compileScript(descriptor, { id, inlineTemplate: true })
  let code = skript.content
  const hoistedUmschreiben = (t) => t.replace(/\b_hoisted_(\d+)\b/g, (_, n) => `_h${id}_${n}`)
  code = hoistedUmschreiben(code)
  const renderImSkript = /_createCommentVNode|_createElementVNode|_createBlock/.test(code)
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
    const neu = pfadUmschreiben(ausgabe, abs, pfad)
    return neu ? ganz.replace(pfad, neu) : ganz
  })
  writeFileSync(datei, code, 'utf8')
}

function modulSchreiben(ausgabe, abs) {
  if (geschrieben.has(abs)) return
  geschrieben.add(abs)
  const code = readFileSync(abs, 'utf8')
    .replace(/from\s+'((?:\.\.?\/)[^']+)'/g, (ganz, pfad) => {
      const neu = pfadUmschreiben(ausgabe, abs, pfad)
      return neu ? ganz.replace(pfad, neu) : ganz
    })
  writeFileSync(ziel(ausgabe, abs), code, 'utf8')
}

// ── fetch-Attrappe wie der Server (Nutzlast unter `message`) ───────────────
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
const unter = (daten) => antwort({ message: daten })

/** Fixtures tragen NUR Server-Felder — `darf_bearbeiten` jetzt auch im Detail. */
const BEITRAG_DETAIL = {
  id: 'B-1', title: 'Chorprobe', category: 'ankuendigung', excerpt: 'Kurz',
  author: 'Anna Muster', date: '2026-11-12', comments: 0, image: '', auf_website: true,
  content: '<p>Um 19 Uhr im Gemeindesaal.</p>', commentList: [],
}
const WIKI_DETAIL = {
  id: 'W-1', title: 'Beamer einrichten', category: 'technik', excerpt: 'Kurz',
  author: 'Anna Muster', authorAvatar: 'AM', updatedAt: '2026-11-12', isNew: false,
  tags: ['Beamer'], content: '<p>Kabel an Eingang 2.</p>',
}

async function rendern(relPfad, plane) {
  const window = await dokument()
  const aufrufe = []
  window.fetch = globalThis.fetch = async (url) => {
    const adresse = String(url)
    aufrufe.push(adresse)
    for (const [muster, geber] of Object.entries(plane)) {
      if (adresse.includes(muster)) return geber()
    }
    return unter({})
  }
  const ausgabe = baumAnlegen()
  const abs = path.join(SRC, relPfad)
  bauteilSchreiben(ausgabe, abs)
  const modul = await import(pathToFileURL(ziel(ausgabe, abs)).href + `?v=${Date.now()}${Math.random()}`)
  const { createApp, h, nextTick } = await import('vue')
  const knoten = window.document.createElement('div')
  window.document.body.appendChild(knoten)
  const app = createApp({ render: () => h(modul.default) })
  app.config.warnHandler = () => {}
  app.mount(knoten)
  for (let i = 0; i < 14; i += 1) {
    await new Promise((r) => setTimeout(r, 10))
    await nextTick()
  }
  return { window, aufrufe, app, body: window.document.body, baum: ausgabe }
}

const knoepfe = (body) => [...body.querySelectorAll('button')]
  .map((b) => (b.textContent || '').replace(/\s+/g, ' ').trim())
const text = (body) => (body.textContent || '').replace(/\s+/g, ' ').trim()

// ═══════════════════════════════════════════════════════════════════════════
// 1 — Widerspruch: Liste JA, Detail NEIN → das DETAIL entscheidet
// ═══════════════════════════════════════════════════════════════════════════

test('UI-R6e · 1a: Beiträge — Liste sagt ja, Detail sagt nein → keine Knöpfe', async () => {
  const window = await dokument()
  window.location.hash = '#/beitraege/B-1'
  const { body, app, baum } = await rendern('diakonos/pages/BeitragDetail.vue', {
    'beitraege.get_beitraege_liste': () => unter([{ ...BEITRAG_DETAIL, darf_bearbeiten: true }]),
    'beitraege.get_beitrag_detail': () => unter({ ...BEITRAG_DETAIL, darf_bearbeiten: false }),
  })
  try {
    assert.match(text(body), /Um 19 Uhr im Gemeindesaal/, 'die Leseseite hat nichts geladen')
    const namen = knoepfe(body)
    assert.ok(!namen.includes('Bearbeiten'),
      `das „ja“ der LISTE erzeugt Knöpfe — das Detail muss entscheiden: ${JSON.stringify(namen)}`)
    assert.ok(!namen.includes('Löschen'), `Löschen trotz „nein“ im Detail: ${JSON.stringify(namen)}`)
    assert.ok(!namen.includes('Für Gäste freigeben'), `Freigeben trotz „nein“ im Detail: ${JSON.stringify(namen)}`)
  } finally { app.unmount(); rmSync(baum, { recursive: true, force: true }); window.location.hash = '' }
})

test('UI-R6e · 1b: Wiki — Liste sagt ja, Detail sagt nein → keine Knöpfe', async () => {
  const window = await dokument()
  window.location.hash = '#/wiki/W-1'
  const { body, app, baum } = await rendern('diakonos/pages/WikiArtikel.vue', {
    'wiki.get_wiki_artikel_liste': () => unter([{ ...WIKI_DETAIL, darf_bearbeiten: true }]),
    'wiki.get_wiki_artikel_detail': () => unter({ ...WIKI_DETAIL, darf_bearbeiten: false }),
  })
  try {
    assert.match(text(body), /Kabel an Eingang 2/, 'die Artikel-Seite hat nichts geladen')
    const namen = knoepfe(body)
    assert.ok(!namen.includes('Bearbeiten'),
      `das „ja“ der LISTE erzeugt Knöpfe — das Detail muss entscheiden: ${JSON.stringify(namen)}`)
    assert.ok(!namen.includes('Löschen'), `Löschen trotz „nein“ im Detail: ${JSON.stringify(namen)}`)
  } finally { app.unmount(); rmSync(baum, { recursive: true, force: true }); window.location.hash = '' }
})

test('UI-R6e · 1c: Wiki — Detail sagt ja → Knöpfe, und die Liste liefert nur „Ähnliche“', async () => {
  const window = await dokument()
  window.location.hash = '#/wiki/W-1'
  const { body, aufrufe, app, baum } = await rendern('diakonos/pages/WikiArtikel.vue', {
    'wiki.get_wiki_artikel_liste': () => unter([
      { ...WIKI_DETAIL, darf_bearbeiten: false },
      { id: 'W-2', title: 'Beamer-Kabel', category: 'technik', tags: ['Beamer'], darf_bearbeiten: false },
    ]),
    'wiki.get_wiki_artikel_detail': () => unter({ ...WIKI_DETAIL, darf_bearbeiten: true }),
  })
  try {
    const namen = knoepfe(body)
    assert.ok(namen.includes('Bearbeiten'), `Knopf fehlt: ${JSON.stringify(namen)}`)
    assert.ok(namen.includes('Löschen'), `Knopf fehlt: ${JSON.stringify(namen)}`)
    assert.ok(namen.includes('Für Gäste freigeben'), `Knopf fehlt: ${JSON.stringify(namen)}`)
    // Die Liste wird weiterhin EINMAL geholt — für „Ähnliche Artikel“.
    const listen = aufrufe.filter((u) => u.includes('get_wiki_artikel_liste'))
    assert.equal(listen.length, 1, `Wiki-Liste ${listen.length}x geholt — für „Ähnliche“ reicht einmal`)
    assert.match(text(body), /Ähnliche Artikel/, '„Ähnliche Artikel“ fehlt (Liste nicht geladen)')
    assert.match(text(body), /Beamer-Kabel/, '„Ähnliche Artikel“ zeigt den zweiten Artikel nicht')
  } finally { app.unmount(); rmSync(baum, { recursive: true, force: true }); window.location.hash = '' }
})

// ═══════════════════════════════════════════════════════════════════════════
// 2 — Beitrags-Leseseite ohne Liste: die Knöpfe brauchen sie nicht mehr
// ═══════════════════════════════════════════════════════════════════════════

test('UI-R6e · 2: Beitrags-Leseseite fragt die Liste NICHT (geteilter Link), Knöpfe stehen trotzdem', async () => {
  const window = await dokument()
  window.location.hash = '#/beitraege/B-1'
  const { body, aufrufe, app, baum } = await rendern('diakonos/pages/BeitragDetail.vue', {
    // KEIN Eintrag für `get_beitraege_liste`: so sieht es ein geteilter Link aus.
    'beitraege.get_beitrag_detail': () => unter({ ...BEITRAG_DETAIL, darf_bearbeiten: true }),
  })
  try {
    assert.match(text(body), /Um 19 Uhr im Gemeindesaal/, 'die Leseseite hat nichts geladen')
    const listen = aufrufe.filter((u) => u.includes('get_beitraege_liste'))
    assert.equal(listen.length, 0, `die Leseseite holt die Liste (${listen.length}x) — sie braucht sie nicht`)
    const namen = knoepfe(body)
    assert.ok(namen.includes('Bearbeiten'), `Knopf fehlt ohne Liste: ${JSON.stringify(namen)}`)
    assert.ok(namen.includes('Löschen'), `Knopf fehlt ohne Liste: ${JSON.stringify(namen)}`)
    assert.ok(namen.includes('Für Gäste freigeben'), `Knopf fehlt ohne Liste: ${JSON.stringify(namen)}`)
  } finally { app.unmount(); rmSync(baum, { recursive: true, force: true }); window.location.hash = '' }
})

test('UI-R6e · 2b: Beitrag „nein“ im Detail → kein Knopf, auch wenn die Liste „ja“ sagt', async () => {
  // Dieselbe Lage wie 2, nur ohne Recht: der Server sagt im Detail nein.
  const window = await dokument()
  window.location.hash = '#/beitraege/B-1'
  const { body, aufrufe, app, baum } = await rendern('diakonos/pages/BeitragDetail.vue', {
    'beitraege.get_beitrag_detail': () => unter({ ...BEITRAG_DETAIL, darf_bearbeiten: false }),
  })
  try {
    assert.match(text(body), /Um 19 Uhr im Gemeindesaal/, 'die Leseseite hat nichts geladen')
    assert.equal(aufrufe.filter((u) => u.includes('get_beitraege_liste')).length, 0,
      'die Leseseite holt die Liste')
    const namen = knoepfe(body)
    assert.ok(!namen.includes('Bearbeiten'), `Knopf trotz „nein“: ${JSON.stringify(namen)}`)
  } finally { app.unmount(); rmSync(baum, { recursive: true, force: true }); window.location.hash = '' }
})

// ═══════════════════════════════════════════════════════════════════════════
// 3 — Das alte DkAktionen-Menü ist weg (Quelle UND DOM)
// ═══════════════════════════════════════════════════════════════════════════

const SEITEN = [
  { datei: 'diakonos/pages/BeitragDetail.vue', leiste: 'bt-detail-aktionen', hash: '#/beitraege/B-1' },
  { datei: 'diakonos/pages/WikiArtikel.vue', leiste: 'wk-lese-aktionen', hash: '#/wiki/W-1' },
]

test('UI-R6e · 3a: Quelle — kein DkAktionen mehr auf den Leseseiten, isAdmin nicht mehr benutzt', () => {
  for (const seite of SEITEN) {
    const quelle = lies(`src/${seite.datei}`)
    // Kommentare dürfen den Befund erklären — geprüft wird der CODE.
    const ohneKommentare = quelle
      .replace(/<!--[\s\S]*?-->/g, '')
      .replace(/\/\*[\s\S]*?\*\//g, '')
      .replace(/^\s*\/\/.*$/gm, '')
    assert.ok(!/DkAktionen/.test(ohneKommentare),
      `${seite.datei}: DkAktionen steht noch im Code (das Menü hing an isAdmin)`)
    assert.ok(!/useSession|isAdmin/.test(ohneKommentare),
      `${seite.datei}: die Seite benutzt isAdmin noch — Bearbeiten/Löschen hängt am Serverrecht`)
    assert.ok(!/detailMitListe|listeEintrag|listeneintrag/.test(ohneKommentare),
      `${seite.datei}: der Hilfsweg über den Listeneintrag steht noch im Code`)
    assert.match(quelle, /<div v-if="darfAendern"/,
      `${seite.datei}: die Änderungs-Knöpfe hängen nicht an `+"`darfAendern`")
  }
})

test('UI-R6e · 3b: Admin OHNE `darf_bearbeiten` sieht weder Knöpfe noch Menüeinträge', async () => {
  const window = await dokument()
  window.location.hash = '#/beitraege/B-1'
  const { body, app, baum } = await rendern('diakonos/pages/BeitragDetail.vue', {
    'beitraege.get_beitraege_liste': () => unter([{ ...BEITRAG_DETAIL, darf_bearbeiten: false }]),
    'beitraege.get_beitrag_detail': () => unter({ ...BEITRAG_DETAIL, darf_bearbeiten: false }),
  })
  try {
    // Die Admin-Kennung steht im Boot (siehe `dokument()`), der Server sagt im
    // Detail NEIN: es gibt weder Knöpfe noch Menüeinträge.
    assert.match(text(body), /Um 19 Uhr im Gemeindesaal/, 'die Leseseite hat nichts geladen')
    assert.equal(body.querySelectorAll('.bt-detail-aktionen').length, 0,
      'die alte Aktions-Leiste (.bt-detail-aktionen) steht noch im DOM')
    assert.ok(!/Aktionen für/.test(text(body)),
      `das ⋯-Menü steht noch im DOM: „${text(body).slice(0, 120)}“`)
    const namen = knoepfe(body)
    for (const verboten of ['Bearbeiten', 'Löschen', 'Für Gäste freigeben']) {
      assert.ok(!namen.includes(verboten),
        `„${verboten}“ trotz Admin-Kennung ohne Recht: ${JSON.stringify(namen)}`)
    }
  } finally { app.unmount(); rmSync(baum, { recursive: true, force: true }); window.location.hash = '' }
})

test('UI-R6e · 3b2: Admin MIT Recht sieht „Bearbeiten“/„Löschen“ genau EINMAL (keine Dopplung)', async () => {
  const window = await dokument()
  window.location.hash = '#/beitraege/B-1'
  const { body, app, baum } = await rendern('diakonos/pages/BeitragDetail.vue', {
    'beitraege.get_beitrag_detail': () => unter({ ...BEITRAG_DETAIL, darf_bearbeiten: true }),
  })
  try {
    assert.equal(body.querySelectorAll('.bt-detail-aktionen').length, 0,
      'die alte Aktions-Leiste (.bt-detail-aktionen) steht noch im DOM')
    assert.ok(!/Aktionen für/.test(text(body)), 'das ⋯-Menü steht noch im DOM')
    const namen = knoepfe(body)
    assert.equal(namen.filter((n) => n === 'Bearbeiten').length, 1,
      `„Bearbeiten“ erscheint ${namen.filter((n) => n === 'Bearbeiten').length}x — es gibt nur EINE Stelle`)
    assert.equal(namen.filter((n) => n === 'Löschen').length, 1,
      `„Löschen“ erscheint ${namen.filter((n) => n === 'Löschen').length}x — es gibt nur EINE Stelle`)
  } finally { app.unmount(); rmSync(baum, { recursive: true, force: true }); window.location.hash = '' }
})

test('UI-R6e · 3c: DOM — Wiki-Leseseite ohne Recht: kein Menü, keine Knöpfe', async () => {
  const window = await dokument()
  window.location.hash = '#/wiki/W-1'
  const { body, app, baum } = await rendern('diakonos/pages/WikiArtikel.vue', {
    'wiki.get_wiki_artikel_liste': () => unter([{ ...WIKI_DETAIL, darf_bearbeiten: false }]),
    'wiki.get_wiki_artikel_detail': () => unter({ ...WIKI_DETAIL, darf_bearbeiten: false }),
  })
  try {
    assert.match(text(body), /Kabel an Eingang 2/, 'die Artikel-Seite hat nichts geladen')
    assert.equal(body.querySelectorAll('.wk-lese-aktionen').length, 0,
      'die alte Aktions-Leiste (.wk-lese-aktionen) steht noch im DOM')
    const namen = knoepfe(body)
    for (const verboten of ['Bearbeiten', 'Löschen', 'Für Gäste freigeben']) {
      assert.ok(!namen.includes(verboten), `„${verboten}“ trotz „nein“: ${JSON.stringify(namen)}`)
    }
  } finally { app.unmount(); rmSync(baum, { recursive: true, force: true }); window.location.hash = '' }
})
