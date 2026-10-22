<template>
  <div class="dk-screen dk-screen-enter">
    <div class="ng-karte">
      <DkEmpty
        icon="🧭"
        title="Seite nicht gefunden"
        :text="`Die Adresse „${angezeigt}“ gibt es nicht (mehr). Vielleicht hilft der Weg zurück zur Übersicht.`"
      />
      <div class="ng-aktionen">
        <DkButton variant="primary" @click="navigate('#/')">Zur Übersicht</DkButton>
        <DkButton variant="secondary" @click="zurueck">Zurück</DkButton>
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * „Seite nicht gefunden“ (OP-UI-6).
 *
 * Unbekannte Adressen landen hier statt still auf der Übersicht. Der Zurück-
 * Knopf nutzt den Browserverlauf; gibt es keinen, führt er zur Übersicht.
 */
import { computed } from 'vue'
import { currentHash, navigate } from '../router.js'
import DkEmpty from '../components/ui/DkEmpty.vue'
import DkButton from '../components/ui/DkButton.vue'

const angezeigt = computed(() => currentHash.value || '#/')

function zurueck() {
  if (window.history.length > 1) window.history.back()
  else navigate('#/')
}
</script>

<style scoped>
.ng-karte {
  max-width: 560px;
  margin: var(--sp-6) auto 0;
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}
.ng-aktionen { display: flex; gap: var(--sp-2); justify-content: center; flex-wrap: wrap; }
</style>
