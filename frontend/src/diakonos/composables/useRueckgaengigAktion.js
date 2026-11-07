/**
 * UX2c — EIN Helfer für „sofort ausführen, dann Rückgängig anbieten“.
 *
 * Bisher rief jede Seite `showToast(...)` mit eigenem Text und einem eigenen
 * `onClick` — drei Stellen mit drei Schreibweisen (Beiträge, Wiki, Lieder).
 * Der Papierkorb (UX2b) bleibt die Quelle für den TEXT („… ist im Papierkorb —
 * bis zum … rückgängig zu machen“), der Rückgängig-Stapel (UX2a) für die
 * Tastatur (Strg+Z) und die Frist. Dieser Helfer verbindet beides:
 *
 *   const { abmelden, mitRueckgaengig } = useRueckgaengigAktion()
 *   await mitRueckgaengig({
 *     beschreibung: papierkorbMeldung(titel, antwort?.wiederherstellbar_bis),
 *     zurueck: () => wiederherstellen('beitrag', id),
 *     danach: loadPosts,
 *   })
 *
 * Ergebnis der Rücknahme: Erfolg → kurze Bestätigung + `danach()`; Fehler →
 * Fehlermeldung, die Aktion bleibt verbraucht (der Stapel nimmt nie zweimal
 * zurück). Der Text der Meldung kommt FERTIG herein, damit die Seiten ihre
 * bisherigen Texte (Papierkorb-Frist!) behalten.
 */
import { onBeforeUnmount } from 'vue'
import { useRueckgaengig } from './useRueckgaengig.js'
import { showToast } from './useToast.js'

/**
 * @returns {{mitRueckgaengig: Function, abmelden: Function,
 *            registrieren: Function, zuruecknehmen: Function}}
 */
export function useRueckgaengigAktion() {
  const { registrieren, zuruecknehmen, abmelden } = useRueckgaengig()
  // Die Verbindung lebt genau so lange wie die Seite, die sie holt (F4 im
  // Stapel: der Strg+Z-Zuhörer fällt beim Verlassen).
  onBeforeUnmount(abmelden)

  /**
   * Eine bereits ausgeführte Aktion anmelden und ihre Meldung zeigen.
   *
   * @param {{beschreibung: string, zurueck: Function, danach?: Function,
   *          erfolg?: string}} angaben
   *        `beschreibung` steht in der Meldung (FERTIG formuliert),
   *        `zurueck()` führt die Gegenrichtung aus und liefert
   *        `{ok, fehler?}` oder `true`,
   *        `danach()` lädt die Liste neu (nach Erfolg UND nach Fehler),
   *        `erfolg` ist die Bestätigung nach geglückter Rücknahme.
   * @returns {Promise<{id: number, beschreibung: string}>}
   */
  async function mitRueckgaengig({ beschreibung, zurueck, danach = null, erfolg = '' }) {
    const eintrag = registrieren(beschreibung, async () => {
      let ergebnis = { ok: true }
      try {
        ergebnis = await zurueck()
      } catch (fehler) {
        ergebnis = { ok: false, fehler: fehler?.message || '' }
      }
      if (ergebnis === true || ergebnis === undefined) ergebnis = { ok: true }
      if (ergebnis?.ok) {
        if (erfolg) showToast(erfolg, 'success')
      } else {
        showToast(ergebnis?.fehler || 'Das Zurücknehmen hat nicht geklappt.', 'error')
      }
      // Auch nach einem Fehler neu laden: der angezeigte Stand soll die
      // Wahrheit des Servers zeigen, nicht den Stand von vor dem Versuch.
      if (typeof danach === 'function') await danach()
      return ergebnis
    })
    return eintrag
  }

  return { mitRueckgaengig, abmelden, registrieren, zuruecknehmen }
}
