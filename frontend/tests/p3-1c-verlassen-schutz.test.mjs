import assert from 'node:assert/strict'
import { test } from 'node:test'
import { readFile } from 'node:fs/promises'

/**
 * UXD-R29: Rückfrage bei Browser-Zurück / Seitenwechsel in Formularen
 * (Mitglied, Profil, Gruppe).
 *
 * Vorher gab es nur `useFormularSchutz` für das Schließen EINES Fensters —
 * der ROUTENWECHSEL verwarf ungespeicherte Eingaben still. Hier wird die
 * neue Composable gegen einen nachgebauten Router geprueft (`onBeforeEach`
 * liefert die Abmeldefunktion, Guards duerfen Promises liefern).
 */

const quellen = {
    router: await readFile(new URL('../src/diakonos/router.js', import.meta.url), 'utf8'),
    schutz: await readFile(new URL('../src/diakonos/composables/useVerlassenSchutz.js', import.meta.url), 'utf8'),
    formular: await readFile(new URL('../src/diakonos/composables/useFormularSchutz.js', import.meta.url), 'utf8'),
}

test('useVerlassenSchutz haengt sich beim Mounten ein und beim Unmounten wieder ab', () => {
    // Die Composable muss `onMounted`/`onBeforeUnmount` benutzen und die von
    // `onBeforeEach` gelieferte Abmeldefunktion aufrufen — sonst bliebe der
    // Guard einer verlassenen Seite fuer immer aktiv.
    assert.match(quellen.schutz, /onMounted\(/u)
    assert.match(quellen.schutz, /onBeforeUnmount\(/u)
    assert.match(quellen.schutz, /onBeforeEach\(/u)
    assert.match(quellen.schutz, /abmelden\(\)/u)
})

test('useVerlassenSchutz fragt ueber darfSchliessen und laesst true durch', async () => {
    const modul = await ladeComposable(async () => true)
    assert.equal(await modul.guard(), true)
    assert.equal(modul.aufrufe.darfSchliessen, 1)
})

test('useVerlassenSchutz bricht den Wechsel bei false ab', async () => {
    // „Weiter bearbeiten“ -> Router darf die Seite NICHT verlassen.
    const modul = await ladeComposable(async () => false)
    assert.equal(await modul.guard(), false)
})

test('useVerlassenSchutz ohne Schutz fragt nicht und laesst durch', async () => {
    const modul = await ladeComposable(null)
    assert.equal(await modul.guard(), true)
})

test('Formularschutz fragt nur bei tatsaechlicher Aenderung', async () => {
    let gefragt = 0
    // `bestaetigen` ist Default-Parameter und wird beim Laden gebunden —
    // der Ersatz muss also VOR dem Import stehen.
    globalThis.__bestaetigen = async () => { gefragt += 1; return true }
    const form = { name: 'Alt' }
    const schutz = await ladeFormularSchutz(() => form)
    assert.equal(await schutz.darfSchliessen(), true, 'unveraendert -> kein Dialog')
    assert.equal(gefragt, 0)
    form.name = 'Neu'
    assert.equal(await schutz.darfSchliessen(), true)
    assert.equal(gefragt, 1, 'geaendert -> genau eine Rueckfrage')
    // Nach dem Merken ist es wieder sauber (das passiert nach dem Speichern).
    schutz.merken()
    assert.equal(await schutz.darfSchliessen(), true)
    assert.equal(gefragt, 1, 'nach merken keine zweite Rueckfrage')
})

test('Formularschutz blockt, solange gespeichert wird', async () => {
    globalThis.__bestaetigen = async () => true
    let speichert = true
    const schutz = await ladeFormularSchutz(() => ({ a: 1 }), () => speichert)
    assert.equal(await schutz.darfSchliessen(), false)
})

test('die drei Formularseiten haengen den Schutz wirklich ein', async () => {
    // Ohne Einbau bliebe die Composable toter Code — genau das war UXD-R29.
    for (const seite of ['MitgliedDetail', 'Profile', 'GruppeDetail']) {
        const quelle = await readFile(new URL(`../src/diakonos/pages/${seite}.vue`, import.meta.url), 'utf8')
        assert.match(quelle, /useVerlassenSchutz\(/u, `${seite}: useVerlassenSchutz fehlt`)
        assert.match(quelle, /useFormularSchutz\(/u, `${seite}: useFormularSchutz fehlt`)
        assert.match(quelle, /\.merken\(\)/u, `${seite}: Grundstand wird nicht gemerkt`)
    }
})

/** Baut die Formular-Composable mit ersetztem Bestätigungsdialog nach. */
async function ladeFormularSchutz(lesen, beschaeftigt) {
    const quelle = quellen.formular.replace(
        "import { bestaetigen } from './useBestaetigen.js'",
        'const bestaetigen = globalThis.__bestaetigen',
    )
    // Eigene Modul-URL je Fall (Import-Cache), damit der Ersatz greift.
    const m = await import('data:text/javascript;base64,' + Buffer.from(
        quelle + `\n// ${Math.random()}`).toString('base64'))
    return m.useFormularSchutz(lesen, beschaeftigt)
}

/** Baut die Composable mit nachgebautem Vue-Lebenszyklus und Router nach. */
async function ladeComposable(darfSchliessen) {
    const aufrufe = { darfSchliessen: 0, eingehaengt: 0, abgemeldet: 0 }
    const lebenszyklus = { mounted: [], unmount: [] }
    globalThis.__vue = {
        onMounted: (fn) => lebenszyklus.mounted.push(fn),
        onBeforeUnmount: (fn) => lebenszyklus.unmount.push(fn),
    }
    globalThis.__router = {
        onBeforeEach: (fn) => {
            aufrufe.eingehaengt += 1
            globalThis.__guard = fn
            return () => { aufrufe.abgemeldet += 1 }
        },
    }
    let quelle = quellen.schutz
        .replace("import { onMounted, onBeforeUnmount } from 'vue'", 'const { onMounted, onBeforeUnmount } = globalThis.__vue')
        .replace("import { onBeforeEach } from '../router.js'", 'const { onBeforeEach } = globalThis.__router')
    // Eigene Modul-URL je Fall: sonst liefert der Import-Cache die Instanz des
    // ersten Falls mit dessen (schon abgearbeiteten) Lebenszyklus-Listen.
    const m = await import('data:text/javascript;base64,' + Buffer.from(
        quelle + `\n// ${Math.random()}`).toString('base64'))
    const schutz = darfSchliessen
        ? { darfSchliessen: async () => { aufrufe.darfSchliessen += 1; return darfSchliessen() } }
        : null
    m.useVerlassenSchutz(schutz)
    // Mounten
    assert.equal(aufrufe.eingehaengt, 0, 'vor dem Mounten noch kein Guard')
    for (const fn of lebenszyklus.mounted) fn()
    assert.equal(aufrufe.eingehaengt, 1, 'beim Mounten genau ein Guard')
    return {
        aufrufe,
        guard: () => globalThis.__guard(),
        unmount: () => { for (const fn of lebenszyklus.unmount) fn() },
    }
}
