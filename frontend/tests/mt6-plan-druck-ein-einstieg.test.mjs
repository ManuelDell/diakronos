/**
 * MT-6 — Pläne drucken: doppelter Druck auf einen reduzieren.
 *
 * Befund (Manuel 11.11., Live-Test dev.ecg-hn.de): Beim Drucken der Pläne
 * (Dienste → Dienstpläne / Planrahmen-Plan) gab es ZWEI Druck-Möglichkeiten
 * mit absolut identischem Druckbild. Ursache in PrAnsicht.vue: zwei
 * `v-if`-Leisten — `pr-druck-leiste` (UXP-R7, „Drucken“ für JEDE Ansicht) und
 * `pr-ansicht-druckleiste` („Druckansicht (A4 …)“ für deklarierte
 * Druckansichten). Ein Plan, der eine `druck`-Ansicht deklariert (z. B. der
 * Chorplan), erfüllte BEIDE Bedingungen und zeigte zwei „Drucken“-Knöpfe
 * untereinander; beide rufen `window.print()` mit denselben Druckregeln auf.
 *
 * SOLL: genau EIN Druck-Einstieg je Plan. Umgesetzt mit EINEM Ausdruck
 * `zeigtDruckleiste = druckKnopf || druckModus`; der Hinweistext der einen
 * Leiste nennt bei Druckansichten zusätzlich Papierformat und den
 * Drucker-Papier-Hinweis (keine Information geht verloren).
 *
 * Geprüft wird beides:
 *   A) an der QUELLE (läuft überall, ohne node_modules), und
 *   B) am GERENDERTEN DOM (mounten von PrAnsicht mit @vue/compiler-sfc +
 *      jsdom — läuft im Frontend-Stage des Image-Builds, wo `vue` und `jsdom`
 *      installiert sind). Ist `vue` lokal nicht da, wird Teil B wie in den
 *      bestehenden Mount-Tests (dev-b1-mount.test.mjs) sauber übersprungen.
 *
 * Läuft in der Node-Testliste: `tests/mt6-*.test.mjs` (frontend/tests/testliste.txt).
 */
import assert from 'node:assert/strict'
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath, pathToFileURL } from 'node:url'

const HIER = path.dirname(fileURLToPath(import.meta.url))
const FRONTEND = path.resolve(HIER, '..')
const SRV = path.join(FRONTEND, 'src')
const QUELLE = path.join(SRV, 'diakonos/components/planrahmen/PrAnsicht.vue')
const PLANVUE = path.join(SRV, 'diakonos/pages/planrahmen/Plan.vue')
const QUELLTEXT = readFileSync(QUELLE, 'utf8')

// ── A) Quelle: genau EIN Druck-Einstieg ────────────────────────────────────

test('MT-6 A1: PrAnsicht hat genau eine Druckleiste mit v-if', () => {
  // Jedes <div v-if=…> im Vorlagenteil, dessen Tag einen Druck-Bezug hat.
  const vorlage = QUELLTEXT.slice(0, QUELLTEXT.indexOf('</template>'))
  const leisten = [...vorlage.matchAll(/<div\b[^>]*\bv-if=/g)]
    .map((m) => vorlage.slice(m.index, vorlage.indexOf('>', m.index)))
    .filter((tag) => /druck/i.test(tag))
  assert.equal(leisten.length, 1,
    `PrAnsicht.vue: ${leisten.length} Druckleisten statt 1 (MT-6)`)
  assert.match(leisten[0], /v-if="zeigtDruckleiste"/,
    'PrAnsicht.vue: die eine Druckleiste hängt nicht an `zeigtDruckleiste`')
  assert.match(leisten[0], /class="pr-druck-leiste"/,
    'PrAnsicht.vue: die eine Druckleiste trägt nicht die Klasse .pr-druck-leiste')
})

test('MT-6 A2: genau ein Drucken-Knopf, genau ein window.print()', () => {
  assert.equal((QUELLTEXT.match(/data-test="pr-drucken"/g) || []).length, 1,
    'PrAnsicht.vue: mehr als ein Knopf [data-test=pr-drucken] (MT-6)')
  assert.equal((QUELLTEXT.match(/>Drucken</g) || []).length, 1,
    'PrAnsicht.vue: mehr als eine Knopfbeschriftung „Drucken“ (MT-6)')
  // Nur CODE zaehlen: die Kommentare im Kopf der Datei nennen window.print()
  // absichtlich mehrfach (Begruendung der Druckregeln).
  const code = QUELLTEXT
    .replace(/<!--[\s\S]*?-->/g, '')          // HTML-Kommentare
    .replace(/\/\*[\s\S]*?\*\//g, '')         // Blockkommentare
    .replace(/^\s*\/\/.*$/gm, '')             // Zeilenkommentare
  assert.equal((code.match(/window\.print\(\)/g) || []).length, 1,
    'PrAnsicht.vue: mehr als ein window.print() im Code (MT-6)')
})

test('MT-6 A3: die zweite Druckleiste ist ersatzlos entfernt', () => {
  assert.ok(!QUELLTEXT.includes('pr-ansicht-druckleiste'),
    'PrAnsicht.vue: .pr-ansicht-druckleiste (zweite Leiste) ist wieder da (MT-6)')
})

test('MT-6 A4: zeigtDruckleiste deckt beide Fälle ab', () => {
  assert.match(QUELLTEXT,
    /const zeigtDruckleiste = computed\(\(\) => props\.druckKnopf \|\| druckModus\.value\)/,
    'PrAnsicht.vue: zeigtDruckleiste muss `druckKnopf || druckModus` sein — sonst fehlt der Knopf bei einer Ansicht ohne druckKnopf')
})

test('MT-6 A5: der Hinweis der einen Leiste bleibt vollständig', () => {
  // Ohne Druckansicht: der UXP-R7-Satz. Mit Druckansicht: Papierformat +
  // Drucker-Hinweis („Hintergrundgrafiken“) — sonst ginge Information verloren.
  assert.match(QUELLTEXT, /Drucken zeigt nur den Plan — Seitenleiste, Knöpfe und Hinweise bleiben weg\./,
    'PrAnsicht.vue: der allgemeine Druckhinweis fehlt')
  assert.match(QUELLTEXT, /A4 quer' : 'A4 hoch'/,
    'PrAnsicht.vue: das Papierformat erscheint nicht mehr im Hinweis')
  assert.match(QUELLTEXT, /Hintergrundgrafiken/,
    'PrAnsicht.vue: der Drucker-Hinweis („Hintergrundgrafiken“) fehlt')
})

test('MT-6 A6: Plan.vue reicht den Knopf weiter, Vorschau bleibt ohne', () => {
  const plan = readFileSync(PLANVUE, 'utf8')
  assert.match(plan, /<PrAnsicht[\s\S]*?druck-knopf[\s\S]*?\/>/,
    'Plan.vue: der Drucken-Knopf wird nicht mehr durchgereicht')
  // Probelauf (Vorschau vor der Übernahme) setzt druck-knopf NICHT — dort soll
  // kein Druck-Einstieg erscheinen (Entwurf, kein Plan).
  const probelauf = readFileSync(
    path.join(SRV, 'diakonos/components/planrahmen/Probelauf.vue'), 'utf8')
  assert.ok(!/druck-knopf/.test(probelauf),
    'Probelauf.vue: die Vorschau soll keinen Druck-Einstieg bekommen (MT-6)')
})

// ── B) Gerendertes DOM: ein Druck-Einstieg je Situation ────────────────────

/**
 * Baut aus einer .vue-Quelle ein ES-Modul im Temp-Baum (wie dev-b1-mount).
 * `inlineTemplate` hängt den Renderer ans Skript; relative Importe werden
 * mitübersetzt. Der Baum liegt EINEN Ordner tief unter `frontend/`, damit Node
 * `frontend/node_modules` (vue, jsdom) findet.
 */
function baumBauen(ausgabe, geschrieben = new Set()) {
  function ziel(abs) {
    const rel = path.relative(SRV, abs).replace(/\.(vue|js|mjs)$/, '.mjs')
    const datei = path.join(ausgabe, 'src', rel)
    mkdirSync(path.dirname(datei), { recursive: true })
    return datei
  }
  function umschreiben(abs, pfad) {
    if (!/\.(vue|js|mjs)$/.test(pfad)) return null
    const zielAbs = path.resolve(path.dirname(abs), pfad)
    if (pfad.endsWith('.vue')) {
      bauteil(zielAbs)
      return pfad.replace(/\.vue$/, '.mjs')
    }
    modul(zielAbs)
    return pfad.replace(/\.(js|mjs)$/, '.mjs')
  }
  function bauteil(abs) {
    if (geschrieben.has(abs)) return
    geschrieben.add(abs)
    const datei = ziel(abs)
    writeFileSync(datei, 'export default {}\n', 'utf8')
    const { compileScript, parse } = vueSfc
    const { descriptor } = parse(readFileSync(abs, 'utf8'), { filename: abs })
    const id = path.basename(abs, '.vue').replace(/\W/g, '_')
    const skript = compileScript(descriptor, { id, inlineTemplate: true })
    const code = skript.content.replace(/from\s+'((?:\.\.?\/)[^']+)'/g, (ganz, pfad) => {
      const neu = umschreiben(abs, pfad)
      return neu ? ganz.replace(pfad, neu) : ganz
    })
    writeFileSync(datei, code, 'utf8')
  }
  function modul(abs) {
    if (geschrieben.has(abs)) return
    geschrieben.add(abs)
    const code = readFileSync(abs, 'utf8')
      .replace(/from\s+'((?:\.\.?\/)[^']+)'/g, (ganz, pfad) => {
        const neu = umschreiben(abs, pfad)
        return neu ? ganz.replace(pfad, neu) : ganz
      })
    writeFileSync(ziel(abs), code, 'utf8')
  }
  return { bauteil }
}

let vueSfc = null
let jsdomKlasse = null
let vueModul = null

/**
 * Werkzeuge laden. WICHTIG: `vue` (genauer `@vue/runtime-dom`) greift `document`
 * beim MODUL-Laden ab — jsdom muss also VOR dem ersten `import('vue')`
 * stehen, sonst rendert Vue spaeter gegen ein `null`-Dokument. Deshalb:
 * jsdom + DOM-Globals zuerst, `vue` erst danach dynamisch.
 */
async function werkzeug() {
  try {
    if (!jsdomKlasse) {
      vueSfc = await import('vue/compiler-sfc')
      const { JSDOM } = await import('jsdom')
      jsdomKlasse = JSDOM
      dokumentGlobals(new JSDOM('<!doctype html><html><head></head><body></body></html>', {
        url: 'http://localhost/diakronos/', pretendToBeVisual: true,
      }).window)
      vueModul = await import('vue')
    }
    return { JSDOM: jsdomKlasse, vue: vueModul }
  } catch {
    return null
  }
}

/** jsdom-Fenster als globale Laufzeit setzen (wie dev-b1-mount.test.mjs). */
function dokumentGlobals(window) {
  for (const [name, wert] of Object.entries({
    window, document: window.document, localStorage: window.localStorage,
    HTMLElement: window.HTMLElement, SVGElement: window.SVGElement,
    Element: window.Element, Node: window.Node,
    getComputedStyle: window.getComputedStyle.bind(window),
    requestAnimationFrame: (fn) => setTimeout(() => fn(Date.now()), 0),
    cancelAnimationFrame: (id) => clearTimeout(id),
  })) globalThis[name] = wert
}

/**
 * Rendert PrAnsicht mit gegebenen Props in ein frisches jsdom-Dokument.
 * Rückgabe: das Dokument (für querySelectorAll auf [data-test=pr-drucken]).
 */
async function rendern(props, w) {
  const { vue } = w
  // Ein frisches jsdom je Render wuerde `@vue/runtime-dom` NICHT mitbekommen
  // (es hat `document` beim Laden gebunden). Deshalb: Dokument aus `werkzeug()`
  // behalten und je Lauf einen leeren Container haengen.
  const window = globalThis.window

  // window.print() zaehlen (jsdom kennt es nicht) — es darf genau einmal
  // erreichbar sein, naemlich ueber den einen Knopf.
  let drucke = 0
  window.print = () => { drucke += 1 }

  const ausgabe = mkdtempSync(path.join(FRONTEND, '.kanban-mt6-'))
  try {
    const baum = baumBauen(ausgabe)
    baum.bauteil(QUELLE)
    const modul = await import(pathToFileURL(
      path.join(ausgabe, 'src', path.relative(SRV, QUELLE).replace(/\.vue$/, '.mjs'))
    ).href)
    const bauteil = modul.default

    const wurzel = window.document.createElement('div')
    window.document.body.appendChild(wurzel)
    const app = vue.createApp(bauteil, props)
    app.config.globalProperties.$dk = {}
    app.mount(wurzel)
    await vue.nextTick()
    // `wurzel` ist die Wurzel DIESES Renders — Abfragen laufen darauf, damit
    // Mounts vorheriger Tests das Ergebnis nicht verfaelschen.
    return { window, app, wurzel, drucke: () => drucke }
  } finally {
    // Der Temp-Baum wird NICHT hier entfernt (Module sind geladen); er wird
    // beim Prozessende weggeraeumt.
    setTimeout(() => { try { rmSync(ausgabe, { recursive: true, force: true }) } catch {} }, 0)
  }
}

const PLAN_GEDRUCKT = { art: 'druck', name: 'Druck', druck: 'A4-quer', spalten: ['anlass'] }
const PLAN_TABELLE = { art: 'tabelle', name: 'Tabelle' }

test('MT-6 B1: Plan MIT Druckansicht zeigt genau einen Drucken-Knopf', async (t) => {
  const w = await werkzeug()
  if (!w) { t.skip('vue/jsdom lokal nicht installiert — DOM-Abnahme laeuft im Image-Build'); return }
  const { wurzel } = await rendern({ ansicht: PLAN_GEDRUCKT, druckKnopf: true }, w)
  const knoepfe = wurzel.querySelectorAll('[data-test="pr-drucken"]')
  assert.equal(knoepfe.length, 1,
    'gerendertes DOM: bei einer Druckansicht erscheinen zwei Druck-Knöpfe (Befund MT-6)')
  const leisten = wurzel.querySelectorAll('.pr-druck-leiste')
  assert.equal(leisten.length, 1, 'gerendertes DOM: mehr als eine Druckleiste (MT-6)')
  assert.equal(wurzel.querySelectorAll('.pr-ansicht-druckleiste').length, 0,
    'gerendertes DOM: die zweite Leiste .pr-ansicht-druckleiste existiert noch')
})

test('MT-6 B2: Plan OHNE Druckansicht behält genau einen Drucken-Knopf', async (t) => {
  const w = await werkzeug()
  if (!w) { t.skip('vue/jsdom lokal nicht installiert — DOM-Abnahme laeuft im Image-Build'); return }
  const { wurzel } = await rendern({ ansicht: PLAN_TABELLE, druckKnopf: true }, w)
  assert.equal(wurzel.querySelectorAll('[data-test="pr-drucken"]').length, 1,
    'gerendertes DOM: die Tabellenansicht hat nicht genau einen Druck-Einstieg')
})

test('MT-6 B3: ohne druckKnopf, aber mit Druckansicht — trotzdem druckbar', async (t) => {
  const w = await werkzeug()
  if (!w) { t.skip('vue/jsdom lokal nicht installiert — DOM-Abnahme laeuft im Image-Build'); return }
  const { wurzel } = await rendern({ ansicht: PLAN_GEDRUCKT, druckKnopf: false }, w)
  assert.equal(wurzel.querySelectorAll('[data-test="pr-drucken"]').length, 1,
    'gerendertes DOM: eine Druckansicht ohne druckKnopf hat keinen Druck-Einstieg')
})

test('MT-6 B4: der eine Knopf ruft window.print() auf', async (t) => {
  const w = await werkzeug()
  if (!w) { t.skip('vue/jsdom lokal nicht installiert — DOM-Abnahme laeuft im Image-Build'); return }
  const { window, wurzel, drucke } = await rendern({ ansicht: PLAN_GEDRUCKT, druckKnopf: true }, w)
  const knopf = wurzel.querySelector('[data-test="pr-drucken"]')
  assert.ok(knopf, 'gerendertes DOM: kein Drucken-Knopf gefunden')
  knopf.dispatchEvent(new window.MouseEvent('click', { bubbles: true }))
  await new Promise((r) => setTimeout(r, 10))
  assert.equal(drucke(), 1, 'gerendertes DOM: der Drucken-Knopf loest window.print() nicht aus')
})

test('MT-6 B5: der Hinweis nennt bei Druckansicht das Papierformat', async (t) => {
  const w = await werkzeug()
  if (!w) { t.skip('vue/jsdom lokal nicht installiert — DOM-Abnahme laeuft im Image-Build'); return }
  const { wurzel } = await rendern({ ansicht: PLAN_GEDRUCKT, druckKnopf: true }, w)
  const text = wurzel.querySelector('.pr-druck-leiste').textContent
  assert.match(text, /A4 quer/, 'gerendertes DOM: Papierformat fehlt im Hinweis der einen Leiste')
  assert.match(text, /Hintergrundgrafiken/, 'gerendertes DOM: Drucker-Hinweis fehlt')

  const zweite = await rendern({ ansicht: PLAN_TABELLE, druckKnopf: true }, w)
  const text2 = zweite.wurzel.querySelector('.pr-druck-leiste').textContent
  assert.match(text2, /Drucken zeigt nur den Plan/,
    'gerendertes DOM: allgemeiner Druckhinweis fehlt bei einer Tabellenansicht')
})

console.log('MT-6: genau EIN Druck-Einstieg je Plan (Quelle + gerendertes DOM)')
