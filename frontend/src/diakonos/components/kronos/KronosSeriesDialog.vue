<script setup>
import { apiAntwortPruefen } from '../../composables/useApi.js'
import { computed, ref } from 'vue'
import { showToast } from '../../composables/useToast.js'
import { useDialogFokus } from '../../composables/useDialogFokus.js'
// UXD-R28: Terminfarbe nur als gueltiger Hex-Wert in den style-String.
import { sichereFarbe } from '../../../shared/sichere-ausgabe.js'

const mode = ref(null)      // 'drag' | 'edit'
const visible = ref(false)
// DES-R6: Fokusfuehrung und Esc-Schliessen wie in DkDialog.
const fenster = ref(null)
const eventData = ref(null)
const rememberSession = ref(false)
const confirmLoeschen = ref(null)   // 'future' | 'all' | null
const loescht = ref(false)
let _resolve = null

/** Anzahl der Termine der Serie, falls der Kalender sie mitliefert (UXK-R3). */
const serienAnzahl = computed(() => {
  const n = eventData.value?.series_count
  return typeof n === 'number' && n > 0 ? n : null
})

/** Rueckfrage mit Folge in Zahlen („4 Termine löschen?"). */
const loeschWarnung = computed(() => {
  const anzahl = serienAnzahl.value
  if (confirmLoeschen.value === 'all') {
    return anzahl
      ? `Wirklich die GESAMTE Serie löschen? ${anzahl} Termine werden gelöscht – das lässt sich nicht rückgängig machen.`
      : 'Wirklich die GESAMTE Serie löschen? Das lässt sich nicht rückgängig machen.'
  }
  return anzahl
    ? `Wirklich alle nachfolgenden Termine löschen? Betroffen sind ${anzahl} Termine der Serie – das lässt sich nicht rückgängig machen.`
    : 'Wirklich alle nachfolgenden Termine löschen? Das lässt sich nicht rückgängig machen.'
})

function showDragConfirmation(ev) {
  mode.value = 'drag'
  eventData.value = ev
  visible.value = true
  rememberSession.value = false
  confirmLoeschen.value = null
  return new Promise(r => { _resolve = r })
}

function showEditOptions(el) {
  mode.value = 'edit'
  eventData.value = el
  visible.value = true
  confirmLoeschen.value = null
  return new Promise(r => { _resolve = r })
}

function zurueck() {
  confirmLoeschen.value = null
}

async function deleteAction(type) {
  if (loescht.value) return
  loescht.value = true
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || ''
  const endpoint = type === 'future'
    ? '/api/method/diakronos.kronos.api.series.delete_future_series_events'
    : '/api/method/diakronos.kronos.api.series.delete_series_batch_fast'
  const body = type === 'future'
    // BLD-R5: Das Datum wird als reiner ISO-Tag gesendet (`YYYY-MM-DD`).
    // Vorher ging der ganze Zeitstempel aus dem Kalender mit („2026-11-08
    // 10:00:00“) — der Server verglich ihn mit der Termin-Spalte, PostgreSQL
    // konnte das nicht casten und antwortete mit einem unbehandelten 500er.
    ? { series_id: eventData.value.series_id,
        from_date: String(eventData.value.element_start || '').slice(0, 10) }
    : { series_id: eventData.value.series_id }
  try {
    const res = await fetch(endpoint, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': csrf },
      body: JSON.stringify(body)
    })
    // UXK-R2: Fehlerantworten waren frueher unsichtbar (der Aufruf wertete sie
    // nie aus); der Nutzer glaubte an Erfolg, obwohl nichts gelöscht wurde.
    let data = null
    try { data = await apiAntwortPruefen(res, { fehlerWerfen: false }) } catch { data = null }
    if (!res.ok || !data || data.exc || data.message?.success !== true) {
      showToast(fehlerText(data, res), 'error')
      loescht.value = false
      confirmLoeschen.value = null
      return
    }
    const anzahl = data.message?.deleted_count
    showToast(
      typeof anzahl === 'number' ? `${anzahl} Termine gelöscht.` : 'Serie gelöscht.',
      'success'
    )
    loescht.value = false
    confirmLoeschen.value = null
    close('deleted')
  } catch (e) {
    console.error('deleteAction failed', e)
    showToast('Serie konnte nicht gelöscht werden. Bitte erneut versuchen.', 'error')
    loescht.value = false
    confirmLoeschen.value = null
  }
}

function fehlerText(data, res) {
  if (data) {
    for (const k of [data.message, data.exception, data.exc, data.error]) {
      if (typeof k === 'string' && k.trim()) return k.replace(/<[^>]+>/g, ' ').trim()
    }
  }
  if (res.status === 403) return 'Keine Berechtigung: Du darfst diese Serie nicht löschen.'
  if (res.status >= 500) return 'Der Server konnte die Serie nicht löschen. Bitte später erneut versuchen.'
  return 'Serie konnte nicht gelöscht werden.'
}

function close(result) {
  visible.value = false
  confirmLoeschen.value = null
  loescht.value = false
  if (_resolve) { _resolve(result); _resolve = null }
}

// DES-R6: Fokus hinein, Tab bleibt im Fenster, Esc schliesst ohne Auswahl.
const { tastenFaenger } = useDialogFokus(visible, fenster, () => close(null))

defineExpose({ showDragConfirmation, showEditOptions })
</script>

<template>
  <Teleport to="body">
    <div v-if="visible" class="diakronos-modal show" @click.self="close(null)">
      <div
        ref="fenster"
        class="diakronos-modal-dialog"
        style="max-width:380px"
        role="dialog"
        aria-modal="true"
        aria-label="Serientermin"
        tabindex="-1"
        @keydown="tastenFaenger"
      >
        <div class="diakronos-modal-content">
          <div class="diakronos-color-bar" :style="{ background: sichereFarbe(eventData?.element_color || eventData?.extendedProps?.element_color) || 'var(--primary)' }"></div>

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
              <!-- UXK-R2/UXK-R3: Loeschen erst nach Rueckfrage. -->
              <template v-if="confirmLoeschen">
                <p class="loesch-warnung">
                  {{ loeschWarnung }}
                </p>
                <div class="series-option-btns">
                  <button class="btn btn-danger" :disabled="loescht" @click="deleteAction(confirmLoeschen)">
                    {{ loescht ? 'Lösche…' : 'Ja, löschen' }}
                  </button>
                  <button class="btn btn-secondary" :disabled="loescht" @click="zurueck">Abbrechen</button>
                </div>
              </template>
              <template v-else>
                <p>Was möchtest du tun?</p>
                <div class="series-option-btns">
                  <button class="btn btn-primary" @click="close('edit')">Bearbeiten als Einzeltermin</button>
                  <button class="btn btn-danger" @click="confirmLoeschen = 'future'">Alle nachfolgenden löschen</button>
                  <button class="btn btn-danger" @click="confirmLoeschen = 'all'">Gesamte Serie löschen</button>
                </div>
              </template>
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
.loesch-warnung {
  color: var(--err);
  font-weight: 500;
}
</style>
