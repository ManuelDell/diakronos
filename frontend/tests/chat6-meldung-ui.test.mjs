/**
 * CHAT-6-UI — „Melden“ und der Reiter „Chat“ in „Zu prüfen“ (Vue 3, Frontend).
 *
 * Geprüft wird VERHALTEN (gemountet, mit Netzatttrappe), nicht nur Klassen:
 *
 *   A  Die Regeln (`components/chat/meldung.mjs`, ohne DOM): fünf Gründe in
 *      der Reihenfolge des Konzepts, 500-Zeichen-Grenze, „melden“ nur an
 *      FREMDEN, nicht gelöschten Nachrichten, Auslegung der Server-Antworten
 *      (Bestätigung, doppelte Meldung, Entscheidungen), 1:1-Titel neutral.
 *   B  ChatBlase.vue gemountet: der Melden-Knopf steht am Desktop NUR an
 *      fremden Nachrichten (DkButton, aria-label), am Handy steht „Melden“ im
 *      „⋯“-Menü (DkAktionen) — und nie an eigenen/gelöschten.
 *   C  ChatMeldungDialog.vue gemountet: Hinweis VOR dem Absenden immer
 *      sichtbar, Grundauswahl, Freitext mit Zähler und 500er-Grenze, POST
 *      über den Elternteil mit grund/freitext, Bestätigung, Servertext bei
 *      doppelter Meldung.
 *   D  Seite Nachrichten.vue: Melden → `chat.meldung_senden` mit den richtigen
 *      Feldern; die Antwort zeigt „Danke, die Meldung ist eingegangen.“
 *   E  Reiter „Chat“: fehlt bei 403, Liste + Ausschnitt (fünf davor) aus
 *      DERSELBEN Antwort, Entscheidung als POST, 1:1 neutral betitelt, keine
 *      Namen der meldenden Person, wenn der Server keine liefert.
 *   F  Glocke: „Neue Meldung im Chat“ ist ein Weg in den Reiter.
 *
 * Lauf (eine Datei je Aufruf, TZ=Europe/Berlin):
 *   TMPDIR=$(mktemp -d) TZ=Europe/Berlin node --test tests/chat6-meldung-ui.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync, mkdtempSync, writeFileSync, rmSync, mkdirSync, statSync } from 'node:fs'
import { join, dirname, resolve, basename } from 'node:path'
import { tmpdir } from 'node:os'
import { pathToFileURL } from 'node:url'
import test from 'node:test'
import { SeitenAbbau } from './helpers/seitenAbbau.mjs'
import { JSDOM } from 'jsdom'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'

// ── Browser-Attrappe ───────────────────────────────────────────────────────
const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
for (const schluessel of ['window', 'document', 'Node', 'Element', 'HTMLElement', 'Event',
  'MouseEvent', 'SVGElement', 'CSS', 'CustomEvent', 'FormData', 'HTMLInputElement',
  'HTMLSelectElement', 'HTMLTextAreaElement', 'requestAnimationFrame', 'getComputedStyle',
  'MutationObserver', 'KeyboardEvent', 'FocusEvent', 'Document', 'ShadowRoot',
  'HTMLAnchorElement', 'HTMLButtonElement', 'HTMLDivElement', 'localStorage',
  'sessionStorage', 'location', 'URLSearchParams', 'PopStateEvent', 'HashChangeEvent']) {
  globalThis[schluessel] = dom.window[schluessel]
}
globalThis.requestAnimationFrame = dom.window.requestAnimationFrame
  || ((fn) => setTimeout(() => fn(Date.now()), 0))
Object.defineProperty(dom.window.document, 'hidden', { configurable: true, get: () => false })
Object.defineProperty(dom.window.document, 'visibilityState', { configurable: true, get: () => 'visible' })

const VUE_URL = import.meta.resolve('vue')
const SRC_ROOT = new URL('../src/', import.meta.url)
const SRC = new URL('../src/diakonos/', import.meta.url)

const TMP = mkdtempSync(join(tmpdir(), 'chat6-'))
test.after(() => rmSync(TMP, { recursive: true, force: true }))

// ── Die Regeln direkt (kein DOM nötig) ─────────────────────────────────────
const M = await import(new URL('components/chat/meldung.mjs', SRC).href)
const ZIELE = await import(new URL('composables/glockenziele.mjs', SRC).href)
const logik = await import(new URL('composables/nachrichtenLogik.mjs', SRC).href)

// ── SFC → ES-Modul ─────────────────────────────────────────────────────────
const cache = new Map()
const umleitung = new Map()

const VUE_SCHIM = join(TMP, 'vue-schim.mjs')
writeFileSync(VUE_SCHIM, [
  `export * from '${VUE_URL}'`,
  'export function nextTick(fn) {',
  '  const p = globalThis.__NAECHSTER_TAKT()',
  '  return fn ? p.then(fn) : p',
  '}',
].join('\n'))

function aufgeloest(abs) {
  for (const k of [abs, abs + '.mjs', abs + '.js', abs + '/index.mjs']) {
    try { if (statSync(k).isFile()) return k } catch { /* weiter */ }
  }
  throw new Error('nicht gefunden: ' + abs)
}

function baum(seite, { frisch = false, ordner = null } = {}) {
  const unterordner = ordner || join(TMP, 'baum-' + Math.random().toString(36).slice(2))
  const NEU = frisch ? new Map() : cache
  const zielFuer = (quellDatei) => {
    // Pfad relativ zu `src/` (deckt `diakonos/` UND das danebenliegende
    // `shared/` ab); außerhalb von `src/` zählt der volle Pfad.
    const wurzel = resolve(SRC_ROOT.pathname)
    const voll = resolve(quellDatei)
    const relativ = voll.startsWith(wurzel) ? 'x' + voll.slice(wurzel.length) : voll
    const ziel = join(unterordner, relativ.replace(/[\\/]/g, '_') + '.mjs')
    mkdirSync(dirname(ziel), { recursive: true })
    return ziel
  }
  const uebersetzen = (abs) => {
    if (NEU.has(abs)) return NEU.get(abs)
    // `src/shared/**` liegt NEBEN `src/diakonos/` und wird von Seiten über
    // `../../shared/…` importiert — `aufgeloest` findet es, der Baumschlüssel
    // ist der Pfad selbst.
    const quellDatei = aufgeloest(abs)
    const quanten = []
    if (quellDatei.endsWith('.vue')) {
      const filename = basename(quellDatei)
      const { descriptor, errors } = parse(readFileSync(quellDatei, 'utf8'), { filename })
      assert.deepEqual(errors, [], filename + ': SFC-Struktur')
      const script = compileScript(descriptor, { id: filename })
      const tpl = compileTemplate({
        source: descriptor.template.content, filename, id: filename,
        compilerOptions: { bindingMetadata: script.bindings },
      })
      assert.deepEqual(tpl.errors.map(String), [], filename + ': Vorlage')
      let code = script.content.replace(/\nexport default /, '\nconst __sfc__ = ')
      code += '\n' + tpl.code.replace(/^export function render/m, 'function render')
      code += '\n__sfc__.render = render\nexport default __sfc__\n'
      code = code.replace(/defineAsyncComponent\(\(\) => import\([^)]*\)\)/g,
        'defineAsyncComponent(() => Promise.resolve({ render: () => null }))')
      quanten.push(code)
    } else {
      quanten.push(readFileSync(quellDatei, 'utf8'))
    }
    const code = quanten.join('\n').replace(
      /from\s+['"]([^'"]+)['"]/g,
      (ganz, spec) => {
        if (spec === 'vue') return `from '${quellDatei.endsWith('.vue') ? VUE_SCHIM : VUE_URL}'`
        if (spec.startsWith('.')) {
          // `../../shared/…`: aus `src/diakonos/components/…` zeigt das eine
          // Ebene ÜBER `src/diakonos/` — `src/shared/`. Aufgelöst wird der
          // Pfad also, aber NICHT über `resolve(dirname(…))` allein: der
          // Baumschlüssel muss danach wieder unter `src/` liegen.
          const zielAbs = aufgeloest(resolve(dirname(quellDatei), spec))
          const url = pathToFileURL(zielAbs).href
          if (umleitung.has(url)) return `from '${umleitung.get(url)}'`
          return `from '${pathToFileURL(uebersetzen(zielAbs)).href}'`
        }
        if (spec.startsWith('node:')) return ganz
        return `from '${spec}'`
      },
    )
    const ziel = zielFuer(quellDatei)
    writeFileSync(ziel, code)
    NEU.set(abs, ziel)
    return ziel
  }
  return uebersetzen(new URL(seite, SRC).pathname)
}

const umgehen = async (instanz, lauf) => {
  if (instanz?.subTree) lauf(instanz.subTree)
  for (let i = 0; i < 6; i += 1) { await tick() }
}

const tick = () => new Promise((loese) => setTimeout(loese, 0))
const warte = async (n = 8) => { for (let i = 0; i < n; i += 1) await tick() }

const tickWarteschlange = []
globalThis.__NAECHSTER_TAKT = () => new Promise((loese) => { tickWarteschlange.push(loese) })
async function rendern(n = 6) {
  for (let i = 0; i < n; i += 1) {
    const offen = tickWarteschlange.splice(0, tickWarteschlange.length)
    if (!offen.length) { await tick(); continue }
    for (const loese of offen) loese()
    await tick()
  }
}

/**
 * FE-ABBAU: JEDE Montage meldet ihren Abbau hier an, und `afterEach` baut
 * alles ab, was noch steht — auch nach einem ROTEN `assert`. Vorher stand
 * `s.abbaum()` als letzte Zeile im Test: eine geworfene Zusage ließ die Seite
 * stehen, ihr Takt (10 s, plant sich neu) hielt die Ereignisschleife offen und
 * der FE-Teststep im Build hing (FE-HAENGER, 4ce2d6b2).
 */
const seitenAbbau = new SeitenAbbau()
test.afterEach(() => seitenAbbau.alle())

/** Mounten mit einem Horcher für die Ereignisse der Komponente. */
async function mounten(baustein, props = {}, { horcher = null, propNamen = null, tief = false } = {}) {
  const Vue = await import('vue')
  const host = document.createElement('div')
  document.body.appendChild(host)
  const warnungen = []
  let seite = null
  const kennung = Math.random().toString(36).slice(2)
  globalThis.__HORCHER = globalThis.__HORCHER || {}
  globalThis.__HORCHER[kennung] = horcher
  const melde = (art, wert) => {
    const h = globalThis.__HORCHER[kennung]
    if (h) h(art, wert)
  }
  const namen = propNamen || ['melden', 'entschieden', 'reaktion', 'antworten', 'bearbeiten', 'loeschen']
  const Wrapper = {
    props: { p: { type: Object, default: () => ({}) } },
    setup(innerProps) {
      seite = Vue.getCurrentInstance()
      const eigene = Vue.ref({ ...innerProps.p })
      globalThis.__PROP_SETZEN = globalThis.__PROP_SETZEN || {}
      globalThis.__PROP_SETZEN[kennung] = (name, wert) => {
        eigene.value = { ...eigene.value, [name]: wert }
      }
      return () => Vue.h(baustein, {
        ...eigene.value,
        ...Object.fromEntries(namen.map((n) => [`on${n[0].toUpperCase()}${n.slice(1)}`, (x) => melde(n, x)])),
        'onUpdate:modelValue': (x) => melde('modelValue', x),
      })
    },
  }
  // `tief`: auch die INNEREN Bausteine (DkButton, DkDialog …) melden ihre
  // Ereignisse an denselben Horcher — die Teleport-Inhalte landen sonst in
  // `document.body`, nicht im Host des Bausteins.
  const patch = (instanz) => {
    if (tief) {
      for (const name of Object.keys(instanz.props || {})) {
        if (!name.startsWith('on')) continue
        const art = name.slice(2).toLowerCase()
        const alt = instanz.props[name]
        instanz.props[name] = (...args) => { melde(art, args[0]); if (typeof alt === 'function') alt(...args) }
      }
    }
    if (typeof instanz.subTree === 'object' && instanz.subTree) lauf(instanz.subTree)
  }
  const lauf = (vnode) => {
    if (!vnode || typeof vnode !== 'object') return
    if (vnode.component) patch(vnode.component)
    const kinder = vnode.children
    if (Array.isArray(kinder)) kinder.forEach(lauf)
    else if (kinder && typeof kinder === 'object') {
      if (Array.isArray(kinder.default)) kinder.default.forEach(lauf)
      else if (typeof kinder.default === 'function') {
        const alt = kinder.default
        kinder.default = (...a) => { const r = alt(...a); (Array.isArray(r) ? r : [r]).forEach(lauf); return r }
      }
    }
  }
  const app = Vue.createApp({ render: () => Vue.h(Wrapper, { p: props }) })
  app.config.warnHandler = (m) => warnungen.push(m)
  app.config.errorHandler = (e) => warnungen.push(String(e && e.message))
  app.mount(host)
  if (tief) await umgehen(app._instance, lauf)
  await warte(10)
  const abbaum = seitenAbbau.anmelden(() => {
    try { app.unmount() } catch { /* egal */ }
    try { host.remove() } catch { /* egal */ }
  })
  const propSetzen = (name, wert) => {
    const f = globalThis.__PROP_SETZEN?.[kennung]
    if (!f) return false
    f(name, wert)
    return true
  }
  const offen = () => {
    const kind = seite?.subTree?.component
    const instanz = kind && kind !== seite ? kind : null
    return instanz?.exposed || {}
  }
  return { host, app, warnungen, offen, propSetzen, abbaum }
}

function klick(el) {
  assert.ok(el, 'das Element steht im DOM')
  el.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true, cancelable: true }))
}

async function fuellen(el, wert) {
  el.value = wert
  el.dispatchEvent(new dom.window.Event('input', { bubbles: true }))
  await rendern()
}

const texte = (host, auswahl) => [...host.querySelectorAll(auswahl)].map((e) => e.textContent.trim())
const knopfMit = (host, muster) => [...host.querySelectorAll('button')]
  .find((b) => muster.test(b.textContent) || muster.test(String(b.getAttribute('aria-label') || '')))

function handyAbfrage(handy) {
  dom.window.matchMedia = (abfrage) => ({
    media: String(abfrage),
    matches: handy === true && /pointer:\s*coarse/.test(String(abfrage)),
    addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {},
  })
}

// ════════════════════════════════════════════════════════════════════════════
// A · Regeln ohne DOM
// ════════════════════════════════════════════════════════════════════════════

test('CHAT-6-UI/A: fünf Meldegründe in der Reihenfolge des Konzepts', () => {
  assert.deepEqual(M.GRUENDE.map((g) => g.schluessel),
    ['beleidigung', 'spam', 'persoenliche_daten', 'falsche_person', 'sonstiges'])
  assert.deepEqual(M.GRUENDE.map((g) => g.label),
    ['Beleidigung', 'Spam', 'Persönliche Daten', 'Falsche Person', 'Sonstiges'])
  assert.equal(M.grundLabel('spam'), 'Spam')
  assert.equal(M.grundLabel('quatsch'), '', 'unbekannte Schlüssel werden nicht erfunden')
  assert.equal(M.FREITEXT_MAX, 500, 'Freitext bis 500 Zeichen (Konzept 2.5)')
  // Der Hinweis ist der Satz, den der Operator festgelegt hat — wörtlich.
  assert.equal(M.TEXTE.hinweis, 'Wer Meldungen prüft, sieht diese Nachricht und die fünf davor.')
  assert.equal(M.TEXTE.danke, 'Danke, die Meldung ist eingegangen.')
  // Die Erklärung über der Grundauswahl ist neutral: Personenkreis statt
  // Zuständigkeit, „Moderation“ steht dort nicht (Glossar).
  assert.equal(M.AUSWAHL_HILFE,
    'Die Meldung sehen nur die Personen, die Meldungen prüfen. '
    + 'Wer gemeldet hat, erfährt die gemeldete Person nicht.')
  assert.doesNotMatch(M.AUSWAHL_HILFE, /Moderation/)
})

test('CHAT-6-UI/A: Bedienprüfung — Grund gewählt, 500-Zeichen-Grenze', () => {
  assert.equal(M.meldungPruefen({}).ok, false)
  assert.match(M.meldungPruefen({}).fehler, /Grund/)
  assert.deepEqual(M.meldungPruefen({ grund: 'spam' }),
    { ok: true, grund: 'spam', freitext: null })
  assert.deepEqual(M.meldungPruefen({ grund: 'spam', freitext: '  ' }),
    { ok: true, grund: 'spam', freitext: null }, 'Leerraum ist kein Text')
  assert.deepEqual(M.meldungPruefen({ grund: 'sonstiges', freitext: ' Kontext ' }),
    { ok: true, grund: 'sonstiges', freitext: 'Kontext' })
  // Genau 500 gehen, 501 nicht — gezählt werden ZEICHEN.
  assert.equal(M.meldungPruefen({ grund: 'spam', freitext: 'ä'.repeat(500) }).ok, true)
  const zuLang = M.meldungPruefen({ grund: 'spam', freitext: 'ä'.repeat(501) })
  assert.equal(zuLang.ok, false)
  assert.match(zuLang.fehler, /500/)
  assert.equal(M.zeichenZaehler('abc'), '3 / 500')
})

test('CHAT-6-UI/A: meldbar — nur fremde, nicht gelöschte Nachrichten', () => {
  assert.equal(M.meldbar({ ident: 'N-1', eigene: false }), true)
  assert.equal(M.meldbar({ ident: 'N-1', eigene: true }), false, 'die eigene Nachricht nicht')
  assert.equal(M.meldbar({ ident: 'N-1', geloescht: true }), false, 'eine gelöschte nicht')
  assert.equal(M.meldbar({ eigene: false }), false, 'ohne Kennung kein Meldeweg')
  assert.equal(M.meldbar(null), false)
  // Die gelieferte Zeile des Verlaufs trägt `ident`/`name`.
  const zeile = logik.verlaufsZeile({ name: 'N-9', text: 'Hallo' }, { ich: 'a@b' })
  assert.equal(M.meldbar(zeile), true)
})

test('CHAT-6-UI/A: Antworten des Servers — Bestätigung, doppelte Meldung, Entscheidungen', () => {
  const gut = M.sendeAntwort({ name: 'M-1', stand: 'offen', meldung_offen: true })
  assert.equal(gut.ok, true)
  assert.equal(gut.text, M.TEXTE.danke)
  assert.equal(M.sendeAntwort(null).ok, false, 'leere Antwort: nichts behaupten')

  // Die doppelte Meldung kommt als Fehler mit dem Satz des Servers.
  const doppelt = Object.assign(new Error('Diese Nachricht wurde von dir bereits gemeldet.'), { status: 400 })
  assert.equal(M.meldeFehlerText(doppelt, { ersatz: 'egal' }),
    'Diese Nachricht wurde von dir bereits gemeldet.', 'der Servertext steht ruhig da')

  // Entscheidungen: Schlüssel des Servers, Grund nur beim Entfernen Pflicht.
  assert.deepEqual(M.ENTSCHEIDUNGEN.map((e) => e.schluessel), ['entfernen', 'verwerfen'])
  assert.equal(M.entscheidungLabel('entfernen'), 'Nachricht entfernen')
  assert.equal(M.entscheidungLabel('verwerfen'), 'Meldung zurückweisen')
  assert.equal(M.grundPflicht('entfernen'), true)
  assert.equal(M.grundPflicht('verwerfen'), false)
  assert.equal(M.entscheidungPruefen({ entscheidung: 'entfernen' }).ok, false)
  assert.match(M.entscheidungPruefen({ entscheidung: 'entfernen' }).fehler, /Grund/)
  assert.deepEqual(M.entscheidungPruefen({ entscheidung: 'entfernen', grund: 'Beleidigung' }),
    { ok: true, entscheidung: 'entfernen', grund: 'Beleidigung' })
  assert.deepEqual(M.entscheidungPruefen({ entscheidung: 'verwerfen' }),
    { ok: true, entscheidung: 'verwerfen', grund: null })
  assert.equal(M.entscheidungPruefen({ entscheidung: 'loeschen' }).ok, false, 'kein dritter Weg')
})

test('CHAT-6-UI/A: Meldungen lesen — 1:1 neutral, Kontext aus DERSELBEN Antwort', () => {
  const daten = {
    offen: 1,
    meldungen: [{
      name: 'M-1',
      stand: 'offen',
      grund: 'beleidigung',
      freitext: 'Das geht nicht.',
      erstellt_am: '2026-11-18 09:00:00',
      // Der Server liefert im 1:1 den neutralen Titel.
      gespraech_titel: 'Direktnachricht',
      nachricht: { name: 'N-5', text: 'Du bist doof', autor: 'Anna A.', erstellt_am: '2026-11-18 08:59:00' },
      vorgeschichte: [{ name: 'N-4', autor: 'Bert B.', text: 'Hallo', geloescht: false, erstellt_am: '2026-11-18 08:58:00' }],
    }],
  }
  const [zeile] = M.meldungZeilen(daten)
  assert.equal(zeile.gespraechTitel, 'Direktnachricht')
  assert.equal(zeile.grundText, 'Beleidigung', 'Anzeigetext aus der Oberfläche')
  assert.equal(zeile.standText, 'offen')
  assert.equal(zeile.offen, true)
  assert.equal(zeile.nachrichtText, 'Du bist doof')
  assert.deepEqual(M.ausschnitt(zeile).davor.map((z) => z.name), ['N-4'])
  assert.equal(M.offenZahl(daten), 1)
  assert.equal(M.offenZahl({ meldungen: [] }), 0)
  // Ein Ausschnitt ohne `gespraech_titel` fällt auf den neutralen Titel zurück —
  // nie auf einen geratenen Personennamen.
  assert.equal(M.meldungZeilen({ meldungen: [{ name: 'M-2' }] })[0].gespraechTitel, 'Direktnachricht')
  // Mehr als fünf Vorgeschichte-Zeilen: es werden genau fünf gezeigt.
  const viele = M.ausschnitt({ vorgeschichte: Array.from({ length: 9 }, (_, i) => ({ name: `V${i}` })) })
  assert.deepEqual(viele.davor.map((z) => z.name), ['V4', 'V5', 'V6', 'V7', 'V8'])
  // Der Reiter steht in der Adresse.
  assert.equal(M.reiterAusAdresse('#/kalender/pruefen?reiter=chat'), 'chat')
  assert.equal(M.reiterAusAdresse('#/kalender/pruefen'), '')
  assert.equal(M.reiterAusAdresse('#/kalender/pruefen?reiter=termine'), '')
  assert.equal(M.MELDUNGEN_ADRESSE, '#/kalender/pruefen?reiter=chat')
})

// ════════════════════════════════════════════════════════════════════════════
// B · ChatBlase: Melden in der Aktionszeile und im Handy-Menü
// ════════════════════════════════════════════════════════════════════════════

function zeile(name, text, { eigene = false, geloescht = false, autor = 'Anna Beispiel', ...rest } = {}) {
  return {
    name, ident: name, id: name, text, eigene, autor, erstellt_am: '2026-11-18 10:00:00',
    zeit: '10:00', bearbeitet: false, geloescht, geloescht_grund: null, reaktionen: [],
    antwort_auf: null, antwortText: '', gelesen_von: null, hinweis: geloescht ? 'Diese Nachricht wurde gelöscht.' : '',
    bearbeitbar: false, ...rest,
  }
}

async function blaseMontieren(nachricht, props = {}, handy = false, { horcher = null } = {}) {
  handyAbfrage(handy)
  const ordner = join(TMP, 'blase-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  umleitung.clear()
  const mod = (await import(pathToFileURL(baum('components/chat/ChatBlase.vue', { frisch: true, ordner })).href)).default
  return mounten(mod, { nachricht, ...props }, { horcher, propNamen: ['melden', 'reaktion', 'antworten', 'bearbeiten', 'loeschen'] })
}

test('CHAT-6-UI/B: Desktop — Melden-Knopf an fremden Nachrichten, nicht an eigenen/gelöschten', async () => {
  document.body.innerHTML = ''
  const meldungen = []
  const s = await blaseMontieren(zeile('N-1', 'Guten Morgen'), {}, false,
    { horcher: (art, wert) => { if (art === 'melden') meldungen.push(wert) } })
  await warte(6)
  const knopf = knopfMit(s.host, /^Melden$/)
  assert.ok(knopf, 'der Melden-Knopf steht in der Aktionszeile')
  assert.equal(knopf.classList.contains('dk-ui-btn'), true, 'als DkButton, keine Eigenklasse')
  assert.equal(knopf.getAttribute('aria-label'), 'Melden')
  assert.ok(knopf.querySelector('svg'), 'Symbol + Beschriftung für Vorlesehilfen')
  klick(knopf)
  await warte(4)
  assert.equal(meldungen.length, 1, 'ein Klick meldet „melden“')
  assert.equal(meldungen[0].ident, 'N-1', 'mit der Nachricht der Blase')
  s.abbaum()

  document.body.innerHTML = ''
  const eigen = await blaseMontieren(zeile('N-2', 'Hallo', { eigene: true }))
  await warte(6)
  assert.equal(knopfMit(eigen.host, /^Melden$/), undefined, 'die eigene Nachricht ist nicht meldbar')
  eigen.abbaum()

  document.body.innerHTML = ''
  const weg = await blaseMontieren(zeile('N-3', 'Weg', { geloescht: true }))
  await warte(6)
  assert.equal(knopfMit(weg.host, /^Melden$/), undefined, 'eine gelöschte Nachricht ist nicht meldbar')
  weg.abbaum()
})

test('CHAT-6-UI/B: Handy — „Melden“ steht im „⋯“-Menü und meldet das Ereignis', async () => {
  document.body.innerHTML = ''
  const gemeldet = []
  const s = await blaseMontieren(zeile('N-1', 'Guten Morgen'), { handyLage: true }, true)
  await warte(6)
  assert.equal(knopfMit(s.host, /^Melden$/), undefined, 'am Handy kein eigener Melden-Knopf')
  const ausloeser = s.host.querySelector('.dk-ui-aktionen-ausloeser')
  assert.ok(ausloeser, 'das „⋯“-Menü ist da (DkAktionen)')
  klick(ausloeser)
  await warte(6)
  const eintraege = [...document.querySelectorAll('.dk-ui-aktionen-eintrag')]
  assert.deepEqual(eintraege.map((e) => e.textContent.trim()), ['Antworten', 'Melden'])
  eintraege[1].dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }))
  await warte(6)
  // Das Ereignis der Komponente trägt die Nachricht — die Seite sendet.
  const mod = await import(pathToFileURL(baum('components/chat/ChatBlase.vue')).href)
  assert.ok(mod.default.emits.includes('melden'), 'die Blase kennt das Ereignis „melden“')
  void gemeldet
  s.abbaum()

  // Eigene Nachricht am Handy: Melden fehlt im Menü.
  document.body.innerHTML = ''
  const eigen = await blaseMontieren(zeile('N-2', 'Hallo', { eigene: true }), { handyLage: true }, true)
  await warte(6)
  klick(eigen.host.querySelector('.dk-ui-aktionen-ausloeser'))
  await warte(6)
  const namen = [...document.querySelectorAll('.dk-ui-aktionen-eintrag')].map((e) => e.textContent.trim())
  assert.deepEqual(namen, ['Antworten', 'Löschen'], 'eigene Nachricht: kein Melden')
  eigen.abbaum()
})

// ════════════════════════════════════════════════════════════════════════════
// C · ChatMeldungDialog: Hinweis, Grenze, Absenden, Bestätigung
// ════════════════════════════════════════════════════════════════════════════

/**
 * Der Dialog liegt per Teleport in `document.body` (wie DkDialog ihn zeichnet).
 * Der Test sucht deshalb DORT — und räumt vor jedem Mount den Körper, damit
 * kein Dialog des vorigen Tests gefunden wird.
 */
async function dialogMontieren(props = {}, { horcher = null } = {}) {
  document.body.innerHTML = ''
  const ordner = join(TMP, 'dialog-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  umleitung.clear()
  const mod = (await import(pathToFileURL(baum('components/chat/ChatMeldungDialog.vue', { frisch: true, ordner })).href)).default
  const mountet = await mounten(mod, { modelValue: true, ...props }, { horcher, tief: true })
  const suche = (auswahl) => document.querySelector(auswahl)
  return {
    ...mountet,
    suche,
    alle: (auswahl) => [...document.querySelectorAll(auswahl)],
    abbaum: () => { mountet.abbaum(); document.body.innerHTML = '' },
  }
}

test('CHAT-6-UI/C: der Hinweis steht VOR dem Absenden da — immer', async () => {
  const s = await dialogMontieren()
  await warte(6)
  const hinweis = s.suche('.dk-meldung-hinweis')
  assert.ok(hinweis, 'der Hinweis ist im Dialog')
  assert.equal(hinweis.textContent.trim(), 'Wer Meldungen prüft, sieht diese Nachricht und die fünf davor.')
  // Er steht VOR den Aktionen (im DOM und damit in der Lesereihenfolge).
  const aktionen = s.suche('.dk-meldung-aktionen')
  assert.equal(hinweis.compareDocumentPosition(aktionen) & 4, 4,
    'der Hinweis kommt im DOM vor den Knöpfen')
  // Er ist der beschriebene Text des Dialogs (aria-describedby).
  const dialog = document.querySelector('[role="dialog"]')
  assert.ok(dialog)
  assert.equal(dialog.getAttribute('aria-describedby'), hinweis.id)
  // Und er verschwindet nicht, wenn schon ein Grund gewählt ist.
  const radio = s.suche('input[type="radio"]')
  radio.checked = true
  radio.dispatchEvent(new dom.window.Event('change', { bubbles: true }))
  await rendern()
  assert.ok(s.suche('.dk-meldung-hinweis'), 'bleibt sichtbar')
  s.abbaum()
})

test('CHAT-6-UI/C: fünf Gründe, Freitext mit Zähler und 500er-Grenze', async () => {
  const s = await dialogMontieren()
  await warte(6)
  const radios = [...s.alle('input[type="radio"]')]
  assert.equal(radios.length, 5)
  assert.deepEqual(radios.map((r) => r.value),
    ['beleidigung', 'spam', 'persoenliche_daten', 'falsche_person', 'sonstiges'])
  assert.equal(radios[0].name, radios[4].name, 'eine Auswahl (ein Name)')
  const feld = s.suche('.dk-meldung-text')
  assert.ok(feld, 'das Freitextfeld steht im Dialog')
  assert.equal(feld.tagName, 'TEXTAREA')
  assert.equal(feld.getAttribute('maxlength'), '500')
  // Das Feld kommt aus DkField: Label und Zähler gehören zum Feld (for/id,
  // aria-describedby) — keine eigene Beschriftung daneben.
  const label = s.suche('.dk-ui-field-label')
  assert.ok(label, 'die Beschriftung kommt aus DkField')
  assert.equal(label.getAttribute('for'), feld.id)
  await fuellen(feld, 'kurz')
  assert.match(s.suche('.dk-ui-field-hilfe').textContent, /4 \/ 500/)
  // Über die Grenze kommt nichts in das Feld (maxlength) — und die Prüfung
  // lehnt es zusätzlich ab (der Server tut dasselbe).
  await fuellen(feld, 'x'.repeat(600))
  assert.equal(s.offen().freitext.value.length, 600)
  // Die Prüfung nennt zuerst den fehlenden Grund; mit Grund die Länge.
  const radio = s.alle('input[type="radio"]')[0]
  radio.checked = true
  radio.dispatchEvent(new dom.window.Event('change', { bubbles: true }))
  await rendern()
  s.offen().abschicken()
  await rendern()
  assert.match(s.suche('.dk-meldung-fehler').textContent, /500/)
  s.abbaum()
})

test('CHAT-6-UI/C: ohne Grund kein Absenden; mit Grund meldet der Dialog grund + freitext', async () => {
  const gemeldet = []
  const s = await dialogMontieren({}, { horcher: (art, wert) => gemeldet.push({ art, wert }) })
  await warte(6)
  const absenden = knopfMit(document.body, /Meldung absenden/)
  assert.ok(absenden, 'der Absenden-Knopf steht da')
  klick(absenden)
  await rendern()
  assert.equal(gemeldet.filter((g) => g.art === 'melden').length, 0, 'ohne Grund keine Meldung')
  assert.match(s.suche('.dk-meldung-fehler').textContent, /Grund/)

  const radio = [...s.alle('input[type="radio"]')].find((r) => r.value === 'persoenliche_daten')
  radio.checked = true
  radio.dispatchEvent(new dom.window.Event('change', { bubbles: true }))
  await fuellen(s.suche('.dk-meldung-text'), 'Da stehen Adressen drin.')
  await rendern()
  klick(knopfMit(document.body, /Meldung absenden/))
  await warte(4)
  const ruf = gemeldet.filter((g) => g.art === 'melden').at(-1)
  assert.ok(ruf, 'der Dialog meldet „melden“')
  assert.equal(ruf.wert.grund, 'persoenliche_daten')
  assert.equal(ruf.wert.freitext, 'Da stehen Adressen drin.')
  s.abbaum()
})

test('CHAT-6-UI/C: Bestätigung nach dem Absenden, Servertext bei doppelter Meldung', async () => {
  const s = await dialogMontieren({ eingegangen: true })
  await warte(6)
  assert.match(document.body.textContent, /Danke, die Meldung ist eingegangen\./)
  assert.equal(s.suche('form'), null, 'kein zweites Absenden')
  s.abbaum()

  const gemeldet = []
  const doppelt = await dialogMontieren({}, { horcher: (art, wert) => gemeldet.push({ art, wert }) })
  await warte(8)
  doppelt.propSetzen('fehler', 'Diese Nachricht wurde von dir bereits gemeldet.')
  await rendern(8)
  await warte(4)
  const meldung = doppelt.suche('.dk-meldung-fehler')
  assert.ok(meldung, 'der Text des Servers steht im Dialog')
  assert.equal(meldung.getAttribute('role'), 'alert')
  assert.match(meldung.textContent, /bereits gemeldet/)
  doppelt.abbaum()
})

// ════════════════════════════════════════════════════════════════════════════
// D/E · Seiten: Nachrichten (Melden) und Zu prüfen (Reiter „Chat“)
// ════════════════════════════════════════════════════════════════════════════

function apiAttrappe(ordner, praefix) {
  const api = join(ordner, 'api.mjs')
  writeFileSync(api, [
    'export async function apiCall(methode, parameter) {',
    `  globalThis.${praefix}_PUSH({ methode, parameter })`,
    `  return globalThis.${praefix}_SERVER({ methode, parameter })`,
    '}',
    'export const apiGet = apiCall',
    "export const apiUrl = (p) => 'https://pruefstand.invalid/' + p",
    'export class AuditConfirmationRequired extends Error {}',
    'export const pruefeSitzungsAntwort = () => false',
    'export const apiAntwortPruefen = async () => ({ message: {} })',
    'export function mitAntwort(wert) { return wert }',
  ].join('\n'))
  const session = join(ordner, 'session.mjs')
  writeFileSync(session, [
    `import { ref } from '${VUE_URL}'`,
    'export function useSession() {',
    "  return { istTester: ref(false), devmodeAn: ref(false), mitglied: ref({ name: 'M-1' }),",
    "    istAdmin: ref(false), istGast: ref(false), fullName: ref(''),",
    "    rollen: ref([]), abmelden: async () => {}, sitzungPruefen: async () => {} }",
    '}',
  ].join('\n'))
  return { api, session }
}

const GESPRAECHE = [{
  name: 'CHAT-1', art: 'gruppe', gruppe: 'chor', untergruppe: null, titel: 'Chor',
  geoeffnet: true, ungelesen: 0, teilnehmer: 9, letzte_nachricht: 'Hallo',
  letzte_am: '2026-11-18 10:00:00', darf_senden: true,
}]

const VERLAUF = {
  gespraech: 'CHAT-1',
  richtung: 'neueste',
  nachrichten: [
    { name: 'CHAT-1-N1', gespraech: 'CHAT-1', text: 'Guten Morgen', eigene: false,
      autor: 'Anna Beispiel', erstellt_am: '2026-11-18 09:00:00' },
    { name: 'CHAT-1-N2', gespraech: 'CHAT-1', text: 'Meine eigene', eigene: true,
      autor: 'Ich', erstellt_am: '2026-11-18 09:05:00' },
  ],
}

async function nachrichtenMontieren({ server = {} } = {}) {
  const ordner = join(TMP, 'seite-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  const { api, session } = apiAttrappe(ordner, '__SEITE')
  const U2 = (rel) => pathToFileURL(SRC.pathname + rel).href
  umleitung.clear()
  umleitung.set(U2('composables/useApi.js'), pathToFileURL(api).href)
  umleitung.set(U2('composables/useSession.js'), pathToFileURL(session).href)

  const aufrufe = []
  globalThis.__SEITE_PUSH = (eintrag) => aufrufe.push(eintrag)
  globalThis.__SEITE_SERVER = ({ methode, parameter }) => {
    const kurz = String(methode).split('.').pop()
    if (server && typeof server[kurz] === 'function') return server[kurz](parameter)
    if (kurz === 'meine_gespraeche') return { gespraeche: GESPRAECHE.map((g) => ({ ...g })) }
    if (kurz === 'verlauf') return { ...VERLAUF, nachrichten: VERLAUF.nachrichten.map((n) => ({ ...n })) }
    if (kurz === 'lesestand_setzen') return { ungelesen: 0 }
    return {}
  }
  dom.window.__DIakonosBOOT = { roles: ['Mitglied'], is_admin: false, module_sichtbar: ['chat'] }
  dom.window.location.hash = '#/nachrichten/CHAT-1'
  handyAbfrage(false)

  const gestartet = new Set()
  const origT = globalThis.setTimeout
  const origI = globalThis.setInterval
  globalThis.setTimeout = (fn, ms) => { const id = origT(fn, ms); gestartet.add(id); return id }
  globalThis.setInterval = (fn, ms) => { const id = origI(fn, ms); gestartet.add(id); return id }
  let gemountet = null
  try {
    const mod = (await import(pathToFileURL(baum('pages/Nachrichten.vue', { frisch: true, ordner })).href)).default
    gemountet = await mounten(mod, {})
  } finally {
    globalThis.setTimeout = origT
    globalThis.setInterval = origI
  }
  const abraeumen = () => {
    for (const t of gestartet) { try { clearTimeout(t); clearInterval(t) } catch { /* egal */ } }
  }
  const vorher = gemountet.abbaum
  gemountet.abbaum = () => { vorher(); abraeumen() }
  await rendern(6)
  await warte(14)
  await rendern(6)
  return { ...gemountet, aufrufe }
}

test('CHAT-6-UI/D: Melden in der Seite → chat.meldung_senden mit grund/freitext', async () => {
  const s = await nachrichtenMontieren({
    server: { meldung_senden: () => ({ name: 'M-1', stand: 'offen', meldung_offen: true }) },
  })
  // Fremde Nachricht: Knopf da. Eigene: nicht.
  const knoepfe = [...s.host.querySelectorAll('.dk-chat-verlaufsliste > li.dk-chat-beitrag')].map((b) => ({
    name: b.getAttribute('data-name'),
    melden: !!knopfMit(b, /^Melden$/),
  }))
  assert.deepEqual(knoepfe, [
    { name: 'CHAT-1-N1', melden: true },
    { name: 'CHAT-1-N2', melden: false },
  ], 'nur die fremde Nachricht trägt „Melden“')

  klick(knopfMit(s.host.querySelector('[data-name="CHAT-1-N1"]'), /^Melden$/))
  await rendern(6)
  await warte(6)
  const dialog = document.querySelector('.dk-meldung')
  assert.ok(dialog, 'der Meldedialog ist offen')
  assert.match(dialog.textContent, /Wer Meldungen prüft, sieht diese Nachricht und die fünf davor\./)

  const radio = [...dialog.querySelectorAll('input[type="radio"]')].find((r) => r.value === 'beleidigung')
  radio.checked = true
  radio.dispatchEvent(new dom.window.Event('change', { bubbles: true }))
  await fuellen(dialog.querySelector('.dk-meldung-text'), 'So nicht.')
  await rendern()
  klick(knopfMit(document.body, /Meldung absenden/))
  await rendern(6)
  await warte(10)
  await rendern(6)
  const ruf = s.aufrufe.filter((a) => a.methode === 'chat.meldung_senden').at(-1)
  assert.ok(ruf, 'die Seite ruft chat.meldung_senden')
  assert.deepEqual(ruf.parameter, { nachricht: 'CHAT-1-N1', grund: 'beleidigung', freitext: 'So nicht.' })
  // Ruhige Bestätigung im Dialog.
  assert.match(document.querySelector('.dk-meldung').textContent, /Danke, die Meldung ist eingegangen\./)
  s.abbaum()
})

test('CHAT-6-UI/D: doppelte Meldung — der Text des Servers steht ruhig im Dialog', async () => {
  const s = await nachrichtenMontieren({
    server: {
      meldung_senden: () => {
        throw Object.assign(new Error('Diese Nachricht wurde von dir bereits gemeldet.'), { status: 400 })
      },
    },
  })
  klick(knopfMit(s.host.querySelector('[data-name="CHAT-1-N1"]'), /^Melden$/))
  await rendern(6)
  await warte(6)
  const dialog = document.querySelector('.dk-meldung')
  assert.ok(dialog, 'der Meldedialog ist offen')
  const radio = dialog.querySelector('input[type="radio"]')
  radio.checked = true
  radio.dispatchEvent(new dom.window.Event('change', { bubbles: true }))
  await rendern()
  klick(knopfMit(document.body, /Meldung absenden/))
  await rendern(6)
  await warte(10)
  await rendern(6)
  const fehler = document.querySelector('.dk-meldung-fehler')
  assert.ok(fehler, 'der Fehler steht im Dialog')
  assert.match(fehler.textContent, /bereits gemeldet/)
  assert.doesNotMatch(document.querySelector('.dk-meldung').textContent, /Danke/, 'keine Bestätigung')
  s.abbaum()
})

// ── Zu prüfen: der Reiter „Chat“ ───────────────────────────────────────────

function meldungForm(überschreiben = {}) {
  return {
    name: 'M-1',
    stand: 'offen',
    grund: 'beleidigung',
    freitext: null,
    erstellt_am: '2026-11-18 09:00:00',
    // Im 1:1 liefert der Server NEUTRAL „Direktnachricht“.
    gespraech_titel: 'Direktnachricht',
    nachricht: {
      name: 'DM-5', text: 'Du bist doof', autor: 'Anna A.',
      erstellt_am: '2026-11-18 08:59:00', geloescht_am: null, text_entfernt: false,
    },
    vorgeschichte: [
      { name: 'DM-1', autor: 'Bert B.', text: 'Hallo Anna', geloescht: false, erstellt_am: '2026-11-17 20:00:00' },
      { name: 'DM-2', autor: 'Anna A.', text: 'Hi Bert', geloescht: false, erstellt_am: '2026-11-17 20:01:00' },
    ],
    ...überschreiben,
  }
}

async function moderationMontieren({ server = {}, hash = '#/kalender/pruefen' } = {}) {
  const ordner = join(TMP, 'mod-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  const { api, session } = apiAttrappe(ordner, '__MOD')
  const U2 = (rel) => pathToFileURL(SRC.pathname + rel).href
  // Die Termin-Tafel zieht `sortablejs` (im Node-Prüfstand nicht installiert)
  // und braucht hier nichts: im Reiter „Chat“ wird sie nicht gezeichnet. Sie
  // wird deshalb durch eine leere Attrappe ersetzt (nur für diesen Test).
  const boardStub = join(ordner, 'board-stub.mjs')
  writeFileSync(boardStub, [
    `import { defineComponent, h } from '${VUE_URL}'`,
    'export default defineComponent({',
    "  name: 'ModerationBoard',",
    '  setup(_, { expose }) {',
    '    expose({ getStagingIds: () => [], reloadBoard: async () => {} })',
    "    return () => h('div', { class: 'board-attrappe' })",
    '  },',
    '})',
  ].join('\n'))
  umleitung.clear()
  umleitung.set(U2('composables/useApi.js'), pathToFileURL(api).href)
  umleitung.set(U2('composables/useSession.js'), pathToFileURL(session).href)
  umleitung.set(pathToFileURL(SRC.pathname + 'components/kronos/ModerationBoard.vue').href,
    pathToFileURL(boardStub).href)

  const aufrufe = []
  globalThis.__MOD_PUSH = (eintrag) => aufrufe.push(eintrag)
  globalThis.__MOD_SERVER = ({ methode, parameter }) => {
    const kurz = String(methode).split('.').pop()
    if (server && typeof server[kurz] === 'function') return server[kurz](parameter)
    // CHAT-6-UI-3: Der Chat-Einstieg steht in `get_session_info`
    // (`chat_moderieren`) — die Liste wird nur noch MIT Recht geholt.
    if (kurz === 'get_session_info') return { can_moderate: true, chat_moderieren: true }
    if (kurz === 'getModerationCount' || kurz === 'get_moderation_count') return { count: 0 }
    if (kurz === 'meldungen_liste') return { meldungen: [], offen: 0 }
    return {}
  }
  dom.window.__DIakonosBOOT = { roles: ['Moderator'], is_admin: false, module_sichtbar: ['kalender', 'chat'] }
  dom.window.location.hash = hash
  handyAbfrage(false)

  const mod = (await import(pathToFileURL(baum('pages/Moderation.vue', { frisch: true, ordner })).href)).default
  const gemountet = await mounten(mod, {}, {
    propNamen: ['entschieden'],
  })
  await rendern(6)
  await warte(14)
  await rendern(6)
  return { ...gemountet, aufrufe }
}

test('CHAT-6-UI/E: bei 403 fehlt der Reiter „Chat“', async () => {
  // CHAT-6-UI-3: Ohne Chat-Recht geht GAR KEIN Listen-Abruf hinaus — die
  // Frage beantwortet `get_session_info` (chat_moderieren false).
  const s = await moderationMontieren({
    server: { get_session_info: () => ({ can_moderate: true, chat_moderieren: false }) },
  })
  assert.ok(s.aufrufe.some((a) => a.methode.endsWith('get_session_info')), 'die Seite fragt den Server')
  assert.ok(!s.aufrufe.some((a) => a.methode === 'chat.meldungen_liste'),
    'ohne Chat-Recht kein meldungen_liste-Aufruf')
  const reiter = [...s.host.querySelectorAll('.kal-reiter-punkt')].map((e) => e.textContent.trim())
  assert.ok(!reiter.some((t) => /^Chat/.test(t)), 'ohne Recht kein Reiter: ' + reiter.join(' | '))
  s.abbaum()
})

test('CHAT-6-UI/E: mit Recht steht der Reiter am Kopf; er führt in die Meldungen', async () => {
  const s = await moderationMontieren({
    server: { meldungen_liste: ({ stand }) => (stand === 'offen'
      ? { meldungen: [meldungForm()], offen: 1 }
      : { meldungen: [], offen: 1 }) },
  })
  const chat = [...s.host.querySelectorAll('.kal-reiter-punkt')].find((e) => /^Chat/.test(e.textContent.trim()))
  assert.ok(chat, 'der Reiter „Chat“ steht am Kopf')
  assert.equal(chat.getAttribute('data-reiter'), 'chat')
  assert.equal(chat.getAttribute('href'), '#/kalender/pruefen?reiter=chat',
    'der Reiter ist ein Link mit eigener Adresse')
  assert.deepEqual(texte(s.host, '.kal-reiter-punkt .kal-reiter-zahl').filter(Boolean), ['1'],
    'die Zahl der offenen Meldungen steht am Reiter')
  s.abbaum()

  // Die Adresse des Reiters zeigt die Meldungen (Liste + Ausschnitt).
  const zweite = await moderationMontieren({
    hash: '#/kalender/pruefen?reiter=chat',
    server: { meldungen_liste: () => ({ meldungen: [meldungForm()], offen: 1 }) },
  })
  assert.ok(zweite.host.querySelector('.dk-mpanel'), 'der Reiter zeigt die Meldungen')
  assert.match(zweite.host.textContent, /Direktnachricht/, 'im 1:1 neutral betitelt')
  assert.doesNotMatch(zweite.host.textContent, /Anna A\.\s*·/, 'kein Name als Gesprächstitel')
  assert.match(zweite.host.textContent, /Beleidigung/)
  // Zeitpunkt über die gemeinsame Zeit-Hilfe (deutsche Zeit, 09:00 UTC = 10:00).
  assert.match(zweite.host.textContent, /18\.11\.2026, 10:00/)
  // Die Termin-Tafel steht im Chat-Reiter NICHT (kein zweiter Ort, keine
  // leere Freigabe-Zeile).
  assert.equal(zweite.host.querySelector('.dk-moderation-erklaerung') !== null, true)
  zweite.abbaum()
})

test('CHAT-6-UI/E: Ausschnitt — gemeldete Nachricht hervorgehoben, fünf davor, keine eigene Abfrage', async () => {
  const historie = Array.from({ length: 7 }, (_, i) => ({
    name: `DM-${i + 1}`, autor: i % 2 ? 'Anna A.' : 'Bert B.', text: `Zeile ${i + 1}`,
    geloescht: false, erstellt_am: `2026-11-17 20:0${i}:00`,
  }))
  const s = await moderationMontieren({
    hash: '#/kalender/pruefen?reiter=chat',
    server: {
      meldungen_liste: () => ({
        meldungen: [meldungForm({ vorgeschichte: historie })], offen: 1,
      }),
    },
  })
  // Aufklappen.
  klick(knopfMit(s.host, /^Ansehen$/))
  await rendern(4)
  const zeilen = [...s.host.querySelectorAll('.dk-mpanel-zeile')]
  // Der Server liefert den Ausschnitt; die Seite zeigt die LETZTEN fünf davor
  // und danach die gemeldete Nachricht.
  assert.equal(zeilen.length, 6, 'fünf davor + die gemeldete')
  assert.deepEqual(zeilen.slice(0, 5).map((z) => z.querySelector('.dk-mpanel-zeile-text').textContent.trim()),
    ['Zeile 3', 'Zeile 4', 'Zeile 5', 'Zeile 6', 'Zeile 7'])
  const gemeldet = zeilen.at(-1)
  assert.equal(gemeldet.classList.contains('is-gemeldet'), true, 'die gemeldete Nachricht ist hervorgehoben')
  assert.equal(gemeldet.querySelector('.dk-mpanel-zeile-text').textContent.trim(), 'Du bist doof')
  assert.match(gemeldet.textContent, /gemeldet/)
  // KEINE zweite Abfrage für den Ausschnitt: nur `meldungen_liste`.
  const abfragen = new Set(s.aufrufe.map((a) => a.methode))
  assert.deepEqual([...abfragen].filter((m) => /meldung|verlauf/.test(m)), ['chat.meldungen_liste'])
  s.abbaum()
})

test('CHAT-6-UI/E: Entscheidung als POST; ohne Grund kein Entfernen', async () => {
  const s = await moderationMontieren({
    hash: '#/kalender/pruefen?reiter=chat',
    server: {
      meldungen_liste: () => ({ meldungen: [meldungForm()], offen: 1 }),
      meldung_entscheiden: () => ({ ...meldungForm(), stand: 'erledigt' }),
    },
  })
  klick(knopfMit(s.host, /^Ansehen$/))
  await rendern(4)
  // KEINE Vorauswahl (Review CHAT-6 R1): erst nach bewusster Wahl trägt der
  // Knopf eine Entscheidung — vorher nur der Aufforderungstext.
  const vorWahl = [...s.host.querySelectorAll('.dk-mpanel-aktionen button')].map((b) => b.textContent.trim())
  assert.deepEqual(vorWahl, ['Entscheidung wählen'], 'ohne Wahl kein „Entfernen“')
  assert.equal([...s.host.querySelectorAll('.dk-mpanel-wahl input')].some((r) => r.checked), false,
    'keine Wahl vorbelegt')
  // Auch ein Klick auf den Knopf schickt nichts hinaus.
  klick(knopfMit(s.host, /Entscheidung wählen/))
  await rendern(4)
  assert.equal(s.aufrufe.filter((a) => a.methode === 'chat.meldung_entscheiden').length, 0,
    'ohne Wahl geht nichts hinaus')
  assert.match(s.host.querySelector('.dk-mpanel-fehler').textContent, /Entscheidung/)

  // Bewusst „Nachricht entfernen“ wählen — ohne Grund geht sie nicht hinaus.
  const entfernen = [...s.host.querySelectorAll('.dk-mpanel-wahl input')]
    .find((r) => r.value === 'entfernen')
  entfernen.checked = true
  entfernen.dispatchEvent(new dom.window.Event('change', { bubbles: true }))
  await rendern(4)
  const absenden = knopfMit(s.host, /Nachricht entfernen/)
  assert.ok(absenden, 'die Entscheidung ist gewählt (Entfernen)')
  klick(absenden)
  await rendern(4)
  assert.equal(s.aufrufe.filter((a) => a.methode === 'chat.meldung_entscheiden').length, 0,
    'ohne Grund kein Entfernen (der Server verlangt ihn ebenfalls)')
  assert.match(s.host.querySelector('.dk-mpanel-fehler').textContent, /Grund/)

  // Grund eintragen und entscheiden — das Feld kommt aus DkField.
  const grundFeld = s.host.querySelector('.dk-mpanel-text')
  assert.ok(grundFeld, 'das Grundfeld steht im Auszug')
  assert.equal(grundFeld.tagName, 'TEXTAREA')
  await fuellen(grundFeld, 'Beleidigung')
  await rendern()
  klick(knopfMit(s.host, /Nachricht entfernen/))
  await warte(8)
  const ruf = s.aufrufe.filter((a) => a.methode === 'chat.meldung_entscheiden').at(-1)
  assert.ok(ruf, 'die Seite ruft chat.meldung_entscheiden')
  assert.deepEqual(ruf.parameter, { meldung: 'M-1', entscheidung: 'entfernen', grund: 'Beleidigung' })
  assert.ok(s.aufrufe.filter((a) => a.methode === 'chat.meldungen_liste').length >= 2,
    'danach wird die Liste neu geholt (Server ist die Wahrheit)')
  s.abbaum()

  // Zurückweisen: Grund freiwillig.
  const zweite = await moderationMontieren({
    hash: '#/kalender/pruefen?reiter=chat',
    server: {
      meldungen_liste: () => ({ meldungen: [meldungForm()], offen: 1 }),
      meldung_entscheiden: () => ({ ...meldungForm(), stand: 'verworfen' }),
    },
  })
  klick(knopfMit(zweite.host, /^Ansehen$/))
  await rendern(4)
  const verwerfen = [...zweite.host.querySelectorAll('input[type="radio"]')]
    .find((r) => r.value === 'verwerfen')
  verwerfen.checked = true
  verwerfen.dispatchEvent(new dom.window.Event('change', { bubbles: true }))
  await rendern()
  klick(knopfMit(zweite.host, /Meldung zurückweisen/))
  await warte(8)
  const ruf2 = zweite.aufrufe.filter((a) => a.methode === 'chat.meldung_entscheiden').at(-1)
  assert.equal(ruf2.parameter.meldung, 'M-1')
  assert.equal(ruf2.parameter.entscheidung, 'verwerfen')
  assert.equal(ruf2.parameter.grund, undefined, 'ohne Grund geht kein leerer Text hinaus')
  zweite.abbaum()
})

test('CHAT-6-UI/E: keine Namen der meldenden Person, wenn der Server keine liefert', async () => {
  const ohneMelder = await moderationMontieren({
    hash: '#/kalender/pruefen?reiter=chat',
    server: { meldungen_liste: () => ({ meldungen: [meldungForm({ melder: null })], offen: 1 }) },
  })
  assert.doesNotMatch(ohneMelder.host.textContent, /Gemeldet von/)
  ohneMelder.abbaum()

  const mitMelder = await moderationMontieren({
    hash: '#/kalender/pruefen?reiter=chat',
    server: { meldungen_liste: () => ({ meldungen: [meldungForm({ melder: 'Bert B.' })], offen: 1 }) },
  })
  assert.match(mitMelder.host.textContent, /Gemeldet von Bert B\./,
    'liefert der Server die Herkunft, steht sie da (2.5: „wer meldet im Dutzend“)')
  mitMelder.abbaum()
})

test('CHAT-6-UI/E: erledigte Meldungen stehen im zweiten Abschnitt (eigener Abruf, MUSS 2)', async () => {
  // Der Server filtert HART auf `stand`: nur `offen` abzufragen lässt den
  // zweiten Abschnitt immer leer. Die Seite holt deshalb beim Öffnen
  // `erledigt` UND `verworfen` — zusammen mit dem letzten `offen`-Stand.
  const s = await moderationMontieren({
    hash: '#/kalender/pruefen?reiter=chat',
    server: {
      meldungen_liste: ({ stand }) => {
        if (stand === 'offen') return { meldungen: [], offen: 0 }
        if (stand === 'erledigt') return { meldungen: [{ ...meldungForm(), name: 'M-2', stand: 'erledigt' }], offen: 0 }
        if (stand === 'verworfen') return { meldungen: [{ ...meldungForm(), name: 'M-3', stand: 'verworfen' }], offen: 0 }
        return { meldungen: [], offen: 0 }
      },
    },
  })
  assert.match(s.host.textContent, /Keine offenen Meldungen/)
  // Vor dem Aufklappen wurde NICHTS auf Vorrat geholt.
  const staende = () => s.aufrufe.filter((a) => a.methode === 'chat.meldungen_liste')
    .map((a) => a.parameter?.stand)
  assert.deepEqual(staende(), ['offen'], 'nur die Arbeitsliste beim Laden')
  // Der Umschalter auf „Erledigte Meldungen“ holt die beiden Stände.
  klick(knopfMit(s.host, /Erledigte Meldungen/))
  await warte(12)
  assert.deepEqual(staende().slice(1).sort(), ['erledigt', 'verworfen'],
    'erledigt und verworfen sind EIGENE Abrufe')
  assert.match(s.host.textContent, /zurückgewiesen/, 'Stand in Klartext')
  assert.match(s.host.textContent, /erledigt/, 'der erledigte Stand steht auch da')
  // Der Zähler bleibt der der OFFENEN Meldungen (hier 0).
  assert.match(s.host.textContent, /Nichts zu prüfen\./)
  s.abbaum()
})

test('CHAT-6-UI/E: nur Chat-Recht (can_moderate false) — Reiter und Liste trotzdem da (MUSS 1)', async () => {
  // Chat-Moderation ist ein EIGENES Recht (HV/MV/GL der Gruppe, Meldestelle im
  // 1:1) und hängt NICHT an `can_moderate` (Kalender). Der Server sagt für
  // beide Wege getrennt „ja“ oder „nein“ — hier: Termine nein, Chat ja.
  const s = await moderationMontieren({
    server: {
      get_session_info: () => ({ can_moderate: false, chat_moderieren: true }),
      meldungen_liste: ({ stand }) => (stand === 'offen'
        ? { meldungen: [meldungForm()], offen: 1 }
        : { meldungen: [], offen: 1 }),
    },
  })
  // Keine Sperrseite: die Seite ist offen.
  assert.equal(s.host.querySelector('.mod-zustand--verweigert'), null, 'kein „Zugriff verweigert“')
  // Der Reiter „Chat“ steht am Kopf — auch ohne Termine-Recht.
  const chat = [...s.host.querySelectorAll('.kal-reiter-punkt')].find((e) => /^Chat/.test(e.textContent.trim()))
  assert.ok(chat, 'der Reiter „Chat“ steht ohne Kalender-Recht')
  assert.equal(chat.getAttribute('data-reiter'), 'chat')
  // Ohne Termine-Recht gibt es den Reiter „Zu prüfen“ NICHT.
  const pruefen = [...s.host.querySelectorAll('.kal-reiter-punkt')]
    .find((e) => /^Zu prüfen/.test(e.textContent.trim()))
  assert.equal(pruefen, undefined, 'kein „Zu prüfen“ ohne Kalender-Recht')
  // Die Liste steht direkt (nur Chat-Recht → Chat-Zweig ist die Seite).
  assert.ok(s.host.querySelector('.dk-mpanel'), 'die Meldungen stehen da')
  assert.match(s.host.textContent, /Direktnachricht/)
  // Die Termine-Tafel/„Alle freigeben“ erscheint NICHT.
  assert.equal(s.host.querySelector('.board-attrappe'), null, 'keine Termine-Tafel')
  assert.equal(knopfMit(s.host, /Alle freigeben/), undefined, 'kein „Alle freigeben“')
  s.abbaum()
})

// ════════════════════════════════════════════════════════════════════════════
// F · Glocke
// ════════════════════════════════════════════════════════════════════════════

test('CHAT-6-UI/F: „Neue Meldung im Chat“ führt in den Reiter', () => {
  assert.equal(ZIELE.istChatMeldung({ document_type: 'chat_meldung' }), true)
  assert.equal(ZIELE.istChatMeldung({ subject: 'Neue Meldung im Chat' }), true)
  assert.equal(ZIELE.istChatMeldung({ subject: 'Datenanfrage von Anna' }), false)
  assert.equal(ZIELE.istChatMeldung({ type: 'Datenanfrage', subject: 'x' }), false)
  assert.equal(ZIELE.istChatMeldung(null), false)
  assert.equal(ZIELE.meldungZiel(), '#/kalender/pruefen?reiter=chat')
  // Der Reiter der Adresse ist derselbe, den die Seite liest.
  assert.equal(M.reiterAusAdresse(ZIELE.meldungZiel()), 'chat')
  // Die Glocke zeichnet den Eintrag als Weg (Knopf mit Ziel), nicht als Text.
  // LEISTE-1: die Glocke steht in ihrem eigenen Baustein.
  const glocke = readFileSync(new URL('../src/diakonos/components/Glocke.vue', import.meta.url), 'utf8')
  assert.match(glocke, /istChatMeldung/)
  assert.match(glocke, /meldungZiel/)
})
