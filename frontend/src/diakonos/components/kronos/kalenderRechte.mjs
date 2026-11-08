/**
 * UX3i (Nacharbeit Review 07.11.) — Rechte und Lesemodus des Kalenders.
 *
 * Warum eine eigene Datei: Die Kopfzeile darf „Kalender verwalten“ und
 * „Kalender importieren“ NUR dann anbieten, wenn der Server es auch erlaubt,
 * und „abgelehnte Termine“ nur dann, wenn der Server welche liefert. Vorher
 * entschied die Seite am Boot-Wert `is_admin` — die Rolle
 * „Kalenderadministrator“ verlor damit ihre Einträge, und Mitgliederadmins
 * sahen Einträge, die der Server ablehnt. Der Lesemodus wiederum entscheidet,
 * ob offene Vorschläge wie feste Termine aussehen.
 *
 * Alles hier sind reine Funktionen: `tests/ux3i-*` führt sie je Rolle aus,
 * ohne Browser und ohne Server.
 */

/**
 * Darf diese Person Kalender verwalten/importieren?
 *
 * Dieselbe Prüfung wie bisher in `KronosSidebar.vue` (dort als Bedingung des
 * Menüs): Kontoname `Administrator` ODER eine der Rollen `Administrator` /
 * `Kalenderadministrator` aus `get_current_user_context`. Der Server prüft
 * bei Verwalten und Import erneut — hier wird nichts erweitert, sondern
 * dieselbe Regel an EINER Stelle benutzt.
 *
 * @param {{ user?: string, roles?: string[] }|null} kontext
 * @returns {boolean}
 */
export function istKalenderAdmin(kontext) {
  if (!kontext || typeof kontext !== 'object') return false
  const rollen = Array.isArray(kontext.roles) ? kontext.roles.map(String) : []
  return String(kontext.user || '') === 'Administrator'
    || rollen.includes('Administrator')
    || rollen.includes('Kalenderadministrator')
}

/**
 * Lesemodus (`true`) oder Bearbeiten (`false`) als Startzustand.
 *
 * Der Kalender startet im LESEMODUS — wie vor UX3i. Das ist keine
 * Geschmacksfrage: Im Lesemodus liefert der Server ausschließlich
 * `status == "Festgelegt"`, im Bearbeiten-Modus sehen Moderatoren zusätzlich
 * offene Vorschläge. Startete die Seite im Bearbeiten-Modus, sähen
 * Moderatoren Vorschläge als feste Termine — genau der Fehler, den das
 * Review gemeldet hat.
 *
 * @param {string[]|undefined} gespeichert — gemerkter Modus aus einem
 *   früheren Besuch (`'view'` / `'edit'`).
 * @returns {boolean} `true` = Lesemodus
 */
export function startLesemodus(gespeichert) {
  return String(gespeichert || '') !== 'edit'
}

/**
 * Neuer Modus nach dem Schalter „Bearbeiten“.
 *
 * Ohne Schreibrecht auf MINDESTENS einen Kalender gibt es keinen
 * Bearbeiten-Modus (UXK-R10): der Wunsch wird abgelehnt, der Zustand bleibt.
 *
 * @param {boolean} bearbeiten — gewünscht
 * @param {boolean} hatSchreibrecht
 * @returns {boolean} `true` = Lesemodus
 */
export function lesemodusNachSchalter(bearbeiten, hatSchreibrecht) {
  if (bearbeiten && !hatSchreibrecht) return true
  return !bearbeiten
}

/** Was ein Klick auf einen Termin im jeweiligen Modus auslöst. */
export function klickAufTermin(lesemodus) {
  return lesemodus ? 'ansehen' : 'bearbeiten'
}

/** Was ein Klick auf einen Tag im jeweiligen Modus auslöst. */
export function klickAufTag(lesemodus) {
  return lesemodus ? 'tagesliste' : 'anlegen'
}

/**
 * Einträge des „⋯“-Menüs der Kalender-Kopfzeile (Entwurf A4, Punkt 5+6).
 *
 * Reihenfolge nach Häufigkeit (N3): erst die Ansicht (Ressourcenplan), dann
 * das Seltene (Verwalten/Import), dann der Umschalter des Lesemodus, zuletzt
 * „Abgelehnte Termine“ und die Hilfe. „Bearbeiten“ ist ein DEZENTER Schalter
 * hier und KEIN eigener Knopf in der Kopfzeile (Review-Entscheidung: der
 * Lesemodus ist der Standard, und ein gefüllter Umschalter wäre ein zweiter
 * Hauptknopf neben „Termin anlegen“ — Regel UX1h).
 *
 * Symbolnamen sind solche aus `components/ui/symbole.mjs` (DkSymbol zeichnet
 * nur bekannte Namen; ein Tippfehler ergäbe ein leeres Feld).
 *
 * @param {{ istKalenderAdmin?: boolean, hatSchreibrecht?: boolean, lesemodus?: boolean }} lage
 * @returns {Array<{key: string, label: string, icon: string, href?: string, aktion?: string}>}
 */
export function kalenderMenue({
  istKalenderAdmin: admin = false,
  hatSchreibrecht = false,
  lesemodus = true,
} = {}) {
  const eintraege = []
  // „Ressourcenplan“ ist eine Ansicht des Kalenders (dieselbe Seite, anderer
  // Blick) — sie steht hier, damit sie keine zweite Hauptaktion neben
  // „Termin anlegen“ ist (A4: genau ein Primärknopf).
  eintraege.push({ key: 'ressourcenplan', label: 'Ressourcenplan', icon: 'kalender', aktion: 'ressourcenplan' })
  // OP-ADMIN-10: Verwalten und Importieren hängen an derselben Rolle — der
  // Server prüft sie erneut.
  if (admin === true) {
    eintraege.push({ key: 'verwalten', label: 'Kalender verwalten', icon: 'bearbeiten', href: '#/kalender/verwalten' })
    eintraege.push({ key: 'importieren', label: 'Kalender importieren', icon: 'herunterladen', href: '#/kalender/import' })
  }
  // Lesemodus ist der Standard; der Schalter heißt nach der HANDLUNG, die er
  // ermöglicht. Ohne Schreibrecht gibt es nichts zu bearbeiten.
  if (hatSchreibrecht === true) {
    eintraege.push({
      key: 'bearbeiten',
      label: lesemodus ? 'Bearbeiten einschalten' : 'Bearbeiten ausschalten',
      icon: 'stift',
      aktion: 'bearbeitenUmschalten',
    })
  }
  // R-P1-8/FIX-7: die eigenen abgelehnten Termine waren am Desktop nur über
  // die (ausgeblendete) Kalenderliste erreichbar. Sie stehen jetzt hier.
  eintraege.push({ key: 'abgelehnte', label: 'Abgelehnte Termine', icon: 'abbrechen', aktion: 'abgelehnteTermine' })
  eintraege.push({ key: 'hilfe', label: 'Hilfe & Infos', icon: 'notiz', aktion: 'hilfe' })
  return eintraege
}
