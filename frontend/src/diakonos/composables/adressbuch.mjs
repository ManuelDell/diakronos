/**
 * adressbuch — Hilfsfunktionen der Adressbuch-Seite (OP-HANDY-19).
 *
 * Befund: Auf dem Handy lief die 5-Spalten-Tabelle seitlich über (437–445 px
 * in einer 340-px-Karte), es gab keinen einzigen `tel:`/`mailto:`-Link und
 * damit keinen Weg, jemanden anzurufen. Diese Datei liefert die reine Logik,
 * die ohne Browser geprüft werden kann.
 */

/**
 * `tel:`-taugliche Nummer. Der RFC lässt nur Ziffern und ein führendes „+“;
 * Leerzeichen, Klammern, Punkte und Bindestriche sind in der Anzeige üblich,
 * im Link aber ungültig und führen auf manchen Geräten zu Fehlschlägen.
 */
export function telHref(nummer) {
  const roh = String(nummer || '').trim()
  if (!roh) return ''
  const plus = roh.startsWith('+') ? '+' : ''
  return plus + roh.replace(/[^0-9]/g, '')
}

/**
 * `mailto:`-taugliche Adresse. Nur offensichtlich kaputte Eingaben (Zeilen-
 * umbrüche, Leerzeichen mitten in der Adresse) werden abgewiesen — bewusst
 * KEINE strenge Prüfung: die Adresse kommt vom Server und wird maskiert
 * ausgeliefert. Ein leerer Wert ergibt einen leeren Link (der Aufrufer lässt
 * ihn dann weg).
 */
export function mailHref(mail) {
  const roh = String(mail || '').trim()
  if (!roh || /\s/.test(roh)) return ''
  return `mailto:${roh}`
}

/**
 * Karten-Ansicht nur auf schmalen Anzeigen (dieselbe Schwelle wie die App:
 * `.dk-sidebar` verschwindet bei 720 px).
 */
export function kartenAnsicht(breitePx) {
  const b = Number(breitePx)
  if (!Number.isFinite(b)) return false
  return b <= 720
}
