<template>
  <!-- DSGVO-2c: eigene Rückfrage statt `confirm()`.
       Die Löschung ist endgültig — der Dialog sagt das deutlich und verlangt
       das ABTIPPEN des vollständigen Namens. Der Server prüft Rechte und
       Antrag noch einmal; hier wird nur gesammelt und erklärt. -->
  <DkDialog
    :model-value="modelValue"
    title="Löschung freigeben"
    size="sm"
    :close-on-overlay="false"
    :dismissible="!laeuft"
    @update:model-value="schliessen"
  >
    <p class="lf-text">
      <strong>{{ name || 'Diese Person' }}</strong> beantragt die Löschung der
      eigenen Daten. Mit „Löschung freigeben“ wird die Löschung
      <strong>endgültig ausgeführt</strong> — sie lässt sich
      <strong>nicht rückgängig machen</strong>.
    </p>

    <DkHint variant="warn" role="status">
      Die Person bekommt vorher eine E-Mail. Danach werden Name und
      E-Mail-Adresse vollständig entfernt, das Konto wird gelöscht und die
      Sitzungen beendet. In alten Plänen steht danach „Gelöschte Person“.
    </DkHint>

    <DkHint v-if="!mailEingerichtet" variant="err" role="alert">
      Mailversand ist nicht eingerichtet — ohne ihn kann die Löschung nicht
      freigegeben werden.
      <a href="#/einstellungen/mailversand">Mailversand einrichten</a>
    </DkHint>

    <DkField
      :label="`Zur Bestätigung den vollständigen Namen eintippen: „${name}“`"
      :help="'Der Name muss genau so getippt werden — Groß- und Kleinschreibung spielt keine Rolle.'"
      :error="eingabeFalsch ? 'Der Name stimmt noch nicht.' : ''"
    >
      <input
        v-model="eingabe"
        class="dk-ui-eingabe"
        autocomplete="off"
        autocapitalize="words"
        :disabled="laeuft"
        :aria-invalid="eingabeFalsch"
      />
    </DkField>

    <DkHint v-if="fehler" variant="err" role="alert">{{ fehler }}</DkHint>

    <template #footer>
      <DkButton variant="ghost" size="sm" :disabled="laeuft" @click="schliessen(false)">
        Abbrechen
      </DkButton>
      <DkButton
        variant="danger"
        size="sm"
        :disabled="!freigabeVollstaendig({ name, eingabe, laeuft }) || !mailEingerichtet"
        :loading="laeuft"
        @click="freigeben"
      >
        Löschung freigeben
      </DkButton>
    </template>
  </DkDialog>
</template>

<script setup>
/**
 * FreigabeDialog — Rückfrage vor der endgültigen Löschung (DSGVO-2c).
 *
 * Der Dialog ist dumm: er zeigt, wen es trifft, sammelt das abgetippte Wort
 * und meldet `freigeben` nach oben. Die API macht die Seite über
 * `composables/useLoeschantraege.js`; Fehler kommen als Text zurück
 * (`fehler`), damit die Rückfrage bei einem Serverfehler offen bleibt.
 *
 * Ohne eingerichteten Mailversand ist der Knopf gesperrt: der Server würde
 * ohnehin nichts löschen (die Mail geht zwingend vorher raus) — hier wird es
 * gesagt, statt es zu versuchen.
 */
import { computed, ref, watch } from 'vue'
import DkDialog from '../ui/DkDialog.vue'
import DkButton from '../ui/DkButton.vue'
import DkField from '../ui/DkField.vue'
import DkHint from '../ui/DkHint.vue'
import { freigabeVollstaendig } from './loeschantraege.mjs'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  /** Vollständiger Name der Person — auch das Vergleichswort. */
  name: { type: String, default: '' },
  laeuft: { type: Boolean, default: false },
  /** Meldung des Servers, nachdem ein Versuch gescheitert ist. */
  fehler: { type: String, default: '' },
  mailEingerichtet: { type: Boolean, default: true },
})
const emit = defineEmits(['update:modelValue', 'freigeben'])

const eingabe = ref('')
// Erst warnen, wenn etwas getippt wurde — nicht schon beim leeren Feld.
const eingabeFalsch = computed(() => eingabe.value.trim() !== '' && !freigabeVollstaendig({
  name: props.name, eingabe: eingabe.value, laeuft: props.laeuft,
}))

// Jede Öffnung beginnt leer: kein Name aus dem letzten Mal.
watch(() => props.modelValue, (offen) => { if (offen) eingabe.value = '' })

function schliessen(wert = false) {
  if (props.laeuft) return
  emit('update:modelValue', wert === true)
}

function freigeben() {
  if (!freigabeVollstaendig({ name: props.name, eingabe: eingabe.value, laeuft: props.laeuft })) return
  emit('freigeben')
}
</script>

<style scoped>
.lf-text { margin: 0 0 var(--sp-3); color: var(--text); line-height: 1.55; }
.lf-text + .dk-ui-hint { margin-bottom: var(--sp-3); }
</style>
