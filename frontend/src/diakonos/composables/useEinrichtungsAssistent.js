/**
 * ON-3 — Zustand des Einrichtungs-Assistenten (Schritt, Status, Entwürfe).
 *
 * WARUM EIN EIGENES MODUL MIT ÄUSSEREM ZUSTAND
 * Die Kopfzeile („Speichern und später fortsetzen“), die Schrittleiste, die
 * Fußleiste und der jeweilige Schritt selbst zeigen denselben Zustand. Läge er
 * in der Seite, müsste jede dieser Stellen ihn durchreichen — und der
 * Schrittwechsel aus der Leiste wäre ein zweiter Weg neben „Weiter/Zurück“.
 * Hier ist er EINE Quelle für die ganze Seite (`pages/einrichtung/Assistent.vue`).
 *
 * Die Regeln selbst stehen in `einrichtungAssistent.mjs` (reine Logik, ohne
 * Vue und ohne Anfrage) — dieses Modul hält nur den Zustand und die Aufrufe an
 * den Server. Alle schreibenden Aufrufe gehen über `apiCall` (POST, CSRF,
 * Sitzungsdialog), wie es der Vertrag docs/ON2-VERTRAG.md verlangt.
 */
import { computed, reactive, ref } from 'vue'

import { apiCall, apiAntwortPruefen } from './useApi.js'
// WEB-5b: EINE Quelle fuer den Betriebs-Praefix (DIAKRONOS_BASE_PATH) — auch
// der Multipart-Weg des Logos laeuft darueber, nie ueber einen festen Pfad.
import { apiUrl } from '../../shared/basis.js'
import {
  logoDateiFehler,
  logoVorschau,
  naechsterSchritt,
  pruefeSchritt,
  schrittListe,
  schrittIndex,
  speicherRumpf,
  startSchritt,
  vorherigerSchritt,
} from './einrichtungAssistent.mjs'

const GEMEINDE = 'diakronos.diakonos.api.gemeinde.'
const EINRICHTUNG = 'diakronos.diakonos.api.einrichtung.'

/** Leere Eingaben aller Schritte (ein Objekt, damit Felder nie `undefined` sind). */
function leereEingaben() {
  return {
    gemeindename: '',
    kurzname: '',
    strasse: '',
    plz: '',
    ort: '',
    kontakt_email: '',
    telefon: '',
    website: '',
  }
}

/**
 * Zustand des Assistenten. Bewusst MODULWEIT: die Seite wird beim Wechsel der
 * Adresse neu aufgebaut (`<component :key="currentHash">`), und ein
 * Neuaufbau darf nicht die halb getippten Eingaben verlieren.
 */
const status = ref(null)
const gemeinde = ref(null)
const schritt = ref('gemeinde')
const laedt = ref(false)
const speichert = ref(false)
const fehler = ref('')
const feldFehler = reactive({})
const eingaben = reactive(leereEingaben())
const moduleEingaben = reactive({})
const mitgliederWahl = ref('spaeter')
// ON-3: Vorschläge sind vorausgewählt (Entwurf 08: „Sie können das abwählen“).
const KALENDER_VORAUSWAHL = { Gottesdienste: true, Gemeindekalender: true }
const kalenderAuswahl = reactive({ ...KALENDER_VORAUSWAHL })
const gruppeSpater = ref(false)
const logoFehler = ref('')
const logoLaeuft = ref(false)
const logoDatei = ref(null)

/** Ein Zurücksetzen für Tests und nach abgeschlossenem Assistenten. */
export function setzeAssistentZurueck() {
  status.value = null
  gemeinde.value = null
  schritt.value = 'gemeinde'
  laedt.value = false
  speichert.value = false
  fehler.value = ''
  for (const feld of Object.keys(feldFehler)) delete feldFehler[feld]
  Object.assign(eingaben, leereEingaben())
  for (const feld of Object.keys(moduleEingaben)) delete moduleEingaben[feld]
  mitgliederWahl.value = 'spaeter'
  for (const feld of Object.keys(kalenderAuswahl)) delete kalenderAuswahl[feld]
  Object.assign(kalenderAuswahl, KALENDER_VORAUSWAHL)
  gruppeSpater.value = false
  logoFehler.value = ''
  logoLaeuft.value = false
  logoDatei.value = null
}

/** Die Schrittleiste mit Zuständen (linke Leiste bzw. Mobil-Kurzform). */
const schritte = computed(() => schrittListe(status.value))

/** Ist der Assistent schon abgeschlossen? Dann zeigt die Seite die Checkliste. */
const abgeschlossen = computed(() => status.value?.assistent_abgeschlossen === true)

/** Die sieben Punkte der Checkliste (Frame 09/15) — nur die offenen brauchen „Einrichten“. */
const punkte = computed(() => (Array.isArray(status.value?.punkte) ? status.value.punkte : []))

/** Erledigte Punkte, mit denen der Satz unter der Überschrift gebaut wird. */
const offenePunkte = computed(() => punkte.value.filter((p) => p && p.erledigt === false))

/** Fortschrittstext unter „Einrichtung“ in der Leiste. */
const fortschrittText = computed(() => {
  const gesamt = Number(status.value?.gesamt_anzahl) || 0
  const offen = Number(status.value?.offen_anzahl) || 0
  if (!gesamt) return ''
  return `${gesamt - offen} von ${gesamt} erledigt`
})

/** Die Kacheln des Modul-Schritts — NUR Module, die es tatsächlich gibt. */
const moduleListe = computed(() => (Array.isArray(gemeinde.value?.module) ? gemeinde.value.module : []))

/** Adresse für die Logo-Vorschau (oder `null` → Monogramm). */
const logoQuelle = computed(() => logoVorschau(gemeinde.value))

/** Monogramm-Buchstabe der Kopfzeile (Kurzname vor Gemeindename, Entwurf 04). */
const monogramm = computed(() => {
  const kandidaten = [gemeinde.value?.kurzname, gemeinde.value?.gemeindename, eingaben.gemeindename]
  for (const roh of kandidaten) {
    const text = String(roh ?? '').trim()
    if (!text) continue
    const erstes = text.replace(/^[^\p{L}\p{N}]+/u, '')[0]
    if (!erstes) continue
    return erstes.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toUpperCase()
  }
  return 'D'
})

/** Fehler dort ablegen, wo das Feld steht (und die alte Meldung räumen). */
function setzeFeldfehler(neu) {
  for (const feld of Object.keys(feldFehler)) delete feldFehler[feld]
  for (const [feld, meldung] of Object.entries(neu || {})) feldFehler[feld] = meldung
}

/**
 * Status und Gemeinde-Stand laden. Ohne geladenen Stand wird NICHTS
 * geschrieben — eine Oberfläche auf Teilstand darf keine Daten überschreiben
 * (dieselbe Regel wie in `useGemeinde`).
 *
 * @param {{start?: boolean}} optionen start=true setzt beim ersten Laden den
 *        Einstiegsschritt (Wiedereinstieg, W4). Ein späteres Nachladen lässt
 *        den gewählten Schritt stehen.
 */
export async function ladeAssistent({ start = false } = {}) {
  laedt.value = true
  fehler.value = ''
  try {
    const [statusAntwort, gemeindeAntwort] = await Promise.all([
      apiCall(EINRICHTUNG + 'status', {}),
      apiCall(GEMEINDE + 'gemeinde_get_einstellungen', {}),
    ])
    status.value = statusAntwort?.message || statusAntwort
    const g = gemeindeAntwort?.message || gemeindeAntwort
    gemeinde.value = g || null
    // Eingaben mit dem Serverstand füllen; was die Person schon getippt hat,
    // bleibt stehen (ein Nachladen darf keine Eingabe überschreiben).
    const gelesen = speicherRumpf('kontakt', g || {}, {})
    for (const [feld, wert] of Object.entries(gelesen)) {
      if (!String(eingaben[feld] ?? '').trim() && wert) eingaben[feld] = wert
    }
    for (const modul of (g?.module || [])) {
      if (!(modul.schluessel in moduleEingaben)) {
        moduleEingaben[modul.schluessel] = modul.sichtbar === true
      }
    }
    if (start) {
      schritt.value = startSchritt(status.value)
      if (schritt.value === 'fertig' && !status.value?.assistent_abgeschlossen) {
        // Alle Schritte erledigt, aber noch nicht abgeschlossen: der Fertig-
        // Schirm zeigt die Checkliste; abgeschlossen wird per Knopf.
        schritt.value = 'fertig'
      }
    }
    return true
  } catch (grund) {
    fehler.value = grund?.message || 'Die Einrichtung konnte nicht geladen werden.'
    return false
  } finally {
    laedt.value = false
  }
}

/** Schritt-Schlüssel setzen (Leiste, „Zurück“, „Weiter“). */
export function geheZu(schluessel) {
  if (schrittIndex(schluessel) < 0) return false
  fehler.value = ''
  setzeFeldfehler({})
  logoFehler.value = ''
  schritt.value = schluessel
  return true
}

/** `einrichtung.schritt_setzen` — Prozessstand, keine Fachdaten. */
async function setzeSchrittZustand(schluessel, zustand) {
  if (!['gemeinde', 'kontakt', 'mailversand', 'module', 'mitglieder_kalender'].includes(schluessel)) {
    return true
  }
  const antwort = await apiCall(EINRICHTUNG + 'schritt_setzen', { schluessel, zustand })
  const d = antwort?.message || antwort
  // Lokal nachziehen, damit die Leiste sofort stimmt (Server bleibt die Quelle;
  // der nächste `ladeAssistent` überschreibt es mit dem echten Stand).
  if (status.value && Array.isArray(status.value.schritte)) {
    const eintrag = status.value.schritte.find((s) => s.schluessel === schluessel)
    if (eintrag) eintrag.zustand = d?.zustand || zustand
  }
  return true
}

/**
 * „Weiter“: speichert die Eingaben des Schritts, setzt ihn auf erledigt und
 * geht einen Schritt weiter. Auf „Fertig“ gibt es nichts zu speichern.
 *
 * @returns {Promise<boolean>} false, wenn gespeichert/validiert nicht ging —
 *          dann bleibt der Schritt stehen und der Fehler ist am Feld.
 */
export async function weiter() {
  const aktuell = schritt.value
  if (aktuell === 'fertig') return false
  fehler.value = ''
  setzeFeldfehler({})
  speichert.value = true
  try {
    if (aktuell === 'gemeinde' || aktuell === 'kontakt') {
      const pruefung = pruefeSchritt(aktuell, eingaben)
      if (Object.keys(pruefung).length) {
        setzeFeldfehler(pruefung)
        return false
      }
      await apiCall(GEMEINDE + 'gemeinde_speichern',
        speicherRumpf(aktuell, gemeinde.value || {}, eingaben))
      // Der Gemeinde-Stand hat sich geändert (Name/Anschrift) — neu lesen, damit
      // Kopfzeile, Monogramm und die Prüfungen der Folgeschritte stimmen.
      try {
        const antwort = await apiCall(GEMEINDE + 'gemeinde_get_einstellungen', {})
        gemeinde.value = antwort?.message || antwort
      } catch { /* Anzeige bleibt auf dem alten Stand; kein Schreibweg */ }
    } else if (aktuell === 'module') {
      // Nur was sich geändert hat — jeder Schalter ist ein eigener Aufruf.
      for (const modul of moduleListe.value) {
        const gewuenscht = moduleEingaben[modul.schluessel] === true
        if (gewuenscht === (modul.sichtbar === true)) continue
        await apiCall(GEMEINDE + 'gemeinde_setze_modul', {
          schluessel: modul.schluessel, sichtbar: gewuenscht,
        })
        modul.sichtbar = gewuenscht
      }
    } else if (aktuell === 'mitglieder_kalender') {
      const namen = Object.entries(kalenderAuswahl)
        .filter(([, gewaehlt]) => gewaehlt === true)
        .map(([name]) => name)
      if (namen.length) {
        await apiCall(EINRICHTUNG + 'kalender_vorschlag_anlegen', { namen })
      }
    }
    // mailversand: die Felder speichert die Schrittkomponente selbst
    // (useMailversand.speichern/Testmail) — hier nur der Prozessstand.
    await setzeSchrittZustand(aktuell, 'erledigt')
    const naechster = naechsterSchritt(aktuell)
    if (naechster) {
      schritt.value = naechster
      // Nachgelagerte Schritte hängen an echten Daten (Mitglieder, Kalender,
      // Module) — nach jedem Schritt leise nachladen.
      ladeAssistentNebenher()
    }
    return true
  } catch (grund) {
    fehler.value = grund?.message || 'Das Speichern hat nicht geklappt. Bitte erneut versuchen.'
    return false
  } finally {
    speichert.value = false
  }
}

/** Status nachladen, ohne den Bildschirm in den Ladezustand zu setzen. */
function ladeAssistentNebenher() {
  apiCall(EINRICHTUNG + 'status', {})
    .then((antwort) => { status.value = antwort?.message || antwort })
    .catch(() => { /* Anzeige bleibt auf dem bekannten Stand */ })
}

/**
 * „Überspringen“ (W3): setzt den Schritt auf `uebersprungen` und geht weiter.
 * Auf „Fertig“ gibt es nichts zu überspringen.
 */
export async function ueberspringen() {
  const aktuell = schritt.value
  if (aktuell === 'fertig') return false
  speichert.value = true
  fehler.value = ''
  try {
    await setzeSchrittZustand(aktuell, 'uebersprungen')
    const naechster = naechsterSchritt(aktuell)
    if (naechster) {
      schritt.value = naechster
      ladeAssistentNebenher()
    }
    return true
  } catch (grund) {
    fehler.value = grund?.message || 'Der Schritt konnte nicht übersprungen werden.'
    return false
  } finally {
    speichert.value = false
  }
}

/** „Zurück“ — ohne Speichern (der Stand wurde beim „Weiter“ gesichert). */
export function zurueck() {
  const vorher = vorherigerSchritt(schritt.value)
  if (!vorher) return false
  return geheZu(vorher)
}

/**
 * „Speichern und später fortsetzen“ (Kopfzeile, W1): nur zur Übersicht —
 * der Fortschritt bleibt, weil der Schrittstand auf dem Server liegt.
 */
export const SPATER_ZIEL = '#/'

/** Logo hochladen (`gemeinde.gemeinde_logo_hochladen`, multipart). */
export async function ladeLogoHoch(datei) {
  logoFehler.value = ''
  const pruefung = logoDateiFehler(datei)
  if (pruefung) {
    logoFehler.value = pruefung
    return false
  }
  logoLaeuft.value = true
  try {
    // Der Gemeinde-Endpunkt nimmt den INHALT der Datei (multipart), nicht den
    // Pfad aus `upload_file` — deshalb hier der direkte Multipart-Weg, mit
    // derselben CSRF-Heilung und Sitzungsprüfung wie `uploadDatei`
    // (`apiAntwortPruefen`), aber ohne den Umweg über die Ablage.
    const url = apiUrl(GEMEINDE + 'gemeinde_logo_hochladen')
    const form = new FormData()
    form.append('file', datei, datei.name)
    const anfrage = () => fetch(url, {
      method: 'POST',
      headers: { 'X-Frappe-CSRF-Token': window.__DIakonosBOOT?.csrf_token || '' },
      body: form,
    })
    const erste = await anfrage()
    const daten = await apiAntwortPruefen(erste, { anfrage })
    const res = daten?.dkAntwort || erste
    if (!res.ok || daten?.exc) {
      throw new Error(daten?.message || `HTTP ${res.status}`)
    }
    const d = daten?.message || daten
    if (gemeinde.value) {
      gemeinde.value.logo_url = d?.logo_url || ''
      gemeinde.value.logo_vorhanden = d?.logo_vorhanden === true
    }
    logoDatei.value = null
    return true
  } catch (grund) {
    logoFehler.value = grund?.message || 'Das Logo konnte nicht hochgeladen werden.'
    return false
  } finally {
    logoLaeuft.value = false
  }
}

/** Logo entfernen (`gemeinde.gemeinde_logo_entfernen`, idempotent). */
export async function entferneLogo() {
  logoFehler.value = ''
  logoLaeuft.value = true
  try {
    const antwort = await apiCall(GEMEINDE + 'gemeinde_logo_entfernen', {})
    const d = antwort?.message || antwort
    if (gemeinde.value) {
      gemeinde.value.logo_url = d?.logo_url || ''
      gemeinde.value.logo_vorhanden = d?.logo_vorhanden === true
    }
    logoDatei.value = null
    return true
  } catch (grund) {
    logoFehler.value = grund?.message || 'Das Logo konnte nicht entfernt werden.'
    return false
  } finally {
    logoLaeuft.value = false
  }
}

/** Abschluss (W2, Schritt 6): `einrichtung.abschliessen`, danach steht die
 * Checkliste als „Einstellungen → Einrichtung“ zur Verfügung (W4).
 */
export async function abschliessen() {
  speichert.value = true
  fehler.value = ''
  try {
    await apiCall(EINRICHTUNG + 'abschliessen', {})
    if (status.value) status.value.assistent_abgeschlossen = true
    await ladeAssistent()
    return true
  } catch (grund) {
    fehler.value = grund?.message || 'Der Abschluss konnte nicht gespeichert werden.'
    return false
  } finally {
    speichert.value = false
  }
}

/** Feldmeldungen für ein Feld (Vorlagenhilfe). */
export function meldungZu(feld) {
  return feldFehler[feld] || ''
}

export function useEinrichtungsAssistent() {
  return {
    status, gemeinde, schritt, laedt, speichert, fehler, eingaben, feldFehler,
    moduleEingaben, mitgliederWahl, kalenderAuswahl, gruppeSpater,
    logoFehler, logoLaeuft, logoDatei,
    schritte, abgeschlossen, punkte, offenePunkte, fortschrittText,
    moduleListe, logoQuelle, monogramm,
    ladeAssistent, geheZu, weiter, ueberspringen, zurueck, abschliessen,
    ladeLogoHoch, entferneLogo,
  }
}
