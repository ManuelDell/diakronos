/**
 * DEVBADGE-1 — Belege: Dev-Abzeichen am Handy (Karte t_2df971b3).
 *
 * Läuft gegen den EIGENEN Wegwerf-Stack (Projekt devbadge1, Musterhausen-Daten,
 * DEVMODE_ENABLED=1) und prüft, was die Karte zusagt:
 *
 *   Das Abzeichen „Dev-Modus an“ (Knopf `.dk-dev-start`) schneidet auf
 *   Kalender, Mitglieder, Gruppen und Start KEIN Bedienelement (Knöpfe, Links,
 *   Felder) — gemessen an den Rechtecken, 360/375/390 hell + dunkel. Dazu
 *   1440 hell + dunkel (Desktop-Lage unten rechts, wie main). Zusätzlich wird
 *   der Seitentitel gemessen (Review 11.11. Punkt 2: er darf höchstens mit
 *   „…“ kürzen, nicht hart abgeschnitten werden).
 *
 * Ausgabe: `<ZIEL>/messung.json` und die Bilder `<ZIEL>/*.png`.
 *
 * Aufruf (wie die übrigen tools/demo-Skripte; playwright wird im Abbild unter
 * /tmp/pw nachinstalliert):
 *   docker run --rm --network devbadge1_default -v "<repo>":/w:ro -v "<ziel>":/ausgabe \
 *       -e BASE=http://app:8000 mcr.microsoft.com/playwright:v1.49.0-noble \
 *       sh -c 'npm i -s --prefix /tmp/pw playwright@1.49.0 >/dev/null 2>&1;
 *              export NODE_PATH=/tmp/pw/node_modules;
 *              node /w/tools/demo/devbadge1-abnahme.mjs'
 */
import fs from 'node:fs'
import path from 'node:path'
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
const { chromium } = require('playwright')

const BASE = (process.env.BASE || 'http://app:8000').replace(/\/$/, '')
const ZIEL = process.env.ZIEL || '/ausgabe'
const ADMIN = process.env.ADMIN_EMAIL || 'admin@example.org'
const ADMIN_PASS = process.env.ADMIN_PASS || 'musterhausen-demo'

fs.mkdirSync(ZIEL, { recursive: true })
const bericht = { base: BASE, seiten: [] }

// Start ist `#/` — `#/start` gibt es nicht (die Seite meldet dann
// „Seite nicht gefunden“, Review 11.11. Punkt 6).
const SEITEN = [
  ['start', '/#/'],
  ['mitglieder', '/#/mitglieder'],
  ['gruppen', '/#/gruppen'],
  ['kalender', '/#/kalender'],
]

async function anmelden(seite) {
  await seite.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' })
  await seite.fill('#dk-usr, input[name="usr"]', ADMIN)
  await seite.fill('#dk-pwd, input[name="pwd"]', ADMIN_PASS)
  await seite.click('button[type="submit"]')
  await seite.waitForURL((u) => !String(u).includes('/login'), { timeout: 90000 })
  await seite.waitForLoadState('networkidle')
}

async function themaSetzen(seite, thema) {
  // Die App liest den Startwert aus `dk-theme` (composables/theme.mjs) und
  // setzt `data-theme` an `html` UND an `.dk-app`. Beides muss stimmen, sonst
  // misst man die helle Fläche mit dunklen Werten.
  await seite.evaluate((t) => {
    localStorage.setItem('dk-theme', t)
    document.documentElement.setAttribute('data-theme', t)
    document.querySelector('.dk-app')?.setAttribute('data-theme', t)
  }, thema)
  await seite.waitForTimeout(500)
  const ist = await seite.evaluate(() => document.querySelector('.dk-app')?.getAttribute('data-theme'))
  if (ist !== thema) return false
  return true
}

async function messen(seite, thema) {
  const ok = await themaSetzen(seite, thema)
  if (!ok) throw new Error(`Theme ${thema} nicht gesetzt`)
  return seite.evaluate(() => {
    const badge = document.querySelector('.dk-dev-start')
    if (!badge) return { fehlt: true }
    const a = badge.getBoundingClientRect()
    const handy = document.querySelector('.dk-app')?.classList.contains('dk-app--handy')
    const kollisionen = []
    for (const el of document.querySelectorAll('button, a[href], input, select, textarea, [role="button"]')) {
      if (el === badge || badge.contains(el) || el.contains(badge)) continue
      const st = getComputedStyle(el)
      if (st.display === 'none' || st.visibility === 'hidden' || st.pointerEvents === 'none') continue
      const b = el.getBoundingClientRect()
      if (b.width < 1 || b.height < 1) continue
      if (a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom) {
        kollisionen.push({
          el: el.tagName.toLowerCase() + (el.className ? '.' + String(el.className).split(' ')[0] : ''),
          text: (el.innerText || el.value || el.textContent || '').trim().slice(0, 40),
          rect: [Math.round(b.left), Math.round(b.top), Math.round(b.width), Math.round(b.height)],
        })
      }
    }
    // Review 11.11. Punkt 2: Seitentitel — Text, Breite und ob er sichtbar
    // beschnitten ist. Gemessen am INNEREN Textknoten: bei `text-overflow:
    // ellipsis` mit `nowrap` meldet `scrollWidth` des Elementes die volle
    // Textbreite, obwohl sichtbar „…“ steht — deshalb „passt“ über die Breite
    // des Textknotens gegen die Box.
    const titel = document.querySelector('.dk-crumb-current')
    let titelAbschnitt = null
    if (titel) {
      const r = titel.getBoundingClientRect()
      const spanne = document.createRange()
      spanne.selectNodeContents(titel)
      const textBreite = Math.ceil(spanne.getBoundingClientRect().width)
      titelAbschnitt = {
        text: titel.textContent.trim(),
        breite: Math.round(r.width),
        textBreite,
        passt: textBreite <= Math.round(r.width) + 1,
        abschnitt: getComputedStyle(titel).textOverflow,
      }
    }
    return {
      handy,
      text: badge.innerText.trim().replace(/\s+/g, ' '),
      rect: [Math.round(a.left), Math.round(a.top), Math.round(a.width), Math.round(a.height)],
      kollisionen,
      titel: titelAbschnitt,
    }
  })
}

// 360/375 sind die schmalen Handy-Breiten aus dem Review, 390 der Regelfall.
const LAGEN = [['mobil-360', 360, 800], ['mobil-375', 375, 812], ['mobil', 390, 844], ['desktop', 1440, 900]]

const browser = await chromium.launch()
try {
  for (const [lage, breite, hoehe] of LAGEN) {
    const mobil = lage !== 'desktop'
    const ctx = await browser.newContext({
      viewport: { width: breite, height: hoehe },
      deviceScaleFactor: 2,
      hasTouch: mobil,
      isMobile: mobil,
      pointer: mobil ? 'coarse' : 'fine',
    })
    const seite = await ctx.newPage()
    await anmelden(seite)
    for (const [name, pfad] of SEITEN) {
      await seite.goto(`${BASE}${pfad}`, { waitUntil: 'domcontentloaded' })
      await seite.waitForTimeout(2500)
      for (const thema of ['light', 'dark']) {
        const m = await messen(seite, thema)
        const bild = path.join(ZIEL, `devbadge1-${lage}-${name}-${thema}.png`)
        await seite.screenshot({ path: bild })
        bericht.seiten.push({ lage, breite, name, thema, bild, ...m })
      }
    }
    await ctx.close()
  }
} finally {
  await browser.close()
}

fs.writeFileSync(path.join(ZIEL, 'messung.json'), JSON.stringify(bericht, null, 2))
const fehler = bericht.seiten.filter((s) => s.fehlt || (s.kollisionen || []).length
  || (s.titel && !s.titel.passt))
console.log(JSON.stringify({
  seiten: bericht.seiten.length,
  fehler: fehler.map((s) => ({
    lage: s.lage, name: s.name, thema: s.thema, fehlt: s.fehlt,
    handy: s.handy, rect: s.rect, text: s.text, kollisionen: s.kollisionen, titel: s.titel,
  })),
  titel: bericht.seiten.map((s) => ({ lage: s.lage, name: s.name, ...(s.titel || {}) })),
}, null, 2))
process.exit(fehler.length ? 1 : 0)
