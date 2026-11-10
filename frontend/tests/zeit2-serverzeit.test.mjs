/**
 * ZEIT-2 — Server-Zeitstempel werden als UTC gelesen und in Europe/Berlin
 * angezeigt; Termin-Wandzeiten bleiben unveraendert.
 *
 * Befund (Opus-Review DEV-B4b, 09.11.): Das Backend speichert technische
 * Zeitstempel (`creation`, `modified`, `zeitstempel`, Veroeffentlichungsstand)
 * als UTC OHNE Zeitzonenangabe („2026-11-09 16:09:12.123456"). Das Frontend
 * las sie mit `new Date(x.replace(' ', 'T'))` — ein String ohne Offset gilt in
 * JavaScript als ORTSZEIT, angezeigt wurde also 17:09 statt 16:09 (Sommer
 * 2 h, Winter 1 h daneben).
 *
 * Dieser Test laeuft unter TZ=Europe/Berlin (siehe `frontend/tests/zeit-setup`
 * bzw. den Aufruf: `TZ=Europe/Berlin node --test …`). Geprueft wird:
 *   1. Sommerzeit (UTC+2) und Winterzeit (UTC+1) — beide Richtungen;
 *   2. die Anzeige haengt NICHT an der Zeitzone des Rechners (Intl mit
 *      `timeZone`), sondern an der Zone der Gemeinde;
 *   3. Termin-Wandzeiten (`wandZeit`) verschieben sich NICHT;
 *   4. Feld-Semantik der umgestellten Dateien: `creation`/`modified`/
 *      `zeitstempel` laufen ueber `serverZeit*`, `element_start`/`datum_von`
 *      ueber `wandZeit`, und es gibt KEIN `replace(' ', 'T')` mehr auf einem
 *      Zeitstempel (Waechter, verhaltensbasiert).
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'

import {
  GEMEINDE_ZONE,
  serverDatum,
  serverUhrzeitText,
  serverZeit,
  serverZeitText,
  wandZeit,
} from '../src/shared/zeit.mjs'

const HIER = fileURLToPath(new URL('.', import.meta.url))
const SRC = join(HIER, '..', 'src')

// ── 0. Testvoraussetzung ────────────────────────────────────────────────────
// Der Fall „naive Eingabe gilt als Ortszeit" laesst sich nur in einer Zone mit
// Versatz pruefen. Node erbt TZ aus der Umgebung; der Test bricht sonst laut ab,
// damit er nie stillschweigend nichts prueft.
const tz = process.env.TZ || Intl.DateTimeFormat().resolvedOptions().timeZone
test('Testvoraussetzung: laeuft in der Zone Europe/Berlin', () => {
  assert.equal(tz, 'Europe/Berlin',
    'Dieser Test muss mit TZ=Europe/Berlin laufen (siehe backend/Dockerfile)')
})

// ── 1. Sommerzeit: 09.11. ist Winter, 15.07. Sommer ────────────────────────
test('Sommerzeit: 15.07.2026 14:00 UTC wird als 16:00 angezeigt (UTC+2)', () => {
  const d = serverZeit('2026-07-15 14:00:00')
  assert.ok(d)
  assert.equal(d.toISOString(), '2026-07-15T14:00:00.000Z', 'als UTC gelesen')
  assert.equal(serverUhrzeitText('2026-07-15 14:00:00'), '16:00')
  assert.equal(serverZeitText('2026-07-15 14:00:00'), '15.07.2026, 16:00')
})

test('Winterzeit: 09.11.2026 16:09 UTC wird als 17:09 angezeigt (UTC+1)', () => {
  assert.equal(serverZeitText('2026-11-09 16:09:12.123456'), '09.11.2026, 17:09')
  assert.equal(serverUhrzeitText('2026-11-09 16:09:12.123456'), '17:09')
})

test('Der Befund selbst: NICHT 17:09 als Rohwert (das war der Fehler)', () => {
  // Alte Lesart: `new Date('2026-11-09T16:09:12')` = 16:09 Ortszeit.
  // Neue Lesart: 16:09 UTC = 17:09 Ortszeit. Der Test haelt beide Zahlen fest,
  // damit ein Rueckfall auf `new Date(...)` auffaellt.
  const alt = new Date('2026-11-09 16:09:12'.replace(' ', 'T'))
  assert.equal(alt.toISOString(), '2026-11-09T15:09:12.000Z', 'so las es das Frontend bisher')
  assert.equal(serverZeit('2026-11-09 16:09:12').toISOString(), '2026-11-09T16:09:12.000Z')
})

test('Datumsgrenze: 09.11.2026 23:30 UTC ist in Berlin schon der 10.11.', () => {
  assert.equal(serverZeitText('2026-11-09 23:30:00'), '10.11.2026, 00:30')
  // 09.11.2026 12:00 UTC bleibt derselbe Tag.
  assert.equal(serverZeitText('2026-11-09 12:00:00'), '09.11.2026, 13:00')
})

test('ISO-Form mit T statt Leerzeichen wird genauso gelesen', () => {
  assert.equal(serverUhrzeitText('2026-11-09T16:09:12'), '17:09')
  assert.equal(serverUhrzeitText('2026-11-09T16:09'), '17:09')
})

// ── 2. Anzeige haengt nicht am Rechner des Betrachters ─────────────────────
test('Anzeige nutzt die Zone der Gemeinde, nicht die des Browsers', () => {
  // Der Test laeuft in Europe/Berlin; die Funktion setzt die Zone trotzdem
  // ausdruecklich. Gegenprobe: derselbe Zeitpunkt, explizit in UTC formatiert.
  assert.equal(GEMEINDE_ZONE, 'Europe/Berlin')
  const dt = serverZeit('2026-07-15 14:00:00')
  const utc = new Intl.DateTimeFormat('de-DE', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit', timeZone: 'UTC',
  }).format(dt)
  assert.equal(utc, '15.07.2026, 14:00')
  assert.equal(serverZeitText('2026-07-15 14:00:00'), '15.07.2026, 16:00')
})

// ── 3. Eindeutige Angaben bleiben unangetastet ─────────────────────────────
test('Werte mit Z oder Offset behalten ihre Zone', () => {
  assert.equal(serverZeitText('2026-11-09T16:09:12Z'), '09.11.2026, 17:09')
  assert.equal(serverZeitText('2026-11-09T16:09:12+02:00'), '09.11.2026, 15:09')
  assert.equal(serverZeitText('2026-11-09T16:09:12.123Z'), '09.11.2026, 17:09')
})

test('Unix-Millisekunden werden als Zeitpunkt gelesen', () => {
  const ms = Date.UTC(2026, 6, 15, 14, 0, 0)
  assert.equal(serverZeitText(ms), '15.07.2026, 16:00')
})

test('Leere und unbrauchbare Werte liefern null/„" statt „Invalid Date"', () => {
  for (const leer of [null, undefined, '', '   ', 'keine Zeit', '2026-13-01 10:00:00', '2026-02-30']) {
    assert.equal(serverZeit(leer), null, String(leer))
  }
  assert.equal(serverZeitText(''), '')
  assert.equal(serverZeitText('keine Zeit'), '')
  assert.equal(serverUhrzeitText(null), '')
})

// ── 4. Termin-Wandzeiten verschieben sich NICHT ────────────────────────────
test('Wandzeit: 15.07.2026 19:00 bleibt 19:00 (kein UTC-Versatz)', () => {
  const d = wandZeit('2026-07-15 19:00:00')
  assert.ok(d)
  assert.equal(d.getHours(), 19, 'Ortszeit 19 Uhr — unverschoben')
  assert.equal(d.getMinutes(), 0)
})

test('Wandzeit: Wintertermin 09.11.2026 19:00 bleibt 19:00', () => {
  const d = wandZeit('2026-11-09 19:00:00')
  assert.equal(d.getHours(), 19)
  // Gegenprobe: derselbe Text als SERVER-Zeitstempel gelesen waere 20:00.
  assert.equal(serverZeit('2026-11-09 19:00:00').getUTCHours(), 19)
  assert.equal(serverUhrzeitText('2026-11-09 19:00:00'), '20:00')
})

test('Wandzeit: Ganztags-Termin 00:00 bleibt 00:00 (kein Tageswechsel)', () => {
  const d = wandZeit('2026-11-08 00:00:00')
  assert.equal(d.getDate(), 8)
  assert.equal(d.getHours(), 0)
})

test('Wandzeit: leer/unbrauchbar -> null', () => {
  assert.equal(wandZeit(''), null)
  assert.equal(wandZeit(null), null)
  assert.equal(wandZeit('keine Zeit'), null)
})

// ── 5. Datumsfelder bleiben der Tag, der dasteht ───────────────────────────
test('serverDatum: „2026-11-09" bleibt 09.11., auch mit Uhrzeit dahinter', () => {
  const a = serverDatum('2026-11-09')
  const b = serverDatum('2026-11-09 23:30:00')
  assert.equal(a.getUTCDate(), 9)
  assert.equal(b.getUTCDate(), 9)
  // 23:30 UTC waere in Berlin schon der 10. — fuer ein DATUMSFELD ist das falsch.
  assert.equal(b.getUTCDate(), 9)
  assert.equal(serverDatum('2026-02-30'), null)
  assert.equal(serverDatum(''), null)
})

// ── 6. Waerter: kein replace(' ', 'T') mehr ausserhalb der zentralen Stelle ─
/**
 * Der Fehler entstand durch `new Date(String(x).replace(' ', 'T'))`. Diese
 * Zeile darf es im App-Code NICHT mehr geben — weder auf Server-Zeitstempeln
 * noch auf Termin-Zeiten (dort heisst die Funktion `wandZeit`). Die einzige
 * Ausnahme ist `src/shared/zeit.mjs` selbst (dort steht das Muster nur noch im
 * ERKLAERTEXT und in keinem Code).
 */
function dateien(wurzel) {
  const out = []
  for (const name of readdirSync(wurzel)) {
    const p = join(wurzel, name)
    if (statSync(p).isDirectory()) out.push(...dateien(p))
    else if (/\.(vue|js|mjs)$/.test(name)) out.push(p)
  }
  return out
}

/** Entfernt Kommentare grob (nur fuer den Waechter; kein Parser noetig). */
function ohneKommentare(text) {
  return text
    .replace(/\/\*[\s\S]*?\*\//g, ' ')
    .replace(/(^|\n)\s*\/\/[^\n]*/g, '$1 ')
    .replace(/<!--[\s\S]*?-->/g, ' ')
}

test('Waechter: kein replace(Leerzeichen, T) mehr im App-Code', () => {
  const treffer = []
  for (const pfad of dateien(SRC)) {
    const rel = relative(SRC, pfad)
    if (rel === join('shared', 'zeit.mjs')) continue          // zentrale Stelle
    const text = ohneKommentare(readFileSync(pfad, 'utf8'))
    if (/replace\(\s*' ',\s*'T'\s*\)/.test(text)) treffer.push(rel)
    if (/replace\(\s*" ",\s*"T"\s*\)/.test(text)) treffer.push(rel)
  }
  assert.deepEqual(treffer, [],
    'Zeitstempel/Zeiten nur ueber src/shared/zeit.mjs (serverZeit/wandZeit) lesen')
})

test('Waechter: kein neuer TZ-abhaengiger „roher" Date-Aufruf auf Zeitstempeln', () => {
  // `new Date(x)` ohne Zone ist genau die Falle. Erlaubt bleiben:
  //  * `new Date()` (jetzt),
  //  * `new Date(msZahl)` im Test,
  //  * Konstruktionen mit expliziten Teilen/UTC (Date.UTC(...), new Date(y, m, d)).
  // Der Waechter prueft nur Dateien, die technische Zeitstempel anzeigen — dort
  // ist ein blankes `new Date(<variable>)` ein Rueckfall in den Befund.
  const dateienMitZeitstempel = [
    'diakonos/pages/Profile.vue',
    'diakonos/components/website/MeineEinwilligung.vue',
    'diakonos/components/widgets/WikiRecentWidget.vue',
    'diakonos/pages/planrahmen/Plan.vue',
    'diakonos/pages/planrahmen/MeineDienste.vue',
    'diakonos/components/AppTopbar.vue',
  ]
  const treffer = []
  for (const rel of dateienMitZeitstempel) {
    const text = ohneKommentare(readFileSync(join(SRC, rel), 'utf8'))
    for (const m of text.matchAll(/new Date\(([^)]*)\)/g)) {
      const arg = m[1].trim()
      if (!arg) continue                        // new Date() = jetzt
      if (/^Date\.UTC/.test(arg)) continue
      if (/^\d+$/.test(arg)) continue            // Millisekunden
      treffer.push(`${rel}: new Date(${arg})`)
    }
  }
  assert.deepEqual(treffer, [],
    'Server-Zeitstempel ueber serverZeit/serverZeitText/serverDatum lesen')
})

test('Feld-Zuordnung: technische Zeitstempel laufen ueber serverZeit*', () => {
  const muss = {
    'diakonos/pages/Profile.vue': ['serverDatum'],
    'diakonos/components/website/MeineEinwilligung.vue': ['serverZeit'],
    'diakonos/components/widgets/WikiRecentWidget.vue': ['serverZeit'],
    'diakonos/pages/planrahmen/Plan.vue': ['serverZeitText'],
    'diakonos/pages/planrahmen/MeineDienste.vue': ['serverZeitText'],
    'diakonos/components/AppTopbar.vue': ['serverZeitText', 'serverZeit'],
  }
  for (const [rel, namen] of Object.entries(muss)) {
    const text = readFileSync(join(SRC, rel), 'utf8')
    for (const name of namen) {
      assert.ok(text.includes(name), `${rel} nutzt ${name}`)
    }
  }
})

test('Feld-Zuordnung: Termin-Zeiten laufen ueber wandZeit (nicht serverZeit)', () => {
  const muss = {
    'diakonos/composables/bf1Anzeige.js': 'wandZeit',
    'diakonos/components/kronos/terminZeitZeile.mjs': 'wandZeit',
    'diakonos/components/kronos/chipText.mjs': 'wandZeit',
    'diakonos/components/kronos/dayEventLabel.mjs': 'wandZeit',
    'diakonos/components/kronos/pruefZeile.mjs': 'wandZeit',
    'diakonos/components/widgets/UpcomingEventsWidget.vue': 'wandZeit',
  }
  for (const [rel, name] of Object.entries(muss)) {
    const text = readFileSync(join(SRC, rel), 'utf8')
    assert.ok(text.includes(name), `${rel} nutzt ${name}`)
    // pruefZeile: `start` ist Wandzeit, `vorText(creation)` ein Zeitstempel.
    if (rel.endsWith('pruefZeile.mjs')) continue
    assert.ok(!/serverZeit\(/.test(ohneKommentare(text)),
      `${rel} darf Termin-Zeiten NICHT als UTC lesen`)
  }
})

// ── 7. Gegenprobe: Kalender-Anzeige bleibt wie sie war ─────────────────────
test('Gegenprobe Kalender: Wandzeit-Formatierung liefert dieselbe Uhrzeit wie vorher', () => {
  // Was die Kalender-Anzeige vorher tat — hier nachgestellt und mit dem neuen
  // Weg verglichen: identisches Ergebnis, also verschiebt sich kein Termin.
  const wert = '2026-11-15 10:00:00'
  const alt = new Date(String(wert).replace(' ', 'T'))
  const neu = wandZeit(wert)
  assert.equal(neu.getTime(), alt.getTime())
  assert.equal(
    neu.toLocaleDateString('de-DE', { weekday: 'short', day: '2-digit', month: '2-digit' }),
    alt.toLocaleDateString('de-DE', { weekday: 'short', day: '2-digit', month: '2-digit' }),
  )
  // Sommer wie Winter.
  for (const sommer of ['2026-07-15 19:00:00', '2026-01-15 19:00:00']) {
    assert.equal(wandZeit(sommer).getTime(), new Date(String(sommer).replace(' ', 'T')).getTime())
  }
})

// ── 8. Nachtrag Review: Wartezeit im Prüf-Panel und Python-Offset-Form ─────
test('Prüf-Panel: vorText liest `modified` (naiv) als UTC', async () => {
  const { vorText, pruefZeile } = await import('../src/diakonos/components/kronos/pruefZeile.mjs')
  const jetzt = new Date('2026-11-07T12:00:00Z')
  // 10:00 UTC -> 2 h; als Wandzeit gelesen waeren es 3 h (Winter).
  assert.equal(vorText('2026-11-07 10:00:00', jetzt), 'vor 2 Stunden')
  const z = pruefZeile({ id: 'x', title: 'T', start: '2026-11-15 19:00:00',
    modified: '2026-07-07 10:00:00' }, new Date('2026-07-07T12:00:00Z'))
  assert.match(z.herkunft, /vor 2 Stunden$/, 'Sommer: ebenfalls 2 h, nicht 4 h')
})

test('Offset in Python-Schreibweise mit Leerzeichen wird gelesen', () => {
  assert.equal(serverZeitText('2026-11-09 16:09:12+00:00'), '09.11.2026, 17:09')
})
