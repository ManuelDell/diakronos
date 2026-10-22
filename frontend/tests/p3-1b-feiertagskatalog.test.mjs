/**
 * P3-1b (K4): Der Feiertags-Katalog der Oberfläche stimmt mit dem Server überein.
 *
 * Der Server führt den Katalog in `planrahmen/feiertage.py`; daraus erzeugt
 * `backend/scripts/planrahmen_feiertage.py` die Datei
 * `doku/feiertage.json`. Diese Datei liegt im Build-Kontext unter
 * `/backend/src/diakronos_app/planrahmen/doku/feiertage.json` (siehe
 * backend/Dockerfile, gleiche Brücke wie fürs Kochbuch).
 *
 * Vorher führte die Oberfläche den Katalog in ZWEI eigenen Listen, die schon
 * abwichen („Gründonnerstag“/„Gruendonnerstag“, „Buß-“/„Buss-“). Ein Kommentar
 * behauptete einen Vergleichstest — den gab es nicht. Hier ist er.
 *
 * Lauf ohne die Server-Datei (Entwicklerrechner ohne Build-Kontext): der Test
 * meldet das ausdrücklich als Skip, nicht als Erfolg.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

import { FEIERTAGE } from '../src/diakonos/components/planrahmen/editor.mjs'
import { FEIERTAG_NAMEN, anlassName, setzeFeiertagskatalog }
    from '../src/diakonos/components/planrahmen/anlaesse.mjs'

const hier = dirname(fileURLToPath(import.meta.url))

// Reihenfolge der Kandidaten: im Image (Build-Kontext) zuerst, dann der
// Entwicklerrechner mit dem Repo zwei Ebenen über `frontend/`.
const KANDIDATEN = [
    '/backend/src/diakronos_app/planrahmen/doku/feiertage.json',
    join(hier, '..', '..', 'backend', 'src', 'diakronos_app', 'planrahmen', 'doku', 'feiertage.json'),
]

const pfad = KANDIDATEN.find((p) => existsSync(p))
const katalog = pfad ? JSON.parse(readFileSync(pfad, 'utf8')) : null

test('K4: die Feiertagsliste der Oberfläche deckt den Server-Katalog', { skip: !katalog && `Server-Katalog nicht gefunden: ${KANDIDATEN.join(', ')}` }, () => {
    const server = katalog.map((e) => e.schluessel)
    const ui = FEIERTAGE.map((f) => f.schluessel)
    assert.deepEqual(ui, server, 'Kennungen weichen ab (Reihenfolge und Inhalt)')
})

test('K4: die Namen sind auf beiden Seiten IDENTISCH geschrieben', { skip: !katalog && 'Server-Katalog nicht gefunden' }, () => {
    const abweichungen = []
    for (const eintrag of katalog) {
        const ui = FEIERTAGE.find((f) => f.schluessel === eintrag.schluessel)
        if (!ui) {
            abweichungen.push(`${eintrag.schluessel}: fehlt in der Oberfläche`)
        } else if (ui.name !== eintrag.name) {
            abweichungen.push(`${eintrag.schluessel}: Oberfläche ${ui.name} ≠ Server ${eintrag.name}`)
        }
    }
    assert.deepEqual(abweichungen, [], 'Schreibweisen laufen auseinander')
})

test('K4: anlaesse.mjs leitet seine Namen aus dem einen Katalog ab', { skip: !katalog && 'Server-Katalog nicht gefunden' }, () => {
    for (const eintrag of katalog) {
        assert.equal(
            FEIERTAG_NAMEN[eintrag.schluessel], eintrag.name,
            `${eintrag.schluessel}: FEIERTAG_NAMEN weicht vom Katalog ab`,
        )
        assert.equal(anlassName(eintrag.schluessel), eintrag.name)
    }
})

test('K4: die Namen tragen Umlaute (Review B — vorher ASCII)', () => {
    // Der Opus-Review beanstandete, dass die Vereinheitlichung in Richtung
    // ASCII lief („Gruendonnerstag“/„Buss-“). Der Name ist kein Schlüssel.
    assert.equal(anlassName('gruendonnerstag'), 'Gründonnerstag')
    assert.equal(anlassName('buss_und_bettag'), 'Buß- und Bettag')
    for (const kennung of ['gruendonnerstag', 'buss_und_bettag']) {
        assert.match(kennung, /^[a-z0-9_]+$/, 'Kennung bleibt ASCII')
    }
})

test('K4: feiertage_holen ueberschreibt die Anzeigenamen zur Laufzeit', () => {
    // Der Server-Endpunkt wird wirklich benutzt (usePlanrahmen.feiertageHolen).
    const vorher = anlassName('gruendonnerstag')
    setzeFeiertagskatalog([{ schluessel: 'gruendonnerstag', name: 'Gründonnerstag (Server)', art: 'oster' }])
    assert.equal(anlassName('gruendonnerstag'), 'Gründonnerstag (Server)')
    assert.equal(anlassName('karfreitag'), 'Karfreitag', 'andere Namen bleiben unberuehrt')
    // Ungueltige Eingaben bleiben wirkungslos (Rueckfall auf die statische Liste).
    setzeFeiertagskatalog(null)
    setzeFeiertagskatalog([{ schluessel: 'karfreitag' }, {}, 'x'])
    assert.equal(anlassName('karfreitag'), 'Karfreitag')
    // Statische Liste wiederherstellen (Testreihenfolge bleibt unbeeinflusst).
    setzeFeiertagskatalog([{ schluessel: 'gruendonnerstag', name: vorher, art: 'oster' }])
    assert.equal(anlassName('gruendonnerstag'), vorher)
})
