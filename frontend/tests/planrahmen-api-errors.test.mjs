import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
// Die einzige Testnaht ersetzt Sitzungs-UI-Reaktivität; apiCall selbst bleibt echt.
const source = readFileSync(new URL('../src/diakonos/composables/useApi.js', import.meta.url), 'utf8')
  .replace("import { useImpersonation } from './useImpersonation.js'", "const useImpersonation = () => ({ isActive: { value: false } })")
  .replace("import { sitzungBeendet } from './useSitzungsablauf.js'",
    "const sitzungBeendet = () => { globalThis.__sitzungBeendet = true }")
  // WEB-8c (R4): der abgelegte Sitzungsfehler (eigene Datei, keine Importe).
  .replace("import { sitzungsFehlerMerken } from './sitzungsstand.js'",
    "const sitzungsFehlerMerken = (f) => f")
  // OP-UI-1 (Rest): gemeinsame Regeln aus shared/sitzung-pruefen.js inline.
  .replace("import { istSitzungsAbbruch } from '../../shared/sitzung-pruefen.js'",
    "const istSitzungsAbbruch = (status, data) => [401, 419].includes(status) || (status === 417 && data?.exc_type === 'CSRFTokenError')")
  // WEB-5b: die Praefix-Hilfsdatei laedt im data:-Modul nicht nach (kein
  // hierarchischer Basispfad). Sie hat keinen eigenen Zustand — ohne Praefix
  // liefert sie genau die alte Adresse; geprueft wird sie in
  // tests/web5b-basis.test.mjs.
  .replace("import { apiUrl } from '../../shared/basis.js'",
    "const apiUrl = (methode) => '/api/method/' + methode")
  // WEB-8b: die CSRF-Heilung liegt in einer eigenen Datei (shared/csrf-heilung.js).
  // Im data:-Modul wird sie inline nachgebildet — hier geht es um die FEHLERFORM
  // von apiCall, nicht um die Heilung; die prueft tests/web8b-csrf-heilung.test.mjs
  // mit dem echten Modul. `datenVon` liest wie in der Vorlage (tolerant).
  .replace("import { istCsrfAblehnung, heileOderMelde, datenVon, SITZUNG_HINWEIS } from '../../shared/csrf-heilung.js'",
    "const istCsrfAblehnung = (res, data) => res?.status === 417 && String(data?.exc_type || '') === 'CSRFTokenError';"
    + " const heileOderMelde = async ({ anfrage }) => { const res = await anfrage(); return { res, data: await datenVon(res) } };"
    + " const SITZUNG_HINWEIS = 'Sitzung abgelaufen — bitte neu anmelden.';"
    + " async function datenVon(res) { if (res?.dkDaten !== undefined) return res.dkDaten; let text = ''; try { text = await res.text() } catch { return { message: `Serverfehler (HTTP ${res?.status})` } } if (!text) return { message: `Serverfehler (HTTP ${res?.status})` }; try { return JSON.parse(text) } catch { return { message: `Serverfehler (HTTP ${res?.status})` } } }")
const { apiCall } = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'))
globalThis.window = { __DIakonosBOOT: { csrf_token: 'test-token' } }

// UXD-R8: Die Antwort wird jetzt als Text gelesen und tolerant geparst
// (vorher blind `res.json()`).
const antwort = (status, koerper) => ({
  ok: status >= 200 && status < 300,
  status,
  text: async () => koerper,
})

const meldungen = [{ pfad: '/wert', code: 'feld.wert', meldung: 'Ungültiger Wert.', hinweis: 'Bitte erneut wählen.' }]
globalThis.fetch = async () => antwort(417, JSON.stringify({ message: 'Prüfung fehlgeschlagen.', meldungen }))
await assert.rejects(apiCall('test'), err => {
  assert.equal(err.status, 417)
  assert.deepEqual(err.meldungen, meldungen)
  assert.equal(err.message, 'Prüfung fehlgeschlagen.')
  return true
})
globalThis.fetch = async () => antwort(403, JSON.stringify({ message: 'Zugriff verweigert.' }))
await assert.rejects(apiCall('test'), err => err.status === 403 && err.meldungen.length === 0)

// UXD-R8: Nicht-JSON (z. B. „Internal Server Error") darf keinen
// JSON-Parse-Fehler werfen, sondern eine lesbare Meldung.
globalThis.fetch = async () => antwort(500, 'Internal Server Error')
await assert.rejects(apiCall('test'), err => {
  assert.equal(err.status, 500)
  assert.match(err.message, /Serverfehler/)
  assert.doesNotMatch(err.message, /JSON/)
  return true
})

globalThis.fetch = async (_url, options) => {
  assert.equal(options.headers['X-Frappe-CSRF-Token'], 'test-token')
  return antwort(200, JSON.stringify({ message: { id: 'test' } }))
}
assert.deepEqual(await apiCall('test'), { id: 'test' })
console.log('API-Fehlerformat: 417, 403, Nicht-JSON (500) und Erfolg bestanden')
