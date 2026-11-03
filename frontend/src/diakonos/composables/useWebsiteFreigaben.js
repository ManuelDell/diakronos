/**
 * BS-1d — Anbindung der Oberfläche „Website-Freigaben“ an die Verwaltungs-API.
 *
 * EINE Stelle für alle Aufrufe: die Komponenten kennen keinen Pfad.
 * Sechs Endpunkte (Vertrag BS-1a, docs/BETRIEBSANLEITUNG.md 18.3):
 *
 *   GET  freigaben_lesen          -> Stand aller Freigaben
 *   POST freigabe_setzen          -> Kalender/Gruppe freigeben (CSRF über `apiCall`)
 *   POST beitrag_auf_website      -> Beitrag auf die Website stellen
 *   POST postfach_speichern       -> Postfach anlegen/ändern
 *   POST postfach_loeschen        -> Postfach entfernen
 *   POST kategorie_oeffentlich    -> Terminart öffentlich schalten
 *
 * Schreibende Aufrufe gehen AUSSCHLIESSLICH über `apiCall` (POST mit
 * `X-Frappe-CSRF-Token`) — ein GET würde die CSRF-Middleware nicht durchlaufen
 * und ist am Server ohnehin mit 405 abgewiesen (BS-1a2/F2).
 *
 * Fehler werden NICHT verschluckt: der Aufrufer bekommt den Fehler und zeigt
 * ihn am Feld bzw. als Meldung. Eine stillschweigend „erfolgreiche“ Freigabe,
 * die der Server abgelehnt hat, wäre die schlimmere Variante.
 */
import { computed, ref } from 'vue'
import { apiCall, apiGet } from './useApi.js'
import { freigabeZeile } from '../../shared/website-freigaben.mjs'

const API = {
  lesen: 'diakronos.diakronos.api.website.freigaben_lesen',
  freigabe: 'diakronos.diakronos.api.website.freigabe_setzen',
  beitrag: 'diakronos.diakronos.api.website.beitrag_auf_website',
  postfachSpeichern: 'diakronos.diakronos.api.website.postfach_speichern',
  postfachLoeschen: 'diakronos.diakronos.api.website.postfach_loeschen',
  kategorie: 'diakronos.diakronos.api.website.kategorie_oeffentlich',
}

export function useWebsiteFreigaben() {
  /** Rohe Serverantwort (Form siehe `shared/website-freigaben.mjs`). */
  const daten = ref(null)
  const laedt = ref(false)
  const fehler = ref('')
  /** Kennungen, an denen gerade etwas geschrieben wird (`art:name`/`slug`). */
  const schreibt = ref(new Set())

  const kalender = computed(() => (daten.value?.kalender || []).map(freigabeZeile))
  const gruppen = computed(() => (daten.value?.gruppen || []).map(freigabeZeile))
  const postfaecher = computed(() => (daten.value?.postfaecher || []).map((p) => ({ ...p })))
  const kategorien = computed(() => (daten.value?.kategorien || []).map((k) => ({ ...k })))

  function laeuft(schluessel) {
    return schreibt.value.has(schluessel)
  }

  function beginne(schluessel) {
    const neu = new Set(schreibt.value)
    neu.add(schluessel)
    schreibt.value = neu
  }

  function beende(schluessel) {
    const neu = new Set(schreibt.value)
    neu.delete(schluessel)
    schreibt.value = neu
  }

  /** Stand neu vom Server holen. Fehler bleiben als Text stehen (kein Wurf). */
  async function laden() {
    laedt.value = true
    fehler.value = ''
    try {
      daten.value = (await apiGet(API.lesen)) || null
      return daten.value
    } catch (e) {
      daten.value = null
      fehler.value = e?.message
        || 'Die Website-Freigaben konnten nicht geladen werden. Bitte die Seite neu laden.'
      return null
    } finally {
      laedt.value = false
    }
  }

  /**
   * Schaltet eine Freigabe und übernimmt die Antwort des Servers.
   *
   * Der Server antwortet mit der VOLLEN neuen Zeile (`art, name, titel,
   * freigabe, slug[, nur_oeffentliche_kategorien]`) — damit wird nur diese eine
   * Zeile ersetzt; die übrigen bleiben stehen (kein Nachladen der ganzen
   * Liste, das den Bildschirm springen ließe).
   *
   * @param {{art: string, name: string, freigabe: boolean, slug?: string, nur_oeffentliche_kategorien?: boolean}} nutzlast
   * @returns {Promise<{ok: boolean, antwort: object|null, fehler: string, status: number}>}
   */
  async function freigabeSetzen(nutzer) {
    const nutzlast = nutzer || {}
    const schluessel = `${nutzlast.art}:${nutzlast.name}`
    beginne(schluessel)
    try {
      const antwort = await apiCall(API.freigabe, nutzlast)
      const liste = nutzlast.art === 'kalender' ? kalender.value : gruppen.value
      const neu = liste.map((z) => (
        z.name === nutzlast.name
          ? { ...freigabeZeile(antwort || {}), name: z.name, titel: z.titel }
          : z
      ))
      if (daten.value) {
        daten.value = {
          ...daten.value,
          [nutzlast.art === 'kalender' ? 'kalender' : 'gruppen']: neu,
        }
      }
      return { ok: true, antwort: antwort || null, fehler: '', status: 200 }
    } catch (e) {
      return { ok: false, antwort: null, fehler: e?.message || 'Die Freigabe wurde nicht gespeichert.', status: Number(e?.status) || 0 }
    } finally {
      beende(schluessel)
    }
  }

  /**
   * Beitrag auf die Website stellen (U3). Gibt dieselbe Form zurück wie
   * `freigabeSetzen`; `antwort` trägt `{name, titel, auf_website, veroeffentlicht}`.
   */
  async function beitragSetzen(name, wert) {
    beginne(`beitrag:${name}`)
    try {
      const antwort = await apiCall(API.beitrag, { name, wert: wert === true })
      return { ok: true, antwort: antwort || null, fehler: '', status: 200 }
    } catch (e) {
      return { ok: false, antwort: null, fehler: e?.message || 'Der Beitrag wurde nicht geändert.', status: Number(e?.status) || 0 }
    } finally {
      beende(`beitrag:${name}`)
    }
  }

  /**
   * Postfach anlegen/ändern (U4). Der Server gibt die GANZE Liste zurück —
   * die wird übernommen, damit Reihenfolge und Server-Sortierung stimmen.
   */
  async function postfachSpeichern(eingabe) {
    beginne(`postfach:${eingabe?.slug || ''}`)
    try {
      const antwort = await apiCall(API.postfachSpeichern, eingabe || {})
      if (daten.value && Array.isArray(antwort?.postfaecher)) {
        daten.value = { ...daten.value, postfaecher: antwort.postfaecher }
      }
      return { ok: true, antwort: antwort || null, fehler: '', status: 200 }
    } catch (e) {
      return { ok: false, antwort: null, fehler: e?.message || 'Das Postfach wurde nicht gespeichert.', status: Number(e?.status) || 0 }
    } finally {
      beende(`postfach:${eingabe?.slug || ''}`)
    }
  }

  /** Postfach entfernen (U4). */
  async function postfachLoeschen(slug) {
    beginne(`postfach:${slug}`)
    try {
      const antwort = await apiCall(API.postfachLoeschen, { slug })
      if (daten.value && Array.isArray(antwort?.postfaecher)) {
        daten.value = { ...daten.value, postfaecher: antwort.postfaecher }
      }
      return { ok: true, antwort: antwort || null, fehler: '', status: 200 }
    } catch (e) {
      return { ok: false, antwort: null, fehler: e?.message || 'Das Postfach wurde nicht entfernt.', status: Number(e?.status) || 0 }
    } finally {
      beende(`postfach:${slug}`)
    }
  }

  /** Terminart öffentlich schalten (U1, Zusatz zur Kategorie-Einschränkung). */
  async function kategorieSetzen(name, wert) {
    beginne(`kategorie:${name}`)
    try {
      const antwort = await apiCall(API.kategorie, { name, wert: wert === true })
      if (daten.value) {
        daten.value = {
          ...daten.value,
          kategorien: (daten.value.kategorien || []).map((k) => (
            k.name === name ? { ...k, oeffentlich: antwort?.oeffentlich === true } : k
          )),
        }
      }
      return { ok: true, antwort: antwort || null, fehler: '', status: 200 }
    } catch (e) {
      return { ok: false, antwort: null, fehler: e?.message || 'Die Terminart wurde nicht geändert.', status: Number(e?.status) || 0 }
    } finally {
      beende(`kategorie:${name}`)
    }
  }

  return {
    daten,
    laedt,
    fehler,
    schreibt,
    kalender,
    gruppen,
    postfaecher,
    kategorien,
    laeuft,
    laden,
    freigabeSetzen,
    beitragSetzen,
    postfachSpeichern,
    postfachLoeschen,
    kategorieSetzen,
    API,
  }
}
