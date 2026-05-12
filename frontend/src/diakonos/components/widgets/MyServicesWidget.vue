<template>
  <BaseWidgetCard label="Meine Dienste" gridSize="medium" :loading="false" :error="null" :isEmpty="false" :isEditing @refresh="refresh" @hide="$emit('hide')" @collapse-change="$emit('collapse-change', $event)">
    <div class="widget-static">Dienstplan wird verknüpft.</div>
  </BaseWidgetCard>
</template>
<script setup>
import BaseWidgetCard from './BaseWidgetCard.vue'
const props = defineProps({ isEditing: Boolean, refreshInterval: { type: Number, default: 60 } })
const emit = defineEmits(['hide', 'collapse-change'])
const refresh = () => {}
</script>
