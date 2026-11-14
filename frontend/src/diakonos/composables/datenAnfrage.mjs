/**
 * datenAnfrage — „Daten anfragen“ (R-9, Manuel 11.11.).
 *
 * Regel: Vor- und Nachnamen sieht jedes Gemeindemitglied. Weitere Daten
 * (E-Mail, Telefon, Adresse, Geburtstag) nur, wenn die PERSON sie unter
 * Profil → Sichtbarkeit freigegeben hat. Hat sie es nicht, bietet die Zeile
 * „Daten anfragen“ an; die Person bekommt eine Meldung und entscheidet selbst.
 *
 * Diese Datei ist die EINE Stelle für die Texte und die Auslegung der
 * Server-Antwort. Sie entscheidet NICHTS über Rechte — was „anfragbar“ ist,
 * sagt der Server je Zeile (`daten_anfragbar`); hier wird nur gelesen und in
 * Klartext übersetzt. Ohne Browser prüfbar (Node-Tests).
 */

/** Feld, das der Server je Adressbuch-Zeile mitliefert. */
export const ANFRAGBAR_FELD = 'daten_anfragbar'

/** Beschriftung des Knopfes (EINE Formulierung, §4 Sprache). */
export const KNOPF_TEXT = 'Daten anfragen'

/** Meldung nach dem Klick, wenn die Anfrage hinausging. */
export const GESENDET = 'Anfrage gesendet. Die Person entscheidet, ob sie ihre Kontaktdaten freigibt.'

/**
 * Meldung, wenn in den letzten Tagen schon angefragt wurde. Der Server nennt
 * keinen Zeitraum in der Antwort — der Klartext bleibt deshalb ohne Zahl
 * („schon angefragt“, nicht „vor 7 Tagen“), damit die Anzeige nicht rechnet,
 * was sie nicht weiß.
 */
export const BEREITS = 'Du hast schon angefragt. Die Person hat die Anfrage bekommen.'

/**
 * Beschriftung des Knopfes, NACHDEM angefragt wurde (Review zu UI-R7, Punkt 3):
 * der Zustand der Zeile, nicht die Aufforderung. Der Knopf bleibt gesperrt —
 * sonst schickte jeder weitere Klick eine neue Anfrage an den Server.
 */
export const ANGEFRAGT_TEXT = 'Angefragt'

/**
 * Meldung, wenn der Server die Anfrage annimmt, aber nichts verschickt hat
 * (`gesendet: false` ohne `bereits`). Den GRUND nennt der Server bewusst NICHT
 * (ausgeschlossen, gesperrt, Zustellfehler, kein Konto …) — die Anzeige
 * behauptet deshalb auch keinen, sondern sagt nur, was sie weiß (Review zu
 * UI-R7, Punkt 4: der alte Satz „hat kein Konto“ war eine Erfindung).
 */
export const NICHT_GESENDET = 'Die Anfrage konnte nicht zugestellt werden. Bitte frage die Person direkt.'

/**
 * Steht an einer Zeile „Daten anfragen“? Nur wenn der Server die Zeile
 * ausdrücklich als anfragbar markiert (fail closed: fehlt das Feld, nicht).
 *
 * Zwei Formen, EINE Regel: die ROHE Server-Zeile trägt `daten_anfragbar`, die
 * Zeilenform der Ansicht (`personenZeilen.mjs`) `datenAnfragbar`. Nur der
 * ausdrückliche Wahrheitswert zählt — kein „1“, kein „true“ als Text.
 */
export function istAnfragbar(zeile) {
  if (!zeile) return false
  return zeile[ANFRAGBAR_FELD] === true || zeile.datenAnfragbar === true
}

/**
 * Steht „Kontaktdaten nicht freigegeben“ statt einer Reihe von Gedankenstrichen?
 *
 * Nur dann, wenn es wirklich etwas zu fragen GIBT (`istAnfragbar`: die Person
 * lebt und hat nicht alles freigegeben) UND nichts zu sehen ist. Maßstab sind
 * die gelieferten Felder: `null` heißt „nicht freigegeben“ (der Server maskiert
 * fail closed), ein leerer Text heißt „nichts hinterlegt“ — beides ist hier
 * dasselbe: es ist nichts zu sehen.
 *
 * Review zu UI-R7, Punkt 5: Ohne die `istAnfragbar`-Prüfung stand der Satz
 * auch bei Personen, die alles freigegeben haben, aber nichts hinterlegt
 * haben — und bei gelöschten Personen. Beiden unterstellte er ein Verbergen.
 *
 * Review UI-R7b, Punkt 6: Das Feld heißt in der ANSICHTSZEILE `ort`
 * (`personenZeilen.mjs` baut „72070 Tübingen“ hinein), nicht `wohnort`. Vorher
 * fragte diese Stelle `wohnort` — die Ansichtszeile hat es nicht, also galt
 * ein freigegebener Ort als „nichts da“ und die Karte zeigte den Satz statt
 * des Ortes. Beide Namen werden gelesen (die ROHE Serverzeile trägt
 * `wohnort`), damit keine der beiden Formen durchfällt.
 */
export function ohneKontaktdaten(zeile) {
  if (!zeile) return false
  if (!istAnfragbar(zeile)) return false
  return !text(zeile.email) && !text(zeile.telefonnummer)
    && !text(zeile.ort) && !text(zeile.wohnort)
}

/** Klartext für die eine Zeile, die die leeren Felder ersetzt. */
export const NICHT_FREIGEGEBEN = 'Kontaktdaten nicht freigegeben'

/**
 * Klartext der Antwort von `mitglieder.daten_anfragen`.
 *   { success, gesendet, bereits? }
 * Rückgabe: { text, art } — `art` ist 'gesendet' | 'bereits' | 'nicht-gesendet'
 * für die Anzeige (Toast-Farbe) und für die Tests.
 */
export function antwortText(antwort) {
  const a = antwort || {}
  if (a.bereits === true) return { text: BEREITS, art: 'bereits' }
  if (a.gesendet === true) return { text: GESENDET, art: 'gesendet' }
  return { text: NICHT_GESENDET, art: 'nicht-gesendet' }
}

/**
 * Ziel eines Klicks auf eine Meldung vom Typ „Datenanfrage“: das EIGENE
 * Profil, Abschnitt „Sichtbarkeit“ (dort stehen die Freigabe-Schalter).
 *
 * Die Adresse ist `#/profile?bereich=sichtbarkeit` — `#/profile` ist die
 * Route der Seite (`router.js`, Seitenname `Profile`); ein zweites `#` als
 * Sprungmarke würde den Hash-Router zerlegen, deshalb steht der Bereich als
 * Abfrageteil. `Profile.vue` liest ihn beim Aufbau und beim `hashchange`.
 */
export const PROFIL_SICHTBARKEIT = '#/profile?bereich=sichtbarkeit'

/** Ist eine Meldung eine Datenanfrage? (Server: `type` der Meldung.) */
export function istDatenanfrage(meldung) {
  return String(meldung?.type || '') === 'Datenanfrage'
}

/**
 * Wer hat gefragt? Der Server schreibt den Anzeigenamen in den Betreff
 * („‹Name› möchte deine Kontaktdaten sehen“) und in den Text. Hier wird der
 * Name aus dem Betreff gelesen — ohne ihn bleibt der Hinweis allgemein, statt
 * einen Namen zu erfinden.
 */
const BETREFF_MUSTER = /^(.+?)\s+möchte deine Kontaktdaten sehen$/i

export function fragendePerson(meldung) {
  const betreff = text(meldung?.subject)
  const treffer = BETREFF_MUSTER.exec(betreff)
  return treffer ? treffer[1].trim() : ''
}

/**
 * Kurzer Hinweis über den Freigabe-Schaltern, wenn die Seite über eine
 * Datenanfrage geöffnet wurde. Ohne Meldung (oder ohne Namen im Betreff)
 * bleibt es beim allgemeinen Satz — ein Name wird nie erfunden.
 */
export function anfrageHinweis(meldung) {
  const wer = fragendePerson(meldung)
  return wer
    ? `${wer} möchte deine Kontaktdaten sehen. Du entscheidest hier, was du freigibst.`
    : 'Jemand möchte deine Kontaktdaten sehen. Du entscheidest hier, was du freigibst.'
}

/**
 * Adresse des Profils mit einem Bereichs-Wunsch — eine Stelle für die
 * Schreibweise (`#/profile?bereich=sichtbarkeit`).
 */
export function profilAdresse(bereich = 'sichtbarkeit') {
  const b = text(bereich)
  return b ? `#/profile?bereich=${encodeURIComponent(b)}` : '#/profile'
}

/** Bereichs-Wunsch aus einer Adresse lesen (`#/profile?bereich=…`). */
export function bereichAusAdresse(hash) {
  const roh = String(hash || '')
  const frage = roh.includes('?') ? roh.slice(roh.indexOf('?') + 1) : ''
  if (!frage) return ''
  try {
    return new URLSearchParams(frage).get('bereich') || ''
  } catch (_) {
    return ''
  }
}

function text(wert) {
  return wert === null || wert === undefined ? '' : String(wert).trim()
}
