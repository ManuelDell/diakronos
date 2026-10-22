/**
 * geloeschte-person.mjs — EINE Regel fuer die Anzeige einer geloeschten Person
 * (DSGVO-2d).
 *
 * WARUM EINE EIGENE DATEI
 * -----------------------
 * Der Server liefert den Anzeigenamen bereits fertig (`personen_anzeige`
 * im Backend: "Gelöschte Person"). Es gibt aber Stellen, an denen die
 * Oberfläche den Namen selbst baut oder eine Kennung zeigt, wenn sie keinen
 * Namen hat — Adressbuchzeile, `ersterName()` fuer Gruss und Avatar, ein
 * Wert ohne Eintrag in der Anzeigetabelle. Genau dort stand bisher
 * `geloescht-3f9a1c` oder eine leere Klammer.
 *
 * Deshalb hier dasselbe Prädikat wie im Server, in reiner Form (ohne Vue,
 * ohne DOM): Die Seite prueft damit, ob sie einen Link ins Profil setzen darf
 * und welchen Text sie zeigt. Die Kuerzung selbst baut das Frontend NICHT
 * nach — sie kommt vom Server.
 *
 * Regeln des Servers (identisch):
 *  * Massgeblich ist `status === 'geloescht'`, zweiter Zeuge ist das Praefix
 *    der neutralen Kennung `geloescht-`.
 *  * Anzeigetext ist IMMER "Gelöschte Person" — kein Klarname, keine Kennung,
 *    keine leeren Klammern, kein Rest-Initial ("Gelöschte P.").
 *  * Auswahllisten bieten geloeschte Personen nicht an (der Server filtert sie
 *    bereits in `gruppen_auswahl.AUSGESCHIEDEN` und im Personenpool).
 */

/** Der Anzeigetext einer geloeschten Person — wortgleich mit dem Server. */
export const GELOESCHT_ANZEIGE = 'Gelöschte Person'

/** Praefix der neutralen Kennung (`dsgvo_anonymisierung.GELOESCHT_PRAEFIX`). */
export const GELOESCHT_PRAEFIX = 'geloescht-'

/**
 * Ist diese Person geloescht? `person` ist eine Kennung oder ein Datensatz
 * mit `status`/`name`/`mitglied`.
 */
export function istGeloescht(person) {
  if (!person) return false
  const istAnzeigetext = (wert) =>
    String(wert ?? '').trim().toLowerCase() === GELOESCHT_ANZEIGE.toLowerCase()
  if (typeof person === 'string') {
    // Der Anzeigetext selbst zählt mit: Seiten, die nur den fertigen Namen
    // haben (Avatar-Initialen aus `full_name`), müssen ihn erkennen.
    return istAnzeigetext(person)
      || person.trim().toLowerCase().startsWith(GELOESCHT_PRAEFIX)
  }
  const status = String(person.status ?? '').trim().toLowerCase()
  if (status === 'geloescht') return true
  // Kennung und Anzeigename stehen je nach Antwort in `name` oder `mitglied`
  // (Gruppen/Kalender: `mitglied` = Kennung, `name` = Anzeigename). BEIDE
  // prüfen — `name` trägt bei gelöschten Zeilen bereits „Gelöschte Person“.
  return [person.name, person.mitglied, person.kennung].some(
    (k) => istAnzeigetext(k)
      || String(k ?? '').trim().toLowerCase().startsWith(GELOESCHT_PRAEFIX))
}

/**
 * Anzeigename einer Person aus den Feldern, die die Seite hat.
 *
 * Reihenfolge: geloescht -> fester Text; sonst `anzeige`/`name`, sonst aus
 * Vor-/Nachname. NIE die Kennung, wenn sie eine Adresse oder ein
 * `geloescht-`-Schluessel ist — dann bleibt ein neutraler Text.
 */
export function personenName(person, { vorname = '', nachname = '' } = {}) {
  if (istGeloescht(person)) return GELOESCHT_ANZEIGE
  if (typeof person === 'string') return person
  const fertig = String(person?.anzeige ?? person?.full_name ?? person?.name ?? '').trim()
  const teile = [vorname || person?.vorname, nachname || person?.nachname]
    .map((t) => (typeof t === 'string' ? t.trim() : ''))
    .filter(Boolean)
    .join(' ')
  if (teile) return teile
  if (fertig && !fertig.includes('@')) return fertig
  return 'Ehemaliges Mitglied'
}

/**
 * Darf die Seite auf das Profil dieser Person verlinken?
 *
 * Eine geloeschte Person hat keins mehr (die Zeile traegt keine Konten, das
 * Konto ist geloescht) — ein Link fuehrte auf eine Fehlerseite.
 */
export function darfProfilLink(person) {
  if (istGeloescht(person)) return false
  // Die Zeile kann die Kennung in `name` ODER in `mitglied` tragen (Gruppen-
  // und Kalenderantworten nennen `mitglied`, der Anzeigename steht in `name`).
  // Geprüft werden BEIDE — sonst bliebe `#/mitglied/<kennung>` stehen, obwohl
  // `name` schon „Gelöschte Person“ ist.
  const kennungen = typeof person === 'string'
    ? [person]
    : [person?.name, person?.mitglied]
  // Kein Link, sobald EINE der Kennungen die neutrale eines gelöschten
  // Datensatzes ist — und nie für eine leere Kennung.
  const echt = kennungen.map((k) => String(k || '').trim()).filter(Boolean)
  if (!echt.length) return false
  return echt.every((k) => !k.toLowerCase().startsWith(GELOESCHT_PRAEFIX))
}

/** Kuerzel einer geloeschten Person ist leer — es gibt keine Initialen. */
export function personenKuerzel(person) {
  if (istGeloescht(person)) return ''
  return String(person?.kuerzel ?? '').trim()
}

export default { GELOESCHT_ANZEIGE, GELOESCHT_PRAEFIX, istGeloescht, personenName, darfProfilLink, personenKuerzel }
