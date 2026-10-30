<template>
  <!-- UX-C3a: Sprungleiste der Abschnitte. Ab 900 px eine senkrechte Liste
       links (bleibt beim Scrollen stehen), darunter eine waagerechte Leiste
       über der Seite. Sie ersetzt kein Menü — sie springt nur. -->
  <nav class="pr-sprung" :aria-label="'Abschnitte'" data-test="pr-pe-sprung">
    <a
      v-for="a in abschnitte"
      :key="a.id"
      class="pr-sprung-punkt"
      :class="{ 'is-aktiv': a.id === aktiv }"
      :href="'#' + zielId(a.id)"
      :aria-current="a.id === aktiv ? 'true' : undefined"
      :data-abschnitt-sprung="a.id"
      @click.prevent="$emit('springen', a.id)"
    >
      <span class="pr-sprung-name">{{ a.name }}</span>
      <span v-if="zahl(a.id) !== null" class="pr-sprung-zahl">{{ zahl(a.id) }}</span>
    </a>
  </nav>
</template>

<script setup>
/**
 * Sprungleiste des Plantyp-Editors (Entwurf C3). Reine Darstellung: die
 * Abschnitte und die aktive Zeile kommen von außen (`abschnitte.mjs`).
 */
import { ABSCHNITTE, zaehler, zielId } from './abschnitte.mjs'

const props = defineProps({
  /** Kennung des Abschnitts, in dem die Lesekante gerade steht. */
  aktiv: { type: String, default: '' },
  /** Die bearbeitete Definition — nur für die Zähler. */
  definition: { type: Object, default: () => ({}) },
})
defineEmits(['springen'])

const abschnitte = ABSCHNITTE

function zahl(id) {
  return zaehler(id, props.definition)
}
</script>

<style scoped>
/* Maße aus den Tokens (--sp-*, --fs-*, --radius). Keine neuen Farbwerte:
   Flächen und Linien kommen aus --dk-surface/--dk-border/--dk-divider. */
.pr-sprung {
  display: flex;
  flex-direction: column;
  gap: 2px;
  position: sticky;
  top: var(--sp-4);
  align-self: start;
}

.pr-sprung-punkt {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-2);
  padding: var(--sp-2) var(--sp-3);
  border-left: 2px solid transparent;
  border-radius: var(--radius);
  font-size: var(--fs);
  color: var(--dk-text-muted);
  text-decoration: none;
  transition: background var(--dk-fast), color var(--dk-fast);
}
.pr-sprung-punkt:hover { background: var(--dk-surface-hover); color: var(--dk-text); }
.pr-sprung-punkt:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 2px; }
.pr-sprung-punkt.is-aktiv {
  color: var(--dk-text);
  font-weight: 600;
  border-left-color: var(--dk-accent);
  background: var(--dk-surface);
}

.pr-sprung-name { min-width: 0; }

/* Zahl neben dem Eintrag — dieselbe Fläche wie .dk-chip-count. */
.pr-sprung-zahl {
  font-size: var(--fs-xs);
  padding: 1px 5px;
  border-radius: var(--badge-r);
  background: var(--dk-surface-2);
  color: var(--dk-text-muted);
}

/* Unter 900 px: waagerechte Leiste, die an der Seite klebt (nicht am
   Fenster — sie soll beim Springen oben bleiben). */
@media (max-width: 900px) {
  .pr-sprung {
    flex-direction: row;
    gap: var(--sp-1);
    position: sticky;
    top: 0;
    z-index: var(--z-sticky);
    padding: var(--sp-2) 0;
    background: var(--dk-bg);
    overflow-x: auto;
    scrollbar-width: thin;
  }
  .pr-sprung-punkt {
    flex: none;
    border: 1px solid var(--dk-border);
    border-left-width: 1px;
    scroll-snap-align: start;
  }
  .pr-sprung-punkt.is-aktiv { border-color: var(--dk-accent); }
}
</style>
