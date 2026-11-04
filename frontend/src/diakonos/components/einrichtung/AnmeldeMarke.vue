<template>
  <!-- ON-4 (H4, Entwurf 02/03): Marke über dem Formular der Anmeldeseite —
       hinterlegtes Logo, sonst das Monogramm der Gemeinde. Die Adresse kommt
       FERTIG vom Server (Betriebspräfix + `?v=`, ON-2b) und wird hier NICHT
       nachgebaut; das Monogramm ist der erste Buchstabe des Gemeindenamens
       (dieselbe Regel wie überall: `monogramm()`).
       `logo_vorhanden: false` → Monogramm. -->
  <div class="dk-markenseite">
    <img
      v-if="logo"
      :src="logo"
      alt=""
      class="dk-markenseite-bild"
    />
    <span v-else class="dk-monogramm" aria-hidden="true">{{ buchstabe }}</span>
    <p class="dk-marke">Diakronos</p>
  </div>
</template>

<script setup>
/**
 * AnmeldeMarke — Logo/Monogramm auf der Anmeldeseite (ON-4/H4).
 *
 * Logik: `markenDaten()` in `composables/einrichtungsHinweise.mjs` (ein Test
 * deckt die Fälle „Logo da“, „nur Name“, „nichts“ ab). Nur Tokens
 * (`var(--…)`) — die Gestaltung von `.dk-monogramm`/`.dk-marke` steht wie
 * bisher in `frontend/src/ssot/seiten.css` (EINE Quelle für Server-Seiten).
 */
import { computed } from 'vue'

import { markenDaten } from '../../composables/einrichtungsHinweise.mjs'

const props = defineProps({
  gemeinde: { type: Object, default: () => ({}) },
})

const daten = computed(() => markenDaten(props.gemeinde))
const logo = computed(() => daten.value.logo || '')
const buchstabe = computed(() => daten.value.buchstabe || 'D')
</script>

<style scoped>
.dk-markenseite {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--sp-1);
  margin-bottom: var(--sp-5);
}
.dk-markenseite-bild {
  width: calc(var(--sp-6) + var(--sp-2));
  height: calc(var(--sp-6) + var(--sp-2));
  object-fit: contain;
  border-radius: var(--radius-lg);
  background: var(--surface);
}
</style>
