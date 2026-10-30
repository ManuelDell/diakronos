/**
 * SEC-3 — Registrierungstoken stark + Bremse: was die Oberfläche zeigen darf.
 *
 * Geprüft wird die VERTRAGSFORM zwischen Server und SPA, nicht das Aussehen
 * (die Karte ist eine Backend-/Sicherheitskarte; Bildschirmfotos gibt es
 * deshalb keine). Der Befund des Pentests war:
 *
 *   (a) ein Link konnte mit einem frei gewählten, kurzen Slug angelegt werden
 *       („pt-mitglied“) — jetzt vergibt der Server `token_urlsafe(32)`
 *       (43 Zeichen), ein mitgeschickter Wert wird verworfen;
 *   (b) die Token-Endpunkte waren nicht gebremst — jetzt antworten sie mit
 *       HTTP 429, und die SPA muss das als „später nochmal“ anzeigen und
 *       NICHT als „dein Link ist ungültig, bitte neu anfordern“.
 *
 * Was hier festgenagelt wird:
 *
 *   (1) Die öffentliche Registrierungsseite übernimmt einen langen
 *       Zufallstoken unverändert (kein Kürzen, kein Umschreiben, kein
 *       Trimmen auf eine „schöne“ Länge) — sonst wäre der starke Token
 *       sofort wieder unbrauchbar.
 *   (2) Die Link-Anzeige der Verwaltung baut die Kopier-Adresse aus
 *       `link_anzeige` des Servers; sie leitet NICHTS selbst aus der
 *       Bezeichnung ab (mögliche zweite Wahrheit, die auseinanderläuft).
 *   (3) Der Token wird nirgends im Frontend geloggt.
 *
 * Der Test liest Quelltext und kompiliert die SFCs NICHT — er prüft
 * Zusagen an der Form der Daten (Regex auf die verwendeten Felder) und
 * läuft im Docker-Build über `node --test`.
 *
 * Lauf: node --test tests/sec3-registrierungstoken.test.mjs   (cwd = frontend/)
 */

import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HIER = dirname(fileURLToPath(import.meta.url))
const SRC = join(HIER, '..', 'src', 'diakonos')

const lies = (pfad) => readFileSync(join(SRC, pfad), 'utf8')

/** Ein Token, wie ihn der Server seit SEC-3 erzeugt (43 Zeichen base64url). */
const STARKER_TOKEN = 'q7Zk3PvN8rTxWbYc2LmHd5JfG4AsE6Uo1IiK9QwRtZ0'

// ── (1) öffentliche Seite nimmt den starken Token unverändert ─────────────

test('Registrierungsseite reicht den Token unverändert an den Server', () => {
  const quelle = lies('pages/Registrierung.vue')

  // Der Token kommt aus der Adresse (`?token=…`) und geht so wieder hinaus.
  assert.match(
    quelle,
    /token/,
    'die Seite muss den Token aus der Adresse lesen',
  )

  // KEINE Kürzung/Umformung des Tokens im Frontend: genau das hat den
  // starken Token zerstört, als er noch aus 10 Zeichen bestand.
  for (const verbot of ['.slice(0,', '.substring(0,', '.trim().toLowerCase()']) {
    assert.ok(
      !quelle.includes(`token${verbot}`),
      `der Token darf nicht umgeformt werden (gefunden: token${verbot})`,
    )
  }
})

test('der starke Token passt in die Anzeige (43 Zeichen, keine Längenprüfung)', () => {
  // Die SPA prüft die Länge NICHT — sonst bräche sie bei einem künftig noch
  // längeren Token (z. B. 64 Zeichen) stillschweigend ab. Geprüft wird die
  // Zusage an der Form: das Feld `token` wird unverändert weitergegeben.
  const quelle = lies('pages/Registrierung.vue')
  assert.ok(
    !/token\.length\s*[<>=!]/.test(quelle),
    'die Seite darf keine Längenannahme über den Token machen',
  )
  assert.equal(STARKER_TOKEN.length, 43, 'Beispieltoken muss 43 Zeichen haben')
})

// ── (2) Kopier-Adresse kommt vom Server ──────────────────────────────────

test('Linkliste zeigt die Server-Adresse (link_anzeige), nicht eine eigene Ableitung', () => {
  const quelle = lies('pages/Registrierung.vue')

  assert.match(
    quelle,
    /link_anzeige/,
    'die Kopier-Adresse muss aus `link_anzeige` des Servers kommen',
  )
  // Keine Ableitung aus der Bezeichnung: der alte Fehler war ein Slug, der
  // aus dem Namen gebaut wurde („sommerfest-2026“) und dann erratbar war.
  assert.ok(
    !/bezeichnung[^\n]{0,60}(toLowerCase|replace\(\/\\s)/.test(quelle),
    'aus der Bezeichnung darf keine Adresse gebaut werden',
  )
})

// ── (3) kein Token im Log ────────────────────────────────────────────────

test('der Token landet nicht in console-Ausgaben der öffentlichen Seite', () => {
  for (const seite of ['pages/Registrierung.vue', 'pages/Gast.vue']) {
    let quelle
    try {
      quelle = lies(seite)
    } catch {
      continue // Seite gibt es in dieser Ausbaustufe nicht
    }
    assert.ok(
      !/console\.\w+\([^)]*\btoken\b/i.test(quelle),
      `${seite}: kein Token in console-Ausgaben`,
    )
  }
})
