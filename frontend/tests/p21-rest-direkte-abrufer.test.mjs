/**
 * OP-UI-1 (Rest): zentrale Sitzungs-/Fehlerprüfung auch fuer die
 * eigenstaendigen Bundles (organigramm/registrierung/gast).
 *
 * Vorher warf `organigramm/App.vue` bei jeder Nicht-ok-Antwort
 * `new Error(res.status)` — die Person sah nur „403" und hielt es fuer
 * entzogene Rechte (genau der Befund OP-UI-1). Diese Tests halten die
 * gemeinsame Regel und die Aufrufstelle fest.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import {
    istSitzungsAbbruch,
    antwortPruefen,
    fehlerText,
    SitzungsFehler,
    anmeldeZiel,
    ALLGEMEINER_FEHLERTEXT,
} from '../src/shared/sitzung-pruefen.js'

function antwort(status, body, { json = true } = {}) {
    return {
        ok: status >= 200 && status < 300,
        status,
        text: async () => (body === undefined ? '' : (json ? JSON.stringify(body) : String(body))),
    }
}

test('Sitzungsabbruch: 401 und 419 und CSRF-Ablauf (417) werden erkannt', () => {
    assert.equal(istSitzungsAbbruch(401, {}), true)
    assert.equal(istSitzungsAbbruch(419, {}), true)
    assert.equal(istSitzungsAbbruch(417, { exc_type: 'CSRFTokenError' }), true)
    // Ein echtes Rechteproblem ist KEIN Sitzungsabbruch.
    assert.equal(istSitzungsAbbruch(403, {}), false)
    // Ein anderer 417 (z. B. Validierungsfehler) ebenso wenig.
    assert.equal(istSitzungsAbbruch(417, { exc_type: 'ValidationError' }), false)
})

test('401 fuehrt zur Anmeldemaske und wirft SitzungsFehler', async () => {
    const ziele = []
    const original = globalThis.location
    globalThis.location = {
        pathname: '/diakonos', search: '', hash: '#/gruppen/organigramm',
        assign(ziel) { ziele.push(ziel) },
    }
    try {
        await assert.rejects(
            () => antwortPruefen(antwort(401, { exc_type: 'SessionExpired' })),
            (e) => e instanceof SitzungsFehler && e.sitzung === true,
        )
        assert.equal(ziele.length, 1)
        // Der Hash bleibt erhalten — Rücksprung an dieselbe Stelle.
        assert.match(ziele[0], /^\/login\?redirect-to=/)
        assert.ok(decodeURIComponent(ziele[0]).includes('#/gruppen/organigramm'))
    } finally {
        globalThis.location = original
    }
})

test('403 bleibt ein sichtbarer Fachfehler ohne Umleitung', async () => {
    const original = globalThis.location
    let umgeleitet = false
    globalThis.location = { pathname: '/diakonos', search: '', hash: '', assign() { umgeleitet = true } }
    try {
        await assert.rejects(
            () => antwortPruefen(antwort(403, { message: 'Dafür fehlt dir die Berechtigung.' })),
            (e) => !(e instanceof SitzungsFehler) && e.status === 403 && /Berechtigung/.test(e.message),
        )
        assert.equal(umgeleitet, false)
    } finally {
        globalThis.location = original
    }
})

test('Nicht-JSON-Antwort (Proxy 500) ergibt verstaendlichen Text statt Parse-Fehler', async () => {
    await assert.rejects(
        () => antwortPruefen(antwort(500, 'Internal Server Error', { json: false })),
        (e) => !/Unexpected token/.test(e.message),
    )
    assert.equal(fehlerText({}, 500), 'Serverfehler (HTTP 500)')
    assert.equal(fehlerText({ message: 'Fehler' }, 502), 'Serverfehler (HTTP 502)')
    assert.equal(fehlerText(null, 0), ALLGEMEINER_FEHLERTEXT)
})

test('anmeldeZiel haengt den Hash an das Rücksprungziel', () => {
    const original = globalThis.location
    globalThis.location = { pathname: '/diakonos', search: '?x=1', hash: '#/gruppe/42' }
    try {
        assert.equal(anmeldeZiel(), '/login?redirect-to=' + encodeURIComponent('/diakonos?x=1#/gruppe/42'))
    } finally {
        globalThis.location = original
    }
})

test('Organigramm nutzt die zentrale Pruefung (keine rohe Statusmeldung mehr)', () => {
    const quelle = readFileSync(new URL('../src/organigramm/App.vue', import.meta.url), 'utf8')
    assert.ok(quelle.includes("from '../shared/sitzung-pruefen.js'"), 'Import fehlt')
    assert.ok(quelle.includes('await antwortPruefen(res)'), 'antwortPruefen nicht verwendet')
    assert.ok(!quelle.includes('throw new Error(res.status)'), 'rohe Statusmeldung noch vorhanden')
})
