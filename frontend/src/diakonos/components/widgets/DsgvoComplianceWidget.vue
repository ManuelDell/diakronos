<template>
  <BaseWidgetCard label="DSGVO-Compliance" gridSize="medium" :loading :error :isEmpty emptyMessage="Keine Daten verfügbar." :isEditing @refresh="refresh" @hide="$emit('hide')" @collapse-change="$emit('collapse-change', $event)">
    <div class="stat-grid small">
      <div class="stat-tile"><div class="stat-value">{{ data?.gesamt ?? 0 }}</div><div class="stat-label">Gesamt</div></div>
      <div class="stat-tile"><div class="stat-value">{{ data?.eingewilligt ?? 0 }}</div><div class="stat-label">Eingewilligt</div></div>
      <div class="stat-tile"><div class="stat-value">{{ data?.ausstehend ?? 0 }}</div><div class="stat-label">Ausstehend</div></div>
      <div class="stat-tile"><div class="stat-value">{{ data?.abgelehnt ?? 0 }}</div><div class="stat-label">Abgelehnt</div></div>
    </div>
  </BaseWidgetCard>
</template>
<script setup>
import BaseWidgetCard from './BaseWidgetCard.vue'
import { useWidgetData } from '../../composables/useWidgetData'
import { computed } from 'vue'
const props = defineProps({ isEditing: Boolean, refreshInterval: { type: Number, default: 60 } })
const emit = defineEmits(['hide', 'collapse-change'])
const { data, loading, error, refresh } = useWidgetData('dsgvo-compliance', props.refreshInterval)
const isEmpty = computed(() => !data.value || Object.keys(data.value).length === 0)
</script>
