import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

/**
 * N9b — Regressionswächter fuer die Nacharbeit N9 (Befund).
 *
 * Geprüft wird an den QUELLDATEIEN (kein vue-Renderer noetig):
 *  - H-1: die oeffentliche Registrierung/Gast-Seite zeigt den Server-Text
 *         (window.__diakronos.texte) und rendert ihn als REINEN TEXT
 *         ({{ }} statt v-html).
 *  - M-1: Willkommenstext der Gemeinde ist angebunden; die Link-Vorgaben
 *         werden beim Anlegen eines Links vorbelegt.
 *  - R-N8: die Karte „Wartende Konten“ zeigt abgelehnte Zuordnungen.
 */

const lesen = (rel) => readFileSync(new URL(rel, import.meta.url), 'utf8')

const registrierung = lesen('../src/registrierung/App.vue')
const gast = lesen('../src/gast/App.vue')
const wartende = lesen('../src/diakonos/components/WartendeKontenKarte.vue')
const regSeite = lesen('../src/diakonos/pages/Registrierung.vue')

test('H-1 Registrierung: Einwilligungstext kommt vom Server und ist reiner Text', () => {
  assert.match(registrierung, /window\.__diakronos\?\.texte/, 'Texte muessen aus dem Boot-Objekt kommen')
  assert.match(registrierung, /\{\{\s*texte\.einwilligung\s*\}\}/, 'Einwilligung als Text ausgeben')
  assert.doesNotMatch(registrierung, /v-html\s*=/, 'kein v-html (XSS-Schutz, reiner Text)')
  // Der alte fest eingebaute Text darf nicht mehr existieren.
  assert.doesNotMatch(registrierung, /Deine personenbezogenen Daten werden zum Zweck/)
})

test('H-1 Gast: Einwilligungstext kommt vom Server und ist reiner Text', () => {
  assert.match(gast, /window\.__diakronos\?\.texte/)
  assert.match(gast, /\{\{\s*texte\.einwilligung\s*\}\}/)
  assert.doesNotMatch(gast, /v-html\s*=/)
})

test('M-1: Willkommenstext und Datenschutzerklaerung sind angebunden', () => {
  assert.match(registrierung, /willkommenstext/)
  assert.match(registrierung, /texte\.datenschutzerklaerung/)
  assert.match(registrierung, /texte\.aufbewahrung/)
  assert.match(gast, /willkommenstext/)
})

test('M-1: Link-Vorgaben werden beim Anlegen eines Links vorbelegt', () => {
  assert.match(regSeite, /gemeinde_get_einstellungen/, 'Vorgaben werden geladen')
  assert.match(regSeite, /linkVorgaben/, 'Vorgaben steuern die Vorbelegung')
  assert.match(regSeite, /ladeLinkVorgaben/)
})

test('M-1 (R-N9b): am einzelnen Link sind „ohne Ablauf"/„unbegrenzt" waehlbar', () => {
  // Ein leeres Feld heisst Vorgabe — ausdruecklich unbefristet/unbegrenzt muss
  // deshalb ein eigener Schalter sein, sonst kann die Verwaltung die Vorgabe
  // nicht uebersteuern (Befund R-N9b).
  assert.match(regSeite, /ohne_ablauf/)
  assert.match(regSeite, /unbegrenzt/)
  // Die ausdrueckliche Wahl setzt den Wert vor dem Absenden hart (sonst saehe
  // der Server die Vorgabe-Zahl als ausdruecklichen Wert).
  assert.match(regSeite, /if \(nutzlast\.ohne_ablauf\)/)
  assert.match(regSeite, /if \(nutzlast\.unbegrenzt\)/)
})

test('R-N8: Wartende Konten zeigt abgelehnte Zuordnungen mit Grund', () => {
  assert.match(wartende, /abgelehnt/)
  assert.match(wartende, /a\.grund/)
  // Der Code wird nie roh angezeigt — es gibt eine Uebersetzung.
  assert.match(wartende, /grundText/)
})

test('M-2: Datenschutz-Texte unterscheiden Entwurf und veroeffentlichte Fassung', () => {
  const gem = lesen('../src/diakonos/composables/useGemeinde.js')
  const seite = lesen('../src/diakonos/pages/einstellungen/DatenschutzTexte.vue')
  // Die wirksame Fassung kommt getrennt vom Entwurf vom Server.
  assert.match(gem, /veroeffentlichte_version/)
  assert.match(gem, /veroeffentlichteVersion/)
  // Die Oberflaeche sagt klar, dass ein Entwurf die Anmeldeseite nicht aendert.
  assert.match(gem, /auf der Anmeldeseite gilt weiter Fassung/)
  assert.match(seite, /statusText/)
})
