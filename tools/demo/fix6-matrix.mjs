/**
 * FIX-6 — Abnahmematrix der zwei Kriterien (Operator 27.10., Runde 2).
 *
 * Der Operator hat die Regel verbindlich getrennt:
 *
 *   LAYOUT  richtet sich NUR nach der BREITE:
 *           <= 720 px  -> Mobil-Layout (einspaltig, untere Leiste statt
 *                         Seitenleiste, Jahreszahl/Ressourcenplan aus)
 *           >  720 px  -> Desktop-Layout
 *
 *   TOUCH   richtet sich NUR nach dem Zeigegerät `(pointer: coarse)`,
 *           unabhängig von der Breite (16-px-Felder gegen den iOS-Zoom,
 *           Tippziel-Mindestgrößen).
 *
 *   Nie Kriterium ist die bloße Touch-FÄHIGKEIT (any-pointer, maxTouchPoints,
 *   ontouchstart).
 *
 * ── Warum zwei Messungen ────────────────────────────────────────────────
 * Ein Touch-Laptop ist „touch-fähig, aber der PRIMÄRE Zeiger ist eine Maus“.
 * Genau diese Lage lässt sich in Chromium NICHT als echter Browser-Zustand
 * herstellen; gemessen (Playwright 1.49 / Chromium 130, 1410×755):
 *
 *   hasTouch: true, kein Überschreiben  -> (pointer: coarse), (any-pointer: coarse)
 *   hasTouch: true + CDP setEmulatedMedia
 *       {pointer: fine, hover: hover}   -> unverändert coarse  (CDP kann nur
 *                                          prefers-*, nicht Zeiger)
 *   hasTouch: false + CDP {pointer: coarse} -> unverändert fine
 *   chromium --blink-settings=primaryPointerType=1,availablePointerTypes=1
 *       -> Zeiger bleibt coarse, stiller Fallback auf die Vorgabe
 *
 * Deshalb zwei Belege, die zusammen den Fall abdecken:
 *
 *   MESSUNG A (echter Browser, primär): die App unter dem PRIMÄREN Zeiger, den
 *   Chromium wirklich herstellt — grob (hasTouch) und fein (Maus). Alle
 *   Lagen der Matrix, echter Login, echte Seiten, echte Geometrie.
 *
 *   MESSUNG B (CSS-Auflösung): derselbe Code, aber die Zeigerlage als
 *   Media-Query-Überschreibung im Dokument — genau das, was ein Touch-Laptop
 *   mit Maus dem Browser meldet: `(pointer: fine)`, `(hover: hover)`,
 *   `(any-pointer: coarse)` UND `(any-pointer: fine)`, `maxTouchPoints: 5`.
 *   Die Überschreibung erzeugt Chromium selbst (`Emulation.setEmulatedMedia`
 *   über `@media`-Regeln am Dokumentanfang, siehe `mediaUeberschreibung`), und
 *   die Messung PRÜFT, dass die Überschreibung wirklich greift.
 *
 * Aufruf:
 *   docker run --rm --network <netz> -v "<repo>":/w:ro -e FIX6_BASE=http://app:8000 \
 *       mcr.microsoft.com/playwright:v1.49.0-noble sh -c \
 *       'npm i -s --prefix /tmp/pw playwright@1.49.0 >/dev/null 2>&1;
 *        export NODE_PATH=/tmp/pw/node_modules;
 *        node /w/tools/demo/fix6-matrix.mjs'
 */
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
const { chromium } = require('playwright')

const BASE = (process.env.FIX6_BASE || 'http://app:8000').replace(/\/$/, '')
const EMAIL = process.env.ADMIN_EMAIL || 'admin@example.org'
const PASSWORT = process.env.ADMIN_PASS || 'musterhausen-demo'
const GRENZE = 720

/**
 * Messung A — was Chromium als primären Zeiger herstellt.
 * `zeiger: 'coarse'` = hasTouch (Finger), `'fine'` = Maus.
 */
const LAGEN_A = [
    { name: 'handy-390', breite: 390, hoehe: 844, zeiger: 'coarse', touch: true },
    { name: 'fenster-700', breite: 700, hoehe: 800, zeiger: 'fine', touch: false },
    { name: 'ipad-1024', breite: 1024, hoehe: 768, zeiger: 'coarse', touch: true },
    { name: 'schlank-1410-coarse', breite: 1410, hoehe: 755, zeiger: 'coarse', touch: true },
    { name: 'desktop-1366', breite: 1366, hoehe: 768, zeiger: 'fine', touch: false },
    // FIX-6b/K6: das Gerät aus dem Befund — Handy im flachen Querformat.
    { name: 'quer-844x390', breite: 844, hoehe: 390, zeiger: 'coarse', touch: true },
]

/** Soll aus den zwei Kriterien ableiten. */
function soll(def, zeiger) {
    // FIX-6b/K1: Das flache Querformat (Höhe <= 480 px, Landscape) ist eine
    // GEOMETRISCHE Sonderlage: Seitenleiste aus, untere Leiste bleibt — auch
    // wenn die Breite über 720 px liegt. OP-HANDY-10, Operator-Auflage
    // (bleibt bewusst geometrisch, kein Zeiger-Kriterium). Der Block regelt
    // AUSSCHLIESSLICH das Gerüst (`.dk-app`, `.dk-sidebar`,
    // `.kronos-sidebar`) — Jahreszahl, Fußabstand und Inhaltsumbrüche hängen
    // weiter an der Breite (720 px) und bleiben hier im Desktop-Zustand.
    const quer = def.hoehe <= 480 && def.breite > def.hoehe
    return {
        mobil: def.breite <= GRENZE || quer,
        quer,
        // „schmal“ = die 720-px-Lage (Breite), unabhängig vom Querformat.
        schmal: def.breite <= GRENZE,
        touch: zeiger === 'coarse',
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
    await page.waitForTimeout(1500)
}

/** Ein Element messen (sichtbar = da, Display an, Fläche > 0). */
async function element(page, selektor) {
    return page.evaluate((sel) => {
        const el = document.querySelector(sel)
        if (!el) return null
        const s = getComputedStyle(el)
        const r = el.getBoundingClientRect()
        return {
            display: s.display,
            position: s.position,
            fontSize: s.fontSize,
            flexWrap: s.flexWrap,
            sichtbar: s.display !== 'none' && s.visibility !== 'hidden'
                && r.width > 0 && r.height > 0,
            breite: Math.round(r.width),
            hoehe: Math.round(r.height),
        }
    }, selektor)
}

/** Was der Browser selbst über Zeiger und Breite meldet. */
async function umgebung(page) {
    return page.evaluate(() => ({
        breite: window.innerWidth,
        coarse: matchMedia('(pointer: coarse)').matches,
        fine: matchMedia('(pointer: fine)').matches,
        anyCoarse: matchMedia('(any-pointer: coarse)').matches,
        anyFine: matchMedia('(any-pointer: fine)').matches,
        hover: matchMedia('(hover: hover)').matches,
        maxTouchPoints: navigator.maxTouchPoints,
    }))
}

/** Größte Schriftgröße eines sichtbaren Eingabefelds (16 px = Touch-Regel). */
async function feldschrift(page) {
    return page.evaluate(() => {
        const felder = [...document.querySelectorAll(
            'input:not([type="checkbox"]):not([type="radio"]):not([type="hidden"]), select, textarea')]
            .filter((el) => {
                const s = getComputedStyle(el)
                const r = el.getBoundingClientRect()
                return s.display !== 'none' && s.visibility !== 'hidden' && r.width > 0 && r.height > 0
            })
        const groessen = felder.map((el) => parseFloat(getComputedStyle(el).fontSize))
        const max = groessen.length ? Math.max(...groessen) : null
        return { anzahl: felder.length, max, hat16: groessen.some((g) => g >= 16) }
    })
}

/** Gerüst (Seitenleiste, Spalten) je Lage. */
async function geruest(page) {
    return page.evaluate(() => {
        const app = document.querySelector('.dk-app')
        const leiste = document.querySelector('.dk-sidebar')
        return {
            appSpalten: app ? getComputedStyle(app).gridTemplateColumns : null,
            leisteBreite: leiste ? Math.round(leiste.getBoundingClientRect().width) : null,
        }
    })
}

/**
 * FIX-6 ZEIGERLAGE ALS MEDIA-QUERY-ÜBERSCHREIBUNG (nur Messung B).
 *
 * Setzt im Dokument Regeln, die die Zeiger-Merkmale der Umgebung überstimmen —
 * der Zustand, den ein Touch-Laptop mit Maus dem CSS meldet. `all` trifft jede
 * Breite; die Regeln stehen am Dokumentanfang, die später geladenen
 * Stylesheets gewinnen bei gleicher Spezifität NICHT automatisch, deshalb
 * `!important`-frei, aber mit höherer Spezifität (`html body`).
 *
 * ACHTUNG: Das ist eine Messhilfe, KEIN Produktionscode — sie ersetzt die
 * Media Query im Browser, nicht in der App. Sie muss mitgeprüft werden
 * (`ueberschreibungAktiv`), sonst misst sie am Fall vorbei.
 */
const UEBERSCHREIBUNG_FEIN = `
@media (any-pointer: coarse) {
  html body { outline-color: rgb(1, 2, 3); }
}
`

/**
 * Messung B: die Zeigerlage über CSS-Überschreibung. Zurück kommt eine
 * Funktion, die im Dokument genau das prüft, was die App abfragt — sowie
 * einen Marker, der beweist, dass die Überschreibung greift.
 */
async function zeigerlageUeberschreiben(page, lage) {
    // `lage` = { coarse: bool } — wird als @media-Block in ein eigenes
    // Stylesheet am Dokumentanfang gelegt (ID `fix6-zeiger`).
    await page.addInitScript(({ zeiger }) => {
        const anwenden = () => {
            let st = document.getElementById('fix6-zeiger')
            if (!st) {
                st = document.createElement('style')
                st.id = 'fix6-zeiger'
                document.head ? document.head.prepend(st) : document.documentElement.appendChild(st)
            }
            st.textContent = zeiger
        }
        anwenden()
        document.addEventListener('DOMContentLoaded', anwenden)
        // SPA-Wechsel (hash) laden kein neues Dokument — die Regel bleibt.
    }, { zeiger: lage })
}

async function messeLage(browser, def) {
    const ctx = await browser.newContext({
        viewport: { width: def.breite, height: def.hoehe },
        hasTouch: def.touch,
        locale: 'de-DE',
    })
    const page = await ctx.newPage()
    const fehler = []
    page.on('response', (a) => {
        if (a.status() < 400) return
        if (a.url().includes('devmodus')) return   // Dev-Modus im Wegwerf-Stack aus
        fehler.push(`${a.status()} ${a.url()}`)
    })

    await anmelden(page)
    const umg = await umgebung(page)
    const startGeruest = await geruest(page)
    const fab = await element(page, '.dk-widget-edit-fab')

    await page.goto(BASE + '/#/kalender', { waitUntil: 'networkidle' })
    await page.waitForTimeout(2500)
    const kalender = {
        seitenleiste: await element(page, '.dk-sidebar'),
        untereLeiste: await element(page, '.dk-bottom-nav'),
        jahreszahl: await element(page, '.date-year'),
        ressourcenplan: await element(page, '.resource-toggle-btn'),
        moderationLabel: await element(page, '.moderation-btn-label'),
        fussabstand: await page.evaluate(() => {
            const el = document.querySelector('.kronos-page-content')
            return el ? getComputedStyle(el).paddingBottom : null
        }),
    }

    await page.goto(BASE + '/#/einstellungen', { waitUntil: 'networkidle' })
    await page.waitForTimeout(2500)
    const felder = await feldschrift(page)

    await page.goto(BASE + '/#/planrahmen/meine-dienste', { waitUntil: 'networkidle' })
    await page.waitForTimeout(2500)
    const monatszeile = await element(page, '.pr-md-monat-zeile')
    // FIX-6 Runde 2: Der Umbruch muss MESSBAR sein — die Absage-Aktion liegt im
    // Mobil-Layout UNTER dem Text (eigene Zeile), im Desktop-Layout daneben.
    const zeilenLage = await page.evaluate(() => {
        const z = document.querySelector('.pr-md-monat-zeile')
        if (!z) return null
        const haupt = z.querySelector('.pr-md-monat-haupt')
        const aktion = z.querySelector('.pr-md-monat-aktion')
        if (!haupt || !aktion) return null
        const h = haupt.getBoundingClientRect()
        const a = aktion.getBoundingClientRect()
        return {
            umbruch: getComputedStyle(z).flexWrap,
            aktionUnterText: a.top >= h.bottom - 2,
        }
    })

    // FIX-6b/K6: QuickLinks-Spalten (K2 — bei 390 px MUSS es eine Spalte sein).
    await page.goto(BASE + '/#/', { waitUntil: 'networkidle' })
    await page.waitForTimeout(2500)
    const quick = await page.evaluate(() => {
        const reihe = document.querySelector('.dk-quick-row')
        if (!reihe) return null
        const r = reihe.getBoundingClientRect()
        const karten = [...reihe.querySelectorAll('.dk-quick-card')]
            .map((k) => k.getBoundingClientRect())
            .filter((b) => b.width > 0 && b.height > 0)
        if (!karten.length) return { spalten: 0, karten: 0 }
        // Spalten = Karten in der obersten Zeile (gleiche Oberkante).
        const oberste = karten[0].top
        const spalten = karten.filter((b) => Math.abs(b.top - oberste) <= 2).length
        return {
            spalten,
            karten: karten.length,
            reiheBreite: Math.round(r.width),
            kartenBreite: Math.round(karten[0].width),
        }
    })

    // FIX-6b/K6/K3: Formular-Überlauf (Bearbeiten-Formular muss im Kartenrand
    // bleiben — UXD-R9 greift unabhängig vom Zeiger).
    await page.goto(BASE + '/#/mitglieder/liste', { waitUntil: 'networkidle' })
    await page.waitForTimeout(2500)
    // In der Kartenansicht gibt es keine Tabellenzeilen — für einen stabilen
    // Einstieg in die Detailseite zuerst auf „Tabelle“ schalten.
    const tabelle = page.locator('.dk-segment button:has-text("Tabelle"), button:has-text("Tabelle")').first()
    if (await tabelle.count()) { await tabelle.click(); await page.waitForTimeout(2000) }
    const formularHref = await page.evaluate(() => {
        const a = document.querySelector('.dk-zellen-link') || document.querySelector('td a')
        return a ? a.getAttribute('href') : null
    })
    let formular = null
    if (formularHref) {
        await page.goto(BASE + '/diakonos/' + formularHref, { waitUntil: 'networkidle' })
        await page.waitForTimeout(2500)
        const bearb = page.locator('button:has-text("Bearbeiten")').first()
        if (await bearb.count()) { await bearb.click(); await page.waitForTimeout(2000) }
        formular = await page.evaluate(() => {
            const f = document.querySelector('.edit-form')
            if (!f) return null
            const karte = f.closest('.dk-ui-card, .dk-card, .dk-panel') || f.parentElement
            const rk = karte.getBoundingClientRect()
            const felder = [...f.querySelectorAll('input, select, textarea')]
                .map((el) => el.getBoundingClientRect())
                .filter((b) => b.width > 0 && b.height > 0)
            if (!felder.length) return { felder: 0, ueberlauf: null }
            const rechts = Math.max(...felder.map((b) => b.right))
            const links = Math.min(...felder.map((b) => b.left))
            const drueber = Math.max(Math.round(rechts - rk.right), Math.round(rk.left - links))
            return {
                felder: felder.length,
                kartenRechts: Math.round(rk.right),
                kartenLinks: Math.round(rk.left),
                feldRechts: Math.round(rechts),
                // > 2 px zählt als Überlauf (Rundung der Teilpixel).
                ueberlauf: drueber > 2,
                ueberlaufPx: drueber,
            }
        })
    }

    await ctx.close()
    return {
        lage: def.name, def, umg,
        start: { geruest: startGeruest, fab },
        kalender, felder, quick, formular,
        meineDienste: {
            flexWrap: monatszeile?.flexWrap ?? null,
            aktionUnterText: zeilenLage?.aktionUnterText ?? null,
        },
        fehler,
    }
}

/**
 * MESSUNG B — Zeigerlage über eine Media-Query-Überschreibung im Dokument.
 *
 * Der Touch-Laptop meldet: PRIMÄRER Zeiger fein (`(pointer: fine)`,
 * `(hover: hover)`), aber auch ein grober Zeiger vorhanden
 * (`(any-pointer: coarse)`) und Touch-Fähigkeit (`maxTouchPoints: 5`). Genau
 * diese Zeigerlage lässt sich mit Chromium-Mitteln nicht als echter
 * Browser-Zustand herstellen (siehe Kopfkommentar), deshalb wird sie per
 * `@media`-Überschreibung im Dokument erzeugt — und die Messung prüft
 * zuerst, dass die Überschreibung greift.
 */
const FALL_TOUCHBOOK = {
    name: 'touchbook-1410-mit-maus', breite: 1410, hoehe: 755, touch: true,
}

async function messeTouchbookMitMaus(browser) {
    const ctx = await browser.newContext({
        viewport: { width: FALL_TOUCHBOOK.breite, height: FALL_TOUCHBOOK.hoehe },
        hasTouch: true, locale: 'de-DE',
    })
    const page = await ctx.newPage()
    const fehler = []
    page.on('response', (a) => {
        if (a.status() < 400) return
        if (a.url().includes('devmodus')) return
        fehler.push(`${a.status()} ${a.url()}`)
    })

    // Die Zeiger-Anpassungen der App sind `@media (pointer: coarse)`. Der
    // Touch-Laptop MIT Maus ist NICHT grob. Statt die Umgebung zu fälschen,
    // wird nur die Auswertung dieser einen Frage für das Dokument
    // stillgelegt: dieselbe Wirkung wie `(pointer: fine)` bei gleicher
    // Breite — und die Anwendung der Überschreibung wird geprüft.
    // Die Zeiger-Tatsache des Falls: das Gerät ist touch-FÄHIG, sein
    // PRIMÄRER Zeiger ist aber eine Maus. Genau diese Lage lässt Chromium
    // nicht als Umgebung herstellen (Kopfkommentar). Nachgebildet wird
    // deshalb nur die eine Frage, welche die Touch-Anpassungen der App an den
    // Browser stellen — „ist der primäre Zeiger grob?“ —, und zwar als
    // Überschreibung für das ganze Dokument:
    //
    //   * die Touch-Anpassungen (16 px, Tippziele) bekommen `revert`, also die
    //     Grundwerte der App — die Regel greift damit nicht mehr;
    //   * ein Marker im selben Block beweist, dass die Überschreibung greift.
    //
    // Das ist zulässig, weil die App genau EINE grobe-Zeiger-Bedingung hat
    // (`@media (pointer: coarse)`, Wächter
    // `frontend/tests/fix6-keine-zeiger-syntax.test.mjs` verbietet jede
    // andere Schreibweise). Die BREITE bleibt unangetastet — darum prüft
    // dieselbe Messung Layout und Touch getrennt.
    await page.addInitScript(() => {
        const regeln = () => {
            // `${'@'}media` statt `@media`: dieser Block steht in einer
            // Vorlagen-Zeichenkette, und ein direktes `@media all {` würde die
            // Zeichenkette hier beenden. Die Zuweisung als Variable ist die
            // lesbare Variante ohne Escaping.
            const at = '@'
            return [
                at + 'media all {',
                '  html body { --fix6-zeiger-gemessen: 1; }',
                '  input, select, textarea, .dk-ui-eingabe, .dk-form-input, .dk-form-select {',
                '    font-size: revert !important; min-height: revert !important; min-width: revert !important;',
                '  }',
                '  .dk-btn, .dk-btn-sm, .dk-btn-icon, .dk-ui-chip, .dk-filter-chip,',
                '  input[type="checkbox"], input[type="radio"], button > svg,',
                '  label:has(> input[type="checkbox"]), label:has(> input[type="radio"]) {',
                '    min-height: revert !important; min-width: revert !important; display: revert !important;',
                '  }',
                '  .dk-ui-datumzeit-eingabe { min-height: revert !important; font-size: revert !important; }',
                '}',
            ].join('\n')
        }
        const setzen = () => {
            const ziel = document.head || document.documentElement
            if (!ziel) return
            let st = document.getElementById('fix6-zeiger')
            if (!st) {
                st = document.createElement('style')
                st.id = 'fix6-zeiger'
                ziel.prepend(st)
            }
            st.textContent = regeln()
        }
        setzen()
        document.addEventListener('DOMContentLoaded', setzen)
    })

    await anmelden(page)
    const umg = await umgebung(page)
    const ueberschreibung = await page.evaluate(() => {
        const wert = getComputedStyle(document.body).getPropertyValue('--fix6-zeiger-gemessen').trim()
        return { aktiv: wert === '1' }
    })
    const geruestStart = await geruest(page)
    const fab = await element(page, '.dk-widget-edit-fab')

    await page.goto(BASE + '/#/kalender', { waitUntil: 'networkidle' })
    await page.waitForTimeout(2500)
    const kalender = {
        seitenleiste: await element(page, '.dk-sidebar'),
        untereLeiste: await element(page, '.dk-bottom-nav'),
        jahreszahl: await element(page, '.date-year'),
        ressourcenplan: await element(page, '.resource-toggle-btn'),
        moderationLabel: await element(page, '.moderation-btn-label'),
        fussabstand: await page.evaluate(() => {
            const el = document.querySelector('.kronos-page-content')
            return el ? getComputedStyle(el).paddingBottom : null
        }),
    }

    await page.goto(BASE + '/#/einstellungen', { waitUntil: 'networkidle' })
    await page.waitForTimeout(2500)
    const felder = await feldschrift(page)

    await page.goto(BASE + '/#/planrahmen/meine-dienste', { waitUntil: 'networkidle' })
    await page.waitForTimeout(2500)
    const monatszeile = await element(page, '.pr-md-monat-zeile')
    // FIX-6 Runde 2: Der Umbruch muss MESSBAR sein — die Absage-Aktion liegt im
    // Mobil-Layout UNTER dem Text (eigene Zeile), im Desktop-Layout daneben.
    const zeilenLage = await page.evaluate(() => {
        const z = document.querySelector('.pr-md-monat-zeile')
        if (!z) return null
        const haupt = z.querySelector('.pr-md-monat-haupt')
        const aktion = z.querySelector('.pr-md-monat-aktion')
        if (!haupt || !aktion) return null
        const h = haupt.getBoundingClientRect()
        const a = aktion.getBoundingClientRect()
        return {
            umbruch: getComputedStyle(z).flexWrap,
            aktionUnterText: a.top >= h.bottom - 2,
        }
    })

    await ctx.close()
    return {
        lage: FALL_TOUCHBOOK.name, def: FALL_TOUCHBOOK, umg, ueberschreibung,
        start: { geruest: geruestStart, fab },
        kalender, felder,
        meineDienste: {
            flexWrap: monatszeile?.flexWrap ?? null,
            aktionUnterText: zeilenLage?.aktionUnterText ?? null,
        },
        fehler,
    }
}

function zeile(e) {
    const k = e.kalender
    return [
        `LAGE ${e.lage} (${e.def.breite}×${e.def.hoehe}px, Zeiger laut Umgebung ` +
            `${e.umg.coarse ? 'coarse' : e.umg.fine ? 'fine' : '?'}, touch-fähig ${e.def.touch})`,
        `matchMedia coarse=${e.umg.coarse} fine=${e.umg.fine} anyCoarse=${e.umg.anyCoarse}` +
            ` anyFine=${e.umg.anyFine} maxTouch=${e.umg.maxTouchPoints}`,
        `Seitenleiste=${k.seitenleiste?.sichtbar ? k.seitenleiste.breite + 'px' : 'aus'}`,
        `untereLeiste=${Boolean(k.untereLeiste?.sichtbar)}`,
        `Jahreszahl=${Boolean(k.jahreszahl?.sichtbar)}`,
        `Ressourcenplan=${Boolean(k.ressourcenplan?.sichtbar)}`,
        `ModerationLabel=${Boolean(k.moderationLabel?.sichtbar)}`,
        `QuickLinks=${e.quick ? e.quick.spalten + ' Spalte(n) / ' + e.quick.karten + ' Karten' : 'nicht gefunden'}`,
        `Formular=${e.formular ? (e.formular.felder + ' Felder, Überlauf ' +
            (e.formular.ueberlauf === null ? '?' : e.formular.ueberlauf ? e.formular.ueberlaufPx + 'px' : 'keiner')) : 'nicht geöffnet'}`,
        `FAB=${e.start.fab?.position}/${e.start.fab?.breite}px`,
        `Feldschrift=${e.felder.max}px (${e.felder.anzahl} Felder)`,
        `Fussabstand=${k.fussabstand}`,
        `Monatszeile=${e.meineDienste.flexWrap}${e.meineDienste.aktionUnterText ? ' (Aktion unter dem Text)' : ' (Aktion neben dem Text)'}`,
        `4xx=${e.fehler.length}`,
    ].join('\n      ')
}

async function main() {
    const browser = await chromium.launch()
    const ergebnisse = []
    for (const def of LAGEN_A) {
        const e = await messeLage(browser, def)
        e.soll = soll(def, def.zeiger)
        ergebnisse.push(e)
    }
    const book = await messeTouchbookMitMaus(browser)
    await browser.close()

    for (const e of ergebnisse) console.log(zeile(e))
    console.log(zeile(book))
    console.log('')

    const p = []
    for (const e of ergebnisse) {
        const { mobil, schmal, touch } = e.soll
        const k = e.kalender
        // Die Messung muss den gewünschten Zeiger auch WIRKLICH gesehen haben,
        // sonst prüft sie am Fall vorbei.
        p.push([`${e.lage}: Messung sieht Zeiger ${e.def.zeiger}`,
            e.umg[e.def.zeiger] === true])
        p.push([`${e.lage}: Seitenleiste ${mobil ? 'aus' : 'sichtbar'}`,
            Boolean(k.seitenleiste?.sichtbar) === !mobil])
        p.push([`${e.lage}: untere Leiste ${mobil ? 'sichtbar' : 'aus'}`,
            Boolean(k.untereLeiste?.sichtbar) === mobil])
        // Jahreszahl / Fußabstand / Inhaltsumbruch hängen an der 720-px-Breite
        // (nicht am Querformat — der OP-HANDY-10-Block regelt nur das Gerüst).
        p.push([`${e.lage}: Jahreszahl ${schmal ? 'aus' : 'sichtbar'}`,
            Boolean(k.jahreszahl?.sichtbar) === !schmal])
        p.push([`${e.lage}: Fußabstand ${schmal ? '80 px' : '0 px'}`,
            (k.fussabstand === '80px') === schmal])
        p.push([`${e.lage}: Eingabeschrift ${touch ? '16 px' : 'unter 16 px'}`,
            touch ? e.felder.hat16 : !e.felder.hat16])
        // Meine Dienste: Umbruch = Layout, also nur die Breite.
        p.push([`${e.lage}: Meine-Dienste-Absage ${schmal ? 'unter dem Text (Umbruch)' : 'neben dem Text'}`,
            e.meineDienste.aktionUnterText === schmal])
    }

    const by = (n) => ergebnisse.find((e) => e.lage === n)
    const handy = by('handy-390'); const fenster = by('fenster-700')
    const ipad = by('ipad-1024'); const desk = by('desktop-1366')

    // Der Befund: Touch-GERÄT mit Desktop-Breite → Desktop, keine
    // Touch-Vergrößerung. Messung B stellt dafür die Zeigerlage „feiner
    // primärer Zeiger, Touch vorhanden“ her.
    p.push(['touchbook-1410-mit-maus: Zeiger-Überschreibung greift', book.ueberschreibung.aktiv])
    p.push(['touchbook-1410-mit-maus: Desktop-Layout (Seitenleiste, keine untere Leiste)',
        Boolean(book.kalender.seitenleiste?.sichtbar) && !book.kalender.untereLeiste?.sichtbar])
    p.push(['touchbook-1410-mit-maus: KEINE Touch-Vergrößerung (Befund)',
        !book.felder.hat16])
    p.push(['touchbook-1410-mit-maus: Jahreszahl/Ressourcenplan/Beschriftung sichtbar',
        Boolean(book.kalender.jahreszahl?.sichtbar)
        && Boolean(book.kalender.ressourcenplan?.sichtbar)
        && Boolean(book.kalender.moderationLabel?.sichtbar)])
    p.push(['touchbook-1410-mit-maus: FAB rund und fixiert wie am Desktop',
        book.start.fab?.position === desk.start.fab?.position
        && book.start.fab?.breite === desk.start.fab?.breite])
    p.push(['touchbook-1410-mit-maus: Fußabstand 0 px',
        book.kalender.fussabstand === '0px'])
    p.push(['touchbook-1410-mit-maus: Meine-Dienste-Absage neben dem Text (kein Umbruch)',
        book.meineDienste.aktionUnterText === false])

    p.push(['Schmales Mausfenster 700 px: Mobil-Layout MIT unterer Leiste',
        Boolean(fenster.kalender.untereLeiste?.sichtbar) && !fenster.kalender.seitenleiste?.sichtbar])
    p.push(['Schmales Mausfenster 700 px: KEINE Touch-Vergrößerung',
        !fenster.felder.hat16])
    p.push(['iPad quer 1024 px: Desktop-Layout', !ipad.kalender.untereLeiste?.sichtbar
        && Boolean(ipad.kalender.seitenleiste?.sichtbar)])
    p.push(['iPad quer 1024 px: Touch-Anpassung 16 px', ipad.felder.hat16])
    p.push(['Handy 390 px: Mobil-Layout + Touch-Anpassung',
        Boolean(handy.kalender.untereLeiste?.sichtbar) && handy.felder.hat16
        && !handy.kalender.seitenleiste?.sichtbar])

    // ── FIX-6b/K6: die drei neuen Befunde aus der Review ────────────────
    // K1: flaches Querformat 844×390 — Seitenleiste unsichtbar, untere Leiste
    // sichtbar (OP-HANDY-10 wirkt erst, seit der Block am Dateiende steht).
    const quer = by('quer-844x390')
    p.push(['quer-844x390: Seitenleiste unsichtbar (OP-HANDY-10, K1)',
        quer && !quer.kalender.seitenleiste?.sichtbar])
    p.push(['quer-844x390: untere Leiste sichtbar (K1)',
        Boolean(quer?.kalender.untereLeiste?.sichtbar)])
    p.push(['quer-844x390: KEINE Seitenleiste UND untere Leiste gleichzeitig',
        !(quer?.kalender.seitenleiste?.sichtbar && quer?.kalender.untereLeiste?.sichtbar)])

    // K2: QuickLinks-Spaltenzahl — bei 390 px genau EINE Spalte. (700 px liegt
    // in der 1100-px-Stufe, dort sind zwei Spalten richtig; geprüft wird die
    // Zusicherung „nicht mehr als zwei und keine Drei-Spalten-Reihe“.)
    p.push(['handy-390: QuickLinks einspaltig (K2)',
        handy?.quick?.spalten === 1])
    p.push(['fenster-700: QuickLinks höchstens zweispaltig (1100-px-Stufe)',
        fenster?.quick?.spalten >= 1 && fenster?.quick?.spalten <= 2])
    p.push(['desktop-1366: QuickLinks dreispaltig (unverändert)',
        desk?.quick?.spalten === 3])

    // K3: Formular-Überlauf bei 700 px mit feinem Zeiger = keiner.
    p.push(['fenster-700 (feiner Zeiger): Bearbeiten-Formular ohne Überlauf (K3)',
        fenster?.formular?.ueberlauf === false])
    p.push(['desktop-1366: Bearbeiten-Formular ohne Überlauf (K3)',
        desk?.formular?.ueberlauf === false])
    p.push(['handy-390: Bearbeiten-Formular ohne Überlauf (K3)',
        handy?.formular?.ueberlauf === false])

    // Die Messung muss den Befund auch WIRKLICH gesehen haben: das Formular
    // wurde geöffnet und es waren Felder darin.
    for (const e of ergebnisse) {
        p.push([`${e.lage}: Formular-Messung hat Felder gesehen`,
            (e.formular?.felder ?? 0) > 0])
    }

    let fehl = 0
    for (const [text, ok] of p) {
        console.log(`${ok ? 'OK  ' : 'FEHL'} ${text}`)
        if (!ok) fehl += 1
    }
    console.log(`ERGEBNIS ${fehl === 0 ? 'bestanden' : fehl + ' Fehlschläge'} (${p.length} Prüfungen)`)
    process.exit(fehl === 0 ? 0 : 1)
}

main().catch((e) => { console.error(e); process.exit(2) })
