/**
 * DEV-4 · Wächter: keine harten Farbwerte und keine Farb-Token, die im
 * Dunkelmodus auf WEISS zeigen (Befund DMB-abb58354487b, „Dunkelmodus
 * fehlerhaft — bitte nicht nur auf der Seite checken“).
 *
 * Geprüft werden die in dieser Karte geänderten Quelltexte (echte Dateien,
 * keine Kopien):
 *
 *   1. tokens.css liefert für BEIDE Themes `--link` / `--link-hover`.
 *   2. `.dk-ui-chip.is-active` / `.dk-filter-chip.is-active` stehen im
 *      Dunkelmodus auf einer hellen Fläche — die Schrift darf NICHT aus einem
 *      Token kommen, das im Dunkelmodus hell wird (`--dk-brand-*`,
 *      `--dk-text*`, `--primary`). Vorher: var(--dk-brand-800) → navy-100 →
 *      1,37:1 (unlesbar).
 *   3. `.dk-ui-btn--primary` / `.dk-ui-btn--danger` und `.btn-primary` setzen
 *      im Dunkelmodus eine FESTE dunkle Markenstufe als Schrift (--dk-navy-*).
 *   4. `.dk-ui-eingabe` hat eine Grundform aus Tokens (Innenabstand, Radius
 *      aus `--radius`) — das Feld stand ohne Radius neben runden Auswahlfeldern.
 *   5. Mitglieder › Datenschutz benutzt keine der nicht existierenden
 *      Feldklassen `.dk-input`/`.dk-select` (die waren die weißen
 *      Browser-Vorgaben mit heller Schrift darauf).
 *   6. Die Seiten dieser Karte enthalten KEINE festen Farbwerte in
 *      Farbdeklarationen (Muster aus DEV-3).
 *
 * Läuft im Docker-Build über den Globb `tests/dev4-*.test.mjs`.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const WURZEL = new URL('../src/diakonos/', import.meta.url)
const read = (p) => readFileSync(new URL(p, WURZEL), 'utf8')

/** Zerlegt ein Stylesheet in Regeln { selektor, rumpf }. */
function regeln(text) {
  const ohneKommentare = text.replace(/\/\*[\s\S]*?\*\//g, '')
  const ergebnis = []
  const stapel = []
  let puffer = ''
  for (const zeichen of ohneKommentare) {
    if (zeichen === '{') {
      stapel.push(puffer.trim())
      puffer = ''
    } else if (zeichen === '}') {
      const selektor = stapel.pop() || ''
      if (!selektor.startsWith('@') && selektor) ergebnis.push({ selektor, rumpf: puffer })
      puffer = ''
    } else {
      puffer += zeichen
    }
  }
  return ergebnis
}

/** Regeln, deren Selektor ALLE genannten Bruchstücke enthält. */
function regelnMit(text, ...teile) {
  return regeln(text).filter((r) => teile.every((t) => r.selektor.includes(t)))
}

/** Alle Selektoren einer (ggf. mit Komma geteilten) Regel. */
const selektoren = (selektor) => selektor.split(',').map((s) => s.trim())

/** Feste Farbe: #rgb/#rrggbb, rgb()/rgba(), hsl()/hsla(), white/black.
 *  Ausnahme: `color-mix(…, black)` mischt Schwarz in eine Token-Farbe — das
 *  ist keine feste Farbe, sondern eine Ableitung (Aufhellung/Abdunklung). */
const FESTE_FARBE = /#[0-9a-fA-F]{3,8}\b|\brgba?\s*\(|\bhsla?\s*\(|\b(white|black)\b/
const festeFarbeIn = (wert) =>
  /#[0-9a-fA-F]{3,8}\b|\brgba?\s*\(|\bhsla?\s*\(|\b(white|black)\b/.test(
    // color-mix kann verschachtelt sein (`color-mix(…, var(--x, black))`) —
    // deshalb alle Vorkommen entfernen, nicht nur das erste.
    wert.replace(/color-mix\(/g, '‹').replace(/[^‹]*\)/g, ''),
  )
const FARB_DEKLARATION = /(^|[;{\s])(color|background|background-color|border-color|fill|stroke)\s*:\s*([^;{}]+)/g

/** Farbwerte einer Regel (ohne var(--…) selbst, nur die Deklarationen). */
function farbDeklarationen(rumpf) {
  const treffer = []
  FARB_DEKLARATION.lastIndex = 0
  let m
  while ((m = FARB_DEKLARATION.exec(rumpf)) !== null) treffer.push(m[2] + ': ' + m[3].trim())
  return treffer
}

// ── 1 · Verweis-Token in beiden Themes ─────────────────────────────────────
test('DEV-4 · tokens.css definiert --link und --link-hover in hell UND dunkel', () => {
  const css = read('tokens.css')
  const regelnAlle = regeln(css)
  const linkHell = regelnAlle.filter((r) => r.selektor === ':root' && /--link\s*:/.test(r.rumpf))
  const linkDunkel = regelnAlle.filter(
    (r) => r.selektor.includes('[data-theme="dark"]') && /--link\s*:/.test(r.rumpf),
  )
  assert.ok(linkHell.length, 'tokens.css: --link im hellen Theme')
  assert.ok(linkDunkel.length, 'tokens.css: --link im dunklen Theme — sonst bleibt der Verweis weiß')
  for (const r of regelnAlle.filter((x) => /--link(-hover)?\s*:/.test(x.rumpf))) {
    assert.doesNotMatch(
      r.rumpf.match(/--link[^;]*/g).join(' '),
      FESTE_FARBE,
      `tokens.css · ${r.selektor}: Verweisfarbe nur über Tokens (--dk-…)`,
    )
  }
})

// ── 2 · Filterchips im Dunkelmodus ─────────────────────────────────────────
test('DEV-4 · aktiver Filterchip: helle Fläche, Schrift nicht aus einem hellen Token', () => {
  const css = read('index.css')
  // Nur die REGEL selbst prüfen (nicht die Regeln für die Zahl im Chip), und
  // je Selektor der kommagetrennten Regel einen eigenen Durchlauf.
  const dunkleChips = []
  for (const r of regelnMit(css, '[data-theme="dark"]', 'is-active')) {
    for (const s of selektoren(r.selektor)) {
      if (/^\[data-theme="dark"\] \.dk-(ui-|filter-)?chip\.is-active$/.test(s)) {
        dunkleChips.push({ selektor: s, rumpf: r.rumpf })
      }
    }
  }
  assert.equal(dunkleChips.length, 2, 'index.css: Dunkelmodus-Regel für .dk-ui-chip und .dk-filter-chip')
  for (const r of dunkleChips) {
    assert.match(r.rumpf, /background:\s*#fff/, `${r.selektor}: helle Fläche bleibt`)
    const farbregel = r.rumpf.match(/(^|;)\s*color:\s*([^;]+)/)
    assert.ok(farbregel, `${r.selektor}: Schriftfarbe muss gesetzt sein`)
    const wert = farbregel[2].trim()
    // Ein Token, das im Dunkelmodus hell wird, ergibt hell auf hell.
    const verboten = ['--dk-brand', '--dk-text', '--text', '--primary', '--muted', '--subtle', '--dk-surface']
    for (const v of verboten) {
      assert.ok(!wert.includes(v), `${r.selektor}: ${wert} wird im Dunkelmodus hell → unlesbar`)
    }
    assert.match(wert, /^var\(--dk-navy-\d+\)$/, `${r.selektor}: feste dunkle Markenstufe erwartet, war ${wert}`)
  }
})

// ── 3 · Primär-/Gefahrenknöpfe ─────────────────────────────────────────────
/**
 * DEV-4b (Review): Fall 3 prüfte eine eigene Dunkelmodus-Regel, die
 * `color: var(--dk-navy-900)` setzte — `--primary-ink` zeigt im Dunkelmodus
 * aber schon auf `--dk-navy-900`, die Regel war wirkungslos und ist entfernt.
 * Geprüft wird jetzt, was die Lesbarkeit wirklich trägt: `--primary-ink` ist
 * in BEIDEN Themes dunkel (hell: #fff-Fläche, dunkel: helle Fläche), und keine
 * Regel setzt für die Knöpfe eine Schrift, die im Dunkelmodus dunkel wird.
 */
test('DEV-4 · --primary-ink trägt in beiden Themes auf der Knopffläche', () => {
  const tokens = read('tokens.css')
  const regelnTokens = regeln(tokens)
  const wurzel = regelnTokens.find((r) => r.selektor === ':root' && /--primary-ink\s*:/.test(r.rumpf))
  assert.ok(wurzel, 'tokens.css: --primary-ink im hellen Theme')
  assert.match(wurzel.rumpf, /--primary-ink:\s*#ffffff/,
    'heller Theme: weiße Schrift auf der dunklen Markenfläche')

  const dunkel = regelnTokens.filter(
    (r) => r.selektor.includes('[data-theme="dark"]') && /--primary-ink\s*:/.test(r.rumpf),
  )
  assert.ok(dunkel.length, 'tokens.css: --primary-ink im dunklen Theme')
  assert.match(dunkel[dunkel.length - 1].rumpf, /--primary-ink:\s*var\(--dk-navy-900\)/,
    'dunkler Theme: ebenso dunkel — eine Extraregel mit demselben Wert ist wirkungslos')

  // Die Knöpfe selbst bleiben bei --primary-ink (kein Doppel).
  const knopf = read('components/ui/DkButton.vue')
  const hell = regeln(knopf).find((x) => x.selektor === '.dk-ui-btn--primary')
  assert.ok(hell && /color:\s*var\(--primary-ink\)/.test(hell.rumpf), 'heller Zustand unverändert')
  const doppelt = regeln(knopf).filter((r) => r.selektor.includes('[data-theme="dark"]'))
  assert.deepEqual(doppelt.map((r) => r.selektor), [],
    'DkButton.vue: keine Dunkelmodus-Regel, die --primary-ink nur wiederholt')

  const kronos = read('kronos.css')
  // Die Knopfklassen der Dialoge stehen zweimal in kronos.css; die spätere
  // (weiter unten, „Shared button classes used in these modals“) gewinnt —
  // deren heller Zustand nimmt --primary-ink.
  const alt = regeln(kronos).filter((r) => r.selektor === '.btn-primary')
  assert.ok(alt.length >= 2, 'kronos.css: .btn-primary (Basis + Dialog-Fassung)')
  assert.match(alt[alt.length - 1].rumpf, /color:\s*var\(--primary-ink\)/,
    'kronos.css: letzte .btn-primary-Fassung nimmt --primary-ink')
  const altDunkel = regeln(kronos).filter((r) => r.selektor.includes('[data-theme="dark"] .btn-primary'))
  assert.deepEqual(altDunkel.map((r) => r.selektor), [],
    'kronos.css: keine wirkungslose Dunkelmodus-Regel für .btn-primary')
})

// ── 4 · Eingabefeld-Grundform ──────────────────────────────────────────────
test('DEV-4 · .dk-ui-eingabe hat einen Radius aus dem Token --radius', () => {
  const css = read('index.css')
  const basis = regeln(css).filter((r) => r.selektor === '.dk-ui-eingabe')
  assert.ok(basis.length, 'index.css: Regel .dk-ui-eingabe')
  const radius = basis.map((r) => (r.rumpf.match(/border-radius:\s*([^;]+)/) || [])[1]).filter(Boolean)
  assert.ok(radius.length, '.dk-ui-eingabe: border-radius fehlt (Radius 0 neben runden Auswahlfeldern)')
  for (const w of radius) {
    assert.equal(w.trim(), 'var(--radius)', '.dk-ui-eingabe: Radius aus dem Token, nicht 8px hart')
  }
  // UX1a: Innenabstand aus der Skala (--sp-2 = 8 px, --sp-3 = 12 px).
  assert.ok(
    basis.some((r) => /padding:\s*(?:var\(--sp-2\) var\(--sp-3\)|8px 12px)/.test(r.rumpf)),
    '.dk-ui-eingabe: Innenabstand wie .dk-form-input',
  )
})

// ── 5 · Mitglieder › Datenschutz ───────────────────────────────────────────
test('DEV-4 · Datenschutz benutzt keine nicht existierende Feldklasse', () => {
  const seite = read('pages/mitglieder/Datenschutz.vue')
  const unbekannt = seite.match(/class="[^"]*\bdk-(input|select)\b[^"]*"/g) || []
  assert.deepEqual(unbekannt, [], 'Klassen .dk-input/.dk-select gibt es im Stylesheet nicht → weiße Browser-Felder')
  // UX3j (A3): Der Stand ist kein natives <select> mehr, sondern derselbe
  // Umschalter wie in den übrigen Reitern (DkSegment, Stil aus dem System);
  // das Suchfeld ist das gemeinsame der Liste (.dk-toolbar-search).
  assert.match(seite, /<DkSegment/, 'Auswahl „Stand“ ist der Baustein des Systems (DkSegment)')
  assert.doesNotMatch(seite, /<select\b/, 'kein natives Auswahlfeld mehr (weiße Browser-Optik)')
  assert.match(seite, /class="dk-toolbar-search"/, 'Suchfeld ist das gemeinsame Feld der Liste')
})

// ── 6 · keine harten Farben in den Seiten dieser Karte ─────────────────────
const SEITEN = [
  'pages/mitglieder/Datenschutz.vue',
  'pages/Profile.vue',
  'components/ui/DkButton.vue',
  'components/ui/DkTabs.vue',
]
test('DEV-4 · geänderte Seiten tragen keine festen Farbwerte in Farbdeklarationen', () => {
  const fehler = []
  for (const datei of SEITEN) {
    const text = read(datei)
    for (const r of regeln(text)) {
      for (const deklaration of farbDeklarationen(r.rumpf)) {
        if (festeFarbeIn(deklaration)) fehler.push(`${datei} · ${r.selektor} → ${deklaration}`)
      }
    }
  }
  assert.deepEqual(fehler, [], 'Nur Token-Farben in den Seiten:\n' + fehler.join('\n'))
})

// ── 7 · kein toter --link-Verbraucher (Review-Runde 1) ─────────────────────
/**
 * Review-Befund: `a.dk-verweis { color: var(--link) }` stand in index.css,
 * die Klasse wurde aber NIRGENDS benutzt — eine Regel, die nichts färbt und
 * beim nächsten Umbau in die Irre führt. Der echte Verweis läuft über
 * `.prof-link` in Profile.vue.
 *
 * Geprüft wird die Regel, nicht ihr Fehlen an einer Stelle: jeder Selektor,
 * der `var(--link)` setzt, muss im Quelltext auch tatsächlich vorkommen.
 */
test('DEV-4 · jede --link-Regel hat eine benutzte Klasse (keine tote Verweis-Regel)', () => {
  const css = read('index.css')
  const profil = read('pages/Profile.vue')
  // Das Markup der Seite (ohne <style>-Block): nur dort entsteht eine Klasse.
  const markup = profil.replace(/<style[\s\S]*?<\/style>/g, '')

  const tote = []
  for (const r of regeln(css)) {
    if (!/var\(--link(?:-hover)?\)/.test(r.rumpf)) continue
    for (const s of selektoren(r.selektor)) {
      const klassen = s.match(/\.[A-Za-z][\w-]*/g) || []
      if (!klassen.length) continue
      const benutzt = klassen.every((k) => {
        const name = k.slice(1)
        // Die Klasse muss im Markup einer .vue-Datei vorkommen — ein Selektor
        // in einem Stylesheet ist kein Benutzer, sondern nur eine zweite Regel.
        return new RegExp(`class="[^"]*\\b${name}\\b`).test(markup) ||
          new RegExp(`'${name}'`).test(markup) ||
          new RegExp(`["']${name}["']`).test(markup)
      })
      if (!benutzt) tote.push(`${s} → ${r.rumpf.trim().slice(0, 40)}`)
    }
  }
  assert.deepEqual(tote, [],
    'Regeln mit var(--link) ohne benutzte Klasse (tote Verweis-Regel):\n' + tote.join('\n'))
  assert.match(profil, /\.prof-link\s*\{[^}]*var\(--link\)/,
    'Profile.vue: der echte Verweis (.prof-link) färbt über --link')
})
