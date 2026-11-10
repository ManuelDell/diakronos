<template>
  <BaseWidgetCard label="Registrierungslinks" gridSize="medium" :loading :error :isEmpty emptyMessage="Keine offenen Registrierungen." :isEditing @refresh="refresh" @hide="$emit('hide')" @collapse-change="$emit('collapse-change', $event)">
    <ul class="widget-list">
      <li v-for="item in data" :key="item.anmeldeformular_id">
        <div class="signup-name">{{ item.name }}</div>
        <div class="signup-link">#{{ item.anmeldeformular_id }}</div>
        <!-- ZEIT-3: `creation` ist UTC — angezeigt wird die Zeitzone der
             Gemeinde (`shared/zeit.mjs`), nie der rohe Serverwert. -->
        <div class="signup-meta">Erstellt: {{ serverZeitText(item.creation) || '—' }} | Ablauf: {{ item.ablaufdatum }}</div>
      </li>
    </ul>
  </BaseWidgetCard>
</template>
<script setup>
import BaseWidgetCard from './BaseWidgetCard.vue'
import { useWidgetData } from '../../composables/useWidgetData'
import { computed } from 'vue'
import { serverZeitText } from '../../../shared/zeit.mjs'
const props = defineProps({ isEditing: Boolean, refreshInterval: { type: Number, default: 60 } })
const emit = defineEmits(['hide', 'collapse-change'])
const { data, loading, error, refresh } = useWidgetData('open-signups', props.refreshInterval)
const isEmpty = computed(() => !data.value || (Array.isArray(data.value) && !data.value.length))
</script>
