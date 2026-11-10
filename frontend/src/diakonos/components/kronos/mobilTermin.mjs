/**
 * A10/A11 — das Termin-Blatt am Handy: Handlungen und Status-Badge.
 *
 * Am Handy gibt es die Terminliste der Kalender-Bibliothek nicht mehr
 * (Entwurf A10: der kompakte Monat zeigt nur Punkte, die Tagesliste öffnet
 * das Blatt A11). Deshalb muss das BLATT alles anbieten, was die Liste
 * angeboten hat (Karte A10, Punkt 6 und 7):
 *
 *   Freigeben   (primär)  — Moderator, nur bei einem zu prüfenden Termin
 *   Bearbeiten  (sekundär)— wer schreiben darf
 *   Absagen     (⋯, getrennt)   — Moderator
 *   Löschen     (⋯, gefährlich, immer zuletzt) — wer schreiben darf
 *
 * Die Regeln stehen hier als reine Funktionen (`tests/a10-*.test.mjs`),
 * die Komponente zeichnet nur. Nichts wird hier entschieden, was der Server
 * nicht ohnehin prüft: „Freigeben“ und „Absagen“ gehen an die vorhandene
 * Moderation (`resolve_conflict`), „Löschen“ an den Papierkorb
 * (`papierkorbMeldung`/`wiederherstellen`) — dieselben Wege wie bisher.
 */

/** Status, die „zu prüfen“ bedeuten (Server: `Vorschlag`, `Konflikt`). */
export const PRUEF_STATUS = Object.freeze(['Vorschlag', 'Konflikt'])

/** Ist der Termin zu prüfen? `true` nur bei den beiden Moderations-Status. */
export function istPruefStatus(termin) {
  const status = String(termin?.status || termin?.extendedProps?.status || '').trim()
  return PRUEF_STATUS.includes(status)
}

const STATUS_TEXT = {
  Vorschlag: 'Zu prüfen',
  Konflikt: 'Zu prüfen · Überschneidung',
  Festgelegt: 'Bestätigt',
  Abgelehnt: 'Abgelehnt',
}

const STATUS_VARIANTE = {
  Vorschlag: 'warn',
  Konflikt: 'warn',
  Festgelegt: 'ok',
  Abgelehnt: 'err',
}

/**
 * Badge über den Zeilen des Blattes (Entwurf A11: „Zu prüfen · eingetragen
 * von J. Rehberg“). Ohne Status gibt es kein Badge (`null`) — nie ein
 * erfundenes „Bestätigt“.
 *
 * @returns {{ text: string, variant: string }|null}
 */
export function statusBadgeFuer(termin) {
  if (!termin || typeof termin !== 'object') return null
  const status = String(termin.status || termin.extendedProps?.status || '').trim()
  if (!status) return null
  const wer = String(termin.antragsteller || termin.extendedProps?.antragsteller || '').trim()
  const basis = STATUS_TEXT[status] || status
  // „eingetragen von …“ nur bei den Prüf-Status — das ist die Herkunft, die
  // für die Entscheidung zählt (dieselbe Angabe wie im Desktop-Panel).
  const text = (PRUEF_STATUS.includes(status) && wer) ? `${basis} · eingetragen von ${wer}` : basis
  return { text, variant: STATUS_VARIANTE[status] || 'neutral' }
}

/**
 * Einträge des „⋯“-Menüs am Termin-Blatt (A10: „Absagen/Löschen im ⋯“).
 *
 * Reihenfolge nach Häufigkeit (N3), Gefährliches zuletzt (Entwurf B1 —
 * `DkAktionen` sortiert und trennt selbst). Höchstens acht Einträge.
 */
export function terminBlattAktionen({
  darfPruefen = false,
  darfBearbeiten = false,
  primaerFreigeben = false,
} = {}) {
  const eintraege = []
  // „Bearbeiten“ steht am Blatt als eigener Knopf, sobald es der Primärknopf
  // nicht ist (A11: „Freigeben“ primär). Im ⋯ erscheint es dann NICHT doppelt.
  if (darfPruefen === true && primaerFreigeben === true) {
    eintraege.push({ key: 'absagen', label: 'Absagen', icon: 'abbrechen', getrennt: true })
  }
  if (darfBearbeiten === true && !(darfPruefen === true && primaerFreigeben === true)) {
    eintraege.push({ key: 'bearbeiten', label: 'Bearbeiten', icon: 'bearbeiten' })
  }
  if (darfBearbeiten === true) {
    eintraege.push({ key: 'loeschen', label: 'Löschen', icon: 'loeschen', gefahr: true })
  }
  return eintraege
}

export default { PRUEF_STATUS, istPruefStatus, statusBadgeFuer, terminBlattAktionen }
