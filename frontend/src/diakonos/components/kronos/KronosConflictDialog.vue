<script setup>
import { ref } from 'vue'
import { useDialogFokus } from '../../composables/useDialogFokus.js'

const visible = ref(false)
const conflictData = ref(null)
let _resolve = null

// DES-R6: Fokusfuehrung und Esc-Schliessen wie in DkDialog.
const fenster = ref(null)

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

// DES-R6: Fokus hinein, Tab bleibt im Fenster, Esc schliesst ohne Auswahl.
const { tastenFaenger } = useDialogFokus(visible, fenster, () => close(null))

defineExpose({ show })
</script>

<template>
  <Teleport to="body">
    <div v-if="visible" class="diakronos-modal diakronos-conflict-modal show" @click.self="close(null)">
      <div
        ref="fenster"
        class="diakronos-modal-dialog modal-dialog-centered"
        style="max-width:420px"
        role="dialog"
        aria-modal="true"
        aria-label="Zeitüberschneidung"
        tabindex="-1"
        @keydown="tastenFaenger"
      >
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
            <template v-if="conflictData?.conflicts?.length">
              <div v-for="(c, i) in conflictData.conflicts" :key="`${c?.ressource || 'r'}-${i}`" class="conflict-event-card" style="margin-bottom:6px">
                <strong :title="c.ressource">{{ c.ressource_title || c.ressource }}</strong>
                <div v-for="ev in (c.events || [])" :key="ev.name" class="conflict-event-time">
                  {{ ev.element_name }} · {{ formatTime(ev.element_start) }} – {{ formatTime(ev.element_end) }}
                </div>
                <!-- OP-EVENT-11: Ressourcenbuchungen nennen bisher nur den
                     Gegenstand. Zweck, Zeitraum und Bucher mitanzeigen.
                     P1-4b/K1: fuer Nicht-Ressourcenmoderatoren maskiert der
                     Server den Buchernamen zu „Belegt“ — dann nicht „gebucht
                     von Belegt“ schreiben. -->
                <div v-for="b in (c.buchungen || [])" :key="b.name" class="conflict-event-time">
                  <template v-if="b.titel || b.zweck">
                    „{{ b.titel || b.zweck }}“
                  </template>
                  <template v-if="b.zeitraum"> · {{ b.zeitraum }}</template>
                  <template v-if="b.nutzer && b.nutzer !== 'Belegt'"> · gebucht von {{ b.nutzer }}</template>
                </div>
              </div>
            </template>
            <div v-else class="conflict-event-card">
              <strong>{{ conflictData?.element_name || conflictData?.title }}</strong>
              <span class="conflict-event-time">{{ formatTime(conflictData?.element_start || conflictData?.start) }} – {{ formatTime(conflictData?.element_end || conflictData?.end) }}</span>
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
