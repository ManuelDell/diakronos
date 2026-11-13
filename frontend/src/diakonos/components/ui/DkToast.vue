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
 * Meldungsbehälter (Stil aus index.css, Farben aus tokens.css) bleibt die
 * einzige Quelle. Diese Komponente ist ein leerer Anker, damit Seiten sie
 * einbinden können; die eigentliche Funktion liefert `showToast`.
 *
 * UX2a — DREI WEGE, je nach Absicht:
 *
 *  1. Rückmeldung ohne Aktion („Gespeichert“):
 *       import { showToast } from '../../composables/useToast.js'
 *       showToast('Gespeichert', 'success')
 *
 *  2. Meldung mit EINER Aktion („Im Kalender ansehen“):
 *       showToast('Termin angelegt.', 'success',
 *         { text: 'Ansehen', onClick: () => navigate('#/kalender') })
 *
 *  3. Rückgängig nach einer sofort ausgeführten Aktion — IMMER über
 *     `useRueckgaengig` (Stapel, 10 s Frist = `ANZEIGE_MS`, Strg+Z):
 *       import { useRueckgaengig } from '../../composables/useRueckgaengig.js'
 *       const { registrieren } = useRueckgaengig()
 *       registrieren('Aus Gruppe entfernt', async () => {
 *         await apiCall('POST', '/api/…/zuruecknehmen')
 *       })
 *     `registrieren` führt NICHTS aus — die Aktion ist bereits passiert.
 *
 * Barrierefreiheit (vom Meldungsdienst, nicht von der Seite zu erledigen):
 * role=status/alert, aria-live, Esc schließt, Aktionen sind fokussierbar,
 * Strg+Z gilt nur außerhalb von Eingabefeldern.
 */
import { showToast } from '../../composables/useToast.js'

defineExpose({ showToast })
</script>

<style scoped>
.dk-ui-toast-anchor { display: none; }
</style>
