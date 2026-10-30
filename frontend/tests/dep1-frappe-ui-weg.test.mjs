// DEP-1 — keine Abhängigkeit mehr von frappe-ui (Befund Manuel 23.10.:
// „Abhängigkeiten von Frappe rausnehmen und mit den echten ersetzen“).
//
// Befund: `frappe-ui@0.1.277` zog über 40 der 57 npm-audit-Meldungen
// (tiptap, socket.io-parser, prosemirror …) und wurde nur in acht Dateien
// benutzt: Plugin + `style.css` in vier `main.js`, `FrappeUIProvider` in
// `diakonos/App.vue`, dazu Button/FormControl/ErrorMessage (gast,
// registrierung) und Spinner/Avatar (organigramm).
//
// Dieser Test hält den Zustand NACH dem Umbau fest — er ist der Wächter gegen
// ein schleichendes Wiedereinziehen des Pakets:
//   1. keine Importe/Verweise auf `frappe-ui` mehr im Quelltext und in den
//      Build-Konfigurationen (tailwind, vite, index.css, tokens.css),
//   2. das Paket steht weder in package.json noch im lockfile,
//   3. die Bereiche, die frappe-Komponenten genutzt haben, nutzen jetzt die
//      eigenen Dk-Bausteine,
//   4. die Schrift „Inter“ kommt lokal aus dem Bündel (@fontsource/inter),
//      nicht mehr aus `frappe-ui/style.css`.

import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const hier = path.dirname(fileURLToPath(import.meta.url))
const frontend = path.resolve(hier, '..')
const src = path.join(frontend, 'src')

function durchlaufe(verzeichnis) {
  const raus = []
  for (const eintrag of fs.readdirSync(verzeichnis, { withFileTypes: true })) {
    const voll = path.join(verzeichnis, eintrag.name)
    if (eintrag.isDirectory()) raus.push(...durchlaufe(voll))
    else raus.push(voll)
  }
  return raus
}

const QUELLDATEIEN = ['.vue', '.js', '.mjs', '.ts', '.css', '.json', '.html']

// Kommentare zählen nicht: die Umbaubegründungen nennen den alten Namen.
function ohneKommentare(text) {
  return text
    .replace(/<!--[\s\S]*?-->/g, '')
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/(^|\s)\/\/[^\n]*/g, '$1')
}

test('kein Quelltext verweist mehr auf frappe-ui (DEP-1)', () => {
  const treffer = []
  for (const datei of durchlaufe(src)) {
    if (!QUELLDATEIEN.some((e) => datei.endsWith(e))) continue
    const inhalt = ohneKommentare(fs.readFileSync(datei, 'utf8'))
    if (/(from|import|@import|require)\s*[^\n]*['"]frappe-ui/.test(inhalt)
        || /frappe-ui\/[a-z]/.test(inhalt)) {
      treffer.push(path.relative(src, datei))
    }
  }
  assert.deepEqual(treffer, [], `frappe-ui wird noch eingebunden:\n${treffer.join('\n')}`)
})

test('Build-Konfiguration hängt nicht mehr an frappe-ui', () => {
  // Kommentare zählen nicht: sie nennen den alten Namen als Begründung.
  // DEP-2: Tailwind 4 kennt keine `tailwind.config.js` mehr — die Quellen und
  // das Theme stehen in `src/style.css` (CSS-first). Geprueft wird deshalb die
  // CSS-Eintragsdatei; existiert doch wieder eine JS-Konfiguration, gilt sie
  // ebenfalls.
  const konfigurationen = [path.join(frontend, 'src', 'style.css')]
  const alt = path.join(frontend, 'tailwind.config.js')
  if (fs.existsSync(alt)) konfigurationen.push(alt)
  for (const datei of konfigurationen) {
    const tailwind = ohneKommentare(fs.readFileSync(datei, 'utf8'))
    assert.doesNotMatch(tailwind, /frappe-ui\/tailwind/,
      `${path.basename(datei)} darf nicht mehr das Frappe-Preset laden.`)
    assert.doesNotMatch(tailwind, /node_modules\/frappe-ui/,
      'Der content-Pfad in node_modules/frappe-ui ist mit dem Paket entfallen.')
  }

  const vite = ohneKommentare(fs.readFileSync(path.join(frontend, 'vite.config.mjs'), 'utf8'))
  assert.doesNotMatch(vite, /['"]frappe-ui['"]/,
    'vite.config.mjs darf frappe-ui nicht mehr auflisten (optimizeDeps).')
})

test('package.json und lockfile führen frappe-ui nicht mehr', () => {
  const pkg = JSON.parse(fs.readFileSync(path.join(frontend, 'package.json'), 'utf8'))
  const alleAbhängigkeiten = { ...pkg.dependencies, ...pkg.devDependencies }
  assert.equal(alleAbhängigkeiten['frappe-ui'], undefined,
    'frappe-ui steht wieder in package.json.')

  const lockPfad = path.join(frontend, 'package-lock.json')
  assert.ok(fs.existsSync(lockPfad), 'package-lock.json fehlt.')
  const lock = JSON.parse(fs.readFileSync(lockPfad, 'utf8'))
  const reste = Object.keys(lock.packages || {})
    .filter((k) => k === 'node_modules/frappe-ui' || k.startsWith('node_modules/@tiptap/'))
  assert.deepEqual(reste, [],
    `Diese Pakete kamen über frappe-ui und müssen aus dem lockfile verschwinden:\n${reste.join('\n')}`)
})

test('die vier Einstiege nutzen die eigenen Dk-Bausteine', () => {
  const erwartet = {
    'gast/App.vue': ['DkButton', 'DkField', 'DkEingabe', 'DkFehlertext'],
    // REG-1b: die Anzeige des Formulars liegt in `components/DkAnmeldeformular.vue`
    // (dieselbe Komponente zeigt die Vorschau im Editor). Die Seite ist nur
    // noch der Rahmen — dort stecken keine frappe-ui-Bausteine mehr.
    'registrierung/components/DkAnmeldeformular.vue': ['DkButton', 'DkField', 'DkEingabe', 'DkFehlertext'],
    'registrierung/App.vue': [],
    'organigramm/App.vue': ['DkSpinner'],
    'diakonos/App.vue': [],
  }
  for (const [datei, bausteine] of Object.entries(erwartet)) {
    const inhalt = fs.readFileSync(path.join(src, datei), 'utf8')
    for (const baustein of bausteine) {
      assert.match(inhalt, new RegExp(`<${baustein}[\\s>]`),
        `${datei}: <${baustein}> fehlt — der frappe-ui-Ersatz ist nicht eingesetzt.`)
    }
    // Frappe-Komponenten in Grossschreibung dürfen nicht mehr vorkommen.
    for (const alt of ['Button', 'FormControl', 'ErrorMessage', 'Spinner', 'Avatar', 'FrappeUIProvider']) {
      assert.doesNotMatch(ohneKommentare(inhalt), new RegExp(`<${alt}[\\s>/]`),
        `${datei}: <${alt}> ist die frappe-ui-Komponente — bitte Dk-Baustein verwenden.`)
    }
  }
})

test('Avatare im Organigramm kommen aus Tokens, nicht aus frappe-ui', () => {
  const inhalt = fs.readFileSync(path.join(src, 'organigramm/App.vue'), 'utf8')
  const stil = inhalt.slice(inhalt.indexOf('<style>'))
  assert.match(stil, /\.oc-kopf-avatar\s*\{/, 'Der Kopf-Avatar des Organigramms braucht eine eigene Regel.')
  for (const regel of ['.oc-kopf-foto', '.oc-kopf-avatar']) {
    assert.ok(stil.includes(regel), `Regel ${regel} fehlt im Organigramm.`)
  }
  // Farben ausschliesslich aus Tokens (der Wächter-Test prüft das zusätzlich).
  assert.match(stil, /var\(--info-soft\)/, 'Avatar-Hintergrund muss der Token --info-soft sein.')
})

test('Schrift Inter liegt lokal im Bündel (@fontsource/inter)', () => {
  const tokens = fs.readFileSync(path.join(src, 'diakonos/tokens.css'), 'utf8')
  // tokens.css wird von ALLEN vier Einstiegen geladen.
  for (const schnitt of ['400', '500', '600', '700']) {
    assert.match(tokens, new RegExp(`@import\\s+['"]@fontsource/inter/latin-${schnitt}\\.css['"]`),
      `tokens.css muss den Schnitt ${schnitt} aus @fontsource/inter importieren.`)
  }
  const pkg = JSON.parse(fs.readFileSync(path.join(frontend, 'package.json'), 'utf8'))
  assert.ok(pkg.dependencies['@fontsource/inter'],
    '@fontsource/inter muss als Abhängigkeit stehen (lokale Schrift, kein Fremdhost).')

  // Kein Verweis auf den alten Schrift-Ort.
  const index = fs.readFileSync(path.join(src, 'diakonos/index.css'), 'utf8')
  assert.doesNotMatch(ohneKommentare(index), /frappe-ui/,
    'index.css darf frappe-ui/style.css nicht mehr importieren.')
})
