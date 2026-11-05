import { ref } from 'vue'
import { apiCall } from './useApi.js'
// UX2g: EINE Quelle für angezeigte Fehlertexte (kein „Unbekannter Fehler").
import { fehlertext } from '../../shared/fehlertexte.js'
import {
  darfGestaltung,
  pruefeFeld,
  pruefeSkala,
  werteFuerServer,
  geaenderteFelder,
  rueckgaengigMeldung,
  frischeCssAdresse,
} from './gestaltung.mjs'

/**
 * UX1k — Einstellungen-Seite „Gestaltung“: lesen, live prüfen, speichern,
 * zurücksetzen, Vorschau.
 *
 * EINE Stelle für alle Aufrufe (die Komponente kennt keinen Pfad). Die
 * Felder mit Bereich, Standard und Gruppierung kommen vom Server
 * (`gestaltung.lesen`, UX1j) — dieses Modul hält KEINE eigene Token-Liste.
 *
 * Der Server entscheidet über die Rechte: alle drei Endpunkte verweigern einem
 * Nicht-System-Manager mit 403. `darfGestaltung` blendet den Bereich
 * zusätzlich aus (Komfort, keine Schranke).
 */
const API = 'diakronos.diakronos.api.gestaltung.'

/**
 * Fehlertext aus der Serverantwort lesen (Feld `message` der Compat-Schicht).
 * Ein brauchbarer Fachsatz des Servers bleibt stehen (er nennt bei einer
 * gebrochenen Skala genau die zwei Token), eine Floskel nie.
 */
function meldungAus(fehler, ersatz) {
  return fehlertext(fehler, { text: ersatz })
}



export function useGestaltung() {
  const laedt = ref(false)
  const speichert = ref(false)
  const geladen = ref(false)
  const fehler = ref('')
  const erfolg = ref('')
  /**
   * Ein Speichervorgang ist gerade erfolgreich durchgelaufen. Der Zustand
   * trägt die SICHTBARE Erfolgsfläche (nicht ihr Text): eine an `erfolg`
   * gehängte Meldung entstünde erst mit dem Text und bliebe für Vorlesehilfen
   * stumm (UX2d2).
   */
  const gespeichert = ref(false)

  /** Felder des Servers: `{token, standard, wert, einheit, min, max, schritt, gruppe, abweichend}`. */
  const felder = ref([])
  /** Eingaben im Formular: Token -> Text (String, damit „leer“ sichtbar bleibt). */
  const eingaben = ref({})
  /** Prüfmeldung je Token (leer = in Ordnung). */
  const feldFehler = ref({})
  /** Skalenbruch: die zwei Token-Paare, die die Ordnung brechen. */
  const skalaPaare = ref([])
  /**
   * Die Kettenglieder der Abstands-Skala — vom SERVER (`skala_ordnung`,
   * UX1j2). Keine Tokenliste im Frontend: sie würde vom Server driften und
   * `--pad` fälschlich als Kettenglied behandeln (Live-Befund 2026-11-05).
   */
  const skalaOrdnung = ref([])
  /** Letzte Aktion für die Rückgängig-Meldung (bis UX2a sie wirklich kann). */
  const rueckgaengig = ref(null)

  const rollen = () => (typeof window === 'undefined' ? null : window.__DIakonosBOOT?.roles)
  const sichtbar = () => darfGestaltung({ rollen: rollen() })

  /** Kennzahlen der Seite (für Kopf und Freischalten des Speichern-Knopfs). */
  const abweichend = ref(0)
  function zaehleAbweichungen() {
    abweichend.value = felder.value.filter(f => f.abweichend === true).length
  }

  /**
   * Serverstand übernehmen. `stand` ist die Antwort von `gestaltung.lesen`
   * (oder einer schreibenden Aktion — beide liefern denselben Aufbau).
   */
  function uebernehmen(stand) {
    const s = stand || {}
    felder.value = Array.isArray(s.felder) ? s.felder.map(f => ({ ...f })) : []
    skalaOrdnung.value = Array.isArray(s.skala_ordnung) ? [...s.skala_ordnung] : []
    eingaben.value = Object.fromEntries(felder.value.map(f => [f.token, String(f.wert)]))
    feldFehler.value = {}
    skalaPaare.value = []
    zaehleAbweichungen()
  }

  /**
   * Den gespeicherten Wert einer Kennzahl nachziehen: Die Antwort der
   * schreibenden Aktion ist der neue Stand — auch wenn die Oberfläche ihn
   * gerade nicht glauben will, gilt der Server.
   */
  function standUebernehmen(stand) {
    uebernehmen(stand)
  }

  async function laden({ mitteilungLeeren = true } = {}) {
    if (!sichtbar()) {
      // Kein zweiter Weg am Server vorbei: der Aufruf würde ohnehin 403
      // liefern. Hier wird gar nicht erst gefragt.
      geladen.value = false
      return false
    }
    laedt.value = true
    if (mitteilungLeeren) {
      fehler.value = ''
      erfolg.value = ''
    }
    try {
      const res = await apiCall(API + 'lesen', {})
      standUebernehmen(res.message || res)
      geladen.value = true
      return true
    } catch (grund) {
      fehler.value = meldungAus(
        grund, 'Die Gestaltung konnte nicht geladen werden. Lade die Seite neu.')
      return false
    } finally {
      laedt.value = false
    }
  }

  /**
   * Live-Prüfung: EIN Feld tippen prüft DIESES Feld und die GANZE Skala.
   * Ergebnis: Meldung am Feld + Skalenbruch (Markierung der beiden Token).
   */
  function pruefeLive(token) {
    const feld = felder.value.find(f => f.token === token)
    if (!feld) return
    const einzeln = pruefeFeld(feld, eingaben.value[token])
    feldFehler.value = {
      ...feldFehler.value,
      [token]: einzeln.ok ? '' : einzeln.text,
    }
    const skala = pruefeSkala(felder.value, eingaben.value, skalaOrdnung.value)
    skalaPaare.value = skala.paare
    // ALLE Kettenglieder neu beurteilen — nicht nur das getippte Feld. Sonst
    // bliebe eine veraltete Skalen-Meldung stehen (Bruch an --sp-3, dann
    // --sp-8 tippen, dann --sp-3 beheben: der Satz blieb an --sp-4).
    // Je Glied: Teil eines Bruch-Paares -> Skalen-Satz (damit man sieht,
    // welches Feld); sonst die eigene Feldprüfung (leer, wenn in Ordnung).
    const neu = { ...feldFehler.value }
    for (const t of skalaOrdnung.value) {
      const feld2 = felder.value.find(f => f.token === t)
      if (!feld2) continue
      if (skala.paare.some(paar => paar.includes(t))) {
        neu[t] = skala.text
      } else {
        const r = pruefeFeld(feld2, eingaben.value[t])
        neu[t] = r.ok ? '' : r.text
      }
    }
    feldFehler.value = neu
    return {
      ok: einzeln.ok && skala.ok,
      text: einzeln.text || (skala.paare.some(p => p.includes(token)) ? skala.text : ''),
    }
  }

  /** Alles prüfen (vor dem Speichern) — `true`, wenn nichts zu beanstanden ist. */
  function pruefeAlles() {
    const einzeln = {}
    let allesOk = true
    let erster = ''
    for (const feld of felder.value) {
      const r = pruefeFeld(feld, eingaben.value[feld.token])
      einzeln[feld.token] = r.ok ? '' : r.text
      if (!r.ok) {
        allesOk = false
        if (!erster) erster = r.text
      }
    }
    const skala = pruefeSkala(felder.value, eingaben.value, skalaOrdnung.value)
    if (!skala.ok) {
      allesOk = false
      for (const [a, b] of skala.paare) {
        einzeln[a] = einzeln[a] || skala.text
        einzeln[b] = einzeln[b] || skala.text
      }
    }
    feldFehler.value = einzeln
    skalaPaare.value = skala.paare
    return {
      ok: allesOk,
      text: skala.ok ? '' : skala.text,
      einzeln: erster,
    }
  }

  /** Die Felder, die gegen den gespeicherten Stand geändert sind. */
  function geaendert() {
    return geaenderteFelder(felder.value, eingaben.value)
  }

  /** Nur speichern, wenn etwas geändert ist (Prinzip S1/I1). */
  const kannSpeichern = () => geaendert().length > 0

  async function speichern() {
    fehler.value = ''
    erfolg.value = ''
    gespeichert.value = false
    rueckgaengig.value = null
    // BARRIEREFREIHEIT: eine Prüfung, die am Feld scheitert, nennt den ersten
    // Grund auch in der Hinweisfläche — sonst stünde „Speichern“ nur scheinbar
    // wirkungslos da (kein Netzaufruf, keine Meldung; im Browser gefunden).
    const pruefung = pruefeAlles()
    if (!pruefung.ok) {
      fehler.value = pruefung.text || pruefung.einzeln
        || 'Bitte die markierten Felder berichtigen.'
      return false
    }
    speichert.value = true
    try {
      const rumpf = { werte: werteFuerServer(felder.value, eingaben.value) }
      const res = await apiCall(API + 'speichern', rumpf)
      standUebernehmen(res.message || res)
      const anzahl = felder.value.filter(f => f.abweichend === true).length
      erfolg.value = anzahl
        ? `Gespeichert. Die Oberfläche weicht jetzt in ${anzahl} Maß(en) vom Standard ab.`
        : 'Gespeichert. Die Oberfläche steht wieder auf den Standardwerten.'
      gespeichert.value = true
      await cssNeuLaden()
      return true
    } catch (grund) {
      fehler.value = meldungAus(
        grund, 'Speichern fehlgeschlagen. Deine Eingaben bleiben erhalten.')
      return false
    } finally {
      speichert.value = false
    }
  }

  /**
   * Ein Feld auf den Standard zurücksetzen. Der Vorgang ist nicht umkehrbar
   * (der alte Wert ist danach weg) — deshalb nennt die Meldung ihn, und die
   * Oberfläche lädt die alten Werte ERNEUT vom Server (bis UX2a ein echtes
   * „Rückgängig“ hat).
   */
  async function zuruecksetzenFeld(token) {
    const feld = felder.value.find(f => f.token === token)
    const alt = feld ? Number(feld.wert) : 0
    return zuruecksetzen({ token, alt, standard: feld ? Number(feld.standard) : 0 })
  }

  async function allesZuruecksetzen() {
    if (!abweichend.value) {
      erfolg.value = 'Alle Maße stehen bereits auf dem Standard.'
      return false
    }
    return zuruecksetzen({ token: null })
  }

  async function zuruecksetzen({ token = null, alt = 0, standard = 0 }) {
    fehler.value = ''
    erfolg.value = ''
    rueckgaengig.value = null
    speichert.value = true
    try {
      const res = await apiCall(API + 'zuruecksetzen', token ? { token } : {})
      standUebernehmen(res.message || res)
      rueckgaengig.value = rueckgaengigMeldung(token
        ? { ziel: 'feld', token, alt, standard }
        : { ziel: 'alle' })
      erfolg.value = token ? `${token} wurde zurückgesetzt.` : 'Alle Maße wurden zurückgesetzt.'
      gespeichert.value = true
      await cssNeuLaden()
      return true
    } catch (grund) {
      fehler.value = meldungAus(
        grund, 'Zurücksetzen fehlgeschlagen. Die Werte sind unverändert.')
      return false
    } finally {
      speichert.value = false
    }
  }

  /** Rückgängig-Meldung wegnehmen, wenn der Nutzer weiterarbeitet. */
  function meldungSchliessen() {
    rueckgaengig.value = null
  }

  /**
   * `gestaltung.css` NEU laden, ohne die Seite neu zu laden.
   *
   * Der Server liefert bei jeder Anfrage den aktuellen Stand (ETag,
   * `Cache-Control: no-cache`); `?v=` macht die Adresse neu, damit auch ein
   * Zwischenspeicher nicht die alte Datei zeigt. Danach wird `?v=` wieder
   * entfernt — das Blatt bleibt im Dokument, die Werte gelten sofort.
   */
  async function cssNeuLaden() {
    if (typeof document === 'undefined') return false
    const link = document.querySelector('link[data-gestaltung]')
      || document.querySelector('link[href*="gestaltung.css"]')
    if (!link) return false
    const adresse = frischeCssAdresse(link.getAttribute('href') || '', Date.now())
    const neu = link.cloneNode()
    neu.setAttribute('href', adresse)
    neu.setAttribute('data-gestaltung', '')
    const fertig = new Promise((loesen) => {
      neu.addEventListener('load', () => loesen(true), { once: true })
      neu.addEventListener('error', () => loesen(false), { once: true })
      // Ein Netz ohne Antwort darf die Oberfläche nicht hängen lassen.
      setTimeout(() => loesen(false), 3000)
    })
    link.after(neu)
    const okCss = await fertig
    if (okCss) link.remove()
    else neu.remove()
    return okCss
  }

  /**
   * Vorschau: die gelieferten Token als CSS-Variablen auf EIN Element setzen
   * (nur in der Musteransicht — die App selbst bleibt unberührt). Die Namen
   * kommen aus den Server-Feldern, nicht aus einer Liste hier.
   */
  function vorschauSetzen(element, abweichungen = {}) {
    if (!element || !element.style) return
    for (const feld of felder.value) {
      const r = pruefeFeld(feld, abweichungen[feld.token] ?? eingaben.value[feld.token])
      const wert = r.ok ? r.wert : Number(feld.standard)
      element.style.setProperty(feld.token, `${wert}px`)
    }
  }

  function vorschauEntfernen(element) {
    if (!element || !element.style) return
    for (const feld of felder.value) element.style.removeProperty(feld.token)
  }

  return {
    // Stand
    laedt, speichert, geladen, fehler, erfolg, gespeichert, abweichend,
    felder, eingaben, feldFehler, skalaPaare, skalaOrdnung, rueckgaengig,
    // Regeln
    sichtbar, pruefeLive, pruefeAlles, geaendert, kannSpeichern,
    // Aktionen
    laden, speichern, zuruecksetzenFeld, allesZuruecksetzen, meldungSchliessen,
    // Vorschau
    vorschauSetzen, vorschauEntfernen, cssNeuLaden,
  }
}
