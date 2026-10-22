/**
 * filterChips — Chips für Such- und Filterzeilen (DES-01).
 *
 * Befund: 28 rohe `<button>`-Zeilen in 12 Seiten bauten die Filterknöpfe
 * jeweils selbst — teils mit Klasse `dk-filter-chip`, teils mit eigenen
 * Klassen, teils gar nicht. Ergebnis: zwei Aussehen (Chips und `DkSegment`)
 * und Stellen, die ihren Zustand (gewählt?) nicht ansagen.
 *
 * Dieser Baustein liefert die Daten für EINE Chip-Zeile. Die Darstellung
 * kommt aus `components/ui/DkFilterChips.vue`; die Logik hier ist reines
 * JavaScript und ohne Browser prüfbar.
 *
 * Regeln, die aus dem Befund folgen:
 *  - Ein Filter ist abwählbar: ein zweiter Klick auf den gewählten Chip
 *    schaltet ihn ab (`abwaehlbar`). „Alle“ bleibt der Ruhezustand.
 *  - Die Zahl am Chip ist die Zahl der Treffer DIESER Auswahl, nicht die
 *    Gesamtzahl — sonst zeigte ein Chip „0“, obwohl man ihn anklicken kann.
 *  - Ohne Treffer bleibt die Zeile sichtbar und sagt das (kein stiller
 *    leerer Streifen).
 */

/** Ein Wert gilt als „nicht gewählt“, wenn er leer ist oder 'alle'. */
export function istAlle(wert) {
  return wert === '' || wert === null || wert === undefined || wert === 'alle'
}

/** Eine Anzeige nur übernehmen, wenn sie ein Skalar ist (kein Objekt/Array). */
function alsText(wert) {
  if (wert === null || wert === undefined) return ''
  const art = typeof wert
  if (art !== 'string' && art !== 'number') return ''
  return String(wert).trim()
}

/**
 * Einen Eintrag auf seinen Chip-Namen bringen (auch für `filtereNachChip`).
 * Leere Angaben landen unter `leerLabel` — vorher hiessen sie „Unbekannt“,
 * also nach einem erfundenen Namen statt nach einer fehlenden Angabe.
 */
export function chipName(eintrag, schluessel, beschriftung, leerLabel = 'Ohne Zuordnung') {
  const roh = schluessel(eintrag)
  const anzeige = alsText(beschriftung ? beschriftung(eintrag) : '')
  const name = anzeige || alsText(roh)
  return name || leerLabel
}

/**
 * Chips aus einer Liste von Einträgen bilden.
 *
 * @param {Array} eintraege        die gefilterten/ungefilterten Einträge
 * @param {(e)=>string} schluessel Wert, nach dem gruppiert wird
 * @param {(e)=>string} [beschriftung] Anzeigename; ohne Angabe der Wert selbst
 * @param {object} optionen        { alleLabel='Alle', alleWert='alle', leerLabel='Ohne Zuordnung' }
 * @returns {Array<{id:string, label:string, anzahl:number}>} erster Chip = „Alle“
 */
export function chipsAus(eintraege = [], schluessel = () => '', beschriftung = null, optionen = {}) {
  const alleLabel = optionen.alleLabel ?? 'Alle'
  const alleWert = optionen.alleWert ?? 'alle'
  const leerLabel = optionen.leerLabel ?? 'Ohne Zuordnung'
  const liste = Array.isArray(eintraege) ? eintraege : []

  const zahlen = new Map()
  for (const e of liste) {
    const name = chipName(e, schluessel, beschriftung, leerLabel)
    zahlen.set(name, (zahlen.get(name) || 0) + 1)
  }

  const chips = [{ id: alleWert, label: alleLabel, anzahl: liste.length }]
  for (const [name, anzahl] of [...zahlen.entries()].sort((a, b) => a[0].localeCompare(b[0], 'de'))) {
    chips.push({ id: name, label: name, anzahl })
  }
  return chips
}

/**
 * Einfache Ja/Nein-Chips (z. B. „Nur freie“, Rechte-Status).
 * `eintraege` sind bereits die gezählten Werte: [{ id, label, anzahl }].
 */
export function chipsMitZahlen(werte = [], alleLabel = 'Alle', alleWert = 'alle') {
  const liste = Array.isArray(werte) ? werte : []
  const summe = liste.reduce((s, w) => s + (Number(w.anzahl) || 0), 0)
  return [
    { id: alleWert, label: alleLabel, anzahl: summe },
    ...liste.map(w => ({
      id: String(w.id),
      label: w.label ?? String(w.id),
      anzahl: Number(w.anzahl) || 0,
    })),
  ]
}

/** Einträge nach dem gewählten Chip filtern. */
export function filtereNachChip(eintraege = [], gewaehlt, schluessel = () => '', beschriftung = null, optionen = {}) {
  const liste = Array.isArray(eintraege) ? eintraege : []
  if (istAlle(gewaehlt)) return liste
  const leerLabel = optionen.leerLabel ?? 'Ohne Zuordnung'
  return liste.filter(e => chipName(e, schluessel, beschriftung, leerLabel) === gewaehlt)
}

/**
 * Klick auf einen Chip: gleicher Chip noch einmal = abwählen (DES-01, S9).
 * „Alle“ ist der Ruhezustand und schaltet nicht auf einen leeren Filter.
 */
export function naechsterChip(aktuell, angeklickt, alleWert = 'alle') {
  if (istAlle(angeklickt)) return alleWert
  return aktuell === angeklickt ? alleWert : angeklickt
}

/**
 * Sprechtext für die Vorlesehilfe: „Alle, 26 Treffer (gewählt)“.
 * Ohne Zustand müsste ein Screenreader raten, welcher Chip gewählt ist.
 */
export function chipSprechtext(chip, gewaehlt, alleWert = 'alle') {
  const istGewaehlt = gewaehlt === chip.id || (istAlle(gewaehlt) && chip.id === alleWert)
  const zahl = Number(chip.anzahl)
  const zahlText = Number.isFinite(zahl) ? `${zahl} ${zahl === 1 ? 'Treffer' : 'Treffer'}` : ''
  return [chip.label, zahlText, istGewaehlt ? 'gewählt' : ''].filter(Boolean).join(', ')
}
