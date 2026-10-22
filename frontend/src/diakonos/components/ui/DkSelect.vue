<template>
  <select
    class="dk-ui-select"
    :id="id || undefined"
    :value="modelValue ?? ''"
    :disabled="disabled"
    :aria-label="ariaLabel || undefined"
    :aria-describedby="ariaDescribedby || undefined"
    :aria-invalid="invalid || undefined"
    @change="$emit('update:modelValue', $event.target.value === '' ? (emptyValue ?? '') : $event.target.value)"
  >
    <option v-if="placeholder" value="" disabled>{{ placeholder }}</option>
    <option v-for="o in optionen" :key="wert(o)" :value="wert(o)">{{ label(o) }}</option>
  </select>
</template>

<script setup>
/**
 * DkSelect — Auswahlfeld (Stil A). Optionen sind Objekte mit value/label
 * oder einfache Skalare.
 * Nur Tokens, keine festen Farben.
 */
import { computed } from 'vue'

const props = defineProps({
  modelValue: { default: '' },
  options: { type: Array, default: () => [] },
  placeholder: { type: String, default: '' },
  disabled: Boolean,
  ariaLabel: { type: String, default: '' },
  // DES-R19: von DkField durchgereichte Kennungen, damit <label for> greift.
  id: { type: String, default: '' },
  ariaDescribedby: { type: String, default: '' },
  invalid: Boolean,
  // Wert, der beim Zurücksetzen auf die leere Option gesendet wird
  emptyValue: { default: null },
})
defineEmits(['update:modelValue'])

const optionen = computed(() => props.options || [])
function wert(o) {
  if (o !== null && typeof o === 'object') return o.value
  return o
}
function label(o) {
  if (o !== null && typeof o === 'object') return o.label ?? o.value
  return o
}
</script>

<style scoped>
.dk-ui-select {
  width: 100%;
  height: var(--control-h);
  padding: 0 12px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--text);
  font: inherit;
  font-size: var(--fs);
  cursor: pointer;
}
.dk-ui-select:focus {
  outline: 2px solid var(--focus-ring);
  outline-offset: 0;
  border-color: var(--dk-navy-400);
}
.dk-ui-select:disabled { opacity: .6; cursor: default; }
.dk-ui-select[aria-invalid="true"] { border-color: var(--err); }
</style>
