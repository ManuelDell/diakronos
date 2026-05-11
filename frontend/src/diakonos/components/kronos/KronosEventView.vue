<script setup>
import { computed, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps({
  show: { type: Boolean, required: true },
  event: { type: Object, default: null }
})

const emit = defineEmits(['update:show'])

function safeColor(c) {
  return c && /^#[0-9a-fA-F]{3,8}$|^var\(/.test(c) ? c : 'var(--primary)'
}

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

function onKeydown(e) {
  if (e.key === 'Escape') emit('update:show', false)
}

onMounted(() => document.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => document.removeEventListener('keydown', onKeydown))
</script>

<template>
  <Teleport to="body">
    <div v-if="show" class="diakronos-modal show" @click.self="emit('update:show', false)">
      <div class="diakronos-modal-dialog modal-dialog-centered modal-md">
        <div class="diakronos-modal-content">
          <div class="diakronos-color-bar" :style="{ background: safeColor(event?.element_color) }"></div>
          <div class="diakronos-modal-header">
            <h5 class="modal-title">{{ event?.element_name || 'Termin' }}</h5>
            <button class="diakronos-close-btn" @click="emit('update:show', false)">&times;</button>
          </div>
          <div class="diakronos-modal-body">
            <div class="event-time">{{ formatTime(event) }}</div>
            <dl class="diakronos-dl">
              <dt>Kalender</dt><dd>{{ event?.element_calendar || '—' }}</dd>
              <dt>Kategorie</dt><dd>{{ event?.event_category_name || '—' }}</dd>
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
