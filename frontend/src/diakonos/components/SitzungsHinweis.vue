<template>
  <DkDialog vorrang v-if="sitzungAbgelaufen" :model-value="true" :dismissible="false" title="Deine Anmeldung ist abgelaufen" size="sm">
    <p>Deine Eingaben bleiben in diesem Tab erhalten. Melde dich in einem neuen Tab mit demselben Konto an und kehre dann hierher zurück.</p>
    <p v-if="sitzungsHinweis" role="alert">{{ sitzungsHinweis }}</p>
    <template #footer>
      <a :href="anmeldeAdresse()" target="_blank" rel="noopener" class="dk-btn dk-btn-secondary">Neu anmelden</a>
      <DkButton :loading="prueft" @click="fortsetzen">Weiterarbeiten</DkButton>
    </template>
  </DkDialog>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import DkDialog from './ui/DkDialog.vue'
import DkButton from './ui/DkButton.vue'
import {
  sitzungAbgelaufen, sitzungsHinweis, anmeldeAdresse, sitzungFortsetzen,
  sitzungsEndeUebernehmen, sitzungsEndeBeobachten,
} from '../composables/useSitzungsablauf.js'
const prueft = ref(false)

// WEB-8c (R4): Ein im Hauptbereich aufgedecktes Sitzungsende muss hier
// sichtbar werden — auch wenn es NICHT über `sitzungBeendet()` kam
// (CSRF-Heilung). `sitzungEndeUebernehmen()` öffnet den Dialog selbst.
watch(
  () => sitzungAbgelaufen.value,
  (offen) => { if (!offen) sitzungsEndeUebernehmen() },
  { immediate: true },
)

// WEB-8d (M2): Früher fragte ein `setInterval(…, 250)` den Stand 4x je
// Sekunde ab. Jetzt ist der Stand ein `shallowRef` und dieser Aufbau HÖRT
// darauf (`sitzungsEndeBeobachten` → `watch`): die Meldung kommt sofort bei
// der Änderung, ohne Takt und ohne Arbeit im Leerlauf. Die Beobachtung wird
// beim Abbau der Anzeige gelöst.
let abmelden = null
onMounted(() => { abmelden = sitzungsEndeBeobachten(() => { sitzungsEndeUebernehmen() }) })
onUnmounted(() => { if (abmelden) { abmelden(); abmelden = null } })

async function fortsetzen() {
  if (prueft.value) return
  prueft.value = true
  try { await sitzungFortsetzen() } finally { prueft.value = false }
}
</script>
