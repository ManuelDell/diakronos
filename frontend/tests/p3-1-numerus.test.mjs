/**
 * P3-1: Klammerplurale in der Oberfläche (OP-CHOR-12 mit OP-UI-27).
 *
 * Reproduziert zuvor: Die Seiten schrieben „{{ n }} Lied(er)“, „1 Termin(e)“,
 * „3 Fassung(en)“, „2 Rolle(n)“ — ein Klammerplural passt zu keiner Zahl und
 * liest sich wie ein Formular. Richtig ist der Numerus aus der Zahl:
 * „1 Lied“, „2 Lieder“, „1 Termin“, „2 Termine“.
 *
 * Der Helfer steht EINMAL in `components/ui/begriffe.mjs` (Glossar S15) und
 * wird vom Plan-Rahmen über `planrahmen/format.mjs` weitergereicht.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

import { wortImNumerus, zahlWort } from '../src/diakonos/components/ui/begriffe.mjs'
import { wortImNumerus as wpNumerus, zahlWort as wpZahl } from '../src/diakonos/components/planrahmen/format.mjs'

const hier = dirname(fileURLToPath(import.meta.url))
const src = join(hier, '..', 'src', 'diakonos')
const lies = (rel) => readFileSync(join(src, rel), 'utf8')

test('wortImNumerus setzt Einzahl und Mehrzahl richtig', () => {
    assert.equal(wortImNumerus(1, 'Lied', 'Lieder'), 'Lied')
    assert.equal(wortImNumerus(0, 'Lied', 'Lieder'), 'Lieder')
    assert.equal(wortImNumerus(2, 'Lied', 'Lieder'), 'Lieder')
    assert.equal(wortImNumerus(1, 'Termin', 'Termine'), 'Termin')
    assert.equal(wortImNumerus(7, 'Fassung', 'Fassungen'), 'Fassungen')
    // Vorgabe ohne Mehrzahl: „+en“.
    assert.equal(wortImNumerus(1, 'Änderung'), 'Änderung')
    assert.equal(wortImNumerus(2, 'Änderung'), 'Änderungen')
})

test('zahlWort setzt den Numerus mit deutscher Zahl', () => {
    assert.equal(zahlWort(1, 'Termin', 'Termine'), '1 Termin')
    assert.equal(zahlWort(3, 'Termin', 'Termine'), '3 Termine')
    assert.equal(zahlWort(1234, 'Lied', 'Lieder'), '1.234 Lieder')
})

test('der Plan-Rahmen reicht denselben Helfer weiter (keine zweite Fassung)', () => {
    assert.equal(wpNumerus, wortImNumerus, 'zwei Fassungen von wortImNumerus')
    assert.equal(wpZahl, zahlWort, 'zwei Fassungen von zahlWort')
})

test('keine Klammerplurale mehr in den betroffenen Seiten', () => {
    const verboten = /Lied\(er\)|Termin\(e\)|Fassung\(en\)|Rolle\(n\)|Lied\(er\)/
    for (const datei of ['pages/Lieder.vue', 'pages/LiedDetail.vue',
                         'pages/LiedgruppeDetail.vue', 'pages/Moderation.vue']) {
        const text = lies(datei)
        const treffer = text.match(verboten)
        assert.equal(treffer, null, `${datei}: Klammerplural „${treffer && treffer[0]}“ steht noch`)
    }
})

test('die betroffenen Seiten nutzen den gemeinsamen Numerus-Helfer', () => {
    const erwartet = {
        'pages/Lieder.vue': /wortImNumerus\(/,
        'pages/LiedDetail.vue': /wortImNumerus\(/,
        'pages/LiedgruppeDetail.vue': /wortImNumerus\(/,
        'pages/Moderation.vue': /zahlWort\(/,
    }
    for (const [datei, muster] of Object.entries(erwartet)) {
        assert.match(lies(datei), muster, `${datei}: Numerus-Helfer fehlt`)
    }
})

test('UXP-R23: keine ae/oe/ue-Ersatzschreibung in sichtbaren Plantexten', () => {
    // „Knoepfe“ in der Druckleiste war die letzte sichtbare Stelle; Kennungen
    // (etwa „vorher_geuebt“) stehen nie in der Anzeige und bleiben ASCII.
    const ansicht = lies('components/planrahmen/PrAnsicht.vue')
    assert.doesNotMatch(ansicht, /Knoepfe/, '„Knoepfe“ statt „Knöpfe“ in PrAnsicht.vue')
    assert.match(ansicht, /Knöpfe/, '„Knöpfe“ fehlt in PrAnsicht.vue')
})
