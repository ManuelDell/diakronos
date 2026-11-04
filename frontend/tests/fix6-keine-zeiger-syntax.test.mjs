/**
 * FIX-6 — Wächter: keine Media-Query-Syntax, die ältere Browser nicht kennen.
 *
 * Operator-Auflage (27.10., Punkt 2): keine `(not (… or …))`-Ausdrücke mehr —
 * die Stufe 4 der Media Queries (Media Queries Level 4) versteht Safari erst
 * ab 16.4; davor fällt die ganze Regel stillschweigend aus. Stattdessen
 * einfache Abfragen:
 *
 *   Layout  → `@media (max-width: 720px)`
 *   Touch   → `@media (pointer: coarse)`
 *
 * Ebenso verboten: `(any-pointer: …)` und `maxTouchPoints`/`ontouchstart` als
 * Kriterium — bloße Touch-FÄHIGKEIT ist kein Zeigegerät (ein Touch-Laptop mit
 * Maus ist ein Desktop).
 *
 * Geprüft werden die Quellen des Frontends UND die beiden im Backend
 * erzeugten Login-Masken (die liegen nicht im Frontend-Build, sind aber
 * ausgeliefertes CSS).
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const FRONTEND = fileURLToPath(new URL('../src/diakonos/', import.meta.url))
// `frontend/tests/` → `frontend/` → Repo-Wurzel. Der frühere Pfad
// (`../../../../` ab dieser Datei) zeigte nur zufällig richtig: er führt
// VIER Ebenen hoch, also aus dem Worktree heraus in den HAUPT-Checkout
// (`/root/projekte/diakronos-standalone/`). Geprüft wurde damit ein fremder
// Baum — der Test fiel um, sobald der Haupt-Checkout weiterlief, obwohl der
// Worktree unverändert war (gedrosselt am 2026-11-04 gemessen). Im Image ist
// `/build/` die Wurzel, auch dort stimmt dieser Weg.
const REPO = fileURLToPath(new URL('../', import.meta.url))
const BACKEND = REPO + 'backend/src/diakronos_app/'

/** Nur Style-Blöcke: Kommentare und Vue-Templates stören die Prüfung. */
function stil(quelle) {
    let text = quelle
    // Im Python-f-String stehen die CSS-Klammern doppelt (`{{`/`}}`), damit
    // Python sie nicht als Platzhalter liest — für die Prüfung wieder einfach.
    text = text.replace(/\{\{/g, '{').replace(/\}\}/g, '}')
    const start = text.search(/<style[^>]*>/)
    if (start >= 0) text = text.slice(start).replace(/<\/?style[^>]*>/g, '')
    return text
        .replace(/\/\*[\s\S]*?\*\//g, '')
        .replace(/^\s*\/\/.*$/gm, '')
        .replace(/^\s*#.*$/gm, '')
}

/**
 * Die Login-Masken werden auch ausgeliefert, ohne dass ihre Quelldateien im
 * Frontend-Build-Stage liegen (backend/ ist in `.dockerignore`). Fehlt die
 * Datei, prüft der Node-Lauf sie NICHT — dafür gibt es IM APP-IMAGE den
 * Python-Test `backend/tests/test_fix6_zeigegeraet.py`, der dieselben zwei
 * Zusicherungen an denselben Dateien prüft. Existiert die Datei (Worktree,
 * lokaler Lauf), wird sie hier mitgeprüft.
 */
function backendDatei(pfad) {
    return existsSync(pfad) ? readFileSync(pfad, 'utf8') : null
}

function quellen() {
    const gefunden = []
    const lauf = (dir) => {
        for (const name of readdirSync(dir)) {
            const pfad = dir + '/' + name
            if (statSync(pfad).isDirectory()) { lauf(pfad); continue }
            if (/\.(vue|css|mjs)$/.test(name) && !name.includes('.test.')) gefunden.push(pfad)
        }
    }
    lauf(FRONTEND)
    return gefunden
}

test('FIX-6: keine Stufe-4-Syntax `not (... or ...)` im Frontend', () => {
    for (const pfad of quellen()) {
        const text = stil(readFileSync(pfad, 'utf8'))
        assert.ok(!/@media[^{]*\bnot\s*\(/.test(text),
            `${pfad}: \`not (...)\` in einer @media-Regel (Safari < 16.4 kann das nicht)`)
        assert.ok(!/@media[^{]*\bor\b/.test(text),
            `${pfad}: \`or\` in einer @media-Regel (Media Queries Level 4)`)
        assert.ok(!/@media[^{]*\band\s*\(not\b/.test(text),
            `${pfad}: negierte Bedingung in einer @media-Regel`)
    }
})

const MASKEN = [BACKEND + 'spa.py', BACKEND + 'anmeldung/routen.py']

test('FIX-6: Login-Masken (spa.py, anmeldung/routen.py) ohne Stufe-4-Syntax', (t) => {
    let geprueft = 0
    for (const pfad of MASKEN) {
        const roh = backendDatei(pfad)
        if (roh === null) continue
        geprueft += 1
        const text = stil(roh)
        assert.ok(!/@media[^{]*\bnot\s*\(/.test(text),
            `${pfad}: \`not (...)\` in einer @media-Regel`)
        assert.ok(!/@media[^{]*\bany-pointer\b/.test(text),
            `${pfad}: \`any-pointer\` in einer @media-Regel`)
    }
    if (geprueft === 0) t.diagnostic('backend/ liegt im Build-Stage nicht vor — prueft test_fix6_zeigegeraet.py im Image')
})

test('FIX-6: 16-px-Felder der Login-Masken hängen am groben Zeiger', (t) => {
    let geprueft = 0
    for (const pfad of MASKEN) {
        const roh = backendDatei(pfad)
        if (roh === null) continue
        geprueft += 1
        const text = stil(roh)
        const ende = text.indexOf('(pointer: coarse)')
        assert.ok(ende >= 0, `${pfad}: \`@media (pointer: coarse)\` fehlt`)
        // Bis zum nächsten @media lesen — so weit reicht die 16-px-Regel.
        const block = text.slice(ende).split(/\n\s*@media/)[0]
        assert.ok(block.includes('font-size: 16px'),
            `${pfad}: \`@media (pointer: coarse)\` mit 16-px-Feldern fehlt`)
    }
    if (geprueft === 0) t.diagnostic('backend/ liegt im Build-Stage nicht vor — prueft test_fix6_zeigegeraet.py im Image')
})
