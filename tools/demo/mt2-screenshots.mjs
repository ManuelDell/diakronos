/**
 * MT-2 — Belege: Profilseite mit gespeichertem Profilbild.
 *
 * Vier Lagen: Desktop 1440 und Handy 390, je hell und dunkel. Zusaetzlich ein
 * Bild des Cropper-Dialogs nach der Dateiauswahl (der Weg, den das Mitglied
 * geht) — damit der Befund „Upload klappt, Speichern scheitert" sichtbar ist.
 *
 * Aufruf im Wegwerf-Netz (playwright wird unter /tmp/pw nachinstalliert).
 * Angemeldet wird das Konto der Rolle „Mitglied“ — Adresse/Passwort NUR aus der
 * Umgebung (SEC-DEF2, kein eingebauter Standard; Musterwerte in
 * tools/demo/TESTKONTEN.md):
 *   docker run --rm --network diakronos-mt2_default \
 *     -v "<repo>":/w:ro -v "<ziel>":/ausgabe \
 *     -e MT2_BASE=http://app:8000/diakronos \
 *     -e MT2_PROFIL_EMAIL=<adresse> -e MT2_PROFIL_PASS=<passwort> \
 *     mcr.microsoft.com/playwright:v1.49.0-noble \
 *     sh -c 'npm i -s --prefix /tmp/pw playwright@1.49.0 >/dev/null 2>&1;
 *            export NODE_PATH=/tmp/pw/node_modules;
 *            node /w/tools/demo/mt2-screenshots.mjs'
 */
import { chromium } from 'playwright'
import fs from 'node:fs'

// SEC-DEF2: KEIN eingebauter Standard-Zugang. Fehlt die Variable, bricht das
// Skript mit Hinweis ab (der oeffentliche Musterhausen-Demo-Standard steht in
// tools/demo/TESTKONTEN.md, wird aber nicht stillschweigend eingesetzt).
function wertOderAbbruch(name) {
  const wert = process.env[name]
  if (wert && String(wert).trim()) return wert
  console.error(`[abbruch] Umgebungsvariable ${name} ist nicht gesetzt. Die Demo-Skripte haben absichtlich KEINEN eingebauten Standard-Zugang (SEC-DEF2).`)
  process.exit(2)
}


const BASIS = process.env.MT2_BASE || 'http://app:8000/diakronos'
const ZIEL = process.env.MT2_ZIEL || '/ausgabe'
// SEC-DEF2: KEIN eingebauter Standard-Zugang; Abbruch mit Hinweis.
// Vorher ein festes Mitglied (rebekka.fink@example.org): das Skript zeigt die
// PROFILSEITE des angemeldeten Mitglieds — ein Konto der Rolle „Mitglied“.
const PROFIL_KONTO = {
  usr: wertOderAbbruch('MT2_PROFIL_EMAIL'),
  pwd: wertOderAbbruch('MT2_PROFIL_PASS'),
}

// 1x1-PNG: reicht als Datei fuer den Cropper (er skaliert selbst).
const BILD = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFAAH/'
  + 'q842iQAAAABJRU5ErkJggg==', 'base64')

const LAGEN = [
  { name: 'desktop-1440-hell', breite: 1440, hoehe: 900, dunkel: false },
  { name: 'desktop-1440-dunkel', breite: 1440, hoehe: 900, dunkel: true },
  { name: 'handy-390-hell', breite: 390, hoehe: 844, dunkel: false, touch: true },
  { name: 'handy-390-dunkel', breite: 390, hoehe: 844, dunkel: true, touch: true },
]

async function anmelden(page) {
  await page.goto(BASIS + '/diakonos#/profile', { waitUntil: 'domcontentloaded' })
  // Anmeldemaske kann vorgeschaltet sein.
  if (await page.locator('input[name="usr"]').count()) {
    await page.fill('input[name="usr"]', PROFIL_KONTO.usr)
    await page.fill('input[name="pwd"]', PROFIL_KONTO.pwd)
    await Promise.all([
      page.waitForLoadState('networkidle').catch(() => {}),
      page.click('button[type="submit"], form button'),
    ])
    await page.waitForTimeout(1500)
  }
  await page.goto(BASIS + '/diakonos#/profile', { waitUntil: 'networkidle' })
  await page.waitForTimeout(1200)
}

async function dunkelSchalten(page, an) {
  const html = page.locator('html')
  const istDunkel = (await html.getAttribute('data-theme')) === 'dark'
  if (istDunkel === an) return
  const knopf = page.locator('[data-dk-theme], button[aria-label*="Dunkel"], button[aria-label*="hell"]').first()
  if (await knopf.count()) {
    await knopf.click()
    await page.waitForTimeout(600)
  }
  if (((await html.getAttribute('data-theme')) === 'dark') !== an) {
    await page.evaluate((d) => {
      document.documentElement.setAttribute('data-theme', d ? 'dark' : 'light')
      try { localStorage.setItem('dk-theme', d ? 'dark' : 'light') } catch (e) {}
    }, an)
    await page.waitForTimeout(400)
  }
}

async function masse(page) {
  return page.evaluate(() => {
    const bild = document.querySelector('.profil-foto-kreis img, .profil-kopf img, img[alt="Foto"]')
    const kasten = bild ? bild.getBoundingClientRect() : null
    return {
      fotoVorhanden: Boolean(bild),
      fotoBreite: kasten ? Math.round(kasten.width) : 0,
      fotoHoehe: kasten ? Math.round(kasten.height) : 0,
      fotoGeladen: bild ? bild.complete && bild.naturalWidth > 0 : false,
      fotoUrl: bild ? bild.getAttribute('src') : null,
      theme: document.documentElement.getAttribute('data-theme') || 'light',
      fehlertext: (document.querySelector('[role="alert"], .dk-toast') || {}).innerText || '',
    }
  })
}

;(async () => {
  fs.mkdirSync(ZIEL, { recursive: true })
  const browser = await chromium.launch()
  const bericht = {}

  for (const lage of LAGEN) {
    const kontext = await browser.newContext({
      viewport: { width: lage.breite, height: lage.hoehe },
      hasTouch: Boolean(lage.touch),
      isMobile: Boolean(lage.touch),
      deviceScaleFactor: 1,
    })
    const page = await kontext.newPage()
    await anmelden(page)
    await dunkelSchalten(page, lage.dunkel)
    await page.waitForTimeout(800)
    await page.screenshot({ path: `${ZIEL}/${lage.name}.png`, fullPage: true })
    bericht[lage.name] = await masse(page)
    await kontext.close()
  }

  // Der Weg, den das Mitglied geht: Datei waehlen -> Cropper -> Speichern.
  const kontext = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  const page = await kontext.newPage()
  await anmelden(page)
  const dateiFeld = page.locator('input[type="file"]').first()
  if (await dateiFeld.count()) {
    await dateiFeld.setInputFiles({ name: 'profilbild.png', mimeType: 'image/png', buffer: BILD })
    await page.waitForTimeout(1200)
    await page.screenshot({ path: `${ZIEL}/desktop-1440-cropper.png`, fullPage: true })
    bericht.cropper = await masse(page)
  }
  await kontext.close()
  await browser.close()

  fs.writeFileSync(`${ZIEL}/messung.json`, JSON.stringify(bericht, null, 2))
  console.log(JSON.stringify(bericht, null, 2))
})().catch((e) => { console.error(e); process.exit(1) })
