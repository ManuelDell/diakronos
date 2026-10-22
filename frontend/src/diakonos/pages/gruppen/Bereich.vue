<template>
  <div class="bereich dk-screen dk-screen-wide dk-screen-enter">
    <DkPageHeader title="Gruppen" sub="Übersicht aller Dienstbereiche, Gruppen und Untergruppen." />

    <!-- Umschalter Liste / Organigramm (Entscheidung 9: das Organigramm ist
         eine Ansicht in „Gruppen“, kein eigener Menüpunkt mehr). -->
    <DkSegment
      v-model="ansicht"
      class="gr-ansicht"
      :options="[
        { value: 'liste', label: 'Liste' },
        { value: 'organigramm', label: 'Organigramm' },
      ]"
      aria-label="Ansicht"
    />

    <component :is="inhalt" embedded />
  </div>
</template>

<script setup>
/**
 * Gruppen-Bereich — schaltet zwischen der Liste und dem Organigramm um.
 * Der Umschalter wandert in die Adresse, damit Lesezeichen und der
 * Zurück-Knopf funktionieren (#/gruppen und #/gruppen/organigramm).
 */
import { computed, defineAsyncComponent } from 'vue'
import { currentHash, navigate } from '../../router.js'
import DkPageHeader from '../../components/ui/DkPageHeader.vue'
import DkSegment from '../../components/ui/DkSegment.vue'

const LISTE       = defineAsyncComponent(() => import('../Gruppen.vue'))
// N13: das Organigramm ist die zweite Ansicht der Gruppenseite; die frühere
// eigene Seite pages/Organigramm.vue ist entfallen, der Baum lebt als
// Komponente components/gruppen/OrganigrammAnsicht.vue weiter.
const ORGANIGRAMM = defineAsyncComponent(() => import('../../components/gruppen/OrganigrammAnsicht.vue'))

const ansicht = computed({
  get: () => ansichtAusHash(currentHash.value),
  set: (wert) => navigate(wert === 'organigramm' ? '#/gruppen/organigramm' : '#/gruppen'),
})

/**
 * N13: die angezeigte Ansicht ergibt sich aus der Adresse. Abfrageteil hinter
 * '?' abschneiden und einen Schlussslash tolerieren; das fuehrende '#' gehoert
 * zur Adresse und bleibt stehen.
 */
function ansichtAusHash(hash) {
  const pfad = String(hash || '').split('?')[0].replace(/\/+$/, '')
  return pfad === '#/gruppen/organigramm' ? 'organigramm' : 'liste'
}

const inhalt = computed(() => (ansicht.value === 'organigramm' ? ORGANIGRAMM : LISTE))
</script>

<style scoped>
.gr-ansicht { margin: var(--sp-3) 0; }
/* Die eingebetteten Seiten bringen ihren eigenen .dk-screen mit; hier liegt
   der Rahmen schon in einem, deshalb innen Abstand und Breite aufheben. */
.bereich :deep(.dk-screen) { max-width: none; padding: 0; margin: 0; }
</style>
