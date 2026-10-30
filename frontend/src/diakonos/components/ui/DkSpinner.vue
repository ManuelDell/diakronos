<template>
  <!--
    Das Rad bringt seine Regel SELBST mit (siehe <style scoped> unten) —
    DEP-2: die Regel `.dk-spinner` in index.css erreicht nur die Einstiege,
    die index.css laden (diakonos, gast). Organigramm und Registrierung laden
    ausschliesslich tokens.css, dort gab es die Regel nicht und der Ladekreis
    war unsichtbar (Review-Auflage aus DEP-1).
  -->
  <span class="dk-ui-spinner-huelle" role="status" :aria-label="text">
    <span class="dk-ui-spinner-rad" :class="{ 'dk-ui-spinner-rad--sm': klein }" aria-hidden="true"></span>
  </span>
</template>

<script setup>
/**
 * DkSpinner — Ladeanzeige für Flächen, die noch keinen Inhalt haben.
 *
 * DEP-1: Ersatz für `Spinner` aus frappe-ui. Wo der Umriss der Seite schon
 * steht, ist DkSkelett die richtige Wahl (Standard S10); der Spinner ist für
 * kurze, ganzflächige Wartezeiten gedacht (z. B. Organigramm wird geladen).
 *
 * Nur Tokens, keine festen Farben (Wächter-Test).
 */
defineProps({
  /** Vorlese-Text, z. B. „Organigramm wird geladen“. */
  text: { type: String, default: 'Inhalt wird geladen' },
  /** Kleine Ausführung (in Knöpfen/Zeilen). */
  klein: Boolean,
})
</script>

<style scoped>
/* DEP-2: Rad und Farbe stehen hier, nicht mehr in index.css — die Einstiege
   organigramm/registrierung laden nur tokens.css. `currentColor` hält die
   Anzeige in jedem Theme lesbar; keine festen Farben (Wächter-Test). */
.dk-ui-spinner-huelle {
  display: inline-flex;
  align-items: center;
  color: inherit;
}

.dk-ui-spinner-rad {
  display: inline-block;
  width: 13px;
  height: 13px;
  flex-shrink: 0;
  border: 2px solid color-mix(in srgb, currentColor 30%, transparent);
  border-top-color: currentColor;
  border-radius: 50%;
  animation: dk-ui-spinner-dreh 0.7s linear infinite;
}

.dk-ui-spinner-rad--sm {
  width: 11px;
  height: 11px;
  border-width: 2px;
}

@media (prefers-reduced-motion: reduce) {
  .dk-ui-spinner-rad {
    animation-duration: 1.6s;
  }
}

@keyframes dk-ui-spinner-dreh {
  to {
    transform: rotate(360deg);
  }
}
</style>
