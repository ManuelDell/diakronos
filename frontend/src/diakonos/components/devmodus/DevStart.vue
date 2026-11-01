<template>
  <!-- DM1: kleiner Knopf zum EINSCHALTEN des Dev-Modus. Er erscheint NUR,
       wenn der Server den Dev-Modus eingeschaltet hat und der Benutzer
       berechtigt ist, aber noch keine Dev-Sitzung laeuft. -->
  <button class="dk-dev-start" type="button" title="Dev-Modus einschalten"
          data-dk-dev @click="einschalten">
    <span class="dk-dev-start-punkt" aria-hidden="true" />
    Dev-Modus an
  </button>
</template>

<script setup>
import { ref } from 'vue'

import { devmodusApi, devmodusKuerzel, sttVerfuegbar, zustandSetzen } from '../../composables/useDevmodus.js'
import { showToast } from '../../composables/useToast.js'

const laeuft = ref(false)

async function einschalten() {
  if (laeuft.value) return
  laeuft.value = true
  try {
    const daten = await devmodusApi.sitzungStarten()
    zustandSetzen(true, daten?.kuerzel || 'Strg+Shift+F', sttVerfuegbar.value)
    showToast('Dev-Modus an — ' + devmodusKuerzel.value + ' zum Auswählen', 'success')
  } catch {
    showToast('Dev-Modus konnte nicht eingeschaltet werden.', 'error')
  } finally {
    laeuft.value = false
  }
}
</script>

<style scoped>
/* ON-0b: Werte kommen aus tokens.css (--dev-* ist die Werkzeug-Gruppe). */
.dk-dev-start {
  position: fixed;
  right: 10px;
  bottom: 10px;
  z-index: 2147482900;
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: var(--font);
  font-size: var(--fs-sm);
  line-height: 1.2;
  cursor: pointer;
  border: 1px solid var(--dev-flaeche-rand);
  background: var(--dev-flaeche);
  color: var(--dev-rot-ink);
  padding: 5px 9px;
  border-radius: var(--badge-r);
  box-shadow: var(--dev-flaeche-schatten);
}
.dk-dev-start-punkt {
  width: 8px; height: 8px; border-radius: 50%; background: var(--dev-rot);
}
@media (max-width: 480px) {
  .dk-dev-start { bottom: calc(64px + 8px); }
}
</style>
