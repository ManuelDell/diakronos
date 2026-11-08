/**
 * BS-2d2 — Mount-Test: „Seite öffnen → Liste + Knopf sichtbar“.
 *
 * Kartenpunkt 1 verlangt, dass der Bereich „Bausteine“ seinen Stand beim
 * ÖFFNEN lädt (`onMounted(laden)`) — nicht erst nach einem Klick. Ein
 * `assert.match(onMounted(laden))` belegt nur, dass die Zeile dasteht.
 *
 * Deshalb läuft dieser Test gegen das ECHTE Bauteil: `BausteineBereich.vue`
 * wird (mit seinen Importen) über `vue/compiler-sfc` kompiliert, in ein
 * Temp-Verzeichnis geschrieben und dort als normale ES-Module geladen — Node
 * löst die relativen Pfade auf, `vue`/`jsdom` kommen aus `node_modules`.
 * Gerendert wird mit `@vue/runtime-dom` in jsdom; `fetch` ist eine Attrappe,
 * die die Antwort von `bausteine_status` liefert (Form BS-2a/BS-2d1).
 *
 * Geprüft wird am gerenderten DOM, OHNE einen Klick:
 *   1. Liste + Knopf sichtbar; Namen und Beschreibungen aus `mitgeliefert[]`.
 *   2. Freigaben aus `mitgeliefert[]` (deutsch), fehlende Angabe → „unbekannt“.
 *   3. Stand je Zeile: mitgeliefert / installiert / ältere Fassung.
 *   4. Einspiel-Knopf sichtbar und secondary, KEIN Primärknopf.
 *   5. Neulade-Knopf „Bausteine neu laden“ mit aria-label — kein zweites
 *      „Stand neu laden“.
 *   6. Ein fehlgeschlagener Abruf ergibt einen lesbaren Satz, keinen leeren
 *      Bereich und keinen Absturz.
 *
 * Läuft im Docker-Build (`node --test`); liest `frontend/**` (Regel 13).
 */
import assert from 'node:assert/strict'
import { mkdirSync, mkdtempSync, readFileSync, rmSync, symlinkSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath, pathToFileURL } from 'node:url'

import { compileScript, compileTemplate, parse } from 'vue/compiler-sfc'

const HIER = path.dirname(fileURLToPath(import.meta.url))
const FRONTEND = path.resolve(HIER, '..')
const SRV = path.join(FRONTEND, 'src')
const BAUTEIL = path.join(SRV, 'diakonos/components/website/BausteineBereich.vue')

// ── jsdom als Dokument ─────────────────────────────────────────────────────

function dokumentBauen() {
  // Erst nach dem Laden verfügbar (jsdom ist Entwicklungsabhängigkeit); als
  // dynamischer Import, damit ein fehlendes Paket den Test NICHT stumm macht.
  return import('jsdom').then(({ JSDOM }) => {
    const dom = new JSDOM('<!doctype html><html><body></body></html>', {
      url: 'http://localhost/diakronos/',
      pretendToBeVisual: true,
    })
    const { window } = dom
    globalThis.window = window
    globalThis.document = window.document
    // `navigator` ist in Node global und nur lesbar — vue-dom liest es nur.
    globalThis.localStorage = window.localStorage
    globalThis.HTMLElement = window.HTMLElement
    globalThis.SVGElement = window.SVGElement
    globalThis.Element = window.Element
    globalThis.Node = window.Node
    globalThis.getComputedStyle = window.getComputedStyle.bind(window)
    window.__DIakonosBOOT = { basePath: '/diakronos', csrf_token: 'test-token' }
    return window
  })
}

// ── SFC-Bauteile zu echten ES-Modulen (Temp-Verzeichnis) ───────────────────

/**
 * Schreibt ein .vue-Bauteil als `.mjs` neben seinen Quellbaum: Die Importe
 * bleiben relativ, wie sie im Original stehen — nur ihre Endung bekommt
 * `.mjs`, damit Node sie als Modul lädt. Das Ergebnis liegt in `ziel`.
 */
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
    // `inlineTemplate` erwartet ein `<script setup>`; bei reinem `<script>`-
    // Bauteil wird die Vorlage hier selbst angehängt. Aufräumen: die Vue-
    // Importe der Vorlage und des Skripts werden zu EINER Zeile zusammengelegt
    // (doppelte Import-Zeilen sind ein Syntaxfehler).
    const tpl = compileTemplate({
      id,
      filename: abs,
      source: descriptor.template.content,
      compilerOptions: { bindingMetadata: skript.bindings, mode: 'module' },
    })
    assert.equal(tpl.errors.length, 0, `${id}: Vorlage nicht kompilierbar: ${tpl.errors.join(', ')}`)
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

  // Relative Importe: Endung anpassen (.js/.mjs → .mjs, .vue → .mjs) und
  // rekursiv mitschreiben; `./x` ohne Endung wie im Original belassen.
  code = code.replace(/from\s+'(\.\.?\/[^']+)'/g, (ganz, pfad) => {
    const zielAbs = path.resolve(path.dirname(abs), pfad)
    if (pfad.endsWith('.vue') || pfad.endsWith('.js') || pfad.endsWith('.mjs')) {
      const neuPfad = pfad.replace(/\.(vue|js|mjs)$/, '.mjs')
      const neuAbs = zielAbs.replace(/\.(vue|js|mjs)$/, '.mjs')
      if (zielAbs.endsWith('.vue')) {
        bauteilSchreiben(zielAbs, ausgabe, wache)
      } else {
        // Ein JS-Modul: unverändert kopieren (seine eigenen .vue-Importe
        // werden mitgezogen).
        modulSchreiben(zielAbs, ausgabe, wache)
      }
      return ganz.replace(pfad, neuPfad)
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
  code = code.replace(/from\s+'(\.\.?\/[^']+)'/g, (ganz, pfad) => {
    const zielAbs = path.resolve(path.dirname(abs), pfad)
    if (pfad.endsWith('.vue')) {
      bauteilSchreiben(zielAbs, ausgabe, wache)
      return ganz.replace(pfad, pfad.replace(/\.vue$/, '.mjs'))
    }
    if (pfad.endsWith('.js') || pfad.endsWith('.mjs')) {
      modulSchreiben(zielAbs, ausgabe, wache)
      return ganz.replace(pfad, pfad.replace(/\.(js|mjs)$/, '.mjs'))
    }
    return ganz
  })
  const zielDatei = path.join(ausgabe, path.relative(SRV, abs).replace(/\.(js|mjs)$/, '.mjs'))
  mkdirSync(path.dirname(zielDatei), { recursive: true })
  writeFileSync(zielDatei, code, 'utf8')
}

/** Antwort von `bausteine_status` (BS-2a + BS-2d1). */
function statusAntwort() {
  return {
    message: {
      erreichbar: true,
      mitgeliefert_version: 10,
      installiert_version: 9,
      veraltet: true,
      revision: 'v10:abc',
      hinweis: '',
      bausteine: [
        { kennung: 'kontakt', name: 'diakronos/kontakt@v9', version: 9 },
        { kennung: 'gruppen', name: 'diakronos/gruppen@v9', version: 9 },
        { kennung: 'handgemacht', name: 'diakronos/handgemacht@v1', version: 1 },
      ],
      mitgeliefert: [
        {
          kennung: 'kontakt',
          name: 'Diakronos: Kontaktformular',
          beschreibung: 'Kontaktformular, das die Nachricht über Diakronos sendet.',
          freigaben: ['kontaktpostfaecher'],
        },
        {
          kennung: 'gruppen',
          name: 'Diakronos: Gruppen-Übersicht',
          beschreibung: 'Zeigt die freigegebenen Gruppen als Kacheln.',
          freigaben: ['gruppen', 'termine'],
        },
        {
          kennung: 'ohne-angabe',
          name: 'Diakronos: Ohne Freigabe-Angabe',
          beschreibung: 'Ein Baustein, zu dem der Server nichts über Freigaben sagt.',
        },
        {
          kennung: 'ohne-freigaben',
          name: 'Diakronos: Nur Termine und Links',
          beschreibung: 'Ausdrücklich ohne Freigabe-Daten.',
          freigaben: [],
        },
      ],
    },
  }
}

/** Ein Rendering des Bauteils mit Attrappen-fetch. */
async function rendern(antwort, { status = 200 } = {}) {
  const window = await dokumentBauen()
  const aufrufe = []
  window.fetch = globalThis.fetch = async (url) => {
    aufrufe.push(String(url))
    const text = typeof antwort === 'string' ? antwort : JSON.stringify(antwort)
    return {
      ok: status >= 200 && status < 300,
      status,
      text: async () => text,
      json: async () => JSON.parse(text),
    }
  }

  const ausgabe = mkdtempSync(path.join(tmpdir(), 'bs2d2-'))
  bauteilSchreiben(BAUTEIL, ausgabe)
  // Die kompilierten Module importieren `vue` als Paketnamen. Node sucht es
  // abwärts von der Datei — deshalb zeigt ein `node_modules` im Temp-Baum auf
  // die echten Pakete des Frontends (ein Symlink, keine Kopie).
  const modules = path.join(ausgabe, 'node_modules')
  mkdirSync(path.dirname(modules), { recursive: true })
  symlinkSync(path.join(FRONTEND, 'node_modules'), modules, 'dir')
  try {
    const { createApp, nextTick } = await import('vue')
    const modul = await import(pathToFileURL(
      path.join(ausgabe, path.relative(SRV, BAUTEIL).replace(/\.vue$/, '.mjs')),
    ).href)
    const bauteil = modul.default
    assert.ok(bauteil, 'Bauteil nicht geladen')

    const ziel = window.document.createElement('div')
    window.document.body.appendChild(ziel)
    const app = createApp(bauteil)
    app.config.warnHandler = () => {}
    app.mount(ziel)
    // Laden läuft asynchron (fetch-Attrappe → mikro-/makrotask).
    await new Promise((r) => setTimeout(r, 0))
    await nextTick()
    await new Promise((r) => setTimeout(r, 0))
    await nextTick()
    return { window, ziel: app._container, aufrufe, app }
  } finally {
    rmSync(ausgabe, { recursive: true, force: true })
  }
}

/** Textinhalt des gerenderten Bauteils (ohne Skripte). */
function text(el) {
  return (el?.textContent || '').replace(/\s+/g, ' ').trim()
}

// ── 1. Seite öffnen → Liste + Knopf sichtbar (ohne Klick) ──────────────────

test('BS-2d2: beim Öffnen steht die Liste da (onMounted, ohne Klick)', async () => {
  const { ziel, aufrufe, app } = await rendern(statusAntwort())
  const inhalt = text(ziel)

  // Der Abruf ist beim MOUNTEN passiert — niemand hat geklickt.
  assert.ok(aufrufe.length >= 1, 'kein Abruf beim Öffnen')
  assert.match(aufrufe[0], /website\.bausteine_status/, `Abruf auf falschem Weg: ${aufrufe[0]}`)
  assert.match(aufrufe[0], /^\/diakronos\/api\/method\//, 'Abruf ohne Betriebs-Präfix')

  // Liste: alle MITGELIEFERTEN Bausteine samt Beschreibung, dazu der eine
  // Baustein, der nur im Werkzeug liegt.
  assert.match(inhalt, /Diakronos: Kontaktformular/)
  assert.match(inhalt, /Kontaktformular, das die Nachricht über Diakronos sendet\./)
  assert.match(inhalt, /Diakronos: Gruppen-Übersicht/)
  assert.match(inhalt, /Diakronos: Ohne Freigabe-Angabe/)
  assert.match(inhalt, /Diakronos: Nur Termine und Links/)
  assert.match(inhalt, /handgemacht/, 'Baustein, der nur im Werkzeug liegt, fehlt')

  // Knopf sichtbar (Stand im Werkzeug ist zurück).
  const knoepfe = [...ziel.querySelectorAll('button')].map((b) => text(b))
  assert.ok(knoepfe.some((k) => /aktualisieren/i.test(k)), `Einspiel-Knopf fehlt: ${knoepfe.join(' | ')}`)
  assert.ok(knoepfe.some((k) => /Bausteine neu laden/.test(k)), `Neulade-Knopf fehlt: ${knoepfe.join(' | ')}`)
  assert.match(inhalt, /Aktualisierung verfügbar/)

  app.unmount()
})

// ── 2. Freigaben aus der Serverantwort ─────────────────────────────────────

test('BS-2d2: die Freigaben stehen aus der Serverantwort am Baustein', async () => {
  const { ziel, app } = await rendern(statusAntwort())
  const inhalt = text(ziel)
  assert.match(inhalt, /Nutzt die Freigaben: Kontakt-Postfächer/)
  assert.match(inhalt, /Nutzt die Freigaben: Gruppen, Termine/)
  // Ausdrücklich leere Liste → „braucht keine“.
  assert.match(inhalt, /Braucht keine Freigabe aus Diakronos\./)
  // Fehlende Angabe → „unbekannt“, NICHT „braucht keine“.
  assert.match(inhalt, /Freigaben: unbekannt/)
  app.unmount()
})

// ── 3. Stand je Zeile ──────────────────────────────────────────────────────

test('BS-2d2: der Stand je Zeile trennt installiert, ältere Fassung und mitgeliefert', async () => {
  const { ziel, app } = await rendern(statusAntwort())
  const inhalt = text(ziel)
  // kontakt v9 im Werkzeug, mitgeliefert ist v10 → „ältere Fassung (9)“;
  // handgemacht v1 liegt dort und ist ebenfalls hinter der Fassung.
  assert.match(inhalt, /ältere Fassung \(9\)/, 'Fassung im Werkzeug nicht benannt')
  assert.match(inhalt, /ältere Fassung \(1\)/, 'Rückstand im Werkzeug nicht benannt')
  // Zwei mitgelieferte Bausteine liegen noch NICHT im Werkzeug.
  assert.equal((inhalt.match(/\bmitgeliefert\b/g) || []).length >= 2, true, '„mitgeliefert“ fehlt an den neuen Zeilen')
  app.unmount()
})

// ── 4. Der eine Primärknopf bleibt „Website-Baukasten öffnen“ ──────────────

test('BS-2d2: kein Primärknopf im Bereich — Einspielen ist secondary', async () => {
  const { ziel, app } = await rendern(statusAntwort())
  const primaer = [...ziel.querySelectorAll('button')].filter(
    (b) => /dk-ui-btn--primary/.test(b.className) && !/bausteine/i.test(b.getAttribute('aria-label') || ''),
  )
  assert.equal(primaer.length, 0, `Primärknopf im Bereich: ${primaer.map((b) => text(b)).join(', ')}`)
  const einspielen = [...ziel.querySelectorAll('button')].find((b) => /aktualisieren/i.test(text(b)))
  assert.ok(einspielen, 'Einspiel-Knopf fehlt')
  assert.match(einspielen.className, /dk-ui-btn--secondary/, 'Einspiel-Knopf ist nicht secondary')
  assert.equal(
    einspielen.getAttribute('aria-label'),
    'Mitgelieferte Bausteine in den Website-Baukasten einspielen',
  )
  app.unmount()
})

// ── 5. Kein zweites „Stand neu laden“ ──────────────────────────────────────

test('BS-2d2: der Neulade-Knopf heißt „Bausteine neu laden“ und ist eindeutig benannt', async () => {
  const { ziel, app } = await rendern(statusAntwort())
  const inhalt = text(ziel)
  assert.doesNotMatch(inhalt, /Stand neu laden/, 'zweites „Stand neu laden“ im Bereich')
  const knopf = [...ziel.querySelectorAll('button')].find((b) => /Bausteine neu laden/.test(text(b)))
  assert.ok(knopf, 'Neulade-Knopf fehlt')
  assert.equal(knopf.getAttribute('aria-label'), 'Bausteine neu laden')
  app.unmount()
})

// ── 6. Fehlerfall: lesbarer Satz statt leerer Bereich ──────────────────────

test('BS-2d2: ein fehlgeschlagener Abruf ergibt einen lesbaren Satz', async () => {
  const { ziel, app } = await rendern({
    message: 'Der Stand der Bausteine konnte nicht geladen werden.',
  }, { status: 500 })
  const inhalt = text(ziel)
  assert.match(inhalt, /konnte nicht geladen werden|nicht abrufbar/i, `kein lesbarer Fehlertext: ${inhalt.slice(0, 200)}`)
  // Kein Absturz: der Bereich steht (Karte + Kopf), nicht ein leeres Blatt.
  assert.ok(ziel.querySelector('.wb-kopf'), 'Bereich nicht gerendert')
  app.unmount()
})
