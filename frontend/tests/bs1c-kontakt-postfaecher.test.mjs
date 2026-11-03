/**
 * BS-1c — Kontaktformular: mehrere Postfächer + Herkunft Primo (Vertragstest).
 *
 * Die Arbeit ist Backend (`website/kontakt.py`); das Formular selbst baut
 * Primo. Dieser Test hält deshalb den VERTRAG fest, damit die Website nicht
 * gegen eine erfundene Form baut — und damit die Zusagen der Karte nicht
 * stillschweigend verschwinden:
 *
 *   (K1) `postfach` wird im Endpunkt gelesen, aufgelöst und bei unbekanntem
 *        oder inaktivem Slug mit einer Feldmeldung abgelehnt; der Rückfall
 *        ist das Postfach `standard` bzw. das erste aktive (sortierung).
 *   (K2) `website.oeffentlich.postfaecher` ist ein GAST-Endpunkt, nur GET,
 *        und gibt NUR `slug` + `bezeichnung` aus (kein `email`).
 *   (K3) `betreff_zusatz` (max. 100) hängt an den FESTEN Betreff; ein Zusatz
 *        mit Steuerzeichen wird abgelehnt statt bereinigt.
 *   (K4) Die Herkunftsprüfung lässt `PRIMO_PUBLIC_URL` zu und setzt CORS nur
 *        für genau diese Herkunft, ohne Credentials; OPTIONS (Preflight) ist
 *        im Methoden-Router zugelassen, führt aber nichts aus.
 *
 * Geprüft wird Quelltext (Regex), nicht das Aussehen; Lauf im Docker-Build
 * über `node --test`:  cwd = frontend/
 */

import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HIER = dirname(fileURLToPath(import.meta.url))
const REPO = join(HIER, '..', '..')
const KONTAKT = join(REPO, 'backend', 'src', 'diakronos_app', 'website', 'kontakt.py')
const ROUTER = join(REPO, 'backend', 'src', 'diakronos_app', 'frappe_compat', 'router.py')
const TESTS = join(REPO, 'backend', 'tests', 'test_bs1c_kontakt_postfaecher.py')

function lies(pfad) {
  assert.ok(existsSync(pfad), `Datei fehlt: ${pfad}`)
  return readFileSync(pfad, 'utf8')
}

test('BS-1c/K1: der Endpunkt nimmt `postfach` an und loest es gegen die Postfaecher auf', () => {
  const quelle = lies(KONTAKT)
  assert.match(quelle, /def postfach_waehlen\(slug: str\)/)
  assert.match(quelle, /def _postfach_slug\(daten: dict\[str, Any\]\) -> str:/)
  // Reihenfolge der Karte: standard -> erstes aktives -> WEBSITE_KONTAKT_EMPFAENGER
  assert.match(quelle, /regeln\.POSTFACH_STANDARD/)
  assert.match(quelle, /postfaecher_oeffentlich\(/)
  assert.match(quelle, /KontaktNichtEingerichtet/)
})

test('BS-1c/K1: unbekanntes/inaktives Postfach ist eine Feldmeldung, keine Mail', () => {
  const quelle = lies(KONTAKT)
  assert.match(quelle, /class PostfachUnbekannt\(ValueError\)/)
  assert.match(quelle, /except PostfachUnbekannt:/)
  assert.match(quelle, /"postfach": "Dieses Postfach gibt es nicht\./)
})

test('BS-1c/K1: die Zieladresse wird nie ausgeliefert (kein `email` in Antworten)', () => {
  const quelle = lies(KONTAKT)
  // Die oeffentliche Liste baut NUR slug + bezeichnung.
  const liste = quelle.split('def postfaecher_oeffentlich(')[1].split('def _registriere_kurzpfad')[0]
  assert.match(liste, /"slug": str\(p\.slug\)/)
  assert.match(liste, /"bezeichnung": str\(p\.bezeichnung\)/)
  assert.ok(!/["']email["']\s*:/.test(liste), 'postfaecher_oeffentlich gibt ein Feld `email` aus')
})

test('BS-1c/K2: `website.oeffentlich.postfaecher` ist Gast-Endpunkt und nur GET', () => {
  const quelle = lies(KONTAKT)
  assert.match(quelle, /@whitelist\(methods=\["GET"\], allow_guest=True\)\ndef postfaecher_oeffentlich\(/)
  assert.match(
    quelle,
    /register_with_frappe_module\(\s*"website\.oeffentlich", "postfaecher", postfaecher_oeffentlich\s*\)/,
  )
})

test('BS-1c/K3: Betreff-Zusatz haengt an den festen Betreff, Hoechstlaenge 100', () => {
  const quelle = lies(KONTAKT)
  assert.match(quelle, /BETREFF_ZUSATZ_MAX = 100/)
  assert.match(quelle, /def betreff_mit_zusatz\(zusatz: str\) -> str:/)
  assert.match(quelle, /def pruefe_betreff_zusatz\(/)
  // Der Zusatz landet im Betreff der Mail (nicht als eigener Kopf).
  assert.match(quelle, /betreff=betreff_mit_zusatz\(bereinigt\.get\("betreff_zusatz", ""\)\)/)
})

test('BS-1c/K3: ein Zusatz mit Steuerzeichen wird abgelehnt, nicht bereinigt', () => {
  const quelle = lies(KONTAKT)
  const block = quelle.split('def pruefe_betreff_zusatz(')[1].split('def pruefe_felder(')[0]
  assert.match(block, /_KOPFZEILEN_STEUERZEICHEN\.search\(zusatz\)/)
  // Der Zusatz wird abgelehnt: Meldung im Feld `betreff_zusatz`, KEIN Versand.
  assert.match(block, /"Der Zusatz im Betreff darf keine Zeilenumbrüche oder "/)
  assert.match(quelle, /fehler\["betreff_zusatz"\] = zusatz_fehler/)
  assert.ok(!/return "", _saubere_kopfzeile/.test(block), 'Zusatz wird still bereinigt')
})

test('BS-1c/K4: Herkunft akzeptiert PRIMO_PUBLIC_URL zusaetzlich zur eigenen Domain', () => {
  const quelle = lies(KONTAKT)
  assert.match(quelle, /def _herkunfts_erlaubt\(request\) -> set\[str\]:/)
  assert.match(quelle, /settings\.primo_public_url_effektiv/)
  assert.match(quelle, /def cors_herkunft\(request\) -> str:/)
  assert.match(quelle, /Access-Control-Allow-Origin/)
  assert.ok(
    !/Access-Control-Allow-Credentials"?\s*:/.test(quelle),
    'CORS darf keine Credentials freigeben (G4)',
  )
  assert.ok(!/'Access-Control-Allow-Origin': "\*"/.test(quelle), 'CORS darf kein Sternchen sein')
})

test('BS-1c/K4: OPTIONS (Preflight) ist im Methoden-Router zugelassen und fuehrt nichts aus', () => {
  const router = lies(ROUTER)
  assert.match(router, /methods=\["GET", "POST", "PUT", "PATCH", "OPTIONS"\]/)
  assert.match(router, /async def _preflight\(path: str, request: Request\)/)
  assert.match(router, /await _preflight\(path, request\)/)
})

// ── BS-1c2: Nachbesserung (F1-F7) ─────────────────────────────────────────

const MIDDLEWARE = join(REPO, 'backend', 'src', 'diakronos_app', 'frappe_compat', 'auth_middleware.py')
const REGISTRY = join(REPO, 'backend', 'src', 'diakronos_app', 'frappe_compat', 'registry.py')
const BREMSE = join(REPO, 'backend', 'src', 'diakronos_app', 'anmeldung', 'kontaktbremse.py')

test('BS-1c2/F1: die Postfach-Liste steht in der exakten Middleware-Ausnahme', () => {
  const quelle = lies(MIDDLEWARE)
  const menge = quelle.split('_OEFFENTLICHE_WEBSITE_NAMEN = frozenset({')[1].split('})')[0]
  for (const name of [
    'website.oeffentlich.postfaecher',
    'kontakt.postfaecher_oeffentlich',
    'diakronos.diakronos.api.website.postfaecher_oeffentlich',
  ]) {
    assert.ok(menge.includes(`"${name}"`), `Ausnahme fehlt: ${name}`)
  }
  // Keine Praefix-Regel (SEC-11b F4 bleibt).
  assert.ok(!/startswith\("website\./.test(quelle), 'Praefix-Ausnahme wieder eingebaut')
})

test('BS-1c2/F2: Herkunft wird EINMAL normalisiert und exakt verglichen', () => {
  const quelle = lies(KONTAKT)
  assert.match(quelle, /def _normalisiere_herkunft\(wert: str\) -> str:/)
  assert.match(quelle, /def _primo_herkunft\(\) -> str:/)
  // Genau EINE Lesestelle der Einstellung.
  const treffer = quelle.match(/primo_public_url_effektiv/g) || []
  assert.equal(treffer.length, 1, 'PRIMO_PUBLIC_URL wird mehrfach gelesen')
  // Standardport faellt weg, Schema muss http(s) sein.
  assert.match(quelle, /_STANDARDPORTS = \{"http": 80, "https": 443\}/)
  assert.match(quelle, /if schema not in _STANDARDPORTS:/)
})

test('BS-1c2/F3: Preflight haengt an `preflight="self"`, nicht an der Funktionsgestalt', () => {
  const router = lies(ROUTER)
  const kontakt = lies(KONTAKT)
  assert.match(kontakt, /@whitelist\(methods=\["POST"\], preflight="self", allow_guest=True\)/)
  assert.match(router, /def _beantwortet_preflight_selbst\(fn\) -> bool:/)
  assert.match(router, /if fn is not None and _beantwortet_preflight_selbst\(fn\):/)
  assert.ok(
    !/inspect\.iscoroutinefunction\(fn\) and _hat_namenparameter/.test(router),
    'Preflight entscheidet wieder nach Funktionsgestalt',
  )
  // Der Dekorator kennt die Option.
  assert.match(lies(REGISTRY), /preflight="self"/)
})

test('BS-1c2/F4: Vary: Origin steht auf jeder Kontakt-Antwort', () => {
  const quelle = lies(KONTAKT)
  const antwort = quelle.split('def _antwort(')[1].split('def _cors_kopfzeilen(')[0]
  assert.match(antwort, /antwort\.headers\["Vary"\] = "Origin"/)
  const preflight = quelle.split('def _preflight(')[1].split('@whitelist')[0]
  assert.match(preflight, /antwort\.headers\["Vary"\] = "Origin"/)
  // Vary steht NICHT mehr nur im CORS-Zweig.
  const cors = quelle.split('def _cors_kopfzeilen(')[1].split('def _antwort_mit_cors(')[0]
  assert.match(cors, /Vary/)
})

test('BS-1c2/F5: die Postfach-Liste hat einen eigenen Bremseimer', () => {
  const kontakt = lies(KONTAKT)
  const bremse = lies(BREMSE)
  assert.match(kontakt, /def _liste_gebremst\(request\):/)
  assert.match(kontakt, /kontaktbremse\.pruefe_liste\(/)
  assert.match(bremse, /def pruefe_liste\(ip: str \| None, client=None\) -> tuple\[bool, str\]:/)
  assert.match(bremse, /LISTE_SCHLUESSEL_PRAEFIX = "diakronos:kontakt-liste:"/)
  // Die Liste darf NICHT ueber den Formular-Eimer laufen.
  const liste = kontakt.split('def postfaecher_oeffentlich(')[1].split('def _liste_gebremst(')[0]
  assert.ok(!/kontaktbremse\.pruefe\(/.test(liste), 'Liste nutzt den Formular-Eimer')
})

test('BS-1c2/F6: Betreff-Zusatz lehnt die volle Steuerzeichenmenge ab', () => {
  const quelle = lies(KONTAKT)
  assert.match(quelle, /_KOPFZEILEN_STEUERZEICHEN = re\.compile\(r"\[\\x00-\\x1f\\x7f\\x85\\u2028\\u2029\]"\)/)
  const block = quelle.split('def pruefe_betreff_zusatz(')[1].split('def pruefe_felder(')[0]
  assert.match(block, /_KOPFZEILEN_STEUERZEICHEN\.search\(zusatz\)/)
})

test('BS-1c2/F7: kein aktives Postfach -> 503, kein stiller Rueckfall', () => {
  const quelle = lies(KONTAKT)
  const block = quelle.split('def postfach_waehlen(slug: str)')[1].split('def _postfach_sitzung')[0]
  assert.match(block, /raise KontaktNichtEingerichtet\(\)/)
  const liste = quelle.split('def postfaecher_oeffentlich(')[1].split('def _liste_gebremst(')[0]
  assert.match(liste, /if bool\(p\.aktiv\)/)
})

test('BS-1c: die Backend-Tests der Karte sind vorhanden (rot -> gruen belegt)', () => {
  const tests = lies(TESTS)
  assert.match(tests, /def test_unbekannter_postfach_slug_ist_400_ohne_kandidatenliste/)
  assert.match(tests, /def test_preflight_auf_dem_kontaktpfad/)
  assert.match(tests, /def test_primo_herkunft_wird_angenommen/)
  // BS-1c2
  assert.match(tests, /def test_f1_postfach_liste_ist_von_der_middleware_ausgenommen/)
  assert.match(tests, /def test_f2_falsches_schema_oder_falscher_port_ist_403/)
  assert.match(tests, /def test_f4_vary_origin_auf_allen_kontakt_antworten/)
  assert.match(tests, /def test_f5_liste_hat_einen_eigenen_bremseimer/)
  assert.match(tests, /def test_f7_kein_aktives_postfach_bleibt_503_und_liste_leer/)
})
