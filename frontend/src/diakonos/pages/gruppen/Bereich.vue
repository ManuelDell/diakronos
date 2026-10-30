<template>
  <div class="bereich dk-screen dk-screen-wide dk-screen-enter">
    <!-- DEV-1 (Befund DMB-7bc7150a146e): „Neue Gruppe/Untergruppe“ gehörte
         bisher nur zur Liste ohne Rahmen (Gruppen.vue, `v-if="!embedded"`). Im
         Bereich war Anlegen damit nur über die Ansicht Organigramm möglich.
         Die Aktion sitzt deshalb hier im Seitenkopf — mit denselben Rechten
         (der Server entscheidet über `can_create_*`) und demselben Dialog wie
         im Organigramm. -->
    <DkPageHeader title="Gruppen" sub="Übersicht aller Dienstbereiche, Gruppen und Untergruppen.">
      <template #actions>
        <template v-if="rechte.canCreateAny">
          <DkButton v-if="rechte.canCreateGruppe" variant="primary" @click="openCreate('gruppe')">
            + Neue Gruppe
          </DkButton>
          <DkButton v-if="rechte.canCreateUntergruppe" variant="secondary" @click="openCreate('untergruppe')">
            + Neue Untergruppe
          </DkButton>
        </template>
      </template>
    </DkPageHeader>

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

    <component :is="inhalt" ref="inhaltRef" embedded />

    <!-- Derselbe Anlege-Dialog wie in der Liste (components/gruppen). -->
    <GruppeAnlegenDialog
      v-model="showCreate"
      :typ="createTyp"
      :dienstbereiche="dienstbereiche"
      :gruppen="gruppenAuswahl"
      @angelegt="nachAnlegen"
    />
  </div>
</template>

<script setup>
/**
 * Gruppen-Bereich — schaltet zwischen der Liste und dem Organigramm um.
 * Der Umschalter wandert in die Adresse, damit Lesezeichen und der
 * Zurück-Knopf funktionieren (#/gruppen und #/gruppen/organigramm).
 *
 * DEV-1: Der Seitenkopf trägt zusätzlich die Anlege-Aktion. Weil der Kopf dem
 * Rahmen gehört, holt dieser die Rechte und die Auswahllisten selbst — vorher
 * hatte die eingebettete Liste sie, im Organigramm kam zusätzlich
 * `get_user_create_permissions` dazu.
 */
import { ref, computed, onMounted, defineAsyncComponent } from 'vue'
import { currentHash, navigate } from '../../router.js'
import { apiCall } from '../../composables/useApi.js'
import { anlegenRechte } from '../../composables/gruppenAnlegen.mjs'
import DkPageHeader from '../../components/ui/DkPageHeader.vue'
import DkButton from '../../components/ui/DkButton.vue'
import DkSegment from '../../components/ui/DkSegment.vue'
import GruppeAnlegenDialog from '../../components/gruppen/GruppeAnlegenDialog.vue'

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

// ── Anlegen (DEV-1) ────────────────────────────────────────────────────────
const inhaltRef = ref(null)
const showCreate = ref(false)
const createTyp = ref('gruppe')
const rechte = ref({ canCreateAny: false, canCreateGruppe: false, canCreateUntergruppe: false, canCreateDienstbereich: false })
const dienstbereiche = ref([])
const gruppenAuswahl = ref([])

function openCreate(typ) {
  createTyp.value = typ
  showCreate.value = true
}

/** Nach dem Anlegen die sichtbare Ansicht neu laden (Liste hält die Daten). */
function nachAnlegen() {
  inhaltRef.value?.reload?.()
}

async function ladeRechte() {
  try {
    // Eine Quelle für Rechte UND Auswahllisten (B5/OP-ADMIN-6 liefert beides).
    const [permsRoh, seite] = await Promise.all([
      apiCall('diakronos.diakonos.api.gruppen.get_user_create_permissions'),
      apiCall('diakronos.diakonos.api.gruppen.get_gruppen_page_data'),
    ])
    rechte.value = anlegenRechte(permsRoh || seite?.create_permissions)
    dienstbereiche.value = seite?.dienstbereich_auswahl || []
    gruppenAuswahl.value = seite?.gruppen_auswahl || []
  } catch (err) {
    // Ohne Rechte keine Knöpfe (fail closed) — die Liste selbst lädt weiter.
    console.error('Anlege-Rechte konnten nicht geladen werden:', err)
  }
}

onMounted(ladeRechte)
</script>

<style scoped>
.gr-ansicht { margin: var(--sp-3) 0; }
/* Die eingebetteten Seiten bringen ihren eigenen .dk-screen mit; hier liegt
   der Rahmen schon in einem, deshalb innen Abstand und Breite aufheben. */
.bereich :deep(.dk-screen) { max-width: none; padding: 0; margin: 0; }
</style>
