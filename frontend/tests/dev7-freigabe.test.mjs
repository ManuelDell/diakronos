/**
 * DEV-7 — Kalendermoderator gibt seine EIGENEN Termine frei
 * (Befund DMB-eb5c6c69ea54).
 *
 * Quelltext-Waechter fuer die Oberflaeche:
 *
 *   * Der Vorschlagsdialog („Termin bearbeiten“) bietet einen Knopf
 *     „Freigeben“ an — fuer eigene UND fremde Vorschlaege gleich, denn die
 *     Schranke ist das Moderationsrecht am Kalender (serverseitig
 *     `_require_moderator`).
 *   * Der Knopf ruft `resolveConflict(..., 'festlegen', ...)` und uebernimmt
 *     dabei die Formularwerte — vorher blieb nach „Speichern“ alles ein
 *     Vorschlag, und es gab im Dialog gar keine Freigabe.
 *   * Am Handy bricht die vierteilige Knopfleiste um (kein Ueberlauf).
 *   * Die API-Schicht kennt die Aktion `festlegen` unveraendert weiter.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const root = new URL('../src/diakonos/', import.meta.url)
const lies = (p) => readFileSync(new URL(p, root), 'utf8')

const MODALS = lies('components/kronos/ModerationModals.vue')
const KANBAN_API = lies('api/kanbanApi.js')

// ── Freigeben-Knopf im Vorschlagsdialog ─────────────────────────────────────

test('DEV-7: Vorschlagsdialog hat einen Knopf „Freigeben“', () => {
  // Der Knopf sitzt im Footer des Bearbeiten-Dialogs, nicht im Konflikt-Dialog.
  const bearbeiten = MODALS.slice(0, MODALS.indexOf('Termin ablehnen'))
  assert.match(bearbeiten, /data-testid="dk-mod-freigeben"/)
  assert.match(bearbeiten, />\s*Freigeben\s*</)
})

test('DEV-7: Freigeben ruft resolveConflict mit der Aktion festlegen', () => {
  assert.match(MODALS, /async function submitFreigeben\(\)/)
  // Eigene Formularwerte gehen mit — die Freigabe darf Korrekturen uebernehmen.
  assert.match(
    MODALS,
    /resolveConflict\(editEvent\.value\.id, 'festlegen', getEditFormData\(editForm\.value\)\)/,
  )
  // Nach dem Erfolg wird die Liste neu geladen.
  assert.match(MODALS, /showToast\('Termin freigegeben', 'success'\)/)
})

test('DEV-7: Freigeben ist nicht auf eigene Termine beschraenkt', () => {
  // Kein owner/antragsteller-Vergleich in der Oberflaeche: wer die Seite
  // sieht, moderiert den Kalender — das entscheidet der Server.
  const freigeben = MODALS.slice(MODALS.indexOf('async function submitFreigeben'))
  const rumpf = freigeben.slice(0, freigeben.indexOf('// ── OP-EVENT-12'))
  assert.doesNotMatch(rumpf, /owner|antragsteller|erstellt_von/)
})

test('DEV-7: „Speichern“ bleibt beim Vorschlagsweg', () => {
  assert.match(MODALS, /resolveConflict\(editEvent\.value\.id, 'vorschlag', /)
})

test('DEV-7: Knopfleiste bricht am Handy um', () => {
  assert.match(MODALS, /@media \(max-width: 480px\)/)
  assert.match(MODALS, /\.dk-mod-footer \{ flex-wrap: wrap; row-gap: var\(--sp-2\); \}/)
  // Jeder Knopf behaelt seine Breite — sonst schneidet DkButton das Label ab.
  assert.match(MODALS, /\.dk-mod-footer > \* \{ flex: 0 0 auto; \}/)
})

test('DEV-7: API-Schicht kennt die Aktion festlegen weiterhin', () => {
  assert.match(KANBAN_API, /'ignore'\|'vorschlag'\|'festlegen'\|'ablehnen'/)
})
