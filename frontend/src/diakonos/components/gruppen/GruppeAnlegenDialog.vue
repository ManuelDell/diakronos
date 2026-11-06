<template>
  <!-- Ein Dialog für Liste UND Bereichs-Rahmen (DEV-1): gleiche Felder und
       derselbe Serveraufruf wie im Organigramm (OP-ADMIN-6/UXD-R4). Vorher lag
       der Dialog in `pages/Gruppen.vue` und war im eingebetteten Modus nicht
       erreichbar, weil dort auch die Knöpfe fehlten. -->
  <DkDialog :model-value="modelValue" :title="titel" @update:model-value="schliessen">
    <!-- OP-UI-23: <form @submit.prevent> — Enter im Feld sendet dieselbe
         Hauptaktion wie der Knopf (statt wirkungslos zu bleiben). -->
    <form class="gr-formular" @submit.prevent="submit">
      <!-- UX2f: Feld mit Prüfung — Meldung beim Verlassen des Feldes, danach
           beim Tippen; aria-invalid/aria-describedby kommen aus DkField. -->
      <DkField
        label="Name"
        required
        :error="fehler.name"
        :regel="regelName"
        :wert="form.name"
        pflicht-name="einen Namen"
        maxlength="140"
        @update:wert="form.name = $event"
        v-slot="feld"
      >
        <input v-bind="feld.feldProps" type="text" placeholder="Name eingeben" />
      </DkField>
      <DkField v-if="form.typ === 'gruppe'" label="Dienstbereich" required :error="fehler.parent">
        <DkSelect v-model="form.parent" :options="dienstbereichOptionen" placeholder="Bitte wählen" />
      </DkField>
      <DkField v-else label="Gruppe" required :error="fehler.parent">
        <DkSelect v-model="form.parent" :options="gruppenOptionen" placeholder="Bitte wählen" />
      </DkField>
    </form>
    <template #footer>
      <DkButton variant="ghost" @click="schliessen(false)">Abbrechen</DkButton>
      <DkButton variant="primary" :loading="sending" @click="submit">Anlegen</DkButton>
    </template>
  </DkDialog>
</template>

<script setup>
/**
 * GruppeAnlegenDialog — „Neue Gruppe/Untergruppe“ anlegen (DEV-1).
 *
 * Ein Dialog für beide Wege (Bereichs-Rahmen und reine Liste). Die Auswahlen
 * kommen vom Aufrufer, weil beide Seiten sie aus ihren eigenen Seitendaten
 * haben (`dienstbereich_auswahl`/`gruppen_auswahl` aus `get_gruppen_page_data`).
 */
import { ref, computed, watch } from 'vue'
import { apiCall } from '../../composables/useApi.js'
import { showToast } from '../../composables/useToast.js'
// UX2g: EINE Quelle fuer angezeigte Fehlertexte statt Floskeln wie
// "Fehler beim Speichern" / "Unbekannter Fehler".
import { aktionsfehler } from '../../../shared/fehlertexte.js'
import { anlegeAufruf } from '../../composables/gruppenAnlegen.mjs'
import DkDialog from '../ui/DkDialog.vue'
import DkButton from '../ui/DkButton.vue'
import DkField from '../ui/DkField.vue'
// UX2f: Prüfregeln aus EINER Quelle.
import { pflicht, laenge as laengeRegel } from '../../composables/feldPruefung.mjs'
import DkSelect from '../ui/DkSelect.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  /** 'gruppe' oder 'untergruppe'. */
  typ: { type: String, default: 'gruppe' },
  /** [{ name, ministry }] — Dienstbereiche zum Auswählen. */
  dienstbereiche: { type: Array, default: () => [] },
  /** [{ name, gruppenname }] — Gruppen zum Auswählen. */
  gruppen: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue', 'angelegt'])

const sending = ref(false)
const form = ref({ typ: props.typ, name: '', parent: '' })
// OP-UI-5/UXD-R22: der Knopf bleibt aktiv; der Klick prüft und benennt das
// fehlende Feld, statt stumm nichts zu tun (vorher `:disabled`).
const fehler = ref({ name: '', parent: '' })

const titel = computed(() => (form.value.typ === 'untergruppe' ? 'Neue Untergruppe' : 'Neue Gruppe'))

// UX2f: Der Name ist Pflicht und höchstens 140 Zeichen lang (dieselbe Grenze,
// die das Feld früher über maxlength hatte — jetzt mit Meldung statt stillem
// Abschneiden).
const regelName = (wert, form) =>
  pflicht('einen Namen')(wert) || laengeRegel({ max: 140, name: 'Der Name' })(wert)
const dienstbereichOptionen = computed(() =>
  props.dienstbereiche.map(d => ({ value: d.name, label: d.ministry || d.name })))
const gruppenOptionen = computed(() =>
  props.gruppen.map(g => ({ value: g.name, label: g.gruppenname || g.name })))

// Beim Öffnen frisch beginnen; der Typ kommt vom angeklickten Knopf.
watch(() => [props.modelValue, props.typ], ([offen]) => {
  if (!offen) return
  form.value = { typ: props.typ, name: '', parent: '' }
  fehler.value = { name: '', parent: '' }
})

function schliessen() {
  if (sending.value) return
  emit('update:modelValue', false)
}

/** Pflichtfelder prüfen (OP-UI-5): Fehler am Feld, Fokus ins erste Feld. */
function pruefe() {
  const f = form.value
  const nächste = { name: '', parent: '' }
  // UX2f: dieselben Regeln und Texte wie am Feld (eine Quelle).
  nächste.name = regelName(f.name, f)
  if (!f.parent) {
    nächste.parent = f.typ === 'untergruppe'
      ? 'Bitte eine Gruppe wählen.'
      : 'Bitte einen Dienstbereich wählen.'
  }
  fehler.value = nächste
  return !nächste.name && !nächste.parent
}

async function submit() {
  if (sending.value) return
  if (!pruefe()) {
    // UX2f: das erste Feld mit Fehler bekommt den Fokus (nicht blind das erste).
    requestAnimationFrame(() => {
      const ziel = document.querySelector('.gr-formular [aria-invalid="true"]')
        || document.querySelector('.gr-formular .dk-ui-eingabe')
      ziel?.focus()
    })
    return
  }
  const f = form.value
  sending.value = true
  try {
    // Methode und Parameter kommen aus EINER Quelle — dieselben Feldnamen wie
    // im Organigramm (UXD-R4).
    const { methode, parameter, toast } = anlegeAufruf(f.typ, f)
    await apiCall(methode, parameter)
    showToast(toast, 'success')
    emit('update:modelValue', false)
    emit('angelegt', { typ: f.typ, name: String(f.name || '').trim() })
  } catch (err) {
    showToast(aktionsfehler('anlegen', err), 'error')
  } finally {
    sending.value = false
  }
}
</script>

<style scoped>
.gr-formular { display: flex; flex-direction: column; gap: var(--sp-3); }
</style>
