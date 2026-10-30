/**
 * FIX-1 (t_01b2d285) — Aufnahme „Mehr“-Blatt am Handy: offen und geschlossen.
 *
 * Befund DMB-a2d846875201 (Route #/profile, Viewport 344x561): „Einklappen
 * nicht möglich, nur durch Auswahl eines Elements möglich“. Aufgenommen wird
 * genau dieses Gerätemaß, je hell und dunkel:
 *
 *   offen      — Blatt geöffnet (Tipp auf „Mehr“)
 *   kopf-zu    — Tippen auf den Blattkopf (Griff/„Navigation“/Pfeil)
 *   aussen-zu  — Tippen außerhalb (Überlappung)
 *   escape-zu  — Escape
 *   mehr-zu    — zweiter Tipp auf „Mehr“
 *
 * Zu jedem Schritt landen Messwerte in `<marke>-messung.json` (Blatt offen?
 * Kopf vorhanden? Höhe in px? aria-label/aria-expanded?) — der Nachweis
 * besteht nicht nur aus Bildern.
 *
 * Aufruf (playwright wird im Abbild unter /tmp/pw nachinstalliert, die
 * Browser liegen bereits unter /ms-playwright):
 *   docker run --rm --network <netz> -v "<repo>":/w:ro -v "<ziel>":/ausgabe \
 *       --name fix1-shots -e FIX1_BASE=http://app:8000 \
 *       mcr.microsoft.com/playwright:v1.49.0-noble sh -c \
 *       'export NODE_PATH=/tmp/pw/node_modules; node /w/tools/demo/fix1-mehr-blatt.mjs --marke nachher'
 */
import { mkdirSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
// playwright wird erst zur Laufzeit installiert (siehe Kopf) — der Pfad kommt
// über NODE_PATH; createRequire löst ihn genauso auf.
const { chromium } = require('playwright')

const BASE = process.env.FIX1_BASE || 'http://app:8000'
const ZIEL = process.env.ZIEL || '/ausgabe'
const EMAIL = process.env.MITGLIED_EMAIL || 'admin@example.org'
const PASSWORT = process.env.MITGLIED_PASS || 'musterhausen-demo'
const SEITE = process.env.FIX1_SEITE || '/diakonos#/profile'

// Befund: Viewport 344x561 (schmales Handy, Touch).
const BREITE = 344
const HOEHE = 561

const argMarke = process.argv.indexOf('--marke')
const MARKE = argMarke > 0 ? process.argv[argMarke + 1] : 'nachher'

const fehler = []
const messungen = []

async function anmelden(page) {
  await page.goto(BASE + '/diakonos', { waitUntil: 'domcontentloaded' })
  await page.waitForTimeout(800)
  const mailFeld = page.locator('input[type=email], input[name=email], input[autocomplete=username]')
  if (await mailFeld.count()) await mailFeld.first().fill(EMAIL)
  const pw = page.locator('input[type=password]')
  if (!(await pw.count())) throw new Error('Anmeldemaske nicht gefunden')
  await pw.first().fill(PASSWORT)
  await page.locator("button[type=submit], button:has-text('Anmelden'), button:has-text('Einloggen')").first().click()
  await page.waitForTimeout(3000)
}

async function zustand(page) {
  return page.evaluate(() => {
    const blatt = document.querySelector('.dk-bn-sheet')
    const kopf = document.querySelector('.dk-bn-sheet-kopf')
    const overlay = document.querySelector('.dk-bn-sheet-overlay')
    const theme = document.querySelector('.dk-bn-sheet-theme')
    const griff = document.querySelector('.dk-bn-sheet-handle')
    const r = kopf ? kopf.getBoundingClientRect() : null
    // Operator-Review: der Griffstrich war unsichtbar (span ohne display:block).
    // Gemessen wird die gerenderte Fläche — 0 px hoch/breit = nicht zu sehen.
    const g = griff ? griff.getBoundingClientRect() : null
    const gStil = griff ? getComputedStyle(griff) : null
    return {
      blattOffen: !!blatt,
      overlayOffen: !!overlay,
      themeZeileSichtbar: !!theme,
      kopfVorhanden: !!kopf,
      kopfTag: kopf ? kopf.tagName.toLowerCase() : null,
      kopfAriaLabel: kopf ? kopf.getAttribute('aria-label') : null,
      kopfAriaExpanded: kopf ? kopf.getAttribute('aria-expanded') : null,
      kopfHoehe: r ? Math.round(r.height) : 0,
      kopfBreite: r ? Math.round(r.width) : 0,
      griffDisplay: gStil ? gStil.display : null,
      griffBreite: g ? Math.round(g.width) : 0,
      griffHoehe: g ? Math.round(g.height) : 0,
      griffFarbe: gStil ? gStil.backgroundColor : null,
      mehrAriaExpanded: document.querySelector('.dk-bottom-nav button.dk-bn-tab.active')
        ?.getAttribute('aria-expanded') ?? null,
      theme: document.documentElement.getAttribute('data-theme'),
      breite: window.innerWidth,
    }
  })
}

async function aufnahme(page, ansicht, schritt, erwartetOffen) {
  const m = await zustand(page)
  messungen.push({ marke: MARKE, ansicht, schritt, erwartetOffen, ...m })
  await page.screenshot({ path: join(ZIEL, `${MARKE}-${ansicht}-${schritt}.png`) })
  if (m.blattOffen !== erwartetOffen) {
    fehler.push(`${ansicht}/${schritt}: Blatt ${m.blattOffen ? 'offen' : 'zu'}, erwartet ${erwartetOffen ? 'offen' : 'zu'}`)
  }
}

function mehrKnopf(page) {
  return page.locator('.dk-bottom-nav button.dk-bn-tab', { hasText: 'Mehr' }).first()
}

async function oeffne(page) {
  const mehr = mehrKnopf(page)
  if (!(await mehr.count())) throw new Error('Knopf „Mehr“ nicht gefunden')
  await mehr.click()
  await page.waitForTimeout(700)
}

async function lauf(page, ansicht) {
  // 1 · offen
  await oeffne(page)
  await aufnahme(page, ansicht, 'offen', true)

  // 2 · Kopf schließt
  if (await page.locator('.dk-bn-sheet-kopf').count()) {
    await page.locator('.dk-bn-sheet-kopf').first().click()
    await page.waitForTimeout(600)
  } else {
    fehler.push(`${ansicht}: kein .dk-bn-sheet-kopf vorhanden (Kopf nicht bedienbar)`)
    await page.keyboard.press('Escape')
    await page.waitForTimeout(600)
  }
  await aufnahme(page, ansicht, 'kopf-zu', false)

  // 3 · außerhalb
  await oeffne(page)
  await page.mouse.click(10, 60)
  await page.waitForTimeout(600)
  await aufnahme(page, ansicht, 'aussen-zu', false)

  // 4 · Escape
  await oeffne(page)
  await page.keyboard.press('Escape')
  await page.waitForTimeout(600)
  await aufnahme(page, ansicht, 'escape-zu', false)

  // 5 · zweiter Tipp auf „Mehr“
  // Der „Mehr“-Knopf liegt UNTER der Überlappung; ein normaler Klick würde von
  // der Überlappung abgefangen (und schlösse das Blatt auf dem falschen Weg).
  // Deshalb ein roher Zeigertipp auf die Knopfmitte, wie ihn ein Finger
  // auslöst, ohne die Trefferprüfung von Playwright.
  await oeffne(page)
  const box = await mehrKnopf(page).boundingBox()
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2)
  await page.waitForTimeout(600)
  await aufnahme(page, ansicht, 'mehr-zu', false)
}

async function main() {
  mkdirSync(ZIEL, { recursive: true })
  const browser = await chromium.launch({ args: ['--no-sandbox'] })
  // Touch-Gerät: die untere Leiste erscheint nur bei (pointer: coarse).
  const ctx = await browser.newContext({
    viewport: { width: BREITE, height: HOEHE },
    hasTouch: true,
    isMobile: true,
    deviceScaleFactor: 2,
    userAgent: 'Mozilla/5.0 (Linux; Android 13; Pixel 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36',
  })
  const page = await ctx.newPage()
  page.on('console', (m) => { if (m.type() === 'error') fehler.push(`console.error: ${m.text()}`) })
  page.on('pageerror', (e) => fehler.push(`pageerror: ${e.message}`))

  await anmelden(page)
  for (const theme of ['light', 'dark']) {
    await page.evaluate((t) => { try { localStorage.setItem('dk-theme', t) } catch { /* gesperrt */ } }, theme)
    await page.reload({ waitUntil: 'domcontentloaded' })
    await page.waitForTimeout(1500)
    await page.goto(BASE + SEITE, { waitUntil: 'domcontentloaded' })
    await page.waitForTimeout(2200)
    await lauf(page, theme)
  }
  await browser.close()

  const bericht = { marke: MARKE, fehler, messungen }
  writeFileSync(join(ZIEL, `${MARKE}-messung.json`), JSON.stringify(bericht, null, 2))
  console.log(JSON.stringify(bericht, null, 2))
  return fehler.length ? 1 : 0
}

main().then((code) => { process.exitCode = code }).catch((e) => {
  fehler.push(`Abbruch: ${e.message}`)
  console.error(e)
  process.exitCode = 2
})
