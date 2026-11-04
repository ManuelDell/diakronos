/**
 * ON-3b — Leitungsregel der Ersteinrichtung (Orchestrator-Nachtrag 2026-11-03).
 *
 * DER ASSISTENT IST KEINE DAUERHAFTE SEITE. Er ist die Ersteinrichtung des
 * Containers und existiert nur, solange sie läuft. Deshalb steht die Regel
 * hier EINMAL, importfrei (wie `fenstertitel.js`): der Router wendet sie an,
 * der Test kann sie ohne DOM ausführen.
 *
 * Die drei Fälle:
 *
 *  1. OFFEN (`einrichtung_offen === true`) + Admin + noch nicht gefragt →
 *     beim Öffnen der App auf `#/einrichtung`. „Einmal pro Sitzung“: hat der
 *     Admin „Speichern und später fortsetzen“ gedrückt, ist die Sitzung
 *     bedient (`EINRICHTUNG_GESEHEN`) und er wird NICHT wieder gegriffen;
 *     beim nächsten Login ist der Merker weg und er kommt wieder.
 *  2. ABGESCHLOSSEN (`einrichtung_offen === false`) → `#/einrichtung` gibt es
 *     für die Bedienung nicht mehr: die Adresse leitet auf `#/einstellungen`
 *     (dort stehen die offenen Punkte).
 *  3. Es gibt keine Admin-Zeile (`null` = unbekannt): nur Fall 2 entfällt,
 *     es wird NIE geleitet — eine unbekannte Auskunft darf niemanden
 *     festhalten (dieselbe Regel wie bei den fehlenden Server-Schritten).
 *
 * Rollen: die Leitung gilt NUR für Admins (`is_admin`); für alle anderen ist
 * der Assistent ohnehin gesperrt (Router-Guard + Server 403).
 */

/** Adresse des Assistenten (nur während der Ersteinrichtung). */
export const EINRICHTUNG_ROUTE = '#/einrichtung'

/** Ziel nach dem Abschluss der Ersteinrichtung. */
export const EINRICHTUNG_ZIEL_NACH_ABSCHLUSS = '#/einstellungen'

/** Sitzungs-Merker: „der Assistent wurde in dieser Sitzung schon gezeigt“. */
export const EINRICHTUNG_GESEHEN = 'dk-einrichtung-gesehen'

/**
 * Soll die aktuelle Adresse auf den Assistenten umgeleitet werden?
 *
 * @param {{pfad: string, hash: string, boot: object, gesehen: boolean}} lage
 *   `pfad`     Adresse ohne Abfrageteil/Endschrägstrich (`#/`, `#/diakonos` …)
 *   `hash`     voller Hash (mit Abfrage)
 *   `boot`     `window.__DIakonosBOOT`
 *   `gesehen`  Merker dieser Sitzung
 * @returns {string|null} Ziel oder `null`
 */
export function einrichtungsWeiterleitung({ pfad, hash, boot, gesehen }) {
  const b = boot || {}
  if (b.is_admin !== true) return null
  // Geschlossen: der Assistent ist kein Dauerzustand. Seine Adresse (Lesezeichen,
  // alter Link, Verlauf) führt zu den Einstellungen, wo die offenen Punkte
  // stehen. Das gilt VOR der „schon gesehen“-Prüfung: der Merker betrifft nur
  // das Hinführen, nicht das Verschwinden der Seite.
  if (b.einrichtung_offen === false) {
    return pfad === EINRICHTUNG_ROUTE ? EINRICHTUNG_ZIEL_NACH_ABSCHLUSS : null
  }
  // Hängt schon am Assistenten? Dann nichts tun (kein Kreisel).
  if (pfad === EINRICHTUNG_ROUTE) return null
  // Offen: Admin beim Öffnen der App zum Assistenten — einmal pro Sitzung.
  if (b.einrichtung_offen === true) {
    return gesehen === true ? null : EINRICHTUNG_ROUTE
  }
  // Unbekannt: nichts anfassen.
  void hash
  return null
}

export function einrichtungSeiteErlaubt(boot) {
  const b = boot || {}
  if (b.is_admin !== true) return false
  // `null`/fehlend = unbekannt → Seite zeigen (der Server entscheidet erneut).
  return b.einrichtung_offen !== false
}

/** Merker dieser Sitzung lesen/schreiben (Fehler dürfen nichts anhalten). */
export function einrichtungGesehen(speicher) {
  try {
    return speicher?.getItem(EINRICHTUNG_GESEHEN) === '1'
  } catch {
    return false
  }
}

export function merkeEinrichtungGesehen(speicher) {
  try {
    speicher?.setItem(EINRICHTUNG_GESEHEN, '1')
  } catch { /* gesperrter Speicher: dann greift die Leitung eben erneut */ }
}
