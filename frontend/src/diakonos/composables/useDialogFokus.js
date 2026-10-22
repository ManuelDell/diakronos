/**
 * useDialogFokus — Tastaturfuehrung fuer modale Fenster (DES-R6).
 *
 * Warum: Nur `components/ui/DkDialog.vue` fuehrte den Fokus korrekt. Die
 * Eigenbauten (DkModal, Stammdaten-Panel, „Mehr“-Blatt der Handy-Navigation,
 * Termin-Fenster des Kalenders) liessen den Fokus auf dem Auslöser hinter dem
 * Fenster stehen: 14 Tab-Sprünge wanderten durch die Seite dahinter, Esc
 * schloss nicht, Screenreader lasen das Fenster nicht vor.
 *
 * Diese Composable bringt dieselbe Logik wie DkDialog:
 *   - beim Oeffnen Fokus in das Fenster (erstes fokussierbares Element,
 *     sonst der Container selbst),
 *   - Tab/Shift+Tab bleiben im Fenster,
 *   - Esc schliesst (abschaltbar),
 *   - beim Schliessen zurueck auf das vorher fokussierte Element.
 *
 * Benutzung:
 *   const fenster = ref(null)                  // Elternelement des Fensters
 *   useDialogFokus(offen, fenster, () => schliessen())
 */
import { ref, watch, nextTick, onBeforeUnmount } from 'vue'

export const FOKUS_SELECTOR = [
  'a[href]', 'button:not([disabled])', 'input:not([disabled])',
  'select:not([disabled])', 'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',')

const fensterStapel = []

export function useDialogFokus(offen, fensterRef, schliessen, { esc = true } = {}) {
  let vorherFokus = null
  const kennung = {}
  const istOberstes = () => fensterStapel.at(-1) === kennung

  /**
   * Aufräumen: Listener abmelden, Marke aus dem Stapel nehmen und den Fokus
   * zurückgeben.
   *
   * P3-4 (Restpunkt 6): Die Rückgabe des Fokus darf nicht davon abhängen, dass
   * dieses Fenster das oberste ist. Wird eine Komponente bei OFFENEM Fenster
   * ausgehängt (Eltern-`v-if`, Routenwechsel), feuert der Watcher nie mit
   * `false`; `onBeforeUnmount` ruft diese Funktion dann als einzigen Weg.
   * Vorher blieb der Fokus in einem entfernten Baum stehen — Screenreader und
   * Tastatur verloren die Orientierung. Jetzt wird der Fokus zurückgegeben,
   * sobald er sich im Fenster oder in einem nicht mehr verbundenen Element
   * befindet.
   */
  function aufraeumen({ erzwingen = false } = {}) {
    if (typeof document === 'undefined') return
    document.removeEventListener('keydown', escGlobal)
    const i = fensterStapel.indexOf(kennung)
    const warOben = istOberstes()
    if (i >= 0) fensterStapel.splice(i, 1)
    const aktiv = document.activeElement
    const fokusVerloren = !aktiv
      || aktiv === document.body
      || fensterRef.value?.contains(aktiv)
      || aktiv?.isConnected === false
    if ((warOben || erzwingen || fokusVerloren)
        && vorherFokus && vorherFokus.isConnected !== false) {
      vorherFokus.focus?.()
    }
    vorherFokus = null
  }

  function fokussierbar() {
    const el = fensterRef.value
    if (!el) return []
    return Array.from(el.querySelectorAll(FOKUS_SELECTOR))
      .filter(k => k.offsetParent !== null || k === document.activeElement)
  }

  function tastenFaenger(e) {
    if (!istOberstes()) return
    if (e.key === 'Escape' && esc) {
      e.stopPropagation()
      schliessen()
      return
    }
    if (e.key !== 'Tab') return
    const elemente = fokussierbar()
    if (!elemente.length) { e.preventDefault(); return }
    const erstes = elemente[0]
    const letztes = elemente[elemente.length - 1]
    const aktiv = document.activeElement
    if (e.shiftKey && aktiv === erstes) { e.preventDefault(); letztes.focus() }
    else if (!e.shiftKey && aktiv === letztes) { e.preventDefault(); erstes.focus() }
  }

  function escGlobal(e) {
    if (e.key === 'Escape' && offen.value && esc && istOberstes()) {
      e.stopImmediatePropagation()
      schliessen()
    }
  }

  watch(offen, async (ist) => {
    if (typeof document === 'undefined') return
    if (ist) {
      vorherFokus = document.activeElement
      fensterStapel.push(kennung)
      document.addEventListener('keydown', escGlobal)
      await nextTick()
      if (!offen.value || !istOberstes()) return
      const elemente = fokussierbar()
      const start = elemente.find(el => el.matches('[autofocus]'))
        || elemente.find(el => el.matches('input:not([type=hidden]), textarea, select, [contenteditable=true]'))
        || elemente[0]
      if (start) start.focus()
      else fensterRef.value?.focus?.()
    } else {
      aufraeumen()
    }
  }, { immediate: true })

  onBeforeUnmount(() => aufraeumen({ erzwingen: true }))

  return { tastenFaenger, fokussierbar }
}

export default useDialogFokus
