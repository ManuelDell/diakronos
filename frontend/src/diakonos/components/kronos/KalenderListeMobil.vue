<template>
  <!-- A10 (Entwurf „A10 Mobil Kalender"): die Listen-Ansicht — kompakter
       Monat mit Punkten, darunter die Termine des gewählten Tages. Der
       „Woche ›“-Link der Tagesliste führt in die Wochenansicht (derselbe
       Zustand, anderer Blick — kein Seitenwechsel). -->
  <div class="kal-a10-liste">
    <KalenderMiniMonat
      :monat="monat"
      :gewaehlt="gewaehlterTag"
      :termine="termine"
      :pruef-ids="pruefIds"
      :farbe="kalenderFarbe"
      @tagWechsel="(tag) => $emit('tagWechsel', tag)"
      @heute="$emit('heute')"
      @zurueck="$emit('zurueck')"
      @vor="$emit('vor')"
      @spanne="(spanne) => $emit('spanne', spanne)"
    />
    <KalenderTagesliste
      :termine="termine"
      :tag="gewaehlterTag"
      :lesemodus="lesemodus"
      @terminOeffnen="(t) => $emit('terminOeffnen', t)"
      @terminAktion="(e) => $emit('terminAktion', e)"
      @woche="$emit('woche')"
    />
  </div>
</template>

<script setup>
/**
 * KalenderListeMobil — die A10-Listen-Ansicht (Mini-Monat + Tagesliste).
 *
 * Reine Zusammenstellung zweier Bauteile; alle Daten und Handlungen kommen
 * von der Seite. Getrennt von `pages/Kalender.vue`, damit dieselbe Ansicht
 * auch im Widget/Test ohne die ganze Seite steht.
 */
import KalenderMiniMonat from './KalenderMiniMonat.vue'
import KalenderTagesliste from './KalenderTagesliste.vue'

defineProps({
  monat: { type: String, required: true },
  gewaehlterTag: { type: String, required: true },
  termine: { type: Array, default: () => [] },
  pruefIds: { type: Array, default: () => [] },
  kalenderFarbe: { type: String, default: '' },
  lesemodus: { type: Boolean, default: true },
})

defineEmits(['tagWechsel', 'heute', 'terminOeffnen', 'terminAktion', 'woche', 'spanne', 'zurueck', 'vor'])
</script>

<style scoped>
.kal-a10-liste {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
  padding: var(--sp-3) var(--sp-2);
}
</style>
