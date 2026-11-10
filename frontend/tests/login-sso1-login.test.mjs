/**
 * LOGIN-SSO1 — Wächter: Formular UND SSO-Knopf, Trenner „oder“ dazwischen.
 *
 * Die Karte ändert SERVER-Verhalten (`/login` mit `AUTH_LOCAL_LOGIN=an` leitet
 * NICHT mehr weiter, sondern zeigt beide Wege). Gegen HTTP geprüft wird das in
 * `backend/tests/test_login_sso1.py` (rot → grün nachgewiesen). Hier steht der
 * Wächter, der die Regel in der QUELLE hält — damit sie in einem späteren Umbau
 * nicht still verschwindet (dann fiele der Befund zurück: „SSO schaltet den
 * lokalen Login aus“).
 *
 * Geprüft wird:
 *   1. `routen.py`: Die Weiterleitung hängt an `_lokal_login_an()`; die
 *      Anmeldeschicht kennt den Modus `an` und den ausdrücklichen Start
 *      (`sso=1`) VOR der 503-Auskunft.
 *   2. `routen.py`: Der Anbieter-Knopf trägt das Ziel (`redirect-to`) mit und
 *      läuft durch `_relatives_ziel` (kein Open Redirect).
 *   3. `seiten.css`: Der Trenner ist gestaltet — Abstände/Schrift/Farbe
 *      ausschliesslich über Tokens (keine festen px-Werte für Abstände).
 *   4. Die sichtbaren Texte des Anmeldebereichs tragen echte Umlaute.
 *
 * Regel 13 (backend/Dockerfile): Die Datei liest `backend/…` und
 * `frontend/src/ssot/…` — beide liegen im Frontend-Stage des Images unter
 * `/sso1-backend/…` bzw. `/frontend/src/ssot/…` (siehe COPY-Zeilen).
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const HIER = dirname(fileURLToPath(import.meta.url))

function suche(kandidaten, was) {
  const pfad = kandidaten.find((p) => existsSync(p))
  assert.ok(pfad, `${was} nicht gefunden (gesucht: ${kandidaten.join(', ')})`)
  return readFileSync(pfad, 'utf8')
}

const ROUTEN = suche(
  [
    resolve(HIER, '..', '..', 'backend', 'src', 'diakronos_app', 'anmeldung', 'routen.py'),
    resolve(HIER, '..', '..', 'sso1-backend', 'anmeldung', 'routen.py'),
  ],
  'routen.py',
)

const SEITEN_CSS = suche(
  [
    resolve(HIER, '..', '..', 'frontend', 'src', 'ssot', 'seiten.css'),
    resolve(HIER, '..', 'src', 'ssot', 'seiten.css'),
  ],
  'seiten.css',
)

const SPA = suche(
  [
    resolve(HIER, '..', '..', 'backend', 'src', 'diakronos_app', 'spa.py'),
    resolve(HIER, '..', '..', 'sso1-backend', 'spa.py'),
  ],
  'spa.py',
)

function routeAbschnitt(text) {
  const start = text.indexOf('def registriere_routen')
  assert.ok(start >= 0, 'registriere_routen fehlt')
  const ende = text.indexOf('@app.get("/auth/oidc/start"', start)
  assert.ok(ende > start, 'Ende der /login-Route nicht gefunden')
  return text.slice(start, ende)
}

test('LOGIN-SSO1: bei AUTH_LOCAL_LOGIN=an leitet /login nicht weiter', () => {
  assert.match(
    ROUTEN,
    /def _lokal_login_an\(\)[\s\S]*?local_login == LOKAL_AN/,
    'die Anmeldeschicht kennt den Modus `an` nicht',
  )
  const route = routeAbschnitt(ROUTEN)
  assert.match(
    route,
    /if konf\.oidc_aktiv\(\) and not no_redirect and not _lokal_login_an\(\):/,
    'die Zwangsweiterleitung hängt nicht mehr an `not _lokal_login_an()`',
  )
})

test('LOGIN-SSO1: der ausdrückliche SSO-Start (?sso=1) steht VOR der 503-Auskunft', () => {
  const route = routeAbschnitt(ROUTEN)
  const start = route.indexOf('_start_weiterleitung(request, ziel)')
  const nichtErlaubt = route.indexOf('not _lokales_login_erlaubt()')
  assert.ok(start >= 0, 'kein Anbieter-Start in der /login-Route')
  assert.ok(nichtErlaubt > start, 'der Anbieter-Start steht hinter der 503-Auskunft')
  assert.match(
    route,
    /request\.query_params\.get\("sso"\) == "1"/,
    '`sso=1` wird nicht mehr ausgewertet',
  )
})

test('LOGIN-SSO1: der Knopf trägt das Ziel und prüft es (kein Open Redirect)', () => {
  const start = ROUTEN.indexOf('def _anbieter_knopf_html')
  assert.ok(start >= 0, '_anbieter_knopf_html fehlt')
  const block = ROUTEN.slice(start, ROUTEN.indexOf('def _oder_trenner_html'))
  assert.match(block, /_relatives_ziel\(/, 'das Ziel wird nicht geprüft')
  assert.match(block, /_sso_vorbelegung\(/, 'das Ziel wird nicht in die Adresse geschrieben')

  const hilfe = ROUTEN.slice(
    ROUTEN.indexOf('def _sso_vorbelegung'),
    ROUTEN.indexOf('def _anbieter_knopf_html'),
  )
  assert.match(hilfe, /redirect-to=/, '`redirect-to` fehlt in der Adresse')
  assert.match(hilfe, /frag=/, 'der Hash wird nicht als `frag` mitgegeben')
})

test('LOGIN-SSO1: der Trenner „oder“ steht zwischen Knopf und Formular', () => {
  const start = ROUTEN.indexOf('def _oder_trenner_html')
  assert.ok(start >= 0, '_oder_trenner_html fehlt')
  const block = ROUTEN.slice(start, start + 900)
  assert.match(block, /dk-oder/, 'Trenner-Klasse fehlt')
  assert.match(block, /oder/, 'der Text „oder“ fehlt')
  assert.match(
    ROUTEN,
    /if lokal and _lokal_login_an\(\):\s*\n\s*trenner_block = _oder_trenner_html\(\)/,
    'der Trenner wird nicht an „beide Wege offen“ gebunden',
  )
})

test('LOGIN-SSO1: der Trenner hat seine Gestaltung in seiten.css (nur Tokens)', () => {
  assert.match(SEITEN_CSS, /\.dk-oder\s*\{/, 'Regel .dk-oder fehlt')
  assert.match(SEITEN_CSS, /\.dk-oder-linie\s*\{/, 'Regel .dk-oder-linie fehlt')
  const block = SEITEN_CSS.slice(SEITEN_CSS.indexOf('.dk-oder {'))
  const teil = block.slice(0, block.indexOf('.dk-abschnitt'))
  assert.match(teil, /gap: var\(--sp-/, 'kein Abstand aus der Skala')
  assert.match(teil, /margin: var\(--sp-/, 'kein Margin aus der Skala')
  assert.match(teil, /font-size: var\(--fs-/, 'keine Schriftrolle')
  assert.match(teil, /background: var\(--line\)/, 'Linienfarbe nicht aus den Tokens')
  // Die EINE feste Angabe, die bleiben darf: die Haarlinie selbst. Alles
  // andere (Abstände, Schrift) kommt aus Tokens.
  const ohneLinie = teil.replace(/height:\s*1px;/g, '')
  assert.doesNotMatch(ohneLinie, /\b\d+px\b/, 'fester px-Wert im Trenner')
})

test('LOGIN-SSO1: sichtbare Texte im Anmeldebereich haben echte Umlaute', () => {
  // Nur die gerenderten Sätze — Kommentare/Bezeichner sind ausgenommen.
  const texte = [
    ROUTEN,
    SPA,
  ].join('\n')
  for (const wort of [
    'Anmeldung nicht möglich',
    'Anmeldelinks für Registrierung',
    'Ungültige Rückkehr vom Anbieter',
    'Die Anmeldung konnte nicht geprüft werden',
    'nicht verfügbar',
  ]) {
    assert.ok(texte.includes(wort), `Satz fehlt oder hat ASCII-Ersatz: ${wort}`)
  }
})
