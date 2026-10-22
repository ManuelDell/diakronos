/**
 * P3-1: Texte im Plan-Bereich (Ursachen, nicht Symptome).
 *
 * Reproduziert zuvor:
 *  - OP-CHOR-12 „1 Änderungen für 1 Termine“, „1 Personen mit klavier“,
 *               „Eintraege vollstaendig“.
 *  - UXP-R22   Anlass-Chips zeigten Kennungen (heiligabend, 1_weihnachtstag)
 *              und standen doppelt neben dem Sammelanlass „feiertag“.
 *  - UXP-R23   Versionsliste „Erstellt von —“ (created_by statt erstellt_von),
 *              Bedarfsdialog zeigte Merkmals-Kennungen („klavier“).
 *  - UXP-R24   Datum doppelt abgefragt (Parameter `datum`/`zeitraum`),
 *              ISO-Datum im Programmkopf, Pfad-Jargon „· /zeitraum“.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

import { zahlWort, wortImNumerus, formatTemplate } from '../src/diakonos/components/planrahmen/format.mjs'
import { anlassName, sichtbareAnlaesse, FEIERTAG_NAMEN, SAMMELANLASS } from '../src/diakonos/components/planrahmen/anlaesse.mjs'

const hier = dirname(fileURLToPath(import.meta.url))
const src = join(hier, '..', 'src', 'diakonos')
const lies = (p) => readFileSync(join(src, p), 'utf8')

test('OP-CHOR-12: Zahlwort richtet sich nach dem Numerus', () => {
    assert.equal(zahlWort(1, 'Änderung', 'Änderungen'), '1 Änderung')
    assert.equal(zahlWort(3, 'Änderung', 'Änderungen'), '3 Änderungen')
    assert.equal(zahlWort(1, 'Termin', 'Termine'), '1 Termin')
    assert.equal(zahlWort(2, 'Termin', 'Termine'), '2 Termine')
    assert.equal(zahlWort(1234, 'Termin', 'Termine'), '1.234 Termine')
    assert.equal(wortImNumerus(1, 'Lied', 'Lieder'), 'Lied')
    assert.equal(wortImNumerus(5, 'Lied', 'Lieder'), 'Lieder')
})

test('OP-CHOR-12: PrDiff baut die Zusammenfassung mit zahlWort', () => {
    const diff = lies('components/planrahmen/PrDiff.vue')
    assert.match(diff, /zahlWort\(/, 'PrDiff nutzt die Plural-Hilfe nicht')
    assert.doesNotMatch(diff, /\{\{ diff\.length \}\} \{\{ vorschlag \? 'Vorschläge' : 'Änderungen' \}\} für \{\{ gruppen\.length \}\} Termine/)
})

test('UXP-R22: Anlässe zeigen Katalognamen, nicht Kennungen', () => {
    assert.equal(anlassName('heiligabend'), 'Heiligabend')
    assert.equal(anlassName('1_weihnachtstag'), '1. Weihnachtstag')
    assert.equal(anlassName('2_weihnachtstag'), '2. Weihnachtstag')
    // Vorlage gewinnt gegen den Katalog.
    assert.equal(anlassName('abendmahl', [{ id: 'abendmahl', name: 'Heiliges Abendmahl' }]), 'Heiliges Abendmahl')
    // Unbekannt: lesbar gemacht, nie roh.
    assert.equal(anlassName('gottesdienst_extra'), 'Gottesdienst extra')
})

test('UXP-R22: Sammelanlass „feiertag“ verschwindet, Doppelungen auch', () => {
    assert.equal(SAMMELANLASS, 'feiertag')
    assert.deepEqual(
        sichtbareAnlaesse(['feiertag', 'heiligabend', 'feiertag']),
        ['heiligabend'],
    )
    assert.deepEqual(sichtbareAnlaesse(['abendmahl', 'abendmahl']), ['abendmahl'])
    assert.deepEqual(sichtbareAnlaesse(undefined), [])
})

test('UXP-R22: die Tabelle zeigt Anlässe nur an EINER Stelle', () => {
    const tabelle = lies('components/planrahmen/PrTabelle.vue')
    const vorkommen = [...tabelle.matchAll(/anlassText\(a\)/g)].length
    // Anlass-Spalte (Zeile) + Mobil-Kartenkopf — nicht mehr zusätzlich in der Termin-Zelle.
    assert.equal(vorkommen, 3, `Anlass-Chips erscheinen ${vorkommen}× — Doppelanzeige?`)
    assert.match(tabelle, /sichtbareAnlaesse/, 'PrTabelle filtert den Sammelanlass nicht')
})

test('UXP-R22: der Feiertagskatalog der Oberfläche deckt alle Kennungen ab', () => {
    for (const id of ['karfreitag', 'himmelfahrt', 'heiligabend', '1_weihnachtstag',
                      '2_weihnachtstag', 'buss_und_bettag', 'erntedank']) {
        assert.ok(FEIERTAG_NAMEN[id], `Feiertag fehlt im Katalog: ${id}`)
    }
})

test('UXP-R23: Versionsliste liest erstellt_von', () => {
    const einrichten = lies('pages/planrahmen/Einrichten.vue')
    assert.match(einrichten, /v\.erstellt_von/, 'Eigenschaft `erstellt_von` wird nicht gelesen')
    assert.doesNotMatch(einrichten, /v\.created_by \|\| '—'/, 'alter Ausdruck (immer „—“) steht noch')
})

test('UXP-R23: Bedarfsdialog zeigt den Anzeigenamen', () => {
    const dialog = lies('components/planrahmen/BedarfDialog.vue')
    assert.match(dialog, /e\.name \|\| e\.kennung/, 'Dialog zeigt weiter nur die Kennung')
})

test('UXP-R24: Datum/Zeitraum werden nicht doppelt abgefragt', () => {
    const uebersicht = lies('pages/planrahmen/Uebersicht.vue')
    assert.match(uebersicht, /ZEITRAUM_PARAMETER/, 'Filter für doppelte Zeitraum-Parameter fehlt')
    assert.match(uebersicht, /parameterFuerServer\(\)/, 'Parameter werden nicht aus dem Zeitraum abgeleitet')
    assert.match(uebersicht, /planAnlegen\([\s\S]{0,120}parameterFuerServer\(\)/)
})

test('UXP-R24: ISO-Daten werden im Programmkopf lokalisiert', () => {
    assert.equal(formatTemplate('{termin.datum}', { termin: { datum: '2026-12-30' } }), '30.12.2026')
    // Kein Datum? Unverändert.
    assert.equal(formatTemplate('{plan.titel}', { plan: { titel: 'Weihnachtskonzert' } }), 'Weihnachtskonzert')
})

test('UXP-R24: roher Pfad erscheint nicht als Meldungs-Kontext', () => {
    const meldungen = lies('components/planrahmen/PrMeldungen.vue')
    assert.match(meldungen, /kontext\(m\) !== pfadRoh\(m\)/, 'Pfad-Jargon wird weiter angezeigt')
})
