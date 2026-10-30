/**
 * API-Zugriffe der Verwaltung (P2-5): Kalender und Ressourcen.
 *
 * Die Seite spricht NIRGENDS direkt `fetch` an — alles laeuft ueber `apiCall`
 * (eine Stelle fuer CSRF, Sitzungspruefung, Fehlerform). Fehlerantworten des
 * Servers tragen `message` (bei Strukturpruefungen zusaetzlich `meldungen`);
 * `serverFehlerText` macht daraus EINEN Satz, den ein Ehrenamtlicher lesen
 * kann — statt „HTTP 417“.
 *
 * Rechte kommen vom Server: die Funktionen hier fragen nicht, ob jemand darf,
 * sie rufen auf. Die Oberflaeche blendet nur aus, was der Server ohnehin
 * verweigert (Kalender: `Kalenderadministrator`, Ressourcen:
 * `Ressourcenmoderator`).
 */

import { readonly, ref } from 'vue'

import { apiCall } from './useApi.js'
import { useSession } from './useSession.js'

const KALENDER = 'diakronos.kronos.api.kalender_verwaltung'
const RESSOURCEN = 'diakronos.diakonos.api.ressourcen'
const DASHBOARD = 'diakronos.diakonos.api.dashboard'

/**
 * Fehlertext aus einer fehlgeschlagenen Anfrage (verstaendlich, deutsch).
 *
 * Reihenfolge: strukturierte Meldungen (`meldungen` aus der API) vor der
 * allgemeinen `message`, sonst ein neutraler Satz. Nichts wird geraten.
 */
export function serverFehlerText(err, fallback = 'Das hat nicht geklappt. Bitte noch einmal versuchen.') {
  const meldungen = Array.isArray(err?.meldungen) ? err.meldungen : []
  if (meldungen.length) {
    const teile = meldungen
      .map(m => (typeof m === 'string' ? m : (m?.meldung || m?.hinweis || '')))
      .filter(Boolean)
    if (teile.length) return teile.join(' ')
  }
  const text = String(err?.message || '').trim()
  // „HTTP 417“ o. ae. ist keine Meldung fuer Menschen.
  if (!text || /^HTTP \d+$/.test(text)) {
    if (err?.status === 403) return 'Dafür fehlt dir das Recht. Bitte die Gemeindeleitung fragen.'
    return fallback
  }
  return text
}

// ── Kalender (OP-ADMIN-10) ──────────────────────────────────────────────────

/** Alle Kalender mit Rechten und Moderatoren (nur Kalenderadministratoren). */
export async function kalenderVerwaltungLaden() {
  return apiCall(`${KALENDER}.get_kalender_verwaltung`)
}

/** Neuen Kalender anlegen. */
export async function kalenderAnlegen(daten) {
  return apiCall(`${KALENDER}.create_kalender`, daten)
}

/** Kalender aendern (nur mitgeschickte Felder). */
export async function kalenderAendern(name, daten) {
  return apiCall(`${KALENDER}.update_kalender`, { name, ...daten })
}

/** Kalender loeschen — der Server verweigert es, solange Termine daran haengen. */
export async function kalenderLoeschen(name) {
  return apiCall(`${KALENDER}.delete_kalender`, { name, bestaetigt: 1 })
}

// ── Ressourcen (OP-ADMIN-11) ────────────────────────────────────────────────

/** Alle Ressourcen in der Pflege-Sicht (Art, Kapazitaet, Tags, Wartung). */
export async function ressourcenVerwaltungLaden() {
  return apiCall(`${RESSOURCEN}.get_ressourcen_verwaltung`)
}

export async function ressourceAnlegen(daten) {
  return apiCall(`${RESSOURCEN}.create_ressource`, daten)
}

export async function ressourceAendern(id, daten) {
  return apiCall(`${RESSOURCEN}.update_ressource`, { ressource_id: id, ...daten })
}

export async function ressourceLoeschen(id) {
  return apiCall(`${RESSOURCEN}.delete_ressource`, { ressource_id: id, bestaetigt: 1 })
}

// ── Konten (Auswahl fuer Moderatoren) ───────────────────────────────────────

/**
 * Alle Benutzerkonten fuer Auswahlfelder — NUR Kennung und Anzeigename.
 *
 * Bewusst KONTEN und nicht Mitglieder: ein Kalender-Moderator ist eine
 * Person mit Konto (die Kind-Zeile zeigt auf `User.name`).
 *
 * R-P2-5 (klein 4): Der frueher benutzte `get_konten_liste` verlangt
 * „Mitgliederadministrator“ — ein reiner Kalenderadministrator (ohne diese
 * Rolle) konnte damit keinen Moderator auswaehlen. `get_moderator_auswahl`
 * verlangt nur eine Verwaltungsrolle und liefert KEINE E-Mail/keine Rollen.
 * Ohne Recht bleibt die Liste leer (fail closed).
 */
export async function kontenListe() {
  const antwort = await apiCall('diakronos.diakonos.api.zugang.get_moderator_auswahl')
  return Array.isArray(antwort?.konten) ? antwort.konten : []
}

// ── Kennzahlen (UXD-R18) ────────────────────────────────────────────────────
/**
 * Zaehler fuer die Seitenleiste. Liefert `{}`, wenn der Server die Zahl nicht
 * herausgibt (falsche Rolle) — die Leiste zeigt dann nichts an, was sie nicht
 * belegen kann.
 */
export async function navigationZaehler() {
  return apiCall(`${DASHBOARD}.get_navigation_zaehler`)
}

// ── Kennzahl „offene Anfragen“ — EIN Stand und EIN Takt (UX-A2a/A2a2) ──────
/**
 * Gemeinsamer Zaehler-Stand. Seitenleiste (Kennzahl an „Mitglieder“) und
 * Mitglieder-Bereichsliste (Kennzahl an „Anfragen“) lesen dieselbe Zahl aus
 * DERSELBEN Abfrage — sonst fragt die Oberflaeche den Server doppelt und
 * zeigt nach einer Aufnahme/Ablehnung zwei verschiedene Staende.
 *
 * `anfragen` ist `null`, solange der Server keine Zahl geliefert hat (falsche
 * Rolle, Fehler, noch nicht geladen) — nie eine erfundene 0.
 *
 * Takt: EIN Intervall fuer alle Anzeigen (`anfragenZaehlerBeobachten`), nicht
 * eines je Bauteil. Der Bereich liest nur; er fragt nicht selbst und holt
 * auch nicht bei jedem Wechsel neu (UX-A2a2 Punkt 3).
 */
const anfragenZahl = ref(null)

/** Nur die Zahl, schreibgeschuetzt (Anzeigen lesen). */
export const anfragenZaehler = readonly(anfragenZahl)

/** Zahl aus einer Serverantwort setzen (fehlender Schluessel → null). */
function setzeAnfragenZahl(antwort) {
  const roh = antwort && typeof antwort === 'object' ? antwort.anfragen : undefined
  const zahl = Number(roh)
  anfragenZahl.value = roh === undefined || roh === null || roh === '' || !Number.isFinite(zahl)
    ? null
    : zahl
}

// Der laufende Abruf wird geteilt: rufen zwei Anzeigen gleichzeitig, geht EINE
// Anfrage an den Server und beide bekommen dasselbe Ergebnis.
let laufendeAbfrage = null

/**
 * Zahl offener Anfragen holen (mit zwischengespeichertem Stand fuer alle).
 * Der Fehler bleibt still: eine Kennzahl darf die Navigation nicht stoeren.
 * @returns {Promise<number|null>}
 */
export async function anfragenZahlLaden() {
  if (!laufendeAbfrage) {
    laufendeAbfrage = navigationZaehler()
      .then((antwort) => { setzeAnfragenZahl(antwort); return anfragenZahl.value })
      .catch(() => { anfragenZahl.value = null; return null })
      .finally(() => { laufendeAbfrage = null })
  }
  return laufendeAbfrage
}

// ── EIN Takt fuer alle Anzeigen ────────────────────────────────────────────
/** Takt der Kennzahl in Millisekunden (eine Minute). */
export const ANFRAGEN_TAKT_MS = 60_000

// Der Server gibt die Zahl nur an Mitgliederadministratoren heraus (ohne
// Rolle fehlt der Schluessel ganz). Deshalb fragt die Oberflaeche auch nur
// dann — sonst liefe je Nutzer eine Anfrage in eine Absage.
let beobachter = 0
let taktTimer = null

/** Die Zahl einmal holen — nur mit Mitgliederadministrator-Recht. */
async function taktSchlag() {
  if (!istAnfragenAdmin()) return null
  return anfragenZahlLaden()
}

/**
 * Kennzahl beobachten: holt sie sofort und dann im gemeinsamen Takt.
 * Beliebig viele Anzeigen duerfen beobachten — es laeuft EIN Intervall und je
 * Takt EINE Anfrage. Das Ergebnis der Aufraeumfunktion entfernt nur den
 * eigenen Beobachter; das Intervall endet mit dem letzten.
 *
 * Rechte: ohne Mitgliederadministrator wird gar nicht gefragt (die Zahl
 * bleibt `null`, es wird nichts angezeigt).
 *
 * @returns {() => void} Aufraeumen (im `onUnmounted` des Bauteils aufrufen)
 */
export function anfragenZaehlerBeobachten() {
  beobachter += 1
  if (beobachter === 1) {
    taktSchlag()
    taktTimer = setInterval(taktSchlag, ANFRAGEN_TAKT_MS)
    // In Tests (und in einer Umgebung ohne Prozess) darf ein laufender Takt den
    // Lauf nicht offen halten; im Browser gibt es kein `unref`.
    if (typeof taktTimer?.unref === 'function') taktTimer.unref()
  }

  let abgemeldet = false
  return () => {
    if (abgemeldet) return
    abgemeldet = true
    beobachter = Math.max(0, beobachter - 1)
    if (beobachter === 0 && taktTimer) {
      clearInterval(taktTimer)
      taktTimer = null
    }
  }
}

/**
 * Kennzahl sofort neu holen — nach einer Handlung, die sie veraendert
 * (Anfrage aufnehmen/ablehnen), NICHT bei jedem Bereichswechsel.
 * Ohne Recht passiert nichts.
 */
export async function anfragenZahlAuffrischen() {
  return taktSchlag()
}

/**
 * Darf dieser Nutzer die Zahl sehen? Dieselbe Rolle, die der Server verlangt
 * (`get_navigation_zaehler`: Mitgliederadministrator oder System Manager).
 * Eigene Funktion, damit sie ohne Vue pruefbar ist.
 */
export function darfAnfragenZaehlerSehen({ isAdmin = false, istSystemManager = false } = {}) {
  return isAdmin === true || istSystemManager === true
}

/** Die Rechte des angemeldeten Nutzers (Laufzeit) — in Tests ersetzbar. */
let rechteQuelle = () => {
  const { isAdmin, istSystemManager } = useSession()
  return { isAdmin: isAdmin.value === true, istSystemManager: istSystemManager.value === true }
}

/** @returns {boolean} */
function istAnfragenAdmin() {
  try {
    return darfAnfragenZaehlerSehen(rechteQuelle())
  } catch {
    return false
  }
}

/**
 * NUR FUER TESTS: Rechte-Quelle ersetzen (`null` = wieder die Anmeldung).
 * Der Takt selbst bleibt davon unberuehrt.
 * @param {null | (() => {istAdmin?: boolean, istSystemManager?: boolean})} quelle
 */
export function __setzeAnfragenRechte(quelle) {
  rechteQuelle = quelle || (() => {
    const { isAdmin, istSystemManager } = useSession()
    return { isAdmin: isAdmin.value === true, istSystemManager: istSystemManager.value === true }
  })
}
