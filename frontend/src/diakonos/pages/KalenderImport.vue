<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { io } from 'socket.io-client'
import { apiCall } from '../composables/useApi.js'
import { navigate } from '../router.js'
import DkPageHeader from '../components/ui/DkPageHeader.vue'
import DkButton from '../components/ui/DkButton.vue'
import DkField from '../components/ui/DkField.vue'
import DkTabs from '../components/ui/DkTabs.vue'

const prefix = 'diakronos.kronos.api.google_import.'
const tab = ref('google')
const step = ref(1)
const loading = ref(true)
const busy = ref(false)
const error = ref('')
const clientId = ref('')
const clientSecret = ref('')
const redirectUri = ref(window.location.origin + '/google-calendar-callback')
const calendars = ref([])
const existing = ref([])
const importing = ref(false)
const result = ref(null)
const progress = ref({})
const warnings = ref([])
const icalMode = ref('new')
const icalName = ref('')
const icalTarget = ref('')
const icalColor = ref('#4285F4')
const icalFile = ref(null)
const icalResult = ref(null)
const disabled = computed(() => busy.value || importing.value || loading.value)
let socket = null
let deadline = null
let disposed = false

// Never display raw server/Google errors: they can contain credentials or tokens.
async function loadExisting() {
  existing.value = await apiCall('diakronos.kronos.api.permissions.get_writable_calendars') || []
}
async function loadStatus() {
  loading.value = true
  try {
    const status = await apiCall(prefix + 'get_credentials_status')
    redirectUri.value = status.redirect_uri || redirectUri.value
    step.value = !status.configured ? 1 : !status.authorized ? 2 : 3
    if (step.value === 3) {
      const list = await apiCall(prefix + 'get_google_calendars')
      calendars.value = list.map(cal => ({ ...cal, selected: true, target: '', timeFilter: 'all',
        color: /^#[0-9a-f]{6}$/i.test(cal.backgroundColor) ? cal.backgroundColor : '#4285F4' }))
    }
  } catch {
    error.value = 'Google-Status oder Kalender konnten nicht geladen werden. Prüfe deine Berechtigung und verbinde Google bei Bedarf erneut.'
  } finally {
    loading.value = false
  }
}
async function saveCredentials() {
  error.value = ''
  if (!clientId.value.trim() || !clientSecret.value || !redirectUri.value.trim()) {
    error.value = 'Bitte Client-ID, Client-Secret und Redirect-URI eingeben.'
    return
  }
  busy.value = true
  try {
    await apiCall(prefix + 'save_credentials', {
      client_id: clientId.value.trim(), client_secret: clientSecret.value, redirect_uri: redirectUri.value.trim(),
    })
    step.value = 2
    calendars.value = []
  } catch {
    error.value = 'Zugangsdaten konnten nicht gespeichert werden. Prüfe deine Berechtigung und die Redirect-URI (Pfad /google-calendar-callback).'
  } finally {
    clientSecret.value = ''
    clientId.value = ''
    busy.value = false
  }
}
async function authorize() {
  error.value = ''
  busy.value = true
  try {
    const data = await apiCall(prefix + 'get_oauth_url')
    const url = new URL(data.url)
    if (url.origin !== 'https://accounts.google.com' || url.pathname !== '/o/oauth2/v2/auth') throw new Error()
    window.location.assign(url.href)
  } catch {
    error.value = 'Google-Anmeldung konnte nicht gestartet werden. Prüfe die gespeicherten Zugangsdaten und versuche es erneut.'
    busy.value = false
  }
}
function stopProgress() {
  importing.value = false
  clearTimeout(deadline)
  socket?.off('gcal_import_progress')
  socket?.disconnect()
  socket = null
}
function receiveProgress(data) {
  if (disposed || !importing.value) return
  progress.value = data
  if (data.status === 'warning') warnings.value.push('Ein Termin wurde übersprungen, weil er nicht unterstützt wird.')
  if (data.status === 'error') warnings.value.push('Ein Kalender konnte nicht vollständig importiert werden.')
  if (data.status === 'done') {
    result.value = data
    if (data.error) error.value = 'Der Import wurde nicht vollständig abgeschlossen. Bereits importierte Kalender bleiben erhalten. Bitte erneut verbinden und den Import prüfen.'
    stopProgress()
    loadExisting().catch(() => { error.value = 'Zielkalender konnten nicht aktualisiert werden. Bitte lade die Seite neu.' })
  }
}
function connectProgress() {
  socket = io({ autoConnect: false, withCredentials: true, timeout: 10000,
    // Nur WebSocket (Befund W2): Uvicorn laeuft mit mehreren Arbeitern ohne
    // Sticky Sessions. Engine.IO beginnt mit HTTP-Long-Polling; die Poll-
    // Anfragen einer sid landen dann bei verschiedenen Arbeitern und der
    // Server antwortet 'Invalid session' — der Fortschrittsbalken bricht ab.
    // Eine WebSocket-Verbindung bleibt fuer ihre ganze Laufzeit bei einem
    // Arbeiter und funktioniert damit auch mit WEB_CONCURRENCY > 1.
    transports: ['websocket'],
    // Engine.IO polling POSTs pass through the same CSRF middleware as RPCs.
    extraHeaders: { 'X-Frappe-CSRF-Token': window.__DIakonosBOOT?.csrf_token || '' },
  })
  socket.on('gcal_import_progress', receiveProgress)
  socket.on('disconnect', () => {
    if (importing.value) error.value = 'Fortschrittsverbindung unterbrochen. Der Import kann im Hintergrund weiterlaufen; bitte nicht erneut starten und die Kalender anschließend prüfen.'
  })
  return new Promise((resolve, reject) => {
    if (socket.connected) return resolve()
    socket.once('connect', resolve)
    socket.once('connect_error', reject)
    socket.connect()
  })
}
async function startGoogleImport() {
  if (disabled.value) return
  error.value = ''
  const mappings = calendars.value.filter(cal => cal.selected).map(cal => ({
    google_id: cal.id, google_name: cal.summary, create_new: !cal.target,
    target_kalender: cal.target, color: cal.color, time_filter: cal.timeFilter,
  }))
  if (!mappings.length) { error.value = 'Bitte mindestens einen Kalender auswählen.'; return }
  importing.value = true
  result.value = null
  progress.value = {}
  warnings.value = []
  try {
    // Connect first: even a fast RQ job must not finish before the listener exists.
    await connectProgress()
    if (disposed) { stopProgress(); return }
    const response = await apiCall(prefix + 'start_import', { mappings_json: JSON.stringify(mappings) })
    if (!response?.queued) throw new Error()
    if (importing.value) deadline = setTimeout(() => {
      error.value = 'Keine Abschlussmeldung erhalten. Der Import kann weiterlaufen. Prüfe die Kalender vor einem erneuten Import.'
      stopProgress()
    }, 660000)
  } catch {
    stopProgress()
    error.value = 'Import konnte nicht gestartet werden. Prüfe deine Berechtigung, die Google-Verbindung und die Fortschrittsverbindung.'
  }
}
async function importIcal() {
  if (busy.value || importing.value) return
  error.value = ''
  icalResult.value = null
  if (icalMode.value === 'new' ? !icalName.value.trim() : !icalTarget.value) {
    error.value = 'Bitte einen Namen für den neuen Kalender oder einen Zielkalender auswählen.'; return
  }
  const file = icalFile.value
  if (!file || !/\.ics$/i.test(file.name) || !file.size || file.size > 5 * 1024 * 1024) {
    error.value = 'Bitte eine nicht leere .ics-Datei mit höchstens 5 MiB auswählen.'; return
  }
  busy.value = true
  try {
    const bytes = new Uint8Array(await file.arrayBuffer())
    // Read original bytes, not decoded text: preserves UTF-8 without mojibake.
    let binary = ''
    for (let i = 0; i < bytes.length; i += 8192) binary += String.fromCharCode(...bytes.subarray(i, i + 8192))
    icalResult.value = await apiCall(prefix + 'upload_ical', {
      file_content_b64: btoa(binary), create_new: icalMode.value === 'new' ? 1 : 0,
      target_kalender: icalMode.value === 'existing' ? icalTarget.value : '',
      calendar_name_new: icalMode.value === 'new' ? icalName.value.trim() : '', color: icalColor.value,
    })
    await loadExisting()
  } catch {
    error.value = 'iCal-Import fehlgeschlagen. Prüfe Berechtigung, Dateiformat, Größe und Zielkalender. Falls bereits ein Ergebnis angezeigt wird, wurde nur die Kalenderliste nicht aktualisiert.'
  } finally {
    busy.value = false
  }
}
onMounted(async () => {
  const url = new URL(window.location.href)
  const callbackError = url.searchParams.has('gcal_error')
  const returned = url.searchParams.get('gcal_step') === '2'
  if (callbackError || url.searchParams.has('gcal_step')) {
    url.searchParams.delete('gcal_error')
    url.searchParams.delete('gcal_step')
    window.history.replaceState(null, '', url.pathname + url.search + url.hash)
  }
  if (callbackError) error.value = 'Google-Verbindung fehlgeschlagen oder abgebrochen. Bitte erneut anmelden.'
  if (returned) tab.value = 'google'
  await Promise.all([loadStatus(), loadExisting().catch(() => {
    error.value = 'Zielkalender konnten nicht geladen werden. Prüfe deine Berechtigung und lade die Seite neu.'
  })])
})
onBeforeUnmount(() => {
  disposed = true
  clientSecret.value = ''
  stopProgress()
})
</script>

<template>
  <main class="dk-import">
    <DkPageHeader title="Kalender importieren" sub="Google-Kalender oder iCal-Datei einmalig übernehmen">
      <template #actions>
        <DkButton variant="secondary" @click="navigate('#/kalender')">Zurück zum Kalender</DkButton>
      </template>
    </DkPageHeader>
    <DkTabs
      class="dk-import-tabs"
      aria-label="Importquelle"
      :model-value="tab"
      :options="[{ value: 'google', label: 'Google-Kalender' }, { value: 'ical', label: 'iCal-Datei (.ics)' }]"
      @update:model-value="tab = $event"
    />
    <p v-if="error" class="dk-import-error" role="alert">{{ error }}</p>
    <p v-if="loading" role="status">Status und Kalender werden geladen …</p>
    <section v-show="tab === 'google'" id="google-panel" class="dk-import-card" role="tabpanel" aria-label="Google-Kalender">
      <p>Einmaliger Import, keine laufende Synchronisierung. Zugangsdaten gelten für diese Instanz.</p>
      <form v-if="step === 1" @submit.prevent="saveCredentials">
        <h2>1. Google-API-Zugangsdaten</h2>
        <p>Aktiviere die Google Calendar API in einem Google-Cloud-Projekt und erstelle einen OAuth-Client vom Typ Webanwendung.</p>
        <fieldset :disabled="disabled">
          <DkField v-slot="feld" label="Client-ID"><input :id="feld.id" v-model="clientId" required maxlength="140" autocomplete="off"></DkField>
          <DkField v-slot="feld" label="Client-Secret"><input :id="feld.id" v-model="clientSecret" required type="password" maxlength="4096" autocomplete="new-password"></DkField>
          <DkField v-slot="feld" label="Redirect-URI" help="Diese URI muss exakt in der Google Console eingetragen sein. Google verlangt eine öffentliche HTTPS-Domain (oder localhost), keine rohe LAN-IP.">
            <input :id="feld.id" :aria-describedby="feld.aria-describedby" v-model="redirectUri" required type="url" maxlength="140">
          </DkField>
          <DkButton type="submit" variant="primary" :loading="busy">{{ busy ? 'Speichern …' : 'Speichern & weiter' }}</DkButton>
        </fieldset>
      </form>
      <template v-else>
        <p>Zugangsdaten gespeichert. <DkButton size="sm" :disabled="disabled" @click="step = 1">Zugangsdaten ändern</DkButton></p>
        <h2 v-if="step === 2">2. Mit Google anmelden</h2>
        <p v-if="step === 2">Melde dich mit dem Google-Konto an, dessen Kalender du importieren möchtest. Du wirst hierher zurückgeleitet.</p>
        <p class="dk-import-uri">{{ redirectUri }}</p>
        <DkButton :disabled="disabled" @click="authorize">{{ busy ? 'Weiterleitung …' : step === 3 ? 'Anderes Konto / erneut verbinden' : 'Mit Google anmelden' }}</DkButton>
      </template>
      <template v-if="step === 3">
        <h2>3. Kalender auswählen und importieren</h2>
        <p v-if="!calendars.length && !loading">Keine Google-Kalender gefunden.</p>
        <fieldset :disabled="disabled">
          <div v-for="cal in calendars" :key="cal.id" class="dk-import-mapping">
            <label><input v-model="cal.selected" type="checkbox"> {{ cal.summary }} {{ cal.primary ? '(Hauptkalender)' : '' }}</label>
            <label>Zielkalender<select v-model="cal.target"><option value="">Neuen Kalender anlegen</option><option v-for="target in existing" :key="target.name" :value="target.name">{{ target.calendar_name || target.name }}</option></select></label>
            <label>Farbe des neuen Kalenders<input v-model="cal.color" type="color" :disabled="!!cal.target"></label>
            <label>Zeitraum<select v-model="cal.timeFilter"><option value="all">Alle Termine</option><option value="from_today">Ab heute</option><option value="last_year">Letztes Jahr</option><option value="last_3_years">Letzte 3 Jahre</option></select></label>
          </div>
          <div class="dk-import-actions">
            <DkButton size="sm" @click="calendars.forEach(cal => cal.selected = true)">Alle auswählen</DkButton>
            <DkButton size="sm" @click="calendars.forEach(cal => cal.selected = false)">Alle abwählen</DkButton>
            <DkButton variant="primary" :disabled="!calendars.length" @click="startGoogleImport">Ausgewählte importieren</DkButton>
          </div>
        </fieldset>
      </template>
      <p v-if="importing" role="status" aria-live="polite">Import läuft … Kalender: {{ progress.calendar_name || 'Warte auf den Hintergrundauftrag' }} <span v-if="progress.cal_num">({{ progress.cal_num }}/{{ progress.cal_total }})</span> · Termine importiert: {{ progress.imported || 0 }}</p>
      <p v-for="(warning, index) in warnings" :key="index">{{ warning }}</p>
      <div v-if="result" role="status"><h2>{{ result.error ? 'Import teilweise fehlgeschlagen' : 'Import abgeschlossen' }}</h2><p>{{ result.total_imported || 0 }} Termine importiert, {{ result.total_skipped || 0 }} übersprungen.</p><p v-for="(cal, index) in result.calendars" :key="index">{{ cal.google_name }} → {{ cal.frappe_kalender }}: {{ cal.imported }} importiert, {{ cal.skipped }} übersprungen.</p></div>
      <DkButton v-if="!loading" :disabled="disabled" @click="error = ''; loadStatus()">Status erneut laden</DkButton>
    </section>
    <section v-show="tab === 'ical'" id="ical-panel" class="dk-import-card" role="tabpanel" aria-label="iCal-Datei (.ics)">
      <h2>iCal-Datei importieren (.ics)</h2>
      <p>Exportiere einen Kalender aus Google, Outlook oder Apple Kalender als .ics-Datei.</p>
      <form @submit.prevent="importIcal"><fieldset :disabled="disabled">
        <label><input v-model="icalMode" type="radio" value="new"> Neuen Kalender anlegen</label>
        <label><input v-model="icalMode" type="radio" value="existing"> Bestehenden Kalender nutzen</label>
        <template v-if="icalMode === 'new'"><DkField v-slot="feld" label="Name des neuen Kalenders"><input :id="feld.id" v-model="icalName" required maxlength="140"></DkField><DkField v-slot="feld" label="Farbe"><input :id="feld.id" v-model="icalColor" type="color"></DkField></template>
        <DkField v-else v-slot="feld" label="Bestehender Kalender"><select :id="feld.id" v-model="icalTarget" required><option value="">— Kalender wählen —</option><option v-for="cal in existing" :key="cal.name" :value="cal.name">{{ cal.calendar_name || cal.name }}</option></select></DkField>
        <DkField v-slot="feld" label="iCal-Datei (.ics), maximal 5 MiB"><input :id="feld.id" type="file" accept=".ics,text/calendar" required @change="icalFile = $event.target.files[0] || null"></DkField>
        <DkButton type="submit" variant="primary" :loading="busy">{{ busy ? 'Import läuft …' : 'Kalender importieren' }}</DkButton>
      </fieldset></form>
      <div v-if="icalResult" role="status"><h2>Import abgeschlossen</h2><p>{{ icalResult.imported || 0 }} Termine importiert, {{ icalResult.skipped || 0 }} übersprungen. Kalender: {{ icalResult.kalender }}</p></div>
    </section>
  </main>
</template>

<style scoped>
/* DES-R12: Die Import-Seite war 1000 px breit und saß dadurch 39 px weiter
   rechts als jede andere Seite (x=335 statt 296). Jetzt dieselbe Breite wie
   der normale Seitenrahmen (.dk-screen, 1280 px). */
.dk-import { padding: var(--sp-6); overflow-y: auto; color: var(--text); max-width: 1280px; width: 100%; margin: 0 auto; display: flex; flex-direction: column; gap: var(--sp-4); }
.dk-import-tabs { margin-top: var(--sp-2); }
h2 { font-size: var(--fs-h2); font-weight: 600; margin: var(--sp-4) 0 var(--sp-2); color: var(--text); }
p { margin: var(--sp-3) 0; }
.dk-import-card { padding: var(--sp-6); background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius-lg); box-shadow: var(--shadow-sm); }
fieldset { border: 0; padding: 0; min-width: 0; display: flex; flex-direction: column; gap: var(--sp-3); }
fieldset > label { display: flex; align-items: center; gap: var(--sp-2); margin: 0; }
.dk-import-mapping { display: flex; flex-direction: column; gap: var(--sp-2); padding: var(--sp-3) var(--sp-4); border: 1px solid var(--line); border-radius: var(--radius); margin: var(--sp-3) 0; }
.dk-import-mapping label { display: flex; align-items: center; gap: var(--sp-2); margin: 0; }
.dk-import-mapping select, .dk-import-mapping input[type="color"] { margin-left: auto; }
.dk-import-actions { display: flex; gap: var(--sp-2); flex-wrap: wrap; margin-top: var(--sp-2); }
.dk-import-error { color: var(--err); border-left: 3px solid var(--err); padding: var(--sp-3); background: var(--err-soft); border-radius: var(--radius-sm); }
.dk-import-uri { overflow-wrap: anywhere; color: var(--muted); }
input:not([type=checkbox]):not([type=radio]):not([type=color]), select {
  width: 100%;
  height: var(--control-h);
  padding: 0 12px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--text);
  font: inherit;
  font-size: var(--fs);
}
input[type=color] { max-width: 100px; height: 34px; }
input:focus, select:focus { outline: 2px solid var(--focus-ring); outline-offset: 0; }
@media (max-width: 640px) { .dk-import { padding: var(--sp-3); } .dk-import-card { padding: var(--sp-4); } }
</style>
