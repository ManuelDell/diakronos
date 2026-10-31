import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

// Beide API-Wege müssen denselben zentralen Ablauf auslösen.
let apiQuelle = await readFile(new URL('./useApi.js', import.meta.url), 'utf8')
apiQuelle = apiQuelle.replace("import { useImpersonation } from './useImpersonation.js'", "const useImpersonation = () => ({isActive:{value:false}})")
apiQuelle = apiQuelle.replace("import { sitzungBeendet } from './useSitzungsablauf.js'", "const sitzungBeendet = () => { globalThis.__ablauf = true }")
// WEB-8c (R4): abgelegter Sitzungsfehler (eigene Datei ohne Importe) — Attrappe.
apiQuelle = apiQuelle.replace("import { sitzungsFehlerMerken } from './sitzungsstand.js'", "const sitzungsFehlerMerken = (f) => f")
// OP-UI-1 (Rest): die gemeinsamen Regeln liegen jetzt in shared/sitzung-pruefen.js.
// Für den Inline-Test werden sie lokal nachgebildet (gleiche Bedingung).
apiQuelle = apiQuelle.replace(
    "import { istSitzungsAbbruch } from '../../shared/sitzung-pruefen.js'",
    "const istSitzungsAbbruch = (status, data) => [401, 419].includes(status) || (status === 417 && data?.exc_type === 'CSRFTokenError')")
// WEB-5b: die Praefix-Hilfsdatei hat im data:-Modul keinen Basispfad — sie hat
// keinen eigenen Zustand; ohne Praefix liefert sie die alte Adresse
// (geprueft in tests/web5b-basis.test.mjs).
apiQuelle = apiQuelle.replace("import { apiUrl } from '../../shared/basis.js'",
    "const apiUrl = (methode) => '/api/method/' + methode")
  // WEB-8b: die CSRF-Heilung liegt in einer eigenen Datei (shared/csrf-heilung.js).
  // Im data:-Modul wird sie inline nachgebildet — hier geht es um die FEHLERFORM
  // von apiCall, nicht um die Heilung; die prueft tests/web8b-csrf-heilung.test.mjs
  // mit dem echten Modul. `datenVon` liest wie in der Vorlage (tolerant).
  .replace("import { istCsrfAblehnung, heileOderMelde, datenVon, SITZUNG_HINWEIS } from '../../shared/csrf-heilung.js'",
    "const istCsrfAblehnung = (res, data) => res?.status === 417 && String(data?.exc_type || '') === 'CSRFTokenError';"
    + " const heileOderMelde = async ({ anfrage }) => { const t = await frischesToken(); if (t) window.__DIakonosBOOT.csrf_token = t; const res = await anfrage(); return { res, data: await datenVon(res) } };"
    + " async function frischesToken() { try { const r = await fetch('/api/method/diakronos.diakonos.api.session.sitzung_status'); if (!r.ok) return ''; const d = await r.json(); return d?.message?.csrf_token || '' } catch { return '' } }"
    + " const SITZUNG_HINWEIS = 'Sitzung abgelaufen — bitte neu anmelden.';"
    + " async function datenVon(res) { if (res?.dkDaten !== undefined) return res.dkDaten; let text = ''; try { text = await res.text() } catch { return { message: `Serverfehler (HTTP ${res?.status})` } } if (!text) return { message: `Serverfehler (HTTP ${res?.status})` }; try { return JSON.parse(text) } catch { return { message: `Serverfehler (HTTP ${res?.status})` } } }")
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

test('WEB-8b: CSRF-Ablauf wird geheilt, Fachfehler (417 ValidationError) NICHT', async () => {
    // Vorher galt: „Keine automatische Schreibwiederholung". WEB-8b dreht das
    // BEWUSST für GENAU den CSRF-Fall: der Server hat die Methode noch nicht
    // ausgeführt (Prüfung in der CsrfMiddleware davor), deshalb ist eine
    // einmalige Wiederholung mit frischem Token sicher (C3). Fachfehler
    // behalten die alte Regel — keine Wiederholung.
    globalThis.window = { __DIakonosBOOT: { csrf_token: 'alt' } }
    for (const fn of [api.apiCall, api.apiGet]) {
        // 417 ValidationError: keine Wiederholung, kein Token-Wechsel.
        globalThis.window = { __DIakonosBOOT: { csrf_token: 'alt' } }
        globalThis.__ablauf = false
        let fachAnfragen = 0
        globalThis.fetch = async () => {
            fachAnfragen++
            return { ok: false, status: 417, text: async () => JSON.stringify({ exc_type: 'ValidationError', message: 'Abgelehnt' }) }
        }
        await assert.rejects(fn('test'), e => e.status === 417)
        assert.equal(globalThis.__ablauf, false, 'Fachfehler ist kein Sitzungsende')
        assert.equal(fachAnfragen, 1, 'Fachfehler werden nicht wiederholt')
        assert.equal(window.__DIakonosBOOT.csrf_token, 'alt', 'kein Token-Wechsel ohne CSRF-Ablauf')

        // 417 CSRFTokenError: Token-Abruf + genau eine Wiederholung. Hier
        // schlägt die Wiederholung ebenfalls fehl -> Weiterleitung/Neuladen
        // (in dieser Attrappe ohne location: nur der Fehler zählt).
        globalThis.window = { __DIakonosBOOT: { csrf_token: 'alt' } }
        globalThis.__ablauf = false
        const aufrufe = []
        globalThis.fetch = async (url) => {
            aufrufe.push(String(url))
            if (String(url).includes('sitzung_status')) {
                // Der Token-Endpunkt liefert ein frisches Token (sonst gäbe es
                // keine sinnvolle Wiederholung — das prüft der eigene Test).
                const koerper = { message: { user: 'anna', csrf_token: 'neu' } }
                return { ok: true, status: 200, json: async () => koerper, text: async () => JSON.stringify(koerper) }
            }
            return { ok: false, status: 417, text: async () => JSON.stringify({ exc_type: 'CSRFTokenError', message: 'Abgelehnt' }) }
        }
        await assert.rejects(fn('test'))
        assert.equal(aufrufe.length, 3, 'Original + Token-Versuch + genau eine Wiederholung')
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
// WEB-8c (R4): der abgelegte Sitzungsfehler (eigene Datei ohne Importe) —
// hier eine Attrappe, damit kein Dateizugriff im data:-Modul noetig ist.
quelle = quelle.replace(/import \{ sitzungsFehlerLesen, sitzungsFehlerVergessen \} from '\.\/sitzungsstand\.js'/,
    'const sitzungsFehlerLesen = () => globalThis.__stand || null\nconst sitzungsFehlerVergessen = () => { globalThis.__stand = null }')
// WEB-8d (M2): die Anzeige hoert jetzt auf den Stand (`watch`) statt zu fragen.
quelle = quelle.replace(/import \{ sitzungsFehlerLesen, sitzungsFehlerVergessen, sitzungsFehlerBeobachten \} from '\.\/sitzungsstand\.js'/,
    'const sitzungsFehlerLesen = () => globalThis.__stand || null\n'
    + 'const sitzungsFehlerVergessen = () => { globalThis.__stand = null }\n'
    + 'const sitzungsFehlerBeobachten = (rueckmeldung, { sofort = false } = {}) => { if (sofort) rueckmeldung(globalThis.__stand || null); globalThis.__beobachter = rueckmeldung; return () => { globalThis.__beobachter = null } }')
// WEB-5b: Praefix-Hilfsdatei ebenfalls inline (ohne Praefix = alte Adresse);
// das Verhalten selbst prueft tests/web5b-basis.test.mjs.
quelle = quelle.replace("import { anmeldeUrl, apiUrl } from '../../shared/basis.js'",
    "const apiUrl = (m) => '/api/method/' + m\nconst anmeldeUrl = (z) => '/login?redirect-to=' + encodeURIComponent(z)")
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
