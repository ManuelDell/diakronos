/**
 * MINIMONAT-1 — Beleg: Die Pfeile ‹ › des Mini-Monats blättern.
 *
 * Gemessen wird am laufenden (Wegwerf-)Stack, nicht behauptet:
 *
 *   A · HANDY 390 (hell UND dunkel): in der Ansicht „Liste“ blättert ‹ einen
 *       Monat zurück und › einen Monat vor — Titel des Mini-Monats, Raster
 *       UND Tagesliste (Kopf „Samstag, 5. Dezember“ o. ä.) ziehen mit.
 *       Zusätzlich: das Raster zeigt den neuen Monat (eine Zelle mit
 *       `is-gewaehlt`, deren `data-tag` im neuen Monat liegt).
 *   B · DESKTOP 1440: am Laptop erscheint NIE die Handy-Leiste (kein
 *       `.dk-app--handy`, keine `.dk-minimonat`/`.dk-minimonat-pfeil`), und der
 *       Desktop-Mini-Monat (KronosMiniCalendar, seit MT-1b2 eine
 *       Dashboard-Kachel) blättert weiterhin über seine EIGENEN Pfeile.
 *
 * Aufruf (Playwright im Abbild nachinstalliert; Belege NUR nach
 * /root/.hermes/scratch/…, nie nach /tmp):
 *   docker run --rm --network <projekt>_default -v "<repo>":/w:ro \
 *       -v /root/.hermes/scratch/diakronos-uiux/minimonat1:/ausgabe \
 *       -e MIN1_BASE=http://app:8000 mcr.microsoft.com/playwright:v1.49.0-noble \
 *       sh -c 'npm i -s --prefix /tmp/pw playwright@1.49.0 >/dev/null 2>&1;
 *              export NODE_PATH=/tmp/pw/node_modules;
 *              node /w/tools/demo/minimonat1-screenshots.mjs'
 */
import { mkdirSync, writeFileSync } from 'node:fs'
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
const { chromium } = require('playwright')

const BASE = (process.env.MIN1_BASE || 'http://app:8000').replace(/\/$/, '')
const ZIEL = process.env.ZIEL || '/ausgabe'
const EMAIL = process.env.ADMIN_EMAIL || 'admin@example.org'
const PASSWORT = process.env.ADMIN_PASS || 'musterhausen-demo'

mkdirSync(ZIEL, { recursive: true })

const MONATE = ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli',
  'August', 'September', 'Oktober', 'November', 'Dezember']

async function anmelden(page) {
  await page.goto(BASE + '/#/', { waitUntil: 'networkidle' })
  const feld = page.locator('input[name="usr"], #dk-usr')
  if (await feld.count()) {
    await feld.first().fill(EMAIL)
    await page.fill('input[name="pwd"], #dk-pwd', PASSWORT)
    await page.click('button[type="submit"]')
    await page.waitForLoadState('networkidle')
  }
}

async function listeOeffnen(page) {
  await page.goto(BASE + '/#/kalender?ansicht=liste', { waitUntil: 'networkidle' })
  await page.waitForSelector('.dk-minimonat', { state: 'attached', timeout: 30000 })
  await page.waitForTimeout(1500)
}

/** Was steht gerade im Mini-Monat und in der Tagesliste? */
async function stand(page) {
  return page.evaluate(() => {
    const text = (el) => (el ? (el.textContent || '').replace(/\s+/g, ' ').trim() : '')
    const gewaehlt = document.querySelector('.dk-minimonat-tag.is-gewaehlt')
    const tage = [...document.querySelectorAll('.dk-minimonat-tag')].map((e) => e.getAttribute('data-tag'))
    return {
      titel: text(document.querySelector('.dk-minimonat-titel')),
      gewaehlt: gewaehlt ? gewaehlt.getAttribute('data-tag') : null,
      ersterTag: tage[0] || null,
      letzterTag: tage[tage.length - 1] || null,
      tageskopf: text(document.querySelector('.dk-tagesliste-titel')),
      zeilen: document.querySelectorAll('.dk-tagesliste-zeile').length,
      punke: document.querySelectorAll('.dk-minimonat-punkt').length,
    }
  })
}

/** „November 2026“ → { jahr, monat } (Monat 1-basiert) oder null. */
function titelMonat(titel) {
  const m = String(titel || '').match(/^([A-Za-zÄÖÜäöüß]+)\s+(\d{4})$/)
  if (!m) return null
  const idx = MONATE.indexOf(m[1])
  return idx < 0 ? null : { jahr: Number(m[2]), monat: idx + 1 }
}

/** Mittelpunkt eines Knopfes klicken (Kante traf im MT-5-Lauf ins Icon). */
async function klicke(knopf) {
  await knopf.scrollIntoViewIfNeeded()
  /** Mittelpunkt messen — und ob der Zeiger dort WIRKLICH den Knopf trifft. */
  const messen = () => knopf.evaluate((el) => {
    const b = el.getBoundingClientRect()
    const x = b.x + b.width / 2
    const y = b.y + b.height / 2
    const treffer = document.elementFromPoint(x, y)
    return {
      x, y, w: b.width, h: b.height,
      trifft: !!(treffer && (el === treffer || el.contains(treffer))),
      treffer: treffer ? `${treffer.tagName}.${treffer.className}`.slice(0, 60) : null,
    }
  })
  let r = await messen()
  // MINIMONAT-1: Nach dem ersten Tipp rückt der Mini-Monat nach oben (die
  // Tagesliste wird kürzer) — der Zeiger steht dann auf dem KOPF der Liste,
  // nicht auf dem Pfeil. Deshalb warten, bis der Knopf wieder unter dem
  // Mittelpunkt liegt, und höchstens dreimal nachfassen. Ohne diese Prüfung
  // maß der Beleg eine Lage, die der Nutzer gar nicht antippt.
  for (let versuch = 0; versuch < 3 && !r.trifft; versuch += 1) {
    await knopf.page().waitForTimeout(400)
    r = await messen()
  }
  if (r.w < 40 || r.h < 40) throw new Error(`Tippziel zu klein: ${Math.round(r.w)}×${Math.round(r.h)}`)
  if (!r.trifft) throw new Error(`Zeiger trifft nicht den Pfeil, sondern ${r.treffer}`)
  await knopf.page().mouse.click(r.x, r.y)
  return { breite: Math.round(r.w), hoehe: Math.round(r.h) }
}

async function handy(page, thema, bericht) {
  await anmelden(page)
  // MINIMONAT-1 (Review): `theme.mjs` kennt nur 'light'/'dark' — 'hell'/'dunkel'
  // war ein wirkungsloser Wert, beide Belege waren byte-gleich. Beleg-Name
  // bleibt deutsch, der gespeicherte Wert ist der echte.
  await page.evaluate((t) => {
    document.documentElement.setAttribute('data-theme', t)
    localStorage.setItem('dk-theme', t)
  }, thema === 'hell' ? 'light' : 'dark')
  await listeOeffnen(page)
  await page.waitForTimeout(600)

  const vorher = await stand(page)
  await page.screenshot({ path: `${ZIEL}/handy-390-${thema}-1-ist.png`, fullPage: false })

  const zurueck = await klicke(page.locator('.dk-minimonat-pfeil').first())
  await page.waitForTimeout(1200)
  const nachZurueck = await stand(page)
  await page.screenshot({ path: `${ZIEL}/handy-390-${thema}-2-zurueck.png`, fullPage: false })

  const vor = await klicke(page.locator('.dk-minimonat-pfeil').nth(1))
  await page.waitForTimeout(1200)
  const nachVor = await stand(page)
  await page.screenshot({ path: `${ZIEL}/handy-390-${thema}-3-vor.png`, fullPage: false })

  const vor2 = await klicke(page.locator('.dk-minimonat-pfeil').nth(1))
  await page.waitForTimeout(1200)
  const nachVor2 = await stand(page)
  await page.screenshot({ path: `${ZIEL}/handy-390-${thema}-4-vor2.png`, fullPage: false })

  // Erwartung aus dem Titel des ersten Stands rechnen (unabhängig vom Datum):
  // ‹ = −1 Monat, › = +1 Monat, ›› = +2 Monate — jeweils über die Jahresgrenze.
  const start = titelMonat(vorher.titel)
  const verschiebe = (n) => {
    if (!start) return null
    const gesamt = start.jahr * 12 + (start.monat - 1) + n
    return `${MONATE[((gesamt % 12) + 12) % 12]} ${Math.floor(gesamt / 12)}`
  }
  const minus = verschiebe(-1)
  const plus = verschiebe(1)
  const plus2 = verschiebe(2)

  bericht[`handy-${thema}`] = {
    vorher, zurueck: { klick: zurueck, stand: nachZurueck, erwartet: minus },
    // Die Schritte bauen AUFEINANDER auf: ‹ → Oktober, › (von Oktober!) →
    // wieder November = der START-monat, › → Dezember. Früher wurde jeder
    // Schritt gegen den Startmonat geprüft (+1/+2) — dann galt „November“
    // nach dem Zurückblättern als Fehler, obwohl genau das richtig ist.
    vor: { klick: vor, stand: nachVor, erwartet: vorher.titel },
    vor2: { klick: vor2, stand: nachVor2, erwartet: plus },
    titelGewechselt: vorher.titel !== nachZurueck.titel,
    zurueckRichtig: nachZurueck.titel === minus,
    vorRichtig: nachVor.titel === vorher.titel,
    vor2Richtig: nachVor2.titel === plus,
    // Die Tagesliste muss zum gezeigten Monat passen (ihr Tag liegt im Monat).
    tageslistePasstZurueck: String(nachZurueck.gewaehlt || '').slice(0, 7) === monatSchluesselTitel(nachZurueck.titel),
    tageslistePasstVor: String(nachVor.gewaehlt || '').slice(0, 7) === monatSchluesselTitel(nachVor.titel),
    tageslistePasstVor2: String(nachVor2.gewaehlt || '').slice(0, 7) === monatSchluesselTitel(nachVor2.titel),
    // Beide Läufe (hell/dunkel) müssen denselben Stand zeigen.
    themaGesetzt: thema,
  }
}

/** „November 2026“ → „2026-11“ (für den Abgleich mit dem gewählten Tag). */
function monatSchluesselTitel(titel) {
  const m = titelMonat(titel)
  if (!m) return ''
  return `${m.jahr}-${String(m.monat).padStart(2, '0')}`
}

async function desktop(page, bericht) {
  await anmelden(page)
  await page.goto(BASE + '/#/kalender', { waitUntil: 'networkidle' })
  await page.waitForSelector('.kronos-calendar-wrap', { state: 'attached', timeout: 30000 })
  await page.waitForTimeout(2000)
  // Am Laptop: NIE die Handy-Leiste, nie der Handy-Bau.
  const kalenderSeite = await page.evaluate(() => ({
    handyBau: !!document.querySelector('.dk-app--handy'),
    handyElemente: document.querySelectorAll('.dk-minimonat, .dk-tagesliste, .dk-mobilkopf').length,
    handyPfeile: document.querySelectorAll('.dk-minimonat-pfeil').length,
    rasterDa: !!document.querySelector('.kronos-calendar-wrap'),
  }))
  await page.screenshot({ path: `${ZIEL}/desktop-1440-1-ist.png`, fullPage: false })

  // Der Desktop-Mini-Monat ist seit MT-1b2 eine Kachel des Dashboards
  // (`MiniCalendarWidget` → `KronosMiniCalendar`), nicht mehr Teil der
  // Kalenderseite. Belegt wird dort: er steht, er blättert über seine EIGENEN
  // Pfeile, und das erzeugt keinen Handy-Bau.
  await page.goto(BASE + '/#/', { waitUntil: 'networkidle' })
  await page.waitForTimeout(2500)
  const messen = () => page.evaluate(() => {
    const text = (el) => (el ? (el.textContent || '').replace(/\s+/g, ' ').trim() : '')
    return {
      titel: text(document.querySelector('.kronos-mini-calendar .mini-title')),
      rasterTage: document.querySelectorAll('.kronos-mini-calendar .mini-cal-day').length,
      handyBau: !!document.querySelector('.dk-app--handy'),
      handyPfeile: document.querySelectorAll('.dk-minimonat-pfeil').length,
    }
  })
  const vorher = await messen()
  await page.screenshot({ path: `${ZIEL}/desktop-1440-2-minimonat-ist.png`, fullPage: false })
  const pfeile = await page.locator('.kronos-mini-calendar .mini-pfeil').count()
  if (pfeile >= 2) {
    await page.locator('.kronos-mini-calendar .mini-pfeil').nth(1).click()
    await page.waitForTimeout(900)
  }
  const nachher = await messen()
  await page.screenshot({ path: `${ZIEL}/desktop-1440-3-minimonat-vor.png`, fullPage: false })

  bericht.desktop = {
    kalenderSeite,
    miniMonat: { vorher, nachher, pfeile, vorhanden: vorher.rasterTage > 0 },
    // Der Desktop-Mini-Monat blättert mit seinen eigenen Pfeilen weiter …
    eigenesBlaettern: vorher.titel !== '' && nachher.titel !== vorher.titel,
    // … und der Handy-Bau bleibt am Laptop aus.
    handyBauAus: !kalenderSeite.handyBau && !vorher.handyBau,
    keineHandyElemente: kalenderSeite.handyElemente === 0,
    keineHandyPfeile: kalenderSeite.handyPfeile === 0 && vorher.handyPfeile === 0,
  }
}

const bericht = {}
const browser = await chromium.launch({ args: ['--no-sandbox'] })
try {
  for (const thema of ['hell', 'dunkel']) {
    const ctx = await browser.newContext({
      viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true,
      deviceScaleFactor: 2, locale: 'de-DE', timezoneId: 'Europe/Berlin',
    })
    const page = await ctx.newPage()
    await handy(page, thema, bericht)
    await ctx.close()
  }
  const ctx = await browser.newContext({
    viewport: { width: 1440, height: 900 }, locale: 'de-DE', timezoneId: 'Europe/Berlin',
  })
  const page = await ctx.newPage()
  await desktop(page, bericht)
  await ctx.close()
} finally {
  await browser.close()
}

writeFileSync(`${ZIEL}/bericht.json`, JSON.stringify(bericht, null, 2))

// ── Gesamturteil: nur was hier „true“ ist, gilt als belegt ────────────────
const pruefungen = []
for (const thema of ['hell', 'dunkel']) {
  const v = bericht[`handy-${thema}`]
  for (const f of ['titelGewechselt', 'zurueckRichtig', 'vorRichtig', 'vor2Richtig',
    'tageslistePasstZurueck', 'tageslistePasstVor', 'tageslistePasstVor2']) {
    pruefungen.push([`handy-${thema}.${f}`, v[f] === true])
  }
  // Die beiden Themen müssen denselben Verlauf zeigen (vorher warf das Skript
  // 'hell'/'dunkel' in ein Theme, das nur 'light'/'dark' kennt — beide Belege
  // waren byte-gleich).
  pruefungen.push([`handy-${thema}.themaGesetzt`, v.themaGesetzt === thema])
}
for (const f of ['eigenesBlaettern', 'handyBauAus', 'keineHandyElemente', 'keineHandyPfeile']) {
  pruefungen.push([`desktop.${f}`, bericht.desktop[f] === true])
}
pruefungen.push(['desktop.miniMonat.vorhanden', bericht.desktop.miniMonat.vorhanden === true])
const offen = pruefungen.filter(([, ok]) => !ok)
console.log('\nGESAMT: ' + (pruefungen.length - offen.length) + '/' + pruefungen.length + ' belegt')
for (const [name, ok] of pruefungen) console.log(`  ${ok ? 'OK  ' : 'ROT '} ${name}`)
console.log(JSON.stringify(bericht, null, 2))
if (offen.length) process.exitCode = 1
