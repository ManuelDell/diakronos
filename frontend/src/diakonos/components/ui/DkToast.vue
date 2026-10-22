<template>
  <!-- Kein eigenes DOM: Meldungen laufen über das bestehende useToast
       (globaler Behälter im <body>). Diese Hülle macht den Baustein nur
       als Komponente benutzbar und dokumentiert den Zugang. -->
  <span class="dk-ui-toast-anchor" hidden aria-hidden="true"></span>
</template>

<script setup>
/**
 * DkToast — dünne Hülle um das bestehende useToast (composables/useToast.js).
 *
 * Die Bibliothek rendert keine eigenen Meldungen: der bestehende globale
 * Toast-Behälter (Stil aus index.css, Farben aus tokens.css) bleibt die
 * einzige Quelle. Diese Komponente ist ein leerer Anker, damit Seiten sie
 * einbinden können; die eigentliche Funktion liefert `showToast`.
 *
 * Verwendung in Seiten:
 *   import { showToast } from '../../composables/useToast.js'
 *   showToast('Gespeichert', 'success')
 */
import { showToast } from '../../composables/useToast.js'

defineExpose({ showToast })
</script>

<style scoped>
.dk-ui-toast-anchor { display: none; }
</style>
