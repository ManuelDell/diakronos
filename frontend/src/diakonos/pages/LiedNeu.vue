<template>
  <div class="dk-screen dk-screen-enter">
    <DkPageHeader
      title="Neues Lied"
      sub="Einmal ausfüllen — das Lied steht danach in der Liste und in allen Plänen."
      :krumen="[{ text: 'Lieder', href: '#/lieder' }, { text: 'Neues Lied' }]"
    />

    <div v-if="!darfSchreiben && geprueft" class="ln-gesperrt">
      <DkEmpty
        title="Kein Zugriff"
        :text="rechteHinweis || 'Für das Anlegen von Liedern fehlt dir die Berechtigung.'"
        icon="🔒"
      >
        <template #aktion>
          <DkButton variant="secondary" @click="zurueck">Zur Liederliste</DkButton>
        </template>
      </DkEmpty>
    </div>

    <LiedBearbeiten
      v-else
      :plantyp="plantyp"
      :plan="plan"
      :definition="definition"
      @gespeichert="nachSpeichern"
      @verlassen="zurueck"
    />
  </div>
</template>

<script setup>
/**
 * LI1 — „Neues Lied“: dieselbe Bearbeiten-Komponente, nur leer.
 * Nach dem Anlegen geht es direkt ins Lied-Detail (die Komponente navigiert).
 *
 * Das Schreibrecht kommt vom Server. Hier wird zusätzlich die ganze Seite
 * freundlich verweigert, falls jemand den Pfad #/lieder/neu direkt aufruft:
 * die Komponente selbst fragt dasselbe Recht ab.
 */
import { ref, onMounted } from 'vue'
import { apiCall } from '../composables/useApi.js'
import { navigate } from '../router.js'
import DkPageHeader from '../components/ui/DkPageHeader.vue'
import DkEmpty from '../components/ui/DkEmpty.vue'
import DkButton from '../components/ui/DkButton.vue'
import LiedBearbeiten from '../components/lieder/LiedBearbeiten.vue'

const props = defineProps({
  /** Optionaler Plantyp-Kontext (Plan-Stammdaten) — sonst freie Anlage. */
  plantyp: { type: String, default: '' },
  plan: { type: String, default: null },
  definition: { type: Object, default: null },
})

const darfSchreiben = ref(false)
const rechteHinweis = ref('')
const geprueft = ref(false)

onMounted(async () => {
  try {
    const erg = await apiCall('diakronos.planrahmen.api.lied_rechte', {
      plantyp: props.plantyp || null, plan: props.plan || null,
    })
    darfSchreiben.value = !!erg?.darf_schreiben
    rechteHinweis.value = erg?.hinweis || ''
  } catch (e) {
    darfSchreiben.value = false
  } finally {
    geprueft.value = true
  }
})

function zurueck() {
  navigate('#/lieder')
}

/** Die Komponente plant den Rückweg (Lied-Detail); hier nur die Rückmeldung. */
function nachSpeichern() {
  /* nichts weiter: der Nutzer landet im Lied-Detail */
}
</script>

<style scoped>
.ln-gesperrt { margin-top: var(--sp-4); }
</style>
