/**
 * UI-R4d — Nacharbeit an den Regeln der Prüfliste (Kleinigkeiten aus dem
 * Review zu UI-R4c). Die Verhaltensfälle (Mount) stehen in
 * `uir4d-pruefliste-mount.test.mjs`; hier laufen die reinen Regeln.
 *
 * Punkt 4: „… wartet auf weitere Stufen.“ ist bei EINEM wartenden Termin
 *   falsch (es gibt keine weiteren). Ohne `ergebnisse` heißt es dann
 *   „… wartet auf die nächste Stufe.“ — Mehrzahl nur, wenn wirklich mehrere
 *   Termine auf mehrere Stufen warten.
 * Punkt 5: die Warteline nennt die Stufe als STUFE („wartet auf Freigabe
 *   für: …“) — sonst liest sie sich wie ein Empfänger.
 * Punkt 6: `has_konflikt` wird im CLIENT berechnet (ModerationBoard
 *   `groupItems`), nicht vom Server — der Kommentar muss das sagen.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const HIER = dirname(fileURLToPath(import.meta.url))
const SRC = resolve(HIER, '..', 'src', 'diakonos')
const lies = (rel) => readFileSync(join(SRC, rel), 'utf8')

const F = await import(pathToFileURL(join(SRC, 'components/kronos/freigabeStufen.mjs')).href)

/** Server-Titel setzen (die Regeln lesen `stufenTitel.wert`). */
function titelSetzen() {
  F.stufenTitel.wert = {
    untergruppe: 'Untergruppe',
    gruppe: 'Gruppe',
    gemeinde: 'Alle Mitglieder der Gemeinde',
  }
}

// ══════════════════════════════════════════════════════════════════════════
// Punkt 4 · „weitere Stufen“ nur, wenn es wirklich mehrere sind
// ══════════════════════════════════════════════════════════════════════════
test('UI-R4d · EIN wartender Termin ohne `ergebnisse` wartet auf „die nächste Stufe“ (kein „weitere“)', () => {
  titelSetzen()
  // Antwort von `finalize_staged_events` ohne `ergebnisse` (alter/karger Server).
  const einer = F.sammelMeldung({ finalized: 1, festgelegt: 0, weitergereicht: 1 })
  assert.equal(einer.text, '1 Termin wartet auf die nächste Stufe.')
  assert.doesNotMatch(einer.text, /weitere Stufen/,
    'bei einem Termin gibt es keine „weiteren Stufen“')
  assert.equal(einer.ton, 'warning')
  assert.equal(einer.weitergereicht, 1)

  // Derselbe Satz als Baustein: `wartetAufSatz` liefert den Objekt-Teil.
  assert.equal(F.wartetAufSatz({ finalized: 1, festgelegt: 0, weitergereicht: 1 }),
    'die nächste Stufe')
})

test('UI-R4d · mehrere wartende Termine ohne Stufen-Auskunft warten auf „weitere Stufen“', () => {
  titelSetzen()
  const zwei = F.sammelMeldung({ finalized: 2, festgelegt: 0, weitergereicht: 2 })
  assert.equal(zwei.text, '2 Termine warten auf weitere Stufen.')
  // Auch gemischt: festgelegt + mehrere wartende.
  const gemischt = F.sammelMeldung({ finalized: 2, festgelegt: 1, weitergereicht: 2 })
  assert.equal(gemischt.text, '1 freigegeben, 2 warten auf weitere Stufen.',
    'zwei wartende Termine sind Mehrzahl — auch wenn einer festgelegt ist')

  // Und gemischt mit EINEM wartenden: Einzahl „wartet auf die nächste Stufe“.
  const einerGemischt = F.sammelMeldung({ finalized: 2, festgelegt: 1, weitergereicht: 1 })
  assert.equal(einerGemischt.text, '1 freigegeben, 1 wartet auf die nächste Stufe.',
    'EIN wartender Termin bleibt Einzahl — auch wenn andere festgelegt sind')
})

test('UI-R4d · eine GENANNTE Stufe schlägt jede Mehrzahl-Formulierung', () => {
  titelSetzen()
  const mitStufe = {
    finalized: 1, festgelegt: 0, weitergereicht: 1,
    ergebnisse: { 'EV-1': { status: 'Vorschlag', offen: ['gemeinde'], naechste_stufe: 'gemeinde' } },
  }
  assert.equal(F.wartetAufSatz(mitStufe), 'die Freigabe der Stufe „Alle Mitglieder der Gemeinde“')
  assert.equal(F.sammelMeldung(mitStufe).text,
    '1 Termin wartet auf die Freigabe der Stufe „Alle Mitglieder der Gemeinde“.')
  // Mehrere Stufen offen → keine benennen (bleibt bei `ergebnisse`).
  const mehrereStufen = {
    finalized: 2, festgelegt: 0, weitergereicht: 2,
    ergebnisse: {
      'EV-1': { status: 'Vorschlag', offen: ['gruppe'], naechste_stufe: 'gruppe' },
      'EV-2': { status: 'Vorschlag', offen: ['gemeinde'], naechste_stufe: 'gemeinde' },
    },
  }
  assert.equal(F.wartetAufSatz(mehrereStufen), 'weitere Stufen')
})

// ══════════════════════════════════════════════════════════════════════════
// Punkt 5 · Warteline liest sich als STUFE
// ══════════════════════════════════════════════════════════════════════════
test('UI-R4d · Warteline sagt „wartet auf Freigabe für: <Stufe>“', () => {
  titelSetzen()
  assert.equal(F.wartetAufText({ stufe: 'untergruppe', darf_pruefen: false }),
    'wartet auf Freigabe für: Untergruppe')
  assert.equal(F.wartetAufText({ stufe: 'gemeinde', darf_pruefen: true }),
    'wartet auf Freigabe für: Alle Mitglieder der Gemeinde')
  // Gleiche Regel wie bei den Freigabe-Sätzen: der Titel ist eine Stufe,
  // kein Empfänger — kein „an …“ ohne „Freigabe“.
  assert.doesNotMatch(F.wartetAufText({ stufe: 'gemeinde' }), /^wartet auf: /,
    'die alte Form („wartet auf: <Titel>“) las sich wie ein Empfänger')
  // Ohne Stufe: keine Zeile (es wird keine Stufe erfunden).
  assert.equal(F.wartetAufText({ stufe: '', darf_pruefen: true }), null)
  assert.equal(F.wartetAufText(null), null)
})

// ══════════════════════════════════════════════════════════════════════════
// Punkt 6 · `has_konflikt` kommt NICHT vom Server
// ══════════════════════════════════════════════════════════════════════════
test('UI-R4d · der Kommentar sagt, woher `has_konflikt` kommt (Client, nicht Server)', () => {
  const quelle = lies('components/kronos/freigabeStufen.mjs')
  // Der Behauptungssatz des alten Kommentars darf nicht mehr stehen.
  assert.doesNotMatch(quelle, /für Serienkarten sagt das der Server über `has_konflikt`/,
    'der Kommentar behauptet weiter, der Server liefere `has_konflikt`')
  // Und der richtige Ort ist benannt.
  assert.match(quelle, /groupItems[\s\S]{0,400}has_konflikt|has_konflikt[\s\S]{0,400}groupItems/,
    'der Kommentar muss `has_konflikt` als Client-Feld (ModerationBoard `groupItems`) benennen')
  // Die Berechnung steht wirklich im Client.
  const tafel = lies('components/kronos/ModerationBoard.vue')
  assert.match(tafel, /const hasKonflikt = evts\.some\(e => e\.status === 'Konflikt'\)/,
    '`has_konflikt` wird in `groupItems` berechnet')
  assert.match(tafel, /has_konflikt: hasKonflikt/)
})
