/**
 * LOGIN-1 — der Waechter zur Weiterleitung von der Anmeldeseite.
 *
 * Die Karte aendert SERVER-Verhalten (`/login` mit gueltiger Sitzung -> 302).
 * Der Server-Teil wird in `backend/tests/test_login1_angemeldet_weiter.py`
 * gegen HTTP geprueft (rot -> gruen nachgewiesen). Hier steht der Waechter,
 * der die Regel in der QUELLE haelt — damit sie nicht in einem spaeteren
 * Umbau still verschwindet (dann faellt der Befund zurueck: „wer angemeldet
 * ist, sieht trotzdem das Anmeldeformular“).
 *
 * Gelesen wird `backend/src/diakronos_app/anmeldung/routen.py`:
 *
 *  1. Die Route `/login` ruft `_weiterleitung_angemeldet` — und zwar VOR der
 *     Anbieter-Weiche (sonst geht derselbe Mensch erst auf die Zwischenseite
 *     und dann zum Anbieter, statt in die App).
 *  2. Das Ziel laeuft durch `_relatives_ziel` (kein Open Redirect) und
 *     traegt das Betriebs-Praefix (WEB-5a: `dev.ecg-hn.de` nutzt
 *     `/diakronos`).
 *  3. `noredirect=1` (Rueckkehr eines Fehlschlags) leitet NICHT weiter —
 *     dort wird immer die lokale Maske gezeigt.
 *
 * Regel 13 (backend/Dockerfile): Die Datei liest `backend/…` und braucht
 * deshalb eine eigene COPY-Zeile im Frontend-Stage. Fehlt sie, meldet dieser
 * Test im Image „Quelle fehlt“ — genau der Vorfall, den Regel 13 verhindert.
 */

import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const HIER = dirname(fileURLToPath(import.meta.url))
// Erster Ort (Worktree): <wurzel>/backend/…; zweiter Ort (Image): /login1-backend/….
// Der Image-Ort haengt am WURZELVERZEICHNIS des Frontend-Stage (`/build` —
// `tests/…` liegt dort direkt), deshalb wird er von `tests/` aus gesucht.
const ORTE = [
  resolve(HIER, '..', '..', 'backend', 'src', 'diakronos_app', 'anmeldung', 'routen.py'),
  resolve(HIER, '..', '..', 'login1-backend', 'anmeldung', 'routen.py'),
]

function quelle() {
  const pfad = ORTE.find((p) => existsSync(p))
  assert.ok(pfad, `routen.py nicht gefunden (gesucht: ${ORTE.join(', ')})`)
  return readFileSync(pfad, 'utf8')
}

function routeAbschnitt(text) {
  const start = text.indexOf('def registriere_routen')
  assert.ok(start >= 0, 'registriere_routen fehlt')
  const ende = text.indexOf('@app.get("/auth/oidc/start"', start)
  assert.ok(ende > start, 'Ende der /login-Route nicht gefunden')
  return text.slice(start, ende)
}

test('LOGIN-1: die /login-Route prueft die Sitzung VOR der Anbieter-Weiche', () => {
  const route = routeAbschnitt(quelle())
  const weiter = route.indexOf('_weiterleitung_angemeldet(request)')
  const anbieter = route.indexOf('_hash_bruecke_seite(ziel)')
  assert.ok(weiter >= 0, 'die Route ruft _weiterleitung_angemeldet NICHT auf')
  assert.ok(
    anbieter >= 0,
    'Anbieter-Weiche nicht gefunden — Test veraltet, Aussage pruefen',
  )
  assert.ok(
    weiter < anbieter,
    'die Weiterleitung steht NACH der Anbieter-Weiche (Befund waere zurueck)',
  )
})

test('LOGIN-1b: noredirect=1 leitet nicht weiter — und OIDC ist keine Bedingung mehr', () => {
  const route = routeAbschnitt(quelle())
  // Die Weiterleitung steht hinter `not no_redirect` — der Rueckkehrpunkt eines
  // Fehlschlags bekommt IMMER die Maske.
  assert.match(
    route,
    /if not no_redirect:\s*\n\s*weiter: Response \| None = _weiterleitung_angemeldet\(request\)/,
    'die Weiterleitung ist nicht mehr allein an `not no_redirect` gebunden',
  )
  assert.match(
    route,
    /no_redirect = request\.query_params\.get\("noredirect"\) == "1"/,
    '`noredirect` wird nicht mehr gelesen',
  )
  // LOGIN-1b (Sicherheits-Review LOGIN-1): `dev.ecg-hn.de` faehrt OIDC=0 und
  // ist der NORMALFALL — die Weiterleitung darf dort nicht an der
  // Anbieter-Weiche haengenbleiben.
  assert.doesNotMatch(
    route,
    /if konf\.oidc_aktiv\(\) and not no_redirect:\s*\n\s*weiter:/,
    'die Weiterleitung haengt wieder an OIDC (Befund LOGIN-1b waere zurueck)',
  )
})

test('LOGIN-1b: Punktsegmente und Zwischenspeicher sind gehaertet', () => {
  const quelle_ = quelle()
  const start = quelle_.indexOf('def _relatives_ziel')
  assert.ok(start >= 0, '_relatives_ziel fehlt')
  const block = quelle_.slice(start, quelle_.indexOf('def _lokales_login_erlaubt'))
  assert.match(block, /_hat_punktsegment\(ziel\)/, 'Punktsegmente nicht abgewiesen')
  assert.match(
    block,
    /in \{"\.", "\.\."\}/,
    'die Pruefung kennt `.` und `..` nicht',
  )

  const wstart = quelle_.indexOf('def _weiterleitung_angemeldet')
  assert.ok(wstart >= 0, '_weiterleitung_angemeldet fehlt')
  const weiter = quelle_.slice(wstart, quelle_.indexOf('def _neue_sitzung_nach_login'))
  assert.match(weiter, /"Cache-Control": "no-store"/, 'no-store fehlt')
  assert.match(weiter, /"Vary": "Cookie"/, 'Vary: Cookie fehlt')
})

test('LOGIN-1: das Ziel traegt das Betriebs-Praefix (WEB-5a)', () => {
  const quelle_ = quelle()
  const start = quelle_.indexOf('def _relatives_ziel')
  assert.ok(start >= 0, '_relatives_ziel fehlt')
  const block = quelle_.slice(start, quelle_.indexOf('def _lokales_login_erlaubt'))
  assert.match(block, /base_path\.pfad\(ziel\)/, 'Praefix fehlt am Ziel')
  assert.match(block, /startswith\("\/\/"\)/, 'protokollrelative Ziele nicht abgewiesen')
  assert.match(block, /"\\\\" in ziel/, 'Backslash-Ziele nicht abgewiesen')
})

test('LOGIN-1: eine abgelaufene oder gesperrte Sitzung wird nicht geleitet', () => {
  const quelle_ = quelle()
  const start = quelle_.indexOf('def _angemeldete_sitzung')
  assert.ok(start >= 0, '_angemeldete_sitzung fehlt')
  const block = quelle_.slice(start, quelle_.indexOf('def _ist_oeffentlicher_pfad'))
  assert.match(block, /sitzungen\.lesen\(sid\)/, 'Sitzungsspeicher wird nicht gefragt')
  assert.match(block, /benutzer_status\.ist_aktiv\(user\)/, 'Kontostatus wird nicht geprueft')
})
