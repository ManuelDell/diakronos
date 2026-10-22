import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { pflichtFehler, erstesFehlerfeld, buchungsFehler } from './formularPruefung.mjs'

test('OP-UI-5: Pflichtfehler nennen jedes Feld, Fokus geht ins erste', () => {
    const fehler = pflichtFehler([['titel', ' ', 'einen Titel'], ['von', '', 'den Beginn'], ['zahl', 0, 'eine Zahl']])
    assert.deepEqual(fehler, { titel: 'Bitte einen Titel angeben.', von: 'Bitte den Beginn angeben.' })
    let fokus = ''
    globalThis.document = { getElementById: id => ({ focus: () => { fokus = id } }) }
    globalThis.requestAnimationFrame = fn => fn()
    erstesFehlerfeld(fehler)
    assert.equal(fokus, 'titel')
})

test('Buchung nennt fehlende Angaben und ein ungültiges Ende', () => {
    assert.equal(Object.keys(buchungsFehler({})).length, 6)
    const form = { resourceId: 'raum', date: '2026-10-20', startTime: '10:00', endDate: '2026-10-20', endTime: '09:00', purpose: 'Probe' }
    assert.match(buchungsFehler(form)['rs-bis-zeit'], /nach dem Beginn/)
    form.endTime = '11:00'
    assert.deepEqual(buchungsFehler(form), {})
})

test('OP-UI-5: Plan und Abwesenheit erlauben Prüfklick und zeigen Feldfehler', async () => {
    for (const file of ['Uebersicht', 'MeineDienste']) {
        const code = await readFile(new URL('../pages/planrahmen/' + file + '.vue', import.meta.url), 'utf8')
        assert.doesNotMatch(code, /:disabled="[^"\n]*!\w*PflichtenOk/)
        assert.match(code, /pflichtFehler\(\[/)
        assert.match(code, /erstesFehlerfeld\(feldFehler.value\)/)
        assert.match(code, /Ende darf nicht vor dem Beginn/)
    }
})
