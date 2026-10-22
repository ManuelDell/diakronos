/**
 * treffzeit — „Dienstag 19:30“ als Baustein statt Freitext (OP-UI-20, S8).
 *
 * Befund: Die Treffzeit einer Gruppe war das vierte Eingabemuster für
 * Datum/Uhrzeit — ein freies Textfeld mit dem Platzhalter „z.B. Dienstag
 * 19:30“. Getippt wurde alles: „Di 19.30“, „dienstags“, „nach Absprache“.
 *
 * Die Angabe ist ein WOCHENRHYTHMUS, kein Termin — deshalb bleibt sie als
 * Text gespeichert (bestehende Werte bleiben gültig), wird aber aus zwei
 * Feldern zusammengesetzt und beim Anzeigen vereinheitlicht.
 *
 * Reine Funktionen ohne Vue/DOM — im Node-Test prüfbar.
 */

export const WOCHENTAGE = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']

/** Schreibweisen, die als Wochentag erkannt werden (klein, ohne Punkt). */
const WOCHENTAG_ALIASE = new Map([
  ['mo', 'Montag'], ['montag', 'Montag'], ['montags', 'Montag'],
  ['di', 'Dienstag'], ['die', 'Dienstag'], ['dienstag', 'Dienstag'], ['dienstags', 'Dienstag'],
  ['mi', 'Mittwoch'], ['mittwoch', 'Mittwoch'], ['mittwochs', 'Mittwoch'],
  ['do', 'Donnerstag'], ['donnerstag', 'Donnerstag'], ['donnerstags', 'Donnerstag'],
  ['fr', 'Freitag'], ['freitag', 'Freitag'], ['freitags', 'Freitag'],
  ['sa', 'Samstag'], ['samstag', 'Samstag'], ['samstags', 'Samstag'], ['sonnabend', 'Samstag'],
  ['so', 'Sonntag'], ['sonntag', 'Sonntag'], ['sonntags', 'Sonntag'],
])

/** „19:30“, „19.30“, „19:30 Uhr“, „9“ → „19:30“ / „09:00“; sonst ''. */
export function normiereUhrzeit(text) {
  const m = String(text || '').match(/(\d{1,2})\s*[:.]?\s*(\d{2})?/)
  if (!m) return ''
  const h = Number(m[1])
  const mi = m[2] === undefined ? 0 : Number(m[2])
  if (h > 23 || mi > 59) return ''
  return `${String(h).padStart(2, '0')}:${String(mi).padStart(2, '0')}`
}

/** Wochentag aus beliebiger Schreibweise; '' wenn keiner erkennbar ist. */
export function normiereWochentag(text) {
  const roh = String(text || '').toLowerCase().replace(/\./g, ' ').trim()
  // Zuerst ganze Wörter, dann Wortanfänge („dienstags“, „Di“).
  const woerter = roh.split(/[\s,/]+/).filter(Boolean)
  for (const wort of woerter) {
    const treffer = WOCHENTAG_ALIASE.get(wort)
    if (treffer) return treffer
  }
  for (const wort of woerter) {
    if (wort.length < 2) continue
    for (const [alias, tag] of WOCHENTAG_ALIASE) {
      if (alias.length >= 2 && wort.startsWith(alias)) return tag
    }
  }
  return ''
}

/**
 * Gespeicherten Text zerlegen: { wochentag, zeit, rest }.
 * `rest` ist alles, was nicht erkannt wurde („nach Absprache“) — es geht
 * nicht verloren, solange der Nutzer das Feld nicht überschreibt.
 */
export function zerlegeTreffzeit(text) {
  const roh = String(text || '').trim()
  const wochentag = normiereWochentag(roh)
  const zeit = normiereUhrzeit(roh.replace(/^(mo|di|mi|do|fr|sa|so)[a-zä]*\.?\s*/i, ''))
  return { wochentag, zeit, rest: '' }
}

/** { wochentag, zeit } → „Dienstag 19:30“, „Dienstag“, „19:30“ oder ''. */
export function baueTreffzeit(wochentag, zeit) {
  const tag = WOCHENTAGE.includes(wochentag) ? wochentag : ''
  const uhr = normiereUhrzeit(zeit)
  if (tag && uhr) return `${tag} ${uhr}`
  return tag || uhr || ''
}

/** Anzeige: erkennt auch Altschreibweisen und setzt sie einheitlich. */
export function anzeigeTreffzeit(text) {
  const roh = String(text || '').trim()
  if (!roh) return ''
  const gebaut = baueTreffzeit(normiereWochentag(roh), normiereUhrzeit(roh))
  // Nicht Erkennbares („nach Absprache“) bleibt unverändert stehen.
  return gebaut || roh
}

/** Für die Vorlesehilfe: „Dienstag, 19:30 Uhr“. */
export function sprechTreffzeit(text) {
  const { wochentag, zeit } = zerlegeTreffzeit(text)
  if (wochentag && zeit) return `${wochentag}, ${zeit} Uhr`
  return anzeigeTreffzeit(text)
}
