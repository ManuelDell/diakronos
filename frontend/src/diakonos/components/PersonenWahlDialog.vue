<template>
  <DkDialog
    vorrang
    :model-value="!!personenWahl"
    :title="personenWahl?.titel || 'Person auswählen'"
    size="sm"
    @update:model-value="abbrechen"
  >
    <p v-if="personenWahl?.text" class="pw-text">{{ personenWahl.text }}</p>
    <ul v-if="optionen.length" class="pw-liste">
      <!-- Jede Person ist ein Knopf der UI-Bibliothek (ghost = ruhige
           Auswahlfläche; die aktuelle Zuweisung wird als Badge markiert).
           UI-R9b: die Auswahl ist ein Umschalter — `aria-pressed` sagt der
           Vorlesehilfe, wer gerade zugewiesen ist (nicht nur dem Auge über
           das Badge). -->
      <li v-for="o in optionen" :key="o.value" class="pw-zeile">
        <DkButton
          variant="ghost"
          size="md"
          :aria-pressed="o.value === aktuell ? 'true' : 'false'"
          @click="personenWahlAntwort(o.value)"
        >
          {{ o.label }}
        </DkButton>
        <DkBadge v-if="o.value === aktuell" variant="info">zugewiesen</DkBadge>
      </li>
    </ul>
    <p v-else class="pw-leer">In dieser Gruppe gibt es noch keine Person, die die Aufgabe übernehmen könnte.</p>
    <template #footer>
      <DkButton variant="ghost" autofocus @click="abbrechen">Abbrechen</DkButton>
      <!-- Nichts aufgehoben werden kann nur, wenn niemand zugewiesen ist. -->
      <DkButton
        variant="secondary"
        :disabled="!aktuell"
        :aria-disabled="!aktuell ? 'true' : undefined"
        :title="!aktuell ? 'Zurzeit ist niemand zugewiesen' : undefined"
        @click="personenWahlAntwort('')"
      >Zuweisung aufheben</DkButton>
    </template>
  </DkDialog>
</template>

<script setup>
/**
 * UI-R9: die eine Person, die eine Aufgabe übernimmt (oder „niemand“).
 * Steht global in App.vue neben dem Bestätigungsdialog — so kann jede Seite
 * `waehlePerson(...)` aufrufen, ohne eigenen Dialog.
 */
import { computed } from 'vue'
import DkDialog from './ui/DkDialog.vue'
import DkButton from './ui/DkButton.vue'
import DkBadge from './ui/DkBadge.vue'
import { personenWahl, personenWahlAntwort } from '../composables/usePersonenWahl.js'

const optionen = computed(() => Array.isArray(personenWahl.value?.optionen) ? personenWahl.value.optionen : [])
/** Wer ist gerade zugewiesen? Leer heißt: niemand. */
const aktuell = computed(() => String(personenWahl.value?.aktuell || ''))

function abbrechen() {
  personenWahlAntwort(null)
}
</script>

<style scoped>
.pw-text { margin: 0 0 var(--sp-3); color: var(--text); font-size: var(--fs-sm); }
.pw-liste { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--sp-1); max-height: 45vh; overflow-y: auto; }
.pw-zeile { display: flex; align-items: center; justify-content: space-between; gap: var(--sp-2); }
.pw-leer { margin: 0; color: var(--muted); font-size: var(--fs-sm); }
</style>
