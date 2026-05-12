<template>
  <BaseWidgetCard label="Mitglieder-Statistik" gridSize="large" :loading :error :isEmpty emptyMessage="Keine Statistiken verfügbar." :isEditing @refresh="refresh" @hide="$emit('hide')" @collapse-change="$emit('collapse-change', $event)">
    <div class="stat-cards-grid">
      <div v-for="item in data" :key="item.label" class="stat-card">
        <div class="stat-value">{{ item.value }}</div>
        <div class="stat-label">{{ item.label }}</div>
        <div class="stat-trend">{{ item.trend }}</div>
        <div v-if="item.note" class="stat-note">{{ item.note }}</div>
      </div>
    </div>
  </BaseWidgetCard>
</template>
<script setup>
import BaseWidgetCard from './BaseWidgetCard.vue'
import { useWidgetData } from '../../composables/useWidgetData'
import { computed } from 'vue'
const props = defineProps({ isEditing: Boolean, refreshInterval: { type: Number, default: 60 } })
const emit = defineEmits(['hide', 'collapse-change'])
const { data, loading, error, refresh } = useWidgetData('member-stats', props.refreshInterval)
const isEmpty = computed(() => !data.value || (Array.isArray(data.value) && !data.value.length))
</script>
