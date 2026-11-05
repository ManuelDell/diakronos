/** Fehlende Daten schränken Automatik ein, blockieren aber nie die Plan-Anlage. */
export function fehlenderBedarf(bedarf) {
  return (Array.isArray(bedarf) ? bedarf : []).filter(b => b.einstufung !== 'ok')
}
export function stammdatenRoute(plantyp, plan = null) {
  // UX3a: Stammdaten gehören zum Bereich „Dienste“ — Plan-Kontext im Reiter
  // „Dienstpläne“, Plantyp-Kontext im Reiter „Vorlagen“. Keine erfundene
  // Kennung: ohne Plantyp steht der Platzhalter „-“ (derselbe Vertrag wie
  // bisher '#/planrahmen/stammdaten/‹plantyp›').
  return plan
    ? '#/dienste/dienstplaene/vorbereiten/' + encodeURIComponent(plan)
    : '#/dienste/vorlagen/-/stammdaten/' + encodeURIComponent(plantyp || '-')
}
