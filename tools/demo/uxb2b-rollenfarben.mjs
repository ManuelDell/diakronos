/**
 * UX-B2b — Belege zu den Rollenfarben auf „Meine Dienste" (Variante D).
 *
 * Node-Fassung von tools/demo/uxb2b-rollenfarben.py. Sie laeuft im
 * Playwright-Image (Knoten + Chromium vorinstalliert) gegen den Wegwerf-Stack
 * (Projekt tbc481e56, Port 8463).
 *
 * Aufgenommen: #/planrahmen/meine-dienste als ADMIN, 1366x900 und 390x844,
 * je hell und dunkel — acht Bilder. Gemessen wird am LEBENDEN DOM
 * (getComputedStyle), nicht aus tokens.css nachgerechnet.
 *
 * Aufruf:
 *   docker run --rm --network tbc481e56_default \
 *     -v <worktree>:/w:ro -v <pw-dir>:/pw:ro -v <ziel>:/ausgabe \
 *     -e BASE=http://app:8000 mcr.microsoft.com/playwright:v1.49.0-noble \
 *     node /w/tools/demo/uxb2b-rollenfarben.mjs
 */
import { mkdirSync, writeFileSync } from 'node:fs'
import { createRequire } from 'node:module'

const require = createRequire('/pw/')
const { chromium } = require('playwright')

const BASE = process.env.BASE || 'http://app:8000'
const ZIEL = process.env.ZIEL || '/ausgabe'
// Mehrere Demo-Konten: sie sind in UNTERSCHIEDLICHEN Zellen eingeteilt — je
// nach Konto kommen andere Rollen vor (gemessen am Demo-Bestand:
// clara.imhof dirigiert UND spielt Klavier, elvira.dorn leitet Einsingen,
// die Verwaltung hat Einsingen). Deshalb wird BEIDES aufgenommen und im JSON
// getrennt ausgewiesen; nur so sind die Rollen mit ECHTEN Daten belegt.
const KONTEN = [
  { marke: 'dirigent', email: process.env.DIRIGENT_EMAIL || 'clara.imhof@example.org' },
  { marke: 'einsingen', email: process.env.EINSINGEN_EMAIL || 'elvira.dorn@example.org' },
]
const PASSWORT = process.env.DEMO_PASS || 'musterhausen-demo'
const SEITE = '#/planrahmen/meine-dienste'
const ERWARTET = ['accent', 'info', 'ok', 'warm-500', 'rueckfall']

const fehler = []
const gemessen = []

// ── Farbrechnung (dieselbe Formel wie der Node-Test) ─────────────────────
/**
 * Computed-Style-Farbe → [r, g, b] in 0..255.
 *
 * `color-mix(in srgb, …)` liefert im Chromium NICHT `rgb(…)`, sondern
 * `color(srgb 0.93 0.87 0.8)` mit Werten in 0..1 (getComputedStyle gibt die
 * Farbe so zurück, wie sie berechnet wurde). Beide Schreibweisen werden
 * gelesen — sonst wäre jede Mischfläche `NaN`.
 */
const nums = (t) => {
  const s = String(t).trim()
  let v
  if (s.startsWith('color(')) {
    // color(srgb r g b) — Werte 0..1, Farbraum-Name zuerst
    v = s.slice(s.indexOf('(') + 1, s.lastIndexOf(')')).split(/[\s/]+/).filter(Boolean)
    if (v[0] && Number.isNaN(Number(v[0]))) v = v.slice(1)
    return v.slice(0, 3).map((x) => Math.round(Number(x) * 255))
  }
  v = s.slice(s.indexOf('(') + 1, s.lastIndexOf(')')).split(',').slice(0, 3).map(Number)
  return v.map((x) => Math.round(x))
}
const lum = ([r, g, b]) => {
  const k = (v) => { const x = v / 255; return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4 }
  return 0.2126 * k(r) + 0.7152 * k(g) + 0.0722 * k(b)
}
const kontrast = (a, b) => {
  const la = lum(a); const lb = lum(b)
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05)
}
const lab = ([r0, g0, b0]) => {
  // Dieselbe Formel wie im Node-Test: sRGB 0..1 (der Test rechnet mit
  // Ganzzahlen 0..255, weil er /255 erst im Körper macht).
  const r = r0 / 255; const g = g0 / 255; const b = b0 / 255
  const f = (t) => (t > 0.008856 ? Math.cbrt(t) : 7.787 * t + 16 / 116)
  const x = f((0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047)
  const y = f(0.2126 * r + 0.7152 * g + 0.0722 * b)
  const z = f((0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883)
  return [116 * y - 16, 500 * (x - y), 200 * (y - z)]
}
const deltaE = (a, b) => {
  const p = lab(a); const q = lab(b)
  return Math.hypot(p[0] - q[0], p[1] - q[1], p[2] - q[2])
}

function pruefe(marke, bedingung, meldung) {
  if (!bedingung) fehler.push(`${marke}: ${meldung}`)
}

async function anmelden(page, email) {
  await page.goto(BASE + '/', { waitUntil: 'networkidle' })
  await page.waitForTimeout(400)
  await page.fill('#dk-usr', email)
  await page.fill('#dk-pwd', PASSWORT)
  await page.keyboard.press('Enter')
  await page.waitForTimeout(3000)
  await page.waitForLoadState('networkidle')
}

/** Die Wahrheit des Browsers: gerenderte Flaeche/Schrift je Rollenzeichen. */
function messen(page) {
  return page.evaluate(() => {
    const sichtbar = (el) => { const r = el.getBoundingClientRect(); return r.width > 2 && r.height > 2 }
    const lies = (el) => {
      const st = getComputedStyle(el)
      return {
        art: el.dataset.art || null,
        text: (el.textContent || '').trim(),
        background: st.backgroundColor,
        color: st.color,
        border: st.borderTopColor,
        sichtbar: sichtbar(el),
        beleg: el.closest('[data-beleg]') ? 'kuenstlich' : 'demo',
      }
    }
    const karte = document.querySelector('.pr-md-monat')
    return {
      legende: [...document.querySelectorAll('.pr-md-legende .pr-md-rolle-zeichen')].map(lies),
      zeilen: [...document.querySelectorAll('.pr-md-monat-zeile .pr-md-rolle-zeichen')].map(lies),
      zeilenTexte: [...document.querySelectorAll('.pr-md-monat-zeile')].map((z) => ({
        rolle: (z.querySelector('.pr-md-feld') || {}).textContent || '',
        datum: (z.querySelector('.pr-md-datum') || {}).textContent || '',
        beleg: z.dataset.beleg || 'demo',
      })),
      karteFlaeche: karte ? getComputedStyle(karte).backgroundColor : null,
      thema: document.documentElement.dataset.theme || '(hell)',
      leer: !!document.querySelector('.dk-empty'),
    }
  })
}

/**
 * Die Demo belegt Dirigent/Klavier/Einsingen. `solo` (Chorplan, Feld
 * `lieder[].solo`) laesst das Seed leer, eine UNBEKANNTE Rolle („Prediger")
 * kommt in einem Chorplan gar nicht vor. Fuer „eine Seite mit allen vier
 * Rollen + einer unbekannten Rolle" werden deshalb ZWEI Zeilen mit den
 * vorhandenen Komponenten-Klassen ergaenzt (reine Anzeige, im JSON als
 * `beleg: kuenstlich` markiert); die Farbwerte stammen ausschliesslich aus dem
 * gerenderten CSS der echten Rollenzeichen.
 */
function rollenSetzen(page, vorhanden) {
  return page.evaluate((schonDa) => {
    const liste = document.querySelector('.pr-md-monat-liste')
    if (!liste) return { fehlt: 'keine Monatsliste' }
    const vorlage = liste.querySelector('.pr-md-monat-zeile')
    if (!vorlage) return { fehlt: 'keine Zeile als Vorlage' }
    const alle = [
      { art: 'accent', zeichen: 'D', feld: 'Dirigent', lied: 'EG 317 — Lobe den Herren' },
      { art: 'info', zeichen: 'K', feld: 'Klavier', lied: 'EG 317 — Lobe den Herren' },
      { art: 'ok', zeichen: 'S', feld: 'Solo', lied: 'EG 317 — Lobe den Herren' },
      { art: 'warm-500', zeichen: 'E', feld: 'Einsingen', lied: '' },
      { art: 'rueckfall', zeichen: 'P', feld: 'Prediger', lied: '' },
    ]
    // Das Stil-Element ist `<style scoped>`: Vue hängt an jedes Element ein
    // `data-v-…`-Merkmal, und die CSS-Selektoren verlangen es MIT. Ohne dieses
    // Merkmal greift KEINE Regel — die Belegzeile bliebe nackter Text. Das
    // Merkmal wird deshalb von der Vorlage übernommen (nie erfunden).
    const merkmal = [...vorlage.attributes].map((a) => a.name).find((n) => n.startsWith('data-v-'))
    const zusatz = alle.filter((z) => !schonDa.includes(z.art))
    for (const z of zusatz) {
      const neu = vorlage.cloneNode(true)
      if (merkmal) neu.setAttribute(merkmal, '')
      const zeichen = neu.querySelector('.pr-md-rolle-zeichen')
      zeichen.dataset.art = z.art
      zeichen.textContent = z.zeichen
      zeichen.title = z.feld
      zeichen.setAttribute('aria-label', z.feld)
      const feld = neu.querySelector('.pr-md-feld')
      if (feld) feld.textContent = z.feld
      const lied = neu.querySelector('.pr-md-lied')
      if (lied) { if (z.lied) lied.textContent = z.lied; else lied.remove() }
      const knopf = neu.querySelector('.pr-md-monat-aktion')
      if (knopf) knopf.remove()
      neu.dataset.beleg = 'kuenstlich'
      liste.appendChild(neu)
    }
    const legende = document.querySelector('.pr-md-legende')
    if (legende) {
      const da = new Set([...legende.querySelectorAll('.pr-md-rolle-zeichen')].map((el) => el.dataset.art))
      for (const z of alle) {
        if (da.has(z.art)) continue
        const punkt = document.createElement('li')
        punkt.className = 'pr-md-legende-punkt'
        punkt.dataset.art = z.art
        punkt.dataset.beleg = 'kuenstlich'
        if (merkmal) punkt.setAttribute(merkmal, '')
        const sp = document.createElement('span')
        sp.className = 'pr-md-rolle-zeichen'
        sp.dataset.art = z.art
        if (merkmal) sp.setAttribute(merkmal, '')
        sp.setAttribute('aria-hidden', 'true')
        sp.textContent = z.zeichen
        punkt.appendChild(sp)
        punkt.appendChild(document.createTextNode(' ' + z.feld))
        legende.appendChild(punkt)
      }
    }
    return { ergaenzt: zusatz.map((z) => z.art) }
  }, vorhanden)
}

async function lauf(browser, breite, hoehe, dunkel, konto) {
  const voll = breite <= 720
  const ctx = await browser.newContext({ viewport: { width: breite, height: hoehe }, locale: 'de-DE', ignoreHTTPSErrors: true })
  if (dunkel) {
    await ctx.addInitScript(() => { try { localStorage.setItem('dk-theme', 'dark') } catch { /* egal */ } })
  }
  const page = await ctx.newPage()
  const marke = breite <= 720 ? 'mobil' : 'desktop'
  const kennung = `${marke}-${dunkel ? 'dunkel' : 'hell'}-${konto.marke}`
  try {
    await anmelden(page, konto.email)
    await page.goto(BASE + '/' + SEITE, { waitUntil: 'networkidle' })
    await page.waitForTimeout(1500)
    await page.waitForSelector('.pr-md-monat-zeile', { timeout: 15000 }).catch(() => {})

    const roh = await messen(page)
    pruefe(kennung, !roh.leer, 'Seite meldet „keine Dienste" (Demo-Bestand fehlt?)')
    pruefe(kennung, roh.zeilen.length > 0, 'keine Dienstzeilen im DOM')
    // Welche Rollen bringt dieses Konto aus ECHTEN Daten mit?
    const echteArten = [...new Set(roh.zeilen.map((z) => z.art).filter(Boolean))].sort()

    const erg = await rollenSetzen(page, echteArten)
    await page.waitForTimeout(300)
    if (erg && erg.fehlt) pruefe(kennung, false, erg.fehlt)

    const daten = await messen(page)
    const zeichen = daten.zeilen.filter((z) => z.art)
    const arten = [...new Set(zeichen.map((z) => z.art))].sort()

    const flaechen = {}
    const texte = {}
    for (const art of arten) {
      const t = zeichen.find((z) => z.art === art)
      const fl = t.background
      // Der Rückfall hat KEINE Fläche (transparent) — dort ist der Untergrund
      // die Karte selbst, also wird gegen die Kartenfläche gemessen.
      const hintergrund = fl === 'rgba(0, 0, 0, 0)' ? daten.karteFlaeche : fl
      flaechen[art] = nums(hintergrund)
      texte[art] = Number(kontrast(nums(t.color), nums(hintergrund)).toFixed(2))
      pruefe(kennung, t.sichtbar, `Rollenzeichen ${art} nicht sichtbar`)
      pruefe(kennung, texte[art] >= 4.5, `Textkontrast ${art}: ${texte[art]}:1 unter 4,5:1`)
    }
    const abstaende = {}
    for (let i = 0; i < arten.length; i++) {
      for (let j = i + 1; j < arten.length; j++) {
        const a = arten[i]; const b = arten[j]
        abstaende[`${a}/${b}`] = Number(deltaE(flaechen[a], flaechen[b]).toFixed(1))
      }
    }
    const legendenArten = [...new Set(daten.legende.map((z) => z.art).filter(Boolean))].sort()
    pruefe(kennung, arten.every((a) => legendenArten.includes(a)),
      `Legende zeigt ${legendenArten}, Zeilen ${arten}`)

    // Der Rückfall darf KEINEN Rollenton tragen (nur Rahmen).
    const rueck = zeichen.find((z) => z.art === 'rueckfall')
    if (rueck) {
      pruefe(kennung, rueck.background === 'rgba(0, 0, 0, 0)' ||
        nums(rueck.background).join() === nums(daten.karteFlaeche).join(),
        `Rückfall trägt einen Ton (${rueck.background} statt Kartenfläche ${daten.karteFlaeche})`)
    }

    gemessen.push({
      kennung, konto: konto.marke, breite, dunkel, thema: daten.thema,
      karteFlaeche: daten.karteFlaeche,
      artenZeilen: arten, artenEcht: echteArten, artenLegende: legendenArten,
      flaechen: Object.fromEntries(Object.entries(flaechen).map(([k, v]) => [k, `rgb(${v.join(',')})`])),
      textkontrast: texte, deltaE: abstaende,
      kuenstlich: (erg && erg.ergaenzt) || [],
      zeilen: daten.zeilenTexte,
    })

    const datei = `${ZIEL}/uxb2b-meine-dienste-${kennung}.png`
    await page.screenshot({ path: datei, fullPage: voll })
    console.log('geschrieben', datei.split('/').pop(), '| Rollen echt:', echteArten.join(',') || '—')
  } finally {
    await ctx.close()
  }
}

const browser = await chromium.launch()
mkdirSync(ZIEL, { recursive: true })
try {
  for (const konto of KONTEN) {
    await lauf(browser, 1366, 900, false, konto)
    await lauf(browser, 1366, 900, true, konto)
    await lauf(browser, 390, 844, false, konto)
    await lauf(browser, 390, 844, true, konto)
  }
} finally {
  await browser.close()
}
// Gesamtabnahme: alle vier Rollen + Rückfall müssen irgendwo mit ECHTEN
// Daten vorkommen (sonst wäre der Beleg nur aus Belegzeilen gebaut).
const alleArten = new Set(gemessen.flatMap((g) => g.artenZeilen))
for (const art of ERWARTET) {
  pruefe('gesamt', alleArten.has(art), `Rolle ${art} kommt auf keiner Seite vor`)
}
writeFileSync(`${ZIEL}/uxb2b-messung.json`, JSON.stringify({ gemessen, fehler }, null, 2), 'utf-8')
console.log(JSON.stringify({ fehler, aufnahmen: gemessen.length }))
process.exit(fehler.length ? 1 : 0)
