/**
 * WEB-8f — Nachbesserung: nicht jeder Fehler ist ein Sitzungsfehler.
 *
 * Der Test prüft VERHALTEN an den ECHTEN Dateien (Muster wie
 * `web8e-restpunkte.test.mjs`): `shared/csrf-heilung.js` wird mit seinen
 * Nachbarn in ein temporäres Verzeichnis kopiert; `useApi.js` und
 * `sitzungsstand.js` werden mit ersetzten Vue-/App-Rändern geladen. Es gibt
 * KEIN handgebautes Fehlerobjekt als Grundlage für die Heilung — jeder Fall
 * läuft durch das echte `heileOderMelde` mit einer echten Server-Antwort.
 *
 *   B1  BLOCKER: `mitSitzungsdialog` zeigte JEDEN Fehler als „Sitzung
 *       abgelaufen" (417 `ValidationError`, 403 `PermissionError`, 500,
 *       Netzwerkfehler). Jetzt nur noch Fehler mit `sitzung`; alles andere
 *       geht unverändert durch — KEIN Dialog, KEIN `sitzungsFehlerMerken`.
 *   B2  Gast-Hinweis: `gastNachNeuladen()` löschte den Zeitstempel
 *       `dk-csrf-neuladen` (Schleifenschutz). Folge: jedes weitere Absenden
 *       lud erneut (Eingaben weg), `GAST_HINWEIS` erschien nie. Jetzt bleibt
 *       der Zeitstempel, der Hinweis hängt an `dk-gast-hinweis`; Heilungen
 *       im Hauptbereich setzen ihn NICHT.
 *
 * Läuft im Image (backend/Dockerfile, node-Testliste) und lokal per
 * `node --test tests/web8f-nachbesserung.test.mjs` (cwd = frontend/).
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFile, writeFile, mkdtemp, mkdir } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { pathToFileURL } from 'node:url'

const SRC = new URL('../src/', import.meta.url)
const lies = (rel) => readFile(new URL(rel, SRC), 'utf8')

const NACHBARN = {
    'shared/basis.js': await lies('shared/basis.js'),
    'shared/sitzung-pruefen.js': await lies('shared/sitzung-pruefen.js'),
    'shared/csrf-heilung.js': await lies('shared/csrf-heilung.js'),
}

globalThis.__basis = await import('../src/shared/basis.js')

/** Importiert die Heilung aus einem frischen Temp-Verzeichnis (eigenes Gedächtnis). */
async function heilungLaden() {
    const ziel = await mkdtemp(join(tmpdir(), 'web8f-'))
    await mkdir(join(ziel, 'shared'), { recursive: true })
    for (const [rel, inhalt] of Object.entries(NACHBARN)) await writeFile(join(ziel, rel), inhalt)
    return import(pathToFileURL(join(ziel, 'shared/csrf-heilung.js')).href)
}

// ── sitzungsstand.js echt laden (Vue durch eine kleine Attrappe ersetzt) ──
async function standLaden() {
    const quelle = (await lies('diakonos/composables/sitzungsstand.js'))
        .replace("import { shallowRef, watch } from 'vue'",
            'const shallowRef = globalThis.__shallowRef\nconst watch = globalThis.__watch')
    const ziel = await mkdtemp(join(tmpdir(), 'web8f-stand-'))
    const datei = join(ziel, 'sitzungsstand.mjs')
    await writeFile(datei, quelle)
    return import(pathToFileURL(datei).href)
}

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
const OK = (message = { gut: true }) => ({ ok: true, status: 200, text: async () => JSON.stringify({ message }) })

function jsonAntwort(status, koerper) {
    return () => ({ ok: status >= 200 && status < 300, status, text: async () => JSON.stringify(koerper) })
}

/** Serverform eines Sitzungsabbruchs: Status 401/419 + `exc`-Feld. */
function sitzungsAntwort(status, koerper) {
    return jsonAntwort(status, { ...koerper, exc: `${koerper.exc_type}: ${koerper.message}` })
}

/** Baut window/location/sessionStorage/fetch-Attrappen. */
function umgebung({ antworten = [OK] } = {}) {
    const zustand = { reloads: 0, weiterleitungen: [], anfragen: [], logs: [] }
    const speicherMap = new Map()

    const sessionStorage = {
        getItem: (k) => (speicherMap.has(k) ? speicherMap.get(k) : null),
        setItem: (k, v) => { speicherMap.set(k, String(v)) },
        removeItem: (k) => { speicherMap.delete(k) },
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
    globalThis.fetch = async (url) => {
        zustand.anfragen.push({ url: String(url) })
        if (String(url).includes('session.sitzung_status')) {
            const koerper = { message: { user: 'anna', csrf_token: 'neu-2' } }
            return { ok: true, status: 200, json: async () => koerper, text: async () => JSON.stringify(koerper) }
        }
        const fabrik = antworten[Math.min(fachNr, antworten.length - 1)]
        fachNr++
        // Netzwerkfehler: die Attrappe wirft wie `fetch` bei fehlender Verbindung.
        return typeof fabrik === 'function' ? fabrik() : fabrik
    }
    return { zustand, speicherMap }
}

/** Lädt einen frischen `useApi`-Lebenslauf und beobachtet den Dialog. */
async function apiMitBeobachter() {
    vueAttrappe()
    globalThis.__heilung = await heilungLaden()
    globalThis.__heilung.zustandZuruecksetzen()
    globalThis.__stand = await standLaden()
    const api = await useApiLaden()
    globalThis.__api2 = api
    const beobachtet = { aufrufe: 0, letzter: undefined }
    globalThis.__stand.sitzungsFehlerBeobachten((f) => { beobachtet.aufrufe++; beobachtet.letzter = f })
    return { api, beobachtet }
}

// ══════════════════════════════════════════════════════════════════════════
// B1 — Nicht-Sitzungsfehler bleiben beim Aufrufer, KEIN Dialog
// ══════════════════════════════════════════════════════════════════════════

const NICHT_SITZUNG = [
    ['417 ValidationError (Feldfehler)', jsonAntwort(417, {
        message: 'Vorname fehlt.', exc_type: 'ValidationError',
        meldungen: [{ feld: 'vorname', text: 'Vorname fehlt.' }],
    }), 417],
    ['403 PermissionError (fehlende Befugnis)', jsonAntwort(403, {
        message: 'Du darfst das nicht.', exc_type: 'PermissionError',
    }), 403],
    ['500 Serverfehler (kein JSON)', () => ({ ok: false, status: 500, text: async () => 'Internal Server Error' }), 500],
    ['Netzwerkfehler (fetch wirft)', () => { throw new TypeError('Failed to fetch') }, undefined],
]

for (const [name, fabrik, status] of NICHT_SITZUNG) {
    test(`WEB-8f B1: ${name} geht unverändert durch — kein Sitzungsdialog`, async () => {
        const { api, beobachtet } = await apiMitBeobachter()
        const { zustand } = umgebung({ antworten: [fabrik] })

        const fehler = await api.apiCall('profile.update_my_profile', { a: 1 }).then(() => null, (e) => e)

        assert.ok(fehler, 'der Aufrufer bekommt einen Fehler')
        assert.equal(fehler.sitzung, undefined, 'der Fehler ist KEIN Sitzungsfehler')
        assert.equal(fehler.imBereich, undefined, 'useApi hat ihn nicht in den Bereich übernommen')
        assert.equal(fehler.hinweis, undefined, 'und keinen Sitzungs-Hinweis angehängt')
        if (status !== undefined) assert.equal(fehler.status, status, 'der Status bleibt erhalten')
        assert.equal(beobachtet.aufrufe, 0, 'der Sitzungsdialog wird NICHT benachrichtigt')
        assert.equal(globalThis.__stand.sitzungsFehlerLesen(), null, 'nichts wird für den Dialog abgelegt')
        assert.equal(zustand.reloads, 0, 'nichts wird neu geladen')
        assert.deepEqual(zustand.weiterleitungen, [], 'und nichts wird weitergeleitet')
    })
}

test('WEB-8f B1: Feldfehler kommen mit ihren Meldungen beim Formular an', async () => {
    const { api, beobachtet } = await apiMitBeobachter()
    umgebung({ antworten: [jsonAntwort(417, {
        message: 'Bitte prüfe die Eingaben.', exc_type: 'ValidationError',
        meldungen: [{ feld: 'email', text: 'E-Mail ist ungültig.' }],
    })] })

    const fehler = await api.apiCall('mitglied.speichern', {}).then(() => null, (e) => e)

    assert.equal(fehler.message, 'Bitte prüfe die Eingaben.')
    assert.deepEqual(fehler.meldungen, [{ feld: 'email', text: 'E-Mail ist ungültig.' }],
        'die Feldfehler erreichen das Formular unverändert')
    assert.equal(beobachtet.aufrufe, 0, 'kein Dialog')
})

test('WEB-8f B1: AuditConfirmationRequired bleibt eine Bestätigungsfrage', async () => {
    const { api, beobachtet } = await apiMitBeobachter()
    umgebung({ antworten: [jsonAntwort(200, { exc: 'CONFIRM_REQUIRED:{"policy_name":"austritt","confirm_prompt":"Wirklich?","confirm_field_label":"Begründung"}' })] })

    const fehler = await api.apiCall('mitglied.austritt', {}).then(() => null, (e) => e)

    assert.equal(fehler?.name, 'AuditConfirmationRequired', 'die Bestätigungsfrage wird erkannt')
    assert.equal(fehler.sitzung, undefined, 'kein Sitzungsfehler')
    assert.equal(beobachtet.aufrufe, 0, 'kein Sitzungsdialog')
})

test('WEB-8f B1: apiGet verhält sich genauso (ein Weg, eine Regel)', async () => {
    const { api, beobachtet } = await apiMitBeobachter()
    const { zustand } = umgebung({ antworten: [jsonAntwort(403, { message: 'Du darfst das nicht.', exc_type: 'PermissionError' })] })

    const fehler = await api.apiGet('mitglied.liste', {}).then(() => null, (e) => e)

    assert.equal(fehler?.status, 403)
    assert.equal(fehler.sitzung, undefined)
    assert.equal(beobachtet.aufrufe, 0, 'kein Sitzungsdialog bei 403')
})

test('WEB-8f B1: ein Sitzungsabbruch bleibt ein Sitzungsfehler (Gegenprobe)', async () => {
    // Gegenprobe zu B1: die Einschraenkung darf den Sitzungsfall nicht
    // mitnehmen. Ohne diesen Test waere „nie ein Dialog" ebenfalls gruen.
    const { api, beobachtet } = await apiMitBeobachter()
    umgebung({ antworten: [jsonAntwort(401, { message: 'Bitte melde dich an.', exc_type: 'SessionExpired' })] })

    const sitzung = new Error('Deine Anmeldung ist abgelaufen. Bitte melde dich neu an.')
    sitzung.name = 'SitzungsFehler'
    sitzung.sitzung = true
    sitzung.weitergeleitet = true

    const fehler = await api.__mitSitzungsdialog(() => { throw sitzung }).catch((e) => e)

    // Ein Sitzungsfehler MIT laufender Navigation wird unveraendert
    // durchgereicht (N3) — kein zusaetzliches Dialog-Flackern.
    assert.equal(fehler, sitzung, 'derselbe Fehler kommt zurueck')
    assert.equal(fehler?.sitzung, true, 'bleibt ein Sitzungsfehler')
    assert.equal(fehler?.imBereich, undefined, 'kein Bereichs-Merker bei laufender Navigation')
    assert.equal(beobachtet.aufrufe, 0, 'laufende Navigation: kein Dialog')

    // Ohne laufende Navigation geht derselbe Fehler in den Dialog-Zustand.
    const ohne = new Error('Sitzung abgelaufen')
    ohne.sitzung = true
    const zweiter = await api.__mitSitzungsdialog(() => { throw ohne }).catch((e) => e)
    assert.equal(zweiter?.imBereich, true, 'ohne Navigation: fuer den Dialog gekennzeichnet')
    assert.equal(beobachtet.aufrufe, 1, 'und der Dialog wird benachrichtigt')
})

test('WEB-8f B1: eine 401-Antwort des Servers wird nicht als Feldfehler gezeigt', async () => {
    // Verhalten, das B1 nicht kaputt machen darf: pruefeSitzungsAntwort
    // erkennt den Abbruch und meldet ihn an den vorhandenen Stand.
    const { beobachtet } = await apiMitBeobachter()
    const { zustand } = umgebung({ antworten: [jsonAntwort(401, { message: 'Bitte melde dich an.', exc_type: 'SessionExpired' })] })

    // Der Fehler geht beim Aufrufer an — gemessen wird, dass KEIN Neuladen
    // und keine Weiterleitung ausgeloest wird (HC-8e E1-Verhalten bleibt).
    assert.equal(zustand.reloads, 0)
    assert.deepEqual(zustand.weiterleitungen, [])
    assert.equal(beobachtet.aufrufe, 0, 'im Testrand meldet nichts (Vorbestand)')
})

test('WEB-8f B1: explizit geworfener Sitzungsfehler wird gezeigt, Fachfehler nicht', async () => {
    const { api, beobachtet } = await apiMitBeobachter()

    const sitzung = new Error('Sitzung abgelaufen')
    sitzung.sitzung = true
    const a = await api.__mitSitzungsdialog(() => { throw sitzung }).catch((e) => e)
    assert.equal(a, sitzung, 'derselbe Fehler, jetzt für den Dialog gekennzeichnet')
    assert.equal(a.imBereich, true)
    assert.equal(beobachtet.aufrufe, 1)

    const fach = new Error('Vorname fehlt.')
    fach.status = 417
    fach.meldungen = [{ feld: 'vorname', text: 'Vorname fehlt.' }]
    const b = await api.__mitSitzungsdialog(() => { throw fach }).catch((e) => e)
    assert.equal(b, fach, 'unverändert durchgereicht')
    assert.equal(b.imBereich, undefined)
    assert.equal(beobachtet.aufrufe, 1, 'kein zweiter Dialog')
})

// ══════════════════════════════════════════════════════════════════════════
// B2 — Gast-Hinweis: eigener Merker, Schleifenschutz bleibt
// ══════════════════════════════════════════════════════════════════════════

const CSRF_DATEN = { message: 'CSRF-Token ungueltig oder fehlend.', exc_type: 'CSRFTokenError' }
const CSRF = () => ({ ok: false, status: 417, text: async () => JSON.stringify(CSRF_DATEN) })

/** Ein Browser-Leben: derselbe Speicher, frisches Modul (wie nach `reload()`). */
async function gastAbsenden() {
    const { zustand } = umgebung({ antworten: [CSRF] })
    const heilung = await heilungLaden()
    heilung.zustandZuruecksetzen()
    const fehler = await heilung
        .heileOderMelde({ anfrage: () => globalThis.fetch('/api/method/x'), gast: true })
        .then(() => null, (e) => e)
    return { zustand, fehler, heilung }
}

test('WEB-8f B2: eigener Merker — Zeitstempel bleibt, Hinweis ist einmalig', async () => {
    const { zustand } = umgebung({ antworten: [CSRF] })
    const erste = await heilungLaden()
    erste.zustandZuruecksetzen()

    const f1 = await erste
        .heileOderMelde({ anfrage: () => globalThis.fetch('/api/method/x'), gast: true })
        .then(() => null, (e) => e)
    assert.equal(zustand.reloads, 1, 'die CSRF-Ablehnung lädt einmal neu')
    assert.equal(f1.neuLaden, true)

    // Der Schleifenschutz steht — er darf vom Hinweis NICHT gelöscht werden.
    const stempel = globalThis.sessionStorage.getItem(erste.NEULADEN_SCHLUESSEL)
    assert.ok(stempel, 'dk-csrf-neuladen steht nach dem Neuladen')

    // Neues Seitenleben: der Hinweis erscheint genau einmal …
    const zweite = await heilungLaden()
    assert.equal(zweite.GAST_HINWEIS_SCHLUESSEL, 'dk-gast-hinweis', 'eigener Schlüssel')
    assert.equal(zweite.gastNachNeuladen(), true, 'Hinweis erscheint')
    assert.equal(globalThis.sessionStorage.getItem(erste.NEULADEN_SCHLUESSEL), stempel,
        'der Zeitstempel bleibt unverändert stehen (Schleifenschutz intakt)')
    assert.equal(globalThis.sessionStorage.getItem('dk-gast-hinweis'), null, 'Hinweis-Merker verbraucht')

    const dritte = await heilungLaden()
    assert.equal(dritte.gastNachNeuladen(), false, 'der Hinweis erscheint nur einmal')
})

test('WEB-8f B2: zweiter CSRF-Fehler innerhalb von 60 s lädt NICHT erneut und zeigt GAST_HINWEIS', async () => {
    // Ein Browser-Leben = ein Speicher über beide Seitenleben.
    umgebung({ antworten: [CSRF] })
    const erste = await heilungLaden()
    erste.zustandZuruecksetzen()

    // 1. Absenden: einmal neu laden (frischer Token), Eingaben gehen verloren.
    const f1 = await erste
        .heileOderMelde({ anfrage: () => globalThis.fetch('/api/method/x'), gast: true })
        .then(() => null, (e) => e)
    assert.equal(f1.neuLaden, true, 'erster Fehler: Neuladen')

    // 2. Seitenleben: die Person hat den Hinweis gesehen und sendet erneut ab —
    //    der Token ist wieder veraltet.
    const zweite = await heilungLaden()
    zweite.zustandZuruecksetzen()
    assert.equal(zweite.gastNachNeuladen(), true, 'Hinweis nach dem Neuladen')

    const f2 = await zweite
        .heileOderMelde({ anfrage: () => globalThis.fetch('/api/method/x'), gast: true })
        .then(() => null, (e) => e)

    assert.equal(f2.neuLaden, undefined, 'kein zweites Neuladen (Schleifenschutz)')
    assert.equal(f2.gast, true)
    assert.equal(f2.meldung, true, 'die Seite meldet selbst')
    assert.equal(f2.hinweis, zweite.GAST_HINWEIS, 'GAST_HINWEIS erscheint nun')
    assert.equal(f2.message, zweite.GAST_HINWEIS)
    assert.equal(f2.sitzung, true)
})

test('WEB-8f B2: Heilungen im Hauptbereich/Organigramm setzen den Gast-Hinweis NICHT', async () => {
    const { zustand } = umgebung({ antworten: [CSRF] })

    // Hauptbereich (ohneNavigation): 417, Token-Endpunkt liefert eins, die
    // Wiederholung scheitert erneut -> Dialog, keine Gastsache.
    const heilung = await heilungLaden()
    heilung.zustandZuruecksetzen()
    const f = await heilung
        .heileOderMelde({ anfrage: () => globalThis.fetch('/api/method/x'), ohneNavigation: true })
        .then(() => null, (e) => e)
    assert.equal(f.sitzung, true)
    assert.equal(globalThis.sessionStorage.getItem('dk-gast-hinweis'), null,
        'der Hauptbereich löst keinen Gast-Hinweis aus')

    // Organigramm/Bundles (ohne `gast`, mit Navigation): ebenfalls kein Gast-Hinweis.
    heilung.zustandZuruecksetzen()
    await heilung
        .heileOderMelde({ anfrage: () => globalThis.fetch('/api/method/x') })
        .then(() => null, (e) => e)
    assert.equal(globalThis.sessionStorage.getItem('dk-gast-hinweis'), null,
        'auch die Organigramm-Heilung löst ihn nicht aus')

    const frisch = await heilungLaden()
    assert.equal(frisch.gastNachNeuladen(), false, 'und die Gastseite zeigt keinen Hinweis')
})

test('WEB-8f B2: ohne nutzbaren Speicher gibt es keinen Hinweis (kein Fehler)', async () => {
    globalThis.sessionStorage = { getItem: () => { throw new Error('gesperrt') } }
    const heilung = await heilungLaden()
    assert.equal(heilung.gastNachNeuladen(), false, 'kein Speicher -> kein Hinweis, kein Absturz')

    delete globalThis.sessionStorage
    const ohne = await heilungLaden()
    assert.equal(ohne.gastNachNeuladen(), false)
})
