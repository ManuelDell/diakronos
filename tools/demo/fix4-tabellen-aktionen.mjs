/**
 * FIX-4 — Mitglieder › Formulare am Handy: Aktionsknöpfe überlagern sich
 * (Befund DMB-9a25839dfda4, Route #/mitglieder/anfragen?bereich=formulare,
 * DkTable, 5. Spalte, Viewport 344×561).
 *
 * Gemessen wird, nicht behauptet:
 *
 *   1. KEIN ÜBERLAGERN — je Zelle der Aktionsspalte (`td.is-aktion`) werden die
 *      Rechtecke aller Knöpfe bestimmt:
 *        · kein Knopf ragt über den Innenbereich seiner Zelle hinaus,
 *        · zwei Knöpfe derselben Zelle überschneiden sich nicht,
 *        · `elementFromPoint` in der Mitte jedes Knopfes liefert den Knopf
 *          selbst (oder ein Kind) — nicht ein fremdes Element.
 *   2. TABELLEN-ÜBERLAUF NUR IM CONTAINER — die Tabelle darf breiter als
 *      `.dk-ui-table-wrap` sein (dort scrollt es), aber die Seite selbst darf
 *      nicht waagerecht überlaufen (`documentElement.scrollWidth`).
 *   3. Aufgenommen werden 344×561 und 390×844, je hell und dunkel, für
 *      „Formulare“ und (gleiches Muster) „Links & QR-Codes“.
 *
 * Aufruf (playwright wird im Abbild unter /tmp/pw nachinstalliert, die
 * Browser liegen bereits unter /ms-playwright):
 *   docker run --rm --network <netz> -v "<repo>":/w:ro -v "<ziel>":/ausgabe \
 *       -e FIX4_BASE=http://app:8000 \
 *       mcr.microsoft.com/playwright:v1.49.0-noble sh -c \
 *       'export NODE_PATH=/tmp/pw/node_modules; node /w/tools/demo/fix4-tabellen-aktionen.mjs --marke nachher'
 */
import { mkdirSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
const { chromium } = require('playwright')

const BASE = process.env.FIX4_BASE || 'http://app:8000'
const ZIEL = process.env.ZIEL || '/ausgabe'
const EMAIL = process.env.ADMIN_EMAIL || 'admin@example.org'
const PASSWORT = process.env.ADMIN_PASS || 'musterhausen-demo'
const SEITE = BASE + '/diakonos#/mitglieder/anfragen'
/** „mitglieder“ ist die Gegenprobe zu Auflage 1: Liste mit 7 Textspalten.
 *  Achtung: die Liste liegt unter `#/mitglieder/liste` (menue.js), nicht unter
 *  `#/mitglieder` — dort steht die Bereichsübersicht. */
const SEITE_MITGLIEDER = BASE + '/diakonos#/mitglieder/liste'

const argMarke = process.argv.indexOf('--marke')
const MARKE = argMarke > 0 ? process.argv[argMarke + 1] : 'nachher'

const VARIANTEN = [
  { name: '344-hell', breite: 344, hoehe: 561, dunkel: false, bereich: 'formulare' },
  { name: '344-hell-links', breite: 344, hoehe: 561, dunkel: false, bereich: 'links' },
  { name: '390-hell', breite: 390, hoehe: 844, dunkel: false, bereich: 'formulare' },
  { name: '390-dunkel', breite: 390, hoehe: 844, dunkel: true, bereich: 'formulare' },
  { name: '390-dunkel-links', breite: 390, hoehe: 844, dunkel: true, bereich: 'links' },
  // Review-Auflage 1: die Mitgliederliste (7 Spalten, KEINE Aktionsspalte)
  // muss bei `table-layout: auto` bleiben — `fixed` würde ihr die Zellen
  // stutzen. Deshalb wird sie in Desktop- und Handybreite mitgemessen.
  { name: '1366-hell-mitglieder', breite: 1366, hoehe: 900, dunkel: false, bereich: 'mitglieder' },
  { name: '1366-dunkel-mitglieder', breite: 1366, hoehe: 900, dunkel: true, bereich: 'mitglieder' },
  { name: '390-hell-mitglieder', breite: 390, hoehe: 844, dunkel: false, bereich: 'mitglieder' },
]

/**
 * Gegenprobe „vorher“: Es wird NICHTS injiziert. Der Gegenbeweis entsteht,
 * indem dasselbe Skript gegen einen Stack aus dem `main`-Quellstand läuft
 * (Image `diakronos-fix4main:test`, gebaut aus `git archive main`). Ein
 * eingeschleustes CSS (frühere Fassung) war nicht ehrlich: es stellte das
 * Verhalten NICHT wieder her, sondern erzeugte ein anderes Layout (die Knöpfe
 * stapelten sich, statt über die Zelle zu laufen) — die Messung zeigte dann
 * fälschlich „kein Fehler“.
 */

const fehler = []
const ergebnisse = []

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

/**
 * Daten für den Befund herstellen — über die ECHTEN Schnittstellen der App
 * (dieselben Aufrufe wie die Seite), nicht per SQL in die DB.
 *
 * Der Befund zeigt drei Formulare mit unterschiedlich langen Bezeichnungen
 * („Testformular Custom-Felder“ bricht zweizeilig um) und einen Link. Ohne
 * Zeilen gäbe es keine Aktionszelle zu messen — der Leerzustand wäre kein
 * Nachweis.
 */
async function datenAnlegen(page) {
  const ruf = (method, args) => page.evaluate(async ([m, a]) => {
    const csrf = window.__DIakonosBOOT?.csrf_token || ''
    const res = await fetch('/api/method/' + m, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': csrf },
      body: JSON.stringify(a),
    })
    const text = await res.text()
    return { ok: res.ok, status: res.status, text }
  }, [method, args])

  // FIX-4 (Review): Der Lauf muss WIEDERHOLBAR sein. Sonst legt jeder
  // Aufruf drei weitere Formulare an, und „vorher“ (9 Zellen) ist nicht mit
  // „nachher“ (6 Zellen) vergleichbar. Vorher den Bestand lesen und nur
  // anlegen, was fehlt — die Messung sieht dann immer denselben Datenstand.
  // Gelesen wird über dieselben Schnittstellen wie die Seite:
  // `get_anmeldeformulare` liefert die Formulare ({"formulare": [...]}),
  // `get_anmeldungen_hub` die Links.
  const liste = await ruf('diakronos.diakronos.api.admin_hub.get_anmeldeformulare', {})
  if (!liste.ok) throw new Error(`get_anmeldeformulare: HTTP ${liste.status} ${liste.text.slice(0, 200)}`)
  const hub = await ruf('diakronos.diakronos.api.admin_hub.get_anmeldungen_hub', {})
  if (!hub.ok) throw new Error(`get_anmeldungen_hub: HTTP ${hub.status} ${hub.text.slice(0, 200)}`)
  let vorhanden = []
  let linkVorhanden = false
  try {
    vorhanden = (JSON.parse(liste.text).message?.formulare || []).map((f) => f.bezeichnung)
  } catch (e) { /* leerer Bestand */ }
  try {
    linkVorhanden = (JSON.parse(hub.text).message?.links || []).some((l) => l.bezeichnung === 'Gemeindefest 2026')
  } catch (e) { /* leerer Bestand */ }

  const formulare = [
    { bezeichnung: 'Männerfreizeit', mit_gaesten: 1, mit_kinder: 0 },
    { bezeichnung: 'Test-Formular', mit_gaesten: 0, mit_kinder: 0 },
    { bezeichnung: 'Testformular Custom-Felder', mit_gaesten: 1, mit_kinder: 1 },
  ]
  for (const f of formulare) {
    if (vorhanden.includes(f.bezeichnung)) continue
    const r = await ruf('diakronos.diakronos.api.admin_hub.create_anmeldeformular', f)
    if (!r.ok) throw new Error(`create_anmeldeformular „${f.bezeichnung}“: HTTP ${r.status} ${r.text.slice(0, 200)}`)
  }
  if (!linkVorhanden) {
    const link = await ruf('diakronos.diakronos.api.registrierungslink_api.create_link', {
      bezeichnung: 'Gemeindefest 2026', typ: 'Mitglied-Registrierung', ohne_ablauf: true,
    })
    if (!link.ok) throw new Error(`create_link: HTTP ${link.status} ${link.text.slice(0, 200)}`)
  }
  // Datenstand festhalten — gleiche Zahl vorher/nachher = vergleichbar.
  const kontrolle = await ruf('diakronos.diakronos.api.admin_hub.get_anmeldeformulare', {})
  let stand = null
  try {
    stand = { formulare: (JSON.parse(kontrolle.text).message?.formulare || []).length }
  } catch (e) { /* egal */ }
  console.log(JSON.stringify({ datenstand: stand }))
}

/**
 * Messung im Browser. Liefert je Aktionszelle die Rechtecke der Knöpfe, ob sie
 * aus der Zelle ragen, ob sie sich überschneiden und ob sie an ihrer Mitte von
 * einem fremden Element bedeckt werden.
 *
 * Wichtig für die Sichtbarkeit: der Tabellen-Überlauf scrollt IM Container
 * (`.dk-ui-table-wrap`). „Sichtbar“ heißt deshalb: innerhalb des
 * Container-Fensters (`wrapRect` + `scrollLeft`) — nicht innerhalb des
 * Dokumentfensters.
 */
const MESS_JS = (bereich) => {
  const runde = (r) => ({
    x: Math.round(r.x * 100) / 100, y: Math.round(r.y * 100) / 100,
    w: Math.round(r.width * 100) / 100, h: Math.round(r.height * 100) / 100,
  })
  const wrap = document.querySelector('.dk-ui-table-wrap')
  const wr = wrap ? wrap.getBoundingClientRect() : null
  const sichtbar = wr
    ? { links: wr.left, rechts: wr.right, oben: wr.top, unten: wr.bottom }
    : { links: 0, rechts: window.innerWidth, oben: 0, unten: window.innerHeight }

  // „Formulare“: Aktionen stehen in der letzten Spalte der Tabelle. Die wird
  // über ihre POSITION gewählt, nicht über `.is-aktion` — sonst misst man den
  // main-Stand (ohne die Klasse) nicht, und genau der ist die Gegenprobe.
  // „Links & QR-Codes“: Aktionen stehen in Karten (`DkCard`).
  const wahl = bereich === 'links' ? '.dk-ui-card' : '.dk-ui-table tbody tr'
  const zellen = bereich === 'links'
    ? [...document.querySelectorAll(wahl)]
    : [...document.querySelectorAll(wahl)].map((tr) => {
      const tds = [...tr.querySelectorAll('td')]
      return tds[tds.length - 1]
    }).filter(Boolean)
  const befunde = []
  zellen.forEach((zelle, zi) => {
    const cr = zelle.getBoundingClientRect()
    const st = getComputedStyle(zelle)
    const pl = parseFloat(st.paddingLeft) || 0
    const pr = parseFloat(st.paddingRight) || 0
    const pt = parseFloat(st.paddingTop) || 0
    const pb = parseFloat(st.paddingBottom) || 0
    const innen = {
      links: cr.left + pl - 0.5, rechts: cr.right - pr + 0.5,
      oben: cr.top + pt - 0.5, unten: cr.bottom - pb + 0.5,
    }
    const knoepfe = [...zelle.querySelectorAll('button, a.dk-ui-btn')].map((b) => {
      const r = b.getBoundingClientRect()
      const mx = r.left + r.width / 2
      const my = r.top + r.height / 2
      const imBild = mx >= sichtbar.links && mx <= sichtbar.rechts
        && my >= sichtbar.oben && my <= sichtbar.unten
      const mitte = imBild ? document.elementFromPoint(mx, my) : null
      // Liegt die Knopfmitte UNTER dem Container-Fenster (weil weiter unten
      // gescrollt wäre), sagt ein Treffer an dieser Stelle nichts über
      // Überlagerung — der Punkt liegt einfach außerhalb des Bildes.
      const unterhalb = my > window.innerHeight || my < 0
      return {
        text: (b.innerText || '').trim(),
        rect: runde(r),
        imBild,
        // Ragt der Knopf über seine Zelle hinaus? (Die Überlagerung des
        // Nachbarn war der Befund.)
        ragt: r.left < innen.links - 0.5 || r.right > innen.rechts + 0.5
          || r.top < innen.oben - 0.5 || r.bottom > innen.unten + 0.5,
        mitteTrifft: !imBild || unterhalb || (!!mitte && (mitte === b || b.contains(mitte))),
      }
    })
    const ueberlappungen = []
    for (let i = 0; i < knoepfe.length; i += 1) {
      for (let j = i + 1; j < knoepfe.length; j += 1) {
        const a = knoepfe[i].rect
        const b = knoepfe[j].rect
        if (a.x < b.x + b.w - 0.5 && b.x < a.x + a.w - 0.5
          && a.y < b.y + b.h - 0.5 && b.y < a.y + a.h - 0.5) {
          ueberlappungen.push([knoepfe[i].text, knoepfe[j].text])
        }
      }
    }
    befunde.push({
      zeile: zi, zelle: runde(cr), knopfzahl: knoepfe.length,
      sichtbareKnoepfe: knoepfe.filter((k) => k.imBild).length,
      knoepfe, ueberlappungen,
    })
  })
  const tabelle = document.querySelector('.dk-ui-table')
  const tr = tabelle ? tabelle.getBoundingClientRect() : null
  return {
    zellen: befunde,
    scrollLeft: wrap ? Math.round(wrap.scrollLeft) : null,
    scrollBreite: wrap ? Math.round(wrap.scrollWidth) : null,
    clientBreite: wrap ? Math.round(wrap.clientWidth) : null,
    tabelleBreite: tr ? Math.round(tr.width * 10) / 10 : null,
    wrapBreite: wr ? Math.round(wr.width * 10) / 10 : null,
    wrapScrollbar: !!wrap && wrap.scrollWidth > wrap.clientWidth + 1,
    tabellenZeilen: document.querySelectorAll('.dk-ui-table tbody tr').length,
    seiteUeberlauf: document.documentElement.scrollWidth - window.innerWidth,
    theme: document.documentElement.getAttribute('data-theme'),
    breite: window.innerWidth,
  }
}

/**
 * Fehlerliste einer Messung (leer = sauber).
 *
 * `bereich === 'links'` ist der Querverweis derselben Karte: „Gleiches Muster
 * bei ‚Links & QR-Codes‘ prüfen“. Dort stehen die Aktionen in Karten, nicht in
 * der Tabelle (Registrierung.vue: Unterbereich „links“ = `DkCard`-Raster). Zu
 * prüfen ist, dass auch dort nichts überlagert: kein Knopf ragt aus seiner
 * Karte, keine zwei Knöpfe derselben Zeile überschneiden sich.
 */
function pruefe(m) {
  const aus = []
  if (!m.zellen.length) aus.push('keine Aktionszelle/-zeile gefunden')
  for (const z of m.zellen) {
    if (z.ueberlappungen.length) {
      aus.push(`Zelle ${z.zeile}: Knöpfe überlagern sich ${JSON.stringify(z.ueberlappungen)}`)
    }
    for (const k of z.knoepfe) {
      if (k.ragt) aus.push(`Zelle ${z.zeile}: „${k.text}“ ragt über die Zelle hinaus ${JSON.stringify(k.rect)}`)
      if (!k.mitteTrifft) aus.push(`Zelle ${z.zeile}: „${k.text}“ wird in der Mitte von einem fremden Element bedeckt`)
    }
  }
  if (m.seiteUeberlauf > 1) aus.push(`Seite läuft waagerecht über: ${m.seiteUeberlauf} px`)
  if (m.tabelleBreite && m.wrapBreite && m.tabelleBreite > m.wrapBreite + 1 && !m.wrapScrollbar) {
    aus.push('Tabelle breiter als ihr Container, dort scrollt es aber nicht')
  }
  return aus
}

/**
 * Messung der Mitgliederliste (Gegenprobe zu Auflage 1). Sie hat KEINE
 * Aktionsspalte, muss also bei `table-layout: auto` bleiben: Die Spalten
 * richten sich nach dem Inhalt, nichts wird gestutzt. Geprüft wird das
 * berechnete `tableLayout` und dass keine Zelle ihre Nachbarin überlappt.
 */
const MESS_MITGLIEDER_JS = () => {
  const runde = (r) => ({ x: Math.round(r.x * 10) / 10, y: Math.round(r.y * 10) / 10,
    w: Math.round(r.width * 10) / 10, h: Math.round(r.height * 10) / 10 })
  const tabelle = document.querySelector('.dk-ui-table')
  const wrap = document.querySelector('.dk-ui-table-wrap')
  const wr = wrap ? wrap.getBoundingClientRect() : null
  const spalten = tabelle ? [...tabelle.querySelectorAll('thead th')].map((th) => ({
    text: (th.innerText || '').trim(), breite: Math.round(th.getBoundingClientRect().width * 10) / 10,
  })) : []
  // Überlappung zweier Zellen derselben Zeile: die x-Bereiche dürfen sich
  // nicht schneiden (sonst liefe Inhalt in die Nachbarzelle).
  const ueberlappungen = []
  const zeilen = tabelle ? [...tabelle.querySelectorAll('tbody tr')] : []
  zeilen.forEach((tr, zi) => {
    const zellen = [...tr.querySelectorAll('td')].map((td) => td.getBoundingClientRect())
    for (let i = 0; i + 1 < zellen.length; i += 1) {
      const a = zellen[i]
      const b = zellen[i + 1]
      if (a.right > b.left + 0.5) {
        ueberlappungen.push({ zeile: zi, spalte: i, ueberlappung: Math.round((a.right - b.left) * 10) / 10 })
      }
    }
  })
  return {
    tableLayout: tabelle ? getComputedStyle(tabelle).tableLayout : null,
    hatHasAktion: !!tabelle && tabelle.classList.contains('has-aktion'),
    spalten,
    zeilen: zeilen.length,
    ueberlappungen,
    tabelleBreite: tabelle ? Math.round(tabelle.getBoundingClientRect().width * 10) / 10 : null,
    wrapBreite: wr ? Math.round(wr.width * 10) / 10 : null,
    seiteUeberlauf: document.documentElement.scrollWidth - window.innerWidth,
    theme: document.documentElement.getAttribute('data-theme'),
    breite: window.innerWidth,
    ersteZeile: zeilen.length ? runde(zeilen[0].getBoundingClientRect()) : null,
  }
}

async function aufnehmen(page, seite, v) {
  await page.setViewportSize({ width: v.breite, height: v.hoehe })
  const ziel = v.bereich === 'mitglieder' ? SEITE_MITGLIEDER : `${SEITE}?bereich=${v.bereich}`
  await page.goto(ziel, { waitUntil: 'domcontentloaded' })
  await page.waitForTimeout(500)
  await page.evaluate((dunkel) => {
    try { localStorage.setItem('dk-theme', dunkel ? 'dark' : 'light') } catch (e) { /* gesperrt */ }
  }, v.dunkel)
  await page.reload({ waitUntil: 'domcontentloaded' })
  await page.waitForTimeout(2200)
  const theme = await page.evaluate(() => document.documentElement.getAttribute('data-theme'))
  if (theme !== (v.dunkel ? 'dark' : 'light')) {
    throw new Error(`${v.name}: Theme ist ${theme}, erwartet ${v.dunkel ? 'dark' : 'light'}`)
  }
  // Die Marke steuert nur noch, ob die Mitglieder-Gegenprobe (Auflage 1)
  // geprüft wird: Der main-Stand hat die Regel nicht, dort wird nichts erwartet.
  // Für den Formular-Befund ist die Marke bedeutungslos — gemessen wird immer
  // die tatsächlich laufende Quelle (main-Stack = vorher, FIX-4 = nachher).
  let m
  if (v.bereich === 'mitglieder') {
    // Tabellenansicht wählen (DkSegment: button[role=tab], Default „Karten“).
    const umschalter = page.locator("button[role=tab]:has-text('Tabelle'), button:has-text('Tabelle')")
    if (await umschalter.count()) {
      try { await umschalter.first().click({ timeout: 3000 }); await page.waitForTimeout(1500) } catch (e) { /* schon aktiv */ }
    }
    m = await page.evaluate(MESS_MITGLIEDER_JS)
    m.fehler = []
    // Auflage 1: keine Aktionsspalte → `auto`. Unter „vorher“ gilt die
    // Gegenprobe (fixed auf allen Tabellen) und es wird NICHTS geprüft.
    if (MARKE !== 'vorher') {
      if (m.tableLayout !== 'auto') m.fehler.push(`table-layout ist ${m.tableLayout}, erwartet auto (keine Aktionsspalte)`)
      if (m.hatHasAktion) m.fehler.push('die Mitgliederliste trägt has-aktion, obwohl sie keine Aktionsspalte hat')
    }
    if (m.ueberlappungen.length) m.fehler.push(`Zellen überlagern sich: ${JSON.stringify(m.ueberlappungen.slice(0, 3))}`)
    if (m.seiteUeberlauf > 1) m.fehler.push(`Seite läuft waagerecht über: ${m.seiteUeberlauf} px`)
    if (!m.zeilen) m.fehler.push('keine Mitgliederzeilen gefunden (Messung ohne Inhalt)')
  } else {
    // Der Befund spielt am rechten Rand der Tabelle: dorthin scrollen, wo die
    // Aktionsspalte ins Bild kommt (der Überlauf der Tabelle scrollt IM
    // Container — genau das ist erlaubt und wird hier benutzt).
    if (v.bereich !== 'links') {
      await page.evaluate(() => {
        const wrap = document.querySelector('.dk-ui-table-wrap')
        if (wrap) wrap.scrollLeft = wrap.scrollWidth
      })
      await page.waitForTimeout(500)
    }
    m = await page.evaluate(MESS_JS, v.bereich)
    m.fehler = pruefe(m)
  }
  m.variante = v.name
  m.bereich = v.bereich
  m.erwartetesTheme = v.dunkel ? 'dark' : 'light'
  m.scrollEnde = v.bereich !== 'links' && v.bereich !== 'mitglieder'
  ergebnisse.push(m)
  fehler.push(...m.fehler.map((f) => `${v.name}: ${f}`))
  await page.screenshot({ path: join(ZIEL, `${MARKE}-${v.name}.png`), fullPage: true })
}

async function main() {
  mkdirSync(ZIEL, { recursive: true })
  const browser = await chromium.launch({ args: ['--no-sandbox'] })
  const ctx = await browser.newContext({ locale: 'de-DE' })
  const page = await ctx.newPage()
  await anmelden(page)
  await datenAnlegen(page)
  for (const v of VARIANTEN) {
    const seite = await ctx.newPage()
    await aufnehmen(seite, SEITE, v)
    await seite.close()
  }
  await browser.close()
  writeFileSync(join(ZIEL, `${MARKE}-messung.json`),
    JSON.stringify({ marke: MARKE, varianten: ergebnisse, fehler }, null, 2))
  console.log(JSON.stringify({
    marke: MARKE,
    fehler,
    zellen: Object.fromEntries(ergebnisse.map((e) => [e.variante, e.zellen ? e.zellen.length : e.zeilen])),
    seiteUeberlauf: Object.fromEntries(ergebnisse.map((e) => [e.variante, e.seiteUeberlauf])),
    mitgliederLayout: Object.fromEntries(ergebnisse
      .filter((e) => e.bereich === 'mitglieder')
      .map((e) => [e.variante, { tableLayout: e.tableLayout, hasAktion: e.hatHasAktion,
        spalten: e.spalten.map((s) => s.breite), zeilen: e.zeilen }])),
  }, null, 2))
  if (fehler.length) process.exitCode = 1
}

main().catch((e) => {
  console.error('ABBRUCH:', e.message)
  process.exitCode = 2
})
