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
.dk-dev-start {
  position: fixed;
  right: 10px;
  bottom: 10px;
  z-index: 2147482900;
  display: flex;
  align-items: center;
  gap: 6px;
  font: 12px/1.2 system-ui, sans-serif;
  cursor: pointer;
  border: 1px solid rgba(224, 36, 36, 0.5);
  background: rgba(255, 255, 255, 0.92);
  color: #a01b1b;
  padding: 5px 9px;
  border-radius: 999px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.18);
}
.dk-dev-start-punkt {
  width: 8px; height: 8px; border-radius: 50%; background: #e02424;
}
@media (max-width: 480px) {
  .dk-dev-start { bottom: calc(64px + 8px); }
}
</style>
