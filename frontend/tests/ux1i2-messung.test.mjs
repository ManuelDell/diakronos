/**
 * UX1i2 · Wächter: die 44-px- und Kontrast-Messung meldet wirklich, was sie
 * melden soll.
 *
 * Anlass (Befund 2026-11-04): der Bericht meldete „36 von 36 mobilen Ansichten
 * ohne Verstoß (0 Stellen)“, obwohl auf `#/personen/liste` mindestens acht
 * sichtbare `button`/`a[href]` nur 28 px groß sind. Ursache: `page.evaluate`
 * bekam das Mess-Skript mit ZWEI Einzelparametern; Playwright legt den
 * übergebenen Wert dann nur in den ERSTEN Parameter, der zweite ist
 * `undefined` — jeder Vergleich `< minTreffer` war damit falsch, und der Lauf
 * meldete still 0 Befunde.
 *
 * Geprüft wird die echte Werkzeugdatei `tools/demo/uiux-pruefung.py` (kein
 * Duplikat), sie liegt AUSSERHALB von frontend/ und kommt über die COPY-Zeile
 * in backend/Dockerfile in den Build-Stage (Regel 13).
 *
 * Zwei Ebenen:
 *   A) Quelltext-Prüfungen — laufen überall (auch ohne python3/Chromium).
 *   B) Messprobe im Browser — läuft nur, wenn python3, playwright und ein
 *      Chromium da sind; sonst SICHTBAR übersprungen. Im Image-Build
 *      (node:22-alpine) ist beides nicht vorhanden, dort greift A).
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { execFileSync } from 'node:child_process'

/** Im REPO liegt die Datei unter <wurzel>/tools/, im IMAGE unter /tools/. */
function werkzeugPfad(datei) {
  for (const pfad of [
    new URL(`../../tools/demo/${datei}`, import.meta.url),
    new URL(`/tools/demo/${datei}`, import.meta.url),
  ]) {
    try {
      readFileSync(pfad)
      return pfad
    } catch {
      // nächster Ort
    }
  }
  return null
}

const WERKZEUG = werkzeugPfad('uiux-pruefung.py')
if (!WERKZEUG) throw new Error('tools/demo/uiux-pruefung.py weder im Repo noch unter /tools')
const QUELLE = readFileSync(WERKZEUG, 'utf8')
const PROBE = werkzeugPfad('ux1i2-probe.py')

/** Ist ein Python-Dolmetscher da? */
function pythonDa() {
  try {
    execFileSync('python3', ['-c', 'print(1)'], { encoding: 'utf8' })
    return true
  } catch {
    return false
  }
}
const PYTHON_DA = pythonDa()

/** Sind playwright + Chromium da? (Im Image-Build: nein.) */
function browserDa() {
  if (!PYTHON_DA || !PROBE) return false
  try {
    execFileSync('python3', ['-c',
      'import playwright.sync_api; playwright.sync_api.sync_playwright().start().chromium.launch(args=["--no-sandbox"]).close()'],
    { encoding: 'utf8', timeout: 120000, stdio: 'ignore' })
    return true
  } catch {
    return false
  }
}
const BROWSER_DA = browserDa()
const OHNE_BROWSER = BROWSER_DA
  ? false
  : '★ UNGEPRÜFT ohne python3/playwright/Chromium (node:22-alpine im Image) — Messlauf weist die Zahlen nach'

// ── A · Quelltext: die Parameter müssen als ARRAY entstrukturiert werden ────
test('UX1i2 · Mess-Skript holt seine Grenzwerte aus EINEM Array (nicht aus zwei Parametern)', () => {
  const skript = QUELLE.match(/MESS_SKRIPT = r"""([\s\S]*?)"""/)[1]
  const kopf = skript.split('\n').find((z) => z.includes('=>'))
  assert.match(kopf, /^\s*\(\[\s*minKontrast\s*,\s*minTreffer\s*\]\)\s*=>/,
    'Signatur muss `([minKontrast, minTreffer]) =>` sein — zwei Einzelparameter ' +
    'bekommen bei playwright nur den ERSTEN Wert (Messfehler UX1i2)')
  // Gegenprobe: genau so darf es NICHT aussehen.
  assert.doesNotMatch(skript, /^\(minKontrast, minTreffer\)/m,
    '`(minKontrast, minTreffer) =>` liefert `undefined` für den zweiten Wert')
})

test('UX1i2 · Zähl-Skript (Überlauf 375 px) hat dieselbe Signatur', () => {
  const skript = QUELLE.match(/ZAEHL_SKRIPT = r"""([\s\S]*?)"""/)[1]
  const kopf = skript.split('\n').find((z) => z.includes('=>'))
  assert.match(kopf, /^\s*\(\[\s*minTreffer\s*\]\)\s*=>/, 'auch hier ein Array, sonst dasselbe Problem')
})

test('UX1i2 · beide Grenzwerte gehen als ein Array in den Browser', () => {
  const aufrufe = [...QUELLE.matchAll(/page\.evaluate\(\s*(MESS_SKRIPT|ZAEHL_SKRIPT)\s*,\s*(\[[^\]]*\])/g)]
  assert.equal(aufrufe.length, 2, 'genau zwei Messaufrufe (MESS_SKRIPT + ZAEHL_SKRIPT)')
  const mess = aufrufe.find((a) => a[1] === 'MESS_SKRIPT')[2]
  assert.match(mess, /KONTRAST_MIN/, 'Kontrastgrenze wird übergeben')
  assert.match(mess, /TREFFER_MIN/, 'Treffergrenze wird übergeben')
})

test('UX1i2 · die Messung prüft selbst, ob ihre Grenzen im Browser angekommen sind', () => {
  assert.match(QUELLE, /grenze: minKontrast/, 'Kontrastgrenze wird zurückgemeldet')
  assert.match(QUELLE, /grenze: minTreffer/, 'Treffergrenze wird zurückgemeldet')
  const block = QUELLE.match(/messung = page\.evaluate\(MESS_SKRIPT[\s\S]*?ergebnis\.update\(/)[0]
  assert.match(block, /!= KONTRAST_MIN/, 'fehlende Kontrastgrenze bricht laut ab')
  assert.match(block, /!= TREFFER_MIN/, 'fehlende Treffergrenze bricht laut ab')
  assert.match(block, /raise RuntimeError/, 'kein stiller „0 Verstöße“-Lauf mehr')
})

// ── A · Mobil-Kontext ──────────────────────────────────────────────────────
test('UX1i2 · der Mobil-Kontext ist wirklich mobil (is_mobile)', () => {
  const block = QUELLE.match(/def neuer_kontext[\s\S]*?return ctx/)[0]
  assert.match(block, /has_touch=hastouch/, 'Touch bleibt gesetzt')
  assert.match(block, /is_mobile=hastouch/, 'is_mobile folgt der Touch-Ansicht (nicht fest false)')
  assert.doesNotMatch(block, /is_mobile=False/, 'fest `False` war der Befund')
})

// ── A · Gegenprobe-Werkzeug + Dockerfile (Regel 13) ────────────────────────
test('UX1i2 · die Gegenprobe steht bereit und prüft 44 px UND Kontrast', () => {
  assert.ok(PROBE, 'tools/demo/ux1i2-probe.py fehlt')
  const probe = readFileSync(PROBE, 'utf8')
  assert.match(probe, /knopf-klein/, 'Testseite mit bekannt 28-px-Knopf')
  assert.match(probe, /--falsch/, 'der alte Fehler ist nachstellbar (rot -> grün belegbar)')
  assert.match(probe, /SOLL_IDS_KLEIN/, 'Soll-Liste der zu kleinen Flächen')
  assert.match(probe, /SOLL_ID_KONTRAST/, 'Soll-Liste der Kontrastverstöße (F2)')
  assert.match(probe, /neuer_kontext/, 'misst über den echten Mobil-Kontext')
})

test('UX1i2 · backend/Dockerfile kopiert die Gegenprobe in den Frontend-Stage', () => {
  let dockerfile
  let testliste
  try {
    dockerfile = readFileSync(new URL('../../backend/Dockerfile', import.meta.url), 'utf8')
    // FE-TEST-1: die Muster stehen in frontend/tests/testliste.txt.
    testliste = readFileSync(new URL('./testliste.txt', import.meta.url), 'utf8')
  } catch {
    return // im Image-Build liegt die Dockerfile nicht im Stage (Regel 13: Nachweis per docker build)
  }
  assert.match(dockerfile, /COPY tools\/demo\/ux1i2-probe\.py \/tools\/demo\/ux1i2-probe\.py/,
    'Regel 13: Datei ausserhalb von frontend/ braucht eine COPY-Zeile')
  assert.match(dockerfile, /^ARG NODE_TESTLISTE=tests\/testliste\.txt$/m,
    'backend/Dockerfile liest die Muster nicht aus tests/testliste.txt')
  assert.match(testliste, /^tests\/ux1i2-\*\.test\.mjs$/m, 'Testdatei steht in der Frontend-Testliste')
})

// ── B · Messprobe im echten Browser (rot -> grün) ──────────────────────────
test('UX1i2 · Messung findet bekannte 28-px-Flächen und bekannten Kontrastfehler', { skip: OHNE_BROWSER }, () => {
  // Die Probe ist der Nachweis: sie setzt eine Seite mit 2× 28 px, 1× 44 px,
  // 1 hellem Absatz und vergleicht Soll gegen Ist. Exit 0 = genau die
  // bekannten Stellen wurden gemeldet.
  const ausgabe = execFileSync('python3', [PROBE.pathname], { encoding: 'utf8', timeout: 180000 })
  assert.match(ausgabe, /ERGEBNIS: GRÜN/, `Probe nicht grün:\n${ausgabe}`)
  assert.match(ausgabe, /zu klein \(<44 px\)\s*=\s*2/, 'genau die zwei 28-px-Flächen')
  assert.match(ausgabe, /Kontrast < 4,5:1\s*=\s*1/, 'genau der eine helle Absatz (F2)')
})

test('UX1i2 · der alte Aufruffehler wird als Messfehler erkannt (Gegenprobe rot)', { skip: OHNE_BROWSER }, () => {
  let ausgabe = ''
  let exit = 0
  try {
    ausgabe = execFileSync('python3', [PROBE.pathname, '--falsch'], { encoding: 'utf8', timeout: 180000 })
  } catch (fehler) {
    exit = fehler.status ?? 1
    ausgabe = fehler.stdout ?? ''
  }
  assert.notEqual(exit, 0, 'mit zwei Einzelparametern MUSS die Probe rot werden')
  assert.match(ausgabe, /ERGEBNIS: ROT/, 'die Probe benennt den Messfehler')
  assert.match(ausgabe, /zu kleine Flächen: \[\]/, 'so sah der Fehler aus: 0 Stellen')
})
