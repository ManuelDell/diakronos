/**
 * CHAT-6-UI-3 — EIN Merker für „darf diese Person Chat-Meldungen prüfen?“.
 *
 * WARUM ES DIESE DATEI GIBT (Review R2, MUSS 2): Der Reiter „Chat“ stand am
 * Kalender-Kopf, obwohl `pages/Kalender.vue` der Kopfzeile `chatRecht`/
 * `chatZahl` gar nicht gab — der Reiter war damit NUR über die Glocke
 * erreichbar.
 *
 * CHAT-6-UI-3 (Operator-Nachtrag): Der EINSTIEG fragt NICHT mehr die Liste.
 * Früher ging für jede Person beim Kalender-Aufbau `chat.meldungen_liste`
 * hinaus — auch für Normalnutzer, die dort nur ein 403 bekamen. Jetzt liest
 * der Merker `get_session_info().chat_moderieren` (Boolean, vom Rechte-Kern
 * `darf_chat_irgendwo_moderieren`). Folge:
 *
 *   * kein Recht → GAR KEIN Listen-Abruf (auch keine Zahl, auch kein Fehler);
 *   * Recht     → EINMAL `chat.meldungen_liste({stand: 'offen'})` für die
 *                 Zahl am Reiter.
 *
 * Die PRÜFSEITE (`pages/Moderation.vue`) fragt die Liste weiterhin selbst —
 * dort gehört die Arbeitsliste hin, nicht in den Merker.
 *
 * REGEL: Diese Datei ist die EINE Stelle, die den Einstieg entscheidet.
 *
 *   const { recht, zahl } = useChatPruefRecht()   // nur lesen (reaktiv)
 *   const lage = await pruefen()                 // Einstieg fragen, merken
 *   merken({ recht: false, zahl: null })         // Prüfseite: Antwort übernehmen
 *
 * WAS „GEMERKT“ HEISST
 *   `recht`: `true` = der Server meldet `chat_moderieren`, `false` = nein,
 *   `null` = noch keine Antwort.
 *   `zahl`: offene Meldungen aus der EINEN Listen-Antwort (`null` = unbekannt).
 *   Eine unbekannte Zahl ist keine 0 — der Reiter zeigt dann keine Zahl.
 *   `geprueft`: liegt eine ANTWORT vor (Recht ja/nein)? Nur dann darf eine
 *   Anzeige ohne eigenes Fragen auskommen.
 *
 * FEHLER SIND KEINE ANTWORT: Ein Netz- oder 5xx-Fehler beim Einstieg oder bei
 * der Zahl setzt weder `recht` noch die bekannte `zahl` — er hinterlässt
 * `fehler` (Klartext) und setzt `geprueft` NICHT. Der nächste Aufruf fragt
 * deshalb wieder; sonst versuchte die Sitzung es nach einem einzigen Aussetzer
 * nie wieder (SOLL 2 der Karte). Ein 403 auf die LISTE dagegen ist die
 * Antwort „nein“ und wird gemerkt.
 *
 * `zuruecksetzen()` gibt es NUR für Tests: die Modulzustände überleben einen
 * Testlauf, ohne den Griff zeigte der nächste Fall den Stand des vorigen.
 */
import { readonly, ref } from 'vue'

import { apiCall as apiAufruf } from './useApi.js'
import { offenZahl } from '../components/chat/meldung.mjs'

/**
 * Der Aufruf selbst — EINE Stelle, damit ein Test ihn ersetzen kann, ohne
 * dieses Modul nachzubauen (dieselbe Bauart wie `useKalenderVerwaltung.js`:
 * die Seiten-Übersetzer der Tests ersetzen `composables/useApi.js`, dieses
 * Modul wird von ihnen NICHT übersetzt).
 */
let api = apiAufruf

/**
 * NUR FÜR TESTS: den Endpunkt-Aufruf ersetzen (`null` = wieder der echte).
 * @param {null | ((methode: string, args?: object) => Promise<any>)} ersatz
 */
export function __setzeApiAufruf(ersatz) {
  api = ersatz || apiAufruf
}

/** Der Einstieg: trägt `chat_moderieren` (Rechte-Kern im Server). */
export const SITZUNG_METHODE = 'diakronos.kronos.api.permissions.get_session_info'

/** Die EINE Frage nach der Zahl — NUR nach einem „ja“ des Einstiegs. */
export const MELDUNGEN_METHODE = 'chat.meldungen_liste'

/** Die EINE Frage, die über den Reiter entscheidet. */
export const MELDUNGEN_PARAMETER = { stand: 'offen' }

/** `true`/`false` = Antwort des Servers, `null` = noch keine. */
const recht = ref(null)
/** Offene Meldungen aus der letzten Antwort (`null` = unbekannt). */
const zahl = ref(null)
/** Liegt eine ANTWORT über das Recht vor (ja oder nein)? */
const geprueft = ref(false)
/** Klartext des letzten Fehlschlags (leer = keiner) — kein Recht, keine Zahl. */
const fehler = ref('')

/** Die laufende Anfrage — zweiter Aufruf hängt sich an, statt neu zu fragen. */
let laufend = null

/**
 * Die Anzeige-Sicht (schreibgeschützt). Anzeigen lesen sie und fragen NICHT
 * selbst; sie zeigen den Reiter erst, wenn `recht === true`.
 *
 * `merken` und `zahlLaden` gibt es auch hier: der Kalender trägt die
 * Rechte-Antwort aus dem Boot-Objekt ein (kein `get_session_info`) und holt
 * danach nur noch die Zahl (CHAT-6-UI-3, Review R1/SOLL 1).
 */
export function useChatPruefRecht() {
  return {
    recht: readonly(recht),
    zahl: readonly(zahl),
    geprueft: readonly(geprueft),
    fehler: readonly(fehler),
    pruefen,
    merken,
    zahlLaden,
  }
}

/** Ein 403 ist die Antwort „nein“ — alles andere ist KEINE Rechtelage. */
function istVerbot(err) {
  return Number(err?.status) === 403
}

/**
 * Den Einstieg fragen (und bei „ja“ EINMAL die Zahl).
 *
 * @param {{frisch?: boolean}} [lage]
 *   `frisch: true` = immer fragen (die Prüfseite: dort entscheidet die
 *   Antwort dieses Besuchs). Ohne `frisch` gilt eine vorhandene ANTWORT —
 *   nur die ERSTE Frage geht hinaus, jede weitere Seite liest denselben
 *   Stand (kein Abruf bei jedem Rendern). Ein Fehlschlag ist keine Antwort:
 *   dort fragt der nächste Aufruf wieder.
 * @returns {Promise<{recht: boolean|null, zahl: number|null, fehler: string}>}
 */
export async function pruefen({ frisch = false } = {}) {
  if (!frisch && geprueft.value) return stand()
  // Eine laufende Frage wird geteilt — der Kalender fragt beim Aufbau, die
  // Prüfseite kann kurz danach öffnen; zwei Anfragen für dieselbe Antwort
  // wären genau der Doppelabruf, den die Karte verbietet.
  if (laufend) return laufend
  laufend = (async () => {
    let rechtAntwort = null
    try {
      const info = await api(SITZUNG_METHODE)
      rechtAntwort = info?.chat_moderieren === true
      recht.value = rechtAntwort
      fehler.value = ''
    } catch (err) {
      if (istVerbot(err)) {
        // 403 ist die Antwort „nein“ — sie wird gemerkt.
        rechtAntwort = false
        recht.value = false
        zahl.value = null
        fehler.value = ''
      } else {
        // Alles andere ist KEINE Antwort über Rechte — `geprueft` bleibt
        // false, damit der nächste Aufruf es erneut versucht.
        fehler.value = String(err?.message || '').trim()
      }
    }
    if (rechtAntwort === null) {
      laufend = null
      return stand()
    }
    geprueft.value = true
    // Zahl NUR mit Recht — ohne Recht gibt es keinen Listen-Abruf.
    if (rechtAntwort) await zahlLaden()
    laufend = null
    return stand()
  })()
  return laufend
}

/**
 * Die Zahl der offenen Meldungen EINMAL holen (nur mit Recht). Ein Fehler
 * lässt die zuletzt bekannte Zahl stehen (`null` bleibt unbekannt) — eine
 * Kennzahl stört den Kalender nicht.
 *
 * Exportiert, weil der Kalender die Rechte-Antwort aus dem Boot-Objekt trägt
 * (CHAT-6-UI-3, Review R1/SOLL 1) und danach NUR noch die Zahl braucht.
 */
export async function zahlLaden() {
  try {
    const daten = await api(MELDUNGEN_METHODE, MELDUNGEN_PARAMETER)
    recht.value = true
    zahl.value = offenZahl(daten)
    fehler.value = ''
  } catch (err) {
    if (istVerbot(err)) {
      // Das Recht ist in der Zwischenzeit weggefallen (403 auf die Liste).
      recht.value = false
      zahl.value = null
      return
    }
    fehler.value = String(err?.message || '').trim()
  }
}

/**
 * Eine Antwort der Prüfseite übernehmen (nach einer Entscheidung: die Zahl
 * ändert sich) — ohne neue Anfrage. `recht` bleibt, wo es ist, wenn das Feld
 * fehlt.
 *
 * @param {{recht?: boolean, zahl?: number|null}} lage
 */
export function merken(lage = {}) {
  if (typeof lage.recht === 'boolean') recht.value = lage.recht
  if (lage.zahl !== undefined) {
    // `null`/fehlend heißt UNBEKANNT — nicht 0 (`Number(null)` wäre 0 und der
    // Reiter behauptete „nichts offen“).
    if (lage.zahl === null) {
      zahl.value = null
    } else {
      const n = Number(lage.zahl)
      zahl.value = Number.isFinite(n) ? n : null
    }
  }
  geprueft.value = true
}

/** Der aktuelle Stand als einfaches Objekt. */
function stand() {
  return { recht: recht.value, zahl: zahl.value, fehler: fehler.value }
}

/**
 * NUR FÜR TESTS: den Merker leeren. Die Modulzustände überleben den Testlauf —
 * der Hilfszugriff auf den Inhalt jeder Seite, die den Stand liest, bleibt
 * allein die Anzeige-Sicht (`useChatPruefRecht`) plus `pruefen`/`merken`.
 */
export function zuruecksetzen() {
  recht.value = null
  zahl.value = null
  geprueft.value = false
  fehler.value = ''
  laufend = null
}
