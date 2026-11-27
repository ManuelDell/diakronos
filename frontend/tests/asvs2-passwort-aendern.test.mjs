// ASVS2-3: eigenes Passwort aendern — Vorpruefung und Formular.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { pruefeEingabe } from '../src/diakonos/components/profil/passwortAendern.mjs'

const lies = (p) => readFileSync(new URL('../src/diakonos/' + p, import.meta.url), 'utf8')

test('ASVS2-3: Vorpruefung nennt den ersten Fehler, sonst leer', () => {
  assert.match(pruefeEingabe('', 'NeuesPasswort-9', 'NeuesPasswort-9'), /aktuelle/)
  assert.match(pruefeEingabe('alt-alt-1', 'kurz', 'kurz'), /8 Zeichen/)
  assert.match(pruefeEingabe('alt-alt-1', 'NeuesPasswort-9', 'NeuesPasswort-8'), /stimmen nicht/)
  assert.match(pruefeEingabe('Gleich-Gleich-1', 'Gleich-Gleich-1', 'Gleich-Gleich-1'), /unterscheiden/)
  assert.equal(pruefeEingabe('alt-alt-1', 'NeuesPasswort-9', 'NeuesPasswort-9'), '')
})

test('ASVS2-3: Formular mit Passwort-Manager-Hinweisen und dem richtigen Aufruf', () => {
  const vue = lies('components/profil/PasswortAendern.vue')
  assert.match(vue, /autocomplete="current-password"/)
  assert.equal((vue.match(/autocomplete="new-password"/g) || []).length, 2)
  assert.match(vue, /type="password"/)
  assert.match(vue, /diakronos\.diakonos\.api\.profile\.passwort_aendern/)
  assert.match(vue, /anmeldeUrl\(undefined, 'passwort'\)/, 'nach dem Wechsel zur Anmeldung mit Hinweis')
  assert.match(vue, /oidc_aktiv === true/, 'bei Authentik nur der Hinweis')
  // Keine Passwoerter in Logs/Konsole
  assert.doesNotMatch(vue, /console\.(log|info|debug)/)
})

test('ASVS2-3: Profilseite bindet die Karte ein', () => {
  const profil = lies('pages/Profile.vue')
  assert.match(profil, /import PasswortAendern from '..\/components\/profil\/PasswortAendern\.vue'/)
  assert.match(profil, /<PasswortAendern \/>/)
})
