/**
 * WEB-8d — Nachbesserungen aus dem Opus-Review zu WEB-8b/8c (Teil 2).
 *
 *   M2  `SitzungsHinweis.vue` fragte den abgelegten Sitzungsfehler 4x je
 *       Sekunde ab (`setInterval(…, 250)`), und `sitzungsstand.js` hielt den
 *       Fehler in einem einfachen Objekt. Erwartet: `shallowRef` + `watch` —
 *       kein Takt, keine Dauerabfrage.
 *   N3  Fehler, bei denen schon navigiert wird (`neuLaden`/`weitergeleitet`),
 *       sind als solche markiert und `mitSitzungsdialog` überspringt sie —
 *       sonst blitzt der Sitzungsdialog vor `reload()`/Weiterleitung auf.
 *   N4  `organigramm/App.vue` prüft `e?.sitzung` statt `instanceof
 *       SitzungsFehler` (die Klasse ist mit `data:`-Modulen nicht eindeutig).
 *   N9  Der R8-Wächter prüft VERHALTEN (Fehlerformen gegen die echten
 *       Gastzweige), nicht mehr den Quelltext per Regex.
 *
 * Läuft im Image (backend/Dockerfile, node-Testliste) und lokal per
 * `node --test tests/web8d-nachbesserung.test.mjs` (cwd = frontend/).
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFile, writeFile, mkdtemp } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { pathToFileURL } from 'node:url'

const SRC = new URL('../src/', import.meta.url)
const lies = (rel) => readFile(new URL(rel, SRC), 'utf8')

// ══════════════════════════════════════════════════════════════════════════
// M2 — sitzungsstand.js: shallowRef statt einfaches Objekt
// ══════════════════════════════════════════════════════════════════════════

/** Lädt `sitzungsstand.js` mit einer Attrappe für `vue` (shallowRef + watch). */
async function standLaden() {
    const quelle = (await lies('diakonos/composables/sitzungsstand.js'))
        .replace("import { shallowRef, watch } from 'vue'",
            'const shallowRef = globalThis.__shallowRef\nconst watch = globalThis.__watch')
    // Echte Datei im Temp-Verzeichnis (data:-Module können `vue` nicht auflösen).
    const ziel = await mkdtemp(join(tmpdir(), 'web8d-stand-'))
    const datei = join(ziel, 'sitzungsstand.mjs')
    await writeFile(datei, quelle)
    return import(pathToFileURL(datei).href)
}

/** Minimale, aber echte Reaktivität: `value` meldet Änderungen an Beobachter. */
function vueAttrappe() {
    const leser = new Set()
    globalThis.__shallowRef = (wert) => {
        let inner = wert
        return {
            get value() { return inner },
            set value(neu) {
                if (neu === inner) return
                inner = neu
                for (const l of [...leser]) l(neu)
            },
        }
    }
    // `watch(quelle, rueckmeldung)`: sofort abonnieren, Abmeldefunktion zurück.
    globalThis.__watch = (quelle, rueckmeldung) => {
        const leserFn = () => rueckmeldung(quelle())
        leser.add(leserFn)
        return () => leser.delete(leserFn)
    }
}

test('WEB-8d M2: der Sitzungsstand ist reaktiv (shallowRef), nicht ein nacktes Objekt', async () => {
    vueAttrappe()
    const modul = await standLaden()
    const stand = modul.sitzungsFehlerStand
    assert.ok(stand && typeof stand === 'object', 'Stand vorhanden')
    assert.ok('value' in stand, 'shallowRef liefert `.value` (beobachtbar) — ein Objekt hätte das nicht')
})

test('WEB-8d M2: Merken/Lesen/Vergessen arbeiten auf `.value`', async () => {
    vueAttrappe()
    const modul = await standLaden()
    assert.equal(modul.sitzungsFehlerLesen(), null)
    const fehler = { hinweis: 'Sitzung abgelaufen' }
    modul.sitzungsFehlerMerken(fehler)
    assert.deepEqual(modul.sitzungsFehlerLesen(), fehler)
    modul.sitzungsFehlerVergessen()
    assert.equal(modul.sitzungsFehlerLesen(), null)
})

test('WEB-8d M2: ein neuer Fehler löst die Anzeige aus (watch, kein 250-ms-Takt)', async () => {
    vueAttrappe()
    const modul = await standLaden()
    let meldungen = 0
    // Genau das, was `SitzungsHinweis.vue` früher per Intervall tat:
    globalThis.__beobachte = () => { meldungen++ }
    modul.sitzungsFehlerBeobachten(globalThis.__beobachte)
    assert.equal(meldungen, 0, 'beim Beobachten wird nicht sofort gemeldet')

    modul.sitzungsFehlerMerken({ hinweis: 'neu' })
    assert.equal(meldungen, 1, 'der neue Stand meldet sich EINMAL (sofort, nicht nach 250 ms)')

    modul.sitzungsFehlerVergessen()
    assert.equal(meldungen, 2, 'auch das Vergessen meldet sich')
})

// ══════════════════════════════════════════════════════════════════════════
// M2b — SitzungsHinweis.vue: kein setInterval mehr
// ══════════════════════════════════════════════════════════════════════════

test('WEB-8d M2: SitzungsHinweis.vue hat KEINEN Takt mehr (kein setInterval/250)', async () => {
    const quelle = await lies('diakonos/components/SitzungsHinweis.vue')
    // Ohne Codezeile pruefen: der Kopf nennt den alten Takt als Begruendung.
    const code = quelle.split('\n').filter(z => !z.trim().startsWith('//')).join('\n')
    assert.equal(/setInterval/.test(code), false, 'kein Dauer-Takt mehr')
    assert.equal(/\b250\b/.test(code), false, 'und keine 250 ms')
    assert.match(code, /sitzungsEndeBeobachten|sitzungsFehlerBeobachten/,
        'die Anzeige hoert auf den Stand (watch) statt zu fragen')
    assert.match(code, /onUnmounted/, 'die Beobachtung wird beim Abbau gelöst')
})

// ══════════════════════════════════════════════════════════════════════════
// N3 — mitSitzungsdialog überspringt Fehler, bei denen schon navigiert wird
// ══════════════════════════════════════════════════════════════════════════

/** Lädt `useApi.js` mit ersetzten Vue-/App-Rändern (wie in p21-sitzung.test.mjs). */
async function useApiLaden({ merker = true } = {}) {
    globalThis.__heilung = await import('../src/shared/csrf-heilung.js')
    globalThis.__basis = await import('../src/shared/basis.js')
    let quelle = await lies('diakonos/composables/useApi.js')
    quelle = quelle
        .replace("import { useImpersonation } from './useImpersonation.js'",
            "const useImpersonation = () => ({ isActive: { value: false } })")
        .replace("import { sitzungBeendet } from './useSitzungsablauf.js'",
            "const sitzungBeendet = (h) => { globalThis.__sitzungDialog = h ?? '' }")
    // Der Ablageort ist optional: mit/ohne Merker prüfen (N3 deckt beide).
    quelle = merker
        ? quelle.replace("import { sitzungsFehlerMerken } from './sitzungsstand.js'",
            "const sitzungsFehlerMerken = (f) => { globalThis.__gemerkt = f; return f }")
        : quelle.replace("import { sitzungsFehlerMerken } from './sitzungsstand.js'", '')
            .replace(/sitzungsFehlerMerken\(fehler\)/, '(fehler)')
    quelle = quelle
        .replace("import { istSitzungsAbbruch } from '../../shared/sitzung-pruefen.js'",
            "const istSitzungsAbbruch = (status, data) => [401, 419].includes(status) || (status === 417 && data?.exc_type === 'CSRFTokenError')")
        .replace("import { apiUrl } from '../../shared/basis.js'",
            "const apiUrl = globalThis.__basis.apiUrl")
        .replace(/import \{ ([^}]+) \} from '\.\.\/\.\.\/shared\/csrf-heilung\.js'/,
            (_, namen) => `const { ${namen} } = globalThis.__heilung`)
    return import('data:text/javascript;base64,' + Buffer.from(quelle).toString('base64'))
}

function umgebung(antworten) {
    const zustand = { reloads: 0, weiterleitungen: [] }
    const speicher = new Map()
    const sessionStorage = {
        getItem: (k) => (speicher.has(k) ? speicher.get(k) : null),
        setItem: (k, v) => speicher.set(k, String(v)),
        removeItem: (k) => speicher.delete(k),
    }
    const location = {
        pathname: '/diakonos', search: '', hash: '#/kalender',
        reload: () => { zustand.reloads++ },
        assign: (z) => zustand.weiterleitungen.push(z),
    }
    globalThis.window = { __DIakonosBOOT: { basePath: '', csrf_token: 'alt' }, location, sessionStorage }
    globalThis.location = location
    globalThis.sessionStorage = sessionStorage
    globalThis.document = { querySelector: () => null }
    let nr = 0
    globalThis.fetch = async (url) => {
        const f = antworten[Math.min(nr, antworten.length - 1)]
        nr++
        return typeof f === 'function' ? f() : f
    }
    return zustand
}

const CSRF = () => ({ ok: false, status: 417, text: async () => JSON.stringify({ message: 'CSRF', exc_type: 'CSRFTokenError' }) })
const AUS = () => ({ ok: false, status: 401, text: async () => JSON.stringify({ message: 'Bitte anmelden', exc_type: 'SessionExpired' }) })

test('WEB-8d N3: mitSitzungsdialog laesst Fehler mit laufender Navigation unveraendert durch', async () => {
    const api = await useApiLaden()
    // Ein Fehler, bei dem bereits navigiert wird: KEIN Dialog, kein Merken.
    for (const marke of ['neuLaden', 'weitergeleitet']) {
        globalThis.__gemerkt = null
        globalThis.__sitzungDialog = null
        const fehler = new Error('läuft')
        fehler.sitzung = true
        fehler[marke] = true
        const ergebnis = await api.__mitSitzungsdialog(() => { throw fehler })
            .catch((e) => e)
        assert.equal(ergebnis, fehler, `${marke}: derselbe Fehler (kein Umbau)`)
        assert.equal(ergebnis.imBereich, undefined, `${marke}: kein Dialog-Aufblitzen`)
        assert.equal(globalThis.__gemerkt, null, `${marke}: nichts abgelegt -> Dialog oeffnet nicht`)
    }
})

test('WEB-8d N3: ein Sitzungsende OHNE Navigation oeffnet weiter den Dialog', async () => {
    const api = await useApiLaden()
    globalThis.__gemerkt = null
    const fehler = new Error('abgelaufen')
    fehler.sitzung = true
    const ergebnis = await api.__mitSitzungsdialog(() => { throw fehler }).catch((e) => e)
    assert.equal(ergebnis.imBereich, true)
    assert.equal(globalThis.__gemerkt, ergebnis, 'der Fehler wird fuer den Dialog abgelegt')
})

// ══════════════════════════════════════════════════════════════════════════
// N4 — organigramm/App.vue prüft e?.sitzung statt instanceof
// ══════════════════════════════════════════════════════════════════════════

test('WEB-8d N4: organigramm/App.vue prueft e?.sitzung (kein instanceof)', async () => {
    const quelle = await lies('organigramm/App.vue')
    // Ohne Kommentarzeilen pruefen: der Kopf nennt `instanceof` als Grund.
    const code = quelle.split('\n').filter(z => !z.trim().startsWith('//')).join('\n')
    assert.equal(/instanceof\s+SitzungsFehler/.test(code), false,
        'instanceof scheitert, sobald die Klasse aus einem anderen Modul kommt (data:-Module)')
    assert.match(code, /e\?\.sitzung/, 'die Markierung am Fehler wird geprueft')
})

// ══════════════════════════════════════════════════════════════════════════
// N9 — der R8-Wächter prüft Verhalten, nicht Quelltext
// ══════════════════════════════════════════════════════════════════════════

/**
 * Liest den `catch`-Zweig einer .vue-Datei und führt ihn als Funktion aus —
 * das VERHALTEN der Gastseite, ohne Vue zu brauchen.
 */
async function gastZweig(datei) {
    const quelle = await lies(datei)
    const start = quelle.indexOf('} catch (e)')
    const ende = quelle.indexOf('} finally')
    assert.ok(start > 0 && ende > start, `${datei}: Fangzweig gefunden`)
    let zweig = quelle.slice(start + '} catch (e) {'.length, ende)
    // Der Zweig setzt `fehler.value`; `fehler` ist eine Ref-Attrappe.
    const rumpf = `(e, fehler) => {${zweig}}`
    return eval(rumpf)
}

test('WEB-8d N9: Gastseiten melden bei laufender Navigation NICHTS (Verhalten)', async () => {
    for (const datei of ['gast/App.vue', 'registrierung/components/DkAnmeldeformular.vue']) {
        const zweig = await gastZweig(datei)
        for (const marke of ['neuLaden', 'weitergeleitet']) {
            const fehler = { value: '' }
            const e = new Error('x')
            e.sitzung = true
            e[marke] = true
            zweig(e, fehler)
            assert.equal(fehler.value, '', `${datei}/${marke}: keine Meldung vor dem Seitenwechsel`)
        }
    }
})

test('WEB-8d N9: Gastseiten zeigen die feste Meldung des Gast-Wegs (Verhalten)', async () => {
    for (const datei of ['gast/App.vue', 'registrierung/components/DkAnmeldeformular.vue']) {
        const zweig = await gastZweig(datei)
        const fehler = { value: '' }
        const e = new Error('Sitzung abgelaufen')
        e.sitzung = true
        e.gast = true
        e.meldung = true
        e.hinweis = 'Sitzung abgelaufen — bitte neu anmelden. Bitte öffne die Seite neu.'
        zweig(e, fehler)
        assert.equal(fehler.value, e.hinweis, `${datei}: fester Hinweis auf der Seite`)
    }
})

test('WEB-8d N9: ein echter Fachfehler bleibt der Verbindungstext (Verhalten)', async () => {
    for (const datei of ['gast/App.vue', 'registrierung/components/DkAnmeldeformular.vue']) {
        const zweig = await gastZweig(datei)
        const fehler = { value: '' }
        zweig(new Error('kaputt'), fehler)
        assert.match(fehler.value, /Verbindungsfehler/, `${datei}: unveraendert bei Fachfehlern`)
    }
})
