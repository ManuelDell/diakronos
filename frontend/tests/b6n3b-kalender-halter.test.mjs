/**
 * B6-N3 — Kalender: Zeilen-Mindesthöhe, Mobil-Halter und die 720-px-Grenze
 * (QUELLTEXT-PRÜFUNGEN, ohne Chromium).
 *
 * WARUM DIESE DATEI NEBEN DEM MESSTEST
 * ------------------------------------
 * `tests/b6n3-kalender-zeilen-mindesthoehe.test.mjs` misst die WIRKUNG im
 * Browser (echte CSS-Dateien, echtes DOM, `getComputedStyle`) und wird im
 * Image ohne Chromium übersprungen. Die folgenden Zusagen lassen sich dort
 * nicht messen, weil sie eine STRUKTUR über zwei Dateien betreffen — sie
 * stehen hier in vier Tests:
 *
 *   E1) die 720-px-Grenze von `.kal-flaeche` (`overflow: auto`) und
 *       `.kal-karte` (`flex: 0 0 auto`) — beide in pages/Kalender.vue — UND
 *       ihre Bindung an die Mindesthöhen-Regel in kronos.css
 *       (`--ec-row-height: minmax(var(--kal-zeile-min), 1fr)`, gleicher
 *       `@media (max-width: 720px)`-Block); das sind zwei Tests
 *       (Umschalten der Fläche/Karte · gleiche Breite über beide Dateien);
 *   E2) der Mobil-Halter `.kal-mobil-raster-halter` steht wie main
 *       (`min-height: 100%`, Inhalt daran, kein eigener Scrollkasten);
 *   E3) die Seite setzt im Mobil-Monat KEINE eigene Zeilenhöhe
 *       (`--ec-row-height` kommt dort allein von der Bibliothek).
 *
 * Sie stehen deshalb hier als Quelltext-Prüfung (Muster:
 * `tests/dev-b6b-grund-handy-selektoren.test.mjs`), damit sie AUCH im Image
 * laufen und nicht nur übersprungen werden. Die Kaskade selbst belegt der
 * Messtest; hier steht der Wortlaut des Baums, der geprüft wird.
 *
 * B6-N3d: Diese drei Prüfungen kamen in B6-N3c ersatzlos weg (ein Verweis im
 * Kopf des Messtests nannte eine Datei, die es nie gab). Wiederhergestellt aus
 * B6-N3b (wt/t_0c621a2b, Datei `b6n3-kalender-zeilen-mindesthoehe.test.mjs`,
 * Punkt E).
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const hier = dirname(fileURLToPath(import.meta.url))
const SRC = resolve(hier, '..', 'src', 'diakonos')
const KALENDER = readFileSync(join(SRC, 'pages', 'Kalender.vue'), 'utf8')

/** CSS ohne Kommentare — Kommentare nennen die alten Regeln absichtlich. */
const ohneKommentare = (text) => text.replace(/\/\*[\s\S]*?\*\//g, '')

const KRONOS_CSS = ohneKommentare(readFileSync(join(SRC, 'kronos.css'), 'utf8'))

const KALENDER_STIL = (() => {
  const i = KALENDER.lastIndexOf('<style')
  assert.ok(i >= 0, 'pages/Kalender.vue: <style>-Block fehlt')
  return ohneKommentare(KALENDER.slice(i))
})()

/** Der `<script>`-Teil der Seite (dort könnte eine Zeilenhöhe gesetzt werden). */
const KALENDER_SCRIPT = (() => {
  const von = KALENDER.indexOf('<script')
  if (von < 0) return ''
  const bis = KALENDER.indexOf('</script>', von)
  return KALENDER.slice(von, bis < 0 ? undefined : bis)
})()

/**
 * Alle Regelköpfe (Selektor + Deklarationen) mit ihrer Lage: steht die Regel
 * in einem @media-Block, kommt dessen Bedingung mit. Verschachtelte @media
 * werden korrekt aufgelöst (Blockzählung über Klammern).
 */
function regeln(css) {
  const treffer = []
  const stapel = []
  let i = 0
  let kopfAb = 0
  while (i < css.length) {
    const z = css[i]
    if (z === '{') {
      const kopf = css.slice(kopfAb, i).trim()
      if (kopf.startsWith('@')) {
        stapel.push(kopf)
        i += 1
        kopfAb = i
        continue
      }
      // Deklarationsblock bis zur passenden Klammer.
      let tiefe = 1
      let j = i + 1
      while (j < css.length && tiefe > 0) {
        if (css[j] === '{') tiefe += 1
        else if (css[j] === '}') tiefe -= 1
        j += 1
      }
      treffer.push({
        selektoren: kopf.split(',').map((s) => s.replace(/\s+/g, ' ').trim()).filter(Boolean),
        koerper: css.slice(i + 1, j - 1),
        medien: [...stapel],
      })
      i = j
      kopfAb = i
      continue
    }
    if (z === '}') {
      stapel.pop()
      i += 1
      kopfAb = i
      continue
    }
    i += 1
  }
  return treffer
}

const KALENDER_REGELN = regeln(KALENDER_STIL)
const KRONOS_REGELN = regeln(KRONOS_CSS)

/** Regeln, deren Selektor-Kette GENAU `selektor` ist (Wortlaut, ohne Medien). */
const mitSelektor = (liste, selektor) => liste.filter((r) => r.selektoren.includes(selektor))

const inMedien = (regel, bedingung) => regel.medien.some((m) => m.includes(bedingung))

/** Enthält der Deklarationsblock die Zeilen-Mindesthöhe (`--ec-row-height`) auf `--kal-zeile-min`? */
const setztZeileMin = (koerper) => /--ec-row-height:\s*minmax\(\s*var\(--kal-zeile-min\)/.test(koerper)

// ══════════════════════════════════════════════════════════════════════════
// E2 · Mobil-Halter: wie main (volle Höhe, Inhalt daran, kein Scrollkasten)
// ══════════════════════════════════════════════════════════════════════════
test('B6-N3b: der Mobil-Halter steht wie main — volle Höhe, Inhalt daran (kein Scrollkasten)', () => {
  // B6-N3b (Review Runde 3, Punkt 1/2): Runde 3 hatte `min-height: 0` am Halter
  // und einen selbstgebauten Scrollkasten fuer den namenlosen Zwischenknoten
  // (`:not(...)[data-v]`, `overflow-y: auto`). Das war eine Fehlmessung: mit
  // main-Stand zeigt der Review-Nachbau auf 390×844 alle Wochen. Geprüft wird
  // deshalb der main-Stand: Halter `min-height: 100%`, darunter genau die eine
  // main-Regel fuer den inneren Kasten — KEIN eigener Scrollkasten, kein
  // `[data-v]`-Zweig.
  const halter = mitSelektor(KALENDER_REGELN, '.kal-mobil-raster-halter')
  assert.equal(halter.length, 1, 'genau EINE Regel fuer den Rasterhalter')
  const koerper = halter[0].koerper
  assert.match(koerper, /min-height:\s*100%/,
    'der Halter braucht `min-height: 100%` (main) — der Inhalt darf nicht unter ihn rutschen')
  assert.ok(!/min-height:\s*0(?![\d.])/.test(koerper),
    'kein `min-height: 0` am Halter — damit wuchs er mit dem Inhalt und die Wochen lagen hinter der Kante')
  assert.match(koerper, /flex:\s*1 1 auto/, 'der Halter fuellt die Flaechenhoehe (main)')
  assert.match(koerper, /flex-direction:\s*column/, 'der Halter stapelt Monatszeile und Raster (main)')
  assert.ok(!/overflow/.test(koerper), 'der Halter selbst scrollt nicht (main)')
  assert.ok(!/flex:\s*0 0 auto/.test(koerper),
    'kein `flex: 0 0 auto` am Halter — er soll die Flaeche fuellen')

  // Die main-Regel fuer den inneren Kasten — wortgleich, EINE Regel, ohne
  // Scrollweg: `.kal-mobil-raster-halter > .kronos-calendar-wrap,
  //  .kal-mobil-raster-halter > .kronos-calendar-shell { flex: 1 1 auto; min-height: 0; }`
  const innen = KALENDER_REGELN.filter((r) =>
    r.selektoren.includes('.kal-mobil-raster-halter > .kronos-calendar-wrap')
    || r.selektoren.includes('.kal-mobil-raster-halter > .kronos-calendar-shell'))
  assert.equal(innen.length, 1, 'genau EINE Regel fuer den inneren Kasten (main-Stand)')
  assert.deepEqual(innen[0].selektoren, [
    '.kal-mobil-raster-halter > .kronos-calendar-wrap',
    '.kal-mobil-raster-halter > .kronos-calendar-shell',
  ], 'die Selektor-Liste ist der main-Stand — kein zusaetzlicher Zweig')
  assert.equal(innen[0].medien.length, 0, 'die Regel gilt ohne Medienbedingung (main)')
  assert.match(innen[0].koerper, /flex:\s*1 1 auto/, 'der innere Kasten fuellt den Halter')
  assert.match(innen[0].koerper, /min-height:\s*0/, 'der innere Kasten darf schrumpfen')
  assert.ok(!/overflow/.test(innen[0].koerper),
    'der innere Kasten bringt KEIN eigenes Scrollen mit — das war der B6-N3-Umbau')

  // Der namenlose Zwischenknoten-Umbau aus Runde 3 ist ganz weg: kein
  // `:not(.kal-monat-mobil)`-Zweig und kein `[data-v]`-Zweig am Halter.
  const umbau = KALENDER_REGELN.filter((r) => r.selektoren.some((s) =>
    /kal-mobil-raster-halter\s*>/.test(s)
    && (/:not\(\.kal-monat-mobil\)|\[data-v/.test(s))))
  assert.deepEqual(umbau.map((r) => r.selektoren), [],
    'der Runde-3-Umbau am Halter (`:not(.kal-monat-mobil)`, `[data-v]`) ist entfernt')
})

// ══════════════════════════════════════════════════════════════════════════
// E1 · 720-px-Grenze: Scrollen der Fläche und Wachsen der Karte, gleiche Breite
// ══════════════════════════════════════════════════════════════════════════
test('B6-N3: Scrollen der Fläche und Wachsen der Karte stehen im Block ≤ 720 px', () => {
  const flaeche = mitSelektor(KALENDER_REGELN, '.kal-flaeche')
    .filter((r) => /overflow:\s*auto/.test(r.koerper))
  assert.equal(flaeche.length, 1, 'genau EINE Regel lässt die Fläche scrollen')
  assert.ok(inMedien(flaeche[0], 'max-width: 720px'),
    'die Fläche darf NUR im schmalen Fenster scrollen (am Desktop gibt es keinen Überstand)')

  const karte = mitSelektor(KALENDER_REGELN, '.kal-karte')
    .filter((r) => /flex:\s*0 0 auto/.test(r.koerper))
  assert.equal(karte.length, 1, 'genau EINE Regel nimmt der Karte das Schrumpfen')
  assert.ok(inMedien(karte[0], 'max-width: 720px'),
    'die Karte wächst NUR im schmalen Fenster mit ihrer natürlichen Höhe')

  // Beide hängen an DERSELBEN Grenze wie die Mindesthöhe — und die steht in
  // kronos.css, also in einer ANDEREN Datei: `.kal-flaeche .ec-month-view
  // .ec-day-grid .ec-main { --ec-row-height: minmax(var(--kal-zeile-min), 1fr) }`.
  // Ohne diesen Vergleich bliebe ungeschützt, dass die Mindesthöhe bei einer
  // anderen Breite greift als Scrollweg/Wachstum (z. B. `900px` → Mindesthöhe
  // auch am Desktop, während Fläche/Karte erst unter 720 px umschalten).
  const zeilenSetzer = KRONOS_REGELN.filter((r) => setztZeileMin(r.koerper))
  assert.ok(zeilenSetzer.length > 0,
    'kronos.css setzt `--ec-row-height` nicht auf `var(--kal-zeile-min)` — Bezug fehlt')
  const grenzen = new Set(zeilenSetzer.flatMap((r) => r.medien))
  assert.deepEqual([...grenzen], ['@media (max-width: 720px)'],
    'die Mindesthöhe in kronos.css muss an genau EINER Breite hängen, dem Block `@media (max-width: 720px)`')
  assert.equal(flaeche[0].medien.join(' '), karte[0].medien.join(' '),
    'Scrollweg der Fläche und Wachsen der Karte müssen an derselben Breite hängen')
  assert.deepEqual([...grenzen], karte[0].medien,
    'Mindesthöhe (kronos.css) und Scrollweg/Wachstum (pages/Kalender.vue) müssen an derselben Breite hängen')
  assert.deepEqual([...grenzen], flaeche[0].medien,
    'Mindesthöhe (kronos.css) und Scrollen der Fläche (pages/Kalender.vue) müssen an derselben Breite hängen')
})

test('B6-N3: am Desktop/Handy bleibt die Fläche ohne Scrollkasten', () => {
  // Gegenprobe: keine unbedingte Regel setzt `overflow: auto` an der Fläche.
  for (const r of mitSelektor(KALENDER_REGELN, '.kal-flaeche')) {
    if (r.medien.length) continue
    assert.ok(!/overflow(-y)?:\s*(auto|scroll)/.test(r.koerper),
      'unbedingtes Scrollen an .kal-flaeche — am Desktop entstünde ein toter Scrollkasten')
  }
  // Und die Karte schrumpft am Desktop weiter (kein `flex: 0 0 auto` global).
  for (const r of mitSelektor(KALENDER_REGELN, '.kal-karte')) {
    if (r.medien.length) continue
    assert.ok(!/flex:\s*0 0 auto/.test(r.koerper),
      'die Karte darf oberhalb von 720 px nicht auf natürliche Höhe wachsen')
  }
})

// ══════════════════════════════════════════════════════════════════════════
// E3 · Mobil-Monat: die Seite setzt KEINE eigene Zeilenhöhe (Bau wie main)
// ══════════════════════════════════════════════════════════════════════════
test('B6-N3: die Seite setzt im Mobil-Monat KEINE eigene Zeilenhöhe (Bau wie main)', () => {
  // Review-Runde 3, Punkt 1: Die Rücksetzungen aus Runde 2 änderten die
  // Handy-Hochlage (Monat 66 → 40 px, Woche ohne Innen-Scroll). Ursache war die
  // Mindesthöhe, die auch am Handy griff — sie ist jetzt an `.kal-flaeche`
  // gebunden (kronos.css), der Mobil-Bau bleibt unberührt.
  //
  // ACHTUNG: `tests/dev-b6b-grund-handy-selektoren.test.mjs` deckt diesen Fall
  // NICHT ab (der Bericht zu B6-N3c behauptete das faelschlich) — jene Datei
  // prüft Grund-/Handy-Selektoren von Befehlspalette und Seitenleiste.
  const setzer = KALENDER_REGELN.filter((r) => /--ec-row-height/.test(r.koerper))
  assert.deepEqual(setzer.map((r) => r.selektoren.join(', ')), [],
    'die Seite setzt `--ec-row-height` — im Mobil-Monat gilt allein die Bibliothek')
  // Auch nicht ueber einen Inline-Stil in der Vorlage oder ein Skript der Seite.
  assert.ok(!/ec-row-height/.test(KALENDER_SCRIPT),
    'pages/Kalender.vue setzt `--ec-row-height` im Skript — der Mobil-Monat gehört der Bibliothek')
})
