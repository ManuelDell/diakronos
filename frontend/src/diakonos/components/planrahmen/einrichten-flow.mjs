/** Fehlende Daten schränken Automatik ein, blockieren aber nie die Plan-Anlage. */
export function fehlenderBedarf(bedarf) {
  return (Array.isArray(bedarf) ? bedarf : []).filter(b => b.einstufung !== 'ok')
}
export function stammdatenRoute(plantyp, plan = null) {
  return plan ? '#/planrahmen/vorbereiten/' + encodeURIComponent(plan) : '#/planrahmen/stammdaten/' + encodeURIComponent(plantyp)
}
