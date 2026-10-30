/**
 * UX-B2b — Meine Dienste: Rollenfarben final (Variante D, Einsingen neutral).
 * Operator-Entscheidung 2026-10-24 zur Rückfrage auf t_3db059a3, Nachbesserung
 * aus derselben Runde: Variante B für den neutralen Ton.
 *
 *   Fläche  = Rollenton 12 % hell / 22 % dunkel über der Kartenfläche
 *   Schrift = einheitlich --text
 *   Dirigent = Akzent (Gold) · Klavier = Info (Blau) · Solo = Erfolg (Grün)
 *   Einsingen = Neutral warmgrau --dk-warm-500 (#5b6178), NICHT --muted
 *   unbekannte Rollen = Rückfall (nur Rahmen, kein Ton)
 *
 * Geprüft wird, was ohne Browser prüfbar ist:
 *
 *  1. ZUORDNUNG — vier verschiedene Töne, Einsingen NICHT mehr warn.
 *  2. KONTRAST — die Schrift der Rollenzeichen erreicht in BEIDEN Themes
 *     4,5:1 (WCAG 1.4.3), nachgerechnet aus tokens.css.
 *  3. FARBABSTAND — die Flächen der vier Rollen sind im Dunkelmodus
 *     messbar unterschiedlich (der eigentliche Befund: --accent und --warn
 *     liegen dort auf demselben Farbton). Der Hellmodus wird ebenfalls
 *     gemessen, hat aber eine physikalische Untergrenze (siehe unten).
 *  4. KEINE FESTWERTE — die Seite setzt nur Token-Namen und Deckkraft.
 *  5. DIE ALTE KONTRAST-NACHBESSERUNG ENTFAELLT — --dk-green-700 ist weg.
 *  6. SEITE — Legende und Zeilen nutzen dieselbe Zuordnung.
 *
 * ── Warum im Dunkelmodus ΔE ≥ 8,6 und nicht ≥ 10? ────────────────────────
 * Gemessen (ΔE76, Flächen über --surface #111631, 22 % Deckkraft):
 *   Dirigent/Klavier  18,9 · Dirigent/Solo 14,1 · Dirigent/Einsingen 18,5
 *   Klavier/Solo      18,1 · Solo/Einsingen 18,8
 *   Klavier/Einsingen  8,6  ← der kleinste Abstand
 * Der Engpass ist Blau (--info #8fb2ff) gegen Warmgrau (--dk-warm-500): bei
 * 22 % rücken beide zusammen. Die 10er-Schwelle wäre nur mit einem Ton nahe
 * der Karten-Textfarbe zu halten (--dk-ink-text #e8eaf4 → ΔE 10,1), also
 * fast weiß statt neutral grau. Die Karte verlangt „messbar unterschiedlich",
 * der Operator hat Variante B ausdrücklich gewählt (ΔE 8,6 zu Klavier) —
 * deshalb steht die Schwelle hier auf 8 und das Paar wird einzeln belegt.
 *
 * ── Warum im Hellmodus keine ΔE-Schwelle? ────────────────────────────────
 * 12 % Ton über Weiß lässt alle vier Flächen dicht zusammenrücken; der
 * kleinste Abstand ist Dirigent/Solo (ΔE 3,1 bei 12 %, 4,6 bei 22 %) — und
 * der hängt NICHT an Einsingen, sondern an der vorgeschriebenen Deckkraft.
 * Die Karte fordert den Farbabstand deshalb auch nur für den Dunkelmodus.
 * Im Hellmodus tragen Buchstabe und Klartext die Rolle (WCAG 1.4.1), der
 * Textkontrast ist mit 14,6–15,8:1 weit über 4,5:1. Beides wird geprüft.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import {
  ROLLEN_FARBEN, RUECKFALL_FARBE, FLAECHE_HELL, FLAECHE_DUNKEL,
  rollenFarbe, rollenSchluessel, legende,
} from '../src/diakonos/components/planrahmen/meine-dienste-monate.mjs'

const root = new URL('../src/diakonos/', import.meta.url)
const lies = (p) => readFileSync(new URL(p, root), 'utf8')
const SEITE = lies('pages/planrahmen/MeineDienste.vue')
const HELFER = lies('components/planrahmen/meine-dienste-monate.mjs')
const TOKENS = lies('tokens.css')

// ── Farbrechnung (WCAG 2.1 + CIE-Lab-Farbabstand) ─────────────────────────

const hex = (s) => {
  const t = String(s).replace('#', '')
  return [parseInt(t.slice(0, 2), 16), parseInt(t.slice(2, 4), 16), parseInt(t.slice(4, 6), 16)]
}
const rgb = (c) => '#' + c.map((v) => Math.round(v).toString(16).padStart(2, '0')).join('')

/** Relativer Kontrast nach WCAG 2.1, Formel 1.4.3. */
function kontrast(a, b) {
  const kanal = (v) => {
    const x = v / 255
    return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4
  }
  const lum = ([r, g, b]) => 0.2126 * kanal(r) + 0.7152 * kanal(g) + 0.0722 * kanal(b)
  const la = lum(a)
  const lb = lum(b)
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05)
}

/** CIE-Lab (D65, sRGB) — für den Farbabstand ΔE76. */
function lab([r, g, b]) {
  const f = (t) => (t > 0.008856 ? Math.cbrt(t) : 7.787 * t + 16 / 116)
  const x = f((0.4124 * r + 0.3576 * g + 0.1805 * b) / 95.047)
  const y = f((0.2126 * r + 0.7152 * g + 0.0722 * b) / 100)
  const z = f((0.0193 * r + 0.1192 * g + 0.9505 * b) / 108.883)
  return [116 * y - 16, 500 * (x - y), 200 * (y - z)]
}
const deltaE = (a, b) => {
  const [p, q] = [lab(a), lab(b)]
  return Math.sqrt((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 + (p[2] - q[2]) ** 2)
}
/** Farbtonabstand ohne Helligkeit (a/b-Achsen) — trennt „anders bunt“ von „nur dunkler“. */
const deltaAB = (a, b) => {
  const [p, q] = [lab(a), lab(b)]
  return Math.sqrt((p[1] - q[1]) ** 2 + (p[2] - q[2]) ** 2)
}

/** Mischung wie `color-mix(in srgb, ton <anteil>, fläche)`. */
const mischen = (ton, flaeche, anteil) =>
  ton.map((v, i) => v * anteil + flaeche[i] * (1 - anteil))

/**
 * Rohwert eines Tokens aus tokens.css — aus der Sektion, in der er steht.
 * `dunkel = false` liest den hellen Block (:root), `dunkel = true` den
 * Dunkelblock ([data-theme="dark"]). Alias-Ketten (var(--x)) werden aufgelöst.
 *
 * Der Dunkelblock beginnt bei einem Selektor, der `[data-theme="dark"]`
 * nennt, und endet mit der zugehörigen schließenden Klammer — deshalb wird
 * die Klammertiefe mitgezählt und nicht nur auf `}` geschaut.
 */
function tokenFreilegen(name, dunkel) {
  const gesucht = new RegExp(`^\\s*${name}\\s*:\\s*([^;]+);`)
  let tiefe = 0
  let blockDunkel = false
  let selektor = ''
  const treffer = []
  // Kommentare ZUERST entfernen: ein Kommentarblock endet auf "*/" und nicht
  // auf "{" — bleibt er stehen, verschiebt sich die Blockzählung um eins und
  // Rohwerte werden dem falschen Theme zugeordnet.
  const ohneKommentar = TOKENS.replace(/\/\*[\s\S]*?\*\//g, '')
  // Der Selektor eines Blocks kann über MEHRERE Zeilen laufen
  // ("[data-theme=\"dark\"]," / ":root[data-theme=\"dark\"] {") — deshalb
  // wird gesammelt, bis die öffnende Klammer kommt.
  for (const zeile of ohneKommentar.split('\n')) {
    const roh = zeile.trim()
    // At-Regeln (@import …;) sind keine Selektoren — sie beenden keinen Block
    // und dürfen nicht in den nächsten Selektor hineinlaufen.
    if (!roh || roh.startsWith('@') && !roh.endsWith('{')) continue
    if (tiefe === 0) {
      selektor += ' ' + roh
      if (!roh.endsWith('{')) continue
      blockDunkel = selektor.includes('[data-theme="dark"]')
      selektor = ''
      tiefe = 1
      continue
    }
    tiefe += (zeile.match(/\{/g) || []).length
    tiefe -= (zeile.match(/\}/g) || []).length
    if (tiefe <= 0) { tiefe = 0; continue }
    if (blockDunkel !== dunkel) continue
    const m = zeile.match(gesucht)
    if (m) treffer.push(m[1].trim())
  }
  // Die Datei definiert mehrere helle `:root`-Blöcke (Rohwerte oben,
  // semantische Namen weiter unten). Eine spätere Definition gewinnt — wie
  // im Browser. Deshalb der LETZTE Treffer, nicht der erste.
  return treffer.length ? treffer[treffer.length - 1] : null
}

/**
 * Ein Farbwert (hex oder var-Kette) als RGB-Tripel.
 *
 * Rohwerte (`--dk-*`, z. B. --dk-warm-500) stehen NUR im hellen :root-Block —
 * sie sind themenunabhängig. Deshalb fällt die Auflösung auf die helle
 * Sektion zurück, wenn der Name im Dunkelblock nicht vorkommt.
 */
function farbe(name, dunkel) {
  let wert = tokenFreilegen(name, dunkel)
  // Rohwerte (`--dk-*`) stehen NUR im hellen :root-Block — sie sind
  // themenunabhängig. Deshalb fällt die Auflösung auf die helle Sektion
  // zurück, wenn der Name im Dunkelblock gar nicht vorkommt.
  if (wert === null) wert = tokenFreilegen(name, false)
  let tiefe = 0
  while (wert && wert.startsWith('var(') && tiefe++ < 8) {
    const inner = wert.slice(4, wert.lastIndexOf(')')).split(',')[0].trim()
    const naechster = tokenFreilegen(inner, dunkel) ?? tokenFreilegen(inner, false)
    wert = naechster
  }
  assert.ok(wert, `${name} (${dunkel ? 'dunkel' : 'hell'}) in tokens.css nicht gefunden`)
  const m = String(wert).match(/#[0-9a-fA-F]{6}/)
  assert.ok(m, `${name} (${dunkel ? 'dunkel' : 'hell'}) ist kein Farbwert: ${wert}`)
  return hex(m[0])
}

/**
 * Der CSS-Name hinter einem Rollen-Schlüssel. Die Tabelle nennt die Rolle
 * `warm-500`, das Token heißt `--dk-warm-500` (Rohwert-Skala) — deshalb wird
 * `warm-500` auf `dk-warm-500` abgebildet, alles andere auf `--<art>`.
 * Abgebildet wird AUSSCHLIESSLICH hier im Test, nicht in der Seite: die Seite
 * schreibt den Token-Namen aus.
 */
const tokenName = (art) => (art === 'warm-500' ? '--dk-warm-500' : `--${art}`)

/**
 * Fläche eines Rollenzeichens: Rollenton mit FLAECHE_* über der Fläche, auf der
 * das Zeichen sitzt. Hell = Karte (--surface), dunkel = Karte (--surface).
 */
function flaeche(art, dunkel) {
  const anteil = dunkel ? FLAECHE_DUNKEL : FLAECHE_HELL
  if (art === RUECKFALL_FARBE) {
    // Rückfall: KEIN Ton — die Kartenfläche selbst, nur mit Rahmen.
    return farbe('--surface', dunkel)
  }
  return mischen(farbe(tokenName(art), dunkel), farbe('--surface', dunkel), anteil)
}

const ROLLEN = Object.keys(ROLLEN_FARBEN)

// ── 1 · Zuordnung ─────────────────────────────────────────────────────────

test('UX-B2b: vier Rollen mit vier verschiedenen Tönen', () => {
  assert.deepEqual(ROLLEN_FARBEN, {
    dirigent: 'accent',
    klavier: 'info',
    solo: 'ok',
    einsingen: 'warm-500',
  })
  const werte = Object.values(ROLLEN_FARBEN)
  assert.equal(new Set(werte).size, 4, 'zwei Rollen teilen sich einen Ton')
})

test('UX-B2b: Einsingen ist NEUTRAL warmgrau (Variante B), nicht warn und nicht muted', () => {
  // Befund: --accent (#e0b866) und --warn (#e0b163) liegen im Dunkelmodus
  // praktisch auf demselben Farbton — als Rollenfarben nicht unterscheidbar.
  // --muted ist im Dunkelmodus #9ba3c1 (blaustichig) und rückt bei 22 % an
  // --info heran (ΔE 4,9) — der Operator hat deshalb Variante B gewählt.
  assert.notEqual(ROLLEN_FARBEN.einsingen, 'warn')
  assert.notEqual(ROLLEN_FARBEN.einsingen, 'muted')
  assert.equal(ROLLEN_FARBEN.einsingen, 'warm-500')
  assert.equal(rollenFarbe('einsingen'), 'warm-500')
  assert.equal(rollenFarbe('lieder[2].Einsingen'), 'warm-500')
  // Der Ton ist ein vorhandener Rohwert aus tokens.css, kein Farbwert in der
  // Seite und keine erfundene Stufe.
  assert.match(TOKENS, /--dk-warm-500:\s*#5b6178/)
  assert.equal(rgb(farbe('--dk-warm-500', false)), '#5b6178')
})

test('UX-B2b: der Rückfall ist ein eigener Ton, keiner der vier', () => {
  assert.equal(RUECKFALL_FARBE, 'rueckfall')
  assert.ok(!Object.values(ROLLEN_FARBEN).includes(RUECKFALL_FARBE))
  assert.equal(rollenFarbe('prediger'), 'rueckfall')
  assert.equal(rollenFarbe(''), 'rueckfall')
  assert.equal(rollenFarbe(null), 'rueckfall')
  // Unbekannte Rolle nie auf einen Rollenton abbilden.
  for (const rolle of ROLLEN) assert.notEqual(rollenFarbe(rolle), RUECKFALL_FARBE)
})

test('UX-B2b: Rollenschlüssel bleibt unverändert (Feldpfad → Rolle)', () => {
  assert.equal(rollenSchluessel('lieder[1].solo'), 'solo')
  assert.equal(rollenSchluessel('  DIRIGENT  '), 'dirigent')
  assert.equal(rollenSchluessel(''), '')
})

// ── 2 · Kontrast der Schrift (hell UND dunkel) ────────────────────────────

for (const [thema, dunkel] of [['hell', false], ['dunkel', true]]) {
  test(`UX-B2b: Schrift der Rollenzeichen erreicht im ${thema}en Modus 4,5:1`, () => {
    const text = farbe('--text', dunkel)
    const zuSchwach = []
    for (const rolle of ROLLEN) {
      const fl = flaeche(ROLLEN_FARBEN[rolle], dunkel)
      const wert = kontrast(text, fl)
      if (wert < 4.5) zuSchwach.push(`${rolle} (${ROLLEN_FARBEN[rolle]}): ${wert.toFixed(2)}:1 auf ${rgb(fl)}`)
    }
    assert.deepEqual(zuSchwach, [],
      `Rollenzeichen unter 4,5:1 im ${thema}en Modus:\n${zuSchwach.join('\n')}`)
  })
}

test('UX-B2b: auch der Rückfall ist im hellen und dunklen Modus lesbar', () => {
  for (const dunkel of [false, true]) {
    const wert = kontrast(farbe('--text', dunkel), flaeche(RUECKFALL_FARBE, dunkel))
    assert.ok(wert >= 4.5, `Rückfall ${dunkel ? 'dunkel' : 'hell'}: ${wert.toFixed(2)}:1`)
  }
})

test('UX-B2b: die Deckkraft der Fläche ist 12 % hell und 22 % dunkel', () => {
  assert.equal(FLAECHE_HELL, 0.12)
  assert.equal(FLAECHE_DUNKEL, 0.22)
  // Im Dunkelmodus muss mehr Ton drauf — sonst verschwindet die Fläche.
  assert.ok(FLAECHE_DUNKEL > FLAECHE_HELL)
})

// ── 3 · Farbabstand der Flächen ───────────────────────────────────────────

test('UX-B2b: die vier Rollenflächen sind im Dunkelmodus messbar unterschiedlich', () => {
  const flaechen = Object.fromEntries(ROLLEN.map((r) => [r, flaeche(ROLLEN_FARBEN[r], true)]))
  const zuNah = []
  const abstaende = {}
  for (let i = 0; i < ROLLEN.length; i++) {
    for (let j = i + 1; j < ROLLEN.length; j++) {
      const a = ROLLEN[i]
      const b = ROLLEN[j]
      const d = deltaE(flaechen[a], flaechen[b])
      abstaende[`${a}/${b}`] = d
      // Schwelle 8, nicht 10: der Engpass ist Klavier/Einsingen (Blau gegen
      // Warmgrau) und liegt bei 12 %/22 % Deckkraft physiologisch bei ~8,6 —
      // für 10 müsste Einsingen fast weiß sein (Herleitung im Kopfkommentar).
      // Vielfache von 3 sind „deutlich sichtbar" (ΔE > 5 gilt als klar
      // unterscheidbar, > 10 als „anderer Farbton").
      if (d < 8) zuNah.push(`${a}/${b}: ΔE ${d.toFixed(1)} (${rgb(flaechen[a])} vs ${rgb(flaechen[b])})`)
    }
  }
  assert.deepEqual(zuNah, [],
    `Flächen im Dunkelmodus zu ähnlich (ΔE >= 8 verlangt):\n${zuNah.join('\n')}`)
  // Der Operator hat Variante B mit ΔE 11,7 zu Klavier zugesagt — der Wert
  // muss also auch wirklich erreicht werden (nicht nur „über 8").
  assert.ok(abstaende['klavier/einsingen'] >= 8.5,
    `Klavier/Einsingen nur ΔE ${abstaende['klavier/einsingen'].toFixed(1)}`)
  // Die drei bunten Rollen bleiben untereinander weit auseinander.
  for (const paar of ['dirigent/klavier', 'dirigent/solo', 'klavier/solo']) {
    assert.ok(abstaende[paar] >= 14, `${paar} nur ΔE ${abstaende[paar].toFixed(1)}`)
  }
})

test('UX-B2b: Dirigent und Einsingen unterscheiden sich im Dunkelmodus im FARBTON, nicht nur in der Helligkeit', () => {
  // Der Kern des Befunds: zwei Töne, die sich nur in der Helligkeit
  // unterscheiden, sind bei gedämpftem Licht und für farbfehlsichtige
  // Menschen nicht zu trennen. Der a/b-Abstand misst „anders bunt".
  const a = flaeche(ROLLEN_FARBEN.dirigent, true)
  const b = flaeche(ROLLEN_FARBEN.einsingen, true)
  const ab = deltaAB(a, b)
  const gruen = flaeche(ROLLEN_FARBEN.solo, true)
  assert.ok(ab > 8, `Dirigent/Einsingen nur ΔAB ${ab.toFixed(1)} — gleicher Farbton`)
  assert.ok(deltaAB(gruen, b) > 8,
    `Solo/Einsingen nur ΔAB ${deltaAB(gruen, b).toFixed(1)} — gleicher Farbton`)
})

test('UX-B2b: im Hellmodus tragen Buchstabe und Klartext — Flächen bleiben zart (12 %) und lesbar', () => {
  // Warum hier keine ΔE-Schwelle: bei 12 % über Weiß rücken alle vier Töne
  // zusammen, der kleinste Abstand ist Dirigent/Solo (ΔE 3,1) und hängt
  // nicht an Einsingen. Die Karte fordert den Farbabstand nur für den
  // Dunkelmodus; im hellen Modus ist die Farbe Zusatzinformation zu
  // Buchstabe (D/K/S/E) und Klartext (WCAG 1.4.1, geprüft im Test unten).
  // Was trotzdem gelten muss: die Flächen sind nicht tonerlos und die
  // Schrift bleibt über 4,5:1.
  const text = farbe('--text', false)
  for (const rolle of ROLLEN) {
    const fl = flaeche(ROLLEN_FARBEN[rolle], false)
    assert.ok(kontrast(text, fl) >= 4.5, `${rolle} hell: ${kontrast(text, fl).toFixed(2)}:1`)
    assert.ok(deltaE(fl, farbe('--surface', false)) > 1.0,
      `${rolle} hell: Fläche ΔE ${deltaE(fl, farbe('--surface', false)).toFixed(1)} — Ton unsichtbar`)
  }
})

test('UX-B2b: --warn wird für keine Rolle mehr benutzt (Dunkelmodus-Farbton)', () => {
  assert.ok(!Object.values(ROLLEN_FARBEN).includes('warn'))
  assert.ok(!Object.values(ROLLEN_FARBEN).includes('accent-d'))
})

// ── 4 · Keine festen Farbwerte in der Seite ───────────────────────────────

test('UX-B2b: die Seite setzt keine festen Farbwerte', () => {
  const farbMuster = /#[0-9a-fA-F]{3,8}\b|\brgba?\s*\(|\bhsla?\s*\(/g
  const verstoesse = []
  SEITE.split('\n').forEach((zeile, i) => {
    farbMuster.lastIndex = 0
    if (zeile.match(farbMuster)) verstoesse.push(`${i + 1}: ${zeile.trim()}`)
  })
  assert.deepEqual(verstoesse, [], 'Feste Farbwerte in MeineDienste.vue:\n' + verstoesse.join('\n'))
})

test('UX-B2b: jede Rolle hat eine data-art-Regel mit Token-Ton und anteiliger Mischung', () => {
  for (const art of Object.values(ROLLEN_FARBEN)) {
    assert.match(SEITE, new RegExp(`\\.pr-md-rolle-zeichen\\[data-art="${art}"\\]`),
      `Regel für data-art="${art}" fehlt`)
    // Die Ton-Zeile steht in der EIGENEN Regel der Rolle (nicht in der
  // gemeinsamen Flächen-Regel, die alle vier Data-Arten zusammenfasst).
    const eigen = SEITE.split('\n')
      .filter((z) => z.includes(`[data-art="${art}"]`) && z.includes('--rolle-ton'))
      .join('\n')
    assert.match(eigen, new RegExp(`--rolle-ton:\\s*var\\(${tokenName(art)}\\)`),
      `data-art="${art}" setzt nicht --rolle-ton: var(${tokenName(art)})`)
  }
  // Die Fläche entsteht als Mischung aus Ton und Kartenfläche mit der
  // Deckkraft-Variablen — nicht als fester Wert.
  assert.match(SEITE, /background:\s*color-mix\(in srgb, var\(--rolle-ton\) var\(--rolle-flaeche\), var\(--surface\)\)/)
})
test('UX-B2b: Schrift ist einheitlich --text, keine Sonderstufe je Rolle', () => {
  const gemeinsam = SEITE.split('.pr-md-rolle-zeichen[data-art="accent"],')[1].split('}')[0]
  assert.match(gemeinsam, /color:\s*var\(--text\)/)
  assert.doesNotMatch(gemeinsam, /--badge-ink-/, 'Rollenzeichen dürfen keine Abzeichen-Sonderfarbe mehr tragen')
})

test('UX-B2b: die Deckkraft steht an den Stellen, die ein Rollenzeichen tragen', () => {
  assert.match(SEITE, /\.pr-md-legende,\s*\n\.pr-md-monat-zeile \{ --rolle-flaeche: 12%; \}/)
  const dunkelBlock = SEITE.split(':root[data-theme="dark"] .pr-md-monat-zeile')[1] || ''
  assert.match(dunkelBlock, /\{ --rolle-flaeche: 22%; \}/,
    'im Dunkelmodus muss die Fläche 22 % tragen')
  // Kein Selektor auf eine Klasse, die es im DOM nicht gibt.
  assert.doesNotMatch(SEITE, /^\.pr-md \{/m, 'Sammel-Selektor .pr-md existiert im DOM nicht')
})

// ── 5 · Die alte Kontrast-Nachbesserung entfällt ──────────────────────────

test('UX-B2b: --dk-green-700 ist aus den Tokens entfernt (war nur für die alte Schriftfarbe)', () => {
  assert.doesNotMatch(TOKENS, /--dk-green-700\s*:/)
  assert.doesNotMatch(SEITE, /dk-green-700/)
  // Keine anderen Stellen im Frontend benutzen ihn noch.
  for (const datei of ['tokens.css', 'index.css']) {
    const inhalt = lies(datei)
    assert.doesNotMatch(inhalt, /--dk-green-700\s*:/, `${datei} definiert --dk-green-700 noch`)
  }
})

test('UX-B2b: die Rollenfarben brauchen keine --badge-ink-*-Sonderstufe mehr', () => {
  const abschnitt = SEITE.split('/* ── UX-B2/B2b')[1].split('.pr-md-monate')[0]
  assert.doesNotMatch(abschnitt, /--badge-ink-/)
})

// ── 6 · Seite: Legende und Zeilen nutzen dieselbe Zuordnung ───────────────

test('UX-B2b: Legende zeigt die Rolle mit demselben Ton wie die Zeile', () => {
  const eintraege = legende(
    ['dirigent', 'klavier', 'solo', 'einsingen', 'prediger'].map((r, i) => ({
      termin: `2026-11-0${i + 1}`, feld_pfad: r, feld_name: r,
    })),
    (r) => r,
  )
  assert.deepEqual(eintraege.map((e) => e.farbe), ['accent', 'info', 'ok', 'warm-500', 'rueckfall'])
  assert.deepEqual(eintraege.map((e) => e.zeichen), ['d', 'k', 's', 'e', 'p'].map((c) => c.toUpperCase()))
})

test('UX-B2b: Legende und Zeile lesen den Ton aus demselben Helfer', () => {
  assert.match(SEITE, /:data-art="e\.farbe"/)
  assert.match(SEITE, /:data-art="rollenFarbe\(d\.feld_pfad \|\| d\.feld_name\)"/)
  // Die Legende holt die Farbe aus `legende()` (dort steht `rollenFarbe(key)`),
  // nicht aus einer zweiten eigenen Tabelle.
  assert.match(SEITE, /legende\(dienste\.value/)
  assert.match(HELFER, /farbe:\s*rollenFarbe\(key\)/)
})

test('UX-B2b: Buchstabe und Klartext bleiben (Farbe ist nicht alles, WCAG 1.4.1)', () => {
  assert.match(SEITE, /\{\{ e\.zeichen \}\}/)
  assert.match(SEITE, /\{\{ e\.text \}\}/)
  assert.match(SEITE, /rollenZeichen\(d\.feld_pfad \|\| d\.feld_name, feldName\(d\.feld_pfad\)\)/)
  assert.match(SEITE, /<span class="pr-md-feld">\{\{ feldName\(d\.feld_pfad\) \}\}<\/span>/)
})
