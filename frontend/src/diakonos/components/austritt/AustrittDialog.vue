<template>
  <!-- AUSTRITT A1: eigener Bestätigungsdialog (kein `confirm()`).
       Drei Angaben: wer, Begründung (Pflicht) und Datum. Der Server prueft
       beides noch einmal — hier wird nur gesammelt und erklaert, was passiert. -->
  <DkDialog
    :model-value="modelValue"
    :title="istAustritt ? 'Austritt erfassen' : 'Person reaktivieren'"
    size="sm"
    @update:model-value="schliessen"
  >
    <template v-if="istAustritt">
      <p class="au-text">
        <strong>{{ name || 'Diese Person' }}</strong> verlässt die Gemeinde.
        Das Konto wird deaktiviert, alle Sitzungen werden sofort beendet und
        die Person erscheint nur noch gekürzt („Vorname N.“) in Plänen.
        Es werden <strong>keine Daten gelöscht</strong> — der Austritt lässt
        sich jederzeit zurücknehmen.
      </p>

      <DkField
        label="Begründung (optional)"
        :error="fehlerGrund"
        help="Zum Beispiel „Austritt auf eigenen Wunsch“ oder „Umzug“. Leer lassen ist in Ordnung — der Eintrag gilt auch ohne Begründung als Austritt."
      >
        <textarea
          v-model="grund"
          class="dk-ui-eingabe au-grund"
          rows="3"
          maxlength="500"
          placeholder="Warum tritt die Person aus?"
        ></textarea>
      </DkField>

      <DkField label="Austrittsdatum" :error="fehlerDatum">
        <input v-model="datum" type="date" class="dk-ui-eingabe" />
      </DkField>
    </template>

    <template v-else>
      <p class="au-text">
        <strong>{{ name || 'Diese Person' }}</strong> ist wieder dabei: der
        Status springt auf „{{ zurueckStatus }}“ zurück, das Konto wird wieder
        freigeschaltet und die Anzeige ist wieder vollständig.
      </p>
    </template>

    <template #footer>
      <DkButton variant="ghost" :disabled="laeuft" @click="schliessen(false)">Abbrechen</DkButton>
      <DkButton
        :variant="istAustritt ? 'danger' : 'primary'"
        :loading="laeuft"
        @click="bestaetigen"
      >
        {{ istAustritt ? 'Austritt erfassen' : 'Reaktivieren' }}
      </DkButton>
    </template>
  </DkDialog>
</template>

<script setup>
/**
 * AustrittDialog — Bestaetigung fuer „Austritt / Deaktivieren“ (A1) und
 * „Reaktivieren“ (A4).
 *
 * Der Dialog fragt NICHTS nach, was der Server ohnehin verweigert: er ist nur
 * dann erreichbar, wenn der Server das Recht dazu gemeldet hat
 * (`permissions`/`austritt` der Detail-Antwort).
 *
 * `art`: 'austritt' (Person austragen) oder 'reaktivieren'.
 */
import { computed, ref, watch } from 'vue'
import DkDialog from '../ui/DkDialog.vue'
import DkButton from '../ui/DkButton.vue'
import DkField from '../ui/DkField.vue'
import { heute } from '../../composables/useAustritt.js'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  art: { type: String, default: 'austritt' },
  name: { type: String, default: '' },
  zurueckStatus: { type: String, default: 'Mitglied' },
  laeuft: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue', 'austritt', 'reaktivieren'])

const istAustritt = computed(() => props.art !== 'reaktivieren')
const grund = ref('')
const datum = ref(heute())
const fehlerGrund = ref('')
const fehlerDatum = ref('')

// Bei jedem Oeffnen frisch: keine alte Begruendung aus dem letzten Mal.
watch(() => props.modelValue, (offen) => {
  if (!offen) return
  grund.value = ''
  datum.value = heute()
  fehlerGrund.value = ''
  fehlerDatum.value = ''
})

function schliessen(wert = false) {
  if (props.laeuft) return
  emit('update:modelValue', wert === true)
}

function bestaetigen() {
  fehlerGrund.value = ''
  fehlerDatum.value = ''
  if (!istAustritt.value) {
    emit('reaktivieren')
    return
  }
  const text = (grund.value || '').trim()
  if (datum.value && !/^\d{4}-\d{2}-\d{2}$/.test(datum.value)) {
    fehlerDatum.value = 'Bitte ein Datum wählen.'
    return
  }
  emit('austritt', { begruendung: text, datum: datum.value })
}
</script>

<style scoped>
.au-text { margin: 0 0 var(--sp-3); color: var(--text); line-height: 1.5; }
.au-grund { width: 100%; resize: vertical; }
.au-text + .dk-ui-field { margin-bottom: var(--sp-3); }
</style>
