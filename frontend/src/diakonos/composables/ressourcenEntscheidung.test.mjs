/**
 * P1-4b — Ressourcen: Termin-Anfragen entscheidbar (Verhaltenstests).
 *
 * Prueft die reine Zuordnung Anfrage -> Endpunkt/Parameter. Damit ist der
 * Befund B1 VERHALTENSBASIERT abgedeckt (Review-Punkt W1) — nicht mehr nur per
 * Quelltext-Regex. Die Seite `Ressourcen.vue` benutzt genau diese Helfer.
 */
import test from 'node:test'
import assert from 'node:assert/strict'

import {
  RESSOURCEN_MODUL,
  entscheidungsEndpunkt,
  entscheidungsArgumente,
  istTerminAnfrage,
} from './ressourcenEntscheidung.js'

const BUCHUNG = { id: 'BUC-1', quelle: undefined, ressource: 'RES-BEAMER' }
const TERMIN = { id: 'ER-1', quelle: 'termin', ressource: 'RES-BEAMER' }

test('P1-4b/B1: Raumbuchung geht an decide_buchung', () => {
  assert.equal(entscheidungsEndpunkt(BUCHUNG), `${RESSOURCEN_MODUL}.decide_buchung`)
})

test('P1-4b/B1: Termin-Ressource geht an decide_termin_ressource', () => {
  assert.equal(entscheidungsEndpunkt(TERMIN), `${RESSOURCEN_MODUL}.decide_termin_ressource`)
})

test('P1-4b/B1: Buchungen uebergeben buchung_id, Termin-Ressourcen zeile_id', () => {
  assert.deepEqual(entscheidungsArgumente(BUCHUNG, 'bestaetigen'), {
    buchung_id: 'BUC-1', entscheidung: 'bestaetigen',
  })
  assert.deepEqual(entscheidungsArgumente(TERMIN, 'bestaetigen'), {
    zeile_id: 'ER-1', entscheidung: 'bestaetigen',
  })
})

test('P1-4b/B1: Ablehnen traegt den Grund mit (getrimmt)', () => {
  assert.deepEqual(entscheidungsArgumente(BUCHUNG, 'ablehnen', '  kein Bedarf  '), {
    buchung_id: 'BUC-1', entscheidung: 'ablehnen', grund: 'kein Bedarf',
  })
  assert.deepEqual(entscheidungsArgumente(TERMIN, 'ablehnen', 'belegt'), {
    zeile_id: 'ER-1', entscheidung: 'ablehnen', grund: 'belegt',
  })
})

test('P1-4b/B1: fehlende/leere Quelle gilt als Buchung (Bestandsverhalten)', () => {
  assert.equal(istTerminAnfrage({ id: 'X' }), false)
  assert.equal(istTerminAnfrage(null), false)
  assert.equal(entscheidungsEndpunkt({ id: 'X' }), `${RESSOURCEN_MODUL}.decide_buchung`)
  assert.equal(istTerminAnfrage(TERMIN), true)
})
