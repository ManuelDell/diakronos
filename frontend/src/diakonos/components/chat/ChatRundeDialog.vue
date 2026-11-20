<template>
  <!-- CHAT-7b-UI (Karte Punkt 1) — „Neue Runde“: Name (Pflicht) und 2–7
       Personen über die VORHANDENE Personensuche (`RundePersonenAuswahl`).
       Angelegt wird erst, wenn die Auswahl gültig ist; ein Server-Fehler steht
       ruhig als role="alert" darunter. Der Dialog selbst (Fokus, Esc, Zurück)
       ist `DkDialog` — nichts Eigenes. -->
  <DkDialog
    :model-value="modelValue"
    :title="NEUE_RUNDE"
    size="md"
    @close="$emit('update:modelValue', false)"
  >
    <div class="dk-runde-dialog">
      <DkField
        v-slot="feld"
        label="Name der Runde"
        help="Woran die Runde zu erkennen ist — z. B. „Samstag-Deko“."
        :wert="titel"
        required
        :maxlength="RUNDE_TITEL_MAX"
        @update:wert="titel = $event"
      >
        <input
          v-bind="feld.feldProps"
          class="dk-runde-feld"
          type="text"
          autocomplete="off"
          placeholder="Name der Runde"
        />
      </DkField>

      <!-- Personen: nur Treffer mit `darf_schreiben`, der Rest ausgegraut. -->
      <RundePersonenAuswahl
        feld-id="runde-neu-personen"
        :auswahl="auswahl"
        :ohne="[ich]"
        @update:auswahl="auswahl = $event"
      />

      <p v-if="fehler" class="dk-runde-fehler" role="alert">{{ fehler }}</p>
    </div>

    <template #footer>
      <DkButton variant="ghost" @click="$emit('update:modelValue', false)">Abbrechen</DkButton>
      <DkButton
        variant="primary"
        :disabled="!zustand.anlegen"
        :loading="laeuft"
        @click="anlegen"
      >{{ NEUE_RUNDE }}</DkButton>
    </template>
  </DkDialog>
</template>

<script setup>
/**
 * ChatRundeDialog — „Neue Runde“ anlegen (CHAT-7b-UI-a, Karte Punkt 1).
 *
 * Die Komponente ZEICHNET: Name, Zähler, Auswahlzeilen, Fehler. Was gültig ist
 * und wann der Anlegen-Knopf steht, entscheidet `nachrichtenRunden.mjs`
 * (`rundeAnlegenZustand`, `auswahlUmschalten`, `auswahlGueltig`) — ohne DOM
 * prüfbar. Gesendet wird hier NICHT: die Seite ruft `chat.runde_anlegen` und
 * gibt das Ergebnis über `laeuft`/`fehler` zurück (ein Weg, wie beim
 * Umfrage-Dialog).
 *
 * Rechtelogik gibt es hier nicht: `darf_schreiben` kommt vom Server
 * (`chat.personen_suchen`); ein Server-Fehler wird als ruhiger Satz gezeigt —
 * „gesperrt“ und „nicht erreichbar“ lassen sich an der Antwort nicht
 * unterscheiden, und die Oberfläche erfindet keinen Unterschied.
 */
import { computed, ref, watch } from 'vue'
import { useSession } from '../../composables/useSession.js'
import {
  NEUE_RUNDE, RUNDE_TITEL_MAX, rundeAnlegenZustand,
} from '../../composables/nachrichtenRunden.mjs'
import DkButton from '../ui/DkButton.vue'
import DkDialog from '../ui/DkDialog.vue'
import DkField from '../ui/DkField.vue'
import RundePersonenAuswahl from './RundePersonenAuswahl.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  /** Läuft der Aufruf `runde_anlegen` gerade? (sperrt den Knopf) */
  laeuft: { type: Boolean, default: false },
  /** Der Satz des Servers nach einem Fehlschlag (`''` = keiner). */
  fehler: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue', 'anlegen'])

const { mitglied } = useSession()
const ich = computed(() => String(mitglied.value?.name || ''))

const titel = ref('')
const auswahl = ref([])

const zustand = computed(() => rundeAnlegenZustand({
  titel: titel.value,
  auswahl: auswahl.value,
  laeuft: props.laeuft,
}))

// Jedes Öffnen beginnt leer: ein abgebrochener Versuch ist kein zweiter.
watch(() => props.modelValue, (offen) => {
  if (!offen) return
  titel.value = ''
  auswahl.value = []
})

function anlegen() {
  if (!zustand.value.anlegen || props.laeuft) return
  emit('anlegen', { titel: titel.value.trim(), auswahl: [...auswahl.value] })
}
</script>

<style scoped>
.dk-runde-dialog {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}
.dk-runde-feld {
  width: 100%;
  min-height: var(--control-h);
  padding: var(--sp-2) var(--sp-3);
  border: var(--rahmen-breite) solid var(--rahmen-farbe);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--text);
  font-family: inherit;
  font-size: var(--fs-14);
  line-height: var(--lh-text);
}
.dk-runde-feld:focus-visible { outline: var(--rahmen-breite) solid var(--focus-ring); outline-offset: var(--rahmen-breite); }
.dk-runde-fehler {
  margin: 0;
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius);
  background: var(--err-soft);
  color: var(--err);
  font-size: var(--fs-12);
}
</style>
