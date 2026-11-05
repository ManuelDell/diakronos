/**
 * UX2d2 — `useLadeSkelett(laedt)`: der Skelett-Zustand einer Seite.
 *
 * Die Regel selbst steht in `./ladeSkelett.mjs` (ohne Vue, im Node-Test ohne
 * Browser prüfbar). Hier wird sie an den Ladezustand einer Seite gebunden:
 *
 *   const { skelettSichtbar } = useLadeSkelett(loading)
 *
 *   <DkSkelett v-if="skelettSichtbar" ... />
 *
 * `loading` ist die Bedingung, unter der der Platzhalter erscheinen darf
 * (z. B. `loading`, `laedt && !daten`). Unter 300 ms Ladedauer erscheint
 * nichts — kein Flackern.
 *
 * UX2d3a: Der erste Stand wird SOFORT geprüft, nicht erst bei der nächsten
 * Änderung. Seiten setzen `loading` beim Aufbau auf `true` (ref-Startwert) und
 * ändern es danach NIE wieder auf `true` — ein reines `watch` sah deshalb nur
 * den Wechsel auf `false` und zeigte nie einen Platzhalter. Der Startwert ist
 * ein Ladezustand wie jeder andere.
 */
import { onUnmounted, ref, watch } from 'vue'
import { ladeSkelett } from './ladeSkelett.mjs'

export function useLadeSkelett(laedt, optionen = {}) {
  const skelettSichtbar = ref(false)
  const waechter = ladeSkelett(laedt.value, (sichtbar) => { skelettSichtbar.value = sichtbar }, optionen)

  const stoppen = watch(laedt, (an) => waechter.pruefe(Boolean(an)), { immediate: true })
  onUnmounted(() => {
    stoppen()
    waechter.beenden()
  })

  return { skelettSichtbar, waechter }
}
