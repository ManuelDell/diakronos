/**
 * PF1: Node-Tests des nutzerbezogenen Browser-Caches (stale-while-revalidate).
 *
 * Laeuft im Image-Build mit (backend/Dockerfile Stage 1). Prueft genau die
 * Sicherheitszusagen des Auftrags: Schluessel enthaelt die Nutzerkennung,
 * Nutzerwechsel/Abmelden leert, Generatorergebnisse werden nicht gecacht,
 * unvollstaendiger Speicher faellt auf normales Laden zurueck.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'

// Minimaler localStorage-Ersatz (Node hat keins).
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
window.localStorage = new Store()

const mod = await import('./usePlanrahmenCache.js')

function frisch() {
    window.localStorage = new Store()
    mod.cacheNutzerSetzen('')
}

test('speichert und liest einen Stand je Nutzer', () => {
    frisch()
    mod.cacheNutzerSetzen('a@example.org')
    mod.standSchreiben('plan_holen', { plan: 'p1' }, { titel: 'Chorplan' })
    assert.deepEqual(mod.standLesen('plan_holen', { plan: 'p1' }), { titel: 'Chorplan' })
})

test('zeigt nie Daten eines anderen Nutzers (Schluessel je Nutzer)', () => {
    frisch()
    mod.cacheNutzerSetzen('a@example.org')
    mod.standSchreiben('plan_holen', { plan: 'p1' }, { geheim: 'A' })
    // Nutzerwechsel leert den Cache vollstaendig.
    mod.cacheNutzerSetzen('b@example.org')
    assert.equal(mod.standLesen('plan_holen', { plan: 'p1' }), null)
})

test('Abmelden (leere Kennung) leert den Cache', () => {
    frisch()
    mod.cacheNutzerSetzen('a@example.org')
    mod.standSchreiben('plan_holen', { plan: 'p1' }, { x: 1 })
    mod.cacheNutzerSetzen('')          // Abmelden
    assert.equal(mod.standLesen('plan_holen', { plan: 'p1' }), null)
    assert.equal(window.localStorage.length, 0)
})

test('parameter sind Teil des Schluessels', () => {
    frisch()
    mod.cacheNutzerSetzen('a@example.org')
    mod.standSchreiben('plan_holen', { plan: 'p1' }, { v: 1 })
    mod.standSchreiben('plan_holen', { plan: 'p2' }, { v: 2 })
    assert.deepEqual(mod.standLesen('plan_holen', { plan: 'p1' }), { v: 1 })
    assert.deepEqual(mod.standLesen('plan_holen', { plan: 'p2' }), { v: 2 })
})

test('Generator-/Trockenlauf-Ergebnisse werden NIE gecacht', () => {
    frisch()
    mod.cacheNutzerSetzen('a@example.org')
    mod.standSchreiben('plan_generieren', { plan: 'p1' }, { diff: [1] })
    mod.standSchreiben('trockenlauf', { plan: 'p1' }, { diff: [2] })
    assert.equal(mod.standLesen('plan_generieren', { plan: 'p1' }), null)
    assert.equal(mod.standLesen('trockenlauf', { plan: 'p1' }), null)
})

test('ohne Nutzerkennung wird nichts gespeichert oder gelesen', () => {
    frisch()
    mod.standSchreiben('plan_holen', { plan: 'p1' }, { x: 1 })
    assert.equal(mod.standLesen('plan_holen', { plan: 'p1' }), null)
    assert.equal(window.localStorage.length, 0)
})

test('Unterschiedsvergleich erkennt Gleichheit und Aenderung', () => {
    assert.equal(mod.gleich({ a: 1 }, { a: 1 }), true)
    assert.equal(mod.gleich({ a: 1 }, { a: 2 }), false)
})

test('einzelnen Eintrag verwerfen (nach Schreibaktion)', () => {
    frisch()
    mod.cacheNutzerSetzen('a@example.org')
    mod.standSchreiben('plan_holen', { plan: 'p1' }, { v: 1 })
    mod.eintragVerwerfen('plan_holen', { plan: 'p1' })
    assert.equal(mod.standLesen('plan_holen', { plan: 'p1' }), null)
})

test('vollstaendiges Leeren entfernt nur Planrahmen-Eintraege', () => {
    frisch()
    mod.cacheNutzerSetzen('a@example.org')
    mod.standSchreiben('plan_holen', { plan: 'p1' }, { v: 1 })
    window.localStorage.setItem('fremd', 'bleibt')
    mod.cacheLeeren()
    assert.equal(window.localStorage.getItem('fremd'), 'bleibt')
    assert.equal(mod.standLesen('plan_holen', { plan: 'p1' }), null)
})

test('nicht verfuegbarer Speicher: kein Cache, aber kein Fehler', () => {
    frisch()
    window.localStorage = {
        get length() { throw new Error('blockiert') },
        key() { throw new Error('blockiert') },
        getItem() { throw new Error('blockiert') },
        setItem() { throw new Error('blockiert') },
        removeItem() { throw new Error('blockiert') },
    }
    mod.cacheNutzerSetzen('a@example.org')
    assert.doesNotThrow(() => mod.standSchreiben('plan_holen', { plan: 'p1' }, { v: 1 }))
    assert.equal(mod.standLesen('plan_holen', { plan: 'p1' }), null)
    assert.doesNotThrow(() => mod.cacheLeeren())
})
