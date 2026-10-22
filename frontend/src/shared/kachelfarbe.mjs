/**
 * P3-4b (Restpunkt 1) / P3-4c (W3) — lesbare Schrift auf farbigen Terminkacheln
 * (WCAG AA, 4,5:1).
 *
 * `--event-ink` (#12183a) galt fuer JEDE Terminkachel. Auf den dunklen
 * Kategoriefarben war das richtig, auf den mittelhellen (blau #2563eb 3,34:1,
 * pink #db2777 3,75:1, grau #78716c 3,60:1) verfehlte es AA (4,5:1). Umgekehrt
 * war weisse Schrift auf den hellen Kacheln (1,59–2,42:1) noch schlechter.
 *
 * Deshalb wird die Schriftfarbe je Kachel nach dem Kontrast gewaehlt:
 *
 *   1. Die Marken-Schrift (`#12183a`) auf heller Flaeche bzw. Weiß auf dunkler
 *      Flaeche — das ist die Optik, die das Theme ueberall verwendet.
 *   2. Erreicht keine der beiden 4,5:1 (P3-4c/W3: Kalenderfarben sind FREI
 *      waehlbar, das Farbraster hat Faelle mit nur 4,15:1 — z. B. #2d78f0 und
 *      #ee2266), wird auf Schwarz bzw. Weiß ausgewichen. Einer der beiden
 *      Werte erreicht gegen JEDE Farbe mindestens 4,5:1 (bei mittlerer
 *      Helligkeit genau der Uebergang; geprueft ueber das ganze Raster).
 *
 * Ohne Hex-Farbe (CSS-Variable, `oklch(...)`, leer) bleibt es beim Theme-Wert
 * `--event-ink` — dann entscheidet das Theme (Hell/Dunkel, Druck), nicht diese
 * Funktion (P3-4c/W3: vorher wurde stattdessen die Konstante `#12183a` fest
 * inline gesetzt, wodurch `--event-ink` im Dunkelmodus NICHT griff).
 */

/** Dunkle Schrift auf hellen Kacheln (Standardfarbe des dunklen Textes). */
export const KACHEL_INK_DUNKEL = '#12183a'
/** Helle Schrift auf dunklen Kacheln. */
export const KACHEL_INK_HELL = '#ffffff'
/** Notfall-Werte, wenn die Marken-Schrift AA nicht erreicht. */
export const KACHEL_INK_SCHWARZ = '#000000'
export const KACHEL_INK_WEISS = '#ffffff'

export const AA_KONTRAST = 4.5

/** `#RGB`/`#RRGGBB` → [r,g,b] in 0..255, sonst null. */
export function hexZuRgb(hex) {
  if (typeof hex !== 'string') return null
  const s = hex.trim()
  const m = s.match(/^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/)
  if (!m) return null
  const t = m[1].length === 3 ? m[1].split('').map(c => c + c).join('') : m[1]
  return [0, 2, 4].map(i => parseInt(t.slice(i, i + 2), 16))
}

/** Relative Luminanz nach WCAG 2.x. */
export function luminanz(hex) {
  const rgb = hexZuRgb(hex)
  if (!rgb) return null
  const [r, g, b] = rgb.map(v => {
    const c = v / 255
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

/** Kontrastverhaeltnis zweier Hex-Farben (1..21), null bei ungueltiger Eingabe. */
export function kontrast(a, b) {
  const la = luminanz(a)
  const lb = luminanz(b)
  if (la === null || lb === null) return null
  const [hell, dunkel] = la > lb ? [la, lb] : [lb, la]
  return (hell + 0.05) / (dunkel + 0.05)
}

/**
 * Schriftfarbe fuer eine Kachelfarbe.
 *
 * @param {string} farbe  Kachelfarbe (Hex) oder'' / CSS-Funktion
 * @param {string} rueckfall  Wert ohne verwertbare Farbe — der Theme-Wert
 *        (`var(--event-ink)`), damit Hell/Dunkel und Druck greifen.
 * @returns {string} Hex-Schriftfarbe oder `rueckfall`
 */
export function kachelSchrift(farbe, rueckfall = 'var(--event-ink)') {
  const dunkel = kontrast(farbe, KACHEL_INK_DUNKEL)
  const hell = kontrast(farbe, KACHEL_INK_HELL)
  // Keine verwertbare Hex-Angabe → das Theme entscheidet.
  if (dunkel === null || hell === null) return rueckfall
  // 1. Marken-Schrift, wenn sie AA erreicht (bessere der beiden).
  const marke = hell >= dunkel ? KACHEL_INK_HELL : KACHEL_INK_DUNKEL
  if (Math.max(hell, dunkel) >= AA_KONTRAST) return marke
  // 2. Mittlere Helligkeit: Marken-Schrift reicht nicht → Notfall-Wert mit dem
  //    besseren Kontrast (einer der beiden erreicht immer 4,5:1).
  return kontrast(farbe, KACHEL_INK_SCHWARZ) >= kontrast(farbe, KACHEL_INK_WEISS)
    ? KACHEL_INK_SCHWARZ
    : KACHEL_INK_WEISS
}
