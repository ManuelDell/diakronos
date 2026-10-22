<template>
  <nav class="dk-ui-tabs" :aria-label="ariaLabel || undefined">
    <button
      v-for="o in optionen"
      :key="wert(o)"
      type="button"
      class="dk-ui-tab"
      :class="{ 'is-active': wert(o) === modelValue }"
      :aria-selected="wert(o) === modelValue"
      role="tab"
      @click="$emit('update:modelValue', wert(o))"
    >{{ label(o) }}</button>
  </nav>
</template>

<script setup>
/**
 * DkTabs — Reiter mit Unterstrich-Aktivzustand (Stil A), z. B. über einem
 * wechselnden Bereich. Optionen wie bei DkSelect.
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
.dk-ui-tabs {
  display: flex;
  gap: var(--sp-1);
  border-bottom: 1px solid var(--line);
  overflow-x: auto;
}
.dk-ui-tab {
  padding: 8px 14px;
  border: none;
  border-bottom: 2px solid transparent;
  background: none;
  color: var(--muted);
  font: inherit;
  font-weight: 550;
  cursor: pointer;
  white-space: nowrap;
  transition: color var(--fast), border-color var(--fast);
}
.dk-ui-tab:hover { color: var(--text); }
.dk-ui-tab.is-active {
  color: var(--primary);
  border-bottom-color: var(--accent);
  font-weight: 650;
}
.dk-ui-tab:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: -2px; }
</style>
