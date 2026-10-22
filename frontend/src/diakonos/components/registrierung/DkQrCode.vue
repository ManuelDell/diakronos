<template>
  <!-- Lokal gerechneter QR-Code (qr.mjs). Das Bild ist reines Schwarz/Weiss und
       steht auf weisser Fläche — auf farbigem Untergrund bleibt es damit
       lesbar, ohne Token-Farben zu doppeln. -->
  <div class="dk-qr" :style="{ width: gross + 'px', height: gross + 'px' }">
    <svg
      v-if="bild.pfad"
      :data-qr-svg="text"
      class="dk-qr-svg"
      :viewBox="bild.viewBox"
      shape-rendering="crispEdges"
      role="img"
      :aria-label="'QR-Code für ' + text"
    >
      <rect x="0" y="0" :width="bild.groesse" :height="bild.groesse" fill="var(--surface)" />
      <path :d="bild.pfad" fill="currentColor" />
    </svg>
    <p v-else class="dk-qr-leer">Kein Link vorhanden.</p>
  </div>
</template>

<script setup>
/**
 * DkQrCode — QR-Code eines Textes als SVG, vollständig im Browser gerechnet.
 *
 * Kein fremder Dienst, keine Netzverbindung (Entscheidung 8 „A: kleine
 * Bibliothek in der App“). Die Rechnung selbst steht in `qr.mjs` (dort
 * getestet); diese Komponente ist nur die Darstellung und trägt das
 * `data-qr-svg`-Merkmal, über das der PNG-Export das Bild findet.
 *
 * Farbe: das Muster nimmt `currentColor` (Textfarbe der Umgebung), die Fläche
 * `var(--surface)`. Harte Farbwerte wären sonst Doppelungen der Tokens.
 */
import { computed } from 'vue'
import { qrSvg } from './qr.mjs'

const props = defineProps({
  text: { type: String, default: '' },
  /** Kantenlänge in Pixeln (Anzeige); die Rechnung ist auflösungsunabhängig. */
  gross: { type: Number, default: 220 },
})

const bild = computed(() => qrSvg(props.text))
</script>

<style scoped>
.dk-qr {
  display: grid;
  place-items: center;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  padding: var(--sp-2);
}
.dk-qr-svg { width: 100%; height: 100%; display: block; }
.dk-qr-leer { font-size: var(--fs-xs); color: var(--muted); margin: 0; }
</style>
