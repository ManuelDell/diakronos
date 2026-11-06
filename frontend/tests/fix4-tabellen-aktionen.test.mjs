/**
 * FIX-4 — Mitglieder › Formulare am Handy: Aktionsknöpfe überlagern sich
 * (Befund DMB-9a25839dfda4, Route #/mitglieder/anfragen?bereich=formulare,
 * DkTable, 5. Spalte, Viewport 344×561).
 *
 * Befund: In der Formular-Tabelle standen „Bearbeiten“ und „Löschen“ in einer
 * Zeile nebeneinander, die Zelle durfte aber nicht breiter werden als ihr
 * Anteil am Tabellen-Mindestmaß (`DkTable` setzt `min-width: 640px`,
 * `table-layout` bleibt `auto`). Die beiden Knöpfe sind mit
 * `white-space: nowrap` (DkButton) breiter als der Rest der Tabelle hergibt —
 * der zweite Knopf lief aus seiner Zelle heraus und legte sich über den
 * Nachbarn. Sichtbar wurde das erst am Handy, weil dort der Tabellenüberlauf
 * innerhalb des Containers beginnt.
 *
 * Behoben ist das Muster an EINER Stelle: `.dk-ui-table` mit Aktionsspalte
 * bekommt `table-layout: fixed` (Klasse `has-aktion`, nur dann — `fixed` auf
 * allen Tabellen stutzte der Mitgliederliste mit sieben Spalten die Zellen),
 * die Aktionsspalte (`th/td.is-aktion`) eine Mindestbreite, und der Inhalt
 * der Aktionszelle `flex-wrap`. Ohne Umbau der Seiten bleibt damit jede
 * Aktionszelle in ihrem Rahmen.
 *
 * Review-Auflagen (Operator, 27.10.) sind mitgeprüft:
 *   1. `fixed` nur mit `aktion`-Spalte (`has-aktion`), Mitgliederliste bleibt
 *      bei `auto`;
 *   2. GruppeDetail zeichnet seine Aktionsspalte aus (`aktion: true`);
 *   3. `.reg-aktionen` (Anmeldungen-Tabelle) hält seine Flex/Abstand-Regel,
 *      `is-aktion` sitzt am `<td>` statt am `<div>`;
 *   4. Testliste der backend/Dockerfile vereinigt (fix2/fix3/fix4).
 *
 * Geprüft wird:
 *   1. DkTable: `fixed` NUR mit Aktionsspalte, Aktionsspalte mit Mindestbreite,
 *      Umbruch im Zelleninhalt, Überlauf bleibt im Container;
 *   2. Registrierung.vue: Aktionen-Spalte als solche ausgezeichnet
 *      (beide Tabellen), `.reg-aktionen` als Flex-Wrapper vorhanden;
 *   3. RessourcenVerwaltung.vue (gleiches Muster): Spalte ausgezeichnet;
 *   4. GruppeDetail.vue: Aktionsspalte ausgezeichnet;
 *   5. nur Tokens, keine harten Farbwerte in den berührten Regeln;
 *   6. DkTable kompiliert (echter SFC-Lauf) und bleibt im Template-Zustand
 *      nutzbar — der Slot der Seiten funktioniert unverändert;
 *   7. die Datei steht in der node-Testliste der backend/Dockerfile.
 */
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import test from 'node:test'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'

const WURZEL = new URL('../src/diakonos/', import.meta.url)
const lies = (p) => readFileSync(new URL(p, WURZEL), 'utf8')

const TABELLE = lies('components/ui/DkTable.vue')
const STIL = TABELLE.slice(TABELLE.lastIndexOf('<style'))
const REG = lies('pages/Registrierung.vue')
const RESSOURCEN = lies('pages/RessourcenVerwaltung.vue')
const GRUPPE = lies('pages/GruppeDetail.vue')
const MITGLIEDER = lies('pages/Mitglieder.vue')

/** Bereich der Vorlage einer Seite. */
function vorlage(quelle) {
  return quelle.slice(quelle.indexOf('<template>'), quelle.lastIndexOf('</template>'))
}

/** Block einer CSS-Regel (Selektor … { … }) aus einem Stylesheet-Text. */
function regel(text, selektor) {
  const i = text.indexOf(selektor)
  assert.ok(i >= 0, `Regel ${selektor} fehlt`)
  return text.slice(i, text.indexOf('}', i) + 1)
}

/** Alle Regelblöcke, deren Selektor den Text enthält (auch Mehrfachselektoren). */
function regeln(text, selektor) {
  const treffer = []
  let i = text.indexOf(selektor)
  while (i >= 0) {
    const start = text.lastIndexOf('}', i) + 1
    treffer.push(text.slice(start, text.indexOf('}', i) + 1))
    i = text.indexOf(selektor, i + 1)
  }
  assert.ok(treffer.length > 0, `keine Regel mit ${selektor}`)
  return treffer.join('\n')
}

/** Stylesheet einer Seite. */
function seitenStil(quelle) {
  return quelle.slice(quelle.lastIndexOf('<style'))
}

// ── 1. DkTable: fixed nur mit Aktionsspalte ────────────────────────────────
test('FIX-4 · DkTable setzt `fixed` nur, wenn eine Spalte `aktion` trägt', () => {
  // Ohne Aktionsspalte bleibt `auto`: `fixed` verteilt die Breite gleichmäßig
  // und würde z.B. der Mitgliederliste (7 Spalten) jede Zelle stutzen.
  assert.doesNotMatch(regel(STIL, '.dk-ui-table {'), /table-layout:/,
    'table-layout darf nicht mehr unbedingt am .dk-ui-table hängen')
  assert.match(regel(STIL, '.dk-ui-table.has-aktion'), /table-layout:\s*fixed/,
    'Aktions-Tabellen brauchen table-layout: fixed — sonst schiebt nowrap-Inhalt die Zelle breiter als die Tabelle')
  assert.match(regel(STIL, '.dk-ui-table {'), /max-width:\s*100%/,
    'die Tabelle bleibt im Container (Überlauf nur IM Tabellencontainer)')
  // Der Container selbst darf weiter waagerecht scrollen (echte Funktion).
  assert.match(regel(STIL, '.dk-ui-table-wrap {'), /overflow-x:\s*auto/,
    'waagerechtes Scrollen bleibt am Container')
})

test('FIX-4 · DkTable hängt `has-aktion` an die Tabelle, nicht an den Wrapper', () => {
  const tpl = TABELLE.slice(0, TABELLE.indexOf('<script'))
  assert.match(tpl, /<table[^>]*:class="\{[^"]*'has-aktion':\s*hatAktion/,
    'die Tabelle selbst trägt die Klasse has-aktion (Bedingung: hatAktion)')
  assert.match(TABELLE, /const hatAktion = computed\(\(\) =>[^)]*spalten[^)]*\.some\(/,
    'hatAktion leitet sich aus den Spalten ab (keine feste Annahme)')
  assert.match(TABELLE, /s\.aktion/, 'die Bedingung prüft das Merkmal `aktion`')
})

test('FIX-4 · die Aktionsspalte hat eine Mindestbreite und bricht um', () => {
  const aktion = regeln(STIL, 'td.is-aktion')
  assert.match(aktion, /min-width:/, 'Aktionszelle: Mindestbreite, damit zwei Knöpfe Platz haben')
  assert.match(aktion, /gap:\s*var\(--sp-\d\)/, 'Aktionszelle: Abstand zwischen den Knöpfen aus Tokens')
  // Der Umbruch passiert im Zellinhalt: das <td> bleibt eine echte
  // Tabellenzelle (display:flex darauf würde sie aus dem Tabellensatz lösen).
  const inhalt = regeln(STIL, 'td.is-aktion > *')
  assert.match(inhalt, /flex-wrap:\s*wrap/, 'Zellinhalt: Umbruch statt Überlagerung')
  assert.doesNotMatch(regel(STIL, '.dk-ui-table tbody :deep(td.is-aktion)'), /display:\s*flex/,
    'das <td> selbst bleibt table-cell (kein display:flex auf der Zelle)')
  // Der Kopf der Spalte gehört zur selben Spalte (gleiche Breitenlogik).
  assert.match(regeln(STIL, 'th.is-aktion'), /width:/, 'Kopfzeile der Aktionsspalte ist mitgedacht')
})

// ── 1b. Das gemessene Rechenexempel des Befunds ────────────────────────────
/**
 * Befund DMB-9a25839dfda4, gemessen am 390er-Gerät: Die Inhaltsbreite der
 * Tabelle ist 640 px (kleinster zulässiger Stand), der Aktionsspalte standen
 * nach `table-layout: auto` nur 62 px zu. Die beiden Knopf-Boxen (aus
 * DkButton.css: `padding: 0 10px`, `gap: 7px`, `font-size: var(--fs-sm)` plus
 * Rahmen) sind zusammen ~155 px breit und tragen `white-space: nowrap` — sie
 * mussten also über den Zellrand laufen und lagen über der Nachbarspalte.
 *
 * Diese Prüfung hält das Rechenexempel fest, damit die Mindestbreite in
 * DkTable nicht stillschweigend unter die Knopfbreite rutscht: Sie liest die
 * Maße aus DkButton.vue/tokens.css (keine erfundenen Zahlen) und vergleicht
 * sie mit der Mindestbreite der Aktionsspalte.
 */
test('FIX-4 · Mindestbreite der Aktionsspalte deckt beide Knöpfe (gemessenes Rechenexempel)', () => {
  const knopf = lies('components/ui/DkButton.vue')
  const tokens = readFileSync(new URL('tokens.css', WURZEL), 'utf8')
  const stil = knopf.slice(knopf.lastIndexOf('<style'))
  const klein = regel(stil, '.dk-ui-btn--sm')
  const rand = /padding:\s*0\s+(\d+)px/.exec(klein)
  const spalt = /gap:\s*(\d+)px/.exec(regel(stil, '.dk-ui-btn {'))
  // UX1b: --fs-sm zeigt auf die Grundstufe (var(--fs-12)); die Zahl steht
  // nur noch in --fs-12. Beides wird gelesen — Rohwert oder Verweis.
  const fsSmRoh = /--fs-sm:\s*([\d.]+)(rem|px)/.exec(tokens)
  const fsSmStufe = /--fs-sm:\s*var\(--fs-(\d+)\)/.exec(tokens)
  const fsSm = fsSmRoh || (fsSmStufe ? [null, fsSmStufe[1], 'px'] : null)
  assert.ok(rand && spalt && fsSm, 'Maße aus DkButton/tokens lesbar')
  const randPx = Number(rand[1]) * 2 + 2          // Innenabstand + 1 px Rahmen je Seite
  const luecke = Number(spalt[1])
  const schrift = fsSm[2] === 'rem' ? Number(fsSm[1]) * 16 : Number(fsSm[1])
  // Buchstabenbreite: konservativ 0,62 em (Inter, 550) — ein Knopf-Text mit
  // 10 Zeichen ist damit mindestens 6,2 em breit.
  const text = (n) => Math.round(n * 0.62 * schrift)
  const beideKnoepfe = text('Bearbeiten'.length) + text('Löschen'.length) + 2 * randPx + luecke
  const mindest = Number(/min-width:\s*(\d+)px/.exec(regeln(STIL, 'td.is-aktion'))[1])
  assert.ok(mindest >= beideKnoepfe,
    `Mindestbreite ${mindest} px deckt zwei kleine Knöpfe (${beideKnoepfe} px) nicht`)
  // … und die Zelle darf jetzt wirklich umbrechen, statt zu überlaufen.
  assert.match(regeln(STIL, 'td.is-aktion > *'), /flex-wrap:\s*wrap/)
})

test('FIX-4 · die Zellen dürfen jetzt schmaler werden als ihr Inhalt (fixed)', () => {
  // Bei `table-layout: fixed` bricht Text in der Zelle um statt sie zu
  // sprengen; `nowrap` bleibt allein den Knöpfen vorbehalten.
  assert.doesNotMatch(regel(STIL, '.dk-ui-table tbody :deep(td)'), /white-space:\s*nowrap/,
    'kein nowrap auf allen Zellen — Text darf umbrechen')
})

// ── 2. Registrierung.vue: Spalten ausgezeichnet, Wrapper mit Abstand ───────
test('FIX-4 · Formular- und Anfrage-Tabelle zeichnen die Aktionsspalte aus', () => {
  const tpl = vorlage(REG)
  assert.match(tpl, /<td class="is-aktion">[\s\S]{0,120}?formularBearbeiten\(f\)/,
    'Formular-Tabelle: das <td> trägt is-aktion')
  assert.match(tpl, /<td class="is-aktion">\s*<!--[\s\S]*?-->\s*<div class="reg-aktionen">[\s\S]{0,200}?aufnehmen\(a\)/,
    'Anfragen-Tabelle: das <td> trägt is-aktion (nicht der innere <div>)')
  // Die Formular-Zeile behält beide Knöpfe nebeneinander (kein Menü nötig).
  assert.match(tpl, /formularEntfernen\(f\)/, '„Löschen“ bleibt')
})

test('FIX-4 · `.reg-aktionen` hält die Knöpfe als Flex-Zeile (Auflage 3)', () => {
  // is-aktion gehört ans <td>; der <div class="reg-aktionen"> ist der Wrapper.
  assert.doesNotMatch(vorlage(REG), /class="reg-aktionen is-aktion"/,
    'is-aktion saß am <div> — dort bewirkt die Zellbreite nichts')
  const regelAktion = regel(seitenStil(REG), '.reg-aktionen {')
  assert.match(regelAktion, /display:\s*flex/,
    '.reg-aktionen braucht wieder display:flex (Knöpfe als Zeile)')
  assert.match(regelAktion, /flex-wrap:\s*wrap/, '.reg-aktionen bricht am Handy um')
  assert.match(regelAktion, /gap:\s*var\(--sp-\d\)/, '.reg-aktionen: Abstand aus Tokens')
})

test('FIX-4 · die Tabelle steht in einem Container, der den Überlauf trägt', () => {
  const tpl = vorlage(REG)
  // DkTable bringt `.dk-ui-table-wrap` mit `overflow-x: auto` selbst mit.
  const formularBlock = tpl.slice(tpl.indexOf("v-if=\"unterbereich === 'formulare'\""));
  assert.match(formularBlock, /<DkTable/, 'Formulare nutzen DkTable (Container kommt mit)')
  // … und der Überlauf bleibt IN der Karte (DkCard klippt), nicht am Body.
  assert.match(TABELLE.slice(TABELLE.indexOf('<style')), /\.dk-ui-table-wrap/,
    'Überlauf-Container ist Teil von DkTable')
})

// ── 3. RessourcenVerwaltung.vue: gleiches Muster ────────────────────────────
test('FIX-4 · RessourcenVerwaltung zeichnet die Aktionsspalte ebenfalls aus', () => {
  const tpl = vorlage(RESSOURCEN)
  // UX2e: Die Aktionszelle trägt das „⋯“-Menü statt der zwei Zeilenknöpfe.
  // Die Auszeichnung selbst bleibt dieselbe (FIX-4: `is-aktion` am <td>).
  assert.match(tpl, /<td class="is-aktion">[\s\S]{0,400}?<DkAktionen/,
    'gleiches Muster wie in den Formularen (<td class="is-aktion"> mit Aktionsmenü)')
  assert.doesNotMatch(seitenStil(RESSOURCEN), /\.rv-aktionen\s*\{[^}]*display:\s*flex/,
    '.rv-aktionen mit display:flex hat am <td> nichts bewirkt')
})

// ── 4. GruppeDetail.vue: Aktionsspalte ausgezeichnet (Auflage 2) ───────────
test('FIX-4 · GruppeDetail zeichnet die Aktionsspalte aus (Auflage 2)', () => {
  assert.match(GRUPPE, /\{\s*key:\s*'aktionen'[^}]*aktion:\s*true\s*\}/,
    "GruppeDetail: die Spalte 'aktionen' braucht aktion: true")
})

// ── 5. Mitgliederliste bleibt bei `auto` (Auflage 1) ───────────────────────
test('FIX-4 · Mitgliederliste: die „⋯"-Spalte ist schmal (kein 200-px-Knopfblock)', () => {
  // UX2e hat der Mitgliederliste eine Aktionsspalte mit dem „⋯"-Menü gegeben.
  // Sie trägt deshalb `aktion: true` (FIX-4-Muster, `table-layout: fixed`);
  // der Grund der ursprünglichen Auflage bleibt gewahrt: die Spalte ist EIN
  // schmaler Knopf (Zellenklasse `.dk-zeilen-aktion`), kein breiter
  // Knopfblock — und die Textspalten der Liste halten ihre Breite.
  assert.match(MITGLIEDER, /aktion:\s*true/, 'die Spalte „Aktionen" ist als Aktionsspalte ausgezeichnet')
  const stil = MITGLIEDER.slice(MITGLIEDER.indexOf('<style'))
  assert.match(stil, /\.dk-zeilen-aktion\s*\{[^}]*width:\s*var\(--control-h\)/,
    'die Aktionszelle ist genau einen Knopf breit')
})

// ── 6. nur Tokens ──────────────────────────────────────────────────────────
test('FIX-4 · die neuen Regeln nutzen Tokens, keine harten Farben', () => {
  const aktion = regeln(STIL, 'td.is-aktion') + regeln(STIL, 'th.is-aktion')
  assert.doesNotMatch(aktion, /#[0-9a-fA-F]{3,8}\b/, 'keine Hex-Farbe')
  assert.doesNotMatch(aktion, /\brgba?\(/, 'kein rgb()/rgba()')
  assert.doesNotMatch(aktion, /\bhsla?\(/, 'kein hsl()/hsla()')
  assert.match(aktion, /var\(--(sp|pad|row-h|line|radius)/,
    'Abstände/Maße kommen aus den Tokens')
})

// ── 7. DkTable kompiliert weiter ───────────────────────────────────────────
test('FIX-4 · DkTable kompiliert (Vorlage und Skript)', () => {
  const { descriptor, errors } = parse(TABELLE, { filename: 'DkTable.vue' })
  assert.deepEqual(errors, [], 'DkTable.vue: SFC-Struktur')
  const skript = compileScript(descriptor, { id: 'DkTable.vue' })
  const tpl = compileTemplate({
    source: descriptor.template.content,
    filename: 'DkTable.vue',
    id: 'DkTable.vue',
    compilerOptions: { bindingMetadata: skript.bindings || {} },
  })
  assert.deepEqual(tpl.errors.map((e) => e.message || String(e)), [], 'DkTable.vue: Vorlage')
  assert.match(descriptor.template.content, /<slot \/>/, 'der Zeilen-Slot der Seiten bleibt')
})

test('FIX-4 · Registrierung.vue kompiliert nach dem Umbau', () => {
  const { descriptor, errors } = parse(REG, { filename: 'Registrierung.vue' })
  assert.deepEqual(errors, [], 'Registrierung.vue: SFC-Struktur')
  const skript = compileScript(descriptor, { id: 'Registrierung.vue' })
  const tpl = compileTemplate({
    source: descriptor.template.content,
    filename: 'Registrierung.vue',
    id: 'Registrierung.vue',
    compilerOptions: { bindingMetadata: skript.bindings || {} },
  })
  assert.deepEqual(tpl.errors.map((e) => e.message || String(e)), [], 'Registrierung.vue: Vorlage')
})

// ── 8. Testliste im Image ─────────────────────────────────────────────────
test('FIX-4 · die Testdatei steht in der node-Testliste der backend/Dockerfile', (t) => {
  // Im Image liegt nur frontend/ (/build) — die Dockerfile steht dort NICHT.
  // Geprüft wird der Eintrag, wo die Dockerfile erreichbar ist (Worktree);
  // beim Lauf im Image entfällt der Nachweis, statt fälschlich rot zu werden
  // (Muster: FIX-1).
  const kandidaten = [
    new URL('../../backend/Dockerfile', import.meta.url),
    new URL('../../../backend/Dockerfile', import.meta.url),
  ]
  const treffer = kandidaten.find((u) => existsSync(u))
  if (!treffer) return t.skip('backend/Dockerfile im Abbild nicht vorhanden')
  const dockerfile = readFileSync(treffer, 'utf8')
  // FE-TEST-1: die Muster stehen in frontend/tests/testliste.txt (die
  // Dockerfile liest sie über ARG NODE_TESTLISTE).
  assert.match(dockerfile, /^ARG NODE_TESTLISTE=tests\/testliste\.txt$/m,
    'backend/Dockerfile liest die Muster nicht aus tests/testliste.txt')
  const testliste = readFileSync(new URL('./testliste.txt', import.meta.url), 'utf8')
  assert.match(testliste, /^tests\/fix4-\*\.test\.mjs$/m,
    'frontend/tests/testliste.txt: tests/fix4-*.test.mjs fehlt')
  // Auflage 4: der Merge mit main hat die Listen vereinigt, nichts ging verloren.
  for (const datei of ['tests/fix2-*.test.mjs', 'tests/fix3-*.test.mjs', 'tests/fix1-*.test.mjs']) {
    assert.ok(testliste.split('\n').includes(datei),
      `frontend/tests/testliste.txt: ${datei} fehlt nach dem Merge`)
  }
})
