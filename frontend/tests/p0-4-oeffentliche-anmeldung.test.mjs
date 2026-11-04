/**
 * P0-4 — Oeffentliche Anmeldung/Registrierung lauffaehig (Frontend-Teil).
 *
 * Geprueft werden die Befunde, die im Frontend liegen:
 *
 *   UXD-R27  Die öffentliche Seite zeigt Serverfehler nie an. `parseServerError`
 *            las nur die Frappe-Schreibweise `_server_messages`; die Compat-
 *            Schicht antwortet aber mit `{"message": …}` (router.py
 *            `_error_response`).
 *
 *   UXD-R3   Der kopierte Registrierungslink war ein relativer Pfad
 *            (`/registrierung?token=…`) und lief in einen 404. `copyLink`
 *            bildet jetzt eine vollständige Adresse.
 *
 *   UXM-R18  Die Seite „Anmeldung“ war ein Freitextfeld für Rollen, halbfertige
 *            Zeilen wurden beim Speichern still verworfen. Die alte Seite ist
 *            mit N12 entfallen; die gleichwertige Prüfung liegt jetzt in
 *            `einstellungen/Anmeldung.vue` (siehe n8-anmeldung.test.mjs).
 *
 * Der Test kompiliert die SFCs echt (kein RegEx-Raten am Quelltext) und
 * fuehrt die Funktionen in einer kleinen Sandbox aus. Laeuft im Docker-Build
 * ueber `node --test`.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript } from 'vue/compiler-sfc'
// UX2g: der Ersatztext ohne Servermeldung kommt aus dem Fehlerkatalog.
import { katalogText, fehlertext } from '../src/shared/fehlertexte.js'

const wurzel = new URL('../src/', import.meta.url)
const lesen = (rel) => readFileSync(new URL(rel, wurzel), 'utf8')

// ── UXD-R27: die Public-Apps zeigen den Serverfehlertext ────────────────────
// REG-1b: Das Anmeldeformular der Registrierung ist in die gemeinsame
// Komponente `registrierung/components/DkAnmeldeformular.vue` gewandert (sie
// zeigt auch die Vorschau im Editor). `parseServerError` steht deshalb dort —
// geprueft wird weiterhin, dass genau EINE Umsetzung existiert und App.vue
// keine zweite Kopie fuehrt.

for (const rel of ['registrierung/components/DkAnmeldeformular.vue', 'gast/App.vue']) {
  const quelle = lesen(rel)
  const { descriptor, errors } = parse(quelle, { filename: rel })
  assert.deepEqual(errors, [], rel + ': SFC-Struktur')
  compileScript(descriptor, { id: rel })

  const skript = descriptor.scriptSetup.content
  const treffer = skript.match(/function parseServerError\s*\(data\)\s*\{[\s\S]*?\n\}/)
  assert.ok(treffer, rel + ': parseServerError gefunden')
  const koerper = treffer[0]
  assert.match(koerper, /data\.message/, rel + ': verwertet data.message')
  // `_server_messages` steht nur noch als Rueckfall (Altbestand) hinter der
  // `message`-Pruefung; ein Kommentar darf davor stehen.
  const codeOhneKommentare = koerper.replace(/\/\/[^\n]*/g, '')
  assert.ok(
    codeOhneKommentare.indexOf('data.message') < codeOhneKommentare.indexOf('_server_messages'),
    rel + ': message wird vor der Altform geprueft',
  )

  // Die Funktion selbst muss die richtige Meldung liefern.
  // UX2g: `fehlertext` wird hereingereicht — der Körper allein kennt den
  // Katalog-Import der Komponente nicht.
  const fn = new Function('fehlertext', `${koerper}; return parseServerError`)
  const ausgeben = fn((...a) => fehlertext(...a))
  assert.equal(ausgeben({ message: 'Ungültiger oder deaktivierter Registrierungslink.' }),
    'Ungültiger oder deaktivierter Registrierungslink.', rel)
  assert.equal(ausgeben({ message: '', _server_messages: JSON.stringify([JSON.stringify({ message: 'Alt' })]) }),
    'Alt', rel + ': Altform bleibt nutzbar')
  // UX2g: ohne Servermeldung nennt der Fehlerkatalog, was passiert ist und
  // was jetzt hilft — statt der Floskel „Ein Fehler ist aufgetreten".
  const leer = ausgeben({})
  assert.equal(leer, katalogText('unbekannt'), rel)
  assert.match(leer, /versuche|lade|melde/i, rel + ': nennt einen nächsten Schritt')
}

// Keine zweite Umsetzung: die Seite selbst reicht nur durch.
{
  const seite = parse(lesen('registrierung/App.vue'), { filename: 'registrierung/App.vue' })
  assert.ok(
    !/function parseServerError/.test(seite.descriptor.scriptSetup.content),
    'registrierung/App.vue: zweite Kopie von parseServerError',
  )
}

// ── UXD-R3: kopierter Link ist eine vollstaendige Adresse ───────────────────

{
  const quelle = lesen('diakonos/pages/Registrierung.vue')
  const { descriptor, errors } = parse(quelle, { filename: 'Registrierung.vue' })
  assert.deepEqual(errors, [], 'Registrierung.vue: SFC-Struktur')
  const skript = descriptor.scriptSetup.content
  const treffer = skript.match(/function copyLink\(url\)\s*\{[\s\S]*?\n\}/)
  assert.ok(treffer, 'copyLink gefunden')
  assert.match(treffer[0], /new URL\(url, window\.location\.origin\)\.href/,
    'copyLink bildet eine absolute Adresse')

  // Verhalten: aus dem relativen Pfad wird die vollstaendige Adresse.
  let kopiert = null
  const copy = new Function(
    'window', 'navigator', 'showToast',
    `${treffer[0]}; return copyLink;`,
  )(
    { location: { origin: 'https://gemeinde.example' } },
    { clipboard: { writeText: (t) => { kopiert = t; return Promise.resolve() } } },
    () => {},
  )
  copy('/diakonos/registrierung?token=abc')
  assert.equal(kopiert, 'https://gemeinde.example/diakonos/registrierung?token=abc',
    'copyLink-Ausgabe')
}

// ── UXM-R18: die alte Seite „Anmeldung“ ist mit N12 entfallen ───────────────
// Ihre Prüfungen (Rolle als Auswahl, keine stillen Zeilen) führt jetzt
// `einstellungen/Anmeldung.vue` weiter; das deckt `n8-anmeldung.test.mjs` ab.

console.log('P0-4 Frontend: Serverfehler werden angezeigt, Link ist absolut')

