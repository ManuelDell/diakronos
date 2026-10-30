<template>
  <p v-if="text" class="dk-ui-fehlertext" role="alert">{{ text }}</p>
</template>

<script setup>
/**
 * DkFehlertext — Fehlermeldung eines Formulars oder Formularabschnitts.
 *
 * DEP-1: Ersatz für `ErrorMessage` aus frappe-ui. Bewusste Unterschiede:
 *  - Der Text wird als TEXT ausgegeben, nie als HTML (frappe-ui schrieb den
 *    Fehler mit innerHTML ein). Serverfehler sind damit auch dann harmlos,
 *    wenn sie Markup enthalten.
 *  - Zeilenumbrüche bleiben erhalten (white-space: pre-line).
 *  - Die Farbe kommt aus dem Token --err, das mit dem Theme wechselt.
 *
 * Nur Tokens, keine festen Farben (Wächter-Test).
 */
import { computed } from 'vue'

const props = defineProps({
  /** Text, Fehlerobjekt (mit .message) oder null. */
  message: { type: [String, Object], default: '' },
})

const text = computed(() => {
  const m = props.message
  if (!m) return ''
  if (typeof m === 'string') return m
  return m.message || ''
})
</script>

<style scoped>
.dk-ui-fehlertext {
  margin: 0;
  padding: var(--sp-2) var(--sp-3);
  border: 1px solid var(--err);
  border-radius: var(--radius);
  background: color-mix(in oklch, var(--err) 10%, transparent);
  color: var(--err);
  font-size: var(--fs);
  font-weight: 500;
  line-height: 1.45;
  white-space: pre-line;
}
</style>
