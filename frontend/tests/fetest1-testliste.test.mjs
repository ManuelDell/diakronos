/**
 * FE-TEST-1 — Wächter über `frontend/tests/testliste.txt`.
 *
 * Seit FE-TEST-1 steht die Liste der Node-Tests für den Frontend-Stage der
 * `backend/Dockerfile` in EINER Datei (`tests/testliste.txt`, ein Glob-Muster
 * pro Zeile). Damit „grün“ auch wirklich „geprüft“ heißt, sichert dieser Test
 * die vier Zusagen der Karte:
 *
 *   W1  Jede Testdatei (`tests/*.test.mjs` und `src/**\/*.test.mjs`) wird von
 *       mindestens einem Muster der Liste erfasst. Ausnahmen sind BEGRÜNDET
 *       im Kopf der Liste vermerkt (Abschnitt „Ausnahmen“) — stilles
 *       Auslassen fällt auf.
 *   W2  Kein Muster läuft ins Leere (jedes trifft mindestens eine Datei).
 *       Ein Tippfehler im Glob würde sonst einfach nichts prüfen.
 *   W3  Kein Muster ist leer/nur Kommentar, und die echte Liste ist nicht
 *       leer (die Dockerfile bricht bei leerer Auswahl ab).
 *   W4  Die Dockerfile liest die Muster aus `$NODE_TESTLISTE`, führt
 *       `node --test` NICHT mehr mit fester Musterliste aus (sonst gäbe es
 *       zwei Quellen), bricht bei leerer Auswahl ab und `.gitattributes`
 *       führt die Liste mit `merge=union` zusammen.
 *
 * Läuft ohne Fremdpakete (nur node:fs/node:path), damit er auch im
 * Frontend-Stage des Images grün ist — dort liegt `frontend/` unter /build.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs'
import { dirname, join, relative, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

/** Wurzel des Frontends (…/frontend) — im Image /build, lokal der Repo-Ordner. */
const FRONTEND = join(dirname(fileURLToPath(import.meta.url)), '..')
const LISTE = join(FRONTEND, 'tests', 'testliste.txt')

const lies = (pfad) => readFileSync(pfad, 'utf8')

/**
 * Repo-Wurzel, um `backend/Dockerfile`, `.gitattributes` und `.gitignore` zu
 * prüfen.
 *
 * Im Image liegt `frontend/` unter /build, und `backend/` gibt es dort NUR als
 * Ablage der Regel-13-Kopien (/backend/Dockerfile wird ausdrücklich für andere
 * Wächter kopiert). Deshalb reicht `backend/Dockerfile` als Merkmal NICHT:
 * eine echte Repo-Wurzel trägt zusätzlich `.gitattributes` oder `.gitignore`
 * (im Frontend-Stage nicht kopiert). Fehlt beides, entfällt die Prüfung mit
 * Begründung (SKIP) — der Nachweis läuft dann über
 * `docker build --target frontend` und den lokalen Lauf.
 */
function repoWurzel() {
  const kandidaten = [
    join(FRONTEND, '..'), // Worktree: <repo>/frontend -> <repo>
    join(FRONTEND, '..', '..'),
  ]
  return kandidaten.find((p) => existsSync(join(p, 'backend', 'Dockerfile'))
    && (existsSync(join(p, '.gitattributes')) || existsSync(join(p, '.gitignore')))) || null
}

/** Muster der Liste: ohne Kommentarzeilen, ohne Leerzeilen, ohne CR. */
function muster(pfad = LISTE) {
  return lies(pfad)
    .split('\n')
    .map((z) => z.replace(/\r$/, '').trim())
    .filter((z) => z !== '' && !z.startsWith('#'))
}

/** Alle Testdateien des Frontends, relativ zu `frontend/`, POSIX-getrennt. */
function testdateien() {
  const gefunden = []
  const lauf = (ordner) => {
    for (const eintrag of readdirSync(ordner)) {
      if (eintrag === 'node_modules' || eintrag.startsWith('.')) continue
      const pfad = join(ordner, eintrag)
      if (statSync(pfad).isDirectory()) lauf(pfad)
      else if (eintrag.endsWith('.test.mjs')) gefunden.push(relative(FRONTEND, pfad).split(sep).join('/'))
    }
  }
  lauf(join(FRONTEND, 'tests'))
  lauf(join(FRONTEND, 'src'))
  return gefunden.sort()
}

/**
 * Glob → RegExp. Unterstützt `*` (innerhalb eines Pfadteils) und `?`.
 * Kein `**`: die Liste benutzt nur `ordner/*.test.mjs`-Muster; `**` würde
 * ein versehentlich zu breites Muster verdecken.
 */
function globZuRegExp(glob) {
  let re = ''
  for (const zeichen of glob) {
    if (zeichen === '*') re += '[^/]*'
    else if (zeichen === '?') re += '[^/]'
    else re += zeichen.replace(/[.+^${}()|[\]\\]/g, '\\$&')
  }
  return new RegExp(`^${re}$`)
}

/**
 * Ausnahmen: Testdateien, die absichtlich NICHT in der Liste stehen.
 * Begründung gehört in den Kopf der Liste (Abschnitt „Ausnahmen“) — die
 * Prüfung unten verlangt, dass jeder Eintrag hier dort erklärt wird.
 */
const AUSNAHMEN = []

test('FE-TEST-1 · die Testliste existiert und enthält Muster', () => {
  assert.ok(existsSync(LISTE), 'frontend/tests/testliste.txt fehlt')
  const alle = muster()
  assert.ok(alle.length > 100, `nur ${alle.length} Muster — Liste unvollständig?`)
  for (const m of alle) {
    assert.match(m, /^[A-Za-z0-9_./*-]+\.test\.mjs$/, `Muster ohne .test.mjs-Endung: ${m}`)
    assert.ok(!m.startsWith('/'), `absoluter Pfad im Muster: ${m}`)
  }
  // Keine Dubletten: doppelte Zeilen blähen den Build auf und verwirren den Merge.
  assert.equal(new Set(alle).size, alle.length, 'die Testliste enthält Dubletten')
})

test('FE-TEST-1 · jedes Muster trifft mindestens eine Datei (kein Muster ins Leere)', () => {
  const dateien = testdateien()
  const insLeere = []
  for (const m of muster()) {
    const re = globZuRegExp(m)
    if (!dateien.some((d) => re.test(d))) insLeere.push(m)
  }
  assert.deepEqual(insLeere, [],
    `Muster ohne Treffer (Tippfehler?): ${insLeere.join(', ')}`)
})

test('FE-TEST-1 · jede Testdatei ist von einem Muster erfasst', () => {
  const regeln = muster().map(globZuRegExp)
  const ungeprüft = testdateien().filter(
    (d) => !regeln.some((re) => re.test(d)) && !AUSNAHMEN.includes(d),
  )
  assert.deepEqual(ungeprüft, [],
    'diese Testdateien laufen im Image nie — Zeile in tests/testliste.txt anhängen')
})

test('FE-TEST-1 · Ausnahmen sind begründet und nicht bloß vergessen', () => {
  // Jede Ausnahme muss im Kopf der Liste (vor dem Muster-Abschnitt) namentlich
  // auftauchen — wer eine Ausnahme will, muss sie dort erklären.
  const kopf = lies(LISTE).split(/^# ── Muster/m)[0]
  for (const datei of AUSNAHMEN) {
    const kurz = datei.split('/').pop()
    assert.ok(kopf.includes(kurz),
      `Ausnahme ${datei} ist im Kopf der Liste nicht begründet`)
  }
})

test('FE-TEST-1 · die Dockerfile liest die Muster aus der Liste', (t) => {
  const wurzel = repoWurzel()
  if (!wurzel) return t.skip('backend/Dockerfile im Abbild nicht vorhanden (Nachweis per docker build)')
  const dockerfile = lies(join(wurzel, 'backend', 'Dockerfile'))
  const zeilen = dockerfile.split('\n')

  // 1. Build-Argument mit der Standard-Liste.
  assert.match(dockerfile, /^ARG NODE_TESTLISTE=tests\/testliste\.txt$/m,
    'backend/Dockerfile: ARG NODE_TESTLISTE=tests/testliste.txt fehlt')

  // 2. Die Ausführung nimmt $NODE_TESTLISTE — nicht mehr eine feste Liste.
  const runZeilen = zeilen.filter((z) => z.includes('node --test'))
  assert.ok(runZeilen.length >= 1, 'kein node --test in der Dockerfile')
  assert.ok(runZeilen.some((z) => z.includes('$muster') || z.includes('${muster}')),
    'node --test läuft NICHT über die Muster aus der Testliste')

  // 3. Keine eingebettete Musterliste mehr (eine Aussage, eine Quelle).
  for (const z of runZeilen) {
    assert.doesNotMatch(z, /tests\/[a-z0-9-]+\*/,
      `backend/Dockerfile führt wieder feste Muster in der node --test-Zeile: ${z.slice(0, 120)}`)
  }

  // 4. Leere Auswahl bricht ab, statt „alle Tests im Verzeichnis“ zu starten.
  assert.match(dockerfile, /if \[ -z "\$muster" \][\s\S]{0,400}?exit 1/,
    'backend/Dockerfile: leerer Auswahl fehlt der Abbruch (node --test ohne Argumente sucht selbst!)')
})

test('FE-TEST-1 · .gitattributes führt die Testliste mit merge=union zusammen', (t) => {
  const wurzel = repoWurzel()
  if (!wurzel) return t.skip('.gitattributes im Abbild nicht vorhanden (Nachweis per docker build)')
  const pfad = join(wurzel, '.gitattributes')
  assert.ok(existsSync(pfad), '.gitattributes fehlt im Repo')
  const regel = lies(pfad)
    .split('\n')
    .map((z) => z.trim())
    .find((z) => z.includes('frontend/tests/testliste.txt'))
  assert.ok(regel, '.gitattributes: keine Regel für frontend/tests/testliste.txt')
  assert.match(regel, /\bmerge=union\b/,
    '.gitattributes: frontend/tests/testliste.txt braucht merge=union')
})

test('FE-TEST-1 · die Auswahl-Datei ist nicht committet (nur lokal)', (t) => {
  const wurzel = repoWurzel()
  if (!wurzel) return t.skip('.gitignore im Abbild nicht vorhanden')
  const gitignore = lies(join(wurzel, '.gitignore'))
  assert.match(gitignore, /^frontend\/tests\/\.auswahl\.txt$/m,
    '.gitignore: frontend/tests/.auswahl.txt fehlt (darf nie ins Repo)')
})
