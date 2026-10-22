/**
 * N3 — QR-Code lokal im Browser (Konzept Abschnitt 5, Entscheidung 8).
 *
 * Der Link eines Registrierungslink wird in der App selbst in einen QR-Code
 * gerechnet; die Adresse geht NICHT an einen fremden Dienst. Die schwere Arbeit
 * macht `qrcode-generator` (MIT, ~4 kB, keine Netzverbindung); dieses Modul
 * kapselt die zwei Fallen, die beim Verwenden der Bibliothek entstehen:
 *
 *  1. `qrcode(typeNumber, errorCorrectionLevel)` — `typeNumber = 0` heisst
 *     „Groesse selbst waehlen“. Ein fester Typ (z. B. 4) bricht bei langen
 *     Adressen ab; `0` waechst mit.
 *  2. Fehlerkorrektur „M“ ist der uebliche Kompromiss fuer Aushaenge
 *     (Gemeindebrief, Plakat): robust genug gegen Fingerabdruecke, ohne den
 *     Code unnoetig zu vergroessern.
 *
 * Reine Rechenfunktionen ohne DOM — dadurch im Node-Test pruefbar
 * (tests/n3-registrierungslinks.test.mjs).
 */

import qrcode from 'qrcode-generator'

/** Fehlerkorrektur wie in guten Aushaengen ueblich (Konzept: „druckbereit“). */
export const FEHLERKORREKTUR = 'M'

/**
 * Module (schwarze Felder) eines QR-Codes als Matrix aus Wahrheitswerten.
 * Zeile = y, Spalte = x; `true` heisst „schwarz“.
 */
export function qrMatrix(text) {
  const inhalt = String(text || '').trim()
  if (!inhalt) return []
  const qr = qrcode(0, FEHLERKORREKTUR)
  qr.addData(inhalt)
  qr.make()
  const groesse = qr.getModuleCount()
  const matrix = []
  for (let y = 0; y < groesse; y++) {
    const zeile = []
    for (let x = 0; x < groesse; x++) zeile.push(qr.isDark(y, x))
    matrix.push(zeile)
  }
  return matrix
}

/**
 * SVG-Pfad des QR-Codes (`M … h … v …`) — dieselbe Form, die die Bibliothek
 * selbst erzeugt. Leer, wenn kein Inhalt.
 */
export function qrSvgPfad(text) {
  const matrix = qrMatrix(text)
  if (!matrix.length) return ''
  let pfad = ''
  for (let y = 0; y < matrix.length; y++) {
    for (let x = 0; x < matrix.length; x++) {
      if (!matrix[y][x]) continue
      let lauf = 1
      while (x + lauf < matrix.length && matrix[y][x + lauf]) lauf++
      pfad += `M${x} ${y}h${lauf}v1h-${lauf}z`
      x += lauf - 1
    }
  }
  return pfad
}

/**
 * Nutzdaten fuer das `<svg>`-Element: viewBox und Pfad.
 * Rand von einem Modul (`-1 … groesse+1`) bleibt der Seite/ViewBox ueberlassen.
 */
export function qrSvg(text) {
  const matrix = qrMatrix(text)
  if (!matrix.length) return { pfad: '', viewBox: '0 0 0 0', groesse: 0 }
  return {
    pfad: qrSvgPfad(text),
    viewBox: `0 0 ${matrix.length} ${matrix.length}`,
    groesse: matrix.length,
  }
}

/** Dateiname fuer den PNG-Download, aus der Bezeichnung des Links. */
export function qrDateiname(bezeichnung) {
  const sauber = String(bezeichnung || '')
    .toLowerCase()
    .replace(/ä/g, 'ae').replace(/ö/g, 'oe').replace(/ü/g, 'ue').replace(/ß/g, 'ss')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
  return `qr-${sauber || 'registrierungslink'}.png`
}
