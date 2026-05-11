<script setup>
import { ref } from 'vue'

const mode = ref(null)      // 'drag' | 'edit'
const visible = ref(false)
const eventData = ref(null)
const rememberSession = ref(false)
let _resolve = null

function showDragConfirmation(ev) {
  mode.value = 'drag'
  eventData.value = ev
  visible.value = true
  rememberSession.value = false
  return new Promise(r => { _resolve = r })
}

function showEditOptions(el) {
  mode.value = 'edit'
  eventData.value = el
  visible.value = true
  return new Promise(r => { _resolve = r })
}

async function deleteAction(type) {
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || ''
  const endpoint = type === 'future'
    ? '/api/method/diakronos.kronos.api.series.delete_future_series_events'
    : '/api/method/diakronos.kronos.api.series.delete_series_batch_fast'
  const body = type === 'future'
    ? { series_id: eventData.value.series_id, from_date: eventData.value.element_start }
    : { series_id: eventData.value.series_id }
  try {
    await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': csrf },
      body: JSON.stringify(body)
    })
  } catch (e) {
    console.error('deleteAction failed', e)
  }
  close('cancelled')
}

function close(result) {
  visible.value = false
  if (_resolve) { _resolve(result); _resolve = null }
}

defineExpose({ showDragConfirmation, showEditOptions })
</script>

<template>
  <Teleport to="body">
    <div v-if="visible" class="diakronos-modal show" @click.self="close(null)">
      <div class="diakronos-modal-dialog" style="max-width:380px">
        <div class="diakronos-modal-content">
          <div class="diakronos-color-bar" :style="{ background: eventData?.element_color || eventData?.extendedProps?.element_color || 'var(--primary)' }"></div>

          <!-- Drag-Confirm Mode -->
          <template v-if="mode === 'drag'">
            <div class="diakronos-modal-header">
              <h5>Serientermin</h5>
              <button class="diakronos-close-btn" @click="close(null)">&times;</button>
            </div>
            <div class="diakronos-modal-body drag-confirm-body">
              <p class="series-event-name">{{ eventData?.title }}</p>
              <p>Diesen Termin aus der Serie lösen und verschieben?</p>
              <label class="checkbox-label">
                <input type="checkbox" v-model="rememberSession" />
                Diese Sitzung nicht mehr fragen
              </label>
            </div>
            <div class="diakronos-modal-footer">
              <button class="btn btn-secondary" @click="close(null)">Abbrechen</button>
              <button class="btn btn-primary" @click="close({ confirmed: true, rememberSession })">Ja, Sicher</button>
            </div>
          </template>

          <!-- Edit-Options Mode -->
          <template v-else-if="mode === 'edit'">
            <div class="diakronos-modal-header">
              <h5>Serientermin</h5>
              <button class="diakronos-close-btn" @click="close('cancelled')">&times;</button>
            </div>
            <div class="diakronos-modal-body">
              <p class="series-event-name">{{ eventData?.element_name }}</p>
              <p>Was möchten Sie tun?</p>
              <div class="series-option-btns">
                <button class="btn btn-primary" @click="close('edit')">Bearbeiten als Einzeltermin</button>
                <button class="btn btn-danger" @click="deleteAction('future')">Alle nachfolgenden löschen</button>
                <button class="btn btn-danger" @click="deleteAction('all')">Gesamte Serie löschen</button>
              </div>
            </div>
            <div class="diakronos-modal-footer">
              <button class="btn btn-secondary" @click="close('cancelled')">Abbrechen</button>
            </div>
          </template>
        </div>
      </div>
    </div>
  </Teleport>
</template>
<style scoped>
input[type="checkbox"] {
  appearance: auto;
  -webkit-appearance: auto;
  width: 16px;
  height: 16px;
  cursor: pointer;
  flex-shrink: 0;
}
.drag-confirm-body label.checkbox-label {
  margin-top: 12px;
}
</style>
