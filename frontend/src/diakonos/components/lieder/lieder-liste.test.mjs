/**
 * PF2: Node-Tests der Lieder-Listen-Logik (Cache-Entscheidung + Aufruf-Parameter).
 *
 * Laeuft im Docker-Build mit (backend/Dockerfile Stage 1). Festgenagelt wird
 * genau das, was die Beschleunigung ausmacht und was gefaehrlich waere, wenn
 * es kippt: gecacht wird NUR der ungefilterte Erstaufruf, und der Schluessel
 * enthaelt keine Filter/Suche (sonst zeigte man einen falschen Stand).
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'

import {
    listenArgs, cacheArgs, cacheAktiv, CACHE_NAME, CACHE_VERSION, PAGE,
} from './lieder-liste.mjs'

const LEER = { gruppe: '', kategorie: '', anlass: '', rechte_status: '' }

test('Aufruf-Parameter: erste Seite ohne Filter', () => {
    assert.deepEqual(listenArgs({ seite: 0, suche: '', filter: LEER }),
        { limit: PAGE, start: 0 })
})

test('Aufruf-Parameter: Seite 2 behaelt Start, Limit bleibt', () => {
    assert.deepEqual(listenArgs({ seite: 50, suche: '', filter: LEER }),
        { limit: PAGE, start: 50 })
})

test('Aufruf-Parameter: Suche und Filter werden mitgegeben', () => {
    const a = listenArgs({ seite: 0, suche: '  grace  ',
        filter: { gruppe: 'G1', kategorie: 'K1', anlass: 'A1', rechte_status: 'Gemeinfrei' } })
    assert.equal(a.suche, 'grace')          // getrimmt
    assert.equal(a.gruppe, 'G1')
    assert.equal(a.kategorie, 'K1')
    assert.equal(a.anlass, 'A1')
    assert.equal(a.rechte_status, 'Gemeinfrei')
})

test('Aufruf-Parameter: leere Suche/Filter tauchen NICHT auf', () => {
    const a = listenArgs({ seite: 0, suche: '   ', filter: LEER })
    for (const k of ['suche', 'gruppe', 'kategorie', 'anlass', 'rechte_status']) {
        assert.equal(k in a, false, k)
    }
})

test('Cache ist NUR beim ungefilterten Erstaufruf aktiv', () => {
    assert.equal(cacheAktiv({ filter: LEER, suche: '' }), true)
    assert.equal(cacheAktiv({ filter: LEER, suche: 'grace' }), false)
    assert.equal(cacheAktiv({ filter: { ...LEER, gruppe: 'G1' }, suche: '' }), false)
    assert.equal(cacheAktiv({ filter: { ...LEER, kategorie: 'K1' }, suche: '' }), false)
    assert.equal(cacheAktiv({ filter: { ...LEER, anlass: 'A1' }, suche: '' }), false)
    assert.equal(cacheAktiv({ filter: { ...LEER, rechte_status: 'Gemeinfrei' }, suche: '' }), false)
})

test('Cache-Schluessel enthaelt KEINE Filter/Suche (kein falscher Stand)', () => {
    const args = cacheArgs({ filter: LEER, suche: '' })
    assert.deepEqual(args, { limit: PAGE, start: 0, version: CACHE_VERSION })
    assert.equal('suche' in args, false)
    assert.equal('gruppe' in args, false)
})

test('Ohne Cache-Erlaubnis gibt es keinen Cache-Schluessel', () => {
    assert.equal(cacheArgs({ filter: LEER, suche: 'x' }), null)
    assert.equal(cacheArgs({ filter: { ...LEER, gruppe: 'G1' }, suche: '' }), null)
})

test('Cache-Name ist stabil und eigenstaendig', () => {
    assert.equal(CACHE_NAME, 'musik_get_lieder')
    assert.equal(typeof CACHE_VERSION, 'number')
})
