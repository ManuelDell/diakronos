<template>
  <BaseWidgetCard label="Wiki-Einträge" gridSize="small" :loading :error :isEmpty emptyMessage="Keine Wiki-Einträge." :isEditing @refresh="refresh" @hide="$emit('hide')" @collapse-change="$emit('collapse-change', $event)">
    <ul class="wl-list">
      <li v-for="item in data" :key="item.route" class="wl-wiki">
        <a :href="'#/wiki'" class="wl-wiki-title">{{ item.title }}</a>
        <span class="wl-wiki-date">{{ formatDate(item.modified) }}</span>
      </li>
    </ul>
  </BaseWidgetCard>
</template>
<script setup>
import BaseWidgetCard from './BaseWidgetCard.vue'
import { useWidgetData } from '../../composables/useWidgetData'
import { serverZeit, GEMEINDE_ZONE } from '../../../shared/zeit.mjs'
import { computed } from 'vue'
const props = defineProps({ isEditing: Boolean, refreshInterval: { type: Number, default: 60 } })
const emit = defineEmits(['hide', 'collapse-change'])
const { data, loading, error, refresh } = useWidgetData('wiki-recent', props.refreshInterval)
const isEmpty = computed(() => !data.value || (Array.isArray(data.value) && !data.value.length))
/** ZEIT-2: `modified` ist ein SERVER-Zeitstempel (UTC ohne Zone). */
function formatDate(s) {
  const d = serverZeit(s)
  if (!d) return s || ''
  return new Intl.DateTimeFormat('de-DE', {
    day: '2-digit', month: 'short', year: 'numeric', timeZone: GEMEINDE_ZONE,
  }).format(d)
}
</script>
