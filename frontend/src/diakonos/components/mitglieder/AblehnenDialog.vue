<template>
  <!-- DSGVO-2c: Ablehnen mit Pflicht-Begründung (kein `confirm()`).
       Die Begründung geht im Wortlaut per E-Mail an die Person und steht
       danach in ihrem Profil — der Dialog sagt das, damit niemand eine
       interne Notiz hineinschreibt. -->
  <DkDialog
    :model-value="modelValue"
    title="Löschantrag ablehnen"
    size="sm"
    :close-on-overlay="false"
    :dismissible="!laeuft"
    @update:model-value="schliessen"
  >
    <p class="la-text">
      Du lehnst den Löschantrag von <strong>{{ name || 'dieser Person' }}</strong> ab.
      Es wird <strong>nichts gelöscht</strong>: die Person behält alle Daten und
      kann jederzeit einen neuen Antrag stellen.
    </p>

    <DkHint variant="info" role="status">
      Die Begründung bekommt die Person per E-Mail und sieht sie in ihrem Profil.
      Bitte verständlich schreiben und nichts Internes hineinschreiben — sie ist
      keine Aktennotiz.
    </DkHint>

    <DkHint v-if="!mailEingerichtet" variant="err" role="alert">
      Mailversand ist nicht eingerichtet — ohne ihn kann der Antrag nicht
      abgelehnt werden.
      <a href="#/einstellungen/mailversand">Mailversand einrichten</a>
    </DkHint>

    <DkField
      label="Begründung"
      required
      :error="grundFehler"
      :help="`${laenge} von ${BEGRUENDUNG_MAX} Zeichen`"
    >
      <textarea
        v-model="begruendung"
        class="dk-ui-eingabe la-grund"
        rows="4"
        :maxlength="BEGRUENDUNG_MAX"
        :disabled="laeuft"
        placeholder="Warum wird der Antrag abgelehnt?"
      ></textarea>
    </DkField>

    <DkHint v-if="fehler" variant="err" role="alert">{{ fehler }}</DkHint>

    <template #footer>
      <DkButton variant="ghost" size="sm" :disabled="laeuft" @click="schliessen(false)">
        Abbrechen
      </DkButton>
      <DkButton
        variant="danger"
        size="sm"
        :disabled="laeuft || !mailEingerichtet"
        :loading="laeuft"
        @click="ablehnen"
      >
        Antrag ablehnen
      </DkButton>
    </template>
  </DkDialog>
</template>

<script setup>
/**
 * AblehnenDialog — Löschantrag mit Begründung ablehnen (DSGVO-2c).
 *
 * Wie `FreigabeDialog` ist der Dialog dumm: er sammelt die Begründung und
 * meldet `ablehnen` mit dem Text nach oben. Die Prüfung (Pflicht, Länge,
 * Steuerzeichen) steht in `loeschantraege.mjs` — dieselben Grenzen wie im
 * Server (`_pruefe_begruendung`), nur früher gesagt.
 *
 * Ohne eingerichteten Mailversand ist der Knopf gesperrt: die Person MUSS die
 * Begründung erhalten (fail closed, wie beim Freigeben).
 */
import { computed, ref, watch } from 'vue'
import DkDialog from '../ui/DkDialog.vue'
import DkButton from '../ui/DkButton.vue'
import DkField from '../ui/DkField.vue'
import DkHint from '../ui/DkHint.vue'
import { BEGRUENDUNG_MAX, begruendungFehler } from './loeschantraege.mjs'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  name: { type: String, default: '' },
  laeuft: { type: Boolean, default: false },
  fehler: { type: String, default: '' },
  mailEingerichtet: { type: Boolean, default: true },
})
const emit = defineEmits(['update:modelValue', 'ablehnen'])

const begruendung = ref('')
// Erst nach dem ersten Versuch meckern — nicht schon beim leeren Feld.
const versucht = ref(false)

const laenge = computed(() => begruendung.value.replace(/\r\n?/g, '\n').trim().length)
const grundFehler = computed(() => (versucht.value ? begruendungFehler(begruendung.value) : ''))

watch(() => props.modelValue, (offen) => {
  if (!offen) return
  begruendung.value = ''
  versucht.value = false
})

function schliessen(wert = false) {
  if (props.laeuft) return
  emit('update:modelValue', wert === true)
}

function ablehnen() {
  if (props.laeuft) return
  versucht.value = true
  if (begruendungFehler(begruendung.value)) return
  emit('ablehnen', begruendung.value.replace(/\r\n?/g, '\n').trim())
}
</script>

<style scoped>
.la-text { margin: 0 0 var(--sp-3); color: var(--text); line-height: 1.55; }
.la-grund { width: 100%; resize: vertical; }
.dk-ui-hint + .dk-ui-field { margin-top: var(--sp-3); }
</style>
