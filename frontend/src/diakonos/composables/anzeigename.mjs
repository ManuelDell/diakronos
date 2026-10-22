/**
 * anzeigename.mjs — reine Rechenregel für den Anzeigenamen (OP-HANDY-25).
 *
 * Ohne Vue und ohne DOM, damit sie ohne Browser prüfbar ist. `useSession`
 * verbindet sie mit den reaktiven Quellen (`mitglied`, `user`).
 *
 * Warum überhaupt: `user.fullname` ist der Frappe-Anzeigename
 * (`user.full_name`). Im Test-/Altbestand ist der oft nur das E-Mail-Präfix
 * („mitglied"), während der Personenname in der Mitgliederzeile steht. Gezeigt
 * werden soll der gepflegte Vorname — nicht die Technik.
 *
 * DSGVO-2d: Ist die Person GELÖSCHT, ist der Anzeigename „Gelöschte Person“ —
 * nie die neutrale Kennung `geloescht-<hex>` (sie stand hier als Begrüssung,
 * weil sie der erste „Namensteil“ von `fullname` war) und nie ein leerer Text.
 */
import { GELOESCHT_ANZEIGE, istGeloescht } from './geloeschte-person.mjs'

/**
 * Erster Namensteil eines Anzeigenamens; fällt auf den Teil vor dem `@` zurück
 * (nie die vollständige E-Mail-Adresse).
 */
export function ersterName(voll) {
  const ohne = String(voll || '').split('@')[0].trim()
  return ohne.split(/\s+/).filter(Boolean)[0] || ''
}

/**
 * Anzeigename: Vorrang `mitglied.vorname`, sonst erster Teil von `fullname`.
 */
export function anzeigename(mitglied, fullname) {
  if (istGeloescht(mitglied) || istGeloescht(fullname)) return GELOESCHT_ANZEIGE
  const vorname = typeof mitglied?.vorname === 'string' ? mitglied.vorname.trim() : ''
  if (vorname) return vorname
  return ersterName(fullname)
}

/**
 * Initialen (1–2 Buchstaben) für den Avatar: aus Vor- und Nachnamen des
 * Mitglieds, sonst aus dem Anzeigenamen.
 */
export function initialen(mitglied, name) {
  // Eine gelöschte Person hat keinen Namen, aus dem Initialen entstehen
  // dürften — der Avatar zeigt ein neutrales Zeichen (kein „GP“).
  if (istGeloescht(mitglied) || istGeloescht(name)) return 'U'
  const teile = [mitglied?.vorname, mitglied?.nachname].filter(Boolean).join(' ').trim()
  const quelle = (teile || String(name || '')).trim()
  const woerter = quelle.split(/\s+/).filter(Boolean)
  const aus = woerter.length > 1
    ? woerter[0][0] + woerter[woerter.length - 1][0]
    : (woerter[0] || '').slice(0, 2)
  return aus.toUpperCase().slice(0, 2) || 'U'
}

export default { anzeigename, ersterName, initialen }
