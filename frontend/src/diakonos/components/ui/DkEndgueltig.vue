<template>
  <!--
    C1 (UX2c) — der EINE Dialog für Unumkehrbares (Entwurf B1, „Endgültig-Dialog“).

    Regel I2: Rückfrage NUR für Unumkehrbares. Ist sie nötig, dann so:
      · Titel als Frage                     („Person anonymisieren?“)
      · konkrete Folge im Fließtext          (was genau verschwindet, was bleibt)
      · beim Schwersten: Namenseingabe       (`bestaetigungswort`)
      · gefährlicher Knopf am Ende           (danger), Ausstieg links daneben

    Der Baustein sammelt und prüft die Eingabe — die Aktion macht die Seite.
    Bleibt der Serveraufruf nötig, meldet die Seite `laeuft` und `fehler`; der
    Dialog bleibt dann offen und die Eingabe steht noch da (Prinzip I4).

    Barrierefreiheit (Review 06.11.): `role="dialog"` am Rahmen trägt
    `aria-label` = Titel; der Folgetext (= das, was der Nutzer wissen MUSS)
    hängt über `aria-describedby` daran. Ohne Bezug hörte die Sprachausgabe
    nur die Frage und nicht die Folge.

    UX2c-N2: Der Bezug steht am Dialog-ELEMENT (`role="dialog"`), nicht an
    einem rollenlosen <div> im Körper — dort wird er nicht gelesen (Befund
    Re-Review). Dafür reicht `DkEndgueltig` die Kennung als `beschrieben` an
    `DkDialog` weiter.
  -->
  <DkDialog
    :model-value="modelValue"
    :title="titel"
    size="sm"
    :close-on-overlay="false"
    :dismissible="!laeuft"
    :beschrieben="beschrieben ? textId : ''"
    @update:model-value="schliessen"
  >
    <div>
      <p v-if="text" :id="textId" class="dk-endgueltig-text">{{ text }}</p>

      <DkHint v-if="warnung" variant="warn" role="status">{{ warnung }}</DkHint>

      <DkField
        v-if="bestaetigungswort"
        :label="`Zur Bestätigung „${bestaetigungswort}“ eingeben`"
        :error="wortFalsch ? 'Die Eingabe stimmt noch nicht.' : ''"
        help="Genau so schreiben; Groß- und Kleinschreibung spielt keine Rolle."
      >
        <input
          ref="wortFeld"
          v-model="eingabe"
          class="dk-ui-eingabe"
          autocomplete="off"
          autocapitalize="none"
          spellcheck="false"
          :disabled="laeuft"
          :aria-invalid="wortFalsch"
          :aria-describedby="beschrieben ? textId : undefined"
        />
      </DkField>

      <slot />
    </div>

    <DkHint v-if="fehler" variant="err" role="alert">{{ fehler }}</DkHint>

    <template #footer>
      <DkButton variant="ghost" :disabled="laeuft" @click="schliessen(false)">
        {{ abbrechen }}
      </DkButton>
      <DkButton
        variant="danger"
        :disabled="!bereit"
        :loading="laeuft"
        @click="bestaetigen"
      >
        {{ aktion }}
      </DkButton>
    </template>
  </DkDialog>
</template>

<script setup>
/**
 * DkEndgueltig — Rückfrage für eine unumkehrbare Aktion (UX2c, C1).
 *
 * Ersetzt die eigenen „Wirklich löschen?“-Dialoge, die entweder gar keine
 * Folge nannten oder das Wort „endgültig“ nur behaupteten. Er ist dumm: er
 * kennt den Text, das Bestätigungswort und ob es gerade läuft — nicht die API.
 *
 * Warum ein eigener Baustein neben `bestaetigen()`: `bestaetigen()` ist die
 * Ein-Zeilen-Rückfrage („Buchung stornieren?“) ohne Folgetext und ohne
 * Eingabe. Sobald eine Aktion Folgen hat, die man nicht wegwischen kann,
 * gehört sie hierher.
 *
 * @example
 *   <DkEndgueltig v-model="offen" titel="Person anonymisieren?"
 *     text="Name, E-Mail und Notizen werden dauerhaft entfernt …"
 *     :bestaetigungswort="name" aktion="Anonymisieren"
 *     :laeuft="laeuft" :fehler="fehler" @bestaetigen="anonymisieren" />
 */
import { computed, nextTick, ref, useId, watch } from 'vue'
import DkDialog from './DkDialog.vue'
import DkButton from './DkButton.vue'
import DkField from './DkField.vue'
import DkHint from './DkHint.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  /** Die Frage — nie „Aktion bestätigen“, immer das Objekt: „Beitrag löschen?“ */
  titel: { type: String, default: 'Wirklich endgültig?' },
  /** Die konkrete Folge: was verschwindet, was bleibt, was nicht zurückkommt. */
  text: { type: String, default: '' },
  /** Zusätzliche Warnung (DkHint, warn) — z. B. eine harte Nebenfolge. */
  warnung: { type: String, default: '' },
  /**
   * Wort, das abgetippt werden muss (der Name des Objekts oder der Person).
   * Leer = keine Eingabe (Aktion zwar endgültig, aber offensichtlich).
   */
  bestaetigungswort: { type: String, default: '' },
  /** Beschriftung des gefährlichen Knopfes („Endgültig löschen“). */
  aktion: { type: String, default: 'Endgültig löschen' },
  /**
   * Beschriftung des Ausstiegs. Hier wird NICHTS eingegeben, was verloren
   * ginge — der Begriffskatalog der Oberfläche sagt dafür „Schließen“;
   * „Abbrechen“ ist für das Verwerfen einer Eingabe reserviert (Begriffe,
   * Standard S15). Seiten, die tatsächlich eine Eingabe verwerfen, dürfen
   * „Abbrechen“ übergeben.
   */
  abbrechen: { type: String, default: 'Schließen' },
  laeuft: { type: Boolean, default: false },
  fehler: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue', 'bestaetigen'])

// Eindeutige Kennung für den Folgetext (mehrere Dialoge je Seite möglich).
const textId = `dk-endgueltig-text-${useId()}`

const eingabe = ref('')
const wortFeld = ref(null)

/** Es gibt einen Folgetext, auf den die Auszeichnung zeigen kann. */
const beschrieben = computed(() => !!String(props.text || '').trim())

/** Verglichen wird ohne Rücksicht auf Groß-/Kleinschreibung und Leerraum. */
function normal(wert) {
  return String(wert || '').trim().replace(/\s+/g, ' ').toLowerCase()
}

const wortFalsch = computed(() => eingabe.value.trim() !== ''
  && normal(eingabe.value) !== normal(props.bestaetigungswort))

/** Der gefährliche Knopf ist erst frei, wenn die Eingabe stimmt. */
const bereit = computed(() => !props.laeuft
  && (!props.bestaetigungswort || normal(eingabe.value) === normal(props.bestaetigungswort)))

// Jedes Öffnen beginnt leer — kein Wort aus dem letzten Mal.
watch(() => props.modelValue, async (offen) => {
  if (!offen) return
  eingabe.value = ''
  if (!props.bestaetigungswort) return
  await nextTick()
  wortFeld.value?.focus?.()
})

function schliessen(wert = false) {
  if (props.laeuft) return
  emit('update:modelValue', wert === true)
}

function bestaetigen() {
  if (props.laeuft) return
  if (!bereit.value) return
  emit('bestaetigen')
}
</script>

<style scoped>
/* Zeilenhöhe aus dem Token (--lh-text, tokens.css) — kein Literal im Stil. */
.dk-endgueltig-text { margin: 0 0 var(--sp-3); color: var(--text); line-height: var(--lh-text); }
.dk-endgueltig-text + .dk-ui-hint { margin-bottom: var(--sp-3); }
</style>
