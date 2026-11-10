/**
 * DEV-B4b · Mount-Test: „Einwilligungen setzen“ am ECHTEN MitgliedDetail.vue.
 *
 * Befund DMB-623c6e586e03 (dev, 29.10., Wunsch Manuel): Die Verwaltung muss
 * die zwei INTERNEN Einwilligungen (Datenschutz, Foto) setzen koennen — ohne
 * Pflicht-Begruendung, aber ersichtlich („vom Admin gesetzt am … durch …“).
 * Die WEBSITE-Einwilligung bleibt ausschliesslich bei der Person.
 *
 * Der Test rendert die echte Seite (Vorlage + `<script setup>` ueber
 * `vue/compiler-sfc`, gerendert in jsdom; `fetch` ist eine Attrappe wie der
 * Server). Geprueft wird am DOM:
 *   1. Verwaltung im BEARBEITUNGSMODUS sieht je Einwilligung einen Schalter —
 *      Datenschutz und Foto, aber KEIN Website-Schalter.
 *   2. Ein Klick sendet `admin_einwilligung_setzen` mit typ/erteilt.
 *   3. Die Herkunftszeile „vom Admin gesetzt am … durch …“ erscheint, wenn
 *      der Server `datenschutz_von_admin` liefert — und nicht ohne.
 *   4. Ohne Bearbeitungsmodus gibt es keine Schalter.
 *
 * Läuft in der Node-Testliste (`tests/dev-b4b-*.test.mjs`), ohne Browser.
 */
import assert from 'node:assert/strict'
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath, pathToFileURL } from 'node:url'

import { compileScript, compileTemplate, parse } from 'vue/compiler-sfc'

const HIER = path.dirname(fileURLToPath(import.meta.url))
const FRONTEND = path.resolve(HIER, '..')
const SRV = path.join(FRONTEND, 'src')
const SEITE = path.join(SRV, 'diakonos/pages/MitgliedDetail.vue')

// ── jsdom ──────────────────────────────────────────────────────────────────

let DOKUMENT = null

async function dokument() {
  if (DOKUMENT) return DOKUMENT
  const { JSDOM } = await import('jsdom')
  const dom = new JSDOM('<!doctype html><html><head></head><body></body></html>', {
    url: 'http://localhost/diakronos/#/mitglied/M-0001',
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
  globalThis.location = window.location
  // `useSession` liest `boot.is_admin` beim MODULSTART — die Verwaltung
  // muss deshalb schon im Boot-Objekt stehen (wie im Betrieb).
  window.__DIakonosBOOT = {
    basePath: '/diakonos',
    csrf_token: 'test-token',
    is_admin: true,
    user_email: 'verwaltung@example.org',
    roles: ['Mitgliederadministrator'],
  }
  DOKUMENT = window
  return window
}

// ── SFC → ES-Module in einem Temp-Baum ─────────────────────────────────────

let AUSGABE = null
const geschrieben = new Set()

function ziel(abs) {
  const rel = path.relative(SRV, abs).replace(/\.(vue|js|mjs)$/, '.mjs')
  const datei = path.join(AUSGABE, 'src', rel)
  mkdirSync(path.dirname(datei), { recursive: true })
  return datei
}

function pfadUmschreiben(abs, pfad) {
  if (!/\.(vue|js|mjs)$/.test(pfad)) return null
  const zielAbs = path.resolve(path.dirname(abs), pfad)
  if (zielAbs.replace(/\\/g, '/').includes('/node_modules/')) return null
  // Review DEV-B4a (10.11.): `from '…'` steht auch in Kommentaren
  // (`useRueckgaengig.js:36` nennt den Import im Fließtext). Ein Kommentar
  // ist kein Modul — ohne diese Pruefung schriebe der Umschreiber eine Datei
  // an einen Pfad, den es nicht gibt, und der Test stürbe an ENOENT.
  if (!existsSync(zielAbs)) return null
  if (pfad.endsWith('.vue')) {
    bauteilSchreiben(zielAbs)
    return pfad.replace(/\.vue$/, '.mjs')
  }
  modulSchreiben(zielAbs)
  return pfad.replace(/\.(js|mjs)$/, '.mjs')
}

function hoistedUmschreiben(t, stamm) {
  return t.replace(/\b_hoisted_(\d+)\b/g, (_, n) => `_h${stamm}_${n}`)
}

function bauteilSchreiben(abs) {
  if (geschrieben.has(abs)) return
  geschrieben.add(abs)
  const datei = ziel(abs)
  writeFileSync(datei, 'export default {}\n', 'utf8')
  const quelle = readFileSync(abs, 'utf8')
  const { descriptor, errors } = parse(quelle, { filename: abs })
  assert.deepEqual(errors, [], `${path.basename(abs)}: SFC-Struktur`)
  const id = path.basename(abs, '.vue').replace(/\W/g, '_')
  const skript = compileScript(descriptor, { id, inlineTemplate: true })
  let code = hoistedUmschreiben(skript.content, id)
  const tpl = compileTemplate({
    id,
    filename: abs,
    source: descriptor.template.content,
    compilerOptions: { bindingMetadata: skript.bindings, mode: 'module' },
    ssr: false,
    isProd: false,
  })
  assert.equal(tpl.errors.length, 0, `${id}: Vorlage nicht kompilierbar: ${tpl.errors.join(', ')}`)
  const ohneExport = hoistedUmschreiben(tpl.code.replace(/export function render/, 'function render'), id)
  const importe = new Set()
  const rest = []
  let ueberspringen = false
  let tiefe = 0
  for (const zeile of `${ohneExport}\n${skript.content}`.split('\n')) {
    if (/^import\s*\{.*\}\s*from\s*["']vue["']\s*;?$/.test(zeile.trim())) {
      for (const n of zeile.slice(zeile.indexOf('{') + 1, zeile.indexOf('}')).split(',')) {
        if (n.trim()) importe.add(n.trim())
      }
      continue
    }
    // Die eingefrorenen Knoten stehen im Renderer (schon umbenannt); die
    // gleichlautenden `const _h…` aus `compileScript` wuerden sie doppelt
    // deklarieren. Mehrzeilige Objekte brauchen den ganzen Block: bis zur
    // schliessenden `}` auf eigener Zeile, sonst bliebe der Rumpf stehen.
    if (/^\s*const _hoisted_\d+\b/.test(zeile)) {
      // Mehrzeilig? Dann bis zur Zeile, die NUR die schliessende `};` traegt.
      if (!/\}\s*;?\s*$/.test(zeile)) { ueberspringen = true; tiefe = 0 }
      else { tiefe = 0 }
      tiefe += (zeile.match(/\{/g) || []).length - (zeile.match(/\}/g) || []).length
      continue
    }
    if (ueberspringen) {
      tiefe += (zeile.match(/\{/g) || []).length - (zeile.match(/\}/g) || []).length
      if (tiefe <= 0) ueberspringen = false
      continue
    }
    rest.push(zeile)
  }
  const rumpf = rest.join('\n')
    .replace(/\bexport const /g, 'const ')
    .replace(/export default /g, 'const __bauteil = ')
  code = `import { ${[...importe].join(', ')} } from 'vue'\n${hoistedUmschreiben(rumpf, id)}`
    + '\n__bauteil.render = render\nexport default __bauteil\n'
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

// ── fetch-Attrappe wie der Server ──────────────────────────────────────────

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

const MITGLIED = {
  name: 'M-0001',
  vorname: 'Anna',
  nachname: 'Beispiel',
  email: 'anna@example.org',
  status: 'Mitglied',
  permissions: { can_view: true, can_edit: true, can_view_sensitive: true },
}

function fetchAttrappe(aufrufe, { dsgvo = {}, rollen = ['Mitgliederadministrator'] } = {}) {
  const stand = {
    datenschutz: false, datenschutz_datum: null,
    foto: false, foto_datum: null,
    werbung: false, werbung_datum: null,
    ...dsgvo,
  }
  return async (url, optionen = {}) => {
    const adresse = String(url)
    const rumpf = typeof optionen.body === 'string' ? optionen.body : ''
    aufrufe.push({ adresse, rumpf })
    if (adresse.includes('get_session_info')) return antwort({ message: { roles: rollen, user: 'verwaltung@example.org' } })
    if (adresse.includes('get_mitglied_detail')) {
      return antwort({ message: { success: true, data: { ...MITGLIED, dsgvo: { ...stand } }, permissions: MITGLIED.permissions } })
    }
    if (adresse.includes('admin_einwilligung_setzen')) {
      // `apiCall` schickt den Koerper als reines JSON (kein params-Wrapper).
      const daten = rumpf ? JSON.parse(rumpf) : {}
      if (daten.typ === 'datenschutz' && daten.erteilt) {
        stand.datenschutz = true
        stand.datenschutz_datum = '2026-11-09'
        stand.datenschutz_von_admin = { am: '2026-11-09 15:38:50', durch: 'verwaltung@example.org' }
      }
      if (daten.typ === 'foto' && daten.erteilt) {
        stand.foto = true
        stand.foto_datum = '2026-11-09'
        stand.foto_von_admin = { am: '2026-11-09 15:39:10', durch: 'verwaltung@example.org' }
      }
      return antwort({ message: { success: true, typ: daten.typ, erteilt: !!daten.erteilt } })
    }
    return antwort({ message: {} })
  }
}

async function rendern(optionen = {}) {
  const window = await dokument()
  window.document.body.innerHTML = ''
  const aufrufe = []
  window.fetch = globalThis.fetch = fetchAttrappe(aufrufe, optionen)
  const lauf = mkdtempSync(path.join(FRONTEND, '.kanban-dev-b4b-'))
  if (!AUSGABE) AUSGABE = lauf
  geschrieben.clear()
  bauteilSchreiben(SEITE)
  const modul = await import(pathToFileURL(ziel(SEITE)).href + `?v=${Date.now()}${Math.random()}`)
  const { createApp, h, nextTick } = await import('vue')
  const knoten = window.document.createElement('div')
  window.document.body.appendChild(knoten)
  const app = createApp({ render: () => h(modul.default) })
  app.config.warnHandler = () => {}
  app.mount(knoten)
  for (let i = 0; i < 10; i += 1) {
    await new Promise((r) => setTimeout(r, 0))
    await nextTick()
  }
  return { window, aufrufe, app, body: window.document.body, baum: lauf, nextTick }
}

function text(body) {
  return (body.textContent || '').replace(/\s+/g, ' ').trim()
}

function knopf(body, name) {
  return [...body.querySelectorAll('button')]
    .find((b) => (b.textContent || '').replace(/\s+/g, ' ').trim() === name)
}

async function warte() {
  for (let i = 0; i < 10; i += 1) await new Promise((r) => setTimeout(r, 0))
}

async function inDsgvoReiter(erg) {
  const tab = [...erg.body.querySelectorAll('button, [role="tab"], a')]
    .find((b) => (b.textContent || '').trim() === 'DSGVO')
  assert.ok(tab, 'DSGVO-Reiter nicht gefunden')
  tab.click()
  await warte()
}

// ── Tests ──────────────────────────────────────────────────────────────────

test('DEV-B4b: Bearbeitungsmodus zeigt Schalter für Datenschutz und Foto — NICHT für die Website', async () => {
  const erg = await rendern()
  try {
    await inDsgvoReiter(erg)
    assert.equal(erg.body.querySelectorAll('.md-schalter').length, 0,
      'ohne Bearbeitungsmodus darf es keine Setz-Schalter geben')

    const bearbeiten = knopf(erg.body, 'Bearbeiten')
    assert.ok(bearbeiten, '„Bearbeiten“-Knopf fehlt')
    bearbeiten.click()
    await warte()

    const schalter = [...erg.body.querySelectorAll('.md-schalter')].map((s) => (s.textContent || '').trim())
    assert.equal(schalter.length, 2, `Schalter: ${JSON.stringify(schalter)}`)
    assert.ok(schalter.some((s) => /Datenschutz/.test(s)), schalter.join(' | '))
    assert.ok(schalter.some((s) => /Foto/.test(s)), schalter.join(' | '))
    assert.ok(!schalter.some((s) => /Website|Veröffentlichung/i.test(s)),
      'die Website-Einwilligung darf hier nicht setzbar sein')
    assert.match(text(erg.body), /nur die Person selbst erteilen/)
  } finally { erg.app.unmount(); rmSync(erg.baum, { recursive: true, force: true }) }
})

test('DEV-B4b: ein Klick auf den Schalter sendet admin_einwilligung_setzen und zeigt die Herkunft', async () => {
  const erg = await rendern()
  try {
    await inDsgvoReiter(erg)
    knopf(erg.body, 'Bearbeiten').click()
    await warte()

    const datenschutz = [...erg.body.querySelectorAll('.md-schalter')]
      .find((s) => /Datenschutz/.test(s.textContent || ''))
    assert.ok(datenschutz, 'Datenschutz-Schalter fehlt')
    const kaestchen = datenschutz.querySelector('input[type="checkbox"]')
    assert.ok(kaestchen, 'Kein Ja/Nein-Kästchen')
    kaestchen.checked = true
    kaestchen.dispatchEvent(new erg.window.Event('change'))

    for (let i = 0; i < 20; i += 1) {
      await new Promise((r) => setTimeout(r, 0))
      if (erg.aufrufe.some((a) => a.adresse.includes('admin_einwilligung_setzen'))) break
    }
    const setzen = erg.aufrufe.filter((a) => a.adresse.includes('admin_einwilligung_setzen'))
    assert.equal(setzen.length, 1, `Aufrufe: ${erg.aufrufe.map((a) => a.adresse).join(', ')}`)
    const gesendet = JSON.parse(setzen[0].rumpf)
    assert.equal(gesendet.typ, 'datenschutz')
    assert.equal(gesendet.erteilt, true)
    assert.equal(gesendet.mitglied_id, 'M-0001')

    for (let i = 0; i < 20; i += 1) {
      await new Promise((r) => setTimeout(r, 0))
      if (/vom Admin gesetzt/.test(text(erg.body))) break
    }
    const sichtbar = text(erg.body)
    assert.match(sichtbar, /vom Admin gesetzt am 09\.11\.2026, \d{2}:\d{2} durch verwaltung@example\.org/,
      `Herkunft fehlt im DSGVO-Reiter: ${sichtbar}`)
  } finally { erg.app.unmount(); rmSync(erg.baum, { recursive: true, force: true }) }
})

test('DEV-B4b: ohne Herkunft vom Server steht KEINE „vom Admin gesetzt“-Zeile', async () => {
  const erg = await rendern({ dsgvo: { datenschutz: true, datenschutz_datum: '2026-10-01' } })
  try {
    await inDsgvoReiter(erg)
    const sichtbar = text(erg.body)
    assert.match(sichtbar, /Datenschutzerklärung akzeptiert/)
    assert.doesNotMatch(sichtbar, /vom Admin gesetzt/, sichtbar)
  } finally { erg.app.unmount(); rmSync(erg.baum, { recursive: true, force: true }) }
})

process.on('exit', () => { if (AUSGABE) rmSync(AUSGABE, { recursive: true, force: true }) })
