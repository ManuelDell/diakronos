/**
 * P2-1b: OP-UI-23 (Fenster-Grundverhalten) und UXD-R22 (leerer Titel/Name)
 * in den zuletzt noch offenen Fenstern und Formularen.
 *
 * Geprüft wird am Quelltext, weil die Fenster Vue-SFCs sind: Enter sendet
 * (<form @submit.prevent> + Absende-Knopf), Abbrechen ist `ghost`, der
 * Pflichtknopf ist nicht mehr gesperrt, und ein fehlender Titel/Name wird am
 * Feld benannt (DkField :error / role="alert"), nicht verschwiegen.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const lies = (pfad) => readFileSync(new URL('../src/diakonos/' + pfad, import.meta.url), 'utf8')

const FENSTER = [
    ['pages/Gruppen.vue', 'Neue Gruppe'],
    ['components/gruppen/OrganigrammAnsicht.vue', 'Gruppe verwalten'],
    ['pages/Wiki.vue', 'Wiki-Artikel'],
    ['pages/Beitraege.vue', 'Beitrag'],
    ['pages/planrahmen/Uebersicht.vue', 'Neuer Plan'],
    ['pages/planrahmen/PlantypEditor.vue', 'Neue Version'],
]

test('OP-UI-23: jedes Formularfenster hat <form @submit.prevent> (Enter sendet)', () => {
    for (const [datei, name] of FENSTER) {
        const code = lies(datei)
        assert.match(code, /@submit\.prevent/, `${name}: kein @submit.prevent`)
        assert.match(code, /<form[ >]/, `${name}: kein <form>-Element`)
    }
})

test('OP-UI-23: Abbrechen ist ghost statt secondary (S3.2)', () => {
    for (const [datei, name] of FENSTER) {
        const code = lies(datei)
        // Der Abbrechen-Knopf in der Fußzeile darf keine zweite Hauptfarbe sein.
        const treffer = code.match(/<DkButton[^>]*>Abbrechen</g) || []
        for (const knopf of treffer) {
            assert.match(knopf, /variant="ghost"/, `${name}: Abbrechen nicht ghost: ${knopf}`)
        }
    }
})

test('UXD-R22/OP-UI-5: leerer Titel/Name wird am Feld benannt, Knopf bleibt aktiv', () => {
    const gruppen = lies('pages/Gruppen.vue')
    assert.match(gruppen, /createFehler/, 'Gruppen: kein Feldfehler-Objekt')
    assert.match(gruppen, /:error="createFehler\.name"/, 'Gruppen: Name ohne :error')
    assert.doesNotMatch(gruppen, /:disabled="!createForm\.name\.trim\(\)/, 'Gruppen: Knopf noch gesperrt')

    const organigramm = lies('components/gruppen/OrganigrammAnsicht.vue')
    assert.match(organigramm, /:error="createFehler\.name"/, 'Organigramm: Name ohne :error')
    assert.match(organigramm, /:error="editFehler\.name"/, 'Organigramm: Bearbeiten ohne :error')

    const wiki = lies('pages/Wiki.vue')
    assert.match(wiki, /:error="editorFehler\.titel"/, 'Wiki: Titel ohne :error')

    const beitraege = lies('pages/Beitraege.vue')
    assert.match(beitraege, /:error="editorFehler\.titel"/, 'Beitrag: Titel ohne :error')
})

test('OP-UI-5: Planvorlage-Version benennt fehlende Pflichtangaben am Feld', () => {
    const code = lies('pages/planrahmen/PlantypEditor.vue')
    assert.match(code, /speichernFeldFehler/, 'kein Feldfehler-Objekt')
    assert.match(code, /role="alert"/, 'keine sichtbare Feldmeldung')
    assert.doesNotMatch(code, /:disabled="speichert \|\| !speichernPflichtenOk"/, 'Knopf noch gesperrt')
})
