/**
 * FIX-6 — Screenshots vorher/nachher (Befund DMB-d446e449ba22).
 *
 * Drei Lagen, je hell und dunkel:
 *   maus-desktop   1410×755, kein Touch      (Referenz)
 *   touch-notebook 1410×755, hasTouch=true   (der Befund)
 *   handy           390×844, hasTouch=true   (Gegenprobe: mobil bleibt mobil)
 *
 * Aufruf (playwright wird im Abbild unter /tmp/pw nachinstalliert):
 *   docker run --rm --network <netz> -v "<repo>":/w:ro -v "<ziel>":/ausgabe \
 *       -e FIX6_BASE=http://app:8000 -e MARKER=vorher \
 *       mcr.microsoft.com/playwright:v1.49.0-noble sh -c \
 *       'npm i -s --prefix /tmp/pw playwright@1.49.0 >/dev/null 2>&1;
 *        export NODE_PATH=/tmp/pw/node_modules;
 *        node /w/tools/demo/fix6-screenshots.mjs'
 */
import { mkdirSync } from 'node:fs'
import { join } from 'node:path'
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
const { chromium } = require('playwright')

const BASE = (process.env.FIX6_BASE || 'http://app:8000').replace(/\/$/, '')
const ZIEL = process.env.ZIEL || '/ausgabe'
const MARKER = process.env.MARKER || 'jetzt'
const EMAIL = process.env.ADMIN_EMAIL || 'admin@example.org'
const PASSWORT = process.env.ADMIN_PASS || 'musterhausen-demo'

/** Lagen der Matrix (Operator 27.10.): Breite trifft das Layout, der Zeiger
 *  (`hasTouch`) die Touch-Anpassungen. */
const LAGEN = [
    { name: 'handy-390-coarse', breite: 390, hoehe: 844, touch: true },
    { name: 'fenster-700-fine', breite: 700, hoehe: 800, touch: false },
    { name: 'ipad-1024-coarse', breite: 1024, hoehe: 768, touch: true },
    { name: 'touch-notebook-1410', breite: 1410, hoehe: 755, touch: true },
    { name: 'desktop-1366-fine', breite: 1366, hoehe: 768, touch: false },
    // FIX-6b/K1: das Gerät aus dem Befund (flaches Querformat 844×390).
    { name: 'quer-844x390', breite: 844, hoehe: 390, touch: true },
]

const SEITEN = [
    { name: 'start', pfad: '/#/' },
    { name: 'kalender', pfad: '/#/kalender' },
    { name: 'meine-dienste', pfad: '/#/planrahmen/meine-dienste' },
]

async function main() {
    mkdirSync(ZIEL, { recursive: true })
    const browser = await chromium.launch()
    for (const lage of LAGEN) {
        for (const thema of ['hell', 'dunkel']) {
            const ctx = await browser.newContext({
                viewport: { width: lage.breite, height: lage.hoehe },
                hasTouch: lage.touch,
                locale: 'de-DE',
                colorScheme: thema === 'dunkel' ? 'dark' : 'light',
            })
            // Der Zeiger folgt `hasTouch` (siehe fix6-zeigegeraet.mjs): hier
            // wird NICHTS per matchMedia-Attrappe erzwungen.
            const page = await ctx.newPage()
            await page.goto(BASE + '/#/', { waitUntil: 'networkidle' })
            const feld = page.locator('input[name="usr"], #dk-usr')
            if (await feld.count()) {
                await feld.first().fill(EMAIL)
                await page.fill('input[name="pwd"], #dk-pwd', PASSWORT)
                await page.click('button[type="submit"]')
                await page.waitForLoadState('networkidle')
            }
            // Thema fest setzen (die App merkt sich die Wahl im localStorage).
            // Das Theme merkt sich die App im localStorage unter 'dk-theme'
            // als ROHEN Wert ('hell' | 'dunkel', siehe composables/theme.mjs) —
            // ein JSON-String kam dort nie an, die Seiten blieben deshalb im
            // Hellmodus (Befund der Sichtprüfung t_fba1a868: „dunkel" war
            // nicht dunkel). Beim ersten Laden VOR dem Skript setzen, damit
            // die App den Wert beim Start liest.
            await page.evaluate((t) => {
                localStorage.setItem('dk-theme', t === 'dunkel' ? 'dark' : 'light')
                document.documentElement.setAttribute('data-theme', t)
            }, thema)
            for (const seite of SEITEN) {
                await page.goto(BASE + seite.pfad, { waitUntil: 'networkidle' })
                await page.waitForTimeout(2000)
                await page.evaluate((t) => {
                    document.documentElement.setAttribute('data-theme', t)
                }, thema)
                await page.waitForTimeout(300)
                const datei = join(ZIEL, `${MARKER}-${seite.name}-${lage.name}-${thema}.png`)
                await page.screenshot({ path: datei, fullPage: false })
                console.log('BILD ' + datei)
            }
            await ctx.close()
        }
    }
    await browser.close()
}

main().catch((e) => { console.error(e); process.exit(2) })
