/**
 * P3-1d — Nacharbeit zu P3-1c (Opus-Review W1–W3, K1–K3).
 *
 * W1 (UXD-R29, Live-Ärger): Die Rückfrage „Änderungen verwerfen?“ kam nach
 *    Speichern und nach Abbrechen bei JEDEM weiteren Seitenwechsel, weil
 *    `lesen()` ohne offenes Formular `null` liefert und der Wächter `"null"` mit
 *    dem zuletzt gemerkten Stand verglich. Geprüft wird der ABLAUF, nicht dass
 *    `merken()` irgendwo vorkommt:
 *      öffnen → ändern → SPEICHERN → wegnavigieren  = KEINE Rückfrage
 *      öffnen → ändern → ABBRECHEN → wegnavigieren  = KEINE Rückfrage
 *      öffnen → ändern → wegnavigieren              = Rückfrage
 * W2: Merkmale sind gruppenweise organisiert (`{person: […], lieder: […]}`).
 *    Der Katalog wertet jetzt die Gruppenform aus; Kochbuch-Vorlagen sind
 *    zusätzliche Quelle. Geprüft mit der ECHTEN Vorlagenform (Kochbuch-Chorplan).
 * W3: `feiertage_holen` wird beim Laden des Plan-Bereichs wirklich gerufen und
 *    wirkt auf die Liste, die der Termin-Editor rendert.
 * K1/K2/K3: Einwort-Toasts, „Zulassung“, Nummernspalte nur bei `{nr}`.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { readFileSync } from 'node:fs'

import * as auswahl from '../src/diakonos/components/planrahmen/auswahlwerte.mjs'

// Der Katalog-Name ist neu; ohne ihn (Stand vor der Nacharbeit) laufen die
// Tests trotzdem und schlagen an der Sache fehl, nicht an einem Importfehler.
const { wertAnzeige, merkeKatalogDefinition, katalogLeeren } = auswahl
const merkeKochbuchVorlage = auswahl.merkeKochbuchVorlage || auswahl.merkeKatalogDefinition
const alleMerkmale = auswahl.alleMerkmale || (() => [])
import { setzeFeiertagskatalog } from '../src/diakonos/components/planrahmen/anlaesse.mjs'
import { FEIERTAGE } from '../src/diakonos/components/planrahmen/editor.mjs'

const quelle = async (p) => readFile(new URL(p, import.meta.url), 'utf8')

/** Kochbuch-Chorplan UND -Programm — die echte Vorlagenform. */
const kochbuch = (name) => JSON.parse(readFileSync(
    new URL(`../../backend/src/diakronos_app/planrahmen/doku/kochbuch/${name}.json`, import.meta.url), 'utf8'))

const chorplan = kochbuch('chorplan')
const programm = kochbuch('programm')

// ── W1: Formularschutz-Ablauf ──────────────────────────────────────────────

/** Formular-Composable mit ersetztem Bestätigungsdialog nachbauen. */
async function schutzMit(lesen) {
    const fragen = []
    const formularQuelle = (await quelle('../src/diakonos/composables/useFormularSchutz.js'))
        .replace("import { bestaetigen } from './useBestaetigen.js'", 'const bestaetigen = globalThis.__frage')
    globalThis.__frage = async (frage) => { fragen.push(frage); return true }
    const m = await import('data:text/javascript;base64,' + Buffer.from(
        formularQuelle + `\n// ${Math.random()}`).toString('base64'))
    return { schutz: m.useFormularSchutz(lesen), fragen }
}

/**
 * Der Ablauf einer Seite: `offen` ist das Bearbeiten-Flag, `form` das
 * Formularmodell. `lesen()` liefert ohne offenes Formular `null` — genau wie
 * MitgliedDetail, Profile und GruppeDetail es verdrahten.
 */
async function seitenAblauf() {
    const zustand = { offen: false, form: { name: '' } }
    const { schutz, fragen } = await schutzMit(() => (zustand.offen ? zustand.form : null))
    return {
        zustand, schutz, fragen,
        oeffnen() { zustand.form = { name: 'Alt' }; zustand.offen = true; schutz.merken() },
        aendern() { zustand.form.name = 'Neu' },
        speichern() { zustand.offen = false },
        abbrechen() { zustand.offen = false },
    }
}

test('W1: oeffnen -> aendern -> speichern -> wegnavigieren fragt NICHT', async () => {
    const s = await seitenAblauf()
    s.oeffnen(); s.aendern(); s.speichern()
    assert.equal(await s.schutz.darfSchliessen(), true, 'nach dem Speichern darf nichts gefragt werden')
    assert.equal(s.fragen.length, 0, 'keine Rückfrage nach dem Speichern')
    // und auch beim zweiten/ dritten Wechsel nicht (der Fehler wiederholte sich)
    assert.equal(await s.schutz.darfSchliessen(), true)
    assert.equal(s.fragen.length, 0)
})

test('W1: oeffnen -> aendern -> abbrechen -> wegnavigieren fragt NICHT', async () => {
    const s = await seitenAblauf()
    s.oeffnen(); s.aendern(); s.abbrechen()
    assert.equal(await s.schutz.darfSchliessen(), true, 'nach dem Abbrechen darf nichts gefragt werden')
    assert.equal(s.fragen.length, 0)
    assert.equal(await s.schutz.darfSchliessen(), true)
    assert.equal(s.fragen.length, 0)
})

test('W1: oeffnen -> aendern -> wegnavigieren FRAGT', async () => {
    const s = await seitenAblauf()
    s.oeffnen(); s.aendern()
    assert.equal(await s.schutz.darfSchliessen(), true, '„Verwerfen“ erlaubt den Wechsel')
    assert.equal(s.fragen.length, 1, 'genau eine Rückfrage bei echten Änderungen')
    assert.match(s.fragen[0].titel, /verwerfen/i)
})

test('W1: oeffnen -> aendern -> zurueckaendern -> wegnavigieren fragt nicht', async () => {
    const s = await seitenAblauf()
    s.oeffnen(); s.aendern(); s.zustand.form.name = 'Alt'
    assert.equal(await s.schutz.darfSchliessen(), true)
    assert.equal(s.fragen.length, 0)
})

test('W1: nach Speichern und erneutem Oeffnen gilt der neue Grundstand', async () => {
    const s = await seitenAblauf()
    s.oeffnen(); s.aendern(); s.speichern()
    assert.equal(await s.schutz.darfSchliessen(), true)
    s.oeffnen()                       // zweites Mal bearbeiten, ohne Änderung
    assert.equal(await s.schutz.darfSchliessen(), true)
    assert.equal(s.fragen.length, 0, 'frisch geöffnetes Formular ist sauber')
    s.aendern()
    assert.equal(await s.schutz.darfSchliessen(), true)
    assert.equal(s.fragen.length, 1, 'danach zählt eine echte Änderung wieder')
})

test('W1: die drei Seiten liefern ohne offenes Formular null (Voraussetzung der Regel)', async () => {
    const muster = [
        ['MitgliedDetail.vue', /\(\) => \(isEditing\.value \? editForm : null\)/],
        ['Profile.vue', /\(\) => \(editingData\.value \? form : null\)/],
        ['GruppeDetail.vue', /\(\) => \(editingDesc\.value/],
    ]
    for (const [datei, re] of muster) {
        const text = await quelle(`../src/diakonos/pages/${datei}`)
        assert.match(text, re, `${datei}: lesen() liefert nicht null, wenn das Formular zu ist`)
    }
})

// ── W2: Anzeigenamen gespeicherter Vorlagen ────────────────────────────────

test('W2: merkmale werden gruppenweise ausgewertet (echte Kochbuchform)', () => {
    katalogLeeren()
    // Neue Vorlagenversion ohne eigenes `anzeigenamen` (wie in der Betriebs-DB).
    merkeKochbuchVorlage(chorplan)
    const ohneNamen = { id: 'instrument', art: 'auswahl', werte: ['Floete', 'Geige'] }
    assert.equal(wertAnzeige(ohneNamen, 'Floete'), 'Flöte', 'Kochbuch-Katalog greift nicht')
    const ensemble = { id: 'ensemble', art: 'auswahl', werte: ['Maennerchor'] }
    merkeKochbuchVorlage(programm)
    assert.equal(wertAnzeige(ensemble, 'Maennerchor'), 'Männerchor')
})

test('W2: die Gruppenform wird erkannt, die Einzelform weiterhin auch', () => {
    const gruppiert = alleMerkmale(chorplan.merkmale)
    const ids = gruppiert.map((m) => m.id)
    assert.ok(ids.includes('instrument'), 'Merkmal „instrument“ aus Gruppe „person“ fehlt')
    assert.ok(ids.includes('dirigent'), 'Merkmal „dirigent“ fehlt')
    // Alte Form {id: def} bleibt lesbar.
    assert.deepEqual(alleMerkmale({ x: { id: 'x', anzeigenamen: { a: 'A' } } }).map((m) => m.id), ['x'])
    assert.deepEqual(alleMerkmale(null), [])
})

test('W2: eine Definition am Objekt hat Vorrang vor dem Katalog', () => {
    katalogLeeren()
    merkeKochbuchVorlage(chorplan)
    const eigen = { id: 'instrument', anzeigenamen: { Floete: 'Querflöte' } }
    assert.equal(wertAnzeige(eigen, 'Floete'), 'Querflöte')
    // Ohne eigenen Eintrag für DIESEN Wert greift der Katalog.
    assert.equal(wertAnzeige(eigen, 'Geige'), 'Geige')
})

test('W2: gespeicherte Versionen ueberschreiben den Kochbuch-Nachschlag', () => {
    katalogLeeren()
    merkeKochbuchVorlage(chorplan)                       // zuerst Kochbuch
    merkeKatalogDefinition({ merkmale: { person: [{ id: 'instrument', anzeigenamen: { Floete: 'Flauto' } }] } })
    assert.equal(wertAnzeige({ id: 'instrument' }, 'Floete'), 'Flauto',
        'die nachgeladene Betriebs-Version muss gewinnen')
})

test('W2: die Uebersicht laedt Kochbuch und Feiertage beim Betreten des Bereichs', async () => {
    // REST-1 (2): Der Katalog laeuft jetzt zentral ueber `katalogSichern()`
    // (Kochbuch-Vorlagen + Feiertage, einmal je Sitzung) — damit ihn auch die
    // Arbeitsseiten beim Direktaufruf holen. Vorher standen die beiden Aufrufe
    // direkt in der Uebersicht.
    const text = await quelle('../src/diakonos/pages/planrahmen/Uebersicht.vue')
    assert.match(text, /katalogSichern/, 'Uebersicht ruft den Katalog nicht ab')
    const zentral = await quelle('../src/diakonos/composables/usePlanrahmen.js')
    assert.match(zentral, /async function kochbuchKatalogMerken\(\)[\s\S]{0,400}kochbuchListe\(\)/)
    assert.match(zentral, /kochbuchKatalogMerken\(\),[\s\S]{0,200}feiertageHolen\(\)/,
        'katalogSichern holt Kochbuch-Vorlagen und Feiertage')
    // Beide VOR bzw. parallel zum Laden der Liste, nicht erst im Editor.
    const laden = text.slice(text.indexOf('async function ladenAlles'))
    assert.ok(laden.indexOf('katalogSichern') < laden.indexOf('await Promise.all(')
        || laden.indexOf('katalogSichern') < laden.indexOf('await Promise.allSettled'),
        'Kochbuch-Katalog wird erst nach der Planliste geholt')
})

test('W2: der Anzeigenamen-Nachschlag holt JEDE Kochbuch-Vorlage ueber die API', async () => {
    const text = await quelle('../src/diakonos/composables/usePlanrahmen.js')
    const start = text.indexOf('async function kochbuchKatalogMerken')
    assert.ok(start > 0, 'kochbuchKatalogMerken fehlt')
    const block = text.slice(start, start + 1600)
    assert.match(block, /kochbuchListe\(\)/)
    assert.match(block, /kochbuchHolen\(/, 'die Kochbuch-Definitionen werden nicht geholt')
    assert.match(block, /merkeKochbuchVorlage\(/)
})

// ── W3: Feiertags-Endpunkt ─────────────────────────────────────────────────

test('W3: setzeFeiertagskatalog wirkt auf die Liste des Termin-Editors', () => {
    const vorher = FEIERTAGE.length
    setzeFeiertagskatalog([
        { schluessel: 'karfreitag', name: 'Karfreitag (Server)', art: 'oster' },
        { schluessel: 'neuer_tag', name: 'Neuer Tag', art: 'fest' },
    ])
    const karfreitag = FEIERTAGE.find((f) => f.schluessel === 'karfreitag')
    assert.equal(karfreitag.name, 'Karfreitag (Server)', 'FEIERTAGE wurde nicht überschrieben')
    assert.ok(FEIERTAGE.some((f) => f.schluessel === 'neuer_tag' && f.name === 'Neuer Tag'))
    assert.equal(FEIERTAGE.length, vorher + 1, 'unbekannte Server-Kennung wird angehängt')
    // Nichts geht verloren.
    assert.ok(FEIERTAGE.some((f) => f.schluessel === '1_advent' && f.name === '1. Advent'))
    // Aufräumen: statische Namen wiederherstellen (andere Tests lesen sie).
    setzeFeiertagskatalog([
        { schluessel: 'karfreitag', name: 'Karfreitag', art: 'oster' },
    ])
    FEIERTAGE.splice(FEIERTAGE.findIndex((f) => f.schluessel === 'neuer_tag'), 1)
    assert.equal(FEIERTAGE.find((f) => f.schluessel === 'karfreitag').name, 'Karfreitag')
})

test('W3: leere oder unsinnige Antwort laesst den Katalog unberuehrt', () => {
    const vorher = FEIERTAGE.map((f) => f.name).join('|')
    setzeFeiertagskatalog(null)
    setzeFeiertagskatalog([])
    setzeFeiertagskatalog([{ schluessel: '', name: 'x' }, { name: 'ohne Kennung' }])
    assert.equal(FEIERTAGE.map((f) => f.name).join('|'), vorher)
})

test('W3: Genau ein Aufrufer ruft feiertage_holen, und er ist kein Editor', async () => {
    // REST-1 (2): Der EINE Aufrufer ist `katalogSichern()` in usePlanrahmen;
    // die Seiten stossen nur diesen an (Uebersicht, Planseite, Stammdaten,
    // Meine Dienste, Einrichten, Editor).
    const zentral = await quelle('../src/diakonos/composables/usePlanrahmen.js')
    const start = zentral.indexOf('export function katalogSichern')
    assert.ok(start > 0, 'katalogSichern fehlt')
    assert.match(zentral.slice(start, start + 900), /feiertageHolen\(\)/)
    const text = await quelle('../src/diakonos/pages/planrahmen/Uebersicht.vue')
    assert.match(text, /katalogSichern/, 'Uebersicht ruft feiertage_holen nicht (ueber katalogSichern)')
    for (const seite of ['components/planrahmen/PrTermineEditor.vue']) {
        const editor = await quelle(`../src/diakonos/${seite}`)
        assert.doesNotMatch(editor, /feiertageHolen/, 'der Editor holt den Katalog nie selbst')
    }
})

// ── K1 / K2 / K3 ───────────────────────────────────────────────────────────

test('K2: es heisst „Zulassung“, nicht „auf Zulassen“', async () => {
    const kart = await quelle('../src/diakonos/components/WartendeKontenKarte.vue')
    assert.doesNotMatch(kart, /auf Zulassen/i)
    assert.match(kart, /auf Zulassung/)
})

test('K3: die Nummernspalte wird nur bei {nr} in der Formatvorlage verdeckt', async () => {
    const ablauf = await quelle('../src/diakonos/components/planrahmen/PrAblauf.vue')
    assert.match(ablauf, /function nrVerdeckt\(/, 'nrVerdeckt fehlt')
    assert.match(ablauf, /format\.includes\('\{nr\}'\)/,
        'die Formatvorlage wird nicht auf {nr} geprüft')
    assert.match(ablauf, /pr-ablauf-nr--verdeckt/, 'die Klasse fehlt')
    // Die pauschale Ausblendung per CSS darf es nicht mehr geben.
    assert.doesNotMatch(ablauf, /\.pr-ablauf--programm \.pr-ablauf-nr \{[^}]*display:\s*none/)
})

test('K1: der Glossar-Waechter sieht Einwort-Toasts', async () => {
    const waechter = await quelle('./p3-1b-glossar-waechter.test.mjs')
    assert.match(waechter, /ANZEIGE_FUNKTION/, 'Einwort-Toast-Erkennung fehlt')
    assert.match(waechter, /showToast/, 'showToast wird nicht erkannt')
})

test('K1: „Genehmigt“ steht in den verbotenen Begriffen', async () => {
    const { BEGRIFFE } = await import('../src/diakonos/components/ui/begriffe.mjs')
    const verboten = Object.values(BEGRIFFE).flatMap((d) => d.verboten)
    assert.ok(verboten.includes('Genehmigt'), 'Glossar verbietet „Genehmigt“ nicht')
})
