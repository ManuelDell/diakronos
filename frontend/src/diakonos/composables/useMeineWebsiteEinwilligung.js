/**
 * BS-3b — Anbindung des Profil-Abschnitts an die Einwilligungs-API (BS-3a).
 *
 * EINE Stelle für die zwei Aufrufe; die Komponente kennt keinen Pfad:
 *
 *   GET  website.meine_einwilligung_lesen   -> eigener Stand
 *   POST website.meine_einwilligung_setzen  -> nur Geändertes (CSRF über apiCall)
 *
 * Die Kurzpfade sind eigens für diese Karte registriert
 * (`api/website._registriere_kurzpfade`); der volle Frappe-Pfad
 * (`diakronos.diakronos.api.website.…`) ginge auch — hier steht die kurze,
 * vom Vertrag der Karte genannte Form, damit ein Umbau der Modulbahn nicht
 * zwei Stellen betrifft. Der Server ist derselbe (`register_with_frappe_module`).
 *
 * WICHTIG: Es gibt KEINE Funktion, um den Stand einer ANDEREN Person zu
 * lesen oder zu setzen. Der Server hat keinen Parameter dafür (DSGVO,
 * Art. 7) — diese Datei erfindet keinen.
 */
import { computed, ref } from 'vue'
import { apiCall, apiGet } from './useApi.js'
import {
  einwilligungAenderungen,
  einwilligungStand as standAusAntwort,
} from '../../shared/website-einwilligung.mjs'

const API = {
  lesen: 'website.meine_einwilligung_lesen',
  setzen: 'website.meine_einwilligung_setzen',
}

export function useMeineWebsiteEinwilligung() {
  /** Rohe Serverantwort (Form siehe shared/website-einwilligung.mjs). */
  const daten = ref(null)
  const laedt = ref(false)
  const fehler = ref('')
  const speichert = ref(false)

  const stand = computed(() => standAusAntwort(daten.value))

  /**
   * Stand der EIGENEN Einwilligung holen.
   * @returns {Promise<object|null>}
   */
  async function laden() {
    laedt.value = true
    fehler.value = ''
    try {
      daten.value = (await apiGet(API.lesen)) || null
      return daten.value
    } catch (e) {
      daten.value = null
      fehler.value = e?.message
        || 'Dein Stand zur Website konnte nicht geladen werden. Bitte die Seite neu laden.'
      return null
    } finally {
      laedt.value = false
    }
  }

  /**
   * Änderungen senden. Der Aufrufer übergibt den ENTWURF und den geladenen
   * Stand; gesendet wird nur, was abweicht (`einwilligungAenderungen`).
   *
   * @param {{einwilligung: boolean, foto: boolean, anzeigename: string}} entwurf
   * @returns {Promise<{ok: boolean, aenderungen: object, fehler: string}>}
   */
  async function speichern(entwurf) {
    if (speichert.value) return { ok: false, aenderungen: { leer: true }, fehler: 'Es läuft bereits ein Speichervorgang.' }
    const aenderungen = einwilligungAenderungen(stand.value, entwurf)
    if (aenderungen.leer) return { ok: false, aenderungen, fehler: '' }
    speichert.value = true
    try {
      const nutzlast = { ...aenderungen }
      delete nutzlast.leer
      const antwort = await apiCall(API.setzen, nutzlast)
      // Der Server antwortet mit dem NEUEN Stand — den zeigen, nicht raten.
      if (antwort && typeof antwort === 'object') daten.value = antwort
      else await laden()
      return { ok: true, aenderungen, fehler: '' }
    } catch (e) {
      return {
        ok: false,
        aenderungen,
        fehler: e?.message || 'Deine Angaben konnten nicht gespeichert werden.',
      }
    } finally {
      speichert.value = false
    }
  }

  return { daten, laedt, fehler, speichert, stand, laden, speichern }
}
