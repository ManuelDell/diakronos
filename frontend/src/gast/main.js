import { createApp } from 'vue'
// DEP-2b: Layer-Reihenfolge ZUERST, sonst legt style.css (Tailwind) sie fest.
import '../layer-reihenfolge.css'
import '../style.css'
import '../diakonos/index.css'
// REG-1c (5): Hell/Dunkel wie auf der oeffentlichen Registrierungsseite —
// `index.css` zieht `tokens.css`, dessen dunkle Werte aber nur unter
// `[data-theme="dark"]` gelten. Ohne diesen Aufruf blieb die Gast-Anmeldung
// immer hell.
import { themeSetzen } from '../diakonos/composables/oeffentliches-theme.mjs'
import App from './App.vue'

themeSetzen({
  dokument: typeof document === 'undefined' ? null : document,
  speicher: typeof localStorage === 'undefined' ? null : localStorage,
  abfrage: typeof window === 'undefined' ? null : window.matchMedia?.bind(window),
})

createApp(App).mount('#app')
