/**
 * ON-5 (E2-5) — die Gemeindemarke (Logo) EINE Stelle fortschreiben.
 *
 * WARUM EIN EIGENES MODUL
 * Es gibt zwei Wege, ein Logo zu setzen: den Schritt „Gemeinde“ im
 * Einrichtungs-Assistenten (`useEinrichtungsAssistent`) und die
 * Gemeinde-Einstellungen (`useGemeinde`). Beide haben nach dem Upload nur den
 * eigenen Zustand fortgeschrieben. Die Seitenleiste liest aber das Boot-Objekt
 * (`window.__DIakonosBOOT.logo_url`, Startwert beim Laden) — sie blieb deshalb
 * auf dem alten Logo stehen, bis die Seite neu geladen wurde (Befund E2-5 im
 * Onboarding-Durchlauf).
 *
 * Hier steht deshalb die EINE Stelle:
 *   1. Boot-Objekt nachziehen (dieselbe Adresse, die der Server liefert —
 *      mit Betriebspräfix und `?v=`-Hash, nichts wird nachgebaut).
 *   2. `dk-marke-geaendert` melden. Das Boot-Objekt ist plain JS; ein
 *      `computed` darauf zeichnet NICHT neu. `AppSidebar` hält darum eine
 *      `ref`, die dieses Ereignis fortschreibt.
 *
 * Keine Vue-Importe: das Modul muss auch im Knoten-Test ohne `vue` laufen.
 */

/** Ereignis, das die Anzeige der Marke neu zeichnen lässt. */
export const MARKE_EREIGNIS = 'dk-marke-geaendert'

/**
 * Neue Marke bekannt machen (leerer Wert = kein Logo).
 *
 * @param {string} url Adresse aus der Server-Antwort (`logo_url`).
 * @returns {string} die übernommene Adresse ('' = kein Logo).
 */
export function merkeGemeindeMarke(url) {
  const wert = String(url || '')
  if (typeof window === 'undefined') return wert
  const boot = window.__DIakonosBOOT
  if (boot) boot.logo_url = wert || null
  if (typeof window.dispatchEvent === 'function' && typeof Event === 'function') {
    window.dispatchEvent(new Event(MARKE_EREIGNIS))
  }
  return wert
}

/** Die aktuell bekannte Marke (leer = Monogramm). */
export function geleseneGemeindeMarke() {
  if (typeof window === 'undefined') return ''
  return String(window.__DIakonosBOOT?.logo_url || '')
}
