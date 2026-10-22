<template>
  <div class="dk-ui-segment" role="tablist" :aria-label="ariaLabel || undefined">
    <button
      v-for="o in optionen"
      :key="wert(o)"
      type="button"
      role="tab"
      class="dk-ui-segment-item"
      :class="{ 'is-active': wert(o) === modelValue }"
      :aria-selected="wert(o) === modelValue"
      @click="$emit('update:modelValue', wert(o))"
    >{{ label(o) }}</button>
  </div>
</template>

<script setup>
/**
 * DkSegment — Umschalter/Tabs als Segmentleiste (Stil A).
 * Optionen wie bei DkSelect (Skalar oder {value,label}).
 * Für die reine Anzeige von Reitern mit anderem Inhalt siehe DkTabs.
 * Nur Tokens, keine festen Farben.
 */
import { computed } from 'vue'

const props = defineProps({
  modelValue: { default: '' },
  options: { type: Array, default: () => [] },
  ariaLabel: { type: String, default: '' },
})
defineEmits(['update:modelValue'])

const optionen = computed(() => props.options || [])
function wert(o) { return (o !== null && typeof o === 'object') ? o.value : o }
function label(o) { return (o !== null && typeof o === 'object') ? (o.label ?? o.value) : o }
</script>

<style scoped>
.dk-ui-segment {
  display: inline-flex;
  gap: 3px;
  padding: 3px;
  border-radius: var(--radius);
  background: var(--surface-2);
  flex-wrap: wrap;
}
.dk-ui-segment-item {
  height: calc(var(--control-h) - 6px);
  padding: 0 12px;
  border: none;
  border-radius: calc(var(--radius) - 2px);
  background: transparent;
  color: var(--muted);
  font: inherit;
  font-weight: 550;
  cursor: pointer;
  white-space: nowrap;
  transition: background var(--fast), color var(--fast);
}
.dk-ui-segment-item:hover { color: var(--text); }
.dk-ui-segment-item.is-active {
  background: var(--surface);
  color: var(--text);
  box-shadow: var(--shadow);
}
.dk-ui-segment-item:focus-visible { outline: 2px solid var(--focus-ring); }
</style>
