/**
 * B6-N3c — Kalender: Zeilen-Mindesthöhe im schmalen Maus-Fenster (MESSTEST).
 *
 * WARUM DIESER TEST (Review B6-N3c, Punkt 1)
 * ------------------------------------------
 * Die Mindesthöhe der Monatszeilen (`--kal-zeile-min`, tokens.css) hing in
 * B6-N2 GLOBAL an `--ec-row-height`. In der Monatsansicht ist `.ec-main` ein
 * Raster mit `overflow: hidden` — eine Zeile mit Untergrenze macht das Raster
 * höher als seinen Kasten, und die überzähligen Wochen werden ABGESCHNITTEN
 * (gemessen 1440×900: 4 von 6 Wochen, main: 6). Seit B6-N3 gilt die
 * Untergrenze NUR im schmalen MAUS-Fenster (≤ 720 px), wo `.kal-flaeche`
 * scrollen darf und die Karte mit ihrer natürlichen Höhe wächst.
 *
 * Bis B6-N3b stand hier eine Quelltext-Prüfung (readFileSync + Regex). Sie
 * konnte die Zusage nicht belegen: die Kaskade entscheidet, nicht der
 * Wortlaut — Bibliotheksregel `.ec-day-grid .ec-main.ec-uniform` (0-3-0),
 * `kronos.css` mit `.kal-flaeche` (0-4-0), `:where()`-Regel im Querformat.
 * Geprüft wird deshalb im BROWSER, nach dem Muster von
 * `tests/mt1c-kalenderliste-breite.test.mjs`: echte CSS-Dateien in die Seite
 * legen, echtes DOM, `getComputedStyle` — kein Stack, kein `vite build`,
 * kein Vue-Mount.
 *
 * GEMESSEN WIRD DIE WIRKUNG, NICHT DER WORTLAUT
 *   A) schmales Maus-Fenster (700×560): jede Wochenzeile des Rasters ist
 *      mindestens `--kal-zeile-min` hoch (am Zweig gemessen: 6 × 115 px),
 *      und der Rasterkasten fasst sie (die Karte wächst, die Fläche scrollt).
 *   B) breites Maus-Fenster (1440×900): die Zeilen teilen die Höhe, KEINE
 *      Untergrenze — alle sechs Wochen im Kasten, kein Überstand.
 *   C) Handy-Lage (390×844, `.dk-app--handy`): dasselbe wie B. Die Mindesthöhe
 *      hängt an `.kal-flaeche` — die es in der Handy-Lage nicht gibt
 *      (`v-if="!istSchmal"`, pages/Kalender.vue) — und kann das A10-Raster
 *      dort nicht überstimmen (B6-N3b: Handy wie main, 6 × 102 px).
 *
 * ROT-BELEG (im Bericht zur Karte): mit `kronos.css` von `main` ist Punkt A
 * rot — main setzt gar keine Untergrenze, die Zeilen schrumpfen auf den
 * Platz. Der Test liest seine CSS-Dateien aus dem Baum, der geprüft wird;
 * für die rote Probe wird `kronos.css` ausgetauscht (Befehl im Bericht).
 *
 * Die Aussage „Scrollen der Fläche und Wachsen der Karte hängen an derselben
 * 720-px-Grenze“, der Mobil-Halter (`.kal-mobil-raster-halter`, main-Stand) und
 * „die Seite setzt im Mobil-Monat keine eigene Zeilenhöhe“ bleiben als
 * QUELLTEXT-Prüfungen in `b6n3b-kalender-halter.test.mjs` — sie betreffen eine
 * Struktur über zwei Dateien, die hier nicht messbar ist. Jene Datei läuft ohne
 * Chromium und wird deshalb auch im Image ausgeführt (nicht übersprungen).
 *
 * Muster `mt1c-…`: der Messteil wird übersprungen, wenn kein Chromium da ist
 * (node:22-alpine im Image).
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { execFileSync } from 'node:child_process'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const hier = dirname(fileURLToPath(import.meta.url))
const SRC = resolve(hier, '..', 'src', 'diakonos')
const lies = (rel) => readFileSync(join(SRC, rel), 'utf8')
/** Die Bibliothek liefert ihre Regeln (`--ec-row-height: minmax(0, 1fr)`). */
const BIBLIOTHEK_CSS = resolve(hier, '..', 'node_modules', '@event-calendar', 'build',
  'dist', 'event-calendar.min.css')

/** Ist ein Chromium über playwright startbar? (Im Image-Build: nein.) */
function browserDa() {
  try {
    execFileSync('python3', ['-c',
      'import playwright.sync_api; playwright.sync_api.sync_playwright().start()'
      + '.chromium.launch(args=["--no-sandbox"]).close()'],
    { encoding: 'utf8', timeout: 120000, stdio: 'ignore' })
    return true
  } catch {
    return false
  }
}
const OHNE_BROWSER = browserDa()
  ? false
  : '★ UNGEPRÜFT ohne python3/playwright/Chromium (node:22-alpine im Image) — Messtest weist die Zahlen nach'

// ══════════════════════════════════════════════════════════════════════════
// Die Messseite: echte Dateien, echtes DOM — kein nachgebauter Auszug
// ══════════════════════════════════════════════════════════════════════════
/** `<style>`-Block der Seite (letzter Block, wie Vue ihn ausliefert). */
const seitenStil = (vue) => vue.slice(vue.lastIndexOf('<style'))

/**
 * Der Rasterbaum, wie `pages/Kalender.vue` ihn baut:
 *   .kal-karte > .kal-karte-raster > KronosCalendar (`<div style="height:100%">`)
 *     > .ec.ec-month-view.ec-day-grid > .ec-main.ec-uniform
 * Die Wochenzeilen setzt die Bibliothek (`--ec-grid-rows`); der Wochentags-Kopf
 * ist der erste Track von `.ec-main` und wird hier abgeschnitten.
 */
const RASTER = `
            <div class="kal-karte-raster" id="raster">
              <div id="huelle" style="height:100%">
                <div class="ec ec-month-view ec-day-grid" id="kal">
                  <div class="ec-main ec-uniform" id="main"></div>
                </div>
              </div>
            </div>`

function messseite({ handy, handyAbweichung = false }) {
  // Handy-Lage: `.kal-flaeche` gibt es nicht (`v-if="!istSchmal"`); das Raster
  // steht im Mobil-Halter (pages/Kalender.vue, A10).
  // `handyAbweichung`: der Runde-3-Umbau — ein namenloser Zwischenknoten
  // zwischen Halter und Raster (Halter `flex: 0 0 auto`, eigener Scrollkasten).
  // `.kal-mobil-raster-halter` ist dort KEIN Flex-Kind der Fläche mehr, und die
  // main-Regel
  //   `.kal-mobil-raster-halter > .kronos-calendar-wrap, … > .kronos-calendar-shell`
  // greift nicht mehr — gemessen: Raster 0 px statt 612 px (Befund der Karte).
  const inhalt = handy
    ? `<div class="kal-mobil-raster-halter">
            <div class="kal-monat-mobil"></div>
            ${handyAbweichung
    ? `<div id="zwischenknoten" style="flex: 0 0 auto; min-height: 0; overflow-y: auto;">
                 <div class="kronos-calendar-wrap">${RASTER}</div>
               </div>`
    : RASTER}
          </div>`
    : `<div class="kal-flaeche">
          <div class="kal-karte">
            <div class="kal-karte-kopf"><h2 class="kal-karte-titel">November 2026</h2>
              <span class="kal-karte-kw">KW 45</span></div>${RASTER}
          </div>
        </div>`
  return `<!doctype html><html lang="de" data-theme="hell"><head><meta charset="utf-8">
<style>${readFileSync(BIBLIOTHEK_CSS, 'utf8')}</style>
<style>${lies('tokens.css')}</style>
<style>${lies('index.css')}</style>
<style>${lies('kronos.css')}</style>
<style>${seitenStil(lies('pages/Kalender.vue'))}</style>
<style>*{transition:none !important;animation:none !important}</style>
</head><body>
<div class="dk-app${handy ? ' dk-app--handy' : ''}" id="app">
  <aside class="dk-sidebar">Haupt</aside>
  <!-- Die App-Hülle liefert die Höhe (index.css: .dk-main-wrap und .dk-content
       sind Flex-Spalten); das Wurzelelement der Seite füllt sie aus
       (.kronos-page-content scoped, zusätzlich height: 100%). -->
  <div class="dk-main-wrap"><div class="dk-content dk-content--kronos">
    <div class="kronos-page-content" style="height:100%">
      <div class="kronos-calendar-wrap">${inhalt}
      </div>
    </div>
  </div></div>
</div>
</body></html>`
}

/**
 * Misst in einem Chromium mit fester Fenstergröße: Zeilenhöhen der Wochen, den
 * aufgelösten Token `--kal-zeile-min`, die Höhe des Rasterkastens und den
 * Überstand (Raster höher als Kasten ⇒ Wochen werden abgeschnitten).
 */
function messlauf({ breite, hoehe, handy = false, handyAbweichung = false }) {
  const py = `
import json, sys
from playwright.sync_api import sync_playwright
seite_html = sys.stdin.read()
p = sync_playwright().start()
try:
    b = p.chromium.launch(args=["--no-sandbox"])
    pg = b.new_page(viewport={"width": ${breite}, "height": ${hoehe}})
    pg.set_content(seite_html, wait_until="load")
    print(json.dumps(pg.evaluate("""() => {
        const main = document.getElementById('main')
        // Die Bibliothek setzt --ec-grid-cols/--ec-grid-rows am \`.ec-main\`
        // (7 Tage, 6 Wochen im November 2026) — daraus rechnen ihre Regeln das
        // Track-Template.
        main.style.setProperty('--ec-grid-cols', '7')
        main.style.setProperty('--ec-grid-rows', '6')
        getComputedStyle(main).gridTemplateRows           // Stil-Flush
        // Track-Liste der Bibliothek: [0] ist der Wochentags-Kopf (max-content),
        // [1..6] sind die sechs Wochenzeilen. Die Track-Liste wird mit
        // Leerzeichen getrennt — hier ausdrücklich nur EINFACHE Leerzeichen
        // (ein /\s+/ hätte auch den Zeilenumbruch der Regel erwischt).
        const spuren = getComputedStyle(main).gridTemplateRows.split(' ')
            .filter((v) => v.trim()).map((v) => parseFloat(v))
        const kasten = (id) => document.getElementById(id).getBoundingClientRect()
        // Rohwert der Variablen, die die Bibliotheksregel setzt (ohne
        // calc-Auflösung — der Browser gibt Zeilenhöhen nur ausgerechnet her).
        const token = getComputedStyle(main).getPropertyValue('--ec-row-height')
        // Der aufgelöste Längenwert der Mindesthöhe — dieselbe Kette, die in
        // --ec-row-height steht (0, wenn das Token nicht ansteht).
        const minPx = parseFloat(
            getComputedStyle(main).getPropertyValue('--kal-zeile-min')) || 0
        return {
            // [0] = Wochentags-Kopf, [1..] = die Wochenzeilen
            zeilen: spuren.slice(1),
            mainHoehe: kasten('main').height,
            mainUeberstand: main.scrollHeight - Math.round(kasten('main').height),
            karteHoehe: kasten('raster').height,
            // Der Rohwert der Zeilenhöhen-Variablen: enthält er die
            // Mindesthöhe, greift die Regel aus dem schmalen Fenster.
            rohToken: token,
            minPx,
        }
    }""")))
    b.close()
finally:
    p.stop()
`
  const ausgabe = execFileSync('python3', ['-c', py], {
    input: messseite({ handy, handyAbweichung }), encoding: 'utf8', timeout: 180000,
    maxBuffer: 4 * 1024 * 1024,
  })
  return JSON.parse(ausgabe.trim().split('\n').pop())
}

/**
 * Grobe Spanne der Mindesthöhe, gelesen aus `--ec-row-height`. Der Browser gibt
 * die Variable als
 *   `minmax(calc(32px + 4px + 2 * calc(12px + 2 * 4px + 1px) + … + 16px), 1fr)`
 * heraus — die Token-Kette steht dort als px-Glieder, nur die Klammern und die
 * Faktoren (`2 *`) stehen noch. Die Funktion summiert ALLE px-Glieder des
 * Rohwerts und ignoriert die Faktoren — das Ergebnis ist deshalb eine grobe
 * SPANNE, nicht der Token-Wert: am Zweig gemessen 86 (die Zeilen selbst sind
 * 6 × 115 px). Sie taugt als Plausibilitätsprüfung („eine Untergrenze ist
 * gesetzt, und zwar nicht 0 oder eine Knopfhöhe“), NICHT als Zahlengleichheit.
 * `NaN` heißt: gar keine px-Länge, also keine Untergrenze (so sieht die
 * Variable an main aus).
 */
const zeileMinWert = (m) => {
  const ketten = (m.rohToken || '').match(/[\d.]+px/g)
  return ketten ? ketten.reduce((a, t) => a + Number(t.replace('px', '')), 0) : NaN
}

/** Alle sechs Wochenzeilen sind mindestens `mindest` hoch. */
const alleMindestens = (zeilen, mindest) =>
  zeilen.length === 6 && zeilen.every((h) => h >= mindest - 0.5)

/**
 * Ohne Untergrenze lebt die Zeile allein vom Platz (Bibliothek:
 * `minmax(0, 1fr)` + `flex-grow`). Am 1440×900-Fenster sind das 125,03 px,
 * im Handy-Raster 102 px — beide nachgemessen. Weicht die Zeile nach oben ab,
 * hat jemand eine Untergrenze gesetzt, und das Raster schneidet Wochen ab.
 */
const PLATZ_HOEHE = { breit: 125.03, handy: 102 }

/** Alle sechs Wochenzeilen stehen auf der Höhe, die der Platz hergibt. */
const zeilenAusPlatz = (m, soll) =>
  m.zeilen.length === 6
  && m.zeilen.every((h) => Math.abs(h - soll) <= 1)

// ══════════════════════════════════════════════════════════════════════════
// A · schmales Maus-Fenster: Untergrenze greift, Kasten fasst die Wochen
// ══════════════════════════════════════════════════════════════════════════
// Die Mindesthöhe je Zeile, wie sie die Karte vorgibt: gerechnet
// 32 + 4 + 3 × 21 + 16 = 115 px (Tageskopf, 2 Chips, „+n“, Luft); die Zeilen
// sind am Zweig auch tatsächlich 6 × 115 px hoch. `zeileMinWert` liest dagegen
// nur eine grobe Spanne aus dem Rohwert (gemessen 86) — für die Frage „steht
// überhaupt eine Untergrenze an?“ vergleicht `mitMindesthoehe` diese Spanne mit
// einem weiten Fenster, NICHT mit 115.
const ZEILE_MIN = 115
/** Steht eine Untergrenze an (grobe Spanne nicht 0 und nicht Knopfhöhe)? */
const mitMindesthoehe = (m) => {
  const wert = zeileMinWert(m)
  return wert >= 40 && wert <= 200
}

test('B6-N3: schmales MAUS-Fenster — jede Monatszeile ist mindestens 115 px hoch (--kal-zeile-min)',
  { skip: OHNE_BROWSER }, () => {
    // 700×560: schmal (≤ 720 px), Prüf-Spalte unter dem Raster, Fenster flach.
    // Am Zweig: Karte 690 px, sechs Zeilen à 115 px — vollständig; an main: 0 px.
    const m = messlauf({ breite: 700, hoehe: 560 })
    assert.ok(Number.isFinite(zeileMinWert(m)),
      `im schmalen Fenster hat --ec-row-height keine Mindesthöhe ` +
      `(gelesen: "${m.rohToken}") — die Zeilen bekämen dann nur den Platz, ` +
      'Termin und „+n“ fielen weg')
    assert.ok(mitMindesthoehe(m),
      `die Mindesthöhe steht nicht an (grobe Spanne ${zeileMinWert(m)}, gelesen: ` +
      `"${m.rohToken}") — ein Termin-Chip plus „+n“ passt dann nicht in die Zeile`)
    assert.ok(alleMindestens(m.zeilen, ZEILE_MIN),
      `im schmalen Fenster müssen ALLE Wochenzeilen ≥ ${ZEILE_MIN} px sein, ` +
      `gemessen: ${m.zeilen.map((h) => h.toFixed(1)).join(' / ')} — ohne die ` +
      'Untergrenze schrumpft die Zeile auf den Platz, Termin und „+n“ fallen weg')
    assert.ok(m.mainHoehe >= 6 * ZEILE_MIN - 1,
      `das Raster ist ${Math.round(m.mainHoehe)} px hoch — sechs Zeilen à ` +
      `${ZEILE_MIN} px brauchen mindestens ${6 * ZEILE_MIN} px`)
    // Die Wochen müssen in den Kasten passen: die Karte wächst mit ihrer
    // natürlichen Höhe, der Überstand liegt in der scrollenden Fläche.
    const summe = m.zeilen.reduce((a, b) => a + b, 0)
    assert.ok(m.karteHoehe >= summe - 1,
      `der Rasterkasten (${Math.round(m.karteHoehe)} px) ist kleiner als seine ` +
      `Wochen (${summe.toFixed(0)} px) — dann schneidet ` +
      '`.ec-month-view .ec-main { overflow: hidden }` die letzte Woche ab')
    assert.ok(m.mainUeberstand <= 1,
      `das Raster hat ${m.mainUeberstand} px Überstand — die Wochen passen nicht ` +
      'in den Kasten (abgeschnittene letzte Woche)')
  })

// ══════════════════════════════════════════════════════════════════════════
// B · breites Fenster: Bibliotheks-Höhe, keine Untergrenze
// ══════════════════════════════════════════════════════════════════════════
test('B6-N3: Desktop (1440×900) — die Wochen teilen den Platz, die Mindesthöhe greift NICHT',
  { skip: OHNE_BROWSER }, () => {
    // Die globale Mindesthöhe aus B6-N2 schnitt am Desktop ganze Wochen ab
    // (gemessen 1440×900: 4 von 6). Hier: der Kasten lebt allein von
    // `minmax(0, 1fr)` und `flex-grow` — die Zeilen sind gleich hoch und
    // stehen vollständig darin (kein Überstand).
    const m = messlauf({ breite: 1440, hoehe: 900 })
    assert.equal(m.zeilen.length, 6, 'sechs Wochenzeilen im Raster')
    assert.ok(!mitMindesthoehe(m),
      `am Desktop greift die Mindesthöhe trotzdem (gelesen: "${m.rohToken}") — ` +
      'damit wird das Raster höher als sein Kasten und schneidet Wochen ab')
    assert.ok(zeilenAusPlatz(m, PLATZ_HOEHE.breit),
      `am Desktop müssen die Wochen die Höhe TEILEN (Raster = 6 × Zeilenhöhe, ` +
      `kein Überstand) — gemessen: Zeilen ` +
      `${m.zeilen.map((h) => h.toFixed(1)).join(' / ')}, Raster ` +
      `${Math.round(m.mainHoehe)} px, Überstand ${m.mainUeberstand} px`)
  })

// ══════════════════════════════════════════════════════════════════════════
// C · Handy-Lage: Raster wie main, keine Mindesthöhe aus dem MAUS-Fenster
// ══════════════════════════════════════════════════════════════════════════
test('B6-N3b: Handy-Lage (390×844) — Raster wie main, keine Mindesthöhe aus dem MAUS-Fenster',
  { skip: OHNE_BROWSER }, () => {
    // B6-N3b (Review Runde 3, Punkt 1): Die Mindesthöhe griff an der BREITE und
    // überstimmte am 390-px-Handy das A10-Raster. Sie hängt jetzt an
    // `.kal-flaeche` — die es in der Handy-Lage nicht gibt (`v-if="!istSchmal"`).
    // Gemessen am Zweig und an main: 6 × 102 px, Raster 612 px.
    const m = messlauf({ breite: 390, hoehe: 844, handy: true })
    // Gegenprobe auf DEMSELBEN Messweg: der Runde-3-Umbau (Zwischenknoten
    // zwischen Halter und Raster) drückte das Raster auf 0 px — er MUSS
    // durchfallen, sonst misst die Probe nicht, was die Karte als Befund nennt.
    const alt = messlauf({ breite: 390, hoehe: 844, handy: true, handyAbweichung: true })
    assert.ok(!zeilenAusPlatz(alt, PLATZ_HOEHE.handy),
      `die Gegenprobe mit dem Runde-3-Zwischenknoten zeigt die main-Höhe ` +
      `(${alt.zeilen.map((h) => h.toFixed(1)).join(' / ')}) — die Probe misst ` +
      'also nicht, was die Karte als Befund nennt')
    assert.equal(m.zeilen.length, 6, 'sechs Wochenzeilen im Handy-Raster')
    assert.ok(!mitMindesthoehe(m),
      `in der Handy-Lage greift die Mindesthöhe aus dem MAUS-Fenster ` +
      `(gelesen: "${m.rohToken}") — das A10-Raster wird gegen main verändert`)
    assert.ok(zeilenAusPlatz(m, PLATZ_HOEHE.handy),
      `in der Handy-Lage muss das Raster wie main aus dem Platz leben ` +
      `(Raster = 6 × Zeilenhöhe, kein Überstand) — gemessen: Zeilen ` +
      `${m.zeilen.map((h) => h.toFixed(1)).join(' / ')}, Raster ` +
      `${Math.round(m.mainHoehe)} px, Überstand ${m.mainUeberstand} px`)
    assert.ok(m.mainHoehe > 0, 'das Raster hat in der Handy-Lage Höhe (Halter füllt die Fläche)')
  })
