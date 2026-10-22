<template>
  <div class="dk-ui-empty">
    <div class="dk-ui-empty-icon" aria-hidden="true">{{ icon }}</div>
    <p class="dk-ui-empty-title">{{ title }}</p>
    <p v-if="text" class="dk-ui-empty-text">{{ text }}</p>
    <div v-if="$slots.aktion || $slots.default" class="dk-ui-empty-aktion">
      <slot name="aktion"><slot /></slot>
    </div>
  </div>
</template>

<script setup>
/**
 * DkEmpty — ruhiger Leerzustand (Stil A): Symbol, Titel, Erklärung, Aktion.
 * Nur Tokens, keine festen Farben.
 */
defineProps({
  title: { type: String, default: 'Nichts vorhanden' },
  text: { type: String, default: '' },
  icon: { type: String, default: '—' },
})
</script>

<style scoped>
.dk-ui-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: var(--sp-2);
  padding: var(--sp-8) var(--sp-6);
}
.dk-ui-empty-icon {
  width: 44px;
  height: 44px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: var(--surface-2);
  color: var(--subtle);
  font-size: 18px;
}
.dk-ui-empty-title { font-size: var(--fs-h4); font-weight: var(--fw-h); margin: 0; color: var(--text); }
.dk-ui-empty-text { font-size: var(--fs); color: var(--muted); margin: 0; max-width: 46ch; line-height: 1.55; }
.dk-ui-empty-aktion { margin-top: var(--sp-2); display: flex; gap: var(--sp-2); flex-wrap: wrap; justify-content: center; }
</style>
