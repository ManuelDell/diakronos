/**
 * MT-1c — Die Kalenderliste darf bei eingeklappter Hauptleiste nicht auf
 * 64 px gequetscht werden.
 *
 * Befund (Review MT-1, Beleg `…/mt1/desktop-1440-hell-leiste-eingeklappt-kalender.png`):
 * Stand die HAUPTleiste eingeklappt (`.dk-app.is-collapsed`), zeigte die
 * Kalenderliste nur noch „Meine Kalend…“, „Got…“, „Gru…“, „Ger…“ — sie war
 * 64 px breit, also genau so breit wie die eingeklappte Leiste.
 *
 * URSACHE (berichtigt, TEST-NACH-1): In `kronos.css` stand
 *
 *     .dk-app.is-collapsed .kronos-sidebar { width: var(--dk-sidebar-col) }
 *
 * Der Selektor meint die Kalenderliste (`.kronos-sidebar`, gerendert von
 * `components/kronos/KronosSidebar.vue`), ist aber als Zustand des
 * App-Rahmens formuliert — und die Liste ist seit OP-UI-11 eine EIGENE
 * Spalte in der Seite (`.kronos-sidebar-inpage`, `pages/Kalender.vue`).
 * Mit EINER Klasse (`.kronos-sidebar-inpage { width: 0 }`) war sie diesem
 * Drei-Klassen-Selektor (`.dk-app.is-collapsed .kronos-sidebar`) nicht
 * gewachsen: solange der Rahmen eingeklappt war, blieb die Liste ein
 * 64-px-Streifen. Genau deshalb stand die offene Regel in `kronos.css`
 * ZWEIMAL — einmal mit zwei Klassen und einmal mit drei
 * (`.kronos-sidebar.kronos-sidebar-inpage.open`); die Kopie war der Notausgang
 * gegen die Rahmenregel. Mit dem Entfernen der Rahmenregel ist die Kopie
 * gefallen, eine Regel genügt.
 *
 * Was auf `main` VOR MT-1c galt (gemessen, nicht behauptet): die SCHLIESSENDE
 * Liste war im eingeklappten Rahmen 64 px breit (der Befund), die OFFENE
 * Liste war es NICHT — sie maß in beiden Rahmenzuständen 256 px, weil die
 * Drei-Klassen-Kopie sie freihielt. Erst ohne diese Kopie fällt sie auf 64 px.
 *
 * Diese Datei prüft zwei Dinge, ohne fremde Werte nachzuschreiben:
 *   A) Quelltext: keine Regel klemmt die Kalenderliste an den Rahmenzustand
 *      (und damit an `--dk-sidebar-col` = 64 px).
 *   B) Messprobe im Browser (übersprungen, wenn kein Chromium da ist): die
 *      echten Regeln aus `tokens.css` + `index.css` + `kronos.css` werden in
 *      die Seite gelegt, die Kaskade entscheidet — eingeklappter Rahmen +
 *      Liste zu ⇒ 0 px, Liste offen ⇒ volle Breite, und zwar in beiden
 *      Rahmenzuständen gleich. Gegenprobe „alter Stand“ (`--alt`) setzt die
 *      entfernte Rahmenregel zurück und MUSS den Befund zeigen.
 *
 * Muster `ux1i2-messung.test.mjs`: Quelltext-Teil läuft überall (auch im
 * node:22-alpine-Image), Messteil nur mit playwright + Chromium.
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

/** CSS ohne Kommentare — Muster dürfen nicht in Erklärtexten greifen. */
function ohneCssKommentare(text) {
  return text.replace(/\/\*[\s\S]*?\*\//g, '')
}

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
const BROWSER_DA = browserDa()
const OHNE_BROWSER = BROWSER_DA
  ? false
  : '★ UNGEPRÜFT ohne python3/playwright/Chromium (node:22-alpine im Image) — Messprobe weist die Zahlen nach'

// ══════════════════════════════════════════════════════════════════════════
// A · Quelltext: der Rahmenzustand ist kein Breiten-Schalter der Liste
// ══════════════════════════════════════════════════════════════════════════
test('MT-1c: keine Regel klemmt die Kalenderliste an den Rahmenzustand (kronos.css)', () => {
  const css = ohneCssKommentare(lies('kronos.css'))
  // Der Befund selbst: der Rahmenzustand als Breiten-Geber der Liste.
  assert.ok(!/\.dk-app\.is-collapsed[^{}]*\.kronos-sidebar/.test(css),
    'keine `.dk-app.is-collapsed … .kronos-sidebar`-Regel in kronos.css')
  // Und die Liste kennt `--dk-sidebar-col` (die schmale Spalte der
  // eingeklappten HAUPTleiste) nirgends als eigene Breite.
  assert.ok(!/\.kronos-sidebar[\s\S]{0,200}?width:\s*var\(--dk-sidebar-col/.test(css),
    'die Kalenderliste nimmt nicht die schmale Spalte der eingeklappten Leiste')
  // Die Karte hat den Befund am Fundort erklärt (kein stummer Löschfleck).
  assert.match(lies('kronos.css'), /MT-1c/, 'kronos.css nennt die Karte am Fundort')
})

// ══════════════════════════════════════════════════════════════════════════
// B · Messprobe: die echten Regeln, im echten Browser, über die Kaskade
// ══════════════════════════════════════════════════════════════════════════
/** Baut die Messseite aus den ECHTEN CSS-Dateien (kein nachgebauter Auszug). */
function messseite(mitAlterRegel) {
  // tokens.css MUSS mit: ohne die Spaltenbreiten (`--dk-sidebar-w`,
  // `--dk-sidebar-col`) gäbe es keine Breiten, und die Probe sähe nur Nullen.
  const tokensCss = lies('tokens.css')
  const indexCss = lies('index.css')
  const kronosCss = lies('kronos.css')
  // `--alt`: die entfernte Regel wieder einsetzen — so sah der Rahmen vor
  // MT-1c aus. Sie greift NUR, wenn der Rahmen `.is-collapsed` trägt.
  const alt = mitAlterRegel
    ? '.dk-app.is-collapsed .kronos-sidebar { width: var(--dk-sidebar-col); }'
    : ''
  return `<!doctype html><html lang="de"><head><meta charset="utf-8">
<style>
${tokensCss}
${indexCss}
${kronosCss}
${alt}
</style></head><body>
<div class="dk-app" id="app">
  <aside class="dk-sidebar" id="haupt">Haupt</aside>
  <div class="dk-main-wrap"><div class="dk-content dk-content--kronos">
    <div class="kronos-page-content"><div class="kronos-calendar-wrap">
      <aside class="kronos-sidebar kronos-sidebar-inpage" id="liste">
        <div class="sidebar-calenderlist-section"><h3 class="sidebar-title">Meine Kalender</h3>
          <div class="calendar-item"><label>Gottesdienste</label></div>
          <div class="calendar-item"><label>Gruppen &amp; Kreise</label></div>
        </div>
      </aside>
      <div class="kal-flaeche">Raster</div>
    </div></div>
  </div></div>
</div>
</body></html>`
}

function messlauf(mitAlterRegel) {
  const py = `
import json, sys
from playwright.sync_api import sync_playwright
seite_html = sys.stdin.read()
p = sync_playwright().start()
try:
    b = p.chromium.launch(args=["--no-sandbox"])
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.set_content(seite_html, wait_until="load")
    # Die Liste hat \`transition: width .2s\` — ohne diesen Abschalter misst man
    # mitten im Übergang (gemessen: 0 px statt 256 px nach dem Öffnen).
    pg.add_style_tag(content="*{transition:none !important;animation:none !important}")
    def messen(rahmen_zu, offen):
        return pg.evaluate("""([ru, of]) => {
            const app = document.getElementById('app')
            const liste = document.getElementById('liste')
            app.classList.toggle('is-collapsed', ru)
            liste.classList.toggle('open', of)
            getComputedStyle(liste).width          // Stil-Flush erzwingen
            const b = liste.getBoundingClientRect()
            return {breite: Math.round(b.width),
                    rahmen: Math.round(document.getElementById('haupt').getBoundingClientRect().width),
                    spalte: getComputedStyle(app).gridTemplateColumns.split(' ')[0]}
        }""", [rahmen_zu, offen])
    print(json.dumps({
        "zu_zu": messen(True, False),
        "zu_offen": messen(True, True),
        "auf_zu": messen(False, False),
        "auf_offen": messen(False, True),
    }))
    b.close()
finally:
    p.stop()
`
  const ausgabe = execFileSync('python3', ['-c', py], {
    input: messseite(mitAlterRegel), encoding: 'utf8', timeout: 180000,
    maxBuffer: 4 * 1024 * 1024,
  })
  return JSON.parse(ausgabe.trim().split('\n').pop())
}

test('MT-1c · eingeklappte Hauptleiste + Liste zu ⇒ 0 px (kein 64-px-Streifen)', { skip: OHNE_BROWSER }, () => {
  const m = messlauf(false)
  // Die Gegenprobe auf DEMSELBEN Messweg: der alte Stand zeigt den Befund —
  // im eingeklappten Rahmen bleibt ein Streifen in der Breite der
  // eingeklappten Hauptleiste stehen, und er verschwindet nicht beim Öffnen.
  // (NICHT geprüft wird hier, wie breit die offene Liste vor MT-1c war: sie
  // war es NICHT, die klemmte — dafür sorgte die Drei-Klassen-Kopie.)
  const alt = messlauf(true)
  assert.ok(alt.zu_zu.breite > 0,
    `vor MT-1c blieb die geschlossene Liste ein Streifen (gemessen ${alt.zu_zu.breite} px)` +
    ' — die Probe misst also wirklich den Befund')
  // Der Streifen nimmt die Breite der eingeklappten Hauptleiste (die Messung
  // liest den gerundeten Rahmen; 1 px Toleranz für die Randlinie).
  assert.ok(Math.abs(alt.zu_zu.breite - alt.zu_zu.rahmen) <= 1,
    `der Streifen war so breit wie die eingeklappte Hauptleiste `
    + `(${alt.zu_zu.breite} zu ${alt.zu_zu.rahmen} px — der Befund)`)
  assert.notEqual(alt.zu_zu.breite, m.zu_zu.breite,
    'alter Stand und Fix unterscheiden sich in diesem Messpunkt — sonst misst die Probe nichts')
  // Mit dem Fix ist die Liste zu, wenn sie zu ist — in beiden Rahmenzuständen.
  assert.equal(m.zu_zu.breite, 0, `zu + Rahmen eingeklappt ⇒ 0 px (gemessen ${m.zu_zu.breite})`)
  assert.equal(m.auf_zu.breite, 0, `zu + Rahmen offen ⇒ 0 px (gemessen ${m.auf_zu.breite})`)
  // Öffnen gibt Breite her — unabhängig vom Rahmenzustand, und nicht nur
  // einen Streifen.
  assert.ok(m.zu_offen.breite > 0,
    `offen im eingeklappten Rahmen nimmt die Liste Platz ein (gemessen ${m.zu_offen.breite} px)`)
  assert.equal(m.zu_offen.breite, m.auf_offen.breite,
    'die offene Liste ist in beiden Rahmenzuständen gleich breit')
})
