/**
 * UX3i3 — Kalender: Kontrast in Woche/Liste, Mobil-Chips, Chip-Text.
 *
 * Karte t_79a73f65 (Altlast aus dem Review zu UX3i-N2, 08.11.). Geprüft wird,
 * was der Test WIRKLICH AUSFÜHREN kann — die reinen Funktionen aus
 * `chipText.mjs` und eine Messfunktion gegen echte Farbwerte. Die Optik selbst
 * (gerenderte Fläche, Kontrast im Browser) weist der Abnahmelauf gegen den
 * Wegwerf-Stack nach (Screenshots hell/dunkel, Desktop 1440 + Mobil 390,
 * Messprotokoll `ux3i3-*.json`).
 *
 *   1. Chip-Text „Titel 19:00“ — eine Reihenfolge durchgängig; der volle
 *      Titel steht in `title`/`aria-label` (Befund 4).
 *   2. `chipFarben` liefert für JEDE Kalenderfarbe in HELL und DUNKEL eine
 *      Schrift, deren Kontrast gegen die TATSÄCHLICH gerenderte Fläche
 *      ≥ 4,5:1 ist (Befunde 1/2) — auch für Flächen, die kräftiger gemischt
 *      werden (55 %).
 *   3. Kein toter Code mehr: der 55-%-Zweig rechnet keine ungenutzte Marke
 *      (Befund 5).
 *   4. Der Kalender baut Monat, Woche, Liste und Handy aus EINER Chip-Logik
 *      (Befunde 2/3); `kronos.css` blendet die Uhrzeit am Handy nicht mehr
 *      aus und nimmt die Listen-Vorgaben der Bibliothek zurück.
 *
 * Der Test liest NUR Dateien innerhalb von frontend/ (Regel 13) und braucht
 * kein Netz.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { pathToFileURL, fileURLToPath } from 'node:url'

const hier = dirname(fileURLToPath(import.meta.url))
const FRONTEND = resolve(hier, '..')
const SRC = join(FRONTEND, 'src', 'diakonos')
const lies = (rel) => readFileSync(join(SRC, rel), 'utf8')

const chip = await import(pathToFileURL(join(SRC, 'components/kronos/chipText.mjs')).href)

// ══════════════════════════════════════════════════════════════════════════
// 0 · Messwerkzeug: Kontrast gegen die GERENDERTE Fläche (Befund 6)
// ══════════════════════════════════════════════════════════════════════════
/*
 * Das alte Messwerkzeug (`n3-screenshots.mjs`, Messung „Kontrast 1,04“)
 * zog die Zahlen aus `getComputedStyle(chip).backgroundColor`. Trifft die
 * Auflösung eine `color-mix()`-Fläche nicht (oder liefert `transparent`),
 * rechnete es gegen SCHWARZ — und meldete 1,04 bei sichtbar gutem Kontrast.
 * Hier wird die Fläche deshalb aus den WERTEN gerechnet, die der Chip
 * tatsächlich setzt: Kalenderfarbe (mit Deckkraft) über der Kartenfläche,
 * und bei `--chip-flaeche` dieselbe Mischung, die `chipStil` ausgibt.
 * Der Browser-Lauf prüft zusätzlich die gerenderte Fläche.
 */

const ZWEI = (n) => String(n).padStart(2, '0')

/** `#rrggbb`/`#rrggbbaa` -> [r,g,b] (Alpha über `grund` gemischt). */
function alsRgb(wert, grund = [255, 255, 255]) {
  const s = String(wert || '').trim()
  const m = /^#([0-9a-fA-F]{6})([0-9a-fA-F]{2})?$/.exec(s)
  if (!m) return null
  const n = parseInt(m[1], 16)
  const rgb = [(n >> 16) & 255, (n >> 8) & 255, n & 255]
  if (!m[2]) return rgb
  const a = parseInt(m[2], 16) / 255
  return rgb.map((c, i) => Math.round(c * a + grund[i] * (1 - a)))
}

function luminanz([r, g, b]) {
  const f = (c) => {
    const s = c / 255
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
  }
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)
}

function kontrast(a, b) {
  const la = luminanz(a)
  const lb = luminanz(b)
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05)
}

const KARTE = { hell: [255, 255, 255], dunkel: [26, 31, 46] }
const MARKE = { hell: [0, 5, 31], dunkel: [255, 255, 255] } // navy-900 / warm-0

/** Die Fläche, die der Chip im Browser zeigt. */
function gerenderteFlaeche(kalenderfarbe, theme) {
  const grund = KARTE[theme]
  const sichtbar = alsRgb(kalenderfarbe, grund)
  if (!sichtbar) return grund
  // `chipFarben` mischt entweder 22 % oder (bei zu wenig Kontrast) 55 %.
  const anteil = chip.chipFarben(kalenderfarbe, { theme }).flaeche ? 0.55 : 0.22
  return sichtbar.map((c, i) => Math.round(c * anteil + grund[i] * (1 - anteil)))
}

const FARBEN = [
  '#16a34a', '#2563eb', '#db2777', '#78716c', '#c9952f', '#1c2850',
  '#f7eee0', '#ffe600', '#2d78f0', '#ee2266', '#16a34a99', '#2563eb80',
]

// ══════════════════════════════════════════════════════════════════════════
// 1 · Chip-Text: Titel zuerst, Uhrzeit hinten (Befund 4)
// ══════════════════════════════════════════════════════════════════════════
const termin = (start, ende, zusatz = {}) => ({
  title: zusatz.title ?? 'Gottesdienst am 1. Advent',
  start: new Date(start),
  end: ende === null ? null : new Date(ende),
  allDay: zusatz.allDay ?? false,
})

test('UX3i3: Chip zeigt „Titel 19:00“ — Titel zuerst, Uhrzeit hinten', () => {
  const t = termin('2026-11-08T19:00:00', '2026-11-08T20:30:00')
  assert.equal(chip.chipText(t), 'Gottesdienst am 1. Advent 19:00',
    'A4 zeigt „Chor 19:00“: der Titel steht vorn und wird nicht von der Uhrzeit verdrängt')
  // Der Befund wörtlich: „10:00 Gottes…“ schnitt den Titel ab.
  assert.doesNotMatch(chip.chipText(t), /^\d{2}:\d{2}\s/, 'kein Zeitstempel am Anfang')
  assert.equal(chip.chipText(termin('2026-11-02T09:05:00', '2026-11-02T10:00:00', { title: 'Chorprobe' })),
    'Chorprobe 09:05')
})

test('UX3i3: ganztägig/mehrtägig tragen keine Uhrzeit (Bestand bleibt)', () => {
  assert.equal(chip.chipText({ title: 'Herbstfreizeit', start: new Date('2026-11-07T00:00:00'), end: new Date('2026-11-09T00:00:00'), allDay: true }),
    'Herbstfreizeit')
  assert.equal(chip.chipText(termin('2026-11-07T18:00:00', '2026-11-08T12:00:00', { title: 'Nacht der Lieder' })),
    'Nacht der Lieder')
})

test('UX3i3: der VOLLE Titel steht in title/aria-label, nie abgeschnitten', () => {
  const lang = termin('2026-11-08T10:00:00', '2026-11-08T11:30:00', {
    title: 'Gottesdienst am Christkönigssonntag mit Abendmahl und Kirchenchor',
  })
  const titel = chip.chipTitel(lang)
  assert.ok(titel.startsWith('Gottesdienst am Christkönigssonntag mit Abendmahl und Kirchenchor · '),
    'voller Titel am Anfang des aria-labels')
  assert.match(titel, /10:00–11:30/)
})

// ══════════════════════════════════════════════════════════════════════════
// 2 · Kontrast ≥ 4,5:1 gegen die gerenderte Fläche (Befunde 1/2/6)
// ══════════════════════════════════════════════════════════════════════════
test('UX3i3: jede Kalenderfarbe trägt AA — hell UND dunkel', () => {
  for (const theme of ['hell', 'dunkel']) {
    for (const farbe of FARBEN) {
      const flaeche = gerenderteFlaeche(farbe, theme)
      const n = kontrast(flaeche, MARKE[theme])
      assert.ok(n >= 4.5,
        `${theme}/${farbe}: Kontrast ${n.toFixed(2)} < 4,5 gegen die gerenderte Fläche`)
    }
  }
})

test('UX3i3: die Messung liest die gerenderte Fläche, nicht den nackten Farbton', () => {
  // Regression zu „Kontrast 1,04“: eine Fläche, die nicht aufgelöst werden
  // konnte, wurde gegen SCHWARZ gerechnet. Die neue Messung nimmt die
  // Kartenfläche — ein grauer Chip ergibt dann einen plausiblen Wert.
  const flaeche = gerenderteFlaeche('#78716c', 'hell')
  assert.ok(flaeche.every((c) => c >= 200), 'grauer Chip mischt auf Weiß zu einer hellen Fläche')
  const n = kontrast(flaeche, MARKE.hell)
  assert.ok(n > 4.5 && n < 21, `plausibler Kontrast (${n.toFixed(2)}), kein 1,04-Artefakt`)
  // Ohne verwertbare Farbe ist die Fläche die Karte selbst.
  assert.deepEqual(gerenderteFlaeche('', 'hell'), KARTE.hell)
  assert.deepEqual(gerenderteFlaeche('kein-farbwert', 'dunkel'), KARTE.dunkel)
})

// ══════════════════════════════════════════════════════════════════════════
// 3 · Kein toter Code im 55-%-Zweig (Befund 5)
// ══════════════════════════════════════════════════════════════════════════
test('UX3i3: chipFarben rechnet keine ungenutzte Marke mehr', () => {
  const quelle = lies('components/kronos/chipText.mjs')
  // Der Befund nannte die Zeilen 238–243: `markeStark`/`kWeissStark` wurden
  // gerechnet, aber nie benutzt. Gesucht wird im AUSFÜHRBAREN Teil
  // (Kommentare zählen nicht — die Erklärung „hier stand toter Code“ bleibt).
  const code = quelle.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '')
  assert.doesNotMatch(code, /markeStark/, 'markeStark war toter Code (berechnet, nie benutzt)')
  assert.doesNotMatch(code, /kWeissStark/, 'kWeissStark war toter Code')
  // Eine Farbe, die die 22-%-Mischung nicht trägt, landet im 55-%-Zweig —
  // und bekommt dieselbe `light-dark()`-Marke (kein Sonderweg).
  const schwach = FARBEN.map((f) => chip.chipFarben(f, { theme: 'hell' }))
  assert.ok(schwach.every((e) => /^light-dark\(var\(--dk-navy-900\), var\(--dk-warm-0\)\)$/.test(e.schrift)),
    'alle Fälle liefern dieselbe `light-dark()`-Marke')
})

// ══════════════════════════════════════════════════════════════════════════
// 4 · Eine Chip-Logik für Monat, Woche, Liste und Handy (Befunde 2/3)
// ══════════════════════════════════════════════════════════════════════════
test('UX3i3: der Kalender baut ALLE Ansichten aus demselben Chip', () => {
  const quelle = lies('components/kronos/KronosCalendar.vue')
  // Der Chip wird nicht mehr auf die Monatsansicht begrenzt.
  assert.doesNotMatch(quelle, /if\s*\(\s*isMonthView\s*&&\s*!isMobile\s*\)/,
    'Chip galt nur im Monat — Woche und Liste hatten eine andere Optik')
  assert.match(quelle, /chipStil\(sichereFarbe\(event\.backgroundColor\)/,
    'Fläche und Schrift kommen aus `chipStil` (eine Rechnung für alle Ansichten)')
  const chips = quelle.match(/class=\\?"?\s*ec-chip/g) || []
  assert.ok((quelle.match(/class="ec-chip"/g) || []).length === 1,
    'genau EIN Chip-Aufbau im Quelltext (kein zweiter Sonderweg)')
  void chips
  // Die alte Kachel-Schrift (schwarz auf Lila) wird hier nicht mehr gesetzt.
  assert.doesNotMatch(quelle, /kachelSchrift/,
    'die Kachel-Schrift der Bibliothek war die Ursache für schwarze Schrift auf Lila')
})

test('UX3i3: am Handy gilt dieselbe Chip-Optik wie am Desktop', () => {
  const css = lies('kronos.css')
  assert.doesNotMatch(css, /\.ec-event-time\s*\{\s*display:\s*none/,
    'die Uhrzeit am Handy auszublenden ließ Termine ohne Zeit stehen')
  // Die Listen-Vorgaben der Bibliothek werden zurückgenommen …
  // `background-color` — genau die EIGENSCHAFT, die die Bibliothek in
  // `.ec-event` setzt (`.ec-list .ec-event`, `.ec-event`). Ein Kurzschrift-
  // `background` war im gebauten CSS nicht durchgekommen (Nacharbeit 2).
  assert.match(css, /\.ec-list \.ec-event\.ec-chip-event\s*\{[^}]*background-color:\s*transparent/s,
    'die Liste darf keinen vollen Farbbalken mehr malen')
  assert.match(css, /\.ec-list \.ec-event\.ec-chip-event\s*\{[^}]*padding:\s*0/s,
    'die Zeile darf den Chip nicht mehr einrücken')
  // … und der Chip gilt dort wie überall.
  assert.match(css, /\.ec-list \.ec-chip\s*\{[^}]*min-height:\s*var\(--control-h\)/s,
    'Klickfläche in der Liste aus dem Konzept-Token (40 px / 44 px grober Zeiger)')
  // Kein zweiter Chip-Aufbau für die enge Handy-Lage (Befund 3: „satte
  // Kacheln statt getönter Chips“).
  const quelle = lies('components/kronos/KronosCalendar.vue')
  const code = quelle.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '')
  assert.equal((code.match(/class="ec-chip"/g) || []).length, 1,
    'es gibt genau EINEN Chip-Aufbau — kein Handy-Sonderweg mit eigener Kachel')
  assert.doesNotMatch(code, /ec-event-inhalt/,
    'die Handy-Sonderform (eigene Kachel) ist nicht mehr im Inhalt')
})

test('NACHTRAG 2b: die Chip-Regel nimmt GENAU die Eigenschaft der Bibliothek zurück', () => {
  const css = lies('kronos.css')
  // Die Bibliothek malt die satte Kachel über `background-color` in `.ec-event`
  // (0-1-0). Eine Rücknahme per Kurzschrift `background` hat im gebauten CSS
  // nicht gewirkt — der Termin blieb in der Woche/Liste eine volle Farbe
  // (gemessen im Browser: `.ec-event` rgb(16,185,129)).
  const start = css.indexOf('.ec-month-view .ec-event.ec-chip-event,')
  assert.ok(start > 0, 'die Chip-Gruppe fehlt')
  const block = css.slice(start, css.indexOf('}', start))
  assert.match(block, /background-color:\s*transparent/, 'Rücknahme über `background-color`')
  assert.doesNotMatch(block.replace(/\/\*[\s\S]*?\*\//g, ''), /(^|;|\s)background:/,
    'Kurzschrift `background` nimmt die Eigenschaft der Bibliothek nicht zurück')
})

test('UX3i3: Chip-Optik steht als EINE Regelgruppe, ohne feste Farbwerte', () => {
  const css = lies('kronos.css')
  const start = css.indexOf('.ec-chip {')
  assert.ok(start > 0, '`.ec-chip` fehlt')
  const block = css.slice(start, css.indexOf('}', start))
  assert.doesNotMatch(block, /#[0-9a-fA-F]{3,8}/, 'keine festen Farbwerte in der Komponente')
  assert.match(block, /var\(--chip-flaeche/, 'Fläche aus dem Token/Inline-Wert')
  assert.match(block, /var\(--chip-ink/, 'Schrift aus dem Token/Inline-Wert')
})

// ══════════════════════════════════════════════════════════════════════════
// 5 · Nacharbeit aus dem Review (08.11.) — Regressionen und Widerspruch 6
// ══════════════════════════════════════════════════════════════════════════
test('NACHTRAG 1: die Wochentagszeile im Monat ist NICHT ausgeblendet (A4)', () => {
  const css = lies('kronos.css')
  // Regression: `.ec.ec-month-view .ec-header { display: none }` nahm „Mo … So“
  // aus A4 heraus. Verboten ist `display: none` für den Kopf — erlaubt bleibt,
  // seine Fläche auf die Karte zu legen.
  const kopf = [...css.matchAll(/\.ec\.ec-month-view\s+\.ec-header\s*\{([^}]*)\}/g)].map((m) => m[1])
  assert.ok(kopf.length > 0, 'die Regel für den Monats-Kopf fehlt')
  for (const block of kopf) {
    assert.doesNotMatch(block, /display:\s*none/, 'die Wochentagszeile gehört zu A4 und bleibt sichtbar')
  }
  // Die Werkzeugleiste der Bibliothek (leer, 14 px Abstand darunter) bleibt weg.
  assert.match(css, /\.ec\s*>\s*\.ec-toolbar\s*\{[^}]*display:\s*none/s,
    'die leere Werkzeugleiste darf ausgeblendet bleiben')
})

test('NACHTRAG 2: `ec-chip-event` wird in JEDER Ansicht vergeben', () => {
  const quelle = lies('components/kronos/KronosCalendar.vue')
  const i = quelle.indexOf('eventClassNames:')
  assert.ok(i > 0, 'eventClassNames fehlt')
  const block = quelle.slice(i, quelle.indexOf('eventContent:', i))
  assert.match(block, /const classes = \['ec-chip-event'\]/,
    'ohne die Klasse greifen die Chip-Regeln in Woche/Liste/Mobil nicht (dicker Farbring)')
  // Der Punkt-Stil des Monats ist eine ZUSATZ-Klasse, kein Ersatz.
  assert.match(block, /classes\.push\('ec-event-dot-style'\)/,
    'der Monats-Punkt bleibt eine zusätzliche Klasse')
})

test('NACHTRAG 4: der tote `:has()`-Block ist entfernt, das Band in der Woche behandelt', () => {
  const css = lies('kronos.css')
  // Der Wirkungslose Block (Review: „mein Versuch greift nicht“) ist GELÖSCHT,
  // nicht umkommentiert — außerhalb von Kommentaren darf `:has(` nicht mehr
  // als Selektor auftauchen.
  const code = css.replace(/\/\*[\s\S]*?\*\//g, '')
  assert.doesNotMatch(code, /:has\(/, 'der wirkungslose `:has()`-Selektor ist zu entfernen')
  // Der Kopf von Woche/Liste malt die Seitenfarbe — hier steht die Karte.
  assert.match(css, /\.ec-list\s+\.ec-header[\s\S]{0,200}background-color:\s*var\(--surface\)/,
    'das graue Band über der Woche/Liste kommt aus dem Bibliotheks-Kopf')
})

test('NACHTRAG 5: Elemente, die es nicht mehr gibt, haben keine Regeln mehr', () => {
  const css = lies('kronos.css')
  const quelle = lies('components/kronos/KronosCalendar.vue')
  const code = quelle.replace(/\/\*[\s\S]*?\*\//g, '')
  assert.doesNotMatch(code, /ec-event-time/, 'die Uhrzeit steckt im Chip-Text, nicht in einem eigenen Element')
  assert.doesNotMatch(css, /^\.ec-event-time\s*\{/m, '`.ec-event-time` ist verwaist (Element gibt es nicht)')
  assert.doesNotMatch(css, /\n\s*\.ec-event-time\s*\{/, '`.ec-event-time` ist verwaist')
  // Und der überholte Satz „Das Handy behält die bisherige Form“ ist korrigiert.
  assert.doesNotMatch(css, /beh[äa]lt die bisherige Form/)
  const kommentare = (quelle.match(/\/\/.*$/gm) || []).join('\n')
  assert.doesNotMatch(kommentare, /beh[äa]lt die bisherige Form/,
    'der Kommentar behauptete einen Handy-Sonderweg, den es nicht mehr gibt')
})

test('NACHTRAG 6: „≥ 4,5:1“ ist belegbar — die schwache Mischung trägt überall AA', () => {
  // Der Widerspruch im Messbericht („≥ 4,44:1“ vs. „0 unter 4,5“) kam aus zwei
  // verschiedenen Rechnungen. Hier wird über das ganze Farbspektrum geprüft,
  // dass der Zweig OHNE kräftigere Fläche (22 %) wirklich ≥ 4,5:1 trägt —
  // dann ist eine Aussage „alle Werte ≥ 4,5:1“ keine Rundung, sondern wahr.
  let minimum = { n: Infinity }
  for (let r = 0; r <= 255; r += 15) {
    for (let g = 0; g <= 255; g += 15) {
      for (let b = 0; b <= 255; b += 15) {
        const farbe = '#' + [r, g, b].map((x) => x.toString(16).padStart(2, '0')).join('')
        for (const theme of ['hell', 'dunkel']) {
          const ergebnis = chip.chipFarben(farbe, { theme })
          // Nur der Fall „Standardfläche“ (22 %) — sonst wird 55 % gemischt.
          if (ergebnis.flaeche) continue
          const n = kontrast(gerenderteFlaeche(farbe, theme), MARKE[theme])
          if (n < minimum.n) minimum = { n, farbe, theme }
        }
      }
    }
  }
  assert.ok(minimum.n >= 4.5,
    `schwächster Fall ${minimum.theme}/${minimum.farbe}: ${minimum.n.toFixed(2)} < 4,5`)
  // Die Meldung im Bericht darf deshalb keine „4,44“ mehr nennen: auf zwei
  // Nachkommastellen gerundet ist jeder Wert ≥ 4,50.
  assert.ok(Number(minimum.n.toFixed(2)) >= 4.5)
})
