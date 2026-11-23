/**
 * BEF-DESIGN-2 — Wächter: Abstände und Schalterzeilen auf der Website-Seite.
 *
 * Befund Manuel 23.11. (#/website, DMB-ac3b): „Design inkonsistent
 * Margin/Padding“. Die Karte „Kalender“ war uneinheitlich: die Schalterzeilen
 * standen eingerückt ohne sichtbaren Schalter davor und klebten am Text
 * darüber, Hilfetexte hatten unterschiedliche Abstände (mal direkt darunter,
 * mal mit Lücke), und das Kürzel-Feld war anders breit als sein Hilfetext.
 *
 * Der Wächter hält die Umstellung fest (Gegenprobe: jeder Test wird gegen die
 * alte Fassung rot, weil dort nackte `DkCheckbox`-Elemente ohne Bereich,
 * eigene `<ul>`-Listen mit `--sp-1` und ein `.wf-zeile-slugfeld` mit
 * `max-width: 420px` standen):
 *
 *   T1  Die Schalter dieser Seite sind `DkSchalterZeile` — je Schalter eine
 *       eigene Zeile, `v-model` gebunden, sichtbares Kästchen links (der
 *       Baustein rendert `DkCheckbox`, nicht nur Text).
 *   T2  Die Zeile trägt ihren Hilfetext über `aria-describedby` am Kästchen —
 *       und zwar NUR, wenn es einen gibt (kein Zeiger ins Leere).
 *   T3  Feld und Hilfetext teilen EINE Breite: `DkField` (EINE Quelle für
 *       Label, Hilfe, Meldung) füllt die Spalte über `.wf-feldspalte`
 *       (`width: 100%`), und das Kürzel-Feld hat keine eigene Obergrenze mehr.
 *   T4  Der Inhalt jeder Karte läuft in EINEM Raster (`.wf-abschnitt`,
 *       Abstand `--gap`) — keine losen Absatz-Ketten mehr.
 *   T5  KEIN fester Abstandswert in den drei Dateien (der Rechner aus UX1a
 *       zählt `margin`, `padding`, `gap`, `border*`, `border-radius`).
 *   T6  Nur Tokens als Abstand — jede Abstands-Deklaration der drei Dateien
 *       nennt eine `var(--…)`-Quelle.
 *
 * Läuft im Docker-Build (`node --test`); liest nur `frontend/**` (Regel 13).
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import { fundstellen, wertIstFest } from '../tools/abstand-bestand.mjs'

const HIER = path.dirname(fileURLToPath(import.meta.url))
const FRONTEND = path.resolve(HIER, '..')

/** Die drei Dateien der Umstellung (Seite, Zeile, Bausteine). */
const SEITE = 'src/diakonos/pages/Website.vue'
const ZEILE = 'src/diakonos/components/website/FreigabeZeile.vue'
const SCHALTERZEULE = 'src/diakonos/components/ui/DkSchalterZeile.vue'
const FELD = 'src/diakonos/components/ui/DkField.vue'
const KENNUNGEN = 'src/diakonos/components/ui/formularZeile.mjs'

const lies = (rel) => readFileSync(path.join(FRONTEND, rel), 'utf8')

/** Kommentare entfernen — geprüft wird der Code, nicht die Erklärung. */
function ohneKommentar(text) {
  return text
    .replace(/<!--[\s\S]*?-->/g, '')
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/^\s*\/\/.*$/gm, '')
}

/** Alle `<style …>…</style>`-Blöcke einer .vue-Datei. */
function styles(quelle) {
  return [...quelle.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)].map((m) => m[1]).join('\n')
}

// ── T1 · Schalter sind eigene Zeilen des gemeinsamen Bausteins ────────────
test('BEF-DESIGN-2/T1: die Schalter der Seite sind Schalterzeilen des Bausteins', () => {
  const seite = ohneKommentar(lies(SEITE))
  const zeile = ohneKommentar(lies(ZEILE))

  // Der Bereich „Kalender“ und die Terminarten nutzen den Baustein.
  assert.match(seite, /<DkSchalterZeile[\s\S]*?nurFreigegebene[\s\S]*?\/>/,
    '„Nur freigegebene Kalender zeigen“ ist keine Schalterzeile')
  assert.match(seite, /<DkSchalterZeile[\s\S]*?:label="k\.titel"/,
    'die Terminarten sind keine Schalterzeilen')
  // Auch die Freigabe-Zeile: je Freigabe EINE Schalterzeile mit dem Titel.
  assert.match(zeile, /<DkSchalterZeile[\s\S]*?:aria-label="`Auf Website zeigen: \$\{titel\}`"/,
    'die Freigabe-Zeile hat keinen Schalter mehr in der Zeile')
  assert.match(zeile, /<span class="wf-zeile-titel">\{\{ titel \}\}<\/span>/,
    'der Titel steht nicht als Beschriftung im Schalter')

  // KEIN nacktes Kästchen mehr direkt in der Seite (das war der Befund:
  // eingerückter Text ohne sichtbaren Schalter davor).
  assert.doesNotMatch(seite, /<DkCheckbox/,
    'die Seite setzt noch ein nacktes DkCheckbox — dafür gibt es DkSchalterZeile')

  // Der Baustein rendert wirklich einen Schalter (Kästchen), nicht nur Text —
  // und er steht VOR der Beschriftung (linksbündig).
  const baustein = ohneKommentar(lies(SCHALTERZEULE))
  assert.match(baustein, /<DkCheckbox/, 'die Schalterzeile rendert kein Kästchen')
  const kaestchen = baustein.indexOf('<DkCheckbox')
  const beschriftung = baustein.indexOf('<slot>{{ label }}</slot>')
  assert.ok(kaestchen >= 0 && beschriftung > kaestchen,
    'das Kästchen muss VOR der Beschriftung stehen (linksbündig)')
})

// ── T2 · Hilfetext hängt am Kästchen, aber nur wenn es einen gibt ─────────
test('BEF-DESIGN-2/T2: der Hilfetext gehört per aria-describedby zum Schalter', async () => {
  const { beschriebenDurch, hilfeKennung, hatHilfe, zeilenKennung } = await import(
    `../${KENNUNGEN}`
  )
  const kennung = zeilenKennung(() => 'zeile-7')

  // Reihenfolge wie in DkField: Meldung vor Hilfe vor nichts.
  assert.equal(beschriebenDurch({ fehler: '', hilfe: 'Text', kennung }), hilfeKennung(kennung))
  assert.match(beschriebenDurch({ fehler: 'Server sagt nein', hilfe: 'Text', kennung }), /fehler/)

  // Nur ODER-Verknüpfung ist falsch: eine Meldung, die `fehlerKennung` heisst,
  // darf nicht die Hilfe-Kennung tragen.
  assert.notEqual(
    beschriebenDurch({ fehler: 'kaputt', hilfe: 'Text', kennung }),
    hilfeKennung(kennung),
  )

  // Ohne Hilfe und ohne Meldung: KEIN Zeiger ins Leere.
  assert.equal(beschriebenDurch({ fehler: '', hilfe: '', kennung }), undefined)
  assert.equal(hatHilfe('   '), false)
  assert.equal(hatHilfe('ein Satz'), true)

  // Der Baustein setzt beides am Kästchen.
  const baustein = ohneKommentar(lies(SCHALTERZEULE))
  assert.match(baustein, /:aria-describedby="zeilenBeschreibung \|\| ''"/,
    'der Schalter trägt kein aria-describedby')
  assert.match(baustein, /v-else-if="zeilenHilfe"\s+:id="hilfeId"/,
    'der Hilfetext hat keine Kennung — aria-describedby zeigt ins Leere')
  // Meldung VOR Hilfe (`v-if` / `v-else-if`): sonst stünden beide gleichzeitig
  // da (Befund beim Rendertest R5).
  const posMeldung = baustein.indexOf('v-if="meldung"')
  const posHilfe = baustein.indexOf('v-else-if="zeilenHilfe"')
  assert.ok(posMeldung >= 0 && posHilfe > posMeldung,
    'Meldung und Hilfetext sind keine Entweder-oder-Zeilen')
})

// ── T3 · Feld und Hilfetext teilen EINE Breite ───────────────────────────
test('BEF-DESIGN-2/T3: Feld und Hilfetext sind gleich breit', () => {
  // EINE Quelle für Felder mit Hilfetext: `DkField` — Hilfe und Meldung
  // stehen darunter, ohne eigenen Außenabstand (kein zweiter Baustein).
  const feld = ohneKommentar(lies(FELD))
  assert.match(feld, /\.dk-ui-field \{ display: flex; flex-direction: column; gap: var\(--sp-1\); \}/,
    'DkField ist keine Spalte mit Token-Abstand')
  assert.match(feld, /\.dk-ui-field-hilfe \{[^}]*margin: 0/,
    'der Hilfetext hat einen eigenen Außenabstand')

  const zeile = ohneKommentar(lies(ZEILE))
  // KEINE eigene Obergrenze mehr am Kürzel-Feld (der Befund: 420 px gegen
  // einen Hilfetext über die volle Breite).
  assert.doesNotMatch(zeile, /max-width:\s*420/,
    'das Kürzel-Feld trägt noch seine eigene Obergrenze')
  assert.doesNotMatch(zeile, /420px/, 'das Kürzel-Feld trägt noch 420px')
  assert.match(zeile, /\.wf-zeile-slugfeld \{ width: 100%/, 
    'das Kürzel-Feld füllt die Spalte nicht')

  // In den Formularen der Seite füllen alle Felder die Zeile.
  const seite = ohneKommentar(lies(SEITE))
  assert.match(seite, /\.wf-feldspalte \{\s*width: 100%;?\s*\}/,
    'die Felder der Formulare füllen die Zeile nicht')
})

// ── T4 · Der Inhalt einer Karte ist EIN Raster ───────────────────────────
test('BEF-DESIGN-2/T4: Karteninhalt läuft in EINEM Raster mit --gap', () => {
  const seite = ohneKommentar(lies(SEITE))
  const abschnitte = seite.match(/class="wf-abschnitt"/g) || []
  // Fünf Karten mit Inhalt (Kalender, Terminarten, Gruppen, Beiträge,
  // Kontakt-Postfächer) — jede mit dem gemeinsamen Raster.
  assert.ok(abschnitte.length >= 5, `nur ${abschnitte.length} Karten nutzen das Raster`)
  assert.match(seite, /\.wf-abschnitt \{[\s\S]*?gap: var\(--gap\)/,
    'das Raster der Karten kennt keinen Gruppenabstand (--gap)')
  // Die Schalter untereinander haben denselben Abstand (kein eigenes Maß).
  assert.match(seite, /\.wf-schalterliste \{[^}]*gap: var\(--gap\)/,
    'die Schalterliste hat einen eigenen Abstand statt --gap')
  // Der alte, engere Kategorie-Kasten ist entfallen.
  assert.doesNotMatch(seite, /class="wf-kategorien"/,
    'die alte Liste der Terminarten (eigener Abstand --sp-1) steht noch da')
})

// ── T5 · Keine festen Abstandswerte in den drei Dateien (Seite, Zeile, Schalterzeile) ──────────────────
test('BEF-DESIGN-2/T5: keine festen padding/margin-Werte auf der Seite', () => {
  const verstoesse = []
  for (const datei of [SEITE, ZEILE, SCHALTERZEULE]) {
    const quelle = lies(datei)
    // Nur der Style-Block zählt: Kommentare und Vorlage dürfen px nennen.
    for (const fund of fundstellen(styles(quelle))) {
      verstoesse.push(`${datei}: ${fund.eigenschaft}: ${fund.wert}`)
    }
  }
  assert.deepEqual(verstoesse, [], 'feste Abstandswerte:\n' + verstoesse.join('\n'))
})

// ── T6 · Jeder Abstand kommt aus einem Token ─────────────────────────────
test('BEF-DESIGN-2/T6: Abstände der Seite kommen ausschließlich aus Tokens', () => {
  const ABSTAND = /(?<![\w-])(margin|padding|gap|row-gap|column-gap|inset)(?:-(?:top|right|bottom|left|inline|block|start|end))*\s*:\s*([^;{}]+)/gi
  const fehler = []
  for (const datei of [SEITE, ZEILE, SCHALTERZEULE]) {
    const css = styles(lies(datei)).replace(/\/\*[\s\S]*?\*\//g, ' ')
    for (const m of css.matchAll(ABSTAND)) {
      const wert = m[2].trim()
      // `0` ist kein Abstand, `auto` keine Zahl — beides ohne Token erlaubt.
      if (/^0(?:px)?$/.test(wert) || /^auto$/.test(wert)) continue
      if (!/var\(--/.test(wert)) fehler.push(`${datei}: ${m[1]}: ${wert}`)
      // Ein fester Wert NEBEN einem Token ist ebenfalls ein eigener Wert.
      if (wertIstFest(wert.replace(/var\([^)]*\)/g, ''))) fehler.push(`${datei}: ${m[1]}: ${wert} (fester Wert neben Token)`)
    }
  }
  assert.deepEqual(fehler, [], 'Abstand ohne Token:\n' + fehler.join('\n'))
})
