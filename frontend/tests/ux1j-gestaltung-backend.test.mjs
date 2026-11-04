/**
 * UX1j — „Gestaltung“-Einstellungen: Vertrag für die Oberfläche (UX1k).
 *
 * Diese Karte ist BACKEND. Der Node-Test hält deshalb die Zusagen fest, auf
 * die sich die Oberfläche verlassen darf — nicht das Aussehen selbst (das ist
 * UX1k). Geprüft wird am Quelltext, weil das Backend Python ist:
 *
 *   1. Es gibt GENAU EINE Positivliste der einstellbaren Token, und sie
 *      enthält die Token der Karte — keine Farben, keine Schriften, keine
 *      Klickflächen.
 *   2. Jedes Token trägt Bereich + Einheit, die Skala ist lückenlos und
 *      aufsteigend — die Oberfläche baut ihre Felder daraus, ohne eigene Liste.
 *   3. Alle drei Endpunkte sind `System Manager`-geprüft, die schreibenden
 *      sind POST (SEC-11).
 *   4. Die ausgelieferte CSS-Datei kann nur `:root { --token: Npx; }` sein:
 *      kein Selektor, kein `url()`, keine Klammer aus einem Wert.
 *   5. `gestaltung.css` hängt NACH `tokens.css` (head-Block und SPA) und ist
 *      ohne Abweichungen LEER.
 *
 * Liest Dateien AUSSERHALB von frontend/ (backend/…) — backend/Dockerfile
 * kopiert sie im Frontend-Stage (Regel 13).
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

/**
 * Zwei Orte, ein Inhalt: im Repo liegt das Backend unter
 * `backend/src/diakronos_app/`, im Docker-Frontend-Stage kopiert der
 * Dockerfile die gebrauchten Dateien nach `/ux1j-backend/` (Regel 13).
 * Gesucht wird in dieser Reihenfolge, damit derselbe Test im Worktree UND im
 * Image laeuft.
 */
const REPO_BACKEND = fileURLToPath(new URL('../../backend/src/diakronos_app/', import.meta.url))
const BILD_BACKEND = '/ux1j-backend/'

const liesBackend = (rel) => {
  for (const basis of [REPO_BACKEND, BILD_BACKEND]) {
    if (existsSync(basis + rel)) return readFileSync(basis + rel, 'utf8')
  }
  assert.fail(`Backend-Datei ${rel} weder im Repo noch im Image gefunden`)
}
const lies = (datei) => liesBackend('gestaltung/' + datei)

/** Die Migration liegt NICHT im Python-Paket (`backend/alembic/versions/`). */
const liesMigration = () => {
  for (const pfad of [
    fileURLToPath(new URL('../../backend/alembic/versions/ux1j_gestaltung.py', import.meta.url)),
    BILD_BACKEND + 'alembic/versions/ux1j_gestaltung.py',
  ]) {
    if (existsSync(pfad)) return readFileSync(pfad, 'utf8')
  }
  assert.fail('Migrationsdatei ux1j_gestaltung.py nicht gefunden')
}

// ── 1. Positivliste ───────────────────────────────────────────────────────

const tokenDatei = lies('tokens.py')

/** Die Token-Definitionen aus `TOKENS` als `{name: {standard, min, max, gruppe}}`. */
function tokenAusQuelle(quelle) {
  const block = quelle.slice(quelle.indexOf('TOKENS: tuple[Token, ...] = ('))
  const rumpf = block.slice(0, block.indexOf('\n)'))
  const gefunden = {}
  for (const m of rumpf.matchAll(/Token\("(--[a-z0-9-]+)",\s*(\d+),\s*(\d+),\s*(\d+)(?:,\s*gruppe="([a-z]+)")?\)/g)) {
    gefunden[m[1]] = {
      standard: Number(m[2]),
      min: Number(m[3]),
      max: Number(m[4]),
      gruppe: m[5] || 'skala',
    }
  }
  return gefunden
}

const TOKEN = tokenAusQuelle(tokenDatei)

test('UX1j: die Positivliste nennt genau die Token der Karte', () => {
  const erwartet = [
    '--sp-1', '--sp-2', '--sp-3', '--sp-4', '--sp-5', '--sp-6', '--sp-7', '--sp-8',
    '--pad', '--abstand-gruppe', '--abstand-innen', '--karte-innen',
    '--karte-rahmen', '--rahmen-breite', '--radius-sm', '--radius', '--radius-lg',
  ]
  assert.deepEqual(Object.keys(TOKEN).sort(), [...erwartet].sort(),
    'die Positivliste weicht von der Karte ab')
})

test('UX1j: Farben, Schriften und Klickflaechen sind NICHT einstellbar', () => {
  const verboten = /--(control-h|row-h|topbar-h|filter-h|primary|accent|bg|surface|text|err|ok|warn|info|dk-|font|schrift|gap)/
  for (const name of Object.keys(TOKEN)) {
    assert.ok(!verboten.test(name), `${name} darf nicht einstellbar sein`)
  }
})

test('UX1j: jedes Token hat Standard, Bereich und Einheit px', () => {
  for (const [name, t] of Object.entries(TOKEN)) {
    assert.ok(Number.isInteger(t.standard), `${name}: Standard fehlt`)
    assert.ok(t.min <= t.standard && t.standard <= t.max, `${name}: Standard ausserhalb des Bereichs`)
    assert.ok(t.gruppe, `${name}: Gruppe fehlt`)
  }
  assert.match(tokenDatei, /def einheit\(self\)[\s\S]*?return "px"/,
    'die Einheit muss aus dem Modul kommen (px), nicht aus der Oberflaeche')
})

test('UX1j: die Abstands-Skala ist lueckenlos und aufsteigend', () => {
  const skala = ['--sp-1', '--sp-2', '--sp-3', '--sp-4', '--sp-5', '--sp-6', '--sp-7', '--sp-8']
  const werte = skala.map((n) => TOKEN[n].standard)
  for (let i = 1; i < werte.length; i += 1) {
    assert.ok(werte[i] > werte[i - 1],
      `${skala[i - 1]} (${werte[i - 1]}) muss kleiner sein als ${skala[i]} (${werte[i]})`)
  }
  assert.equal(TOKEN['--sp-1'].standard, 4)
  assert.equal(TOKEN['--sp-8'].standard, 64)
  assert.equal(TOKEN['--pad'].standard, 16, '--pad ist konzeptgemaess 16 px')
  assert.equal(TOKEN['--karte-rahmen'].standard, 0, 'Karten sind konzeptgemaess rahmenlos')
})

// ── 2. Server prueft, nicht die Oberflaeche ───────────────────────────────

test('UX1j: die Skalen-Pruefung sitzt serverseitig', () => {
  assert.match(tokenDatei, /def pruefe_skala/, 'pruefe_skala fehlt')
  assert.match(tokenDatei, /muss kleiner sein als/, 'die Meldung nennt die gebrochene Stelle nicht')
  // Die Liste prueft in `tokens.py`; der Endpunkt ruft den Speicher, und der
  // Speicher prueft JEDEN Wert ueber `pruefe_wert` — es gibt keinen zweiten Weg.
  const speicher = lies('speicher.py')
  assert.match(speicher, /T\.pruefe_wert\(/, 'der Speicher prueft die Werte nicht ueber die Liste')
  assert.match(lies('api.py'), /speicher\.speichern\(/, 'der Endpunkt schreibt nicht ueber den Speicher')
})

test('UX1j: die CSS-Ausgabe baut nur Zahlen + px', () => {
  const speicher = lies('speicher.py')
  // Der einzige Ort, an dem ein Wert in Text geht: f"{name}: {zahl}px;".
  assert.match(speicher, /f"  \{t\.name\}: \{werte\[t\.name\]\}px;"/,
    'die CSS-Zeile muss aus Name + Zahl + px gebaut werden')
  assert.ok(!/url\(|expression\(|javascript:/i.test(speicher),
    'der Speicher darf kein Fremd-CSS erzeugen')
  assert.match(speicher, /if not werte:\s*\n\s*return ""/,
    'ohne Abweichungen muss die Datei LEER sein')
})

// ── 3. Rollen und Methoden ────────────────────────────────────────────────

test('UX1j: alle drei Endpunkte sind nur fuer System Manager', () => {
  const api = lies('api.py')
  const funktionen = ['gestaltung_lesen', 'gestaltung_speichern', 'gestaltung_zuruecksetzen']
  for (const fn of funktionen) {
    const stelle = api.indexOf(`def ${fn}(`)
    assert.ok(stelle > 0, `${fn} fehlt`)
    const davor = api.slice(Math.max(0, stelle - 300), stelle)
    assert.match(davor, /@whitelist\(/, `${fn}: @whitelist fehlt`)
    assert.match(davor, /allow_guest=False/, `${fn}: allow_guest=False fehlt`)
    assert.ok(davor.includes('_angemeldeter_system_manager()') ||
      api.slice(stelle, stelle + 600).includes('_angemeldeter_system_manager()'),
      `${fn} prueft die Rolle nicht`)
  }
  assert.match(api, /"System Manager" not in get_roles\(\)/,
    'die Rollenpruefung muss auf System Manager gehen')
})

test('UX1j: die schreibenden Endpunkte sind POST (SEC-11)', () => {
  const api = lies('api.py')
  for (const fn of ['gestaltung_speichern', 'gestaltung_zuruecksetzen']) {
    const stelle = api.indexOf(`def ${fn}(`)
    const davor = api.slice(Math.max(0, stelle - 300), stelle)
    assert.match(davor, /@whitelist\(methods=\["POST"\], allow_guest=False\)/,
      `${fn} muss methods=["POST"] deklarieren`)
  }
  // Der lesende Endpunkt darf NICHT auf POST festgelegt sein.
  const leseStelle = api.indexOf('def gestaltung_lesen(')
  assert.ok(!api.slice(Math.max(0, leseStelle - 200), leseStelle).includes('methods=['),
    'gestaltung_lesen ist lesend und braucht keine Methoden-Sperre')
})

// ── 4. Einbau: nach tokens.css, vor der Anmeldung ─────────────────────────

test('UX1j: der head-Block laedt gestaltung.css NACH tokens.css', () => {
  const rahmen = liesBackend('anmeldung/seitenrahmen.py')
  // Nur im Rueckgabe-String suchen — die Namen stehen auch in Kommentaren.
  const iTokens = rahmen.indexOf('href="{tokens}"')
  const iGestalt = rahmen.indexOf('href="{gestaltung}"')
  const iSeiten = rahmen.indexOf('href="{seiten}"')
  assert.ok(iTokens > 0 && iGestalt > 0 && iSeiten > 0, 'die drei <link>-Tags fehlen')
  assert.ok(iTokens < iGestalt, 'tokens.css muss VOR gestaltung.css stehen')
  assert.ok(iGestalt < iSeiten, 'gestaltung.css muss VOR seiten.css stehen')
})

test('UX1j: die SPA laedt gestaltung.css ebenfalls nach den Build-Stylesheets', () => {
  const spa = liesBackend('spa.py')
  const iCss = spa.indexOf('css_tags = "\\n    ".join(')
  const iGestalt = spa.indexOf('_gestaltung_url = _rahmen.gestaltung_url()')
  assert.ok(iCss > 0 && iGestalt > iCss,
    'in render_index muss gestaltung.css NACH den Build-Stylesheets angehaengt werden')
})

test('UX1j: die Route wird vor mount_spa eingetragen', () => {
  const main = liesBackend('main.py')
  const iRoute = main.indexOf('_gestaltung_routen(app)')
  // Der AUFRUF in `erstelle_app`, nicht der Import oder ein Kommentar.
  const iSpa = main.lastIndexOf('\n    mount_spa(app)')
  assert.ok(iRoute > 0, 'die Route wird nicht registriert')
  assert.ok(iRoute < iSpa, 'die Route muss VOR mount_spa stehen (sonst liefert die SPA HTML)')
})

test('UX1j: die Route ist praefixbewusst und cachebar', () => {
  const route = lies('route.py')
  assert.match(route, /base_path\.pfad\(CSS_PFAD\)/, 'die Adresse muss ueber base_path gebaut werden')
  assert.match(route, /"ETag": etag/, 'ETag fehlt')
  assert.match(route, /if-none-match/, 'der 304-Vergleich fehlt')
  assert.match(route, /Cache-Control/, 'Cache-Regel fehlt')
})

// ── 5. Migration ──────────────────────────────────────────────────────────

test('UX1j: die Migration legt die Tabelle an und haengt am Kopf on1_einrichtung', () => {
  const migration = liesMigration()
  assert.match(migration, /down_revision[^=]*=\s*"on1_einrichtung"/)
  assert.match(migration, /create_table\(\s*\n\s*TABELLE/)
  for (const spalte of ['token', 'wert', 'geaendert_von', 'geaendert_am']) {
    assert.ok(migration.includes(`"${spalte}"`), `Spalte ${spalte} fehlt`)
  }
  assert.match(migration, /def downgrade/, 'downgrade fehlt')
})
