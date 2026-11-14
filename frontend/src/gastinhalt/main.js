import { createApp } from 'vue'
// DEP-2b: Layer-Reihenfolge ZUERST, sonst legt style.css (Tailwind) sie fest.
import '../layer-reihenfolge.css'
import '../style.css'
import '../diakonos/tokens.css'
import '../grundreset.css'
// Hell/Dunkel wie auf den übrigen öffentlichen Seiten (Registrierung/Gast-
// Anmeldung): `tokens.css` kennt die dunklen Werte nur unter
// `[data-theme="dark"]`.
import { themeSetzen } from '../diakonos/composables/oeffentliches-theme.mjs'
import App from './App.vue'

themeSetzen({
  dokument: typeof document === 'undefined' ? null : document,
  speicher: typeof localStorage === 'undefined' ? null : localStorage,
  abfrage: typeof window === 'undefined' ? null : window.matchMedia?.bind(window),
})

createApp(App).mount('#app')
