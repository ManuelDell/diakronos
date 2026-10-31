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
 *
 * WEB-8c (R10): die Regel selbst steht in `shared/csrf-heilung.js`. Diese
 * Datei importiert sie nur noch und reicht sie weiter — der Zirkel
 * `csrf-heilung.js` <-> `sitzung-pruefen.js` ist damit aufgelöst (die Heilung
 * braucht die Sitzungsprüfung nicht mehr).
 */

/** Serverzeichen für „nicht mehr angemeldet" (S14). */
// WEB-5b: Anmeldemaske unter dem Betriebs-Praefix (DIAKRONOS_BASE_PATH).
import { anmeldeUrl } from './basis.js'
// WEB-8b: CSRF-Ablehnung automatisch heilen (Token neu, 1 Wiederholung, dann
// Force-Refresh mit 60-s-Schleifenschutz) — EINE Wahrheit für alle Aufrufer.
// Der Import ist absichtlich ein Namensraum (kein Destrukturieren), damit ein
// fehlender Name NICHT als toter Zweig durchrutscht (ein solcher Import bricht
// sofort ab — belegt in `tests/web8d-csrf-gastseiten.test.mjs` und
// `tests/web8b-csrf-heilung.test.mjs`) und der Zirkel trotzdem weg ist: die
// Heilung importiert diese Datei nicht mehr.
// WEB-8d (N5): `istCsrfAblehnung` und `SITZUNGS_STATUS` werden ebenfalls nur
// noch weitergereicht, statt hier kopiert zu werden.
import * as heilung from './csrf-heilung.js'

export const istSitzungsAbbruch = heilung.istSitzungsAbbruch
// WEB-8d (N5): die CSRF-Regel und die Statusliste kommen AUS der Heilung —
// vorher stand die Bedingung hier zeichengleich noch einmal.
export const istCsrfAblehnung = heilung.istCsrfAblehnung
export const SITZUNGS_STATUS = heilung.SITZUNGS_STATUS
const heileOderMelde = heilung.heileOderMelde
const datenVon = heilung.datenVon
const GRUND_CSRF = heilung.GRUND_CSRF

/** Klartext, wenn der Server keinen brauchbaren Text mitliefert (S6). */
export const ALLGEMEINER_FEHLERTEXT =
  'Das hat nicht geklappt. Bitte versuche es später noch einmal.'

/** Ziel der Anmeldemaske: aktuelle Adresse samt Hash, damit nichts verloren geht. */
export function anmeldeZiel() {
  const pfad = globalThis.location?.pathname || ''
  const suche = globalThis.location?.search || ''
  const hash = globalThis.location?.hash || ''
  return anmeldeUrl(pfad + suche + hash, GRUND_CSRF)
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
    return { message: `Serverfehler (HTTP ${res?.status})` }
  }
  if (!text) return { message: `Serverfehler (HTTP ${res?.status})` }
  try {
    return JSON.parse(text)
  } catch {
    return { message: `Serverfehler (HTTP ${res?.status})` }
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
 * WEB-8b: Kommt eine CSRF-Ablehnung (417 + `CSRFTokenError`), wird sie NICHT
 * sofort als Sitzungsende behandelt, sondern über `shared/csrf-heilung.js`
 * geheilt (frisches Token + genau eine Wiederholung, sonst Force-Refresh).
 *
 * WEB-8c (R2): die schon gelesene Antwort wird MITGEGEBEN (`res`/`data`), damit
 * die Heilung nicht noch einmal `anfrage()` ausführt. Aufrufer, die ihren
 * Aufruf erst hier machen lassen, lassen `res` weg.
 *
 * @param {Response} [res] die gelesene Antwort (fehlt sie, wird `anfrage()`
 *   genau einmal ausgeführt)
 * @param {{weiterleiten?: boolean, anfrage?: () => Promise<Response>,
 *          data?: object}} optionen
 *   weiterleiten=true (Standard): bei Sitzungsabbruch zur Anmeldemaske
 *   navigieren und einen SitzungsFehler werfen. `false` gibt den Zustand nur
 *   zurück, wenn die jeweilige Maske selbst reagieren will.
 *   `anfrage` (optional): erlaubt die CSRF-Heilung; fehlt sie, bleibt es beim
 *   bisherigen Verhalten (Weiterleitung zur Anmeldung).
 * @returns {Promise<object>} die gelesenen Daten bei Erfolg
 * @throws {SitzungsFehler|Error}
 */
export async function antwortPruefen(res, { weiterleiten = true, anfrage = null, data } = {}) {
  if (!res) res = await anfrage()
  if (data === undefined) data = await datenVon(res)

  // WEB-8b: CSRF zuerst — `istSitzungsAbbruch` zählt ihn mit, hier wird er
  // aber geheilt statt gemeldet (siehe shared/csrf-heilung.js).
  if (anfrage && istCsrfAblehnung(res, data)) {
    const ergebnis = await heileOderMelde({ anfrage, res, data })
    res = ergebnis.res
    data = ergebnis.data
  }

  return pruefeErgebnis(res, data, weiterleiten)
}

/** Auswertung einer (ggf. wiederholten) Antwort — ohne CSRF-Sonderweg. */
function pruefeErgebnis(res, data, weiterleiten) {
  if (istSitzungsAbbruch(res.status, data)) {
    // Ein CSRF-Ablauf ist an dieser Stelle NICHT mehr heilbar (die Heilung
    // lief vorher und hat aufgegeben) -> `neuLaden` kennzeichnet den Fall für
    // die Aufrufer (R8).
    const neuLaden = res.status === 417
    if (weiterleiten && globalThis.location) {
      globalThis.location.assign(anmeldeZiel())
    }
    throw new SitzungsFehler({ neuLaden })
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

/**
 * Eigener Typ, damit Aufrufer den Sitzungsabbruch von Fachfehlern trennen.
 *
 * Traegt `sitzung` (immer) sowie `neuLaden` bzw. `weitergeleitet` — damit
 * Gast-/Registrierungsseiten (WEB-8c R8) nichts rendern, während navigiert
 * wird: es erscheint kein „Verbindungsfehler" vor dem Seitenwechsel.
 */
export class SitzungsFehler extends Error {
  constructor({ neuLaden = false } = {}) {
    super('Deine Anmeldung ist abgelaufen. Bitte melde dich neu an.')
    this.name = 'SitzungsFehler'
    this.sitzung = true
    if (neuLaden) this.neuLaden = true
    else this.weitergeleitet = true
  }
}
