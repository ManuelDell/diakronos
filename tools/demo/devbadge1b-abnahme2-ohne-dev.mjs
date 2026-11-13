/**
 * DEVBADGE-1b — Belege, 2. Runde (Review Opus, Punkt 5).
 *
 * Läuft gegen den EIGENEN Wegwerf-Stack (`devbadge1b`, 127.0.0.1:16081). Zwei
 * Zusagen der Karte werden gemessen, jeweils NEBENEINANDER:
 *
 *   ohne-dev = dieselbe Seite OHNE den Dev-Eintrag: keine Klasse
 *             `dk-app--dev`, kein Dev-Knopf im DOM (der Knopf kommt vom
 *             Server; er wird für diese Messung aus dem DOM genommen).
 *             ACHTUNG: Das ist NICHT der main-Stand, sondern der Branch, dem
 *             nur die Dev-Klasse und der Knopf fehlen — CSS und JS stammen
 *             weiterhin von `develop`. Dass die Messwerte ohne Dev-Eintrag
 *             mit main übereinstimmen, belegt der Quelltext-Wächter
 *             `tests/devbadge1b-css-main-treue.test.mjs` (B3–B5), nicht
 *             dieser Lauf.
 *   branch   = die Seite mit der Gerüst-Klasse `dk-app--dev` (Dev-Eintrag
 *             sichtbar). Der Dev-Knopf bleibt im DOM.
 *
 * Gemessen wird bei 390 / 430 / 600 / 844 und 1440, hell und dunkel:
 *   * Kopf-Rand, Plakette (Position + Schrift), Titel (Breite, „…“)
 *   * Bearbeiten-FAB (unten/rechts) auf der Startseite
 *   * Dev-Knopf: Trefferfläche, Kollisionen
 * Der VOLLBILD-Assistent `#/einrichtung` steht im eigenen Beleg-Lauf
 * `tools/demo/devbadge1b-einrichtung.mjs` (er braucht eine FRISCHE Instanz —
 * auf einer eingerichteten Installation leitet `#/einrichtung` auf
 * `#/einstellungen` um).
 *
 * Aufruf (aus frontend/):
 *   BASE=http://127.0.0.1:16081 node ../tools/demo/devbadge1b-abnahme2-ohne-dev.mjs
 */
import fs from 'node:fs'
import path from 'node:path'
import { createRequire } from 'node:module'

// Playwright liegt im Arbeitsbaum der Belege (nicht im Image): Modul-Basis ist
// das Scratch-Verzeichnis, aus dem die Läufe gestartet werden.
const require = createRequire(process.env.PW_BASIS
  ? `${process.env.PW_BASIS.replace(/\/$/, '')}/package.json`
  : '/root/.hermes/scratch/diakronos-uiux/package.json')
const { chromium } = require('playwright')

const BASE = (process.env.BASE || 'http://127.0.0.1:16081').replace(/\/$/, '')
const ZIEL = process.env.ZIEL || '/root/.hermes/scratch/diakronos-uiux/devbadge1b/belege'
const ADMIN = process.env.ADMIN_EMAIL || 'admin@example.org'
const ADMIN_PASS = process.env.ADMIN_PASS || 'musterhausen-demo'

fs.mkdirSync(ZIEL, { recursive: true })

const SEITEN = [
  ['start', '/#/'],
  ['mitglieder', '/#/mitglieder'],
  ['gruppen', '/#/gruppen'],
  ['kalender', '/#/kalender'],
]

const LAGEN = [
  ['mobil-390', 390, 844, true],
  ['mobil-430', 430, 900, true],
  ['mobil-600', 600, 900, true],
  ['mobil-844', 844, 390, true], // Querformat (OP-HANDY-10)
  ['desktop-1440', 1440, 900, false],
]

async function anmelden(seite) {
  await seite.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' })
  await seite.fill('#dk-usr, input[name="usr"]', ADMIN)
  await seite.fill('#dk-pwd, input[name="pwd"]', ADMIN_PASS)
  await seite.click('button[type="submit"]')
  await seite.waitForURL((u) => !String(u).includes('/login'), { timeout: 120000 })
  await seite.waitForLoadState('networkidle')
}

async function themaSetzen(seite, thema) {
  await seite.evaluate((t) => {
    localStorage.setItem('dk-theme', t)
    document.documentElement.setAttribute('data-theme', t)
    document.querySelector('.dk-app')?.setAttribute('data-theme', t)
  }, thema)
  await seite.waitForTimeout(350)
}

/**
 * Stellt einen der beiden Zustände her — auf einer FRISCH geladenen Seite
 * (die Vue-Instanz gehört sich selbst; ein `remove()` an einem Vue-Knoten
 * würde beim nächsten Rerender nicht wiederhergestellt, das war der Fehler
 * im ersten Beleg-Lauf: „0 Dev-Knöpfe“ im zweiten Durchgang).
 *
 *   branch = Dev-Eintrag sichtbar. Ist er es nach dem Laden nicht (kein
 *            Knopf im DOM), wird er für die Messung per Klon in die Kopfzeile
 *            gesetzt — gemessen wird die CSS-Kopplung an `dk-app--dev`.
 *   ohne-dev = OHNE Dev-Eintrag: Klasse weg, Knopf-Knoten weg. Gemessen wird
 *            also der Branch ohne Dev-Kopplung — NICHT main (CSS/JS von
 *            `develop`); der Abgleich mit main steht im Node-Wächter.
 */
async function zustandSetzen(seite, zustand) {
  await seite.evaluate((z) => {
    const app = document.querySelector('.dk-app')
    if (!app) return
    const vorhanden = Array.from(document.querySelectorAll('.dk-dev-start'))
    if (z === 'ohne-dev') {
      // Ohne Dev-Eintrag: hier steht KEIN Dev-Knopf — aus der Messung nehmen.
      // (Der Knoten bleibt für Vue stehen: nur `display` aus, damit ein
      // Rerender nichts „zurückholt“ und die Messung stabil bleibt.)
      app.classList.remove('dk-app--dev')
      for (const el of vorhanden) el.style.display = 'none'
      return
    }
    app.classList.add('dk-app--dev')
    for (const el of vorhanden) el.style.display = ''
    if (!vorhanden.length) {
      // Kein Knopf vom Server (Dev-Modus aus): für die CSS-Messung einen
      // gleich großen Klon in den Kopf-Platz setzen.
      const platz = document.createElement('div')
      platz.className = 'dk-topbar-dev'
      const klon = document.createElement('button')
      klon.type = 'button'
      klon.className = 'dk-dev-start dk-dev-start--kopf'
      klon.setAttribute('aria-label', 'Dev-Modus an — einschalten (Klon für die Messung)')
      const punkt = document.createElement('span')
      punkt.className = 'dk-dev-start-punkt'
      klon.appendChild(punkt)
      platz.appendChild(klon)
      const rechts = document.querySelector('.dk-topbar-right')
      ;(rechts || document.querySelector('.dk-topbar'))?.appendChild(platz)
    }
  }, zustand)
  await seite.waitForTimeout(300)
}

async function messen(seite) {
  return seite.evaluate(() => {
    const app = document.querySelector('.dk-app')
    const topbar = document.querySelector('.dk-topbar')
    const rolle = document.querySelector('.dk-topbar-rolle')
    const badge = rolle?.querySelector('.dk-ui-badge')
    const krumen = document.querySelector('.dk-crumbs')
    const titel = document.querySelector('.dk-crumb-current')
    const fab = document.querySelector('.dk-widget-edit-fab')
    const knoepfe = Array.from(document.querySelectorAll('.dk-dev-start'))
    const kasten = (el) => {
      if (!el) return null
      const r = el.getBoundingClientRect()
      const st = getComputedStyle(el)
      return {
        sichtbar: st.display !== 'none' && st.visibility !== 'hidden' && r.width > 0 && r.height > 0,
        x: Math.round(r.left), y: Math.round(r.top),
        w: Math.round(r.width), h: Math.round(r.height),
        font: st.fontSize,
        flex: st.flex,
        ellipsis: st.textOverflow,
      }
    }
    let titelTeil = null
    if (titel) {
      const r = titel.getBoundingClientRect()
      const spanne = document.createRange()
      spanne.selectNodeContents(titel)
      const textBreite = Math.ceil(spanne.getBoundingClientRect().width)
      titelTeil = {
        text: titel.textContent.trim(),
        w: Math.round(r.width),
        textBreite,
        // „…“ heißt: der Text passt NICHT in den Kasten (text-overflow greift).
        gepunktet: getComputedStyle(titel).textOverflow === 'ellipsis' && textBreite > Math.round(r.width) + 1,
      }
    }
    // Kollisionen des Dev-Knopfs mit Bedienelementen.
    const kollisionen = []
    for (const knopf of knoepfe) {
      const a = knopf.getBoundingClientRect()
      for (const el of document.querySelectorAll('button, a[href], input, select, textarea, [role="button"]')) {
        if (el === knopf || knopf.contains(el) || el.contains(knopf)) continue
        const st = getComputedStyle(el)
        if (st.display === 'none' || st.visibility === 'hidden' || st.pointerEvents === 'none') continue
        const b = el.getBoundingClientRect()
        if (b.width < 1 || b.height < 1) continue
        if (a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom) {
          kollisionen.push({
            el: el.tagName.toLowerCase() + (el.className ? '.' + String(el.className).split(' ')[0] : ''),
            text: (el.innerText || el.value || '').trim().slice(0, 30),
          })
        }
      }
    }
    return {
      handy: !!app?.classList.contains('dk-app--handy'),
      dev: !!app?.classList.contains('dk-app--dev'),
      kopfRand: topbar ? getComputedStyle(topbar).padding : null,
      rolle: kasten(rolle),
      badge: kasten(badge),
      krumen: kasten(krumen),
      titel: titelTeil,
      fab: fab ? { ...kasten(fab), unten: getComputedStyle(fab).bottom, rechts: getComputedStyle(fab).right } : null,
      knoepfe: knoepfe.map((k) => kasten(k)),
      kollisionen,
    }
  })
}

const bericht = { base: BASE, seiten: [] }
const browser = await chromium.launch()
try {
  for (const [lage, breite, hoehe, mobil] of LAGEN) {
    const ctx = await browser.newContext({
      viewport: { width: breite, height: hoehe },
      deviceScaleFactor: 2,
      hasTouch: mobil,
      isMobile: mobil,
      colorScheme: 'light',
    })
    const seite = await ctx.newPage()
    // Das Rollen-Abzeichen („Moderator“) meldet der KALENDER aus
    // `can_moderate` im Boot-Objekt (Quelle: zugängliche Kalender). Der Prüfer
    // ist Administrator ohne Kalender-Recht — für DIESEN Beleg (Plakette vs.
    // Titel) wird der Wert VOR dem App-Start gesetzt: `addInitScript` läuft vor
    // jedem Skript der Seite, damit der Kalender ihn beim Aufbau liest.
    await seite.addInitScript(() => {
      let boot = window.__DIakonosBOOT
      Object.defineProperty(window, '__DIakonosBOOT', {
        configurable: true,
        get() { return boot },
        set(wert) {
          boot = wert
          if (boot && typeof boot === 'object') boot.can_moderate = true
        },
      })
      // Falls die Seite das Objekt schon gesetzt hat (Inline-Skript davor).
      if (boot && typeof boot === 'object') boot.can_moderate = true
      const timer = setInterval(() => {
        if (window.__DIakonosBOOT && typeof window.__DIakonosBOOT === 'object') {
          window.__DIakonosBOOT.can_moderate = true
        }
      }, 50)
      setTimeout(() => clearInterval(timer), 20000)
    })
    await anmelden(seite)
    for (const [name, pfad] of SEITEN) {
      await seite.goto(`${BASE}${pfad}`, { waitUntil: 'domcontentloaded' })
      await seite.waitForTimeout(2200)
      for (const thema of ['light', 'dark']) {
        await themaSetzen(seite, thema)
        for (const zustand of ['branch', 'ohne-dev']) {
          await zustandSetzen(seite, zustand)
          const m = await messen(seite)
          const bild = path.join(ZIEL, `${lage}-${name}-${thema}-${zustand}.png`)
          await seite.screenshot({ path: bild })
          bericht.seiten.push({ lage, breite, hoehe, name, thema, zustand, bild, ...m })
        }
      }
    }
    await ctx.close()
  }
} finally {
  await browser.close()
}

fs.writeFileSync(path.join(ZIEL, 'messung.json'), JSON.stringify(bericht, null, 2))

// ── Auswertung ──────────────────────────────────────────────────────────────
const fehler = []
const kurz = []
for (const s of bericht.seiten) {
  const wo = `${s.lage}/${s.name}/${s.thema}/${s.zustand}`
  const handy = s.handy
  if (s.zustand === 'ohne-dev') {
    // ohne Dev-Eintrag (erwartet wie main): 20 px Rand, Plakette in 14 px
    // und `flex: none`, Kasten
    // `flex: 1 1 auto`, Titel ohne „…“-Beschnitt (textOverflow nicht ellipsis),
    // FAB 24 px — und KEINE Klasse `dk-app--dev`, kein Dev-Knopf.
    if (s.dev) fehler.push(`${wo}: Klasse dk-app--dev noch gesetzt`)
    if (s.knoepfe.some((k) => k.sichtbar)) fehler.push(`${wo}: Dev-Knopf noch sichtbar (ohne-dev: keiner)`)
    if (handy && s.kopfRand !== '0px 20px') fehler.push(`${wo}: Kopf-Rand ${s.kopfRand} statt 0px 20px (ohne-dev wie main)`)
    if (handy && s.rolle && !s.rolle.sichtbar) fehler.push(`${wo}: Plakette fehlt (ohne-dev zeigt sie)`)
    if (handy && s.rolle && s.rolle.font !== '14px') fehler.push(`${wo}: Plakette ${s.rolle.font} statt 14px (ohne-dev wie main)`)
    if (handy && s.krumen && s.krumen.flex !== '1 1 auto') fehler.push(`${wo}: Krumen flex ${s.krumen.flex} statt 1 1 auto (ohne-dev wie main)`)
    if (handy && s.titel && s.titel.ellipsis === 'ellipsis') fehler.push(`${wo}: Titel kürzt mit „…“ (ohne-dev tut das nicht)`)
    if (s.name === 'start' && s.fab && !handy && s.fab.unten !== '24px') fehler.push(`${wo}: FAB unten ${s.fab.unten} statt 24px (ohne-dev wie main)`)
  } else {
    // branch (Dev-Eintrag sichtbar): Klasse da, Knopf da, Kopf 12 px, Plakette
    // schrumpfend/weg, FAB 60 px am Desktop.
    if (!s.dev) fehler.push(`${wo}: Klasse dk-app--dev fehlt`)
    if (handy && s.knoepfe.length !== 1) fehler.push(`${wo}: ${s.knoepfe.length} Dev-Knöpfe am Handy statt 1`)
    if (handy && s.knoepfe[0] && (s.knoepfe[0].w !== 44 || s.knoepfe[0].h !== 44)) {
      fehler.push(`${wo}: Dev-Knopf ${s.knoepfe[0].w}x${s.knoepfe[0].h} statt 44x44`)
    }
    if (handy && s.kollisionen.length) fehler.push(`${wo}: Dev-Knopf kollidiert: ${JSON.stringify(s.kollisionen)}`)
    if (handy && s.kopfRand !== '0px 12px') fehler.push(`${wo}: Kopf-Rand ${s.kopfRand} statt 0px 12px (Dev)`)
    if (s.name === 'start' && s.fab && !handy && s.fab.unten !== '60px') fehler.push(`${wo}: FAB unten ${s.fab.unten} statt 60px (Dev)`)
  }
  kurz.push({
    wo, handy, dev: s.dev,
    kopfRand: s.kopfRand,
    plakette: s.rolle ? `${s.rolle.sichtbar ? 'ja' : 'nein'} ${s.rolle.font} x${s.rolle.x} ${s.rolle.flex}` : 'kein DOM',
    krumen: s.krumen ? s.krumen.flex : null,
    titel: s.titel ? `${s.titel.text} ${s.titel.w}px ${s.titel.gepunktet ? 'GEKÜRZT' : 'passt'}` : null,
    fab: s.fab ? `u${s.fab.unten}/r${s.fab.rechts}` : null,
    knoepfe: s.knoepfe.length,
    kollisionen: s.kollisionen.length,
  })
}

console.log(JSON.stringify({ messungen: bericht.seiten.length, fehler, kurz }, null, 2))
process.exit(fehler.length ? 1 : 0)
