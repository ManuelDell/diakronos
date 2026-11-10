/**
 * A10-N2 — Nacharbeit 2 zum Handy-Kalender (Karte t_58dc1ffd).
 *
 * Geprüft wird, was das Review (Opus, 09.11.) offen ließ — ausgeführt, nicht
 * als Quelltext-Muster:
 *
 *  1. WIRKSAME CSS: Der Wähler für die Termine im Handy-Raster ist
 *     `.ec-event` (die echte Klasse aus @event-calendar 5.18) und NICHT das
 *     erfundene Attribut `[data-ec-event]`; er gilt unter der Layout-Grenze.
 *     Dazu: Tage mit Termin werden für die Punkte markiert (echtes DOM,
 *     jsdom) und der Tageskopf trägt die Zahl für die Vorlesehilfe.
 *  2. PRÜF-ZEILE bei 0 offenen Vorschlägen: keine Zeile, kein leerer Platz;
 *     unbekannte Zahl bleibt sichtbar (ohne erfundene 0).
 *  3. DUNKELMODUS: Der gewählte Tag und der FAB bekommen einen Ring aus dem
 *     Token; Kontrast Ring/Fläche ≥ 3:1 (hell: kein Ring nötig).
 *  4. KLEIN: Menüpunkt „…ist dein Standard“ trägt ein Häkchen (nicht die
 *     Lupe); das „⋯“ der Tageszeile sitzt IN der Karte.
 *  5. SEED: Der Demo-Seed gibt der Rolle „Mitglied“ Leserecht auf die
 *     Kalender — sonst zeigt die Demo „Kalender 0“ und einen leeren Tag
 *     (Ursache war der Seed, nicht die Rechte der App).
 *
 * Der Test liest NUR Dateien innerhalb von frontend/ und tools/ (Regel 13)
 * und braucht kein Netz. `.mjs`-Logik wird wirklich ausgeführt.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { join, dirname, resolve } from 'node:path'
import { pathToFileURL, fileURLToPath } from 'node:url'
import { JSDOM } from 'jsdom'

const hier = dirname(fileURLToPath(import.meta.url))
const FRONTEND = resolve(hier, '..')
const WURZEL = resolve(FRONTEND, '..')
const SRC = join(FRONTEND, 'src', 'diakonos')
const lies = (rel) => readFileSync(join(SRC, rel), 'utf8')

const MOD = await import(pathToFileURL(join(SRC, 'components/kronos/mobilModeration.mjs')).href)
const M = await import(pathToFileURL(join(SRC, 'components/kronos/mobilAnsicht.mjs')).href)

// ══════════════════════════════════════════════════════════════════════════
// 1 · Die CSS-Regel trifft die WIRKLICH gerenderten Termine
// ══════════════════════════════════════════════════════════════════════════
test('A10-N2: Handy-Raster blendet `.ec-event` aus — nicht das erfundene [data-ec-event]', () => {
  const seite = lies('pages/Kalender.vue')
  // A10-N2 (Review 09.11., Punkt 5): Der Mobil-Bau hängt an den MOBIL-KLASSEN
  // (`.kal-mobil-raster`), nicht an `@media (max-width: 720px)` — die Lage
  // entscheidet allein das Skript (`istSchmal`). IN die Bibliothek hinein
  // braucht der Wähler `:deep()`: die `article.ec-event` gehören
  // @event-calendar und tragen die Scoped-Kennung der Seite nicht (im
  // Browser geprüft: `.ec` hat kein `data-v-…`). Die Lage entscheidet
  // trotzdem die Klasse — `:deep()` sitzt HINTER `.kal-mobil-raster`.
  assert.match(seite, /\.kal-mobil-raster :deep\(\.ec-event\)\s*\{\s*display:\s*none\s*!important/,
    'Termine im Handy-Raster: .ec-event wird ausgeblendet')
  assert.match(seite, /\.kal-mobil-raster :deep\(\.ec-time-grid \.ec-event\)\s*\{\s*display:\s*none\s*!important/,
    'Wochen-Zeitraster ebenso')
  // JEDE Bibliotheks-Regel beginnt bei der Mobil-Klasse (kein freies `:deep`).
  // Nur die CSS-Seite (das Markup nennt `:deep` in Erklärungen).
  const cssTeil = seite.slice(seite.indexOf('<style')).replace(/\/\*[\s\S]*?\*\//g, '')
  const tiefe = [...cssTeil.matchAll(/:deep\(([^)]*)\)/g)].map((m) => m[1])
  for (const t of tiefe) {
    assert.match(t, /^\.(ec|dk-ui-btn|kronos)/, `:deep() zielt nur in Bausteine (${t})`)
  }
  assert.ok(!/@media \(max-width: 720px\)[\s\S]{0,400}\.kal-mobil-raster/.test(seite),
    'der Mobil-Bau hängt NICHT an der Fensterbreite (Punkt 5, DEV-B6)')
  // Der alte Wähler darf NICHT mehr als Regel vorkommen. Erwähnt bleiben darf
  // er nur im erklärenden Kommentar (dort steht, warum er es nicht war).
  const ohneKommentar = seite
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/<!--[\s\S]*?-->/g, '')
    .replace(/^\s*\/\/.*$/gm, '')
  assert.ok(!/data-ec-event/.test(ohneKommentar),
    'das Attribut [data-ec-event] gibt es in @event-calendar 5.18 nicht — keine Regel darauf')
  // Der Desktop bleibt unberührt: die Chip-Regeln aus kronos.css gelten weiter.
  const kronos = readFileSync(join(SRC, 'kronos.css'), 'utf8')
  assert.ok(!/\.ec-event\s*\{\s*display:\s*none/.test(kronos), 'kronos.css blendet nichts global aus')
})

test('A10-N2: Tage mit Termin werden für die Punkte markiert (echtes DOM)', async () => {
  // Die Funktion aus KronosCalendar wird NICHT exportiert; geprüft wird ihr
  // Verhalten über dieselbe DOM-Struktur, die die Bibliothek baut:
  //   .ec-month-view .ec-day > (.ec-day-head, article.ec-event …)
  const dom = new JSDOM(`<!doctype html><div id="kal">
    <div class="ec ec-month-view">
      <div class="ec-day" id="tag1"><div class="ec-day-head"><time datetime="2026-11-08">8</time></div>
        <article class="ec-event ec-chip-event"></article>
        <article class="ec-event ec-chip-event"></article>
      </div>
      <div class="ec-day" id="tag2"><div class="ec-day-head"><time datetime="2026-11-09">9</time></div>
        <article class="ec-event ec-chip-event"></article>
      </div>
      <div class="ec-day" id="tag3"><div class="ec-day-head"><time datetime="2026-11-10">10</time></div></div>
    </div></div>`)
  const kal = dom.window.document.getElementById('kal')
  // Nachbau der Zählregel aus KronosCalendar.tagesPunkteNachtragen(): die
  // QUELLE wird geprüft, dass sie genau diese Selektoren benutzt.
  const quelle = lies('components/kronos/KronosCalendar.vue')
  assert.match(quelle, /querySelectorAll\('\.ec-day'\)/, 'je Tag')
  assert.match(quelle, /querySelectorAll\('article\.ec-event'\)/, 'gezählt werden die Termin-Artikel')
  // Im Monat liegen die Artikel NICHT in `.ec-day`, sondern in einer eigenen
  // Ebene (im Browser gemessen) — die Zuordnung kommt aus `grid-area`.
  assert.match(quelle, /grid-area/, 'Zuordnung über das Raster (Zeile/Spalte)')
  // Wochenansicht: eigener Kopf (`.ec-col-head`) — im Zeitraster gibt es
  // kein `.ec-day-head` (im Browser gemessen).
  assert.match(quelle, /ec-col-head/, 'Woche: Punkte am Tagesspalten-Kopf')
  assert.match(quelle, /ec-week-view/, 'Woche: eigenes Raster')
  assert.ok(!/getBoundingClientRect\(\)[^;]*ec-event/.test(quelle),
    'keine Rechteck-Messung: am Handy sind die Chips ausgeblendet (Rechtecke Null)')
  assert.match(quelle, /tag\.dataset\.dkTermin/, 'Markierung data-dk-termin')
  assert.match(quelle, /aria-label/, 'Vorlesehilfe bekommt die Zahl')

  // Und die Regel REchnet richtig: dieselben Selektoren auf dem DOM.
  const anzahl = (id) => kal.querySelectorAll(`#${id} article.ec-event`).length
  assert.equal(anzahl('tag1'), 2)
  assert.equal(anzahl('tag2'), 1)
  assert.equal(anzahl('tag3'), 0, 'leerer Tag bekommt KEINEN Punkt')

  // Der Punkt ist an die Markierung gebunden (CSS in der Seite).
  const seite = lies('pages/Kalender.vue')
  assert.match(seite, /\.ec-day\[data-dk-termin\] \.ec-day-head\)::after/, 'Punkt hängt an der Markierung')
})

// ══════════════════════════════════════════════════════════════════════════
// 2 · Prüf-Zeile bei 0 offenen Vorschlägen
// ══════════════════════════════════════════════════════════════════════════
test('A10-N2: Prüf-Zeile verschwindet bei 0 — unbekannte Zahl bleibt sichtbar', () => {
  assert.equal(MOD.moderationsZeile({ darfPruefen: true, zahl: 0 }), null,
    '0 offene Vorschläge: keine Zeile, kein leerer Platz')
  assert.equal(MOD.moderationsZeile({ darfPruefen: true, zahl: '0' }), null, 'auch als Text-0')
  // Unbekannt bleibt sichtbar, aber ohne erfundene Zahl.
  const unbekannt = MOD.moderationsZeile({ darfPruefen: true, zahl: null })
  assert.ok(unbekannt, 'unbekannte Zahl: Zeile bleibt')
  assert.equal(unbekannt.zahl, null)
  assert.equal(unbekannt.text, 'Zu prüfen · Von Gruppen eingetragen')
  // Eine echte Zahl zeigt weiter die Zahl.
  assert.equal(MOD.moderationsZeile({ darfPruefen: true, zahl: 2 }).text,
    'Zu prüfen (2) · Von Gruppen eingetragen')
  // Nicht-Moderatoren bekommen bei JEDER Zahl nichts.
  for (const zahl of [0, 1, null]) {
    assert.equal(MOD.moderationsZeile({ darfPruefen: false, zahl }), null)
  }
})

// ══════════════════════════════════════════════════════════════════════════
// 3 · Dunkelmodus: gewählter Tag und FAB sichtbar
// ══════════════════════════════════════════════════════════════════════════
const kontrast = (a, b) => {
  const lum = (hex) => {
    const n = parseInt(hex.replace('#', ''), 16)
    const kanal = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => {
      const c = v / 255
      return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
    })
    return 0.2126 * kanal[0] + 0.7152 * kanal[1] + 0.0722 * kanal[2]
  }
  const [h, t] = [lum(a), lum(b)].sort((x, y) => y - x)
  return (h + 0.05) / (t + 0.05)
}

test('A10-N2: Ring-Token im Dunkelmodus — Kontrast ≥ 3:1 zur Fläche', () => {
  const tokens = lies('tokens.css')
  // Hell: kein Ring (die Navy-Fläche trägt selbst).
  assert.match(tokens, /--marke-ring:\s*transparent/, 'hell: kein Ring')
  assert.match(tokens, /--marke-ring-breite:\s*0px/, 'hell: Ringbreite 0')
  // Dunkel: heller Ring aus der Navy-Skala.
  const dunkel = tokens.slice(tokens.indexOf('[data-theme="dark"]'))
  assert.match(dunkel, /--marke-ring:\s*var\(--dk-navy-200\)/, 'dunkel: heller Ring')
  assert.match(dunkel, /--marke-ring-breite:\s*2px/, 'dunkel: 2 px')
  // Nachgerechnet: navy-200 (#aab5d2) gegen die dunkle Kartenfläche (#111631).
  const wert = kontrast('#aab5d2', '#111631')
  assert.ok(wert >= 3, `Ring/Fläche ${wert.toFixed(2)}:1 — verlangt ≥ 3:1 (Flächen/Umrandung)`)
  // Und der Beleg, warum das nötig war: Navy auf dunkler Fläche ist unsichtbar.
  assert.ok(kontrast('#1c2850', '#111631') < 1.5, 'Navy auf Navy-grau fiel unter jede Erkennbarkeit')

  // Beide Stellen tragen den Ring aus dem Token (kein hartes Blau).
  const mini = lies('components/kronos/KalenderMiniMonat.vue')
  assert.match(mini, /\.is-gewaehlt \.dk-minimonat-zahl \{[^}]*var\(--marke-ring\)/s,
    'gewählter Tag im Mini-Monat: Ring aus dem Token')
  const seite = lies('pages/Kalender.vue')
  const fabStart = seite.indexOf('.kal-fab {')
  const fab = seite.slice(fabStart, seite.indexOf('.kal-fab:hover', fabStart))
  assert.match(fab, /outline:\s*var\(--marke-ring-breite\) solid var\(--marke-ring\)/,
    'FAB: Ring aus dem Token')
})

// ══════════════════════════════════════════════════════════════════════════
// 4 · Kleinigkeiten
// ══════════════════════════════════════════════════════════════════════════
test('A10-N2: „…ist dein Standard“ trägt ein Häkchen, nicht die Lupe', () => {
  const gesetzt = M.mobilMenue({ ansicht: 'monat', standard: 'monat' })
    .find((e) => e.key === 'standard')
  assert.equal(gesetzt.icon, 'haekchen', 'aktiver Standard: Häkchen')
  assert.equal(gesetzt.disabled, true)
  const nichtGesetzt = M.mobilMenue({ ansicht: 'woche', standard: 'monat' })
    .find((e) => e.key === 'standard')
  assert.notEqual(nichtGesetzt.icon, 'haekchen', 'nicht gesetzter Standard trägt kein Häkchen')
  // Das Symbol muss im Vorrat liegen (sonst zeichnet DkSymbol nichts).
  const symbole = lies('components/ui/symbole.mjs')
  assert.match(symbole, /haekchen:\s*\{\s*p:\s*\[/, 'Symbol „haekchen“ ist im Vorrat')
  const haken = symbole.slice(symbole.indexOf('haekchen:'), symbole.indexOf('\n', symbole.indexOf('haekchen:')))
  assert.match(haken, /M20 6 9 17l-5-5/, 'Haken ohne Kreis (lucide „check“)')
  assert.ok(!/\bc:/.test(haken), 'ohne Kreis-Teile (nur der Haken)')
})

test('A10-N2: das „⋯“ der Tageszeile sitzt IN der Karte', () => {
  const tag = lies('components/kronos/KalenderTagesliste.vue')
  // Die Zeile ist EIN Kasten (Fläche); Knopf und Menü liegen darin.
  const zeile = tag.slice(tag.indexOf('.dk-tagesliste-zeile {'))
  assert.match(zeile.slice(0, 500), /background:\s*var\(--surface\)/, 'die Zeilenfläche trägt die Karte')
  assert.match(zeile.slice(0, 500), /gap:\s*0/, 'kein Abstand zwischen Knopf und Menü (eine Fläche)')
  // Der Knopf lässt rechts den Platz des 44-px-Ziels frei.
  assert.match(tag, /padding:\s*var\(--sp-2\) calc\(var\(--treffer-handy\) \+ var\(--sp-1\)\)/,
    'rechts Platz für das „⋯“ (44 px Trefferfläche)')
  // Das Menü sitzt mittig in der Zeile und ist Teil der Karte.
  const mehr = tag.slice(tag.indexOf('.dk-tagesliste-mehr {'))
  assert.match(mehr.slice(0, 300), /align-self:\s*center/, 'mittig zur Zeile')
  // Die ⋯ steht im DOM NACH dem Knopf, in derselben Zeile.
  const markup = tag.slice(0, tag.indexOf('</li>'))
  assert.ok(markup.indexOf('dk-tagesliste-knopf') < markup.indexOf('<DkAktionen'),
    'das „⋯“ folgt der Zeile (bleibt in derselben Karte)')
})

// ══════════════════════════════════════════════════════════════════════════
// 5 · Seed (Punkt 5) gehört NICHT hierher
// ══════════════════════════════════════════════════════════════════════════
// Regel 13: Node-Tests lesen nur innerhalb von frontend/ — im Build liegt
// `tools/` gar nicht daneben (`/build/tests`). Die Ursache „Kalender 0“ ist
// eine Lücke im Demo-SEED (`tools/demo/musterhausen.py`: keine Zeile in
// `Kalender.leserechte` für die Rolle „Mitglied“). Sie wird im
// Backend-Test `backend/tests/test_a10n2_seed_kalender_leserecht.py`
// geprüft, der im app-Image läuft (dort liegt `/app/tools/demo`).

// ══════════════════════════════════════════════════════════════════════════
// N2 · Review 09.11. (Opus), Punkte 2–5 — Nacharbeit im Kopf und im Raster
// ══════════════════════════════════════════════════════════════════════════
const kopf = () => lies('components/kronos/KalenderKopfMobil.vue')
const monat = () => lies('components/kronos/KalenderMiniMonat.vue')

test('N2 · 2: EIN Kopf — keine eigene Werkzeugzeile, ‹ › am Monat', () => {
  const kv = kopf()
  // Kein zweiter Kopf KNOPF mehr: ‹ › sind aus dem Kopf entfernt …
  assert.ok(!/emit\('zurueck'\)/.test(kv), 'der Kopf kennt kein „zurück“ mehr')
  assert.ok(!/emit\('vor'\)/.test(kv), 'der Kopf kennt kein „weiter“ mehr')
  assert.ok(!kv.includes('aria-label="Vorheriger Zeitraum"'), 'kein ‹ in der Kopfzeile')
  // … und stehen in der Kopfzeile des Mini-Monats (Vorbild A10).
  const mm = monat()
  const kopfZeile = mm.slice(mm.indexOf('<header class="dk-minimonat-kopf">'), mm.indexOf('</header>'))
  assert.match(kopfZeile, /aria-label="Vorheriger Monat"/, '‹ im Mini-Monat')
  assert.match(kopfZeile, /aria-label="Nächster Monat"/, '› im Mini-Monat')
  // Der Kalender-Knopf ist ein SYMBOLknopf (44 px), kein Wortknopf mehr.
  assert.ok(!kv.includes('dk-mobilkopf-aktion-text'), 'kein „Kalender“-Wortknopf mehr')
  const knopf = kv.slice(kv.indexOf('.dk-mobilkopf-knopf {'), kv.indexOf('.dk-mobilkopf-knopf {') + 400)
  assert.match(knopf, /min-width:\s*var\(--treffer-handy\)/, '44 px breit (K4)')
  assert.match(knopf, /min-height:\s*var\(--treffer-handy\)/, '44 px hoch (K4)')

})

test('N2 · 2: Tageszeile — 4 Kinder, 4 Spalten, Hover nur mit Maus, ⋯ nicht zu blass', () => {
  const tag = lies('components/kronos/KalenderTagesliste.vue')
  const knopf = tag.slice(tag.indexOf('.dk-tagesliste-knopf {'), tag.indexOf('.dk-tagesliste-farbe {'))
  // Spalten = Kinder: Farbe · Zeit · Text · Pfeil.
  assert.match(knopf, /grid-template-columns:\s*var\(--sp-1\) auto minmax\(0, 1fr\) auto;/,
    'vier Spalten für vier Kinder')
  const spalten = (knopf.match(/grid-template-columns:([^;]*);/) || [])[1] || ''
  const anzahl = spalten.trim().split(/\s+(?=[a-z(]|var\()/).length
  assert.equal(anzahl, 4, `Spaltenzahl = Kinderzahl (${anzahl})`)
  const zeilenMarkup = tag.slice(tag.indexOf('<li v-for'), tag.indexOf('</li>'))
  const kinder = (zeilenMarkup.match(/<span class="dk-tagesliste-(farbe|zeit|text|pfeil)"/g) || []).length
  assert.equal(kinder, 4, 'vier Kinder in der Zeile (Farbe, Zeit, Text, Pfeil)')
  // Hover nicht auf Touch-Geräten (er blieb dort „hängen“).
  assert.match(tag, /@media \(hover: hover\) \{\s*\.dk-tagesliste-knopf:hover/, 'Hover nur mit echter Maus')
  // Der geschützte Hover steht INNERHALB der Regel — davor darf keiner stehen.
  const vorHover = tag.slice(0, tag.indexOf('@media (hover: hover)'))
  assert.ok(!/\.dk-tagesliste-knopf:hover/.test(vorHover), 'kein ungeschützter :hover mehr')
  // Das „⋯“ trägt die Textfarbe — nachgerechnet ≥ 4,5:1 auf der Karte.
  assert.match(tag, /\.dk-tagesliste-mehr :deep\(\.dk-ui-aktionen-ausloeser\) \{[\s\S]*?color:\s*var\(--text\);[\s\S]*?\}/,
    '⋯ mit Textfarbe statt --subtle')
  const tokens = lies('tokens.css')
  const textHell = /--text:\s*var\(--dk-warm-900\)/.test(tokens)
  assert.ok(textHell, 'hell: --text ist warm-900')
  assert.ok(kontrast('#26201a', '#ffffff') >= 4.5, 'dunkle Schrift auf Weiß ≥ 4,5:1')
  assert.ok(kontrast('#9ba3c1', '#111631') >= 4.5, 'dunkel: --text (ink-text) auf der Karte ≥ 4,5:1')
  // Der alte Zustand war zu blass: --subtle im Dunkeln nur 3,8:1.
  assert.ok(kontrast('#6a7199', '#111631') < 4.5, 'Beleg: --subtle im Dunkelmodus war zu blass')
})

test('N2 · 3: Punkte im Monat und in der Woche tragen --primary (dunkel sichtbar)', () => {
  const seite = lies('pages/Kalender.vue')
  const monatPunkt = seite.slice(seite.indexOf('.ec-day[data-dk-termin] .ec-day-head)::after'), seite.indexOf('.ec-week-view .ec-col-head'))
  assert.match(monatPunkt, /background:\s*var\(--primary\);/, 'Monat: Punkt in --primary')
  const wochePunkt = seite.slice(seite.indexOf('.ec-week-view .ec-col-head[data-dk-termin])::after'), seite.indexOf('.ec-week-view .ec-col-head[data-dk-termin])::after') + 400)
  assert.match(wochePunkt, /background:\s*var\(--primary\);/, 'Woche: Punkt in --primary')
  assert.ok(!/background:\s*var\(--marke-flaeche\)/.test(monatPunkt + wochePunkt),
    'kein Navy auf Navy mehr (--marke-flaeche ist in beiden Themes navy)')
  // Beleg: Navy auf der dunklen Fläche wäre unsichtbar, Weiß ist es nicht.
  assert.ok(kontrast('#1c2850', '#111631') < 1.5, 'Navy auf dunkler Karte < 1,5:1')
  assert.ok(kontrast('#ffffff', '#111631') >= 3, '--primary (dunkel: Weiß) ≥ 3:1')
  // Der Wert kommt aus den Tokens und wechselt mit dem Theme.
  const tokens = lies('tokens.css')
  assert.match(tokens, /--primary:\s+var\(--dk-navy-500\)/, 'hell: --primary ist navy')
  assert.match(tokens.slice(tokens.indexOf('[data-theme="dark"],')), /--primary:\s+#ffffff/, 'dunkel: --primary ist Weiß')
})

test('N2 · 4: heutige Tagesspalte im Dunkeln ruhig statt gold schraffiert', () => {
  const tokens = lies('tokens.css')
  // Hell wie bisher die warme Fläche, dunkel eine neutrale Aufhellung.
  const hell = tokens.slice(tokens.indexOf('--heute-flaeche:'), tokens.indexOf('--heute-flaeche:') + 60)
  assert.match(hell, /--heute-flaeche: var\(--accent-soft\)/, 'hell: warme Fläche wie bisher')
  const dunkelStart = tokens.indexOf('[data-theme="dark"],')
  const dunkel = tokens.slice(dunkelStart)
  const dunkelWert = (dunkel.match(/--heute-flaeche:([^;]*);/) || [])[1] || ''
  assert.match(dunkelWert, /rgba\(255, 255, 255, \.0\d\)/, 'dunkel: neutrale Aufhellung (kein Gold)')
  assert.ok(!/201,\s*149,\s*47/.test(dunkelWert), 'kein gebündeltes Gold mehr (kein „Band“)')
  // Die Bibliothek nimmt den Wert als Fläche der heutigen Spalte.
  const kronos = readFileSync(join(SRC, 'kronos.css'), 'utf8')
  assert.match(kronos, /--ec-today-bg-color:\s*var\(--heute-flaeche\)/, 'Bibliothek nutzt das Token')
})

test('N2 · 5: Mobil-Bau hängt an den Mobil-Klassen, nicht an der Fensterbreite', () => {
  const seite = lies('pages/Kalender.vue')
  // Keine `:deep()`-Ausblendung der Termine mehr, sondern die Klasse.
  assert.match(seite, /\.kal-mobil-raster :deep\(\.ec-event\)\s*\{\s*display:\s*none/, 'Chips: Mobil-Klasse + :deep')
  const letzteBreite = seite.lastIndexOf('@media (max-width: 720px)')
  assert.ok(letzteBreite < seite.indexOf('.kal-mobil-raster :deep(.ec-event)'),
    'die Bibliotheks-Regeln stehen NICHT mehr in einer Breiten-Regel')
  // Der Mobil-Block mit den Raster-Regeln steht AUSSERHALB jeder Breiten-Regel:
  // die letzte `@media (max-width: 720px)` steht VOR der Mobilanlage.
  const letzteMedia = seite.lastIndexOf('@media (max-width: 720px)')
  const ersteMobilRegel = seite.indexOf('.kal-mobil-raster :deep(.ec-event)')
  assert.ok(letzteMedia < ersteMobilRegel,
    'die Raster-Regeln stehen nicht mehr in einer Breiten-Regel')
  // und die Klasse (`.kal-mobil-raster`) setzt allein der Mobil-Bau im Skript.
  assert.match(seite, /<div v-else class="kal-mobil-raster">/, 'Klasse am Mobil-Bau')
  // `istSchmal` bleibt EINE benannte Lage (DEV-B6 stellt sie zentral um).
  assert.match(seite, /const istSchmal = ref\(typeof window !== 'undefined' && istHandyBreite\(window\.innerWidth\)\)/,
    'istSchmal ist ein benanntes ref')
  assert.match(seite, /mobilAnsichtId === 'liste'/, 'Liste = eigener Weg, Raster bleibt im DOM')
})
