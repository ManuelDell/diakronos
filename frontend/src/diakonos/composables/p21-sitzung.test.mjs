import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

// Beide API-Wege müssen denselben zentralen Ablauf auslösen.
let apiQuelle = await readFile(new URL('./useApi.js', import.meta.url), 'utf8')
apiQuelle = apiQuelle.replace("import { useImpersonation } from './useImpersonation.js'", "const useImpersonation = () => ({isActive:{value:false}})")
apiQuelle = apiQuelle.replace("import { sitzungBeendet } from './useSitzungsablauf.js'", "const sitzungBeendet = () => { globalThis.__ablauf = true }")
// OP-UI-1 (Rest): die gemeinsamen Regeln liegen jetzt in shared/sitzung-pruefen.js.
// Für den Inline-Test werden sie lokal nachgebildet (gleiche Bedingung).
apiQuelle = apiQuelle.replace(
    "import { istSitzungsAbbruch } from '../../shared/sitzung-pruefen.js'",
    "const istSitzungsAbbruch = (status, data) => [401, 419].includes(status) || (status === 417 && data?.exc_type === 'CSRFTokenError')")
const api = await import('data:text/javascript;base64,' + Buffer.from(apiQuelle).toString('base64'))
test('OP-UI-1: POST und GET zeigen den zentralen Sitzungsablauf', async () => {
    globalThis.window = { __DIakonosBOOT: { csrf_token: 'token' } }
    for (const fn of [api.apiCall, api.apiGet]) {
        globalThis.__ablauf = false
        globalThis.fetch = async () => ({ok:false, status:401, text:async()=>JSON.stringify({message:'Bitte neu anmelden'})})
        await assert.rejects(fn('test'), e => e.status === 401)
        assert.equal(globalThis.__ablauf, true)
    }
})

test('Nur 417 mit CSRFTokenError bietet die kontrollierte Sitzungsprüfung an', async () => {
    globalThis.window = { __DIakonosBOOT: { csrf_token: 'alt' } }
    for (const fn of [api.apiCall, api.apiGet]) {
        for (const exc_type of ['CSRFTokenError', 'ValidationError']) {
            globalThis.__ablauf = false
            let anfragen = 0
            globalThis.fetch = async () => {
                anfragen++
                return { ok: false, status: 417, text: async () => JSON.stringify({ exc_type, message: 'Abgelehnt' }) }
            }
            await assert.rejects(fn('test'), e => e.status === 417)
            assert.equal(globalThis.__ablauf, exc_type === 'CSRFTokenError')
            assert.equal(anfragen, 1, 'Keine automatische Schreibwiederholung')
            assert.equal(window.__DIakonosBOOT.csrf_token, 'alt', 'Kein ungeprüfter CSRF-Wechsel')
        }
    }
})

test('Uploads: Sitzungswechsel wird erkannt, Fachfehler bleibt Fachfehler, Nicht-JSON wird lesbar', async () => {
    for (const [status, exc_type, erwartet] of [[401, 'SessionExpired', true], [417, 'CSRFTokenError', true], [417, 'ValidationError', false]]) {
        globalThis.__ablauf = false
        const res = { ok: false, status, text: async () => JSON.stringify({ message: 'Abgelehnt', exc_type }) }
        await assert.rejects(api.apiAntwortPruefen(res), e => e.status === status && e.message === 'Abgelehnt')
        assert.equal(globalThis.__ablauf, erwartet)
    }
    globalThis.__ablauf = false
    const legacy = await api.apiAntwortPruefen({ok:false, status:417, text:async()=>JSON.stringify({message:'Bitte das Ende prüfen.', exc_type:'CSRFTokenError', meldungen:[{pfad:'/ende'}]})}, {fehlerWerfen:false})
    assert.equal(legacy.message, 'Bitte das Ende prüfen.', 'Legacy-Fehleranzeige verliert den Fachtext nicht')
    assert.equal(legacy.meldungen[0].pfad, '/ende')
    assert.equal(globalThis.__ablauf, true, 'Auch ohne Exception wird die Sitzung geprüft')
    await assert.rejects(api.apiAntwortPruefen({ok:false, status:502, text:async()=>'<html>Bad Gateway</html>'}), /Serverfehler/)
    assert.deepEqual(await api.apiAntwortPruefen({ok:true, status:200, text:async()=>'{"message":{"file_url":"/files/bild.jpg"}}'}), {message:{file_url:'/files/bild.jpg'}})
})

let leert = 0
let quelle = await readFile(new URL('./useSitzungsablauf.js', import.meta.url), 'utf8')
quelle = quelle.replace("import { ref } from 'vue'", 'const ref = value => ({value})')
quelle = quelle.replace("import { cacheLeeren } from './usePlanrahmenCache.js'", 'const cacheLeeren = () => globalThis.__leeren()')
globalThis.__leeren = () => leert++
const mod = await import('data:text/javascript;base64,' + Buffer.from(quelle).toString('base64'))
globalThis.window = { location: { pathname: '/diakonos', search: '', hash: '#/wiki' }, __DIakonosBOOT: { user: 'konto', csrf_token: 'alt' } }

test('Sitzungsablauf leert Cache, bleibt im Tab und erhält Rücksprung', () => {
    mod.sitzungBeendet()
    assert.equal(leert, 1)
    assert.equal(mod.sitzungAbgelaufen.value, true)
    assert.equal(mod.anmeldeAdresse(), '/login?redirect-to=%2Fdiakonos%23%2Fwiki')
})
test('Neuanmeldung mit anderem Konto gibt alte Formulare nicht frei', async () => {
    globalThis.fetch = async () => ({ ok: true, json: async () => ({ message: { user: 'fremd', csrf_token: 'neu' } }) })
    assert.equal(await mod.sitzungFortsetzen(), false)
    assert.equal(mod.sitzungAbgelaufen.value, true)
    assert.equal(window.__DIakonosBOOT.csrf_token, 'alt')
})
test('Gleiches Konto aktualisiert CSRF ohne Schreibaktion zu wiederholen', async () => {
    const aufrufe = []
    let metaToken = 'alt'
    globalThis.document = { querySelector: selector => {
        assert.equal(selector, 'meta[name="csrf-token"]')
        return { setAttribute: (name, value) => { assert.equal(name, 'content'); metaToken = value } }
    } }
    globalThis.fetch = async (url, opt) => { aufrufe.push({ url, opt }); return { ok: true, json: async () => ({ message: { user: 'konto', csrf_token: 'neu' } }) } }
    assert.equal(await mod.sitzungFortsetzen(), true)
    assert.equal(mod.sitzungAbgelaufen.value, false)
    assert.equal(window.__DIakonosBOOT.csrf_token, 'neu')
    assert.equal(metaToken, 'neu', 'Direkte Kalender-Aufrufer erhalten denselben geprüften Token')
    assert.equal(aufrufe.length, 1)
    assert.equal(aufrufe[0].opt.method, undefined, 'Nur lesender GET, keine automatische Wiederholung')
})
