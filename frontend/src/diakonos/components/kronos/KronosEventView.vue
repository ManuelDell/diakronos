<script setup>
import { computed, onMounted, onBeforeUnmount } from 'vue'
import DkBadge from '../ui/DkBadge.vue'
import { sichereFarbe } from '../../../shared/sichere-ausgabe.js'
import { useZurueckSchliesst } from '../../composables/useZurueckSchliesst.js'

const props = defineProps({
  show: { type: Boolean, required: true },
  event: { type: Object, default: null }
})

const emit = defineEmits(['update:show'])

function formatTime(event) {
  if (!event) return '—'
  const s = new Date((event.element_start || '').replace(' ', 'T'))
  const e = new Date((event.element_end || '').replace(' ', 'T'))
  const optsD = { weekday: 'short', day: 'numeric', month: 'short' }
  const optsT = { hour: '2-digit', minute: '2-digit' }
  const sameDay = s.toDateString() === e.toDateString()
  if (event.all_day) {
    return s.toLocaleDateString('de-DE', { ...optsD, year: 'numeric' }) + ' (Ganztägig)'
  }
  if (sameDay) {
    return s.toLocaleDateString('de-DE', optsD) + ' ' +
           s.toLocaleTimeString('de-DE', optsT) + ' – ' +
           e.toLocaleTimeString('de-DE', optsT)
  }
  return s.toLocaleDateString('de-DE', { ...optsD, ...optsT }) + ' – ' +
         e.toLocaleDateString('de-DE', { ...optsD, ...optsT })
}

const descLines = computed(() => {
  const d = props.event?.description
  return d ? String(d).split('\n') : ['—']
})

const resourceTitle = computed(() => {
  // The event's extendedProps.ressource holds the Link name; we need the title
  // calendar_get.py already resolves ressource_name for zusaetzliche_ressourcen
  // For the primary Ort, we show the ressource ID as fallback
  return props.event?.ressource_name || props.event?.ressource || '—'
})

const additionalResources = computed(() => {
  return props.event?.zusaetzliche_ressourcen || []
})

/** Bestätigt → ok, sonst (z. B. Angefragt) → warn. */
function statusVariant(status) {
  return status === 'Bestätigt' ? 'ok' : 'warn'
}

/** K-A: Ablehnungsgrund aus den extendedProps (nur Antragsteller/Moderator).
 *  Der Server liefert die Felder nur an den Antragsteller bzw. Moderatoren —
 *  fehlen sie, bleibt der Block aus. */
const ablehnungsGrund = computed(
  () => props.event?.ablehnungs_grund || props.event?.extendedProps?.ablehnungs_grund || ''
)
const moderiertVon = computed(
  () => props.event?.moderiert_von || props.event?.extendedProps?.moderiert_von || ''
)

function onKeydown(e) {
  if (e.key === 'Escape') emit('update:show', false)
}

onMounted(() => document.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => document.removeEventListener('keydown', onKeydown))

// OP-HANDY-7: Die Zurück-Taste/-Geste schließt das Termin-Fenster. Vorher
// blieb es offen und blockierte die Taps auf der Seite darunter.
useZurueckSchliesst(computed(() => props.show), () => emit('update:show', false))
</script>

<template>
  <Teleport to="body">
    <div v-if="show" class="diakronos-modal show" @click.self="emit('update:show', false)">
      <div class="diakronos-modal-dialog modal-dialog-centered modal-md">
        <div class="diakronos-modal-content">
          <div class="diakronos-color-bar" :style="{ background: sichereFarbe(event?.element_color) || 'var(--primary)' }"></div>
          <div class="diakronos-modal-header">
            <h5 class="modal-title">{{ event?.element_name || 'Termin' }}</h5>
            <button class="diakronos-close-btn" aria-label="Schließen" @click="emit('update:show', false)">&times;</button>
          </div>
          <div class="diakronos-modal-body">
            <div class="event-time">{{ formatTime(event) }}</div>
            <!-- K-A (R-P1-8): Ein abgelehnter Termin des Antragstellers nennt
                 den Grund — der Server liefert ihn nur an ihn bzw. Moderatoren. -->
            <div v-if="ablehnungsGrund" class="event-ablehnung">
              <strong>Abgelehnt</strong>
              <span v-if="moderiertVon"> — bearbeitet von {{ moderiertVon }}</span>
              <div class="event-ablehnung-grund">{{ ablehnungsGrund }}</div>
            </div>
            <dl class="diakronos-dl">
              <dt>Kalender</dt><dd>{{ event?.element_calendar || '—' }}</dd>
              <dt>Kategorie</dt><dd>{{ event?.event_category_name || '—' }}</dd>
              <dt>Ort</dt><dd>{{ resourceTitle }}</dd>
              <template v-if="additionalResources.length > 0">
                <dt>Weitere Ressourcen</dt>
                <dd>
                  <div class="additional-resources-list">
                    <div
                      v-for="(res, idx) in additionalResources"
                      :key="idx"
                      class="additional-resource-item"
                    >
                      <span class="resource-label">
                        {{ res.ressource_name || res.freitext_ressource || '—' }}
                      </span>
                      <DkBadge :variant="statusVariant(res.status)">{{ res.status }}</DkBadge>
                    </div>
                  </div>
                </dd>
              </template>
              <dt>Beschreibung</dt>
              <dd>
                <template v-for="(line, i) in descLines" :key="i">
                  <br v-if="i > 0" />{{ line }}
                </template>
              </dd>
            </dl>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.diakronos-modal {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: color-mix(in oklch, var(--dk-navy-900) 55%, transparent);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: var(--z-modal);
  opacity: 0;
  visibility: hidden;
  transition: opacity var(--med) var(--ease), visibility var(--med) var(--ease);
}
.diakronos-modal.show {
  opacity: 1;
  visibility: visible;
}
.diakronos-modal-dialog {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
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
}
.diakronos-modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--sp-4) var(--sp-5);
  border-bottom: 1px solid var(--line);
}
.diakronos-modal-header h5 {
  margin: 0;
  font-size: var(--fs-h2);
  font-weight: var(--fw-h);
  color: var(--text);
}
.diakronos-close-btn {
  background: none;
  border: none;
  font-size: 1.5rem;
  cursor: pointer;
  color: var(--muted);
  line-height: 1;
}
.diakronos-close-btn:hover { color: var(--text); }
.diakronos-modal-body {
  padding: var(--sp-4) var(--sp-5);
  overflow-y: auto;
}
.event-time {
  font-size: var(--fs);
  color: var(--muted);
  margin-bottom: var(--sp-3);
}
.event-ablehnung {
  border-left: 3px solid var(--dk-danger);
  background: color-mix(in oklch, var(--dk-danger) 8%, transparent);
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius-sm);
  margin-bottom: var(--sp-3);
  font-size: var(--fs-sm);
}
.event-ablehnung-grund { margin-top: var(--sp-1); color: var(--text); white-space: pre-wrap; }
.diakronos-dl {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: var(--sp-1) var(--sp-3);
  margin: 0;
}
.diakronos-dl dt {
  font-weight: 600;
  font-size: var(--fs);
  color: var(--text);
}
.diakronos-dl dd {
  margin: 0;
  font-size: var(--fs);
  color: var(--muted);
}

/* Additional resources */
.additional-resources-list {
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
}
.additional-resource-item {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}
.resource-label {
  font-size: var(--fs);
}
</style>
