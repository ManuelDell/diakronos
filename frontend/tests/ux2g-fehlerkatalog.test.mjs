/**
 * UX2g — Wächter für den Fehlerkatalog.
 *
 * BEFUND (Manuel, Dev-Modus): Fehlerflächen zeigten „Unbekannter Fehler",
 * „Fehler beim Speichern", „Ein Fehler ist aufgetreten" — oder technische
 * Codes wie „HTTP 500". Eine Ehrenamtliche kann damit nichts anfangen: die
 * Meldung sagt nicht, was passiert ist, warum, und was jetzt hilft.
 *
 * Die Karte führt EINEN Katalog ein (`src/shared/fehlertexte.js`) und
 * ersetzt damit jede dieser Floskeln in der Oberfläche. Dieser Test hält
 * beide Hälften fest:
 *
 *   (1) VERHALTEN — der Katalog liefert für jede Fehlerlage einen Satz nach
 *       dem Muster „was ist passiert · was jetzt hilft", ohne Jargon, ohne
 *       Zahlen-Code. Fachliche Servermeldungen gehen wörtlich durch.
 *   (2) BESTAND  — keine Floskel steht mehr als ANGEZEIGTE Meldung im
 *       Quelltext. Der Test liest die Quellen, weil eine Floskel als
 *       Literal in einem `showToast(… || 'Unbekannter Fehler')` sitzt und
 *       nur so zuverlässig zu finden ist.
 *
 * Lauf: node --test tests/ux2g-fehlerkatalog.test.mjs   (cwd = frontend/)
 */

import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join, relative } from 'node:path'

import {
  FEHLERTEXTE,
  FLOKSEN,
  ZUSTAENDE,
  aktionsfehler,
  fehlerkurz,
  fehlertext,
  istFloskel,
  katalogText,
  servertextBrauchbar,
  wirktTechnisch,
  zustandFuer,
} from '../src/shared/fehlertexte.js'

const HIER = dirname(fileURLToPath(import.meta.url))
const SRC = join(HIER, '..', 'src')

// ── (1) Verhalten: die Einstufung nach exc_type / HTTP-Status ──────────────

test('UX2g: jeder Zustand hat einen vollständigen Satz (was + jetzt)', () => {
  for (const zustand of ZUSTAENDE) {
    const eintrag = FEHLERTEXTE[zustand]
    assert.ok(eintrag, `Zustand fehlt im Katalog: ${zustand}`)
    assert.ok(eintrag.was && eintrag.was.length > 8, `${zustand}: „was" fehlt`)
    assert.ok(eintrag.jetzt && eintrag.jetzt.length > 8, `${zustand}: „jetzt" fehlt`)
    const satz = katalogText(zustand)
    assert.match(satz, /[.!?]$/, `${zustand}: kein ganzer Satz: ${satz}`)
    // I4: kein Jargon, kein Code, keine Zahl-Kennung in der Meldung.
    assert.doesNotMatch(satz, /\b(HTTP|Status|Exception|Error|null|undefined)\b/i,
      `${zustand}: Jargon in der Meldung: ${satz}`)
    assert.doesNotMatch(satz, /\b[1-5]\d\d\b/, `${zustand}: Statuscode in der Meldung: ${satz}`)
  }
})

test('UX2g: die Lage wird aus Status und exc_type eingestuft', () => {
  const faelle = [
    [{ status: 401 }, 'sitzung'],
    [{ status: 419 }, 'sitzung'],
    [{ excType: 'CSRFTokenError' }, 'sitzung'],
    [{ status: 403 }, 'rechte'],
    [{ status: 404 }, 'weg'],
    [{ status: 409 }, 'konflikt'],
    [{ status: 412 }, 'konflikt'],
    [{ status: 400 }, 'eingabe'],
    [{ status: 417 }, 'eingabe'],
    [{ status: 422 }, 'eingabe'],
    [{ status: 429 }, 'ueberlastet'],
    [{ status: 500 }, 'server'],
    [{ status: 503 }, 'server'],
  ]
  for (const [lage, erwartet] of faelle) {
    assert.equal(zustandFuer(lage), erwartet, `${JSON.stringify(lage)} -> ${erwartet}`)
  }
  // Kein Status = keine Antwort. Mit `angefragt` (die Anfrage ist
  // gescheitert) ist das „Verbindung weg"; ohne jede Lage nicht.
  assert.equal(zustandFuer({}), 'unbekannt')
  assert.equal(zustandFuer({ status: 0 }), 'unbekannt')
  assert.equal(zustandFuer({ status: 0, angefragt: true }), 'netz')
  assert.equal(zustandFuer({ excType: 'TypeError' }), 'netz')
})

test('UX2g: ein fachlicher Servertext geht wörtlich durch, Floskeln nicht', () => {
  const fachlich = 'Das Ende muss nach dem Beginn liegen.'
  assert.equal(fehlertext({ message: fachlich, status: 417 }), fachlich,
    'die deutsche Fachmeldung des Servers muss stehen bleiben')

  // Die alten Floskeln sind keine Auskunft -> Katalogtext.
  for (const floskel of ['Unbekannter Fehler', 'Fehler', 'API-Fehler', 'Ein Fehler ist aufgetreten']) {
    const text = fehlertext({ message: floskel, status: 500 })
    assert.equal(text, katalogText('server'), `„${floskel}" darf nicht angezeigt werden`)
  }

  // Technische Innereien werden nicht durchgereicht.
  for (const innen of ['HTTP 500', 'diakronos_app.api.x', 'TypeError: bad', 'Traceback (most recent call last)']) {
    assert.ok(wirktTechnisch(innen), `als technisch erkannt: ${innen}`)
    const text = fehlertext({ message: innen, status: 500 })
    assert.equal(text, katalogText('server'), `„${innen}" darf nicht angezeigt werden`)
  }
})

test('UX2g: eine Aktion nennt die Handlung, wenn die Lage unklar ist', () => {
  // Unklare Lage (kein Status, kein exc_type) -> neutral „Das hat nicht geklappt".
  const neutral = aktionsfehler('speichern', {})
  assert.match(neutral, /^Das Speichern hat nicht geklappt\./, neutral)
  assert.match(neutral, /versuche/i, neutral)

  // Klare Lage schlägt den Rahmen: ein 500 ist ein Serverausfall, kein
  // „Speichern"-Problem.
  const server = aktionsfehler('speichern', { status: 500 })
  assert.equal(server, katalogText('server'), 'ein 500 ist kein Speicherproblem')

  // Fachtext geht auch hier vor.
  const fachlich = 'Der Termin liegt außerhalb des Planungszeitraums.'
  assert.equal(aktionsfehler('speichern', { message: fachlich, status: 417 }), fachlich)
})

test('UX2g: fehlerkurz liefert nur „was ist passiert"', () => {
  assert.equal(fehlerkurz({ status: 403 }), FEHLERTEXTE.rechte.was)
  assert.equal(fehlerkurz({ status: 0, angefragt: true }), FEHLERTEXTE.netz.was)
  // Ein brauchbarer Fachsatz bleibt ganz (er ist schon ein Satz).
  const fachlich = 'Das Ende muss nach dem Beginn liegen.'
  assert.equal(fehlerkurz({ message: fachlich, status: 417 }), fachlich)
})

test('UX2g: Floskel-Erkennung deckt die alten Meldungen', () => {
  for (const alt of ['Unbekannter Fehler', 'Unbekannter Fehler.', 'Fehler', 'Ein Fehler ist aufgetreten.',
    'Fehler beim Speichern', 'Ungueltige Anfrage', 'Interner Fehler']) {
    assert.ok(istFloskel(alt), `als Floskel erkannt: ${alt}`)
  }
  assert.ok(!istFloskel('Das Ende muss nach dem Beginn liegen.'), 'Fachsatz ist keine Floskel')
})

test('UX2g: Browser-Meldungen (fetch) sind keine Auskunft', () => {
  // UX2g-Befund aus der Abnahme: bei Netzausfall stand „Failed to fetch" als
  // angezeigte Meldung — englisch, technisch, nichtssagend.
  for (const roh of ['Failed to fetch', 'TypeError: Failed to fetch', 'Load failed',
    'NetworkError when attempting to fetch resource.']) {
    assert.ok(wirktTechnisch(roh), `als technisch erkannt: ${roh}`)
    const err = Object.assign(new Error(roh), { name: 'TypeError' })
    assert.equal(fehlertext(err), katalogText('netz'), `„${roh}" darf nicht angezeigt werden`)
  }
})

// ── (2) Bestand: keine Floskel mehr als angezeigte Meldung ─────────────────

/** Alle Vue/JS-Quellen unter `src/` (ohne die Katalogdatei selbst). */
function quelldateien(wurzel) {
  const ergebnis = []
  const lauf = (pfad) => {
    for (const eintrag of readdirSync(pfad)) {
      const voll = join(pfad, eintrag)
      if (statSync(voll).isDirectory()) { lauf(voll); continue }
      if (!/\.(vue|js|mjs)$/.test(eintrag)) continue
      if (voll.endsWith(join('shared', 'fehlertexte.js'))) continue
      if (/\.test\.mjs$/.test(eintrag)) continue
      ergebnis.push(voll)
    }
  }
  lauf(wurzel)
  return ergebnis
}

/**
 * Kommentare und Entwickler-Protokolle entfernen, damit ein ERKLÄRENDER Satz
 * („ersetzt „Fehler beim Speichern"") oder `console.error('Fehler beim …')`
 * nicht als Befund zählt. `console.*` sieht nur die Entwicklerkonsole, nie
 * eine Person in der Oberfläche — die Karte meint ANGEZEIGTE Meldungen.
 */
function ohneKommentare(quelle) {
  return quelle
    .replace(/\/\*[\s\S]*?\*\//g, '')     // Blockkommentar
    .replace(/<!--[\s\S]*?-->/g, '')      // HTML-Kommentar im Template
    .split('\n')
    .filter((zeile) => !/^\s*(\/\/|\*)/.test(zeile))
    .filter((zeile) => !/console\.(error|warn|log|debug|info)\s*\(/.test(zeile))
    .join('\n')
}

/** Die Floskeln, die als Meldung nirgends mehr stehen dürfen. */
const VERBOTEN = [
  'Unbekannter Fehler',
  'Ein Fehler ist aufgetreten',
  'Fehler beim Speichern',
  'Fehler beim Erstellen',
  'Fehler beim Laden',
  'Fehler beim Entfernen',
  'Fehler beim Löschen',
  'Fehler beim Anlegen',
  'API-Fehler',
]

test('UX2g: keine Floskel steht mehr als Meldung in der Oberfläche', () => {
  const befunde = []
  for (const datei of quelldateien(SRC)) {
    const code = ohneKommentare(readFileSync(datei, 'utf8'))
    for (const floskel of VERBOTEN) {
      if (code.includes(floskel)) {
        befunde.push(`${relative(SRC, datei)}: „${floskel}"`)
      }
    }
  }
  assert.deepEqual(befunde, [],
    'diese Floskeln müssen durch den Fehlerkatalog ersetzt werden (src/shared/fehlertexte.js)')
})

test('UX2g: der Katalog wird an den zentralen Stellen benutzt', () => {
  // Der Toast ist die häufigste Fehlerfläche — er darf leer/Floskel nicht
  // mehr auf einen eigenen Satz abbilden, sondern fragt den Katalog.
  const toast = readFileSync(join(SRC, 'diakonos', 'composables', 'useToast.js'), 'utf8')
  assert.match(toast, /from '\.\.\/\.\.\/shared\/fehlertexte\.js'/,
    'useToast muss den Katalog importieren')

  // Die zentrale API-Schicht (apiCall/apiGet) hängt Status und exc_type an
  // den Fehler — daraus stuft der Katalog ein.
  const api = readFileSync(join(SRC, 'diakonos', 'composables', 'useApi.js'), 'utf8')
  assert.match(api, /\berror\.status\s*=\s*res\.status/, 'apiCall hängt den Status an den Fehler')
  assert.match(api, /\berror\.exc_type\s*=/, 'apiCall hängt exc_type an den Fehler (Katalog-Einstufung)')

  // FLOKSEN und VERBOTEN dürfen nicht auseinanderlaufen: die Liste, gegen die
  // der Katalog prüft, enthält jede verbotene Floskel.
  for (const floskel of VERBOTEN) {
    assert.ok(FLOKSEN.includes(floskel.toLowerCase()),
      `FLOKSEN im Katalog muss „${floskel}" enthalten`)
  }
})

test('UX2g: der Katalog selbst nennt keine Floskel als Meldung', () => {
  // Gegenprobe: die Datei darf die Wörter nur in Kommentaren/der FLOKSEN-
  // Liste führen, nicht als angezeigten Satz.
  for (const zustand of ZUSTAENDE) {
    const satz = katalogText(zustand)
    for (const floskel of VERBOTEN) {
      assert.ok(!satz.toLowerCase().includes(floskel.toLowerCase()),
        `${zustand}: Katalogtext enthält die Floskel „${floskel}": ${satz}`)
    }
  }
  // „Fehler" allein ist als Wort erlaubt („Der Server …"), aber nie als
  // ganzer Text.
  assert.ok(!servertextBrauchbar('Fehler'), '„Fehler" allein ist keine Meldung')
})
