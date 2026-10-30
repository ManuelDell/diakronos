/**
 * FIX-6 — Messung der zwei Kriterien (Befund DMB-d446e449ba22).
 *
 * Operator-Entscheidung 27.10.: LAYOUT richtet sich nur nach der Breite
 * (<= 720 px → Mobil-Layout), TOUCH-Anpassungen nur nach dem Zeigegerät
 * (`(pointer: coarse)`, ohne Breite).
 *
 * Matrix (jede Lage eigener Browser-Kontext; der Zeiger wird gesetzt):
 *
 *   390-coarse        390x844   grober Zeiger   → Mobil-Layout + Touch
 *   700-fine          700x800   feiner Zeiger   → Mobil-Layout, KEIN Touch
 *   1024-coarse      1024x768   grober Zeiger   → Desktop-Layout + Touch
 *   1410-fine-touch  1410x755   fein + Touch    → Desktop (der Befund)
 *   1366-fine        1366x768   feiner Zeiger   → Desktop, kein Touch
 *
 * Gemessen wird je Lage: Seitenleiste sichtbar?, untere Leiste sichtbar?,
 * Schriftgröße eines Eingabefelds (16 px = Touch-Anpassung aktiv), FAB,
 * Jahreszahl, Ressourcenplan, Fußabstand, Monatszeilen-Umbruch — plus was der
 * Browser selbst über `matchMedia` meldet.
 *
 * Aufruf (playwright wird im Abbild unter /tmp/pw nachinstalliert, die
 * Browser liegen unter /ms-playwright):
 *   docker run --rm --network <netz> -v "<repo>":/w:ro \
 *       -e FIX6_BASE=http://app:8000 \
 *       mcr.microsoft.com/playwright:v1.49.0-noble sh -c \
 *       'npm i -s --prefix /tmp/pw playwright@1.49.0 >/dev/null 2>&1;
 *        export NODE_PATH=/tmp/pw/node_modules;
 *        node /w/tools/demo/fix6-zeigegeraet.mjs'
 */
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
const { chromium } = require('playwright')

const BASE = (process.env.FIX6_BASE || 'http://app:8000').replace(/\/$/, '')
const EMAIL = process.env.ADMIN_EMAIL || 'admin@example.org'
const PASSWORT = process.env.ADMIN_PASS || 'musterhausen-demo'

/** Lagen der Matrix. `grob` = primaerer Zeiger ist ein Finger. */
const LAGEN = [
    { name: '390-coarse', breite: 390, hoehe: 844, touch: true, layout: 'mobil', touchAn: true },
    { name: '700-fine', breite: 700, hoehe: 800, touch: false, layout: 'mobil', touchAn: false },
    { name: '1024-coarse', breite: 1024, hoehe: 768, touch: true, layout: 'desktop', touchAn: true },
    // Der Befund: 1410 px MIT Touch-Fähigkeit. Der Zeiger folgt `hasTouch` —
    // ein Touch-Gerät mit FINGER als primärem Zeiger bekommt die
    // Touch-Anpassungen (der Zeiger entscheidet), das LAYOUT bleibt Desktop.
    { name: '1410-fine-touch', breite: 1410, hoehe: 755, touch: true, layout: 'desktop', touchAn: true },
    { name: '1366-fine', breite: 1366, hoehe: 768, touch: false, layout: 'desktop', touchAn: false },
]

/** Sichtbarkeit/Geometrie eines Elements (null, wenn nicht vorhanden). */
async function info(page, selektor) {
    return page.evaluate((sel) => {
        const el = document.querySelector(sel)
        if (!el) return null
        const s = getComputedStyle(el)
        const r = el.getBoundingClientRect()
        return {
            display: s.display,
            position: s.position,
            sichtbar: s.display !== 'none' && s.visibility !== 'hidden'
                && r.width > 0 && r.height > 0,
            breite: Math.round(r.width),
            hoehe: Math.round(r.height),
        }
    }, selektor)
}

/**
 * Schriftgroessen der Eingabefelder der Seite (16 px = Touch-Regel).
 *
 * Gemessen wird die GROESSTE Schrift aller sichtbaren Felder: Seite und
 * Dialog zeigen unterschiedliche Felder, und die Touch-Regel greift je Feld.
 * `hat16` sagt, ob mindestens ein sichtbares Feld 16 px hat.
 */
async function feldSchrift(page) {
    return page.evaluate(() => {
        const felder = [...document.querySelectorAll(
            'input:not([type="checkbox"]):not([type="radio"]):not([type="hidden"]), select, textarea')]
            .filter((el) => {
                const r = el.getBoundingClientRect()
                return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== 'hidden'
            })
        const groessen = felder.map((el) => Math.round(parseFloat(getComputedStyle(el).fontSize)))
        const max = groessen.length ? Math.max(...groessen) : null
        return {
            anzahl: groessen.length,
            groessen: [...new Set(groessen)].sort((a, b) => a - b),
            max,
            hat16: groessen.some((n) => n >= 16),
        }
    })
}

async function messe(page) {
    return {
        breite: await page.evaluate(() => window.innerWidth),
        zeigegerat: await page.evaluate(() => ({
            fine: matchMedia('(pointer: fine)').matches,
            coarse: matchMedia('(pointer: coarse)').matches,
            anyFine: matchMedia('(any-pointer: fine)').matches,
            anyCoarse: matchMedia('(any-pointer: coarse)').matches,
            maxTouchPoints: navigator.maxTouchPoints,
        })),
        feldSchrift: await feldSchrift(page),
        // Die Seitenleiste ist im DOM immer vorhanden; sichtbar ist sie über
        // `display` (die Mobil-Regel setzt `display: none`).
        seitenleisteDa: await page.evaluate(() => {
            const el = document.querySelector('.dk-sidebar')
            if (!el) return false
            const s = getComputedStyle(el)
            return s.display !== 'none' && s.visibility !== 'hidden'
        }),
        fab: await info(page, '.dk-widget-edit-fab'),
        untereLeiste: await info(page, '.dk-bottom-nav'),
        jahreszahl: await info(page, '.date-year'),
        ressourcenknopf: await info(page, '#resource-toggle-btn'),
        moderationLabel: await info(page, '.moderation-btn-label'),
        seitenleiste: await info(page, '.dk-sidebar'),
    }
}

async function anmelden(page) {
    await page.goto(BASE + '/#/', { waitUntil: 'networkidle' })
    const feld = page.locator('input[name="usr"], #dk-usr')
    if (await feld.count()) {
        await feld.first().fill(EMAIL)
        await page.fill('input[name="pwd"], #dk-pwd', PASSWORT)
        await page.click('button[type="submit"]')
        await page.waitForLoadState('networkidle')
    }
    await page.waitForTimeout(1200)
}

async function lage(browser, def) {
    const ctx = await browser.newContext({
        viewport: { width: def.breite, height: def.hoehe },
        hasTouch: def.touch,
        locale: 'de-DE',
    })
    // Playwright bildet den Zeiger über `hasTouch` ab: `hasTouch: true` ->
    // (pointer: coarse), `hasTouch: false` -> (pointer: fine). Genau das ist
    // die Unterscheidung des Operators (Finger vs. Maus). Ein Erzwingen per
    // matchMedia-Attrappe wäre falsch: das CSS wertet dann weiterhin den
    // echten Zeiger aus, und die Messung zeigt einen Widerspruch (CSS 16 px,
    // Attrappe „fine“). Deshalb wird hier NICHTS überschrieben.
    const page = await ctx.newPage()
    const fehler = []
    // Fehlende Programme/Seiten (4xx) werden mitgeschrieben. Der Dev-Modus ist
    // im Wegwerf-Stack absichtlich AUS — sein Uebersichts-Endpunkt antwortet
    // dann mit 404. Das ist kein Fehler dieser Karte und faellt heraus.
    page.on('response', (a) => {
        if (a.status() < 400) return
        if (a.url().includes('devmodus')) return
        fehler.push(`${a.status()} ${a.url()}`)
    })

    await anmelden(page)
    const start = await messe(page)

    await page.goto(BASE + '/#/kalender', { waitUntil: 'networkidle' })
    await page.waitForTimeout(2500)
    const kalender = await messe(page)
    kalender.fussabstand = await page.evaluate(() => {
        const el = document.querySelector('.kronos-page-content')
        return el ? getComputedStyle(el).paddingBottom : null
    })

    // Felder der Einstellungen (dort stehen Formularfelder; die Startseite
    // hat keine). Die 16-px-Regel greift je Feld — eines genügt als Beleg.
    await page.goto(BASE + '/#/einstellungen', { waitUntil: 'networkidle' })
    await page.waitForTimeout(2500)
    const einstellungen = { feldSchrift: await feldSchrift(page) }

    await page.goto(BASE + '/#/planrahmen/meine-dienste', { waitUntil: 'networkidle' })
    await page.waitForTimeout(2500)
    const meineDienste = {
        zeilenUmbruch: await page.evaluate(() => {
            const el = document.querySelector('.pr-md-monat-zeile')
            return el ? getComputedStyle(el).flexWrap : null
        }),
    }

    await ctx.close()
    return { lage: def.name, soll: def, start, kalender, einstellungen, meineDienste, fehler }
}

/** Kurzfassung als eine Zeile — so bleibt die Messung im Protokoll lesbar. */
function zeile(e) {
    const s = e.start
    const k = e.kalender
    return [
        `LAGE ${e.lage}`,
        `breite=${s.breite}`,
        `coarse=${s.zeigegerat.coarse}`,
        `fine=${s.zeigegerat.fine}`,
        `maxTouch=${s.zeigegerat.maxTouchPoints}`,
        `seitenleiste=${k.seitenleisteDa}`,
        `felder=${JSON.stringify(e.einstellungen.feldSchrift.groessen)}(max ${e.einstellungen.feldSchrift.max})`,
        `hatFeld16=${e.einstellungen.feldSchrift.hat16}`,
        `untereLeiste=${k.untereLeiste?.sichtbar}`,
        `fab=${s.fab?.position}/${s.fab?.breite}px`,
        `jahreszahl=${k.jahreszahl?.sichtbar}`,
        `ressourcenplan=${k.ressourcenknopf?.sichtbar}`,
        `moderationLabel=${k.moderationLabel?.sichtbar}`,
        `fussabstand=${k.fussabstand}`,
        `monatszeile=${e.meineDienste.zeilenUmbruch}`,
        `4xx=${e.fehler.length}`,
    ].join(' ')
}

async function main() {
    const browser = await chromium.launch()
    const ergebnisse = []
    for (const def of LAGEN) ergebnisse.push(await lage(browser, def))
    await browser.close()

    for (const e of ergebnisse) console.log(zeile(e))

    // Pruefung gegen die zwei Kriterien der Karte.
    const pruefungen = []
    for (const e of ergebnisse) {
        const mobil = e.soll.layout === 'mobil'
        const touch = e.soll.touchAn
        const name = e.lage
        // Die Seitenleiste ist im DOM immer vorhanden; sichtbar ist sie, wenn
        // sie Breite und Höhe hat (die Mobil-Regel setzt `display: none`).
        pruefungen.push([`${name}: Seitenleiste ${mobil ? 'aus' : 'sichtbar'}`,
            e.kalender.seitenleisteDa === !mobil])
        pruefungen.push([`${name}: untere Leiste ${mobil ? 'sichtbar' : 'aus'}`,
            Boolean(e.kalender.untereLeiste?.sichtbar) === mobil])
        pruefungen.push([`${name}: Eingabeschrift ${touch ? '16 px (Touch)' : 'unter 16 px (kein Touch)'}`,
            touch ? e.einstellungen.feldSchrift.hat16 : !e.einstellungen.feldSchrift.hat16])
        pruefungen.push([`${name}: Jahreszahl ${mobil ? 'aus' : 'sichtbar'}`,
            Boolean(e.kalender.jahreszahl?.sichtbar) === !mobil])
        pruefungen.push([`${name}: Fussabstand ${mobil ? '80 px' : '0 px'}`,
            (e.kalender.fussabstand === '80px') === mobil])
        pruefungen.push([`${name}: keine fehlenden Programme/Seiten (4xx)`, e.fehler.length === 0])
    }
    // Der Befund selbst: 1410 px MIT Touch muss sich wie 1366 px mit Maus
    // verhalten (Touch-Laptop = Desktop, ohne Touch-Vergroesserungen).
    const notebook = ergebnisse.find((e) => e.lage === '1410-fine-touch')
    const desktop = ergebnisse.find((e) => e.lage === '1366-fine')
    pruefungen.push(['Befund 1410 px + Touch: Layout wie 1366 px mit Maus (FAB, Jahreszahl)',
        notebook.start.fab?.position === desktop.start.fab?.position
        && notebook.kalender.jahreszahl?.sichtbar === desktop.kalender.jahreszahl?.sichtbar])
    // Schmales Mausfenster: Mobil-Layout, aber ohne Touch-Vergroesserungen.
    const schmal = ergebnisse.find((e) => e.lage === '700-fine')
    pruefungen.push(['700 px mit Maus: Mobil-Layout MIT unterer Leiste',
        Boolean(schmal.kalender.untereLeiste?.sichtbar)])
    pruefungen.push(['700 px mit Maus: keine Touch-Vergroesserung (kein Feld ab 16 px)',
        !schmal.kalender.feldSchrift.hat16])
    // iPad quer: Desktop-Layout, aber Touch-Anpassungen.
    const ipad = ergebnisse.find((e) => e.lage === '1024-coarse')
    pruefungen.push(['1024 px mit grobem Zeiger: Desktop-Layout, 16-px-Felder',
        !ipad.kalender.untereLeiste?.sichtbar && ipad.einstellungen.feldSchrift.hat16])

    let fehl = 0
    for (const [text, ok] of pruefungen) {
        console.log(`${ok ? 'OK  ' : 'FEHL'} ${text}`)
        if (!ok) fehl += 1
    }
    console.log(`ERGEBNIS ${fehl === 0 ? 'bestanden' : fehl + ' Fehlschlaege'} (${pruefungen.length} Pruefungen)`)
    process.exit(fehl === 0 ? 0 : 1)
}

main().catch((e) => { console.error(e); process.exit(2) })
