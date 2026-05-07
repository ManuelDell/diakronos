import { createApp } from 'vue'
import { FrappeUI } from 'frappe-ui'
import 'frappe-ui/style.css'
import '../style.css'

import AnmeldungenHub from './AnmeldungenHub.vue'
import DsgvoUebersicht from './DsgvoUebersicht.vue'
import Statistik from './Statistik.vue'

function makeApp(Component) {
    const app = createApp(Component)
    app.use(FrappeUI, { socketio: false, resources: false })
    return app
}

export function mountAnmeldungen(el) {
    const instance = makeApp(AnmeldungenHub).mount(el)
    return () => instance.refresh?.()
}

export function mountDsgvo(el) {
    const instance = makeApp(DsgvoUebersicht).mount(el)
    return () => instance.refresh?.()
}

export function mountStatistik(el) {
    const instance = makeApp(Statistik).mount(el)
    return () => instance.refresh?.()
}
