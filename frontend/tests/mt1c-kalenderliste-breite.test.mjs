/**
 * MT-1c — Die Kalenderliste darf bei eingeklappter Hauptleiste nicht auf
 * 64 px gequetscht werden.
 *
 * Befund (Review MT-1, Beleg `…/mt1/desktop-1440-hell-leiste-eingeklappt-kalender.png`):
 * Stand die HAUPTleiste eingeklappt (`.dk-app.is-collapsed`), zeigte die
 * Kalenderliste nur noch „Meine Kalend…“, „Got…“, „Gru…“, „Ger…“ — sie war
 * 64 px breit, also genau so breit wie die eingeklappte Leiste.
 *
 * Ursache (Review MT-1c, Punkt 3): `kronos.css` hatte
 *
 *     .dk-app.is-collapsed .kronos-sidebar { width: var(--dk-sidebar-col) }
 *
 * Der Selektor meint die Kalenderliste (`.kronos-sidebar`, gerendert von
 * `components/kronos/KronosSidebar.vue`), ist aber als Zustand des
 * App-Rahmens formuliert — und die Liste ist seit OP-UI-11 eine EIGENE
 * Spalte in der Seite (`.kronos-sidebar-inpage`, `pages/Kalender.vue`).
 *
 * Entscheidend ist NICHT die offene Liste (die war im Befund breit, der
 * Beleg zeigt sie geschlossen), sondern: über 1100 px ist die Liste
 * standardmäßig ZU (`useKronosSidebar`), `.kronos-sidebar-inpage { width: 0 }`
 * gewann aber nicht gegen die Drei-Klassen-Regel `.kronos-sidebar
 * .kronos-sidebar-inpage.open`, wenn `open` gesetzt war — und mit der alten
 * Rahmenregel blieb im eingeklappten Rahmen ein 64-px-Streifen stehen.
 *
 * Diese Datei prüft deshalb zwei Dinge, ohne fremde Werte nachzuschreiben:
 *   A) Quelltext: keine Regel klemmt die Kalenderliste an den Rahmenzustand
 *      (und damit an `--dk-sidebar-col` = 64 px).
 *   B) Messprobe im Browser (übersprungen, wenn kein Chromium da ist): die
 *      echten Regeln aus `index.css` + `kronos.css` werden in die Seite
 *      gelegt, die Kaskade entscheidet — eingeklappter Rahmen + Liste ohne
 *      `open` ⇒ 0 px, Liste mit `open` ⇒ die volle Spalte. Beckenprobe
 *      „alter Stand“ (`--alt`) setzt die entfernte Rahmenregel zurück und
 *      MUSS rot werden.
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
  // Und die Liste kennt `--dk-sidebar-col` (64 px) nirgends als eigene Breite.
  assert.ok(!/\.kronos-sidebar[\s\S]{0,200}?width:\s*var\(--dk-sidebar-col/.test(css),
    'die Kalenderliste nimmt nicht die schmale Spalte der eingeklappten Leiste')
  // Die Karte hat den Befund am Fundort erklärt (kein stummer Löschfleck).
  assert.match(lies('kronos.css'), /MT-1c/, 'kronos.css nennt die Karte am Fundort')
})

test('MT-1c: nur die HAUPTleiste zieht sich beim Einklappen zusammen (index.css)', () => {
  const css = ohneCssKommentare(lies('index.css'))
  assert.match(css, /\.dk-app\.is-collapsed\s*\{\s*grid-template-columns:\s*var\(--dk-sidebar-col\)/,
    'der Rahmen wird über die Rasterspalte eingeklappt — nicht über die Kindbreite')
  assert.ok(!/\.dk-app\.is-collapsed[^{}]*\.kronos-sidebar/.test(css),
    'index.css fasst die Kalenderliste nicht an')
})

test('MT-1c: Kalender.vue schaltet die Liste nur über ihren Offen-Zustand', () => {
  const vue = lies('pages/Kalender.vue')
  assert.match(vue, /:class="\{ open: kronosSidebar\.offen\.value \}"/,
    'die Klasse `open` kommt aus `useKronosSidebar`')
  assert.ok(!/is-collapsed/.test(vue),
    'der Rahmenzustand steuert die Kalenderliste in der Seite nicht')
})

// ══════════════════════════════════════════════════════════════════════════
// B · Messprobe: die echten Regeln, im echten Browser, über die Kaskade
// ══════════════════════════════════════════════════════════════════════════
/** Baut die Messseite aus den ECHTEN CSS-Dateien (kein nachgebauter Auszug). */
function messseite(mitAlterRegel) {
  // tokens.css MUSS mit: ohne `--sidebar-w`/`--sidebar-col` gibt es keine
  // Spaltenbreiten, und die Probe würde nur Nullen sehen.
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
  // Die Gegenprobe auf DEMSELBEN Messweg: der alte Stand zeigt genau den
  // Befund — 64 px Streifen im eingeklappten Rahmen, und auch die OFFENE Liste
  // wird dorthin gequetscht.
  const alt = messlauf(true)
  assert.equal(alt.zu_zu.breite, 64,
    `vor MT-1c war die geschlossene Liste 64 px breit (gemessen ${alt.zu_zu.breite})` +
    ' — die Probe misst also wirklich den Befund')
  assert.equal(alt.zu_offen.breite, 64,
    `vor MT-1c blieb auch die offene Liste bei 64 px (gemessen ${alt.zu_offen.breite})`)
  // Mit dem Fix ist die Liste zu, wenn sie zu ist — in beiden Rahmenzuständen.
  assert.equal(m.zu_zu.breite, 0, `zu + Rahmen eingeklappt ⇒ 0 px (gemessen ${m.zu_zu.breite})`)
  assert.equal(m.auf_zu.breite, 0, `zu + Rahmen offen ⇒ 0 px (gemessen ${m.auf_zu.breite})`)
  // Öffnen gibt die volle Spalte her — unabhängig vom Rahmenzustand.
  assert.equal(m.zu_offen.breite, 256, `offen im eingeklappten Rahmen: ${m.zu_offen.breite} px`)
  assert.equal(m.zu_offen.breite, m.auf_offen.breite,
    'die offene Liste ist in beiden Rahmenzuständen gleich breit')
  // Und die HAUPTleiste zieht sich weiterhin zusammen (Raster 64 px).
  assert.equal(m.zu_zu.spalte, '64px', 'die HAUPTleiste bleibt beim Einklappen 64 px schmal')
  assert.equal(m.auf_zu.spalte, '256px', 'ausgeklappt nimmt sie ihre normale Spalte')
})
