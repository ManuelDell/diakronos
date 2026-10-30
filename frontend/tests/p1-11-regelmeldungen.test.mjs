/**
 * P1-11 — Regelmeldungen der Planansicht sind internes Planerwissen (UXP-R19).
 *
 * Die Regelpruefung („0 Fehler · 39 Warnungen") darf einem Mitglied nicht
 * angezeigt werden. Sie wird an jeder Anzeigestelle an das Bearbeitungsrecht
 * gebunden. Da Vue-Templates ohne Renderer nicht sinnvoll laufen, prueft
 * dieser Test den Quelltext an den entscheidenden Stellen — der eigentliche
 * Rechte-Entscheid kommt ohnehin vom Server (`darf_bearbeiten`).
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const root = new URL('../src/diakonos/', import.meta.url)
const lies = p => readFileSync(new URL(p, root), 'utf8')

test('Jede Ansicht bindet die Regelmeldungen an meldungenZeigen/bearbeitbar (UXP-R19)', () => {
  // Tabelle, Raster: neues Flag `meldungenZeigen`.
  for (const datei of ['components/planrahmen/PrTabelle.vue', 'components/planrahmen/PrRaster.vue']) {
    const q = lies(datei)
    assert.match(q, /<PrMeldungen v-if="meldungenZeigen"/,
      `${datei}: PrMeldungen nicht an meldungenZeigen gebunden`)
    assert.match(q, /meldungenZeigen: \{ type: Boolean, default: false \}/,
      `${datei}: meldungenZeigen-Prop fehlt (Default muss aus sein)`)
  }
  // Kalender + Ablauf/Programm: ueber `bearbeitbar`.
  for (const datei of ['components/planrahmen/PrKalender.vue', 'components/planrahmen/PrAblauf.vue']) {
    const q = lies(datei)
    assert.match(q, /<PrMeldungen v-if="bearbeitbar"|v-if="meldungenZeigen"/,
      `${datei}: PrMeldungen nicht an das Bearbeitungsrecht gebunden`)
  }
})

test('PrAnsicht reicht das Recht als meldungen-zeigen an Tabelle/Raster/Kalender (UXP-R19)', () => {
  const q = lies('components/planrahmen/PrAnsicht.vue')
  const treffer = q.match(/:meldungen-zeigen="bearbeitbar"/g) || []
  assert.ok(treffer.length >= 3, `erwartet mindestens 3 Bindungen, gefunden ${treffer.length}`)
})

test('Die Planseite zeigt die Regelpruefung nur mit Bearbeitungsrecht (UXP-R19)', () => {
  const q = lies('pages/planrahmen/Plan.vue')
  // PLAN-W1: Der Block der Regelpruefung ist an darfBearbeiten gebunden UND
  // ein-/ausklappbar (Einklapp-Zustand je Benutzer im localStorage).
  const block = q.match(/<PrMeldungen\s[^>]*titel="Regelprüfung des aktuellen Plans"[\s\S]{0,400}?\/>/)
  assert.ok(block, 'Plan.vue: Warnblock der Regelprüfung nicht gefunden')
  assert.match(block[0], /v-if="darfBearbeiten"/,
    'Plan.vue: Regelprüfung des Plans nicht an darfBearbeiten gebunden')
  assert.match(block[0], /:meldungen="terminMeldungen\(eintraege\)"/,
    'Plan.vue: Warnblock zeigt nicht die Termin-Meldungen')
  assert.match(block[0], /:offen="warnblockOffen"/,
    'Plan.vue: Warnblock ohne Einklapp-Zustand')
  assert.match(block[0], /@aktualisiert:offen="warnblockMerken"/,
    'Plan.vue: Einklapp-Zustand wird nicht gemerkt')
})
