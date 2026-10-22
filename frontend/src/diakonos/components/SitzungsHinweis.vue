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
import { ref } from 'vue'
import DkDialog from './ui/DkDialog.vue'
import DkButton from './ui/DkButton.vue'
import { sitzungAbgelaufen, sitzungsHinweis, anmeldeAdresse, sitzungFortsetzen } from '../composables/useSitzungsablauf.js'
const prueft = ref(false)
async function fortsetzen() {
  if (prueft.value) return
  prueft.value = true
  try { await sitzungFortsetzen() } finally { prueft.value = false }
}
</script>
