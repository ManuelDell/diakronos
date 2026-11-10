<template>
  <!-- UX2e · Symbol aus dem Vorrat (symbole.mjs): gleiche Strichfamilie für
       alle Menüeinträge, 24er-Raster, Strichstärke 2, runde Enden. -->
  <svg
    class="dk-ui-symbol"
    :class="{ 'is-gefuellt': gefuellt }"
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
 *
 * `gefuellt` (A11): füllt die Pfade mit der Strichfarbe und stanzt innere
 * Formen aus (`fill-rule: evenodd`). Nötig, wenn zwei geschlossene Formen
 * zusammenspielen und die innere leer bleiben soll — Entwurf A11 will den Ort
 * als Pin mit offener Mitte. Für alle übrigen Symbole bleibt es beim reinen
 * Strich (Vorgabe `false`), damit die Strichfamilie einheitlich bleibt.
 */
import { computed } from 'vue'
import { SYMBOLE } from './symbole.mjs'

const props = defineProps({
  name: { type: String, default: '' },
  /** Kantenlänge in px; Standard = Textgröße der Zeile (16 px). */
  groesse: { type: [Number, String], default: 16 },
  /** Fläche füllen und Innenformen ausstanzen (nur für passende Symbole). */
  gefuellt: { type: Boolean, default: false },
})

const LEER = { p: [], c: [] }
const form = computed(() => SYMBOLE[props.name] || LEER)
</script>

<style scoped>
.dk-ui-symbol {
  display: block;
  flex: none;
}
/* Fläche statt Strich: `evenodd` stanzt die zweite (innere) Form aus. */
.dk-ui-symbol.is-gefuellt {
  fill: currentColor;
  fill-rule: evenodd;
  shape-rendering: geometricPrecision;
}
</style>
