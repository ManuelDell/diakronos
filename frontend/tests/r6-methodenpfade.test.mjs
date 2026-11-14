/**
 * UI-R6c — Jeder Methodenpfad der R6-Oberfläche steht in `whitelist.json`.
 *
 * Befund der Karte: `whitelist.json` nennt für `get_anlegeorte` nur
 * `api.get_anlegeorte`, `rechte.get_anlegeorte`, `get_anlegeorte` und
 * `diakronos_app.api.rechte.get_anlegeorte`. Die Oberfläche rief trotzdem
 * `diakronos.diakronos.api.rechte.get_anlegeorte` — ein Pfad, den die Whitelist
 * NICHT kennt (er lief nur über den Rückfall `registriere_originalpfad`), und
 * der Kommentar daneben behauptete „Pfad aus whitelist.json“.
 *
 * Dieser Test prüft das nicht an einer Liste von Hand, sondern an den ECHTEN
 * Dateien: er liest jedes Methoden-Literal (`apiCall('a.b.c')`, `apiUrl(…)`,
 * `fetch(apiUrl(…))`) heraus und vergleicht es mit den `pfade`-Listen der
 * Whitelist.
 *
 * Zwei Prüfungen:
 *   1. Jeder Pfad steht in der Whitelist (Gegenprobe: `rechte.get_anlegeorte`
 *      zurück auf `diakronos.diakronos.…` → rot).
 *   2. In diesen Dateien steht KEIN Pfad mit `diakronos.`-Paketpräfix. Für
 *      `api.`/`rechte.`/`diakronos_app.` gibt es je Eintrag einen Whitelist-
 *      Pfad; ein zusätzlicher `diakronos.`-Pfad existiert dort nicht und wäre
 *      eine zweite, ungeprüfte Schreibweise — er liefe nur über den Rückfall,
 *      also an der Whitelist vorbei.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const HIER = path.dirname(fileURLToPath(import.meta.url))
const FRONTEND = path.resolve(HIER, '..')
const REPO = path.resolve(FRONTEND, '..')
const WHITELIST = path.join(REPO, 'backend/src/diakronos_app/frappe_compat/inventar/whitelist.json')

/** Die Dateien der R6-Oberfläche, die Methoden aufrufen. */
const DATEIEN = [
    'src/diakonos/composables/useAnlegenOrte.js',
    'src/diakonos/components/r6/GastFreigabe.vue',
    'src/gastinhalt/App.vue',
    // UI-R6d: Die R6-Knöpfe stehen jetzt auf den Lese-Unterseiten — deren
    // Methoden (Detail, Kommentar, Löschen; Wiki-Liste für „Ähnliche“) gehören
    // mitgeprüft.
    'src/diakonos/pages/BeitragDetail.vue',
    'src/diakonos/pages/WikiArtikel.vue',
]

/**
 * `frappe.*` gehört dem Rahmen (CSRF-Token, Sitzung), nicht der App: die
 * Whitelist führt ausschließlich `diakronos_app`-Funktionen und hat für
 * `frappe.sessions.get_csrf_token` keinen Eintrag — dessen Wächter ist der
 * Rahmen selbst. Diese Aufrufe werden deshalb nicht gegen die Whitelist
 * geprüft (sie sind KEINE App-Methoden); alles andere muss dort stehen.
 */
const RAHMEN_PRAEFIX = 'frappe.'

/** Alle `pfade` der Whitelist als eine Menge. */
function whitelistPfade() {
    const inhalt = JSON.parse(readFileSync(WHITELIST, 'utf8'))
    const menge = new Set()
    for (const eintrag of inhalt.eintraege || []) {
        for (const p of eintrag.pfade || []) menge.add(p)
    }
    return menge
}

/**
 * Methoden-Literale einer Datei.
 *
 * Gesucht werden die Aufrufwege dieser Oberfläche:
 *   apiCall('a.b.c', …) / apiGet('a.b.c', …) / apiUrl('a.b.c') / fetch(apiUrl('a.b.c'))
 * und indirekt über eine Konstante (`apiCall(PFAD_ANLEGEORTE, …)` mit
 * `const PFAD_ANLEGEORTE = 'rechte.get_anlegeorte'`). Nur der Pfad-Teil
 * (Ziffern, Buchstaben, `_`, `.`) zählt; Argumente und Kommentare fallen weg.
 * Importe (`.js`/`.mjs`) werden nicht erfasst, weil sie keinen Methodennamen
 * sind — der Ausdruck verlangt mindestens einen Punkt und keinen Schrägstrich.
 */
function methodenPfade(quelle) {
    const treffer = []
    const CONST = "(?:const|let|var)\\s+([A-Za-z0-9_$]+)\\s*=\\s*'([A-Za-z0-9_]+(?:\\.[A-Za-z0-9_]+)+)'"
    const konstante = new Map()
    for (const m of quelle.matchAll(new RegExp(CONST, 'g'))) konstante.set(m[1], m[2])
    // `apiCall('a.b.c'` und `apiCall(PFAD_X` (Konstante, oben aufgelöst).
    const muster = /(?:apiCall|apiGet|apiUrl)\(\s*(?:'([A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+)'|([A-Za-z0-9_$]+))\s*[,)]/g
    for (const m of quelle.matchAll(muster)) {
        if (m[1]) treffer.push(m[1])
        else if (konstante.has(m[2])) treffer.push(konstante.get(m[2]))
    }
    return treffer
}

test('UI-R6c: jeder Methodenpfad der R6-Oberfläche steht in whitelist.json', () => {
    const erlaubt = whitelistPfade()
    assert.ok(erlaubt.size > 100, `Whitelist unerwartet klein: ${erlaubt.size} Pfade`)

    const fehlend = []
    const gefunden = []
    for (const rel of DATEIEN) {
        const quelle = readFileSync(path.join(FRONTEND, rel), 'utf8')
        const pfade = methodenPfade(quelle)
        assert.ok(pfade.length > 0, `${rel}: kein Methodenaufruf gefunden — Muster veraltet?`)
        for (const p of pfade) {
            if (p.startsWith(RAHMEN_PRAEFIX)) continue
            gefunden.push([rel, p])
            if (!erlaubt.has(p)) fehlend.push(`${rel}: ${p}`)
        }
    }

    // Sicherheitsnetz: die drei Dateien rufen wirklich die Methoden auf, um die
    // es in der Karte geht (sonst prüfte der Test eine leere Menge).
    const namen = gefunden.map(([, p]) => p)
    for (const erwartet of [
        'rechte.get_anlegeorte',
        'rechte.get_gastlinks',
        'rechte.gastlink_erstellen',
        'rechte.gastlink_widerrufen',
        'rechte.gast_inhalt',
        // UI-R6d: die Wege der Lese-Unterseiten.
        'beitraege.get_beitrag_detail',
        'beitraege.create_kommentar',
        'beitraege.delete_beitrag',
        'wiki.get_wiki_artikel_detail',
        'wiki.delete_wiki_artikel',
        // UI-R6e: `get_beitraege_liste` fällt hier weg — die Beitrags-Leseseite
        // holt die Liste nicht mehr (das Recht steht im Detail). Die WIKI-Liste
        // bleibt: sie trägt weiterhin „Ähnliche Artikel“.
        'wiki.get_wiki_artikel_liste',
    ]) {
        assert.ok(namen.includes(erwartet), `Aufruf ${erwartet} nicht gefunden — Test greift ins Leere`)
    }

    assert.deepEqual(fehlend, [], `Pfade ohne Whitelist-Eintrag: ${JSON.stringify(fehlend)}`)
})

test('UI-R6c: kein `diakronos.`-Paketpräfix in den R6-Dateien (nur Whitelist-Pfade)', () => {
    const verstoesse = []
    for (const rel of DATEIEN) {
        const quelle = readFileSync(path.join(FRONTEND, rel), 'utf8')
        for (const m of quelle.matchAll(/diakronos\.diakronos\.[A-Za-z0-9_.]+/g)) {
            verstoesse.push(`${rel}: ${m[0]}`)
        }
    }
    assert.deepEqual(verstoesse, [],
        `Pfad mit Paketpräfix (läuft nur über den Rückfall, nicht über die Whitelist): ${JSON.stringify(verstoesse)}`)
})
