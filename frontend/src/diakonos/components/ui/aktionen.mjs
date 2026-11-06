/**
 * UX2e — Reine Logik des Aktionsmenüs „⋯“ (Entwurf B1).
 *
 * Das Menü hängt an JEDEM Listeneintrag (Prinzip N6: Objekt-Aktionen ans
 * Objekt; K4: Gefährliches nie neben häufigen Aktionen). Diese Datei hält
 * den Teil, den man ohne Browser prüfen kann — die Tastaturführung —, damit
 * die Node-Tests dasselbe Verhalten messen, das die Komponente ausführt:
 *
 *   Taste            Wirkung
 *   ---------------- ------------------------------------------------
 *   Kontextmenü-Taste / Shift+F10   Menü an der Zeile öffnen       (nur Locher)
 *   ↓ / ↑ / Pos1 / Ende            Einträge durchwandern (zyklisch)
 *   Zeichen a…z                    Sprung zum nächsten Eintrag mit
 *                                  diesem Anfangsbuchstaben
 *   ↵ / Leertaste                  Eintrag ausführen
 *   Esc                            schließen, Fokus zurück
 *   Tab                            schließen (Fokus verlässt das Menü)
 *
 * Zahlen und Grenzen: 5–8 Einträge (Prinzip RICHTWERTE „Kontextmenü 5–8“),
 * die gefährliche Gruppe steht immer ganz unten und wird nie durchwandert,
 * bevor die häufigen dran waren (K4).
 */

/** Höchstzahl der Einträge (Prinzip RICHTWERTE). */
export const MAX_EINTRAEGE = 8

/** Kleinstzahl der Einträge, ab der ein „⋯“-Menü sinnvoll ist. */
export const MIN_EINTRAEGE = 1

/**
 * Ist die Taste die Kontextmenü-Taste? (Menü-Taste oder Umschalt+F10 —
 * dieselbe Kombination, die Browser und Windows-Programme benutzen.)
 */
export function istKontextmenueTaste(ereignis) {
  if (!ereignis) return false
  const taste = ereignis.key
  return taste === 'ContextMenu' || (ereignis.shiftKey === true && taste === 'F10')
}

/**
 * Nächster/übernächster Eintrag, zyklisch. `richtung` ist +1 (↓) oder −1 (↑).
 * Ohne Einträge bleibt es bei 0 (−1 ist dann kein gültiger Index).
 */
export function naechsterIndex(index, anzahl, richtung) {
  if (!anzahl || anzahl < 1) return -1
  const start = Number.isInteger(index) && index >= 0 && index < anzahl ? index : 0
  return (start + richtung + anzahl) % anzahl
}

/**
 * Sprung per Anfangsbuchstabe (wie in Listen üblich). Gesucht wird ab dem
 * Eintrag NACH dem aktuellen (mehrmaliges Tippen desselben Buchstabens
 * wandert weiter). Kein Treffer → der Index bleibt, wo er ist.
 *
 * @param {Array<{label: string}>} eintraege
 * @param {number} index aktueller Index
 * @param {string} zeichen ein Buchstabe
 */
export function springeZuBuchstabe(eintraege, index, zeichen) {
  const liste = Array.isArray(eintraege) ? eintraege : []
  const buchstabe = String(zeichen || '').toLocaleLowerCase('de')
  if (!liste.length || buchstabe.length !== 1 || !/\p{L}/u.test(buchstabe)) return index
  const anzahl = liste.length
  const start = Number.isInteger(index) && index >= 0 ? index : -1
  for (let schritt = 1; schritt <= anzahl; schritt += 1) {
    const kandidat = (start + schritt + anzahl) % anzahl
    const label = String(liste[kandidat]?.label || '').toLocaleLowerCase('de')
    if (label.startsWith(buchstabe)) return kandidat
  }
  return index
}

/**
 * Index der ersten gefährlichen Gruppe (Einträge mit `gefahr: true`).
 * Alles davor ist „häufig“, alles ab hier ist „abgesetzt“. −1 = keine
 * gefährliche Aktion.
 */
export function ersteGefahr(eintraege) {
  const liste = Array.isArray(eintraege) ? eintraege : []
  return liste.findIndex(e => e && e.gefahr === true)
}

/**
 * Einträge normalisieren: höchstens MAX_EINTRAEGE, leere/flüchtige
 * Beschriftungen fallen weg, die gefährlichen wandern ans Ende (B1: „Das
 * Gefährliche steht allein, in Rot, am Ende“). Die Reihenfolge der übrigen
 * bleibt unangetastet (K3: Häufiges oben — das entscheidet die Seite).
 */
export function eintraegeNormalisieren(eintraege) {
  const liste = (Array.isArray(eintraege) ? eintraege : [])
    .filter(e => e && typeof e.label === 'string' && e.label.trim())
  const haeufig = liste.filter(e => e.gefahr !== true)
  const gefahr = liste.filter(e => e.gefahr === true)
  return [...haeufig, ...gefahr].slice(0, MAX_EINTRAEGE)
}

/**
 * Tastatur-Ereignis im geöffneten Menü behandeln. Liefert die Folge als
 * Objekt — die Komponente führt sie aus (kein DOM-Zugriff hier, damit der
 * Test ohne Browser läuft):
 *
 *   { aktion: 'schliessen' }            Fokus zurück zum Auslöser
 *   { aktion: 'waehlen', index }        Eintrag ausführen
 *   { aktion: 'fokus', index }          Fokus auf einen anderen Eintrag
 *   null                                Taste nicht verwendet
 */
export function tasteImMenue(ereignis, { index = -1, anzahl = 0 } = {}) {
  if (!ereignis) return null
  const taste = ereignis.key
  const eintraegeDa = anzahl > 0
  if (!eintraegeDa) {
    return (taste === 'Escape' || istKontextmenueTaste(ereignis)) ? { aktion: 'schliessen' } : null
  }
  switch (taste) {
    case 'Escape':
      return { aktion: 'schliessen' }
    case 'Tab':
      // K5/S5: Der Fokus verlässt das Menü — es schließt, statt ihn zu fangen.
      return { aktion: 'schliessen' }
    case 'ArrowDown':
      return { aktion: 'fokus', index: naechsterIndex(index, anzahl, 1) }
    case 'ArrowUp':
      return { aktion: 'fokus', index: naechsterIndex(index, anzahl, -1) }
    case 'Home':
      return { aktion: 'fokus', index: 0 }
    case 'End':
      return { aktion: 'fokus', index: anzahl - 1 }
    case 'Enter':
      // Ein Eintrag ohne Aktion (z. B. „Bearbeiten“ eines gesperrten Objekts
      // wird gar nicht erst angeboten) — ohne Auswahl öffnet ↵ nichts.
      return index >= 0 ? { aktion: 'waehlen', index } : null
    case ' ':
      return index >= 0 ? { aktion: 'waehlen', index } : null
    default:
      return null
  }
}

/**
 * Prüft ein Eintrags-Set gegen die Entwurfsregeln (B1, Prinzip N6/K4).
 * Liefert eine Liste der Verstöße (leer = in Ordnung). Wird von den
 * Seiten-Tests benutzt: keine Seite darf z. B. zwei gefährliche Aktionen
 * oder mehr als acht Einträge anbieten.
 */
export function eintraegePruefen(eintraege) {
  const verstoesse = []
  const liste = Array.isArray(eintraege) ? eintraege : []
  if (liste.length > MAX_EINTRAEGE) {
    verstoesse.push(`zu viele Einträge (${liste.length} > ${MAX_EINTRAEGE})`)
  }
  for (const e of liste) {
    if (!e || typeof e.label !== 'string' || !e.label.trim()) {
      verstoesse.push('Eintrag ohne Beschriftung')
    }
  }
  // Gefährliches MUSS zusammen am Ende stehen — sonst steht es neben
  // häufigen Aktionen (K4).
  const gefahren = liste.filter(e => e && e.gefahr === true)
  const letzteHaeufig = liste.map(e => e && e.gefahr === true).lastIndexOf(false)
  const ersteGefahrIndex = liste.findIndex(e => e && e.gefahr === true)
  if (gefahren.length && ersteGefahrIndex !== -1 && ersteGefahrIndex < letzteHaeufig) {
    verstoesse.push('Gefährliches steht nicht am Ende (K4)')
  }
  return verstoesse
}

export default {
  MAX_EINTRAEGE, MIN_EINTRAEGE, istKontextmenueTaste, naechsterIndex,
  springeZuBuchstabe, ersteGefahr, eintraegeNormalisieren, tasteImMenue,
  eintraegePruefen,
}
