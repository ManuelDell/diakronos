/**
 * BUG-WEB-VORSCHAU — die Ansprechpartner-Vorschau fragt den öffentlichen Stand
 * per **GET** ab (nicht per POST).
 *
 * BEFUND (UX-Nachmessung 25.11.): `#/website` löste in jeder Ansicht
 * `405 POST /api/method/website.oeffentlich.ansprechpartner` aus. Der Endpunkt
 * deklariert `methods=["GET"]` (`website/oeffentlich_api.py`), der 405-Text
 * lautet „Aufruf per POST abgewiesen (erlaubt: GET)“ — die Vorschau blieb
 * deshalb IMMER leer, samt Fehlertext.
 *
 * WARUM KEIN `apiGet`-STUB
 * ========================
 * Die Lehre aus den verdeckten Fehlern: ein Stub, der `apiGet` durch `apiCall`
 * ersetzt (so wie `bs3b-ansprechpartner-bereich.test.mjs` mit
 * `export const apiGet = apiCall`), macht jede Methode gleich — der Test
 * bleibt grün, obwohl der Aufruf 405 liefert. Hier läuft deshalb der ECHTE
 * `useApi`-Code gegen ein `fetch`, das die HTTP-Methode festhält und alles
 * ausser GET mit 405 beantwortet (wie der Server).
 *
 * Geprüft wird:
 *   A  die Methode des Vorschau-Aufrufs ist GET (und der Pfad ist der
 *      öffentliche Endpunkt),
 *   B  eine Antwort in der Form des Endpunkts (`{"message": [ … ]}`) landet in
 *      `oeffentlich` — die Vorschau ist danach NICHT leer,
 *   C  Gegenprobe: derselbe Aufruf mit POST endet mit 405 und die Vorschau
 *      bleibt leer (der Test könnte den Fehler also sehen).
 *
 * Lokal: node --test tests/bug-web-vorschau-ansprechpartner-get.test.mjs
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, symlinkSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const HIER = path.dirname(fileURLToPath(import.meta.url))
const FRONTEND = path.resolve(HIER, '..')
const SRV = path.join(FRONTEND, 'src')
const COMPOSABLE = path.join(SRV, 'diakonos/composables/useAnsprechpartnerBereiche.js')

const OEFFENTLICH = 'website.oeffentlich.ansprechpartner'

/** Der öffentliche Stand, wie `oeffentlich_api.ansprechpartner` ihn liefert. */
function stand() {
  return [
    { bereich: 'Musik', funktion: 'xyz', name: 'Anna Muster', foto_url: null, postfach: 'musik' },
    { bereich: 'Chor', funktion: 'abc', name: 'Bernd Beispiel', foto_url: null, postfach: null },
  ]
}

/** Temporäre Bäume dieses Laufs (erst nach ALLEN Tests entfernen). */
const offeneBaeume = []
test.after(() => {
  for (const baum of offeneBaeume) rmSync(baum, { recursive: true, force: true })
})

// ── Quellen in ein ausführbares JS-Abbild kopieren ────────────────────────
// Dieselbe Technik wie in den übrigen FE-Tests: `.js`/`.mjs` werden zu
// `.mjs` umgeschrieben und die relativen Importe mitgezogen. `vue` und alle
// übrigen Pakete kommen über einen Symlink auf `frontend/node_modules`.
function modulSchreiben(abs, ausgabe, wache = new Set()) {
  if (wache.has(abs)) return
  wache.add(abs)
  let code = readFileSync(abs, 'utf8')
  code = code.replace(/from\s+'([.][^']+)'/g, (ganz, pfad) => {
    if (/\.vue$/.test(pfad)) throw new Error(`${abs}: Vue-Bauteil wird hier nicht gebraucht`)
    if (/\.(js|mjs)$/.test(pfad)) {
      modulSchreiben(path.resolve(path.dirname(abs), pfad), ausgabe, wache)
      return ganz.replace(pfad, pfad.replace(/\.(js|mjs)$/, '.mjs'))
    }
    return ganz
  })
  const zielDatei = path.join(ausgabe, path.relative(SRV, abs).replace(/\.(js|mjs)$/, '.mjs'))
  mkdirSync(path.dirname(zielDatei), { recursive: true })
  writeFileSync(zielDatei, code, 'utf8')
}

function ausgabeBauen() {
  // ACHTUNG (Befund 25.11.): `frontend/node_modules` ist im Worktree NICHT
  // vorhanden (auch nicht als Symlink). Ein Symlink auf `../..` und zurueck
  // zeigte ins Leere — deshalb wird der Ort EINMAL gesucht: der naechste
  // `node_modules`-Ordner aufwaerts ab `frontend/` oder der gemeinsame unter
  // `<repo>/frontend/node_modules`; fehlt beides, ist das ein Testfehler mit
  // klarer Meldung (kein stilles „vue nicht gefunden“).
  const ausgabe = mkdtempSync(path.join(tmpdir(), 'bug-web-vorschau-'))
  modulSchreiben(COMPOSABLE, ausgabe)
  const modules = path.join(ausgabe, 'node_modules')
  // Das geteilte `node_modules` liegt im HAUPT-Checkout (der Worktree hat
  // keins): `git rev-parse --git-common-dir` zeigt auf `<repo>/.git`, also
  // liegt `<repo>/frontend/node_modules` zwei Ebenen darueber. Dazu die
  // naechsten Kandidaten aufwaerts — fehlt alles, klarer Testfehler.
  let haupt = ''
  try {
    // `--path-format=absolute` noetig: sonst kommt im Worktree ein relativer
    // Pfad (`…/.git/worktrees/<task>`), und der `..` daneben zeigt ins Nichts.
    const gitVerzeichnis = execFileSync(
      'git', ['rev-parse', '--path-format=absolute', '--git-common-dir'],
      { cwd: FRONTEND, encoding: 'utf8' },
    ).trim()
    haupt = path.resolve(gitVerzeichnis, '..')
  } catch { /* kein git: Kandidaten unten reichen */ }
  const kandidaten = [
    path.join(FRONTEND, 'node_modules'),
    path.join(FRONTEND, '..', 'node_modules'),
    ...(haupt ? [path.join(haupt, 'frontend', 'node_modules')] : []),
  ]
  const quelle = kandidaten.find((p) => existsSync(path.join(p, 'vue')))
  assert.ok(quelle, 'kein node_modules mit `vue` gefunden — geprüft: ' + kandidaten.join(', '))
  symlinkSync(quelle, modules, 'dir')
  return ausgabe
}

/**
 * Ein `fetch`, wie der Server es tut: der öffentliche Endpunkt nimmt NUR GET
 * an, jede andere Methode endet mit 405 und genau dem Text aus
 * `oeffentlich_http.methoden_abweisung`. Alle Aufrufe werden festgehalten.
 */
function fetchAttrappe(aufrufe) {
  globalThis.window = { __DIakonosBOOT: { basePath: '/diakronos', csrf_token: 't' } }
  globalThis.localStorage = { getItem: () => null, setItem: () => {}, removeItem: () => {} }
  return async (url, optionen = {}) => {
    const methode = String(optionen.method || 'GET').toUpperCase()
    aufrufe.push({ url: String(url), methode })
    if (!String(url).includes('ansprechpartner')) {
      return new Response(JSON.stringify({ message: { bereiche: [], auswahl: {}, postfaecher: [] } }), {
        status: 200, headers: { 'Content-Type': 'application/json' },
      })
    }
    if (methode !== 'GET') {
      return new Response(JSON.stringify({
        message: 'Aufruf per POST abgewiesen (erlaubt: GET).',
        exception: 'MethodNotAllowed',
      }), { status: 405, headers: { 'Content-Type': 'application/json' } })
    }
    return new Response(JSON.stringify({ message: stand() }), {
      status: 200, headers: { 'Content-Type': 'application/json' },
    })
  }
}

async function composableLaden(aufrufe, { methodeErzwingen = null } = {}) {
  const ausgabe = ausgabeBauen()
  offeneBaeume.push(ausgabe)
  const echt = fetchAttrappe(aufrufe)
  globalThis.fetch = methodeErzwingen
    ? (url, optionen = {}) => echt(url, { ...optionen, method: methodeErzwingen })
    : echt
  const modul = await import(pathToFileURL(
    path.join(ausgabe, path.relative(SRV, COMPOSABLE).replace(/\.(js|mjs)$/, '.mjs')),
  ).href)
  return modul.useAnsprechpartnerBereiche()
}

// ══════════════════════════════════════════════════════════════════════════
// A · Die Methode
// ══════════════════════════════════════════════════════════════════════════

test('BUG-WEB-VORSCHAU: der öffentliche Stand wird per GET geholt, nie per POST', async () => {
  const aufrufe = []
  const bereiche = await composableLaden(aufrufe)
  await bereiche.oeffentlichenStandLaden()

  const vorschau = aufrufe.filter((a) => a.url.includes('ansprechpartner'))
  assert.equal(vorschau.length, 1, 'genau ein Aufruf für die Vorschau')
  assert.equal(vorschau[0].methode, 'GET',
    'die Vorschau schickt ' + vorschau[0].methode + ' — der Endpunkt erlaubt nur GET (405)')
  assert.ok(vorschau[0].url.includes(OEFFENTLICH),
    `falscher Endpunkt: ${vorschau[0].url}`)
  // Kein POST irgendwohin im Vorschau-Weg.
  assert.deepEqual(aufrufe.filter((a) => a.methode !== 'GET'), [])
})

// ══════════════════════════════════════════════════════════════════════════
// B · Die Vorschau ist danach NICHT leer
// ══════════════════════════════════════════════════════════════════════════

test('BUG-WEB-VORSCHAU: die Antwort des Endpunkts füllt die Vorschau', async () => {
  const aufrufe = []
  const bereiche = await composableLaden(aufrufe)
  const liste = await bereiche.oeffentlichenStandLaden()

  assert.equal(bereiche.oeffentlichFehler.value, '', 'kein Fehlertext in der Vorschau')
  assert.equal(liste.length, 2, 'beide zugestimmten Personen erscheinen')
  assert.deepEqual(liste.map((e) => e.name), ['Anna Muster', 'Bernd Beispiel'])
  assert.deepEqual(liste.map((e) => e.bereich), ['Musik', 'Chor'])
  // Die reaktive Liste ist derselbe Stand (die Vorlage liest sie).
  assert.equal(bereiche.oeffentlich.value.length, 2)
})

test('BUG-WEB-VORSCHAU: die `{ansprechpartner: […]}`-Form wird weiter verkraftet', async () => {
  const aufrufe = []
  const bereiche = await composableLaden(aufrufe)
  const echt = globalThis.fetch
  globalThis.fetch = async (url, optionen) => {
    if (String(url).includes('ansprechpartner')) {
      return new Response(JSON.stringify({ message: { ansprechpartner: stand() } }), {
        status: 200, headers: { 'Content-Type': 'application/json' },
      })
    }
    return echt(url, optionen)
  }
  const liste = await bereiche.oeffentlichenStandLaden()
  assert.equal(liste.length, 2, 'die ältere Rückgabeform bleibt lesbar')
})

// ══════════════════════════════════════════════════════════════════════════
// C · Gegenprobe — der Test sieht den Fehler wirklich
// ══════════════════════════════════════════════════════════════════════════

test('BUG-WEB-VORSCHAU: mit POST (dem alten Fehler) bleibt die Vorschau leer und meldet 405', async () => {
  const aufrufe = []
  const bereiche = await composableLaden(aufrufe, { methodeErzwingen: 'POST' })
  const liste = await bereiche.oeffentlichenStandLaden()

  assert.equal(liste.length, 0, 'POST liefert keine Vorschau — genau der Befund')
  assert.match(bereiche.oeffentlichFehler.value, /POST|405|GET/i,
    `Fehlertext fehlt: ${JSON.stringify(bereiche.oeffentlichFehler.value)}`)
})

// ══════════════════════════════════════════════════════════════════════════
// D · Der Wächter hat etwas zu prüfen (kein leerer Lauf)
// ══════════════════════════════════════════════════════════════════════════

test('BUG-WEB-VORSCHAU: das Inventar führt den Endpunkt wirklich als GET-only', () => {
  const inventar = JSON.parse(readFileSync(
    path.join(FRONTEND, '../backend/src/diakronos_app/frappe_compat/inventar/whitelist.json'),
    'utf8',
  ))
  const eintrag = inventar.eintraege.find(
    (e) => e.name === 'ansprechpartner' && /website/.test(String(e.funktion)),
  )
  assert.ok(eintrag, 'ansprechpartner fehlt im Inventar — Grundlage fehlt')
  assert.deepEqual(eintrag.methoden, ['GET'],
    `ansprechpartner deklariert ${JSON.stringify(eintrag.methoden)} statt ["GET"]`)
})
