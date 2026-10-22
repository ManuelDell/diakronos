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

import { apiCall } from './useApi.js'

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
