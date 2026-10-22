import { readFileSync } from 'node:fs'
import { webcrypto } from 'node:crypto'
import { test } from 'node:test'
import assert from 'node:assert/strict'

const lies = p => readFileSync(new URL('../src/diakonos/' + p, import.meta.url), 'utf8')
const dialog = lies('components/mitglieder/MitgliedHinzufuegenDialog.vue')

test('Link als Standard, drei Wege, OIDC ohne lokale Passwortauswahl', () => {
  assert.match(dialog, /const zugangsart = ref\('link'\)/)
  for (const art of ['link', 'startpasswort', 'kein']) assert.ok(dialog.includes(`value="${art}"`))
  assert.match(dialog, /<fieldset v-else class="mh-zugang">/)
  assert.match(dialog, /v-else-if="modus"/)
  assert.match(dialog, /zugangsart: modus.value \? 'kein' : zugangsart.value/)
  assert.match(dialog, /startpasswort: modus.value \|\| zugangsart.value !== 'startpasswort' \? '' : startpasswort.value/)
  assert.match(dialog, /const modus = ref\(null\)/)
  assert.match(dialog, /if \(laeuft.value \|\| modus.value === null\) return/)
})

test('Passwortvorschlag verwendet CSPRNG und bleibt verdeckt', () => {
  const start = dialog.indexOf('function passwortVorschlagen()')
  const ende = dialog.indexOf('\nfunction zuruecksetzen', start)
  const ausfuehren = new Function('crypto', `const startpasswort = { value: '' }; ${dialog.slice(start, ende)}; passwortVorschlagen(); return startpasswort.value`)
  const a = ausfuehren(webcrypto), b = ausfuehren(webcrypto)
  assert.match(a, /^[0-9a-f]{24}$/)
  assert.notEqual(a, b)
  assert.match(dialog, /const passwortSichtbar = ref\(false\)/)
  assert.match(dialog, /:type="passwortSichtbar \? 'text' : 'password'"/)
  assert.match(dialog, /startpasswort.value = ''\n    emit\('angelegt'/)
})

test('Felder besitzen gebundene Label-IDs, Fehler bleiben im Dialog', () => {
  assert.ok((dialog.match(/:id="feld.id"/g) || []).length >= 4)
  assert.ok((dialog.match(/v-slot="feld"/g) || []).length >= 4)
  assert.match(dialog, /:close-on-overlay="false"/)
  assert.match(dialog, /fehler.allgemein = err\?\.message/)
})

test('Mitglied-Detail lädt bei auslaufendem Routenwechsel keine leere Kennung', async () => {
  const text = lies('pages/MitgliedDetail.vue')
  const start = text.indexOf('async function loadMitglied()')
  // OP-ADMIN-12 hat `startImpersonation` entfernt (der Knopf tat nichts) —
  // die Grenze ist jetzt die naechste Funktion, die es sicher gibt.
  const ende = text.indexOf('\nfunction startEdit', start)
  let anfragen = 0, meldungen = 0
  const ausfuehren = new Function('apiCall', 'console', `
    const loading = { value: true }, error = { value: null }, mitglied = { value: null }, dsgvo = {}
    const mitgliedId = { value: '' }
    const getRouteParam = () => undefined
    const _fillEditForm = () => {}
    ${text.slice(start, ende)}
    return loadMitglied()
  `)
  await ausfuehren(async () => { anfragen++; return {} }, { error: () => { meldungen++ } })
  assert.equal(anfragen, 0)
  assert.equal(meldungen, 0)
})

test('Ergebnis und Zugangskarte benutzen denselben vertraulichen lokalen QR-Teiler', () => {
  const ergebnis = lies('components/mitglieder/PasswortLink.vue')
  const karte = lies('components/ZugangKarte.vue')
  assert.match(ergebnis, /<RegLinkTeilen[^>]+vertraulich/)
  assert.match(ergebnis, /keine E-Mail versendet/)
  assert.match(karte, /Passwort-Link neu erzeugen/)
  assert.match(karte, /v-if="!oidcAnmeldung" label="Startpasswort setzen"/)
  assert.match(karte, /oidcAnmeldung.value = daten.oidc_aktiv === true/)
  assert.match(karte, /<PasswortLink/)
})
