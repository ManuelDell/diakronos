import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

/** N7 — Profil beantragt statt sofort zu löschen oder abzumelden.
 *
 *  DSGVO-2b hat den Antrag in einen eigenen Bereich ausgelagert
 *  (`components/mitglieder/LoeschantragKarte.vue` + `composables/useLoeschantrag.js`).
 *  Die Zusagen bleiben dieselben und werden deshalb an den neuen Stellen
 *  geprüft — nicht abgeschwächt: das Ziel (die eigene Person) kommt IMMER aus
 *  der Sitzung, der Antrag wird bestätigt, und es gibt keinen eigenen
 *  fetch-/Session-Weg. */
const lies = (p) => readFileSync(new URL('../src/diakonos/' + p, import.meta.url), 'utf8')
const page = lies('pages/Profile.vue')
const karte = lies('components/mitglieder/LoeschantragKarte.vue')
const api = lies('composables/useLoeschantrag.js')

test('N7: Profil beantragt statt sofort zu löschen oder abzumelden', () => {
  assert.match(api, /datenschutz\.loeschung_beantragen/)
  assert.match(api, /bestaetigt: true/)
  assert.doesNotMatch(page, /profile\.delete_my_data|Unwiderruflich löschen|window.location.href/)
  assert.match(page, /Meine Daten &amp; Datenschutz/)
  assert.match(page, /ohne Konto/)
  // Der Bereich hängt im Profil, nicht in einer eigenen Route.
  assert.match(page, /LoeschantragKarte/)
})

test('N7: Selbstauskunft und Antragsstand über zentrale API, keine Ziel-ID', () => {
  assert.match(page, /datenschutz\.meine_auskunft/)
  assert.match(api, /datenschutz\.mein_loeschantrag/)
  assert.match(page, /import \{ apiCall \} from/)
  // Kein Ziel im Aufruf: die Person kommt aus der Sitzung.
  assert.doesNotMatch(page + api, /mitglied_id:|async function apiFetch/)
  assert.match(page, /createObjectURL/)
  assert.match(page, /revokeObjectURL/)
})

test('N7: Rückfrage, Fehler und bestätigter Antragsstand bleiben sichtbar', () => {
  assert.match(karte, /:close-on-overlay="false"/)
  assert.match(karte, /role="alert"/)
  assert.match(karte, /role="status"/)
  assert.match(page, /dialogFehler\.value = antragFehlerText\(/)
  assert.match(page, /Löschantrag gestellt/)
  assert.doesNotMatch(page + karte, /alert\(|console\.error\(/)
})
