<template>
  <Teleport to="body">
    <div v-if="modelValue" class="dk-modal-overlay" @click.self="onCancel">
      <div
        ref="fenster"
        class="dk-modal dk-warnung-fenster"
        role="dialog"
        aria-modal="true"
        :aria-label="title"
        tabindex="-1"
        @keydown="tastenFaenger"
      >
        <h3 class="dk-warnung-titel">⚠️ {{ title }}</h3>
        <p class="dk-warnung-text">{{ message }}</p>
        <label v-if="sessionKey" class="dk-warnung-session">
          <input type="checkbox" v-model="noMore" />
          In dieser Session nicht mehr warnen
        </label>
        <div class="dk-modal-actions">
          <button class="dk-btn dk-btn-ghost" @click="onCancel">Abbrechen</button>
          <button class="dk-btn dk-btn-warning" @click="onConfirm">{{ confirmLabel }}</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
/**
 * DkWarning — Warnfenster mit Bestaetigung.
 * DES-R6: Fokusfuehrung und Esc-Schliessen wie in DkDialog (useDialogFokus).
 */
import { ref, computed, watch } from 'vue'
import { useDialogFokus } from '../composables/useDialogFokus.js'

const props = defineProps({
  modelValue: Boolean,
  title: String,
  message: String,
  confirmLabel: { type: String, default: 'Trotzdem fortfahren' },
  sessionKey: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue', 'confirm', 'cancel'])

const noMore = ref(false)
const fenster = ref(null)
const offen = computed(() => props.modelValue)

watch(() => props.modelValue, (val) => {
  if (val) noMore.value = false
})

function onCancel() {
  emit('update:modelValue', false)
  emit('cancel')
}

function onConfirm() {
  if (props.sessionKey && noMore.value) {
    sessionStorage.setItem(props.sessionKey, '1')
  }
  emit('update:modelValue', false)
  emit('confirm')
}

// Esc/Abbrechen verwerfen — wie der Abbrechen-Knopf.
const { tastenFaenger } = useDialogFokus(offen, fenster, onCancel)
</script>

<style scoped>
/* DES-02: Die Inline-Angaben dieses Bausteins sind hier zu Klassen geworden. */
.dk-warnung-fenster { max-width: 420px; width: 100%; }
.dk-warnung-titel { color: var(--dk-warning); }
.dk-warnung-text { margin: var(--sp-2) 0 var(--sp-4); font-size: var(--fs); color: var(--dk-text); }
.dk-warnung-session {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  font-size: var(--fs-sm);
  color: var(--dk-text-muted);
  cursor: pointer;
  margin-bottom: var(--sp-4);
}
</style>
