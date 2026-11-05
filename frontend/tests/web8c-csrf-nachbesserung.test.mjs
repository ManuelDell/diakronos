/**
 * WEB-8c — Nachbesserung der CSRF-Heilung aus WEB-8b (Befunde R1–R10).
 *
 * Der Test prüft VERHALTEN an den ECHTEN Aufrufstellen (kein Nachbau der
 * Logik): `shared/csrf-heilung.js` wird mit seinen unveränderten
 * Nachbardateien in ein temporäres Verzeichnis kopiert und dort importiert
 * (wie `web8b-csrf-heilung.test.mjs`); `useApi.js` und `usePlanrahmen.js`
 * werden wie in `p21-sitzung.test.mjs` über ein `data:`-Modul geladen — nur
 * die Vue-/App-Ränder (Impersonation, Sitzungsdialog) sind ersetzt.
 *
 * Behoben werden (Karte WEB-8c):
 *   R1  `uploadDatei` prüfte nach der Heilung die ALTE 417-Antwort
 *       („[object Object]"). Erwartet: der Upload gelingt, `file_url` kommt an.
 *   R2  Jede Heilung schickte die Anfrage EINMAL zu viel (der Aufrufer rief
 *       `anfrage()` und `heileOderMelde` noch einmal). Erwartet: genau DREI
 *       fetch-Aufrufe (Versuch, Token, Wiederholung).
 *   R3  N parallele 417 -> EIN Token-Abruf; das Neuladen passiert genau
 *       einmal, spätere Aufrufer navigieren NICHT zusätzlich zur Anmeldung
 *       (sonst überschreibt `location.assign(logout)` das `reload()`).
 *   R4  Der Hinweis aus C2 erschien nie: der Hauptbereich öffnet den
 *       vorhandenen Sitzungsdialog (`sitzungBeendet(SITZUNG_HINWEIS)`); die
 *       öffentlichen Bundles gehen auf `?grund=csrf` (feste Kennung, kein
 *       Freitext in der Adresse).
 *   R7  Ohne nutzbaren `sessionStorage` kein Auto-Reload (Endlosschleife über
 *       Seitenleben hinweg) -> direkt zur Anmeldung mit Hinweis.
 *   R8  Gast-/Registrierungsseite: bei `e.sitzung`/`e.neuLaden` wird NICHTS
 *       gerendert (kein kurzes „Verbindungsfehler" vor der Navigation).
 *   R10 Kein zirkulärer Import mehr: `csrf-heilung.js` lädt ohne
 *       `sitzung-pruefen.js`.
 *
 * Läuft im Image (backend/Dockerfile, node-Testliste) und lokal per
 * `node --test tests/web8c-csrf-nachbesserung.test.mjs` (cwd = frontend/).
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFile, writeFile, mkdtemp, mkdir } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { pathToFileURL } from 'node:url'

const SRC = new URL('../src/', import.meta.url)
const lies = (rel) => readFile(new URL(rel, SRC), 'utf8')

// ── 1) Die echte Heilung, unverändert, mit ihren Nachbarn ──────────────────
const NACHBARN = {
    'shared/basis.js': await lies('shared/basis.js'),
    'shared/sitzung-pruefen.js': await lies('shared/sitzung-pruefen.js'),
    'shared/csrf-heilung.js': await lies('shared/csrf-heilung.js'),
}

// Die echte Präfix-Hilfe (kein Vue, kein Zustand) wird direkt geladen.
globalThis.__basis = await import('../src/shared/basis.js')
// UX2g: der Fehlerkatalog (echte Umsetzung) für die `data:`-Module unten.
globalThis.__fehlertexte = await import('../src/shared/fehlertexte.js')

/** Importiert die Heilung aus einem frischen Temp-Verzeichnis (eigenes Gedächtnis). */
async function heilungLaden({ ohneNachbarn = false } = {}) {
    const ziel = await mkdtemp(join(tmpdir(), 'web8c-'))
    await mkdir(join(ziel, 'shared'), { recursive: true })
    for (const [rel, inhalt] of Object.entries(NACHBARN)) {
        if (ohneNachbarn && rel.endsWith('sitzung-pruefen.js')) continue
        await writeFile(join(ziel, rel), inhalt)
    }
    return import(pathToFileURL(join(ziel, 'shared/csrf-heilung.js')).href)
}

// ── 2) useApi.js / usePlanrahmen.js mit ersetzten Vue-/App-Rändern ─────────
// Dieselben Ersetzungen wie `p21-sitzung.test.mjs`; geprüft wird die echte
// Aufrufstelle (Reihenfolge und Anzahl der fetch-Aufrufe).
function randErsetzen(quelle) {
    return quelle
        .replace("import { useImpersonation } from './useImpersonation.js'",
            "const useImpersonation = () => ({ isActive: { value: false } })")
        .replace("import { sitzungBeendet } from './useSitzungsablauf.js'",
            "const sitzungBeendet = (h) => { globalThis.__sitzungDialog = h ?? '' }")
        .replace("import { sitzungsFehlerMerken } from './sitzungsstand.js'",
            "const sitzungsFehlerMerken = (f) => { globalThis.__sitzungsFehler = f; return f }")
        .replace("import { istSitzungsAbbruch } from '../../shared/sitzung-pruefen.js'",
            "const istSitzungsAbbruch = (status, data) => [401, 419].includes(status) || (status === 417 && data?.exc_type === 'CSRFTokenError')")
        .replace("import { apiUrl } from '../../shared/basis.js'",
            "const apiUrl = globalThis.__basis.apiUrl")
        .replace(/import \{ ([^}]+) \} from '\.\.\/\.\.\/shared\/csrf-heilung\.js'/,
            (_, namen) => `const { ${namen} } = globalThis.__heilung`)
}

async function useApiLaden() {
    const quelle = randErsetzen(await lies('diakonos/composables/useApi.js'))
    return import('data:text/javascript;base64,' + Buffer.from(quelle).toString('base64'))
}

async function usePlanrahmenLaden() {
    globalThis.__api = await useApiLaden()
    const quelle = (await lies('diakonos/composables/usePlanrahmen.js'))
        // Die echten Helfer bleiben die echten Helfer: apiCall/apiAntwortPruefen
        // aus useApi.js werden VOR dem `data:`-Umbau ersetzt (sie ziehen Vue).
        .replace("import { ref, computed } from 'vue'",
            "const ref = (v) => ({ value: v }); const computed = (f) => ({ get value() { return f() } })")
        .replace("import { apiCall } from './useApi.js'", '')
        .replace("import { apiAntwortPruefen } from './useApi.js'", '')
        .replace("import { formatTemplate } from '../components/planrahmen/format.mjs'",
            "const formatTemplate = (t) => String(t ?? '')")
        .replace("import { GELOESCHT_ANZEIGE, istGeloescht } from './geloeschte-person.mjs'",
            "const GELOESCHT_ANZEIGE = 'Gelöschte Person'; const istGeloescht = () => false")
        .replace("import { stammdatenNormalisieren } from '../components/planrahmen/stammdaten.mjs'",
            "const stammdatenNormalisieren = (x) => x")
        .replace("import { setzeFeiertagskatalog } from '../components/planrahmen/anlaesse.mjs'",
            "const setzeFeiertagskatalog = () => {}")
        .replace("import { merkeKatalogDefinition, merkeKochbuchVorlage } from '../components/planrahmen/auswahlwerte.mjs'", '')
        .replace("import { wertAnzeige } from '../components/planrahmen/auswahlwerte.mjs'",
            "const merkeKatalogDefinition = () => {}; const merkeKochbuchVorlage = () => {}; const wertAnzeige = (w) => w")
        .replace(/import \{\n    cacheNutzerSetzen[\s\S]*?\} from '\.\/usePlanrahmenCache\.js'/,
            "const cacheNutzerSetzen = () => {}, standLesen = () => null, standSchreiben = () => {}, " +
            "staendeGleich = () => true, eintragVerwerfen = () => {}, browserCacheLeeren = () => {}")
        .replace("import { apiUrl } from '../../shared/basis.js'",
            "const apiUrl = globalThis.__basis.apiUrl")
        .replace(/import \{ ([^}]+) \} from '\.\.\/\.\.\/shared\/csrf-heilung\.js'/,
            (_, namen) => `const { ${namen} } = globalThis.__heilung`)
        // UX2g: der Fehlerkatalog als echte Umsetzung (der `data:`-Umbau kann
        // keinen relativen Pfad auflösen).
        .replace("import { fehlertext } from '../../shared/fehlertexte.js'",
            "const fehlertext = (...a) => globalThis.__fehlertexte.fehlertext(...a)")
        // `apiCall`/`apiAntwortPruefen` kommen aus dem echt geladenen useApi.js.
        .replace(/^/, 'const { apiCall, apiAntwortPruefen } = globalThis.__api\n')
    const modul = await import('data:text/javascript;base64,' + Buffer.from(quelle).toString('base64'))
    // `uploadDatei` liegt im zurückgegebenen Objekt (Composable-Fassade).
    return modul.usePlanrahmen()
}

// ── Attrappen ──────────────────────────────────────────────────────────────
const CSRF_DATEN = { message: 'CSRF-Token ungueltig oder fehlend.', exc_type: 'CSRFTokenError' }
const CSRF = () => ({ ok: false, status: 417, text: async () => JSON.stringify(CSRF_DATEN) })
const OK = (message = { gut: true }) => ({ ok: true, status: 200, text: async () => JSON.stringify({ message }) })

/**
 * Baut window/location/sessionStorage/fetch-Attrappen und gibt ein
 * Protokoll aller Aufrufe zurück.
 *
 * `antworten` ist eine Liste von Fabriken für Fach-Antworten (der Reihe nach);
 * der Token-Endpunkt antwortet immer mit `token`.
 */
function umgebung({ speicher = true, token = 'neu-2', antworten = [OK], reloadZaehlt = true } = {}) {
    const zustand = { reloads: 0, weiterleitungen: [], anfragen: [], tokens: [], logs: [] }
    const speicherMap = new Map()

    const sessionStorage = {
        getItem: (k) => (speicher ? (speicherMap.has(k) ? speicherMap.get(k) : null) : (() => { throw new Error('gesperrt') })()),
        setItem: (k, v) => { if (!speicher) throw new Error('gesperrt'); speicherMap.set(k, String(v)) },
        removeItem: (k) => { if (!speicher) throw new Error('gesperrt'); speicherMap.delete(k) },
    }
    const location = {
        pathname: '/diakronos', search: '', hash: '#/personen',
        reload: () => { if (reloadZaehlt) zustand.reloads++ },
        assign: (ziel) => { zustand.weiterleitungen.push(ziel) },
    }
    const document = {
        querySelector: (sel) => (String(sel).includes('csrf-token')
            ? { get content() { return window.__DIakonosBOOT.csrf_token }, set content(v) { window.__DIakonosBOOT.csrf_token = v },
                getAttribute: () => window.__DIakonosBOOT.csrf_token, setAttribute: (_n, v) => { window.__DIakonosBOOT.csrf_token = v } }
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
// R10 — kein zirkulärer Import
// ══════════════════════════════════════════════════════════════════════════

test('WEB-8c R10: csrf-heilung.js lädt OHNE sitzung-pruefen.js (kein Zirkel)', async () => {
    // Mit dem alten Stand fehlte `istSitzungsAbbruch` -> Import scheitert.
    const modul = await heilungLaden({ ohneNachbarn: true })
    assert.equal(typeof modul.heileOderMelde, 'function')
    assert.equal(typeof modul.istCsrfAblehnung, 'function')

    const quelle = NACHBARN['shared/csrf-heilung.js']
    assert.equal(/from '\.\/sitzung-pruefen\.js'/.test(quelle), false,
        'die Heilung importiert die Sitzungsprüfung nicht mehr')
    const pruefung = NACHBARN['shared/sitzung-pruefen.js']
    assert.equal(/import \{[^}]*\bistSitzungsAbbruch\b[^}]*\} from '\.\/csrf-heilung\.js'/.test(pruefung), false,
        'die Sitzungsprüfung holt `istSitzungsAbbruch` NICHT aus der Heilung')
})

// ══════════════════════════════════════════════════════════════════════════
// R2 — jede Heilung: Versuch, Token, Wiederholung = genau 3 fetch
// ══════════════════════════════════════════════════════════════════════════

test('WEB-8c R2: apiCall heilt mit GENAU 3 fetch-Aufrufen (kein Extra-Versuch)', async () => {
    globalThis.__heilung = await heilungLaden()
    const api = await useApiLaden()
    const { zustand, window } = umgebung({ antworten: [CSRF, OK({ gespeichert: true })] })

    const ergebnis = await api.apiCall('test.schreiben', { a: 1 })

    assert.equal(zustand.anfragen.filter(a => !a.url.includes('sitzung_status')).length, 2,
        'Versuch + genau eine Wiederholung (nicht drei Fach-Aufrufe)')
    assert.equal(zustand.anfragen.length, 3, 'Versuch, Token-Abruf, Wiederholung')
    assert.deepEqual(zustand.anfragen.map(a => a.url), [
        '/api/method/test.schreiben',
        '/api/method/diakronos.diakonos.api.session.sitzung_status',
        '/api/method/test.schreiben',
    ])
    assert.equal(zustand.tokens[0], 'alt-1', 'erster Versuch mit dem alten Token')
    assert.equal(zustand.tokens[2], 'neu-2', 'Wiederholung mit dem frischen Token')
    assert.equal(window.__DIakonosBOOT.csrf_token, 'neu-2')
    assert.deepEqual(ergebnis, { gespeichert: true })
})

test('WEB-8c R2: apiGet und antwortPruefen heilen ebenfalls ohne Extra-Versuch', async () => {
    globalThis.__heilung = await heilungLaden()
    const api = await useApiLaden()
    {
        const { zustand } = umgebung({ antworten: [CSRF, OK({ liste: [1] })] })
        const ergebnis = await api.apiGet('test.lesen', { q: 'x' })
        assert.deepEqual(ergebnis, { liste: [1] })
        assert.equal(zustand.anfragen.length, 3, 'apiGet: Versuch, Token, Wiederholung')
    }
    {
        const pruef = await import('../src/shared/sitzung-pruefen.js')
        const { zustand } = umgebung({ antworten: [OK({ ok: 1 })] })
        // Der Aufrufer hat die erste Antwort schon geholt (organigramm/App.vue).
        const erste = await globalThis.fetch('/api/method/test.org')
        const daten = await pruef.antwortPruefen(erste, { anfrage: () => globalThis.fetch('/api/method/test.org') })
        assert.deepEqual(daten, { message: { ok: 1 } })
        assert.equal(zustand.anfragen.length, 1, 'ohne CSRF kein zusätzlicher Aufruf')
    }
})

test('WEB-8c R2: antwortPruefen mit bereits gelesener 417-Antwort heilt in 2 Aufrufen', async () => {
    globalThis.__heilung = await heilungLaden()
    const pruef = await import('../src/shared/sitzung-pruefen.js')
    const { zustand } = umgebung({ antworten: [OK({ nodes: [] })] })

    const erste = CSRF()
    const daten = await pruef.antwortPruefen(erste, { anfrage: () => globalThis.fetch('/api/method/test.org') })

    assert.deepEqual(daten, { message: { nodes: [] } })
    assert.equal(zustand.anfragen.length, 2, 'Token-Abruf + Wiederholung (die 417 liegt schon vor)')
    assert.equal(zustand.anfragen[0].url.includes('sitzung_status'), true)
})

// ══════════════════════════════════════════════════════════════════════════
// R1 — uploadDatei: nach der Heilung gilt die NEUE Antwort
// ══════════════════════════════════════════════════════════════════════════

test('WEB-8c R1: uploadDatei liefert nach der Heilung die file_url (kein „[object Object]")', async () => {
    globalThis.__heilung = await heilungLaden()
    const plan = await usePlanrahmenLaden()
    const { zustand } = umgebung({
        antworten: [CSRF, OK({ file_url: '/files/noten.pdf', file_name: 'noten.pdf' })],
    })

    const datei = new Blob(['%PDF-1.4 test'], { type: 'application/pdf' })
    datei.name = 'noten.pdf'

    const ergebnis = await plan.uploadDatei(datei)

    assert.deepEqual(ergebnis, { file_url: '/files/noten.pdf', file_name: 'noten.pdf' },
        'die Felder der WIEDERHOLTEN Antwort kommen an')
    assert.equal(zustand.anfragen.filter(a => a.url.includes('upload_file')).length, 2,
        'Upload genau einmal + genau eine Wiederholung')
    assert.equal(zustand.anfragen.length, 3, 'Upload, Token, Upload-Wiederholung')
})

test('WEB-8c R1: uploadDatei wirft bei fachlichem Fehler die Servermeinung', async () => {
    globalThis.__heilung = await heilungLaden()
    const plan = await usePlanrahmenLaden()
    umgebung({
        antworten: [() => ({ ok: false, status: 417, text: async () => JSON.stringify({ message: 'Dateiinhalt oder Content-Type nicht erlaubt (SVG ist gesperrt).', exc_type: 'ValidationError' }) })],
    })
    const datei = new Blob(['<svg/>'], { type: 'image/svg+xml' })
    datei.name = 'boese.svg'

    await assert.rejects(() => plan.uploadDatei(datei), (e) => {
        assert.equal(e.status, 417)
        assert.match(e.message, /nicht erlaubt/)
        return true
    })
})

// ══════════════════════════════════════════════════════════════════════════
// R3 — parallele Fehler: EIN Token-Abruf, EIN Neuladen, keine Anmeldung
// ══════════════════════════════════════════════════════════════════════════

test('WEB-8c R3: zwei parallele CSRF-Fehler -> 1 Token-Abruf, 1 reload, KEINE Anmeldung', async () => {
    globalThis.__heilung = await heilungLaden()
    const api = await useApiLaden()
    // Beide Versuche und beide Wiederholungen scheitern -> Neuladen.
    const { zustand } = umgebung({ antworten: [CSRF] })

    const [a, b] = await Promise.allSettled([
        api.apiCall('test.a'),
        api.apiCall('test.b'),
    ])

    const tokenAbrufe = zustand.anfragen.filter(x => x.url.includes('sitzung_status')).length
    assert.equal(tokenAbrufe, 1, 'N parallele 417 teilen sich EINEN Token-Abruf')
    // WEB-8e (E1): der Hauptbereich navigiert NICHT mehr weg — er zeigt den
    // vorhandenen Dialog (weder `reload()` noch `location.assign`).
    assert.equal(zustand.reloads, 0, 'kein Neuladen im Hauptbereich')
    assert.deepEqual(zustand.weiterleitungen, [], 'kein location.assign zur Anmeldung')
    assert.equal(a.status, 'rejected')
    assert.equal(b.status, 'rejected')
    // WEB-8e (E1): beide Aufrufer gehen als Dialog-Fehler durch —
    // `sitzung` + `imBereich`, ohne Navigationsmerker.
    const gruende = [a.reason, b.reason]
    assert.ok(gruende.every(f => f?.sitzung === true && f?.imBereich === true),
        'beide sind Dialog-Fehler im Bereich')
    assert.equal(gruende.some(f => f?.neuLaden), false, 'kein Neulade-Merker im Hauptbereich')
    assert.equal(gruende.some(f => f?.weitergeleitet), false, 'niemand wird zur Anmeldung geschickt')
})

// ══════════════════════════════════════════════════════════════════════════
// R4 — der Hinweis aus C2 erscheint (Dialog im Hauptbereich, ?grund=csrf öffentlich)
// ══════════════════════════════════════════════════════════════════════════

test('WEB-8c R4: im Sperrfenster öffnet der Hauptbereich den Sitzungsdialog mit HINWEIS', async () => {
    globalThis.__heilung = await heilungLaden()
    const api = await useApiLaden()
    const { zustand, window } = umgebung({ antworten: [CSRF] })
    window.sessionStorage.setItem('dk-csrf-neuladen', String(Date.now() - 5_000))
    globalThis.__sitzungDialog = null

    // Der Hauptbereich uebersetzt den Heilungs-Fehler in den vorhandenen
    // Dialog (so macht es die Fehlerbehandlung von apiCall/useApi).
    let fehler = null
    try {
        await api.apiCall('test.a')
    } catch (e) {
        fehler = e
    }

    assert.equal(zustand.reloads, 0, 'kein zweites Neuladen im Fenster')
    assert.ok(fehler, 'der Aufrufer bekommt einen Fehler')
    assert.equal(fehler.sitzung, true, 'als Sitzungsende gekennzeichnet')
    assert.equal(fehler.hinweis, 'Sitzung abgelaufen — bitte neu anmelden.', 'R4: fester Hinweis am Fehler')
    assert.equal(typeof api.pruefeSitzungsAntwort, 'function')
    api.pruefeSitzungsAntwort({ ok: false, status: 417 }, { exc_type: 'CSRFTokenError' }, fehler.hinweis)
    assert.equal(globalThis.__sitzungDialog, 'Sitzung abgelaufen — bitte neu anmelden.',
        'der vorhandene Dialog bekommt den festen Hinweis (R4)')
    assert.deepEqual(zustand.weiterleitungen.filter(z => String(z).includes('/login')), [],
        'Hauptbereich navigiert NICHT weg (würde das reload() überschreiben)')
})

test('WEB-8c R4: öffentliche Maske geht auf ?grund=csrf (feste Kennung, kein Freitext)', async () => {
    const modul = await heilungLaden()
    const { zustand, window } = umgebung({ antworten: [CSRF] })
    window.sessionStorage.setItem('dk-csrf-neuladen', String(Date.now() - 5_000))
    window.__DIakonosBOOT.basePath = '/diakronos'

    await assert.rejects(() => modul.heileOderMelde({ anfrage: () => globalThis.fetch('/api/method/x') }))

    assert.equal(zustand.weiterleitungen.length, 1)
    const ziel = zustand.weiterleitungen[0]
    assert.match(ziel, /^\/diakronos\/login\?/)
    assert.match(ziel, /[?&]grund=csrf(&|$)/, 'feste Kennung statt freiem Text')
    assert.equal(ziel.includes('Sitzung'), false, 'kein Freitext in der Adresse')
    assert.match(ziel, /redirect-to=/, 'Rücksprungziel bleibt erhalten')
})

// ══════════════════════════════════════════════════════════════════════════
// R7 — ohne sessionStorage kein Auto-Reload (sonst Endlosschleife)
// ══════════════════════════════════════════════════════════════════════════

test('WEB-8c R7: sessionStorage gesperrt -> KEIN Auto-Reload, direkt Anmeldung mit Hinweis', async () => {
    const modul = await heilungLaden()
    {
        // a) Speicher wirft (Privatmodus)
        const { zustand } = umgebung({ speicher: false, antworten: [CSRF] })
        await assert.rejects(() => modul.heileOderMelde({ anfrage: () => globalThis.fetch('/api/method/x') }))
        assert.equal(zustand.reloads, 0, 'kein Neuladen ohne Merker (sonst Schleife über Seitenleben)')
        assert.equal(zustand.weiterleitungen.length, 1, 'stattdessen die Anmeldemaske')
        assert.match(zustand.weiterleitungen[0], /grund=csrf/)
    }
    {
        // b) Speicher fehlt ganz (undefined)
        const modul2 = await heilungLaden()
        const { zustand } = umgebung({ antworten: [CSRF] })
        delete globalThis.sessionStorage
        await assert.rejects(() => modul2.heileOderMelde({ anfrage: () => globalThis.fetch('/api/method/x') }))
        assert.equal(zustand.reloads, 0)
        assert.equal(zustand.weiterleitungen.length, 1)
    }
})

test('WEB-8c R7: letzteHeilung() liefert null, wenn es keinen sessionStorage gibt', async () => {
    const modul = await heilungLaden()
    umgebung()
    delete globalThis.sessionStorage
    const wert = await Promise.resolve(modul.letzteHeilung()).catch(() => 'Fehler')
    assert.equal(wert, null)
})

// ══════════════════════════════════════════════════════════════════════════
// R8 — Gast-/Registrierungsseite: nichts rendern, wenn navigiert wird
// ══════════════════════════════════════════════════════════════════════════

test('WEB-8c R8: Gast-/Registrierungsformular zeigt bei Sitzungsende KEINEN Verbindungsfehler', async () => {
    for (const datei of ['gast/App.vue', 'registrierung/components/DkAnmeldeformular.vue']) {
        const quelle = await lies(datei)
        // WEB-8d (N3) / WEB-8e (E2): KEINE Meldung, solange navigiert wird.
        // WEB-8e: Gastseiten kennen kein `weitergeleitet` mehr (sie werden nie
        // zur Anmeldung geschickt) — geprueft wird der Weg, der bleibt.
        assert.match(quelle, /e\?\.neuLaden/, `${datei}: fängt e.neuLaden ab`)
        // Der Fangzweig darf den Verbindungstext NICHT fuer Sitzungsende setzen:
        // er muss `neuLaden` VOR der Meldung abfangen.
        const zweig = quelle.slice(quelle.indexOf('} catch (e'), quelle.indexOf('} finally'))
        assert.ok(zweig.length > 0, `${datei}: Fangzweig gefunden`)
        assert.match(zweig, /if \(e\?\.neuLaden\) return/,
            `${datei}: laufende Navigation kehrt VOR jeder Meldung zurueck`)
        const vorMeldung = zweig.slice(0, zweig.indexOf("fehler.value = 'Verbindungsfehler"))
        assert.ok(vorMeldung.length > 0, `${datei}: der Fangzweig setzt die Meldung`)
        assert.match(vorMeldung, /e\?\.neuLaden/, `${datei}: die Pruefung steht vor der Meldung`)
    }
})

// ══════════════════════════════════════════════════════════════════════════
// R9 — useApi.js: kein toter Zweig in pruefeSitzungsAntwort
// ══════════════════════════════════════════════════════════════════════════

test('WEB-8c R9: pruefeSitzungsAntwort enthält keine CSRF-Sonderbehandlung mehr', async () => {
    const quelle = await lies('diakonos/composables/useApi.js')
    const start = quelle.indexOf('export function pruefeSitzungsAntwort')
    const ende = quelle.indexOf('export async function apiAntwortPruefen')
    const rumpf = quelle.slice(start, ende)
    assert.ok(start > 0 && ende > start)
    assert.equal(rumpf.includes('istCsrfAblehnung'), false,
        'CSRF-Ablehnungen sind hier nie mehr wahr (geheilt oder Neuladen) — der Zweig war tot')
    assert.equal(rumpf.includes('sitzungBeendet'), true, 'Sitzungsabbruch öffnet weiter den Dialog')
})
