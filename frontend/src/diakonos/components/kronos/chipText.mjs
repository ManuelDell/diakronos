/**
 * UX3i — Termin-Chips im Monatsraster (Entwurf A4).
 *
 * Warum eine eigene Datei: `KronosCalendar.vue` baut den Chip als HTML-STRING
 * für die Kalender-Bibliothek; Textregeln, Kontrast und die „+n weitere“-Zahl
 * sind dort nicht ausführbar. Hier stehen sie als reine Funktionen — der Node-
 * Test (`tests/ux3i-kalender-a4.test.mjs`) führt sie wirklich aus (Prinzip:
 * Verhalten statt Quelltext-Regex).
 *
 * Beschriftung (A4, verbindlich): EINE Variante durchgängig —
 *   mit Uhrzeit:   „19:00 Titel“
 *   ohne Uhrzeit:  „Titel“  (ganztägig, mehrtägig, ohne Uhrzeit)
 */

import { wandZeit } from '../../../shared/zeit.mjs'

/** Höchstzahl gleichzeitig sichtbarer Chips je Tag, wenn die Bibliothek kürzt. */
export const CHIPS_JE_TAG = 3

const ZWEI = (n) => String(n).padStart(2, '0')

/* Die Marken-Rohwerte, deren HELLIGKEIT die Kontrastrechnung braucht
   (dieselben Werte wie --dk-warm-0 / --dk-navy-900 in `tokens.css`).
   Wächter: `tools/css-ssot-bestand.txt` führt beide Zeilen als Ausnahme
   (Grund: Rechnung, keine Gestaltung). */
const WEISS = '#ffffff'
const NAVY_900 = '#00051f'
/* Kartenfläche als RGB — Weiß bzw. --dk-ink-2; nur zur Mischungsrechnung. */
const RGB_KARTE_HELL = [255, 255, 255]
const RGB_KARTE_DUNKEL = [26, 31, 46]

/** Wandelt Server-/Bibliothekswerte in ein Datum; `null`, wenn unbrauchbar. */
function alsDatum(wert) {
  if (!wert) return null
  if (wert instanceof Date) return Number.isNaN(wert.getTime()) ? null : wert
  return wandZeit(String(wert).trim())
}

/** `HH:MM` einer Zeitangabe. */
export function uhrzeit(wert) {
  const d = alsDatum(wert)
  if (!d) return ''
  return `${ZWEI(d.getHours())}:${ZWEI(d.getMinutes())}`
}

/**
 * Text eines Chips: „Titel 19:00“ — die Uhrzeit steht HINTEN und nur, wenn
 * der Termin an diesem Tag eine echte Uhrzeit hat.
 *
 * UX3i3/Befund 4 (Manuel, 08.11.): Vorher stand die Uhrzeit VORN
 * („10:00 Gottes…“). Im Monatsraster ist die Spalte so schmal, dass die
 * Ellipse genau den TITEL abschnitt — der Termin war nicht mehr zu erkennen.
 * A4 zeigt „Chor 19:00“: erst der Titel, dann die Uhrzeit. Durchgängig EINE
 * Variante (Monat, Woche, Liste).
 *
 * Keine Uhrzeit bei:
 *   * ganztägigen Terminen (`allDay`),
 *   * mehrtägigen Terminen (dann steht der Titel; der Tag ergibt sich aus der
 *     Zelle, die Uhrzeit stünde am falschen Tag),
 *   * Terminen, deren Beginn 00:00 ist und die am selben Tag enden
 *     (Bestandsdaten tragen ganztägig ohne `allDay`-Flag so — dieselbe Regel
 *     wie `dayEventLabel.mjs`).
 *
 * @param {{ title?: string, start?: any, end?: any, allDay?: boolean }} termin
 * @param {{ tag?: string }} [optionen] — `tag` (`YYYY-MM-DD`) der Zelle:
 *   nur dann steht die Uhrzeit, wenn der Termin an diesem Tag BEGINNT oder
 *   andauert (ein am Vortag begonnener Termin zeigt in der Follezelle keinen
 *   Startzeitpunkt, der nicht stimmt).
 */
export function chipText(termin, optionen = {}) {
  const t = termin || {}
  const titel = String(t.title || '').trim()
  const start = alsDatum(t.start)
  if (!start) return titel
  if (t.allDay) return titel

  const ende = alsDatum(t.end)
  const mehrtag = ende ? start.toDateString() !== ende.toDateString() : false
  if (mehrtag) return titel

  // Bestandsdaten: 00:00–00:00 ohne allDay-Flag = ganztägig.
  if (start.getHours() === 0 && start.getMinutes() === 0 && ende
      && ende.getHours() === 0 && ende.getMinutes() === 0) {
    return titel
  }

  // Zelle eines ANDEREN Tages als der Beginn: kein Startzeitpunkt.
  if (optionen.tag) {
    const zelle = String(optionen.tag).slice(0, 10)
    const eigenerTag = `${start.getFullYear()}-${ZWEI(start.getMonth() + 1)}-${ZWEI(start.getDate())}`
    if (zelle && zelle !== eigenerTag) return titel
  }

  const zeit = uhrzeit(start)
  if (!zeit) return titel
  return titel ? `${titel} ${zeit}` : zeit
}

/**
 * Vollständiger Titel für `title`/`aria-label` des Chips — nie abgeschnitten,
 * dazu Datum und Zeit (der Chip selbst kürzt nur optisch).
 */
export function chipTitel(termin) {
  const t = termin || {}
  const titel = String(t.title || '').trim() || 'Termin'
  const start = alsDatum(t.start)
  if (!start) return titel
  const ende = alsDatum(t.end)
  const datum = start.toLocaleDateString('de-DE', { weekday: 'short', day: 'numeric', month: 'long' })
  if (t.allDay || !ende) return t.allDay ? `${titel} · ${datum} · ganztägig` : `${titel} · ${datum}`
  const gleicherTag = start.toDateString() === ende.toDateString()
  if (gleicherTag) return `${titel} · ${datum} · ${uhrzeit(start)}–${uhrzeit(ende)}`
  const endeDatum = ende.toLocaleDateString('de-DE', { day: 'numeric', month: 'long' })
  return `${titel} · ${datum} bis ${endeDatum}`
}

/**
 * UX3i4 — Text eines Termin-BLOCKS im Zeitraster (Woche/Tag).
 *
 * Im Zeitraster ist die Höhe die DAUER; der Block steht über so vielen Zeilen,
 * wie die Dauer hergibt. Die Beschriftung braucht dort zwei Stücke, weil in
 * einer schmalen Tagesspalte (~130 px) „Titel 10:00“ sonst schon nach wenigen
 * Zeichen abgeschnitten wäre — und der TITEL ist die wichtigere Information
 * (UX3i3/Befund 4: die Uhrzeit darf den Titel nicht verdrängen).
 *
 *   Titel  → ohne Uhrzeit, volle Breite der Zeile 1
 *   Zeit   → „10:00–11:30“ in Zeile 2, nur wenn der Termin an DIESEM Tag eine
 *            echte Uhrzeit hat (dieselben Regeln wie `chipText`: ganztägig,
 *            mehrtägig und 00:00–00:00 tragen keine Uhrzeit; ein Folgetag
 *            eines mehrtägigen Termins zeigt keinen falschen Startpunkt).
 *
 * @param {{ title?: string, start?: any, end?: any, allDay?: boolean }} termin
 * @param {{ tag?: string }} [optionen] — `tag` (`YYYY-MM-DD`) der Spalte
 * @returns {{ titel: string, zeit: string }}
 */
export function zeitBlockText(termin, optionen = {}) {
  const t = termin || {}
  const titel = String(t.title || '').trim()
  const start = alsDatum(t.start)
  if (!start) return { titel, zeit: '' }
  if (t.allDay) return { titel, zeit: '' }

  const ende = alsDatum(t.end)
  const mehrtag = ende ? start.toDateString() !== ende.toDateString() : false
  if (mehrtag) return { titel, zeit: '' }
  if (start.getHours() === 0 && start.getMinutes() === 0 && ende
      && ende.getHours() === 0 && ende.getMinutes() === 0) {
    return { titel, zeit: '' }
  }
  if (optionen.tag) {
    const zelle = String(optionen.tag).slice(0, 10)
    const eigenerTag = `${start.getFullYear()}-${ZWEI(start.getMonth() + 1)}-${ZWEI(start.getDate())}`
    if (zelle && zelle !== eigenerTag) return { titel, zeit: '' }
  }

  const beginn = uhrzeit(start)
  if (!beginn) return { titel, zeit: '' }
  const schluss = ende ? uhrzeit(ende) : ''
  // Gleiche Uhrzeit = Dauer 0 bzw. Ende fehlt: dann nur der Start.
  const zeit = schluss && schluss !== beginn ? `${beginn}–${schluss}` : beginn
  return { titel: titel || zeit, zeit: titel ? zeit : '' }
}

/** Kein Code-Ausführungsrisiko in `style="…"` — nur echte Farbwerte. */
function sichereCssFarbe(wert) {
  const s = String(wert || '').trim()
  return /^(#[0-9a-fA-F]{3,8}|rgba?\([0-9.,%\s]+\)|hsla?\([0-9.,%\s]+\))$/.test(s) ? s : ''
}

/** Hilfsfarben je Theme: gegen Weiß bzw. gegen die dunkle Fläche. */
const KONTRÄSTE = {
  hell: { dunkel: 'var(--dk-navy-900)', hell: 'var(--dk-warm-0)' },
  dunkel: { dunkel: 'var(--dk-warm-0)', hell: 'var(--dk-navy-900)' },
}

/**
 * Marken-Schrift als `light-dark(hell, dunkel)`: erster Wert gilt im HELLEN,
 * zweiter im DUNKLEN Theme. Der Browser löst beim Zeichnen neu auf, damit ein
 * Theme-Wechsel die schon gezeichneten Chips mitnimmt (Nachtrag Punkt 1):
 * hell liegt die dunkle Marke auf der getönten Fläche, dunkel die helle.
 */
const lightDark = () => 'light-dark(var(--dk-navy-900), var(--dk-warm-0))'

function relLuminanz([r, g, b]) {
  const f = (c) => {
    const s = c / 255
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
  }
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)
}

/** `#rrggbb` (oder `#rgb`) -> [r, g, b]; `null` für alles andere. */
function alsRgb(wert) {
  const s = String(wert || '').trim()
  let m = /^#([0-9a-fA-F]{6})$/.exec(s)
  if (m) {
    const n = parseInt(m[1], 16)
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255]
  }
  m = /^#([0-9a-fA-F]{3})$/.exec(s)
  if (m) {
    return m[1].split('').map((c) => parseInt(c + c, 16))
  }
  return null
}

/**
 * Farbwerte des Servers tragen oft eine Deckkraft (`#16a34a99` — die
 * Bibliothek legt sie über die Kartenfläche). Für die RECHNUNG muss daraus die
 * tatsächlich sichtbare Fläche werden: Farbe über der Karte. Ohne diesen
 * Schritt rechnete der Kontrast gegen den vollen Farbton und lag damit zu
 * optimistisch (Review 07.11.). Alpha 255 gilt als deckend.
 */
function mitDeckkraft(wert, grund) {
  const s = String(wert || '').trim()
  const m = /^#([0-9a-fA-F]{6})([0-9a-fA-F]{2})$/.exec(s)
  if (!m) return alsRgb(s)
  const rgb = alsRgb('#' + m[1])
  if (!rgb) return null
  const alpha = parseInt(m[2], 16) / 255
  return rgb.map((c, i) => Math.round(c * alpha + grund[i] * (1 - alpha)))
}

function kontrastverhaeltnis(a, b) {
  const la = relLuminanz(a)
  const lb = relLuminanz(b)
  const hell = Math.max(la, lb)
  const dunkel = Math.min(la, lb)
  return (hell + 0.05) / (dunkel + 0.05)
}

/**
 * Fläche und Schriftfarbe eines Chips im Monatsraster.
 *
 * Regel (Prinzip Ä4: Kontrast ≥ 4,5:1, Farbe nie alleiniger Träger):
 *   1. Die tatsächlich sichtbare Chipfläche wird GERECHNET: Kalenderfarbe
 *      (mit ihrer Deckkraft, z. B. `#16a34a99`) über der Kartenfläche.
 *   2. Davon wird der Ton für den Chip abgeleitet (22 % der sichtbaren Farbe
 *      über der Karte — die Mischung, die die Bibliothek als Chipfläche nutzt).
 *   3. Die Schriftfarbe kommt aus den Theme-Marken, die auf DIESEM Ton den
 *      höheren Kontrast erreicht. Reicht keine von beiden, wird die Fläche
 *      kräftiger eingefärbt (55 %) — die Schrift bleibt dieselbe
 *      `light-dark()`-Marke, weil BEIDE Marken (navy-900 hell, warm-0 dunkel)
 *      auf der kräftigeren Mischung mehr Kontrast haben als auf der
 *      schwächeren (Farbe über der Karte bleibt zwischen den Marken).
 *
 * Review 07.11.: `--chip-flaeche` wurde in `kronos.css` gelesen, aber nie
 * gesetzt — der Chip fiel auf `--primary` zurück und zeigte nicht die
 * Kalenderfarbe. Beide Variablen werden jetzt gesetzt; der Kontrast wird gegen
 * die ECHTE Fläche gerechnet, nicht gegen den vollen Farbton.
 *
 * @returns {{ flaeche: string, schrift: string }}
 *   `flaeche` ist ein `color-mix()`-Ausdruck (kein Rohwert) oder '' — dann
 *   gilt die Standardfläche des Themes.
 *
 * Nacharbeit 07.11. Punkt 1 (Nachtrag): `schrift` ist bei den beiden
 * Marken-Fällen KEIN fester Token mehr, sondern `light-dark(...)`. Der Grund:
 * `chipStil` wird im Kalender EINMAL beim Zeichnen gerechnet; ein Wechsel des
 * Themes danach (Einstellung, Systemwechsel) ließ die alte Schriftfarbe auf
 * der neuen Fläche stehen — 1,04:1 im Dunkelmodus. `light-dark()` löst beim
 * Zeichnen neu auf (setzt `color-scheme` an den Theme-Wurzeln voraus, siehe
 * `tokens.css`) und ist gegen die je Theme gerechnete Mischung geprüft: hell
 * die dunkle Marke, dunkel die helle.
 */
export function chipFarben(kalenderfarbe, { theme = 'hell' } = {}) {
  const dunkelTheme = theme === 'dunkel'
  const marken = KONTRÄSTE[dunkelTheme ? 'dunkel' : 'hell']
  // Die Marken-Schriftfarben sind die Rohwerte der Skala aus `tokens.css`
  // (--dk-warm-0, --dk-navy-900). Die Rechnung braucht ihre HELLIGKEIT —
  // keine Gestaltung; ausgegeben wird weiterhin ein Token-Ausdruck.
  const schriftDunkel = alsRgb(dunkelTheme ? WEISS : NAVY_900)
  const schriftHell = alsRgb(dunkelTheme ? NAVY_900 : WEISS)
  // Grundfläche, auf der gemischt wird (die Karte): Weiß bzw. --dk-ink-2.
  const grund = dunkelTheme ? RGB_KARTE_DUNKEL : RGB_KARTE_HELL
  const sichtbar = mitDeckkraft(kalenderfarbe, grund)
  if (!sichtbar) {
    // Keine echte Kalenderfarbe (Fremdfarben aus fremden Daten, z. B.
    // Google-Kalender, oder ein fehlender Wert): der Chip nimmt die
    // Standardfläche des Themes und die sichere Schrift (dieselbe Regel wie
    // `kachelSchrift` für die Tageskacheln).
    return { flaeche: '', schrift: marken.dunkel }
  }
  const ton = (anteil) => sichtbar.map((c, i) => Math.round(c * anteil + grund[i] * (1 - anteil)))
  const schwach = ton(0.22)
  const kDunkelSchwach = kontrastverhaeltnis(schwach, schriftDunkel)
  const kHellSchwach = kontrastverhaeltnis(schwach, schriftHell)
  // UX3i3 (Befund 5 / Nacharbeit 6): Hier stand TOTER CODE — `markeStark`
  // und `kWeissStark` wurden gerechnet, aber nie benutzt, und beide Zweige
  // gaben dieselbe `light-dark()`-Marke zurück. Jetzt trägt die Rechnung die
  // Entscheidung: reicht der Kontrast auf der 22-%-Fläche NICHT (`>= 4.5`
  // heißt „mindestens 4,5:1“), wird die Fläche auf die kräftigere 55-%-Mischung
  // gehoben (dann steht sie zusätzlich als `color-mix()` im Stil). Reicht
  // schon die schwache Fläche, bleibt es bei `''` (= Standardfläche des
  // Themes, gemischt in `kronos.css`). Die Schrift ist in BEIDEN Fällen
  // `light-dark()` — sie wird beim Zeichnen je Theme aufgelöst.
  //
  // Nacharbeit 6 (Widerspruch im Messbericht): Der Kontrast wird nicht mehr
  // nur hier gegen die MARKEN gerechnet. `tools/ux3i3-abnahme.mjs` misst die
  // tatsächlich gerenderten Pixel (Fläche UND Schrift im Screenshot) — dort
  // steht die Zahl, die im Bericht auftaucht. Eine hier gerechnete Zahl ist
  // eine Vorhersage, kein Beleg.
  const reicht = kDunkelSchwach >= 4.5 || kHellSchwach >= 4.5
  if (reicht) {
    return { flaeche: '', schrift: lightDark() }
  }
  const stark = ton(0.55)
  if (kontrastverhaeltnis(stark, schriftDunkel) < 4.5 &&
      kontrastverhaeltnis(stark, schriftHell) < 4.5) {
    // Auch die kräftigere Fläche trägt keine der beiden Marken (kann bei
    // Fremdfarben vorkommen): dann die Standardfläche des Themes mit der
    // sicheren Marke — nie eine Schrift, die den Kontrast nicht trägt.
    return { flaeche: '', schrift: marken.dunkel }
  }
  return {
    flaeche: `color-mix(in srgb, ${kalenderfarbe} 55%, var(--surface))`,
    schrift: lightDark(),
  }
}

/**
 * Der Inline-Stil eines Chips: Fläche (Kalenderfarbe) UND Schriftfarbe.
 *
 * Review 07.11. Punkt 4: gesetzt wurde nur `--chip-ink`; `--chip-flaeche`
 * blieb leer, und `kronos.css` mischte deshalb `--primary`. Hier werden beide
 * gesetzt — die Fläche als `color-mix()` der Kalenderfarbe über der
 * Kartenfläche (dieselbe Mischung, gegen die `chipFarben` gerechnet hat).
 */
export function chipStil(kalenderfarbe, optionen = {}) {
  const farben = chipFarben(kalenderfarbe, optionen)
  const sichtbar = sichereCssFarbe(kalenderfarbe)
  const flaeche = farben.flaeche || (sichtbar
    ? `color-mix(in srgb, ${sichtbar} 22%, var(--surface))`
    : '')
  return `--chip-ink:${farben.schrift};${flaeche ? `--chip-flaeche:${flaeche};` : ''}`
}

/** „+2 weitere“ — Zahl und Einzahl/Mehrzahl in einem. */
export function weitereText(anzahl) {
  const n = Number(anzahl)
  if (!Number.isFinite(n) || n <= 0) return ''
  return `+${n} weitere`
}

/**
 * Beschriftung des Kartenkopfs „KW a–b“.
 *
 * Der Kalender zeichnet sechs Wochen; die Nummern kommen aus den Rändern des
 * gezeigten Bereichs (`datesSet.start` incl. / `datesSet.end` excl.).
 * Rückgabe `''`, wenn sich die Woche nicht bestimmen lässt — dann steht dort
 * nichts (nie eine erfundene Zahl).
 *
 * @param {Date|string} start — erster gezeigter Tag
 * @param {Date|string} end — Tag NACH dem letzten gezeigten Tag
 */
export function kwBereich(start, end) {
  const s = alsDatum(start)
  const e = alsDatum(end)
  if (!s || !e) return ''
  const letzter = new Date(e.getTime() - 24 * 3600 * 1000)
  const a = isoWoche(s)
  const b = isoWoche(letzter)
  if (!a || !b) return ''
  if (a.nummer === b.nummer && a.jahr === b.jahr) return `KW ${a.nummer}`
  return `KW ${a.nummer}–${b.nummer}`
}

/** ISO-8601-Kalenderwoche (Montag = Wochenbeginn). */
export function isoWoche(datum) {
  const d = alsDatum(datum)
  if (!d) return null
  // Auf UTC-Mitternacht des LOKALEN Kalendertags normalisieren, damit
  // Sommer-/Winterzeit keine Rolle spielt.
  const t = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()))
  const tag = t.getUTCDay() || 7          // Sonntag = 7
  t.setUTCDate(t.getUTCDate() + 4 - tag)  // Donnerstag derselben Woche
  const jahr = t.getUTCFullYear()
  const ersterDonnerstag = new Date(Date.UTC(jahr, 0, 4))
  const offset = (ersterDonnerstag.getUTCDay() || 7)
  ersterDonnerstag.setUTCDate(ersterDonnerstag.getUTCDate() + 4 - offset)
  const nummer = 1 + Math.round((t - ersterDonnerstag) / (7 * 24 * 3600 * 1000))
  return { jahr, nummer }
}

/** Deutscher Monatstitel mit Jahr („November 2026“) aus `view.title`. */
export function monatstitel(titel) {
  const s = String(titel || '').trim()
  if (!s) return ''
  // Die Bibliothek liefert je nach Sprache „November 2026“ oder „November2026“.
  const m = s.match(/^(.*?)\s*(\d{4})\s*$/)
  if (!m) return s
  return `${m[1].trim()} ${m[2]}`
}
