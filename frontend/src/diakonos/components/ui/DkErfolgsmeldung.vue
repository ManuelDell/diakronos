<template>
  <!-- UX2d2: Die Region steht IMMER im DOM. Nur ihr Inhalt wechselt (Text beim
       Erfolg, leer sonst) — eine erst beim Erscheinen eingehängte
       `aria-live`-Fläche wird von Screenreadern nicht zuverlässig vorgelesen.
       Vorlesen darf man, was schon da war, als es sich änderte. -->
  <div class="dk-ui-erfolg" role="status" aria-live="polite" aria-atomic="true">{{ text }}</div>
</template>

<script setup>
/**
 * DkErfolgsmeldung — dauerhafte Vorlese-Fläche für kurze Rückmeldungen (UX2d2).
 *
 * Befund (UX2d): Die Erfolgsmeldung hing an einem `v-if`; die Live-Region
 * entstand erst mit dem Text und blieb deshalb stumm.
 *
 * Regel: Kein eigenes Erscheinungsbild des Textes — die sichtbare Erfolgsfläche
 * ist `DkEmpty` (Zustand „erfolg"). Diese Komponente trägt NUR die Vorlese-
 * Region, damit es nicht zwei sichtbare Meldungen gibt.
 */
defineProps({
  /** Der anzusagende Satz; leer = nichts zu sagen (Region bleibt stehen). */
  text: { type: String, default: '' },
})
</script>

<style scoped>
.dk-ui-erfolg {
  /* Sichtbar unsichtbar: die Region nimmt keinen Platz ein, bleibt aber im
     DOM und damit für Vorlesehilfen erreichbar. Maße über die kleinste
     Abstandsstufe, damit hier kein fester Wert steht (Wächter-Test). */
  position: absolute;
  width: var(--sp-1);
  height: var(--sp-1);
  margin: calc(var(--sp-1) * -1);
  padding: 0;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
  border: 0;
}
</style>
