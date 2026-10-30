/**
 * theme-setzen — Hell/Dunkel am Wurzelelement setzen (REG-1c).
 *
 * Befund aus der Abnahme: Die OEFFENTLICHEN Seiten (`registrierung`, `gast`)
 * hatten gar keinen Einstieg in den Modus. `tokens.css` kennt die dunklen
 * Werte nur unter `[data-theme="dark"]`; ohne das Merkmal am `<html>` blieb
 * die Anmeldeseite IMMER hell — auch bei `prefers-color-scheme: dark` und
 * auch dann, wenn im Konto „Dunkel“ gewaehlt war (gemessen: Flaeche
 * `rgb(250,250,248)` bei dunkler Systemeinstellung).
 *
 * Die Regel ist dieselbe wie in der App (`composables/theme.mjs`): bewusste
 * Wahl im Speicher, sonst die Systemeinstellung, sonst hell. Bewusst KEIN
 * Umschalter auf der oeffentlichen Seite — ein Besucher ohne Konto soll nichts
 * einstellen muessen; er bekommt, was sein Geraet sagt.
 *
 * Ohne Vue/DOM-Attrappe pruefbar: Umgebung wird als Parameter uebergeben
 * (siehe `frontend/tests/reg1c-*`).
 */

/** Startwert: Speicher -> System -> hell (dieselbe Reihenfolge wie in der App). */
export function startTheme({ speicher = null, system = null } = {}) {
  try {
    const gespeichert = speicher?.getItem('dk-theme')
    if (gespeichert === 'dark' || gespeichert === 'light') return gespeichert
  } catch {
    // gesperrter Speicher (Privatmodus) -> Systemeinstellung versuchen
  }
  if (system === 'dark' || system === 'light') return system
  return 'light'
}

/**
 * Theme am Wurzelelement setzen und (falls moeglich) spaeteren Wechseln der
 * Systemeinstellung folgen. Eine bewusste Wahl im Speicher gewinnt und wird
 * nicht ueberschrieben.
 *
 * @param {{dokument?: Document, speicher?: Storage, abfrage?: Function}} umgebung
 * @returns {'dark'|'light'} der gesetzte Wert
 */
export function themeSetzen({ dokument = null, speicher = null, abfrage = null } = {}) {
  const system = () => {
    try {
      const treffer = abfrage ? abfrage('(prefers-color-scheme: dark)') : null
      return treffer?.matches ? 'dark' : 'light'
    } catch {
      return null
    }
  }

  const setzen = (wert) => {
    try {
      dokument?.documentElement?.setAttribute('data-theme', wert)
    } catch {
      // Kein DOM (Test/Server) -> nichts zu tun
    }
    return wert
  }

  const wert = startTheme({ speicher, system: system() })
  setzen(wert)

  // Folgt die Seite der Systemeinstellung? Nur wenn keine Wahl gespeichert ist.
  try {
    const gespeichert = speicher?.getItem('dk-theme')
    const treffer = abfrage ? abfrage('(prefers-color-scheme: dark)') : null
    if (!gespeichert && treffer?.addEventListener) {
      treffer.addEventListener('change', (ereignis) => {
        setzen(ereignis?.matches ? 'dark' : 'light')
      })
    }
  } catch {
    // Ohne Abfrage bleibt es beim Startwert
  }
  return wert
}
