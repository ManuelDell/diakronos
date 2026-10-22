<template>
  <VueDraggable
    v-if="isEditing"
    v-model="localWidgets"
    class="dk-widget-grid-wrapper"
    handle=".dk-drag-handle"
    :animation="200"
    @end="onDragEnd"
  >
    <component
      v-for="widget in localWidgets"
      :key="widget.widget_id"
      :is="getComponent(widget.widget_id)"
      v-bind="widgetProps(widget)"
      @hide="$emit('hide-widget', widget.widget_id)"
      @refresh="$emit('refresh-widget', widget.widget_id)"
      @collapse-change="(v) => $emit('collapse-widget', widget.widget_id, v)"
    />
  </VueDraggable>

  <div v-else class="dk-widget-grid-wrapper">
    <component
      v-for="widget in widgets"
      :key="widget.widget_id"
      :is="getComponent(widget.widget_id)"
      v-bind="widgetProps(widget)"
      @hide="$emit('hide-widget', widget.widget_id)"
      @refresh="$emit('refresh-widget', widget.widget_id)"
      @collapse-change="(v) => $emit('collapse-widget', widget.widget_id, v)"
    />
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { VueDraggable } from 'vue-draggable-plus'
import { useWidgetRegistry } from '../../composables/useWidgetRegistry'

const props = defineProps({
  widgets:     { type: Array, default: () => [] },
  isEditing:   { type: Boolean, default: false },
  badgeCounts: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['hide-widget', 'refresh-widget', 'collapse-widget', 'reorder'])

const { getComponent } = useWidgetRegistry()

// Lokale Kopie für DnD (wird nach Drop mit Store synchronisiert)
const localWidgets = ref([...props.widgets])

watch(() => props.widgets, (w) => {
  localWidgets.value = [...w]
}, { deep: true })

function onDragEnd() {
  // Positionen neu nummerieren und an Parent melden
  const reordered = localWidgets.value.map((w, i) => ({ ...w, position: i }))
  emit('reorder', reordered)
}

function widgetProps(widget) {
  return {
    isEditing:       props.isEditing,
    refreshInterval: widget.refresh_interval || 0,
    emptyMessage:    widget.empty_state_message || 'Keine Daten.',
    badgeCount:      props.badgeCounts[widget.widget_id] || 0,
  }
}
</script>
