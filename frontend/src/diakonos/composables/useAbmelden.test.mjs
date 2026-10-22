/**
 * BF1-L (W3/W4/W9): Node-Tests fuer `useAbmelden`.
 *
 * Laeuft im Image-Build mit (backend/Dockerfile Stage 1). Prueft genau die
 * Stellen, die das Review als unbewiesen bemangelt hat:
 *  - der Server nennt ein Ziel (JSON `redirect`) -> die SPA FOLGT ihm
 *    (vorher scheiterte `redirect: 'manual'` am `opaqueredirect` des Browsers),
 *  - eine Fehlerantwort (403 CSRF / 500) wird NICHT als Erfolg gewertet —
 *    es wird kein Cache geleert und NICHT auf /login gesprungen,
 *  - beim gelungenen Abmelden werden ALLE nutzerbezogenen Browser-Staende
 *    geleert (Planrahmen-Cache, Entwuerfe, Impersonation).
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'

class Store {
    #m = new Map()
    get length() { return this.#m.size }
    key(i) { return [...this.#m.keys()][i] ?? null }
    getItem(k) { return this.#m.has(k) ? this.#m.get(k) : null }
    setItem(k, v) { this.#m.set(String(k), String(v)) }
    removeItem(k) { this.#m.delete(String(k)) }
    clear() { this.#m.clear() }
}

globalThis.window = globalThis.window || {}
globalThis.sessionStorage = globalThis.sessionStorage || new Store()
window.__DIakonosBOOT = { csrf_token: 'csrf-test' }

const mod = await import('./useAbmelden.js')
const cacheMod = await import('./usePlanrahmenCache.js')

// Der Abmelde-Weg setzt am Ende `window.location.href`. Node hat kein
// `location`-Objekt; wir ersetzen es durch einen Beobachter.
function setzeOrt() {
    const ort = { href: '/ausgangslage' }
    globalThis.window.location = ort
    return ort
}

function frisch() {
    window.localStorage = new Store()
    globalThis.sessionStorage = new Store()
    cacheMod.cacheLeeren()
    cacheMod.cacheNutzerSetzen('')
    delete globalThis.fetch
    setzeOrt()
}

/** Antwort-Attrappe: JSON-Koerper, Status, optionale Header. */
function antwort({ status = 200, body = {}, headers = {} } = {}) {
    return {
        status,
        ok: status >= 200 && status < 300,
        headers: { get: (n) => headers[n] ?? null },
        clone() { return this },
        async json() { return body },
    }
}

// ── Erfolgsfall: Server nennt ein Ziel, die SPA folgt ihm ───────────────────

test('abmelden: folgt dem Server-Ziel aus dem JSON-Koerper', async () => {
    frisch()
    const ort = setzeOrt()
    let aufgerufen = null
    globalThis.fetch = async (url, opt) => {
        aufgerufen = { url, opt }
        return antwort({ status: 200, body: { message: { redirect: 'https://anbieter.example/end-session' } } })
    }
    const res = await mod.abmelden()
    assert.equal(res.ok, true)
    assert.equal(aufgerufen.url, '/logout')
    assert.equal(aufgerufen.opt.method, 'POST')
    assert.equal(
        aufgerufen.opt.headers['X-Frappe-CSRF-Token'], 'csrf-test',
        'CSRF-Token muss mitgeschickt werden können (POST ist seit PT1 Pflicht).',
    )
    assert.equal(
        ort.href, 'https://anbieter.example/end-session',
        'Die SPA muss dem vom Server genannten RP-Logout-Ziel folgen (W3).',
    )
})

test('abmelden: SPA-Ziel -> lokal auf /login', async () => {
    frisch()
    const ort = setzeOrt()
    globalThis.fetch = async () => antwort({ status: 200, body: { message: { redirect: '/diakonos' } } })
    const res = await mod.abmelden()
    assert.equal(res.ok, true)
    assert.equal(ort.href, '/login')
})

// ── Fehlerfall: NICHT als Erfolg werten ─────────────────────────────────────

test('abmelden: 403 (CSRF) wird nicht als Erfolg gewertet', async () => {
    frisch()
    const ort = setzeOrt()
    globalThis.fetch = async () => antwort({ status: 403, body: {} })
    const res = await mod.abmelden()
    assert.equal(res.ok, false)
    assert.match(res.fehler, /403/)
    assert.equal(ort.href, '/ausgangslage', 'Darf bei Fehler NICHT auf /login springen (W3).')
})

test('abmelden: 500 wird nicht als Erfolg gewertet', async () => {
    frisch()
    const ort = setzeOrt()
    globalThis.fetch = async () => antwort({ status: 500, body: {} })
    const res = await mod.abmelden()
    assert.equal(res.ok, false)
    assert.equal(ort.href, '/ausgangslage')
})

test('abmelden: Netzfehler wird nicht als Erfolg gewertet', async () => {
    frisch()
    const ort = setzeOrt()
    globalThis.fetch = async () => { throw new Error('offline') }
    const res = await mod.abmelden()
    assert.equal(res.ok, false)
    assert.match(res.fehler, /Verbindung/i)
    assert.equal(ort.href, '/ausgangslage')
})

// ── Fallback: SEC1-Route fehlt -> Frappe-kompatibler Pfad ───────────────────

test('abmelden: 404 der SEC1-Route nutzt den Fallback-Pfad', async () => {
    frisch()
    const ort = setzeOrt()
    const pfade = []
    globalThis.fetch = async (url) => {
        pfade.push(url)
        if (url === '/logout') return antwort({ status: 404, body: {} })
        return antwort({ status: 200, body: { message: { redirect: '/login' } } })
    }
    const res = await mod.abmelden()
    assert.equal(res.ok, true)
    assert.deepEqual(pfade, ['/logout', '/api/method/logout'])
    assert.equal(ort.href, '/login')
})

// ── Cache/Staende leeren (W4) ───────────────────────────────────────────────

test('abmelden: leert Planrahmen-Cache, Entwuerfe und Impersonation', async () => {
    frisch()
    setzeOrt()
    // Nutzerbezogene Staende anlegen: Planrahmen-Cache braucht eine Kennung.
    cacheMod.cacheNutzerSetzen('a@example.org')
    cacheMod.standSchreiben('plan_holen', { plan: 'p1' }, { geheim: 1 })
    window.localStorage.setItem('dk-entwurf:plan:p1', '{}')
    window.localStorage.setItem('pr-entwurf:a@example.org:plan:p1', '{}')
    window.localStorage.setItem('dk-impersonation', 'Administrator')
    globalThis.fetch = async () => antwort({ status: 200, body: { message: { redirect: '/login' } } })

    await mod.abmelden()

    assert.equal(cacheMod.standLesen('plan_holen', { plan: 'p1' }), null, 'Planrahmen-Cache nicht geleert.')
    assert.equal(window.localStorage.getItem('pr-entwurf:a@example.org:plan:p1'), null, 'Echter Plan-Entwurf nicht geleert.')
    assert.equal(window.localStorage.getItem('dk-entwurf:plan:p1'), null, 'Entwurf nicht geleert.')
    assert.equal(window.localStorage.getItem('dk-impersonation'), null, 'Impersonation nicht geleert.')
})

test('alleBrowserStaendeLeeren: leert auch ohne vorherigen Plan-Seitenaufruf', () => {
    frisch()
    // KEIN cacheNutzerSetzen vorher — genau der Fall, in dem die frueher
    // benutzte cacheNutzerSetzen('')-Loesung nichts leerte (W4).
    window.localStorage.setItem('dk-pr-swr:pf1-v1:a@example.org:plan_holen:{}', '{"x":1}')
    window.localStorage.setItem('dk-entwurf:x', '1')
    window.localStorage.setItem('fremd', 'bleibt')
    mod.alleBrowserStaendeLeeren()
    const rest = []
    for (let i = 0; i < window.localStorage.length; i += 1) rest.push(window.localStorage.key(i))
    assert.ok(!rest.some((k) => k.startsWith('dk-pr-swr:')), 'Planrahmen-Cache blieb stehen.')
    assert.ok(!rest.includes('dk-entwurf:x'), 'Entwurf blieb stehen.')
    assert.ok(rest.includes('fremd'), 'Fremde Schluessel duerfen NICHT geloescht werden.')
})
