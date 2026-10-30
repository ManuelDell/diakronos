/**
 * UX-B2 — Meine Dienste: Monatskarten mit Rollenfarbe (Manuel 2026-10-23,
 * Befund DMB-964a27d87752, Entwurf B2).
 *
 * Zwei reine Helfer, ohne Vue und ohne Browser testbar (Muster:
 * meine-dienste.mjs):
 *
 *  1. `monatsGruppen(dienste)` — je Monat eine Karte. Die Dienste kommen
 *     unsortiert von der API; die Karte traegt ihren Schluessel (`2026-11`),
 *     einen lesbaren Titel („November 2026") und die Zeilen in Datumsreihenfolge.
 *
 *  2. `rollenFarbe(rolle)` — Zuordnung Rolle → Farb-Ton. Die Rollen stehen
 *     NICHT fest im Code: die Tabelle unten ist eine Zuordnung mit
 *     Rueckfall-Ton (`RUECKFALL_FARBE`), alles Unbekannte bekommt ihn.
 *     Farben sind ausschliesslich vorhandene Tokens aus tokens.css
 *     (--accent, --info, --ok, --muted) — keine neuen Farbwerte.
 *
 * UX-B2b (Variante D, Operator-Entscheidung 2026-10-24): Die FLÄCHE eines
 * Rollenzeichens ist der Rollenton mit 12 % (hell) bzw. 22 % (dunkel) über der
 * Kartenfläche; die SCHRIFT ist einheitlich `--text`. Damit traegt die Farbe
 * die Rolle und der Text bleibt ueberall gleich gut lesbar.
 *
 * Einsingen ist NICHT mehr `--warn`: im Dunkelmodus liegen --accent (#e0b866)
 * und --warn (#e0b163) praktisch auf demselben Farbton — zwei Rollen waeren
 * dort nicht zu unterscheiden. Variante D + Operator-Entscheidung 2026-10-24
 * (Variante B): Einsingen bekommt den neutralen, warmgrauen Ton
 * `--dk-warm-500` (#5b6178). Ergebnis:
 *   Dirigent = Akzent (Gold), Klavier = Info (Blau), Solo = Erfolg (Gruen),
 *   Einsingen = Neutral (Grau), unbekannte Rollen = Rueckfall (Flaeche ohne
 *   Ton, nur Rahmen).
 *
 * Warum nicht `--muted`? `--muted` ist im Dunkelmodus #9ba3c1 (blaustichig)
 * und liegt bei 22 % Deckkraft nur ΔE 4,9 von --info (#8fb2ff) entfernt —
 * gemessen im Test. `--dk-warm-500` ist ein Rohwert (themenunabhaengig) und
 * haelt im Dunkelmodus ΔE 8,6 zu Klavier; die 10er-Schwelle waere bei 12 %/22 %
 * nur mit einem fast weissen Ton zu halten (Herleitung im Testkommentar).
 * Farbe bleibt nie das einzige Unterscheidungsmittel: jedes Rollenzeichen
 * traegt zusaetzlich einen Buchstaben (D/K/S/E, bei unbekannten Rollen den
 * Anfangsbuchstaben) und die Zeile nennt die Rolle im Klartext (WCAG 1.4.1).
 */

/** Farb-Ton der Rollen — nur vorhandene Tokens aus tokens.css. */
export const ROLLEN_FARBEN = {
  dirigent: 'accent',
  klavier: 'info',
  solo: 'ok',
  einsingen: 'warm-500',
}

/** Rueckfall fuer alles, was die Tabelle nicht kennt (z. B. „Prediger"). */
export const RUECKFALL_FARBE = 'rueckfall'

/**
 * Deckkraft des Rollentons auf der Kartenfläche (Variante D).
 * Hell 12 %, dunkel 22 % — im Dunkelmodus braucht es mehr Ton, weil 12 %
 * auf der dunklen Fläche fast verschwindet.
 */
export const FLAECHE_HELL = 0.12
export const FLAECHE_DUNKEL = 0.22

/**
 * Rollen-Schluessel normalisieren: `feld_pfad` ist 'lieder[1].solo',
 * `feld_name` ist 'solo'. Beides muss denselben Schluessel ergeben.
 */
export function rollenSchluessel(rolle) {
  const roh = String(rolle ?? '').trim().toLowerCase()
  if (!roh) return ''
  // letzten Pfadabschnitt nehmen: 'lieder[1].solo' -> 'solo'
  const letzte = roh.split(/[.:/]/).filter(Boolean).pop() || ''
  // Index entfernen: 'solo[2]' -> 'solo'
  return letzte.split('[')[0]
}

/**
 * Farb-Token zu einer Rolle. Unbekannte Rollen (und leere Angaben) bekommen
 * die Rueckfall-Farbe — nie `undefined`, nie ein geratener Ton.
 */
export function rollenFarbe(rolle) {
  const key = rollenSchluessel(rolle)
  return Object.prototype.hasOwnProperty.call(ROLLEN_FARBEN, key)
    ? ROLLEN_FARBEN[key]
    : RUECKFALL_FARBE
}

/** Ist die Rolle in der Tabelle bekannt (fuer die Legende)? */
export function istBekannteRolle(rolle) {
  const key = rollenSchluessel(rolle)
  return Object.prototype.hasOwnProperty.call(ROLLEN_FARBEN, key)
}

/**
 * Anfangsbuchstabe fuer das Rollenzeichen. Zwei Rollen mit gleichem Anfangs-
 * buchstaben sind bei den vorhandenen Rollen ausgeschlossen (D/K/S/E); bei
 * unbekannten Rollen bleibt der Anfangsbuchstabe die beste Naeherung.
 */
export function rollenZeichen(rolle, text) {
  const quelle = String(text || rollenSchluessel(rolle) || '').trim()
  return quelle ? quelle.charAt(0).toUpperCase() : '•'
}

/** „November 2026" aus einem ISO-Datum (ohne Zeitzonen-Umrechnung). */
const MONATSNAMEN = [
  'Januar', 'Februar', 'März', 'April', 'Mai', 'Juni',
  'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember',
]

export function monatsTitel(isoDatum) {
  const teile = String(isoDatum ?? '').split('-')
  if (teile.length < 2) return ''
  const monat = Number(teile[1])
  const jahr = teile[0]
  if (!Number.isInteger(monat) || monat < 1 || monat > 12 || !jahr) return ''
  return `${MONATSNAMEN[monat - 1]} ${jahr}`
}

/**
 * Dienste je Monat gruppieren — eine Karte je Monat, aufsteigend nach Monat,
 * die Zeilen darin aufsteigend nach Datum.
 *
 * Rueckgabe: [{ schluessel: '2026-11', titel: 'November 2026', dienste: [...] }]
 *
 * Dienste ohne lesbares Datum landen NICHT in einer Sammelkarte, sondern
 * entfallen — sie waeren in einer Monatskarte am falschen Ort und die API
 * liefert `termin` immer (ISO). Der Aufrufer filtert sie vorher schon
 * (MeineDienste.vue: nur heute oder spaeter).
 */
export function monatsGruppen(dienste) {
  const karte = new Map()
  for (const d of dienste || []) {
    const iso = String(d?.termin ?? '')
    // Nur 'JJJJ-MM-TT' — alles andere kann nicht einsortiert werden.
    if (!/^\d{4}-\d{2}/.test(iso)) continue
    const schluessel = iso.slice(0, 7)
    if (!karte.has(schluessel)) {
      karte.set(schluessel, { schluessel, titel: monatsTitel(iso), dienste: [] })
    }
    karte.get(schluessel).dienste.push(d)
  }
  return [...karte.values()]
    .map((g) => ({
      ...g,
      dienste: g.dienste
        .slice()
        .sort((a, b) => String(a?.termin ?? '').localeCompare(String(b?.termin ?? ''))),
    }))
    .sort((a, b) => a.schluessel.localeCompare(b.schluessel))
}

/**
 * Legende: die Rollen, die in den angezeigten Diensten wirklich vorkommen —
 * in der Reihenfolge der Tabelle, danach die unbekannten Rollen in der
 * Reihenfolge ihres Auftretens. Keine Rollen ohne Dienste: eine Legende, die
 * Farben ohne Vorkommen zeigt, erklaert nichts.
 *
 * Rueckgabe: [{ rolle, text, farbe, zeichen }]
 */
export function legende(dienste, textFn) {
  const gesehen = new Set()
  const bekannt = []
  const unbekannt = []
  const texte = new Map()
  for (const d of dienste || []) {
    const key = rollenSchluessel(d?.feld_pfad || d?.feld_name)
    if (!key || gesehen.has(key)) continue
    gesehen.add(key)
    const text = typeof textFn === 'function' ? textFn(key) : key
    texte.set(key, text)
    const eintrag = { rolle: key, text, farbe: rollenFarbe(key), zeichen: rollenZeichen(key, text) }
    if (istBekannteRolle(key)) bekannt.push(eintrag)
    else unbekannt.push(eintrag)
  }
  const reihenfolge = Object.keys(ROLLEN_FARBEN)
  bekannt.sort((a, b) => reihenfolge.indexOf(a.rolle) - reihenfolge.indexOf(b.rolle))
  return [...bekannt, ...unbekannt]
}

/** Zahl der Dienste auf Deutsch („1 Dienst" / „2 Dienste"). */
export function diensteText(anzahl) {
  const n = Number(anzahl) || 0
  return `${n} ${n === 1 ? 'Dienst' : 'Dienste'}`
}
