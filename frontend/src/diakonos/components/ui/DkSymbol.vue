<template>
  <!-- UX2e · Symbol aus dem Vorrat (symbole.mjs): gleiche Strichfamilie für
       alle Menüeinträge, 24er-Raster, Strichstärke 2, runde Enden. -->
  <svg
    class="dk-ui-symbol"
    :width="groesse"
    :height="groesse"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
    focusable="false"
  >
    <path v-for="(d, i) in form.p || []" :key="'p' + i" :d="d" />
    <circle
      v-for="(c, i) in form.c || []"
      :key="'c' + i"
      :cx="c[0]" :cy="c[1]" :r="c[2]"
    />
  </svg>
</template>

<script setup>
/**
 * DkSymbol — zeichnet ein Symbol aus dem Vorrat (`./symbole.mjs`).
 * Unbekannte oder fehlende Namen zeichnen NICHTS (kein Platzhalterkasten,
 * keine Täuschung); die Node-Tests prüfen die verwendeten Namen gegen den
 * Vorrat.
 */
import { computed } from 'vue'
import { SYMBOLE } from './symbole.mjs'

const props = defineProps({
  name: { type: String, default: '' },
  /** Kantenlänge in px; Standard = Textgröße der Zeile (16 px). */
  groesse: { type: [Number, String], default: 16 },
})

const LEER = { p: [], c: [] }
const form = computed(() => SYMBOLE[props.name] || LEER)
</script>

<style scoped>
.dk-ui-symbol {
  display: block;
  flex: none;
}
</style>
