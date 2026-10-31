/**
 * WEB-8d — Zweite Nachbesserung der CSRF-Heilung.
 *
 * Befunde aus dem Opus-Review zu WEB-8b/8c. Der Test prüft VERHALTEN an den
 * ECHTEN Dateien (kein Nachbau der Logik): `shared/csrf-heilung.js` samt
 * Nachbarn wird in ein temporäres Verzeichnis kopiert und dort importiert.
 *
 *   M1  Gast-/Registrierungsseiten: die Token-Erneuerung über
 *       `session.sitzung_status` verlangt Anmeldung — ein Gast bekam 401,
 *       wurde zur Anmeldung geschickt und nach dem zweiten Fehler auf
 *       `/login` geparkt, obwohl er kein Konto hat. Erwartet:
 *       `heileOderMelde({gast: true})` überspringt den Token-Abruf, lädt
 *       höchstens EINMAL neu (frisches Seiten-Token über `location.reload()`,
 *       der 60-s-Schleifenschutz verhindert das zweite Neuladen) und
 *       NAVIGIERT NIE zur Anmeldung.
 *   N5  `sitzung-pruefen.js` holt `istCsrfAblehnung` und `SITZUNGS_STATUS` aus
 *       `csrf-heilung.js` (statt sie zeichengleich zu kopieren) und verweist
 *       im Kommentar auf eine EXISTIERENDE Testdatei.
 *   N6  `SITZUNG_GRUND` und `sitzungsFehler()` sind entfernt (ungenutzt).
 *
 * Läuft im Image (backend/Dockerfile, node-Testliste) und lokal per
 * `node --test tests/web8d-csrf-gastseiten.test.mjs` (cwd = frontend/).
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFile, writeFile, mkdtemp, mkdir } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { pathToFileURL } from 'node:url'

const SRC = new URL('../src/', import.meta.url)
const lies = (rel) => readFile(new URL(rel, SRC), 'utf8')

// ── Die echte Heilung, unverändert, mit ihren Nachbarn ────────────────────
const NACHBARN = {
    'shared/basis.js': await lies('shared/basis.js'),
    'shared/sitzung-pruefen.js': await lies('shared/sitzung-pruefen.js'),
    'shared/csrf-heilung.js': await lies('shared/csrf-heilung.js'),
}

globalThis.__basis = await import('../src/shared/basis.js')

/** Importiert die Heilung aus einem frischen Temp-Verzeichnis (eigenes Gedächtnis). */
async function heilungLaden() {
    const ziel = await mkdtemp(join(tmpdir(), 'web8d-'))
    await mkdir(join(ziel, 'shared'), { recursive: true })
    for (const [rel, inhalt] of Object.entries(NACHBARN)) {
        await writeFile(join(ziel, rel), inhalt)
    }
    return import(pathToFileURL(join(ziel, 'shared/csrf-heilung.js')).href)
}

// ── Attrappen ─────────────────────────────────────────────────────────────
const CSRF_DATEN = { message: 'CSRF-Token ungueltig oder fehlend.', exc_type: 'CSRFTokenError' }
const CSRF = () => ({ ok: false, status: 417, text: async () => JSON.stringify(CSRF_DATEN) })
const OK = (message = { gut: true }) => ({ ok: true, status: 200, text: async () => JSON.stringify({ message }) })

/**
 * Baut window/location/sessionStorage/fetch-Attrappen und gibt ein Protokoll
 * aller Aufrufe zurück. `sitzungStatus` antwortet auf den Token-Endpunkt:
 * `null` = der Endpunkt verlangt Anmeldung (401, so wie für einen Gast).
 */
function umgebung({ token = 'neu-2', sitzungStatus = 'ok', antworten = [OK] } = {}) {
    const zustand = { reloads: 0, weiterleitungen: [], anfragen: [], tokens: [], logs: [] }
    const speicherMap = new Map()

    const sessionStorage = {
        getItem: (k) => (speicherMap.has(k) ? speicherMap.get(k) : null),
        setItem: (k, v) => { speicherMap.set(k, String(v)) },
        removeItem: (k) => { speicherMap.delete(k) },
    }
    const location = {
        pathname: '/gast', search: '?token=abc', hash: '',
        reload: () => { zustand.reloads++ },
        assign: (ziel) => { zustand.weiterleitungen.push(ziel) },
    }
    const document = {
        querySelector: (sel) => (String(sel).includes('csrf-token')
            ? {
                get content() { return window.__DIakonosBOOT.csrf_token },
                set content(v) { window.__DIakonosBOOT.csrf_token = v },
                getAttribute: () => window.__DIakonosBOOT.csrf_token,
                setAttribute: (_n, v) => { window.__DIakonosBOOT.csrf_token = v },
            }
            : null),
    }
    const window = { __DIakonosBOOT: { basePath: '', csrf_token: 'alt-1' }, location, sessionStorage, document }
    globalThis.window = window
    globalThis.location = location
    globalThis.sessionStorage = sessionStorage
    globalThis.document = document
    for (const name of ['log', 'warn', 'error', 'info', 'debug']) {
        globalThis.console[name] = (...teile) => { zustand.logs.push(teile.map(String).join(' ')) }
    }

    let fachNr = 0
    globalThis.fetch = async (url, optionen = {}) => {
        zustand.anfragen.push({ url: String(url), optionen })
        zustand.tokens.push(optionen?.headers?.['X-Frappe-CSRF-Token'] ?? null)
        if (String(url).includes('session.sitzung_status')) {
            if (sitzungStatus === 'anmeldung') {
                // So antwortet der Server einem GAST: die Sitzung fehlt.
                const koerper = { message: 'Bitte melde dich an.', exc_type: 'SessionExpired' }
                return { ok: false, status: 401, text: async () => JSON.stringify(koerper) }
            }
            const koerper = { message: { user: 'anna', csrf_token: token } }
            return { ok: true, status: 200, json: async () => koerper, text: async () => JSON.stringify(koerper) }
        }
        const fabrik = antworten[Math.min(fachNr, antworten.length - 1)]
        fachNr++
        return typeof fabrik === 'function' ? fabrik() : fabrik
    }
    return { zustand, window }
}

// ══════════════════════════════════════════════════════════════════════════
// M1 — Gastseiten: kein Token-Abruf, höchstens EIN Neuladen, NIE /login
// ══════════════════════════════════════════════════════════════════════════

test('WEB-8d M1: heileOderMelde({gast:true}) ruft session.sitzung_status NICHT auf', async () => {
    const modul = await heilungLaden()
    // Der Token-Endpunkt antwortet hier wie für einen Gast: 401.
    const { zustand } = umgebung({ sitzungStatus: 'anmeldung', antworten: [CSRF] })

    let fehler = null
    try {
        await modul.heileOderMelde({ anfrage: () => globalThis.fetch('/api/method/x'), gast: true })
    } catch (e) {
        fehler = e
    }

    assert.ok(fehler, 'der Gast bekommt die Meldung auf der Seite')
    assert.equal(fehler.gast, true)
    assert.deepEqual(
        zustand.anfragen.map(a => a.url).filter(u => u.includes('sitzung_status')), [],
        'der Gast hat keine Sitzung — der Token-Endpunkt liefert ihm nur 401',
    )
    assert.equal(zustand.anfragen.filter(a => a.url === '/api/method/x').length, 1,
        'ohne Token gibt es keinen zweiten Versuch mit leerem Token')
})

test('WEB-8d M1: Gast lädt höchstens EINMAL neu (frisches Seiten-Token), dann feste Meldung', async () => {
    const modul = await heilungLaden()
    {
        // Erster Fehler: ein Neuladen ist erlaubt -> frisches Seiten-Token.
        const { zustand } = umgebung({ sitzungStatus: 'anmeldung', antworten: [CSRF] })
        let fehler = null
        try {
            await modul.heileOderMelde({ anfrage: () => globalThis.fetch('/api/method/x'), gast: true })
        } catch (e) {
            fehler = e
        }
        assert.equal(zustand.reloads, 1, 'genau EIN Neuladen (frisches Seiten-Token)')
        assert.deepEqual(zustand.weiterleitungen, [], 'NIE zur Anmeldung')
        assert.ok(fehler, 'der Aufrufer bekommt einen Fehler')
        assert.equal(fehler.sitzung, true)
        assert.equal(fehler.neuLaden, true, 'der Aufrufer erkennt „Seite lädt neu“')
        assert.equal(fehler.weitergeleitet, undefined, 'keine Weiterleitung zur Anmeldung')
        assert.equal(fehler.gast, true)
        assert.doesNotMatch(fehler.hinweis, /neu anmelden/,
            'die Person hat kein Konto — kein Anmelde-Hinweis')
        assert.match(fehler.hinweis, /öffne sie neu/, 'fester Hinweis: Seite neu öffnen')
    }
    {
        // Zweiter Fehler im 60-s-Fenster: KEIN zweites Neuladen, Meldung auf
        // der Seite — nicht die Anmeldemaske.
        const modul2 = await heilungLaden()
        const { zustand, window } = umgebung({ sitzungStatus: 'anmeldung', antworten: [CSRF] })
        window.sessionStorage.setItem('dk-csrf-neuladen', String(Date.now() - 5_000))
        let fehler = null
        try {
            await modul2.heileOderMelde({ anfrage: () => globalThis.fetch('/api/method/x'), gast: true })
        } catch (e) {
            fehler = e
        }
        assert.equal(zustand.reloads, 0, 'kein zweites Neuladen im Sperrfenster')
        assert.deepEqual(zustand.weiterleitungen, [], 'und erst recht keine Anmeldemaske')
        assert.equal(fehler.gast, true)
        assert.equal(fehler.meldung, true, 'die Seite zeigt den Hinweis selbst')
        assert.doesNotMatch(fehler.hinweis, /neu anmelden/)
        assert.match(fehler.hinweis, /öffne sie neu/)
    }
})

test('WEB-8d M1: without sessionStorage (Privatmodus) kein Neuladen — aber nie /login', async () => {
    const modul = await heilungLaden()
    const { zustand, window } = umgebung({ sitzungStatus: 'anmeldung', antworten: [CSRF] })
    // Speicher fehlt ganz: der Merker ginge über das Neuladen verloren.
    delete window.sessionStorage
    delete globalThis.sessionStorage

    let fehler = null
    try {
        await modul.heileOderMelde({ anfrage: () => globalThis.fetch('/api/method/x'), gast: true })
    } catch (e) {
        fehler = e
    }
    assert.equal(zustand.reloads, 0)
    assert.deepEqual(zustand.weiterleitungen, [], 'Gast wird nicht zur Anmeldung geschickt')
    assert.equal(fehler.gast, true)
    assert.equal(fehler.meldung, true)
})

test('WEB-8d M1: scheitert die Wiederholung erneut, bleibt der Gast auf der Seite', async () => {
    const modul = await heilungLaden()
    const { zustand } = umgebung({ sitzungStatus: 'anmeldung', antworten: [CSRF] })
    let fehler = null
    try {
        await modul.heileOderMelde({ anfrage: () => globalThis.fetch('/api/method/x'), gast: true })
    } catch (e) {
        fehler = e
    }
    assert.equal(zustand.reloads, 1)
    assert.deepEqual(zustand.weiterleitungen, [])
    assert.equal(fehler.gast, true)
})

test('WEB-8d M1: WITHOUT gast (Hauptbereich) bleibt der bisherige Weg erhalten', async () => {
    const modul = await heilungLaden()
    // Für angemeldete Nutzer wird der Token-Endpunkt weiter genutzt …
    const { zustand } = umgebung({ antworten: [CSRF, OK({ gespeichert: true })] })
    const ergebnis = await modul.heileOderMelde({
        anfrage: () => globalThis.fetch('/api/method/x'),
        ohneNavigation: true,
    })
    assert.deepEqual(ergebnis.data, { message: { gespeichert: true } })
    assert.equal(zustand.anfragen.length, 3, 'Versuch, Token-Abruf, Wiederholung')
    assert.equal(zustand.anfragen.some(a => a.url.includes('sitzung_status')), true)
})

// ══════════════════════════════════════════════════════════════════════════
// M1b — die Gastseiten benutzen den Gast-Weg
// ══════════════════════════════════════════════════════════════════════════

test('WEB-8d M1: Gast- und Registrierungsformular heilen über den Gast-Weg', async () => {
    for (const datei of ['gast/App.vue', 'registrierung/components/DkAnmeldeformular.vue']) {
        const quelle = await lies(datei)
        const aufruf = quelle.match(/heileOderMelde\(\{[^}]*\}\)/)
        assert.ok(aufruf, `${datei}: heileOderMelde-Aufruf gefunden`)
        assert.match(aufruf[0], /gast:\s*true/, `${datei}: Gastseite heilt ohne Sitzung`)
    }
})

// ══════════════════════════════════════════════════════════════════════════
// N5 — eine Wahrheit: sitzung-pruefen.js importiert die Regeln
// ══════════════════════════════════════════════════════════════════════════

test('WEB-8d N5: istCsrfAblehnung und SITZUNGS_STATUS kommen aus csrf-heilung.js', async () => {
    const modul = await heilungLaden()

    // Die Regeln sind DIESELBEN Objekte wie in der Heilung (keine Kopie).
    assert.equal(NACHBARN['shared/sitzung-pruefen.js'].includes('res?.status === 417'), false,
        'keine zeichengleiche Kopie der CSRF-Bedingung mehr')
    assert.equal(/^export const SITZUNGS_STATUS = \[401, 419\]$/m.test(NACHBARN['shared/sitzung-pruefen.js']), false,
        'SITZUNGS_STATUS wird nicht mehr neu angelegt')
    assert.equal(typeof modul.istCsrfAblehnung, 'function')
    assert.deepEqual(modul.SITZUNGS_STATUS, [401, 419])
})

test('WEB-8d N5: der Kommentar verweist auf eine EXISTIERENDE Testdatei', async () => {
    const pruefung = NACHBARN['shared/sitzung-pruefen.js']
    const verweise = [...pruefung.matchAll(/tests?\/([a-z0-9._-]+\.(?:test\.)?mjs)/g)].map(m => m[1])
    for (const name of verweise) {
        const treffer = name.endsWith('.test.mjs')
            ? lies(`../tests/${name}`).catch(() => null)
            : lies(`diakonos/composables/${name}`).catch(() => null)
        assert.ok(await treffer, `verwiesene Datei ${name} fehlt`)
    }
    assert.match(pruefung, /web8b-csrf-heilung\.test\.mjs|web8d-csrf-gastseiten\.test\.mjs/,
        'der Kommentar nennt einen echten Wächter')
})

// ══════════════════════════════════════════════════════════════════════════
// N6 — ungenutzte Ausfuhr entfernt
// ══════════════════════════════════════════════════════════════════════════

test('WEB-8d N6: SITZUNG_GRUND und sitzungsFehler() sind entfernt', async () => {
    const modul = await heilungLaden()
    // Nur die echten Ausfuhren zählen: der Dateikopf nennt die entfernten
    // Namen (Dokumentation), deshalb wird auf `export` geprüft.
    assert.equal(modul.SITZUNG_GRUND, undefined, 'SITZUNG_GRUND ist ungenutzt')
    assert.equal(modul.sitzungsFehler, undefined, 'sitzungsFehler() ist ungenutzt')
    assert.equal(/export const SITZUNG_GRUND\b/.test(NACHBARN['shared/csrf-heilung.js']), false)
    assert.equal(/export function sitzungsFehler\b/.test(NACHBARN['shared/csrf-heilung.js']), false)
})

test('WEB-8d N6: kein Quelltext benutzt die entfernten Namen', async () => {
    const dateien = [
        'diakonos/composables/useApi.js',
        'shared/sitzung-pruefen.js',
        'diakonos/components/SitzungsHinweis.vue',
    ]
    for (const datei of dateien) {
        const quelle = await lies(datei)
        assert.equal(/\bSITZUNG_GRUND\b/.test(quelle), false, `${datei}: SITZUNG_GRUND`)
        assert.equal(/\bsitzungsFehler\s*\(/.test(quelle), false, `${datei}: sitzungsFehler()`)
    }
})
