<template>
  <BaseWidgetCard label="Anmeldungen verwalten" gridSize="large" :loading :error :isEmpty emptyMessage="Keine Anmeldungen." :isEditing @refresh="refresh" @hide="$emit('hide')" @collapse-change="$emit('collapse-change', $event)">
    <ul class="widget-list reg-list">
      <li v-for="item in limitedData" :key="item.anmeldedatum + item.vorname + item.nachname">
        <div class="reg-avatar">{{ getInitials(item.vorname, item.nachname) }}</div>
        <div class="reg-info">
          <div class="reg-name">{{ item.vorname }} {{ item.nachname }}</div>
          <div class="reg-meta">{{ item.anmeldungstyp }} • {{ item.anmeldedatum }}</div>
        </div>
        <span class="dk-badge" :class="statusClass(item.status)">{{ item.status }}</span>
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
const { data, loading, error, refresh } = useWidgetData('manage-registrations', props.refreshInterval)
const isEmpty = computed(() => !data.value || (Array.isArray(data.value) && !data.value.length))
const limitedData = computed(() => (data.value || []).slice(0, 5))
const getInitials = (v, n) => ((v || '')[0] || '') + ((n || '')[0] || '')
const statusClass = (status) => {
  if (status === 'Ausstehend') return 'dk-badge-warn'
  if (status === 'Bestätigt') return 'dk-badge-ok'
  if (status === 'Abgelehnt') return 'dk-badge-err'
  return ''
}
</script>
