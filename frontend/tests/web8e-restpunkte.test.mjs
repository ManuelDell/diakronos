/**
 * WEB-8e — Restpunkte der CSRF-Heilung (Opus-Review zu WEB-8d).
 *
 * Der Test prüft VERHALTEN an den ECHTEN Dateien: `shared/csrf-heilung.js`
 * wird mit seinen Nachbarn in ein temporäres Verzeichnis kopiert und dort
 * importiert (wie `web8b-…`/`web8c-…`/`web8d-…`); `useApi.js` und
 * `sitzungsstand.js` werden mit ersetzten Vue-/App-Rändern geladen. Es gibt
 * KEIN handgebautes Fehlerobjekt als Grundlage — jeder Fall läuft durch das
 * echte `heileOderMelde` mit einer echten 417-Antwort ohne frisches Token.
 *
 *   E1  Hauptbereich: 417, aber kein frisches Token (Token-Endpunkt 401) ->
 *       der Fehler trägt `imBereich` und NICHT `neuLaden`;
 *       `mitSitzungsdialog` legt ihn über `sitzungsFehlerMerken` ab, der
 *       Dialog öffnet (M2-Watcher), die Seite lädt NICHT neu und es gibt
 *       keine Weiterleitung. Vorher setzte `zurAnmeldung('neuLaden',
 *       {ohneNavigation:true})` `neuLaden` UND `imBereich` — `useApi.js`
 *       wertete `neuLaden` als „navigiert schon" und der Fehler ging nicht
 *       in den Dialog (`sitzungImBereich` war unerreichbar).
 *   E2  Gastseiten: ein 401/419 (Sitzung weg) lädt NICHT neu, sondern meldet
 *       sofort (`gastFehler({neuLaden:false})`); nur eine CSRF-Ablehnung
 *       geht in den einmaligen Neulade-Weg.
 *   E3  Nach dem einmaligen Gast-Neuladen erscheint beim NEUEN Seitenleben
 *       ein kurzer Hinweis („Die Seite wurde neu geladen, bitte Eingaben
 *       prüfen.") — der Marker dafür ist `dk-csrf-neuladen`.
 *   E4  Kein Text „Die Anmeldung wird neu geladen …" auf Gastseiten.
 *
 * Läuft im Image (backend/Dockerfile, node-Testliste) und lokal per
 * `node --test tests/web8e-restpunkte.test.mjs` (cwd = frontend/).
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFile, writeFile, mkdtemp, mkdir } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { pathToFileURL } from 'node:url'

const SRC = new URL('../src/', import.meta.url)
const lies = (rel) => readFile(new URL(rel, SRC), 'utf8')

const GASTSEITEN = ['gast/App.vue', 'registrierung/components/DkAnmeldeformular.vue']

// ── Die echte Heilung mit ihren Nachbarn ──────────────────────────────────
const NACHBARN = {
    'shared/basis.js': await lies('shared/basis.js'),
    'shared/sitzung-pruefen.js': await lies('shared/sitzung-pruefen.js'),
    'shared/csrf-heilung.js': await lies('shared/csrf-heilung.js'),
}

globalThis.__basis = await import('../src/shared/basis.js')

/** Importiert die Heilung aus einem frischen Temp-Verzeichnis (eigenes Gedächtnis). */
async function heilungLaden() {
    const ziel = await mkdtemp(join(tmpdir(), 'web8e-'))
    await mkdir(join(ziel, 'shared'), { recursive: true })
    for (const [rel, inhalt] of Object.entries(NACHBARN)) await writeFile(join(ziel, rel), inhalt)
    return import(pathToFileURL(join(ziel, 'shared/csrf-heilung.js')).href)
}

// ── sitzungsstand.js echt laden (Vue durch eine kleine Attrappe ersetzt) ──
async function standLaden() {
    const quelle = (await lies('diakonos/composables/sitzungsstand.js'))
        .replace("import { shallowRef, watch } from 'vue'",
            'const shallowRef = globalThis.__shallowRef\nconst watch = globalThis.__watch')
    const ziel = await mkdtemp(join(tmpdir(), 'web8e-stand-'))
    const datei = join(ziel, 'sitzungsstand.mjs')
    await writeFile(datei, quelle)
    return import(pathToFileURL(datei).href)
}

/** Minimale Reaktivität: `shallowRef` meldet Änderungen, `watch` hört zu. */
function vueAttrappe() {
    const leser = new Set()
    globalThis.__watcher = leser
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
    globalThis.__watch = (quelle, rueckmeldung) => {
        const fn = () => rueckmeldung(quelle())
        leser.add(fn)
        return () => leser.delete(fn)
    }
}

// ── useApi.js mit ersetzten Vue-/App-Rändern ──────────────────────────────
function randErsetzen(quelle) {
    return quelle
        .replace("import { useImpersonation } from './useImpersonation.js'",
            "const useImpersonation = () => ({ isActive: { value: false } })")
        .replace("import { sitzungBeendet } from './useSitzungsablauf.js'",
            "const sitzungBeendet = (h) => { globalThis.__sitzungBeendet = h ?? '' }")
        .replace("import { sitzungsFehlerMerken } from './sitzungsstand.js'",
            "const sitzungsFehlerMerken = (f) => globalThis.__stand.sitzungsFehlerMerken(f)")
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

// ── Attrappen ─────────────────────────────────────────────────────────────
const CSRF_DATEN = { message: 'CSRF-Token ungueltig oder fehlend.', exc_type: 'CSRFTokenError' }
const CSRF = () => ({ ok: false, status: 417, text: async () => JSON.stringify(CSRF_DATEN) })
const ABGELAUFEN = () => ({
    ok: false,
    status: 401,
    text: async () => JSON.stringify({ message: 'Bitte melde dich an.', exc_type: 'SessionExpired' }),
})
const OK = (message = { gut: true }) => ({ ok: true, status: 200, text: async () => JSON.stringify({ message }) })

/**
 * Baut window/location/sessionStorage/fetch-Attrappen.
 *
 * `tokenAntwort`: `'ok'` (liefert `token`), `'anmeldung'` (Token-Endpunkt
 * antwortet 401 — so wie für eine Sitzung, die wirklich weg ist) oder
 * `'ohne-token'` (200, aber ohne `csrf_token`).
 */
function umgebung({ token = 'neu-2', tokenAntwort = 'ok', antworten = [OK], speicher = true } = {}) {
    const zustand = { reloads: 0, weiterleitungen: [], anfragen: [], logs: [] }
    const speicherMap = new Map()

    const sessionStorage = {
        getItem: (k) => (speicher ? (speicherMap.has(k) ? speicherMap.get(k) : null) : (() => { throw new Error('gesperrt') })()),
        setItem: (k, v) => { if (!speicher) throw new Error('gesperrt'); speicherMap.set(k, String(v)) },
        removeItem: (k) => { if (!speicher) throw new Error('gesperrt'); speicherMap.delete(k) },
    }
    const location = {
        pathname: '/diakronos', search: '', hash: '#/profile',
        reload: () => { zustand.reloads++ },
        assign: (ziel) => { zustand.weiterleitungen.push(ziel) },
    }
    const document = { querySelector: () => null }
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
        if (String(url).includes('session.sitzung_status')) {
            if (tokenAntwort === 'anmeldung') return ABGELAUFEN()
            const inhalt = tokenAntwort === 'ohne-token' ? {} : { user: 'anna', csrf_token: token }
            const koerper = { message: inhalt }
            return { ok: true, status: 200, json: async () => koerper, text: async () => JSON.stringify(koerper) }
        }
        const fabrik = antworten[Math.min(fachNr, antworten.length - 1)]
        fachNr++
        return typeof fabrik === 'function' ? fabrik() : fabrik
    }
    return { zustand, window }
}

// ══════════════════════════════════════════════════════════════════════════
// E1 — Hauptbereich: 417 ohne frisches Token -> DIALOG, keine Navigation
// ══════════════════════════════════════════════════════════════════════════

test('WEB-8e E1: 417 ohne frisches Token kennzeichnet „im Bereich, ohne Navigation"', async () => {
    const heilung = await heilungLaden()
    heilung.zustandZuruecksetzen()
    const { zustand } = umgebung({ tokenAntwort: 'anmeldung', antworten: [CSRF] })

    // ECHTER Weg: Erstversuch 417, Token-Abruf scheitert (Sitzung weg).
    const fehler = await heilung
        .heileOderMelde({ anfrage: () => globalThis.fetch('/api/method/x'), ohneNavigation: true })
        .then(() => null, (e) => e)

    assert.ok(fehler, 'der Aufrufer bekommt einen Fehler')
    assert.equal(fehler.sitzung, true, 'als Sitzungsende gekennzeichnet')
    assert.equal(fehler.imBereich, true, 'der Hauptbereich zeigt den Dialog selbst')
    assert.equal(fehler.neuLaden, undefined,
        'kein Neuladen-Merker — sonst hält useApi den Fehler für „navigiert schon"')
    assert.equal(fehler.weitergeleitet, undefined, 'und keine Weiterleitung')
    assert.equal(fehler.hinweis, heilung.SITZUNG_HINWEIS, 'fester Hinweis für den Dialog')
    assert.equal(zustand.reloads, 0, 'nichts wird neu geladen')
    assert.deepEqual(zustand.weiterleitungen, [], 'und nichts wird navigiert')
})

test('WEB-8e E1: derselbe Fehler kommt als Dialog an (Merken -> Beobachter -> Dialog)', async () => {
    vueAttrappe()
    globalThis.__heilung = await heilungLaden()
    globalThis.__heilung.zustandZuruecksetzen()
    const { zustand } = umgebung({ tokenAntwort: 'anmeldung', antworten: [CSRF] })
    // Der Stand wird NACH der Attrappe geladen (ein Seitenleben = ein Modul).
    globalThis.__stand = await standLaden()
    const api = await useApiLaden()

    // Der Dialog (`SitzungsHinweis.vue`) hört auf den Stand (M2-Watcher).
    let dialogMeldungen = 0
    globalThis.__stand.sitzungsFehlerBeobachten(() => { dialogMeldungen++ })
    globalThis.__sitzungBeendet = ''

    const fehler = await api.apiCall('profile.update_my_profile', { a: 1 }).then(() => null, (e) => e)

    assert.ok(fehler, 'apiCall endet mit einem Fehler')
    assert.equal(fehler.imBereich, true, 'useApi hat den Fehler in den Bereich übernommen')
    assert.equal(fehler.hinweis, 'Sitzung abgelaufen — bitte neu anmelden.')
    assert.equal(dialogMeldungen, 1, 'der Dialog wird benachrichtigt (shallowRef-Änderung)')
    assert.equal(globalThis.__stand.sitzungsFehlerLesen(), fehler, 'der Fehler liegt für den Dialog bereit')
    assert.equal(zustand.reloads, 0, 'die Seite lädt NICHT neu')
    assert.deepEqual(zustand.weiterleitungen, [], 'keine Weiterleitung weg von der SPA')
    // Beleg, dass der echte Ablauf lief: Versuch, Token-Versuch, sonst nichts.
    assert.equal(zustand.anfragen.length, 2, 'Versuch + Token-Abruf (keine sinnlose Wiederholung)')
})

test('WEB-8e E1: Fehler mit LAUFENDER Navigation bleiben ohne Dialog (N3 bleibt)', async () => {
    vueAttrappe()
    globalThis.__stand = await standLaden()
    const api = await useApiLaden()
    let gemeldet = 0
    globalThis.__stand.sitzungsFehlerBeobachten(() => { gemeldet++ })

    for (const marke of ['neuLaden', 'weitergeleitet']) {
        const fehler = new Error('läuft')
        fehler.sitzung = true
        fehler[marke] = true
        const ergebnis = await api.__mitSitzungsdialog(() => { throw fehler }).catch((e) => e)
        assert.equal(ergebnis, fehler, `${marke}: unverändert durchgereicht`)
        assert.equal(ergebnis.imBereich, undefined, `${marke}: kein Dialog vor dem Seitenwechsel`)
    }
    assert.equal(gemeldet, 0, 'es wird nichts für den Dialog abgelegt')
})

// ══════════════════════════════════════════════════════════════════════════
// E2 — Gastseiten: 401/419 melden sofort, nur CSRF lädt einmal neu
// ══════════════════════════════════════════════════════════════════════════

test('WEB-8e E2: Gastseite — Sitzung weg (401/419) lädt NICHT neu, meldet sofort', async () => {
    for (const status of [401, 419]) {
        const heilung = await heilungLaden()
        heilung.zustandZuruecksetzen()
        const { zustand } = umgebung({ antworten: [() => ({ ok: false, status, text: async () => JSON.stringify({ message: 'Bitte melde dich an.', exc_type: 'SessionExpired' }) })] })

        const fehler = await heilung
            .heileOderMelde({ anfrage: () => globalThis.fetch('/api/method/x'), gast: true })
            .then(() => null, (e) => e)

        assert.ok(fehler, `${status}: der Gast bekommt eine Meldung`)
        assert.equal(fehler.gast, true)
        assert.equal(fehler.neuLaden, undefined, `${status}: KEIN Neuladen (es gibt keine Sitzung zu erneuern)`)
        assert.equal(fehler.meldung, true, `${status}: die Seite zeigt ihren festen Text`)
        assert.equal(fehler.hinweis, heilung.GAST_HINWEIS)
        assert.equal(zustand.reloads, 0, `${status}: nichts wird neu geladen`)
        assert.deepEqual(zustand.weiterleitungen, [], `${status}: nie zur Anmeldung`)
    }
})

test('WEB-8e E2: Gastseite — nur die CSRF-Ablehnung führt ins einmalige Neuladen', async () => {
    const heilung = await heilungLaden()
    heilung.zustandZuruecksetzen()
    const { zustand } = umgebung({ antworten: [CSRF] })
    const fehler = await heilung
        .heileOderMelde({ anfrage: () => globalThis.fetch('/api/method/x'), gast: true })
        .then(() => null, (e) => e)

    assert.equal(zustand.reloads, 1, 'CSRF: genau EIN Neuladen (frisches Seiten-Token)')
    assert.equal(fehler.neuLaden, true)
    assert.equal(fehler.gast, true)
    assert.deepEqual(zustand.weiterleitungen, [])
})

// E2 — die Gastseiten prüfen die Merkmale in der richtigen Reihenfolge -------

test('WEB-8e E2: Gastseiten unterscheiden „melden" von „lädt neu" (Verhalten)', async () => {
    for (const datei of GASTSEITEN) {
        const quelle = await lies(datei)
        const start = quelle.indexOf('} catch (e)')
        const ende = quelle.indexOf('} finally')
        assert.ok(start > 0 && ende > start, `${datei}: Fangzweig gefunden`)
        const zweig = eval(`(e, fehler) => {${quelle.slice(start + '} catch (e) {'.length, ende)}}`)

        // a) Sitzung weg (E2): sofortige Meldung auf der Seite.
        for (const marke of ['meldung', 'gast']) {
            const zustand = { value: '' }
            const e = new Error('abgelaufen')
            e.sitzung = true
            e.gast = true
            e[marke] = true
            e.hinweis = 'Fester Gast-Hinweis'
            if (marke === 'meldung') zweig(e, zustand)
        }
        {
            const zustand = { value: '' }
            const e = new Error('abgelaufen')
            e.sitzung = true
            e.gast = true
            e.meldung = true
            e.hinweis = 'Fester Gast-Hinweis'
            zweig(e, zustand)
            assert.equal(zustand.value, 'Fester Gast-Hinweis', `${datei}: 401/419 wird gemeldet`)
        }
        // b) Neuladen läuft: keine Meldung, kein Text im Formular.
        {
            const zustand = { value: '' }
            const e = new Error('x')
            e.sitzung = true
            e.gast = true
            e.neuLaden = true
            e.hinweis = 'Die Seite wurde neu geladen, bitte Eingaben prüfen.'
            zweig(e, zustand)
            assert.equal(zustand.value, '', `${datei}: während des Neuladens keine Meldung`)
        }
        // c) Fachfehler: unverändert der Verbindungstext.
        {
            const zustand = { value: '' }
            zweig(new Error('kaputt'), zustand)
            assert.match(zustand.value, /Verbindungsfehler/, `${datei}: Fachfehler unverändert`)
        }
    }
})

// ══════════════════════════════════════════════════════════════════════════
// E3 — Hinweis nach dem einmaligen Gast-Neuladen
// ══════════════════════════════════════════════════════════════════════════

test('WEB-8e E3: nach dem Gast-Neuladen zeigt die Seite einen kurzen Hinweis', async () => {
    // Ein Testleben = EIN Browser-Speicher (sessionStorage lebt über das
    // Neuladen hinweg, aber nicht über einen neuen Tab).
    const speicherMap = new Map()
    const sessionStorage = {
        getItem: (k) => (speicherMap.has(k) ? speicherMap.get(k) : null),
        setItem: (k, v) => speicherMap.set(k, String(v)),
        removeItem: (k) => speicherMap.delete(k),
    }
    const { zustand } = umgebung({ antworten: [CSRF] })
    globalThis.sessionStorage = sessionStorage
    globalThis.window.sessionStorage = sessionStorage

    // 1. Seitenleben: die CSRF-Ablehnung lädt einmal neu (Marker entsteht) …
    const heilung = await heilungLaden()
    heilung.zustandZuruecksetzen()
    const fehler = await heilung
        .heileOderMelde({ anfrage: () => globalThis.fetch('/api/method/x'), gast: true })
        .then(() => null, (e) => e)
    assert.equal(zustand.reloads, 1, 'genau ein Neuladen')
    assert.equal(fehler.neuLaden, true, 'der Aufrufer erkennt „Seite lädt neu"')
    assert.equal(typeof heilung.NEULADEN_SCHLUESSEL, 'string', 'Marker für „gerade neu geladen"')

    // 2. Neues Seitenleben (dasselbe Gedächtnis, frisches Modul):
    //    `gastNachNeuladen()` meldet den Hinweis genau EINMAL.
    const zweite = await heilungLaden()
    assert.equal(zweite.gastNachNeuladen(), true, 'der Hinweis erscheint beim neuen Seitenleben')
    assert.match(zweite.HINWEIS_NACH_NEULADEN, /neu geladen/, 'Text nennt das Neuladen')
    assert.match(zweite.HINWEIS_NACH_NEULADEN, /Eingaben prüfen/, 'und bittet um Prüfung der Eingaben')
    assert.equal(zweite.gastNachNeuladen(), false, 'nur EINMAL (kein Dauerhinweis)')

    // 3. Der Hinweis ist kein Dauertext: nach dem Abholen ist der Merker weg,
    //    also erscheint er beim nächsten Seitenaufbau nicht noch einmal.
    const dritte = await heilungLaden()
    assert.equal(dritte.gastNachNeuladen(), false, 'kein zweiter Hinweis')
})

test('WEB-8e E3: Gastseiten zeigen den Neulade-Hinweis an (Quelle + Verhalten)', async () => {
    const heilung = await heilungLaden()
    const hinweis = heilung.HINWEIS_NACH_NEULADEN
    for (const datei of GASTSEITEN) {
        const quelle = await lies(datei)
        assert.match(quelle, /gastNachNeuladen/, `${datei}: fragt den Merker ab`)
        assert.match(quelle, /HINWEIS_NACH_NEULADEN/, `${datei}: nutzt den festen Text`)
        assert.match(quelle, /role="note"/, `${datei}: Hinweis ist als Notiz ausgezeichnet`)
    }
})

// ══════════════════════════════════════════════════════════════════════════
// E4 — neutraler Text statt „Die Anmeldung wird neu geladen …"
// ══════════════════════════════════════════════════════════════════════════

test('WEB-8e E4: Gastseiten nennen keine „Anmeldung", die neu geladen wird', async () => {
    // Nur der CODE zaehlt (Kommentare nennen den alten Text als Begruendung).
    const quelle = NACHBARN['shared/csrf-heilung.js']
        .split('\n').filter(z => !z.trim().startsWith('*') && !z.trim().startsWith('//')).join('\n')
    assert.equal(/gastFehler[\s\S]{0,400}Die Anmeldung wird neu geladen/.test(quelle), false,
        'die Heilung erzeugt den Anmelde-Text nicht mehr an der Gast-Stelle')
    assert.match(quelle, /GAST_NEULADEN_HINWEIS = 'Die Seite wird neu geladen/, 'neutraler Text für Gäste')
    for (const datei of GASTSEITEN) {
        const text = (await lies(datei)).split('\n').filter(z => !z.trim().startsWith('//')).join('\n')
        assert.equal(/Die Anmeldung wird neu geladen/.test(text), false,
            `${datei}: kein Anmelde-Text auf einer Seite ohne Konto`)
        assert.equal(/neu anmelden/i.test(text), false,
            `${datei}: Gäste haben kein Konto — auch kein „neu anmelden"`)
    }
})
