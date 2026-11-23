/**
 * BEF-DESIGN-1 — Seitenkarten und Kopf-Knöpfe (Befund Manuel 23.11.).
 *
 * Drei Befunde, EINE Ursache je Baustein:
 *
 *  1. Seitenkarten (Beiträge, Wiki): „Design inconsistent“ · „Margin/Padding!
 *     Erneut! Bedenke SSOT“. Der Kopf der Karte war gepolstert, der Inhalt
 *     darunter nicht — die Karten lagen mit `flach` in der Seitenspalte, und
 *     `flach` nahm NUR dem Körper den Innenabstand (`--karte-innen`). Dazu
 *     brachten die Zeilen eigene Abstände mit (`6px var(--sp-2)`,
 *     `.dk-widget-item` mit `8px 0` und `-16px`-Hover-Versatz), sodass
 *     „Archiv“ anders stand als „Kategorien“. Jetzt: EINE Quelle — der
 *     Kartenkörper trägt `--karte-innen` für Kopf UND Inhalt, die Zeilen
 *     tragen nur noch den SENKRECHTEN Abstand.
 *
 *  2. Kopf-Knöpfe „+ Neuer Beitrag“, „+ Neuer Artikel“, „Bearbeiten“: Symbol
 *     ÜBER dem Text, Beschriftung unten abgeschnitten. Ursache war
 *     `.dk-ui-btn-label` mit `flex-wrap: wrap` und festen 7 px. Jetzt:
 *     einzeilig (`white-space: nowrap`), Abstand aus der Skala.
 *
 *  3. Kürzel „Strg K“ in der Kopfzeile stand in zwei Zeilen. Jetzt: nowrap.
 *
 * Geprüft wird an der QUELLE (CSS/SFC), weil die Befunde Layout-Regeln sind —
 * jsdom rechnet keine Layouts. Ergänzend wird DkCard echt gemountet, damit
 * der Test nicht nur Kommentare prüft, sondern den gerenderten Kopf/Körper.
 *
 * Lauf: node --test tests/befdesign1-*.test.mjs   (cwd = frontend/)
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, existsSync, mkdtempSync, writeFileSync, rmSync, mkdirSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, dirname, resolve, basename } from 'node:path'
import { pathToFileURL, fileURLToPath } from 'node:url'
import { JSDOM } from 'jsdom'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'

const hier = dirname(fileURLToPath(import.meta.url))
const FRONTEND = resolve(hier, '..')
const SRC = join(FRONTEND, 'src', 'diakonos')

// ── Hilfen ────────────────────────────────────────────────────────────────
/** Datei ohne Kommentare — geprüft wird die WIRKUNG, nicht die Begründung. */
function ohneKommentare(text) {
  return text.replace(/\/\*[\s\S]*?\*\//g, '').replace(/<!--[\s\S]*?-->/g, '')
}
/** Eine Regel `selektor { … }` (erste Fundstelle, ohne Kommentare). */
function regel(text, selektor) {
  const t = ohneKommentare(text)
  const i = t.indexOf(selektor)
  assert.ok(i >= 0, `Regel ${selektor} fehlt`)
  const auf = t.indexOf('{', i)
  const zu = t.indexOf('}', auf)
  assert.ok(auf > 0 && zu > auf, `Regel ${selektor} ist unlesbar`)
  return t.slice(auf + 1, zu)
}
/** Die scoped-Styles einer .vue-Datei. */
function stil(datei) {
  const text = readFileSync(join(SRC, datei), 'utf8')
  const m = text.match(/<style[^>]*>([\s\S]*?)<\/style>/)
  assert.ok(m, `${datei}: kein Stilblock`)
  return m[1]
}
const DKCARD = readFileSync(join(SRC, 'components/ui/DkCard.vue'), 'utf8')
const DKBTN = readFileSync(join(SRC, 'components/ui/DkButton.vue'), 'utf8')
const INDEX_CSS = readFileSync(join(SRC, 'index.css'), 'utf8')

/** Seitenleisten-Karten einer Seite: `DkCard` mit `title` im `aside`. */
function seitenkarten(datei) {
  const text = readFileSync(join(SRC, datei), 'utf8')
  const aside = text.match(/<aside[^>]*dk-aside[^>]*>([\s\S]*?)<\/aside>/)
  assert.ok(aside, `${datei}: keine Seitenspalte (aside.dk-aside)`)
  return [...aside[1].matchAll(/<DkCard\b[^>]*>/g)].map((m) => m[0])
}

// ── 1 · EINE Quelle für den Innenabstand der Karte ────────────────────────
test('BEF-DESIGN-1 · Kartenkopf UND Kartenkörper polstern aus demselben Token', () => {
  const kopf = regel(DKCARD, '.dk-ui-card-kopf {')
  const koerper = regel(DKCARD, '.dk-ui-card-koerper {')
  assert.match(kopf, /padding:\s*var\(--karte-innen\)/, 'der Kopf polstert nicht aus --karte-innen')
  assert.match(koerper, /padding:\s*var\(--karte-innen\)/, 'der Körper polstert nicht aus --karte-innen')
  assert.match(regel(DKCARD, '.dk-ui-card-kopf + .dk-ui-card-koerper {'), /padding-top:\s*var\(--sp-3\)/,
    'der Abstand zwischen Titel und Inhalt kommt nicht aus der Skala')
})

test('BEF-DESIGN-1 · `flach` ist KEIN Seitenleisten-Werkzeug mehr', () => {
  // Der Befund: `flach` nahm NUR dem Körper den Abstand — genau das ließ den
  // Titel gepolstert und den Inhalt am Rand stehen.
  assert.match(regel(DKCARD, '.dk-ui-card-koerper.is-flach {'), /padding:\s*0/,
    '`flach` muss weiterhin den Körper randlos machen (Tabellen, eigene Raster)')
  // `zeile` ist der Weg, der Kopf UND Körper den Abstand nimmt — eine Stelle.
  const zeileKopf = regel(DKCARD, '.dk-ui-card.is-zeile .dk-ui-card-kopf {')
  assert.match(zeileKopf, /padding:\s*0/, '`zeile` nimmt dem Kopf den Abstand nicht')
})

// ── 2 · Seitenkarten der Seiten (Beiträge, Wiki) ──────────────────────────
for (const datei of ['pages/Beitraege.vue', 'pages/Wiki.vue']) {
  test(`BEF-DESIGN-1 · ${datei}: Seitenkarten sind DkCard MIT Kopf, nicht \`flach\``, () => {
    const karten = seitenkarten(datei)
    assert.ok(karten.length >= 2, `${datei}: zu wenige Seitenkarten gefunden`)
    for (const karte of karten) {
      assert.match(karte, /\stitle=/, `${datei}: Seitenkarte ohne Titel: ${karte}`)
      assert.doesNotMatch(karte, /\sflach[\s>/]/, `${datei}: Seitenkarte trägt \`flach\`: ${karte}`)
    }
  })

  test(`BEF-DESIGN-1 · ${datei}: Zeilen der Seitenkarten tragen keinen waagerechten Abstand`, () => {
    const css = ohneKommentare(stil(datei))
    // Jede Regel, die einen waagerechten Innenabstand oder einen Rand setzt,
    // ist ein Seiten-Sonderfall — genau der Grund für „jede Karte macht es
    // anders“. Erlaubt sind 0-Werte.
    const treffer = [...css.matchAll(/([^{}]+)\{([^}]*)\}/g)].filter(([, , rumpf]) => {
      const pad = rumpf.match(/(?:^|;|\s)padding(?:-left|-right|-inline|-inline-start|-inline-end)?\s*:\s*([^;]+)/)
      const margin = rumpf.match(/(?:^|;|\s)margin(?:-left|-right|-inline|-inline-start|-inline-end)?\s*:\s*([^;]+)/)
      // Erlaubt ist „nur senkrecht“: padding/margin aus zwei Werten, deren
      // WAAGERECHTER (zweiter) 0 ist — etwa `var(--sp-2) 0`. Erlaubt ist
      // ebenso ein reiner Einzelwert ohne waagerechte Wirkung (padding-top).
      const senkrechtNur = (wert) => {
        const teile = wert.trim().split(/\s+/)
        if (teile.length === 1) return true
        return teile[1] === '0'
      }
      return [pad, margin].some((m) => {
        if (!m) return false
        const wert = m[1].trim()
        if (/^(?:0|auto)(?:\s+(?:0|auto))*$/.test(wert)) return false
        return !senkrechtNur(wert)
      })
    }).map(([sel]) => sel.trim())
    // ZEILEN der Seitenkarte (Listeneinträge, Text) — Chips sind eigene
    // Bausteine mit eigenem Innenleben und bringen ihren Abstand mit.
    const seitenZeilen = treffer.filter((sel) => /^\.(?:bt-popular|bt-cat-item|bt-archive-item|wk-recent-zeile|wk-help-text)\b/.test(sel))
    assert.deepEqual(seitenZeilen, [],
      `${datei}: Seitenkarten-Zeilen setzen waagerechten Abstand selbst (eine Quelle: --karte-innen)`)
  })
}

test('BEF-DESIGN-1 · Beiträge: die beliebten Beiträge nutzen KEINE Fremdklasse mit Versatz', () => {
  const text = ohneKommentare(readFileSync(join(SRC, 'pages/Beitraege.vue'), 'utf8'))
  assert.doesNotMatch(text, /dk-widget-item/,
    'die Zeile hängt wieder an `.dk-widget-item` (8 px 0 und -16 px Hover-Versatz)')
  // Und die eigene Zeilenklasse muss existieren (sonst fällt die Zeile in den
  // Browser-Grundstil zurück).
  assert.match(stil('pages/Beitraege.vue'), /\.bt-popular \{/, 'die Zeile hat keine eigene Gestalt (.bt-popular)')
  // Und die globale Klasse trägt selbst einen waagerechten Versatz — sie darf
  // in einer gepolsterten Karte nicht mehr verwendet werden.
  assert.match(INDEX_CSS, /\.dk-widget-item:hover \{[^}]*margin:\s*0 -16px/,
    'Annahme geändert: `.dk-widget-item` hat keinen Versatz mehr — Test anpassen')
})

test('BEF-DESIGN-1 · Wiki: Schlagwort-Chips liegen auf der Abstands-Skala', () => {
  const css = ohneKommentare(stil('pages/Wiki.vue'))
  const chip = regel(css, '.wk-tag-cloud-item {')
  assert.match(chip, /padding:\s*var\(--sp-\d\) var\(--sp-\d\)/, 'Chip-Innenabstand ist kein Token mehr')
  assert.match(css, /\.wk-tag-cloud \{[^}]*gap:\s*var\(--sp-\d\)/, 'Chip-Abstand ist kein Token mehr')
})

// ── 3 · Kopf-Knöpfe: Icon und Text in EINER Zeile ────────────────────────
test('BEF-DESIGN-1 · Knopf-Beschriftung bricht NIE um (Icon bleibt neben dem Text)', () => {
  const label = regel(DKBTN, '.dk-ui-btn-label {')
  assert.match(label, /white-space:\s*nowrap/, 'die Beschriftung darf umbrechen — Symbol rutscht wieder darüber')
  assert.doesNotMatch(label, /flex-wrap:\s*wrap/, '`flex-wrap: wrap` ist zurück (Ursache des Befunds)')
  assert.match(label, /gap:\s*var\(--sp-\d\)/, 'der Abstand zwischen Symbol und Text ist kein Token')
  assert.doesNotMatch(label, /gap:\s*\d+px/, 'fester px-Abstand in der Beschriftung (Wächter ux1a)')
})

test('BEF-DESIGN-1 · die Kopf-Knöpfe der Seiten setzen keinen eigenen Textumbruch', () => {
  for (const datei of ['pages/Beitraege.vue', 'pages/Wiki.vue', 'pages/LiedDetail.vue']) {
    const css = ohneKommentare(stil(datei))
    const treffer = [...css.matchAll(/[^{}]*dk-ui-btn[^{}]*\{[^}]*\}/g)].map((m) => m[0])
    for (const t of treffer) {
      assert.doesNotMatch(t, /white-space|flex-direction/, `${datei}: Seite biegt den Knopftext lokal um: ${t.trim()}`)
    }
  }
})

// ── 4 · Kürzel „Strg K“ einzeilig ────────────────────────────────────────
test('BEF-DESIGN-1 · Kürzel „Strg K“ steht einzeilig', () => {
  const kuerzel = regel(INDEX_CSS, '.dk-topbar-suche .dk-topbar-suche-kuerzel {')
  const kuerzelGrund = regel(INDEX_CSS, '.dk-topbar-suche-kuerzel {')
  assert.match(kuerzel, /white-space:\s*nowrap/, 'das Kürzel darf wieder auf zwei Zeilen brechen')
  assert.match(kuerzelGrund, /flex:\s*none/, 'das Kürzel wird gestaucht (Umbruch trotz nowrap)')
  // Die Suche selbst hält ihre Teile in einer Zeile.
  assert.match(regel(INDEX_CSS, '.dk-topbar-suche {'), /display:\s*flex/, 'das Suchfeld ist kein Flex-Container mehr')
})

// ── 5 · Am ECHTEN Bauteil: Kopf und Körper tragen denselben Abstand ───────
const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/', pretendToBeVisual: true })
const { window: W } = dom
for (const name of ['window', 'document', 'HTMLElement', 'Element', 'Node', 'SVGElement', 'Text', 'Comment',
  'DocumentFragment', 'getComputedStyle', 'requestAnimationFrame', 'cancelAnimationFrame', 'MutationObserver',
  'CustomEvent', 'Event', 'MouseEvent', 'KeyboardEvent', 'localStorage', 'sessionStorage']) {
  if (W[name] === undefined) continue
  try { globalThis[name] = W[name] } catch (_) { Object.defineProperty(globalThis, name, { value: W[name], configurable: true, writable: true }) }
}
if (W.navigator) {
  try { Object.defineProperty(globalThis, 'navigator', { value: W.navigator, configurable: true }) } catch (_) {}
}
globalThis.window = W
W.__DIakonosBOOT = { csrf_token: 'x', modules: [], user_email: 'ich@example.org' }
globalThis.matchMedia = () => ({ matches: false, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {} })
W.matchMedia = globalThis.matchMedia

const Vue = await import('vue')
const TMP = mkdtempSync(join(tmpdir(), 'befdesign1-'))
const STUB = join(TMP, 'stubs')
mkdirSync(STUB, { recursive: true })
writeFileSync(join(STUB, 'sprung.mjs'), 'export function sprungId(anker) { return anker ? "dk-sprung-" + anker : undefined }\n')
const STELLVERTRETER = new Map([[join(SRC, 'pages/sprung'), join(STUB, 'sprung.mjs')]])
const cache = new Map()
const VUE_URL = import.meta.resolve('vue')

function stellvertreterFuer(abs) {
  const ohne = String(abs).replace(/\.(js|mjs|vue)$/, '')
  return STELLVERTRETER.get(ohne) || null
}
function kompilieren(abs) {
  const ersatz = stellvertreterFuer(abs)
  if (ersatz) return ersatz
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
  code = code.replace(/from\s+['"]([^'"]+)['"]/g, (v, spec) => {
    if (!spec.startsWith('.')) return v
    const ziel = resolve(dirname(abs), spec)
    const datei = spec.endsWith('.vue') || stellvertreterFuer(ziel) ? kompilieren(ziel) : ziel
    return `from '${pathToFileURL(datei).href}'`
  })
  const ziel = resolve(TMP, filename.replace(/\.vue$/, '') + '.' + cache.size + '.mjs')
  writeFileSync(ziel, code)
  cache.set(abs, ziel)
  return ziel
}
test.after(() => rmSync(TMP, { recursive: true, force: true }))
const tick = () => new Promise((loese) => setTimeout(loese, 0))

test('BEF-DESIGN-1 · DkCard rendert Kopf und Körper als getrennte Flächen mit Inhalt', async () => {
  const bauteil = (await import(pathToFileURL(kompilieren(join(SRC, 'components/ui/DkCard.vue'))).href)).default
  const host = document.createElement('div')
  document.body.appendChild(host)
  const app = Vue.createApp({
    render: () => Vue.h(bauteil, { title: 'Kategorien' }, { default: () => Vue.h('div', { class: 'test-zeile' }, 'Gemeindeleben') }),
  })
  app.mount(host)
  await tick()
  const kopf = host.querySelector('.dk-ui-card-kopf')
  const koerper = host.querySelector('.dk-ui-card-koerper')
  assert.ok(kopf, 'Kartenkopf fehlt')
  assert.ok(koerper, 'Kartenkörper fehlt')
  assert.equal(kopf.nextElementSibling, koerper, 'Kopf und Körper stehen nicht nebeneinander in der Karte')
  assert.ok(koerper.querySelector('.test-zeile'), 'der Inhalt steht nicht im Kartenkörper')
  assert.equal(host.querySelector('.dk-ui-card').classList.contains('is-flach'), false,
    'die Karte ist ohne `flach` gerendert — der Körper behält seinen Abstand')
  try { app.unmount() } catch (_) {}
  host.remove()
})

// ── 6 · Wächter: keine neuen Seitenkarten-Sonderfälle ──────────────────────
test('BEF-DESIGN-1 · keine .vue-Datei polstert einen Kartenkopf selbst', () => {
  // Ein Seiten-Sonderfall für den Kartenkopf war die Ursache des Befunds. Der
  // Kopf gehört DkCard; wer ihn in einer Seite anfasst, baut die zweite Quelle.
  const verstoesse = []
  const durchlaufe = (verz) => {
    for (const eintrag of readdirSync(verz, { withFileTypes: true })) {
      if (eintrag.name === 'node_modules') continue
      const pfad = join(verz, eintrag.name)
      if (eintrag.isDirectory()) { durchlaufe(pfad); continue }
      if (!eintrag.name.endsWith('.vue')) continue
      const rel = pfad.slice(SRC.length + 1)
      if (rel === 'components/ui/DkCard.vue') continue
      const text = readFileSync(pfad, 'utf8')
      const stilblock = text.match(/<style[^>]*>([\s\S]*?)<\/style>/)
      if (!stilblock) continue
      const css = ohneKommentare(stilblock[1])
      // BEF-DESIGN-1: eine Zeile IN einer Karte (`zeile`, `.ke-zeile`) darf
      // ihren senkrechten Abstand selbst feinjustieren — der senkrechte Wert
      // ist eine Feinheit der Zeile, kein zweiter Kartenabstand. Verboten ist
      // der WAAGERECHTE Abstand am Kopf/Körper (genau der Befund: Titel
      // gepolstert, Inhalt am Rand).
      for (const m of css.matchAll(/([^{}]+)\{([^}]*)\}/g)) {
        if (!/dk-ui-card-(?:kopf|koerper)\b/.test(m[1])) continue
        const waagerecht = m[2].match(/(?:^|;|\s)padding(?:-left|-right|-inline|-inline-start|-inline-end)?\s*:\s*([^;]+)/)
        if (!waagerecht) continue
        const wert = waagerecht[1].trim()
        if (/^(?:0|auto)(?:\s+(?:0|auto))*$/.test(wert)) continue
        const teile = wert.split(/\s+/)
        if (teile.length >= 2 && teile.every((t, i) => i === 1 || t === '0') && teile[1] === '0') continue
        verstoesse.push(`${rel}: ${m[1].trim()}`)
      }
    }
  }
  durchlaufe(SRC)
  assert.deepEqual(verstoesse, [],
    'Seiten polstern den Kartenkopf/-körper selbst — Abstand gehört in DkCard (--karte-innen)')
})
