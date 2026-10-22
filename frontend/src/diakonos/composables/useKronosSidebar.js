/**
 * UXK-R9 — gemeinsamer Zustand der Kalender-Seitenleiste.
 *
 * Am Handy liegt die `KronosSidebar` (Kalenderliste/Filter, CalDAV-Anleitung,
 * Import) fest ausserhalb des Bildes (kronos.css: `transform: translateX(-100%)`).
 * Ohne oeffnenden Knopf waren ausgerechnet „Meine Kalender“ und die Anleitung
 * mobil unerreichbar.
 *
 * Die Leiste wird in `App.vue` gerendert, der Umschalter sitzt aber in
 * `pages/Kalender.vue` (Kopfzeile). Ein kleiner gemeinsamer Zustand haelt
 * beide Seiten auf derselben Wahrheit — statt die Bindung ueber mehrere
 * Komponenten zu fädeln.
 */
import { ref } from 'vue'

const offen = ref(false)

export function useKronosSidebar() {
  function auf() { offen.value = true }
  function zu() { offen.value = false }
  function umschalten() { offen.value = !offen.value }

  return { offen, auf, zu, umschalten }
}
