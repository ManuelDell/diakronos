/**
 * UX3h3 — „Speichern nur, wenn geändert“: die EINE Regel dafür.
 *
 * Warum eine eigene Datei: „hat sich etwas geändert?“ ist FACHLOGIK (Vergleich
 * des geladenen Stands mit dem, was in den Feldern steht). Ein Test kann sie
 * hier AUSFÜHREN; in der Komponente wäre sie nur als Quelltext lesbar. Dieselbe
 * Aufteilung wie bei `gestaltung.mjs`, `website.mjs` oder `felderAusAdresse`.
 *
 * Vorbild war `gestaltung.mjs` (`geaenderteFelder`): die Gestaltung prüfte
 * ihre Maße schon gegen den gespeicherten Stand. Diese Datei macht dasselbe
 * für Formulare beliebiger Form — sie kennt KEINE Feldnamen. Wer ein Formular
 * umbaut, ändert den Aufruf, nicht die Regel.
 *
 * Zwei Regeln, die hier zusammenlaufen:
 *   1. Ein Feld, dessen Wert nicht mit `===` gleich ist, gilt als geändert.
 *      Deshalb vergleicht `wertGleich` Zahlen und ihre Textform als gleich
 *      (`30` ≡ `"30"`, `15.0` ≡ `15`): ein `type="number"`-Feld liefert Text,
 *      der Server aber Zahlen — ohne diese Normalisierung stünde „Speichern“
 *      nach dem Laden sofort offen, obwohl niemand etwas getippt hat (im
 *      Prüfstand gemessen: `aufbewahrungTage` 30 gegen „30“).
 *   2. Zeilen mit einem leeren Schlüssel (`gruppe: ''`) sind der leere
 *      Eingabe-Platz „Zuordnung ergänzen“ und zählen NICHT als Änderung; erst
 *      ein eingetippter Wert macht daraus eine Änderung. Sonst wäre der Knopf
 *      nach einem versehentlichen Klick auf „ergänzen“ für immer offen.
 *
 * Bewusst NICHT hier: Dialoge beim Verlassen der Seite. Die Karte UX3h3 sagt
 * ausdrücklich „kein Dialog“ — ungespeicherte Änderung heißt hier nur: der
 * Knopf bleibt offen.
 */

/** Zahl aus Text lesen — `null`, wenn es keine (endliche) Zahl ist. */
function alsZahl(wert) {
  if (typeof wert === 'number') return Number.isFinite(wert) ? wert : null
  if (typeof wert !== 'string') return null
  const text = wert.trim()
  // Leerer Text ist NICHT die Zahl 0 (Number('') === 0 wäre falsch).
  if (!text) return null
  const zahl = Number(text)
  return Number.isFinite(zahl) ? zahl : null
}

/**
 * Sind zwei Feldwerte derselbe Stand?
 *
 * Gleich sind: gleiche Zeichenkette, gleiche Zahl, Zahl und ihre Textform
 * (`3` ≡ `"3"`, `3.0` ≡ `"3.0"`). Nicht gleich sind Objekte und Listen, wenn
 * sie sich in einem Wert unterscheiden; deren SCHLÜSSEL-Reihenfolge zählt
 * nicht (ein neu gebautes `{ a, b }` ist derselbe Stand wie `{ b, a }`).
 *
 * @param {unknown} links
 * @param {unknown} rechts
 * @returns {boolean}
 */
export function wertGleich(links, rechts) {
  if (links === rechts) return true
  // NaN gilt als gleich (sonst meldete ein kaputtes Feld dauerhaft „geändert“).
  if (typeof links === 'number' && typeof rechts === 'number') {
    return Number.isNaN(links) && Number.isNaN(rechts)
  }
  // Nur Zahl gegen Text angleichen — zwei Texte bleiben Texte ('01067' ≠ '1067',
  // '+49711' ≠ '49711'), sonst bliebe „Speichern“ bei echter Änderung zu.
  if ((typeof links === 'number') !== (typeof rechts === 'number')) {
    const zahlLinks = alsZahl(links)
    const zahlRechts = alsZahl(rechts)
    if (zahlLinks !== null && zahlRechts !== null) return zahlLinks === zahlRechts
  }
  if (Array.isArray(links) || Array.isArray(rechts)) {
    if (!Array.isArray(links) || !Array.isArray(rechts)) return false
    if (links.length !== rechts.length) return false
    return links.every((wert, i) => wertGleich(wert, rechts[i]))
  }
  if (links && rechts && typeof links === 'object' && typeof rechts === 'object') {
    const schluesselLinks = Object.keys(links)
    const schluesselRechts = Object.keys(rechts)
    if (schluesselLinks.length !== schluesselRechts.length) return false
    return schluesselLinks.every(kl =>
      Object.prototype.hasOwnProperty.call(rechts, kl)
      && wertGleich(links[kl], rechts[kl]))
  }
  return false
}

/** Trägt diese Zeile schon einen Wert? (leerer Schlüssel = leerer Platz) */
function zeileGefuellt(zeile) {
  if (!zeile || typeof zeile !== 'object') return false
  if (!Object.prototype.hasOwnProperty.call(zeile, 'gruppe')) return true
  return String(zeile.gruppe ?? '').trim() !== ''
}

/**
 * Welche Felder weichen vom geladenen Stand ab?
 *
 * @param {Record<string, unknown>} stand     der geladene (gespeicherte) Stand
 * @param {Record<string, unknown>} eingaben  das, was jetzt in den Feldern steht
 * @returns {string[]} die Namen der geänderten Felder (leer = nichts geändert)
 */
export function geaenderteFelder(stand, eingaben = {}) {
  const alt = stand && typeof stand === 'object' ? stand : {}
  const neu = eingaben && typeof eingaben === 'object' ? eingaben : {}
  const namen = new Set([...Object.keys(alt), ...Object.keys(neu)])
  const geaendert = []
  for (const name of namen) {
    if (wertGleich(neu[name], alt[name])) continue
    if (Array.isArray(alt[name]) || Array.isArray(neu[name])) {
      // Listen (z. B. die Zeilen der Authentik-Zuordnungen): ein leerer
      // Platz ist noch keine Änderung — eingetippte Werte schon.
      const alteListe = Array.isArray(alt[name]) ? alt[name] : []
      const neueListe = Array.isArray(neu[name]) ? neu[name] : []
      if (!listeGeaendert(alteListe, neueListe)) continue
    }
    geaendert.push(name)
  }
  return geaendert
}

/** Trägt diese Zeile einen Inhalt? (leere Zeichenketten zählen nicht) */
function zeileHatInhalt(zeile) {
  if (!zeile || typeof zeile !== 'object') return false
  return Object.values(zeile).some((wert) => String(wert ?? '').trim() !== '')
}

/** Die Zeilen, die einen Inhalt tragen. Ein leerer Platz am Ende zählt nicht. */
export function zeilenMitInhalt(liste) {
  return (Array.isArray(liste) ? liste : []).filter((zeile, i, alle) => (
    zeileHatInhalt(zeile) || i < alle.length - 1
  ))
}

/**
 * Haben sich zwei Zeilen-Listen geändert? Ein leerer Platz am ENDE (oder eine
 * ganz leere Zeile) ist der Stellvertreter „neue Zeile anfangen“ und zählt
 * nicht — auch nicht, wenn jemand ihn wieder entfernt hat.
 */
function listeGeaendert(alteListe, neueListe) {
  const links = zeilenMitInhalt(alteListe)
  const rechts = zeilenMitInhalt(neueListe)
  if (links.length !== rechts.length) return true
  return rechts.some((zeile, i) => !wertGleich(zeile, links[i]))
}

/**
 * Hat sich gegenüber dem geladenen Stand etwas geändert?
 * (Der Ausdruck, den „Speichern“ als `disabled` benutzt.)
 *
 * @param {Record<string, unknown>} stand
 * @param {Record<string, unknown>} eingaben
 * @returns {boolean}
 */
export function hatSichGeaendert(stand, eingaben) {
  return geaenderteFelder(stand, eingaben).length > 0
}

/**
 * Stand für den Vergleich normalisieren: fehlende Felder werden zu `''` —
 * ein `undefined` im Formular ist derselbe Stand wie ein leerer Text.
 */
export function standFuerVergleich(stand) {
  if (!stand || typeof stand !== 'object') return {}
  const ergebnis = {}
  for (const [name, wert] of Object.entries(stand)) {
    ergebnis[name] = wert === undefined || wert === null ? '' : wert
  }
  return ergebnis
}
