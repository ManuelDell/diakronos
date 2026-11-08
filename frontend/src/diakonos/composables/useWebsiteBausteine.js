/**
 * BS-2d — Anbindung des Bereichs „Bausteine“ an die Verwaltungs-API.
 *
 * EINE Stelle für die zwei Aufrufe; die Komponenten kennen keinen Pfad.
 * Vertrag BS-2a (`api/website.py`, docs/BETRIEBSANLEITUNG.md Abschnitt 19):
 *
 *   GET  bausteine_status        -> Stand der Bibliothek (lesend)
 *   POST bausteine_installieren  -> mitgelieferte Bibliothek einspielen
 *
 * `bausteine_installieren` geht AUSSCHLIESSLICH über `apiCall` (POST mit
 * CSRF-Token) — am Server steht der Endpunkt in `_NUR_POST` und weist ein GET
 * mit 405 ab (BS-1a2/F2). Ein GET hier wäre also nicht nur unsauber, sondern
 * kaputt.
 *
 * Fehler werden NICHT verschluckt: der Aufrufer bekommt Text und Status und
 * zeigt die Meldung im Bereich. Eine stillschweigend „erfolgreiche“
 * Installation, die der Server abgelehnt hat, wäre die schlimmere Variante.
 */
import { computed, ref } from 'vue'
import { apiCall, apiGet } from './useApi.js'
import { bausteinZeilen, bausteineStand, bausteineZustand } from '../../shared/website-bausteine.mjs'

const API = {
  status: 'diakronos.diakronos.api.website.bausteine_status',
  installieren: 'diakronos.diakronos.api.website.bausteine_installieren',
}

export function useWebsiteBausteine() {
  /** Rohe Serverantwort von `bausteine_status` (Form siehe shared/website-bausteine.mjs). */
  const daten = ref(null)
  const laedt = ref(false)
  const fehler = ref('')
  /** Läuft gerade ein Einspielvorgang? (EIN Knopf, ein Vorgang.) */
  const spieltEin = ref(false)
  /** Ergebnis des letzten Einspielvorgangs (rohe Antwort oder Fehler). */
  const ergebnis = ref(null)

  const stand = computed(() => bausteineStand(daten.value))
  const zustand = computed(() => bausteineZustand(daten.value))
  const zeilen = computed(() => bausteinZeilen(daten.value))

  /** Stand neu vom Server holen. Fehler bleiben als Text stehen (kein Wurf). */
  async function laden() {
    laedt.value = true
    fehler.value = ''
    try {
      daten.value = (await apiGet(API.status)) || null
      return daten.value
    } catch (e) {
      daten.value = null
      fehler.value = e?.message
        || 'Der Stand der Bausteine konnte nicht geladen werden. Bitte die Seite neu laden.'
      return null
    } finally {
      laedt.value = false
    }
  }

  /**
   * Bibliothek ins Werkzeug einspielen (der eine schreibende Aufruf).
   *
   * Der Server zieht die mitgelieferten Quellen ein; bereits eingesetzte
   * Kopien in Websites bleiben unangetastet (BS-2a, F2c). Danach wird der
   * Stand frisch gelesen — die Anzeige soll den Serverstand zeigen, nicht
   * den vermuteten.
   *
   * @returns {Promise<{ok: boolean, antwort: object|null, fehler: string, status: number}>}
   */
  async function einspielen() {
    if (spieltEin.value) return { ok: false, antwort: null, fehler: 'Es läuft bereits ein Vorgang.', status: 0 }
    spieltEin.value = true
    ergebnis.value = null
    try {
      const antwort = await apiCall(API.installieren, {})
      ergebnis.value = { ok: true, antwort: antwort || null, fehler: '', status: 200 }
      await laden()
      return ergebnis.value
    } catch (e) {
      ergebnis.value = {
        ok: false,
        antwort: null,
        fehler: e?.message || 'Die Bausteine konnten nicht eingespielt werden.',
        status: Number(e?.status) || 0,
      }
      return ergebnis.value
    } finally {
      spieltEin.value = false
    }
  }

  return {
    daten,
    laedt,
    fehler,
    spieltEin,
    ergebnis,
    stand,
    zustand,
    zeilen,
    laden,
    einspielen,
    API,
  }
}
