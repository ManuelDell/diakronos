/**
 * DEP-2 — Wächter für die Build-Kette (Tailwind 4, keine Frappe-Presets).
 *
 * Warum: `npm audit` meldete nach DEP-1 nur noch Meldungen aus der
 * Build-Kette (vite/esbuild und tailwindcss 3 → chokidar/braces/micromatch/
 * fast-glob, postcss-nested/postcss-selector-parser). Tailwind 3.4.19 ist der
 * letzte Stand der 3er-Reihe (`v3-lts`) und bekommt keine Korrekturen mehr;
 * DEP-2 hebt deshalb auf die 4er-Reihe. Der Sprung ändert, WIE Tailwind
 * eingebunden wird (CSS-first statt `tailwind.config.js`), und genau das
 * würde still kaputtgehen: fehlt die Datei oder der `@source`-Pfad, baut Vite
 * weiter — aber ohne Utility-Klassen. Dieser Test hält den Zustand fest.
 *
 * Geprüft wird:
 *   1. Tailwind 4 ist installiert (nicht die 3er-Reihe),
 *   2. `src/style.css` bindet Theme und Utilities ein,
 *   3. KEIN Preflight (das Projekt setzt sein eigenes Reset — sonst würden
 *      Tabellen/Überschriften/Formulare app-weit umgestellt),
 *   4. `@source` nennt die Quellen ausdrücklich,
 *   5. es gibt keine `tailwind.config.js` mehr (CSS-first),
 *   6. die Presets `@tailwindcss/forms`/`-typography` kommen NICHT zurück
 *      (Auflage aus dem DEP-1-Review: nicht wieder einführen, außer ein Paket
 *      wird wirklich gebraucht),
 *   7. die im Quelltext benutzten Utility-Klassen stehen im gebauten CSS
 *      (nur wenn `dist/` vorhanden ist — im Image wird vor diesem Test gebaut).
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const hier = path.dirname(fileURLToPath(import.meta.url))
const frontend = path.resolve(hier, '..')
const pkg = JSON.parse(fs.readFileSync(path.join(frontend, 'package.json'), 'utf8'))
const alle = { ...pkg.dependencies, ...pkg.devDependencies }

function ohneKommentare(text) {
  return text
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/(^|\s)\/\/[^\n]*/g, '$1')
}

test('Tailwind 4 statt der abgekündigten 3er-Reihe', () => {
  assert.ok(alle.tailwindcss, 'tailwindcss fehlt in package.json')
  const haupt = Number(String(alle.tailwindcss).replace(/[^0-9.]/g, '').split('.')[0])
  assert.ok(haupt >= 4, `tailwindcss steht wieder auf der 3er-Reihe (${alle.tailwindcss}); 3.4.19 bekommt keine Sicherheitskorrekturen mehr`)
  assert.ok(alle['@tailwindcss/postcss'], 'Für Tailwind 4 fehlt das PostCSS-Plugin @tailwindcss/postcss')
  assert.equal(alle['@tailwindcss/forms'], undefined, '@tailwindcss/forms darf nicht wieder eingeführt werden')
  assert.equal(alle['@tailwindcss/typography'], undefined, '@tailwindcss/typography darf nicht wieder eingeführt werden')
})

test('src/style.css bindet Theme und Utilities ein, aber kein Preflight', () => {
  const datei = path.join(frontend, 'src', 'style.css')
  assert.ok(fs.existsSync(datei), 'src/style.css fehlt — die Utilities kämen in keinen Einstieg')
  const css = ohneKommentare(fs.readFileSync(datei, 'utf8'))
  assert.match(css, /@import\s+["']tailwindcss\/theme["']/, 'Theme-Ebene fehlt')
  assert.match(css, /@import\s+["']tailwindcss\/utilities["']/, 'Utilities-Ebene fehlt')
  assert.doesNotMatch(css, /@import\s+["']tailwindcss["']/, 'Das Gesamtpaket zieht Preflight mit — nur theme + utilities einbinden')
  assert.doesNotMatch(css, /tailwindcss\/preflight/, 'Preflight darf nicht geladen werden (eigenes Reset in index.css)')
  assert.match(css, /@source\s+["']/, 'Ohne @source durchsucht Tailwind auch Tests und Markdown')
  assert.doesNotMatch(css, /frappe-ui/, 'Frappe-Presets bleiben draußen')
})

test('das Reset (box-sizing, Schrift) steht in grundreset.css und erreicht alle Einstiege', () => {
  // Bis DEP-2 kam beides aus dem Tailwind-Preflight. Faellt es weg, rechnet der
  // Browser wieder content-box (.dk-screen 80 px zu breit) und Elemente
  // ausserhalb von .dk-app fallen auf Times New Roman — beides im
  // Bildvergleich vorher/nachher aufgefallen.
  //
  // DEP-2-Review, Punkt 5: registrierung und organigramm laden index.css NICHT
  // (nur tokens.css) und hatten deshalb kein Reset. Es liegt seitdem in
  // src/grundreset.css — eine Quelle, die alle vier Einstiege einbinden.
  const reset = fs.readFileSync(path.join(frontend, 'src', 'grundreset.css'), 'utf8')
  // DEP-2b: die Selektoren stehen in :where(...) (Spezifitaet 0), damit
  // Komponentenklassen immer gewinnen. Der Test prueft deshalb die Form MIT
  // :where — die alte Schreibweise waere die Regression.
  assert.match(reset, /:where\(\*\),\s*\n\s*:where\(\*::before\),\s*\n\s*:where\(\*::after\)\s*\{\s*box-sizing:\s*border-box;/,
    'Das globale box-sizing-Reset fehlt (kam frueher aus dem Tailwind-Preflight) oder steht nicht in :where(...)')
  assert.match(reset, /:where\(body\)\s*\{[^}]*font-family:[^}]*Inter/,
    'Der body traegt die Schrift nicht mehr (Elemente ausserhalb .dk-app fallen auf Times New Roman)')
  assert.match(reset, /:where\(button,\s*\n?\s*input,[^}]*font:\s*inherit;/,
    'Formularelemente erben die Schrift nicht mehr (sie fallen auf Arial zurueck)')
  assert.match(reset, /margin:\s*0;/, 'Der Formularelement-Abstand-Reset fehlt')

  // index.css bindet es ein (damit diakonos und gast es bekommen) …
  const index = fs.readFileSync(path.join(frontend, 'src', 'diakonos', 'index.css'), 'utf8')
  assert.match(index, /@import\s+['"]\.\.\/grundreset\.css['"]/, 'index.css laedt grundreset.css nicht')
  // … und die beiden Einstiege ohne index.css laden es direkt.
  for (const einstieg of ['registrierung', 'organigramm']) {
    const main = fs.readFileSync(path.join(frontend, 'src', einstieg, 'main.js'), 'utf8')
    assert.match(main, /import\s+['"]\.\.\/grundreset\.css['"]/,
      `${einstieg}/main.js laedt das Reset nicht — dort fehlte box-sizing komplett`)
  }
})

test('keine tailwind.config.js mehr (CSS-first)', () => {
  assert.equal(fs.existsSync(path.join(frontend, 'tailwind.config.js')), false,
    'Mit Tailwind 4 gilt src/style.css; eine JS-Konfiguration wäre eine zweite Quelle')
})

test('die benutzten Utility-Klassen stehen im gebauten CSS', (t) => {
  const verzeichnis = path.join(frontend, 'dist', 'css')
  if (!fs.existsSync(verzeichnis)) {
    t.skip('dist/css fehlt (kein Build in diesem Lauf)')
    return
  }
  const datei = fs.readdirSync(verzeichnis).find((name) => name.endsWith('.css'))
  assert.ok(datei, 'dist/css enthält keine CSS-Datei')
  const css = fs.readFileSync(path.join(verzeichnis, datei), 'utf8')
  // Klassen, die im Quelltext tatsächlich vorkommen (grep, 2026-10-23).
  for (const klasse of ['p-4', 'gap-2', 'ml-6', 'pl-4', 'space-y-2', 'border-l-2', 'text-4xl', 'min-w-0']) {
    assert.match(css, new RegExp('\\.' + klasse.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '[{> ,]'),
      `.${klasse} fehlt im gebauten CSS — @source greift nicht`)
  }
})
