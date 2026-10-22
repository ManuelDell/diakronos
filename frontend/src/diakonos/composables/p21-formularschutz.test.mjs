import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { bestaetigen, bestaetigung, bestaetigungAntwort } from './useBestaetigen.js'

test('Gleichzeitige Rückfragen überschreiben einander nicht; Esc/Schließen verwirft nie', async () => {
    const erste = bestaetigen({ titel: 'Erste Frage', aktion: 'Verwerfen' })
    const zweite = bestaetigen({ titel: 'Zweite Frage', aktion: 'Löschen' })
    assert.equal(bestaetigung.value.titel, 'Erste Frage')
    bestaetigungAntwort(false)
    assert.equal(await erste, false)
    await Promise.resolve()
    assert.equal(bestaetigung.value.titel, 'Zweite Frage')
    bestaetigungAntwort(true)
    assert.equal(await zweite, true)
    await Promise.resolve()
    assert.equal(bestaetigung.value, null)
})

let quelle = await readFile(new URL('./useFormularSchutz.js', import.meta.url), 'utf8')
quelle = quelle.replace("import { bestaetigen } from './useBestaetigen.js'", 'const bestaetigen = () => { throw new Error("Dialog nicht bereit") }')
const { useFormularSchutz } = await import('data:text/javascript;base64,' + Buffer.from(quelle).toString('base64'))

for (const ausloeser of ['Esc', 'Schließen', 'Abbrechen']) {
    test(`OP-UI-2: ${ausloeser} erhält Eingaben bei Abbruch und verwirft nur bestätigt`, async () => {
        const form = { titel: '', inhalt: '', ressourcen: [] }
        let antwort = false
        let fragen = 0
        let speichern = false
        const schutz = useFormularSchutz(() => form, () => speichern, async frage => {
            fragen++
            assert.equal(frage.aktion, 'Verwerfen')
            return antwort
        })
        schutz.merken()
        assert.equal(await schutz.darfSchliessen(), true)
        assert.equal(fragen, 0)
        form.titel = 'Nicht verlieren'
        form.inhalt = 'Langer Text'
        form.ressourcen.push({ id: 'Raum' })
        const vorher = JSON.stringify(form)
        assert.equal(await schutz.darfSchliessen(), false)
        assert.equal(JSON.stringify(form), vorher)
        antwort = true
        assert.equal(await schutz.darfSchliessen(), true)
        speichern = true
        assert.equal(await schutz.darfSchliessen(), false)
        speichern = false
        schutz.merken()
        assert.equal(await schutz.darfSchliessen(), true, 'Nach erfolgreichem Speichern kein Verwerfen-Dialog')
    })
}

test('Wiki, Beitrag, Buchung und Kalender verwenden denselben Schutz an allen Schließwegen', async () => {
    for (const [datei, handler] of [
        ['pages/Wiki.vue', 'editorSchliessen'], ['pages/Beitraege.vue', 'editorSchliessen'],
        ['pages/Ressourcen.vue', 'buchungSchliessen'],
        ['components/kronos/KronosEventCreate.vue', 'close'], ['components/kronos/KronosEventEdit.vue', 'close'],
    ]) {
        const text = await readFile(new URL('../' + datei, import.meta.url), 'utf8')
        assert.match(text, /useFormularSchutz/, datei)
        assert.match(text, new RegExp(`async function ${handler}\\(`), datei)
        assert.match(text, /darfSchliessen\(\)/, datei)
        if (datei.startsWith('pages/')) {
            assert.match(text, new RegExp(`@click="${handler}"[^>]*>Abbrechen`), datei)
        }
    }
})
