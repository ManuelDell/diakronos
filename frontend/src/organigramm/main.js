import { createApp } from 'vue'
// DEP-2b: Layer-Reihenfolge ZUERST — sie muss vor dem Grundreset feststehen,
// sonst entscheidet die Stelle im Buendel, ob das Reset Komponenten
// ueberstimmt (Befund: Filterchips ohne Rahmen/Hintergrund/Innenabstand).
import '../layer-reihenfolge.css'
import '../style.css'
import '../diakonos/tokens.css'
import '../grundreset.css'
import App from './App.vue'

createApp(App).mount('#app')
