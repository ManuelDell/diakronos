/**
 * UI-R3c — EIN Ladevorgang für `get_kalender_verwaltung`.
 *
 * BEFUND (Karte UI-R3c, MUSS 2): Auf der Kalenderseite fragten `Kalender.vue`
 * (für das ⋯-Menü) und `KronosSidebar.vue` (für ihren Menüpunkt) denselben
 * Endpunkt — zwei Anfragen mit derselben Antwort je Seitenaufbau; auf der
 * Verwaltungsseite fragten `KalenderVerwaltung.vue` und die gemeinsame Fläche
 * `KalenderEinstellungen.vue`. Zwei Antworten können ausserdem auseinander
 * fallen (die eine ist älter), und die zweite Anfrage kostet Zeit, in der die
 * Menüpunkte noch fehlen.
 *
 * REGEL: Diese Datei ist die EINE Stelle, die den Endpunkt ruft. Alle Anzeigen
 * lesen denselben Stand und dieselbe laufende Anfrage:
 *
 *   const { verwaltung, antwortDa, sperrt, laden, teilen } = useKalenderVerwaltung()
 *   laden()          holt (oder nimmt die laufende Anfrage) und setzt den Stand
 *   teilen(antwort)  übernimmt eine Antwort, die der Aufrufer selbst geholt
 *                    hat (die Verwaltungsseite braucht sie auch für die
 *                    Anlegeorte) — ohne zweite Anfrage
 *
 * `verwaltung` ist `null`, solange keine Antwort da ist — die Oberfläche zeigt
 * bis dahin NICHTS (kein Aufblitzen, kein „nichts zu verwalten“).
 *
 * `sperrt` ist das 403 des Servers: diese Person verwaltet nichts. Das ist
 * KEIN Fehler, sondern eine Lage (die Seite zeigt einen Satz statt Aktionen).
 *
 * UI-R3e (fail closed): Jeder andere Fehler setzt `fehler`, LEERT den Stand
 * und setzt `sperrt` zurück. Der alte Stand war einmal wahr — ist er es nicht
 * mehr, darf ihn keine Anzeige weiter zeigen (sonst stünde „Verwalten“ und
 * „Neuer Kalender“ für eine Lage, die niemandem mehr gehört). `laden()` gibt
 * dann `null` zurück.
 *
 * Zum Nachladen (`auffrischen`): eine Änderung an einem Kalender macht den
 * Stand veraltet. `laden({ frisch: true })` holt deshalb NEU, statt eine
 * laufende Anfrage zu teilen; ohne `frisch` gilt „eine Anfrage zur Zeit“ —
 * gleichzeitige Anzeigen starten keine zweite, und EINE ANTWORT IST SCHON DA:
 * dann wird gar nicht gefragt.
 *
 * UI-R3f (MUSS 1): Der BESITZER eines Seitenaufbaus (`pages/Kalender.vue`,
 * `pages/KalenderVerwaltung.vue`) lädt FRISCH; alle anderen Anzeigen (die
 * Leiste) lesen nur den reaktiven Stand. Damit gibt es genau EINE Anfrage je
 * Seitenbesuch — aber keine Antwort, die die ganze SPA-Sitzung überlebt.
 *
 * UI-R3e (Reihenfolge): jede Anfrage bekommt eine Nummer. Nur die jüngste
 * Antwort schreibt den Stand — eine ältere, die zuletzt eintrifft, wird
 * verworfen (sonst überschrieb sie nach einem Nachladen den neuen Stand).
 */
import { readonly, ref } from 'vue'

import { apiCall as apiAufruf } from './useApi.js'

/**
 * Der Aufruf selbst — EINE Stelle, damit ein Test ihn ersetzen kann, ohne
 * dieses Modul nachzubauen (die Seiten-Übersetzer der Tests ersetzen
 * `composables/useApi.js`; dieses Modul wird von ihnen NICHT übersetzt und
 * würde sonst den echten Endpunkt ansprechen).
 */
let api = apiAufruf

/**
 * NUR FÜR TESTS: den Endpunkt-Aufruf ersetzen (`null` = wieder der echte).
 * @param {null | ((methode: string, args?: object) => Promise<any>)} ersatz
 */
export function __setzeApiAufruf(ersatz) {
  api = ersatz || apiAufruf
}

/** Der Endpunkt (eine Schreibweise für alle Aufrufer). */
export const VERWALTUNG_METHODE = 'diakronos.kronos.api.kalender_verwaltung.get_kalender_verwaltung'

/** Der geteilte Stand — alle Anzeigen lesen ihn. */
const verwaltung = ref(null)
/** Ist schon EINE Antwort eingetroffen (auch eine Fehler- oder 403-Antwort)? */
const antwortDa = ref(false)
/** 403 des Servers: diese Person verwaltet keine Kalender. */
const sperrt = ref(false)
/** Fehlertext des letzten Fehlschlags (leer = keiner). */
const fehler = ref('')
/**
 * Wann der letzte Fehlschlag (403/Netzfehler) eintraf — `null`, solange keine
 * Antwort da ist. Ein Fehlschlag ist KEIN Stand: nach `FEHLSCHLAG_GEDULD_MS`
 * fragen die Anzeigen wieder (siehe `laden`), sonst könnte ein einzelner
 * Aussetzer das Verwalten bis zum nächsten Seitenaufbau verbergen.
 */
let fehlschlagAm = null

/** Wie lange ein Fehlschlag als „Antwort“ gilt, bevor neu gefragt wird. */
export const FEHLSCHLAG_GEDULD_MS = 5000

/** Die laufende Anfrage (geteilt) und ein Zähler, der sie identifiziert. */
let laufende = null
/**
 * UI-R3e: die Nummer der jüngsten gestarteten Anfrage. Nur ihre Antwort
 * schreibt den Stand; jede ältere gilt als überholt (auch wenn sie zuletzt
 * eintrifft).
 */
let juengste = 0

/**
 * Den Stand setzen — die EINE Stelle, die `verwaltung`/`antwortDa`/`sperrt`
 * schreibt. `null` heisst „keine Antwort“ (noch nicht geladen bzw. gesperrt).
 */
function setzeStand(daten) {
  verwaltung.value = daten || null
  sperrt.value = false
  fehler.value = ''
  fehlschlagAm = null
  antwortDa.value = true
}

/**
 * Antwort übernehmen, die der Aufrufer selbst geholt hat (Verwaltungsseite).
 * Das ist KEIN zweiter Aufruf — die Seite hat ohnehin gefragt.
 */
export function teilen(antwort) {
  // Eine geteilte Antwort ist der jüngste Stand: eine noch laufende Anfrage
  // darf ihn danach nicht überschreiben.
  juengste += 1
  if (!antwort) {
    // Keine Antwort (Netzfehler) ist KEIN Stand: der Stand bleibt leer, `sperrt`
    // wird zurückgesetzt, `fehler` bleibt für die Anzeige stehen (fail closed —
    // die Seite zeigt „nicht geladen“, ohne „Neuer Kalender“).
    verwaltung.value = null
    sperrt.value = false
    antwortDa.value = true
    fehlschlagAm = Date.now()
    return null
  }
  setzeStand(antwort)
  return verwaltung.value
}

/**
 * Den Stand holen. Ohne `frisch` wird eine LAUFENDE Anfrage geteilt (eine
 * Anfrage zur Zeit) — ist die Antwort schon da, wird nicht gefragt.
 *
 * UI-R3f (MUSS 1): Ein Besitzer (die Seite, die gerade aufgebaut wird) ruft
 * `laden({ frisch: true })`. Sonst hielte der geteilte Stand eine Antwort für
 * die GANZE SPA-Sitzung: nach Anlegen/Löschen über „Gruppe → Einstellungen“
 * zeigte „Kalender verwalten“ die alte Liste, und ein während der Sitzung
 * gegebenes oder genommenes Recht änderte den Eintrag erst nach einem vollen
 * Neuladen.
 *
 * Fehler werden NICHT geworfen — der Stand trägt sie (`sperrt` bei 403,
 * `fehler` sonst), damit jede Anzeige dieselbe Lage sieht und niemand einen
 * unbehandelten Fehler weiterreicht. Der Rückgabewert ist der neue Stand.
 *
 * @param {{frisch?: boolean}} [optionen]
 * @returns {Promise<object|null>}
 */
export async function laden({ frisch = false } = {}) {
  if (!frisch) {
    if (laufende) return laufende
    // UI-R3e: IST DIE ANTWORT SCHON DA, wird nicht noch einmal gefragt. Vorher
    // hing „einmal laden“ am Timing: die Kalenderliste (`KronosSidebar.vue`)
    // fragte erst nach `get_current_user_context`, die Seite
    // (`Kalender.vue`) erst nach `store.fetchAccessibleCalendars` — war die
    // erste Anfrage schon fertig, ging die zweite trotzdem raus.
    //
    // Nur ein FEHLSCHLAG (403 oder Netzfehler) ist keine Auskunft, auf die man
    // sich verlässt: nach `FEHLSCHLAG_GEDULD_MS` wird neu gefragt.
    if (antwortDa.value) {
      const alt = fehlschlagAm !== null && (Date.now() - fehlschlagAm) >= FEHLSCHLAG_GEDULD_MS
      if (!alt) return verwaltung.value
    }
  }
  // UI-R3e: diese Anfrage ist die jüngste — eine noch laufende ältere Antwort
  // schreibt danach nichts mehr.
  const nummer = (juengste += 1)
  const anfrage = (async () => {
    try {
      const antwort = await api(VERWALTUNG_METHODE)
      if (nummer !== juengste) return verwaltung.value
      setzeStand(antwort)
      return verwaltung.value
    } catch (err) {
      if (nummer !== juengste) return verwaltung.value
      // 403 = der Server gibt dieser Person nichts zu verwalten. Eine Lage,
      // kein Fehler: keine Meldung, nur ein leerer Stand.
      if (Number(err?.status) === 403) {
        verwaltung.value = null
        sperrt.value = true
        fehler.value = ''
        antwortDa.value = true
        fehlschlagAm = Date.now()
        return null
      }
      // UI-R3e (fail closed): der alte Stand wird GELEERT, nicht behalten —
      // er war einmal wahr, ist es nach diesem Fehlschlag nicht mehr belegt.
      // `sperrt` wird zurückgesetzt (dieser Ausgang ist kein 403).
      verwaltung.value = null
      sperrt.value = false
      fehler.value = String(err?.message || '').trim() || 'Die Kalender konnten nicht geladen werden.'
      antwortDa.value = true
      fehlschlagAm = Date.now()
      return null
    } finally {
      if (laufende === anfrage) laufende = null
    }
  })()
  laufende = anfrage
  return anfrage
}

/**
 * NUR FÜR TESTS: den geteilten Stand leeren (die Modulzustände überleben einen
 * Test; ohne diesen Griff zeigte der nächste Fall den Stand des vorigen).
 */
export function __leeren() {
  verwaltung.value = null
  antwortDa.value = false
  sperrt.value = false
  fehler.value = ''
  fehlschlagAm = null
  laufende = null
  juengste = 0
}

/**
 * Die Anzeige-Sicht (schreibgeschützt) — `laden`/`teilen` sind die Wege, den
 * Stand zu ändern.
 */
export function useKalenderVerwaltung() {
  return {
    verwaltung: readonly(verwaltung),
    antwortDa: readonly(antwortDa),
    sperrt: readonly(sperrt),
    fehler: readonly(fehler),
    laden,
    teilen,
  }
}
