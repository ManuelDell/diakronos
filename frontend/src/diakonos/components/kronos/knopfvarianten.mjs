/**
 * UX1e — Alt-Knopf nach Baustein, Kalender-/Moderationsbereich.
 *
 * WARUM DIE REGEL UMGEZOGEN IST (UX1f)
 * Die Zuordnung „alte Klasse -> neue Variante“ steht seit UX1f EINMAL zentral
 * in `diakonos/knopfvarianten.mjs`: Personen, Gruppen, Registrierung und Gast
 * brauchen dieselbe Regel. Diese Datei bleibt der gewohnte Einstiegspunkt des
 * Kalenderbereichs und reicht nur weiter — zwei Fassungen der Regel dürfen
 * nicht auseinanderlaufen.
 *
 * Die Zuordnung selbst setzt `frontend/tests/ux1e-knopf-system.test.mjs`
 * wirklich aus (kein Regex-Raten).
 */
export {
  VARIANTEN,
  GROESSEN,
  BESCHRIFTUNGEN,
  klassenListe,
  knopfAusKlassen,
  beschriftung,
} from '../../knopfvarianten.mjs'
