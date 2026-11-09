/**
 * BS-3b — Website-Bereich „Ansprechpartner“ (Verwaltung, Website-Rolle).
 *
 * Die Karte verlangt (Punkt 2):
 *   • Laden der gespeicherten Bereiche, des Funktionskatalogs und der
 *     Postfächer (BS-1a),
 *   • Bereiche setzen (volle Liste, delete-and-replace),
 *   • Kontakt-Postfach je Bereich,
 *   • Vorschau, wer davon aktuell öffentlich erscheint,
 *   • KEIN UI-Weg, eine fremde Einwilligung zu setzen — nur der Hinweistext
 *     „Die Person stimmt selbst im Profil zu“.
 *
 * Teil A prüft die Regel (`src/shared/website-einwilligung.mjs`), Teil B das
 * ECHTE Bauteil `AnsprechpartnerBereich.vue` in jsdom (apiCall-Attrappe).
 *
 * Lauf: node --test tests/bs3b-ansprechpartner-bereich.test.mjs  (cwd = frontend/)
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdirSync, mkdtempSync, readFileSync, rmSync, symlinkSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

import { compileScript, compileTemplate, parse } from 'vue/compiler-sfc'

import {
  BEREICH_ARTEN,
  EINWILLIGUNG_NUR_SELBST,
  auswahlGeaendert,
  auswahlZeile,
  bereichBezeichnung,
  bereicheNutzlast,
  bereicheZeilen,
  bereitsGewaehlt,
  funktionsKatalog,
  postfachAuswahl,
} from '../src/shared/website-einwilligung.mjs'

const HIER = path.dirname(fileURLToPath(import.meta.url))
const FRONTEND = path.resolve(HIER, '..')
const SRV = path.join(FRONTEND, 'src')
const BAUTEIL = path.join(SRV, 'diakonos/components/website/AnsprechpartnerBereich.vue')

// ── Serverantwort wie `ansprechpartner_bereiche_lesen` (BS-3a) ─────────────
function leseAntwort() {
  return {
    bereiche: [
      { art: 'dienstbereich', funktion: 'musik', bezeichnung: '', postfach: 'musik', sortierung: 1 },
      { art: 'gruppe', funktion: 'Chor', bezeichnung: 'Chor', postfach: null, sortierung: 2 },
    ],
    auswahl: {
      dienstbereich: [
        { funktion: 'musik', bezeichnung: 'Musik' },
        { funktion: 'kinder', bezeichnung: 'Kinder und Familien' },
      ],
      gruppe: [
        { funktion: 'Chor', bezeichnung: 'Chor' },
        { funktion: 'Jugend', bezeichnung: 'Jugend' },
      ],
    },
    postfaecher: [
      { slug: 'musik', bezeichnung: 'Musik' },
      { slug: 'gemeinde', bezeichnung: 'Allgemeine Anfragen' },
    ],
    einwilligungen_verwaltbar: false,
  }
}

// ══════════════════════════════════════════════════════════════════════════
// A · Die Regel
// ══════════════════════════════════════════════════════════════════════════

test('BS-3b: Zeilen werden normalisiert, sortiert und mit einem Schlüssel versehen', () => {
  const zeilen = bereicheZeilen({
    bereiche: [
      { art: 'Gruppe', funktion: 'Jugend', sortierung: 5 },
      { art: 'dienstbereich', funktion: 'musik', bezeichnung: 'Musik', postfach: null, sortierung: 1 },
    ],
  })
  assert.equal(zeilen.length, 2)
  assert.equal(zeilen[0].art, 'dienstbereich', 'Sortierung bestimmt die Reihenfolge')
  assert.equal(zeilen[0].schluessel, 'dienstbereich:musik')
  assert.equal(zeilen[0].postfach, '', 'null wird zu einem leeren Wert')
  assert.equal(zeilen[1].art, 'gruppe')
})

test('BS-3b: der Funktionskatalog wird als Liste gelesen (und als Objekt verkraftet)', () => {
  const liste = funktionsKatalog(leseAntwort(), 'dienstbereich')
  assert.deepEqual(liste.map((e) => e.funktion), ['kinder', 'musik'])
  // Alte Doku-Form `{name: {bezeichnung}}` darf die Oberfläche nicht blind machen.
  const objekt = funktionsKatalog({ auswahl: { gruppe: { Chor: { bezeichnung: 'Chor' } } } }, 'gruppe')
  assert.deepEqual(objekt, [{ funktion: 'Chor', bezeichnung: 'Chor' }])
})

test('BS-3b: Postfächer kommen nur als Slug und Bezeichnung (nie als Adresse)', () => {
  const postfaecher = postfachAuswahl({
    postfaecher: [{ slug: 'musik', bezeichnung: 'Musik', email: 'geheim@example.org' }],
  })
  assert.deepEqual(postfaecher, [{ slug: 'musik', bezeichnung: 'Musik' }])
  assert.equal('email' in postfaecher[0], false)
})

test('BS-3b: die Nutzlast ist die VOLLE Liste ohne Einwilligungsfelder', () => {
  const nutzlast = bereicheNutzlast([
    { art: 'dienstbereich', funktion: 'musik', bezeichnung: '', postfach: '', sortierung: 0 },
    { art: 'gruppe', funktion: 'Chor', bezeichnung: ' Chor ', postfach: 'musik', sortierung: 1 },
  ])
  assert.deepEqual(nutzlast[0], {
    art: 'dienstbereich', funktion: 'musik', bezeichnung: '', postfach: null, sortierung: 0,
  })
  assert.equal(nutzlast[1].bezeichnung, 'Chor')
  for (const eintrag of nutzlast) {
    for (const verboten of ['website_einwilligung', 'website_einwilligung_foto', 'website_anzeigename']) {
      assert.equal(verboten in eintrag, false, `${verboten} gehört nicht in die Nutzlast`)
    }
  }
})

test('BS-3b: „geändert?“ erkennt Postfach-/Bezeichnungs-/Listenwechsel', () => {
  const antwort = leseAntwort()
  const gleich = bereicheZeilen(antwort)
  assert.equal(auswahlGeaendert(antwort, gleich), false)
  assert.equal(
    auswahlGeaendert(antwort, gleich.map((z, i) => (i === 0 ? { ...z, postfach: 'gemeinde' } : z))),
    true,
  )
  assert.equal(
    auswahlGeaendert(antwort, gleich.slice(0, 1)),
    true,
    'eine entfernte Zeile ist eine Änderung',
  )
})

test('BS-3b: eine Funktion darf nur einmal gewählt werden; Art-Label und Bezeichnung passen', () => {
  const zeilen = [{ art: 'gruppe', funktion: 'Chor' }]
  assert.equal(bereitsGewaehlt(zeilen, 'gruppe', 'Chor'), true)
  assert.equal(bereitsGewaehlt(zeilen, 'dienstbereich', 'Chor'), false)
  assert.equal(BEREICH_ARTEN.map((a) => a.value).join(','), 'dienstbereich,gruppe')
  const katalog = [{ funktion: 'Chor', bezeichnung: 'Chor Süd' }]
  assert.equal(bereichBezeichnung({ funktion: 'Chor' }, katalog), 'Chor Süd')
  assert.equal(bereichBezeichnung({ funktion: 'Chor', bezeichnung: 'Chor Nord' }, katalog), 'Chor Nord')
  assert.equal(auswahlZeile({ art: 'gruppe', funktion: 'Chor' }).schluessel, 'gruppe:Chor')
})

test('BS-3b: der Hinweis „die Person stimmt selbst zu“ ist wortgleich hinterlegt', () => {
  assert.match(EINWILLIGUNG_NUR_SELBST, /Person selbst/)
  assert.match(EINWILLIGUNG_NUR_SELBST, /nicht setzen/)
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

/** Temp-Bäume dieses Laufs (erst nach ALLEN Tests entfernt). */
const offeneBaeume = []
test.after(() => {
  for (const baum of offeneBaeume) rmSync(baum, { recursive: true, force: true })
})

const tick = () => new Promise((r) => setTimeout(r, 0))
async function warte(n = 8) { for (let i = 0; i < n; i += 1) await tick() }
const text = (el) => (el?.textContent || '').replace(/\s+/g, ' ').trim()

/**
 * Bauteil rendern. `antworten` bildet Methode → Antwort ab; `oeffentlich` ist
 * der Stand von `website.oeffentlich.ansprechpartner`.
 */
async function rendern({ antworten = {}, oeffentlich = [], schreibFehler = null } = {}) {
  const window = await dokumentBauen()
  const aufrufe = []
  const ausgabe = mkdtempSync(path.join(tmpdir(), 'bs3b-verw-'))

  globalThis.__BS3B_API = async (methode, parameter) => {
    aufrufe.push({ methode, parameter })
    if (/oeffentlich\.ansprechpartner$/.test(methode)) return oeffentlich
    if (/bereiche_setzen$/.test(methode)) {
      if (schreibFehler) throw new Error(schreibFehler)
      return { bereiche: parameter.bereiche }
    }
    if (/bereiche_lesen$/.test(methode)) return antworten.lesen ?? leseAntwort()
    throw new Error('unerwarteter Aufruf: ' + methode)
  }

  bauteilSchreiben(BAUTEIL, ausgabe)
  const apiZiel = path.join(ausgabe, 'diakonos/composables/useApi.mjs')
  mkdirSync(path.dirname(apiZiel), { recursive: true })
  writeFileSync(apiZiel, [
    'export async function apiCall(methode, parameter) {',
    '  return globalThis.__BS3B_API(methode, parameter)',
    '}',
    'export const apiGet = apiCall',
    "export const apiUrl = (pfad) => '/diakronos/api/method/' + String(pfad).replace(/\\./g, '/')",
    'export class AuditConfirmationRequired extends Error {}',
    'export const pruefeSitzungsAntwort = () => false',
    'export async function apiAntwortPruefen() { return { message: { ok: true } } }',
  ].join('\n'), 'utf8')

  const modules = path.join(ausgabe, 'node_modules')
  mkdirSync(path.dirname(modules), { recursive: true })
  symlinkSync(path.join(FRONTEND, 'node_modules'), modules, 'dir')
  const { createApp, nextTick } = await import('vue')
  const modul = await import(pathToFileURL(
    path.join(ausgabe, path.relative(SRV, BAUTEIL).replace(/\.vue$/, '.mjs')),
  ).href)
  const ziel = window.document.createElement('div')
  window.document.body.appendChild(ziel)
  const app = createApp(modul.default)
  app.config.warnHandler = () => {}
  app.mount(ziel)
  await warte(10)
  await nextTick()
  // NICHT beim Prozessende löschen: sonst laufen mehrere Temp-Bäume parallel
  // weiter und `import()` derselben Pfade liefert den ERSTEN Modul-Cache
  // (Befund: Bauteil-Zustand aus einem früheren Test). Aufräumen übernimmt
  // `test.after` unten.
  offeneBaeume.push(ausgabe)

  return { window, ziel, app, aufrufe }
}

const knopf = (ziel, muster) => [...ziel.querySelectorAll('button')].find((b) => muster.test(text(b)))
/** Der Speichern-Knopf der Ansicht (der einzige Primärknopf im Bereich). */
const speichernKnopf = (ziel) => ziel.querySelector('button.dk-ui-btn--primary')
function klicken(window, el) { el.dispatchEvent(new window.MouseEvent('click', { bubbles: true })) }
/** Die native Auswahl im Feld (DkSelect zeichnet ein `<select>`). */
function aenderbaresFeld(el) {
  return el.tagName === 'SELECT' ? el : el.querySelector('select')
}

function waehlen(window, el, wert) {
  const feld = el.tagName === 'SELECT' || el.querySelector ? aenderbaresFeld(el) : null
  assert.ok(feld, 'kein Auswahlfeld gefunden')
  feld.value = wert
  feld.dispatchEvent(new window.Event('change', { bubbles: true }))
}

test('BS-3b: beim Öffnen werden Auswahl, Katalog und Postfächer geladen', async () => {
  const { ziel, aufrufe, app } = await rendern({})
  const methoden = aufrufe.map((a) => a.methode)
  assert.ok(methoden.some((m) => /ansprechpartner_bereiche_lesen$/.test(m)), 'Auswahl nicht geladen')
  assert.ok(methoden.some((m) => /oeffentlich\.ansprechpartner$/.test(m)), 'öffentlicher Stand nicht geladen')

  const inhalt = text(ziel)
  assert.match(inhalt, /Ansprechpartner/)
  assert.match(inhalt, /Musik/, 'Dienstbereich Musik fehlt')
  assert.match(inhalt, /Chor/, 'Gruppe Chor fehlt')
  app.unmount()
})

test('BS-3b: die Einwilligung wird hier NIE gesetzt — nur der Hinweis steht da', async () => {
  const { ziel, app } = await rendern({})
  assert.match(text(ziel), /Ob jemand auf der Website erscheint, entscheidet die Person selbst in ihrem Profil/)
  // Kein Kästchen für eine fremde Einwilligung, kein Foto-Schalter, kein
  // Anzeigename-Feld — nur Auswahlen und Knöpfe.
  assert.equal(ziel.querySelectorAll('input[type="checkbox"]').length, 0)
  assert.equal(ziel.querySelectorAll('input[type="text"]').length, 0)
  // Und in der Nutzlast steht kein Einwilligungsfeld (Regel dafür: Teil A).
  app.unmount()
})

test('BS-3b: Speichern ist gesperrt, solange die Auswahl unverändert ist', async () => {
  const { ziel, app } = await rendern({})
  const speichern = speichernKnopf(ziel)
  assert.ok(speichern, 'Speichern-Knopf fehlt')
  assert.equal(speichern.disabled, true)
  assert.equal(speichern.getAttribute('aria-disabled'), 'true')
  // Genau EIN Primärknopf im Bereich.
  const primaer = [...ziel.querySelectorAll('button')].filter((b) => /dk-ui-btn--primary/.test(b.className))
  assert.equal(primaer.length, 1, `Primärknöpfe: ${primaer.map((b) => text(b)).join(', ')}`)
  app.unmount()
})

test('BS-3b: einen Bereich hinzufügen öffnet Speichern; die Liste geht vollständig raus', async () => {
  const { ziel, window, app, aufrufe } = await rendern({})
  // Art und Funktion der NEUEN Zeile stehen im Block „hinzufügen“ — nicht in
  // den Zeilen darüber (die tragen nur ihr Postfach-Feld).
  const [artFeld, funktionFeld] = [...ziel.querySelectorAll('.wa-neu-zeile select')]
  assert.ok(artFeld && funktionFeld, 'Auswahlfelder zum Übernehmen fehlen')
  waehlen(window, artFeld, 'gruppe')
  await warte(3)
  waehlen(window, funktionFeld, 'Jugend')
  await warte(3)
  klicken(window, knopf(ziel, /^Übernehmen$/))
  await warte(4)
  assert.match(text(ziel), /Jugend/)
  const speichern = speichernKnopf(ziel)
  assert.equal(speichern.disabled, false, 'Speichern muss nach der Änderung offen sein')
  klicken(window, speichern)
  await warte(10)
  const schreiben = aufrufe.filter((a) => /bereiche_setzen$/.test(a.methode))
  assert.equal(schreiben.length, 1)
  const liste = schreiben[0].parameter.bereiche
  assert.equal(liste.length, 3, 'die VOLLE Liste geht raus (delete-and-replace)')
  assert.deepEqual(liste[2], {
    art: 'gruppe', funktion: 'Jugend', bezeichnung: '', postfach: null, sortierung: 2,
  })
  for (const eintrag of liste) {
    assert.equal('website_einwilligung' in eintrag, false)
  }
  assert.match(text(ziel), /gespeichert/)
  app.unmount()
})

test('BS-3b: das Kontakt-Postfach wird je Bereich gewählt und mitgeschickt', async () => {
  const { ziel, window, app, aufrufe } = await rendern({})
  const zeile = ziel.querySelector('[data-wa-zeile="dienstbereich:musik"]')
  const postfachFeld = zeile.querySelector('select')
  assert.ok(postfachFeld, 'Postfach-Feld der Zeile Musik fehlt')
  waehlen(window, postfachFeld, 'gemeinde')
  await warte(6)
  assert.equal(postfachFeld.value, 'gemeinde', 'Auswahlfeld zeigt den gewählten Slug')

  const speichern = speichernKnopf(ziel)
  assert.equal(speichern.disabled, false, 'Speichern muss nach der Änderung offen sein')
  klicken(window, speichern)
  await warte(10)
  const schreiben = aufrufe.find((a) => /bereiche_setzen$/.test(a.methode))
  assert.ok(schreiben, 'kein Schreibaufruf erfolgt')
  const liste = schreiben.parameter.bereiche
  // Welche Position den gewählten Slug trägt, hängt an der Serverantwort-
  // Sortierung — geprüft wird der Inhalt, nicht die Stelle.
  assert.equal(liste.find((e) => e.funktion === 'musik').postfach, 'gemeinde')
  assert.equal(liste.find((e) => e.funktion === 'Chor').postfach, null)
  app.unmount()
})

test('BS-3b: Vorschau zeigt den ÖFFENTLICHEN Stand, ohne Einwilligung erscheint niemand', async () => {
  const ohne = await rendern({ oeffentlich: [] })
  assert.match(text(ohne.ziel), /Niemand erscheint gerade/)
  assert.match(text(ohne.ziel), /nicht zugestimmt|zugestimmt/) // Hinweis auf die fehlende Einwilligung
  ohne.app.unmount()

  const mit = await rendern({
    oeffentlich: [
      { bereich: 'Musik', funktion: 'fn-1', name: 'Anna', foto_url: '', postfach: 'pf-1' },
    ],
  })
  const inhalt = text(mit.ziel)
  assert.match(inhalt, /Anna/)
  assert.match(inhalt, /Musik/)
  // Die Vorschau zeigt NUR, was öffentlich ist — kein Name einer Person ohne
  // Einwilligung (die Verwaltungs-API liefert auch keinen).
  assert.doesNotMatch(inhalt, /Miriam/)
  mit.app.unmount()
})

test('BS-3b: ein Serverfehler beim Speichern bleibt als Meldung stehen', async () => {
  const { ziel, window, app } = await rendern({
    schreibFehler: 'Diese Funktion gibt es im Organigramm nicht mehr. Bitte die Liste neu laden.',
  })
  const postfachFeld = ziel.querySelector('[data-wa-zeile="dienstbereich:musik"] select')
  assert.ok(postfachFeld, 'Postfach-Feld der Zeile Musik fehlt')

  waehlen(window, postfachFeld, 'gemeinde')
  await warte(4)
  const speichern = speichernKnopf(ziel)
  assert.equal(speichern.disabled, false, 'Speichern muss nach der Änderung offen sein')
  klicken(window, speichern)
  await warte(10)
  assert.match(text(ziel), /gibt es im Organigramm nicht mehr/)
  app.unmount()
})
