/**
 * REST-1 (2) — Anzeigenamen beim DIREKTAUFRUF (Befund R-P3-1d W-a).
 *
 * Der Kochbuch-Katalog (Quelle der Anzeigenamen für gespeicherte Vorlagen ohne
 * eigenes `anzeigenamen`) wurde nur in `Uebersicht.vue` geladen. Wer direkt auf
 * eine Planseite, die Druckansicht, die Stammdaten, den Editor oder „Meine
 * Dienste“ kam (geteilter Link, Neuladen, Lesezeichen), sah weiter „Floete“.
 *
 * Dieser Test fährt das echte `usePlanrahmen.js` (inkl. `useApi.js`) mit einem
 * fetch-Ersatz und prüft:
 *   - JEDER Direktaufruf löst den Katalog aus,
 *   - der Katalog wird je Sitzung nur EINMAL geholt (K-a),
 *   - danach löst `wertAnzeige` die Kennung auf den Anzeigenamen auf.
 *
 * Je Einstiegspunkt wird das Modul mit eigener Modul-URL geladen — so hat jeder
 * Fall seinen eigenen (frischen) Einmal-Cache und die Fälle beeinflussen sich
 * nicht.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'

class Store {
    #m = new Map()
    get length() { return this.#m.size }
    key(i) { return [...this.#m.keys()][i] ?? null }
    getItem(k) { return this.#m.has(k) ? this.#m.get(k) : null }
    setItem(k, v) { this.#m.set(String(k), String(v)) }
    removeItem(k) { this.#m.delete(String(k)) }
    clear() { this.#m.clear() }
}

globalThis.window = {
    __DIakonosBOOT: { csrf_token: 'token', user_email: 'test@example.org' },
    localStorage: new Store(),
    location: { hash: '#/planrahmen', pathname: '/diakonos', search: '' },
    addEventListener() {},
    removeEventListener() {},
}

const KATALOG = {
    felder: [
        { id: 'instrument', typ: 'auswahl', werte: ['Floete'], anzeigenamen: { Floete: 'Flöte' } },
    ],
    merkmale: {},
    parameter: [],
}

/** fetch-Ersatz: sammelt die Methodennamen und antwortet wie der Server. */
let aufrufe = []
const vorlagen = ['chorplan']

globalThis.fetch = async (url) => {
    const methode = String(url).split('/api/method/')[1] || ''
    aufrufe.push(methode)
    const kurz = methode.replace('diakronos.planrahmen.api.', '')
    let message = {}
    if (kurz === 'kochbuch_liste') message = vorlagen.slice()
    else if (kurz === 'kochbuch_holen') message = KATALOG
    else if (kurz === 'feiertage_holen') message = [{ schluessel: 'karfreitag', name: 'Karfreitag', art: 'fest' }]
    else if (kurz === 'plan_holen') message = { plan: { id: 'p1', titel: 'Chorplan' }, termine: [], eintraege: [] }
    else if (kurz === 'stammdaten_holen') message = { personen: [], gruppen: [] }
    else if (kurz === 'meine_dienste') message = []
    else if (kurz === 'plantypen_liste') message = []
    else if (kurz === 'plantyp_versionen_liste') message = []
    return {
        ok: true,
        status: 200,
        text: async () => JSON.stringify({ message }),
    }
}

const werte = await import('../src/diakonos/components/planrahmen/auswahlwerte.mjs')

let zaehler = 0
/** Frische Modulinstanz (eigener Einmal-Cache) je Fall. */
async function frischeApi() {
    zaehler += 1
    aufrufe = []
    werte.katalogLeeren()
    window.localStorage = new Store()
    const mod = await import(`../src/diakonos/composables/usePlanrahmen.js?rest1=${zaehler}`)
    return mod.usePlanrahmen()
}

function katalogAufrufe() {
    return aufrufe.filter((m) => m.endsWith('kochbuch_liste') || m.endsWith('kochbuch_holen'))
}

const EINSTIEGE = [
    ['Planseite (planHolen)', (api) => api.planHolen('p1')],
    ['Meine Dienste (meineDienste)', (api) => api.meineDienste()],
    ['Stammdaten (stammdatenHolen)', (api) => api.stammdatenHolen('chorplan')],
    ['Einrichten (plantypenListe)', (api) => api.plantypenListe()],
    ['Plantyp-Editor (plantypVersionenListe)', (api) => api.plantypVersionenListe('chorplan')],
]

for (const [name, aufruf] of EINSTIEGE) {
    test(`Direktaufruf ${name} laedt den Katalog`, async () => {
        const api = await frischeApi()
        await aufruf(api)
        assert.ok(katalogAufrufe().includes('diakronos.planrahmen.api.kochbuch_liste'),
            `${name} hat den Katalog nicht geladen`)
        assert.equal(werte.wertAnzeige({ id: 'instrument', werte: ['Floete'] }, 'Floete'), 'Flöte',
            'ohne Katalog bleibt die Kennung stehen („Floete“ statt „Flöte“)')
    })
}

test('der Katalog wird je Sitzung nur EINMAL geholt (K-a)', async () => {
    const api = await frischeApi()
    await api.planHolen('p1')
    const ersterSatz = katalogAufrufe().length
    assert.equal(ersterSatz, 2, 'erster Satz ist Liste + eine Vorlage')
    await api.planHolen('p2')
    await api.stammdatenHolen('chorplan')
    await api.meineDienste()
    await api.plantypenListe()
    assert.equal(katalogAufrufe().length, ersterSatz,
        'der Katalog wurde erneut geholt — kein Einmal-Cache')
})

test('ein Fehler im Katalog haelt die Planseite nicht auf und wird wiederholt', async () => {
    const api = await frischeApi()
    const echtesFetch = globalThis.fetch
    let fehlversuche = 0
    globalThis.fetch = async (url, optionen) => {
        const methode = String(url)
        if (methode.endsWith('kochbuch_liste')) {
            fehlversuche += 1
            return { ok: false, status: 500, text: async () => 'Internal Server Error' }
        }
        return echtesFetch(url, optionen)
    }
    try {
        const daten = await api.planHolen('p1')
        assert.equal(daten?.plan?.titel, 'Chorplan', 'die Planseite muss trotzdem laden')
        assert.equal(fehlversuche, 1)
        // Der Fehlschlag darf nicht endgueltig gemerkt sein: die naechste Seite
        // versucht es erneut (sonst blieben die Anzeigenamen fuer die ganze
        // Sitzung verloren).
        await api.meineDienste()
        assert.equal(fehlversuche, 2, 'der Katalog wurde nach dem Fehler nicht neu versucht')
    } finally {
        globalThis.fetch = echtesFetch
    }
})
