/**
 * P1-11 — Aufbereitung der Mitglieder-Sicht „Meine Dienste" (OP-CHOR-7).
 *
 * Die API liefert je Zuordnung bereits Lied-Titel, Uhrzeit und Mitwirkende.
 * Diese reinen Helfer machen daraus verstaendlichen deutschen Text; sie sind
 * ohne Vue testbar (Muster: meldungen.mjs / klartext.mjs).
 */

/** Rollenname aus dem letzten Feldpfad-Glied ('lieder[1].solo' → 'Solo'). */
export function feldName(pfad) {
  const teil = String(pfad || '').split(/[.:/]/).filter(Boolean).pop() || ''
  const ohneIndex = teil.split('[')[0]
  if (!ohneIndex) return 'Dienst'
  return ohneIndex.charAt(0).toUpperCase() + ohneIndex.slice(1)
}

const ROLLEN_TEXT = {
  dirigent: 'Dirigent',
  klavier: 'Klavier',
  solo: 'Solo',
  einsingen: 'Einsingen',
  leitung: 'Leitung',
}

/** Menschenlesbare Rollenbezeichnung (unbekannte Rollen bleiben roh). */
export function rollenText(rolle) {
  const r = String(rolle || '')
  return ROLLEN_TEXT[r] || r
}

/** Eine Zeile „Dirigent: A · Solo: B" aus der Mitwirkenden-Liste. */
export function mitwirkendeText(mitwirkende) {
  return (mitwirkende || [])
    .map((m) => {
      const rolle = rollenText(m?.rolle)
      return rolle ? `${rolle}: ${m?.name}` : String(m?.name ?? '')
    })
    .filter(Boolean)
    .join(' · ')
}

/**
 * Ist eine Zuordnung mit einer gemeldeten Abwesenheit im Konflikt?
 * Der Server setzt `abwesend`; dieser Helfer bleibt fuer die Anzeige auch
 * dann korrekt, wenn das Feld fehlt (nie faelschlich warnen).
 */
export function istKonflikt(dienst) {
  return Boolean(dienst?.abwesend)
}

/**
 * P1-11b (Befund 4, OP-HANDY-5): Die Dashboard-Kachel speist sich aus zwei
 * Quellen — dem alten Kronos-Modell und dem Plan-Rahmen. Stand derselbe
 * Einsatz in beiden, stand er doppelt in der Kachel. Diese Funktion fuehrt
 * beide Listen zusammen und entfernt Dubletten ueber den Schluessel
 * „Titel + Zeitpunkt". Der Plan-Rahmen gewinnt (er ist die fachlich
 * fuehrende Quelle, die alten Kronos-Elemente laufen aus).
 *
 * Die Eintraege kommen bereits aufbereitet ({ titel, sort, ... }); die
 * Reihenfolge bleibt stabil (nach `sort`, dann Einfuegereihenfolge).
 */
export function ohneDubletten(eintraege) {
  const gesehen = new Set()
  const ergebnis = []
  for (const e of eintraege || []) {
    // Zeitpunkt ohne die reine Anzeigezeit: `sort` traegt ISO/Datum.
    const schluessel = [String(e?.titel ?? ''), String(e?.sort ?? '')].join('|')
    if (gesehen.has(schluessel)) continue
    gesehen.add(schluessel)
    ergebnis.push(e)
  }
  return ergebnis
}

/**
 * P1-11b (Befund 4): fertige Kachel-Zeilen aus beiden Quellen.
 * `planEintraege` steht vorn, `alteEintraege` folgt — bei Gleichstand
 * (Titel + Zeitpunkt) gewinnt der Plan-Rahmen.
 */
export function kachelEintraege(planEintraege, alteEintraege) {
  return ohneDubletten([...(planEintraege || []), ...(alteEintraege || [])])
    .sort((a, b) => String(a?.sort ?? '').localeCompare(String(b?.sort ?? '')))
}
