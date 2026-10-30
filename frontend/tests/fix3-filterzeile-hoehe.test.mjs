/**
 * FIX-3 — Beiträge: Knopf und Suchfeld gleich hoch (Befund DMB-eb3ae73fc36f).
 *
 * Befund (24.10., Route #/beitraege, Viewport 344×694, Element
 * `div.dk-filters.bt-filter`): „Button und suchmaske unterschiedlich groß“.
 * Screenshot: der Filterchip (34 px) steht neben dem Suchfeld (39 px) — das
 * Feld holte seine Höhe allein aus `padding: 10px 14px`, der Chip aus
 * `padding: 7px 12px`. Dieselbe Schieflage hatten Lieder (Alt-Knopf
 * `.dk-btn-sm` ≈ 27 px neben dem Suchfeld) und Wiki (Eigen-Chips ≈ 29 px).
 *
 * Behoben ist das zentral: ein Token `--filter-h` (tokens.css) setzt die Höhe
 * für Suchfeld, Filterchip und DkButton „md“; der Innenabstand der Felder ist
 * nur noch waagerecht. Die Seiten bauen keine eigenen Maße mehr nach.
 *
 * Geprüft wird:
 *   1. das Token existiert und ist an --control-h gebunden (keine neue Zahl);
 *   2. Suchfeld, Chip und DkButton „md“ lesen IHRE Höhe aus diesem Token —
 *      keines der drei holt sie mehr aus einem senkrechten Innenabstand;
 *   3. die Seiten (Beiträge, Lieder, Wiki, Liedgruppe) übernehmen das Maß,
 *      statt es lokal zu setzen;
 *   4. die Datei steht in der node-Testliste der backend/Dockerfile.
 *
 * Die Messung im Browser (getBoundingClientRect bei 344 px und 1366 px) macht
 * tools/demo/fix3-filterzeile.py; dieser Test sichert die Regel, damit die
 * Höhen nicht still wieder auseinanderlaufen.
 */
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import test from 'node:test'

const WURZEL = new URL('../src/diakonos/', import.meta.url)
const lies = (p) => readFileSync(new URL(p, WURZEL), 'utf8')

const TOKENS = lies('tokens.css')
const CSS = lies('index.css')

/** Regel `.<selektor> { … }` samt allem, was davor steht (auch Mehrfachwahl). */
function regelBlock(text, selektor) {
  const i = text.indexOf(selektor)
  if (i < 0) return null
  const auf = text.indexOf('{', i)
  const zu = text.indexOf('}', auf)
  return text.slice(i, zu + 1)
}

const ohneKommentare = (t) => t.replace(/\/\*[\s\S]*?\*\//g, '')

// ── 1. Das gemeinsame Maß ──────────────────────────────────────────────────
test('FIX-3 · es gibt ein Höhen-Token --filter-h, gebunden an --control-h', () => {
  const treffer = /--filter-h:\s*([^;]+);/.exec(ohneKommentare(TOKENS))
  assert.ok(treffer, '--filter-h in tokens.css definiert')
  assert.equal(treffer[1].trim(), 'var(--control-h)',
    'keine neue Zahl — die Filterzeile folgt der vorhandenen Knopfhöhe')
})

test('FIX-3 · --control-h bleibt die einzige Zahl für die Knopfhöhe', () => {
  const control = /--control-h:\s*(\d+)px;/.exec(ohneKommentare(TOKENS))
  assert.ok(control, '--control-h gefunden')
  // Die Zahl steht genau einmal (auch im Dunkelmodus nicht überschrieben).
  const zahlen = ohneKommentare(TOKENS).match(/--control-h:/g) || []
  assert.equal(zahlen.length, 1, '--control-h nur an einer Stelle definiert')
})

// ── 2. Die drei Bausteine der Filterzeile ──────────────────────────────────
test('FIX-3 · das Suchfeld holt seine Höhe aus --filter-h, nicht aus dem Innenabstand', () => {
  const block = regelBlock(ohneKommentare(CSS), '.dk-search-bar {')
  assert.ok(block, 'Regel .dk-search-bar gefunden')
  assert.match(block, /min-height:\s*var\(--filter-h\)/, 'Höhe aus dem Token')
  const padding = /(?:^|[;{]\s*)padding:\s*([^;]+);/.exec(block)
  assert.ok(padding, 'padding gesetzt')
  // Senkrechter Innenabstand würde die Höhe wieder mitbestimmen: erlaubt ist
  // nur die Kurzform „0 14px“ (oben/unten 0) oder ein einzelner waagerechter
  // Wert — in keinem Fall „10px 14px“ wie im Befund.
  const teile = padding[1].trim().split(/\s+/)
  assert.ok(teile.length <= 2, `padding nur waagerecht: ${padding[1].trim()}`)
  if (teile.length === 2) {
    assert.equal(teile[0], '0', `senkrechter Innenabstand muss 0 sein: ${padding[1].trim()}`)
  } else {
    assert.ok(!/^\d/.test(teile[0]), `kein senkrechter Innenabstand: ${padding[1].trim()}`)
  }
})

test('FIX-3 · der Filterchip bekommt dieselbe Höhe wie das Suchfeld', () => {
  // Gezielt die Chip-Regel (nicht die Trefferflächen-Regel im Handy-Block).
  const block = regelBlock(ohneKommentare(CSS), '.dk-ui-chip,\n.dk-filter-chip {') ||
    regelBlock(ohneKommentare(CSS), '.dk-filter-chip {')
  assert.ok(block, 'Regel .dk-ui-chip/.dk-filter-chip gefunden')
  assert.match(block, /height:\s*var\(--filter-h\)/)
  // Nur waagerechter Innenabstand — sonst verschiebt er die Höhe erneut.
  const padding = /(?:^|[;{]\s*)padding:\s*([^;]+);/.exec(block)
  assert.ok(padding, 'padding gesetzt')
  const teile = padding[1].trim().split(/\s+/)
  assert.ok(teile.length <= 2, `padding nur waagerecht: ${padding[1].trim()}`)
  if (teile.length === 2) assert.equal(teile[0], '0', 'senkrechter Innenabstand 0')
})

test('FIX-3 · DkButton „md“ nutzt dasselbe Höhen-Token (kein zweiter Wert)', () => {
  const button = lies('components/ui/DkButton.vue')
  const mdBlock = regelBlock(ohneKommentare(button), '.dk-ui-btn--md')
  assert.ok(mdBlock, 'Regel .dk-ui-btn--md gefunden')
  assert.match(mdBlock, /height:\s*var\(--filter-h\)/)
  assert.ok(!/\.dk-ui-btn--md\s*\{[^}]*height:\s*var\(--control-h\)/.test(ohneKommentare(button)),
    'die alte, unabhängige Höhe ist ersetzt')
})

test('FIX-3 · die Filterzeile selbst schrumpft das Suchfeld nicht weg', () => {
  const block = regelBlock(ohneKommentare(CSS), '.dk-filters {')
  assert.ok(block, 'Regel .dk-filters gefunden')
  assert.match(block, /align-items:\s*center/, 'Kinder stehen auf einer Mittellinie')
  assert.match(ohneKommentare(CSS), /\.dk-filters > \.dk-search-bar\s*\{[^}]*align-self:\s*center/)
})

// ── 3. Die Seiten übernehmen das Maß ───────────────────────────────────────
test('FIX-3 · Beiträge: die Seite setzt keine eigene Feldhöhe mehr', () => {
  const seite = lies('pages/Beitraege.vue')
  const suche = regelBlock(ohneKommentare(seite), '.bt-suche {')
  assert.ok(suche, 'Regel .bt-suche gefunden')
  assert.ok(!/height|padding:\s*\d+px\s+\d+px/.test(suche),
    'Höhe/Innenabstand kommen aus index.css, nicht aus der Seite')
  assert.match(suche, /max-width/, 'nur die Breite bleibt seitenlokal')
})

test('FIX-3 · Lieder: der Filter-Knopf ist der gemeinsame Baustein, kein Alt-Knopf', () => {
  const seite = lies('pages/Lieder.vue')
  const tpl = seite.slice(seite.indexOf('<template>'), seite.lastIndexOf('</template>'))
  const start = tpl.lastIndexOf('<DkButton', tpl.indexOf('ld-filter-knopf'))
  assert.ok(start > 0, 'DkButton für das Filterblatt gefunden')
  const knopf = tpl.slice(start, tpl.indexOf('</DkButton>', start))
  assert.match(knopf, /ld-filter-knopf/)
  assert.match(knopf, /aria-expanded/)
  assert.ok(!/dk-btn-sm/.test(knopf), 'die kleine Alt-Klasse ist weg')
})

test('FIX-3 · Lieder: das Suchfeld der Werkzeugleiste nutzt dieselbe Höhe', () => {
  const block = regelBlock(ohneKommentare(CSS), '.dk-toolbar-search input {')
  assert.ok(block, 'Regel .dk-toolbar-search input gefunden')
  assert.match(block, /min-height:\s*var\(--filter-h\)/)
})

test('FIX-3 · Wiki: Kategorien laufen über DkFilterChips, nicht über Eigenknöpfe', () => {
  const seite = lies('pages/Wiki.vue')
  const tpl = seite.slice(seite.indexOf('<template>'), seite.lastIndexOf('</template>'))
  assert.match(tpl, /<DkFilterChips/, 'gemeinsamer Chip-Baustein')
  assert.ok(!/class="wk-cat-chip"/.test(tpl), 'keine eigenen Kategorieknöpfe mehr')
  const skript = seite.slice(seite.indexOf('<script setup>'), seite.indexOf('</script>'))
  assert.match(skript, /const kategorieChips = computed/, 'Chip-Daten aus der Kategorienliste')
  assert.match(skript, /import DkFilterChips from/, 'Baustein eingebunden')
  // Der Zustand bleibt der alte Schlüssel ('all'), damit das Filtern unverändert hängt.
  assert.match(skript, /activeCategory = ref\('all'\)/)
})

test('FIX-3 · Liedgruppe: Suchfeld und Zuordnungs-Knopf stehen in einer Zeile', () => {
  const datei = lies('components/lieder/LiedgruppeBearbeiten.vue')
  const block = regelBlock(ohneKommentare(datei), '.lgb-suche {')
  assert.ok(block, 'Regel .lgb-suche gefunden')
  assert.match(block, /display:\s*flex/)
})

// ── 4. Keine harten Farben in den geänderten Regeln ────────────────────────
test('FIX-3 · die Filterzeilen-Regeln tragen keine hart codierten Farben', () => {
  for (const sel of ['.dk-search-bar {', '.dk-ui-chip,', '.dk-filters {']) {
    const block = regelBlock(ohneKommentare(CSS), sel)
    const farben = block.match(/(color|background)\s*:\s*([^;]+)/g) || []
    for (const f of farben) {
      assert.ok(!/#[0-9a-fA-F]{3,8}\b/.test(f) && !/\b(rgb|hsl)\(/.test(f),
        `harter Farbwert in ${sel}: ${f.trim()}`)
    }
  }
})

// ── 5. Der Test läuft im Image ─────────────────────────────────────────────
test('FIX-3 · die Testdatei steht in der node-Testliste der backend/Dockerfile', (t) => {
  // Im Image liegt nur frontend/ — die Dockerfile steht dort NICHT. Geprüft
  // wird der Eintrag, wo sie erreichbar ist; im Abbild entfällt der Nachweis,
  // statt fälschlich rot zu werden (Muster: uxc3b/fix1).
  const kandidaten = [
    new URL('../../backend/Dockerfile', import.meta.url),
    new URL('../../../backend/Dockerfile', import.meta.url),
  ]
  const treffer = kandidaten.find((u) => existsSync(u))
  if (!treffer) return t.skip('backend/Dockerfile im Abbild nicht vorhanden')
  const dockerfile = readFileSync(treffer, 'utf8')
  assert.match(dockerfile, /tests\/fix3-\*\.test\.mjs/, 'Glob tests/fix3-*.test.mjs eingetragen')
})

// Review FIX-3: Wiki benutzt 'all' als „Alle“-Wert — ohne alle-wert="all"
// setzt ein zweiter Klick 'alle', der Server filtert dann auf eine Kategorie
// „alle“ und die Liste ist leer.
{
  const wiki = readFileSync(new URL('../src/diakonos/pages/Wiki.vue', import.meta.url), 'utf8')
  const tag = wiki.match(/<DkFilterChips[\s\S]*?\/>/)?.[0] || ''
  if (!/alle-wert="all"/.test(tag)) throw new Error('Wiki.vue: DkFilterChips braucht alle-wert="all"')
}
