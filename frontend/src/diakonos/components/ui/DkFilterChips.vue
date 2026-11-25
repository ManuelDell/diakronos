<template>
  <div v-if="chips.length" class="dk-ui-chips" :class="{ 'is-scrollbar': scrollbar }" role="group" :aria-label="ariaLabel || undefined">
    <button
      v-for="chip in chips"
      :key="chip.id"
      type="button"
      class="dk-ui-chip"
      :class="{ 'is-active': istGewaehlt(chip) }"
      :aria-pressed="istGewaehlt(chip)"
      @click="$emit('waehlen', naechsterChip(modelValue, chip.id, alleWert))"
    >
      {{ chip.label }}
      <span v-if="mitZahl" class="dk-ui-chip-zahl">{{ chip.anzahl }}</span>
    </button>
  </div>
</template>

<script setup>
/**
 * DkFilterChips — eine Filterzeile als Chips (DES-01, Standard S9).
 *
 * Ersetzt die 28 von Hand gebauten `<button>`-Zeilen. Ein Chip ist eine
 * Umschaltung (`aria-pressed`), ein zweiter Klick auf denselben Chip wählt
 * ihn ab. Alles Darstellerische kommt aus `index.css` (`.dk-ui-chip`), die
 * Zahlen aus `composables/filterChips.mjs`.
 *
 * `chips` = [{ id, label, anzahl }] — der erste Eintrag ist „Alle“.
 */
import { computed } from 'vue'
import { naechsterChip, istAlle } from '../../composables/filterChips.mjs'

const props = defineProps({
  chips: { type: Array, default: () => [] },
  /** Gewählter Wert; leer/'alle' = Ruhezustand. */
  modelValue: { type: String, default: '' },
  /** Wert des „Alle“-Chips. */
  alleWert: { type: String, default: 'alle' },
  /** Zahl am Chip zeigen (bei Zähl-Chips sinnvoll, bei Ja/Nein nicht). */
  mitZahl: { type: Boolean, default: true },
  /** Auf schmalen Anzeigen seitlich scrollbar statt umbrechend. */
  scrollbar: { type: Boolean, default: false },
  ariaLabel: { type: String, default: '' },
})
defineEmits(['waehlen'])

const chips = computed(() => (Array.isArray(props.chips) ? props.chips : []))
function istGewaehlt(chip) {
  return props.modelValue === chip.id || (istAlle(props.modelValue) && chip.id === props.alleWert)
}
</script>

<style scoped>
/* UX-K2 (Nachmessung 25.11.): Die Ansicht-Umschalter der Werkzeugleiste
   („Kachelansicht“/„Listenansicht“, je nur ein Symbol) standen mit 40×44 in
   der Messung — 4 px zu schmal für den Finger. Die Mindestbreite steht hier
   ausdrücklich, weil dieser Stil `scoped` ist (`.dk-ui-chip[data-v-…]`, zwei
   Klassen) und die globale Regel in `index.css` mit einer Klasse verliert —
   dazu kam `--control-h` im 40er-Grundmaß. Nur bei Fingerbedienung; am
   Desktop bleibt der Chip inhaltsbreit. */
@media (pointer: coarse) {
  .dk-ui-chip {
    min-width: var(--treffer-grob);
  }
}
</style>
