<template>
  <BaseWidgetCard label="Ankündigungen" gridSize="medium" :loading :error :isEmpty emptyMessage="Keine Ankündigungen." :isEditing @refresh="refresh" @hide="$emit('hide')" @collapse-change="$emit('collapse-change', $event)">
    <ul class="widget-list">
      <li v-for="item in (data || []).slice(0, 3)" :key="item.id">
        <div class="announce-subject">{{ item.title }}</div>
        <div class="announce-content">{{ (item.excerpt || '').slice(0, 100) }}</div>
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
const { data, loading, error, refresh } = useWidgetData('announcements', props.refreshInterval)
const isEmpty = computed(() => !data.value || (Array.isArray(data.value) && !data.value.length))
</script>
