/**
 * FIX-1 — Profil am Handy: Theme-Auswahl einklappbar (Befund DMB-a2d846875201).
 *
 * Befund (24.10., Route #/profile, Viewport 344×561, Element
 * `div.dk-bn-sheet-theme`): „Einklappen nicht möglich, nur durch Auswahl eines
 * Elements möglich“. Gemeint ist das „Mehr“-Blatt der Handy-Navigation
 * (AppBottomNav.vue), in dem die Theme-Zeile sitzt.
 *
 * Behoben ist der Kopf: er war reine Anzeige und ist jetzt ein Knopf, der das
 * Blatt schließt. Tippen außerhalb, Escape und Zurück schlossen schon vorher —
 * hier nur abgesichert, damit das nicht still zurückfällt.
 *
 * Geprüft wird:
 *   1. das Markup — Kopf ist ein Knopf mit Beschriftung, Griff und Pfeil,
 *      die Überlappung schließt, die Theme-Zeile bleibt ausgenommen;
 *   2. Escape/Fokus sind verdrahtet und aria-expanded sitzt am „Mehr“-Knopf
 *      (nicht am Schließknopf);
 *   3. Schließfläche groß genug (44 px), Griff sichtbar, nur Tokens —
 *      keine harten Farbwerte (Hell- und Dunkelmodus aus tokens.css);
 *   4. die Datei steht in der node-Testliste der backend/Dockerfile.
 */
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import test from 'node:test'

import { KOPF_ARIA, KOPF_TEXT } from '../src/diakonos/components/mehrBlatt.mjs'

const WURZEL = new URL('../src/diakonos/', import.meta.url)
const lies = (p) => readFileSync(new URL(p, WURZEL), 'utf8')

const NAV = lies('components/AppBottomNav.vue')
const TPL = NAV.slice(NAV.indexOf('<template>'), NAV.lastIndexOf('</template>'))
const SKRIPT = NAV.slice(NAV.indexOf('<script setup>'), NAV.indexOf('</script>'))
const STIL = NAV.slice(NAV.lastIndexOf('<style'))

/** Bereich des Kopfknopfes bis zur Theme-Zeile. */
function kopfBereich() {
  const start = TPL.lastIndexOf('<button', TPL.indexOf('dk-bn-sheet-kopf'))
  return { start, text: TPL.slice(start, TPL.indexOf('dk-bn-sheet-theme')) }
}

// ── 1. Kopf-Beschriftung ───────────────────────────────────────────────────
test('FIX-1 · die Kopf-Beschriftung nennt sichtbar „Navigation“ und im aria-label das Schließen', () => {
  assert.equal(KOPF_TEXT, 'Navigation')
  assert.match(KOPF_ARIA, /^Navigation/)
  assert.match(KOPF_ARIA, /schlie/)
})

// ── 2. Markup: der Kopf ist wirklich ein Klickziel ─────────────────────────
test('FIX-1 · der Blattkopf ist ein Knopf, der das Blatt schließt', () => {
  const { start, text: kopf } = kopfBereich()
  assert.ok(start > 0, 'Kopf-Bereich gefunden')
  assert.equal(TPL.slice(start, start + 7), '<button', 'Kopf ist ein <button>')
  assert.match(kopf, /class="dk-bn-sheet-kopf"/, 'Kopf trägt seine Klasse')
  assert.match(kopf, /type="button"/, 'kein Formularabsenden')
  assert.match(kopf, /:aria-label="KOPF_ARIA"/, 'vorgelesener Hinweis „schließen“')
  assert.match(kopf, /@click="closeMore"/, 'Tippen schließt')
  assert.match(kopf, /dk-bn-sheet-handle/, 'der Griff liegt IN der Schließfläche')
  assert.match(kopf, /dk-bn-sheet-pfeil/, 'der Pfeil liegt IN der Schließfläche')
  assert.match(kopf, /dk-bn-sheet-title/, 'die Überschrift liegt IN der Schließfläche')
  // Ein reines Anzeige-Div vor dem Knopf wäre der alte Zustand.
  assert.ok(!/<div class="dk-bn-sheet-handle">/.test(TPL), 'kein toter Griff mehr')
  assert.ok(!/<div class="dk-bn-sheet-title">/.test(TPL), 'keine tote Überschrift mehr')
})

test('FIX-1 · der Kopf umfasst die Theme-Auswahl NICHT (sonst schlösse das Umschalten mit)', () => {
  const { text: kopf } = kopfBereich()
  assert.ok(!/dk-bn-sheet-theme/.test(kopf), 'Theme-Zeile liegt hinter dem Kopf')
  const thema = TPL.slice(TPL.indexOf('class="dk-bn-sheet-theme"'), TPL.indexOf('dk-bn-sheet-grid'))
  assert.match(thema, /@click="\$emit\('toggle-theme'\)"/,
    'der Theme-Schalter schaltet nur um')
  assert.ok(!/closeMore/.test(thema), 'die Theme-Zeile schließt das Blatt nicht')
})

test('FIX-1 · Überlappung schließt nur bei Tipp auf sie selbst (@click.self)', () => {
  assert.match(TPL, /class="dk-bn-sheet-overlay"[^>]*@click\.self="closeMore"/)
})

// ── 3. Escape, Fokus, Zustand ──────────────────────────────────────────────
test('FIX-1 · Escape ist über die Fokusführung verdrahtet', () => {
  assert.match(SKRIPT, /useDialogFokus\(showMore,\s*sheetFenster,\s*closeMore\)/,
    'Escape und Tab-Kreis schließen über closeMore')
  assert.match(TPL, /aria-modal="true"/, 'modales Fenster')
  assert.match(TPL, /ref="sheetFenster"/, 'Fokusziel vorhanden')
})

test('FIX-1 · aria-expanded sitzt am „Mehr“-Knopf, nicht am Schließknopf', () => {
  const mehrKnopf = TPL.slice(TPL.lastIndexOf('<button', TPL.indexOf('>Mehr<')), TPL.indexOf('>Mehr<'))
  assert.match(mehrKnopf, /:aria-expanded="showMore"/, '„Mehr“ sagt, ob das Blatt offen ist')
  const { text: kopf } = kopfBereich()
  assert.ok(!/aria-expanded/.test(kopf),
    'der Schließknopf trägt kein aria-expanded (er ist immer „offen“)')
})

// ── 4. Schließflächen und Tokens ───────────────────────────────────────────
test('FIX-1 · die Schließfläche ist mindestens 44 px hoch und ohne harte Farben', () => {
  const alle = STIL.replace(/\/\*[\s\S]*?\*\//g, '')
  const kopf = /\.dk-bn-sheet-kopf\s*\{([^}]*)\}/.exec(alle)
  assert.ok(kopf, 'Regel .dk-bn-sheet-kopf gefunden')
  const hoehe = /min-height:\s*(\d+)px/.exec(kopf[1])
  assert.ok(hoehe, 'min-height gesetzt')
  assert.ok(Number(hoehe[1]) >= 44, `Trefferfläche ${hoehe[1]}px ist zu klein`)

  // Keine hart codierten Farbwerte im Blatt-Stil: nur Tokens/Funktionen.
  const farben = alle.match(/(^|[;{\s])(color|background|border-color)\s*:\s*([^;]+)/g) || []
  for (const f of farben) {
    assert.ok(!/#[0-9a-fA-F]{3,8}\b/.test(f) && !/\b(rgb|hsl)\(/.test(f),
      `harter Farbwert: ${f.trim()}`)
  }
})

test('FIX-1 · der Griffstrich bleibt sichtbar (span braucht display:block)', () => {
  assert.match(TPL, /<span class="dk-bn-sheet-handle"/, 'Griff ist ein span im Knopf')
  const regel = /\.dk-bn-sheet-handle\s*\{([^}]*)\}/.exec(STIL.replace(/\/\*[\s\S]*?\*\//g, ''))
  assert.ok(regel, 'Regel .dk-bn-sheet-handle gefunden')
  assert.match(regel[1], /display:\s*block/, 'ohne display:block verschwindet der Strich')
  assert.match(regel[1], /height:\s*4px/)
  assert.match(regel[1], /background:\s*var\(--dk-border\)/, 'Farbe aus Tokens (hell/dunkel)')
})

test('FIX-1 · der Pfeil nutzt die Textfarbe des Themes', () => {
  const pfeil = /\.dk-bn-sheet-pfeil\s*\{([^}]*)\}/.exec(STIL.replace(/\/\*[\s\S]*?\*\//g, ''))
  assert.ok(pfeil, 'Regel .dk-bn-sheet-pfeil gefunden')
  assert.match(pfeil[1], /color:\s*var\(--dk-text-muted\)/)
})

// ── 5. Der Test läuft im Image ─────────────────────────────────────────────
test('FIX-1 · die Testdatei steht in der node-Testliste der backend/Dockerfile', (t) => {
  // Im Image liegt nur frontend/ (/build) — die Dockerfile steht dort NICHT.
  // Geprüft wird der Eintrag, wo die Dockerfile erreichbar ist (Worktree);
  // beim Lauf im Image oder in einem Mount ohne Repo entfällt der Nachweis,
  // statt fälschlich rot zu werden (Muster: uxc3b).
  const kandidaten = [
    new URL('../../backend/Dockerfile', import.meta.url),
    new URL('../../../backend/Dockerfile', import.meta.url),
  ]
  const treffer = kandidaten.find((u) => existsSync(u))
  if (!treffer) return t.skip('backend/Dockerfile im Abbild nicht vorhanden')
  const dockerfile = readFileSync(treffer, 'utf8')
  assert.match(dockerfile, /tests\/fix1-\*\.test\.mjs/, 'Globb tests/fix1-*.test.mjs eingetragen')
})
