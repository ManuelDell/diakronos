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
