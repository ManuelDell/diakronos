/**
 * P1-4b — reine Entscheidungs-Helfer der Ressourcen-Moderation.
 *
 * Sie liegen extra hier, damit die Zuordnung „Anfrage -> Endpunkt“ per
 * node:test GEPRUEFT WERDEN KANN, statt nur im Quelltext von Ressourcen.vue zu
 * stehen (Review-Punkt W1: Verhaltenstests statt Quelltext-Regex).
 *
 * Hintergrund (Befund B1): `get_anfragen` spiegelt Termin-Ressourcen
 * (`quelle: "termin"`) in dieselbe Liste wie Raumbuchungen. Die Oberflaeche
 * zeigte fuer BEIDE dieselben Knoepfe und rief `decide_buchung` auf — dessen
 * `buchung_id` laedt aber `Ressourcen Buchung`, die gespiegelte Zeile ist eine
 * `Element Ressource`-Kind-Zeile. Der Moderator sah Knoepfe, die nur Fehler
 * erzeugten.
 */

/** Modul der Ressourcen-Endpunkte (SPA-Pfad). */
export const RESSOURCEN_MODUL = 'diakronos.diakonos.api.ressourcen'

/**
 * Endpunkt zum Bestaetigen/Ablehnen einer Anfrage.
 *
 * `quelle === 'termin'` -> `decide_termin_ressource` (Kind-Zeile am Termin),
 * sonst -> `decide_buchung` (Ressourcen Buchung).
 */
export function entscheidungsEndpunkt(anfrage) {
  return anfrage?.quelle === 'termin'
    ? `${RESSOURCEN_MODUL}.decide_termin_ressource`
    : `${RESSOURCEN_MODUL}.decide_buchung`
}

/**
 * Aufrufparameter fuer die Entscheidung. Buchungen heissen `buchung_id`,
 * Termin-Ressourcen `zeile_id` — der Namensunterschied ist Teil der
 * Serversignatur, nicht Geschmack.
 */
export function entscheidungsArgumente(anfrage, entscheidung, grund = '') {
  const id = anfrage?.id
  const basis = entscheidung === 'ablehnen'
    ? { entscheidung: 'ablehnen', grund: String(grund || '').trim() }
    : { entscheidung: 'bestaetigen' }
  if (anfrage?.quelle === 'termin') {
    return { zeile_id: id, ...basis }
  }
  return { buchung_id: id, ...basis }
}

/** Zeigt die Anfrage auf einen Termin (statt auf eine Ressourcenbuchung)? */
export function istTerminAnfrage(anfrage) {
  return anfrage?.quelle === 'termin'
}
