/**
 * DEP-2 (Review) — Wächter für die Punkte 1, 3, 4, 5 und 6 der Operator-Runde.
 *
 * Die Node-Tests von DEP-2 deckten den Fortschrittsweg ab, nicht die
 * Randfälle. Diese Datei hält genau die Fehler fest, die im Review aufgefallen
 * sind — jede Prüfung benennt den Fehler, den sie verhindert:
 *
 *   1. HOCH   `{state: null}` als erste Abfrage: der Zustand wurde `null`, das
 *             Template las `progress.calendar_name` → Absturz. `null` heißt
 *             jetzt „noch nichts gemeldet", der Startzustand bleibt stehen.
 *   3. MITTEL Warnungen wurden alle 2 s erneut angehängt bzw. gingen zwischen
 *             zwei Abfragen verloren → der Stand bringt die vollständige Liste
 *             mit, die Seite übernimmt sie (dedupliziert, ohne Anhängen).
 *   4. MITTEL `@vitejs/plugin-vue` muss zu vite 7 passen (`^6`), sonst ist
 *             `npm ci` nur mit `--legacy-peer-deps` möglich — der Schalter ist
 *             aus Dockerfile und READMEs entfernt und darf nicht zurück.
 *   5. MITTEL Tailwind 4 hat kein Preflight; registrierung und organigramm
 *             luden nur tokens.css und hatten damit KEIN Reset. Das Reset liegt
 *             jetzt in src/grundreset.css und wird von allen vier Einstiegen
 *             geladen.
 *   6. NIEDRIG Die untere Leiste: Beschriftungen kräftiger/dunkler, der aktive
 *             Reiter hebt sich ab (nicht über `--primary` — das ist im
 *             Dunkelmodus WEISS).
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'

const lies = rel => fs.readFileSync(new URL('../' + rel, import.meta.url), 'utf8')
const pkg = JSON.parse(lies('package.json'))

/**
 * Baut das `<script setup>` aus KalenderImport.vue in einer vm-Sandbox auf —
 * dasselbe Muster wie google-import.test.mjs (kein Vue-Compiler nötig, keine
 * Timer: setTimeout wird nur festgehalten).
 */
function baueKomponente({ status = {}, staende = [] } = {}) {
  const quelle = lies('src/diakonos/pages/KalenderImport.vue')
  const calls = [], mounted = [], unmounted = [], timers = []
  const context = {
    ref: value => ({ value }), computed: fn => ({ get value() { return fn() } }),
    onMounted: fn => mounted.push(fn), onBeforeUnmount: fn => unmounted.push(fn),
    navigate: () => {}, URL, URLSearchParams, btoa, Uint8Array, setTimeout: (fn, ms) => (timers.push({ fn, ms }), timers.length),
    clearTimeout: () => {},
    // WEB-5b: Adressen der Seite laufen ueber mitBasis(); ohne Boot-Objekt im
    // Kontext ergibt das die alte Adresse (Verhalten: tests/web5b-basis.test.mjs).
    mitBasis: (pfad) => '/' + String(pfad || '').replace(/^\/+/, ''),
    window: {
      __DIakonosBOOT: { is_admin: true, csrf_token: 'csrf-test' },
      location: { origin: 'https://example.org', href: 'https://example.org/diakronos#/kalender/import', assign: () => {} },
      history: { replaceState: () => {} },
    },
    __api: async (method) => {
      calls.push({ method })
      if (method.endsWith('get_credentials_status')) return status
      if (method.endsWith('get_google_calendars')) return [{ id: 'one', summary: 'Gemeinde', backgroundColor: '#ff0000' }]
      if (method.endsWith('get_writable_calendars')) return [{ name: 'Bestand', calendar_name: 'Bestand' }]
      if (method.endsWith('get_import_progress')) return { state: staende.length ? staende.shift() : null }
      if (method.endsWith('start_import')) return { queued: true }
      return { success: true }
    },
  }
  const script = quelle.match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '')
  vm.createContext(context)
  vm.runInContext(script + '\nthis.state = { tab, step, error, busy, clientId, clientSecret, redirectUri, calendars, result, progress, warnings, importing, saveCredentials, startGoogleImport, loadStatus };this.pollRunde = pollRunde;', context)
  // Zwei Microtask-Runden: dann sind die .then/.finally-Ketten fertig.
  context.apiCall = async (...args) => {
    const r = await context.__api(...args)
    await new Promise(x => setImmediate(x))
    await new Promise(x => setImmediate(x))
    return r
  }
  return { ...context.state, calls, mounted, unmounted, timers,
    poll: async () => {
      context.pollRunde()
      await new Promise(r => setImmediate(r))
      await new Promise(r => setImmediate(r))
    } }
}

function ohneKommentare(text) {
  return text
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/(^|\s)\/\/[^\n]*/g, '$1')
}

// ── Punkt 1: `{state: null}` darf die Seite nicht abstürzen lassen ─────────

test('Fortschritt: Startzustand ist ein Objekt, null wird nicht übernommen (Punkt 1)', () => {
  const quelle = lies('src/diakonos/pages/KalenderImport.vue')
  const script = ohneKommentare(quelle.match(/<script setup>([\s\S]*?)<\/script>/)[1])
  // Der Zustand startet als Objekt mit `status` — nicht als `{}` und nicht `null`.
  assert.match(script, /const progress = ref\(\{\s*status:/,
    'progress startet ohne status — das Template liest progress.status')
  // `null` aus der Abfrage darf den Zustand nicht ersetzen.
  const empfänger = script.slice(script.indexOf('function receiveProgress'), script.indexOf('function pollRunde'))
  assert.match(empfänger, /if \(!data \|\| typeof data !== 'object'\) return/,
    'receiveProgress übernimmt null/keine Objekte — genau das war der Absturz')
  // Nach dem Start eines Imports steht ein gültiger Zustand bereit.
  const start = script.slice(script.indexOf('async function startGoogleImport'))
  assert.match(start, /progress\.value = \{ status: 'startet'/,
    'startGoogleImport setzt keinen gültigen Startzustand')
  // Das Template liest null-sicher.
  const template = quelle.match(/<template>([\s\S]*)<\/template>/)[1]
  assert.doesNotMatch(template, /\{\{\s*progress\.calendar_name/,
    'Template liest progress.calendar_name ohne Null-Schutz')
  assert.match(template, /progress\?\.calendar_name/)
})

test('Fortschritt: null-Serie lässt den Balken stehen und beendet nichts (Punkt 1)', async () => {
  const s = baueKomponente({
    status: { configured: true, authorized: true },
    // Erste drei Abfragen liefern `null`, danach ein echter Stand.
    staende: [null, null, null, { status: 'importing', calendar_name: 'Chor', imported: 7 }],
  })
  await s.mounted[0]()
  await s.startGoogleImport()
  for (let i = 0; i < 3; i++) await s.poll()
  assert.equal(s.importing.value, true, 'eine leere Abfrage beendet den Import')
  assert.equal(s.progress.value.calendar_name, undefined, 'ohne Stand gibt es keinen Kalendernamen')
  assert.equal(s.progress.value.status, 'startet', 'der Startzustand bleibt stehen')
  await s.poll()
  assert.equal(s.progress.value.calendar_name, 'Chor')
  assert.equal(s.progress.value.imported, 7)
  s.unmounted[0]()
})

// ── Punkt 3: Warnungen vollständig und ohne Dubletten ──────────────────────

test('Fortschritt: Warnungen kommen aus dem Server-Stand, nicht aus der Seite (Punkt 3)', async () => {
  const warnung = 'Grosser Kalender: Import kann laenger dauern.'
  const s = baueKomponente({
    status: { configured: true, authorized: true },
    staende: [
      { status: 'warning', warning: warnung, warnings: [warnung] },
      // Stehender Stand: dieselbe Warnung noch einmal — darf NICHT doppelt werden.
      { status: 'importing', calendar_name: 'Chor', imported: 3, warnings: [warnung] },
      { status: 'importing', calendar_name: 'Chor', imported: 9, warnings: [warnung] },
    ],
  })
  await s.mounted[0]()
  await s.startGoogleImport()
  for (let i = 0; i < 3; i++) await s.poll()
  assert.deepEqual(s.warnings.value, [warnung], 'die Warnung steht doppelt oder fehlt')
})

test('Fortschritt: eine Warnung, die zwischen zwei Abfragen kam, bleibt im Endstand (Punkt 3)', async () => {
  const s = baueKomponente({
    status: { configured: true, authorized: true },
    staende: [
      { status: 'importing', calendar_name: 'Chor', imported: 1, warnings: [] },
      // Der Abschluss trägt die Warnliste des gesamten Laufs.
      { status: 'done', total_imported: 5, total_skipped: 1, calendars: [],
        warnings: ['Grosser Kalender: Import kann laenger dauern.'] },
    ],
  })
  await s.mounted[0]()
  await s.startGoogleImport()
  await s.poll()
  assert.deepEqual(s.warnings.value, [])
  await s.poll()
  assert.deepEqual(s.warnings.value, ['Grosser Kalender: Import kann laenger dauern.'])
  assert.equal(s.importing.value, false)
})

test('Fortschritt: ein Zwischenstand überschreibt den Abschluss nicht mehr (Punkt 1/3)', async () => {
  const s = baueKomponente({
    status: { configured: true, authorized: true },
    staende: [
      { status: 'done', total_imported: 3, total_skipped: 0, calendars: [] },
      // Später eintreffender Zwischenstand (z. B. verspätete Antwort).
      { status: 'importing', calendar_name: 'Chor', imported: 1 },
    ],
  })
  await s.mounted[0]()
  await s.startGoogleImport()
  await s.poll()
  assert.equal(s.result.value.total_imported, 3)
  s.unmounted[0]()
  // Result bleibt das Ergebnis; der Zustand wird nicht durch den Zwischenstand ersetzt.
  assert.equal(s.progress.value.status, 'done')
})

// ── Punkt 4: Peer-Konflikt weg, kein --legacy-peer-deps ───────────────────

test('Build-Kette: @vitejs/plugin-vue passt zu vite 7, kein --legacy-peer-deps (Punkt 4)', async () => {
  const haupt = v => Number(String(v || '0').replace(/[^0-9.]/g, '').split('.')[0])
  assert.ok(haupt(pkg.devDependencies.vite) >= 7, `vite steht auf ${pkg.devDependencies.vite}`)
  assert.ok(haupt(pkg.devDependencies['@vitejs/plugin-vue']) >= 6,
    `@vitejs/plugin-vue ${pkg.devDependencies['@vitejs/plugin-vue']} passt nicht zu vite 7 (Peer ^5||^6 bei v5.x)`)

  // Das Dockerfile liegt im Build-Image NICHT neben dem Frontend (die
  // Build-Stufe hat nur /build = frontend/). Die Prüfung läuft daher nur, wo
  // die Datei erreichbar ist — im Worktree; im Image greift die
  // package.json/lock-Prüfung oben, die den Schalter ohnehin erzwingen würde.
  const dockerfilePfad = new URL('../backend/Dockerfile', import.meta.url)
  if (fs.existsSync(dockerfilePfad)) {
    const dockerfile = fs.readFileSync(dockerfilePfad, 'utf8')
      // Nur echte Anweisungen prüfen: der Kommentar erklärt den entfernten
      // Schalter und darf ihn nennen.
      .split('\n').filter(z => !z.trimStart().startsWith('#')).join('\n')
    assert.doesNotMatch(dockerfile, /--legacy-peer-deps/,
      'Das Dockerfile installiert wieder mit --legacy-peer-deps')
  }
  const readme = lies('README.md').split('\n').filter(z => !z.trimStart().startsWith('#'))
  assert.doesNotMatch(readme.join('\n'), /^[^`\n]*npm (ci|install)[^\n]*--legacy-peer-deps/m,
    'frontend/README.md nennt wieder --legacy-peer-deps')

  // DEP-2b: die Operator-Runde nannte zusätzlich README.md im Wurzelverzeichnis
  // (Anleitung „Entwicklung und Tests“) und den RISIKOBERICHT — beide nannten
  // den Schalter noch als ANWEISUNG. Geprüft wird jede Zeile, die `npm ci` oder
  // `npm install` zeigt, ohne den Schalter zu zeigen; historische Erwähnungen
  // („stand hier früher“) bleiben erlaubt, weil sie ihn nicht empfehlen.
  const wurzel = new URL('../../', import.meta.url)
  for (const datei of ['README.md', 'frontend/RISIKOBERICHT.md']) {
    const pfad = new URL(datei, wurzel)
    if (!fs.existsSync(pfad)) continue
    const zeilen = fs.readFileSync(pfad, 'utf8')
      .split('\n')
      .filter(z => !z.trimStart().startsWith('#'))
    assert.doesNotMatch(zeilen.join('\n'),
      /^[^`\n]*npm (ci|install)[^\n]*--legacy-peer-deps/m,
      `${datei} nennt wieder --legacy-peer-deps als Anweisung`)
  }

  // Der lock muss den neuen Peer-Bereich tragen — sonst löst `npm ci` wieder auf
  // den alten Stand auf und der Konflikt kehrt still zurück.
  const lock = JSON.parse(lies('package-lock.json'))
  const eintrag = lock.packages['node_modules/@vitejs/plugin-vue']
  assert.ok(eintrag, '@vitejs/plugin-vue fehlt im lock')
  assert.ok(haupt(eintrag.version) >= 6, `lock hat @vitejs/plugin-vue ${eintrag.version}`)
})

// ── Punkt 5: Reset für alle vier Einstiege ────────────────────────────────

test('Grundreset: alle vier Einstiege laden box-sizing/font-Reset (Punkt 5)', () => {
  const reset = ohneKommentare(lies('src/grundreset.css'))
  // DEP-2b: Selektoren in :where(...) — Spezifitaet 0, Komponenten gewinnen.
  assert.match(reset, /:where\(\*\),\s*\n\s*:where\(\*::before\),\s*\n\s*:where\(\*::after\)\s*\{\s*box-sizing:\s*border-box/,
    'grundreset.css setzt kein box-sizing (oder nicht in :where(...))')
  assert.match(reset, /:where\(body\)\s*\{[^}]*margin:\s*0/, 'grundreset.css setzt body-margin nicht')
  assert.match(reset, /font:\s*inherit/, 'grundreset.css setzt die Feld-Schrift nicht auf inherit')
  // Kein Preflight: das Reset darf die Preflight-Datei nicht einbinden.
  assert.doesNotMatch(reset, /tailwindcss\/preflight|@import\s+["']tailwindcss["']/,
    'das Reset zieht den Tailwind-Preflight nach')

  // Einstiege: diakonos und gast über index.css, registrierung und organigramm
  // direkt (sie laden tokens.css, nicht index.css).
  const index = lies('src/diakonos/index.css')
  assert.match(index, /@import\s+['"]\.\.\/grundreset\.css['"]/,
    'index.css bindet das Grundreset nicht ein (diakonos + gast)')
  for (const einstieg of ['registrierung', 'organigramm']) {
    const main = lies(`src/${einstieg}/main.js`)
    assert.match(main, /import\s+['"]\.\.\/grundreset\.css['"]/,
      `${einstieg}/main.js lädt das Grundreset nicht — dort fehlt box-sizing komplett`)
  }
  // Keine Doppelpflege: das Reset steht nicht mehr zusätzlich in index.css.
  const indexSauber = ohneKommentare(index)
  assert.doesNotMatch(indexSauber, /\*,\s*\*::before,\s*\*::after\s*\{\s*box-sizing/,
    'index.css setzt box-sizing noch einmal — zwei Quellen für ein Reset')
})

// ── Punkt 6: untere Leiste lesbar und mit abgesetztem aktivem Reiter ──────

test('Untere Leiste: kräftige Beschriftung, aktiver Reiter über --accent (Punkt 6)', () => {
  const quelle = lies('src/diakonos/components/AppBottomNav.vue')
  const stil = ohneKommentare(quelle.match(/<style scoped>([\s\S]*?)<\/style>/)[1])
  const tab = stil.match(/\.dk-bn-tab\s*\{([\s\S]*?)\}/)[1]
  // UX1b: Gewichte sind Tokens — kraeftig heisst var(--fw-fett) (600). Eine
  // Rohzahl 600/700 gibt es im Stylesheet nicht mehr (Waechter ux1b).
  assert.match(tab, /font-weight:\s*var\(--fw-fett\)/, 'die Beschriftung ist wieder zu dünn')
  assert.match(tab, /color:\s*var\(--dk-text\)/, 'die Beschriftung nimmt nicht die Textfarbe des Themes')
  assert.doesNotMatch(tab, /--primary/, 'inaktive Reiter nehmen --primary (im Dunkelmodus WEISS)')
  const aktiv = stil.match(/\.dk-bn-tab\.active\s*\{([\s\S]*?)\}/)[1]
  assert.match(aktiv, /color:\s*var\(--accent\)/,
    'der aktive Reiter nimmt nicht --accent — im Dunkelmodus war --primary WEISS und damit unsichtbar')
  assert.doesNotMatch(aktiv, /--primary/)
  // Der Zustand hängt nicht allein an der Farbe (WCAG 1.4.1).
  assert.match(stil, /\.dk-bn-tab\.active span::after/, 'dem aktiven Reiter fehlt die zweite Kennzeichnung')
})
