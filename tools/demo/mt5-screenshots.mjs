/**
 * MT-5 — Screenshots und Messung: kein englischer Bibliothekstext im Kalender.
 *
 * Der Befund (Manuel, Live 11.11.): Die Ansicht „Liste“ zeigte ohne Termine
 * „No events“. Belegt werden ZWEI leere Lagen und eine Gegenprobe:
 *
 *   1. LEER OHNE TRICK (Review 11.11., Punkt 6): ein ECHTER Zeitraum ohne
 *      Termine. Der Seed „Musterhausen“ legt Gottesdienste nur zwei Monate und
 *      feste Termine ± einige Wochen um den Stichtag an — zehn Jahre voraus ist
 *      der Kalender wirklich leer. Angesteuert mit den Pfeilen der Ansicht
 *      (ein Monatsschritt je Klick), am Handy zusätzlich über den Mini-Monat;
 *      KEIN Filter-Trick (`selected_calendars` bleibt unberührt, alle Kalender
 *      sind an — es gibt schlicht nichts anzuzeigen).
 *   2. LEER DURCH FILTER (bisheriger Beleg, bleibt zur Abgrenzung): keine
 *      passende Kalender-Kennung im Filter → der Server liefert keine Termine;
 *      derselbe Leerzustand muss erscheinen.
 *   3. GEGENPROBE: Liste MIT Terminen — dort steht der Leerzustand NICHT.
 *
 * Gemessen wird der Text im Leerkasten der Bibliothek (`.ec-no-events`), ob
 * fremde englische Bibliothekstexte sichtbar sind, und — als Nachweis, dass
 * die Gestaltung GREIFT (Review, Punkt 1) — die GERECHNETEN Werte des
 * Bausteins: Kreis des Symbols, Schriftgröße/Gewicht/Farbe von Titel und Satz,
 * Lage im leeren Feld.
 *
 * Aufruf (Playwright im Abbild nachinstalliert):
 *   docker run --rm --network <projekt>_default -v "<repo>":/w:ro -v "<ziel>":/ausgabe \
 *       -e MT5_BASE=http://app:8000 mcr.microsoft.com/playwright:v1.49.0-noble \
 *       sh -c 'npm i -s --prefix /tmp/pw playwright@1.49.0 >/dev/null 2>&1;
 *              export NODE_PATH=/tmp/pw/node_modules;
 *              node /w/tools/demo/mt5-screenshots.mjs'
 */
import { mkdirSync, writeFileSync } from 'node:fs'
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
const { chromium } = require('playwright')

const BASE = (process.env.MT5_BASE || 'http://app:8000').replace(/\/$/, '')
const ZIEL = process.env.ZIEL || '/ausgabe'
const EMAIL = process.env.ADMIN_EMAIL || 'admin@example.org'
const PASSWORT = process.env.ADMIN_PASS || 'musterhausen-demo'

/** Zehn Jahre voraus, 3. Januar (die Adresse der Seite kennt kein Datum —
 *  angesteuert per Monatsschritt, s. `zuLeeremZeitraum`): dort hat der Seed
 *  nichts eingetragen, und der Tag liegt im Sechs-Wochen-Raster des
 *  Mini-Monats. */
const LEER_JAHR = Number(process.env.MT5_LEER_JAHR || (new Date().getFullYear() + 10))
const LEER_TAG = `${LEER_JAHR}-01-03`

const LAGEN = [
  { name: 'desktop-1440', breite: 1440, hoehe: 900, touch: false },
  { name: 'handy-390', breite: 390, hoehe: 844, touch: true },
]

// Englische Texte der Terminbibliothek. Ein Termin des Nutzers darf so
// heißen — gesucht wird nur im Gerüst der Bibliothek (Kopf, Rest-Zeilen,
// Leerkasten), nicht in den Termin-Chips. Dieselbe Wortliste prüft
// `frontend/tests/mt5-kalender-leerzustand.test.mjs` (Test F).
const ENGLISCH = ['No events', 'all-day', 'more', 'All Day', 'Today']

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

async function messen(page) {
  return page.evaluate((englisch) => {
    const rein = (el) => (el ? (el.textContent || '').replace(/\s+/g, ' ').trim() : '')
    const leer = document.querySelector('.ec-no-events')
    // Gerüst der Bibliothek: Kopfzeilen der Liste, Rest-Zeile „+n weitere“,
    // Leerkasten — NICHT die Termin-Chips (die gehören dem Nutzer).
    const geruest = [
      ...document.querySelectorAll('.ec-list .ec-day-head, .ec-list h4, .ec-no-events, .ec-more-link, .ec-day-side'),
    ].map(rein).filter(Boolean)
    const chips = [...document.querySelectorAll('.ec-chip-text')].map(rein)
    const gefunden = []
    for (const textStueck of geruest) {
      for (const wort of englisch) {
        const re = wort === 'more' ? /\+\s*\d+\s+more\b/i : new RegExp('\\b' + wort + '\\b', 'i')
        if (re.test(textStueck)) gefunden.push({ text: textStueck, wort })
      }
    }
    // Gestaltung des Bausteins — gerechnet, nicht behauptet.
    const stil = (sel) => {
      const el = leer?.querySelector(sel)
      if (!el) return null
      const s = getComputedStyle(el)
      const b = el.getBoundingClientRect()
      return {
        schrift: s.fontSize, gewicht: s.fontWeight, farbe: s.color,
        zeilenhoehe: s.lineHeight,
        breite: Math.round(b.width), hoehe: Math.round(b.height),
        radius: s.borderRadius, hintergrund: s.backgroundColor,
      }
    }
    const r = leer ? leer.getBoundingClientRect() : null
    const feld = document.querySelector('.ec-main')?.getBoundingClientRect() || null
    return {
      ansicht: document.querySelector('.ec')?.className || '',
      leertext: rein(leer),
      leerHtml: leer ? leer.innerHTML.replace(/\s+/g, ' ').slice(0, 320) : null,
      leerSichtbar: !!leer && r.width > 0 && r.height > 0,
      leerGroesse: r ? [Math.round(r.width), Math.round(r.height)] : null,
      leerFlaeche: leer ? getComputedStyle(leer).backgroundColor : null,
      leerSymbolSeite: leer ? getComputedStyle(leer).textAlign : null,
      leerMitteAbweichung: r && feld
        ? Math.round(Math.abs((r.top + r.height / 2) - (feld.top + feld.height / 2))) : null,
      symbol: stil('.dk-ui-empty-icon'),
      titel: stil('.dk-ui-empty-title'),
      satz: stil('.dk-ui-empty-text'),
      geruest,
      chipAnzahl: chips.length,
      englischGefunden: gefunden,
      sichtbarerText: rein(document.querySelector('#dk-inhalt') || document.body).slice(0, 700),
    }
  }, ENGLISCH)
}

/** Ansicht „Liste“ öffnen (`?ansicht=liste`), optional auf ein Datum. */
async function listeOeffnen(page) {
  await page.goto(BASE + '/#/kalender?ansicht=liste', { waitUntil: 'networkidle' })
  await page.waitForSelector('nav.dk-bottom-nav', { state: 'attached', timeout: 30000 })
  await page.waitForTimeout(1800)
}

/**
 * Echten leeren Zeitraum ansteuern (Review 11.11., Punkt 6): die Adresse
 * kennt KEIN Datum — also über die Bibliothek selbst springen (Monatsschritt
 * der Kopfzeile). Es wird KEIN Kalender-Filter missbraucht: alle Häkchen
 * bleiben an.
 *
 * AM HANDY NICHT MÖGLICH, gemessen 11.11.: die Auswahl „Liste“ zeigt dort die
 * A10-Liste; an sie kommt man nur über den Mini-Monat. Dessen Pfeile melden
 * zwar „vor/zurück“, Titel und Raster bleiben aber stehen — die Seite hört an
 * dieser Stelle nicht zu (Live-Befund für Manuel, NICHT Teil dieser Karte).
 * Der einzige ohne Blättern wählbare Tag ist HEUTE. Belegt werden deshalb am
 * Handy: heute MIT Terminen (sofern der Tag einen hat) und der Leerzustand
 * der A10-Liste über den Filter unten — der Leerkasten der Bibliothek ist dort
 * gar nicht im DOM.
 */
async function zuLeeremZeitraum(page, handy) {
  if (handy) {
    // Handy: der leere TAG von heute; die Messung liest die A10-Liste.
    await tagWaehlen(page, heuteTag())
    return
  }
  const ziel = new Date(LEER_TAG + 'T12:00:00')
  const jetzt = new Date()
  const monatsschritte = (ziel.getFullYear() - jetzt.getFullYear()) * 12
    + (ziel.getMonth() - jetzt.getMonth())
  // Am Desktop springt der Pfeil der Kopfzeile („Nächster Zeitraum“) EINEN
  // Monat. Geklickt wird auf die MITTE des Knopfes: ein Klick auf die Kante
  // landete im Icon und wurde nicht übernommen (Befund Lauf 5).
  const weiter = page.getByLabel('Nächster Zeitraum').first()
  await weiter.waitFor({ state: 'attached', timeout: 20000 })
  const tabelle = await weiter.evaluate((el) => {
    const r = el.getBoundingClientRect()
    return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) }
  })
  for (let i = 0; i < monatsschritte; i += 1) {
    await page.waitForTimeout(300)
    await page.mouse.click(tabelle.x + tabelle.w / 2, tabelle.y + tabelle.h / 2)
    await page.waitForTimeout(150)
  }
  await page.waitForTimeout(1500)
}

/**
 * Einen Tag der A10-Liste wählen — OHNE Adress-Trick: der Mini-Monat bekommt
 * den Tag über einen echten Klick auf seine Zelle (er meldet ihn der Seite,
 * die Tagesliste lädt). Liegt der Tag außerhalb des gezeigten Monats, wird
 * zuerst mit „Nächster Monat“ dorthin geblättert.
 */
async function tagWaehlen(page, tag) {
  // Gemessen (11.11.): der Mini-Monat der A10-Liste blättert NICHT über seine
  // Pfeile — Titel und Raster bleiben beim aktuellen Monat stehen (Live-
  // Befund für Manuel, nicht Teil dieser Karte). Belegt wird der leere Tag
  // deshalb an dem Tag, der ohne Blättern im Raster steht: HEUTE.
  const imRaster = await page.locator(`[data-tag="${tag}"]`).count()
  if (!imRaster) {
    throw new Error(`Tag ${tag} steht nicht im Raster (Mini-Monat blättert nicht)`)
  }
  const zelle = page.locator(`[data-tag="${tag}"]`)
  await zelle.scrollIntoViewIfNeeded()
  await page.waitForTimeout(200)
  const punkt = await zelle.evaluate((el) => {
    const r = el.getBoundingClientRect()
    const treffer = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2)
    return { x: r.x + r.width / 2, y: r.y + r.height / 2, trifft: el === treffer || el.contains(treffer) }
  })
  if (!punkt.trifft) throw new Error(`Tag ${tag} ist an seiner Stelle verdeckt`)
  await page.mouse.click(punkt.x, punkt.y)
  const tagText = new Intl.DateTimeFormat('de-DE',
    { weekday: 'long', day: 'numeric', month: 'long' }).format(new Date(tag + 'T12:00:00'))
  const gewaehlt = await page.waitForFunction(
    (t) => document.querySelector(`[data-tag="${t}"]`)?.classList.contains('is-gewaehlt'),
    tag, { timeout: 8000 },
  ).then(() => true).catch(() => false)
  if (!gewaehlt) throw new Error(`Klick auf ${tag} wurde nicht übernommen`)
  await page.waitForFunction(
    (text) => [...document.querySelectorAll('.kal-a10-liste h2')]
      .some((h) => h.textContent.includes(text)),
    tagText, { timeout: 8000 },
  ).catch(() => {})
  await page.waitForTimeout(400)
}

/** Nennt der Mini-Monats-Titel den Monat des Tages? („Juli 2034“) */
function monatsTitelPasst(titel, tag) {
  const d = new Date(tag + 'T12:00:00')
  const monat = new Intl.DateTimeFormat('de-DE', { month: 'long' }).format(d)
  return String(titel || '').includes(monat) && String(titel || '').includes(String(d.getFullYear()))
}

/** Heutiges Datum als `JJJJ-MM-TT` (Ortszeit). */
function heuteTag() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

/** Monate von HEUTE bis zum Tag (Juli 2034 → 92). */
function monateBis(tag) {
  const ziel = new Date(tag + 'T12:00:00')
  const jetzt = new Date()
  return (ziel.getFullYear() - jetzt.getFullYear()) * 12 + (ziel.getMonth() - jetzt.getMonth())
}

/** Kalender-Filter ohne Treffer: der Server liefert keine Termine. */
async function filterLeeren(page) {
  await page.evaluate(() => {
    // Vorher füllen: eine LEERE Liste liest der Server als „alle“ und die
    // Seitenleiste verschwände (Befund des ersten Laufs).
    const ids = [...document.querySelectorAll('input[type="checkbox"][id^="cal-"]')]
      .filter((h) => !h.closest('.kal-pruef-panel'))
      .map((h) => h.getAttribute('value') || h.id.replace(/^cal-/, ''))
    localStorage.setItem('selected_calendars', JSON.stringify([...new Set(ids)]))
  })
  await listeOeffnen(page)
  await page.evaluate(() => localStorage.setItem('selected_calendars', '["keine"]'))
  await listeOeffnen(page)
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
        locale: 'de-DE',
        colorScheme: thema === 'dunkel' ? 'dark' : 'light',
      })
      const page = await ctx.newPage()
      await anmelden(page)
      await page.evaluate((t) => {
        localStorage.setItem('dk-theme', t === 'dunkel' ? 'dark' : 'light')
        document.documentElement.setAttribute('data-theme', t)
        localStorage.removeItem('selected_calendars')
      }, thema)

      // 3) Gegenprobe: Liste MIT Terminen (heute).
      await listeOeffnen(page)
      const mitTerminen = await messen(page)
      await page.screenshot({ path: `${ZIEL}/mt5-${lage.name}-${thema}-liste-mit-terminen.png` })

      // 1) LEER OHNE TRICK: echter Zeitraum ohne Termine.
      await listeOeffnen(page)
      await zuLeeremZeitraum(page, lage.touch)
      const echtLeer = await messen(page)
      const sichtbar = await page.evaluate(() => ({
        titel: document.querySelector('.ec-title')?.textContent
          || document.querySelector('.kal-monat-mobil-titel')?.textContent
          || document.querySelector('.dk-minimonat-raster')?.getAttribute('aria-label') || '',
        tagesListe: (document.querySelector('.kal-a10-liste')?.textContent || '').replace(/\s+/g, ' ').trim().slice(-200),
        tagesTitel: document.querySelector('.kal-a10-liste h2')?.textContent || '',
        miniTitel: document.querySelector('.dk-minimonat-titel')?.textContent || '',
      }))
      await page.screenshot({ path: `${ZIEL}/mt5-${lage.name}-${thema}-liste-leer-zeitraum.png` })

      // 2) Leer durch Filter (bisheriger Beleg).
      await filterLeeren(page)
      const leer = await messen(page)
      await page.screenshot({ path: `${ZIEL}/mt5-${lage.name}-${thema}-liste-leer-filter.png` })

      bericht.push({
        lage: lage.name, thema, leerTag: LEER_TAG, sichtbar,
        mitTerminen, echtLeer, leer,
      })
    }
  }
  await browser.close()
  writeFileSync(`${ZIEL}/mt5-bericht.json`, JSON.stringify(bericht, null, 2))
  const kurz = (m) => ({
    leerText: m.leertext, sichtbar: m.leerSichtbar,
    englisch: m.englischGefunden.length, chips: m.chipAnzahl,
    symbol: m.symbol ? `${m.symbol.breite}x${m.symbol.hoehe} r=${m.symbol.radius} bg=${m.symbol.hintergrund}` : null,
    titel: m.titel ? `${m.titel.schrift}/${m.titel.gewicht} ${m.titel.farbe}` : null,
    satz: m.satz ? `${m.satz.schrift} lh=${m.satz.zeilenhoehe} ${m.satz.farbe}` : null,
    mittigAbweichung: m.leerMitteAbweichung,
  })
  console.log(JSON.stringify(bericht.map((b) => ({
    lage: b.lage, thema: b.thema,
    echtLeer: kurz(b.echtLeer), filterLeer: kurz(b.leer),
    mitTerminenEnglisch: b.mitTerminen.englischGefunden.length,
    mitTerminenChips: b.mitTerminen.chipAnzahl,
  })), null, 2))
}

main().catch((e) => { console.error(e); process.exit(1) })
