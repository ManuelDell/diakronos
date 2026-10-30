/**
 * SEC-8 — Wächter für den Fehlerklassen-Vertrag zwischen Server und SPA.
 *
 * Die Karte (Pentest R3-A) nimmt den internen Python-Klassennamen aus
 * `exception`/`exc_type` — `DoesNotExistError`, `ValidationError`, `NotFound`,
 * `MethodNotAllowed`, `InternalError` waren über den Status-Code eine Landkarte
 * der Fehlerarten.
 *
 * ABER: Das Feld ist für die SPA kein Schmuck. Drei Werte werden tatsächlich
 * ausgewertet, und wenn einer davon verschwindet, bricht eine Funktion, die
 * niemand sieht, bis es zu spät ist:
 *
 *   - `CSRFTokenError` → `shared/sitzung-pruefen.js:34`: Sitzung neu aufbauen
 *     statt dem Menschen einen Fachfehler zu zeigen.
 *   - `SessionExpired` → 401/419 gelten dort als Sitzungsende.
 *   - `PermissionError` → Rechteanzeige; die Sitzung wird NICHT erneuert.
 *
 * Der Test nagelt beides fest:
 *
 *   (1) Die drei Werte stehen als Allowlist im Backend-Router, und der
 *       generische Wert ist `Error` — gelesen aus dem Quelltext, damit die
 *       Zusage nicht nur in einer Testdatei lebt.
 *   (2) Das Frontend wertet weiter genau diese Werte aus (grep-Äquivalent auf
 *       den Quelldateien): fällt `CSRFTokenError` aus `sitzung-pruefen.js`,
 *       wird der Test rot — egal ob Server oder Client sich ändert.
 *   (3) Kein interner Klassenname steht als angezeigter Text im Frontend.
 *
 * Lauf: node --test tests/sec8-fehlerklassen.test.mjs   (cwd = frontend/)
 */

import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HIER = dirname(fileURLToPath(import.meta.url))
const FRONTEND = join(HIER, '..')
const REPO = join(FRONTEND, '..')

const lies = (...teile) => readFileSync(join(...teile), 'utf8')

/**
 * Im Frontend-Schritt des Images existiert nur `frontend/` (/build) — kein
 * `../backend`. Was hier geprüft wird, muss deshalb INNERHALB von `frontend/`
 * liegen (sonst fehlt der Test im Image und hat nichts bewiesen).
 *
 * Die Backend-Zusagen (Allowlist, generischer Wert) selbst prüft
 * `backend/tests/test_sec8_exception_allowlist.py` als pytest im Image
 * (`COPY backend/tests /app/tests`); hier wird die Kopplung gehalten: die
 * drei Werte, die das Frontend liest, stehen dort wörtlich.
 */
const BACKEND_TEST_KOPIE = join(FRONTEND, 'tests', 'fixtures', 'sec8-allowlist-vertrag.txt')

/** Die drei Werte, auf die das Frontend reagiert (= Vertrag, S1). */
const VERTRAG = ['CSRFTokenError', 'SessionExpired', 'PermissionError']

// ── (1) Der Vertrag selbst: drei Werte, ein generischer Rest ──────────────

/** Liest die Vertragsdatei und trennt Allowlist von generischem Wert. */
function vertragsdatei() {
  const roh = lies(BACKEND_TEST_KOPIE)
  const zeilen = roh.split('\n').map((z) => z.trim())
  const bereich = (marke) => {
    const start = zeilen.indexOf(marke)
    assert.ok(start >= 0, `Abschnitt ${marke} fehlt in ${BACKEND_TEST_KOPIE}`)
    const werte = []
    for (const z of zeilen.slice(start + 1)) {
      if (!z) continue
      if (z.startsWith('#')) break
      werte.push(z)
    }
    return werte
  }
  return {
    allowlist: bereich('# allowlist:').sort(),
    generisch: bereich('# generisch (alles andere):'),
  }
}

test('die Vertragsdatei nennt genau die drei Frontend-Werte als Allowlist', () => {
  const { allowlist } = vertragsdatei()
  assert.deepEqual(allowlist, [...VERTRAG].sort(), `Allowlist ist ${allowlist.join(', ')}`)
})

test('der generische Wert ist "Error", nicht ein Klassenname', () => {
  const { generisch } = vertragsdatei()
  assert.deepEqual(generisch, ['Error'], 'ohne generischen Wert fällt der Router auf den echten Namen zurück')
})

test('kein interner Klassenname steht auf der Allowlist', () => {
  // Die Allowlist darf nicht heimlich um interne Namen wachsen — jeder Wert
  // braucht einen LESER im Frontend (Tests darunter) und eine Quelle im
  // Backend-Test `test_sec8_exception_allowlist.py`.
  const { allowlist } = vertragsdatei()
  for (const name of INTERNE_NAMEN) {
    assert.ok(!allowlist.includes(name), `${name} steht auf der Allowlist — Leck wieder offen`)
  }
})

// ── (2) Das Frontend wertet weiter genau diese Werte aus ───────────────────

test('sitzung-pruefen.js erkennt den CSRF-Ablauf am exc_type', () => {
  const quelle = lies(FRONTEND, 'src', 'shared', 'sitzung-pruefen.js')

  assert.match(
    quelle,
    /exc_type[^\n]*===\s*'CSRFTokenError'/,
    'ohne diese Bedingung baut die SPA die Sitzung bei CSRF-Ablauf nicht neu auf',
  )
  assert.match(quelle, /SITZUNGS_STATUS\s*=\s*\[401,\s*419\]/, '401/419 müssen Sitzungsende bleiben')
})

test('useApi.js prüft jede Fehlerantwort über die gemeinsame Regel', () => {
  const quelle = lies(FRONTEND, 'src', 'diakonos', 'composables', 'useApi.js')

  // Beide Wege (POST `apiCall`, GET `apiGet`) müssen die zentrale Prüfung
  // rufen — sonst gibt es zwei Wahrheiten über „Sitzung abgelaufen".
  const pruefungen = quelle.match(/pruefeSitzungsAntwort\(res, data\)/g) || []
  assert.ok(pruefungen.length >= 2, `erwartet >= 2 Prüfstellen, gefunden ${pruefungen.length}`)
  assert.match(quelle, /from '\.\.\/\.\.\/shared\/sitzung-pruefen\.js'/, 'eine Wahrheit, nicht zwei')
})

// ── (3) Keine Interna als angezeigter Text ────────────────────────────────

/** Interne Klassennamen — dieselbe Liste wie im Backend-Test. */
const INTERNE_NAMEN = [
  'DoesNotExistError',
  'ValidationError',
  'MethodNotAllowed',
  'InternalError',
  'AuthenticationError',
  'RateLimitError',
  'DuplicateEntryError',
  'FrappeCompatError',
  'FrappeError',
  'NotFound',
]

test('kein interner Klassenname steht als Meldung im Frontend', () => {
  const dateien = [
    ['src', 'diakonos', 'composables', 'useApi.js'],
    ['src', 'diakonos', 'composables', 'usePlanrahmen.js'],
    ['src', 'shared', 'sitzung-pruefen.js'],
    ['src', 'gast', 'App.vue'],
  ]

  for (const teile of dateien) {
    const quelle = lies(FRONTEND, ...teile)
    const ohneKommentare = quelle
      .split('\n')
      .filter((z) => !/^\s*(\/\/|\*|\/\*)/.test(z))
      .join('\n')
    for (const name of INTERNE_NAMEN) {
      // Erlaubt ist der Vergleich mit einem Allowlist-Wert; verboten ist der
      // interne Name als FALLBACK- oder Anzeigetext.
      const alsText = new RegExp(`(new Error\\(|fehler\\.value\\s*=|message\\s*[:=]\\s*)['"\`][^'"\`]*${name}`, 'i')
      assert.ok(
        !alsText.test(ohneKommentare),
        `${teile.join('/')}: ${name} steht als angezeigter Text — genau der R3-A-Befund`,
      )
    }
  }
})

test('generische Meldungen bleiben bedienbare Sätze', () => {
  // Die angezeigte Meldung ist der Fachtext des Servers; die generischen
  // Texte des Routers dürfen nicht zu Diagnosezeilen werden.
  for (const meldung of ['Ungueltige Anfrage', 'Methode nicht gefunden', 'Interner Fehler']) {
    assert.ok(meldung.length <= 40, `zu lang für eine Fehlerbox: ${meldung}`)
    assert.ok(!meldung.includes('_'), `Unterstriche verraten Feld-/Modulnamen: ${meldung}`)
  }
})
