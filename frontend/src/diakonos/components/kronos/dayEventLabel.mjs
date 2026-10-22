/**
 * Beschriftung eines Termins im Tages-Dialog — als reine Funktion.
 *
 * P1-5c (4/K3): Die Logik lag als Funktion im `<script setup>` von
 * `KronosDayEventsDialog.vue` und war dort nicht aufrufbar. Der Node-Test
 * konnte deshalb nur den Quelltext mit Regex pruefen (K3: „prueft nur Regex,
 * keine Logik“). Hier steht dieselbe Regel als Funktion, die der Dialog
 * importiert und der Test wirklich ausfuehrt.
 *
 * Regeln (aus dem Dialog uebernommen):
 *   * Kein Ende: Punkttermin -> `all_day` heisst „Ganztägig“, sonst Startzeit.
 *   * Start = Ende an einem Tag, 00:00:00: Bestandsdaten tragen ganztägige
 *     Termine so OHNE `all_day`-Flag -> „Ganztägig“ (BLD-R6). Nur echte
 *     00:00-Spannen zaehlen; 14:00–14:00 ist KEIN ganztägiger Termin
 *     (P1-5c/4) und zeigt die Uhrzeit.
 *   * Mehrtägig: Tagesbereich, mit Uhrzeit wenn vorhanden, sonst „Ganztägig“.
 */

function alsDatum(wert) {
  if (!wert) return null
  const d = new Date(String(wert).replace(' ', 'T'))
  return isNaN(d.getTime()) ? null : d
}

/** True, wenn die Spanne als „ganztägig ohne Uhrzeit“ gilt. */
export function istOhneUhrzeit(allDay, start, ende) {
  if (allDay) return true
  if (!start || !ende) return false
  if (start.getTime() !== ende.getTime()) return false
  return start.getHours() === 0 && start.getMinutes() === 0 && start.getSeconds() === 0
}

export function formatTimeRange(ev) {
  const optsT = { hour: '2-digit', minute: '2-digit' }
  const optsD = { day: '2-digit', month: '2-digit' }
  const roh = ev || {}
  const s = alsDatum(roh.start)
  if (!s) return String(roh.start || '')
  const eRoh = alsDatum(roh.end)
  // K2: Termine ohne Ende sind Punkttermine — nicht „Invalid Date“ zeigen.
  if (!eRoh) {
    return roh.allDay ? 'Ganztägig' : s.toLocaleTimeString('de-DE', optsT)
  }
  const gleicherTag = s.getFullYear() === eRoh.getFullYear()
    && s.getMonth() === eRoh.getMonth() && s.getDate() === eRoh.getDate()
  const ohneUhrzeit = istOhneUhrzeit(roh.allDay, s, eRoh)
  if (!gleicherTag) {
    const links = s.toLocaleDateString('de-DE', optsD)
    const rechts = eRoh.toLocaleDateString('de-DE', optsD)
    if (ohneUhrzeit) return `Ganztägig ${links} – ${rechts}`
    return links + ' ' + s.toLocaleTimeString('de-DE', optsT)
      + ' – ' + rechts + ' ' + eRoh.toLocaleTimeString('de-DE', optsT)
  }
  if (ohneUhrzeit) return 'Ganztägig'
  return s.toLocaleTimeString('de-DE', optsT) + ' – ' + eRoh.toLocaleTimeString('de-DE', optsT)
}
