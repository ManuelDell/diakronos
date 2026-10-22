import { lesbarerName } from './klartext.mjs'
import { fehlenderBedarf } from './einrichten-flow.mjs'

export function bedarfHinweise(bedarf, definition = {}) {
  return fehlenderBedarf(bedarf).map(b => {
    if (b.art === 'merkmal') {
      const m = definition.merkmale?.person?.find(m => m.id === b.kennung)
      // OP-CHOR-11: Der Hinweis nennt die tatsaechliche Wirkung — markierte
      // Personen werden bei fehlender Vorbelegung der Reihe nach vorgeschlagen.
      const name = m?.name || lesbarerName(b.kennung)
      return `Wer ${name}? Markiere die passenden Personen in den Stammdaten — der Vorschlag teilt sie dann der Reihe nach ein.`
    }
    if (b.art === 'sammlung') {
      const s = definition.sammlungen?.find(s => s.id === b.kennung)
      return `Ergänze die Liste „${s?.name || lesbarerName(b.kennung)}“ und ihre Angaben in den Stammdaten.`
    }
    return `Prüfe die Personen für „${lesbarerName(b.kennung)}“ in den Stammdaten.`
  })
}

/**
 * Die drei Erststart-Schritte mit Erledigt-Status (UX C2).
 *
 * Schritt 1 ist erledigt, wenn keine Angaben fehlen (keine Hinweise);
 * Schritt 2, sobald ein Plan existiert; Schritt 3, sobald veröffentlicht.
 * Rein aus den uebergebenen Fakten — keine Erfindung, keine Serverabfrage.
 */
export function erststartSchritte({ hinweise = [], angelegt = false, veroeffentlicht = false } = {}) {
  return [
    { nummer: 1, erledigt: !hinweise.length, titel: 'Wer kann was?' },
    { nummer: 2, erledigt: !!angelegt, titel: 'Plan erstellen' },
    { nummer: 3, erledigt: !!veroeffentlicht, titel: 'Automatisch einteilen & prüfen' },
  ]
}

