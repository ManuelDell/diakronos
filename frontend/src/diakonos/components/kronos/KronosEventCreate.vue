<template>
  <Teleport to="body">
    <div v-if="show" class="diakronos-modal show" @click.self="close">
      <div class="diakronos-modal-dialog">
        <div class="diakronos-modal-content">
          <!-- Farbige Leiste -->
          <div class="diakronos-color-bar" :style="{ backgroundColor: selectedCalendarColor }"></div>

          <div class="diakronos-modal-header">
            <h3>Neuer Termin</h3>
            <button class="close-btn" @click="close">&times;</button>
          </div>

          <!-- Tabs -->
          <div class="diakronos-tabs">
            <button
              class="tab-btn"
              :class="{ active: activeTab === 'basic' }"
              @click="activeTab = 'basic'"
            >
              Grunddaten
            </button>
            <button
              class="tab-btn"
              :class="{ active: activeTab === 'details' }"
              @click="activeTab = 'details'"
            >
              Details
            </button>
          </div>

          <div class="tab-content">
            <!-- Tab 1: Grunddaten -->
            <div v-show="activeTab === 'basic'">
              <div class="form-group">
                <label>Titel *</label>
                <input v-model="form.element_name" type="text" placeholder="Termintitel" />
              </div>

              <div class="form-row">
                <div class="form-group">
                  <label>Beginn *</label>
                  <input ref="startInput" type="text" placeholder="Beginn" />
                </div>
                <div class="form-group">
                  <label>Ende *</label>
                  <input ref="endInput" type="text" placeholder="Ende" />
                </div>
              </div>

              <div class="checkbox-row">
                <input id="create-all-day" v-model="form.all_day" type="checkbox" />
                <label for="create-all-day">Ganztägig</label>
              </div>

              <div class="form-group">
                <label>Kalender *</label>
                <select v-model="form.element_calendar">
                  <option value="">Bitte wählen</option>
                  <option v-for="cal in calendars" :key="cal.name" :value="cal.name">
                    {{ cal.calendar_name }}
                  </option>
                </select>
              </div>

              <div class="form-group">
                <label>Ressource</label>
                <select v-model="form.ressource">
                  <option value="">Bitte wählen</option>
                  <option v-for="res in ressources" :key="res.name" :value="res.name">
                    {{ res.ressource_name }}
                  </option>
                </select>
              </div>
            </div>

            <!-- Tab 2: Details -->
            <div v-show="activeTab === 'details'">
              <div class="checkbox-row">
                <input id="create-series" v-model="form.is_series" type="checkbox" />
                <label for="create-series">Serientermin</label>
              </div>

              <div v-if="form.is_series" class="form-group">
                <label>Wiederholung</label>
                <select v-model="form.repeat_type">
                  <option value="">Bitte wählen</option>
                  <option value="daily">Täglich</option>
                  <option value="weekly">Wöchentlich</option>
                  <option value="monthly">Monatlich</option>
                </select>
              </div>

              <div v-if="form.is_series" class="form-group">
                <label>Serienende</label>
                <input ref="seriesEndInput" type="text" placeholder="Serienende" />
              </div>

              <div class="form-group">
                <label>Beschreibung</label>
                <textarea v-model="form.description" rows="3"></textarea>
              </div>

              <div class="form-group">
                <label>Kategorie</label>
                <select v-model="form.element_category">
                  <option value="">Bitte wählen</option>
                  <option v-for="cat in categories" :key="cat.name" :value="cat.name">
                    {{ cat.event_category_name }}
                  </option>
                </select>
              </div>

              <div class="checkbox-row">
                <input id="create-ignore-conflict" v-model="form.ignore_conflict" type="checkbox" />
                <label for="create-ignore-conflict">Konflikte ignorieren</label>
              </div>
            </div>
          </div>

          <div class="diakronos-modal-footer">
            <button class="btn-secondary" @click="close">Abbrechen</button>
            <button class="btn-primary" @click="save">Speichern</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Konflikt-Dialog -->
    <KronosConflictDialog ref="conflictDialog" />
  </Teleport>
</template>

<script setup>
import { ref, reactive, watch, computed, onMounted, nextTick } from 'vue'
import flatpickr from 'flatpickr'
import 'flatpickr/dist/flatpickr.min.css'
import { German } from 'flatpickr/dist/l10n/de.js'
import KronosConflictDialog from './KronosConflictDialog.vue'

const props = defineProps({
  show: { type: Boolean, default: false },
  initialData: { type: Object, default: () => ({}) }
})

const emit = defineEmits(['update:show', 'created'])

const activeTab = ref('basic')
const startInput = ref(null)
const endInput = ref(null)
const seriesEndInput = ref(null)
const conflictDialog = ref(null)

const calendars = ref([])
const categories = ref([])
const ressources = ref([])
const kronosSettings = ref({})

let fpStart = null
let fpEnd = null
let fpSeriesEnd = null

const form = reactive({
  element_name: '',
  element_start: '',
  element_end: '',
  all_day: false,
  element_calendar: '',
  ressource: '',
  is_series: false,
  repeat_type: '',
  series_end: '',
  description: '',
  element_category: '',
  ignore_conflict: false
})

const selectedCalendarColor = computed(() => {
  const cal = calendars.value.find(c => c.name === form.element_calendar)
  return cal?.color || '#4a90d9'
})

function resetForm() {
  form.element_name = ''
  form.element_start = ''
  form.element_end = ''
  form.all_day = false
  form.element_calendar = ''
  form.ressource = ''
  form.is_series = false
  form.repeat_type = ''
  form.series_end = ''
  form.description = ''
  form.element_category = ''
  form.ignore_conflict = false

  if (props.initialData) {
    if (props.initialData.element_start) form.element_start = props.initialData.element_start
    if (props.initialData.element_end) form.element_end = props.initialData.element_end
    if (props.initialData.element_calendar) form.element_calendar = props.initialData.element_calendar
  }

  activeTab.value = 'basic'
}

function initFlatpickr() {
  const config = {
    locale: German,
    enableTime: true,
    time_24hr: true,
    dateFormat: 'Y-m-d H:i',
    onChange: (selectedDates, dateStr, instance) => {
      if (instance === fpStart) {
        form.element_start = dateStr
      } else if (instance === fpEnd) {
        form.element_end = dateStr
      } else if (instance === fpSeriesEnd) {
        form.series_end = dateStr
      }
    }
  }

  if (startInput.value && !fpStart) {
    fpStart = flatpickr(startInput.value, config)
  }
  if (endInput.value && !fpEnd) {
    fpEnd = flatpickr(endInput.value, config)
  }
  if (seriesEndInput.value && !fpSeriesEnd) {
    fpSeriesEnd = flatpickr(seriesEndInput.value, { ...config, enableTime: false, dateFormat: 'Y-m-d' })
  }

  if (fpStart && form.element_start) fpStart.setDate(form.element_start, false)
  if (fpEnd && form.element_end) fpEnd.setDate(form.element_end, false)
  if (fpSeriesEnd && form.series_end) fpSeriesEnd.setDate(form.series_end, false)
}

function destroyFlatpickr() {
  if (fpStart) { fpStart.destroy(); fpStart = null }
  if (fpEnd) { fpEnd.destroy(); fpEnd = null }
  if (fpSeriesEnd) { fpSeriesEnd.destroy(); fpSeriesEnd = null }
}

function close() {
  emit('update:show', false)
}

async function loadData() {
  try {
    const csrf = document.querySelector('meta[name="csrf-token"]')?.content || ''
    const [calRes, catRes, resRes, settingsRes] = await Promise.all([
      fetch("/api/method/diakronos.kronos.api.permissions.get_writable_calendars", { credentials: 'same-origin' }).then(r => r.json()),
      fetch("/api/resource/Eventkategorie?fields=[\"name\",\"event_category_name\"]&limit_page_length=500", { credentials: 'same-origin' }).then(r => r.json()),
      fetch("/api/method/diakronos.kronos.api.ressource_api.get_ressources", {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': csrf },
        body: JSON.stringify({})
      }).then(r => r.json()),
      fetch("/api/method/diakronos.kronos.api.ressource_api.get_kronos_settings", {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': csrf },
        body: JSON.stringify({})
      }).then(r => r.json())
    ])

    calendars.value = calRes.message || []
    categories.value = catRes.data || []
    ressources.value = resRes.message || []
    kronosSettings.value = settingsRes.message || {}
  } catch (err) {
    console.error('Fehler beim Laden der Daten:', err)
  }
}

async function checkConflict() {
  if (!form.ressource || form.ignore_conflict) return false
  try {
    const csrf = document.querySelector('meta[name="csrf-token"]')?.content || ''
    const res = await fetch("/api/method/diakronos.kronos.api.ressource_api.check_resource_conflict", {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': csrf },
      body: JSON.stringify({
        ressource: form.ressource,
        element_start: form.element_start,
        element_end: form.element_end
      })
    })
    const data = await res.json()
    return data.message?.has_conflict || false
  } catch (err) {
    console.error('Konfliktprüfung fehlgeschlagen:', err)
    return false
  }
}

async function save() {
  if (!form.element_name || !form.element_calendar || !form.element_start) {
    alert('Bitte füllen Sie alle Pflichtfelder aus.')
    return
  }

  const hasConflict = await checkConflict()
  if (hasConflict) {
    const result = await conflictDialog.value?.show({
      element_name: form.element_name,
      element_start: form.element_start,
      element_end: form.element_end,
      ressource: form.ressource
    })
    if (!result) return
    if (result === 'ignore') form.ignore_conflict = true
  }

  await doSave()
}

async function doSave() {
  const payload = {
    element_name: form.element_name,
    element_start: form.element_start,
    element_end: form.element_end,
    all_day: form.all_day ? 1 : 0,
    element_calendar: form.element_calendar,
    ressource: form.ressource || null,
    description: form.description || null,
    element_category: form.element_category || null,
    ignore_conflict: form.ignore_conflict ? 1 : 0
  }

  try {
    const csrf = document.querySelector('meta[name="csrf-token"]')?.content || ''
    let res
    if (form.is_series && form.repeat_type) {
      payload.repeat_type = form.repeat_type
      payload.series_end = form.series_end || null
      res = await fetch("/api/method/diakronos.kronos.api.event_crud.create_series", {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': csrf },
        body: JSON.stringify(payload)
      })
    } else {
      res = await fetch("/api/method/diakronos.kronos.api.event_crud.create_event", {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': csrf },
        body: JSON.stringify(payload)
      })
    }

    const data = await res.json()
    if (data.message) {
      emit('created', data.message)
      close()
      resetForm()
    } else {
      alert(data.exc || 'Fehler beim Erstellen des Termins.')
    }
  } catch (err) {
    console.error('Speichern fehlgeschlagen:', err)
    alert('Fehler beim Speichern.')
  }
}

watch(() => props.show, async (val) => {
  if (val) {
    resetForm()
    await nextTick()
    initFlatpickr()
  } else {
    destroyFlatpickr()
  }
})

onMounted(() => {
  loadData()
  if (props.show) {
    resetForm()
    nextTick(() => initFlatpickr())
  }
})
</script>

<style scoped>
.diakronos-modal {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1050;
  opacity: 0;
  visibility: hidden;
  transition: opacity 0.3s ease, visibility 0.3s ease;
}
.diakronos-modal.show {
  opacity: 1;
  visibility: visible;
}
.diakronos-modal-dialog {
  background: #fff;
  border-radius: 8px;
  max-width: 560px;
  width: 90%;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.diakronos-modal-content {
  display: flex;
  flex-direction: column;
  max-height: 90vh;
}
.diakronos-color-bar {
  height: 6px;
  width: 100%;
  transition: background-color 0.3s ease;
}
.diakronos-modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #e5e7eb;
}
.diakronos-modal-header h3 {
  margin: 0;
  font-size: 1.15rem;
  font-weight: 600;
}
.close-btn {
  background: none;
  border: none;
  font-size: 1.5rem;
  cursor: pointer;
  color: #6b7280;
}
.diakronos-tabs {
  display: flex;
  border-bottom: 1px solid #e5e7eb;
}
.tab-btn {
  flex: 1;
  padding: 10px;
  background: none;
  border: none;
  cursor: pointer;
  font-weight: 500;
  color: #6b7280;
  border-bottom: 2px solid transparent;
  transition: all 0.2s;
}
.tab-btn.active {
  color: #2563eb;
  border-bottom-color: #2563eb;
}
.tab-content {
  display: block;
  padding: 16px 20px;
  overflow-y: auto;
  max-height: calc(90vh - 200px);
}
.form-group {
  margin-bottom: 12px;
}
.form-group label {
  display: block;
  margin-bottom: 4px;
  font-weight: 500;
  font-size: 0.875rem;
  color: #374151;
}
.form-group input,
.form-group select,
.form-group textarea {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 0.875rem;
  box-sizing: border-box;
}
.form-row {
  display: flex;
  gap: 12px;
}
.form-row .form-group {
  flex: 1;
}
.checkbox-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}
.checkbox-row input[type="checkbox"] {
  width: auto;
}
.diakronos-modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 12px 20px;
  border-top: 1px solid #e5e7eb;
}
.btn-primary,
.btn-secondary {
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 0.875rem;
  cursor: pointer;
  border: none;
}
.btn-primary {
  background: #2563eb;
  color: #fff;
}
.btn-secondary {
  background: #f3f4f6;
  color: #374151;
}
input[type="checkbox"] {
  appearance: auto;
  -webkit-appearance: auto;
  width: 16px;
  height: 16px;
  cursor: pointer;
  flex-shrink: 0;
}
</style>
