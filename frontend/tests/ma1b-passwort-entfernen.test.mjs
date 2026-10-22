/**
 * MAIL-1b (N4): Knopf „Gespeichertes Passwort entfernen“.
 *
 * R-MAIL-1/N4: `passwort_entfernen` gab es nur in der API, nicht in der
 * Oberflaeche. Wer auf „keine Verschlüsselung“ oder einen Server ohne Anmeldung
 * umstellen wollte, bekam dauerhaft „Bitte das Passwort entfernen“
 * (`smtp_einstellungen.py`) — ohne Bedienmoeglichkeit.
 *
 * Geprueft wird hier am Quelltext, weil die Seite keinen Test-Runner mit
 * Vue-Mounting hat (wie in `ma1-mailversand.test.mjs`):
 *
 * 1. Das Composable hat `passwortEntfernenAnfrage` (kein `confirm()`) und
 *    schickt `passwort_entfernen: true` an genau den Speicher-Endpunkt.
 * 2. Die Seite fragt vorher in einem eigenen Dialog (DkDialog/DkBestaetigung)
 *    nach und nennt die Folge („keine Anmeldung mehr“).
 * 3. Der Aufruf steht nur dort, wo ein Passwort hinterlegt ist.
 * 4. Der Server kennt den Schalter schon (`mailversand_speichern`) — hier
 *    zusaetzlich abgesichert, damit die Oberflaeche nicht ins Leere greift.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const lies = (pfad) => readFileSync(new URL('../src/diakonos/' + pfad, import.meta.url), 'utf8')

/** Quelltext ohne Kommentare — Aussagen ueber „es gibt kein X“ stehen dort. */
const liesCode = (pfad) => {
  const roh = lies(pfad)
  const ohneBloecke = roh.replace(/<!--[\s\S]*?-->/g, '').replace(/\/\*[\s\S]*?\*\//g, '')
  return ohneBloecke.replace(/^\s*\/\/.*$/gm, '')
}

const COMPOSABLE = 'composables/useMailversand.js'
const SEITE = 'pages/einstellungen/Mailversand.vue'

// ── 1. Composable ─────────────────────────────────────────────────────────

test('MAIL-1b: das Composable bietet „Passwort entfernen“ an', () => {
  const quelle = liesCode(COMPOSABLE)
  assert.ok(quelle.includes('passwortEntfernen'), 'eigener Zustand fuer den Dialog')
  assert.ok(quelle.includes('passwortEntfernenBestaetigen'),
    'die bestaetigte Aktion ist eine eigene Funktion')
  assert.ok(quelle.includes('passwort_entfernen: true'),
    'der Schalter der API wird gesetzt')
})

test('MAIL-1b: „Passwort entfernen“ geht an den Speicher-Endpunkt', () => {
  const quelle = liesCode(COMPOSABLE)
  const block = quelle.slice(quelle.indexOf('async function passwortEntfernenBestaetigen'))
  assert.ok(block.includes("API + 'mailversand_speichern'"),
    'derselbe Endpunkt wie Speichern (kein vierter Weg)')
  const namen = [...quelle.matchAll(/apiCall\(API \+ '([a-z_]+)'/g)].map(m => m[1]).sort()
  assert.deepEqual([...new Set(namen)],
    ['mailversand_get', 'mailversand_speichern', 'mailversand_testmail'])
})

test('MAIL-1b: nach dem Entfernen ist „gesetzt“ falsch und das Feld leer', () => {
  const quelle = liesCode(COMPOSABLE)
  const block = quelle.slice(quelle.indexOf('async function passwortEntfernenBestaetigen'))
  assert.ok(block.includes('uebernehmen('), 'der Serverstand wird uebernommen')
  assert.ok(block.includes("passwort.value = ''"), 'kein Rest im Eingabefeld')
})

test('MAIL-1b: ein frisch eingetipptes Passwort wird nicht mit „entfernen“ verworfen', () => {
  // Befund aus der Abnahme (Browser-Probe im Wegwerf-Stack): Der Server lehnt
  // `passwort` + `passwort_entfernen` zu Recht ab. Die Oberflaeche schickte
  // beides zusammen und bekam 417 „Für die Anmeldung fehlt das Passwort“ —
  // ein eingetipptes Passwort darf aber nicht stillschweigend geloescht werden.
  const quelle = liesCode(COMPOSABLE)
  const block = quelle.slice(quelle.indexOf('async function passwortEntfernenBestaetigen'),
    quelle.indexOf('return {', quelle.indexOf('async function passwortEntfernenBestaetigen')))
  assert.ok(block.includes('let rumpf'), 'der Rumpf wird vor dem Absenden gebaut')
  assert.ok(/if \(passwort\.value\) \{\s*rumpf\.passwort_entfernen = false/.test(block),
    'mit eingetipptem Passwort geht der Loesch-Schalter nicht mit')
  assert.ok(block.includes('passwort: passwort.value'),
    'und das eingetippte Passwort geht mit')
})

test('MAIL-1b: die Formularpruefung kennt den offenen Loeschauftrag', () => {
  // Ohne das hier meldet `pruefeFormular` „Für die Anmeldung fehlt das
  // Passwort“, obwohl der Benutzer gerade das Entfernen bestaetigt hat.
  const quelle = liesCode(COMPOSABLE)
  const block = quelle.slice(quelle.indexOf('function pruefeFormular'),
    quelle.indexOf('function alsRumpf'))
  assert.ok(block.includes('!passwortEntfernen.value'),
    'ein offener Loeschauftrag zaehlt als „kein Passwort noetig“')
})

// ── 2. Seite ──────────────────────────────────────────────────────────────

test('MAIL-1b: der Knopf steht bei der Anmeldung und nur mit hinterlegtem Passwort', () => {
  const seite = liesCode(SEITE)
  assert.ok(seite.includes('Gespeichertes Passwort entfernen'), 'Wortlaut des Knopfes')
  assert.ok(/v-if="passwortGesetzt"/.test(seite), 'nur wenn eines hinterlegt ist')
})

test('MAIL-1b: der Dialog fragt nach (kein confirm())', () => {
  const seite = liesCode(SEITE)
  assert.ok(seite.includes('DkDialog'), 'eigener Dialog wie in Datenschutz.vue')
  assert.ok(seite.includes('passwortEntfernenOeffnen'), 'der Knopf oeffnet den Dialog')
  assert.ok(!seite.includes('confirm('), 'kein Browser-confirm')
  assert.ok(seite.includes('nicht mehr angemeldet'),
    'der Dialog nennt die Folge: ohne Passwort keine Anmeldung')
  assert.ok(seite.includes('lässt sich nicht'),
    'und dass das Passwort danach neu eingetippt werden muss')
  assert.ok(seite.includes('neu eintippen'))
})
