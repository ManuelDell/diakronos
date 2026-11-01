/**
 * ON-0a — Wächter: EINE CSS-Quelle (tokens.css), auch für Server-Seiten.
 *
 * Was dieser Test festhält (Karte ON-0a, S1 + S3):
 *
 *  S1  Die beiden Stylesheets der Server-Seiten werden unter FESTEN Namen
 *      gebaut und NUR dort definiert:
 *        src/diakonos/tokens.css -> dist/diakronos-tokens.css
 *        src/ssot/seiten.css     -> dist/diakronos-seiten.css
 *      Das Grund-Stylesheet ist KEINE zweite Farbquelle: es verwendet
 *      ausschließlich `var(--…)` aus tokens.css.
 *
 *  S3  In den Vue-Quellen der neuen Bereiche stehen keine festen Farb-,
 *      Schrift- oder Radius-Werte (die Detailprüfung der größeren Fläche
 *      macht `waechter-tokens.test.mjs`).
 *
 * Der Backend-Teil (keine Hex-Werte in serverseitigem HTML, Bestandsliste
 * `tools/css-ssot-bestand.txt` darf nur schrumpfen) steht in
 * `backend/tests/test_on0a_css_ssot.py` — dort, wo die Vorlagen liegen.
 *
 * Läuft wie die übrigen Frontend-Tests im Docker-Build (node --test).
 */
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs'

const SRC = new URL('../src/', import.meta.url)
const WURZEL = new URL('../', import.meta.url)

// Feste Farbe: #rgb/#rrggbb/#rrggbbaa, rgb()/rgba(), hsl()/hsla().
const FARB_MUSTER = /#[0-9a-fA-F]{3,8}\b|\brgba?\s*\(|\bhsla?\s*\(/g
// Feste Schriftfamilie: `font-family:` mit einem KONKRETEN Wert. `inherit`
// und `var(--…)` sind erlaubt — sie bringen keine eigene Wahrheit mit.
// Der Wert wird einzeln geprüft (Lookahead im Gesamtmuster wäre unzuverlässig,
// weil der Treffer dann schon vor dem Wert beginnt).
const SCHRIFT_MUSTER = /font-family\s*:\s*([^;}]*)/gi
const SCHRIFT_ERLAUBT = /^(inherit|var\(--[\w-]+\))$/i

function findeFesteSchriften(text) {
  const treffer = []
  for (const m of text.matchAll(SCHRIFT_MUSTER)) {
    const wert = m[1].trim().replace(/\s*!important$/i, '').trim()
    if (SCHRIFT_ERLAUBT.test(wert)) continue
    treffer.push(m[0].trim())
  }
  return treffer
}
// Feste Radius-Zahl: `border-radius: 8px` (0 und 50% sind erlaubt — Kreis/Reset).
const RADIUS_MUSTER = /border-radius\s*:\s*(?!var\(|0(?:px)?\s*[;}]|50%)[0-9.]+/gi

function lies(relativ) {
  return readFileSync(new URL(relativ, SRC), 'utf8')
}

// ── 1 · Das Grund-Stylesheet ist keine zweite Farbquelle ───────────────────
{
  const seiten = lies('ssot/seiten.css')

  const farben = seiten.match(FARB_MUSTER) || []
  assert.deepEqual(
    farben, [],
    'src/ssot/seiten.css darf KEINE Farbwerte tragen — alles über var(--…): ' +
      farben.join(', '),
  )

  const schriften = findeFesteSchriften(seiten)
  assert.deepEqual(
    schriften, [],
    'src/ssot/seiten.css darf keine feste Schriftfamilie setzen: ' + schriften.join(', '),
  )

  const radien = seiten.match(RADIUS_MUSTER) || []
  assert.deepEqual(
    radien, [],
    'src/ssot/seiten.css darf keinen festen Radius setzen: ' + radien.join(', '),
  )

  // Es muss die Tokens BENUTZEN — sonst wäre es nur zufällig farbfrei.
  assert.ok(seiten.includes('var(--bg)'), 'Grund-Stylesheet nutzt --bg nicht')
  assert.ok(seiten.includes('var(--surface)'), 'Grund-Stylesheet nutzt --surface nicht')
  assert.ok(seiten.includes('var(--text)'), 'Grund-Stylesheet nutzt --text nicht')
  // Kein eigener Dunkelmodus: den liefert tokens.css. Geprueft wird der
  // REGELTEXT ohne Kommentare — der Hinweis im Kopf der Datei nennt das
  // Stichwort absichtlich und ist kein zweiter Dunkelmodus.
  const ohneKommentare = seiten.replace(/\/\*[\s\S]*?\*\//g, '')
  assert.ok(
    !ohneKommentare.includes('prefers-color-scheme'),
    'Grund-Stylesheet baut einen zweiten Dunkelmodus — den liefert tokens.css',
  )
}

// ── 2 · tokens.css bleibt die einzige Rohwert-Quelle ───────────────────────
{
  const tokens = lies('diakonos/tokens.css')
  assert.ok(tokens.includes('--dk-navy-500'), 'tokens.css ohne Marken-Skala')
  assert.ok(tokens.includes('--font'), 'tokens.css ohne Schrift-Token')
  // ON-0a: die Handy-Schriftgröße der Eingabefelder ist jetzt EIN Token.
  assert.ok(
    tokens.includes('--fs-in-zeiger'),
    'tokens.css ohne --fs-in-zeiger (Eingabefelder im groben Zeiger)',
  )
}

// ── 3 · Der Build schreibt beide Dateien unter festen Namen ────────────────
{
  const vite = readFileSync(new URL('vite.config.mjs', WURZEL), 'utf8')
  assert.ok(
    vite.includes('diakronos-tokens.css'),
    'vite.config.mjs baut diakronos-tokens.css nicht',
  )
  assert.ok(
    vite.includes('diakronos-seiten.css'),
    'vite.config.mjs baut diakronos-seiten.css nicht',
  )
  assert.ok(
    vite.includes('src/ssot/seiten.css'),
    'vite.config.mjs kennt das Grund-Stylesheet src/ssot/seiten.css nicht',
  )
  assert.ok(
    /plugins\s*:\s*\[[^\]]*ssotStylesheets\(\)/.test(vite),
    'vite.config.mjs registriert den ssotStylesheets-Plugin nicht',
  )
}

// ── 4 · Das Backend bindet Tokens + Grundregeln über EINEN Helfer ein ──────
{
  const rahmen = new URL('../backend/src/diakronos_app/anmeldung/seitenrahmen.py', WURZEL)
  assert.ok(existsSync(rahmen), 'backend/src/diakronos_app/anmeldung/seitenrahmen.py fehlt')
  const text = readFileSync(rahmen, 'utf8')
  assert.ok(text.includes('diakronos-tokens.css'), 'seitenrahmen.py nennt die Token-Datei nicht')
  assert.ok(text.includes('diakronos-seiten.css'), 'seitenrahmen.py nennt das Grund-Stylesheet nicht')
  assert.ok(text.includes('base_path.pfad('), 'seitenrahmen.py baut die Adressen nicht präfixbewusst')
}

// ── 5 · Keine feste Schriftfamilie in den neuen Vue-Bereichen ──────────────
function vueDateien(verzeichnis) {
  const pfad = new URL(verzeichnis, SRC)
  if (!existsSync(pfad)) return []
  const treffer = []
  for (const name of readdirSync(pfad)) {
    const kind = new URL(name, pfad)
    if (statSync(kind).isDirectory()) treffer.push(...vueDateien(`${verzeichnis}${name}/`))
    else if (name.endsWith('.vue')) treffer.push(`${verzeichnis}${name}`)
  }
  return treffer
}

{
  const bereiche = ['diakonos/pages/planrahmen/', 'diakonos/components/planrahmen/', 'diakonos/components/ui/']
  const verstoesse = []
  let geprueft = 0
  for (const datei of bereiche.flatMap(vueDateien)) {
    geprueft += 1
    const text = lies(datei)
    for (const treffer of findeFesteSchriften(text)) {
      verstoesse.push(`${datei}: ${treffer.trim()}`)
    }
  }
  assert.ok(geprueft > 0, 'Es wurden Vue-Dateien zum Prüfen gefunden')
  assert.deepEqual(
    verstoesse, [],
    'Feste Schriftfamilie verboten — die Schrift kommt aus --font (tokens.css):\n' +
      verstoesse.join('\n'),
  )
}
