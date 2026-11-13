/**
 * MT-5b — Der Leerzustand des Kalenders wird beim Verlassen der Seite abgebaut.
 *
 * Befund (Review MT-5, Opus): `leerzustandKnoten()` in `KronosCalendar.vue`
 * baute je Seitenbesuch eine EIGENE Vue-App für `DkEmpty` (`createApp`), die
 * nie abgebaut wurde. Die Bibliothek räumt beim `destroy()` nur ihr DOM ab —
 * die App samt reaktiver Hülle blieb zurück (kleines Leck je Besuch).
 *
 * GEPRÜFT WIRD AM VERHALTEN, nicht am Quelltext: `KronosCalendar.vue` wird
 * wie im Betrieb gebaut (`vue/compiler-sfc` → `createApp().mount()` in jsdom);
 * nur die Kalender-Bibliothek ist eine Attrappe. Sie bekommt über
 * `noEventsContent` genau die Knoten, die der Baustein übergibt, hängt sie in
 * einen Kasten (`.ec-no-events`) — wie das Listen-Plugin es tut — und baut
 * beim `destroy()` nur ihr DOM ab. Ob die Vue-App des Leerzustands lebt,
 * zeigt der GERENDERTE Baum: Vue kennzeichnet gebundene Knoten mit
 * `_vei`/`_vnode`; `unmount()` entfernt sie.
 *
 *   1. Beim Aufbau steht der Leerzustand da (Anatomie und Text von DkEmpty) —
 *      die Messung hat also eine echte Grundlage.
 *   2. `unmount()` des Bausteins baut die Leerzustand-App ab: der Halter
 *      trägt danach keinen Vue-Knoten mehr (kein Leck je Seitenbesuch).
 *   3. Der Baustein legt KEINEN `config.warnHandler` ohne Begründung an —
 *      Vue-Warnungen bleiben sichtbar (Review MT-5, Punkt 2).
 *
 * Der Test liest NUR Dateien innerhalb von frontend/ (Regel 13), braucht kein
 * Netz und keine echte Bibliothek.
 *
 * Lauf: node --test tests/mt5b-leerzustand-abbau.test.mjs   (cwd = frontend/)
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, mkdtempSync, writeFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, dirname, resolve, basename } from 'node:path'
import { pathToFileURL, fileURLToPath } from 'node:url'
import { JSDOM } from 'jsdom'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'

// ── jsdom als Dokument (Vue greift beim Import darauf zu) ─────────────────
const dom = new JSDOM('<!doctype html><html><body></body></html>', {
  url: 'http://localhost/#/kalender',
  pretendToBeVisual: true,
})
const W = dom.window
globalThis.window = W
globalThis.document = W.document
try { globalThis.navigator = W.navigator } catch { /* Node hat ein eigenes */ }
for (const schluessel of ['Node', 'Element', 'HTMLElement', 'SVGElement', 'Event',
  'MouseEvent', 'KeyboardEvent', 'CustomEvent', 'CSS', 'getComputedStyle', 'MutationObserver',
  'ResizeObserver', 'IntersectionObserver', 'localStorage', 'sessionStorage']) {
  if (W[schluessel]) globalThis[schluessel] = W[schluessel]
}
globalThis.getComputedStyle = W.getComputedStyle.bind(W)
globalThis.requestAnimationFrame = (fn) => W.setTimeout(() => fn(Date.now()), 0)
globalThis.cancelAnimationFrame = (id) => W.clearTimeout(id)
W.matchMedia = (abfrage) => ({
  matches: false,
  media: abfrage,
  addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {},
})

const Vue = await import('vue')

const hier = dirname(fileURLToPath(import.meta.url))
const FRONTEND = resolve(hier, '..')
const SRC = join(FRONTEND, 'src', 'diakonos')
const lies = (rel) => readFileSync(join(SRC, rel), 'utf8')

// ══════════════════════════════════════════════════════════════════════════
// Attrappe der Kalender-Bibliothek
// ══════════════════════════════════════════════════════════════════════════
/**
 * `EventCalendar.create(el, optionen)` legt einen Kasten an, hängt die
 * übergebenen `noEventsContent`-Knoten hinein (Bundle: `t.replaceChildren(…
 * e.domNodes)`) und merkt die Optionen. `destroy()` entfernt NUR den Kasten —
 * die Knoten selbst und ihre Vue-App sind Sache des Bausteins (genau das ist
 * der geprüfte Punkt).
 */
const BIBLIOTHEK = `
export const __bibliothek = { aufbauten: [] }
function create(el, optionen) {
  const kasten = el.ownerDocument.createElement('div')
  kasten.className = 'ec ec-list'
  const leer = el.ownerDocument.createElement('div')
  leer.className = 'ec-no-events'
  const knoten = optionen?.noEventsContent?.domNodes || []
  leer.replaceChildren(...knoten)
  kasten.appendChild(leer)
  el.replaceChildren(kasten)
  const eintrag = { el, optionen, kasten, zerstoert: false }
  __bibliothek.aufbauten.push(eintrag)
  return {
    setOption() {},
    getOption: (name) => optionen?.[name],
    destroy() {
      eintrag.zerstoert = true
      kasten.remove()
    },
    next() {}, prev() {}, today() {}, gotoDate() {}, changeView() {}, refetchEvents() {},
  }
}
export default { create }
`

// ── SFC → ES-Module (Temp-Verzeichnis) ────────────────────────────────────
const TMP = mkdtempSync(join(tmpdir(), 'mt5b-'))
const cache = new Map()
const VUE_URL = import.meta.resolve('vue')

const ERSATZ = new Map([
  ['@event-calendar/build', BIBLIOTHEK],
  ['@event-calendar/build/dist/event-calendar.min.css', ''],
])

function fremdesModul(spec) {
  if (!ERSATZ.has(spec)) return null
  const datei = resolve(TMP, 'ersatz-' + spec.replace(/[^a-z0-9]+/gi, '-') + '.mjs')
  if (!cache.has(datei)) {
    writeFileSync(datei, ERSATZ.get(spec) + '\n')
    cache.set(datei, datei)
  }
  return datei
}

function kompilieren(abs) {
  if (cache.has(abs)) return cache.get(abs)
  const filename = basename(abs)
  const { descriptor, errors } = parse(readFileSync(abs, 'utf8'), { filename })
  assert.deepEqual(errors, [], filename + ': SFC-Struktur')
  const script = compileScript(descriptor, { id: filename.replace(/\W/g, '_') })
  const tpl = compileTemplate({
    source: descriptor.template.content,
    filename,
    id: filename.replace(/\W/g, '_'),
    compilerOptions: { bindingMetadata: script.bindings },
  })
  assert.deepEqual(tpl.errors.map(String), [], filename + ': Vorlage')
  let code = script.content.replace(/\nexport default /, '\nconst __sfc__ = ')
  code += '\n' + tpl.code.replace(/^export function render/m, 'function render')
  code += '\n__sfc__.render = render\nexport default __sfc__\n'
  code = code.replace(/from\s+['"]vue['"]/g, `from '${VUE_URL}'`)
  code = code.replace(/from\s+['"]([^'"]+)['"]/g, (voll, spec) => {
    if (spec.startsWith('.')) {
      const ziel = resolve(dirname(abs), spec)
      return `from '${pathToFileURL(spec.endsWith('.vue') ? kompilieren(ziel) : ziel).href}'`
    }
    const ersatz = fremdesModul(spec)
    return ersatz ? `from '${pathToFileURL(ersatz).href}'` : voll
  })
  code = code.replace(/^import\s+['"]([^'"]+)['"];?$/gm, (ganz, spec) => {
    const ersatz = fremdesModul(spec)
    return ersatz ? `import '${pathToFileURL(ersatz).href}';` : ganz
  })
  const zielDatei = resolve(TMP, filename.replace(/\.\w+$/, '') + '.' + cache.size + '.mjs')
  writeFileSync(zielDatei, code)
  cache.set(abs, zielDatei)
  return zielDatei
}

test.after(() => rmSync(TMP, { recursive: true, force: true }))

// ── Datenquellen des Bausteins ────────────────────────────────────────────
/** Leere, gültige Antworten — gemessen wird der Leerzustand, nicht Termine. */
globalThis.fetch = async () => ({
  ok: true,
  status: 200,
  headers: { get: () => 'application/json' },
  text: async () => JSON.stringify({ message: [] }),
  json: async () => ({ message: [] }),
})

const tick = () => new Promise((loese) => setTimeout(loese, 0))
const warten = (ms = 200) => new Promise((loese) => setTimeout(loese, ms))

/** Den Baustein wie im Betrieb montieren. */
async function bausteinMounten() {
  document.body.innerHTML = ''
  const bausteinModul = await import(pathToFileURL(
    kompilieren(join(SRC, 'components/kronos/KronosCalendar.vue')),
  ).href)
  const bibliothek = await import(pathToFileURL(fremdesModul('@event-calendar/build')).href)

  const host = document.createElement('div')
  document.body.appendChild(host)
  const warnungen = []
  const app = Vue.createApp({ components: { Kalender: bausteinModul.default }, template: '<Kalender />' })
  app.config.warnHandler = (meldung) => warnungen.push(String(meldung))
  app.config.errorHandler = (fehler) => warnungen.push(String(fehler))
  app.mount(host)
  await tick()
  await warten()
  return { app, host, bibliothek, warnungen }
}

/** Der Halter des Leerzustands im Kasten der Bibliothek. */
function leerkasten() {
  return document.querySelector('.ec-no-events .dk-kalender-leer')
}

const text = (el) => (el?.textContent || '').replace(/\s+/g, ' ').trim()

/** Trägt der Knoten noch Vue-Bindungen? (`_vei` = Zuhörer, `_vnode` = VNode) */
function vueGebunden(knoten) {
  if (!knoten) return false
  const alle = [knoten, ...knoten.querySelectorAll('*')]
  return alle.some((el) => el._vei || el._vnode || el.__vnode)
}

// ══════════════════════════════════════════════════════════════════════════
// 1 · Beim Aufbau steht der Leerzustand da (Anatomie von DkEmpty)
// ══════════════════════════════════════════════════════════════════════════
test('MT-5b · 1: der Leerzustand ist beim Aufbau echte DkEmpty-Gestalt', async () => {
  const { app, bibliothek, warnungen } = await bausteinMounten()
  try {
    assert.equal(bibliothek.__bibliothek.aufbauten.length, 1, 'die Bibliothek wurde aufgebaut')
    const halter = leerkasten()
    assert.ok(halter, 'die übergebenen DOM-Knoten wurden in den Leerkasten eingehängt')
    assert.equal(text(halter.querySelector('.dk-ui-empty-title')), 'Keine Termine',
      'der Leerzustand ist der App-Baustein DkEmpty')
    assert.equal(text(halter.querySelector('.dk-ui-empty-text')),
      'In diesem Zeitraum ist nichts eingetragen.')
    assert.ok(vueGebunden(halter), 'die App-Instanz ist während der Anzeige lebendig')
    assert.deepEqual(warnungen, [], 'Vue meldet beim Aufbau kein Problem')
  } finally {
    app.unmount()
  }
})

// ══════════════════════════════════════════════════════════════════════════
// 2 · Unmount baut die Leerzustand-App ab (kein Leck je Seitenbesuch)
// ══════════════════════════════════════════════════════════════════════════
test('MT-5b · 2: unmount() des Bausteins baut die Leerzustand-App ab', async () => {
  const { app, bibliothek } = await bausteinMounten()
  const halter = leerkasten()
  assert.ok(halter, 'Leerzustand steht vor dem Unmount')
  assert.ok(vueGebunden(halter), 'vor dem Unmount hängt die Vue-App am Halter')

  app.unmount()
  await tick()

  // Die Bibliothek hat ihren Kasten mit `destroy()` abgeräumt …
  assert.equal(bibliothek.__bibliothek.aufbauten[0].zerstoert, true, 'die Bibliothek wurde abgebaut')
  // … und der Halter trägt KEINE Vue-Bindung mehr: die Leerzustand-App ist
  // abgebaut, nicht nur aus dem Baum genommen.
  assert.equal(vueGebunden(halter), false,
    'die Leerzustand-App lebt nach dem Unmount weiter (Vue-Knoten noch am Halter)')
  assert.equal(halter.textContent, '', 'der abgebaute Halter ist leer')
})

// ══════════════════════════════════════════════════════════════════════════
// 3 · Kein verschluckender warnHandler ohne Begründung
// ══════════════════════════════════════════════════════════════════════════
test('MT-5b · 3: der Baustein legt keinen leeren config.warnHandler an', () => {
  const q = lies('components/kronos/KronosCalendar.vue')
  assert.ok(!/warnHandler/.test(q),
    'KronosCalendar setzt keinen warnHandler mehr (Vue-Warnungen bleiben sichtbar)')
  // Der Leerzustand baut seine App an EINER Stelle; das Abräumen gehört zum
  // Unmount-Haken.
  const ab = q.slice(q.indexOf('onBeforeUnmount('))
  assert.match(ab.slice(0, ab.indexOf('\n})')),
    /leerzustandAppAbbauen\(\)/, 'onBeforeUnmount baut die Leerzustand-App ab')
})
