/**
 * theme — Startwert und Umschalten des Hell/Dunkel-Modus (DES-R22).
 *
 * Befund: Der Umschalter lag nur in der Seitenleiste — am Handy ist die
 * Seitenleiste `display:none`, der Knopf damit unerreichbar. Außerdem kam der
 * Startwert fest aus 'light'; die Systemeinstellung des Nutzers
 * (`prefers-color-scheme: dark`) wurde ignoriert.
 *
 * Diese Datei ist ohne Vue/DOM-Attrappe prüfbar: die Umgebung (localStorage,
 * matchMedia) wird als Parameter übergeben.
 */

export const THEME_SCHLUESSEL = 'dk-theme'

/**
 * Startwert des Themes.
 * Reihenfolge: bewusste Wahl (Speicher) → Systemeinstellung → 'light'.
 * @param {{speicher?: {getItem(k:string):string|null}, system?: 'dark'|'light'|null}} umgebung
 */
export function startTheme({ speicher = null, system = null } = {}) {
  try {
    const gespeichert = speicher?.getItem(THEME_SCHLUESSEL)
    if (gespeichert === 'dark' || gespeichert === 'light') return gespeichert
  } catch {
    // gesperrter Speicher (Privatmodus) → Systemeinstellung versuchen
  }
  if (system === 'dark' || system === 'light') return system
  return 'light'
}

/** Anderes Theme. */
export function naechstesTheme(aktuell) {
  return aktuell === 'dark' ? 'light' : 'dark'
}

/** Anzeigetext des Umschalters (nennt das Ziel, nicht den Zustand). */
export function umschalterText(aktuell) {
  return aktuell === 'dark' ? 'Hell-Modus' : 'Dunkel-Modus'
}
