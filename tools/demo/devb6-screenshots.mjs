/**
 * DEV-B6 — Screenshots: die Handy-Leiste darf am Laptop NIE kommen.
 *
 * Lagen (Operator/Manuel 09.11.):
 *   laptop-702x894    702×894, feiner Zeiger  → Befund: KEINE Leiste,
 *                                               Seitenleiste (eingeklappt)
 *   fenster-400x800   400×800, feiner Zeiger  → KEINE Leiste
 *   handy-390coarse   390×844, grober Zeiger  → Leiste da (Gegenprobe)
 *   handy-quer-844    844×390, grober Zeiger  → Leiste da (OP-HANDY-10)
 *
 * Je Lage hell und dunkel. Gemessen wird zusätzlich die Sichtbarkeit der
 * Gerüst-Teile (Leiste, Seitenleiste, Menü-Knopf, Fußabstand, Kalender-Spalte)
 * und das Ergebnis als JSON neben die Bilder geschrieben.
 *
 * DEV-B6b (Review-Nacharbeit 10.11., Punkt 7) zusätzlich je Lage:
 *   * Strg+K: Palette geöffnet — Hülle fixiert und abgedunkelt (Punkt 2),
 *     Bild `…-palette.png`, Messung `palette`.
 *   * Kalender-Knopf: was öffnet sich (Popover oder Liste), wo steht die
 *     Liste (linke Kante — Punkt 3: `MEINE KALENDER` darf nicht über die
 *     App-Seitenleiste ragen), Bild `…-kalenderliste.png`.
 *   * Rechte Kanten aller sichtbaren Elemente (Punkt 4: `overflow: hidden`
 *     versteckt abgeschnittenen Inhalt) — `kanten`.
 *   * Navigation Start→Kalender: die Seite muss danach den Kalender zeigen.
 *
 * Aufruf (playwright wird im Abbild unter /tmp/pw nachinstalliert):
 *   docker run --rm --network devb6_default -v "<repo>":/w:ro -v "<ziel>":/ausgabe \
 *       -e DEVB6_BASE=http://app:8000 mcr.microsoft.com/playwright:v1.49.0-noble \
 *       sh -c 'npm i -s --prefix /tmp/pw playwright@1.49.0 >/dev/null 2>&1;
 *              export NODE_PATH=/tmp/pw/node_modules;
 *              node /w/tools/demo/devb6-screenshots.mjs'
 */
import { mkdirSync, writeFileSync } from 'node:fs'
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
const { chromium } = require('playwright')

const BASE = (process.env.DEVB6_BASE || 'http://app:8000').replace(/\/$/, '')
const ZIEL = process.env.ZIEL || '/ausgabe'
const EMAIL = process.env.ADMIN_EMAIL || 'admin@example.org'
const PASSWORT = process.env.ADMIN_PASS || 'musterhausen-demo'

const LAGEN = [
    { name: 'laptop-702x894-fine', breite: 702, hoehe: 894, touch: false },
    { name: 'fenster-400x800-fine', breite: 400, hoehe: 800, touch: false },
    // Review-Punkt 2: flaches Fenster mit MAUS — die Querformat-Alternative
    // prüft den Zeiger mit, hier darf NIE eine Leiste erscheinen.
    { name: 'laptop-flach-1280x450-fine', breite: 1280, hoehe: 450, touch: false },
    { name: 'handy-390-coarse', breite: 390, hoehe: 844, touch: true },
    { name: 'handy-quer-844x390-coarse', breite: 844, hoehe: 390, touch: true },
    { name: 'desktop-1440-fine', breite: 1440, hoehe: 900, touch: false },
]
const SEITEN = [
    { name: 'start', pfad: '/#/' },
    { name: 'kalender', pfad: '/#/kalender' },
]

async function info(page, selektor) {
    return page.evaluate((sel) => {
        const el = document.querySelector(sel)
        if (!el) return null
        const s = getComputedStyle(el)
        const r = el.getBoundingClientRect()
        return {
            display: s.display,
            sichtbar: s.display !== 'none' && s.visibility !== 'hidden' && r.width > 0 && r.height > 0,
            breite: Math.round(r.width),
            hoehe: Math.round(r.height),
        }
    }, selektor)
}

async function main() {
    mkdirSync(ZIEL, { recursive: true })
    const browser = await chromium.launch()
    const bericht = []
    for (const lage of LAGEN) {
        for (const thema of ['hell', 'dunkel']) {
            const ctx = await browser.newContext({
                viewport: { width: lage.breite, height: lage.hoehe },
                hasTouch: lage.touch,
                isMobile: false,
                locale: 'de-DE',
                colorScheme: thema === 'dunkel' ? 'dark' : 'light',
            })
            const page = await ctx.newPage()
            await page.goto(BASE + '/#/', { waitUntil: 'networkidle' })
            const feld = page.locator('input[name="usr"], #dk-usr')
            if (await feld.count()) {
                await feld.first().fill(EMAIL)
                await page.fill('input[name="pwd"], #dk-pwd', PASSWORT)
                await page.click('button[type="submit"]')
                await page.waitForLoadState('networkidle')
            }
            await page.evaluate((t) => {
                localStorage.setItem('dk-theme', t === 'dunkel' ? 'dark' : 'light')
                document.documentElement.setAttribute('data-theme', t)
            }, thema)
            for (const seite of SEITEN) {
                await page.goto(BASE + seite.pfad, { waitUntil: 'networkidle' })
                // Warten, bis die App-Hülle steht: die untere Leiste liegt
                // immer im DOM (das CSS macht sie unsichtbar), die
                // Seitenleiste ebenso. Vorher gemessen = leere Werte.
                await page.waitForSelector('nav.dk-bottom-nav', { state: 'attached', timeout: 30000 })
                await page.waitForSelector('aside.dk-sidebar', { state: 'attached', timeout: 30000 })
                await page.waitForTimeout(1200)
                const messung = {
                    lage: lage.name, thema, seite: seite.name,
                    breite: await page.evaluate(() => window.innerWidth),
                    zeiger: await page.evaluate(() => ({
                        fine: matchMedia('(pointer: fine)').matches,
                        coarse: matchMedia('(pointer: coarse)').matches,
                    })),
                    leiste: await info(page, '.dk-bottom-nav'),
                    seitenleiste: await info(page, '.dk-sidebar'),
                    menueKnopf: await info(page, '.dk-menue-knopf'),
                    fussabstand: await page.evaluate(() => {
                        const el = document.querySelector('#dk-inhalt')
                        return el ? getComputedStyle(el).paddingBottom : null
                    }),
                    kalenderRechts: await info(page, '.kal-pruef-panel'),
                    // DEV-B6 (Review-Punkt 5): Werkzeugzeile muss erreichbar
                    // bleiben (nicht aus dem Kopf gerutscht) und die Startseite
                    // darf waagerecht nicht überlaufen.
                    werkzeuge: await page.evaluate(() => {
                        const kopf = document.querySelector('.kronos-header')
                        if (!kopf) return null
                        const r = kopf.getBoundingClientRect()
                        const knopf = [...kopf.querySelectorAll('button')].map((b) => {
                            const q = b.getBoundingClientRect()
                            return { text: (b.getAttribute('aria-label') || b.textContent || '').trim().slice(0, 24),
                                imBild: q.left >= -1 && q.right <= window.innerWidth + 1 && q.width > 0 }
                        })
                        return { kopfBreite: Math.round(r.width), ueberKopf: Math.round(r.bottom) > window.innerHeight, knopf }
                    }),
                    ueberlauf: await page.evaluate(() => ({
                        scroller: document.scrollingElement ? document.scrollingElement.scrollWidth : null,
                        fenster: window.innerWidth,
                    })),
                    liste: await info(page, '.kronos-sidebar-inpage'),
                    navEinstiege: await page.evaluate(() => ({
                        menueKnopf: [...document.querySelectorAll('.dk-menue-knopf')]
                            .filter((e) => getComputedStyle(e).display !== 'none').length,
                        listenUmschalter: [...document.querySelectorAll('.sidebar-toggle-btn')]
                            .filter((e) => getComputedStyle(e).display !== 'none').length,
                    })),
                }
                // ── Punkt 4: rechte Kanten (Abschneiden sichtbar machen) ──
                messung.kanten = await page.evaluate(() => {
                    const aussen = []
                    const grenze = window.innerWidth + 1
                    for (const el of document.querySelectorAll('#dk-inhalt *')) {
                        const s = getComputedStyle(el)
                        if (s.display === 'none' || s.visibility === 'hidden') continue
                        const r = el.getBoundingClientRect()
                        if (r.width <= 0 || r.height <= 0) continue
                        if (r.right <= grenze && r.left >= -1) continue
                        aussen.push({
                            tag: el.tagName.toLowerCase(),
                            klasse: (el.className && String(el.className).trim().slice(0, 60)) || '',
                            links: Math.round(r.left), rechts: Math.round(r.right),
                        })
                        if (aussen.length >= 8) break
                    }
                    return { fenster: window.innerWidth, ueberstand: aussen }
                })

                // ── Punkt 2: Strg+K — Palette (Hülle fixiert + abgedunkelt) ──
                await page.keyboard.press('Control+k')
                await page.waitForTimeout(600)
                messung.palette = await page.evaluate(() => {
                    const huelle = document.querySelector('.dk-palette-huelle')
                    if (!huelle) return { offen: false }
                    const s = getComputedStyle(huelle)
                    const r = huelle.getBoundingClientRect()
                    return {
                        offen: true,
                        position: s.position,
                        hintergrund: s.backgroundColor,
                        decktFenster: r.width >= window.innerWidth - 1 && r.height >= window.innerHeight - 1,
                        zeilenHoehe: (() => {
                            const z = document.querySelector('.dk-palette-zeile')
                            return z ? Math.round(z.getBoundingClientRect().height) : null
                        })(),
                        paletteBreite: (() => {
                            const p = document.querySelector('.dk-palette')
                            return p ? Math.round(p.getBoundingClientRect().width) : null
                        })(),
                    }
                })
                if (messung.palette.offen) {
                    const d = `${lage.name}-${thema}-${seite.name}-palette.png`
                    await page.screenshot({ path: `${ZIEL}/${d}`, fullPage: false })
                    messung.dateiPalette = d
                    await page.keyboard.press('Escape')
                    await page.waitForTimeout(300)
                }

                // ── Punkt 3: der EINE Weg zur Kalenderliste ──
                if (seite.name === 'kalender') {
                    const knopf = page.locator('[data-kalender-ausloeser][data-kalender-sichtbar="1"]')
                        .or(page.locator('[data-kalender-ausloeser]'))
                    messung.kalenderliste = { knopfGefunden: await knopf.count() > 0 }
                    if (messung.kalenderliste.knopfGefunden) {
                        await knopf.first().click()
                        await page.waitForTimeout(700)
                        messung.kalenderliste.zustand = await page.evaluate(() => {
                            const liste = document.querySelector('.kronos-sidebar-inpage')
                            const pop = document.querySelector('.kal-auswahl, [role="dialog"].kal-auswahl')
                            const r = liste ? liste.getBoundingClientRect() : null
                            const popSichtbar = pop ? getComputedStyle(pop).display !== 'none' : false
                            return {
                                popover: popSichtbar,
                                listeOffen: liste ? liste.classList.contains('open') : null,
                                listePosition: liste ? getComputedStyle(liste).position : null,
                                listeLinks: r ? Math.round(r.left) : null,
                                listeBreite: r ? Math.round(r.width) : null,
                                seitenleisteBreite: (() => {
                                    const sb = document.querySelector('aside.dk-sidebar')
                                    if (!sb) return 0
                                    const q = sb.getBoundingClientRect()
                                    return getComputedStyle(sb).display === 'none' ? 0 : Math.round(q.width)
                                })(),
                            }
                        })
                        const d = `${lage.name}-${thema}-${seite.name}-kalenderliste.png`
                        await page.screenshot({ path: `${ZIEL}/${d}`, fullPage: false })
                        messung.dateiKalenderliste = d
                        // Wieder schließen, damit die nächste Lage sauber startet.
                        await page.keyboard.press('Escape')
                        await page.mouse.click(5, 5)
                        await page.waitForTimeout(300)
                    }
                }

                const datei = `${lage.name}-${thema}-${seite.name}.png`
                await page.screenshot({ path: `${ZIEL}/${datei}`, fullPage: false })
                messung.datei = datei
                bericht.push(messung)
                console.log(JSON.stringify(messung))
            }
            await ctx.close()
        }
    }
    writeFileSync(`${ZIEL}/messung.json`, JSON.stringify(bericht, null, 2))
    await browser.close()
}

main().catch((e) => { console.error(e); process.exit(1) })
