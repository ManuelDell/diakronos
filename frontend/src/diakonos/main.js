import { createApp } from 'vue'
import { FrappeUI } from 'frappe-ui'
import 'frappe-ui/style.css'
import './index.css'
import './kronos.css'
import App from './App.vue'
// PF1: Der nutzerbezogene Browser-Cache MUSS hier geprueft werden — main.js
// laeuft bei JEDEM Start der SPA, auch auf Seiten, die den Planrahmen nie
// importieren. Wechselt die Nutzerkennung (Anmeldung als jemand anderes),
// wird der Cache vollstaendig geleert, bevor irgendeine Seite ihn liest.
import { cacheNutzerSetzen, cacheLeeren } from './composables/usePlanrahmenCache.js'

const boot = window.__DIakonosBOOT || {}
const kennung = boot.user_email || boot.user_fullname || ''
if (kennung) {
    cacheNutzerSetzen(kennung)   // Nutzerwechsel -> leert den alten Stand
} else {
    cacheLeeren()                // kein Nutzer -> nichts darf liegenbleiben
    cacheNutzerSetzen('')
}

const app = createApp(App)
app.use(FrappeUI, { socketio: false, resources: false })

// DM1: Komponenten-Kette fuer den Dev-Modus. Im Produktionsbuild entfernt Vue
// `__vueParentComponent` — ohne diese Anmerkung bliebe die Komponentenkette
// eines Elements leer. Der Mixin setzt am Wurzel-Element jeder Komponente
// ihren Namen ab (`__dkKette`, von innen nach aussen gesammelt). Der Aufwand
// ist eine Zuweisung je Komponenten-Instanz — auch ohne Dev-Modus. Der
// Overlay-Code selbst wird weiterhin nur im Dev-Modus geladen.
app.mixin({
    mounted() {
        const name = this.$options?.name || this.$options?.__name
            || this.$options?.__file?.split('/').pop()?.replace(/\.vue$/, '')
        const el = this.$el
        if (!name || !el || el.nodeType !== 1) return
        // Nur der EIGENE Name. Die Kette entsteht, indem der Dev-Modus die
        // DOM-Vorfahren hochlaeuft und deren Namen sammelt (dedupliziert).
        // (Kinder mounten VOR ihren Eltern — eine Vererbung ueber den
        // Elternknoten waere zum Mount-Zeitpunkt noch nicht verfuegbar.)
        el.__dkName = name
    },
})

app.mount('#app')
