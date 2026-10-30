/**
 * WEB-5b · ZENTRALE HILFSDATEI — Verhalten von `src/shared/basis.js`.
 *
 * Der Wächter (`web5b-praefix.test.mjs`) prüft, DASS niemand mehr Pfade von
 * Hand baut. Diese Datei prüft, dass die eine verbleibende Stelle es richtig
 * tut: MIT Präfix (`/diakonos`), OHNE Präfix (Bestand — Zeichen für Zeichen
 * die alte Adresse), bei verschachtelten Präfixen und ohne Doppel-Präfix.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'

const mod = await import('../src/shared/basis.js')

/** Setzt den Boot-Stand; `null` = kein Boot-Objekt (öffentliche Bundles). */
function bootSetzen(basePath) {
  if (basePath === null) {
    delete globalThis.window
    return
  }
  globalThis.window = { __DIakonosBOOT: { basePath } }
}

test('WEB-5b · ohne Präfix bleibt jede Adresse unverändert', () => {
  for (const leer of [undefined, null, '', '   ', '/']) {
    bootSetzen(leer)
    assert.equal(mod.basisPfad(), '', `basisPfad(${JSON.stringify(leer)})`)
    assert.equal(mod.mitBasis('/api/method/x'), '/api/method/x')
    assert.equal(mod.apiUrl('diakonos.x.y'), '/api/method/diakonos.x.y')
    assert.equal(mod.ressourceUrl('Element/1'), '/api/resource/Element/1')
    assert.equal(mod.dateiUrl('/files/a.png'), '/files/a.png')
    assert.equal(mod.anmeldeUrl('/diakonos#/wiki'), '/login?redirect-to=%2Fdiakonos%23%2Fwiki')
    assert.equal(mod.socketPfad(), '/socket.io')
    assert.equal(mod.healthUrl(), '/healthz')
  }
})

test('WEB-5b · ohne Boot-Objekt (öffentliche Bundles) kein Präfix, kein Absturz', () => {
  bootSetzen(null)
  assert.equal(mod.basisPfad(), '')
  assert.equal(mod.apiUrl('x.y'), '/api/method/x.y')
})

test('WEB-5b · mit Präfix liegt alles unter /diakonos', () => {
  bootSetzen('/diakonos')
  assert.equal(mod.basisPfad(), '/diakonos')
  assert.equal(mod.mitBasis('/api/method/x'), '/diakonos/api/method/x')
  assert.equal(mod.mitBasis('api/method/x'), '/diakonos/api/method/x', 'ohne führenden / ergänzt')
  assert.equal(mod.apiUrl('diakonos.x.y'), '/diakonos/api/method/diakonos.x.y')
  assert.equal(mod.ressourceUrl('Eventkategorie?limit=1'), '/diakonos/api/resource/Eventkategorie?limit=1')
  assert.equal(mod.dateiUrl('/files/a.png'), '/diakonos/files/a.png')
  assert.equal(mod.dateiUrl('/private/files/b.pdf'), '/diakonos/private/files/b.pdf')
  assert.equal(mod.anmeldeUrl('/diakonos#/wiki'), '/diakonos/login?redirect-to=%2Fdiakonos%23%2Fwiki')
  assert.equal(mod.anmeldeUrl(), '/diakonos/login')
  assert.equal(mod.socketPfad(), '/diakonos/socket.io')
  assert.equal(mod.healthUrl(), '/diakonos/healthz')
  assert.equal(mod.mitBasis(''), '/diakonos', 'leerer Pfad = der Präfix selbst')
})

test('WEB-5b · bereits präfigierte Adressen werden NICHT doppelt versehen', () => {
  bootSetzen('/diakonos')
  // Der Server liefert `file_url` und Registrierungslinks schon präfigiert
  // (WEB-5a) — sonst entstünde /diakonos/diakronos/files/…
  assert.equal(mod.dateiUrl('/diakonos/files/a.png'), '/diakonos/files/a.png')
  assert.equal(mod.anmeldeUrl('/diakonos/login'), '/diakonos/login?redirect-to=%2Fdiakonos%2Flogin')
  assert.equal(mod.mitBasis('/diakonos'), '/diakonos')
  assert.equal(mod.mitBasis('/diakonos/api/method/x'), '/diakonos/api/method/x')
})

test('WEB-5b · absolute Adressen bleiben absolut', () => {
  bootSetzen('/diakonos')
  for (const url of ['http://example.org/a.png', 'https://example.org/b', 'data:image/png;base64,AA', 'blob:abc', '//cdn.example.org/x']) {
    assert.equal(mod.dateiUrl(url), url)
  }
})

test('WEB-5b · verschachtelter Präfix und unaufgeräumte Schreibweise', () => {
  bootSetzen('/gemeinde/app')
  assert.equal(mod.apiUrl('x'), '/gemeinde/app/api/method/x')
  // Der Server normalisiert bereits; das Frontend ist trotzdem wehrhaft.
  bootSetzen('gemeinde/app/')
  assert.equal(mod.basisPfad(), '/gemeinde/app')
  assert.equal(mod.socketPfad(), '/gemeinde/app/socket.io')
})

test('WEB-5b · Werte werden bei jedem Aufruf gelesen (Laufzeit-Änderung wirkt)', () => {
  bootSetzen('/diakonos')
  assert.equal(mod.apiUrl('x'), '/diakonos/api/method/x')
  bootSetzen('')
  assert.equal(mod.apiUrl('x'), '/api/method/x')
})
