import { createApp } from 'vue'
import { FrappeUI } from 'frappe-ui'
import 'frappe-ui/style.css'
import './index.css'
import App from './App.vue'

const app = createApp(App)
app.use(FrappeUI)
app.mount('#app')
