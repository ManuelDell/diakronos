/**
 * BEF-DESIGN-2 — der Postfach-Dialog der Seite RENDERT seine Felder.
 *
 * Anlass (R1, Operator-Review nach Opus): In `pages/Website.vue` stand
 * `<DkFieldZeile>` — ein Tippfehler gegen den importierten Namen
 * `DkFeldZeile`. Vue rendert ein unbekanntes Element stillschweigend als
 * eigenes DOM-Element: das Feld „Reihenfolge“ verlor Label, Hilfe und
 * Fehleranzeige, und KEIN Test hat es gemerkt (die Quelltext-Wächter lesen nur
 * Dateien, sie prüfen nicht, ob eine Komponente existiert).
 *
 * Dieser Test schließt die Lücke: er übersetzt die ECHTE Seite mit
 * `vue/compiler-sfc` (wie der Build, Vorlage inline), mountet sie in jsdom und
 * sieht im ERZEUGTEN DOM nach:
 *
 *   P1  Die Vorlage der Seite nennt NUR Bausteine, die sie auch importiert
 *       (kein `<DkFeldZeile>`/`<DkFieldZeile>` mehr — und allgemein jedes
 *       groß geschriebene Element ist entweder importiert oder ein echtes
 *       HTML/SVG-Element). Das ist die direkte Gegenprobe zum Tippfehler.
 *   P2  Jedes Feld des Postfach-Dialogs erscheint mit Label und Eingabe:
 *       „Bezeichnung“, „Kürzel“, „E-Mail-Adresse“, „Reihenfolge“ — und
 *       „Reihenfolge“ ist ein `DkField` (`.dk-ui-field`), kein unbekanntes
 *       Element.
 *   P3  Der Dialog bringt den Schalter „Postfach ist aktiv“ als
 *       Schalterzeile mit sichtbarem Kästchen.
 *
 * Läuft im Docker-Build (`node --test`); liest nur `frontend/**` (Regel 13).
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
  url: 'https://example.test/#/website',
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
globalThis.Event = dom.window.Event
globalThis.CustomEvent = dom.window.CustomEvent
globalThis.MutationObserver = dom.window.MutationObserver
// Vue-Übergänge (`<Transition>`) takten über requestAnimationFrame.
globalThis.requestAnimationFrame = (fn) => setTimeout(() => fn(Date.now()), 0)
globalThis.cancelAnimationFrame = (id) => clearTimeout(id)

const { createApp, h, nextTick } = await import(
  path.join(FRONTEND, 'node_modules', 'vue', 'index.mjs')
)
const { parse, compileScript } = await import(
  path.join(FRONTEND, 'node_modules', 'vue', 'compiler-sfc', 'index.mjs')
)

const SEITE = path.join(FRONTEND, 'src', 'diakonos', 'pages', 'Website.vue')
const VUE_URL = pathToFileURL(path.join(FRONTEND, 'node_modules', 'vue', 'index.mjs')).href

const quelle = readFileSync(SEITE, 'utf8')
const vorlage = (() => {
  const { descriptor, errors } = parse(quelle, { filename: SEITE })
  assert.deepEqual(errors, [], 'Website.vue liest nicht')
  return descriptor.template.content
})()

// ── P1 · Nur importierte Bausteine in der Vorlage ────────────────────────
test('BEF-DESIGN-2/P1: die Vorlage nennt nur Bausteine, die auch importiert sind', () => {
  // Importierte Namen aus dem Skript-Block (Default-Importe der Bausteine).
  const skriptBlock = quelle.slice(quelle.indexOf('<script setup>'))
  const importiert = new Set(
    [...skriptBlock.matchAll(/^import\s+([A-Za-z_$][\w$]*)\s+from/gm)].map((m) => m[1]),
  )
  // Elemente, die im Skript per Import stehen ODER echte HTML/SVG-Elemente
  // sind. Alles andere ist ein Tippfehler, den Vue still als Fremdelement
  // rendert — genau der Befund (`DkFieldZeile` statt `DkFeldZeile`).
  const HTML = new Set([
    'div', 'span', 'p', 'a', 'ul', 'ol', 'li', 'strong', 'em', 'b', 'i',
    'code', 'input', 'form', 'table', 'tr', 'td', 'th', 'tbody', 'thead',
    'button', 'label', 'h1', 'h2', 'h3', 'h4', 'template', 'Transition',
    'Teleport',
  ])
  const genannt = new Set(
    [...vorlage.matchAll(/<([A-Za-z][\w.-]*)/g)].map((m) => m[1]),
  )
  const fremd = [...genannt].filter((name) => !HTML.has(name) && !importiert.has(name))
  assert.deepEqual(fremd, [],
    `unbekannte Bausteine in der Vorlage (nicht importiert): ${fremd.join(', ')}`)
  assert.doesNotMatch(vorlage, /<DkFeldZeile|<DkFieldZeile/,
    'die Vorlage nennt wieder ein erfundenes Feld-Element')
})

// ── Seitendarstellung für P2/P3 ──────────────────────────────────────────
/**
 * Die Seite lädt ihren Stand über `useApi` (GET) und `useSession`. Beides
 * wird HIER ersetzt — nicht die Seite, nicht die Bausteine: geprüft wird die
 * echte Vorlage mit den echten Komponenten.
 */
const STAND = {
  kalender: [],
  gruppen: [],
  kategorien: [],
  postfaecher: [
    { slug: 'allgemein', bezeichnung: 'Allgemein', email: 'post@example.org', aktiv: true, sortierung: 10 },
  ],
}

const ohneEndung = (datei) => datei.replace(/\.(vue|mjs)$/, '')

/**
 * Anbindungen, die durch stille Stellvertreter ersetzt werden: Netz, Sitzung
 * und alles, was daran hängt (Freigaben laden, Bausteine, Ansprechpartner).
 * Die ECHTEN Bausteine der Seite bleiben — geprüft wird die Vorlage.
 */
const NETZ = new Set([
  'useApi.js', 'useSession.js', 'useWebsite.js', 'useWebsiteFreigaben.js',
  'useWebsiteBausteine.js', 'useAnsprechpartnerBereiche.js',
  'useToast.js', 'useBestaetigen.js', 'useRueckgaengigAktion.js', 'useLadeSkelett.js',
])

let Seite = null

async function ladeSeite() {
  if (Seite) return Seite
  const { descriptor, errors } = parse(quelle, { filename: SEITE })
  assert.deepEqual(errors, [], 'Website.vue liest nicht')
  const skript = compileScript(descriptor, {
    id: 'Website.vue',
    inlineTemplate: true,
    templateOptions: { compilerOptions: { mode: 'module' } },
  })
  const dir = path.dirname(SEITE)
  const code = skript.content
    .replace(/from ['"]vue['"]/g, `from '${VUE_URL}'`)
    // Bausteine: die ECHTEN .vue-Dateien — über einen kleinen Übersetzer.
    .replace(/from ['"](\.[^'"]+)\.vue['"]/g, (_, rel) => `from '${vueModul(path.resolve(dir, rel + '.vue'))}'`)
    // Reine .mjs (shared/, Sprungmarken) bleiben echt.
    .replace(/from ['"](\.[^'"]+)\.mjs['"]/g,
      (_, rel) => `from '${pathToFileURL(path.resolve(dir, rel + '.mjs')).href}'`)
    // Anbindungen (Netz, Sitzung): ersetzt durch stille Stellvertreter.
    .replace(/from ['"](\.[^'"]+)\/([\w.-]+)\.js['"]/g, (ganz, _rel, datei) => {
      if (!NETZ.has(`${datei}.js`)) {
        return `from '${pathToFileURL(path.resolve(dir, `${datei}.js`)).href}'`
      }
      return `from '${stellvertreter(datei)}'`
    })

  const modul = `data:text/javascript;base64,${Buffer.from(code, 'utf8').toString('base64')}`
  const geladen = await import(modul)
  assert.ok(geladen.default, 'Website.vue hat keine Komponente')
  Seite = geladen.default
  return Seite
}

const vueModule = new Map()
const stellvertreterModule = new Map()

/**
 * Übersetzt eine .vue-Datei zu einem Datenmodul — mit denselben Ersetzungen
 * wie die Seite. Rekursiv: ein Baustein darf wieder Bausteine importieren.
 */
function vueModul(absolut) {
  if (vueModule.has(absolut)) return vueModule.get(absolut)
  const text = readFileSync(absolut, 'utf8')
  const { descriptor } = parse(text, { filename: absolut })
  const skript = compileScript(descriptor, {
    id: path.basename(absolut),
    inlineTemplate: true,
    templateOptions: { compilerOptions: { mode: 'module' } },
  })
  const dir = path.dirname(absolut)
  const code = skript.content
    .replace(/from ['"]vue['"]/g, `from '${VUE_URL}'`)
    .replace(/from ['"](\.[^'"]+)\.vue['"]/g, (_, rel) => `from '${vueModul(path.resolve(dir, rel + '.vue'))}'`)
    .replace(/from ['"](\.[^'"]+)\.mjs['"]/g,
      (_, rel) => `from '${pathToFileURL(path.resolve(dir, rel + '.mjs')).href}'`)
    .replace(/from ['"](\.[^'"]+)\/([\w.-]+)\.js['"]/g, (ganz, rel, datei) => {
      if (!NETZ.has(`${datei}.js`)) {
        return `from '${pathToFileURL(path.resolve(dir, rel, `${datei}.js`)).href}'`
      }
      return `from '${stellvertreter(datei)}'`
    })
  const modul = `data:text/javascript;base64,${Buffer.from(code, 'utf8').toString('base64')}`
  vueModule.set(absolut, modul)
  return modul
}

/** Stille Stellvertreter — je Modul EIN Datenmodul (Node lädt einmal). */
function stellvertreter(datei) {
  const text = {
    useToast: 'export function showToast() {}',
    useBestaetigen: 'export async function bestaetigen() { return true }',
    useRueckgaengigAktion: 'export function useRueckgaengigAktion() { return { mitRueckgaengig: async (fn) => fn() } }',
    useLadeSkelett: 'import { ref } from ' + JSON.stringify(VUE_URL) + '\nexport function useLadeSkelett() { return { skelettSichtbar: ref(false) } }',
    useSession: 'import { ref } from ' + JSON.stringify(VUE_URL) + '\nexport function useSession() { return { rollen: ref(["Administrator"]) } }',
    useWebsite: [
      'import { ref } from ' + JSON.stringify(VUE_URL),
      'export function oeffneInNeuemTab() {}',
      'export function useWebsite() {',
      '  const daten = ref(null)',
      '  return {',
      '    daten,',
      '    laedt: ref(false),',
      '    geprueft: ref(false),',
      '    fehler: ref(""),',
      '    pruefen: async () => {},',
      '    zustand: () => ({ titel: "Nicht verbunden", ton: "warn", text: "" }),',
      '    details: () => "",',
      '    primoOeffnen: async () => ({ ok: true }),',
      '  }',
      '}',
    ].join('\n'),
    useWebsiteFreigaben: 'import { ref, computed } from ' + JSON.stringify(VUE_URL) + '\nexport function useWebsiteFreigaben() {\n'
      + '  const daten = ref(' + JSON.stringify(STAND) + ')\n'
      + '  const laedt = ref(false)\n'
      + '  const fehler = ref("")\n'
      + '  const schreibt = ref(new Set())\n'
      + '  return {\n'
      + '    daten, laedt, fehler,\n'
      + '    kalender: computed(() => daten.value.kalender || []),\n'
      + '    gruppen: computed(() => daten.value.gruppen || []),\n'
      + '    postfaecher: computed(() => daten.value.postfaecher || []),\n'
      + '    kategorien: computed(() => daten.value.kategorien || []),\n'
      + '    laeuft: () => false,\n'
      + '    laden: async () => {},\n'
      + '    freigabeSetzen: async () => ({ ok: true }),\n'
      + '    postfachSpeichern: async () => ({ ok: true }),\n'
      + '    postfachLoeschen: async () => ({ ok: true }),\n'
      + '    kategorieSetzen: async () => ({ ok: true }),\n'
      + '  }\n}',
    useWebsiteBausteine: 'import { ref } from ' + JSON.stringify(VUE_URL) + '\n'
      + 'export function useWebsiteBausteine() {\n'
      + '  return {\n'
      + '    daten: ref(null), laedt: ref(false), fehler: ref(""), spieltEin: ref(false),\n'
      + '    ergebnis: ref(null),\n'
      + '    stand: () => ({}), zustand: () => ({ ton: "info", titel: "", text: "" }),\n'
      + '    zeilen: () => [],\n'
      + '    laden: async () => {}, einspielen: async () => ({ ok: true }),\n'
      + '  }\n'
      + '}',
    useAnsprechpartnerBereiche: 'import { ref } from ' + JSON.stringify(VUE_URL) + '\n'
      + 'export function useAnsprechpartnerBereiche() {\n'
      + '  return {\n'
      + '    daten: ref(null), laedt: ref(false), fehler: ref(""), speichert: ref(false),\n'
      + '    katalog: ref([]), postfaecher: ref([]),\n'
      + '    oeffentlich: ref({}), oeffentlichFehler: ref(""),\n'
      + '    laden: async () => {}, setzen: async () => ({ ok: true }),\n'
      + '    oeffentlichenStandLaden: async () => ({ ok: true }),\n'
      + '  }\n'
      + '}',
    useApi: `export async function apiGet() { return ${JSON.stringify(STAND)} }\nexport async function apiCall() { return {} }`,
  }[datei]
  assert.ok(text, `kein Stellvertreter für ${datei}`)
  const modul = `data:text/javascript;base64,${Buffer.from(text, 'utf8').toString('base64')}`
  stellvertreterModule.set(datei, modul)
  return modul
}

async function zeichne() {
  const Bauteil = await ladeSeite()
  const ziel = document.createElement('div')
  document.body.appendChild(ziel)
  const app = createApp({ render: () => h(Bauteil) })
  app.mount(ziel)
  // Laden der Freigaben (apiGet) und Platzhalter-Takt abwarten.
  for (let i = 0; i < 40; i += 1) {
    await nextTick()
    await new Promise((fertig) => setTimeout(fertig, 0))
  }
  return { ziel, app }
}

/** Öffnet den Postfach-Dialog über den echten Knopf der Karte. */
async function oeffnePostfach(ziel) {
  const knopf = [...ziel.querySelectorAll('button')]
    .find((b) => (b.textContent || '').trim() === 'Postfach anlegen')
  assert.ok(knopf, 'der Knopf „Postfach anlegen“ fehlt')
  knopf.click()
  for (let i = 0; i < 10; i += 1) {
    await nextTick()
    await new Promise((fertig) => setTimeout(fertig, 0))
  }
}

/** Alle sichtbaren Dialoge (DkDialog teleportiert nach `body`). */
const dialoge = () => [...document.body.querySelectorAll('[role="dialog"]')]

// ── P2 · Jedes Feld des Dialogs hat Label und Eingabe ────────────────────
test('BEF-DESIGN-2/P2: „Reihenfolge“ ist ein echtes Feld mit Label und Eingabe', async () => {
  const { ziel, app } = await zeichne()
  await oeffnePostfach(ziel)

  const dialog = dialoge().find((d) => (d.textContent || '').includes('Postfach anlegen'))
  assert.ok(dialog, 'der Postfach-Dialog ist nicht offen')

  for (const beschriftung of ['Bezeichnung', 'Kürzel', 'E-Mail-Adresse', 'Reihenfolge']) {
    const label = [...dialog.querySelectorAll('label')]
      .find((el) => (el.textContent || '').trim().replace(/\*+$/, '') === beschriftung)
    assert.ok(label, `das Feld „${beschriftung}“ hat kein Label`)
    const feldId = label.getAttribute('for')
    const eingabe = feldId
      ? dialog.querySelector(`#${CSS_ESCAPE(feldId)}`)
      : label.querySelector('input, textarea, select')
    assert.ok(eingabe, `das Feld „${beschriftung}“ hängt an keiner Eingabe (for=${feldId})`)
    // Das Label sitzt in einer ECHTEN Feld-Hülle — nicht in einem
    // unbekannten Element (der Befund: `<DkFeldZeile>` blieb ein Fremdelement).
    const huelle = (feldId && dialog.querySelector(`#${CSS_ESCAPE(feldId)}`))?.closest('.dk-ui-field')
    assert.ok(huelle, `das Feld „${beschriftung}“ steht nicht in einer Feld-Hülle (.dk-ui-field)`)
  }

  // „Reihenfolge“ bringt zusätzlich seinen Hilfetext mit (er gehört zum Feld).
  const reihenfolge = [...dialog.querySelectorAll('label')]
    .find((el) => (el.textContent || '').trim() === 'Reihenfolge')
  const reihenfolgeFeld = reihenfolge.closest('.dk-ui-field')
  assert.match(reihenfolgeFeld.textContent, /Kleinere Zahl steht weiter oben\./,
    'der Hilfetext des Feldes „Reihenfolge“ fehlt')
  // Und KEIN Fremdelement dieses Namens im DOM.
  assert.equal(dialog.querySelectorAll('dkfieldzeile, dk-feld-zeile, dkfield-zeile').length, 0,
    'die Seite rendert noch ein unbekanntes Feld-Element')

  app.unmount()
})

// ── P3 · Der Schalter im Dialog ist eine Schalterzeile ───────────────────
test('BEF-DESIGN-2/P3: „Postfach ist aktiv“ ist eine Schalterzeile mit Kästchen', async () => {
  const { ziel, app } = await zeichne()
  await oeffnePostfach(ziel)

  const dialog = dialoge().find((d) => (d.textContent || '').includes('Postfach anlegen'))
  assert.ok(dialog, 'der Postfach-Dialog ist nicht offen')
  const zeile = [...dialog.querySelectorAll('.dk-ui-schalterzeile')]
    .find((el) => (el.textContent || '').includes('Postfach ist aktiv'))
  assert.ok(zeile, 'der Schalter „Postfach ist aktiv“ ist keine Schalterzeile')
  const kaestchen = zeile.querySelector('input[type="checkbox"]')
  assert.ok(kaestchen, 'die Schalterzeile rendert kein sichtbares Kästchen')
  assert.equal(kaestchen.checked, true, 'der Schalter startet nicht im Stand des Formulars')

  app.unmount()
})

/** CSS.escape-Ersatz: Kennungen der Bausteine sind `[A-Za-z0-9_-]+`. */
function CSS_ESCAPE(wert) {
  return String(wert).replace(/([^A-Za-z0-9_-])/g, '\\$1')
}
