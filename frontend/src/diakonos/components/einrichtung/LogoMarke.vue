<template>
  <!-- ON-4 (H4, Entwurf 04/10/11): Marke der Gemeinde in Kopfzeile und
       Seitenleiste. Mit hinterlegtem Logo das Logo, sonst das Monogramm
       („Ohne Logo verwendet Diakronos ein Monogramm.“).
       Bewusst NICHT `<img>` mit fremder Adresse: die Adresse kommt fertig
       (mit Betriebspräfix und `?v=`) aus `gemeinde_get_einstellungen`/`status`
       (ON-2, `logoQuelle`) und wird hier NICHT nachgebaut. Ein SVG im Logo
       läuft nur als Bild — kein Markup (SVG-Schutz aus ON-2). -->
  <span class="dk-logo-marke" :class="'dk-logo-marke--' + size">
    <img v-if="quelle" :src="quelle" alt="" class="dk-logo-marke-bild" />
    <span v-else-if="buchstabe" class="dk-logo-marke-monogramm" aria-hidden="true">{{ buchstabe }}</span>
    <slot v-else name="leer" />
  </span>
</template>

<script setup>
/**
 * LogoMarke — Logo oder Monogramm der Gemeinde (ON-4/H4).
 *
 * Rein darstellend: die ADRESSE kommt von außen (`quelle`, fertig vom Server)
 * und der BUCHSTABE ebenfalls (`buchstabe`, aus `monogramm()` in
 * `composables/einrichtung.mjs`). So gibt es keine zweite Rechnung und keinen
 * nachgebauten Pfad (WEB-5a: Betriebspräfix, ON-2b: `?v=`).
 *
 * `size`: sm (Kopfzeile) | md (Seitenleiste) | lg (Seiten der Ersteinrichtung).
 * Nur Tokens (`var(--…)`) — keine Farb-, Schrift- oder Radius-Zahlen.
 */
defineProps({
  quelle: { type: String, default: '' },
  buchstabe: { type: String, default: '' },
  size: { type: String, default: 'md' },
})
</script>

<style scoped>
.dk-logo-marke {
  display: inline-grid;
  place-items: center;
  flex: none;
  overflow: hidden;
  border-radius: var(--radius-sm);
  background: var(--side-bg);
  color: var(--accent);
  line-height: 1;
  font-weight: var(--fw-h);
}
.dk-logo-marke--sm { width: var(--sp-6); height: var(--sp-6); }
.dk-logo-marke--md { width: var(--sp-8); height: var(--sp-8); }
.dk-logo-marke--lg {
  width: calc(var(--sp-8) + var(--sp-2));
  height: calc(var(--sp-8) + var(--sp-2));
  border-radius: var(--radius-lg);
}
.dk-logo-marke-bild {
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: var(--surface);
}
.dk-logo-marke-monogramm {
  font-size: var(--fs-monogramm);
  letter-spacing: 0;
}
</style>
