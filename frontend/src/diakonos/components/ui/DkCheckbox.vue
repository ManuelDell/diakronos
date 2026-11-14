<template>
  <label class="dk-ui-checkbox" :class="{ 'is-disabled': disabled }">
    <input
      type="checkbox"
      :checked="!!modelValue"
      :disabled="disabled"
      :aria-label="ariaLabel || undefined"
      :aria-describedby="ariaDescribedby || undefined"
      @change="$emit('update:modelValue', $event.target.checked)"
    />
    <span v-if="label || $slots.default" class="dk-ui-checkbox-label">
      <slot>{{ label }}</slot>
    </span>
  </label>
</template>

<script setup>
/**
 * DkCheckbox — Ja/Nein-Kästchen mit Label (Stil A). Nutzt die native
 * Checkbox (Tastatur + Vorleseprogramme kostenlos korrekt).
 * Nur Tokens, keine festen Farben.
 */
defineProps({
  modelValue: Boolean,
  label: { type: String, default: '' },
  disabled: Boolean,
  /**
   * BS-3b: Kennung(en) des Erklärtextes — `aria-describedby` gehört auf das
   * Kästchen, nicht auf das umgebende `<label>` (dort liest es kein
   * Vorleseprogramm zuverlässig vor). Leer = kein Attribut im DOM.
   */
  ariaDescribedby: { type: String, default: '' },
  /**
   * UI-R9b: zugänglicher Name des KÄSTCHENS. Ein `aria-label` am umgebenden
   * `<label>` erreicht das `<input>` nicht — Vorleseprogramme lesen dann den
   * Zeilentext statt der Handlung („erledigt“/„wieder öffnen“). Diese Angabe
   * gehört deshalb auf das `<input>`; ohne Angabe steht kein Attribut im DOM.
   */
  ariaLabel: { type: String, default: '' },
})
defineEmits(['update:modelValue'])
</script>

<style scoped>
.dk-ui-checkbox {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-2);
  cursor: pointer;
  font-size: var(--fs);
  color: var(--text);
}
.dk-ui-checkbox.is-disabled { opacity: .6; cursor: default; }
.dk-ui-checkbox input {
  width: 16px;
  height: 16px;
  margin: 0;
  accent-color: var(--primary);
  cursor: inherit;
}
.dk-ui-checkbox-label { line-height: 1.4; }
</style>
