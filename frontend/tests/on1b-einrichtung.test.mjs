/**
 * ON-1b — Wächter für die serverseitig gerenderten Einrichtungs-Seiten.
 *
 * Was dieser Test festhält (Karte ON-1b, F1 + F5):
 *
 *  F1  Der Einrichtungs-Token ist das Geheimnis des Links — er darf nicht in
 *      ein Protokoll geraten. Der Wächter prüft am Quelltext, dass
 *      a) der Zugriffs-Logfilter existiert und am `uvicorn.access`-Logger
 *         hängt,
 *      b) er den Einrichtungspfad auf `/einrichtung/***` umschreibt und
 *      c) die Betreiber-Anleitung den Reverse-Proxy-Fall nennt (dort kann
 *         die App nichts wegfiltern — das muss dastehen).
 *
 *  F5  Die toten Konstanten `CSP` und `ANTWORT_KOPFZEILEN` sind aus
 *      `einrichtung_seiten.py` entfernt (die Policy hängt zentral an
 *      `sec_header`; eine zweite im selben Feld wäre die Schnittmenge).
 *
 *  SSOT In den Seiten-Modulen steht KEIN fester Farb-, Schrift- oder
 *      Radius-Wert — alles kommt aus `tokens.css`/`seiten.css`.
 *
 * Läuft wie die übrigen Frontend-Tests im Docker-Build (`node --test`).
 * Er liest Backend-Quellen (Regel 13) — die nötigen Dateien sind im
 * Frontend-Stage des Images per COPY vorhanden.
 */
import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import { dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

/**
 * Datei lesen — im Repo liegt der Test unter `frontend/tests/` (zwei Ebenen
 * unter der Wurzel), im Image-Frontend-Stage unter `/build/tests/` (eine).
 * Beide Lagen sind zulaessig; genommen wird die erste, die existiert.
 */
const HIER = dirname(fileURLToPath(import.meta.url))

function lies(relativ) {
  // Kein `path.resolve` mit fuehrenden `..`: auf einer Wurzel wie `/build/tests`
  // normalisiert Node `../..` zu `/` und verliert die Wurzel. Deshalb von Hand
  // hochgehen und die Segmente selbst zusammensetzen.
  const hoch = HIER.split('/')
  for (let i = 0; i < 2; i += 1) {
    if (hoch.length) hoch.pop()
    const pfad = [...hoch, relativ].join('/')
    if (existsSync(pfad)) return readFileSync(pfad, 'utf8')
  }
  throw new Error(`Datei nicht gefunden: ${relativ} (gesucht ab ${HIER})`)
}

const routen = lies('backend/src/diakronos_app/anmeldung/einrichtung_routen.py')
const seiten = lies('backend/src/diakronos_app/einrichtung_seiten.py')
const ANLEITUNG = lies('docs/BETRIEBSANLEITUNG.md')

// ── F1: Token nicht im Zugriffsprotokoll ──────────────────────────────────

assert.match(
  routen,
  /class EinrichtungsAccessLogFilter\(logging\.Filter\)/,
  'F1: Zugriffs-Logfilter fehlt in einrichtung_routen.py',
)
assert.match(
  routen,
  /zugriff = logging\.getLogger\("uvicorn\.access"\)/,
  'F1: Filter wird nicht am uvicorn.access-Logger installiert',
)
assert.match(routen, /zugriff\.addFilter\(EinrichtungsAccessLogFilter\(\)\)/, 'F1: addFilter fehlt')
assert.match(routen, /TOKEN_PLATZHALTER = "\*\*\*"/, 'F1: Platzhalter *** fehlt')
assert.match(routen, /_SEITEN_PRAEFIX = "\/einrichtung\/"/, 'F1: Einrichtungspfad fehlt')

// Der Platzhalter wird ANGEHÄNGT, der Pfad davor bleibt (Betriebs-Präfix).
assert.match(
  routen,
  /neu\[2\] = f"\{praefix\}\{_SEITEN_PRAEFIX\}\{TOKEN_PLATZHALTER\}/,
  'F1: Pfad wird nicht auf <praefix>/einrichtung/*** umgeschrieben',
)

// Reverse-Proxy-Logs sind NICHT filterbar — der Hinweis muss in der Anleitung stehen.
assert.match(
  ANLEITUNG,
  /Reverse-Proxy-Logs sind ebenfalls betroffen/,
  'F1: BETRIEBSANLEITUNG nennt den Reverse-Proxy-Fall nicht',
)
assert.match(
  ANLEITUNG,
  /\/einrichtung\/\*\*\*/,
  'F1: BETRIEBSANLEITUNG zeigt den Platzhalter nicht',
)

// ── F2: Fehlerseite trägt ein frisches _csrf ──────────────────────────────

const fehlerseite = routen.slice(routen.indexOf('def _fehlerseite('))
assert.match(
  fehlerseite,
  /maske_token import erzeuge_token/,
  'F2: _fehlerseite erzeugt kein frisches _csrf',
)
assert.doesNotMatch(
  fehlerseite.split('"""').slice(-1)[0],
  /csrf_token=""/,
  'F2: _fehlerseite setzt weiterhin csrf_token=""',
)

// ── F3: der GET schreibt nicht ────────────────────────────────────────────

const getRoute = routen.slice(
  routen.indexOf('@app.get("/einrichtung/{token}"'),
  routen.indexOf('@app.post("/einrichtung/{token}"'),
)
assert.match(
  getRoute,
  /pruefe_token\(token, zaehle=False\)/,
  'F3: GET prüft den Token mit Zähler (schreibender GET)',
)

// ── F4: keine SSO-Kennzeichnung ───────────────────────────────────────────

assert.doesNotMatch(routen, /sitzungen\.anlegen\([^)]*sso=True\)/, 'F4: Sitzung als SSO markiert')
assert.match(routen, /sitzungen\.anlegen\(werte\["email"\], sso=False\)/, 'F4: sso=False fehlt')

// ── F5: tote Konstanten weg ───────────────────────────────────────────────

assert.doesNotMatch(seiten, /^CSP\s*=/m, 'F5: CSP ist wieder da')
assert.doesNotMatch(seiten, /^ANTWORT_KOPFZEILEN\s*=/m, 'F5: ANTWORT_KOPFZEILEN ist wieder da')
assert.doesNotMatch(seiten, /__all__\s*=\s*\[[^\]]*"CSP"/, 'F5: CSP steht noch in __all__')

// ── F6: der Token gewinnt über die Formularfelder ─────────────────────────

const postRoute = routen.slice(routen.indexOf('@app.post("/einrichtung/{token}"'))
const stelleVorpruefung = postRoute.indexOf('pruefe_token(token, zaehle=False)')
const stelleValidierung = postRoute.indexOf('werte = _pruefe_werte(felder)')
assert.ok(stelleVorpruefung > 0, 'F6: Vorprüfung des Tokens fehlt im POST')
assert.ok(
  stelleVorpruefung < stelleValidierung,
  'F6: der Token wird NACH der Feldprüfung geprüft (Orakel)',
)

// ── SSOT: keine festen Farb-/Schrift-/Radius-Werte in den Seiten-Modulen ──

const FESTE_FARBE = /#[0-9a-fA-F]{3,8}\b|\brgba?\s*\(|\bhsla?\s*\(/
const FESTE_SCHRIFT = /font-family\s*:\s*(?!inherit|var\()/i
const FESTER_RADIUS = /border-radius\s*:\s*\d/i

for (const [name, text] of [
  ['einrichtung_routen.py', routen],
  ['einrichtung_seiten.py', seiten],
]) {
  // Kommentare/Zeichenketten-Erklärungen sind erlaubt; geprüft wird der Code.
  const code = text
    .split('\n')
    .filter((z) => !z.trimStart().startsWith('#'))
    .join('\n')
  assert.doesNotMatch(code, FESTE_FARBE, `${name}: fester Farbwert (SSOT: tokens.css)`)
  assert.doesNotMatch(code, FESTE_SCHRIFT, `${name}: feste Schriftfamilie (SSOT: tokens.css)`)
  assert.doesNotMatch(code, FESTER_RADIUS, `${name}: fester Radius (SSOT: tokens.css)`)
}

// ── F8: der Kasten nennt die Adresse MIT Betriebs-Präfix ──────────────────

const EINRICHTUNG_MODUL = lies('backend/src/diakronos_app/einrichtung.py')
const ERSTINSTALLATION = lies('backend/src/diakronos_app/erstinstallation.py')

assert.match(
  EINRICHTUNG_MODUL,
  /if not base_path\.aktiver_praefix\(\):/,
  'F8: link_anzeige holt den Praefix nicht selbst aus den Einstellungen',
)
assert.match(
  ERSTINSTALLATION,
  /_praefix_setzen\(\)/,
  'F8: der Entrypoint-Prozess setzt den Praefix nicht',
)

console.log('on1b-einrichtung: F1/F2/F3/F4/F5/F6/F8 + SSOT geprüft')
