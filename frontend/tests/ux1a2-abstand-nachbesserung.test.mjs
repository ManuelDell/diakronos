/**
 * UX1a2 — Wächter: Nachbesserung der Abstands-Tokens.
 *
 * Sieben Prüfungen, je eine je Befund der Karte:
 *
 *   F1  Die Zuordnung der alten Skala ist EINDEUTIG und wird EINMAL
 *       angewandt. Der Umsteller (`tools/ux1a2-zuordnung.py`) steht hier mit
 *       seiner Zuordnungstabelle; die Probe zeigt, dass eine Kette
 *       (alt --sp-6 → --sp-5 → --sp-alt-20) NICHT passiert. Zusätzlich:
 *       `--sp-alt-20` steht an keiner Stelle, die in `main` 24 oder 32 px war
 *       (Stichprobe der Karten-Dateien: Assistent, AssistentSchritte,
 *       DkPageHeader, DkEmpty, seiten.css).
 *
 *   F2  Die ON-3b/ON-4-Zeilen (AnmeldeMarke, EinrichtungsLeiste, LogoMarke,
 *       MitgliederLeerzustand) tragen die 24/32-px-Maße auf der neuen Skala
 *       (--sp-5/--sp-6) — nicht --sp-alt-20.
 *
 *   F3  `--gap` ist 12 px (= --sp-3), nicht 8.
 *
 *   F4  `--sp-alt-20` ist EINGEFROREN: der Test zählt `var(--sp-alt-20)` je
 *       Datei (ausser der Quelle `tokens.css`, die den Token DEFINIERT und
 *       darum auch im Kommentar nennt); der Bestand darf nur schrumpfen,
 *       neue Dateien fangen bei 0 an.
 *
 *   F5  Der Wächter (`tools/abstand-bestand.mjs`) sieht die Langformen,
 *       negative Werte, `.5rem` und `:style`-Bindungen (Gegenproben).
 *
 *   F6  Der Drift-Test gegen `gestaltung/tokens.py` ist scharf: er wird rot,
 *       sobald die Datei existiert und abweicht (Probe an einem Wegwerf-
 *       Verzeichnis über `UX1A_BACKEND`).
 *
 *   T   Die Werkzeuge selbst: die Zuordnung ist eine einmalige Abbildung,
 *       die px-Werte bleiben gleich (Selbstprobe des Prüfskripts).
 *
 * Läuft wie die übrigen Frontend-Tests im Image-Build (node --test, Regel 13).
 * Braucht KEINE Dateien ausserhalb von `frontend/` — die F6-Probe legt ihr
 * Beispiel selbst in einem temporären Verzeichnis an.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdtempSync, mkdirSync, readFileSync, readdirSync, statSync, writeFileSync, rmSync } from 'node:fs'
import { execFileSync } from 'node:child_process'
import os from 'node:os'
import path from 'node:path'
import { FRONTEND, fundstellen, wertIstFest } from '../tools/abstand-bestand.mjs'

const lies = (rel) => readFileSync(path.join(FRONTEND, rel), 'utf8')

/** Der Umsteller (Python) — hier nur als Datei gelesen, nicht ausgeführt. */
const UMSTELLER = path.join(FRONTEND, 'tools', 'ux1a2-zuordnung.py')

/** Erwartete Zuordnung der Karte (F1). */
const ZUORDNUNG = {
  '--sp-5': '--sp-alt-20',
  '--sp-6': '--sp-5',
  '--sp-8': '--sp-6',
}

/** Alle `style`-Blöcke einer .vue-Datei (oder die ganze Datei bei .css). */
function styleText(quelle) {
  const m = /<style[^>]*>([\s\S]*?)<\/style>/.exec(quelle)
  return m ? m[1] : quelle
}

// ── F1 · Die Zuordnung ist eindeutig und wird EINMAL angewandt ─────────────
test('F1: der Umsteller bildet alt --sp-6/--sp-8 auf 24/32 ab, nicht auf 20', () => {
  const quelle = readFileSync(UMSTELLER, 'utf8')
  for (const [alt, neu] of Object.entries(ZUORDNUNG)) {
    assert.match(
      quelle,
      new RegExp(`'${alt}':\\s*'${neu}'`),
      `Zuordnung ${alt} → ${neu} fehlt im Umsteller`,
    )
  }
  // Die px-Tabellen müssen beide Skalen führen — sonst vergleicht das
  // Prüfskript Äpfel mit Birnen.
  assert.match(quelle, /ALT_PX\s*=\s*\{[^}]*'sp-6': 24/, 'ALT_PX nennt --sp-6 nicht mit 24')
  assert.match(quelle, /NEU_PX\s*=\s*\{[^}]*'sp-5': 24/, 'NEU_PX nennt --sp-5 nicht mit 24')
  assert.match(quelle, /NEU_PX\s*=\s*\{[^}]*'sp-6': 32/, 'NEU_PX nennt --sp-6 nicht mit 32')
})

test('F1: der Umsteller ersetzt über EINE RegExp mit Funktionsersatz (keine Kette)', () => {
  const quelle = readFileSync(UMSTELLER, 'utf8')
  assert.match(
    quelle,
    /return TOKEN\.sub\(\s*lambda m: ZUORDNUNG\.get\(m\.group\(0\)/,
    'kein gleichzeitiger Funktionsersatz gefunden — dann wäre es wieder eine Kette',
  )
  // Kein hintereinander geschaltetes `.replace('--sp-6', '--sp-5')`-Muster.
  assert.doesNotMatch(
    quelle,
    /\.replace\(\s*['"]--sp-[568]['"]\s*,\s*['"]--sp/,
    'Ketten-Ersetzung per .replace(...) gefunden — genau der Fehler aus d3568d18',
  )
})

test('F1: die Karten-Dateien tragen die 24/32-px-Maße auf der Skala, nicht bei --sp-alt-20', () => {
  // Je Datei: was in `main` 24 bzw. 32 px war, muss jetzt --sp-5 bzw. --sp-6
  // sein. Die Stichprobe nennt genau die Zeilen aus der Karte.
  const faelle = [
    // [Datei, Zeilenmuster, erwarteter Token, Klartext]
    ['src/diakonos/components/einrichtung/AssistentSchritte.vue', /\.assistent-punkt \{[^}]*padding-bottom:\s*var\(([\w-]+)\)/, 'sp-5', 'padding-bottom war --sp-6 (24)'],
    ['src/diakonos/components/einrichtung/AssistentSchritte.vue', /bottom:\s*var\(([\w-]+)\);/, 'sp-5', 'bottom war --sp-6 (24)'],
    ['src/diakonos/components/ui/DkPageHeader.vue', /min-height:\s*calc\(var\(([\w-]+)\) \+ var\(--sp-2\)\)/, 'sp-6', 'min-height war 32 + 8'],
    ['src/diakonos/components/ui/DkEmpty.vue', /\.dk-ui-empty \{[^}]*padding:\s*var\(([\w-]+)\) var\(([\w-]+)\)/, 'sp-6', 'padding oben war --sp-8 (32)'],
  ]
  for (const [datei, muster, soll, klartext] of faelle) {
    const css = styleText(lies(datei))
    const m = muster.exec(css)
    assert.ok(m, `${datei}: Muster nicht gefunden (${klartext})`)
    // Die Muster fangen den Namen MIT Präfix (`--sp-5`) — verglichen wird ohne.
    const gefunden = [...m.slice(1)].filter(Boolean).map((g) => g.replace(/^--/, ''))
    assert.ok(
      gefunden.includes(soll),
      `${datei}: ${klartext} — erwartet --${soll}, gefunden ${gefunden.map((g) => '--' + g).join(', ')}`,
    )
    assert.ok(
      !gefunden.includes('sp-alt-20'),
      `${datei}: ${klartext} liegt wieder bei --sp-alt-20 (20 px) — Kettenfehler aus d3568d18`,
    )
  }
})

test('F1: seiten.css addiert auf die 32-px-Stufe (--sp-6), nicht auf 20', () => {
  const css = lies('src/ssot/seiten.css')
  // `width: calc(var(--sp-N) + var(--sp-1))` beim Monogramm (main: --sp-8 = 32).
  const monogramm = /\.dk-monogramm \{[^}]*width:\s*calc\(var\(--([\w-]+)\) \+ var\(--sp-1\)\)/.exec(css)
  assert.ok(monogramm, '.dk-monogramm width nicht gefunden')
  assert.equal(monogramm[1], 'sp-6', `Monogramm-Breite: erwartet --sp-6 (32+4), ist --${monogramm[1]}`)
})

// ── F2 · Die per Rebase gekommenen Zeilen sind umgemappt ───────────────────
test('F2: die ON-3b/ON-4-Dateien tragen ihre Maße auf der Skala', () => {
  const faelle = [
    // AnmeldeMarke.vue:48-52 (margin-bottom war --sp-6 = 24) und das Bildmaß
    // (--sp-8 = 32, plus --sp-2 = 8).
    ['src/diakonos/components/einrichtung/AnmeldeMarke.vue', /\.dk-markenseite \{[^}]*margin-bottom:\s*var\(--([\w-]+)\)/, 'sp-5'],
    ['src/diakonos/components/einrichtung/AnmeldeMarke.vue', /\.dk-markenseite-bild \{[^}]*width:\s*calc\(var\(([\w-]+)\) \+ var\(--sp-2\)\)/, 'sp-6'],
    // EinrichtungsLeiste.vue:78-79 (Zeichen war --sp-6 = 24)
    ['src/diakonos/components/einrichtung/EinrichtungsLeiste.vue', /\.dk-einrichtungs-leiste-zeichen \{[^}]*width:\s*var\(([\w-]+)\)/, 'sp-5'],
    // LogoMarke.vue:47-51 (--sm war --sp-6 = 24, --md war --sp-8 = 32, --lg 32+8)
    ['src/diakonos/components/einrichtung/LogoMarke.vue', /\.dk-logo-marke--sm \{[^}]*width:\s*var\(([\w-]+)\)/, 'sp-5'],
    ['src/diakonos/components/einrichtung/LogoMarke.vue', /\.dk-logo-marke--md \{[^}]*width:\s*var\(([\w-]+)\)/, 'sp-6'],
    ['src/diakonos/components/einrichtung/LogoMarke.vue', /\.dk-logo-marke--lg \{[^}]*width:\s*calc\(var\(([\w-]+)\) \+ var\(--sp-2\)\)/, 'sp-6'],
    // MitgliederLeerzustand.vue:65-72 (padding war --sp-8/--sp-6, Symbol 32+32+8)
    ['src/diakonos/components/einrichtung/MitgliederLeerzustand.vue', /\.dk-ui-empty \{[^}]*padding:\s*var\(([\w-]+)\) var\(([\w-]+)\)/, 'sp-6'],
    ['src/diakonos/components/einrichtung/MitgliederLeerzustand.vue', /\.dk-ui-empty-icon \{[^}]*width:\s*calc\(var\(([\w-]+)\) \+ var\(([\w-]+)\) \+ var\(--sp-2\)\)/, 'sp-6'],
  ]
  for (const [datei, muster, soll] of faelle) {
    const css = styleText(lies(datei))
    const m = muster.exec(css)
    assert.ok(m, `${datei}: Muster nicht gefunden`)
    // Die Muster fangen den Namen MIT Präfix (`--sp-5`) — verglichen wird ohne.
    const gefunden = [...m.slice(1)].filter(Boolean).map((g) => g.replace(/^--/, ''))
    assert.ok(gefunden.includes(soll), `${datei}: erwartet --${soll}, gefunden ${gefunden.map((g) => `--${g}`).join(', ')}`)
    assert.ok(!gefunden.includes('sp-alt-20'), `${datei}: wieder bei --sp-alt-20 (20 px)`)
  }
  // seiten.css:265-270 (Marke) — margin-bottom war --sp-6 = 24.
  const seite = lies('src/ssot/seiten.css')
  assert.match(
    seite,
    /\.dk-marke \{[^}]*margin:\s*0 0 var\(--sp-5\)/,
    'seiten.css: .dk-marke margin ist nicht auf --sp-5 (24)',
  )
})

// ── F3 · --gap ist wieder 12 ───────────────────────────────────────────────
test('F3: --gap ist 12 px (--sp-3), nicht 8', () => {
  const tokens = lies('src/diakonos/tokens.css')
  const m = /--gap:\s*([^;]+);/.exec(tokens)
  assert.ok(m, '--gap nicht definiert')
  assert.equal(m[1].trim(), 'var(--sp-3)', '--gap muss auf --sp-3 (12 px) zeigen')
  const sp3 = /--sp-3:\s*(\d+)px;/.exec(tokens)
  assert.ok(sp3, '--sp-3 nicht definiert')
  assert.equal(Number(sp3[1]), 12, '--sp-3 ist nicht 12 px')
})

// ── F4 · --sp-alt-20 ist eingefroren ───────────────────────────────────────
/**
 * Eingefrorener Bestand: Datei → Zahl der `var(--sp-alt-20)`-Vorkommen.
 * Diese Zahlen sind die Wahrheit; sie dürfen GESENKT werden (Zeile dann
 * löschen, sobald 0), aber nie erhöht. Neue Dateien fangen bei 0 an.
 *
 * Stand: nach F1/F2 + dem vollstaendigen Lauf ueber ALLE Dateien, 04.11.2026 —
 */
const ALT20 = {
  'frontend/src/diakonos/components/einrichtung/AssistentSchritte.vue': 2,
  'frontend/src/diakonos/components/kronos/KronosEventCreate.vue': 3,
  'frontend/src/diakonos/components/kronos/KronosEventEdit.vue': 3,
  'frontend/src/diakonos/components/kronos/KronosEventView.vue': 2,
  'frontend/src/diakonos/components/ui/DkPageHeader.vue': 1,
  'frontend/src/diakonos/pages/Beitraege.vue': 3,
  'frontend/src/diakonos/pages/Gruppen.vue': 1,
  'frontend/src/diakonos/pages/LiedDetail.vue': 1,
  'frontend/src/diakonos/pages/LiedgruppeDetail.vue': 1,
  'frontend/src/diakonos/pages/Moderation.vue': 1,
  'frontend/src/diakonos/pages/Profile.vue': 1,
  'frontend/src/diakonos/pages/Registrierung.vue': 2,
  'frontend/src/diakonos/pages/Website.vue': 1,
  'frontend/src/diakonos/pages/Wiki.vue': 4,
  'frontend/src/diakonos/pages/einrichtung/Assistent.vue': 5,
  'frontend/src/diakonos/pages/mitglieder/Uebersicht.vue': 2,
  'frontend/src/diakonos/pages/planrahmen/PlantypEditor.vue': 1,
}

test('F4: --sp-alt-20 darf nur schrumpfen (Bestand je Datei eingefroren)', () => {
  const jetzt = bestand22()
  const verstoesse = []
  for (const [pfad, zahl] of jetzt) {
    const soll = ALT20[pfad]
    if (soll === undefined) verstoesse.push(`${pfad}: ${zahl} × --sp-alt-20, Datei ist NEU (Bestand 0)`)
    else if (zahl > soll) verstoesse.push(`${pfad}: ${zahl} × --sp-alt-20, erlaubt ${soll}`)
  }
  for (const [pfad, soll] of Object.entries(ALT20)) {
    const ist = jetzt.get(pfad) || 0
    if (ist < soll) {
      verstoesse.push(`${pfad}: ${ist} × --sp-alt-20, eingefroren ${soll} — Bestand ist gesunken, Zahl senken`)
    }
  }
  assert.deepEqual(
    verstoesse,
    [],
    'Bestand von --sp-alt-20 (Zwischenmaß 20 px, wird abgebaut):\n  ' + verstoesse.join('\n  '),
  )
})

/** Zählt `var(--sp-alt-20)` je Datei unter `src/` (nur Dateien mit > 0). */
function bestand22() {
  const SRC = path.join(FRONTEND, 'src')
  const QUELLE = 'frontend/src/diakonos/tokens.css'
  const werte = new Map()
  const lauf = (dir) => {
    for (const name of readdirSync(dir)) {
      const p = path.join(dir, name)
      if (statSync(p).isDirectory()) {
        if (name === 'node_modules' || name === 'dist') continue
        lauf(p)
      } else if (/\.(vue|css|js|mjs)$/.test(name)) {
        const text = readFileSync(p, 'utf8')
        // Kommentare zählen NICHT: sie sind keine Nutzung.
        const zahl = (text.replace(/\/\*[\s\S]*?\*\//g, ' ').match(/var\(--sp-alt-20\)/g) || []).length
        const rel = `frontend/${path.relative(FRONTEND, p).split(path.sep).join('/')}`
        // Die Quelle definiert das Zwischenmaß — sie ist keine „Nutzung".
        if (zahl > 0 && rel !== QUELLE) werte.set(rel, zahl)
      }
    }
  }
  lauf(SRC)
  return werte
}

// ── F5 · Der Wächter sieht die Lücken nicht mehr ───────────────────────────
test('F5: Langformen, negative Werte, .5rem und :style-Bindungen zählen', () => {
  const faelle = [
    ['.a{margin-top:4px}', 1, 'margin-top (Langform)'],
    ['.a{margin-right:4px;margin-bottom:4px;margin-left:4px}', 3, 'alle physikalischen Langformen'],
    ['.a{padding-block-start:4px}', 1, 'logische Langform'],
    ['.a{padding-inline-end:4px}', 1, 'logische Langform inline-end'],
    ['.a{inset-block-start:4px}', 1, 'inset-* Langform'],
    ['.a{row-gap:4px}', 1, 'row-gap'],
    ['.a{column-gap:4px}', 1, 'column-gap'],
    ['.a{margin:-4px}', 1, 'negativer Wert'],
    ['.a{margin:-0.5rem}', 1, 'negativer rem-Wert'],
    ['.a{padding:.5rem}', 1, 'Wert ohne führende Null'],
    [':style="{ padding: \'4px\' }"', 1, ':style-Bindung mit Text'],
    // Erlaubt bleibt erlaubt:
    ['.a{margin-top:0}', 0, 'Null'],
    ['.a{margin-block-start:var(--sp-2)}', 0, 'Token'],
    ['.a{padding:calc(var(--sp-1) * -1)}', 0, 'negative Rechnung über Tokens'],
    ['.a{margin-inline:auto}', 0, 'auto'],
  ]
  for (const [css, soll, name] of faelle) {
    assert.equal(fundstellen(css).length, soll, `${name}: erwartet ${soll} Fundstelle(n)`)
  }
  assert.equal(wertIstFest('calc(100% - 4px)'), true, 'calc mit fester Zahl bleibt fest')
  assert.equal(wertIstFest("'4px'"), true, 'angegebene Länge in :style bleibt fest')
})

// ── F6 · Der Drift-Test ist scharf ─────────────────────────────────────────
test('F6: der Drift-Test wird rot, sobald tokens.py existiert und abweicht', () => {
  const testdatei = path.join(FRONTEND, 'tests', 'ux1a-abstand-tokens.test.mjs')
  const probe = mkdtempSync(path.join(os.tmpdir(), 'ux1a2-drift-'))
  try {
    mkdirSync(path.join(probe, 'gestaltung'))
    // Eine falsche Tokendatei: --sp-5 mit 20 statt 24.
    // Die Abweichung MUSS erkannt werden.
    const falsch = [
      'TOKENS = (',
      '    Token("--sp-1", 4, 1, 32),',
      '    Token("--sp-2", 8, 2, 40),',
      '    Token("--sp-3", 12, 4, 48),',
      '    Token("--sp-4", 16, 8, 64),',
      '    Token("--sp-5", 20, 12, 80),',
      '    Token("--sp-6", 32, 16, 96),',
      '    Token("--sp-7", 48, 24, 128),',
      '    Token("--sp-8", 64, 32, 160),',
      '    Token("--pad", 16, 4, 48),',
      '    Token("--abstand-gruppe", 24, 8, 64),',
      '    Token("--abstand-innen", 8, 2, 32),',
      '    Token("--karte-innen", 16, 4, 48),',
      ')',
    ].join('\n')
    const py = path.join(probe, 'gestaltung', 'tokens.py')
    writeFileSync(py, falsch, 'utf8')

    const lauf = () => {
      // Das Kind läuft OHNE den Test-Runner: `node tests/…test.mjs`. Grund
      // (gemessen): im Test-Runner eines Test-Runners (verschachtelt) schluckt
      // der äußere Lauf die Ausgabe des inneren — der Fehlschlag war dann
      // unsichtbar und der Prozess endete mit 0. Direkt ausgeführt wirft die
      // Datei bei einer Abweichung ihren AssertionError und endet mit != 0.
      // Geprüft wird beides: Rückgabewert UND gemeldete Zeile.
      const args = [testdatei]
      try {
        const out = execFileSync(process.execPath, args, {
          cwd: FRONTEND,
          env: { ...process.env, UX1A_BACKEND: probe },
          stdio: 'pipe',
          encoding: 'utf8',
        })
        return { code: 0, text: out }
      } catch (e) {
        return { code: e.status || 1, text: `${e.stdout || ''}${e.stderr || ''}` }
      }
    }

    const abweichend = lauf()
    assert.equal(abweichend.code !== 0, true, 'mit einer abweichenden tokens.py endet der Drift-Test mit Erfolg (nicht scharf)')
    assert.match(
      abweichend.text,
      /--sp-5: tokens\.css 24px ≠ tokens\.py Standard 20px/,
      'mit einer abweichenden tokens.py meldet der Drift-Test die Abweichung NICHT ' +
        '(--sp-5: tokens.css 24 ≠ tokens.py 20) — dann wäre er nicht scharf',
    )
    assert.match(
      abweichend.text,
      /AssertionError|Drift zwischen tokens\.css|not ok/,
      'die Abweichung wurde nicht als Fehler gemeldet (nur Text, kein Fehlschlag)',
    )

    // Gegenprobe: eine passende Tokendatei macht ihn grün (sonst wäre er
    // immer rot und damit nutzlos).
    writeFileSync(py, falsch.replace('Token("--sp-5", 20,', 'Token("--sp-5", 24,'), 'utf8')
    const passend = lauf()
    assert.equal(passend.code, 0, 'mit einer PASSENDEN tokens.py ist der Drift-Test rot')
    assert.doesNotMatch(
      passend.text,
      /≠ tokens\.py Standard/,
      'mit einer PASSENDEN tokens.py meldet der Drift-Test trotzdem einen Unterschied',
    )
  } finally {
    rmSync(probe, { recursive: true, force: true })
  }
})
