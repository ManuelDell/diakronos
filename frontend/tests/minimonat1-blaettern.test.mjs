/**
 * MINIMONAT-1 — Handy-Kalender (Liste, A10): Mini-Monat blättert nicht.
 *
 * Befund (am Code gemessen, vom Review bestätigt): die A10-Liste reichte
 * `@zurueck`/`@vor` an `calendarRef.prev()/next()` weiter — den Halter des
 * RASTERS. Der Raster-Baustein hängt an `v-else` zur Liste, ist in der
 * Listenansicht also NICHT gemountet; `calendarRef` ist dort `null`, und der
 * Tipp tat lautlos nichts. Die Seite rechnet den Monatsschritt deshalb selbst
 * (`schrittMitTag` in `mobilAnsicht.mjs`).
 *
 * Geprüft wird das VERHALTEN: die Rechnung (Monat + geklemmter Tag), die
 * verdrahtete Listenansicht (Pfeil ändert Monat UND Tag, genau EIN Laden des
 * neuen Zeitraums) und der Laufzähler der Terminquelle (eine späte Antwort
 * eines alten Laufs überschreibt den neuen nicht). Der Desktop-Mini-Monat
 * (`KronosMiniCalendar`) hat eigene Pfeile und bleibt unberührt.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, mkdtempSync, writeFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, dirname, resolve, basename } from 'node:path'
import { pathToFileURL, fileURLToPath } from 'node:url'
import { JSDOM } from 'jsdom'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'

const hier = dirname(fileURLToPath(import.meta.url))
const FRONTEND = resolve(hier, '..')
const SRC = join(FRONTEND, 'src', 'diakonos')
const lies = (rel) => readFileSync(join(SRC, rel), 'utf8')
const seite = () => lies('pages/Kalender.vue')

const M = await import(pathToFileURL(join(SRC, 'components/kronos/mobilAnsicht.mjs')).href)

// ══════════════════════════════════════════════════════════════════════════
// 1 · Die Rechnung: Monat UND mitwandernder, geklemmter Tag
// ══════════════════════════════════════════════════════════════════════════
test('MINIMONAT-1 · 1: schrittMitTag blättert Monat und klemmt den Tag', () => {
  // Über die Jahresgrenze, in beide Richtungen.
  assert.deepEqual(M.schrittMitTag('2026-11', '2026-11-13', 1), { monat: '2026-12', tag: '2026-12-13' })
  assert.deepEqual(M.schrittMitTag('2026-12', '2026-12-15', 1), { monat: '2027-01', tag: '2027-01-15' })
  assert.deepEqual(M.schrittMitTag('2026-01', '2026-01-10', -1), { monat: '2025-12', tag: '2025-12-10' })
  // Der Tag darf nie über den Zielmonat hinausragen.
  assert.deepEqual(M.schrittMitTag('2026-01', '2026-01-31', 1), { monat: '2026-02', tag: '2026-02-28' })
  assert.deepEqual(M.schrittMitTag('2026-03', '2026-03-31', -1), { monat: '2026-02', tag: '2026-02-28' })
  assert.deepEqual(M.schrittMitTag('2024-01', '2024-01-31', 1), { monat: '2024-02', tag: '2024-02-29' },
    'Schaltjahr: 29. Februar')
  // Mehrere Monate auf einmal.
  assert.deepEqual(M.schrittMitTag('2026-11', '2026-11-30', 3), { monat: '2027-02', tag: '2027-02-28' })
  // Der Monatsschritt allein bleibt die reine Monatsregel.
  assert.equal(M.monatsSchritt('2026-11', -1), '2026-10')
  assert.equal(M.monatsSchritt('2026-13', 1), '', 'kein Monat 13')
  assert.equal(M.monatsSchritt('2026-11', 0), '2026-11')
  assert.deepEqual(M.schrittMitTag('', '2026-11-13', 1), { monat: '', tag: '' },
    'unbrauchbarer Monat ergibt keine erfundene Antwort')
})

// ══════════════════════════════════════════════════════════════════════════
// 2 · Verdrahtung: das Ereignis kommt an, und die Bibliothek wird nicht mehr
//     bewegt (in der Liste ist sie gar nicht gemountet, `calendarRef` = null)
// ══════════════════════════════════════════════════════════════════════════
test('MINIMONAT-1 · 2: die A10-Liste meldet „zurueck“/„vor“ an die Seite', () => {
  const q = seite()
  const block = q.slice(q.indexOf('<KalenderListeMobil'), q.indexOf('/>', q.indexOf('<KalenderListeMobil')))
  assert.ok(block, 'KalenderListeMobil steht in der Seite')
  assert.match(block, /@zurueck="monatZurueck"/, '‹ → monatZurueck')
  assert.match(block, /@vor="monatVor"/, '› → monatVor')
  assert.ok(!/@zurueck="calendarRef\?\.prev\(\)"/.test(block), 'kein Raster-`prev()` am Mini-Monat')
  assert.ok(!/@vor="calendarRef\?\.next\(\)"/.test(block), 'kein Raster-`next()` am Mini-Monat')
  for (const [name, schritte] of [['monatZurueck', '-1'], ['monatVor', '1']]) {
    const start = q.indexOf(`function ${name}(`)
    const fn = q.slice(start, start + 200)
    assert.ok(fn.startsWith(`function ${name}(`), `${name} ist da`)
    assert.match(fn, new RegExp(`monatBewegen\\(\\s*${schritte}\\s*\\)`), `${name} bewegt um ${schritte} Monat(e)`)
  }
  const start = q.indexOf('function monatBewegen(')
  const bewegen = q.slice(start, start + 1200)
  assert.ok(bewegen.startsWith('function monatBewegen('), 'monatBewegen ist da')
  assert.match(bewegen, /schrittMitTag\(\s*mobilMonat\.value/, 'monatBewegen nutzt die eine Regel')
  assert.match(bewegen, /mobilMonat\.value\s*=/, 'setzt den gezeigten Monat')
  assert.match(bewegen, /gewaehlterTag\.value\s*=/, 'zieht den gewählten Tag mit (Tagesliste passt)')
  assert.ok(!/mobilTermineLaden\(\)/.test(bewegen),
    'monatBewegen lädt NICHT selbst — das spanne-Ereignis lädt den neuen Zeitraum')
  // Keine zweite Monatsrechnung auf der Seite (nur EINE Wahrheit).
  assert.ok(!/getMonth\(\)\s*\+\s*-?1/.test(bewegen), 'kein eigenes Monat-Rechnen neben der Regel')
})

test('MINIMONAT-1 · 3: Desktop-Mini-Monat unberührt (eigene Pfeile, eigenes Ereignis)', () => {
  const desktop = lies('components/kronos/KronosMiniCalendar.vue')
  assert.ok(!/schrittMitTag|monatsSchritt/.test(desktop), 'Desktop kennt die Handy-Regel nicht')
  assert.ok(!/mobilMonat/.test(desktop), 'Desktop liest den Handy-Zustand nicht')
  const q = seite()
  const desktopBlock = q.slice(q.indexOf('<KronosMiniCalendar'), q.indexOf('/>', q.indexOf('<KronosMiniCalendar')))
  assert.ok(!/@zurueck="monatZurueck"/.test(desktopBlock) && !/@vor="monatVor"/.test(desktopBlock),
    'Desktop-Mini-Monat bleibt am Kalender')
  // Die Handy-Liste samt Mini-Monat hängt an der Handy-Lage (nur dort).
  assert.match(q, /<KalenderListeMobil\s+v-if="mobilAnsichtId === 'liste'"/,
    'die Liste gilt nur für die Handy-Listen-Ansicht')
})

// ══════════════════════════════════════════════════════════════════════════
// 4 · Laufzähler der Terminquelle: der jüngste Lauf gewinnt
// ══════════════════════════════════════════════════════════════════════════
test('MINIMONAT-1 · 4: mobilTermineLaden lässt nur den jüngsten Lauf schreiben', () => {
  const q = seite()
  const start = q.indexOf('async function mobilTermineLaden(')
  assert.ok(start > 0, 'mobilTermineLaden ist da')
  const fn = q.slice(start, start + 2500)
  assert.match(fn, /const nr = \+\+ladeNr/, 'jeder Lauf nimmt eine Nummer')
  assert.match(fn, /if \(nr !== ladeNr\) return/, 'ein überholter Lauf schreibt nicht')
  assert.ok(fn.indexOf('if (nr !== ladeNr) return') < fn.indexOf('mobilTermine.value = liste'),
    'die Prüfung steht VOR dem Schreiben')
  assert.match(q, /let ladeNr = 0/, 'der Zähler ist deklariert')
})

// ══════════════════════════════════════════════════════════════════════════
// 5 · GEMOUNTET (jsdom): die verdrahtete Listenansicht — Pfeil › wechselt
//     Monat UND Tag und lädt genau EINMAL den neuen Zeitraum
// ══════════════════════════════════════════════════════════════════════════
const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
for (const schluessel of ['window', 'document', 'Node', 'Element', 'HTMLElement', 'Event',
  'MouseEvent', 'SVGElement', 'CSS']) {
  if (dom.window[schluessel]) globalThis[schluessel] = dom.window[schluessel]
}
try { globalThis.navigator = dom.window.navigator } catch { /* Node hat ein eigenes */ }
const Vue = await import('vue')

const TMP = mkdtempSync(join(tmpdir(), 'minimonat1-'))
const cache = new Map()
const VUE_URL = import.meta.resolve('vue')

function kompilieren(abs) {
  if (cache.has(abs)) return cache.get(abs)
  const filename = basename(abs)
  const { descriptor, errors } = parse(readFileSync(abs, 'utf8'), { filename })
  assert.deepEqual(errors, [], filename + ': SFC-Struktur')
  const script = compileScript(descriptor, { id: filename })
  const tpl = compileTemplate({
    source: descriptor.template.content,
    filename,
    id: filename,
    compilerOptions: { bindingMetadata: script.bindings },
  })
  assert.deepEqual(tpl.errors.map(String), [], filename + ': Vorlage')
  let code = script.content.replace(/\nexport default /, '\nconst __sfc__ = ')
  code += '\n' + tpl.code.replace(/^export function render/m, 'function render')
  code += '\n__sfc__.render = render\nexport default __sfc__\n'
  code = code.replace(/from\s+['"]vue['"]/g, `from '${VUE_URL}'`)
  code = code.replace(/from\s+['"](\.[^'"]+)['"]/g, (voll, spec) => {
    const ziel = resolve(dirname(abs), spec)
    return `from '${pathToFileURL(spec.endsWith('.vue') ? kompilieren(ziel) : ziel).href}'`
  })
  const zielDatei = resolve(TMP, filename.replace(/\.vue$/, '') + '.' + cache.size + '.mjs')
  writeFileSync(zielDatei, code)
  cache.set(abs, zielDatei)
  return zielDatei
}

test.after(() => rmSync(TMP, { recursive: true, force: true }))
const tick = () => new Promise((loese) => setTimeout(loese, 0))

/**
 * Die Listenansicht wie in `pages/Kalender.vue` verdrahtet: dieselben
 * Empfänger (`monatZurueck`/`monatVor` über `schrittMitTag`) und dieselbe
 * Laderegel (`spanne` → EIN Laden des neuen Zeitraums; späte Antworten eines
 * überholten Laufs schreiben nicht).
 */
async function listeMounten() {
  const listeModul = await import(pathToFileURL(
    kompilieren(join(SRC, 'components/kronos/KalenderListeMobil.vue')),
  ).href)
  const host = document.createElement('div')
  document.body.appendChild(host)
  const { ref, computed } = Vue
  const mobilMonat = ref('2026-11')
  const gewaehlterTag = ref('2026-11-13')
  const mobilTermine = ref([])
  const laden = []          // Zeiträume, die wirklich geholt wurden
  let ladeNr = 0
  // Wie die Seite: die Antwort kommt verzögert; nur der jüngste Lauf schreibt.
  function mobilTermineLaden(vonTag, bisTag) {
    const nr = ++ladeNr
    laden.push([vonTag, bisTag])
    return new Promise((loese) => setTimeout(() => {
      if (nr !== ladeNr) { loese(); return }
      mobilTermine.value = [{ id: `t-${bisTag}`, start: `${bisTag.slice(0, 10)}T18:00:00` }]
      loese()
    }, 0))
  }
  const app = Vue.createApp({
    components: { Geprueft: listeModul.default },
    setup: () => ({
      monat: mobilMonat,
      tag: gewaehlterTag,
      termine: mobilTermine,
      monatBewegen(schritte) {
        const neu = M.schrittMitTag(mobilMonat.value, gewaehlterTag.value, schritte)
        if (!neu.monat || neu.monat === mobilMonat.value) return
        mobilMonat.value = neu.monat
        gewaehlterTag.value = neu.tag
      },
      spanneWechseln(spanne) {
        if (!Array.isArray(spanne) || spanne.length !== 2) return
        mobilTermineLaden(String(spanne[0]), String(spanne[1]))
      },
      stand: computed(() => ({ monat: mobilMonat.value, tag: gewaehlterTag.value })),
      laden,
    }),
    template: '<Geprueft :monat="monat" :gewaehlter-tag="tag" :termine="termine" '
      + '@zurueck="monatBewegen(-1)" @vor="monatBewegen(1)" @spanne="spanneWechseln" />'
      + '<p class="stand">{{ stand.monat }} · {{ stand.tag }}</p>',
  })
  app.config.warnHandler = () => {}
  app.mount(host)
  await tick()
  return { app, host, mobilMonat, gewaehlterTag, mobilTermine, laden }
}

test('MINIMONAT-1 · 5: gemountet — › wechselt Monat und Tag, lädt EINMAL neu', async () => {
  const { app, host, mobilMonat, gewaehlterTag, laden, mobilTermine } = await listeMounten()
  try {
    assert.match(host.textContent, /November 2026/, 'Start: November 2026')
    const vorher = laden.length
    const knoepfe = [...host.querySelectorAll('.dk-minimonat-pfeil')]
    assert.equal(knoepfe.length, 2, 'zwei Pfeile')
    // › = nächster Monat
    knoepfe[1].dispatchEvent(new window.MouseEvent('click', { bubbles: true }))
    await tick()
    await tick()
    assert.equal(mobilMonat.value, '2026-12', 'der gezeigte Monat wandert')
    assert.equal(gewaehlterTag.value, '2026-12-13', 'der gewählte Tag wandert mit')
    assert.match(host.textContent, /Dezember 2026/, 'der Mini-Monat zeigt den neuen Monat')
    // GENAU EIN neuer Ladevorgang — für die Spanne des NEUEN Monats.
    const neue = laden.slice(vorher)
    assert.equal(neue.length, 1, `ein einziger Aufruf für den neuen Zeitraum (${JSON.stringify(neue)})`)
    const [von, bis] = neue[0]
    assert.match(von, /^2026-1[12]/, `die Spanne beginnt im November/Dezember (${von})`)
    assert.match(bis, /^2027-01/, `die Spanne endet im Januar (${bis})`)
    assert.equal(mobilTermine.value.length, 1, 'die Punkte gehören zum neuen Zeitraum')
    // ‹ geht zurück.
    knoepfe[0].dispatchEvent(new window.MouseEvent('click', { bubbles: true }))
    await tick()
    await tick()
    assert.equal(mobilMonat.value, '2026-11')
    assert.equal(gewaehlterTag.value, '2026-11-13')
    assert.match(host.textContent, /November 2026/)
  } finally {
    app.unmount()
    host.remove()
  }
})

// ══════════════════════════════════════════════════════════════════════════
// 6 · Überholte Antwort verliert (Laufzähler; ohne Fix rot)
// ══════════════════════════════════════════════════════════════════════════
test('MINIMONAT-1 · 6: überholte Antwort schreibt nicht (neuer Zeitraum gewinnt)', async () => {
  /** Der Ladeweg wie in `pages/Kalender.vue` — mit und ohne Zähler. */
  function baue(mitZaehler) {
    let ladeNr = 0
    const stand = { termine: null }
    function laden(antwort, verzoegerung) {
      const nr = mitZaehler ? ++ladeNr : 0
      return new Promise((loese) => setTimeout(() => {
        if (mitZaehler && nr !== ladeNr) { loese(); return }
        stand.termine = antwort
        loese()
      }, verzoegerung))
    }
    return { stand, laden }
  }
  // Die November-Antwort kommt SPÄT, die Dezember-Antwort früh.
  const ohne = baue(false)
  await Promise.all([ohne.laden('NOVEMBER', 30), ohne.laden('DEZEMBER', 5)])
  assert.equal(ohne.stand.termine, 'NOVEMBER',
    'ohne Zähler gewinnt die zuletzt eintreffende (alte) Antwort — das ist der Fehler')
  const mit = baue(true)
  await Promise.all([mit.laden('NOVEMBER', 30), mit.laden('DEZEMBER', 5)])
  assert.equal(mit.stand.termine, 'DEZEMBER', 'mit Zähler gewinnt der jüngste Lauf')
})

// ══════════════════════════════════════════════════════════════════════════
// 7 · Raster nach dem Umschalten: springt auf den geblätterten Tag
// ══════════════════════════════════════════════════════════════════════════
test('MINIMONAT-1 · 7: `@bereit` setzt das Raster auf den gewählten Tag', () => {
  const q = seite()
  assert.match(q, /@bereit="rasterSteht"/, 'der Bereit-Haken führt in die Seite')
  const start = q.indexOf('function rasterSteht(')
  const fn = q.slice(start, start + 600)
  assert.ok(fn.startsWith('function rasterSteht('), 'rasterSteht ist da')
  assert.match(fn, /rasterBereit\.value = true/, 'der Ladezustand endet')
  assert.match(fn, /gotoDate\(gewaehlterTag\.value\)/, 'das Raster springt auf den gewählten Tag')
})

// ══════════════════════════════════════════════════════════════════════════
// 8 · Der tote Raster-Halter-Rest ist weg (in der Liste ist die Bibliothek
//     nicht gemountet — es gibt dort keinen offscreen-Zustand)
// ══════════════════════════════════════════════════════════════════════════
test('MINIMONAT-1 · 8: kein offscreen-Rest am Rasterhalter', () => {
  const q = seite()
  assert.ok(!/offscreen/.test(q), 'keine offscreen-Klasse und keine offscreen-Regel mehr')
  assert.match(q, /<div v-else class="kal-mobil-raster">/, 'das Raster hängt an v-else zur Liste')
})
