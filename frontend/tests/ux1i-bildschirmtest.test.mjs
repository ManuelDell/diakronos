/**
 * UX1i · Wächter: der automatische Bildschirmtest prüft wirklich, was die
 * UI-Release-Checkliste verlangt (Kontrast, 44 px, Primärknöpfe, Graustufen,
 * Überlauf bei 375 px, Konsolen-/Netzwerkfehler).
 *
 * Geprüft wird die echte Werkzeugdatei `tools/demo/uiux-pruefung.py` (kein
 * Duplikat) — sie liegt AUSSERHALB von frontend/ und kommt über die
 * COPY-Zeile in backend/Dockerfile in diesen Build-Stage (Regel 13).
 *
 * Die PYTHON-Aufrufe laufen im Image (Frontend-Stage) und im Repo, sofern
 * `python3` da ist; fehlt der Dolmetscher, entfällt genau der betroffene
 * Test mit Begründung. Die Quelltext-Prüfungen laufen überall.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { execFileSync } from 'node:child_process'

/** Im REPO liegt die Datei unter <wurzel>/tools/, im IMAGE unter /tools/. */
function werkzeugPfad() {
  for (const pfad of [
    new URL('../../tools/demo/uiux-pruefung.py', import.meta.url),
    new URL('/tools/demo/uiux-pruefung.py', import.meta.url),
  ]) {
    try {
      readFileSync(pfad)
      return pfad
    } catch {
      // nächster Ort
    }
  }
  throw new Error('tools/demo/uiux-pruefung.py weder im Repo noch unter /tools')
}

const WERKZEUG = werkzeugPfad()
const QUELLE = readFileSync(WERKZEUG, 'utf8')

/** Ist ein Python-Dolmetscher da? (Im Image: ja.) */
function pythonDa() {
  try {
    execFileSync('python3', ['-c', 'print(1)'], { encoding: 'utf8' })
    return true
  } catch {
    return false
  }
}
const PYTHON_DA = pythonDa()
// ★ SICHTBAR übersprungen: die Zahlen dieses Waechters sind damit im
// node:22-alpine-Stage NICHT geprüft — sie weist der Messlauf gegen den
// Wegwerf-Stack nach (siehe Kopf der Datei).
const OHNE_PYTHON = PYTHON_DA
  ? false
  : '★ UNGEPRÜFT ohne python3 (node:22-alpine im Image) — Zahlen weist der Messlauf nach'

/**
 * Rechnet im ECHTEN Werkzeugmodul, damit eine Änderung der Formel auffällt.
 * Die Datei importiert `playwright` auf Modulebene; im Frontend-Stage gibt es
 * das Paket nicht, deshalb wird vorher ein leerer Stellvertreter eingesetzt.
 */
function python(jsonAusdruck) {
  const skript = `
import sys, types, importlib.util, json
stelle = types.ModuleType("playwright.sync_api")
stelle.sync_playwright = lambda: None
paket = types.ModuleType("playwright")
paket.sync_api = stelle
sys.modules["playwright"] = paket
sys.modules["playwright.sync_api"] = stelle
spec = importlib.util.spec_from_file_location("w", sys.argv[1])
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
print(json.dumps(${jsonAusdruck}))
`
  return JSON.parse(execFileSync('python3', ['-c', skript, WERKZEUG.pathname], { encoding: 'utf8' }).trim())
}

// ── 1 · Grenzen der Checkliste ─────────────────────────────────────────────
test('UX1i · Grenzen des Bildschirmtests sind die der Checkliste', { skip: OHNE_PYTHON }, () => {
  const g = python('{"kontrast": m.KONTRAST_MIN, "treffer": m.TREFFER_MIN, "ueberlauf": m.UEBERLAUF_BREITE}')
  assert.equal(g.kontrast, 4.5, 'Kontrast-Mindestwert 4,5:1 (Prinzip Ä4)')
  assert.equal(g.treffer, 44, 'Trefferfläche 44 px mobil (Prinzip K4)')
  assert.equal(g.ueberlauf, 375, 'Überlauf wird bei 375 px Breite gemessen')
})

test('UX1i · die zwei Ansichten sind Desktop 1440 und Mobil 390 mit Touch', { skip: OHNE_PYTHON }, () => {
  const a = python('[[x[0], x[1], x[2], x[3]] for x in m.ANSICHTEN]')
  assert.deepEqual(a.find((x) => x[0] === 'desktop'), ['desktop', 1440, 900, false])
  assert.deepEqual(a.find((x) => x[0] === 'mobil'), ['mobil', 390, 844, true],
    'mobil 390 px breit MIT hasTouch')
  assert.deepEqual(python('list(m.THEMES)'), ['hell', 'dunkel'], 'hell UND dunkel')
})

// ── 2 · Kontrastformel nach WCAG 2.x ───────────────────────────────────────
test('UX1i · Kontrastformel entspricht WCAG (Weiß/Schwarz 21:1, gleich 1:1)', { skip: OHNE_PYTHON }, () => {
  const w = python(`[
    m.kontrast((255, 255, 255, 1), (0, 0, 0, 1)),
    m.kontrast((255, 255, 255, 1), (255, 255, 255, 1)),
    m.kontrast((118, 118, 118, 1), (255, 255, 255, 1)),
  ]`)
  assert.ok(Math.abs(w[0] - 21) < 0.01, 'Weiß auf Schwarz = 21:1')
  assert.equal(w[1], 1, 'gleiche Farbe = 1:1')
  // #767676 auf Weiß ist der bekannte Grenzfall: 4,54:1 (knapp über 4,5).
  assert.ok(Math.abs(w[2] - 4.54) < 0.02, `#767676 auf Weiß ≈ 4,54:1, war ${w[2]}`)
})

test('UX1i · Farbauswertung und Durchsichtigkeiten werden zusammengerechnet', { skip: OHNE_PYTHON }, () => {
  const r = python(`[
    list(m.zerlege('rgb(18, 24, 58)')),
    list(m.zerlege('rgba(0, 0, 0, 0.25)')),
    m.zerlege(''),
    [round(x, 2) for x in m.ueber((0, 0, 0, 0.5), (255, 255, 255, 1))],
  ]`)
  assert.deepEqual(r[0], [18, 24, 58, 1])
  assert.deepEqual(r[1], [0, 0, 0, 0.25], 'Alpha wird mitgelesen')
  assert.equal(r[2], null, 'was kein rgb/rgba ist, wird nicht geraten')
  assert.deepEqual(r[3], [127.5, 127.5, 127.5, 1], '50 % Schwarz über Weiß = mittleres Grau')
})

test('UX1i · Schrift über durchsichtiger Fläche wird gegen den echten Grund gerechnet', { skip: OHNE_PYTHON }, () => {
  const k = python(`[
    m.text_kontrast((21, 24, 42, 1), [(201, 149, 47, 0.10)]),
    m.text_kontrast((21, 24, 42, 1), []),
    m.verstoesse(4.49),
    m.verstoesse(4.5),
  ]`)
  assert.ok(k[0] > 14 && k[0] < 20, `dunkle Schrift auf getönter Fläche ≈ 15:1, war ${k[0]}`)
  assert.ok(k[1] > k[0], 'ohne Fläche zählt Weiß — etwas heller als die getönte Fläche')
  assert.deepEqual(k[2], [4.49], 'unter 4,5 ist ein Verstoß')
  assert.deepEqual(k[3], [], 'genau 4,5 gilt als bestanden')
})

// ── 3 · Werte aus tokens.css (nachgerechnet) ───────────────────────────────
test('UX1i · Tokens der App: --muted ist in BEIDEN Themes lesbar (>= 4,5:1)', { skip: OHNE_PYTHON }, () => {
  // Werte aus frontend/src/diakonos/tokens.css: hell --surface #ffffff,
  // --muted --dk-warm-500 #5b6178; dunkel --surface --dk-ink-2 #111631,
  // --muted --dk-ink-text-muted #9ba3c1.
  const r = python(`[
    m.text_kontrast((0x5b, 0x61, 0x78, 1), [(255, 255, 255, 1)]),
    m.text_kontrast((0x9b, 0xa3, 0xc1, 1), [(17, 22, 49, 1)]),
    m.text_kontrast((0x9a, 0x9a, 0xa0, 1), [(255, 255, 255, 1)]),
  ]`)
  assert.ok(r[0] >= 4.5, `--muted hell auf --surface: ${r[0]}:1`)
  assert.ok(r[1] >= 4.5, `--muted dunkel auf --surface: ${r[1]}:1`)
  assert.ok(r[2] < 4.5, `zu helles Grau auf Weiß bleibt ein Verstoß (${r[2]}:1)`)
})

// ── 4 · Seitenliste (Quelltext) ────────────────────────────────────────────
test('UX1i · alle Hauptseiten der Karte stehen in der Prüfliste', () => {
  const liste = QUELLE.match(/SEITEN[^=]*=\s*\[([\s\S]*?)\n\]/)[1]
  const namen = [...liste.matchAll(/\("([a-z0-9-]+)"/g)].map((m) => m[1])
  for (const pflicht of ['uebersicht', 'mitglieder', 'kalender', 'gruppen', 'dienstplan',
    'plaene', 'lieder', 'beitraege', 'wiki', 'ressourcen', 'einstellungen', 'website', 'anmeldung']) {
    assert.ok(namen.includes(pflicht), `Seite „${pflicht}“ fehlt in SEITEN`)
  }
  assert.ok(namen.filter((s) => s.startsWith('einstellungen')).length >= 4,
    'Einstellungen-Unterseiten sind einzeln aufgeführt (jede hat eine eigene Adresse)')
  assert.match(liste, /\("anmeldung",\s*None,\s*None\)/, 'Anmeldeseite wird OHNE Sitzung geladen')
})

// ── 5 · alle sechs Prüfpunkte in Messung, Bericht und Abbruch ──────────────
test('UX1i · alle sechs Prüfpunkte werden gemessen, berichtet und brechen ab', () => {
  const skript = QUELLE.match(/MESS_SKRIPT = r"""([\s\S]*?)"""/)[1]
  assert.match(skript, /kontrast/, '(1) Kontrast wird berechnet')
  assert.match(skript, /getComputedStyle/, 'aus den BERECHNETEN Stilen, nicht aus dem Quelltext')
  assert.match(skript, /zu_klein/, '(2) Trefferflächen unter der Mindestgröße werden gesammelt')
  assert.match(skript, /dk-ui-btn--primary/, '(3) sichtbare Primärknöpfe werden gezählt')
  assert.match(skript, /scrollWidth/, '(5) horizontaler Überlauf')
  assert.match(QUELLE, /screenshot_graustufen/, '(4) Graustufen-Screenshot')
  assert.match(QUELLE, /Seiten ohne Messung/, 'Seiten ohne Messung stehen im Bericht')
  assert.match(QUELLE, /netzwerkfehler/, '(6) Netzwerkfehler werden gesammelt')
  assert.match(QUELLE, /konsolenfehler/, '(6) Konsolenfehler werden gesammelt')

  const verletzt = QUELLE.match(/def verletzt\(e\):[\s\S]*?\n\n/)[0]
  for (const punkt of ['kontrast', 'treffer_regel', 'primaer_anzahl', 'ueberlauf',
    'ueberlauf_375', 'konsolenfehler', 'netzwerkfehler']) {
    assert.ok(verletzt.includes(punkt), `Abbruchkriterium prüft „${punkt}“`)
  }
  assert.match(QUELLE, /return 1 if daten\["zusammenfassung"\]\["verletzt"\] else 0/,
    'Rückgabewert 1 bei einem Befund (CI-tauglich)')
})

test('UX1i · Trefferflächen werden nur mobil als Verstoß gewertet, aber immer gemessen', () => {
  const block = QUELLE.match(/if hastouch:\n([\s\S]*?)else:\n([\s\S]*?)\n\n/)[0]
  assert.match(block, /len\(messung\["treffer"\]\["zu_klein"\]\)/, 'mobil zählt jeder Treffer unter 44 px')
  assert.match(block, /nur mobil geprüft/, 'Desktop meldet nur einen Hinweis')
})

// ── 6 · das Werkzeug liest nur ─────────────────────────────────────────────
test('UX1i · das Werkzeug verändert nichts (keine schreibenden Anfragen)', () => {
  // Die Anmeldung selbst ist ein POST — sie läuft über das getippte Formular
  // der App, nicht über eine schreibende API-Anfrage des Werkzeugs.
  assert.doesNotMatch(QUELLE, /request\.(post|put|patch|delete)\(/, 'keine schreibenden API-Aufrufe')
  assert.doesNotMatch(QUELLE, /method:\s*['"](POST|PUT|PATCH|DELETE)/i, 'kein fetch mit schreibender Methode')
  assert.match(QUELLE, /LIEST NUR/, 'die Datei sagt selbst: sie liest nur (Anmeldung ausgenommen)')
})

// ── 7 · Docker-Regel 13: der Build-Stage bekommt die Datei ─────────────────
test('UX1i · backend/Dockerfile kopiert das Werkzeug in den Frontend-Stage', () => {
  // Im Frontend-Stage des Images gibt es backend/ nicht — die COPY-Zeile
  // weist der Abnahmelauf `docker build --target frontend` nach (Regel 13).
  let dockerfile
  try {
    dockerfile = readFileSync(new URL('../../backend/Dockerfile', import.meta.url), 'utf8')
  } catch {
    return
  }
  assert.match(dockerfile, /COPY tools\/demo\/uiux-pruefung\.py \/tools\/demo\/uiux-pruefung\.py/,
    'Regel 13: Datei ausserhalb von frontend/ braucht eine COPY-Zeile')
})
