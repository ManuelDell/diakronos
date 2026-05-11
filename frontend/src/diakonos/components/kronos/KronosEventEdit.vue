<template>
  <Teleport to="body">
    <div v-if="show" class="diakronos-modal show" @click.self="close">
      <div class="diakronos-modal-dialog">
        <div class="diakronos-modal-content">
          <!-- Farbige Leiste -->
          <div class="diakronos-color-bar" :style="{ backgroundColor: selectedCalendarColor }"></div>

          <div class="diakronos-modal-header">
            <h3>Termin bearbeiten</h3>
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
                <input id="edit-all-day" v-model="form.all_day" type="checkbox" />
                <label for="edit-all-day">Ganztägig</label>
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
                <input id="edit-ignore-conflict" v-model="form.ignore_conflict" type="checkbox" />
                <label for="edit-ignore-conflict">Konflikte ignorieren</label>
              </div>

            </div>
          </div>

          <div class="diakronos-modal-footer">
            <button class="btn-danger btn-delete" v-if="!showDeleteConfirm" @click="showDeleteConfirm = true">
              Löschen
            </button>
            <div v-if="showDeleteConfirm" class="delete-confirm-inline">
              <span>Wirklich löschen?</span>
              <button class="btn-danger" @click="doDelete">Ja</button>
              <button class="btn-secondary" @click="showDeleteConfirm = false">Nein</button>
            </div>
            <div style="flex:1"></div>
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
  event: { type: Object, default: () => ({}) }
})

const emit = defineEmits(['update:show', 'updated', 'deleted'])

const activeTab = ref('basic')
const startInput = ref(null)
const endInput = ref(null)
const conflictDialog = ref(null)
const showDeleteConfirm = ref(false)

const calendars = ref([])
const categories = ref([])
const ressources = ref([])
const kronosSettings = ref({})

let fpStart = null
let fpEnd = null

const form = reactive({
  name: '',
  element_name: '',
  element_start: '',
  element_end: '',
  all_day: false,
  element_calendar: '',
  ressource: '',
  description: '',
  element_category: '',
  ignore_conflict: false,
  status: ''
})

const selectedCalendarColor = computed(() => {
  const cal = calendars.value.find(c => c.name === form.element_calendar)
  return cal?.color || '#4a90d9'
})

function populateForm() {
  const ev = props.event || {}
  form.name = ev.name || ''
  form.element_name = ev.element_name || ''
  form.element_start = ev.element_start || ''
  form.element_end = ev.element_end || ''
  form.all_day = !!ev.all_day
  form.element_calendar = ev.element_calendar || ''
  form.ressource = ev.ressource || ''
  form.description = ev.description || ''
  form.element_category = ev.element_category || ''
  form.ignore_conflict = !!ev.ignore_conflict
  form.status = ev.status || ''
  activeTab.value = 'basic'
  showDeleteConfirm.value = false
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
      }
    }
  }

  if (startInput.value && !fpStart) {
    fpStart = flatpickr(startInput.value, config)
  }
  if (endInput.value && !fpEnd) {
    fpEnd = flatpickr(endInput.value, config)
  }

  if (fpStart && form.element_start) fpStart.setDate(form.element_start, false)
  if (fpEnd && form.element_end) fpEnd.setDate(form.element_end, false)
}

function destroyFlatpickr() {
  if (fpStart) { fpStart.destroy(); fpStart = null }
  if (fpEnd) { fpEnd.destroy(); fpEnd = null }
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
        element_end: form.element_end,
        exclude_event: form.name
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
    name: form.name,
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
    const res = await fetch("/api/method/diakronos.kronos.api.event_crud.save_event", {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': csrf },
      body: JSON.stringify(payload)
    })

    const data = await res.json()
    if (data.message) {
      emit('updated')
      close()
    } else {
      alert(data.exc || 'Fehler beim Speichern des Termins.')
    }
  } catch (err) {
    console.error('Speichern fehlgeschlagen:', err)
    alert('Fehler beim Speichern.')
  }
}

async function doDelete() {
  if (!form.name) return
  try {
    const csrf = document.querySelector('meta[name="csrf-token"]')?.content || ''
    const res = await fetch("/api/method/diakronos.kronos.api.event_crud.delete_event", {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': csrf },
      body: JSON.stringify({ name: form.name })
    })

    const data = await res.json()
    if (data.message) {
      emit('deleted')
      close()
      showDeleteConfirm.value = false
    } else {
      alert(data.exc || 'Fehler beim Löschen des Termins.')
    }
  } catch (err) {
    console.error('Löschen fehlgeschlagen:', err)
    alert('Fehler beim Löschen.')
  }
}

watch(() => props.show, async (val) => {
  if (val) {
    populateForm()
    await nextTick()
    initFlatpickr()
  } else {
    destroyFlatpickr()
    showDeleteConfirm.value = false
  }
})

watch(() => props.event, (val) => {
  if (props.show && val) {
    populateForm()
    nextTick(() => {
      if (fpStart && form.element_start) fpStart.setDate(form.element_start, false)
      if (fpEnd && form.element_end) fpEnd.setDate(form.element_end, false)
    })
  }
}, { deep: true })

onMounted(() => {
  loadData()
  if (props.show) {
    populateForm()
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
.delete-section {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #e5e7eb;
}
.delete-confirm {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.delete-confirm span {
  font-weight: 500;
  color: #dc2626;
}
.btn-danger {
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 0.875rem;
  cursor: pointer;
  border: none;
  background: #dc2626;
  color: #fff;
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
.btn-delete {
  margin-right: auto;
}
.delete-confirm-inline {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-right: auto;
}
.delete-confirm-inline span {
  font-size: 0.875rem;
  color: #dc2626;
  font-weight: 500;
}
</style>
