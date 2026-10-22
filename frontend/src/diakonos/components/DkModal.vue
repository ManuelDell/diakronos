<template>
  <Teleport to="body">
    <div v-if="modelValue" class="dk-modal-overlay">
      <div
        ref="fenster"
        class="dk-modal"
        :class="{ 'dk-modal--planrahmen': variant === 'planrahmen' }"
        role="dialog"
        aria-modal="true"
        :aria-label="title"
        tabindex="-1"
        @keydown="tastenFaenger"
      >
        <h3 v-if="title">{{ title }}</h3>
        <slot />
        <div v-if="$slots.footer" class="dk-modal-actions" :class="{ 'dk-modal-actions--sticky': footerSticky }">
          <slot name="footer" />
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
/**
 * DkModal — schlankes modales Fenster.
 *
 * DES-R6: Fokusfuehrung und Esc-Schliessen wie in DkDialog (ueber
 * useDialogFokus). Vorher blieb der Fokus auf dem Auslöser hinter dem
 * Fenster stehen und Esc schloss nicht.
 */
import { ref, computed } from 'vue'
import { useDialogFokus } from '../composables/useDialogFokus.js'
import { useZurueckSchliesst } from '../composables/useZurueckSchliesst.js'

const props = defineProps({
  modelValue: Boolean,
  beforeClose: { type: Function, default: null },
  title: String,
  variant: { type: String, default: '' },
  // UXP-R11: Fusszeile am unteren Rand des Dialogfelds festhalten, damit
  // „Übernehmen“/„Abbrechen“ auch bei langem Inhalt ohne Scrollen erreichbar
  // ist (im Plan-Dialog lagen die Knoepfe ~2500 px unter dem Inhalt).
  footerSticky: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])

const fenster = ref(null)
const offen = computed(() => props.modelValue)

/**
 * Schließen. Liefert `true`, wenn tatsächlich geschlossen wurde, `false`, wenn
 * `beforeClose` abgelehnt hat (P3-4, Restpunkt 11: `useZurueckSchliesst` legt
 * dann den verbrauchten History-Eintrag neu an).
 */
async function close() {
  if (props.beforeClose && !(await props.beforeClose())) return false
  emit('update:modelValue', false)
  return true
}

const { tastenFaenger } = useDialogFokus(offen, fenster, close)
// OP-HANDY-7: Zurück-Taste/-Geste schließt das Fenster (vorher verließ sie
// die Seite — z. B. bei der Ressourcen-Buchung).
useZurueckSchliesst(offen, close)
</script>

<style scoped>
.dk-modal--planrahmen { max-width: 760px; max-height: calc(100dvh - 32px); overflow: auto; }
</style>
