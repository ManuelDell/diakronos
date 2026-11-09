/**
 * DEC-B5 — reine Helfer der Ressourcen-Ansicht „Eigene Anfragen“.
 *
 * Sie liegen extra hier, damit die Regeln per `node:test` GEPRÜFT WERDEN
 * KÖNNEN (Verhaltensprüfung statt Quelltext-Regex) — dasselbe Muster wie
 * `ressourcenEntscheidung.js` (P1-4b/B1).
 *
 * Hintergrund (Manuel 2026-11-09): „Wenn man die Rechte hat, soll man es
 * freigeben können.“ Der Server erlaubt die Selbstfreigabe jetzt
 * (`decide_buchung` / `decide_termin_ressource`), kennzeichnet sie im
 * Audit-Protokoll als „Selbstfreigabe“ und liefert je eigener Anfrage
 * `darf_entscheiden`. Die Oberfläche darf Freigeben/Ablehnen deshalb NICHT
 * pauschal anzeigen (das war der Befund: Knöpfe, die nur Fehler erzeugten),
 * sondern nur, wenn der Server das Recht bestätigt.
 */

/**
 * Steht an der eigenen Anfrage „Freigeben“/„Ablehnen“?
 *
 * Zwei Bedingungen, beide vom Server (`get_meine_buchungen`):
 *   * `darf_entscheiden` — Freigaberecht (Ressourcenmoderator /
 *     Mitgliederadministrator / System Manager / Administrator),
 *   * Status „Angefragt“ — eine entschiedene Anfrage lässt sich nicht erneut
 *     entscheiden (der Server antwortet mit 417).
 */
export function darfSelbstFreigeben(anfrage) {
  return Boolean(anfrage?.darf_entscheiden) && anfrage?.status === 'Angefragt'
}

/**
 * Braucht die Anfrage „Zurücknehmen“?
 *
 * Nur offene EIGENE Anfragen — und nur dann, wenn nicht schon
 * Freigeben/Ablehnen dastehen (UX1h: eine Handlung je Lage, keine zwei
 * einander ausschließenden Knopfpaare).
 */
export function brauchtZuruecknehmen(anfrage) {
  return anfrage?.status === 'Angefragt'
    && anfrage?.quelle !== 'termin'
    && !darfSelbstFreigeben(anfrage)
}

/**
 * Schlüssel einer eigenen Anfrage.
 *
 * Raumbuchungen (`Ressourcen Buchung`) und Termin-Ressourcen (`Element
 * Ressource`) sind verschiedene Tabellen — ihre Namen dürfen kollidieren.
 * Deshalb gehört `quelle` zum Schlüssel.
 */
export function anfrageSchluessel(anfrage) {
  return `${anfrage?.quelle || 'buchung'}-${anfrage?.id ?? ''}`
}

/**
 * Die Moderatorenliste ohne die eigenen Anfragen.
 *
 * Eigene offene Anfragen stehen im Bereich „Eigene Anfragen“ (mit
 * Selbstfreigabe-Kennzeichnung) — dort, nicht doppelt in „Offene Anfragen“.
 * Erkannt wird die eigene Anfrage an `gebucht_von` (Serverangabe der
 * Moderatorenliste), nicht an der Kennung allein.
 */
export function anfragenAnderer(anfragen, eigenerNutzer) {
  const nutzer = String(eigenerNutzer || '')
  return (anfragen || []).filter(a => !(nutzer && a?.gebucht_von === nutzer))
}

/** Statuszeile, die nur offene Anfragen zählt (Kopfzahl am Bereich). */
export function zaehleOffene(anfragen) {
  return (anfragen || []).filter(a => a?.status === 'Angefragt').length
}
