/**
 * UX2e5 — Termin-Daten für das „⋯"-Menü der Terminliste.
 *
 * Die Bibliothek @event-calendar/build zeichnet ihre Zeilen selbst und gibt
 * dem Einbau (`eventDidMount`) nur das Zeilen-Element — keine Rückreferenz auf
 * den Datensatz. Für das Menü („Bearbeiten", „Löschen") wird der Datensatz
 * deshalb an der Zeile mitgeführt: `eventContent` schreibt ihn als JSON in
 * `data-termin-daten` am Inhaltsknoten (kein Kennungs-Raten, keine zweite
 * Quelle). Ausgelesen wird er hier — auch dann, wenn die Bibliothek die Zeile
 * (z. B. nach einem Neuladen) neu gebaut hat.
 */

export const DATEN_ATTRIBUT = 'data-termin-daten'

/** Liest den Datensatz aus einer Bibliotheks-Zeile; `null`, wenn keiner dran ist. */
export function liesTerminDaten(zeile) {
  if (!zeile) return null
  // Von unten nach oben: der INNERSTE Träger gilt (bei mehreren — Altbestand
  // aus der Zeit vor UX2e5 — ist das der zuletzt geschriebene).
  const kandidaten = [...Array.from(zeile.querySelectorAll?.(`[${DATEN_ATTRIBUT}]`) || []), zeile]
  for (const knoten of kandidaten) {
    const roh = knoten?.getAttribute?.(DATEN_ATTRIBUT)
    if (!roh) continue
    try {
      const daten = JSON.parse(roh)
      if (daten && typeof daten === 'object') return daten
    } catch {
      // Kaputte Nutzlast gilt wie keine — die Kennung bleibt der Rückfall.
    }
  }
  return null
}

/** Der Datensatz in der Form, die die Seite (Kalender.vue) erwartet. */
export function erstelleTerminDaten(zeile) {
  const daten = liesTerminDaten(zeile)
  if (!daten) {
    // Rückfall: die Kennung der Zeile, damit das Menü nie ohne Termin dasteht.
    const kennung = zeile?.getAttribute?.('data-event-id') || ''
    return kennung ? { id: kennung, title: '', extendedProps: {} } : null
  }
  return {
    id: daten.id || '',
    title: daten.title || '',
    start: daten.start || null,
    end: daten.end || null,
    allDay: !!daten.allDay,
    backgroundColor: daten.backgroundColor || '',
    extendedProps: daten.extendedProps && typeof daten.extendedProps === 'object'
      ? daten.extendedProps
      : {},
  }
}

export default { DATEN_ATTRIBUT, liesTerminDaten, erstelleTerminDaten }
