import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { kachelSchrift, kontrast, KACHEL_INK_DUNKEL, KACHEL_INK_HELL }
  from '../src/shared/kachelfarbe.mjs'

/**
 * P3-4b — Restpunkte 1 (Kachel-Schrift nach Luminanz) und 9 (Wochenzahl).
 *
 * 1) `--event-ink` (#12183a) galt fuer JEDE Terminkachel. Auf den mittelhellen
 *    Kategoriefarben blau #2563eb (3,34:1), pink #db2777 (3,75:1) und grau
 *    #78716c (3,60:1) verfehlte das AA; weisse Schrift war auf den hellen
 *    Kacheln mit 1,59–2,42:1 noch schlechter. Die Schriftfarbe wird deshalb je
 *    Kachel aus der Helligkeit gewaehlt.
 */
const root = new URL('../', import.meta.url)
const lies = p => readFileSync(new URL(p, root), 'utf8')

const KATEGORIEFARBEN = [
  '#2563eb', // blau
  '#db2777', // pink
  '#78716c', // grau
  '#f59e0b', // amber
  '#16a34a', // gruen
  '#1c2850', // Marke navy-500
  '#ffffff',
  '#12183a',
]

test('Restpunkt 1: jede Kategorie-Kachelfarbe erreicht mit der gewaehlten Schrift AA', () => {
  for (const farbe of KATEGORIEFARBEN) {
    const schrift = kachelSchrift(farbe)
    const verhaeltnis = kontrast(farbe, schrift)
    assert.ok(verhaeltnis >= 4.5,
      `${farbe}: ${schrift} nur ${verhaeltnis.toFixed(2)}:1 (AA verlangt 4,5:1)`)
  }
})

test('Restpunkt 1: die vorher feste Schriftfarbe verfehlte AA auf blau, pink und grau', () => {
  for (const farbe of ['#2563eb', '#db2777', '#78716c']) {
    assert.ok(kontrast(farbe, KACHEL_INK_DUNKEL) < 4.5,
      `${farbe}: der alte Festwert #12183a bestand AA schon — Test waere sinnlos`)
  }
})

test('Restpunkt 1: dunkle Kacheln bekommen helle, helle Kacheln dunkle Schrift', () => {
  assert.equal(kachelSchrift('#12183a'), KACHEL_INK_HELL)
  assert.equal(kachelSchrift('#1c2850'), KACHEL_INK_HELL)
  assert.equal(kachelSchrift('#f59e0b'), KACHEL_INK_DUNKEL)
  assert.equal(kachelSchrift('#ffffff'), KACHEL_INK_DUNKEL)
})

test('Restpunkt 1: ohne verwertbare Farbe bleibt der Theme-Wert stehen', () => {
  // P3-4c/W3: Die Marken-Konstante `#12183a` wurde vorher fest inline gesetzt.
  // Damit war `--event-ink` (Dunkelmodus, Druck) wirkungslos — es muss der
  // Theme-Wert sein, nicht die Konstante.
  assert.equal(kachelSchrift(''), 'var(--event-ink)')
  assert.equal(kachelSchrift('var(--primary)'), 'var(--event-ink)')
  assert.equal(kachelSchrift('url(zzz)'), 'var(--event-ink)')
  assert.equal(kachelSchrift('oklch(0.7 0.1 200)'), 'var(--event-ink)',
    'auch moderne Farbfunktionen sind keine Hex-Angabe')
  assert.notEqual(kachelSchrift(''), KACHEL_INK_DUNKEL,
    'ohne Farbe darf NICHT die Konstante kommen (sonst greift --event-ink nicht)')
})

/**
 * P3-4c / W3: Kalenderfarben sind FREI waehlbar. Mit nur zwei festen
 * Kandidaten (#12183a, #fff) liegt das Minimum im Farbraster bei 4,15:1
 * (z. B. #2d78f0, #ee2266) — AA (4,5:1) war damit NICHT garantiert.
 */
test('W3: JEDE frei gewaehlte Kachelfarbe erreicht AA (400 Zufallsfarben)', () => {
  // Reproduzierbarer Zufall (fester Startwert) — kein flatternder Test.
  let saat = 424242
  const zufall = () => {
    saat = (saat * 1103515245 + 12345) & 0x7fffffff
    return saat / 0x7fffffff
  }
  const kandidaten = [
    '#2d78f0', // der Reviewer-Fall: 4,15:1 mit #12183a
    '#ee2266', // Raster-Minimum mit #ffffff
    '#7c7c7c', // Grauton, 4,17:1
  ]
  for (let i = 0; i < 400; i += 1) {
    const kanal = () => Math.floor(zufall() * 256).toString(16).padStart(2, '0')
    kandidaten.push('#' + kanal() + kanal() + kanal())
  }
  for (const farbe of kandidaten) {
    const schrift = kachelSchrift(farbe)
    const verhaeltnis = kontrast(farbe, schrift)
    assert.ok(verhaeltnis !== null, `${farbe}: keine Schriftfarbe`)
    assert.ok(verhaeltnis >= 4.5,
      `${farbe}: ${schrift} nur ${verhaeltnis.toFixed(2)}:1 (AA verlangt 4,5:1)`)
  }
})

test('W3: das ganze Farbraster erreicht AA, nicht nur die Palette', () => {
  // Stichprobe ueber den Farbwuerfel (6 Stufen je Kanal = 4096 Farben).
  for (let r = 0; r < 256; r += 51) {
    for (let g = 0; g < 256; g += 51) {
      for (let b = 0; b < 256; b += 51) {
        const hex = '#' + [r, g, b].map(v => v.toString(16).padStart(2, '0')).join('')
        const schrift = kachelSchrift(hex)
        const verhaeltnis = kontrast(hex, schrift)
        assert.ok(verhaeltnis >= 4.5,
          `${hex}: ${schrift} nur ${verhaeltnis.toFixed(2)}:1`)
      }
    }
  }
})

test('W3: die Marken-Schrift bleibt, wo sie AA erreicht', () => {
  // Optik: nur im Grenzfall (mittlere Helligkeit) wird auf Schwarz/Weiß
  // ausgewichen — sonst bleibt es bei #12183a bzw. Weiß.
  assert.equal(kachelSchrift('#ffffff'), KACHEL_INK_DUNKEL)
  assert.equal(kachelSchrift('#f59e0b'), KACHEL_INK_DUNKEL)
  assert.equal(kachelSchrift('#12183a'), KACHEL_INK_HELL)
  assert.equal(kachelSchrift('#1c2850'), KACHEL_INK_HELL)
})

test('Restpunkt 1: der Kalender waehlt die Schrift aus der Kachelfarbe', () => {
  const kalender = lies('src/diakonos/components/kronos/KronosCalendar.vue')
  assert.match(kalender, /kachelSchrift\(sichereFarbe\(event\.backgroundColor\)\)/,
    'die Schriftfarbe wird nicht aus der Kachelfarbe gewaehlt')
  assert.match(kalender, /class="ec-event-body" style="color:/,
    'die gewaehlte Schriftfarbe landet nicht am Kachelelement')
})

test('Restpunkt 9: die Wochenzahl wird unter 640 px per CSS ausgeblendet', () => {
  const css = lies('src/diakonos/kronos.css')
  // Der Selektor `.ec .ec-day-head span` setzt weiter oben ebenfalls
  // `display: inline-block !important` (gleiche Spezifitaet 0-2-1, spaeter im
  // Blatt) und gewinnt gegen `.ec .ec-week-number`. Deshalb muss die
  // Ausblend-Regel hoeher spezifiziert sein, sonst bleibt „W40“ am Handy stehen.
  assert.match(css,
    /@media \(max-width: 640px\)\s*\{[^}]*\.ec \.ec-day-head > \.ec-week-number\s*\{\s*display:\s*none/,
    'unter 640 px ist die Wochenzahl nicht (spezifisch genug) ausgeblendet und ueberlappt die Tageszahl')
  assert.ok(!/@media \(max-width: 640px\)\s*\{[^}]*\.ec \.ec-week-number\s*\{\s*display:\s*none/.test(css),
    'die Ausblend-Regel steht wieder in der schwachen Spezifitaet, die von .ec-day-head span ueberstimmt wird')
  assert.match(css, /\.ec \.ec-week-number\s*\{[^}]*overflow:\s*hidden/,
    'die Wochenzahl kann in die Tageszahl laufen')
})

test('Restpunkt 9: die Nummer wird nicht mehr beim Aufbau per matchMedia abgeschaltet', () => {
  const kalender = lies('src/diakonos/components/kronos/KronosCalendar.vue')
  assert.match(kalender, /weekNumbers:\s*true/,
    'weekNumbers haengt wieder an einer einmaligen Breitenmessung')
  assert.ok(!/istSchmal\(\)/.test(kalender), 'die alte Breitenmessung ist noch im Code')
})
