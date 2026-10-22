<template>
  <div class="dk-ui-field" :class="{ 'has-error': !!error, 'is-disabled': disabled }">
    <label v-if="label" :for="eingabeId" class="dk-ui-field-label">
      {{ label }}<span v-if="required" class="dk-ui-field-pflicht" aria-hidden="true">*</span>
    </label>
    <slot :id="eingabeId" :aria-describedby="beschreibungId" :aria-invalid="!!error" />
    <p v-if="error" :id="beschreibungId" class="dk-ui-field-fehler" role="alert">{{ error }}</p>
    <p v-else-if="help" :id="beschreibungId" class="dk-ui-field-hilfe">{{ help }}</p>
  </div>
</template>

<script setup>
/**
 * DkField — Hülle für ein Eingabefeld: Label, Hilfe, Fehler (Stil A).
 * Der Slot erhält id/aria-describedby/aria-invalid zur Auszeichnung des
 * eigenen <input>/<select>.
 * Nur Tokens, keine festen Farben.
 */
import { computed, useId } from 'vue'

const props = defineProps({
  label: { type: String, default: '' },
  help: { type: String, default: '' },
  error: { type: String, default: '' },
  required: Boolean,
  disabled: Boolean,
})
const id = useId()
const eingabeId = computed(() => 'dk-field-' + id)
const beschreibungId = computed(() => 'dk-field-desc-' + id)
</script>

<style scoped>
.dk-ui-field { display: flex; flex-direction: column; gap: var(--sp-1); }
.dk-ui-field-label {
  font-size: var(--fs-sm);
  font-weight: 600;
  color: var(--text);
}
.dk-ui-field-pflicht { color: var(--err); margin-left: 3px; }
.dk-ui-field-hilfe { font-size: var(--fs-sm); color: var(--muted); margin: 0; }
.dk-ui-field-fehler { font-size: var(--fs-sm); color: var(--err); margin: 0; font-weight: 500; }
.dk-ui-field.is-disabled { opacity: .6; }
</style>
