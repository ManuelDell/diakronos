import { ref, computed } from 'vue'
import { apiCall } from './useApi.js'
// ON-4: Adressen unter dem Betriebs-Praefix (DIAKRONOS_BASE_PATH) bauen —
// derselbe Weg wie der Assistent, NIE ein fester Pfad.
import { apiUrl } from '../../shared/basis.js'
// ON-5 (E2-5): die Marke der Gemeinde EINE Stelle fortschreiben.
import { merkeGemeindeMarke } from './gemeindeMarke.mjs'
import * as EINRICHTUNG_REGELN from './einrichtungAssistent.mjs'
// ON-4: EINE Quelle fuer die Pruefungen des Assistenten (KEINE Kopie).
// Der Import steht zur AUFRUFZEIT (dynamisch): dieses Modul ist reine Logik und
// wird von Tests ohne `node_modules` ausgewertet — ein statischer Import waere
// dort ein Fehler. `einrichtungAssistent.mjs` bringt keine weiteren Importe mit.
// Darf er nicht geladen werden (z. B. Test ohne Importe), bleiben die Felder
// ungeprueft: der SERVER prueft ohnehin (ON2-VERTRAG) — die Regel faellt dann
// nach hinten, sie faellt nicht aus.
//: Der Modulpfad steht NICHT als Literal im Quelltext: sonst wollte Rollup den
//: Assistenten mitbuendeln — und Tests, die dieses Modul ohne Importe
//: auswerten (N9), fielen ueber den dynamischen Import. Ein `import()` mit
//: variablem Pfad bleibt ein Laufzeit-Import.
// Review ON-4: STATISCH importiert — ein variabler import()-Pfad wird von Vite
// nicht gebuendelt und lief im gebauten Stand ins Leere (Pruefung fiel aus).
async function assistentRegeln() {
  return EINRICHTUNG_REGELN
}

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
  // ON-4 (Nachtrag Orchestrator 2026-11-03): Die Angaben aus dem Assistenten
  // werden nach der Ersteinrichtung AUSSCHLIESSLICH hier gepflegt — Kurzname,
  // Anschrift, Telefon, Website, Logo und die Zeitzone (nur Anzeige).
  const kurzname = ref('')
  const strasse = ref('')
  const plz = ref('')
  const ort = ref('')
  const telefon = ref('')
  const website = ref('')
  const zeitzone = ref('')
  const zeitzoneHinweis = ref('')
  const logoUrl = ref('')
  const logoLaeuft = ref(false)
  const logoFehler = ref('')

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
      kurzname.value = d.kurzname || ''
      strasse.value = d.strasse || ''
      plz.value = d.plz || ''
      ort.value = d.ort || ''
      telefon.value = d.telefon || ''
      website.value = d.website || ''
      zeitzone.value = d.zeitzone || ''
      zeitzoneHinweis.value = d.zeitzone_hinweis || ''
      // ON-2: Die Adresse kommt FERTIG (Betriebspraefix + `?v=`) — hier wird
      // sie NICHT nachgebaut. Dieselbe Regel wie im Assistenten
      // (`logoVorschau`): ohne Logoadresse ODER bei `logo_vorhanden: false`
      // gibt es keine Vorschau (dann zeigt die Marke das Monogramm).
      logoUrl.value = (d.logo_vorhanden === false ? '' : (d.logo_url || ''))
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
    // Dieselben Pruefungen wie im Assistenten (EINE Stelle: `pruefeSchritt`,
    // derselbe Code — keine Kopie der Regeln). Ist die Regel-Datei nicht
    // ladbar (reine Logik-Tests ohne Importe), wird NICHT geprueft: der
    // Server prueft ohnehin (ON2-VERTRAG).
    const regeln = await assistentRegeln();
    const feldFehler = {};
    if (regeln) {
      Object.assign(feldFehler, regeln.pruefeSchritt('gemeinde', {
        gemeindename: gemeindename.value, kurzname: kurzname.value,
      }));
      Object.assign(feldFehler, regeln.pruefeSchritt('kontakt', {
        kontakt_email: kontaktEmail.value,
        plz: plz.value,
        website: website.value,
        strasse: strasse.value,
        ort: ort.value,
        telefon: telefon.value,
      }));
    }
    if (Object.keys(feldFehler).length) {
      // Absage AM FELD (wie im Assistenten): `fehler` traegt den Text fuer die
      // Flaeche darueber, das Formular zeigt ihn zusaetzlich am Eingabefeld.
      // Rueckgabe bleibt `false` — dieselbe Form wie vor ON-4.
      fehler.value = Object.values(feldFehler)[0]
      return false
    }
    speichert.value = true
    const nutzlast = {
      gemeindename: gemeindename.value.trim(),
      kontakt_email: kontaktEmail.value.trim(),
      oeffentliche_adresse: oeffentlicheAdresse.value.trim(),
      willkommenstext: willkommenstext.value,
      // ON-4: die ON-2-Felder. Ein leerer Wert LOESCHT die Angabe
      // (ON2-VERTRAG Abschnitt 1) — deshalb wird immer der volle Satz gesendet.
      kurzname: kurzname.value.trim(),
      strasse: strasse.value.trim(),
      plz: plz.value.trim(),
      ort: ort.value.trim(),
      telefon: telefon.value.trim(),
      website: website.value.trim(),
    }
    if (mitLinkVorgaben) {
      nutzlast.link_laufzeit_tage = Number(linkLaufzeitTage.value) || 0
      nutzlast.link_max_anmeldungen = Number(linkMaxAnmeldungen.value) || 0
    }
    try {
      await apiCall(API + 'gemeinde_speichern', nutzlast)
      erfolg.value = 'Gemeinde-Einstellungen gespeichert.'
      // ON-4: Der Einrichtungs-Stand aendert sich mit (Name/Logo/Kontakt) —
      // Karte und Hinweisleisten lesen ihn beim naechsten Anzeigen neu.
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

  /**
   * Logo hochladen (ON-2 `gemeinde_logo_hochladen`, multipart). Die grobe
   * Vorpruefung ist dieselbe wie im Assistenten (`logoDateiFehler`); die echte
   * Pruefung (Magic-Bytes, Masse) macht der Server.
   */
  async function logoHochladen(datei) {
    if (!bedienbar.value || !datei) return false
    const regeln = await assistentRegeln()
    const vorab = regeln ? regeln.logoDateiFehler(datei) : ''
    if (vorab) {
      logoFehler.value = vorab
      return false
    }
    logoFehler.value = ''
    logoLaeuft.value = true
    try {
      const csrf = document.querySelector('meta[name="csrf-token"]')?.content || ''
      const form = new FormData()
      form.append('file', datei)
      const res = await fetch(
        apiUrl('diakronos.diakonos.api.gemeinde.gemeinde_logo_hochladen'),
        { method: 'POST', headers: { 'X-Frappe-CSRF-Token': csrf }, body: form },
      )
      const inhalt = await res.json().catch(() => ({}))
      if (!res.ok) throw new Error(inhalt?.exception || 'Das Logo konnte nicht gespeichert werden.')
      const d = inhalt?.message || inhalt
      logoUrl.value = d?.logo_url || ''
      // ON-5 (E2-5): Seitenleiste/Marke sofort aktuell (kein Neuladen).
      merkeGemeindeMarke(d?.logo_url || '')
      erfolg.value = 'Logo gespeichert.'
      return true
    } catch (e) {
      logoFehler.value = e.message || 'Das Logo konnte nicht gespeichert werden.'
      return false
    } finally {
      logoLaeuft.value = false
    }
  }

  /** Logo entfernen (ON-2 `gemeinde_logo_entfernen`, idempotent). */
  async function logoEntfernen() {
    if (!bedienbar.value) return false
    logoFehler.value = ''
    logoLaeuft.value = true
    try {
      const res = await apiCall(API + 'gemeinde_logo_entfernen', {})
      const d = res?.message || res
      logoUrl.value = d?.logo_url || ''
      // ON-5 (E2-5): auch das Entfernen muss die Marke sofort leeren.
      merkeGemeindeMarke(d?.logo_url || '')
      erfolg.value = 'Logo entfernt.'
      return true
    } catch (e) {
      logoFehler.value = e.message || 'Das Logo konnte nicht entfernt werden.'
      return false
    } finally {
      logoLaeuft.value = false
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
    modulSchalten,
    // ON-4: Angaben aus dem Assistenten, die jetzt hier gepflegt werden.
    kurzname, strasse, plz, ort, telefon, website, zeitzone, zeitzoneHinweis,
    logoUrl, logoLaeuft, logoFehler, logoHochladen, logoEntfernen }
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
