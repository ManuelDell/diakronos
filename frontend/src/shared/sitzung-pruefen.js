/**
 * OP-UI-1 — zentrale Sitzungs- und Fehlerprüfung für eigenständige Oberflächen.
 *
 * Warum: Der Hauptbereich (`diakonos`) hat die Prüfung in
 * `composables/useApi.js` (`apiAntwortPruefen`). Die eigenständigen Bundles
 * `organigramm`, `registrierung` und `gast` laden jedoch ohne Vue-Router,
 * Pinia und ohne die Arbeitsseiten-Hüllen. Vorher antworteten sie auf eine
 * abgelaufene Sitzung mit `throw new Error(res.status)` — die Person sah nur
 * „403" und hielt es für entzogene Rechte (genau der OP-UI-1-Befund).
 *
 * Diese Datei bringt dieselbe Unterscheidung ohne Abhängigkeiten zu Vue:
 * eine abgelaufene Anmeldung (401/419, CSRF-Ablauf) führt zur Anmelde-Maske
 * mit Rücksprung auf die aktuelle Adresse, ein Rechtefehler bleibt sichtbar,
 * alle übrigen Fehler werden in Klartext übersetzt.
 *
 * Der Hauptbereich nutzt weiter `useApi.js`; beide Wege benutzen aber
 * dieselben Regeln (`istSitzungsAbbruch`) und denselben Ersatztext, damit
 * es nur EINE Wahrheit gibt.
 */

/** Serverzeichen für „nicht mehr angemeldet" (S14). */
export const SITZUNGS_STATUS = [401, 419]

/** Klartext, wenn der Server keinen brauchbaren Text mitliefert (S6). */
export const ALLGEMEINER_FEHLERTEXT =
  'Das hat nicht geklappt. Bitte versuche es später noch einmal.'

/**
 * Ist die Antwort ein Sitzungsabbruch? Neben 401/419 zählt auch der
 * CSRF-Ablauf (417 + `CSRFTokenError`) — der alte Token ist dann wertlos.
 */
export function istSitzungsAbbruch(status, data) {
  if (SITZUNGS_STATUS.includes(status)) return true
  return status === 417 && String(data?.exc_type || '') === 'CSRFTokenError'
}

/** Ziel der Anmeldemaske: aktuelle Adresse samt Hash, damit nichts verloren geht. */
export function anmeldeZiel() {
  const pfad = globalThis.location?.pathname || ''
  const suche = globalThis.location?.search || ''
  const hash = globalThis.location?.hash || ''
  return '/login?redirect-to=' + encodeURIComponent(pfad + suche + hash)
}

/**
 * Antwort robust lesen. Ein Proxy (500/502) liefert kein JSON; ein blindes
 * `res.json()` würde hier „Unexpected token …" werfen (UXD-R8).
 */
export async function liesAntwort(res) {
  let text = ''
  try {
    text = await res.text()
  } catch {
    return { message: `Serverfehler (HTTP ${res.status})` }
  }
  if (!text) return { message: `Serverfehler (HTTP ${res.status})` }
  try {
    return JSON.parse(text)
  } catch {
    return { message: `Serverfehler (HTTP ${res.status})` }
  }
}

/** Fehlertext aus einer Antwort in Klartext (S6, OP-UI-15). */
export function fehlerText(data, status) {
  const text = typeof data?.message === 'string' ? data.message.trim() : ''
  if (text && text !== 'Fehler' && text !== 'Unbekannter Fehler') return text
  const exc = typeof data?.exc === 'string' ? data.exc.trim() : ''
  if (exc) return exc
  return status ? `Serverfehler (HTTP ${status})` : ALLGEMEINER_FEHLERTEXT
}

/**
 * Prüft eine Antwort zentral.
 *
 * @param {Response} res
 * @param {{weiterleiten?: boolean}} optionen
 *   weiterleiten=true (Standard): bei Sitzungsabbruch zur Anmeldemaske
 *   navigieren und einen SitzungsFehler werfen. `false` gibt den Zustand nur
 *   zurück, wenn die jeweilige Maske selbst reagieren will.
 * @returns {Promise<object>} die gelesenen Daten bei Erfolg
 * @throws {SitzungsFehler|Error}
 */
export async function antwortPruefen(res, { weiterleiten = true } = {}) {
  const data = await liesAntwort(res)
  if (istSitzungsAbbruch(res.status, data)) {
    if (weiterleiten && globalThis.location) {
      globalThis.location.assign(anmeldeZiel())
    }
    throw new SitzungsFehler()
  }
  if (!res.ok) {
    const fehler = new Error(fehlerText(data, res.status))
    fehler.status = res.status
    fehler.meldungen = Array.isArray(data?.meldungen) ? data.meldungen : []
    throw fehler
  }
  if (data && typeof data === 'object' && data.exc) {
    throw new Error(String(data.exc))
  }
  return data
}

/** Eigener Typ, damit Aufrufer den Sitzungsabbruch von Fachfehlern trennen. */
export class SitzungsFehler extends Error {
  constructor() {
    super('Deine Anmeldung ist abgelaufen. Bitte melde dich neu an.')
    this.name = 'SitzungsFehler'
    this.sitzung = true
  }
}
