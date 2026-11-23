/**
 * BEF-DESIGN-2 — die Freigabezeile steht auf den gemeinsamen Bausteinen.
 *
 * Der Befund Manuels war die KARTE „Kalender“ (#/website): die Schalterzeilen
 * „Nur freigegebene Kalender zeigen“, „Gemeindeleben“ und „Nur öffentliche
 * Terminarten zeigen“ standen eingerückt ohne sichtbaren Schalter davor, und
 * das Kürzel-Feld war anders breit als sein Hilfetext. Geprüft wird hier das
 * ERZEUGTE DOM der Zeile (Vorlage mit `vue/compiler-sfc` übersetzt, in jsdom
 * gemountet, mit den echten Bausteinen):
 *
 *   Z1  Je Freigabe steht ein sichtbarer Schalter (Kästchen) mit dem Titel als
 *       Beschriftung — links in der Zeile, nicht als reiner Text.
 *   Z2  Der Schalter trägt den zugänglichen Namen „Auf Website zeigen: <Titel>“
 *       und meldet seine Änderung an den Aufrufer (Rückfrage bleibt dort).
 *   Z3  Der Kategorie-Schalter („Nur öffentliche Terminarten zeigen“) ist eine
 *       eigene Schalterzeile — mit dem Hinweis darunter, KEIN zusätzlicher
 *       Erklärsatz am Freigabe-Schalter.
 *   Z4  Das Kürzel-Feld und sein Hilfetext stehen in EINER Spalte (`.wf-zeile`),
 *       das Feld ohne eigene Obergrenze — die Hilfe endet an derselben Kante.
 *   Z5  Die Servermeldung der Zeile erscheint GENAU EINMAL (am Kürzel-Feld) —
 *       nicht zusätzlich als zweites `role="alert"` unter dem Schalter.
 *   Z6  Unter dem Freigabe-Schalter steht KEIN Erklärsatz („Erscheint auf der
 *       Website.“ o. ä.) — der Schalter sagt es selbst; der Titel ist fett.
 *
 * Gegenprobe: Z5/Z6 sind rot gegen die Fassung von Commit 08031d6a (dort
 * standen `:error` UND der Erklärsatz an der Schalterzeile).
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath, pathToFileURL } from 'node:url'

import { JSDOM } from 'jsdom'

const HIER = path.dirname(fileURLToPath(import.meta.url))
const FRONTEND = path.resolve(HIER, '..')

const dom = new JSDOM('<!doctype html><html><body></body></html>', {
  url: 'https://example.test/',
  pretendToBeVisual: true,
})
globalThis.window = dom.window
globalThis.document = dom.window.document
Object.defineProperty(globalThis, 'navigator', {
  value: dom.window.navigator, configurable: true, writable: true,
})
globalThis.HTMLElement = dom.window.HTMLElement
globalThis.Element = dom.window.Element
globalThis.SVGElement = dom.window.SVGElement
globalThis.Node = dom.window.Node

const { createApp, h, nextTick } = await import(
  path.join(FRONTEND, 'node_modules', 'vue', 'index.mjs')
)
const { parse, compileScript } = await import(
  path.join(FRONTEND, 'node_modules', 'vue', 'compiler-sfc', 'index.mjs')
)

const UI = path.join(FRONTEND, 'src', 'diakonos', 'components', 'ui')
const WEBSITE = path.join(FRONTEND, 'src', 'diakonos', 'components', 'website')
const VUE_URL = pathToFileURL(path.join(FRONTEND, 'node_modules', 'vue', 'index.mjs')).href

const module = new Map()

/** Übersetzt eine .vue-Datei (Vorlage inline) und lädt sie als Modul. */
async function ladeSfc(absolut) {
  const quelle = readFileSync(absolut, 'utf8')
  const { descriptor, errors } = parse(quelle, { filename: absolut })
  assert.deepEqual(errors, [], `${path.basename(absolut)} liest nicht`)
  const skript = compileScript(descriptor, {
    id: path.basename(absolut),
    inlineTemplate: true,
    templateOptions: { compilerOptions: { mode: 'module' } },
  })
  const dir = path.dirname(absolut)
  const code = skript.content
    .replace(/from ['"]vue['"]/g, `from '${VUE_URL}'`)
    .replace(/from ['"](\.\.?\/[^'"]+)\.vue['"]/g, (_, rel) => {
      const ziel = path.resolve(dir, `${rel}.vue`)
      assert.ok(module.has(ziel), `${path.basename(ziel)} ist nicht geladen`)
      return `from '${module.get(ziel)}'`
    })
    .replace(/from ['"](\.\.?\/[^'"]+)(\.mjs)['"]/g,
      (_, rel, endung) => `from '${pathToFileURL(path.resolve(dir, rel + endung)).href}'`)
  const modul = `data:text/javascript;base64,${Buffer.from(code, 'utf8').toString('base64')}`
  module.set(absolut, modul)
  const geladen = await import(modul)
  assert.ok(geladen.default, `${path.basename(absolut)} hat keine Komponente`)
  return geladen.default
}

let Zeile = null
async function baustein() {
  if (Zeile) return Zeile
  // Abhängigkeiten zuerst: die Zeile nutzt Knopf, Feld und Schalterzeile.
  for (const name of ['DkButton.vue', 'DkCheckbox.vue', 'DkField.vue', 'DkSchalterZeile.vue']) {
    await ladeSfc(path.join(UI, name))
  }
  Zeile = await ladeSfc(path.join(WEBSITE, 'FreigabeZeile.vue'))
  return Zeile
}

async function zeichne(props) {
  const Bauteil = await baustein()
  const ziel = document.createElement('div')
  document.body.appendChild(ziel)
  const ereignisse = []
  const app = createApp({
    render: () => h(Bauteil, {
      ...props,
      onFreigabe: (wert) => ereignisse.push(['freigabe', wert]),
      'onNur-oeffentliche-kategorien': (wert) => ereignisse.push(['kategorien', wert]),
      onSlug: (wert) => ereignisse.push(['slug', wert]),
    }),
  })
  app.mount(ziel)
  await nextTick()
  return { ziel, ereignisse, app }
}

test('BEF-DESIGN-2/Z1: jede Freigabe hat einen sichtbaren Schalter mit Titel', async () => {
  const { ziel, app } = await zeichne({ titel: 'Gemeindeleben', name: 'G-1', freigabe: false })
  const kaestchen = ziel.querySelector('input[type="checkbox"]')
  assert.ok(kaestchen, 'kein sichtbarer Schalter in der Zeile')
  const beschriftung = ziel.querySelector('.dk-ui-checkbox-label')
  assert.ok(beschriftung && beschriftung.textContent.trim() === 'Gemeindeleben',
    'der Titel steht nicht als Beschriftung am Schalter')
  app.unmount()
})

test('BEF-DESIGN-2/Z2: der Schalter trägt den zugänglichen Namen und meldet Änderungen', async () => {
  const { ziel, ereignisse, app } = await zeichne({
    titel: 'Gemeindeleben', name: 'G-1', freigabe: false,
  })
  const kaestchen = ziel.querySelector('input[type="checkbox"]')
  assert.equal(kaestchen.getAttribute('aria-label'), 'Auf Website zeigen: Gemeindeleben')
  kaestchen.checked = true
  kaestchen.dispatchEvent(new dom.window.Event('change'))
  await nextTick()
  assert.deepEqual(ereignisse, [['freigabe', { an: true, slug: '' }]],
    'die Zeile meldet die Änderung nicht an den Aufrufer')
  app.unmount()
})

test('BEF-DESIGN-2/Z3: „Nur öffentliche Terminarten“ ist eine eigene Schalterzeile', async () => {
  const { ziel, app } = await zeichne({
    titel: 'Gemeindeleben',
    name: 'G-1',
    freigabe: true,
    zeigeKategorieSchalter: true,
    nurOeffentlicheKategorien: true,
    kategoriHinweis: 'Nur Termine der öffentlichen Terminarten erscheinen.',
  })
  const zeilen = ziel.querySelectorAll('.dk-ui-schalterzeile')
  assert.equal(zeilen.length, 2, 'die Zeile hat nicht zwei Schalterzeilen')
  const kategorieZeile = [...zeilen].find(
    (el) => (el.textContent || '').includes('Nur öffentliche Terminarten zeigen'),
  )
  assert.ok(kategorieZeile, 'der Kategorie-Schalter fehlt')
  // Der Kategorie-Schalter trägt WÖRTLICH den Hinweis des Aufrufers —
  // und die Freigabe-Zeile selbst bringt keinen zweiten Erklärsatz mit.
  assert.match(kategorieZeile.textContent, /Nur Termine der öffentlichen Terminarten erscheinen\./,
    'der Hinweis steht nicht unter dem Kategorie-Schalter')
  const freigabeZeile = [...zeilen].find(
    (el) => !(el.textContent || '').includes('Nur öffentliche Terminarten zeigen'),
  )
  assert.doesNotMatch(freigabeZeile.textContent, /Erscheint (nicht )?auf der Website\./,
    'der Freigabe-Schalter trägt wieder einen Erklärsatz')
  app.unmount()
})

test('BEF-DESIGN-2/Z4: Kürzel-Feld und Hilfetext stehen in EINER Spalte', async () => {
  const { ziel, app } = await zeichne({ titel: 'Gemeindeleben', name: 'G-1', freigabe: true })
  const feld = ziel.querySelector('.wf-zeile .wf-zeile-slugfeld')
  assert.ok(feld, 'das Kürzel-Feld steht nicht in der Zeile')
  const eingabe = feld.querySelector('input.dk-ui-eingabe')
  const hilfe = feld.querySelector('.dk-ui-field-hilfe')
  assert.ok(eingabe && hilfe, 'Feld oder Hilfetext fehlt')
  // Beide sitzen im selben Block — kein getrennter Breitenrahmen.
  assert.equal(eingabe.closest('.wf-zeile-slugfeld'), hilfe.closest('.wf-zeile-slugfeld'))
  // Das Feld hat KEINE eigene Obergrenze mehr (Befund: 420 px gegen den Text).
  const css = readFileSync(path.join(WEBSITE, 'FreigabeZeile.vue'), 'utf8')
  assert.doesNotMatch(css, /max-width:\s*420/)
  assert.match(css, /\.wf-zeile-slugfeld \{ width: 100%/)
  app.unmount()
})

test('BEF-DESIGN-2/Z5: die Servermeldung erscheint GENAU EINMAL (am Kürzel-Feld)', async () => {
  const meldung = 'Dieses Kürzel ist schon vergeben.'
  const { ziel, app } = await zeichne({
    titel: 'Gemeindeleben', name: 'G-1', freigabe: true, fehler: meldung,
  })
  // Kein Wechsel am Kürzel-Feld: die Meldung des Servers gilt dem gespeicherten
  // Stand und steht dort (`slugFehler`).
  const meldungen = [...ziel.querySelectorAll('[role="alert"]')]
    .filter((el) => (el.textContent || '').trim() === meldung)
  assert.equal(meldungen.length, 1,
    `die Servermeldung steht ${meldungen.length}× im DOM (genau 1× erwartet)`)
  // Und sie steht am Kürzel-Feld, nicht unter dem Schalter.
  assert.ok(meldungen[0].closest('.wf-zeile-slugfeld'),
    'die Servermeldung hängt nicht an ihrem Feld')
  app.unmount()
})

test('BEF-DESIGN-2/Z6: kein Erklärsatz unter dem Schalter, Titel fett', async () => {
  for (const freigabe of [true, false]) {
    const { ziel, app } = await zeichne({ titel: 'Gemeindeleben', name: 'G-1', freigabe })
    const zeile = ziel.querySelector('.dk-ui-schalterzeile')
    // KEIN Hilfetext — weder als Absatz noch als Text im Schalter.
    assert.equal(zeile.querySelectorAll('p').length, 0,
      'unter dem Freigabe-Schalter steht ein Erklärsatz')
    assert.doesNotMatch(zeile.textContent, /Erscheint (nicht )?auf der Website\./)
    // Der Titel ist die Beschriftung des Schalters und steht fett (Token).
    const titel = zeile.querySelector('.wf-zeile-titel')
    assert.ok(titel && titel.textContent.trim() === 'Gemeindeleben', 'Titel fehlt als Beschriftung')
    const css = readFileSync(path.join(WEBSITE, 'FreigabeZeile.vue'), 'utf8')
    assert.match(css, /\.wf-zeile-titel \{ font-weight: var\(--fw-fett\); \}/,
      'der Titel bekommt sein Schriftgewicht nicht aus dem Token')
    app.unmount()
  }
})
