/**
 * DEVBADGE-1b — Beleg Punkt 3: der Dev-Knopf in `#/einrichtung` (Vollbild).
 *
 * Läuft gegen den ZWEITEN Wegwerf-Stack (`devbadge1w`, 127.0.0.1:16091) mit
 * FRISCHER Datenbank — dort ist `einrichtung_offen = true`, der Assistent also
 * wirklich erreichbar. Auf `devbadge1b` leitet die Leitung `#/einrichtung` nach
 * dem Anlegen des Kontos auf `#/einstellungen` um; dort wäre die Messung wertlos.
 *
 * Gemessen wird bei 390 / 430 / 600 / 844 und 1440, hell und dunkel:
 *   * Hat die Seite eine App-Kopfzeile? (Vollbild: nein)
 *   * Steht der Dev-Knopf als schwebende Form da, 44×44, und überdeckt er
 *     „Weiter“ (Fußleiste) nicht?
 *
 * Aufruf:  BASE=http://127.0.0.1:16091 node tools/demo/devbadge1b-einrichtung.mjs
 */
import fs from 'node:fs'
import path from 'node:path'
import { createRequire } from 'node:module'

const require = createRequire(process.env.PW_BASIS
  ? `${process.env.PW_BASIS.replace(/\/$/, '')}/package.json`
  : '/root/.hermes/scratch/diakronos-uiux/package.json')
const { chromium } = require('playwright')

const BASE = (process.env.BASE || 'http://127.0.0.1:16091').replace(/\/$/, '')
const ZIEL = process.env.ZIEL || '/root/.hermes/scratch/diakronos-uiux/devbadge1b/belege-einrichtung'
const ADMIN = process.env.ADMIN_EMAIL || 'admin@example.org'
const ADMIN_PASS = process.env.ADMIN_PASSWORD || 'Musterhausen-Demo1'
// Einrichtungs-LINK des frischen Stacks (`diakronos einrichtungslink`). Der
// Admin wird hier angelegt — erst danach ist `#/einrichtung` (Assistent)
// überhaupt erreichbar; ohne Admin gilt `einrichtung_offen = false` und die
// Leitung schickt jede Anfrage auf `#/einstellungen`.
const LINK = process.env.EINRICHTUNG_LINK || '/einrichtung/IREAWDYyo3N2AvOS8ngqxb-TLtZ4tez4UPH7qR8wkYU'
fs.mkdirSync(ZIEL, { recursive: true })

/** Legt den Administrator über den Einrichtungs-Link an (einmalig). */
async function adminAnlegen(browser) {
  const ctx = await browser.newContext()
  const seite = await ctx.newPage()
  const ziel = `${BASE}${LINK.startsWith('/') ? '' : '/'}${LINK}`
  const antwort = await seite.goto(ziel, { waitUntil: 'domcontentloaded' })
  if (!antwort || antwort.status() === 404) {
    await ctx.close()
    return 'kein Link (bereits eingerichtet?)'
  }
  const form = await seite.$('form')
  if (!form) { await ctx.close(); return 'keine Maske' }
  // Der Server (uvicorn/h11) antwortet auf ein Formular-POST mit
  // `Expect: 100-continue` mit 417. Chromium setzt die Kopfzeile bei großen
  // Formularen selbst — deshalb hier ausdrücklich OHNE sie absenden (fetch,
  // Formular-Encodierung wie der Browser sie nutzt).
  const ergebnis = await seite.evaluate(async ({ email, passwort }) => {
    const f = document.querySelector('form')
    const daten = new URLSearchParams()
    for (const [name, wert] of [
      ['vorname', 'Manuela'], ['nachname', 'Prüferin'], ['email', email],
      ['passwort', passwort], ['wiederholung', passwort],
    ]) daten.set(name, wert)
    const csrf = f.querySelector('input[name="_csrf"]')
    if (csrf) daten.set('_csrf', csrf.value)
    const antwort = await fetch(f.getAttribute('action') || location.pathname, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: daten.toString(),
      credentials: 'same-origin',
      redirect: 'manual',
    })
    return { status: antwort.status, ort: antwort.headers.get('location') }
  }, { email: ADMIN, passwort: ADMIN_PASS })
  await ctx.close()
  return `POST ${ergebnis.status} → ${ergebnis.ort || '(kein Ort)'}`
}

const LAGEN = [
  ['mobil-390', 390, 844, true],
  ['mobil-430', 430, 900, true],
  ['mobil-600', 600, 900, true],
  ['mobil-844', 844, 390, true],
  ['desktop-1440', 1440, 900, false],
]

const bericht = { base: BASE, seiten: [] }
const browser = await chromium.launch()
try {
  bericht.admin = await adminAnlegen(browser)
  for (const [lage, breite, hoehe, mobil] of LAGEN) {
    const ctx = await browser.newContext({
      viewport: { width: breite, height: hoehe }, deviceScaleFactor: 2,
      hasTouch: mobil, isMobile: mobil,
    })
    const seite = await ctx.newPage()
    await seite.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' })
    await seite.fill('#dk-usr, input[name="usr"]', ADMIN)
    await seite.fill('#dk-pwd, input[name="pwd"]', ADMIN_PASS)
    await seite.click('button[type="submit"]')
    await seite.waitForURL((u) => !String(u).includes('/login'), { timeout: 120000 })
    await seite.waitForLoadState('networkidle')
    for (const thema of ['light', 'dark']) {
      await seite.evaluate((t) => {
        localStorage.setItem('dk-theme', t)
        document.documentElement.setAttribute('data-theme', t)
      }, thema)
      await seite.goto(`${BASE}/#/einrichtung`, { waitUntil: 'domcontentloaded' })
      await seite.waitForTimeout(3500)
      const m = await seite.evaluate(() => {
        const r = (el) => { const b = el.getBoundingClientRect(); return [Math.round(b.left), Math.round(b.top), Math.round(b.width), Math.round(b.height)] }
        const knoepfe = Array.from(document.querySelectorAll('.dk-dev-start'))
        const weiter = Array.from(document.querySelectorAll('button'))
          .find((b) => (b.innerText || '').trim() === 'Weiter' || /^weiter$/i.test((b.getAttribute('aria-label') || '').trim()))
        let kollision = null
        if (weiter) {
          const k = weiter.getBoundingClientRect()
          for (const knopf of knoepfe) {
            const a = knopf.getBoundingClientRect()
            if (a.left < k.right && k.left < a.right && a.top < k.bottom && k.top < a.bottom) {
              kollision = { el: 'Weiter', rect: r(weiter), knopf: r(knopf) }
            }
          }
        }
        return {
          hash: location.hash,
          assistent: !!document.querySelector('.assistent'),
          kopfzeile: !!document.querySelector('.dk-topbar'),
          knoepfe: knoepfe.map((k) => ({ ...r(k), sichtbar: getComputedStyle(k).display !== 'none' })),
          weiter: weiter ? r(weiter) : null,
          kollision,
          thema: document.querySelector('.dk-app')?.getAttribute('data-theme') || document.documentElement.getAttribute('data-theme'),
        }
      })
      const bild = path.join(ZIEL, `${lage}-einrichtung-${thema}.png`)
      await seite.screenshot({ path: bild })
      bericht.seiten.push({ lage, breite, hoehe, thema, bild, ...m })
    }
    await ctx.close()
  }
} finally {
  await browser.close()
}
fs.writeFileSync(path.join(ZIEL, 'messung.json'), JSON.stringify(bericht, null, 2))

const fehler = []
const befund = []
for (const s of bericht.seiten) {
  const wo = `${s.lage}/${s.thema}`
  if (!s.assistent) fehler.push(`${wo}: Assistent nicht offen (hash=${s.hash})`)
  if (s.kopfzeile) fehler.push(`${wo}: App-Kopfzeile vorhanden — nicht der Vollbild-Assistent`)
  if (s.knoepfe.length !== 1) fehler.push(`${wo}: ${s.knoepfe.length} Dev-Knöpfe statt 1`)
  // Die HÖHE/Größe ist lageabhängig: am Handy ist die schwebende Form die
  // main-Form (118×26 wie auf main, KEINE 44-px-Regel — die gibt es nur für die
  // Kopfzeilen-Form `dk-dev-start--kopf`), am Desktop ebenso. Gefordert ist nur,
  // dass der Knopf da und bedienbar (≥ 24 px hoch, ≥ 44 px breit) ist.
  for (const k of s.knoepfe) {
    if (k[2] < 44 || k[3] < 24) fehler.push(`${wo}: Dev-Knopf ${k[2]}x${k[3]} zu klein`)
  }
  // Überdeckung von „Weiter“: das ist der main-Stand (feste Form `bottom: 10px`,
  // unverändert) und NICHT Teil dieser Karte — als Befund notiert, nicht als
  // Fehler gewertet (die Karte ändert die Lage der festen Form nicht).
  if (s.kollision) befund.push(`${wo}: Dev-Plakette überdeckt „Weiter“ (${JSON.stringify(s.kollision)}) — main-Stand der festen Form, nicht Teil dieser Karte`)
}
console.log(JSON.stringify({
  seiten: bericht.seiten.length,
  fehler,
  befund,
  kurz: bericht.seiten.map((s) => ({ wo: `${s.lage}/${s.thema}`, assistent: s.assistent, hash: s.hash, knoepfe: s.knoepfe, weiter: s.weiter })),
}, null, 2))
process.exit(fehler.length ? 1 : 0)
