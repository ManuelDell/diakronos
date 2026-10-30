/**
 * SEC-7 — Wächter für die Oberfläche: eine generische Fehlerantwort bleibt
 * bedienbar.
 *
 * Die Karte härtet den Method-Router (`backend/src/diakronos_app/frappe_compat/
 * router.py`): Argumentfehler antworten jetzt mit HTTP 417 und der generischen
 * Meldung „Ungueltige Anfrage", unbekannte und unzulässige Methodenpfade mit
 * HTTP 404. Vorher stand dort die Python-Signatur (`submit_registrierung()
 * missing 3 required positional arguments: …`) — ein Leck, aber auch ein Text,
 * den eine Ehrenamtliche nie zu sehen bekommen darf.
 *
 * Geprüft wird deshalb die VERTRAGSFORM zwischen Server und SPA:
 *
 *   (1) `apiCall`/`apiGet` zeigen `data.message` als Meldung an — die kurze
 *       generische Meldung des Servers landet also wörtlich in der
 *       Fehlerbox, ohne Umschreiben zu einer technischen Ersatzmeldung.
 *   (2) Die Meldung ist ein Satz, kein Diagnosetext: keine Signatur, kein
 *       Modulpfad, kein Exception-Klassenname. Der Wächter übernimmt genau
 *       die Begriffe, die der Backend-Test (`tests/test_sec7_method_router.py`)
 *       aus der Antwort verbannt — läuft eine davon je wieder in eine
 *       angezeigte Meldung, ist das ein Befund.
 *   (3) Der Statuscode wird NICHT als Text gezeigt, solange der Server eine
 *       Meldung mitschickt (`Ungueltige Anfrage` statt `HTTP 417`).
 *
 * Der Test liest Quelltext und führt die Meldungsauswahl nicht aus — er
 * nagelt die Zusage an der Form fest und läuft im Docker-Build über
 * `node --test` (siehe `backend/Dockerfile`).
 *
 * Lauf: node --test tests/sec7-fehlertexte.test.mjs   (cwd = frontend/)
 */

import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HIER = dirname(fileURLToPath(import.meta.url))
const SRC = join(HIER, '..', 'src', 'diakonos')

const lies = (pfad) => readFileSync(join(SRC, pfad), 'utf8')

/** Die Meldungen, die der gehärtete Router jetzt liefert (SEC-7/S1+S2). */
const GENERISCH_417 = 'Ungueltige Anfrage'
const GENERISCH_404 = 'Methode nicht gefunden'

/**
 * Begriffe, die in einer ANGEZEIGTEN Meldung nichts zu suchen haben:
 * Python-Signatur, Traceback, Exception-Klassen, Modulpfade. Dieselbe Liste
 * wie im Backend-Test — sie darf hier nicht schrumpfen.
 */
const INTERN = [
  'missing',
  'required positional',
  'positional argument',
  'unexpected keyword',
  'Traceback',
  'diakronos_app',
  'TypeError',
  'ImportError',
  'importlib',
  'relative import',
]

// ── (1) Die generische Meldung wird unverändert angezeigt ──────────────────

test('apiCall zeigt die Servermeldung wörtlich an (kein Umschreiben)', () => {
  const quelle = lies('composables/useApi.js')

  // Der Fehlertext kommt aus `data.message`, danach `data.exception`, erst
  // dann der Status. Genau diese Reihenfolge macht aus „Ungueltige Anfrage"
  // die sichtbare Meldung — und aus dem alten Signaturtext eben jenen Text.
  assert.match(
    quelle,
    /const msg = data\?\.message \|\| data\?\.exception \|\| `HTTP \$\{res\.status\}`/,
    'apiCall muss `message` vor `exception` vor dem Status lesen',
  )
  assert.match(quelle, /const error = new Error\(msg\)/, 'die Meldung geht in den Error')

  // Die generische Meldung darf NICHT durch eine eigene, technischere
  // Ersatzmeldung ersetzt werden (z. B. „Unbekannter Fehler bei …").
  assert.ok(
    !new RegExp(`${GENERISCH_417}\\s*\\?`).test(quelle),
    'die Servermeldung darf nicht durch eine Frontend-Ersatzmeldung ersetzt werden',
  )
})

test('apiGet nutzt dieselbe Meldungsauswahl wie apiCall', () => {
  const quelle = lies('composables/useApi.js')

  // `apiGet` und `apiCall` müssen dieselbe Regel tragen; zwei Wege mit
  // unterschiedlicher Auswahl hiesse: ein Endpunkt zeigt „Ungueltige
  // Anfrage", der andere den Status.
  const treffer = quelle.match(/data\?\.message \|\| data\?\.exception \|\| `HTTP \$\{res\.status\}`/g) || []
  assert.ok(treffer.length >= 2, `erwartet >= 2 identische Auswahlstellen, gefunden ${treffer.length}`)
})

// ── (2) Keine Interna in Meldungen, die angezeigt werden ──────────────────

test('kein Signatur-/Exception-Text steht als angezeigte Meldung im Frontend', () => {
  const dateien = ['composables/useApi.js', 'composables/useSitzungsablauf.js']
  for (const datei of dateien) {
    const quelle = lies(datei)
    // Kommentare erklären die alte Lücke und nennen den Befund — geprüft
    // werden die Zeichenketten, die als Meldung dienen (`new Error(...)`,
    // `message = ...`). Ein Kommentar, der „missing" erklärt, ist harmlos.
    const zeilen = quelle
      .split('\n')
      .filter((z) => !/^\s*(\/\/|\*|\/\*)/.test(z))
      .join('\n')
    for (const wort of INTERN) {
      const alsMeldung = new RegExp(`(new Error\\(|message\\s*[:=]\\s*)[^\n]*${wort}`, 'i')
      assert.ok(
        !alsMeldung.test(zeilen),
        `${datei}: ${wort} steht in einer Meldung — das ist genau der SEC-7-Befund`,
      )
    }
  }
})

test('die generischen Meldungen sind Sätze, keine Diagnosezeilen', () => {
  for (const meldung of [GENERISCH_417, GENERISCH_404]) {
    assert.ok(meldung.length <= 40, `zu lang für eine Fehlerbox: ${meldung}`)
    assert.ok(!/[(){}\[\]]/.test(meldung), `Klammern verraten Code: ${meldung}`)
    assert.ok(!meldung.includes('_'), `Unterstriche sind Modul-/Feldnamen: ${meldung}`)
  }
})

// ── (3) Der Methodenpfad bleibt ein dotted name ───────────────────────────

test('die SPA baut Methodenpfade nur aus dotted names', () => {
  const quelle = lies('composables/useApi.js')

  // `'/api/method/' + method` — die Methode kommt als Konstante aus dem
  // Aufrufer. Der Wächter hält fest, dass hier KEINE Kodierung, kein
  // `encodeURIComponent` und kein Zusammenbau aus Nutzereingaben passiert:
  // der Pfad muss bereits ein gültiger dotted name sein, sonst antwortet
  // der Server jetzt mit 404 „Methode nicht gefunden".
  // WEB-5b: der Pfad entsteht ueber apiUrl() (Betriebs-Praefix). Gleiche
  // Zusicherung: reines Anhaengen des dotted name, keine Kodierung.
  assert.match(quelle, /const url = apiUrl\(method\)/)
  assert.match(readFileSync(new URL('../src/shared/basis.js', import.meta.url), 'utf8'),
    /return mitBasis\('\/api\/method\/' \+ String\(methode \|\| ''\)\)/)
  assert.ok(
    !/api\/method\/.encodeURIComponent/.test(quelle),
    'kein Kodieren des Methodenpfads — das würde die Whitelist nur umgehen wollen',
  )
})
