/**
 * UX3i — Kalender-Auswahl (Entwurf A4, Punkt 5): Zähler, Namen, Umschalten.
 *
 * Das „⋯“-Menü der Kopfzeile steht NICHT mehr hier: welche Einträge es gibt,
 * hängt seit der Nacharbeit (07.11.) an den Rechten aus
 * `get_current_user_context` und am Lesemodus — siehe `kalenderRechte.mjs`
 * (`kalenderMenue`).
 */

/**
 * Anzeigename eines Kalenders (nie ein leerer Eintrag).
 */
export function kalenderName(kalender) {
  const k = kalender || {}
  const name = String(k.title || k.name || '').trim()
  return name || 'Kalender'
}

/** Schlüssel eines Kalenders in der Auswahl (`name` ist die Kennung). */
export function kalenderSchluessel(kalender) {
  return String(kalender?.name || '')
}

/**
 * Anzahl der EINGEBLENDETEN Kalender für den Zähler am Knopf „Kalender“.
 * Gezählt wird nur, was es wirklich gibt — ein alter Eintrag in der
 * gespeicherten Auswahl zählt nicht (er blendet nichts ein).
 */
export function eingeblendeteZahl(alle, ausgewaehlt) {
  const namen = new Set((Array.isArray(alle) ? alle : []).map(kalenderSchluessel))
  const gewaehlt = new Set((Array.isArray(ausgewaehlt) ? ausgewaehlt : []).map(String))
  let n = 0
  for (const name of gewaehlt) if (namen.has(name)) n += 1
  return n
}

/**
 * Neue Auswahl nach dem Umschalten EINES Kästchens.
 * Die übrigen Kalender behalten ihren Zustand; die Reihenfolge folgt der
 * Liste der Kalender (nicht der Klickfolge).
 */
export function auswahlUmschalten(alle, ausgewaehlt, name, an) {
  const liste = (Array.isArray(alle) ? alle : []).map(kalenderSchluessel).filter(Boolean)
  const gewaehlt = new Set((Array.isArray(ausgewaehlt) ? ausgewaehlt : []).map(String))
  const schluessel = String(name || '')
  if (!schluessel) return [...gewaehlt]
  if (an) gewaehlt.add(schluessel)
  else gewaehlt.delete(schluessel)
  const bekannt = liste.filter((n) => gewaehlt.has(n))
  // Unbekannte Einträge (Kalender, die es nicht mehr gibt) fallen weg.
  return bekannt
}
