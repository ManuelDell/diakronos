/**
 * PLAN-W1 — Warnungen in Plänen nur für Planer, einklappbar
 * (Befund DMB-7d8e3068c388, Manuel 2026-10-23: „Nur für Planer“).
 *
 * Der Befund: Wer einen Plan nur ANSIEHT, bekam die Prüf-Warnungen
 * (PrMeldungen) zu sehen — und konnte sie nicht abstellen. Festgehalten wird
 * die Oberflächen-Seite:
 *
 *   * Plan.vue zeigt den Warnblock NUR mit Bearbeitungsrecht — und reicht
 *     dieses Recht als zweite Wand an alle Prüf-Meldungen weiter
 *     (`provide('planrahmenWarnungen')`), damit auch alte Cache-Stände und die
 *     kompakten Zeilen-Meldungen (Tabelle/Raster/Kalender) nicht durchkommen.
 *   * PrMeldungen liefert für Betrachter nichts aus — unabhängig davon, was
 *     ihm gereicht wird.
 *   * Der Warnblock ist ein-/ausklappbar; die Wahl gilt je Benutzer weiter
 *     (localStorage, Kern in `warnblock.mjs`) und wird beim Abmelden geleert.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import {
  WARNBLOCK_PRAEFIX, warnblockKern, warnblockSchluessel,
} from '../src/diakonos/composables/warnblock.mjs'

const root = new URL('../src/diakonos/', import.meta.url)
const lies = (p) => readFileSync(new URL(p, root), 'utf8')

const PLAN = lies('pages/planrahmen/Plan.vue')
const MELDUNGEN = lies('components/planrahmen/PrMeldungen.vue')
const ABMELDEN = lies('composables/useAbmelden.js')

/** Storage-Attrappe wie window.localStorage. */
function speicher() {
  const daten = new Map()
  return {
    getItem: (k) => (daten.has(k) ? daten.get(k) : null),
    setItem: (k, v) => { daten.set(k, String(v)) },
    removeItem: (k) => { daten.delete(k) },
    get length() { return daten.size },
    key: (i) => [...daten.keys()][i] ?? null,
    _daten: daten,
  }
}

// ── Planer sehen die Warnungen, Betrachter nie ─────────────────────────────

test('PLAN-W1: der Warnblock der Regelprüfung hängt am Bearbeitungsrecht', () => {
  // Der Block mit der Zusammenfassung „Regelprüfung des aktuellen Plans"
  // darf ohne `darfBearbeiten` nicht im Baum stehen.
  const block = PLAN.slice(PLAN.indexOf('titel="Regelprüfung des aktuellen Plans"') - 900,
                            PLAN.indexOf('titel="Regelprüfung des aktuellen Plans"'))
  assert.match(block, /v-if="darfBearbeiten"/, 'Warnblock ohne Rechteprüfung')
  // Und das Recht kommt aus der Server-Antwort, nicht aus einer Annahme.
  assert.match(PLAN, /const darfBearbeiten = computed\(\(\) => !\!\(planDaten\.value\?\.darf_bearbeiten/)
})

test('PLAN-W1: das Bearbeitungsrecht gilt auch für die übrigen Prüf-Meldungen', () => {
  // PrMeldungen prüft den injizierten Riegel selbst …
  assert.match(MELDUNGEN, /const warnungenErlaubt = inject\('planrahmenWarnungen'/)
  assert.match(MELDUNGEN, /<template v-if="meldungenZeigen">/)
  // … und der Plan setzt ihn auf genau das Bearbeitungsrecht.
  assert.match(PLAN, /provide\('planrahmenWarnungen', computed\(\(\) => darfBearbeiten\.value\)\)/)
  // Der Riegel umschließt ALLE Fälle (kompakt, Zusammenfassung, Liste):
  // die Sperre steht vor dem ersten `<details`.
  assert.ok(MELDUNGEN.indexOf('v-if="meldungenZeigen"') < MELDUNGEN.indexOf('v-if="kompakt && meldungen.length"'),
    'Sperre steht nicht vor dem ersten Warnblock')
})

test('PLAN-W1: Ansicht bekommt das Recht als meldungen-zeigen (Tabelle/Raster/Kalender)', () => {
  const ansicht = lies('components/planrahmen/PrAnsicht.vue')
  const treffer = ansicht.match(/:meldungen-zeigen="bearbeitbar"/g) || []
  assert.equal(treffer.length, 3, 'nicht alle Ansichten folgen dem Bearbeitungsrecht')
})

// ── Einklappen, je Benutzer gemerkt ────────────────────────────────────────

test('PLAN-W1: der Warnblock ist ein- und ausklappbar und meldet die Bedienung', () => {
  assert.match(MELDUNGEN, /zusammenfassung && meldungen\.length/)
  assert.match(MELDUNGEN, /:open="offen === null \? undefined : offen"/)
  assert.match(MELDUNGEN, /@toggle="offenSetzen\(\$event\)"/)
  assert.match(MELDUNGEN, /emit\('aktualisiert:offen', an\)/)
  // Die Beschriftung sagt, was der Klick tut.
  assert.match(MELDUNGEN, /\{\{ offen \? 'Einklappen' : 'Anzeigen' \}\}/)
  // Ein Aufbau durch die Bindung selbst ist keine Bedienung -> Sperre.
  assert.match(MELDUNGEN, /const sperre = ref\(false\)/)
})

test('PLAN-W1: die Wahl des Planers wird gespeichert und wieder angewendet', () => {
  assert.match(PLAN, /const warnblockOffen = ref\(!warnblock\.eingeklappt\(\)\)/)
  assert.match(PLAN, /:offen="warnblockOffen"/)
  assert.match(PLAN, /function warnblockMerken\(offen\)/)
  assert.match(PLAN, /warnblock\.setzen\(!warnblockOffen\.value\)/)
})

test('PLAN-W1: Zustand gilt je Benutzer, Vorgabe ist „offen"', () => {
  const s = speicher()
  const a = warnblockKern({ speicher: s, benutzer: () => 'anna@example.org' })
  const b = warnblockKern({ speicher: s, benutzer: () => 'bernd@example.org' })
  // Ohne Eintrag bleibt der Block offen — Warnungen sind sichtbar.
  assert.equal(a.eingeklappt(), false)
  assert.equal(a.umschalten(), true)
  assert.equal(a.eingeklappt(), true)
  // Der andere Benutzer ist davon unberührt.
  assert.equal(b.eingeklappt(), false)
  // Der Schlüssel hängt am Benutzer.
  assert.equal(a.schluessel(), warnblockSchluessel('anna@example.org'))
  assert.notEqual(a.schluessel(), b.schluessel())
  assert.ok(a.schluessel().startsWith(WARNBLOCK_PRAEFIX))
  // Wieder aufklappen entfernt den Eintrag (kein Rest im Speicher).
  assert.equal(a.umschalten(), false)
  assert.equal(s.getItem(a.schluessel()), null)
})

test('PLAN-W1: verstümmelter oder fehlender Speicher öffnet den Block', () => {
  const s = speicher()
  s.setItem(warnblockSchluessel('anna@example.org'), 'kaputt')
  const k = warnblockKern({ speicher: s, benutzer: () => 'anna@example.org' })
  assert.equal(k.eingeklappt(), false)
  // Ohne Speicher (privater Modus) funktioniert alles still weiter.
  const ohne = warnblockKern({ speicher: null, benutzer: () => 'anna@example.org' })
  assert.equal(ohne.eingeklappt(), false)
  assert.equal(ohne.setzen(true), false)
  // Ein gesperrter Speicher darf nie werfen.
  const gesperrt = warnblockKern({
    speicher: { getItem() { throw new Error('gesperrt') }, setItem() { throw new Error('gesperrt') }, removeItem() { throw new Error('gesperrt') } },
    benutzer: () => 'anna@example.org',
  })
  assert.equal(gesperrt.eingeklappt(), false)
  assert.doesNotThrow(() => gesperrt.setzen(true))
})

test('PLAN-W1: der gemerkte Zustand überlebt das Abmelden', () => {
  // Operator-Korrektur: Die Wahl haengt am BENUTZER (Schluessel
  // `pr-warnblock:<benutzer>`) und soll beim naechsten Anmelden wieder
  // gelten — sie gehoert deshalb NICHT in die Aufraeum-Praefixe der
  // Abmeldung (sonst waere der Zustand nach jedem Abmelden weg).
  const praefixe = ABMELDEN.match(/const PRAEFIXE = \[[^\]]*\]/)
  assert.ok(praefixe, 'Praefix-Liste der Abmeldung nicht gefunden')
  assert.doesNotMatch(praefixe[0], /pr-warnblock/)
  // Und der Schluessel selbst bleibt benutzergebunden.
  assert.ok(warnblockSchluessel('anna@example.org').startsWith(WARNBLOCK_PRAEFIX))
})
