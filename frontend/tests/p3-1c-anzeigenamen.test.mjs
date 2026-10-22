/**
 * P3-1c (A): Anzeigenamen der Auswahlwerte an ALLEN Anzeigeorten.
 *
 * Der Opus-Review (P3-1b, wichtig A): `auswahlOptionen`/`wertAnzeige` wurden nur
 * im Formular (MerkmalWert, PrParameterForm) benutzt. Plan-Zellen,
 * Programm-Ablauf/Druck und die Filterchips zeigten weiter die gespeicherte
 * Kennung („Maennerchor“/„Floete“). Ausserdem tragen aeltere, in der
 * Betriebs-DB gespeicherte Vorlagenversionen kein `anzeigenamen` — der Name
 * muss zur Laufzeit aus dem Katalog aufgeloest werden (keine Datenmigration).
 *
 * Teil 1 prueft die reine Aufloeselogik (`auswahlwerte.mjs`, importierbar ohne
 * Vue). Teil 2 prueft `zellen.js` (Zellen/Raster/Kalender), das seinerseits
 * `usePlanrahmen.js` (und damit Vue) importiert: wie in
 * `planrahmen-composable.test.mjs` wird die Quelle gelesen und der Vue-/Helfer-
 * Import durch schlanke Ersatzfunktionen ersetzt — geprueft wird die
 * Zellenlogik, nicht das Vue-Setup.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

import {
    wertAnzeige, auswahlOptionen, merkeKatalogDefinition, katalogLeeren,
} from '../src/diakonos/components/planrahmen/auswahlwerte.mjs'

// ── Teil 2: zellen.js ohne Vue laden ───────────────────────────────────────

globalThis.__p31cInstanzenZu = (eintraege, terminId, basisPfad) => {
    const gruppen = new Map()
    for (const e of eintraege || []) {
        if (e.termin !== terminId) continue
        if (!(e.feld_pfad === basisPfad || e.feld_pfad.startsWith(basisPfad + '.')
            || e.feld_pfad.startsWith(basisPfad + '[') || e.feld_pfad.startsWith(basisPfad + '@')
            || e.feld_pfad.startsWith(basisPfad + '#') || e.feld_pfad.startsWith(basisPfad + '/'))) continue
        const rest = e.feld_pfad.slice(basisPfad.length)
        const key = rest === '' ? '__selbst' : rest.replace(/^\./, '')
        if (!gruppen.has(key)) gruppen.set(key, { index: null, selbst: null, unter: new Map() })
        const g = gruppen.get(key)
        if (key === '__selbst') g.selbst = e
        else g.unter.set(key, e)
    }
    const liste = [...gruppen.values()]
    return liste.length ? liste : [{ index: null, selbst: null, unter: new Map() }]
}
globalThis.__p31cWertText = (w) => (w === null || w === undefined || w === '' ? '–' : String(w))
globalThis.__p31cFormat = () => ''
globalThis.__p31cKontext = () => ({})
globalThis.__p31cGehoertZu = (pfad, basis) => pfad === basis
    || ['.', '[', '@', '#', '/'].some((t) => pfad.startsWith(basis + t))
// Die echte Aufloeselogik (Tests von Teil 1 nutzen sie ebenso).
globalThis.__p31cWertAnzeige = wertAnzeige

let zellenQuelle = await readFile(
    new URL('../src/diakonos/components/planrahmen/zellen.js', import.meta.url), 'utf8')
// Den Vue-tragenden Helfer-Import durch schlanke Ersatzfunktionen ersetzen —
// geprueft wird die Zellenlogik, nicht das Vue-Setup (wie in
// planrahmen-composable.test.mjs).
zellenQuelle = zellenQuelle.replace(
    /import \{[^}]*\} from '\.\.\/\.\.\/composables\/usePlanrahmen\.js'/,
    'const instanzenZu = globalThis.__p31cInstanzenZu;\n'
    + 'const wertText = globalThis.__p31cWertText;\n'
    + 'const formatVorlage = globalThis.__p31cFormat;\n'
    + 'const zellenKontext = globalThis.__p31cKontext;\n'
    + 'const feldGehoertZu = globalThis.__p31cGehoertZu;')
assert.ok(!zellenQuelle.includes("usePlanrahmen.js'"), 'Ersatz des Vue-Imports fehlgeschlagen')
// Auch der relative Import auf den Katalog wird ersetzt (data:-URL kann
// relative Pfade nicht aufloesen).
zellenQuelle = zellenQuelle.replace(
    /import \{ wertAnzeige \} from '\.\/auswahlwerte\.mjs'/,
    'const wertAnzeige = globalThis.__p31cWertAnzeige;')
assert.ok(!zellenQuelle.includes("'./auswahlwerte.mjs'"), 'Ersatz des Katalog-Imports fehlgeschlagen')
const zellen = await import('data:text/javascript;base64,' + Buffer.from(zellenQuelle).toString('base64'))
const { feldWertText, feldZellen, gruppenZellen, zellenInhalt } = zellen

// ── Teil 1: reine Aufloeselogik ────────────────────────────────────────────

test('A: wertAnzeige nutzt den eigenen Anzeigenamen der Definition', () => {
    const feld = { id: 'ensemble', art: 'auswahl', werte: ['Maennerchor'], anzeigenamen: { Maennerchor: 'Männerchor' } }
    assert.equal(wertAnzeige(feld, 'Maennerchor'), 'Männerchor')
    assert.equal(wertAnzeige(feld, 'Unbekannt'), 'Unbekannt', 'ohne Eintrag bleibt der Wert')
})

test('A: ohne eigenes anzeigenamen loest der Katalog den Namen auf', () => {
    katalogLeeren()
    merkeKatalogDefinition({
        felder: [{ id: 'ensemble', art: 'auswahl', werte: ['Maennerchor'], anzeigenamen: { Maennerchor: 'Männerchor' } }],
    })
    const altesFeld = { id: 'ensemble', art: 'auswahl', werte: ['Maennerchor'] }
    assert.equal(wertAnzeige(altesFeld, 'Maennerchor'), 'Männerchor', 'Katalog-Nachschlag fehlt')
    const eigenesFeld = { id: 'ensemble', art: 'auswahl', anzeigenamen: { Maennerchor: 'Eigener Name' } }
    assert.equal(wertAnzeige(eigenesFeld, 'Maennerchor'), 'Eigener Name', 'eigener Eintrag hat Vorrang')
    katalogLeeren()
    assert.equal(wertAnzeige(altesFeld, 'Maennerchor'), 'Maennerchor',
        'ohne Katalog bleibt die Kennung (kein Platzhalter)')
})

test('A: der Katalog sammelt Merkmale, Gruppen-Unterfelder und Parameter', () => {
    katalogLeeren()
    merkeKatalogDefinition({
        felder: [{ id: 'gruppe1', art: 'gruppe', inhalt: [
            { id: 'floete', art: 'auswahl', werte: ['Floete'], anzeigenamen: { Floete: 'Flöte' } },
        ] }],
        merkmale: { lieder: { id: 'lieder', art: 'auswahl', anzeigenamen: { Maennerchor: 'Männerchor' } } },
        parameter: [{ id: 'ort', art: 'auswahl', anzeigenamen: { Saal: 'Großer Saal' } }],
    })
    assert.equal(wertAnzeige({ id: 'floete', art: 'auswahl' }, 'Floete'), 'Flöte')
    assert.equal(wertAnzeige({ id: 'lieder', art: 'auswahl' }, 'Maennerchor'), 'Männerchor')
    assert.equal(wertAnzeige({ id: 'ort', art: 'auswahl' }, 'Saal'), 'Großer Saal')
    katalogLeeren()
})

test('A: ungültige Katalogeingaben bleiben wirkungslos', () => {
    katalogLeeren()
    merkeKatalogDefinition(null)
    merkeKatalogDefinition('x')
    merkeKatalogDefinition({ merkmale: { leer: {} } })
    assert.equal(wertAnzeige({ id: 'leer', art: 'auswahl' }, 'X'), 'X')
    katalogLeeren()
})

test('A: auswahlOptionen zeigen Anzeigenamen in Listenreihenfolge', () => {
    const feld = { id: 'ensemble', art: 'auswahl', werte: ['Floete', 'Maennerchor'],
        anzeigenamen: { Floete: 'Flöte', Maennerchor: 'Männerchor' } }
    assert.deepEqual(auswahlOptionen(feld), [
        { wert: 'Floete', text: 'Flöte' },
        { wert: 'Maennerchor', text: 'Männerchor' },
    ])
})

// ── Teil 2: Zellen ─────────────────────────────────────────────────────────

test('A: feldWertText zeigt Auswahlwerte als Anzeigename (auch Listen)', () => {
    const feld = { id: 'ensemble', art: 'auswahl', anzeigenamen: { Maennerchor: 'Männerchor', Floete: 'Flöte' } }
    assert.equal(feldWertText(feld, 'Maennerchor'), 'Männerchor')
    assert.equal(feldWertText(feld, ['Maennerchor', 'Floete']), 'Männerchor, Flöte')
    assert.equal(feldWertText(feld, null), '–')
    assert.equal(feldWertText(feld, ''), '–')
    assert.equal(feldWertText({ id: 'titel', art: 'text' }, 'Abendlied'), 'Abendlied')
})

test('A: feldZellen nutzt die Felddeklaration fuer Auswahlwerte', () => {
    const feld = { id: 'ensemble', art: 'auswahl', werte: ['Maennerchor'], anzeigenamen: { Maennerchor: 'Männerchor' } }
    const eintraege = [{ termin: 't1', feld_pfad: 'ensemble', wert: 'Maennerchor', fixiert: false }]
    const zellenListe = feldZellen({ eintraege, plan: null, termin: { id: 't1' }, feldPfad: 'ensemble', feld, format: '' })
    assert.equal(zellenListe.length, 1)
    assert.equal(zellenListe[0].text, 'Männerchor', 'Plan-Zelle zeigt die Kennung statt des Anzeigenamens')
})

test('A: gruppenZellen loest Unterfelder auf (Auswahl + Katalog-Rueckfall)', () => {
    katalogLeeren()
    merkeKatalogDefinition({ felder: [{ id: 'floete', art: 'auswahl', anzeigenamen: { Floete: 'Flöte' } }] })
    const eintraege = [
        { termin: 't1', feld_pfad: 'gruppe1.floete', wert: 'Floete', fixiert: false },
        { termin: 't1', feld_pfad: 'gruppe1.titel', wert: 'Abendlied', fixiert: false },
    ]
    const inhalt = [{ id: 'floete', art: 'auswahl' }, { id: 'titel', art: 'text' }]
    const liste = gruppenZellen({ eintraege, termin: { id: 't1' }, basis: 'gruppe1', inhalt })
    const nachName = Object.fromEntries(liste.map((z) => [z.name, z.text]))
    assert.equal(nachName.floete, 'Flöte', 'Gruppen-Unterfeld zeigt die Kennung statt des Anzeigenamens')
    assert.equal(nachName.titel, 'Abendlied')
    katalogLeeren()
})

test('A: zellenInhalt reicht inhalt an Gruppenfelder durch', () => {
    const eintraege = [{ termin: 't1', feld_pfad: 'gruppe1.floete', wert: 'Floete', fixiert: false }]
    const feld = { id: 'gruppe1', art: 'gruppe', pfad: 'gruppe1',
        inhalt: [{ id: 'floete', art: 'auswahl', anzeigenamen: { Floete: 'Flöte' } }] }
    const liste = zellenInhalt({ eintraege, plan: null, termin: { id: 't1' }, feld, format: '' })
    assert.equal(liste[0].text, 'Flöte')
})
