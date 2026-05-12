<template>
  <BaseWidgetCard label="Anstehende Termine" gridSize="medium" :loading :error :isEmpty emptyMessage="Keine anstehenden Termine." :isEditing @refresh="refresh" @hide="$emit('hide')" @collapse-change="$emit('collapse-change', $event)">
    <ul class="widget-list">
      <li v-for="item in data" :key="item.element_start + item.element_name">
        <div class="event-date">{{ new Date(item.element_start).toLocaleDateString('de-DE',{weekday:'short',day:'2-digit',month:'short'}) }}</div>
        <div class="event-name">{{ item.element_name }}</div>
        <div class="event-cal">{{ item.element_calendar }}</div>
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
</script>
