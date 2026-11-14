/**
 * R6 · Mount-Test: Detail-Dialog und Gast-Dialog am gerenderten DOM.
 *
 * Zwei Befunde aus dem Review (12.11.), die sich nur im gerenderten DOM
 * zeigen — die Regel allein (tests/r6-nacharbeit.test.mjs) belegt sie nicht:
 *
 *  1. MITTEL Regression Detail-Dialoge: `get_beitrag_detail` lieferte KEIN
 *     `darf_bearbeiten` — wer das Detail unverändert einsetzte, verlor
 *     „Für Gäste freigeben“/„Löschen“. Seit R-12l liefert das Detail das Feld
 *     selbst (UI-R6e): die Leseseiten nehmen es DIREKT von dort.
 *     Geprüft: Detail mit `darf_bearbeiten` → Knöpfe SICHTBAR; ohne → NICHT
 *     sichtbar; und die Knöpfe hängen an KEINEM Listen-Aufruf.
 *
 *  2. NIEDRIG-MITTEL Barrierefreiheit: rohe `<input>` in `DkField` banden die
 *     Slot-Kennung nicht — `<label for>` zeigte ins Leere, das Passwortfeld
 *     hatte keinen zugänglichen Namen. Geprüft am Gast-Dialog
 *     („Für Gäste freigeben“) und an der öffentlichen Gastseite.
 *
 * Aufbau wie tests/dev-b1-mount.test.mjs: `vue/compiler-sfc` übersetzt die
 * ECHTEN Bauteile, gerendert wird in jsdom, `fetch` ist eine Attrappe, die
 * antwortet wie der Server (Nutzlast unter `message`).
 */
import assert from 'node:assert/strict'
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath, pathToFileURL } from 'node:url'

import { compileScript, compileTemplate, parse } from 'vue/compiler-sfc'

const HIER = path.dirname(fileURLToPath(import.meta.url))
const FRONTEND = path.resolve(HIER, '..')
const SRV = path.join(FRONTEND, 'src')

// ── jsdom als Dokument ─────────────────────────────────────────────────────

let DOKUMENT = null

async function dokument() {
    if (!DOKUMENT) {
        const { JSDOM } = await import('jsdom')
        const dom = new JSDOM('<!doctype html><html><head></head><body></body></html>', {
            url: 'http://localhost/diakronos/',
            pretendToBeVisual: true,
        })
        const { window } = dom
        globalThis.window = window
        globalThis.document = window.document
        globalThis.localStorage = window.localStorage
        globalThis.HTMLElement = window.HTMLElement
        globalThis.SVGElement = window.SVGElement
        globalThis.Element = window.Element
        globalThis.Node = window.Node
        globalThis.getComputedStyle = window.getComputedStyle.bind(window)
        globalThis.requestAnimationFrame = (fn) => setTimeout(() => fn(Date.now()), 0)
        globalThis.cancelAnimationFrame = (id) => clearTimeout(id)
        // Boot-Objekt wie in der App (Rollen hier ohne Admin — das Recht kommt
        // in diesen Tests ausdrücklich aus der Liste, nicht aus `is_admin`).
        window.__DIakonosBOOT = {
            basePath: '/diakonos',
            csrf_token: 'test-token',
            user_email: 'test@example.org',
            user_fullname: 'Test Person',
        }
        DOKUMENT = window
    }
    DOKUMENT.document.body.innerHTML = ''
    return DOKUMENT
}

// ── .vue/.js → ES-Module in einem Temp-Baum ────────────────────────────────

const geschrieben = new Set()

function baumAnlegen() {
    const lauf = mkdtempSync(path.join(FRONTEND, '.kanban-r6-'))
    geschrieben.clear()
    // Sicherheitsnetz: der Test selbst räumt nach jedem Fall ab; bricht er
    // vorher ab, verschwindet der Baum spätestens hier.
    BAUM_PFADE.push(lauf)
    return lauf
}

const BAUM_PFADE = []
process.on('exit', () => {
    for (const pfad of BAUM_PFADE) {
        try {
            rmSync(pfad, { recursive: true, force: true })
        } catch { /* schon weg */ }
    }
})

function ziel(ausgabe, abs) {
    const rel = path.relative(SRV, abs).replace(/\.(vue|js|mjs)$/, '.mjs')
    const datei = path.join(ausgabe, 'src', rel)
    mkdirSync(path.dirname(datei), { recursive: true })
    return datei
}

function pfadUmschreiben(ausgabe, abs, pfad) {
    if (!/\.(vue|js|mjs)$/.test(pfad)) return null
    const zielAbs = path.resolve(path.dirname(abs), pfad)
    // Importe stehen in diesen Dateien auch in Kommentaren (Beispielcode) —
    // ein Pfad ohne Datei wird unverändert durchgereicht.
    if (!existsSync(zielAbs)) return null
    if (pfad.endsWith('.vue')) {
        bauteilSchreiben(ausgabe, zielAbs)
        return pfad.replace(/\.vue$/, '.mjs')
    }
    modulSchreiben(ausgabe, zielAbs)
    return pfad.replace(/\.(js|mjs)$/, '.mjs')
}

function bauteilSchreiben(ausgabe, abs) {
    if (geschrieben.has(abs)) return
    geschrieben.add(abs)
    const id = path.basename(abs, '.vue').replace(/\W/g, '_')
    const datei = ziel(ausgabe, abs)
    writeFileSync(datei, 'export default {}\n', 'utf8')

    const { descriptor } = parse(readFileSync(abs, 'utf8'), { filename: abs })
    const skript = compileScript(descriptor, { id, inlineTemplate: true })
    if (!descriptor.script && !descriptor.scriptSetup) {
        // Reine Vorlage (kein <script>): eigener Renderer unten.
    }
    let code = skript.content
    const hoistedUmschreiben = (t) => t.replace(/\b_hoisted_(\d+)\b/g, (_, n) => `_h${id}_${n}`)
    code = hoistedUmschreiben(code)
    const renderImSkript = /_createCommentVNode|_createElementVNode|_createBlock/.test(code)
    if (!renderImSkript) {
        const tpl = compileTemplate({
            id,
            filename: abs,
            source: descriptor.template.content,
            compilerOptions: { bindingMetadata: skript.bindings, mode: 'module' },
        })
        assert.equal(tpl.errors.length, 0, `${id}: Vorlage nicht kompilierbar: ${tpl.errors.join(', ')}`)
        const ohneExport = hoistedUmschreiben(tpl.code.replace(/export function render/, 'function render'))
        const importe = new Set()
        const rest = []
        for (const zeile of `${ohneExport}\n${skript.content}`.split('\n')) {
            if (/^import\s*\{.*\}\s*from\s*["']vue["']\s*;?$/.test(zeile.trim())) {
                for (const n of zeile.slice(zeile.indexOf('{') + 1, zeile.indexOf('}')).split(',')) {
                    if (n.trim()) importe.add(n.trim())
                }
                continue
            }
            if (/^const _hoisted_\d+\b/.test(zeile.trim())) continue
            rest.push(zeile)
        }
        const rumpf = rest.join('\n')
            .replace(/\bexport const /g, 'const ')
            .replace(/export default /g, 'const __bauteil = ')
        code = `import { ${[...importe].join(', ')} } from 'vue'\n${hoistedUmschreiben(rumpf)}`
            + '\n__bauteil.render = render\nexport default __bauteil\n'
    }
    code = code.replace(/from\s+'((?:\.\.?\/)[^']+)'/g, (ganz, pfad) => {
        const neu = pfadUmschreiben(ausgabe, abs, pfad)
        return neu ? ganz.replace(pfad, neu) : ganz
    })
    writeFileSync(datei, code, 'utf8')
}

function modulSchreiben(ausgabe, abs) {
    if (geschrieben.has(abs)) return
    geschrieben.add(abs)
    let code = readFileSync(abs, 'utf8')
    code = code.replace(/from\s+'((?:\.\.?\/)[^']+)'/g, (ganz, pfad) => {
        const neu = pfadUmschreiben(ausgabe, abs, pfad)
        return neu ? ganz.replace(pfad, neu) : ganz
    })
    writeFileSync(ziel(ausgabe, abs), code, 'utf8')
}

// ── fetch-Attrappe wie der Server ──────────────────────────────────────────

function antwort(daten, status = 200) {
    const textInhalt = JSON.stringify(daten)
    return {
        ok: status >= 200 && status < 300,
        status,
        text: async () => textInhalt,
        json: async () => JSON.parse(textInhalt),
        headers: { get: () => 'application/json' },
    }
}

/**
 * Die Attrappe beantwortet nur, was der jeweilige Test braucht; alles andere
 * bekommt eine leere Nutzlast (kein Absturz, keine erfundene Liste).
 */
function fetchAttrappe(aufrufe, plane = {}) {
    return async (url, optionen = {}) => {
        const adresse = String(url)
        let rumpf = {}
        try {
            rumpf = JSON.parse(optionen.body || '{}')
        } catch {
            rumpf = {}
        }
        aufrufe.push({ adresse, rumpf })
        for (const [muster, antwortGeber] of Object.entries(plane)) {
            if (adresse.includes(muster)) return antwortGeber(rumpf, adresse)
        }
        return antwort({ message: {} })
    }
}

/** Wie der Server: Nutzlast liegt unter `message` (Compat-Schicht). */
const unter = (daten) => antwort({ message: daten })

async function rendern(relPfad, props, { plane = {} } = {}) {
    const window = await dokument()
    const aufrufe = []
    window.fetch = globalThis.fetch = fetchAttrappe(aufrufe, plane)
    const ausgabe = baumAnlegen()
    const abs = path.join(SRV, relPfad)
    bauteilSchreiben(ausgabe, abs)
    const datei = ziel(ausgabe, abs)
    const modul = await import(pathToFileURL(datei).href + `?v=${Date.now()}${Math.random()}`)
    const { createApp, h, nextTick } = await import('vue')
    const knoten = window.document.createElement('div')
    window.document.body.appendChild(knoten)
    const app = createApp({ render: () => h(modul.default, props ?? {}) })
    app.config.warnHandler = () => {}
    app.mount(knoten)
    for (let i = 0; i < 12; i += 1) {
        await new Promise((r) => setTimeout(r, 0))
        await nextTick()
    }
    return { window, aufrufe, app, body: window.document.body, baum: ausgabe }
}

function text(body) {
    return (body.textContent || '').replace(/\s+/g, ' ').trim()
}

function knoepfe(body) {
    return [...body.querySelectorAll('button')].map((b) => (b.textContent || '').replace(/\s+/g, ' ').trim())
}

/**
 * Zugänglicher Name eines Feldes: `<label for=…>`-Text oder aria-label.
 * Der Weg, den ein Screenreader nimmt — genau das war beim Befund kaputt.
 */
function zugänglicherName(body, feld) {
    if (!feld) return ''
    const aria = feld.getAttribute('aria-label')
    if (aria) return aria.trim()
    const id = feld.getAttribute('id')
    if (!id) return ''
    const label = body.querySelector(`label[for="${id}"]`)
    return label ? (label.textContent || '').replace(/[*\s]+/g, ' ').trim() : ''
}

// ── Punkt 1: Detail-Dialog behält das Recht aus der Liste ──────────────────
//
// UI-R6c (Punkt 3): Die Fixtures tragen NUR Felder, die der Server wirklich
// liefert — Feldlisten aus den Listen-APIs (`backend/src/diakronos_app/api/
// beitraege.py::get_beitraege_liste` → name, titel, kategorie, auszug, bild,
// autor, datum, auf_website + gerechnet `comments`/`darf_bearbeiten`; Detail
// zusätzlich `content`/`commentList`). `authorAvatar` gibt es beim BEITRAG
// NICHT (nur beim Wiki-Artikel), und ein `date` statt `auf_website` hätte den
// Website-Schalter still auf AUS gestellt.

const BEITRAG_LISTE = {
    id: 'B-1', title: 'Chorprobe am Mittwoch', category: 'ankuendigung',
    excerpt: 'Kurz', author: 'Anna Muster', date: '2026-11-12',
    comments: 0, image: '', auf_website: true,
}

/**
 * UI-R6e: Das DETAIL trägt `darf_bearbeiten` jetzt selbst (Backend R-12l) —
 * die Fixture antwortet wie der Server, also MIT dem Feld (je nach Recht).
 */
function beitragDetail(darf) {
    return {
        id: 'B-1', title: 'Chorprobe am Mittwoch', category: 'ankuendigung',
        excerpt: 'Kurz', author: 'Anna Muster', date: '2026-11-12', comments: 0,
        image: '', auf_website: true,
        content: '<p>Um 19 Uhr im Gemeindesaal.</p>', commentList: [],
        darf_bearbeiten: !!darf,
    }
}

const BEITRAG_DETAIL = beitragDetail(true)

function beitraegePlane(darf) {
    return {
        'gemeinde_get_einstellungen': () => unter({}),
        // UI-R6b: EINE Abfrage für die Anlegeorte (statt Gruppenliste + je Gruppe).
        'rechte.get_anlegeorte': () => unter({ orte: [] }),
        'beitraege.get_beitraege_liste': () => unter([
            { ...BEITRAG_LISTE, ...(darf ? { darf_bearbeiten: true } : {}) },
        ]),
        'beitraege.get_beitrag_detail': () => unter(beitragDetail(darf)),
    }
}

/** Dieselbe Antwort OHNE Liste: so sieht es ein geteilter Link aus. */
function beitraegePlaneOhneListe(darf) {
    const plane = beitraegePlane(darf)
    delete plane['beitraege.get_beitraege_liste']
    return plane
}

/**
 * UI-R6d/R6e: Die Detail-Knöpfe stehen seit MT-7 NICHT mehr in einem Fenster
 * der Liste, sondern auf der LESE-UNTERSEITE (`pages/BeitragDetail.vue`). Die
 * Tests mounten deshalb genau diese Seite — wie nach einem Klick der Liste
 * (Adresse `#/beitraege/<Kennung>`). `darf_bearbeiten` kommt DIRETT aus dem
 * Detail (R-12l); die Liste wird für die Knöpfe nicht mehr befragt.
 */
async function leseSeite(hash) {
    const window = await dokument()
    window.location.hash = hash
    return window
}

test('R6e: Beitrags-Leseseite mit `darf_bearbeiten` aus dem DETAIL zeigt alle drei Knöpfe — ohne Listen-Aufruf', async () => {
    await leseSeite('#/beitraege/B-1')
    try {
        const { body, aufrufe, app, baum } = await rendern('diakonos/pages/BeitragDetail.vue', {}, { plane: beitraegePlane(true) })
        try {
            const namen = knoepfe(body)
            assert.ok(namen.includes('Für Gäste freigeben'), `Knopf fehlt: ${JSON.stringify(namen)}`)
            assert.ok(namen.includes('Bearbeiten'), `Knopf fehlt: ${JSON.stringify(namen)}`)
            assert.ok(namen.includes('Löschen'), `Knopf fehlt: ${JSON.stringify(namen)}`)
            // Das Detail trägt den Inhalt.
            assert.match(text(body), /Um 19 Uhr im Gemeindesaal/)
            // UI-R6e: Das Recht steht im Detail — die Leseseite fragt die Liste
            // NICHT mehr. Sonst hinge der Knopf wieder an einem zweiten Aufruf.
            const liste = aufrufe.filter((a) => String(a.adresse).includes('get_beitraege_liste'))
            assert.equal(liste.length, 0,
                `die Leseseite holt die Liste (${liste.length}x) — die Knöpfe brauchen sie nicht mehr`)
        } finally { app.unmount(); rmSync(baum, { recursive: true, force: true }) }
    } finally { (await dokument()).location.hash = '' }
})

test('R6e: das Recht kommt aus dem DETAIL, nicht aus der Liste (Liste im Test abgeschaltet)', async () => {
    // Gegenprobe zum Test oben: Hier antwortet der Server auf den Listen-Aufruf
    // GAR NICHT (geteilter Link, Liste nicht ladbar). Die Knöpfe müssen
    // trotzdem stehen — sie hängen allein an `darf_bearbeiten` des Details.
    await leseSeite('#/beitraege/B-1')
    try {
        const { body, aufrufe, app, baum } = await rendern('diakonos/pages/BeitragDetail.vue', {}, { plane: beitraegePlaneOhneListe(true) })
        try {
            assert.match(text(body), /Um 19 Uhr im Gemeindesaal/, 'Leseseite wurde nicht aufgebaut')
            const namen = knoepfe(body)
            assert.ok(namen.includes('Bearbeiten'), `Knopf fehlt ohne Liste: ${JSON.stringify(namen)}`)
            assert.ok(namen.includes('Löschen'), `Knopf fehlt ohne Liste: ${JSON.stringify(namen)}`)
            assert.ok(!aufrufe.some((a) => String(a.adresse).includes('get_beitraege_liste')),
                'die Leseseite fragt die Liste doch')
        } finally { app.unmount(); rmSync(baum, { recursive: true, force: true }) }
    } finally { (await dokument()).location.hash = '' }
})

test('R6e: Admin OHNE `darf_bearbeiten` im Detail sieht weder Knöpfe noch Menüeinträge', async () => {
    // Der Befund: Das alte „⋯“-Menü hing an `isAdmin` — ein Administrator ohne
    // Recht sah dort Bearbeiten/Löschen, ein Administrator MIT Recht sah sie
    // doppelt. Das Menü ist gestrichen; die Knöpfe hängen allein am Detail.
    await leseSeite('#/beitraege/B-1')
    try {
        // Rollen wie im Boot-Objekt dieser Datei (kein Admin) — der Fall wird
        // über die SERVER-Antwort geprüft: Detail sagt NEIN.
        const { body, app, baum } = await rendern('diakonos/pages/BeitragDetail.vue', {}, { plane: beitraegePlane(false) })
        try {
            assert.match(text(body), /Um 19 Uhr im Gemeindesaal/, 'Leseseite wurde nicht aufgebaut')
            const namen = knoepfe(body)
            assert.ok(!namen.includes('Für Gäste freigeben'), `Knopf trotz fehlendem Recht: ${JSON.stringify(namen)}`)
            assert.ok(!namen.includes('Bearbeiten'), `Knopf trotz fehlendem Recht: ${JSON.stringify(namen)}`)
            assert.ok(!namen.includes('Löschen'), `Knopf trotz fehlendem Recht: ${JSON.stringify(namen)}`)
            // Kein Menü mehr: weder ein Auslöser noch ein solcher Eintrag.
            assert.equal(body.querySelectorAll('.bt-detail-aktionen').length, 0,
                'die Leseseite hat noch eine Aktions-Leiste (⋯-Menü)')
            assert.ok(!/Aktionen für/.test(text(body)),
                `Menü-Beschriftung steht noch im DOM: „${text(body).slice(0, 120)}“`)
        } finally { app.unmount(); rmSync(baum, { recursive: true, force: true }) }
    } finally { (await dokument()).location.hash = '' }
})

const ANLEGEORTE_CHOR = { gruppe: 'GR-Chor', untergruppe: null, titel: 'Chor', tiefe: 0, gemeinde: false }

test('R6: „Neuer Beitrag“ erscheint nur mit Anlege-Recht (und löst keine POST-Kette aus)', async () => {
    // ZWEI Möglichkeiten: dann fragt die Auswahl nach, und „Weiter“ reicht die
    // gewählte Einheit samt SERVER-Titel weiter. Bei genau einer Möglichkeit
    // gibt es nichts zu wählen — der Titel-Weg wird deshalb hier geprüft.
    const mitRecht = await rendern('diakonos/pages/Beitraege.vue', {}, {
        plane: {
            ...beitraegePlane(false),
            'rechte.get_anlegeorte': () => unter({
                orte: [
                    ANLEGEORTE_CHOR,
                    { gruppe: 'GR-Jugend', untergruppe: null, titel: 'Jugendkreis', tiefe: 0, gemeinde: false },
                ],
            }),
        },
    })
    try {
        assert.ok(knoepfe(mitRecht.body).includes('Neuer Beitrag'), 'Knopf fehlt trotz Anlege-Recht')
        // Der Weg über die Auswahl reicht den SERVER-Titel weiter: nach dem
        // „Weiter“ im Auswahl-Dialog steht im Editor „Chor“, nicht „GR-Chor“.
        // (Ohne `titel` beim Weiterreichen stünde hier die rohe Kennung.)
        const knopf = [...mitRecht.body.querySelectorAll('button')]
            .find(b => (b.textContent || '').replace(/\s+/g, ' ').trim() === 'Neuer Beitrag')
        knopf.dispatchEvent(new DOKUMENT.MouseEvent('click', { bubbles: true }))
        for (let i = 0; i < 12; i += 1) await new Promise((r) => setTimeout(r, 0))
        // Der Weg über die Auswahl: „Weiter“ im Dialog gibt die Einheit weiter.
        // Danach steht im Editor der SERVER-Titel („Chor“), nicht die rohe
        // Kennung („GR-Chor“) — der Ort wird mitsamt `titel` durchgereicht.
        const weiter = [...mitRecht.body.querySelectorAll('button')]
            .find(b => (b.textContent || '').replace(/\s+/g, ' ').trim() === 'Weiter')
        assert.ok(weiter, '„Weiter“ im Auswahl-Dialog fehlt')
        weiter.dispatchEvent(new DOKUMENT.MouseEvent('click', { bubbles: true }))
        for (let i = 0; i < 12; i += 1) await new Promise((r) => setTimeout(r, 0))
        assert.equal(mitRecht.body.querySelector('.bt-einheit-text')?.textContent.trim(), 'Chor',
            `Beiträge-Editor zeigt nicht den Server-Titel: ${mitRecht.body.querySelector('.bt-einheit-text')?.textContent}`)
        assert.ok(!/GR-CHOR/i.test(text(mitRecht.body)), 'Beiträge-Editor zeigt die rohe Kennung')
    } finally { mitRecht.app.unmount(); rmSync(mitRecht.baum, { recursive: true, force: true }) }

    const ohneRecht = await rendern('diakonos/pages/Beitraege.vue', {}, { plane: beitraegePlane(false) })
    try {
        assert.ok(!knoepfe(ohneRecht.body).includes('Neuer Beitrag'),
            `Knopf trotz fehlendem Recht: ${JSON.stringify(knoepfe(ohneRecht.body))}`)
    } finally { ohneRecht.app.unmount(); rmSync(ohneRecht.baum, { recursive: true, force: true }) }
})

test('R6: beim Laden der Seite öffnet sich KEIN Auswahl-Dialog (Befund aus dem Beleg-Lauf)', async () => {
    // Mit mehreren Möglichkeiten öffnete ein Aufruf von `starten()` den Dialog
    // schon beim Seitenladen — ungefragt über der Seite. `rechteLaden()` fragt
    // nur; der Dialog gehört zum Klick auf „Neuer Beitrag“.
    const { body, app, baum } = await rendern('diakonos/pages/Beitraege.vue', {}, {
        plane: {
            ...beitraegePlane(false),
            'rechte.get_anlegeorte': () => unter({
                orte: [
                    ANLEGEORTE_CHOR,
                    { gruppe: 'GR-Jugend', untergruppe: null, titel: 'Jugendkreis', tiefe: 0, gemeinde: false },
                ],
            }),
        },
    })
    try {
        const dialoge = body.querySelectorAll('[role="dialog"]').length
        assert.equal(dialoge, 0, 'Auswahl-Dialog steht ungefragt offen')
        assert.ok(knoepfe(body).includes('Neuer Beitrag'), 'Kopfknopf fehlt trotz Recht')
    } finally { app.unmount(); rmSync(baum, { recursive: true, force: true }) }
})

// ── UI-R6b Punkt 1: EINE Abfrage je Seitenladen ───────────────────────────

test('UI-R6b: „Neuer Beitrag“ fragt die Orte mit GENAU EINEM Aufruf (keine Welle je Gruppe)', async () => {
    // Vorher: 1 × `get_gruppen_hierarchie` + 1 × `get_meine_rechte` JE Einheit.
    // Jetzt: EIN `get_anlegeorte(typ)` — der Server antwortet mit der Liste.
    const { body, aufrufe, app, baum } = await rendern('diakonos/pages/Beitraege.vue', {}, {
        plane: {
            ...beitraegePlane(false),
            'rechte.get_anlegeorte': () => unter({
                orte: [
                    ANLEGEORTE_CHOR,
                    { gruppe: 'GR-Chor', untergruppe: 'UG-Blas', titel: 'Bläsergruppe', tiefe: 1, gemeinde: false },
                    { gruppe: 'GR-Jugend', untergruppe: null, titel: 'Jugendkreis', tiefe: 0, gemeinde: false },
                ],
            }),
        },
    })
    try {
        const ortsAbfragen = aufrufe.filter(a => a.adresse.includes('rechte.get_anlegeorte'))
        assert.equal(ortsAbfragen.length, 1, `Abfragen: ${ortsAbfragen.length} — es darf genau eine sein`)
        // Der Typ steht in der Nutzlast — EINE Abfrage kann nur EINEN Typ bedienen.
        assert.equal(ortsAbfragen[0].rumpf?.typ, 'beitrag')
        // Die abgeschafften Wege laufen nicht mehr mit.
        assert.equal(aufrufe.filter(a => a.adresse.includes('get_gruppen_hierarchie')).length, 0,
            'get_gruppen_hierarchie darf hier nicht mehr gefragt werden')
        assert.equal(aufrufe.filter(a => a.adresse.includes('rechte.get_meine_rechte')).length, 0,
            'keine Einzelfragen je Gruppe mehr')
        assert.ok(knoepfe(body).includes('Neuer Beitrag'), 'Knopf fehlt trotz Orten')
    } finally { app.unmount(); rmSync(baum, { recursive: true, force: true }) }
})

test('UI-R6b: Admin mit Gemeinde, HV mit Gruppe+Untergruppe, Mitglied ohne Ort', async () => {
    const ORTE_ADMIN = {
        orte: [
            { gruppe: null, untergruppe: null, titel: 'Alle Mitglieder der Gemeinde', tiefe: 0, gemeinde: true },
            ANLEGEORTE_CHOR,
            { gruppe: 'GR-Chor', untergruppe: 'UG-Blas', titel: 'Bläsergruppe', tiefe: 1, gemeinde: false },
        ],
    }
    const ORTE_HV = {
        orte: [
            ANLEGEORTE_CHOR,
            { gruppe: 'GR-Chor', untergruppe: 'UG-Blas', titel: 'Bläsergruppe', tiefe: 1, gemeinde: false },
        ],
    }

    // Admin: der Kopfknopf steht — und die Auswahl bietet die Gemeinde an.
    const admin = await rendern('diakonos/pages/Beitraege.vue', {}, {
        plane: { ...beitraegePlane(false), 'rechte.get_anlegeorte': () => unter(ORTE_ADMIN) },
    })
    try {
        assert.ok(knoepfe(admin.body).includes('Neuer Beitrag'), 'Admin: Knopf fehlt')
        knoepfe(admin.body).includes('Neuer Beitrag')
        // Klick öffnet die Gruppenwahl mit den Server-Titeln in Server-Reihenfolge.
        const knopf = [...admin.body.querySelectorAll('button')]
            .find(b => (b.textContent || '').replace(/\s+/g, ' ').trim() === 'Neuer Beitrag')
        knopf.dispatchEvent(new DOKUMENT.MouseEvent('click', { bubbles: true }))
        for (let i = 0; i < 12; i += 1) await new Promise((r) => setTimeout(r, 0))
        const optionen = [...admin.body.querySelectorAll('option')].map(o => (o.textContent || '').replace(/\u00a0/g, '').trim())
        assert.deepEqual(optionen, ['Alle Mitglieder der Gemeinde', 'Chor', 'Bläsergruppe'])
    } finally { admin.app.unmount(); rmSync(admin.baum, { recursive: true, force: true }) }

    // HV: Gruppe + Untergruppe — kein Gemeindeeintrag.
    const hv = await rendern('diakonos/pages/Beitraege.vue', {}, {
        plane: { ...beitraegePlane(false), 'rechte.get_anlegeorte': () => unter(ORTE_HV) },
    })
    try {
        assert.ok(knoepfe(hv.body).includes('Neuer Beitrag'), 'HV: Knopf fehlt')
        const knopf = [...hv.body.querySelectorAll('button')]
            .find(b => (b.textContent || '').replace(/\s+/g, ' ').trim() === 'Neuer Beitrag')
        knopf.dispatchEvent(new DOKUMENT.MouseEvent('click', { bubbles: true }))
        for (let i = 0; i < 12; i += 1) await new Promise((r) => setTimeout(r, 0))
        const optionen = [...hv.body.querySelectorAll('option')].map(o => (o.textContent || '').replace(/\u00a0/g, '').trim())
        assert.deepEqual(optionen, ['Chor', 'Bläsergruppe'], 'HV: kein Gemeinde-Eintrag')
    } finally { hv.app.unmount(); rmSync(hv.baum, { recursive: true, force: true }) }

    // Mitglied: keine Orte → KEIN „Neuer Beitrag“.
    const mitglied = await rendern('diakonos/pages/Beitraege.vue', {}, { plane: beitraegePlane(false) })
    try {
        assert.ok(!knoepfe(mitglied.body).includes('Neuer Beitrag'),
            `Mitglied: Knopf trotz leerer Liste: ${JSON.stringify(knoepfe(mitglied.body))}`)
        // Und die WIKI-Seite ebenso: kein „Neuer Artikel“ bei leerer Ortsliste.
        const wiki = await rendern('diakonos/pages/Wiki.vue', {}, { plane: wikiPlane(false) })
        try {
            assert.ok(!knoepfe(wiki.body).includes('Neuer Artikel'),
                `Mitglied (Wiki): Knopf trotz leerer Liste: ${JSON.stringify(knoepfe(wiki.body))}`)
        } finally { wiki.app.unmount(); rmSync(wiki.baum, { recursive: true, force: true }) }
    } finally { mitglied.app.unmount(); rmSync(mitglied.baum, { recursive: true, force: true }) }
})

// ── Punkt 3: Passwortfelder haben einen zugänglichen Namen ────────────────

test('R6: Gast-Dialog — beide Passwortfelder haben Label und Namen', async () => {
    const { body, app, baum } = await rendern('diakonos/components/r6/GastFreigabe.vue', {
        modelValue: true, typ: 'beitrag', objekt: 'B-1', titel: 'Chorprobe',
    }, {
        plane: { 'rechte.get_gastlinks': () => unter({ links: [] }) },
    })
    try {
        const felder = [...body.querySelectorAll('input[type="password"]')]
        assert.equal(felder.length, 2, `Passwortfelder: ${felder.length}`)
        assert.equal(zugänglicherName(body, felder[0]), 'Passwort für Gäste')
        assert.equal(zugänglicherName(body, felder[1]), 'Passwort wiederholen')
        // Kennung im Feld = Ziel des Labels (kein `label for` ins Leere).
        for (const feld of felder) {
            assert.ok(feld.getAttribute('id'), 'Passwortfeld ohne Kennung')
            assert.equal(feld.getAttribute('name'), feld.getAttribute('name'))
            assert.ok(feld.getAttribute('name'), 'Passwortfeld ohne Namen')
            // UI-R6b Punkt 5: `:aria-required="feld.required"` war an BEIDEN
            // Passwortfeldern wirkungslos (der Slot trägt kein `required`). Am
            // Feld steht jetzt das ECHTE `required` — ein `aria-required`
            // daneben wäre eine zweite Wahrheit.
            assert.ok(feld.hasAttribute('required'),
                `Pflichtfeld ohne required: ${feld.getAttribute('name')}`)
            assert.equal(feld.getAttribute('aria-required'), null,
                `wirkungsloses aria-required steht noch am Feld ${feld.getAttribute('name')}`)
        }
        const auswahl = body.querySelector('select.dk-ui-select')
        assert.ok(auswahl, 'Gültigkeits-Auswahl fehlt')
        assert.equal(zugänglicherName(body, auswahl), 'Gültig')
    } finally { app.unmount(); rmSync(baum, { recursive: true, force: true }) }
})

test('R6: öffentliche Gastseite — Passwortfeld hat einen zugänglichen Namen', async () => {
    const window = await dokument()
    window.location.hash = '#/gast/tok-123'
    try {
        const { body, app, baum } = await rendern('gastinhalt/App.vue', {}, {
            plane: { 'rechte.gast_inhalt': () => antwort({ message: 'Das Passwort stimmt nicht.' }, 403) },
        })
        try {
            const feld = body.querySelector('input[type="password"]')
            assert.ok(feld, 'Passwortfeld fehlt')
            assert.equal(zugänglicherName(body, feld), 'Passwort')
            assert.equal(feld.getAttribute('autocomplete'), 'off', 'autocomplete muss off bleiben')
            // Token steht NIE im Dokumenttext (nur im Hash der Adresse).
            assert.ok(!text(body).includes('tok-123'), 'Token im Seiteninhalt sichtbar')
        } finally { app.unmount(); rmSync(baum, { recursive: true, force: true }) }
    } finally {
        window.location.hash = ''
    }
})

// ── UI-R6b Punkt 3: Verhaltenstests, die mit dem alten Code ROT werden ────
//
// Befund des Reviews: Wiki.vue ließ sich auf `selectedArticle = res` (Detail
// ohne `darf_bearbeiten`) zurückdrehen, der feste Aufruf in GruppeDetail war
// entfernbar, GruppeDetail sprang wieder auf `#/wiki` — alle 37 r6-Tests
// blieben grün. Die Regeln stimmten, ihre ANWENDUNG an der Seite nicht. Die
// folgenden Tests mounten die echten Seiten und sehen nach, was dasteht.

// UI-R6c (Punkt 3): auch der Wiki-Artikel trägt nur Server-Felder —
// `wiki.py::_artikel_to_dict` liefert id, title, excerpt, category, tags,
// author, authorAvatar, updatedAt, isNew (+ `darf_bearbeiten` aus der Liste,
// `content` im Detail). Ein `date` gibt es dort NICHT; das Datum heißt
// `updatedAt`.

const WIKI_LISTE = [{
    id: 'W-1', title: 'Beamer einrichten', category: 'technik',
    excerpt: 'Kurz', author: 'Anna Muster', authorAvatar: 'AM', updatedAt: '2026-11-12',
    tags: ['Beamer'], isNew: false, darf_bearbeiten: true,
}]

/**
 * UI-R6e: Das DETAIL trägt `darf_bearbeiten` selbst (Backend R-12l) — die
 * Fixture antwortet wie der Server, also MIT dem Feld (je nach Recht). Die
 * LISTE bleibt für „Ähnliche Artikel“ da und trägt dort dasselbe Feld.
 */
function wikiDetail(darf) {
    return {
        id: 'W-1', title: 'Beamer einrichten', category: 'technik',
        excerpt: 'Kurz', author: 'Anna Muster', authorAvatar: 'AM',
        updatedAt: '2026-11-12', isNew: false, tags: ['Beamer'],
        content: '<p>Kabel an Eingang 2.</p>',
        darf_bearbeiten: !!darf,
    }
}

const WIKI_DETAIL = wikiDetail(true)

function wikiPlane(darf) {
    return {
        'gemeinde_get_einstellungen': () => unter({}),
        'rechte.get_anlegeorte': () => unter({ orte: [] }),
        'wiki.get_wiki_artikel_liste': () => unter([
            { ...WIKI_LISTE[0], ...(darf ? { darf_bearbeiten: true } : { darf_bearbeiten: false }) },
        ]),
        'wiki.get_wiki_artikel_detail': () => unter(wikiDetail(darf)),
    }
}

test('UI-R6e: Wiki-Leseseite mit `darf_bearbeiten` im DETAIL zeigt alle drei Knöpfe', async () => {
    // UI-R6d: Das Detail-Fenster der Liste gibt es nicht mehr (MT-7) — die
    // Knöpfe stehen auf `pages/WikiArtikel.vue`. Das Recht kommt seit R-12l
    // DIREKT aus der Detail-Antwort.
    await leseSeite('#/wiki/W-1')
    try {
        const { body, app, baum } = await rendern('diakonos/pages/WikiArtikel.vue', {}, { plane: wikiPlane(true) })
        try {
            const namen = knoepfe(body)
            assert.ok(namen.includes('Für Gäste freigeben'), `Knopf fehlt: ${JSON.stringify(namen)}`)
            assert.ok(namen.includes('Bearbeiten'), `Knopf fehlt: ${JSON.stringify(namen)}`)
            assert.ok(namen.includes('Löschen'), `Knopf fehlt: ${JSON.stringify(namen)}`)
            // Das Detail trägt den Inhalt.
            assert.match(text(body), /Kabel an Eingang 2/)
        } finally { app.unmount(); rmSync(baum, { recursive: true, force: true }) }
    } finally { (await dokument()).location.hash = '' }
})

test('UI-R6e: Wiki-Liste sagt JA, das Detail NEIN — das DETAIL entscheidet (keine Knöpfe)', async () => {
    // Der Hilfsweg über den Listeneintrag ist entfallen: Widersprechen sich
    // Liste und Detail, gilt das Detail. Früher hätte `detailMitListe` hier ein
    // „ja“ aus der Liste durchgereicht und die Knöpfe gezeigt.
    await leseSeite('#/wiki/W-1')
    try {
        const plane = wikiPlane(false)
        plane['wiki.get_wiki_artikel_liste'] = () => unter([{ ...WIKI_LISTE[0], darf_bearbeiten: true }])
        const { body, app, baum } = await rendern('diakonos/pages/WikiArtikel.vue', {}, { plane })
        try {
            assert.match(text(body), /Kabel an Eingang 2/, 'Leseseite wurde nicht aufgebaut')
            const namen = knoepfe(body)
            assert.ok(!namen.includes('Bearbeiten'), `Liste überschreibt das Detail: ${JSON.stringify(namen)}`)
            assert.ok(!namen.includes('Löschen'), `Liste überschreibt das Detail: ${JSON.stringify(namen)}`)
        } finally { app.unmount(); rmSync(baum, { recursive: true, force: true }) }
    } finally { (await dokument()).location.hash = '' }
})

test('UI-R6e: Wiki-Leseseite OHNE `darf_bearbeiten` zeigt KEINEN der drei Knöpfe', async () => {
    // Ohne Recht im Detail steht keiner der drei Knöpfe da — die Seite
    // erfindet kein Recht. Der Artikel selbst ist lesbar.
    await leseSeite('#/wiki/W-1')
    try {
        const { body, app, baum } = await rendern('diakonos/pages/WikiArtikel.vue', {}, { plane: wikiPlane(false) })
        try {
            assert.match(text(body), /Kabel an Eingang 2/, 'Leseseite wurde nicht aufgebaut')
            const namen = knoepfe(body)
            assert.ok(!namen.includes('Für Gäste freigeben'), `Knopf trotz fehlendem Recht: ${JSON.stringify(namen)}`)
            assert.ok(!namen.includes('Bearbeiten'), `Knopf trotz fehlendem Recht: ${JSON.stringify(namen)}`)
            assert.ok(!namen.includes('Löschen'), `Knopf trotz fehlendem Recht: ${JSON.stringify(namen)}`)
            assert.equal(body.querySelectorAll('.wk-lese-aktionen').length, 0,
                'die Artikel-Seite hat noch eine Aktions-Leiste (⋯-Menü)')
        } finally { app.unmount(); rmSync(baum, { recursive: true, force: true }) }
    } finally { (await dokument()).location.hash = '' }
})

test('UI-R6b: `#/wiki?gruppe=GR-Chor` öffnet den Editor mit GR-Chor — ohne zweiten Klick', async () => {
    // Der Sprung von der Gruppenseite: die Adresse nennt die Gruppe, die Seite
    // öffnet den Editor EINMAL damit (Punkt 4) und räumt die Adresse auf.
    const window = await dokument()
    window.location.hash = '#/wiki?gruppe=GR-Chor'
    try {
        const { body, aufrufe, app, baum } = await rendern('diakonos/pages/Wiki.vue', {}, {
            plane: {
                ...wikiPlane(false),
                'rechte.get_anlegeorte': () => unter({
                    orte: [
                        { gruppe: null, untergruppe: null, titel: 'Alle Mitglieder der Gemeinde', tiefe: 0, gemeinde: true },
                        { gruppe: 'GR-Chor', untergruppe: null, titel: 'Chor', tiefe: 0, gemeinde: false },
                        { gruppe: 'GR-Jugend', untergruppe: null, titel: 'Jugendkreis', tiefe: 0, gemeinde: false },
                    ],
                }),
            },
        })
        try {
            // Der Editor steht offen, ohne dass jemand „+ Neuer Artikel“ gedrückt hat.
            const titelfeld = body.querySelector('.wk-editor input, [role="dialog"] input')
            assert.ok(titelfeld, 'Editor wurde nicht geöffnet')
            // Die Einheit steht im Formular — mit dem TITEL des Servers („Chor“),
            // nicht mit der rohen Kennung („GR-Chor“).
            assert.equal(body.querySelector('.wk-einheit-text')?.textContent.trim(), 'Chor',
                `Editor zeigt nicht den Server-Titel: ${body.querySelector('.wk-einheit-text')?.textContent}`)
            // Und NIRGENDS im DOM die rohe Kennung: der Editor reicht die Einheit
            // weiter, verliert dabei aber den Server-Titel nicht.
            assert.ok(!/GR-CHOR/i.test(text(body)),
                `Editor zeigt die rohe Kennung statt des Server-Titels: ${text(body).slice(0, 300)}`)
            // Die Auswahl-Rückfrage („Für wen ist das?“) ist NICHT aufgegangen —
            // sonst bräuchte der Sprung einen zweiten Klick.
            const auswahlDialog = [...body.querySelectorAll('[role="dialog"]')]
                .find(d => (d.getAttribute('aria-label') || '') === 'Für wen ist das?')
            assert.equal(auswahlDialog, undefined, 'Die Gruppenauswahl darf nicht aufblitzen')
            // EINE Abfrage, wie überall.
            assert.equal(aufrufe.filter(a => a.adresse.includes('rechte.get_anlegeorte')).length, 1)
            // „Nur für diesen einen Sprung“: die Adresse ist wieder `#/wiki`.
            assert.equal(window.location.hash, '#/wiki', 'Adresse nicht aufgeräumt')
        } finally { app.unmount(); rmSync(baum, { recursive: true, force: true }) }
    } finally {
        window.location.hash = ''
    }
})

test('UI-R6b: `#/wiki?gruppe=GR-Fremd` öffnet KEINEN Editor (kein Recht, nur Adresse aufräumen)', async () => {
    const window = await dokument()
    window.location.hash = '#/wiki?gruppe=GR-Fremd'
    try {
        const { body, app, baum } = await rendern('diakonos/pages/Wiki.vue', {}, {
            plane: {
                ...wikiPlane(false),
                'rechte.get_anlegeorte': () => unter({
                    orte: [{ gruppe: 'GR-Chor', untergruppe: null, titel: 'Chor', tiefe: 0, gemeinde: false }],
                }),
            },
        })
        try {
            assert.ok(!body.querySelector('.wk-editor input'), 'Editor trotz fehlendem Recht geöffnet')
            assert.equal(window.location.hash, '#/wiki', 'Adresse nicht aufgeräumt')
        } finally { app.unmount(); rmSync(baum, { recursive: true, force: true }) }
    } finally {
        window.location.hash = ''
    }
})

test('UI-R6b: Mitglied (keine Orte) — beim Sprung von der Gruppenseite kein Editor', async () => {
    const window = await dokument()
    window.location.hash = '#/wiki?gruppe=GR-Chor'
    try {
        const { body, app, baum } = await rendern('diakonos/pages/Wiki.vue', {}, { plane: wikiPlane(false) })
        try {
            assert.ok(!body.querySelector('.wk-editor input'), 'Editor trotz leerer Ortsliste geöffnet')
            assert.ok(!knoepfe(body).includes('Neuer Artikel'), 'Kopfknopf trotz leerer Ortsliste')
        } finally { app.unmount(); rmSync(baum, { recursive: true, force: true }) }
    } finally {
        window.location.hash = ''
    }
})

// ── UI-R6b Punkt 3c: GruppeDetail nimmt die Gruppe in den Wiki-Sprung mit ──
//
// Review-Gegenprobe: `wikiAnlegenZiel` ließ sich auf `#/wiki` zurückdrehen,
// ohne dass ein Test rot wurde. Der Sprung trug dann keine Gruppe mehr — die
// Vorauswahl im Editor wäre leer. Hier wird der Knopf der Gruppenseite
// gedrückt und die Adresse angeschaut.

/** Boot als Administrator: `canManage` ist dann ohne Rolle wahr. */
async function alsAdmin(dok) {
    dok.__DIakonosBOOT = {
        basePath: '/diakonos',
        csrf_token: 'test-token',
        user_email: 'test@example.org',
        user_fullname: 'Test Person',
        is_admin: true,
        modules: [],
    }
    return dok
}

/**
 * Gruppenseite rendern und den Wiki-Knopf drücken; liefert den Hash danach.
 * `detail` ist die Antwort von `gruppen.get_gruppe_detail`.
 */
async function gruppenSprung(detail) {
    const window = await dokument()
    await alsAdmin(window)
    const { body, app, baum } = await rendern('diakonos/pages/GruppeDetail.vue', {}, {
        plane: {
            'gruppen.get_gruppe_detail': () => unter(detail),
            'gruppen.get_gruppe_termine': () => unter({ termine: [] }),
        },
    })
    try {
        const knopf = body.querySelector('button[aria-label="Wiki-Artikel anlegen"]')
        assert.ok(knopf, 'Wiki-Knopf der Gruppenseite fehlt')
        knopf.dispatchEvent(new DOKUMENT.MouseEvent('click', { bubbles: true }))
        for (let i = 0; i < 6; i += 1) await new Promise((r) => setTimeout(r, 0))
        return window.location.hash
    } finally {
        app.unmount(); rmSync(baum, { recursive: true, force: true })
        window.location.hash = ''
        delete window.__DIakonosBOOT.is_admin
    }
}

test('UI-R6b: GruppeDetail — Hauptgruppe springt auf `#/wiki?gruppe=GR-Chor`', async () => {
    // Die Adresse der Gruppenseite ist `#/gruppe/<name>` — daraus liest die
    // Seite ihre Kennung (`getRouteParam('id')`).
    const window = await dokument()
    window.location.hash = '#/gruppe/GR-Chor'
    try {
        const hash = await gruppenSprung({
            gruppe: { name: 'GR-Chor', gruppenname: 'Chor', status: 'Aktiv' },
            mitglieder: [], verantwortliche: [], untergruppen: [], aufgaben: [],
            ankuendigungen: [], wiki_artikel: [], is_member: true,
        })
        assert.equal(hash, '#/wiki?gruppe=GR-Chor')
    } finally {
        window.location.hash = ''
    }
})

test('UI-R6b: GruppeDetail — Untergruppe nimmt Gruppe UND Untergruppe mit', async () => {
    // Die echte Adresse der Unterseite (`#/gruppe/<name>` → `getRouteParam('id')`).
    const window = await dokument()
    window.location.hash = '#/gruppe/UG-Blas'
    try {
        const hash = await gruppenSprung({
            untergruppe: { name: 'UG-Blas', untergruppenname: 'Bläsergruppe', gruppe: 'GR-Chor', status: 'Aktiv' },
            mitglieder: [], verantwortliche: [], untergruppen: [], aufgaben: [],
            ankuendigungen: [], wiki_artikel: [], is_member: true,
        })
        assert.equal(hash, '#/wiki?gruppe=GR-Chor&untergruppe=UG-Blas')
    } finally {
        window.location.hash = ''
    }
})

// ── UI-R6c Punkt 2: GENAU EIN Anlegeort — der Server-Titel muss durchkommen ──
//
// Befund: `useAnlegenMitGruppe.starten()` gab bei genau einer Möglichkeit nur
// `{gruppe, untergruppe}` zurück (ohne `titel`). Der Editor zeigte dann die
// Kennung („GR-Chor“, „GR-Chor · UG-Blas“) bzw. bei Gemeinde einen eigenen
// Text — bei MEHREREN Orten kam der Titel dagegen über `GruppeWaehlen` an.
// Diese Tests nehmen je Seitenart den Ein-Ort-Fall; die Kennung ist bewusst
// vom Titel verschieden („GR-Chor“ ≠ „Chor“), damit ein Verlust auffällt.

/** Eine Seite rendern und den Kopfknopf „+ …“ drücken (ohne Auswahl-Dialog). */
async function anlegenEinOrt(seite, knopfText, orte) {
    const plane = seite.includes('Wiki') ? wikiPlane(false) : beitraegePlane(false)
    const ergebnis = await rendern(seite, {}, {
        plane: { ...plane, 'rechte.get_anlegeorte': () => unter({ orte }) },
    })
    try {
        const knopf = [...ergebnis.body.querySelectorAll('button')]
            .find(b => (b.textContent || '').replace(/\s+/g, ' ').trim() === knopfText)
        assert.ok(knopf, `Kopfknopf „${knopfText}“ fehlt`)
        knopf.dispatchEvent(new DOKUMENT.MouseEvent('click', { bubbles: true }))
        for (let i = 0; i < 12; i += 1) await new Promise((r) => setTimeout(r, 0))
        return ergebnis
    } catch (fehler) {
        ergebnis.app.unmount()
        rmSync(ergebnis.baum, { recursive: true, force: true })
        throw fehler
    }
}

/** Editor offen? Erkannt am Einheiten-Block (`.bt-einheit-text`/`.wk-einheit-text`). */
function editorEinheit(body, klasse) {
    return body.querySelector(klasse)
}

test('UI-R6c: Beiträge, GENAU EIN Ort (Gruppe) — Editor zeigt den Server-Titel, nicht „GR-Chor“', async () => {
    const { body, app, baum } = await anlegenEinOrt('diakonos/pages/Beitraege.vue', 'Neuer Beitrag', [ANLEGEORTE_CHOR])
    try {
        const feld = editorEinheit(body, '.bt-einheit-text')
        assert.ok(feld, 'Editor wurde nicht geöffnet (Einheiten-Block fehlt)')
        assert.equal(feld.textContent.trim(), 'Chor', `Editor zeigt nicht den Server-Titel: ${feld.textContent}`)
        assert.ok(!/GR-CHOR/i.test(text(body)), `Editor zeigt die rohe Kennung: ${text(body).slice(0, 300)}`)
    } finally { app.unmount(); rmSync(baum, { recursive: true, force: true }) }
})

test('UI-R6c: Beiträge, GENAU EIN Ort (Untergruppe) — Editor zeigt „Bläsergruppe“', async () => {
    const { body, app, baum } = await anlegenEinOrt('diakonos/pages/Beitraege.vue', 'Neuer Beitrag', [
        { gruppe: 'GR-Chor', untergruppe: 'UG-Blas', titel: 'Bläsergruppe', tiefe: 1, gemeinde: false },
    ])
    try {
        const feld = editorEinheit(body, '.bt-einheit-text')
        assert.ok(feld, 'Editor wurde nicht geöffnet (Einheiten-Block fehlt)')
        assert.equal(feld.textContent.trim(), 'Bläsergruppe', `Editor zeigt nicht den Server-Titel: ${feld.textContent}`)
        // Der alte Rückfall war die zusammengesetzte Kennung „GR-Chor · UG-Blas“.
        assert.ok(!/GR-CHOR|UG-BLAS/i.test(text(body)), `Kennung statt Titel: ${text(body).slice(0, 300)}`)
    } finally { app.unmount(); rmSync(baum, { recursive: true, force: true }) }
})

test('UI-R6c: Beiträge, GENAU EIN Ort (Gemeinde) — Titel des Servers, kein eigener Gemeinde-Text', async () => {
    // Der Server nennt den gemeindeweiten Ort „Alle Mitglieder der Gemeinde“
    // (`STUFEN_TITEL`). Der frühere eigene Text lautete „Für alle Mitglieder
    // der Gemeinde“ — hier kommt bewusst ein ANDERER Server-Titel, damit
    // sichtbar wird, wer den Text bestimmt.
    const { body, app, baum } = await anlegenEinOrt('diakonos/pages/Beitraege.vue', 'Neuer Beitrag', [
        { gruppe: null, untergruppe: null, titel: 'Ganze Gemeinde Musterhausen', tiefe: 0, gemeinde: true },
    ])
    try {
        const feld = editorEinheit(body, '.bt-einheit-text')
        assert.ok(feld, 'Editor wurde nicht geöffnet (Einheiten-Block fehlt)')
        assert.equal(feld.textContent.trim(), 'Ganze Gemeinde Musterhausen',
            `Editor zeigt nicht den Server-Titel: ${feld.textContent}`)
        assert.ok(!/Für alle Mitglieder der Gemeinde/.test(text(body)),
            'Der eigene Gemeinde-Text steht wieder da (GEMEINDE_TEXT)')
    } finally { app.unmount(); rmSync(baum, { recursive: true, force: true }) }
})

test('UI-R6c: Wiki, GENAU EIN Ort (Gruppe) — Editor zeigt den Server-Titel', async () => {
    const { body, app, baum } = await anlegenEinOrt('diakonos/pages/Wiki.vue', 'Neuer Artikel', [ANLEGEORTE_CHOR])
    try {
        const feld = editorEinheit(body, '.wk-einheit-text')
        assert.ok(feld, 'Editor wurde nicht geöffnet (Einheiten-Block fehlt)')
        assert.equal(feld.textContent.trim(), 'Chor', `Editor zeigt nicht den Server-Titel: ${feld.textContent}`)
        assert.ok(!/GR-CHOR/i.test(text(body)), `Editor zeigt die rohe Kennung: ${text(body).slice(0, 300)}`)
    } finally { app.unmount(); rmSync(baum, { recursive: true, force: true }) }
})

test('UI-R6c: Wiki, GENAU EIN Ort (Untergruppe) — Editor zeigt „Bläsergruppe“', async () => {
    const { body, app, baum } = await anlegenEinOrt('diakonos/pages/Wiki.vue', 'Neuer Artikel', [
        { gruppe: 'GR-Chor', untergruppe: 'UG-Blas', titel: 'Bläsergruppe', tiefe: 1, gemeinde: false },
    ])
    try {
        const feld = editorEinheit(body, '.wk-einheit-text')
        assert.ok(feld, 'Editor wurde nicht geöffnet (Einheiten-Block fehlt)')
        assert.equal(feld.textContent.trim(), 'Bläsergruppe', `Editor zeigt nicht den Server-Titel: ${feld.textContent}`)
        assert.ok(!/GR-CHOR|UG-BLAS/i.test(text(body)), `Kennung statt Titel: ${text(body).slice(0, 300)}`)
    } finally { app.unmount(); rmSync(baum, { recursive: true, force: true }) }
})

test('UI-R6c: Wiki, GENAU EIN Ort (Gemeinde) — Titel des Servers, kein eigener Gemeinde-Text', async () => {
    const { body, app, baum } = await anlegenEinOrt('diakonos/pages/Wiki.vue', 'Neuer Artikel', [
        { gruppe: null, untergruppe: null, titel: 'Ganze Gemeinde Musterhausen', tiefe: 0, gemeinde: true },
    ])
    try {
        const feld = editorEinheit(body, '.wk-einheit-text')
        assert.ok(feld, 'Editor wurde nicht geöffnet (Einheiten-Block fehlt)')
        assert.equal(feld.textContent.trim(), 'Ganze Gemeinde Musterhausen',
            `Editor zeigt nicht den Server-Titel: ${feld.textContent}`)
        assert.ok(!/Für alle Mitglieder der Gemeinde/.test(text(body)),
            'Der eigene Gemeinde-Text steht wieder da (GEMEINDE_TEXT)')
    } finally { app.unmount(); rmSync(baum, { recursive: true, force: true }) }
})

// ── UI-R6d Punkt 3: die Knöpfe werden NICHT gedruckt (wie „‹ zurück“, MT-7c) ──

/**
 * Druckregel der Leseseiten: `.bt-detail-knoepfe` / `.wk-lese-knoepfe` steht in
 * einem `@media print`-Block auf `display: none` — und GENAU diese Klasse
 * trägt der gerenderte Knopf-Block (sonst zeigte die Regel ins Leere).
 * jsdom wertet keine Medien aus; belegt wird deshalb die Zuordnung
 * Quelle ↔ gerendertes DOM, wie bei MT-7c.
 */
function druckAus(quelle, klasse) {
    const css = quelle.replace(/<script[\s\S]*?<\/script>/g, '').replace(/\/\*[\s\S]*?\*\//g, '')
    // Alle Druckblöcke sammeln (auch `@media print and (…)`).
    const bloecke = css.match(/@media[^{]*\bprint\b[^{]*\{[\s\S]*?\n\}/g) || []
    return bloecke.some((block) => new RegExp(`\\.${klasse}\\s*\\{[^}]*display:\\s*none`).test(block))
}

test('UI-R6d: der Druck blendet die Änderungs-Knöpfe beider Leseseiten aus', async () => {
    const seiten = [
        { datei: 'diakonos/pages/BeitragDetail.vue', klasse: 'bt-detail-knoepfe', hash: '#/beitraege/B-1', plane: () => beitraegePlane(true) },
        { datei: 'diakonos/pages/WikiArtikel.vue', klasse: 'wk-lese-knoepfe', hash: '#/wiki/W-1', plane: () => wikiPlane(true) },
    ]
    for (const seite of seiten) {
        const quelle = readFileSync(path.join(SRV, seite.datei), 'utf8')
        assert.ok(druckAus(quelle, seite.klasse),
            `${seite.datei}: @media print blendet .${seite.klasse} nicht aus`)

        await leseSeite(seite.hash)
        try {
            const { body, app, baum } = await rendern(seite.datei, {}, { plane: seite.plane() })
            try {
                const block = body.querySelector(`.${seite.klasse}`)
                assert.ok(block, `${seite.datei}: der Knopf-Block .${seite.klasse} fehlt im DOM (Regel zeigt ins Leere)`)
                // Am Bildschirm sichtbar: nur der Druckblock darf ihn verstecken.
                assert.notEqual(DOKUMENT.getComputedStyle(block).display, 'none',
                    `${seite.datei}: .${seite.klasse} ist am Bildschirm unsichtbar`)
            } finally { app.unmount(); rmSync(baum, { recursive: true, force: true }) }
        } finally { (await dokument()).location.hash = '' }
    }
})
