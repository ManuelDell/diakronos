/**
 * UX3i5 — Kalender-LISTE: je Termin eine Zeile, Tageskopf mit Trenner und
 * voller Fläche.
 *
 * Karte t_16e4670d (live-Befunde Manuel, 08.11.). Nach UX3i4 standen zwei
 * Termine eines Tages NEBENEINANDER (inline-flex), und der Integrations-Fix
 * (`display: grid` + `:has(> …)`) machte die Termine unsichtbar. Dieser Test
 * hält die drei Befunde mit dem fest, was er wirklich ausführen kann:
 *
 *   1. LISTE: Der Tag (`.ec-day`) ist ein umbrechender Zeilen-Kasten; jeder
 *      Termin fordert eine ganze Zeile an, sein „⋯“-Halter steht mit fester
 *      Breite (`--control-h`) rechts daneben auf DERSELBEN Zeile. KEIN Grid
 *      (die Ursache des Rückziehers war `display: grid` am Tag).
 *   2. TAGESKOPF-TEXT: „Freitag, 6. November 2026“ — der Trenner hängt an
 *      genau EINER Stelle (CSS am ersten `time`), die Formate kommen
 *      ausdrücklich aus den Optionen der Bibliothek.
 *   3. TAGESKOPF-FLÄCHE: eine Zeile über die volle Breite (100 %), Fläche
 *      aus dem Token `--surface`, keine Linie, Abstände aus der Skala.
 *
 * Der Test liest NUR Dateien innerhalb von frontend/ (Regel 13) und braucht
 * kein Netz. Er prüft Quelltext-Regeln, nicht das gerenderte Bild — das Bild
 * ist der Beleg der Karte (Screenshots Desktop 1440 hell+dunkel, Mobil 390).
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const hier = dirname(fileURLToPath(import.meta.url))
const FRONTEND = resolve(hier, '..')
const SRC = join(FRONTEND, 'src', 'diakonos')
const lies = (rel) => readFileSync(join(SRC, rel), 'utf8')

/** Quelltext ohne Kommentare — geprüft wird Code, nicht Prosa. */
function ohneKommentare(text, { js = true } = {}) {
  const quelle = String(text)
  let rest = quelle
  let aus = ''
  for (;;) {
    const start = rest.indexOf('/*')
    if (start < 0) { aus += rest; break }
    aus += rest.slice(0, start)
    const ende = rest.indexOf('*/', start + 2)
    if (ende < 0) { aus += rest.slice(start); break }
    rest = rest.slice(ende + 2)
  }
  return js ? aus.replace(/\/\/.*$/gm, '') : aus
}
const ohneCssKommentare = (text) => ohneKommentare(text, { js: false })

/** Ein CSS-Block zu einem Selektor (erster Treffer). */
function block(css, selektor) {
  const code = ohneCssKommentare(css)
  const i = code.indexOf(selektor)
  assert.ok(i >= 0, `Regel fehlt: ${selektor}`)
  const start = code.indexOf('{', i + selektor.length - 1)
  assert.ok(start > 0, `keine öffnende Klammer nach: ${selektor}`)
  return code.slice(start + 1, code.indexOf('}', start))
}
/** Die letzte Regel mit diesem Selektor (Gewinner der Kaskade). */
function letzteRegel(css, text) {
  const code = ohneCssKommentare(css)
  const treffer = []
  for (const m of code.matchAll(/([^{}]+)\{([^}]*)\}/g)) {
    if (m[1].includes(text)) treffer.push(m[2])
  }
  assert.ok(treffer.length > 0, `Regel fehlt: ${text}`)
  return treffer[treffer.length - 1]
}

/** Alle CSS-Blöcke, die GENAU diesen Selektor (getrimmt) tragen — für Regeln
 *  mit `!important`, die absichtlich in mehreren Blöcken stehen. */
function bloecke(css, selektor) {
  const code = ohneCssKommentare(css)
  const treffer = []
  for (const m of code.matchAll(/([^{}]+)\{([^}]*)\}/g)) {
    if (m[1].trim() === selektor) treffer.push(m[2])
  }
  assert.ok(treffer.length > 0, `Regel fehlt: ${selektor}`)
  return treffer
}

const css = lies('kronos.css')
const bibel = lies('components/kronos/KronosCalendar.vue')

// ══════════════════════════════════════════════════════════════════════════
// 1 · Liste: je Termin eine Zeile, „⋯“ rechts auf derselben Zeile
// ══════════════════════════════════════════════════════════════════════════
test('UX3i5: der Listentag ist ein umbrechender Zeilen-Kasten (kein Grid)', () => {
  // Der Tag trägt ZWEI Regeln: die Bestandsregel (Höhe/Auslaufen) und die
  // neue Zeilen-Regel. Geprüft wird die NEUE (mit `flex-wrap`).
  const tags = bloecke(css, '.ec-list .ec-day')
  const tag = tags.find((r) => /flex-wrap/.test(r))
  assert.ok(tag, 'die Zeilen-Regel für den Listentag fehlt')
  assert.match(tag, /display:\s*flex/, 'der Tag stapelt Kopf und Termine in Zeilen')
  assert.match(tag, /flex-wrap:\s*wrap/, 'ohne Umbruch lägen die Termine nebeneinander (Befund 1)')
  assert.match(tag, /flex-direction:\s*row/, 'Zeilen, keine Spalten')
  // Grid war die Ursache des Rückziehers (Termine unsichtbar).
  assert.doesNotMatch(ohneCssKommentare(css), /\.ec-list \.ec-day[^{]*\{[^}]*display:\s*grid/,
    'kein Grid am Listentag — das machte die Termine unsichtbar (Rückzieher 08.11.)')
  assert.doesNotMatch(ohneCssKommentare(css), /:has\(>\s*\[data-aktionen-zeile\]\)/,
    'der zurückgenommene Grid-Fix darf nicht zurückkommen')
})

test('UX3i5: Kopf und jeder Termin beginnen eine eigene Zeile', () => {
  // Kopf: volle Zeile, aber OHNE die Platzreserve des „⋯“ (Nacharbeit Review
  // 09.11.: der Kopf stand mit in der max-inline-size-Regel und ließ rechts
  // einen grauen Streifen stehen).
  const kopfZeile = block(css, '.ec-list .ec-day > .ec-day-head {')
  assert.match(kopfZeile, /flex:\s*0 0 100%/, 'der Kopf beginnt eine eigene, ganze Zeile')
  assert.doesNotMatch(kopfZeile, /max-inline-size/,
    'der Kopf trägt keine Platzreserve für das „⋯“ — er reicht durchgehend über die Breite')
  // Termin: volle Zeile mit Platz für sein „⋯“.
  const zeile = block(css, '.ec-list .ec-day > article.ec-event {')
  assert.match(zeile, /flex:\s*0 0 100%/, 'volle Zeile je Termin (sonst wieder nebeneinander)')
  assert.match(zeile, /max-inline-size:\s*calc\(100% - var\(--control-h\)\)/,
    'rechts bleibt genau der Platz des „⋯“ — es schiebt den Termin nicht um')
})

test('UX3i5: das „⋯“ steht rechts in der Zeile SEINES Termins', () => {
  const halter = block(css, '.ec-list .ec-day > .kronos-liste-aktionen-halter')
  assert.match(halter, /flex:\s*0 0 var\(--control-h\)/,
    'feste Breite in der Klickfläche des Konzepts (40 px, bei pointer: coarse 44 px)')
  assert.match(halter, /justify-content:\s*flex-end/, 'der Knopf sitzt am rechten Rand, nicht am Termin klebend')
  assert.match(halter, /margin-block-start:\s*calc\(-1 \* var\(--control-h\)\)/,
    'eine Zeile zurück: der Halter gehört auf die Zeile des Termins davor')
  assert.match(halter, /margin-inline-start:\s*auto/, 'rechtsbündig in der Zeile')
})

test('UX3i5: der Chip bleibt sichtbar (Breite und Höhe, Text nicht gekappt)', () => {
  const chip = block(css, '.ec-list .ec-chip {')
  assert.match(chip, /inline-size:\s*fit-content/, 'der Chip ist so breit wie sein Text')
  assert.match(chip, /min-height:\s*var\(--control-h\)/, 'Klickfläche bleibt das Konzeptmaß')
  assert.match(chip, /display:\s*flex/, 'Text steht in einer Zeile mit fester Höhe')
  // Der Chip trägt seinen Text selbst (kein `font-size: 0`, kein `text-indent`).
  assert.doesNotMatch(chip, /font-size:\s*0(px|;)/, 'der Termintext darf nicht unsichtbar gemacht werden')
  assert.doesNotMatch(chip, /color:\s*transparent/, 'der Termintext bleibt lesbar')
})

test('UX3i5: die Kennzeichnung der Listenzeile setzt das Skript, nicht das CSS', () => {
  const code = ohneKommentare(bibel)
  assert.match(code, /function zeilenHerrichten\(/, 'die Kennzeichnung fehlt')
  assert.match(code, /\.ec-list article\.ec-event/, 'nur Listenzeilen werden gekennzeichnet (Monat bleibt Punkt)')
  assert.match(code, /data-aktionen-zeile/, 'die Kennzeichnung heißt `data-aktionen-zeile`')
})

// ══════════════════════════════════════════════════════════════════════════
// 2 · Tageskopf: Trenner zwischen Wochentag und Datum
// ══════════════════════════════════════════════════════════════════════════
test('UX3i5: der Tageskopf setzt einen Trenner zwischen Wochentag und Datum', () => {
  const trenner = block(css, '.ec-list .ec-day-head > time:first-child::after')
  assert.match(trenner, /content:\s*","/, '„Freitag, 6. November 2026“ — das Komma fehlte (Befund 2)')
  assert.match(trenner, /\/\s*""/, 'der Trenner wird von der Vorlesehilfe übersprungen (reine Gestaltung)')
  assert.match(trenner, /margin-inline-end:/, 'der Abstand nach dem Komma kommt aus der Skala')
  // Nur EINE Stelle setzt den Trenner (kein zweiter Weg über ein zweites Zeichen).
  assert.equal((ohneCssKommentare(css).match(/content:\s*","/g) || []).length, 1,
    'der Trenner steht an genau einer Stelle')
})

test('UX3i5: die Kopf-Formate stehen ausdrücklich in den Optionen', () => {
  const code = ohneKommentare(bibel)
  assert.match(code, /listDayFormat:\s*\{\s*weekday:\s*'long'\s*\}/,
    'Wochentag lang („Freitag“) — nicht die Vorgabe der Bibliothek')
  assert.match(code, /listDaySideFormat:\s*\{\s*day:\s*'numeric',\s*month:\s*'long',\s*year:\s*'numeric'\s*\}/,
    'Datum als „6. November 2026“ — Tag, Monat, Jahr aus einer Hand')
})

// ══════════════════════════════════════════════════════════════════════════
// 3 · Tageskopf-Fläche: eine Zeile über die volle Breite
// ══════════════════════════════════════════════════════════════════════════
test('UX3i5: der Tageskopf trägt EINE Fläche über die volle Breite', () => {
  // Die Kopfregeln stehen in ZWEI Blöcken (Grundfläche + Zeilenaufbau); der
  // Gewinner der Kaskade ist der ZUSAMMENGEFASSTE Stand beider.
  const kopf = bloecke(css, '.ec-list .ec-day-head').join('\n')
  assert.match(kopf, /background-color:\s*var\(--surface\)/,
    'Kartenfläche als Token — kein fester Farbwert (Befund 3: weißer Kasten, Rest grau)')
  assert.match(kopf, /inline-size:\s*100%/, 'die Fläche reicht über die ganze Zeile')
  assert.match(kopf, /max-inline-size:\s*100%/, 'kein Überlauf über die Karte hinaus')
  assert.match(kopf, /box-sizing:\s*border-box/, 'Innenabstand zählt in die Breite')
  assert.match(kopf, /display:\s*flex/, 'Wochentag und Datum stehen in einer Zeile')
  assert.match(kopf, /justify-content:\s*flex-start/,
    'Wochentag und Datum stehen ZUSAMMEN links („Freitag, 6. November 2026“)')
  assert.doesNotMatch(kopf, /justify-content:\s*space-between/,
    'kein Auseinanderziehen über die ganze Breite (Nacharbeit Review 09.11.)')
  // Eine Linie wäre ein sichtbarer Rahmen: `border: 0` (oder `none`) hebt ihn
  // auf. Geprüft wird JEDE `border`-Deklaration der Kopfregeln.
  const raender = [...ohneCssKommentare(kopf).matchAll(/border[^:;]*:\s*([^;]+);/g)].map((m) => m[1].trim())
  for (const wert of raender) {
    assert.match(wert, /^(0|none)$/, `keine Linie: der Abstand trennt (Ä2) — gefunden: ${wert}`)
  }
  assert.doesNotMatch(ohneCssKommentare(kopf), /#[0-9a-fA-F]{3,8}/, 'keine festen Farbwerte (Dark Mode über Variablen)')
})

test('UX3i5: Kopf-Abstände und Schrift kommen aus den Tokens', () => {
  const kopf = bloecke(css, '.ec-list .ec-day-head').join('\n')
  assert.match(kopf, /gap:\s*var\(--sp-/, 'Abstand aus der Skala')
  assert.match(kopf, /padding:\s*var\(--sp-\d+\) var\(--sp-\d+\) var\(--sp-\d+\)/,
    'Innenabstand nur aus --sp-1..--sp-8')
  assert.doesNotMatch(ohneCssKommentare(kopf), /\b\d+px/, 'keine festen Pixelwerte im Kopf (Wächter: Abstands-Bestand)')
  // Die Schrift-Regel gilt für BEIDE Zeiten; ``.ec-day-side` nimmt nur Gewicht
  // und Farbe zurück (eine Schriftstufe, Prinzip Ä3).
  const zeit = bloecke(css, '.ec-list .ec-day-head > time').join('\n')
  assert.match(zeit, /font-size:\s*var\(--fs(-|\))/, 'Schriftstufe aus den Tokens')
  assert.match(zeit, /font-weight:\s*var\(--fw-/, 'Gewicht aus den Tokens')
  assert.doesNotMatch(ohneCssKommentare(zeit), /\b\d+px/, 'keine festen Schriftgrößen')
  // Hierarchie (Nacharbeit Review 09.11.): der Tageskopf steht NICHT über dem
  // Kartenkopf. Der Kartenkopf trägt 14 px (--fs), also höchstens diese Stufe.
  assert.doesNotMatch(ohneCssKommentare(zeit), /font-size:\s*var\(--fs-(16|20|26)\)/,
    'der Tageskopf bleibt auf oder unter der Schriftstufe des Kartenkopfs')
})
