<template>
  <BaseWidgetCard label="Zu moderierende Termine" gridSize="medium" :loading :error :isEmpty emptyMessage="Alle Termine sind auf dem neuesten Stand." :isEditing @refresh="refresh" @hide="$emit('hide')" @collapse-change="$emit('collapse-change', $event)">
    <ul class="widget-list">
      <li v-for="item in data" :key="item.name + item.element_start">
        <div class="reg-name">{{ item.name }}</div>
        <div class="reg-event">{{ item.element_name }}</div>
        <div class="reg-res">{{ item.ressource }}</div>
      </li>
    </ul>
    <button class="dk-btn" @click="navigate('#/kalender')">→ Zum Kalender</button>
  </BaseWidgetCard>
</template>
<script setup>
import BaseWidgetCard from './BaseWidgetCard.vue'
import { useWidgetData } from '../../composables/useWidgetData'
import { computed } from 'vue'
const props = defineProps({ isEditing: Boolean, refreshInterval: { type: Number, default: 60 } })
const emit = defineEmits(['hide', 'collapse-change'])
const { data, loading, error, refresh } = useWidgetData('pending-registrations', props.refreshInterval)
const isEmpty = computed(() => !data.value || (Array.isArray(data.value) && !data.value.length))
const navigate = (href) => { window.location.hash = href }
</script>
