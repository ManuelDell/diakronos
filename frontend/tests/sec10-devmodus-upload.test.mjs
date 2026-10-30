/**
 * SEC-10 — Wächter: Dev-Modus-Uploads nutzen den Inhalt, nicht die Endung.
 *
 * Der Backend-Beweis läuft in pytest (backend/tests/test_sec10_*). Hier wird
 * die Client-Seite eingefroren: der Dialog schickt den vom MediaRecorder
 * gemeldeten MIME-Typ mit (das Backend verlangt Übereinstimmung mit dem
 * Inhalt) und liest aus der Bericht-Antwort nur den RELATIVEN Schlüssel
 * `bericht` — nie einen absoluten Server-Pfad.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const hier = dirname(fileURLToPath(import.meta.url))
const quelle = join(hier, '..', 'src', 'diakonos')
const repo = join(hier, '..', '..')

function lies(pfad) {
  return readFileSync(join(quelle, pfad), 'utf8')
}

function backend(pfad) {
  return readFileSync(join(repo, 'backend', 'src', 'diakronos_app', 'devmodus', pfad), 'utf8')
}

test('Aufnahme meldet den MediaRecorder-Typ (nicht "audio/webm" geraten)', () => {
  const text = lies('components/devmodus/sprache.mjs')
  assert.match(text, /MediaRecorder\.isTypeSupported/)
  assert.match(text, /\{ blob: new Blob\([^)]*\)[^}]*typ:/s,
    'stoppen() liefert blob UND typ')
  const dialog = lies('components/devmodus/BefundDialog.vue')
  assert.match(dialog, /audioHochladen\(datenUrl, typ\)/,
    'der erkannte Typ geht mit zum Server')
})

test('Bericht-Aufrufer liest nur den relativen Schlüssel', () => {
  const text = lies('pages/devmodus/Befunde.vue')
  const zeile = text.split('\n').find(z => z.includes('berichtErzeugen'))
  assert.ok(zeile, 'berichtErzeugen wird aufgerufen')
  assert.match(text, /antwort\?\.bericht/,
    'die Anzeige nimmt `bericht` (relativ), nicht `pfad`')
  assert.doesNotMatch(text, /antwort\?\.pfad|antwort\.pfad/,
    'kein absoluter Server-Pfad im Frontend')
})

test('Bericht-Endpunkt liefert keinen absoluten Pfad mehr', () => {
  const bericht = backend('bericht.py')
  const block = bericht.slice(bericht.indexOf('def erzeugen'))
  const rueck = block.slice(block.indexOf('return {'), block.indexOf('}', block.indexOf('return {')))
  assert.doesNotMatch(rueck, /"pfad":\s*str\(/,
    'kein `pfad` mit absolutem Pfad in erzeugen()')
  assert.match(rueck, /"bericht":\s*str\(md_pfad\.relative_to/)
})

test('Audio-Upload prüft Inhalt und Größe (Magic-Bytes statt Typfeld)', () => {
  const dienste = backend('dienste.py')
  const block = dienste.slice(dienste.indexOf('def audio_speichern'))
  const ende = block.indexOf('\ndef aus_base64')
  const rumpf = block.slice(0, ende)
  assert.match(rumpf, /audio_erkennen\(rohdaten\)/, 'Inhalt wird erkannt')
  assert.match(rumpf, /if not rohdaten/, 'leere Daten werden abgelehnt')
  assert.match(rumpf, /max_audio_bytes\(\)/, 'Größenlimit aus der Einstellung')
  assert.match(rumpf, /pass nicht zum angegebenen Typ|passt nicht zum angegebenen Typ/,
    'Widerspruch Inhalt/Typ wird abgelehnt')
  const erkennen = dienste.slice(dienste.indexOf('def audio_erkennen'),
    dienste.indexOf('def audio_speichern'))
  assert.match(erkennen, /\\x1a\\x45\\xdf\\xa3/, 'WebM/EBML-Signatur')
  assert.match(erkennen, /OggS/, 'OGG-Signatur')
  assert.match(erkennen, /ftyp/, 'M4A/MP4-Signatur an Offset 4')
})
