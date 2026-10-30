/**
 * WEB-5b · WÄCHTER — keine fest verdrahteten Backend-Pfade mehr in `frontend/src`.
 *
 * BEFUND: Diakronos kann unter einem Präfix laufen (`DIAKRONOS_BASE_PATH`,
 * WEB-5a). Dann liegen API, Anmeldung, Dateien und socket.io unter
 * `{basePath}/…`. Vorher bauten ~30 Dateien ihre Adressen selbst zusammen
 * (`"/api/method/…"`, `"/files/…"`, `"/login"`, `"/logout"`, `"/diakonos"`) —
 * unter dem Präfix landeten alle auf 404 oder auf der Website, die auf `/`
 * liegt.
 *
 * Dieser Test friert den behobenen Zustand ein: ein STRING-LITERAL, das mit
 * einem Backend-Pfad beginnt, darf nur noch in der zentralen Hilfsdatei
 * `src/shared/basis.js` stehen. Überall sonst gilt `mitBasis(...)`,
 * `apiUrl(...)`, `dateiUrl(...)`, `anmeldeUrl(...)`, `socketPfad()` — oder
 * einer der zentralen Helfer (`useApi.js`, `shared/sitzung-pruefen.js`), die
 * die Hilfsdatei benutzen.
 *
 * Was NICHT zählt (bewusst):
 *   - Zeilen, die mit `*`, `//` oder `/*` beginnen (Erklärtexte, in denen
 *     Pfade als Beispiel stehen),
 *   - Bezeichner-Fragmente wie `'#/login'` oder `/diakonos/diakronos`-URLs in
 *     Kommentaren — geprüft wird der ANFANG des Literals.
 *
 * Läuft im Image (backend/Dockerfile, node-Testliste) und lokal per
 * `node --test tests/web5b-praefix.test.mjs`.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync } from 'node:fs'

const WURZEL = new URL('../src/', import.meta.url)

/** Die EINE erlaubte Stelle (zentrale Hilfsdatei, S1). */
const ZENTRALE_DATEI = 'shared/basis.js'

/** Literale, die einen Backend-Pfad beginnen (S1/S4 der Karte). */
const VERBOTEN = ['/api/', '/files/', '/private/files', '/login', '/logout', '/diakonos']

function alleQuellen(verzeichnis = '') {
  const pfad = new URL(verzeichnis, WURZEL)
  const ergebnis = []
  for (const name of readdirSync(pfad)) {
    if (name === 'node_modules') continue
    const kind = new URL(name, pfad)
    if (statSync(kind).isDirectory()) {
      ergebnis.push(...alleQuellen(verzeichnis + name + '/'))
    } else if (/\.(m?js|vue)$/.test(name) && !/\.test\.m?js$/.test(name)) {
      ergebnis.push(verzeichnis + name)
    }
  }
  return ergebnis
}

/** Ist die Zeile Kommentar oder Erklärtext (kein ausführbarer Code)? */
function istKommentar(zeile) {
  const t = zeile.trim()
  return t.startsWith('*') || t.startsWith('//') || t.startsWith('/*')
}

/**
 * Alle Treffer: String-Literale (einfach, doppelt, Backtick), die mit einem
 * verbotenen Pfad beginnen — plus Template-Literale wie `` `/api/${x}` ``.
 * Ausgenommen ist ausdrücklich nur der Text INNERHALB eines `mitBasis(...)`
 * o. ä. — dort ist der Pfad ja gerade gewollt. Das prüft der Test, indem er
 * die Zeile nach dem Aufruf-Kontext abschneidet.
 */
function trefferIn(text, datei) {
  const raus = []
  text.split('\n').forEach((zeile, i) => {
    if (istKommentar(zeile)) return
    for (const pfad of VERBOTEN) {
      // Literal-Grenze: '…' "…" `…` — der Pfad muss DIREKT am Anfang stehen.
      const literale = [...zeile.matchAll(/(['"`])([^'"`]*)\1/g)]
      for (const l of literale) {
        const wert = l[2]
        if (!wert.startsWith(pfad)) continue
        // Steht das Literal als Argument von mitBasis(...)/anmeldeUrl(...)? Dann
        // ist der Pfad ausdrücklich gewollt (die Hilfsdatei setzt den Präfix).
        const davor = zeile.slice(0, l.index)
        if (/(?:mitBasis|anmeldeUrl)\s*\(\s*$/.test(davor)) continue
        raus.push(`${datei}:${i + 1}  →  ${zeile.trim()}`)
        break
      }
      if (raus.length && raus[raus.length - 1].startsWith(datei + ':')) break
    }
  })
  return raus
}

test('WEB-5b · S1/S4: kein fest verdrahteter Backend-Pfad ausserhalb der zentralen Hilfsdatei', () => {
  const treffer = []
  for (const datei of alleQuellen()) {
    if (datei === ZENTRALE_DATEI) continue
    treffer.push(...trefferIn(readFileSync(new URL(datei, WURZEL), 'utf8'), datei))
  }
  assert.deepEqual(
    treffer,
    [],
    'Backend-Adressen nur noch über src/shared/basis.js bauen '
      + '(mitBasis/apiUrl/dateiUrl/anmeldeUrl/socketPfad) oder über useApi.js:\n'
      + treffer.join('\n'),
  )
})

test('WEB-5b · S1: die zentrale Hilfsdatei hat genau EINE Präfix-Quelle', () => {
  const text = readFileSync(new URL(ZENTRALE_DATEI, WURZEL), 'utf8')
  const leser = text.match(/__DIakonosBOOT\?\.basePath/g) || []
  assert.equal(leser.length, 1, 'basePath darf nur an EINER Stelle gelesen werden (basisPfad())')
  for (const name of ['mitBasis', 'apiUrl', 'dateiUrl', 'anmeldeUrl', 'socketPfad', 'basisPfad']) {
    assert.match(text, new RegExp(`export function ${name}\\(`), `${name}() fehlt`)
  }
})

test('WEB-5b · S2: Vite-Assets relativ gebaut (kein Präfix im Build)', () => {
  const config = readFileSync(new URL('../vite.config.mjs', import.meta.url), 'utf8')
  // `base: './'` erzeugt relative Asset-Adressen im index.html — der Server
  // setzt den Präfix, das Bundle kennt ihn nicht. Ein absoluter Pfad hier
  // würde einen zweiten Build je Präfix erzwingen (Karte: ausdrücklich nicht).
  assert.match(config, /base:\s*'\.\/'/, "vite base muss './' sein (Laufzeit-Präfix statt Build-Präfix)")
  assert.doesNotMatch(config, /base:\s*'\/diakonos/, 'kein fest verdrahteter Asset-Präfix im Build')
})

test('WEB-5b · S3: Hash-Router bleibt unverändert (kein Präfix im Hash)', () => {
  const router = readFileSync(new URL('diakonos/router.js', WURZEL), 'utf8')
  assert.doesNotMatch(
    router,
    /mitBasis|basisPfad|basePath/,
    'der Hash-Router bekommt KEINEN Präfix (Hash ist relativ zur Seite)',
  )
})
