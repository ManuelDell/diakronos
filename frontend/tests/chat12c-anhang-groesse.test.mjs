/**
 * CHAT-12c-UI — Anhangsgröße in den Admin-Einstellungen einstellbar (Frontend).
 *
 * Grundlage ist das FERTIGE Backend (CHAT-12c-BE, `wt/t_2e315156`):
 *
 *   GET  chat.chat_einstellungen_lesen
 *        → {anhang_max_mb, standard: 10, minimum: 1, maximum: 50}
 *   POST chat.chat_einstellungen_speichern(anhang_max_mb)  — nur Administrator
 *        → {anhang_max_mb, gespeichert: true, standard, minimum, maximum}
 *   chat.meine_gespraeche trägt `anhang_max_bytes` (Bytes) — für die
 *        Vorab-Prüfung der Chat-Seite, kein zweiter Rundlauf.
 *
 * Geprüft wird VERHALTEN, nicht nur Quelltext:
 *
 *   A  Die Regeln ohne DOM (`components/chat/anhaenge.mjs`): Grenze aus der
 *      Serverantwort, Rückfall 10 MB ohne Serverwert, Vorab-Prüfung und der
 *      Satz mit der ECHTEN MB-Zahl.
 *   B  Die Admin-Einstellungen (`pages/einstellungen/anhanggroesse.mjs`):
 *      Lesen der Antwort, Prüfung 1…50, Nutzlast `anhang_max_mb`, Fehlertexte.
 *   C  `Fristen.vue` gemountet: das Feld steht da, zeigt den gespeicherten
 *      Wert und den Standard, Speichern schickt `anhang_max_mb` an
 *      `chat.chat_einstellungen_speichern`, ein Server-Fehler steht am Feld,
 *      ein 403 wird ruhig erklärt.
 *   D  `Nachrichten.vue` gemountet: die Grenze aus `meine_gespraeche` gilt für
 *      die Auswahl — 25 MB eingestellt → 20-MB-Datei geht durch, 26 MB wird
 *      abgewiesen mit „max. 25 MB“; ohne Serverwert 10 MB.
 *
 * Lauf (eine Datei je Aufruf, TZ=Europe/Berlin):
 *   TMPDIR=$(mktemp -d) TZ=Europe/Berlin node --test tests/chat12c-anhang-groesse.test.mjs
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
  'sessionStorage', 'location', 'URLSearchParams', 'PopStateEvent', 'HashChangeEvent',
  'AbortController', 'AbortSignal', 'File', 'Blob', 'FileList']) {
  globalThis[schluessel] = dom.window[schluessel]
}
globalThis.requestAnimationFrame = dom.window.requestAnimationFrame
  || ((fn) => setTimeout(() => fn(Date.now()), 0))
globalThis.CSS = dom.window.CSS || { escape: (s) => String(s) }
Object.defineProperty(dom.window.document, 'hidden', { configurable: true, get: () => false })
Object.defineProperty(dom.window.document, 'visibilityState', { configurable: true, get: () => 'visible' })

const VUE_URL = import.meta.resolve('vue')
const SRC_ROOT = new URL('../src/', import.meta.url)
const SRC = new URL('../src/diakonos/', import.meta.url)
const lies = (p) => readFileSync(new URL(p, SRC), 'utf8')

const TMP = mkdtempSync(join(tmpdir(), 'chat12c-'))
test.after(() => rmSync(TMP, { recursive: true, force: true }))

const T = await import(new URL('components/chat/anhaenge.mjs', SRC).href)
const G = await import(new URL('pages/einstellungen/anhanggroesse.mjs', SRC).href)

// ── SFC → ES-Modul (derselbe Weg wie die übrigen chat*-UI-Tests) ───────────
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
    const wurzel = resolve(SRC_ROOT.pathname)
    const voll = resolve(quellDatei)
    const relativ = voll.startsWith(wurzel) ? 'x' + voll.slice(wurzel.length) : voll
    const ziel = join(unterordner, relativ.replace(/[\\/]/g, '_') + '.mjs')
    mkdirSync(dirname(ziel), { recursive: true })
    return ziel
  }
  const uebersetzen = (abs) => {
    if (NEU.has(abs)) return NEU.get(abs)
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

function mounten(baustein) {
  return import('vue').then(async (Vue) => {
    const host = document.createElement('div')
    document.body.appendChild(host)
    const warnungen = []
    const app = Vue.createApp({ render: () => Vue.h(baustein) })
    app.config.warnHandler = (m) => warnungen.push(m)
    app.config.errorHandler = (e) => warnungen.push(String(e && e.message))
    app.mount(host)
    await warte(10)
    return {
      host, app, warnungen,
      abbaum: seitenAbbau.anmelden(() => {
        try { app.unmount() } catch { /* egal */ }
        try { host.remove() } catch { /* egal */ }
      }),
    }
  })
}

function klick(el) {
  assert.ok(el, 'das Element steht im DOM')
  el.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true, cancelable: true }))
}

async function fuellen(el, wert) {
  assert.ok(el, 'das Feld steht im DOM')
  el.value = wert
  el.dispatchEvent(new dom.window.Event('input', { bubbles: true }))
  await rendern(2)
}

const knopf = (host, muster) => [...host.querySelectorAll('button')].find((b) => muster.test(b.textContent))

function feldUeberLabel(host, beschriftung) {
  const label = [...host.querySelectorAll('label')]
    .find((l) => l.textContent.trim() === beschriftung)
  if (!label) return null
  const ziel = label.getAttribute('for')
  return ziel ? host.querySelector(`#${ziel}`) : null
}

const MB = 1024 * 1024

// ════════════════════════════════════════════════════════════════════════════
// A · Die Grenze aus der Serverantwort (Chat-Seite)
// ════════════════════════════════════════════════════════════════════════════

test('CHAT-12c-UI/A: die Grenze kommt aus `anhang_max_bytes`, ohne Wert gilt 10 MB', () => {
  assert.equal(T.anhangMaxBytes({ anhang_max_bytes: 25 * MB }), 25 * MB)
  assert.equal(T.anhangMaxBytes({ anhang_max_bytes: 1 * MB }), 1 * MB)
  // Ohne Serverwert (alter Server / leer / Unsinn): der Standard.
  assert.equal(T.anhangMaxBytes({}), 10 * MB)
  assert.equal(T.anhangMaxBytes(null), 10 * MB)
  assert.equal(T.anhangMaxBytes({ anhang_max_bytes: null }), 10 * MB)
  assert.equal(T.anhangMaxBytes({ anhang_max_bytes: 'abc' }), 10 * MB)
  assert.equal(T.anhangMaxBytes({ anhang_max_bytes: 0 }), 10 * MB)
  assert.equal(T.anhangMaxBytes({ anhang_max_bytes: -5 }), 10 * MB)
  // Der Rückfall ist die EINE Standardzahl des Moduls.
  assert.equal(T.ANHANG_MAX_BYTES, 10 * MB)
  assert.equal(T.ANHANG_MAX_MB, 10)
})

test('CHAT-12c-UI/A: MB-Text nennt ganze MB ohne Nachkommastelle, krumme mit Komma', () => {
  assert.equal(T.mbText(25 * MB), '25')
  assert.equal(T.mbText(10 * MB), '10')
  assert.equal(T.mbText(1 * MB), '1')
  assert.equal(T.mbText(2.5 * MB), '2,5')
  assert.equal(T.mbText(0), '10', 'ohne brauchbare Zahl der Standard')
  assert.equal(T.mbText(null), '10')
})

test('CHAT-12c-UI/A: 25 MB eingestellt → 20 MB geht, 26 MB abgewiesen mit „25 MB“', () => {
  const grenze = T.anhangMaxBytes({ anhang_max_bytes: 25 * MB })
  const datei = (name, groesse) => {
    const d = new File([new Uint8Array(1)], name, { type: 'image/jpeg' })
    Object.defineProperty(d, 'size', { configurable: true, value: groesse })
    return d
  }
  assert.equal(T.auswahlPruefen([datei('zwanzig.jpg', 20 * MB)], 0, 0, grenze).ok, true)
  // Genau die Grenze ist erlaubt (der Server weist erst darüber ab).
  assert.equal(T.auswahlPruefen([datei('genau.jpg', 25 * MB)], 0, 0, grenze).ok, true)
  const zuGross = T.auswahlPruefen([datei('sechsundzwanzig.jpg', 26 * MB)], 0, 0, grenze)
  assert.equal(zuGross.ok, false)
  assert.match(zuGross.text, /zu groß/)
  assert.match(zuGross.text, /max\. 25 MB/, 'die ECHTE Zahl aus der Einstellung')
  assert.doesNotMatch(zuGross.text, /10 MB/, 'nicht der Standard, wenn 25 gilt')
})

test('CHAT-12c-UI/A: ohne Serverwert prüft die Vorab-Prüfung gegen 10 MB', () => {
  const datei = (name, groesse) => {
    const d = new File([new Uint8Array(1)], name, { type: 'image/jpeg' })
    Object.defineProperty(d, 'size', { configurable: true, value: groesse })
    return d
  }
  const grenze = T.anhangMaxBytes({})
  assert.equal(T.auswahlPruefen([datei('ok.jpg', 10 * MB)], 0, 0, grenze).ok, true)
  const zuGross = T.auswahlPruefen([datei('zu.jpg', 20 * MB)], 0, 0, grenze)
  assert.equal(zuGross.ok, false)
  assert.match(zuGross.text, /max\. 10 MB/)
})

// ════════════════════════════════════════════════════════════════════════════
// B · Die Regeln der Admin-Einstellung (ohne DOM)
// ════════════════════════════════════════════════════════════════════════════

test('CHAT-12c-UI/B: Antwort gelesen — Wert, Standard und Grenzen', () => {
  const stand = G.standLesen({ anhang_max_mb: 25, standard: 10, minimum: 1, maximum: 50 })
  assert.deepEqual(stand, { gespeichert: 25, standard: 10, minimum: 1, maximum: 50 })
  assert.equal(G.feldText(stand), '25', 'das Feld zeigt den GESPEICHERTEN Wert')
  assert.equal(G.standardText(stand), '10')
  assert.equal(G.standardHinweis(stand), 'Standard: 10 MB · gilt für Anhänge im Chat')
  // Fehlt der Wert, bleibt das Feld leer — keine geratene Zahl.
  assert.equal(G.feldText(G.standLesen({})), '')
  // Grenzen ohne Serverangabe: die Vorgabe des Kartentexts (1–50).
  const ohne = G.standLesen({ anhang_max_mb: 25 })
  assert.equal(ohne.minimum, 1)
  assert.equal(ohne.maximum, 50)
  assert.equal(ohne.standard, 10)
})

test('CHAT-12c-UI/B: Eingabe 1…50, ganze Zahl, leer ist leer', () => {
  const stand = G.standLesen({ anhang_max_mb: 25, standard: 10, minimum: 1, maximum: 50 })
  assert.deepEqual(G.eingabePruefen('25', stand), { ok: true, fehler: '', wert: 25 })
  assert.equal(G.eingabePruefen('1', stand).ok, true, 'die Untergrenze ist erlaubt')
  assert.equal(G.eingabePruefen('50', stand).ok, true, 'die Obergrenze ist erlaubt')
  assert.equal(G.eingabePruefen('0', stand).ok, false)
  assert.match(G.eingabePruefen('0', stand).fehler, /zwischen 1 und 50/)
  assert.match(G.eingabePruefen('51', stand).fehler, /zwischen 1 und 50/)
  assert.match(G.eingabePruefen('2.5', stand).fehler, /ganze Zahl/)
  assert.match(G.eingabePruefen('abc', stand).fehler, /ganze Zahl/)
  assert.match(G.eingabePruefen('', stand).fehler, /ganze Zahl/)
  assert.match(G.eingabePruefen(' ', stand).fehler, /ganze Zahl/, 'Leerzeichen sind leer, nicht 0')
  assert.equal(G.eingabePruefen('  30  ', stand).ok, true, 'Leerraum um die Zahl stört nicht')
  // Servergrenzen werden übernommen, wenn sie mitkommen.
  const eng = G.standLesen({ anhang_max_mb: 5, standard: 10, minimum: 2, maximum: 20 })
  assert.match(G.eingabePruefen('25', eng).fehler, /zwischen 2 und 20/)
})

test('CHAT-12c-UI/B: Nutzlast `anhang_max_mb`, „geändert“ erkennt den Unterschied', () => {
  assert.deepEqual(G.speicherNutzlast('30'), { anhang_max_mb: 30 })
  assert.deepEqual(G.speicherNutzlast(30), { anhang_max_mb: 30 })
  const stand = G.standLesen({ anhang_max_mb: 25, standard: 10, minimum: 1, maximum: 50 })
  assert.equal(G.geaendert('25', stand), false)
  assert.equal(G.geaendert('30', stand), true)
})

test('CHAT-12c-UI/B: Server-Fehler wird gezeigt, 403 ruhig erklärt', () => {
  const fehler = new Error('Anhanggröße muss zwischen 1 und 50 MB liegen.')
  fehler.status = 422
  assert.equal(G.speicherFehlerText(fehler), 'Anhanggröße muss zwischen 1 und 50 MB liegen.')
  const verboten = new Error('Kein Zugriff')
  verboten.status = 403
  assert.equal(G.speicherFehlerText(verboten), 'Nur die Administration darf die Anhangsgröße ändern.')
  assert.equal(G.speicherFehlerText({}), 'Die Anhangsgröße konnte nicht gespeichert werden.')
})

// ════════════════════════════════════════════════════════════════════════════
// C · Fristen.vue gemountet — das Feld in den Admin-Einstellungen
// ════════════════════════════════════════════════════════════════════════════

/** Eine Antwort, wie `chat.fristen_lesen` sie liefert (unverändert aus CHAT-8). */
function fristenAntwort(überschreiben = {}) {
  return {
    chat_frist_gruppe_monate: 24,
    chat_frist_direkt_monate: 12,
    standard: { gruppe: 24, direkt: 12 },
    minimum: 1,
    maximum: 120,
    nachricht_monate: 6,
    umfrage_stimmen_monate: 6,
    meldung_monate: 12,
    ...überschreiben,
  }
}

async function einstellungenMontieren({ server = {} } = {}) {
  const ordner = join(TMP, 'einst-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  const api = join(ordner, 'api.mjs')
  writeFileSync(api, [
    'export async function apiCall(methode, parameter) {',
    '  globalThis.__PUSH({ methode, parameter })',
    '  return globalThis.__SERVER({ methode, parameter })',
    '}',
    'export const apiGet = apiCall',
  ].join('\n'))
  const U2 = (rel) => pathToFileURL(SRC.pathname + rel).href
  umleitung.clear()
  umleitung.set(U2('composables/useApi.js'), pathToFileURL(api).href)

  const aufrufe = []
  globalThis.__PUSH = (eintrag) => aufrufe.push(eintrag)
  globalThis.__SERVER = ({ methode, parameter }) => {
    const kurz = String(methode).split('.').pop()
    if (typeof server[kurz] === 'function') return server[kurz](parameter)
    if (kurz === 'fristen_lesen') return fristenAntwort()
    if (kurz === 'fristen_speichern') return { ...fristenAntwort(parameter), gespeichert: true }
    if (kurz === 'chat_einstellungen_lesen') {
      return { anhang_max_mb: 25, standard: 10, minimum: 1, maximum: 50 }
    }
    if (kurz === 'chat_einstellungen_speichern') {
      return { anhang_max_mb: parameter?.anhang_max_mb, gespeichert: true,
        standard: 10, minimum: 1, maximum: 50 }
    }
    return {}
  }

  const mod = (await import(pathToFileURL(baum('pages/einstellungen/Fristen.vue', { frisch: true, ordner })).href)).default
  const s = await mounten(mod)
  await rendern(6)
  await warte(14)
  await rendern(6)
  return { ...s, aufrufe }
}

test('CHAT-12c-UI/C: das Feld „Höchstgröße je Anhang“ steht da — Wert, Standard, Grenzen', async () => {
  const s = await einstellungenMontieren()
  assert.match(s.host.textContent, /Nachrichten aufbewahren/, 'der Abschnitt steht')
  const feld = feldUeberLabel(s.host, 'Höchstgröße je Anhang')
  assert.ok(feld, 'das Feld ist mit seinem Label verbunden')
  assert.equal(feld.type, 'number')
  assert.equal(feld.value, '25', 'der gespeicherte Wert, nicht der Standard')
  assert.equal(feld.getAttribute('min'), '1')
  assert.equal(feld.getAttribute('max'), '50')
  assert.equal(feld.getAttribute('step'), '1')
  assert.match(s.host.textContent, /gilt für Anhänge im Chat/, 'der Hinweis der Karte')
  assert.match(s.host.textContent, /Standard: 10 MB/)
  // Sprungmarke der Einstellungen-Suche — die Kennung steht im Markup.
  assert.deepEqual(
    [...s.host.querySelectorAll('.dk-ui-field')].map((e) => e.id),
    ['dk-sprung-gruppe', 'dk-sprung-direkt', 'dk-sprung-anhang'],
  )
  // Der Lesen-Aufruf ist der des Backends (Chat-12c, nicht die Fristen).
  assert.ok(s.aufrufe.some((a) => a.methode === 'diakronos_app.api.chat.chat_einstellungen_lesen'),
    'die Einstellung wird über ihren eigenen Endpunkt gelesen')
  assert.equal(s.warnungen.length, 0, s.warnungen.join(' | '))
  s.abbaum()
})

test('CHAT-12c-UI/C: Speichern schickt `anhang_max_mb` an chat.chat_einstellungen_speichern', async () => {
  const s = await einstellungenMontieren()
  const feld = feldUeberLabel(s.host, 'Höchstgröße je Anhang')
  await fuellen(feld, '30')
  await rendern(4)
  klick(knopf(s.host, /^Speichern$/))
  await rendern(8)
  await warte(14)
  await rendern(6)
  const ruf = s.aufrufe.filter((a) => /chat_einstellungen_speichern$/.test(a.methode)).at(-1)
  assert.ok(ruf, 'chat.chat_einstellungen_speichern wurde gerufen')
  assert.deepEqual(ruf.parameter, { anhang_max_mb: 30 })
  assert.match(s.host.textContent, /Gespeichert/, 'die Rückmeldung steht da')
  assert.equal(feldUeberLabel(s.host, 'Höchstgröße je Anhang').value, '30')
  // Die Fristen wurden NICHT mitgesendet (nichts geändert).
  assert.equal(s.aufrufe.filter((a) => /fristen_speichern$/.test(a.methode)).length, 0)
  // Und kein zweiter Ladevorgang (der Stand kommt aus der Antwort).
  assert.equal(s.aufrufe.filter((a) => /chat_einstellungen_lesen$/.test(a.methode)).length, 1)
  s.abbaum()
})

test('CHAT-12c-UI/C: ein ungültiger Wert geht NICHT hinaus und wird am Feld gesagt', async () => {
  const s = await einstellungenMontieren()
  const feld = feldUeberLabel(s.host, 'Höchstgröße je Anhang')
  await fuellen(feld, '51')
  await rendern(4)
  assert.match(s.host.textContent, /zwischen 1 und 50/)
  klick(knopf(s.host, /^Speichern$/))
  await rendern(8)
  assert.equal(s.aufrufe.filter((a) => /chat_einstellungen_speichern$/.test(a.methode)).length, 0,
    'kein Aufruf mit einem Wert außerhalb des Bereichs')
  assert.equal(feld.getAttribute('aria-invalid'), 'true', 'das Feld weiß, dass es nicht stimmt')
  s.abbaum()
})

test('CHAT-12c-UI/C: die Server-Meldung steht am Feld', async () => {
  const s = await einstellungenMontieren({
    server: {
      chat_einstellungen_speichern: () => {
        const fehler = new Error('Anhanggröße muss zwischen 1 und 50 MB liegen.')
        fehler.status = 422
        throw fehler
      },
    },
  })
  await fuellen(feldUeberLabel(s.host, 'Höchstgröße je Anhang'), '30')
  await rendern(4)
  klick(knopf(s.host, /^Speichern$/))
  await rendern(8)
  await warte(14)
  await rendern(6)
  assert.match(s.host.textContent, /Anhanggröße muss zwischen 1 und 50 MB liegen\./,
    'die Meldung des Servers, nicht eine eigene Behauptung')
  s.abbaum()
})

test('CHAT-12c-UI/C: ein 403 bleibt ruhig an der Seite', async () => {
  const s = await einstellungenMontieren({
    server: {
      chat_einstellungen_speichern: () => {
        const fehler = new Error('Kein Zugriff')
        fehler.status = 403
        throw fehler
      },
    },
  })
  await fuellen(feldUeberLabel(s.host, 'Höchstgröße je Anhang'), '30')
  await rendern(4)
  klick(knopf(s.host, /^Speichern$/))
  await rendern(8)
  await warte(14)
  await rendern(6)
  assert.match(s.host.textContent, /Nur die Administration darf die Anhangsgröße ändern\./)
  assert.ok(feldUeberLabel(s.host, 'Höchstgröße je Anhang'), 'das Formular bleibt stehen')
  assert.equal(s.warnungen.length, 0, s.warnungen.join(' | '))
  s.abbaum()
})

test('CHAT-12c-UI/C: „Höchstgröße auf Standard“ füllt den Standardwert', async () => {
  const s = await einstellungenMontieren()
  const zurueck = knopf(s.host, /Höchstgröße auf Standard/)
  assert.ok(zurueck, 'der Knopf steht da')
  assert.equal(zurueck.disabled, false, '25 ist nicht der Standard — der Knopf ist bedienbar')
  klick(zurueck)
  await warte(4)
  await rendern(6)
  assert.equal(feldUeberLabel(s.host, 'Höchstgröße je Anhang').value, '10')
  s.abbaum()
})

// ════════════════════════════════════════════════════════════════════════════
// D · Nachrichten.vue gemountet — die Grenze der Chat-Seite
// ════════════════════════════════════════════════════════════════════════════

const GESPRAECH = { kennung: 'CHAT-2', art: 'gruppe', anzeigename: 'Chor', ungelesen: 0 }
const VERLAUF = [{
  name: 'N-1', gespraech: 'CHAT-2', text: 'Hallo', absender: 'M-1', absendername: 'Anna',
  zeit: '2026-11-21T10:00:00+01:00', eigene: true, anhaenge: [],
}]

async function chatMontieren({ anhangMaxBytes = 25 * MB, ohneFeld = false } = {}) {
  const ordner = join(TMP, 'chat-' + Math.random().toString(36).slice(2))
  mkdirSync(ordner, { recursive: true })
  const aufrufe = []
  const uploads = []
  const api = join(ordner, 'api.mjs')
  writeFileSync(api, [
    'export async function apiCall(methode, parameter) {',
    '  globalThis.__PUSH({ methode, parameter })',
    '  return globalThis.__SERVER({ methode, parameter })',
    '}',
    'export async function apiGet(methode, parameter) {',
    '  globalThis.__PUSH({ methode, parameter })',
    '  return globalThis.__SERVER({ methode, parameter })',
    '}',
    'export const apiUrl = (p) => "/diakonos/api/method/" + p',
    'export class AuditConfirmationRequired extends Error {}',
    'export const pruefeSitzungsAntwort = () => false',
    'export const apiAntwortPruefen = async (res) => res.__daten || {}',
  ].join('\n'))
  const session = join(ordner, 'session.mjs')
  writeFileSync(session, [
    `import { ref } from '${VUE_URL}'`,
    'export function useSession() {',
    '  return { mitglied: ref({ name: "M-0" }), istMitgliederverwaltung: ref(false),',
    '    istAdministrator: ref(false), roles: ref([]) }',
    '}',
  ].join('\n'))
  const U = (rel) => pathToFileURL(SRC.pathname + rel).href
  umleitung.clear()
  umleitung.set(U('composables/useApi.js'), pathToFileURL(api).href)
  umleitung.set(U('composables/useSession.js'), pathToFileURL(session).href)

  globalThis.__PUSH = (e) => aufrufe.push(e)
  globalThis.__SERVER = async ({ methode }) => {
    const kurz = String(methode).split('.').pop()
    if (kurz === 'meine_gespraeche') {
      return ohneFeld
        ? { gespraeche: [GESPRAECH] }
        : { gespraeche: [GESPRAECH], anhang_max_bytes: anhangMaxBytes }
    }
    if (kurz === 'verlauf') return { richtung: 'neueste', nachrichten: VERLAUF }
    if (kurz === 'nachrichten_suchen') return { treffer: [], mehr: false, vor: null }
    if (kurz === 'lesestand_setzen') return { ungelesen: 0 }
    if (kurz === 'meine_sperren') return { sperren: [] }
    if (kurz === 'senden') return VERLAUF[0]
    return {}
  }
  const echtesFetch = globalThis.fetch
  globalThis.fetch = async (url, optionen = {}) => {
    const form = optionen.body
    const felder = {}
    if (form && typeof form.forEach === 'function') {
      form.forEach((wert, schluessel) => { felder[schluessel] = wert })
    }
    uploads.push({ url: String(url), felder })
    return {
      ok: true, status: 200,
      __daten: { message: { name: `CHAT-A-${uploads.length}`, dateiname: felder.datei?.name || '',
        mime: felder.datei?.type || '', groesse: felder.datei?.size || 0 } },
      async text() { return '' },
    }
  }
  dom.window.__DIakonosBOOT = { roles: ['Mitglied'], is_admin: false, module_sichtbar: ['chat'] }
  dom.window.location.hash = '#/nachrichten/CHAT-2'
  dom.window.matchMedia = (abfrage) => ({
    media: String(abfrage), matches: false,
    addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {},
  })
  const mod = (await import(pathToFileURL(baum('pages/Nachrichten.vue', { ordner, frisch: true })).href)).default
  const m = await mounten(mod)
  for (let i = 0; i < 15; i += 1) { await warte(8); await rendern(4) }
  return {
    ...m,
    aufrufe,
    uploads,
    abbaum: () => { globalThis.fetch = echtesFetch; m.abbaum() },
  }
}

function dateiEcht(name, groesse, typ = 'image/jpeg') {
  const d = new dom.window.File([new Uint8Array(Math.min(groesse, 64))], name, { type: typ })
  Object.defineProperty(d, 'size', { configurable: true, value: groesse })
  return d
}

const auswaehlen = async (host, dateien) => {
  const feld = host.querySelector('input[type="file"]')
  assert.ok(feld, 'das Dateifeld steht im DOM')
  Object.defineProperty(feld, 'files', { configurable: true, value: dateien })
  feld.dispatchEvent(new dom.window.Event('change', { bubbles: true }))
  for (let i = 0; i < 12; i += 1) { await warte(6); await rendern(3) }
}

test('CHAT-12c-UI/D: 25 MB eingestellt → 20-MB-Datei geht durch', async () => {
  const s = await chatMontieren({ anhangMaxBytes: 25 * MB })
  await auswaehlen(s.host, [dateiEcht('zwanzig.jpg', 20 * MB)])
  assert.equal(s.uploads.length, 1, 'die Datei wurde hochgeladen (nicht vorab abgewiesen)')
  assert.equal(s.host.querySelector('.dk-chat-fehler'), null, 'keine Fehlermeldung')
  s.abbaum()
})

test('CHAT-12c-UI/D: 25 MB eingestellt → 26-MB-Datei abgewiesen mit „25 MB“', async () => {
  const s = await chatMontieren({ anhangMaxBytes: 25 * MB })
  await auswaehlen(s.host, [dateiEcht('sechsundzwanzig.jpg', 26 * MB)])
  assert.equal(s.uploads.length, 0, 'kein Upload einer zu großen Datei')
  const meldung = s.host.querySelector('.dk-chat-fehler')
  assert.ok(meldung, 'es steht eine Meldung da')
  assert.match(meldung.textContent, /zu groß/)
  assert.match(meldung.textContent, /max\. 25 MB/, 'die ECHTE Zahl aus der Einstellung')
  s.abbaum()
})

test('CHAT-12c-UI/D: ohne Serverwert gilt der Standard 10 MB', async () => {
  const s = await chatMontieren({ ohneFeld: true })
  await auswaehlen(s.host, [dateiEcht('zwanzig.jpg', 20 * MB)])
  assert.equal(s.uploads.length, 0, 'ohne Serverwert wird gegen 10 MB geprüft')
  const meldung = s.host.querySelector('.dk-chat-fehler')
  assert.ok(meldung)
  assert.match(meldung.textContent, /max\. 10 MB/)
  // Genau 10 MB geht noch durch.
  await auswaehlen(s.host, [dateiEcht('zehn.jpg', 10 * MB)])
  assert.equal(s.uploads.length, 1, 'die Grenze selbst ist erlaubt')
  s.abbaum()
})

// ════════════════════════════════════════════════════════════════════════════
// E · Grenzen des Umbaus (Wächter: keine zweite Adresse, keine px)
// ════════════════════════════════════════════════════════════════════════════

test('CHAT-12c-UI/E: alle Importe der neuen und geänderten Dateien existieren wirklich', () => {
  // Lehre Sammel 10: die Tests ersetzen useApi.js durch einen Stub — ein
  // Import, den es nicht gibt, fällt erst im Build auf. Deshalb hier gegen die
  // ECHTEN Exporte prüfen. Geprüft werden die NAMEN der neuen Haus-Module
  // (die Seite selbst zieht viele alte Importe mit; die sind nicht Thema
  // dieser Karte).
  const namenIn = (rel) => {
    const quelle = readFileSync(resolve(SRC.pathname + rel), 'utf8')
    const namen = new Set()
    for (const m of quelle.matchAll(/^export\s+(?:async\s+)?function\s+([A-Za-z0-9_$]+)/gm)) namen.add(m[1])
    for (const m of quelle.matchAll(/^export\s+(?:const|let|class)\s+([A-Za-z0-9_$]+)/gm)) namen.add(m[1])
    for (const m of quelle.matchAll(/^export\s*\{([^}]*)\}/gm)) {
      for (const teil of m[1].split(',')) {
        const name = teil.trim().split(/\s+as\s+/).pop()?.trim()
        if (name) namen.add(name)
      }
    }
    return namen
  }
  // Die Erwartungen sind der Vertrag der beiden neuen Regeln-Module.
  const anhaenge = namenIn('components/chat/anhaenge.mjs')
  for (const name of ['anhangMaxBytes', 'mbText', 'auswahlPruefen', 'ANHANG_MAX_BYTES', 'ANHANG_MAX_MB']) {
    assert.ok(anhaenge.has(name), `anhaenge.mjs exportiert ${name}`)
  }
  const groesse = namenIn('pages/einstellungen/anhanggroesse.mjs')
  for (const name of ['standLesen', 'eingabePruefen', 'feldText', 'standardText',
    'standardHinweis', 'speicherNutzlast', 'geaendert', 'speicherFehlerText']) {
    assert.ok(groesse.has(name), `anhanggroesse.mjs exportiert ${name}`)
  }
  // Und die SEITE importiert genau diese Namen — zeilenweise, weil die
  // Import-Blöcke im Haus über mehrere Zeilen stehen. Ein Name, den das Ziel
  // nicht exportiert, würde hier auffallen (und erst recht im Build).
  for (const [rel, ziel, pfadMuster] of [
    ['pages/Nachrichten.vue', 'components/chat/anhaenge.mjs', /chat\/anhaenge\.mjs/],
    ['pages/einstellungen/Fristen.vue', 'pages/einstellungen/anhanggroesse.mjs', /\.\/anhanggroesse\.mjs/],
  ]) {
    const quelle = readFileSync(resolve(SRC.pathname + rel), 'utf8')
    const zeilen = quelle.split('\n')
    let gefunden = false
    for (let i = 0; i < zeilen.length; i += 1) {
      if (!/^\s*import\s*\{/.test(zeilen[i])) continue
      let block = ''
      let j = i
      while (j < zeilen.length && !/\}\s*from\s*'\./.test(block)) {
        block += (block ? '\n' : '') + zeilen[j]
        j += 1
      }
      const m = /import\s*\{([\s\S]*?)\}\s*from\s*'(\.[^']+)'/.exec(block)
      if (!m || !pfadMuster.test(m[2])) continue
      gefunden = true
      for (const teil of m[1].split(',')) {
        const name = teil.trim().split(/\s+as\s+/)[0].trim()
        if (!name) continue
        assert.ok(namenIn(ziel).has(name),
          `${rel} importiert „${name}“ — ${ziel} exportiert es nicht`)
      }
      // Der neue Name dieser Karte in der Chat-Seite steht im Import.
      if (rel === 'pages/Nachrichten.vue') {
        assert.match(m[1], /anhangMaxBytes/, 'die Chat-Seite holt die Grenze aus anhaenge.mjs')
      }
    }
    assert.ok(gefunden, `${rel} importiert aus ${ziel}`)
  }
})

test('CHAT-12c-UI/E: keine festen px-Werte in den berührten Bausteinen', () => {
  for (const rel of ['components/chat/anhaenge.mjs', 'pages/einstellungen/anhanggroesse.mjs']) {
    assert.doesNotMatch(lies(rel), /:\s*[^;{}]*\b\d+px\b/, `${rel}: nur Tokens`)
  }
  // Die Gestaltung von Fristen.vue ist unverändert; geprüft werden die
  // DEKLARATIONEN (nicht die Kommentare, in denen „44 px“ als Begründung
  // steht) und kein neues Maß.
  const stil = (lies('pages/einstellungen/Fristen.vue').split('<style')[1] || '')
    .replace(/\/\*[\s\S]*?\*\//g, '')
    // Die vorhandene Handy-Regel (`@media (max-width: 720px)`) ist ein
    // BREAKPOINT, kein Abstand — der Wächter ux1a prüft Abstände, nicht
    // Haltepunkte. Er bleibt, wie er war.
    .replace(/@media\s*\([^)]*\)/g, '@media')
  assert.doesNotMatch(stil, /:\s*[^;{}]*\b\d+px\b/, 'Fristen.vue: Abstände aus Tokens')
})

test('CHAT-12c-UI/E: das Feld nutzt den Endpunkt des Backends über apiCall, nicht eine eigene Adresse', () => {
  const seite = lies('pages/einstellungen/Fristen.vue')
  assert.match(seite, /apiCall\('diakronos_app\.api\.chat\.chat_einstellungen_lesen'/)
  assert.match(seite, /apiCall\(\s*'diakronos_app\.api\.chat\.chat_einstellungen_speichern'/)
  assert.doesNotMatch(seite, /fetch\(|XMLHttpRequest|\/api\/method\//,
    'keine zweite Adress-Logik neben apiCall')
  // Die Chat-Seite liest die Grenze aus der Antwort, die sie ohnehin lädt.
  const chat = lies('pages/Nachrichten.vue')
  assert.match(chat, /anhangGrenze\.value = anhangMaxBytes\(antwort\)/)
  assert.doesNotMatch(chat, /apiGet\('chat\.chat_einstellungen_lesen'\)|chat\.chat_einstellungen_lesen/,
    'kein zweiter Rundlauf für die Grenze')
})

test('CHAT-12c-UI/E: Die Einstellungen-Suche findet das neue Feld', async () => {
  const S = await import(new URL('pages/einstellungen/suche.mjs', SRC).href)
  assert.deepEqual(S.FELDER.fristen.map((f) => f.id), ['gruppe', 'direkt', 'anhang'])
  assert.equal(S.trefferFelder('fristen', 'Höchstgröße').length, 1)
  assert.equal(S.trefferFelder('fristen', 'Anhang').length, 1)
  assert.equal(S.STICHWORTE.fristen.includes('Höchstgröße'), true)
})
