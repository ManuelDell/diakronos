/**
 * FIX-6c — Toter Code in `composables/eingabeart.mjs` und die doppelte
 * Mobilgrenze 720 (Befunde 4 + 6 aus dem Review zu FIX-6).
 *
 * Befund 4: `useEingabeart`, `lageImBrowser`, `istMobilLayoutImBrowser`,
 *   `istTouch` und `GROBER_ZEIGER_ABFRAGE` wurden von KEINER Komponente
 *   importiert — nur von den Tests selbst. Der lebende Code liest Breite und
 *   Zeiger direkt (`PrTabelle.vue` nimmt `MOBIL_GRENZE_PX`, das CSS hat seine
 *   eigenen `@media`-Regeln). Toter Code, der wie eine benutzte Schnittstelle
 *   aussieht, ist eine Falle: der nächste Bearbeiter ändert ihn und wundert
 *   sich, dass nichts passiert. Deshalb ist er entfernt.
 *
 * Befund 6: die Mobilgrenze 720 px stand zweimal im Skript-Bestand — als
 *   `MOBIL_GRENZE_PX` (eingabeart.mjs) und als `HANDY_HINWEIS_PX`
 *   (handyHinweis.mjs). Zwei Zahlen, die gleich bleiben MÜSSEN, driften
 *   irgendwann; die Hinweisgrenze leitet sich jetzt aus der einen Grenze ab.
 *
 * Befund 3 (Wächter): der Touch-Kontext-Wächter in
 *   `tests/dev3-dialog-ueberschriften.test.mjs` akzeptierte noch das frühere
 *   zusammengesetzte Kriterium `not ((pointer: fine)` als Touch-Kontext. Seit
 *   der Operator-Entscheidung (27.10.) gilt NUR `(pointer: coarse)` — ein
 *   `not ((pointer: fine)` ist keine Touch-Regel mehr.
 *
 * Geprüft wird:
 *   1. Keine Komponente importiert die entfernten Namen (und die Datei
 *      exportiert sie auch nicht mehr).
 *   2. Jeder verbleibende Export von `eingabeart.mjs` wird in `src/` benutzt.
 *   3. `HANDY_HINWEIS_PX` ist die eine Grenze (`MOBIL_GRENZE_PX`), und 720
 *      steht in keiner anderen `.mjs` als Mobilgrenze.
 *   4. Beide Grenzen verhalten sich gleich, inklusive der Grenzpixel.
 *   5. Der Touch-Wächter akzeptiert `not ((pointer: fine)` nicht mehr.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import * as eingabeart from '../src/diakonos/composables/eingabeart.mjs'
import { istSchmal, hinweisZeigen, HANDY_HINWEIS_PX } from '../src/diakonos/composables/handyHinweis.mjs'

const WURZEL = new URL('../src/diakonos/', import.meta.url)
const lies = (p) => readFileSync(new URL(p, WURZEL), 'utf8')

/** Alle Dateien unter src/diakonos (rekursiv), ohne Testdateien. */
function quellen(suffixe = ['.vue', '.css', '.mjs']) {
    const gefunden = []
    const lauf = (dir) => {
        for (const name of readdirSync(dir)) {
            const pfad = dir + '/' + name
            if (statSync(pfad).isDirectory()) { lauf(pfad); continue }
            if (suffixe.some((s) => name.endsWith(s)) && !name.includes('.test.')) gefunden.push(pfad)
        }
    }
    lauf(fileURLToPath(WURZEL))
    return gefunden
}

function ohneKommentare(text) {
    return text
        .replace(/\/\*[\s\S]*?\*\//g, '')
        .replace(/^\s*\/\/.*$/gm, '')
}

/** Nur der <style>-Teil einer .vue-Datei (Template-Text zählt nicht). */
function stilTeil(quelle) {
    const start = quelle.search(/<style[^>]*>/)
    if (start < 0) return quelle
    return quelle.slice(start).replace(/<\/?style[^>]*>/g, '')
}

// ── 1. Toter Code ist weg ───────────────────────────────────────────────────

const ENTFERNT = [
    'useEingabeart',
    'lageImBrowser',
    'istMobilLayoutImBrowser',
    'istTouch',
    'GROBER_ZEIGER_ABFRAGE',
]

test('FIX-6c: die unbenutzten Exporte sind aus eingabeart.mjs entfernt', () => {
    for (const name of ENTFERNT) {
        assert.equal(name in eingabeart, false,
            `eingabeart.mjs exportiert "${name}" noch — keine Komponente nutzt ihn`)
        assert.equal(eingabeart[name], undefined,
            `eingabeart.mjs exportiert "${name}" noch — keine Komponente nutzt ihn`)
    }
})

test('FIX-6c: keine Quelle importiert die entfernten Namen', () => {
    for (const pfad of quellen()) {
        const text = ohneKommentare(readFileSync(pfad, 'utf8'))
        for (const name of ENTFERNT) {
            // Wortgrenze: `istMobilLayout` ist NICHT `istMobilLayoutImBrowser`.
            const treffer = new RegExp(`\\b${name}\\b`).test(text)
            assert.equal(treffer, false, `${pfad}: benutzt "${name}", das es nicht mehr gibt`)
        }
    }
})

test('FIX-6c: jeder verbleibende Export von eingabeart.mjs wird in src/ benutzt', () => {
    const flaeche = quellen()
        .filter((p) => !p.endsWith('composables/eingabeart.mjs'))
        .map((p) => ohneKommentare(readFileSync(p, 'utf8')))
        .join('\n')
    const exporte = Object.keys(eingabeart)
    assert.ok(exporte.length > 0, 'eingabeart.mjs exportiert nichts mehr')
    for (const name of exporte) {
        assert.ok(new RegExp(`\\b${name}\\b`).test(flaeche),
            `"${name}" wird in keiner Komponente benutzt — toter Export`)
    }
    // Der Randfall, der die Grenze trägt, muss ausdrücklich dabei sein.
    assert.ok(exporte.includes('MOBIL_GRENZE_PX'), 'MOBIL_GRENZE_PX fehlt (PrTabelle.vue nutzt es)')
    // `SCHMAL_ABFRAGE` (Kartenvorgabe T1: „behalten“) ist mit entfernt, weil
    // NICHTS es liest — auch nicht das CSS. Eine Abfrage-Zeichenkette im
    // Skript, die niemand auswertet, wäre genau der tote Code, den die Karte
    // beseitigt; wer sie braucht, baut sie aus MOBIL_GRENZE_PX.
    assert.equal(exporte.includes('SCHMAL_ABFRAGE'), false,
        'SCHMAL_ABFRAGE hat keinen Benutzer mehr und ist entfernt')
})

// ── 2. Eine Mobilgrenze ─────────────────────────────────────────────────────

test('FIX-6c: HANDY_HINWEIS_PX ist die eine Grenze der App (kein zweites Literal)', () => {
    assert.equal(HANDY_HINWEIS_PX, eingabeart.MOBIL_GRENZE_PX,
        'HANDY_HINWEIS_PX muss aus MOBIL_GRENZE_PX kommen')
    assert.equal(HANDY_HINWEIS_PX, 720)
})

test('FIX-6c: 720 steht in keiner anderen .mjs als Mobilgrenze', () => {
    const fehler = []
    for (const pfad of quellen(['.mjs'])) {
        if (pfad.endsWith('composables/eingabeart.mjs')) continue // die eine Definition
        const text = ohneKommentare(readFileSync(pfad, 'utf8'))
        const kurz = pfad.slice(pfad.indexOf('diakonos/') + 'diakonos/'.length)
        if (/\b720\b/.test(text)) fehler.push(`${kurz}: Zahl 720 (Grenze aus eingabeart.mjs importieren)`)
        if (/\bMOBIL_GRENZE_PX\s*=|export const HANDY_HINWEIS_PX\s*=\s*\d/.test(text)) {
            fehler.push(`${kurz}: eigene Grenzkonstante`)
        }
    }
    assert.deepEqual(fehler, [], `Doppelte Mobilgrenze:\n${fehler.join('\n')}`)
})

test('FIX-6c: beide Grenzen verhalten sich gleich (auch am Grenzpixel)', () => {
    // 720 gehört noch zum schmalen Bereich, 721 nicht mehr — für den Hinweis
    // wie für das Layout.
    for (const breite of [320, 390, 390.5, 720, 721, 1024, 1366, 1410]) {
        const schmal = istSchmal(breite)
        const mobil = breite > 0 && breite <= eingabeart.MOBIL_GRENZE_PX
        assert.equal(schmal, mobil, `Breite ${breite}: Hinweis ${schmal}, Layout ${mobil}`)
    }
    assert.equal(istSchmal(720), true, '720 px gehört noch dazu')
    assert.equal(istSchmal(721), false, '721 px ist Desktop')
    assert.equal(istSchmal(0), false, 'unbekannte Breite ist nicht schmal')
    assert.equal(istSchmal(NaN), false, 'unbekannte Breite ist nicht schmal')
    // Der Hinweis hängt zusätzlich am Bearbeitungsrecht (unverändert).
    assert.equal(hinweisZeigen({ schmal: true, darfBearbeiten: false }), false)
    assert.equal(hinweisZeigen({ schmal: true, darfBearbeiten: true }), true)
})

// ── 3. Wächter: nur (pointer: coarse) ist Touch-Kontext ─────────────────────

test('FIX-6c: der Touch-Wächter der Dialog-Überschriften akzeptiert kein "not ((pointer: fine)" mehr', () => {
    const text = lies('../../tests/dev3-dialog-ueberschriften.test.mjs')
    const treffer = text.match(/const TOUCH_MEDIA = (\/.+?\/[a-z]*)\s*$/m)
    assert.ok(treffer, 'TOUCH_MEDIA nicht gefunden')
    const quelle = treffer[1]
    assert.ok(/coarse/.test(quelle), `TOUCH_MEDIA prüft kein "pointer: coarse" mehr: ${quelle}`)
    assert.ok(!/fine/.test(quelle),
        `TOUCH_MEDIA lässt noch das alte Kriterium "not ((pointer: fine)" gelten: ${quelle}`)
})

test('FIX-6c: keine Touch-Regel im Stylesheet benutzt noch "not ((pointer: fine)"', () => {
    const fehler = []
    for (const pfad of quellen(['.css', '.vue'])) {
        const text = ohneKommentare(stilTeil(readFileSync(pfad, 'utf8')))
        around: for (const m of text.matchAll(/@media\s*([^{]+)\{/g)) {
            if (/not\s*\(\s*\(\s*pointer\s*:\s*fine\s*\)/i.test(m[1])) {
                fehler.push(`${pfad}: @media ${m[1].trim()}`)
                break around
            }
        }
    }
    assert.deepEqual(fehler, [],
        `Touch-Kontext ist nur (pointer: coarse):\n${fehler.join('\n')}`)
})
