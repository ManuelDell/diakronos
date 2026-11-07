/**
 * UX2e5 — Die Einträge des „⋯"-Menüs an einem Termin der Terminliste.
 *
 * Prinzip N6 („Objekt-Aktionen ans Objekt") und K2 (schrittweise Offenlegung):
 * Der Termin selbst bleibt die Fläche für „ansehen/bearbeiten" (Klick auf die
 * Zeile); das Menü trägt die Handlungen, die man am Termin sucht, ohne die
 * Zeile zu öffnen. Gefährliches steht am Ende, getrennt
 * (`DkAktionen` sortiert und trennt selbst — siehe ../ui/aktionen.mjs).
 *
 * Die Schlüssel sind der Vertrag mit der Seite (`Kalender.vue`): sie führt die
 * Handlungen aus, das Widget kennt keine Adressen und keine Berechtigungen.
 */
export const MENUE_EINTRAEGE = Object.freeze([
  { key: 'bearbeiten', label: 'Bearbeiten', icon: 'bearbeiten' },
  { key: 'ansehen', label: 'Ansehen', icon: 'ansehen' },
  { key: 'loeschen', label: 'Löschen', icon: 'loeschen', gefahr: true },
])

/** Die Schlüssel in der Reihenfolge, in der das Menü sie zeigt. */
export const MENUE_SCHLUESSEL = MENUE_EINTRAEGE.map((e) => e.key)

export default MENUE_EINTRAEGE
