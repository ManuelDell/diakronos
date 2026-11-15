/**
 * UI-R3c/UI-R3g — EIN Ladevorgang für `get_kalender_verwaltung`.
 *
 * WARUM ES DIESE DATEI GIBT: Auf der Kalenderseite fragten `Kalender.vue`
 * (für das ⋯-Menü) und `KronosSidebar.vue` (für ihren Menüpunkt) denselben
 * Endpunkt; auf der Verwaltungsseite taten es `KalenderVerwaltung.vue` und die
 * gemeinsame Fläche `KalenderEinstellungen.vue` (UI-R3c, MUSS 2). Zwei
 * Antworten können auseinander fallen, und die zweite Anfrage kostet Zeit, in
 * der die Menüpunkte noch fehlen.
 *
 * REGEL: Diese Datei ist die EINE Stelle, die den Endpunkt ruft. Je
 * Seitenbesuch fragt genau EIN Besitzer — `pages/Kalender.vue` bzw.
 * `pages/KalenderVerwaltung.vue` — mit `laden()`; alle Anzeigen lesen nur den
 * reaktiven Stand:
 *
 *   const { verwaltung, antwortDa, sperrt, fehler, saet } = useKalenderVerwaltung()
 *   laden()                   holt eine frische Antwort und schreibt den Stand
 *
 * Es gibt KEINEN zweiten Weg mehr (UI-R3g, SOLL 3): `teilen()` (eine vom
 * Aufrufer geholte Antwort einspeisen) und der nicht-frische Zweig von
 * `laden()` („nimm die laufende Anfrage, oder die Antwort ist schon da“)
 * hatten keinen Betriebsaufruf. Jeder Aufruf holt NEU — der Stand trägt immer
 * die Antwort eines Besitzers.
 *
 * `verwaltung` ist `null`, solange keine Antwort da ist — die Oberfläche zeigt
 * bis dahin NICHTS (kein Aufblitzen, kein „nichts zu verwalten“).
 *
 * `sperrt` ist das 403 des Servers: diese Person verwaltet nichts. Das ist
 * KEIN Fehler, sondern eine Lage (die Seite zeigt einen Satz statt Aktionen).
 *
 * UI-R3e (fail closed): Jeder andere Fehler setzt `fehler`, LEERT den Stand
 * und setzt `sperrt` zurück. Der alte Stand war einmal wahr — ist er es nicht
 * mehr, darf ihn keine Anzeige weiter zeigen. `laden()` gibt dann `null`
 * zurück.
 *
 * UI-R3g (MUSS 1b): `aktuellerSatz()` beginnt einen Seitenbesuch. Ab da trägt
 * der geteilte Stand die Antwort des VORIGEN Besuchs — `gehoertZu(satz)` sagt
 * Anzeigen, ob die Antwort zu ihrem Besuch gehört. Nur so ist der Eintrag
 * „Kalender verwalten“ weg, sobald jemand die Seite neu betritt, statt bis zur
 * frischen Antwort aus dem alten Recht zu stehen.
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

/**
 * UI-R3g (SOLL 4): Kennung für eine ÜBERHOLTE Ladung. `laden()` gibt sie
 * zurück, wenn eine jüngere Anfrage inzwischen läuft bzw. den Stand
 * geschrieben hat — die Antwort der älteren darf dann weder den Stand noch
 * eine Seite verändern (sie könnte älter sein als der geteilte Stand).
 */
export const UEBERHOLT = Symbol.for('diakonos.kalenderVerwaltung.ueberholt')

/** Ist das Ergebnis von `laden()` ein „überholt“ (nichts übernehmen)? */
export function ueberholt(ergebnis) {
  return ergebnis === UEBERHOLT
}

/** Der Endpunkt (eine Schreibweise für alle Aufrufer). */
export const VERWALTUNG_METHODE = 'diakronos.kronos.api.kalender_verwaltung.get_kalender_verwaltung'

/** Der geteilte Stand — alle Anzeigen lesen ihn. */
const verwaltung = ref(null)
/** Ist schon EINE Antwort eingetroffen (auch eine Fehler- oder 403-Antwort)? */
const antwortDa = ref(false)
/**
 * UI-R3g (MUSS 1b): der SATZ des laufenden Seitenbesuchs. Jeder Besitzer ruft
 * `aktuellerSatz()` VOR seiner Anfrage; die Anzeigen zeigen „Verwalten“ nur,
 * wenn die Antwort zu diesem Satz gehört — der geteilte Stand trägt bis dahin
 * die Antwort des vorigen Besuchs.
 */
const saet = ref(0)
/** 403 des Servers: diese Person verwaltet keine Kalender. */
const sperrt = ref(false)
/** Fehlertext des letzten Fehlschlags (leer = keiner). */
const fehler = ref('')
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
  antwortDa.value = true
}

/**
 * UI-R3g (MUSS 1b): einen neuen Seitenbesuch beginnen — NUR der Besitzer
 * (`pages/Kalender.vue`, `pages/KalenderVerwaltung.vue`) ruft das, unmittelbar
 * bevor er seine (frische) Anfrage startet. Ab hier gilt der geteilte Stand
 * als „Antwort eines FRÜHEREN Besuchs“: Anzeigen blenden den Eintrag aus, bis
 * die Antwort zu DIESEM Satz da ist. Es ist kein Netzaufruf — die eine
 * Anfrage je Besuch bleibt die eine.
 *
 * @returns {number} der Satz, den der Aufrufer an `gehoertZu()` gibt
 */
export function aktuellerSatz() {
  // Der neue Besuch entwertet die Antwort des vorigen SOFORT — für alle, die
  // den geteilten Stand lesen (`gehoertZu`): „Antwort da“ und „Satz“ gehören
  // zusammen, sonst gälte der alte Stand noch als Antwort.
  antwortDa.value = false
  saet.value += 1
  return saet.value
}

/**
 * Gehört die Antwort im geteilten Stand zu diesem Satz? Nur dann darf eine
 * Anzeige „Verwalten“ zeigen. Eine Antwort ist nur ein STAND, wenn sie Daten
 * trägt: ein 403 oder ein Fehlschlag hinterlässt `null` — der Eintrag war aus
 * und bleibt es (`kalenderVerwaltungSichtbar(null)` ist ebenfalls `false`).
 *
 * @param {number} satz — Ergebnis von `aktuellerSatz()`
 * @returns {boolean}
 */
export function gehoertZu(satz) {
  return Number.isFinite(Number(satz))
    && antwortDa.value
    && verwaltung.value !== null
    && saet.value === Number(satz)
}

/**
 * Den Stand FRISCH holen — der EINE Weg (UI-R3g, SOLL 3).
 *
 * Ein Besitzer (`pages/Kalender.vue`, `pages/KalenderVerwaltung.vue`) beginnt
 * seinen Besuch mit `aktuellerSatz()` und ruft dann `laden()`.
 * Jede Ladung bekommt eine Nummer; nur die JÜNGSTE schreibt den Stand. Eine
 * überholte Ladung gibt `UEBERHOLT` zurück (`ueberholt(ergebnis)`) — sie sagt
 * damit „nichts übernehmen“ statt einen fremden (womöglich älteren) Stand
 * zurückzugeben (SOLL 4).
 *
 * Fehler werden NICHT geworfen — der Stand trägt sie (`sperrt` bei 403,
 * `fehler` sonst), damit jede Anzeige dieselbe Lage sieht. Rückgabewert ist
 * der neue Stand, `null` (gesperrt/Fehler) oder `UEBERHOLT`.
 *
 * @returns {Promise<object|null|symbol>}
 */
export async function laden() {
  // UI-R3e: diese Anfrage ist die jüngste — eine noch laufende ältere Antwort
  // schreibt danach nichts mehr.
  const nummer = (juengste += 1)
  const anfrage = (async () => {
    try {
      const antwort = await api(VERWALTUNG_METHODE)
      // UI-R3g (SOLL 4): eine ÜBERHOLTE Ladung gibt nicht den geteilten Stand
      // zurück — der könnte älter sein als ihre eigene Antwort.
      if (nummer !== juengste) return UEBERHOLT
      setzeStand(antwort)
      return verwaltung.value
    } catch (err) {
      if (nummer !== juengste) return UEBERHOLT
      // 403 = der Server gibt dieser Person nichts zu verwalten. Eine Lage,
      // kein Fehler: keine Meldung, nur ein leerer Stand.
      if (Number(err?.status) === 403) {
        verwaltung.value = null
        sperrt.value = true
        fehler.value = ''
        antwortDa.value = true
        return null
      }
      // UI-R3e (fail closed): der alte Stand wird GELEERT, nicht behalten —
      // er war einmal wahr, ist es nach diesem Fehlschlag nicht mehr belegt.
      // `sperrt` wird zurückgesetzt (dieser Ausgang ist kein 403).
      verwaltung.value = null
      sperrt.value = false
      fehler.value = String(err?.message || '').trim() || 'Die Kalender konnten nicht geladen werden.'
      antwortDa.value = true
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
  laufende = null
  juengste = 0
  saet.value = 0
}

/**
 * Die Anzeige-Sicht (schreibgeschützt) — `laden` ist der Weg, den Stand zu
 * ändern.
 *
 * `saet` (UI-R3: `set`, „Satz“) steigt bei JEDEM Besuch des Besitzers, bevor
 * er fragt. Anzeigen, die den Eintrag „Kalender verwalten“ aus dem geteilten
 * Stand ableiten, merken sich den Satz, zu dem ihr eigenes Bild gehört: sie
 * zeigen den Eintrag nur, wenn die Antwort zu DIESEM Satz gehört — der Stand
 * ist bis dahin der des vorigen Besuchs.
 */
export function useKalenderVerwaltung() {
  return {
    verwaltung: readonly(verwaltung),
    antwortDa: readonly(antwortDa),
    sperrt: readonly(sperrt),
    fehler: readonly(fehler),
    saet: readonly(saet),
    laden,
  }
}

/** Die Anzeige-Sicht plus dem Besuch des Besitzers (siehe `saet`). */
export function useKalenderVerwaltungSicht() {
  return { ...useKalenderVerwaltung(), aktuellerSatz }
}
