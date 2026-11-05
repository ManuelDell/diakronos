/**
 * UX-B2 — Meine Dienste: Monatskarten mit Rollenfarbe
 * (Manuel 2026-10-23, Befund DMB-964a27d87752, Entwurf B2).
 *
 * Geprüft wird, was ohne Browser prüfbar ist:
 *
 *  1. MONATSGRUPPIERUNG — je Monat eine Karte, aufsteigend, Zeilen nach Datum.
 *  2. ROLLENFARBE MIT RÜCKFALL — bekannte Rollen bekommen ihren Token,
 *     unbekannte die Rückfallfarbe (nie `undefined`, nie ein geratener Ton).
 *  3. Dirigent und Einsingen sind unterscheidbar (Hinweis aus dem Entwurf:
 *     nicht beide im Gold/Bernstein).
 *  4. Nur vorhandene Tokens: jede Farbe ist einer der vier Namen
 *     accent/info/ok/warn bzw. der Rückfall — die Seite setzt sie als
 *     `data-art` um und liest die Werte aus tokens.css.
 *  5. Die Legende zeigt nur vorkommende Rollen, in fester Reihenfolge.
 *  6. Die Seite selbst: Rendern der Karten, Erhalt von Absagen/Abwesenheit.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import {
  ROLLEN_FARBEN, RUECKFALL_FARBE,
  monatsGruppen, monatsTitel, rollenFarbe, rollenSchluessel, rollenZeichen,
  istBekannteRolle, legende, diensteText,
} from '../src/diakonos/components/planrahmen/meine-dienste-monate.mjs'

const root = new URL('../src/diakonos/', import.meta.url)
const lies = (p) => readFileSync(new URL(p, root), 'utf8')
const SEITE = lies('pages/planrahmen/MeineDienste.vue')
const TOKENS = lies('tokens.css')

/** Ein Diensteintrag, wie ihn `meine_dienste` liefert. */
function dienst(termin, feld, extra = {}) {
  const feldName = String(feld).split(/[.:/]/).filter(Boolean).pop().split('[')[0]
  return { termin, feld_pfad: feld, feld_name: feldName, titel: 'Chorplan November', ...extra }
}

// ── 1 · Monatsgruppierung ─────────────────────────────────────────────────

test('UX-B2: je Monat eine Karte, aufsteigend nach Monat', () => {
  const dienste = [
    dienst('2027-01-10', 'einsingen'),
    dienst('2026-11-22', 'lieder[1].klavier'),
    dienst('2026-12-06', 'lieder[0].dirigent'),
    dienst('2026-11-08', 'lieder[2].solo'),
  ]
  const gruppen = monatsGruppen(dienste)
  assert.deepEqual(gruppen.map((g) => g.schluessel), ['2026-11', '2026-12', '2027-01'])
  assert.deepEqual(gruppen.map((g) => g.titel), ['November 2026', 'Dezember 2026', 'Januar 2027'])
  assert.deepEqual(gruppen.map((g) => g.dienste.length), [2, 1, 1])
})

test('UX-B2: die Zeilen einer Karte stehen nach Datum', () => {
  const gruppen = monatsGruppen([
    dienst('2026-11-22', 'lieder[1].klavier'),
    dienst('2026-11-08', 'lieder[2].solo'),
    dienst('2026-11-15', 'lieder[0].dirigent'),
  ])
  assert.deepEqual(gruppen[0].dienste.map((d) => d.termin),
    ['2026-11-08', '2026-11-15', '2026-11-22'])
})

test('UX-B2: leere und unbrauchbare Termine fallen raus, die übrigen bleiben einsortiert', () => {
  const gruppen = monatsGruppen([
    dienst('2026-11-08', 'solo'),
    { feld_pfad: 'solo' },                       // kein termin
    { termin: '', feld_pfad: 'solo' },
    { termin: 'irgendwann', feld_pfad: 'solo' },
    dienst('2026-12-06', 'dirigent'),
  ])
  assert.deepEqual(gruppen.map((g) => g.schluessel), ['2026-11', '2026-12'])
  assert.equal(gruppen[0].dienste.length, 1)
})

test('UX-B2: kein Dienst → keine Karte', () => {
  assert.deepEqual(monatsGruppen([]), [])
  assert.deepEqual(monatsGruppen(undefined), [])
})

test('UX-B2: Monatstitel rechnet nicht über Zeitzonen (kein Tag-Versatz)', () => {
  // Ein `new Date('2026-11-01')` wäre in UTC-1 noch Oktober — hier steht der
  // Monat direkt aus dem ISO-Text.
  assert.equal(monatsTitel('2026-11-01'), 'November 2026')
  assert.equal(monatsTitel('2026-12-31'), 'Dezember 2026')
  assert.equal(monatsTitel('2027-03-01'), 'März 2027')
  assert.equal(monatsTitel(''), '')
  assert.equal(monatsTitel('2027-13-01'), '')
})

test('UX-B2: die Gruppierung verändert die Eingabe nicht', () => {
  const dienste = [dienst('2026-11-22', 'klavier'), dienst('2026-11-08', 'solo')]
  const kopie = JSON.stringify(dienste)
  monatsGruppen(dienste)
  assert.equal(JSON.stringify(dienste), kopie)
})

// ── 2 · Rollenfarbe mit Rückfall ──────────────────────────────────────────

test('UX-B2: bekannte Rollen bekommen ihren Token', () => {
  assert.equal(rollenFarbe('dirigent'), 'accent')
  assert.equal(rollenFarbe('klavier'), 'info')
  assert.equal(rollenFarbe('solo'), 'ok')
  // UX-B2b: Einsingen ist neutral (Grau) — --accent und --warn liegen im
  // Dunkelmodus auf demselben Farbton und wären als Rollen nicht trennbar.
  // UX-B2b: Einsingen trägt den warmgrauen Ton `--dk-warm-500` („warm-500“).
  assert.equal(rollenFarbe('einsingen'), 'warm-500')
})

test('UX-B2: die Rolle wird aus dem Feldpfad erkannt (lieder[1].solo → solo)', () => {
  assert.equal(rollenSchluessel('lieder[1].solo'), 'solo')
  assert.equal(rollenSchluessel('ablauf/abc-123.moderator'), 'moderator')
  assert.equal(rollenSchluessel('einsingen'), 'einsingen')
  assert.equal(rollenSchluessel('  DIRIGENT  '), 'dirigent')
  assert.equal(rollenSchluessel(''), '')
  assert.equal(rollenSchluessel(null), '')
  assert.equal(rollenFarbe('lieder[0].Klavier'), 'info')
})

test('UX-B2: unbekannte Rollen und leere Angaben bekommen die Rückfallfarbe', () => {
  assert.equal(rollenFarbe('prediger'), RUECKFALL_FARBE)
  assert.equal(rollenFarbe('technik-ton'), RUECKFALL_FARBE)
  assert.equal(rollenFarbe(''), RUECKFALL_FARBE)
  assert.equal(rollenFarbe(null), RUECKFALL_FARBE)
  assert.equal(rollenFarbe(undefined), RUECKFALL_FARBE)
  // Nie ein geratener Ton und nie `undefined`.
  assert.ok(rollenFarbe('völlig-neue-rolle'))
  assert.equal(typeof rollenFarbe('völlig-neue-rolle'), 'string')
})

test('UX-B2: `istBekannteRolle` trennt Tabelle und Rückfall', () => {
  assert.equal(istBekannteRolle('solo'), true)
  assert.equal(istBekannteRolle('lieder[2].einsingen'), true)
  assert.equal(istBekannteRolle('prediger'), false)
  assert.equal(istBekannteRolle(''), false)
})

// ── 3 · Dirigent und Einsingen unterscheidbar ─────────────────────────────

test('UX-B2: Dirigent und Einsingen liegen nicht im selben Farbtoken', () => {
  assert.notEqual(ROLLEN_FARBEN.dirigent, ROLLEN_FARBEN.einsingen)
  assert.notEqual(rollenFarbe('dirigent'), rollenFarbe('einsingen'))
})

test('UX-B2: alle vier Rollen haben vier verschiedene Tokens', () => {
  const werte = Object.values(ROLLEN_FARBEN)
  assert.equal(new Set(werte).size, werte.length)
  // UX-B2b: Einsingen trägt den neutralen Ton statt --warn.
  assert.deepEqual(werte.slice().sort(), ['accent', 'info', 'ok', 'warm-500'])
})

test('UX-B2: das Rollenzeichen trägt immer einen Buchstaben (Farbe ist nicht alles)', () => {
  assert.equal(rollenZeichen('dirigent', 'Dirigent'), 'D')
  assert.equal(rollenZeichen('lieder[1].solo', 'Solo'), 'S')
  assert.equal(rollenZeichen('einsingen', 'Einsingen'), 'E')
  assert.equal(rollenZeichen('prediger', 'Prediger'), 'P')
  // Ohne Text bleibt der Rollenname als Quelle; ohne alles ein Punkt.
  assert.equal(rollenZeichen('klavier', ''), 'K')
  assert.equal(rollenZeichen('', ''), '•')
})

// ── 4 · Nur vorhandene Tokens ─────────────────────────────────────────────

test('UX-B2: jede Rollenfarbe ist ein vorhandener Token-Name', () => {
  // UX-B2b: `warm-500` ist `--dk-warm-500` aus tokens.css (Rohwert).
  const erlaubt = new Set(['accent', 'info', 'ok', 'warm-500', RUECKFALL_FARBE])
  for (const [rolle, farbe] of Object.entries(ROLLEN_FARBEN)) {
    assert.ok(erlaubt.has(farbe), `${rolle} → ${farbe} ist kein vorhandener Token`)
  }
})

test('UX-B2: die Tokens, auf die die Seite zeigt, stehen in tokens.css (hell und dunkel)', () => {
  for (const name of ['--accent', '--accent-d', '--info', '--info-soft',
    '--ok', '--ok-soft', '--warn', '--warn-soft']) {
    const treffer = TOKENS.match(new RegExp(`${name}\\s*:`, 'g')) || []
    assert.ok(treffer.length >= 2,
      `${name} muss in beiden Themes definiert sein (gefunden: ${treffer.length})`)
  }
})

test('UX-B2: die Seite setzt keine festen Farbwerte (nur data-art + var(--…))', () => {
  const farbMuster = /#[0-9a-fA-F]{3,8}\b|\brgba?\s*\(|\bhsla?\s*\(/g
  const zeilen = SEITE.split('\n')
  const verstoesse = []
  zeilen.forEach((zeile, i) => {
    farbMuster.lastIndex = 0
    const m = zeile.match(farbMuster)
    if (m) verstoesse.push(`${i + 1}: ${zeile.trim()}`)
  })
  assert.deepEqual(verstoesse, [], 'Feste Farbwerte in MeineDienste.vue:\n' + verstoesse.join('\n'))
  // Und die Zuordnung steht als `data-art` — nicht als eingebauter Farbwert.
  for (const art of ['accent', 'info', 'ok', 'warm-500']) {
    assert.match(SEITE, new RegExp(`\\.pr-md-rolle-zeichen\\[data-art="${art}"\\]`),
      `Regel für data-art="${art}" fehlt`)
  }
})

test('UX-B2: für die Rückfallfarbe gibt es ein neutrales Zeichen ohne Statusfarbe', () => {
  // Das Rückfallzeichen nutzt Fläche/Hover + gedämpfte Schrift — kein
  // vierter/fünfter Status-Ton, der eine Rolle vortäuschen würde.
  const block = SEITE.split('.pr-md-rolle-zeichen {')[1] || ''
  const bisSchliessung = block.split('}')[0]
  // UX-B2b: der Rückfall ist eine Fläche OHNE Rollenton, nur mit Rahmen.
  assert.match(bisSchliessung, /background:\s*transparent/)
  assert.match(bisSchliessung, /--dk-border-strong/)
  assert.match(bisSchliessung, /color:\s*var\(--dk-text\)/)
  assert.doesNotMatch(bisSchliessung, /--(accent|info|ok|warn|muted)\b/)
})

// ── 5 · Legende ───────────────────────────────────────────────────────────

test('UX-B2: die Legende zeigt nur vorkommende Rollen, in fester Reihenfolge', () => {
  const eintraege = legende([
    dienst('2026-11-08', 'lieder[2].solo'),
    dienst('2026-11-15', 'lieder[0].dirigent'),
    dienst('2026-11-22', 'lieder[1].solo'),
  ], (r) => r.charAt(0).toUpperCase() + r.slice(1))
  assert.deepEqual(eintraege.map((e) => e.rolle), ['dirigent', 'solo'])
  assert.deepEqual(eintraege.map((e) => e.text), ['Dirigent', 'Solo'])
  assert.deepEqual(eintraege.map((e) => e.farbe), ['accent', 'ok'])
  assert.deepEqual(eintraege.map((e) => e.zeichen), ['D', 'S'])
})

test('UX-B2: unbekannte Rollen stehen in der Legende hinter den bekannten, mit Rückfallfarbe', () => {
  const eintraege = legende([
    dienst('2026-11-08', 'prediger'),
    dienst('2026-11-15', 'lieder[1].klavier'),
  ], (r) => r)
  assert.deepEqual(eintraege.map((e) => e.rolle), ['klavier', 'prediger'])
  assert.equal(eintraege[0].farbe, 'info')
  assert.equal(eintraege[1].farbe, RUECKFALL_FARBE)
})

test('UX-B2: ohne Dienste keine Legende (keine Farben ohne Vorkommen)', () => {
  assert.deepEqual(legende([], (r) => r), [])
})

test('UX-B2: Zahl der Dienste auf Deutsch', () => {
  assert.equal(diensteText(1), '1 Dienst')
  assert.equal(diensteText(2), '2 Dienste')
  assert.equal(diensteText(0), '0 Dienste')
})

// ── 6 · Die Seite selbst ──────────────────────────────────────────────────

test('UX-B2: die Seite rendert je Monat eine Karte mit Titel, Zahl und Zeilen', () => {
  assert.match(SEITE, /v-for="m in g\.monate"/)
  assert.match(SEITE, /class="dk-card pr-md-monat"/)
  assert.match(SEITE, /class="pr-md-monat-titel"/)
  assert.match(SEITE, /diensteText\(m\.dienste\.length\)/)
  assert.match(SEITE, /v-for="\(d, i\) in m\.dienste"/)
  // Die Monatskarten kommen aus dem reinen Helfer, nicht aus Inline-Logik.
  assert.match(SEITE, /monatsGruppen\(sortiert\)/)
})

test('UX-B2: jede Zeile trägt ein Rollenzeichen mit Farbe und Buchstaben', () => {
  assert.match(SEITE, /class="pr-md-rolle-zeichen"/)
  assert.match(SEITE, /:data-art="rollenFarbe\(d\.feld_pfad \|\| d\.feld_name\)"/)
  assert.match(SEITE, /rollenZeichen\(d\.feld_pfad \|\| d\.feld_name, feldName\(d\.feld_pfad\)\)/)
  // Für Vorlesehilfen ist die Rolle als Text hinterlegt.
  assert.match(SEITE, /:aria-label="feldName\(d\.feld_pfad\)"/)
})

test('UX-B2: die Legende steht über den Karten und nennt Rolle im Klartext', () => {
  const legendePos = SEITE.indexOf('pr-md-legende')
  const kartenPos = SEITE.indexOf('pr-md-monate')
  assert.ok(legendePos > 0 && kartenPos > legendePos, 'Legende muss vor den Karten stehen')
  assert.match(SEITE, /legendeEintraege/)
  assert.match(SEITE, /\{\{ e\.text \}\}/)
})

test('UX-B2: vorhandene Funktionen bleiben — Absagen, Plan öffnen, Abwesenheiten', () => {
  assert.match(SEITE, /@click="absageAnfragen\(d, g\)"/)
  assert.match(SEITE, /:disabled="absageLaeuft\[d\.feld_pfad\]"/)
  assert.match(SEITE, /class="pr-md-planlink"[^>]*:href="planLink\(g\)"/)
  assert.match(SEITE, /Abwesenheit melden/)
  assert.match(SEITE, /abwesenheitLoeschenAktion\(a\)/)
  assert.match(SEITE, /abwesenheitMeldenAktion/)
  assert.match(SEITE, /Einteilung absagen/)
  // Der Konflikthinweis bei Abwesenheit ist erhalten.
  assert.match(SEITE, /Du hast für diesen Tag eine Abwesenheit gemeldet/)
})

test('UX-B2: Mobil-Umschaltung verschiebt die Absage-Aktion, das Zeichen bleibt', () => {
  // FIX-6: Die Mobil-Umschaltung hängt NUR an der Breite (Layout-Kriterium
  // der App, Operator-Entscheidung 27.10.) — 720 px bleiben unverändert.
  const block = SEITE.split('@media (max-width: 720px) {')[1] || ''
  assert.match(block, /\.pr-md-monat-zeile \{[^}]*flex-wrap: wrap/)
  assert.match(block, /\.pr-md-monat-aktion \{[^}]*margin-left/)
})

// ── 7 · Kontrast der Rollenzeichen (WCAG AA, 4,5:1 für Text) ──────────────

/** Relativer Kontrast nach WCAG 2.1 (Formel 1.4.3). */
function kontrast(vorn, hinten) {
  const kanal = (c) => {
    const x = c / 255
    return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4
  }
  const lum = ([r, g, b]) => 0.2126 * kanal(r) + 0.7152 * kanal(g) + 0.0722 * kanal(b)
  const a = lum(vorn)
  const b = lum(hinten)
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)
}

const hex = (s) => {
  const t = s.replace('#', '')
  return [parseInt(t.slice(0, 2), 16), parseInt(t.slice(2, 4), 16), parseInt(t.slice(4, 6), 16)]
}
/** Farbe aus tokens.css (Rohwert) — schlägt fehl, wenn sie fehlt. */
function token(name) {
  const m = TOKENS.match(new RegExp(`${name}\\s*:\\s*(#[0-9a-fA-F]{6})`))
  assert.ok(m, `${name} fehlt in tokens.css`)
  return hex(m[1])
}

test('UX-B2b ersetzt die Schriftstufen-Nachbesserung: Kontrast prüft jetzt uxb2b-rollenfarben.test.mjs', () => {
  // UX-B2b (Variante D) setzt die Schrift einheitlich auf --text und die
  // Fläche auf Rollenton 12 %/22 %. Damit entfallen die alten Abzeichen-
  // Schriftstufen und --dk-green-700. Der Kontrast-Nachweis für hell UND
  // dunkel steht in tests/uxb2b-rollenfarben.test.mjs (dort gegen die
  // echten Token-Werte gerechnet).
  assert.doesNotMatch(SEITE, /--badge-ink-/)
  assert.doesNotMatch(TOKENS, /--dk-green-700/)
})
