/**
 * PF2: Reine Hilfsfunktionen der Lieder-Liste, ausgelagert damit sie testbar
 * sind (die Seite selbst nutzt sie; die Logik bleibt in `Lieder.vue` gleich).
 *
 * Bewusst winzig und ohne Vue/Netz — nur die Entscheidungen, die man
 * nachpruefen koennen muss:
 *   - WANN wird der Browser-Cache benutzt (nur ungefilterter Erstaufruf)
 *   - WIE sieht der Cache-Schluessel aus (Seitengroesse + Start + Version,
 *     KEINE Filter/Suche — die werden immer frisch geholt)
 *   - WIE sehen die Aufruf-Parameter der Liste aus (Seite + Suche + Filter)
 */

export const CACHE_NAME = 'musik_get_lieder'
export const CACHE_VERSION = 2
export const PAGE = 50

/** Parameter des Listaufrufs aus Suchtext + Filtern. */
export function listenArgs({ seite, suche = '', filter = {} } = {}) {
  return {
    limit: PAGE,
    start: seite || 0,
    ...(suche && suche.trim() ? { suche: suche.trim() } : {}),
    ...(filter.gruppe ? { gruppe: filter.gruppe } : {}),
    ...(filter.kategorie ? { kategorie: filter.kategorie } : {}),
    ...(filter.anlass ? { anlass: filter.anlass } : {}),
    ...(filter.rechte_status ? { rechte_status: filter.rechte_status } : {}),
  }
}

/** Cache-Schluessel-Argumente des ungefilterten Erstaufrufs. */
export function cacheArgs({ filter = {}, suche = '' } = {}) {
  // Nur der ungefilterte Erstaufruf darf gecacht werden.
  if (!cacheAktiv({ filter, suche })) return null
  return { limit: PAGE, start: 0, version: CACHE_VERSION }
}

/** Ist der Cache fuer den aktuellen Zustand ueberhaupt erlaubt? */
export function cacheAktiv({ filter = {}, suche = '' } = {}) {
  const gefiltert = !!(filter.gruppe || filter.kategorie || filter.anlass || filter.rechte_status)
  return !(suche || '').trim() && !gefiltert
}
