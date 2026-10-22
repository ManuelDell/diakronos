/**
 * Dev-Modus (DM1) — gebündelter Zugriff auf die Dev-Modus-Endpunkte.
 *
 * Alle Aufrufe laufen über `apiCall` (CSRF, Sitzung, Fehlerbehandlung an EINER
 * Stelle). Der Zustand "Dev-Modus an/aus" wird im Browser gemerkt
 * (localStorage) und beim Start mit dem Server abgeglichen — verbindlich ist
 * immer der Server.
 */

import { ref } from 'vue'

import { apiCall } from '../composables/useApi.js'

const PRAEFIX = 'diakronos.devmodus.api.'
const SCHLUESSEL = 'dk-devmodus-an'

/** Reaktiver Zustand, den App.vue und die Seiten teilen. */
export const devmodusAn = ref(false)
export const devmodusKuerzel = ref('Strg+Shift+F')
export const sttVerfuegbar = ref(false)

/** Merkt den Wunschzustand im Browser (nicht die Wahrheit — die kommt vom Server). */
export function wunschSetzen(an) {
  try {
    if (an) localStorage.setItem(SCHLUESSEL, '1')
    else localStorage.removeItem(SCHLUESSEL)
  } catch { /* Speicher kann gesperrt sein (Privatmodus) */ }
}

export function wunschLesen() {
  try { return localStorage.getItem(SCHLUESSEL) === '1' } catch { return false }
}

export function zustandSetzen(an, kuerzel, stt) {
  devmodusAn.value = Boolean(an)
  if (kuerzel) devmodusKuerzel.value = kuerzel
  if (stt !== undefined) sttVerfuegbar.value = Boolean(stt)
  wunschSetzen(Boolean(an))
}

function ruf(methode, args = {}) {
  return apiCall(PRAEFIX + methode, args)
}

/**
 * URL eines Befund-Bildes (UXM-R12).
 *
 * NICHT ``/files/<pfad>``: dort verlangt die Freigabe eine ``File``-Zeile, die
 * es fuer Befund-Bilder nie gibt (das war der 404 aus der Nachtpruefung).
 * Stattdessen der Dev-Modus-Endpunkt, der die Dev-Rechte prueft.
 */
export function bildUrl(pfad) {
  return '/api/method/' + PRAEFIX + 'bild?pfad=' + encodeURIComponent(String(pfad))
}

/** Fehlermeldungen (pfad/code/meldung/hinweis) lesbar machen. */
export function fehlerZeilen(fehler) {
  const meldungen = fehler?.meldungen
  if (Array.isArray(meldungen) && meldungen.length) {
    return meldungen.map(m =>
      [m.pfad, m.meldung, m.hinweis].filter(Boolean).join(' — '))
  }
  return [fehler?.message || 'Unbekannter Fehler']
}

export const devmodusApi = {
  uebersicht: () => ruf('uebersicht'),
  sitzungStatus: () => ruf('sitzung_status'),
  sitzungStarten: () => ruf('sitzung_starten'),
  sitzungBeenden: () => ruf('sitzung_beenden'),
  ereignisse: (seitSekunden = 60) => ruf('ereignisse_holen', { seit_sekunden: seitSekunden }),
  befunde: (filter = {}) => ruf('befunde_holen', filter),
  befundHolen: (name) => ruf('befund_holen', { name }),
  befundSpeichern: (daten) => ruf('befund_speichern', daten),
  befundSetzen: (name, status) => ruf('befund_setzen', { name, status }),
  befundLoeschen: (name) => ruf('befund_loeschen', { name }),
  bildHochladen: (daten, typ) => ruf('bild_hochladen', { daten, typ }),
  audioHochladen: (daten, typ) => ruf('audio_hochladen', { daten, typ }),
  berichtErzeugen: () => ruf('bericht_erzeugen'),
}

/**
 * Beim Start: den Serverzustand holen. Ist der Dev-Modus eingeschaltet UND der
 * Nutzer berechtigt, wird der Overlay-Code geladen (App.vue). Ohne Schalter
 * antwortet der Endpunkt 404 — das ist der Normalfall und kein Fehler.
 */
export async function devmodusPruefen() {
  try {
    const daten = await devmodusApi.uebersicht()
    devmodusKuerzel.value = daten?.kuerzel || 'Strg+Shift+F'
    sttVerfuegbar.value = Boolean(daten?.stt)
    devmodusAn.value = Boolean(daten?.sitzung)
    return daten
  } catch {
    devmodusAn.value = false
    return null
  }
}

/** Automatisch wieder einschalten, wenn der Nutzer es zuletzt an hatte. */
export async function devmodusAutostart() {
  const daten = await devmodusPruefen()
  if (!daten) return null
  if (wunschLesen() && !daten.sitzung) {
    try {
      await devmodusApi.sitzungStarten()
      devmodusAn.value = true
    } catch { /* Rechte fehlen jetzt: nicht erzwingen. */ }
  }
  return daten
}
