/**
 * FIX-5 — Gruppen-Detail: einheitliche Abstände, gleiche Kartenköpfe,
 * Handy-Überlauf der Gruppenkarten (Befund DMB-096ae0364b59 + DEV-1).
 *
 * Befund (16.10., Route `#/gruppe/<name>`, `pages/GruppeDetail.vue`):
 * „Design nicht einheitlich. Gap zwischen den Kacheln nicht einheitlich.“
 * Dazu im Bild: Karten mit Aktionsknopf sind 4 px höher als Karten ohne
 * (Knopf „sm“ = 28 px gegen eine Titelzeile), und die Gruppenkarten laufen
 * am Handy seitlich über die Seite (Folgepunkt DEV-1).
 *
 * Geprüft wird:
 *   1. es gibt EIN Token für den Kartenabstand (`--grid-gap`) und die
 *      Detailseite benutzt es an allen drei Stellen (Raster, Spalte,
 *      Vollbreiten-Block) statt eigener Werte;
 *   2. die Rasterspalten sind `minmax(0, …)` — sonst sprengt langer Inhalt
 *      die Spalte und das Raster läuft seitlich über;
 *   3. der Kartenkopf hat eine Mindesthöhe aus Tokens; damit sind Köpfe mit
 *      und ohne Knopf gleich hoch;
 *   4. die Gruppenkacheln sind höchstens eine Rasterspalte breit (das frühere
 *      feste `max-width: 190px` war die Ursache des Handy-Überlaufs);
 *   5. die Token-Regeln tragen keine hart codierten Farben;
 *   6. die Datei steht in der node-Testliste der backend/Dockerfile.
 *
 * Die Messung im Browser (getBoundingClientRect bei 390 px und 1366 px,
 * hell und dunkel) macht tools/demo/fix5-gruppendetail.py; dieser Test
 * sichert die Regel, damit die Maße nicht still wieder auseinanderlaufen.
 */
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import test from 'node:test'

const WURZEL = new URL('../src/diakonos/', import.meta.url)
const lies = (p) => readFileSync(new URL(p, WURZEL), 'utf8')
const ohneKommentare = (t) => t.replace(/\/\*[\s\S]*?\*\//g, '')

const TOKENS = lies('tokens.css')
const DETAIL = lies('pages/GruppeDetail.vue')
const LISTE = lies('pages/Gruppen.vue')
const KARTE = lies('components/ui/DkCard.vue')

/** Regel `selektor { … }` (erste Fundstelle) ohne Kommentare. */
function regelBlock(text, selektor) {
  const t = ohneKommentare(text)
  const i = t.indexOf(selektor)
  if (i < 0) return null
  const auf = t.indexOf('{', i)
  const zu = t.indexOf('}', auf)
  return t.slice(i, zu + 1)
}

// ── 1. Ein Abstands-Token für das Raster ───────────────────────────────────
test('FIX-5 · es gibt ein Token --grid-gap, das aus der Raumleiter kommt', () => {
  const treffer = /--grid-gap:\s*([^;]+);/.exec(ohneKommentare(TOKENS))
  assert.ok(treffer, '--grid-gap in tokens.css definiert')
  assert.match(treffer[1].trim(), /^var\(--sp-[1-8]\)$/,
    'keine neue Zahl — der Abstand kommt aus der 4er-Leiter')
})

test('FIX-5 · das Raster, die Spalten und der Vollbreiten-Block nutzen dasselbe Token', () => {
  for (const [selektor, name] of [
    ['.grup-grid {', 'Raster'],
    ['.grup-spalte {', 'Spalte'],
    ['.grup-breit {', 'Vollbreiten-Block'],
  ]) {
    const block = regelBlock(DETAIL, selektor)
    assert.ok(block, `Regel ${selektor} gefunden`)
    assert.match(block, /(gap|margin-top):\s*var\(--grid-gap\)/,
      `${name}: Abstand kommt aus --grid-gap`)
  }
})

test('FIX-5 · die Detailseite setzt keinen eigenen Rasterabstand mehr', () => {
  for (const selektor of ['.grup-grid {', '.grup-spalte {', '.grup-breit {']) {
    const block = regelBlock(DETAIL, selektor)
    assert.ok(!/(gap|margin-top):\s*var\(--sp-\d\)/.test(block),
      `${selektor} trägt noch ein eigenes Maß`)
  }
})

// ── 2. Spalten dürfen nicht vom Inhalt aufgeblasen werden ──────────────────
test('FIX-5 · die Rasterspalten sind minmax(0, …) — Handy-Überlauf', () => {
  const raster = regelBlock(DETAIL, '.grup-grid {')
  assert.match(raster, /grid-template-columns:\s*minmax\(0,\s*2fr\)\s+minmax\(0,\s*1fr\)/)
  const handy = /@media\s*\(max-width:\s*768px\)\s*\{\s*\.grup-grid\s*\{([^}]*)\}/.exec(ohneKommentare(DETAIL))
  assert.ok(handy, 'Handy-Regel für .grup-grid gefunden')
  assert.match(handy[1], /grid-template-columns:\s*minmax\(0,\s*1fr\)/,
    'auch einspaltig mit minmax(0, 1fr)')
  const spalte = regelBlock(DETAIL, '.grup-spalte {')
  assert.match(spalte, /min-width:\s*0/, 'Spalte darf schrumpfen')
})

// ── 3. Kartenköpfe gleich hoch ─────────────────────────────────────────────
test('FIX-5 · DkCard bleibt unverändert (Kopfhöhe NICHT app-weit)', () => {
  // Operator-Auflage (Review Opus): DkCard wird an ~30 Stellen benutzt. Eine
  // Mindesthöhe dort hätte überall die Köpfe verändert — der Ausgleich gehört
  // ausschließlich auf die Karten DIESER Seite (siehe nächster Test).
  const kopf = regelBlock(KARTE, '.dk-ui-card-kopf {')
  assert.ok(kopf, 'Regel .dk-ui-card-kopf gefunden')
  assert.ok(!/min-height:/.test(kopf),
    'kein min-height in DkCard — sonst wirkt der Ausgleich app-weit')
})

test('FIX-5 · die Detailseite gleicht die Kartenköpfe LOKAL aus', () => {
  const t = ohneKommentare(DETAIL)
  const regel = /\.dk-screen\s*:deep\(\.dk-ui-card-kopf\)\s*\{([^}]*)\}/.exec(t)
  assert.ok(regel, 'lokale Regel .dk-screen :deep(.dk-ui-card-kopf) vorhanden')
  const min = /min-height:\s*([^;]+);/.exec(regel[1])
  assert.ok(min, 'min-height gesetzt (Karten mit/ohne Knopf gleich hoch)')
  assert.match(min[1].trim(), /^calc\(var\(--row-h\)\s*\+\s*2\s*\*\s*var\(--sp-2\)\)$/,
    'Höhe aus Tokens (--row-h + 2 × --sp-2), keine harte Zahl')
  assert.ok(!/(^|[^-])height:\s*[^;]+;/.test(regel[1]),
    'feste Höhe würde mehrzeilige Köpfe abschneiden — gewollt ist min-height')
})

test('FIX-5 · alle Karten der Detailseite gehen durch DkCard (eine Kopfhöhe)', () => {
  const tpl = DETAIL.slice(DETAIL.indexOf('<template>'), DETAIL.lastIndexOf('</template>'))
  assert.ok(!/class="[^"]*dk-ui-card-kopf/.test(tpl),
    'kein eigener Kartenkopf in der Seite')
  assert.match(tpl, /<DkCard title="Details">/)
  assert.match(tpl, /<DkCard title="Nächste Termine">/)
})

test('FIX-5 · die Verantwortlichen-Karte benutzt DkCard, keinen Eigenbau', () => {
  const datei = lies('components/VerantwortlicheKarte.vue')
  const tpl = datei.slice(datei.indexOf('<template>'), datei.lastIndexOf('</template>'))
  assert.match(tpl, /<DkCard title="Verantwortliche">/, 'gleicher Kopf wie die übrigen Karten')
})

// ── 4. Gruppenkacheln: keine Breite über die Rasterspalte hinaus ───────────
test('FIX-5 · die Gruppenkachel ist höchstens eine Rasterspalte breit', () => {
  const kachel = regelBlock(LISTE, '.gr-kachel {')
  assert.ok(kachel, 'Regel .gr-kachel gefunden')
  const max = /max-width:\s*([^;]+);/.exec(kachel)
  assert.ok(max, 'max-width gesetzt')
  assert.equal(max[1].trim(), '100%',
    'früher 190px — am Handy breiter als die 132-px-Spalte, das war DEV-1')
  assert.match(kachel, /width:\s*100%/, 'die Kachel füllt genau ihre Spalte')
})

test('FIX-5 · der Kachelstreifen bleibt in der Seite und scrollt selbst', () => {
  const streifen = regelBlock(LISTE, '.gr-grid-scroll {')
  assert.match(streifen, /overflow-x:\s*auto/, 'waagerechtes Scrollen bleibt gewollt')
  assert.match(streifen, /min-width:\s*0/, 'Streifen darf die Seite nicht breiter machen')
  assert.match(streifen, /max-width:\s*100%/)
})

test('FIX-5 · jedes Raster trägt eine Marke für die Messung im Browser', () => {
  const tpl = LISTE.slice(LISTE.indexOf('<template>'), LISTE.lastIndexOf('</template>'))
  assert.match(tpl, /class="gr-grid-scroll" data-raster="meine"/)
  assert.match(tpl, /class="gr-grid-scroll" data-raster="alle"/)
})

// ── 5. Keine harten Farben in den geänderten Regeln ────────────────────────
test('FIX-5 · die geänderten Regeln tragen keine hart codierten Farben', () => {
  const bloecke = [
    regelBlock(DETAIL, '.grup-grid {'),
    regelBlock(DETAIL, '.grup-datenwert'),
    regelBlock(LISTE, '.gr-kachel {'),
    regelBlock(KARTE, '.dk-ui-card-kopf {'),
  ]
  for (const block of bloecke) {
    assert.ok(block, 'Regel vorhanden')
    const farben = block.match(/(color|background|border-color)\s*:\s*([^;]+)/g) || []
    for (const f of farben) {
      assert.ok(!/#[0-9a-fA-F]{3,8}\b/.test(f) && !/\b(rgb|hsl)\(/.test(f),
        `harter Farbwert: ${f.trim()}`)
    }
  }
})

// ── 6. Der Test läuft im Image ─────────────────────────────────────────────
test('FIX-5 · die Testdatei steht in der node-Testliste der backend/Dockerfile', (t) => {
  // Im Abbild liegt nur frontend/ — die Dockerfile steht dort NICHT. Geprüft
  // wird der Eintrag, wo sie erreichbar ist; im Abbild entfällt der Nachweis
  // (Muster: fix3).
  const kandidaten = [
    new URL('../../backend/Dockerfile', import.meta.url),
    new URL('../../../backend/Dockerfile', import.meta.url),
  ]
  const treffer = kandidaten.find((u) => existsSync(u))
  if (!treffer) return t.skip('backend/Dockerfile im Abbild nicht vorhanden')
  const dockerfile = readFileSync(treffer, 'utf8')
  assert.match(dockerfile, /tests\/fix5-\*\.test\.mjs/, 'Glob tests/fix5-*.test.mjs eingetragen')
})

test('FIX-5 · im Build-Abbild (frontend/) stehen alle geänderten Maße', (t) => {
  // Zweiter, unabhängiger Nachweis: im Abbild liegt das gebaute frontend/ samt
  // src/. Fehlt es (Worktree-Lauf), entfällt der Nachweis.
  const kandidaten = [new URL('../../src/diakonos/', import.meta.url)]
  const wurzel = kandidaten.find((u) => existsSync(u))
  if (!wurzel) return t.skip('src/diakonos im Abbild nicht vorhanden')
  const tokenImAbbild = readFileSync(new URL('tokens.css', wurzel), 'utf8')
  assert.match(tokenImAbbild, /--grid-gap:\s*var\(--sp-4\)/, 'Token ist im Abbild vorhanden')
  const karteImAbbild = readFileSync(new URL('components/ui/DkCard.vue', wurzel), 'utf8')
  assert.ok(!/min-height:/.test(regelBlock(karteImAbbild, '.dk-ui-card-kopf {')),
    'DkCard im Abbild ohne Kopfhöhe (nicht app-weit)')
  const detailImAbbild = readFileSync(new URL('pages/GruppeDetail.vue', wurzel), 'utf8')
  assert.match(detailImAbbild, /\.dk-screen\s*:deep\(\.dk-ui-card-kopf\)\s*\{/,
    'lokaler Kopfausgleich ist im Abbild vorhanden')
})

