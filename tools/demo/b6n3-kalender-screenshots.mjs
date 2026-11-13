/**
 * B6-N3 — Belege: Monatsraster zeigt am Desktop UND am Handy alle Wochen,
 * die Zeilen-Mindesthöhe greift nur im schmalen Maus-Fenster (≤ 720 px).
 *
 * WARUM (Review-Runde 2, Punkt A und E · Runde 3, Punkte 1-3 und 6)
 * ------------------------------------------------------------------
 * B6-N2 setzte `--ec-row-height: minmax(var(--kal-zeile-min), 1fr)` GLOBAL.
 * In der Monatsansicht ist `.ec-main` ein Raster mit `overflow: hidden`; die
 * Untergrenze macht es höher als seinen Kasten und die überzähligen Wochen
 * werden ABGESCHNITTEN (Beleg b6n2n: 1440×900 nur 4 von 6 Wochen).
 *
 * Runde 3: Die Mindesthöhe hängt jetzt an `.kal-flaeche` (gibt es nur
 * ausserhalb der Handy-Lage) UND an der Breite; der Mobil-Bau ist wieder der
 * von main. GEMESSEN wird deshalb nicht „sind Termine im DOM“, sondern die
 * SICHTBARKEIT der Wochen gegen ihren Behälter (getBoundingClientRect):
 *   * jede Wochenzeile (`.ec-day`, nach `top` gruppiert),
 *   * ihr Abstand zur Unterkante des Rasters/der Fläche,
 *   * wie viele Wochen VOLLSTÄNDIG im Kasten liegen,
 *   * ob die Fläche scrollen kann (dann ist Abschneiden erlaubt).
 * In der Handy-Lage zusätzlich für MONAT **und** WOCHE:
 *   * die Zeilenhöhen und die Gesamthöhe des Bibliotheksrasters (muss dem
 *     main-Stand entsprechen),
 *   * ob es einen Scrollweg gibt (B6-N3b: am Handy scrollt die SEITE, der
 *     Halter steht wie main auf `min-height: 100%`),
 *   * die obere Kante des Rasters (Startstunde der Woche).
 *
 * Lagen (Karte): 1440, 1280, 900, 721, 720, 702, 400 (Maus) + Handy 390
 * (grober Zeiger), je hell und dunkel. Zusätzlich 1280×450 mit MAUS (flaches
 * Fenster: OP-HANDY-9 darf dort NICHT greifen) und 844×390 mit grobem Zeiger
 * (Handy quer).
 *
 * BELEGE: siehe Tabelle im Kartenkommentar; Rohzahlen in `b6n3-bericht.json`.
 *
 * Aufruf:
 *   docker run --rm --network <projekt>_default -v "<repo>":/w:ro -v "<ziel>":/ausgabe \
 *       -e B6N3_BASE=http://app:8000 mcr.microsoft.com/playwright:v1.49.0-noble \
 *       sh -c 'npm i -s --prefix /tmp/pw playwright@1.49.0 >/dev/null 2>&1;
 *              export NODE_PATH=/tmp/pw/node_modules;
 *              node /w/tools/demo/b6n3-kalender-screenshots.mjs'
 */
import { mkdirSync, writeFileSync } from 'node:fs'
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
const { chromium } = require('playwright')

const BASE = (process.env.B6N3_BASE || 'http://app:8000').replace(/\/$/, '')
const ZIEL = process.env.ZIEL || '/ausgabe'
const EMAIL = process.env.ADMIN_EMAIL || 'admin@example.org'
const PASSWORT = process.env.ADMIN_PASS || 'musterhausen-demo'

const LAGEN = [
  { name: 'desktop-1440x900-fine', breite: 1440, hoehe: 900, touch: false },
  { name: 'desktop-1280x800-fine', breite: 1280, hoehe: 800, touch: false },
  { name: 'desktop-900x800-fine', breite: 900, hoehe: 800, touch: false },
  // Grenze: 721 px ist NICHT mehr schmal, 720 px ist schmal (dieselbe Zahl
  // fuer .kal-karte/.kal-flaeche UND fuer die Mindesthoehe).
  { name: 'grenze-721x800-fine', breite: 721, hoehe: 800, touch: false },
  { name: 'grenze-720x800-fine', breite: 720, hoehe: 800, touch: false },
  { name: 'schmal-702x894-fine', breite: 702, hoehe: 894, touch: false },
  { name: 'schmal-400x800-fine', breite: 400, hoehe: 800, touch: false },
  // Handy: die Seite startet in der LISTE (A10-Bau). Fuer Monat und Woche wird
  // das jeweilige Segment getippt — belegt wird der ECHTE Weg.
  { name: 'handy-390x844-coarse-monat', breite: 390, hoehe: 844, touch: true, mobilAnsicht: 'Monat' },
  { name: 'handy-390x844-coarse-woche', breite: 390, hoehe: 844, touch: true, mobilAnsicht: 'Woche' },
  // Punkt A: flaches Fenster mit MAUS — darf KEINE 72-px-Zeilen bekommen.
  { name: 'laptop-flach-1280x450-fine', breite: 1280, hoehe: 450, touch: false },
  // Gegenprobe: Handy quer (OP-HANDY-9) — dort ist Scrollen der richtige Weg.
  { name: 'handy-quer-844x390-coarse-monat', breite: 844, hoehe: 390, touch: true, mobilAnsicht: 'Monat' },
]

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

/** Kalender öffnen und warten, bis das Monatsraster wirklich steht. */
async function kalenderOeffnen(page, timeoutMs = 20000) {
  await page.goto(BASE + '/#/kalender', { waitUntil: 'networkidle' })
  const ende = Date.now() + timeoutMs
  while (Date.now() < ende) {
    const bereit = await page.evaluate(() => {
      const main = document.querySelector('.ec-day-grid.ec-month-view .ec-main')
      return !!main && document.querySelectorAll('.ec-day-grid.ec-month-view .ec-day').length >= 28
    }).catch(() => false)
    if (bereit) break
    await page.waitForTimeout(250)
  }
  // Danach noch einen Frame für Schrift/Layout abwarten.
  await page.waitForTimeout(800)
  await page.evaluate(() => new Promise((fertig) => requestAnimationFrame(() => requestAnimationFrame(fertig))))
}

/** A10-Kopfzeile: Segment („Monat“/„Woche“) antippen — echter Klick. */
async function mobilAnsichtWaehlen(page, label) {
  // Ueber das DATA-Attribut waehlen: zwei Segmente koennen denselben Text
  // tragen (Monat/Woche/Liste), `hasText` griffe dann das falsche.
  const kennung = label.toLowerCase()
  const knopf = page.locator(`button.dk-mobilkopf-segment[data-ansicht="${kennung}"]`)
  if (await knopf.count()) await knopf.first().click()
  else await page.locator('button.dk-mobilkopf-segment', { hasText: new RegExp('^' + label + '$') }).first().click()
  // Warten, bis der Raster-Kasten die gewaehlte Ansicht traegt (die Bibliothek
  // tauscht das Raster nach dem Umschalten aus).
  const klasse = label === 'Woche' ? '.ec-time-grid' : '.ec-day-grid'
  for (let i = 0; i < 40; i += 1) {
    const passt = await page.evaluate((sel) => {
      const h = document.querySelector('.kal-mobil-raster-halter:not(.offscreen) .ec-day-grid')
      return !!h && !!h.querySelector(sel)
    }, klasse).catch(() => false)
    if (passt) break
    await page.waitForTimeout(250)
  }
  await page.waitForTimeout(900)
  await page.evaluate(() => new Promise((fertig) => requestAnimationFrame(() => requestAnimationFrame(fertig))))
}

/** Handy (A10): Bibliotheksraster von Monat/Woche vermessen. */
async function messenHandy(page) {
  return page.evaluate(() => {
    const runden = (v) => Math.round(v)
    const seite = document.querySelector('.kronos-page-content')
    const handyKlasse = !!document.querySelector('.dk-app--handy')
    // Erst auf die gewaehlte Ansicht warten — nach dem Umschalten baut die
    // Bibliothek das Raster kurz neu (der alte Monat steht noch im DOM).
    const raster = document.querySelector('.kal-mobil-raster-halter:not(.offscreen) .ec-day-grid')
    if (!raster) return { handy: true, handyKlasse, raster: null, grund: 'kein Bibliotheksraster im DOM' }
    // Sichtbaren Raster-Kasten finden: der naechste Vorfahre von `.ec-day-grid`,
    // der tatsaechlich scrollen kann. B6-N3b: Der Mobil-Bau ist wieder der von
    // main — am Handy scrollt die SEITE (`.kronos-page-content`), der Halter
    // (`min-height: 100%`) und der innere Kasten bringen KEIN eigenes Scrollen
    // mit. Waehrend der Suche wird deshalb angehalten, sobald der Scrollkasten
    // die Seite ist (dann ist der Weg oben/unten gemeint).
    const wrap = (() => {
      let e = raster.parentElement
      while (e && e !== document.body) {
        if (/(auto|scroll)/.test(getComputedStyle(e).overflowY)) return e
        e = e.parentElement
      }
      return raster.parentElement
    })()
    const rr = raster.getBoundingClientRect()
    if (rr.height < 20) {
      return { handy: true, handyKlasse, raster: null, grund: 'Raster unsichtbar (Halter offscreen)' }
    }
    // Ansicht am INHALT erkennen: die Woche baut ein Zeitraster mit
    // Tagesspalten (`ec-col-head`/`.ec-day-side`), der Monat ein Tagesraster
    // mit 7 Zellen je Woche. Die Klassen `ec-month-view`/`ec-week-view` tragen
    // BEIDE Raster — sie taugen nicht als Unterscheidung.
    // Zeitraster (Woche): KEINE Tagesspalten (`.ec-day`) — es hat seine eigene
    // Kopflinie (`.ec-col-head` je Tag) und Stundenzeilen. Das Monatsraster hat
    // 28+ `.ec-day`-Zellen. (Ein `ec-col-head` gibt es in BEIDEN: im Monat ist
    // es der Wochen-Kopf, ein Element mit nur der Wochennummer.)
    const ansicht = raster.querySelectorAll('.ec-day').length >= 28
      ? 'monat'
      : (raster.querySelectorAll('.ec-col-head').length ? 'woche' : 'unbekannt')
    // Zeilen: Zellen nach ihrer Oberkante gruppieren.
    // Monat: Tagesspalten (`.ec-day`). Woche: Tagesspalten des Zeitrasters
    // (`.ec-col`) — beides nach Oberkante gruppiert.
    const spalten = ansicht === 'woche'
      ? [...raster.querySelectorAll('.ec-col-head')]
      : [...raster.querySelectorAll('.ec-day')]
    const zeilen = new Map()
    for (const zelle of spalten) {
      const r = zelle.getBoundingClientRect()
      if (r.width < 1 && r.height < 1) continue
      const k = runden(r.top)
      const e = zeilen.get(k) || { top: r.top, unten: r.bottom, zellen: 0 }
      e.unten = Math.max(e.unten, r.bottom); e.zellen += 1
      zeilen.set(k, e)
    }
    const reihen = [...zeilen.values()].sort((a, b) => a.top - b.top)
    // Sichtbar ist, was zwischen Oberkante des Rasters und Unterkante des
    // inneren Kastens liegt (der Kasten schneidet, die Seite darf scrollen).
    const wr = wrap ? wrap.getBoundingClientRect() : rr
    const sichtbar = reihen.filter((r) => r.top >= wr.top - 1 && r.unten <= wr.bottom + 1)
    const hoehen = reihen.map((r) => runden(r.unten - r.top))
    return {
      fenster: [window.innerWidth, window.innerHeight],
      handyKlasse,
      handy: true,
      ansicht,
      raster: {
        ansicht,
        wochen: reihen.length,
        wochenVollstaendig: sichtbar.length,
        zeilenHoehen: hoehen,
        zeileMin: hoehen.length ? Math.min(...hoehen) : null,
        zeileMax: hoehen.length ? Math.max(...hoehen) : null,
        kasten: [runden(rr.width), runden(rr.height)],
        oberkante: runden(rr.top),
        kastenUnten: runden(wr.bottom),
      },
      scrollkasten: wrap ? {
        klasse: String(wrap.className).split(' ')[0],
        scrollt: wrap.scrollHeight > wrap.clientHeight + 1,
        scrollHoehe: wrap.scrollHeight,
        kundHoehe: wrap.clientHeight,
      } : null,
      seite: seite ? {
        scrollt: seite.scrollHeight > seite.clientHeight + 1,
        scrollHoehe: seite.scrollHeight,
        kundHoehe: seite.clientHeight,
      } : null,
      termine: raster.querySelectorAll('.ec-event').length,
      flaeche: null,
      karte: null,
    }
  })
}

/** Desktop/schmales Fenster: Monatsraster vermessen. */
async function messen(page) {
  return page.evaluate(() => {
    const runden = (v) => Math.round(v)
    const handyBau = !!document.querySelector('.kal-a10, .kal-mobil-raster, .kal-monat-mobil')
    if (handyBau) return { raster: null, handyBau, grund: 'Handy-Bau im DOM' }
    const main = document.querySelector('.kal-flaeche .ec-day-grid.ec-month-view .ec-main')
      || document.querySelector('.ec-day-grid.ec-month-view .ec-main')
      || document.querySelector('.ec-main')
    const flaeche = document.querySelector('.kal-flaeche')
    const karte = document.querySelector('.kal-karte')
    const tage = [...document.querySelectorAll('.ec-day')]
    if (!main || !tage.length) {
      return { raster: null, handyBau, grund: 'kein Monatsraster im DOM' }
    }
    // Wochenzeilen: Tage nach ihrer Oberkante gruppieren.
    const zeilen = new Map()
    for (const tag of tage) {
      const r = tag.getBoundingClientRect()
      if (r.width < 1 && r.height < 1) continue
      const schluessel = runden(r.top)
      const eintrag = zeilen.get(schluessel) || { top: r.top, unten: r.bottom, zellen: 0 }
      eintrag.unten = Math.max(eintrag.unten, r.bottom)
      eintrag.zellen += 1
      zeilen.set(schluessel, eintrag)
    }
    const reihen = [...zeilen.values()].sort((a, b) => a.top - b.top)
    const mr = main.getBoundingClientRect()
    const fr = flaeche ? flaeche.getBoundingClientRect() : null
    const kr = karte ? karte.getBoundingClientRect() : null
    // Untere Grenze, an der abgeschnitten würde: der nächste Kasten mit
    // `overflow: hidden` (Raster) bzw. der Scrollkasten der Fläche.
    const grenze = Math.min(
      ...[mr.bottom, fr ? fr.bottom : Infinity, kr ? kr.bottom : Infinity],
    )
    const sichtbar = reihen.filter((r) => r.top >= mr.top - 1 && r.unten <= grenze + 1)
    const angeschnitten = reihen.filter((r) => r.unten > grenze + 1)
    const hoehen = reihen.map((r) => runden(r.unten - r.top))
    const stiflaeche = flaeche ? getComputedStyle(flaeche) : null
    return {
      fenster: [window.innerWidth, window.innerHeight],
      zeiger: {
        fine: matchMedia('(pointer: fine)').matches,
        coarse: matchMedia('(pointer: coarse)').matches,
      },
      handyKlasse: !!document.querySelector('.dk-app--handy'),
      raster: {
        wochen: reihen.length,
        wochenVollstaendig: sichtbar.length,
        wochenAngeschnitten: angeschnitten.length,
        letzteWocheAngeschnittenUm: angeschnitten.length
          ? runden(Math.max(...angeschnitten.map((r) => r.unten - grenze))) : 0,
        zeilenHoehen: hoehen,
        zeileMin: hoehen.length ? Math.min(...hoehen) : null,
        zeileMax: hoehen.length ? Math.max(...hoehen) : null,
        rowHeightToken: getComputedStyle(main).getPropertyValue('--ec-row-height').trim(),
        kalZeileMin: getComputedStyle(document.documentElement)
          .getPropertyValue('--kal-zeile-min').trim(),
        kasten: [runden(mr.width), runden(mr.height)],
        grenze: runden(grenze),
      },
      flaeche: fr ? {
        box: [runden(fr.width), runden(fr.height)],
        overflow: stiflaeche.overflow,
        overflowY: stiflaeche.overflowY,
        scrollt: flaeche.scrollHeight > flaeche.clientHeight + 1,
        scrollHoehe: flaeche.scrollHeight,
        kundHoehe: flaeche.clientHeight,
      } : null,
      karte: kr ? { box: [runden(kr.width), runden(kr.height)] } : null,
      termine: document.querySelectorAll('.ec-day-grid.ec-month-view .ec-event').length,
      weitere: [...document.querySelectorAll('.ec-more-link')].length,
      a10: false,
    }
  })
}

/** Urteil je Lage — nach DENSELBEN Regeln wie die Karte. */
function urteilFuer(lage, daten) {
  const schmal = lage.breite <= 720 && !lage.touch
  if (daten.handy) {
    if (!daten.raster) return `FEHLER Handy: kein Raster gemessen (${daten.grund || '—'})`
    const r = daten.raster
    if (r.wochen < 4) return 'FEHLER: zu wenige Zeilen gemessen'
    if (r.wochenVollstaendig === r.wochen) {
      return `OK Handy ${r.ansicht}: ${r.wochenVollstaendig}/${r.wochen} Zeilen ganz, ` +
        `Zeile ${r.zeileMin}-${r.zeileMax} px (Höhe ${r.kasten[1]} px, oben ${r.oberkante})`
    }
    const scrollweg = !!daten.scrollkasten?.scrollt || !!(daten.seite && daten.seite.scrollt)
    return `FEHLER Handy ${r.ansicht} abgeschnitten: ${r.wochenVollstaendig}/${r.wochen}, ` +
      `Scrollweg ${scrollweg ? 'da' : 'fehlt'}`
  }
  const r = daten.raster
  if (!r) return `kein Raster gemessen (${daten.grund || '—'})`
  if (r.wochen < 4) return 'FEHLER: zu wenige Wochen gemessen'
  const scrollweg = !!daten.flaeche?.scrollt
  if (schmal) {
    return r.zeileMin >= 80 && scrollweg
      ? `OK schmal: Zeile ${r.zeileMin} px, Fläche scrollt (${r.wochenVollstaendig}/${r.wochen} ganz)`
      : `FEHLER schmal: Zeile ${r.zeileMin} px, Fläche scrollt ${scrollweg ? 'ja' : 'NEIN'}`
  }
  return r.wochenVollstaendig === r.wochen
    ? `OK: alle ${r.wochen} Wochen vollständig (Zeile ${r.zeileMin} px)`
    : `FEHLER abgeschnitten: ${r.wochenVollstaendig}/${r.wochen}, ${r.wochenAngeschnitten} Zeilen, ` +
      `unterste ${r.letzteWocheAngeschnittenUm} px hinter der Grenze`
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
      }, thema)
      await kalenderOeffnen(page)
      if (lage.mobilAnsicht) await mobilAnsichtWaehlen(page, lage.mobilAnsicht)
      const daten = lage.mobilAnsicht ? await messenHandy(page) : await messen(page)
      const urteil = urteilFuer(lage, daten)
      await page.screenshot({ path: `${ZIEL}/b6n3-kalender-${lage.name}-${thema}.png` })
      bericht.push({ lage: lage.name, thema, urteil, ...daten })
      await ctx.close()
    }
  }
  await browser.close()
  writeFileSync(`${ZIEL}/b6n3-bericht.json`, JSON.stringify(bericht, null, 2))
  console.log(JSON.stringify(bericht.map((b) => ({
    lage: b.lage,
    thema: b.thema,
    urteil: b.urteil,
    raster: b.raster ? {
      ansicht: b.raster.ansicht || null,
      zeilen: b.raster.wochen,
      voll: b.raster.wochenVollstaendig,
      angeschnitten: b.raster.wochenAngeschnitten ?? null,
      zeileMin: b.raster.zeileMin,
      zeileMax: b.raster.zeileMax,
      kasten: b.raster.kasten,
      oberkante: b.raster.oberkante ?? null,
      rowHeightToken: b.raster.rowHeightToken || null,
    } : null,
    flaeche: b.flaeche ? { scrollt: b.flaeche.scrollt, overflow: b.flaeche.overflow, hoehen: [b.flaeche.scrollHoehe, b.flaeche.kundHoehe] } : null,
    scrollkasten: b.scrollkasten || null,
    seite: b.seite || null,
  })), null, 2))
}

main().catch((e) => { console.error(e); process.exit(1) })
