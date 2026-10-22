<template>
  <BaseWidgetCard label="Meine Buchungen" gridSize="small" :loading :error :isEmpty emptyMessage="Keine Buchungen." :isEditing @refresh="refresh" @hide="$emit('hide')" @collapse-change="$emit('collapse-change', $event)">
    <ul class="widget-list">
      <li v-for="item in upcomingBookings" :key="item.start_date + item.ressource_name">
        <div class="booking-res">{{ item.ressource_name }}</div>
        <div class="booking-date">{{ item.start_date }} – {{ item.end_date }}</div>
        <div class="booking-status">{{ item.status }}</div>
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
const { data, loading, error, refresh } = useWidgetData('my-bookings', props.refreshInterval)
const isEmpty = computed(() => !data.value || (Array.isArray(data.value) && !data.value.length))
const upcomingBookings = computed(() => (data.value || []).slice(0, 3))
</script>
