<script setup>
import { ref } from 'vue'

const visible = ref(false)
const conflictData = ref(null)
let _resolve = null

function formatTime(iso) {
  if (!iso) return '—'
  const d = new Date(String(iso).replace(' ', 'T'))
  return d.toLocaleString('de-DE', {
    weekday: 'short', day: 'numeric', month: 'short',
    hour: '2-digit', minute: '2-digit'
  })
}

function show(data) {
  conflictData.value = data
  visible.value = true
  return new Promise(r => { _resolve = r })
}

function close(result) {
  visible.value = false
  if (_resolve) { _resolve(result); _resolve = null }
}

defineExpose({ show })
</script>

<template>
  <Teleport to="body">
    <div v-if="visible" class="diakronos-modal diakronos-conflict-modal show" @click.self="close(null)">
      <div class="diakronos-modal-dialog modal-dialog-centered" style="max-width:420px">
        <div class="diakronos-modal-content">
          <div class="conflict-modal-header">
            <span class="conflict-icon">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"></path>
                <line x1="12" y1="9" x2="12" y2="13"></line>
                <line x1="12" y1="17" x2="12.01" y2="17"></line>
              </svg>
            </span>
            <h5>Zeitüberschneidung</h5>
            <button class="diakronos-close-btn" @click="close(null)">&times;</button>
          </div>
          <div class="conflict-modal-body">
            <p>Die gewählte Ressource ist bereits belegt:</p>
            <div class="conflict-event-card">
              <strong>{{ conflictData?.title }}</strong>
              <span class="conflict-event-time">{{ formatTime(conflictData?.start) }} – {{ formatTime(conflictData?.end) }}</span>
            </div>
            <p class="conflict-question">Wie soll fortgefahren werden?</p>
          </div>
          <div class="conflict-modal-footer">
            <button class="btn btn-secondary" @click="close(null)">Abbrechen</button>
            <button class="btn btn-warning" @click="close('ignore')">Trotzdem speichern</button>
            <button class="btn btn-danger" @click="close('conflict')">Als Konflikt markieren</button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
