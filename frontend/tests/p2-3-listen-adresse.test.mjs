/**
 * P2-3 · OP-UI-8 — Such- und Filterzustand bleibt in der Adresse.
 *
 * Befund: Bei „Lieder“ und „Gruppen“ ging die Suche nach „Detail ansehen →
 * Zurück“ verloren (Lieder 24→50 bzw. 28→50 Treffer; Gruppen 15→26 Kacheln).
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  adresseSchreiben, zustandAusAdresse, pfadOhneAbfrage,
} from '../src/diakonos/composables/listenzustand.mjs'

test('OP-UI-8 · Lieder: Suchbegriff überlebt den Ausflug ins Detail', () => {
  // Nutzer sucht „Herr“ und öffnet ein Lied.
  const adresse = adresseSchreiben('#/lieder', { q: 'Herr' })
  assert.equal(adresse, '#/lieder?q=Herr')
  // Beim Zurückkehren liest die Liste denselben Zustand.
  assert.equal(zustandAusAdresse(adresse).q, 'Herr')
})

test('OP-UI-8 · Lieder: Filter bleiben ebenfalls erhalten', () => {
  const adresse = adresseSchreiben('#/lieder', {
    q: 'Komm', kategorie: 'Lob', anlass: 'Gottesdienst',
  })
  const zustand = zustandAusAdresse(adresse)
  assert.equal(zustand.q, 'Komm')
  assert.equal(zustand.kategorie, 'Lob')
  assert.equal(zustand.anlass, 'Gottesdienst')
})

test('OP-UI-8 · Gruppen: gewählter Dienstbereich bleibt erhalten', () => {
  const adresse = adresseSchreiben('#/gruppen', { gruppenname: 'Diakonie' })
  assert.equal(zustandAusAdresse(adresse).gruppenname, 'Diakonie')
})

test('OP-UI-8 · leere Werte stehen nicht in der Adresse', () => {
  assert.equal(adresseSchreiben('#/lieder', { q: '', kategorie: '' }), '#/lieder')
  assert.equal(adresseSchreiben('#/lieder', {}), '#/lieder')
})

test('OP-UI-8 · Sonderzeichen/Umlaute werden kodiert', () => {
  const adresse = adresseSchreiben('#/lieder', { q: 'Weiß & Blau' })
  assert.ok(adresse.startsWith('#/lieder?'))
  assert.equal(zustandAusAdresse(adresse).q, 'Weiß & Blau')
})

test('OP-UI-8 · Pfad bleibt unverändert, Abfrageteil wird getrennt', () => {
  assert.equal(pfadOhneAbfrage('#/lieder?q=Herr'), '#/lieder')
  assert.equal(pfadOhneAbfrage('#/gruppen'), '#/gruppen')
})

test('OP-UI-8 · fremde Parameter werden nicht übernommen', () => {
  const zustand = zustandAusAdresse('#/lieder?q=x&boese=1')
  assert.equal(zustand.q, 'x')
  assert.ok(!('boese' in zustand))
})
