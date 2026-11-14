<template>
  <!--
    R6: „Für wen ist das?“ — Auswahl der (Unter-)Gruppe beim Anlegen eines
    Beitrags/Wiki-Artikels.

    Die Liste enthält NUR die Orte, die der Server in `rechte.get_anlegeorte`
    genannt hat (`anlegeorteAusAntwort` in composables/r6Gastzugang.mjs) —
    dieselbe Regel, mit der er das Anlegen hernach durchsetzt. Titel und
    Reihenfolge (Gemeinde, dann je Gruppe die Gruppe und ihre Untergruppen)
    kommen fertig vom Server. Es gibt keinen Ausweg, der die Prüfung umgeht:
    ist nichts erlaubt, steht hier ein Hinweis statt einer leeren Auswahl —
    und KEIN Knopf, der ohnehin 403 gäbe.
  -->
  <DkDialog
    :model-value="modelValue"
    size="sm"
    :title="titel"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <div class="r6-einheit">
      <p v-if="laden" class="r6-einheit-status" role="status">Wird geprüft …</p>

      <template v-else-if="optionen.length === 0">
        <p class="r6-einheit-status">
          Du darfst derzeit keinen {{ was }} anlegen. Das dürfen die
          Hauptverantwortlichen (HV) und Mitverantwortlichen (MV) einer Gruppe bzw. die
          Gruppenleitung (GL) einer Untergruppe — oder der Administrator für die
          ganze Gemeinde.
        </p>
      </template>

      <template v-else>
        <!-- Befund (Review 12.11., Punkt 3): ohne `v-slot="feld"` blieb
             `<label for>` ohne Ziel — das Feld hatte keinen zugänglichen
             Namen. Die Kennung kommt deshalb aus dem Feld selbst. -->
        <DkField :label="label" :help="hilfe" v-slot="feld">
          <DkSelect
            :id="feld.id"
            :model-value="gewaehlt"
            :options="auswahlOptionen"
            :aria-describedby="feld['aria-describedby']"
            @update:model-value="waehlen"
          />
        </DkField>
        <p v-if="optionen.length === 1" class="r6-einheit-status">
          Es gibt für dich genau eine Möglichkeit — sie ist schon gewählt.
        </p>
      </template>
    </div>

    <template #footer>
      <DkButton type="button" variant="secondary" @click="$emit('update:modelValue', false)">
        Abbrechen
      </DkButton>
      <DkButton
        type="button"
        variant="primary"
        :disabled="!gewaehlt || laden"
        @click="uebernehmen"
      >
        Weiter
      </DkButton>
    </template>
  </DkDialog>
</template>

<script setup>
/**
 * R6 — Auswahl der Gruppe vor dem Anlegen. Rein darstellend: die Orte kommen
 * fertig vom Server (`optionen` samt `titel`/`tiefe`), die Vorauswahl ebenso
 * (`startwert`). „Weiter“ gibt den GEWÄHLTEN ORT zurück (samt Server-`titel`);
 * der Editor schickt `gruppe`/`untergruppe` an
 * `create_beitrag`/`create_wiki_artikel` und zeigt `titel` an.
 */
import { computed, ref, watch } from 'vue'
import DkDialog from '../ui/DkDialog.vue'
import DkField from '../ui/DkField.vue'
import DkSelect from '../ui/DkSelect.vue'
import DkButton from '../ui/DkButton.vue'
import { ortAusWert, gewaehlteEinheit, einheitWert } from '../../composables/r6Gastzugang.mjs'

const props = defineProps({
  modelValue: Boolean,
  // Fertige Orte vom Server ({gruppe, untergruppe, titel, tiefe, gemeinde}).
  optionen: { type: Array, default: () => [] },
  // Vorauswahl als Optionswert (`einheitWert`) oder leer.
  startwert: { type: String, default: '' },
  laden: Boolean,
  titel: { type: String, default: 'Für wen ist das?' },
  label: { type: String, default: 'Gruppe' },
  hilfe: { type: String, default: '' },
  // Teil des Satzes im Leerzustand: „Du darfst derzeit keinen Beitrag anlegen.“
  was: { type: String, default: 'Beitrag' },
})

const emit = defineEmits(['update:modelValue', 'waehlen'])

const eigeneWahl = ref('')

/**
 * Die tatsächlich ausgewählte Einheit — Regel in `gewaehlteEinheit` (dort
 * geprüft). Sie wird ins Feld ZURÜCKGEBUNDEN: ohne das stünde die Liste auf
 * `selectedIndex = -1` (zeigt nichts), während dieser Wert schon gilt —
 * Feld und „Weiter“ widersprächen sich (Befund im Beleg-Lauf).
 */
const gewaehlt = computed(() => gewaehlteEinheit(props.optionen, {
  eigeneWahl: eigeneWahl.value,
  start: props.startwert,
}))

/** Auswahl der Person merken; ein neues Öffnen beginnt wieder bei der Vorauswahl. */
function waehlen(wert) {
  eigeneWahl.value = String(wert ?? '')
}

watch(() => props.modelValue, (offen) => {
  if (offen) eigeneWahl.value = ''
})

const auswahlOptionen = computed(() => (props.optionen || []).map((o) => ({
  value: einheitWert(o),
  // Einrückung der Untergruppe: sie gehört sichtbar zur Hauptgruppe darüber.
  // Reines Leerzeichen, kein Gestaltungsmittel — die Auswahlliste des
  // Browsers kennt keine Einzüge.
  label: (o.tiefe ? '\u00a0\u00a0\u00a0' : '') + (o.titel || einheitWert(o)),
})))

function uebernehmen() {
  if (!gewaehlt.value) return
  // Der ganze Ort (inkl. `titel`) — nicht nur die beiden Kennungen.
  emit('waehlen', ortAusWert(gewaehlt.value, props.optionen))
  emit('update:modelValue', false)
}
</script>

<style scoped>
.r6-einheit-status {
  margin: 0 0 var(--sp-3);
  color: var(--muted);
  font-size: var(--fs-sm);
  line-height: 1.5;
}
</style>
