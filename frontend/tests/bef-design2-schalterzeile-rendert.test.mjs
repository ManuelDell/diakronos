/**
 * BEF-DESIGN-2 — die Schalterzeile RENDERT wirklich einen Schalter.
 *
 * Der Quelltext-Wächter (`bef-design2-website-abstaende.test.mjs`) liest nur
 * Dateien; dieser Test baut die beiden Bausteine mit dem ECHTEN SFC-Übersetzer
 * (`vue/compiler-sfc`) zu Modulen zusammen, lädt sie (Daten-URL) und sieht im
 * ERZEUGTEN DOM nach:
 *
 *   R1  `<input type="checkbox">` steht VOR der Beschriftung (linksbündig) und
 *       nimmt Klicks an (Modell ändert sich).
 *   R2  Der Hilfetext steht darunter, trägt eine Kennung, und das Kästchen
 *       verweist per `aria-describedby` genau darauf.
 *   R3  Ohne Hilfe (und ohne Meldung) gibt es KEIN `aria-describedby` und
 *       keinen leeren Absatz — kein Zeiger ins Leere, kein Abstand ohne Inhalt.
 *   R4  Der Hilfetext ist eingerückt (Kästchenbreite über die Tokens) und steht
 *       NACH dem Kästchen — nicht bündig am Kästchen und nicht ohne Bezug.
 *   R5  Eine Meldung (`error`) gewinnt gegen den Hilfetext (Server weiß mehr)
 *       und steht als `role="alert"` da.
 *
 * Gegenprobe: gegen die alte Fassung der Website-Seite gab es diesen Baustein
 * nicht — die Schalter standen dort als nacktes `DkCheckbox` ohne Hilfetext-
 * Anbindung im Kartenkörper (R1–R5 waren nicht zu bestehen).
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
// `navigator` ist in Node 22 nur lesbar — über `defineProperty` setzen.
Object.defineProperty(globalThis, 'navigator', {
  value: dom.window.navigator, configurable: true, writable: true,
})
globalThis.HTMLElement = dom.window.HTMLElement
globalThis.Element = dom.window.Element
globalThis.SVGElement = dom.window.SVGElement
globalThis.Node = dom.window.Node

// Über die Exporte des Pakets (nicht über Unterpfade): `vue` liefert in Node
// die Laufzeit, `vue/compiler-sfc` den Übersetzer — beide so, wie der Build
// sie sieht.
const { createApp, h, nextTick } = await import(
  path.join(FRONTEND, 'node_modules', 'vue', 'index.mjs')
)
const { parse, compileScript } = await import(
  path.join(FRONTEND, 'node_modules', 'vue', 'compiler-sfc', 'index.mjs')
)

const UI = path.join(FRONTEND, 'src', 'diakonos', 'components', 'ui')
const VUE_URL = pathToFileURL(path.join(FRONTEND, 'node_modules', 'vue', 'index.mjs')).href

/**
 * Übersetzt eine .vue-Datei mit `compileScript` (Vorlage INLINE — genau der
 * Weg des Builds). Die Bausteine werden NACHEINANDER geladen (erst
 * `DkCheckbox`, dann die Zeile), damit kein `.vue`-Import im Modul steht:
 * Node kennt die Endung nicht, und genau das ist der Grund für diesen Umweg.
 */
const zwischenspeicher = new Map()

function uebersetze(absolut) {
  const quelle = readFileSync(absolut, 'utf8')
  const { descriptor, errors } = parse(quelle, { filename: absolut })
  assert.deepEqual(errors, [], `${path.basename(absolut)} liest nicht`)
  const skript = compileScript(descriptor, {
    id: path.basename(absolut),
    inlineTemplate: true,
    templateOptions: { compilerOptions: { mode: 'module' } },
  })
  let code = skript.content
    .replace(/from ['"]vue['"]/g, `from '${VUE_URL}'`)
    .replace(/from ['"](\.\.?\/[^'"]+)\.vue['"]/g, (_, rel) => {
      // Der Baustein ist schon geladen (siehe `ladeSfc`).
      const schluessel = path.resolve(path.dirname(absolut), `${rel}.vue`)
      return `from '${zwischenspeicher.get(schluessel)}'`
    })
    .replace(/from ['"](\.\.?\/[^'"]+)(\.mjs)['"]/g, (_, rel, endung) => {
      return `from '${pathToFileURL(path.resolve(path.dirname(absolut), rel + endung)).href}'`
    })
  return code
}

/**
 * Lädt eine .vue-Datei als Modul. Bausteine, die sie importiert, müssen vorher
 * in `zwischenspeicher` liegen (URL ihres Datenmoduls).
 */
async function ladeSfc(absolut) {
  const code = uebersetze(absolut)
  const modul = `data:text/javascript;base64,${Buffer.from(code, 'utf8').toString('base64')}`
  zwischenspeicher.set(absolut, modul)
  const geladen = await import(modul)
  assert.ok(geladen.default, `${path.basename(absolut)} hat keine Komponente`)
  return geladen.default
}

let SchalterZeile = null
async function baustein() {
  if (SchalterZeile) return SchalterZeile
  // Abhängigkeit zuerst: die Zeile importiert das Kästchen.
  await ladeSfc(path.join(UI, 'DkCheckbox.vue'))
  SchalterZeile = await ladeSfc(path.join(UI, 'DkSchalterZeile.vue'))
  return SchalterZeile
}

/** Baut die Schalterzeile in ein frisches Element und gibt den Stand zurück. */
async function zeichne(props) {
  const Bauteil = await baustein()
  const ziel = document.createElement('div')
  document.body.appendChild(ziel)
  const stand = { wert: props.modelValue === true }
  const app = createApp({
    render: () => h(Bauteil, {
      ...props,
      modelValue: stand.wert,
      'onUpdate:modelValue': (wert) => { stand.wert = wert },
    }),
  })
  app.mount(ziel)
  await nextTick()
  return { ziel, stand, app }
}

test('BEF-DESIGN-2/R1: die Schalterzeile rendert ein Kästchen VOR der Beschriftung', async () => {
  const { ziel, stand, app } = await zeichne({ label: 'Gemeindeleben', modelValue: false })
  const kaestchen = ziel.querySelector('input[type="checkbox"]')
  assert.ok(kaestchen, 'kein Kästchen im DOM — die Zeile ist nur Text')
  assert.equal(kaestchen.disabled, false)

  // Reihenfolge im DOM: Kästchen vor dem Text der Beschriftung (linksbündig).
  assert.ok((ziel.textContent || '').includes('Gemeindeleben'), 'Beschriftung fehlt')
  const blattknoten = [...ziel.querySelectorAll('*')].filter((el) => el.children.length === 0)
  const posKaestchen = blattknoten.indexOf(kaestchen)
  const posText = blattknoten.findIndex((el) => (el.textContent || '').trim() === 'Gemeindeleben')
  assert.ok(posKaestchen >= 0 && posText > posKaestchen,
    'das Kästchen steht nicht vor der Beschriftung')

  // Der Schalter nimmt Klicks an (Modell ändert sich).
  kaestchen.checked = true
  kaestchen.dispatchEvent(new dom.window.Event('change'))
  await nextTick()
  assert.equal(stand.wert, true, 'der Klick erreicht das Modell nicht')
  app.unmount()
})

test('BEF-DESIGN-2/R2: der Hilfetext hängt per aria-describedby am Kästchen', async () => {
  const { ziel, app } = await zeichne({
    label: 'Gemeindeleben',
    help: 'Erscheint auf der Website.',
    modelValue: true,
  })
  const kaestchen = ziel.querySelector('input[type="checkbox"]')
  const beschrieben = kaestchen.getAttribute('aria-describedby')
  assert.ok(beschrieben, 'das Kästchen hat kein aria-describedby')
  const zielText = ziel.querySelector(`#${beschrieben}`)
  assert.ok(zielText, `aria-describedby zeigt auf nichts: ${beschrieben}`)
  assert.match(zielText.textContent, /Erscheint auf der Website\./)
  app.unmount()
})

test('BEF-DESIGN-2/R3: ohne Hilfe kein Zeiger ins Leere und kein leerer Absatz', async () => {
  const { ziel, app } = await zeichne({ label: 'Gemeindeleben', modelValue: true })
  const kaestchen = ziel.querySelector('input[type="checkbox"]')
  assert.equal(kaestchen.getAttribute('aria-describedby'), null, 'leeres aria-describedby im DOM')
  const absaetze = [...ziel.querySelectorAll('p')].map((p) => p.textContent.trim())
  assert.deepEqual(absaetze, [], 'leerer Absatz unter der Zeile')
  app.unmount()
})

test('BEF-DESIGN-2/R4: der Hilfetext ist eingerückt und steht unter dem Kästchen', async () => {
  const datei = path.join(UI, 'DkSchalterZeile.vue')
  const css = readFileSync(datei, 'utf8')
  const regel = /\.dk-ui-schalterzeile-hilfe,[\s\S]*?\}/.exec(css)
  assert.ok(regel, 'Regel für den Hilfetext fehlt')
  assert.match(regel[0], /padding-left: calc\(var\(--sp-4\) \+ var\(--sp-2\)\)/,
    'der Hilfetext ist nicht auf die Beschriftung eingerückt')
  assert.match(regel[0], /margin: 0/, 'der Hilfetext bringt einen eigenen Außenabstand mit')

  // Und im DOM steht er NACH dem Kästchen (darunter, nicht davor).
  const { ziel, app } = await zeichne({ label: 'Gemeindeleben', help: 'Ein Satz.', modelValue: true })
  const kaestchen = ziel.querySelector('input[type="checkbox"]')
  const hilfe = ziel.querySelector('.dk-ui-schalterzeile-hilfe')
  assert.ok(hilfe && hilfe.textContent.trim() === 'Ein Satz.')
  assert.ok(kaestchen.compareDocumentPosition(hilfe) & dom.window.Node.DOCUMENT_POSITION_FOLLOWING,
    'der Hilfetext steht nicht unter dem Kästchen')
  app.unmount()
})

test('BEF-DESIGN-2/R5: eine Meldung gewinnt gegen den Hilfetext', async () => {
  const { ziel, app } = await zeichne({
    label: 'Gemeindeleben',
    help: 'Der Hilfetext steht hier nicht.',
    error: 'Das hat nicht geklappt.',
    modelValue: true,
  })
  const kaestchen = ziel.querySelector('input[type="checkbox"]')
  const beschrieben = ziel.querySelector(`#${kaestchen.getAttribute('aria-describedby')}`)
  assert.match(beschrieben.textContent, /Das hat nicht geklappt\./, 'die Meldung steht nicht am Kästchen')
  assert.equal(beschrieben.getAttribute('role'), 'alert')
  assert.doesNotMatch(ziel.textContent, /Der Hilfetext steht hier nicht\./,
    'Hilfe und Meldung stehen gleichzeitig')
  app.unmount()
})
