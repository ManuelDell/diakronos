<template>
  <BaseWidgetCard label="Anstehende Termine" gridSize="medium" :loading :error :isEmpty emptyMessage="Keine anstehenden Termine." :isEditing @refresh="refresh" @hide="$emit('hide')" @collapse-change="$emit('collapse-change', $event)">
    <ul class="wl-list">
      <li v-for="item in data" :key="item.id" class="wl-event">
        <div class="wl-event-accent"></div>
        <div class="wl-event-body">
          <div class="wl-event-title">{{ item.title }}</div>
          <div class="wl-event-date">{{ formatDate(item.start) }}</div>
        </div>
      </li>
    </ul>
  </BaseWidgetCard>
</template>
<script setup>
import BaseWidgetCard from './BaseWidgetCard.vue'
import { useWidgetData } from '../../composables/useWidgetData'
import { computed } from 'vue'
const props = defineProps({ isEditing: Boolean, refreshInterval: { type: Number, default: 60 } })
const emit = defineEmits(['hide', 'collapse-change'])
const { data, loading, error, refresh } = useWidgetData('upcoming-events', props.refreshInterval)
const isEmpty = computed(() => !data.value || (Array.isArray(data.value) && !data.value.length))
function formatDate(s) {
  if (!s) return ''
  const d = new Date(s.replace(' ', 'T'))
  if (isNaN(d)) return s
  return d.toLocaleDateString('de-DE', { weekday: 'short', day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
}
</script>
