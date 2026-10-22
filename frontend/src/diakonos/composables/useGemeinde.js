import { ref, computed } from 'vue'
import { apiCall } from './useApi.js'

/** N9: Gemeinde-, Modul- und Datenschutz-Einstellungen in EINEM Ort. */
const API = 'diakronos.diakonos.api.gemeinde.'

/**
 * Gemeinde-Abschnitt: Gemeindename, Kontakt, öffentliche Adresse,
 * Willkommenstext, Vorgaben für neue Links und Modul-Sichtbarkeit.
 *
 * Geladen wird einmal; gespeichert wird je Karte. Das Formular bleibt
 * bedienbar, aber ohne geladene Werte wird nichts geschrieben — so entsteht
 * kein Teilstand aus einer veralteten Oberfläche.
 */
export function useGemeinde() {
  const laedt = ref(false)
  const speichert = ref(false)
  const geladen = ref(false)
  const fehler = ref('')
  const erfolg = ref('')

  const gemeindename = ref('')
  const kontaktEmail = ref('')
  const oeffentlicheAdresse = ref('')
  const willkommenstext = ref('')
  const linkLaufzeitTage = ref(30)
  const linkMaxAnmeldungen = ref(0)
  const module = ref([])
  const modulSpeichert = ref('')

  const bedienbar = computed(() => geladen.value && !laedt.value && !speichert.value)

  async function laden() {
    laedt.value = true
    geladen.value = false
    fehler.value = ''
    try {
      const res = await apiCall(API + 'gemeinde_get_einstellungen', {})
      const d = res.message || res
      gemeindename.value = d.gemeindename || ''
      kontaktEmail.value = d.kontakt_email || ''
      oeffentlicheAdresse.value = d.oeffentliche_adresse || ''
      willkommenstext.value = d.willkommenstext || ''
      linkLaufzeitTage.value = Number(d.link_laufzeit_tage ?? 30)
      linkMaxAnmeldungen.value = Number(d.link_max_anmeldungen ?? 0)
      module.value = d.module || []
      geladen.value = true
    } catch (e) {
      fehler.value = e.message || 'Die Gemeinde-Einstellungen konnten nicht geladen werden.'
    } finally {
      laedt.value = false
    }
  }

  async function speichern({ mitLinkVorgaben = true } = {}) {
    if (!bedienbar.value) return false
    fehler.value = ''
    erfolg.value = ''
    if (!gemeindename.value.trim()) {
      fehler.value = 'Bitte einen Gemeindenamen eintragen.'
      return false
    }
    speichert.value = true
    const nutzlast = {
      gemeindename: gemeindename.value.trim(),
      kontakt_email: kontaktEmail.value.trim(),
      oeffentliche_adresse: oeffentlicheAdresse.value.trim(),
      willkommenstext: willkommenstext.value,
    }
    if (mitLinkVorgaben) {
      nutzlast.link_laufzeit_tage = Number(linkLaufzeitTage.value) || 0
      nutzlast.link_max_anmeldungen = Number(linkMaxAnmeldungen.value) || 0
    }
    try {
      await apiCall(API + 'gemeinde_speichern', nutzlast)
      erfolg.value = 'Gemeinde-Einstellungen gespeichert.'
      return true
    } catch (e) {
      fehler.value = e.message || 'Speichern fehlgeschlagen. Deine Eingaben bleiben erhalten.'
      return false
    } finally {
      speichert.value = false
    }
  }

  /** Nur die Vorgaben für neue Registrierungslinks speichern (eigene Karte). */
  async function linkvorgabenSpeichern() {
    if (!bedienbar.value) return false
    fehler.value = ''
    erfolg.value = ''
    speichert.value = true
    try {
      await apiCall(API + 'gemeinde_setze_linkvorgaben', {
        link_laufzeit_tage: Number(linkLaufzeitTage.value) || 0,
        link_max_anmeldungen: Number(linkMaxAnmeldungen.value) || 0,
      })
      erfolg.value = 'Vorgaben für neue Links gespeichert.'
      return true
    } catch (e) {
      fehler.value = e.message || 'Speichern fehlgeschlagen. Deine Eingaben bleiben erhalten.'
      return false
    } finally {
      speichert.value = false
    }
  }

  /** Modul-Sichtbarkeit sofort umschalten (eigene kleine Schreiboperation). */
  async function modulSchalten(schluessel, sichtbar) {
    if (!bedienbar.value) return
    modulSpeichert.value = schluessel
    fehler.value = ''
    try {
      await apiCall(API + 'gemeinde_setze_modul', { schluessel, sichtbar })
      const m = module.value.find(x => x.schluessel === schluessel)
      if (m) m.sichtbar = sichtbar
    } catch (e) {
      fehler.value = e.message || 'Das Modul konnte nicht geschaltet werden.'
    } finally {
      modulSpeichert.value = ''
    }
  }

  return { laedt, speichert, geladen, fehler, erfolg, gemeindename, kontaktEmail,
    oeffentlicheAdresse, willkommenstext, linkLaufzeitTage, linkMaxAnmeldungen,
    module, modulSpeichert, bedienbar, laden, speichern, linkvorgabenSpeichern,
    modulSchalten }
}

/** Datenschutz-Abschnitt: die pflegbaren Texte samt Fassungszähler. */
export function useDatenschutzTexte() {
  const laedt = ref(false)
  const speichert = ref(false)
  const geladen = ref(false)
  const fehler = ref('')
  const erfolg = ref('')

  const einwilligung = ref('')
  const datenschutzerklaerung = ref('')
  const aufbewahrung = ref('')
  const veroeffentlicht = ref(false)
  const version = ref(1)
  // N9b (M-2): Fassung der zuletzt VEROEFFENTLICHTEN Fassung. Solange der
  // Entwurf nicht veroeffentlicht ist, gilt weiter diese Fassung auf der
  // oeffentlichen Seite und im Beleg.
  const veroeffentlichteVersion = ref(1)

  const bedienbar = computed(() => geladen.value && !laedt.value && !speichert.value)
  // Was steht gerade auf der Anmeldeseite? Bei veroeffentlichtem Entwurf der
  // eigene Text, sonst die zuletzt veroeffentlichte Fassung.
  const statusText = computed(() => (
    veroeffentlicht.value
      ? 'Für neue Anmeldungen sichtbar.'
      : `Entwurf — auf der Anmeldeseite gilt weiter Fassung ${veroeffentlichteVersion.value}.`
  ))

  async function laden() {
    laedt.value = true
    geladen.value = false
    fehler.value = ''
    try {
      const res = await apiCall(API + 'datenschutz_get_texte', {})
      const d = res.message || res
      einwilligung.value = d.einwilligung || ''
      datenschutzerklaerung.value = d.datenschutzerklaerung || ''
      aufbewahrung.value = d.aufbewahrung || ''
      veroeffentlicht.value = !!d.veroeffentlicht
      version.value = Number(d.version || 1)
      veroeffentlichteVersion.value = Number(d.veroeffentlichte_version || 1)
      geladen.value = true
    } catch (e) {
      fehler.value = e.message || 'Die Datenschutz-Texte konnten nicht geladen werden.'
    } finally {
      laedt.value = false
    }
  }

  async function speichern() {
    if (!bedienbar.value) return false
    fehler.value = ''
    erfolg.value = ''
    if (!einwilligung.value.trim() || !datenschutzerklaerung.value.trim()
        || !aufbewahrung.value.trim()) {
      fehler.value = 'Alle drei Texte werden gebraucht.'
      return false
    }
    speichert.value = true
    try {
      const res = await apiCall(API + 'datenschutz_speichern', {
        einwilligung: einwilligung.value,
        datenschutzerklaerung: datenschutzerklaerung.value,
        aufbewahrung: aufbewahrung.value,
        veroeffentlicht: veroeffentlicht.value,
      })
      const d = res.message || res
      version.value = Number(d.version || version.value)
      if (veroeffentlicht.value) {
        veroeffentlichteVersion.value = version.value
        erfolg.value = `Gespeichert und veröffentlicht (Fassung ${version.value}).`
      } else {
        erfolg.value = `Entwurf gespeichert (Fassung ${version.value}). Auf der Anmeldeseite gilt weiter Fassung ${veroeffentlichteVersion.value}.`
      }
      return true
    } catch (e) {
      fehler.value = e.message || 'Speichern fehlgeschlagen. Deine Eingaben bleiben erhalten.'
      return false
    } finally {
      speichert.value = false
    }
  }

  return { laedt, speichert, geladen, fehler, erfolg, einwilligung,
    datenschutzerklaerung, aufbewahrung, veroeffentlicht, version,
    veroeffentlichteVersion, statusText, bedienbar,
    laden, speichern }
}
