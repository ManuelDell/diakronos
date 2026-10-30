import { createApp } from 'vue'
// DEP-2b: Layer-Reihenfolge ZUERST — sie muss vor dem Grundreset feststehen,
// sonst entscheidet die Stelle im Buendel, ob das Reset Komponenten
// ueberstimmt (Befund: Filterchips ohne Rahmen/Hintergrund/Innenabstand).
import '../layer-reihenfolge.css'
import '../style.css'
import '../diakonos/tokens.css'
import '../grundreset.css'
// REG-1c (5): Hell/Dunkel auch auf der OEFFENTLICHEN Seite. `tokens.css` kennt
// die dunklen Werte nur unter `[data-theme="dark"]`; ohne diesen Aufruf blieb
// die Anmeldeseite immer hell — auch bei dunkler Systemeinstellung (gemessen:
// Flaeche `rgb(250,250,248)` bei `prefers-color-scheme: dark`).
import { themeSetzen } from '../diakonos/composables/oeffentliches-theme.mjs'
import App from './App.vue'

themeSetzen({
  dokument: typeof document === 'undefined' ? null : document,
  speicher: typeof localStorage === 'undefined' ? null : localStorage,
  abfrage: typeof window === 'undefined' ? null : window.matchMedia?.bind(window),
})

createApp(App).mount('#app')
