/**
 * WEB-8b — CSRF-Fehler im Client automatisch heilen.
 *
 * ZIEL (Manuel): „Wenn die Meldung 'CSRF-Token ungültig' kommt, soll ein
 * Force-Refresh beim Client kommen, damit es automatisiert geschieht."
 *
 * Vorgabe (Orchestrator, C1–C4):
 *   C1  Bei 417 + `exc_type=CSRFTokenError`:
 *         a) EINMAL still ein frisches CSRF-Token holen (vorhandener Weg:
 *            `diakronos.diakonos.api.session.sitzung_status` liefert
 *            `{user, csrf_token}`, siehe `useSitzungsablauf.js`) und die
 *            ursprüngliche Anfrage genau EINMAL wiederholen.
 *         b) Scheitert das erneut mit CSRFTokenError -> `window.location.reload()`.
 *   C2  Schleifenschutz: höchstens 1 automatisches Neuladen pro 60 s
 *       (Zeitstempel in `sessionStorage`, Zugriff in try/catch). Tritt der
 *       Fehler im Fenster erneut auf: KEIN Neuladen, sondern Weiterleitung zur
 *       Anmeldung (`anmeldeUrl()`) mit Hinweis
 *       „Sitzung abgelaufen — bitte neu anmelden."
 *   C3  401/419 (SessionExpired) bleibt wie heute -> Anmeldung. Keine Heilung.
 *   C4  Kein Token in Logs/Konsole.
 *
 * Der Test prüft VERHALTEN (Attrappen für fetch/location/sessionStorage), keine
 * Textmuster — die Quelle wird wie in `p21-sitzung.test.mjs` über ein
 * `data:`-Modul geladen, weil `useApi.js` Vue- und App-Abhängigkeiten zieht.
 *
 * Läuft im Image (backend/Dockerfile, node-Testliste) und lokal per
 * `node --test tests/web8b-csrf-heilung.test.mjs` (cwd = frontend/).
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFile, writeFile, mkdtemp } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { pathToFileURL } from 'node:url'

// ── Laden der echten Quelle ───────────────────────────────────────────────
//
// `shared/csrf-heilung.js` liegt neben `shared/basis.js`. Ein `data:`-Modul
// kann relative Importe nicht auflösen (ERR_INVALID_URL). Deshalb wird die
// Quelle UNVERÄNDERT in ein temporäres Verzeichnis geschrieben; der Import
// `./basis.js` zeigt dort auf die ebenfalls unveränderte echte Datei. Kein
// Nachbau, keine Kopie der Logik — geprüft wird der Produktivcode.
const quellVerzeichnis = new URL('../src/shared/', import.meta.url)
const quelle = await readFile(new URL('csrf-heilung.js', quellVerzeichnis), 'utf8')
// Die echten Nachbardateien (unverändert), damit `./basis.js` und
// `./sitzung-pruefen.js` im Temp-Verzeichnis genauso auflösen wie im Bundle.
const NACHBARN = ['basis.js', 'sitzung-pruefen.js']
const nachbarQuellen = Object.fromEntries(
    await Promise.all(NACHBARN.map(async (n) => [n, await readFile(new URL(n, quellVerzeichnis), 'utf8')])),
)

const laden = async (zusatz = {}) => {
    const ziel = await mkdtemp(join(tmpdir(), 'web8b-'))
    for (const [name, inhalt] of Object.entries(nachbarQuellen)) await writeFile(join(ziel, name), inhalt)
    await writeFile(join(ziel, 'csrf-heilung.js'), quelle)
    for (const [name, inhalt] of Object.entries(zusatz)) await writeFile(join(ziel, name), inhalt)
    return import(pathToFileURL(join(ziel, 'csrf-heilung.js')).href)
}

const CSRF = { ok: false, status: 417, text: async () => JSON.stringify({ message: 'CSRF-Token ungueltig oder fehlend.', exc_type: 'CSRFTokenError' }) }
const OK = (message = { gut: true }) => ({ ok: true, status: 200, text: async () => JSON.stringify({ message }) })

/** Baut eine frische Umgebung (window, location, sessionStorage, fetch). */
function umgebung({ speicherFrei = true, tokenAntwort = { user: 'anna', csrf_token: 'neu-2' } } = {}) {
    const protokoll = []
    const zustand = { reloads: 0, weiterleitungen: [], logs: [], anfragen: [], tokens: [] }
    const speicher = new Map()

    const sessionStorage = {
        getItem: (k) => (speicherFrei ? (speicher.has(k) ? speicher.get(k) : null) : (() => { throw new Error('gesperrt') })()),
        setItem: (k, v) => { if (!speicherFrei) throw new Error('gesperrt'); speicher.set(k, String(v)) },
        removeItem: (k) => { if (!speicherFrei) throw new Error('gesperrt'); speicher.delete(k) },
    }

    const location = {
        pathname: '/diakronos',
        search: '',
        hash: '#/personen',
        reload: () => { zustand.reloads++ },
        assign: (ziel) => { zustand.weiterleitungen.push(ziel) },
    }

    const window = {
        __DIakonosBOOT: { basePath: '/diakronos', csrf_token: 'alt-1' },
        location,
        sessionStorage,
        document: {
            querySelector: (sel) => (sel.includes('csrf-token')
                ? { getAttribute: () => window.__DIakonosBOOT.csrf_token, setAttribute: (_n, v) => { window.__DIakonosBOOT.csrf_token = v } }
                : null),
        },
    }

    globalThis.window = window
    globalThis.location = location
    globalThis.sessionStorage = sessionStorage
    globalThis.document = window.document

    globalThis.fetch = async (url, optionen = {}) => {
        protokoll.push(String(url))
        zustand.anfragen.push({ url: String(url), optionen })
        zustand.tokens.push(optionen?.headers?.['X-Frappe-CSRF-Token'] ?? null)
        if (String(url).includes('session.sitzung_status')) {
            const koerper = { message: tokenAntwort }
            return { ok: true, status: 200, json: async () => koerper, text: async () => JSON.stringify(koerper) }
        }
        return typeof tokenAntwort === 'function' ? tokenAntwort() : OK()
    }

    // C4: nichts darf in Konsole/Log landen.
    for (const name of ['log', 'warn', 'error', 'info', 'debug']) {
        globalThis.console[name] = (...teile) => { zustand.logs.push(teile.join(' ')) }
    }

    return { protokoll, zustand, window }
}

/** Setzt den 60-s-Zeitstempel der letzten Heilung (C2). */
const ZEITSTEMPEL = 'dk-csrf-neuladen'

/** Frisches Modul je Test (Modulgedächtnis darf nicht überlaufen). */
const frisch = () => laden()

test('WEB-8b C1a: frisches Token holen, dann die Anfrage GENAU EINMAL wiederholen', async () => {
    const modul = await frisch()
    const { zustand, window } = umgebung()
    let anfragen = 0
    let fache = 0
    const originale = globalThis.fetch
    const override = globalThis.fetch = async (url, opt = {}) => {
        anfragen++
        zustand.anfragen.push({ url: String(url), optionen: opt })
        zustand.tokens.push(opt?.headers?.['X-Frappe-CSRF-Token'] ?? null)
        if (String(url).includes('session.sitzung_status')) {
            // Der Token-Endpunkt liefert IMMER ein frisches Token — hier darf
            // die Attrappe nicht über `fetch`-Aufrufe hinweg zählen.
            const koerper = { message: { user: 'anna', csrf_token: 'neu-2' } }
            return { ok: true, status: 200, json: async () => koerper, text: async () => JSON.stringify(koerper) }
        }
        // Erste Fach-Anfrage abgelehnt, Wiederholung erfolgreich.
        const wert = ++fache
        return wert === 1 ? CSRF : OK()
    }

    // Wie die echten Aufrufer: der Token wird bei JEDEM Versuch frisch gelesen.
    const tun = modul.heileOderMelde({
        anfrage: () => globalThis.fetch('/api/method/x', {
            headers: { 'X-Frappe-CSRF-Token': window.__DIakonosBOOT.csrf_token },
        }),
    })

    const ergebnis = await tun

    assert.equal(anfragen, 3, 'Original + Token-Abruf + genau eine Wiederholung (kein vierter Aufruf)')
    assert.equal(ergebnis.data?.message?.gut, true, 'die gemeldeten Daten kommen aus der Antwort')
    assert.equal(ergebnis.res.ok, true)
    assert.equal(zustand.anfragen[1].url.includes('session.sitzung_status'), true, 'der vorhandene Token-Weg wird benutzt')
    assert.equal(zustand.tokens[0], 'alt-1', 'der erste Versuch trägt den alten Token')
    assert.equal(zustand.tokens[2], 'neu-2', 'die Wiederholung trägt das frische Token')
    assert.equal(window.__DIakonosBOOT.csrf_token, 'neu-2', 'Boot-Objekt kennt den neuen Token')
    assert.deepEqual(zustand.anfragen.map(a => a.url), [
        '/api/method/x',
        '/diakronos/api/method/diakronos.diakonos.api.session.sitzung_status',
        '/api/method/x',
    ], 'Reihenfolge: Original, Token, Wiederholung — genau drei Anfragen')
    assert.equal(zustand.reloads, 0, 'bei Erfolg wird nicht neu geladen')
    assert.deepEqual(zustand.weiterleitungen, [])
})

test('WEB-8b C1b: zweites 417 -> genau EIN window.location.reload()', async () => {
    const modul = await frisch()
    const { zustand } = umgebung()
    const originale = globalThis.fetch
    globalThis.fetch = async (url, opt) => (String(url).includes('session.sitzung_status')
        ? originale(url, opt)
        : CSRF)

    await modul.heileOderMelde({ anfrage: () => globalThis.fetch('/api/method/x', {}) }).catch(() => {})

    assert.equal(zustand.reloads, 1, 'genau ein Neuladen')
    assert.deepEqual(zustand.weiterleitungen, [], 'noch keine Anmelde-Weiterleitung')
})

test('WEB-8b C2: im 60-s-Fenster kein zweites Neuladen, sondern Anmeldung mit Hinweis', async () => {
    const modul = await frisch()
    const { zustand, window } = umgebung()
    window.sessionStorage.setItem(ZEITSTEMPEL, String(Date.now() - 5_000))
    const originale = globalThis.fetch
    globalThis.fetch = async (url, opt) => (String(url).includes('session.sitzung_status')
        ? originale(url, opt)
        : CSRF)

    const fehler = await modul.heileOderMelde({ anfrage: () => globalThis.fetch('/api/method/x', {}) }).then(
        () => null,
        (e) => e,
    )

    assert.equal(zustand.reloads, 0, 'kein zweites Neuladen im Fenster (keine Schleife)')
    assert.equal(zustand.weiterleitungen.length, 1, 'stattdessen die Anmeldemaske')
    assert.match(zustand.weiterleitungen[0], /^\/diakronos\/login\?redirect-to=/, 'präfixbewusst über anmeldeUrl()')
    assert.match(decodeURIComponent(zustand.weiterleitungen[0]), /diakronos#\/personen/, 'Rücksprungziel bleibt erhalten')
    assert.ok(fehler, 'der Aufrufer bekommt einen Fehler (kein stilles Weiterlaufen)')
    assert.ok(zustand.logs.every((z) => !z.includes('neu-2') && !z.includes('alt-1')), 'C4: kein Token in der Konsole')
})

test('WEB-8b C2: nach Ablauf der 60 s ist wieder ein Neuladen erlaubt', async () => {
    const modul = await frisch()
    const { zustand, window } = umgebung()
    window.sessionStorage.setItem(ZEITSTEMPEL, String(Date.now() - 61_000))
    const originale = globalThis.fetch
    globalThis.fetch = async (url, opt) => (String(url).includes('session.sitzung_status')
        ? originale(url, opt)
        : CSRF)

    await modul.heileOderMelde({ anfrage: () => globalThis.fetch('/api/method/x', {}) }).catch(() => {})

    assert.equal(zustand.reloads, 1, 'ausserhalb des Fensters wird wieder geladen')
    assert.deepEqual(zustand.weiterleitungen, [])
})

// WEB-8c (R7) hat diese Vorgabe GEAENDERT: ohne nutzbaren sessionStorage gibt
// es GAR KEIN Neuladen mehr (der Merker ginge ueber das Neuladen verloren ->
// Endlosschleife ueber Seitenleben hinweg); es geht direkt zur Anmeldung.
// Der Nachweis steht in `tests/web8c-csrf-nachbesserung.test.mjs`.
test('WEB-8b C2 (WEB-8c R7): sessionStorage gesperrt -> kein Absturz, kein Neuladen, Anmeldung', async () => {
    const modul = await frisch()
    const { zustand } = umgebung({ speicherFrei: false })
    const originale = globalThis.fetch
    globalThis.fetch = async (url, opt) => (String(url).includes('session.sitzung_status')
        ? originale(url, opt)
        : CSRF)

    const lauf = () => modul.heileOderMelde({ anfrage: () => globalThis.fetch('/api/method/x', {}) }).catch(() => {})
    await lauf()
    await lauf()
    await lauf()

    assert.equal(zustand.reloads, 0, 'WEB-8c R7: ohne Merker KEIN Neuladen (sonst Schleife ueber Seitenleben)')
    assert.equal(zustand.weiterleitungen.length, 1, 'stattdessen genau EINE Weiterleitung zur Anmeldung')
})

test('WEB-8b: Token-Abruf selbst scheitert (kein Token) -> Neuladen, kein Endlosversuch', async () => {
    const modul = await frisch()
    const { zustand, window } = umgebung({ tokenAntwort: { user: 'anna', csrf_token: '' } })
    const originale = globalThis.fetch
    let wiederholungen = 0
    globalThis.fetch = async (url, opt) => {
        if (String(url).includes('session.sitzung_status')) return originale(url, opt)
        wiederholungen++
        return CSRF
    }

    await modul.heileOderMelde({ anfrage: () => globalThis.fetch('/api/method/x', {}) }).catch(() => {})

    assert.equal(wiederholungen, 1, 'ohne frisches Token keine sinnlose Wiederholung')
    assert.equal(zustand.reloads, 1, 'stattdessen Force-Refresh')
    assert.equal(window.__DIakonosBOOT.csrf_token, 'alt-1', 'ohne Token bleibt der alte Wert stehen (nichts erfunden)')
})

test('WEB-8b C3: SessionExpired (401/419) bleibt unverändert -> Anmeldung, keine Heilung', async () => {
    for (const status of [401, 419]) {
        const modul = await frisch()
        const { zustand } = umgebung()
        let anfragen = 0
        globalThis.fetch = async () => {
            anfragen++
            return { ok: false, status, text: async () => JSON.stringify({ message: 'Bitte neu anmelden', exc_type: 'SessionExpired' }) }
        }

        await modul.heileOderMelde({ anfrage: () => globalThis.fetch('/api/method/x', {}) }).catch(() => {})

        assert.equal(anfragen, 1, `${status}: keine Token-Erneuerung, keine Wiederholung`)
        assert.equal(zustand.reloads, 0, `${status}: kein Neuladen`)
        assert.equal(zustand.weiterleitungen.length, 1, `${status}: Anmeldemaske`)
        assert.match(zustand.weiterleitungen[0], /^\/diakronos\/login\?redirect-to=/)
    }
})

test('WEB-8b: fachlicher Fehler (417 ValidationError) wird NICHT geheilt', async () => {
    const modul = await frisch()
    const { zustand } = umgebung()
    let anfragen = 0
    globalThis.fetch = async () => {
        anfragen++
        return { ok: false, status: 417, text: async () => JSON.stringify({ message: 'Bitte das Ende prüfen.', exc_type: 'ValidationError' }) }
    }

    await modul.heileOderMelde({ anfrage: () => globalThis.fetch('/api/method/x', {}) })

    assert.equal(anfragen, 1)
    assert.equal(zustand.reloads, 0)
    assert.deepEqual(zustand.weiterleitungen, [])
})

test('WEB-8b: Erfolg beim ersten Versuch -> kein Token-Abruf', async () => {
    const modul = await frisch()
    const { protokoll, zustand } = umgebung()
    globalThis.fetch = async (url, opt) => {
        protokoll.push(String(url))
        zustand.anfragen.push({ url: String(url), optionen: opt })
        return OK('ok')
    }

    const ergebnis = await modul.heileOderMelde({ anfrage: () => globalThis.fetch('/api/method/x', {}) })

    assert.equal(ergebnis.res.ok, true)
    assert.equal(protokoll.length, 1, 'kein zusätzlicher Aufruf')
    assert.equal(zustand.anfragen[0].url, '/api/method/x')
    assert.deepEqual(ergebnis.data, { message: 'ok' }, 'die Daten sind schon gelesen (kein zweites res.text())')
})
