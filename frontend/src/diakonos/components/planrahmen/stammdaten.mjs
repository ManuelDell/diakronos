/** Übersetzt die öffentliche API-Kennungen in die Matrix-/Tabellenstruktur. */
export function stammdatenNormalisieren(daten) {
  // Titel kann als eigenes Feld ODER in daten kommen: beides zusammenführen,
  // sonst verlieren Einträge mit leerem daten-Objekt ihren Titel.
  const zeile = e => {
    const daten = { ...((e && typeof e.daten === 'object' && e.daten) || {}) }
    const titel = e?.titel ?? daten.titel
    if (titel !== undefined && titel !== null && titel !== '') daten.titel = titel
    return { ...e, id: e?.kennung ?? e?.id, titel: titel ?? '', daten }
  }
  const sammlungen = Object.fromEntries((daten.sammlungen || []).map(s => [s.schluessel, (s.eintraege || []).map(zeile)]))
  sammlungen.lieder = (daten.lieder || []).map(zeile)
  return {
    ...daten,
    personen: (daten.personen || []).map(p => ({ ...p, id: p.kennung })),
    sammlungen,
  }
}
