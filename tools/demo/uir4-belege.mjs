/**
 * UI-R4 — Belege: Prüfliste mit Moderationsstufen + Freigabe-Anträge.
 *
 * Vier Lagen (Desktop 1440 + Handy 390, hell/dunkel) der Seite „Zu prüfen“,
 * dazu die ECHTEN Serverantworten (get_kanban_board_data / get_moderation_count
 * / get_rollen_erklaerung / get_offene_sichtbarkeits_antraege) und ein
 * zweistufiger Vorschlag (Gruppenleitung gibt frei → wartet auf die Gemeinde).
 *
 * Aufruf im Wegwerf-Netz:
 *   docker run --rm --network uir4_default -v "$PWD/tools/demo":/w:ro \
 *     -v <ziel>:/ausgabe -e UIR4_BASE=http://app:8000 \
 *     mcr.microsoft.com/playwright:v1.49.0-noble \
 *     sh -c 'npm i -s --prefix /tmp/pw playwright@1.49.0 >/dev/null 2>&1;
 *            export NODE_PATH=/tmp/pw/node_modules; node /w/uir4-belege.mjs'
 */
import { chromium } from 'playwright'
import fs from 'node:fs'

const BASIS = process.env.UIR4_BASE || 'http://app:8000'
const ZIEL = process.env.UIR4_ZIEL || '/ausgabe'
const PASS = process.env.UIR4_PASS || 'musterhausen-demo'
const MODERATOR = process.env.UIR4_MODERATOR || 'admin@example.org'
const MITGLIED = process.env.UIR4_MITGLIED || 'anna.beispiel@example.org'

const LAGEN = [
  { name: 'desktop-1440-hell', breite: 1440, hoehe: 900, dunkel: false, handy: false },
  { name: 'desktop-1440-dunkel', breite: 1440, hoehe: 900, dunkel: true, handy: false },
  { name: 'handy-390-hell', breite: 390, hoehe: 844, dunkel: false, handy: true },
  { name: 'handy-390-dunkel', breite: 390, hoehe: 844, dunkel: true, handy: true },
]

fs.mkdirSync(ZIEL, { recursive: true })
const bericht = { fehler: [], lagen: [], server: {}, ablauf: {} }

/** Anmeldung über die ECHTE Maske (Demo-Passwort). */
async function anmelden(page, email) {
  await page.goto(BASIS + '/diakonos', { waitUntil: 'networkidle' })
  await page.waitForTimeout(800)
  const form = page.locator('input[type="text"], input[name="email"], input[type="email"]').first()
  if (await form.count()) {
    await form.fill(email)
    const pw = page.locator('input[type="password"]').first()
    await pw.fill(PASS)
    await page.locator('button[type="submit"], button:has-text("Anmelden")').first().click()
    await page.waitForTimeout(2500)
  }
  await page.goto(BASIS + '/diakonos#/kalender/pruefen', { waitUntil: 'networkidle' })
  await page.waitForTimeout(2500)
}

async function thema(page, dunkel) {
  const ist = await page.evaluate("document.documentElement.getAttribute('data-theme')")
  if ((ist === 'dark') === dunkel) return
  const knopf = page.locator('[data-dk-theme]').first()
  if (await knopf.count()) {
    await knopf.click()
    await page.waitForTimeout(500)
  }
  const jetzt = await page.evaluate("document.documentElement.getAttribute('data-theme')")
  if ((jetzt === 'dark') !== dunkel) {
    await page.evaluate((d) => document.documentElement.setAttribute('data-theme', d),
      dunkel ? 'dark' : 'light')
    await page.waitForTimeout(300)
  }
}

/** Handy-Lage NUR über die App-Klasse (kein Breiten-Trick). */
async function handyLage(page, an) {
  await page.evaluate((an) => {
    document.querySelector('.dk-app')?.classList.toggle('dk-app--handy', an)
  }, an)
  await page.waitForTimeout(300)
}

const messen = (page, marke) => page.evaluate((marke) => {
  const txt = (s) => [...document.querySelectorAll(s)]
    .filter((e) => e.offsetParent !== null)
    .map((e) => e.textContent.replace(/\s+/g, ' ').trim())
  const zahl = document.querySelector('.dk-moderation-anzahl')?.textContent?.trim() || ''
  const karten = txt('.dk-mcard').length
  const wartet = txt('.dk-mcard-wartet')
  const freigeben = [...document.querySelectorAll('.dk-mcard-freigeben')]
    .filter((e) => e.offsetParent !== null).length
  const stufen = txt('.dk-mcard-stufe')
  const antraege = txt('.dk-antrag-karte')
  const spalten = txt('.dk-mboard-col-title').map((t, i) => {
    const kopf = document.querySelectorAll('.dk-mboard-col-header')[i]
    return t + '=' + (kopf?.querySelector('.dk-mboard-count')?.textContent?.trim() || '?')
  })
  return {
    marke, zahl, karten, wartet, freigeben, stufen, antraege, spalten,
    erklaerung: document.querySelector('.dk-moderation-erklaerung')?.textContent?.replace(/\s+/g, ' ').trim(),
    scrollBreite: document.documentElement.scrollWidth,
    fensterBreite: window.innerWidth,
    handyKlasse: !!document.querySelector('.dk-app--handy'),
    // Verschachtelte Bedienelemente (Knopf im Link) dürfen nicht vorkommen.
    knopfImLink: [...document.querySelectorAll('a button')].length,
  }
}, marke)

async function serverantworten(page) {
  return page.evaluate(async () => {
    const ruf = async (fn, params = {}) => {
      const r = await fetch('/api/method/' + fn, {
        method: 'POST', credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'X-Frappe-CSRF-Token': (window.__DIakonosBOOT || {}).csrf_token || '',
        },
        body: JSON.stringify(params),
      })
      let k = null
      try { k = await r.json() } catch { k = null }
      return { status: r.status, koerper: k }
    }
    const erklaerung = await ruf('diakronos.api.rechte.get_rollen_erklaerung')
    const brett = await ruf('diakronos.kronos.api.kanban_api.get_kanban_board_data')
    const zahl = await ruf('diakronos.kronos.api.kanban_api.get_moderation_count')
    const antraege = await ruf('diakronos.api.rechte.get_offene_sichtbarkeits_antraege')
    return {
      stufen_titel: erklaerung.koerper?.message?.stufen_titel,
      zahl: zahl.koerper?.message?.count,
      vorschlaege: (brett.koerper?.message?.vorschlaege || []).map((e) => ({
        id: e.id, title: e.title, stufe: e.stufe, darf_pruefen: e.darf_pruefen, status: e.status,
      })),
      konflikte: (brett.koerper?.message?.konflikte || []).length,
      antraege: antraege.koerper?.message?.antraege || [],
    }
  })
}

const lauf = async () => {
  const b = await chromium.launch()
  for (const lage of LAGEN) {
    const ctx = await b.newContext({
      viewport: { width: lage.breite, height: lage.hoehe },
      hasTouch: lage.handy, locale: 'de-DE',
    })
    const page = await ctx.newPage()
    await anmelden(page, MODERATOR)
    if (lage.handy) await handyLage(page, true)
    await thema(page, lage.dunkel)
    await page.waitForTimeout(600)
    const werte = await messen(page, lage.name)
    if (werte.scrollBreite > werte.fensterBreite + 1) {
      bericht.fehler.push(`${lage.name}: seitlicher Überlauf ${werte.scrollBreite} > ${werte.fensterBreite}`)
    }
    if (werte.knopfImLink) bericht.fehler.push(`${lage.name}: ${werte.knopfImLink} Knopf/Knöpfe in einem Link`)
    bericht.lagen.push(werte)
    await page.screenshot({ path: `${ZIEL}/pruefliste-${lage.name}.png`, fullPage: true })
    if (lage.name === 'desktop-1440-hell') bericht.server = await serverantworten(page)
    if (lage.handy) await handyLage(page, false)
    await ctx.close()
  }

  // ── Zweistufig: die Gemeinde-Moderation sieht einen Vorschlag, der auf sie
  // wartet; die Karte nennt die Stufe, der Knopf erscheint nur bei darf_pruefen.
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, locale: 'de-DE' })
  const page = await ctx.newPage()
  await anmelden(page, MODERATOR)
  bericht.ablauf.vorher = await serverantworten(page)
  // Ersten Vorschlag, den der Aufrufer prüfen darf, über die Karte freigeben.
  const knopf = page.locator('.dk-mcard-freigeben').first()
  if (await knopf.count()) {
    const urlVorher = page.url()
    await knopf.click()
    await page.waitForTimeout(2500)
    bericht.ablauf.nachKlick = await messen(page, 'nach-freigabe')
    bericht.ablauf.urlGleich = page.url() === urlVorher
    await page.screenshot({ path: `${ZIEL}/pruefliste-nach-freigabe.png`, fullPage: true })
    bericht.ablauf.toast = await page.evaluate(() =>
      [...document.querySelectorAll('.dk-toast, [role="status"]')]
        .map((e) => e.textContent.replace(/\s+/g, ' ').trim()).filter(Boolean).slice(0, 4))
    bericht.ablauf.nachher = await serverantworten(page)
  } else {
    bericht.ablauf.hinweis = 'Kein Freigeben-Knopf sichtbar (nichts zu prüfen?)'
  }
  await ctx.close()

  // ── Mitglied ohne Moderationsrecht: die Seite sagt es klar.
  const ctx2 = await b.newContext({ viewport: { width: 1440, height: 900 }, locale: 'de-DE' })
  const page2 = await ctx2.newPage()
  await anmelden(page2, MITGLIED)
  bericht.ablauf.mitglied = await page2.evaluate(() => ({
    verweigert: !!document.querySelector('.mod-verweigert'),
    text: document.querySelector('.mod-verweigert-text')?.textContent?.replace(/\s+/g, ' ').trim(),
  }))
  await page2.screenshot({ path: `${ZIEL}/pruefliste-mitglied-verweigert.png`, fullPage: true })
  await ctx2.close()

  await b.close()
  fs.writeFileSync(`${ZIEL}/bericht.json`, JSON.stringify(bericht, null, 2))
  console.log(JSON.stringify(bericht, null, 2))
}

lauf().catch((e) => {
  console.error('FEHLER', e)
  fs.writeFileSync(`${ZIEL}/bericht.json`, JSON.stringify({ ...bericht, abbruch: String(e) }, null, 2))
  process.exit(1)
})
