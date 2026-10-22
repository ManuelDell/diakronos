/**
 * DSGVO-2b — „Meine Daten löschen lassen“ im eigenen Profil.
 *
 * Zwei reine Regeln, damit die Oberfläche nichts selbst erfindet:
 *
 *  * `antragsStand` — welche Fläche der Profilbereich zeigt. Der Server
 *    liefert den Stand (`datenschutz.mein_loeschantrag`), die Oberfläche
 *    übersetzt ihn nur in einen von fünf Fällen. Ein unbekannter oder
 *    fehlender Status gilt als „nie beantragt“: dann ist der Antragsknopf
 *    sichtbar, und der Server entscheidet (er kennt den echten Stand).
 *  * `bestaetigungWort` — das Wort, das die Person zur Bestätigung tippt.
 *    Es steht im Dialog (Kontrollkästchen UND Wort) und ist hier EINMAL
 *    festgelegt (`BESTAETIGUNG_WORT`), damit Oberfläche und Wächter nicht
 *    auseinanderlaufen.
 *
 * Nichts hiervon entscheidet über Rechte: wer löschen darf, sagt allein der
 * Server (`loeschung_bestaetigen` prüft den Administrator).
 */

/** Wort, das die Person vor dem Antrag abtippen muss. */
export const BESTAETIGUNG_WORT = 'LÖSCHEN'

/** Die fünf Stände, die die Oberfläche kennt (Werte aus `_antrag_stand`). */
export const ANTRAG_STAND = {
  OHNE: 'ohne',
  OFFEN: 'offen',
  ZURUECKGEZOGEN: 'zurueckgezogen',
  ABGELEHNT: 'abgelehnt',
  AUSGEFUEHRT: 'ausgefuehrt',
}

/**
 * Welche Fläche gehört zum Stand des Antrags?
 *
 * ``ohne``        → nichts gestellt: Erklärung + Knopf „Löschung beantragen“.
 * ``offen``       → „Antrag gestellt am … — wartet auf Bearbeitung“ + Zurückziehen.
 * ``zurueckgezogen`` → Hinweis auf den Rückzug (mit Datum) + neuer Antrag möglich.
 * ``abgelehnt``   → Begründung der Verwaltung + „Erneut beantragen“.
 * ``ausgefuehrt`` → Nachweis („ausgeführt am …“), kein Knopf mehr.
 */
export function antragsStand(stand) {
  const status = String(stand?.status || '').trim().toLowerCase()
  if (status === 'offen') return ANTRAG_STAND.OFFEN
  if (status === 'zurueckgezogen') return ANTRAG_STAND.ZURUECKGEZOGEN
  if (status === 'abgelehnt') return ANTRAG_STAND.ABGELEHNT
  if (status === 'ausgefuehrt') return ANTRAG_STAND.AUSGEFUEHRT
  return ANTRAG_STAND.OHNE
}

/** Darf die Person (erneut) beantragen? Nur solange nichts offen oder erledigt ist. */
export function darfBeantragen(stand) {
  const lage = antragsStand(stand)
  return lage === ANTRAG_STAND.OHNE
    || lage === ANTRAG_STAND.ZURUECKGEZOGEN
    || lage === ANTRAG_STAND.ABGELEHNT
}

/** Darf die Person den offenen Antrag zurückziehen? Genau dann, wenn er offen ist. */
export function darfZurueckziehen(stand) {
  return antragsStand(stand) === ANTRAG_STAND.OFFEN
}

/**
 * Bestätigung prüfen: Kästchen gesetzt UND Wort exakt getippt.
 * Groß-/Kleinschreibung und Leerzeichen am Rand zählen nicht mit — die
 * Person soll nicht an „löschen“ statt „LÖSCHEN“ scheitern.
 */
export function bestaetigungVollstaendig({ kaestchen = false, wort = '', laeuft = false } = {}) {
  if (laeuft) return false
  if (kaestchen !== true) return false
  return String(wort || '').trim().toUpperCase() === BESTAETIGUNG_WORT
}

/**
 * ISO-Zeitstempel des Servers (``2026-10-22T01:11:31`` oder mit ``Z``) als
 * deutsches Datum ``22.10.2026``. Alles andere bleibt leer — kein „Invalid
 * Date“ auf einer Seite, die eine endgültige Entscheidung begleitet.
 */
export function datumDeutsch(wert) {
  const text = String(wert || '').trim()
  const treffer = text.match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (!treffer) return ''
  return `${treffer[3]}.${treffer[2]}.${treffer[1]}`
}

/**
 * Die zwei Sätze, die VOR dem Antrag stehen (Pflicht der Karte: endgültig,
 * nicht rückgängig, Name und Mail verschwinden, in alten Plänen steht
 * „Gelöschte Person“, vorher kommt eine Mail).
 */
export const ERKLAERUNG = [
  'Deine Löschung ist endgültig und lässt sich nicht rückgängig machen: Name und E-Mail-Adresse werden vollständig entfernt, dein Zugang wird beendet.',
  'In alten Plänen stehst du danach als „Gelöschte Person“. Bevor gelöscht wird, bekommst du eine E-Mail; ein Administrator prüft und bestätigt deinen Antrag vorher.',
]
