// R-3: Das Menü zeigt Module nur mit Leserecht (das EINE Rechtesystem).
// Der Server liefert `module_sichtbar` im Boot; `sichtbareEintraege` filtert
// Einträge mit Feld `modul`. Ohne Boot-Liste wird nicht gefiltert (alter Stand).
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { MENUE, sichtbareEintraege, bootModule } from '../src/diakonos/menue.js'

const alleIds = (opts) => MENUE.flatMap(g => sichtbareEintraege(g, opts).map(e => e.id))

test('Beiträge, Wiki und Lieder tragen ein Modul', () => {
    const eintraege = MENUE.flatMap(g => g.eintraege || [])
    const modul = Object.fromEntries(eintraege.map(e => [e.id, e.modul]))
    assert.equal(modul.beitraege, 'beitraege')
    assert.equal(modul.wiki, 'wiki')
    assert.equal(modul.lieder, 'lieder')
})

test('ohne Modul-Recht kein Menüpunkt (Live-Test 11.11.: Jugendleiter sieht Lieder)', () => {
    const ids = alleIds({ module: ['kalender', 'beitraege', 'wiki', 'aufgaben'] })
    assert.ok(!ids.includes('lieder'))
    assert.ok(ids.includes('wiki'))
    assert.ok(ids.includes('beitraege'))
})

test('mit Modul-Recht erscheint der Punkt', () => {
    assert.ok(alleIds({ module: ['lieder'] }).includes('lieder'))
})

test('Einträge ohne Modul bleiben unberührt (Kalender, Personen)', () => {
    const ids = alleIds({ module: [] })
    assert.ok(ids.includes('kalender'))
    assert.ok(!ids.includes('wiki') && !ids.includes('lieder') && !ids.includes('beitraege'))
})

test('ohne Boot-Liste wird nicht gefiltert (alter Server)', () => {
    delete globalThis.__DIakonosBOOT
    assert.equal(bootModule(), null)
    assert.ok(alleIds({}).includes('lieder'))
})

test('Boot-Liste wird gelesen', () => {
    globalThis.__DIakonosBOOT = { module_sichtbar: ['wiki'] }
    try {
        assert.deepEqual(bootModule(), ['wiki'])
        const ids = alleIds({})
        assert.ok(ids.includes('wiki') && !ids.includes('lieder'))
    } finally {
        delete globalThis.__DIakonosBOOT
    }
})
