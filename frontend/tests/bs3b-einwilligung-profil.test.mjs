/**
 * BS-3b — Profil-Abschnitt „Auf der Website als Ansprechpartner erscheinen“.
 *
 * Die Karte verlangt (Punkt 1):
 *   • Laden des EIGENEN Stands,
 *   • Ändern von Einwilligung, Anzeigename und Foto-Zustimmung,
 *   • Speichern NUR bei Änderung (UX3h3-Muster),
 *   • Foto-Schalter gesperrt ohne Einwilligung ODER ohne Foto,
 *   • Widerruf ohne Rückfrage, mit „Rückgängig“ (UX2c-Mechanik).
 *
 * Zwei Teile wie bei UX3h3:
 *
 *   A · die REGEL (`src/shared/website-einwilligung.mjs`) direkt ausgeführt —
 *       Vergleich, Foto-Sperre, Widerruf-Meldung;
 *   B · das Bauteil `MeineEinwilligung.vue` WIRKLICH gemountet (jsdom, echte
 *       Klick-/input-Ereignisse). `apiCall`/`apiGet` werden auf eine Attrappe
 *       umgebogen (gleiche Modul-URL wie im Quellbaum) — kein Netz.
 *
 * Lauf: node --test tests/bs3b-einwilligung-profil.test.mjs  (cwd = frontend/)
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdirSync, mkdtempSync, readFileSync, rmSync, symlinkSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

import { compileScript, compileTemplate, parse } from 'vue/compiler-sfc'

import {
  ANZEIGENAME_MAX,
  angezeigterName,
  einwilligungAenderungen,
  einwilligungStand,
  fotoHinweis,
  fotoWaehlbar,
  speicherMeldung,
  speichernMoeglich,
} from '../src/shared/website-einwilligung.mjs'

const HIER = path.dirname(fileURLToPath(import.meta.url))
const FRONTEND = path.resolve(HIER, '..')
const SRV = path.join(FRONTEND, 'src')
const BAUTEIL = path.join(SRV, 'diakonos/components/website/MeineEinwilligung.vue')

// ══════════════════════════════════════════════════════════════════════════
// A · Die Regel selbst
// ══════════════════════════════════════════════════════════════════════════

test('BS-3b: der Stand liest die Serverantwort, fehlende Felder sind „nein“', () => {
  const leer = einwilligungStand(null)
  assert.equal(leer.einwilligung, false)
  assert.equal(leer.foto, false)
  assert.equal(leer.fotoErlaubt, false, 'ohne Angabe ist das Foto NICHT erlaubt')
  assert.equal(leer.oeffentlich, false)
  assert.equal(leer.anzeigename, '')

  const stand = einwilligungStand({
    website_einwilligung: true,
    website_einwilligung_am: '2026-11-08 10:12:33',
    website_einwilligung_foto: true,
    website_anzeigename: 'Anna',
    foto_erlaubt: true,
    oeffentlich: true,
  })
  assert.equal(stand.einwilligung, true)
  assert.equal(stand.fotoErlaubt, true)
  assert.equal(stand.oeffentlich, true)
  assert.equal(stand.am, '2026-11-08 10:12:33')
})

test('BS-3b: ohne Einwilligung ist das Foto nie „erlaubt“ — auch nicht mit roher Foto-Zustimmung', () => {
  const stand = einwilligungStand({
    website_einwilligung: false,
    website_einwilligung_foto: true,
    foto_erlaubt: true,
  })
  assert.equal(stand.foto, true, 'die rohe Zustimmung bleibt sichtbar')
  assert.equal(stand.fotoErlaubt, false, 'ohne Namens-Einwilligung darf sie nicht wirken')
})

test('BS-3b: der Foto-Schalter ist nur mit Einwilligung UND Foto wählbar', () => {
  assert.equal(fotoWaehlbar({ einwilligung: false, hatFoto: true }), false)
  assert.equal(fotoWaehlbar({ einwilligung: true, hatFoto: false }), false)
  assert.equal(fotoWaehlbar({ einwilligung: true, hatFoto: true }), true)
  // Und jeder gesperrte Fall nennt einen Grund (Karte: „sonst Hinweis“).
  assert.match(fotoHinweis({ einwilligung: false, hatFoto: true, foto: false }), /zugestimmt/)
  assert.match(fotoHinweis({ einwilligung: true, hatFoto: false, foto: false }), /Profilfoto/)
  assert.equal(fotoHinweis({ einwilligung: true, hatFoto: true, foto: true }), '')
})

test('BS-3b: gespeichert wird nur, was sich vom geladenen Stand unterscheidet', () => {
  const stand = { einwilligung: false, foto: false, anzeigename: '' }
  assert.deepEqual(einwilligungAenderungen(stand, { ...stand }), { leer: true })
  assert.deepEqual(
    einwilligungAenderungen(stand, { einwilligung: true, foto: false, anzeigename: '' }),
    { einwilligung: true, leer: false },
  )
  // Rückweg: getippt und wieder gelöscht = keine Änderung.
  assert.deepEqual(
    einwilligungAenderungen(stand, { einwilligung: false, foto: false, anzeigename: 'Anna' }),
    { anzeigename: 'Anna', leer: false },
  )
  assert.equal(
    einwilligungAenderungen(stand, { einwilligung: false, foto: false, anzeigename: '  ' }).leer,
    true,
    'nur Leerzeichen ist kein Anzeigename',
  )
})

test('BS-3b: der Widerruf schickt KEIN Foto-Feld — das setzt der Server zurück', () => {
  const stand = { einwilligung: true, foto: true, anzeigename: 'Anna' }
  const aenderungen = einwilligungAenderungen(stand, { einwilligung: false, foto: false, anzeigename: 'Anna' })
  assert.deepEqual(aenderungen, { einwilligung: false, leer: false })
  assert.equal('foto' in aenderungen, false, 'Foto-Zustimmung gehört beim Widerruf nicht in den Aufruf')
})

test('BS-3b: der Speichern-Knopf ist gesperrt, solange nichts geändert ist', () => {
  const stand = { einwilligung: false, foto: false, anzeigename: '' }
  assert.equal(speichernMoeglich(stand, { ...stand }).speicherbar, false)
  assert.equal(
    speichernMoeglich(stand, { einwilligung: true, foto: false, anzeigename: '' }).speicherbar,
    true,
  )
  const zuLang = speichernMoeglich(stand, {
    einwilligung: false,
    foto: false,
    anzeigename: 'x'.repeat(ANZEIGENAME_MAX + 1),
  })
  assert.equal(zuLang.speicherbar, false)
  assert.match(zuLang.grund, new RegExp(String(ANZEIGENAME_MAX)))
})

test('BS-3b: die Rückmeldung nennt beim Widerruf die Rücknahme', () => {
  const widerruf = speicherMeldung({ einwilligung: false, leer: false })
  assert.equal(widerruf.rueckgaengig, true)
  assert.match(widerruf.text, /widerrufen/i)
  const erteilt = speicherMeldung({ einwilligung: true, leer: false })
  assert.equal(erteilt.rueckgaengig, false)
  assert.match(erteilt.text, /erscheint/)
})

test('BS-3b: Vorschau — der Anzeigename gilt, leer heißt voller Name', () => {
  assert.equal(angezeigterName('Anna', { vorname: 'Anna', nachname: 'Beispiel' }), 'Anna')
  assert.equal(angezeigterName('', { vorname: 'Anna', nachname: 'Beispiel' }), 'Anna Beispiel')
  assert.equal(angezeigterName('  ', { vorname: 'Anna' }), 'Anna')
})

// ══════════════════════════════════════════════════════════════════════════
// B · Das Bauteil, wirklich gemountet
// ══════════════════════════════════════════════════════════════════════════

function dokumentBauen() {
  return import('jsdom').then(({ JSDOM }) => {
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
    globalThis.getComputedStyle = window.getComputedStyle.bind(window)
    globalThis.MutationObserver = window.MutationObserver
    window.__DIakonosBOOT = { basePath: '/diakronos', csrf_token: 'test-token' }
    return window
  })
}

/** SFC/JS-Bausteine als echte ES-Module in ein Temp-Verzeichnis schreiben. */
function bauteilSchreiben(abs, ausgabe, wache = new Set()) {
  if (wache.has(abs)) return
  wache.add(abs)
  const quelle = readFileSync(abs, 'utf8')
  const { descriptor } = parse(quelle, { filename: abs })
  const id = path.basename(abs)
  assert.ok(descriptor.script || descriptor.scriptSetup, `${id}: kein Skript`)
  const skript = compileScript(descriptor, { id, inlineTemplate: true })
  let code = skript.content
  if (!/_createElementVNode|_createCommentVNode|_createBlock/.test(code)) {
    const tpl = compileTemplate({
      id,
      filename: abs,
      source: descriptor.template.content,
      compilerOptions: { bindingMetadata: skript.bindings, mode: 'module' },
    })
    assert.deepEqual(tpl.errors.map(String), [], `${id}: Vorlage nicht kompilierbar`)
    const ohneExport = tpl.code.replace(/export function render/, 'function render')
    const importe = new Set()
    const rest = []
    for (const zeile of `${ohneExport}\n${skript.content}`.split('\n')) {
      if (/^import\s*\{.*\}\s*from\s*["']vue["']\s*;?$/.test(zeile.trim())) {
        for (const name of zeile.slice(zeile.indexOf('{') + 1, zeile.indexOf('}')).split(',')) {
          if (name.trim()) importe.add(name.trim())
        }
        continue
      }
      rest.push(zeile)
    }
    const rumpf = rest.join('\n')
      .replace(/\bexport const /g, 'const ')
      .replace(/export default /g, 'const __bauteil = ')
    code = `import { ${[...importe].join(', ')} } from 'vue'\n${rumpf}`
      + '\n__bauteil.render = render\nexport default __bauteil\n'
  }
  code = code.replace(/from\s+'([.][^']+)'/g, (ganz, pfad) => {
    const zielAbs = path.resolve(path.dirname(abs), pfad)
    if (/\.(vue|js|mjs)$/.test(pfad)) {
      const neu = pfad.replace(/\.(vue|js|mjs)$/, '.mjs')
      if (zielAbs.endsWith('.vue')) bauteilSchreiben(zielAbs, ausgabe, wache)
      else modulSchreiben(zielAbs, ausgabe, wache)
      return ganz.replace(pfad, neu)
    }
    return ganz
  })
  const zielDatei = path.join(ausgabe, path.relative(SRV, abs).replace(/\.vue$/, '.mjs'))
  mkdirSync(path.dirname(zielDatei), { recursive: true })
  writeFileSync(zielDatei, code, 'utf8')
}

function modulSchreiben(abs, ausgabe, wache = new Set()) {
  if (wache.has(abs)) return
  wache.add(abs)
  let code = readFileSync(abs, 'utf8')
  code = code.replace(/from\s+'([.][^']+)'/g, (ganz, pfad) => {
    const zielAbs = path.resolve(path.dirname(abs), pfad)
    if (pfad.endsWith('.vue')) {
      bauteilSchreiben(zielAbs, ausgabe, wache)
      return ganz.replace(pfad, pfad.replace(/\.vue$/, '.mjs'))
    }
    if (/\.(js|mjs)$/.test(pfad)) {
      modulSchreiben(zielAbs, ausgabe, wache)
      return ganz.replace(pfad, pfad.replace(/\.(js|mjs)$/, '.mjs'))
    }
    return ganz
  })
  const zielDatei = path.join(ausgabe, path.relative(SRV, abs).replace(/\.(js|mjs)$/, '.mjs'))
  mkdirSync(path.dirname(zielDatei), { recursive: true })
  writeFileSync(zielDatei, code, 'utf8')
}

const tick = () => new Promise((r) => setTimeout(r, 0))
async function warte(n = 6) { for (let i = 0; i < n; i += 1) await tick() }

const text = (el) => (el?.textContent || '').replace(/\s+/g, ' ').trim()

/**
 * Das Bauteil mit Attrappen-API rendern.
 *
 * `stand`   Antwort von `meine_einwilligung_lesen`
 * `options` `{ foto: '<URL>'|'', vorname, nachname }`
 */
async function rendern(stand, { foto = '', vorname = 'Anna', nachname = 'Beispiel' } = {}) {
  const window = await dokumentBauen()
  const aufrufe = []
  // Antwort auf das Schreiben: der Server liefert den neuen Stand zurück.
  let schreibAntwort = null

  const ausgabe = mkdtempSync(path.join(tmpdir(), 'bs3b-'))
  const apiDatei = path.join(ausgabe, 'api-attrappe.mjs')
  writeFileSync(apiDatei, [
    'export async function apiCall(methode, parameter) {',
    '  return globalThis.__BS3B_API(methode, parameter)',
    '}',
    'export const apiGet = apiCall',
    "export const apiUrl = (pfad) => '/diakronos/api/method/' + String(pfad).replace(/\\./g, '/')",
    'export class AuditConfirmationRequired extends Error {}',
    'export const pruefeSitzungsAntwort = () => false',
    'export async function apiAntwortPruefen() { return { message: { ok: true } } }',
  ].join('\n'))

  globalThis.__BS3B_API = async (methode, parameter) => {
    aufrufe.push({ methode, parameter })
    if (schreibAntwort) return schreibAntwort(parameter)
    return stand
  }

  bauteilSchreiben(BAUTEIL, ausgabe)
  // Die Attrappe ersetzt das echte `useApi.js`: die umgeschriebene Datei wird
  // an SEINER Stelle abgelegt (gleicher relativer Pfad).
  const apiZiel = path.join(ausgabe, 'diakonos/composables/useApi.mjs')
  mkdirSync(path.dirname(apiZiel), { recursive: true })
  writeFileSync(apiZiel, readFileSync(apiDatei, 'utf8'), 'utf8')

  const modules = path.join(ausgabe, 'node_modules')
  mkdirSync(path.dirname(modules), { recursive: true })
  symlinkSync(path.join(FRONTEND, 'node_modules'), modules, 'dir')
  try {
    const { createApp, nextTick, h } = await import('vue')
    const modul = await import(pathToFileURL(
      path.join(ausgabe, path.relative(SRV, BAUTEIL).replace(/\.vue$/, '.mjs')),
    ).href)
    const ziel = window.document.createElement('div')
    window.document.body.appendChild(ziel)
    const app = createApp({
      render: () => h(modul.default, { personenFoto: foto, vorname, nachname }),
    })
    app.config.warnHandler = () => {}
    app.mount(ziel)
    await warte(8)
    await nextTick()
    return {
      window,
      ziel: app._container,
      app,
      aufrufe,
      schreibe: (fn) => { schreibAntwort = fn },
      neuZeichnen: async () => { await warte(6); await nextTick() },
    }
  } finally {
    // Aufräumen erst nach dem Test (der Aufrufer unmountet) — die Dateien
    // werden hier NICHT gelöscht, weil die Module noch geladen sind.
    process.on('exit', () => rmSync(ausgabe, { recursive: true, force: true }))
  }
}

/** Der Schalter (erstes Kästchen) und der Foto-Schalter (zweites). */
function kaestchen(ziel) {
  return [...ziel.querySelectorAll('input[type="checkbox"]')]
}
function knopf(ziel, muster) {
  return [...ziel.querySelectorAll('button')].find((b) => muster.test(text(b)))
}
function klicken(window, el) {
  el.dispatchEvent(new window.MouseEvent('click', { bubbles: true }))
}

const BASIS_STAND = {
  website_einwilligung: false,
  website_einwilligung_am: null,
  website_einwilligung_foto: false,
  website_anzeigename: '',
  foto_erlaubt: false,
  oeffentlich: false,
}

test('BS-3b: beim Öffnen wird der EIGENE Stand geladen — nur dieser Endpunkt', async () => {
  const { ziel, aufrufe, app } = await rendern(BASIS_STAND)
  assert.equal(aufrufe.length, 1, `unerwartete Aufrufe: ${JSON.stringify(aufrufe)}`)
  assert.match(aufrufe[0].methode, /website\.meine_einwilligung_lesen$/)
  assert.match(text(ziel), /Auf der Website als Ansprechpartner erscheinen/)
  assert.match(text(ziel), /Keine Zustimmung/)
  app.unmount()
})

test('BS-3b: Schalter und Erklärtext hängen zusammen (aria-describedby)', async () => {
  const { ziel, app } = await rendern(BASIS_STAND)
  const [schalter] = kaestchen(ziel)
  const kennung = schalter.getAttribute('aria-describedby')
  assert.ok(kennung, 'kein aria-describedby am Schalter')
  const erklaerung = ziel.querySelector(`#${kennung}`)
  assert.ok(erklaerung, 'der beschriebene Erklärtext fehlt im DOM')
  const inhalt = text(erklaerung)
  assert.match(inhalt, /Was erscheinen kann/)
  assert.match(inhalt, /Was nie erscheint/)
  assert.match(inhalt, /E-Mail-Adresse/)
  assert.match(inhalt, /jederzeit widerrufen/)
  // Das Label des Schalters nennt den Inhalt, nicht nur „Einwilligung“.
  assert.match(text(ziel), /Ich bin einverstanden, dass mein Name auf der Website der Gemeinde erscheint/)
  app.unmount()
})

test('BS-3b: Speichern ist gesperrt, solange nichts geändert ist', async () => {
  const { ziel, window, app } = await rendern(BASIS_STAND)
  const speichern = knopf(ziel, /^Speichern$/)
  assert.ok(speichern, 'Speichern-Knopf fehlt')
  assert.equal(speichern.disabled, true)
  assert.equal(speichern.getAttribute('aria-disabled'), 'true')

  klicken(window, kaestchen(ziel)[0])
  await warte(4)
  assert.equal(knopf(ziel, /^Speichern$/).disabled, false, 'nach dem Umschalten muss Speichern offen sein')

  // Rückweg: wieder aus -> keine Änderung -> gesperrt.
  klicken(window, kaestchen(ziel)[0])
  await warte(4)
  assert.equal(knopf(ziel, /^Speichern$/).disabled, true)
  app.unmount()
})

test('BS-3b: der Foto-Schalter ist ohne Einwilligung gesperrt und erklärt warum', async () => {
  const { ziel, app } = await rendern(BASIS_STAND, { foto: '/files/foto.jpg' })
  const [, fotoSchalter] = kaestchen(ziel)
  assert.ok(fotoSchalter, 'Foto-Schalter fehlt')
  assert.equal(fotoSchalter.disabled, true, 'Foto ohne Einwilligung wählbar')
  assert.match(text(ziel), /Ein Foto kann erst erscheinen/)
  app.unmount()
})

test('BS-3b: ohne Profilfoto bleibt der Foto-Schalter gesperrt (Hinweis statt Schalter)', async () => {
  const { ziel, window, app } = await rendern(
    { ...BASIS_STAND, website_einwilligung: true, foto_erlaubt: false },
    { foto: '' },
  )
  const [, fotoSchalter] = kaestchen(ziel)
  assert.equal(fotoSchalter.disabled, true)
  assert.match(text(ziel), /noch kein Profilfoto/)
  // Die Einwilligung selbst bleibt umschaltbar.
  assert.equal(kaestchen(ziel)[0].checked, true)
  klicken(window, kaestchen(ziel)[0])
  await warte(4)
  assert.equal(knopf(ziel, /^Speichern$/).disabled, false)
  app.unmount()
})

test('BS-3b: mit Einwilligung und Foto ist der Foto-Schalter wählbar', async () => {
  const { ziel, app } = await rendern(
    { ...BASIS_STAND, website_einwilligung: true, foto_erlaubt: true },
    { foto: '/files/foto.jpg' },
  )
  const [, fotoSchalter] = kaestchen(ziel)
  assert.equal(fotoSchalter.disabled, false)
  app.unmount()
})

test('BS-3b: Speichern schickt NUR das Geänderte (POST, CSRF-Weg über apiCall)', async () => {
  const { ziel, window, app, aufrufe, schreibe } = await rendern(BASIS_STAND)
  schreibe((parameter) => ({
    website_einwilligung: true,
    website_einwilligung_am: '2026-11-09 09:00:00',
    website_einwilligung_foto: false,
    website_anzeigename: parameter.anzeigename || '',
    foto_erlaubt: false,
    oeffentlich: true,
  }))

  klicken(window, kaestchen(ziel)[0])
  await warte(4)
  const eingabe = ziel.querySelector('input[type="text"]')
  eingabe.value = 'Anna'
  eingabe.dispatchEvent(new window.Event('input', { bubbles: true }))
  await warte(4)

  klicken(window, knopf(ziel, /^Speichern$/))
  await warte(8)
  const schreiben = aufrufe.filter((a) => /meine_einwilligung_setzen/.test(a.methode))
  assert.equal(schreiben.length, 1, 'genau EIN Schreibaufruf')
  assert.deepEqual(schreiben[0].parameter, { einwilligung: true, anzeigename: 'Anna' })
  assert.equal('foto' in schreiben[0].parameter, false, 'unverändertes Foto darf nicht mitgeschickt werden')

  // Nach dem Speichern ist der Knopf wieder gesperrt (Stand = Serverantwort).
  assert.equal(knopf(ziel, /^Speichern$/).disabled, true)
  assert.match(text(ziel), /Zustimmung erteilt/)
  app.unmount()
})

test('BS-3b: Widerruf geht ohne Rückfrage und bietet „Rückgängig“', async () => {
  const { ziel, window, app, aufrufe, schreibe } = await rendern({
    ...BASIS_STAND,
    website_einwilligung: true,
    website_einwilligung_am: '2026-11-01 08:00:00',
    oeffentlich: true,
  })
  schreibe(() => ({ ...BASIS_STAND, website_einwilligung: false, oeffentlich: false }))

  // Kein Dialog liegt im Weg: der Klick auf das Kästchen stellt den Entwurf nur
  // um; erst „Speichern“ widerruft — und zwar ohne Rückfrage.
  klicken(window, kaestchen(ziel)[0])
  await warte(4)
  assert.equal(kaestchen(ziel)[0].checked, false, 'das Kästchen fällt beim Widerruf')
  klicken(window, knopf(ziel, /^Speichern$/))
  await warte(8)

  const schreiben = aufrufe.filter((a) => /meine_einwilligung_setzen/.test(a.methode))
  assert.equal(schreiben.length, 1)
  assert.deepEqual(schreiben[0].parameter, { einwilligung: false })
  assert.match(text(ziel), /widerrufen/i)
  const zurueck = knopf(ziel, /^Rückgängig$/)
  assert.ok(zurueck, 'Rückgängig-Knopf fehlt nach dem Widerruf')

  // Rückgängig stellt die Einwilligung wieder her.
  schreibe(() => ({
    ...BASIS_STAND,
    website_einwilligung: true,
    website_einwilligung_am: '2026-11-09 09:10:00',
    oeffentlich: true,
  }))
  klicken(window, zurueck)
  await warte(8)
  const zurueckAufrufe = aufrufe.filter((a) => /meine_einwilligung_setzen/.test(a.methode))
  assert.equal(zurueckAufrufe.length, 2)
  assert.deepEqual(zurueckAufrufe[1].parameter, { einwilligung: true })
  assert.match(text(ziel), /Zustimmung gilt wieder|Zustimmung erteilt/)
  app.unmount()
})

test('BS-3b: ein Serverfehler bleibt als Meldung stehen (kein stiller Erfolg)', async () => {
  const { ziel, window, app, schreibe } = await rendern(BASIS_STAND)
  schreibe(() => { throw new Error('Die Einwilligung kann nur die Person selbst erteilen.') })
  klicken(window, kaestchen(ziel)[0])
  await warte(4)
  klicken(window, knopf(ziel, /^Speichern$/))
  await warte(8)
  assert.match(text(ziel), /nur die Person selbst erteilen/)
  assert.equal(knopf(ziel, /^Speichern$/).disabled, false, 'nach dem Fehler bleibt die Änderung offen')
  app.unmount()
})
