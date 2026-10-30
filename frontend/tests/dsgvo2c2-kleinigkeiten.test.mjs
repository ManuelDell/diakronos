/**
 * DSGVO-2c2 — Review-Kleinigkeiten der Löschantrag-Oberfläche.
 *
 * Vier Befunde aus dem Review von DSGVO-2c, jeder mit eigener Zusage:
 *
 *  1. Übersicht: die Kachel „Löschanträge“ zeigte bei einem Fehler eine
 *     ERFUNDENE 0 (`offeneLoeschantraege ?? 0`). Jetzt steht dort KEINE Zahl
 *     („–“) und kein Hinweis — die Auskunft fehlt, sie ist nicht null.
 *  2. Übersicht: die Zahl kommt über den vorhandenen Helfer
 *     `offeneAntraegeZaehlen()` statt über einen zweiten, eigenen Aufruf von
 *     `get_loeschantraege`.
 *  3. Datenschutz: der tote Zweig `istAntrag`/`nur_antrag` ist weg — kein
 *     Aufruf `oeffnen(m, true)` mehr (serverseitig wirkungslos).
 *  4. Löschantragsliste: bei offenen Anträgen stand das Datum DOPPELT
 *     („Beantragt am 22.10.2026 · offen · 22.10.2026“). Jetzt einmal.
 *
 * Geprüft wird der Quelltext (wie `dsgvo2c`/`dsgvo2d`): die Regel selbst in
 * `loeschantraege.mjs` mit Werten, die Seiten per Quelltextmuster.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import { antragsStatusText, beantragtText, standText } from '../src/diakonos/components/mitglieder/loeschantraege.mjs'

const lies = (p) => readFileSync(new URL('../src/diakonos/' + p, import.meta.url), 'utf8')
const komponente = (p) => readFileSync(new URL('../src/diakonos/components/mitglieder/' + p, import.meta.url), 'utf8')

const uebersicht = lies('pages/mitglieder/Uebersicht.vue')
const datenschutz = lies('pages/mitglieder/Datenschutz.vue')
const liste = komponente('LoeschantraegeListe.vue')
const api = lies('composables/useLoeschantraege.js')

/** Nur AUSFÜHRBARER Code: Kommentare dürfen Wege benennen, geprüft wird was läuft. */
function skript(vue) {
  const marker = '<script setup>'
  const start = vue.indexOf(marker)
  const teil = start === -1 ? vue : vue.slice(start + marker.length)
  return teil
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .split('\n').map((z) => z.replace(/\/\/.*$/, '')).join('\n')
}

// ── 1. Keine erfundene Null in der Kachel ──────────────────────────────────

test('DSGVO-2c2 · die Kachel „Löschanträge“ erfindet bei einem Fehler keine 0', () => {
  // Die WERT-Zeile der Kachel darf aus „keine Auskunft“ keine Zahl machen.
  const wertZeile = skript(uebersicht).split('\n').find(z => /wert: offeneLoeschantraege/.test(z))
  assert.ok(wertZeile, 'die Kachel setzt ihren Wert sichtbar')
  assert.doesNotMatch(wertZeile, /\?\? 0/,
    'eine fehlende Auskunft ist keine Null')
  // Keine Zahl -> ein Strich, wie an den übrigen Stellen des Hauses.
  assert.match(uebersicht, /wert: offeneLoeschantraege\.value === null \? '–' : offeneLoeschantraege\.value/)
  // Kein Ton und kein Hinweis ohne Auskunft (sonst klingt „–“ wie „nichts zu tun“).
  assert.match(uebersicht, /ton: \(\(offeneLoeschantraege\.value \?\? 0\) > 0 \? 'warn' : 'neutral'\)/)
  assert.match(uebersicht, /hinweis: \(offeneLoeschantraege\.value \?\? 0\) > 0 \? 'warten auf Freigabe' : ''/)
  // Der Unterschied zwischen „keine Auskunft“ und „null offene“ bleibt erhalten:
  // nur der Helfer kennt den Fehlerfall, und er liefert dann `null`.
  assert.match(api, /export async function offeneAntraegeZaehlen\(\) \{\n  try \{[\s\S]*?\} catch \{\n    return null\n  \}\n\}/)
})

test('DSGVO-2c2 · „Zu erledigen“ bleibt bei fehlender Auskunft still', () => {
  // `if (offen)` — bei `null` keine Zeile, bei 0 keine Zeile: richtig so.
  assert.match(skript(uebersicht), /const offen = offeneLoeschantraege\.value\n  if \(offen\) \{/)
})

// ── 2. Ein Weg zur Zahl: der vorhandene Helfer ─────────────────────────────

test('DSGVO-2c2 · die Übersicht nutzt offeneAntraegeZaehlen() statt eines zweiten Aufrufs', () => {
  assert.match(skript(uebersicht),
    /import \{ offeneAntraegeZaehlen \} from '\.\.\/\.\.\/composables\/useLoeschantraege\.js'/)
  assert.match(skript(uebersicht),
    /offeneLoeschantraege\.value = await offeneAntraegeZaehlen\(\)/)
  // KEIN direkter Endpunkt-Aufruf und kein eigenes Zählen mehr auf der Seite.
  assert.doesNotMatch(skript(uebersicht), /apiCall\('diakronos\.diakonos\.api\.datenschutz\.get_loeschantraege'\)/)
  assert.doesNotMatch(skript(uebersicht), /Array\.isArray\(liste\) \? liste\.length : null/)
  // Der Helfer bleibt die einzige Stelle, die zählt.
  assert.match(api, /export async function offeneAntraegeZaehlen\(\) \{\n  try \{\n    const antraege = await antraegeLaden\('offen'\)\n    return Array\.isArray\(antraege\) \? antraege\.length : null\n  \} catch \{\n    return null\n  \}\n\}/)
})

// ── 3. Toter Zweig ist weg ─────────────────────────────────────────────────

test('DSGVO-2c2 · Datenschutz.vue hat keinen toten Zweig istAntrag/nur_antrag mehr', () => {
  for (const quelle of [skript(datenschutz), datenschutz]) {
    assert.doesNotMatch(quelle, /istAntrag/)
    assert.doesNotMatch(quelle, /nur_antrag/)
    assert.doesNotMatch(quelle, /oeffnen\(m, true\)/)
    assert.doesNotMatch(quelle, /dialogTitel/)
  }
  // Der Dialog heißt fest, was er tut.
  assert.match(datenschutz, /title="Person anonymisieren"/)
  assert.match(skript(datenschutz), /function oeffnen\(m\) \{\n  ziel\.value = m\n/)
})

// ── 4. Das Datum steht einmal ──────────────────────────────────────────────

test('DSGVO-2c2 · offener Antrag nennt das Datum nicht zweimal', () => {
  // Die Regel: Stand OHNE Datum, wenn das Datum derselbe Tag ist, den
  // `beantragtText` schon nennt. Nicht der Fall ist: „abgelehnt am 09.10.“
  // neben „Beantragt am 01.10.“ — dort sind es zwei verschiedene Tage.
  assert.equal(
    standText({ status: 'offen', beantragt_am: '2026-10-22T08:00:00' }),
    antragsStatusText({ status: 'offen', beantragt_am: '2026-10-22T08:00:00' }).text)
  assert.equal(standText({ status: 'offen', beantragt_am: '2026-10-22T08:00:00' }), 'offen')
  assert.equal(beantragtText({ status: 'offen', beantragt_am: '2026-10-22T08:00:00' }), 'Beantragt am 22.10.2026')
  // Abgelehnt: anderer Tag -> Datum bleibt („abgelehnt · 09.10.2026“).
  assert.equal(
    standText({ status: 'abgelehnt', beantragt_am: '2026-10-01', abgelehnt_am: '2026-10-09' }),
    'abgelehnt · 09.10.2026')
  // Gleicher Tag (Altbestand: am Antragstag erledigt) -> auch hier nur einmal.
  assert.equal(
    standText({ status: 'abgelehnt', beantragt_am: '2026-10-09', abgelehnt_am: '2026-10-09' }),
    'abgelehnt')
  // Ohne Datum zum Stand bleibt der Stand allein.
  assert.equal(standText({ status: 'offen' }), 'offen')
  assert.equal(standText({ status: 'zurueckgezogen' }), 'zurückgezogen')
  // Die Liste benutzt die neue Funktion statt der eigenen Zeilenbauerei.
  assert.match(skript(liste), /import \{\n  ANTRAG_FILTER, antragsStatusText, beantragtText, nameFuerAntrag, standText,\n\} from '\.\/loeschantraege\.mjs'/)
  assert.match(liste, /\{\{ standText\(a\) \}\}/)
  assert.doesNotMatch(liste, /function standText\(a\) \{\n  const stand = antragsStatusText\(a\)\n  if \(stand\.am\) return/)
})
