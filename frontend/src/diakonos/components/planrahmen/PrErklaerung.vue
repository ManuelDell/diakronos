<template>
  <!-- UX-C3a: feste Spalte „Was bedeutet das?“ rechts. Ab 1200 px sichtbar,
       darunter ausgeblendet (Entwurf C3 — beide Seitenspalten brauchen
       zusammen ~490 px). Sie ersetzt die Info-Symbole: die Erklärung steht
       dauerhaft neben dem Abschnitt, ohne dass man zielen muss. -->
  <aside class="pr-erklaerung" data-test="pr-pe-erklaerung" :aria-hidden="sichtbar ? undefined : 'true'">
    <div class="pr-erklaerung-titel">Was bedeutet das?</div>
    <dl class="pr-erklaerung-liste">
      <template v-for="e in eintraege" :key="e.id">
        <dt :data-begriff="e.id">{{ e.begriff }}</dt>
        <dd :title="'Doku: ' + e.quelle">{{ e.text }}</dd>
      </template>
    </dl>
    <p class="pr-erklaerung-fuss">
      Diese Spalte erklärt die Begriffe des Abschnitts. Ausführlich steht alles
      im Leitfaden (Pläne › Leitfaden).
    </p>
  </aside>
</template>

<script setup>
/**
 * Erklärspalte des Plantyp-Editors (Entwurf C3). Die Texte stammen aus
 * `abschnitte.mjs` und sind aus LEITFADEN/REFERENZ/GLOSSAR abgeleitet — die
 * Quelle steht im Werkzeugtip jedes Begriffs.
 */
import { computed } from 'vue'
import { erklaerungenFuer } from './abschnitte.mjs'

const props = defineProps({
  /** Abschnitt, dessen Begriffe oben stehen. */
  abschnitt: { type: String, default: '' },
  /** Ab hier (px) ist die Spalte sichtbar (aria-hidden für schmale Fenster). */
  breite: { type: Number, default: 0 },
})

const eintraege = computed(() => erklaerungenFuer(props.abschnitt))
const sichtbar = computed(() => props.breite >= 1200)
</script>

<style scoped>
.pr-erklaerung {
  position: sticky;
  top: var(--sp-4);
  align-self: start;
  padding: var(--sp-4);
  border: 1px solid var(--dk-border);
  border-radius: var(--radius-lg);
  background: var(--dk-surface);
  box-shadow: var(--dk-shadow-xs);
}

.pr-erklaerung-titel {
  font-size: var(--fs-sm);
  font-weight: 650;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--dk-text-subtle);
  margin-bottom: var(--sp-3);
}

.pr-erklaerung-liste {
  margin: 0 0 var(--sp-3);
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}
.pr-erklaerung-liste dt { font-size: var(--fs); font-weight: 600; color: var(--dk-text); }
.pr-erklaerung-liste dd { margin: 2px 0 0; font-size: var(--fs-sm); color: var(--dk-text-muted); line-height: 1.5; }

.pr-erklaerung-fuss {
  margin: 0;
  padding-top: var(--sp-3);
  border-top: 1px solid var(--dk-divider);
  font-size: var(--fs-xs);
  color: var(--dk-text-subtle);
  line-height: 1.5;
}

/* Unter 1200 px entfällt die Spalte (Entwurf C3). Die Regel steht zusätzlich
   im Raster der Seite, damit auch die dritte Spalte verschwindet. */
@media (max-width: 1199px) {
  .pr-erklaerung { display: none; }
}
</style>
