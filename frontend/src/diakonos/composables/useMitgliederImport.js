/**
 * useMitgliederImport — Datenzugriff des Import-Reiters (N11).
 *
 * Bündelt ALLE Aufrufe des Reiters an einer Stelle (Kartenvorgabe: „API-Zugriff
 * gebuendelt“). Die Serverantworten werden unverändert weitergereicht; die
 * Oberfläche zeigt die strukturierten Meldungen (`pfad`/`code`/`meldung`/
 * `hinweis`) so an, wie sie kommen.
 *
 * Eiserne Regel aus dem Kartentext: Rechte kommen vom Server. Hier wird
 * nichts vorab „erlaubt“; ein fehlendes Recht endet in einer Fehlermeldung,
 * nicht in einer stillen Ausblendung.
 */
import { ref } from 'vue'
import { apiCall } from './useApi.js'

const API = 'diakronos.diakonos.api.mitglieder.'

/** Groesste Datei, die der Server annimmt (1 MB, siehe `MAX_IMPORT_BYTES`). */
export const MAX_IMPORT_BYTES = 1_000_000
/** Groesste Zeilenzahl (siehe `MAX_IMPORT_ZEILEN`). */
export const MAX_IMPORT_ZEILEN = 2000

export function useMitgliederImport() {
  const prueft = ref(false)
  const uebernimmt = ref(false)
  const vorschau = ref(null)
  const ergebnis = ref(null)

  /** Vorpruefung: Server liest die Datei und meldet je Zeile neu/Dublette/Fehler. */
  async function pruefen(csvInhalt, spalten) {
    prueft.value = true
    try {
      const antwort = await apiCall(API + 'import_mitglieder_vorschau', {
        csv_inhalt: csvInhalt,
        spalten: spalten && Object.keys(spalten).length ? spalten : undefined,
      })
      vorschau.value = antwort || null
      return vorschau.value
    } finally {
      prueft.value = false
    }
  }

  /**
   * Uebernahme. `dublettenUeberspringen=false` verlangt zwingend
   * `bestaetigt=true` — der Server lehnt das Anlegen von Dubletten ohne
   * ausdrueckliche Bestaetigung ab (Vorgabe: Standard 0).
   */
  async function uebernehmen(csvInhalt, spalten, { dublettenUeberspringen = true, bestaetigt = false } = {}) {
    uebernimmt.value = true
    try {
      const antwort = await apiCall(API + 'import_mitglieder_uebernehmen', {
        csv_inhalt: csvInhalt,
        spalten: spalten && Object.keys(spalten).length ? spalten : undefined,
        dubletten_ueberspringen: dublettenUeberspringen,
        bestaetigt: bestaetigt ? 1 : 0,
      })
      ergebnis.value = antwort || null
      return ergebnis.value
    } finally {
      uebernimmt.value = false
    }
  }

  /** Export der gefilterten Mitgliederliste (Kopfzeile der Liste, N11). */
  async function exportieren({ suche = '', status = '', persoenlicheDaten = false } = {}) {
    const antwort = await apiCall(API + 'exportiere_mitglieder_csv', {
      suche: suche || undefined,
      status: status || undefined,
      persoenliche_daten: persoenlicheDaten === true,
    })
    return antwort || { csv: '', dateiname: 'mitglieder.csv', anzahl: 0 }
  }

  function zuruecksetzen() {
    vorschau.value = null
    ergebnis.value = null
  }

  return {
    prueft,
    uebernimmt,
    vorschau,
    ergebnis,
    pruefen,
    uebernehmen,
    exportieren,
    zuruecksetzen,
  }
}
