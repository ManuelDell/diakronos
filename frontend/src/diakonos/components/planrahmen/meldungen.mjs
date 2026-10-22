export function meldungsGruppen(meldungen) {
  const gruppen = new Map()
  const anzahl = { fehler: 0, warnung: 0, hinweis: 0 }
  for (const m of meldungen) {
    const stufe = ({ muss: 'fehler', sollte: 'warnung' }[m.stufe] || m.stufe || 'fehler')
    anzahl[stufe] = (anzahl[stufe] || 0) + 1
    const regel = m.baustein || m.bewertung?.baustein || m.code || 'Allgemein'
    const key = stufe + ':' + regel
    if (!gruppen.has(key)) gruppen.set(key, { key, stufe, regel, meldungen: [] })
    gruppen.get(key).meldungen.push(m)
  }
  return { anzahl, gruppen: [...gruppen.values()] }
}

export function terminMeldungen(eintraege, termin) {
  const result = new Map()
  for (const e of eintraege || []) {
    if (termin && e.termin !== termin) continue
    for (const m of e.meldungen || []) {
      const meldung = { ...m, termin: e.termin, feld_pfad: e.feld_pfad }
      const key = JSON.stringify(meldung)
      if (!result.has(key)) result.set(key, meldung)
    }
  }
  return [...result.values()]
}
