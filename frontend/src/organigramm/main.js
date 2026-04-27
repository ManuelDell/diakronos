import { createApp } from 'vue'
import { FrappeUI } from 'frappe-ui'
import 'frappe-ui/style.css'
import '../style.css'
import App from './App.vue'

createApp(App).use(FrappeUI).mount('#app')
