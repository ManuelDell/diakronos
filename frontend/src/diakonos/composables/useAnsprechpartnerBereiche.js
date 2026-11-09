/**
 * BS-3b — Anbindung des Verwaltungsbereichs „Ansprechpartner“ (Website-Rolle).
 *
 * Zwei Aufrufe, EINE Stelle (BS-3a, `api/website.py`; Rolle wie BS-1a/BS-1d —
 * der Server weist ohne Website-Rolle mit 403 ab):
 *
 *   GET  website.ansprechpartner_bereiche_lesen  -> Auswahl, Katalog, Postfächer
 *   POST website.ansprechpartner_bereiche_setzen -> VOLLE Liste (CSRF via apiCall)
 *
 * Es gibt hier bewusst KEINE Einwilligungs-Funktion: der Server nimmt in
 * `ansprechpartner_bereiche_setzen` kein Einwilligungsfeld an (403,
 * `_weise_einwilligungsfelder_ab`), und `einwilligungen_verwaltbar` ist
 * `false`. Diese Datei bildet nur ab, was der Vertrag hergibt.
 *
 * Zur Vorschau „wer erscheint“: der Vertrag von BS-3a liefert KEINE Liste der
 * betroffenen Personen (G1: keine Personendaten über die Verwaltungs-API).
 * Diese Datei erfindet sie nicht — sie liest nur den ÖFFENTLICHEN Stand
 * (`website.oeffentlich.ansprechpartner`, allow_guest, Feld-Positivliste).
 * Was dort steht, ist genau das, was die Website zeigt; alles andere ist
 * „erscheint nicht“.
 */
import { computed, ref } from 'vue'
import { apiCall, apiGet } from './useApi.js'
import {
  bereicheNutzlast,
  bereicheZeilen,
  funktionsKatalog,
  postfachAuswahl,
} from '../../shared/website-einwilligung.mjs'

const API = {
  // Hinweis: `bereicheZeilen` & Co. kommen aus `shared/website-einwilligung.mjs`.
  lesen: 'website.ansprechpartner_bereiche_lesen',
  setzen: 'website.ansprechpartner_bereiche_setzen',
  oeffentlich: 'website.oeffentlich.ansprechpartner',
}

export function useAnsprechpartnerBereiche() {
  const daten = ref(null)
  const laedt = ref(false)
  const fehler = ref('')
  const speichert = ref(false)

  /** Gespeicherte Auswahl als Zeilen (Sortierung, Funktion). */
  const zeilen = computed(() => bereicheZeilen(daten.value))
  const katalog = computed(() => ({
    dienstbereich: funktionsKatalog(daten.value, 'dienstbereich'),
    gruppe: funktionsKatalog(daten.value, 'gruppe'),
  }))
  const postfaecher = computed(() => postfachAuswahl(daten.value))
  /** Darf die Verwaltung eine Einwilligung setzen? Der Vertrag sagt: nie. */
  const einwilligungenVerwaltbar = computed(() => daten.value?.einwilligungen_verwaltbar === true)

  /** Der öffentliche Stand (Vorschau) — nur freigegebene Felder. */
  const oeffentlich = ref([])
  const oeffentlichFehler = ref('')

  async function laden() {
    laedt.value = true
    fehler.value = ''
    try {
      daten.value = (await apiGet(API.lesen)) || null
      return daten.value
    } catch (e) {
      daten.value = null
      fehler.value = e?.message
        || 'Die Ansprechpartner konnten nicht geladen werden. Bitte die Seite neu laden.'
      return null
    } finally {
      laedt.value = false
    }
  }

  /**
   * Öffentlichen Stand holen (Vorschau). Fehler bleiben Text — eine leere
   * Vorschau ist eine gültige Antwort (niemand hat zugestimmt).
   * @returns {Promise<object[]>}
   */
  async function oeffentlichenStandLaden() {
    oeffentlichFehler.value = ''
    try {
      const antwort = await apiCall(API.oeffentlich, {})
      // `apiCall` liefert die Nutzlast (bei Frappe das `message`-Feld).
      const liste = Array.isArray(antwort) ? antwort : (antwort?.ansprechpartner ?? [])
      oeffentlich.value = Array.isArray(liste) ? liste : []
      return oeffentlich.value
    } catch (e) {
      oeffentlich.value = []
      oeffentlichFehler.value = e?.message
        || 'Die öffentliche Vorschau konnte nicht geladen werden.'
      return []
    }
  }

  /**
   * Die Auswahl als GANZE Liste schreiben (delete-and-replace).
   * @param {object[]} liste
   * @returns {Promise<{ok: boolean, fehler: string}>}
   */
  async function setzen(liste) {
    if (speichert.value) return { ok: false, fehler: 'Es läuft bereits ein Speichervorgang.' }
    speichert.value = true
    fehler.value = ''
    try {
      const antwort = await apiCall(API.setzen, { bereiche: bereicheNutzlast(liste) })
      // Der Server antwortet mit der gespeicherten Liste — neu laden ist
      // trotzdem richtig: Katalog/Postfächer können sich geändert haben.
      if (antwort && Array.isArray(antwort.bereiche)) {
        daten.value = { ...(daten.value || {}), bereiche: antwort.bereiche }
      }
      await laden()
      await oeffentlichenStandLaden()
      return { ok: true, fehler: '' }
    } catch (e) {
      return {
        ok: false,
        fehler: e?.message || 'Die Ansprechpartner konnten nicht gespeichert werden.',
      }
    } finally {
      speichert.value = false
    }
  }

  return {
    daten, laedt, fehler, speichert,
    zeilen, katalog, postfaecher, einwilligungenVerwaltbar,
    oeffentlich, oeffentlichFehler,
    laden, setzen, oeffentlichenStandLaden,
  }
}
