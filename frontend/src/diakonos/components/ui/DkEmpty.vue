<template>
  <div class="dk-ui-empty">
    <div class="dk-ui-empty-icon" aria-hidden="true">{{ icon }}</div>
    <p class="dk-ui-empty-title">{{ title }}</p>
    <p v-if="text" class="dk-ui-empty-text">{{ text }}</p>
    <!-- UX2d2: „Erneut versuchen“ ist eine HANDLUNG dieser Fläche, kein Satz.
         Der Knopf kommt vom gemeinsamen Knopf-System (DkButton, secondary) —
         genau ein gefüllter Knopf je Ansicht bleibt gewahrt. Ist kein Handler
         angeschlossen, steht kein Knopf da (keine tote Klickfläche). -->
    <div v-if="erneutVersuchen" class="dk-ui-empty-aktion">
      <DkButton variant="secondary" @click="erneutVersuchen">Erneut versuchen</DkButton>
    </div>
    <div v-if="$slots.aktion || $slots.default" class="dk-ui-empty-aktion">
      <slot name="aktion"><slot /></slot>
    </div>
  </div>
</template>

<script setup>
/**
 * DkEmpty — ruhiger Leerzustand (Stil A): Symbol, Titel, Erklärung, Aktion.
 * Nur Tokens, keine festen Farben.
 *
 * UX2d2: `erneutVersuchen` ist der Handler für eine Fläche, die nicht geladen
 * werden konnte. Die Seite reicht ihn durch — dieser Baustein baut den Knopf
 * dazu. Vorher blieb die Aufforderung ein nackter Text ohne Ziel.
 */
import DkButton from './DkButton.vue'

defineProps({
  title: { type: String, default: 'Nichts vorhanden' },
  text: { type: String, default: '' },
  icon: { type: String, default: '—' },
  /** Handler für „Erneut versuchen"; ohne Handler entfällt der Knopf. */
  erneutVersuchen: { type: Function, default: null },
})
</script>

<style scoped>
.dk-ui-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: var(--sp-2);
  padding: var(--sp-6) var(--sp-5);
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
