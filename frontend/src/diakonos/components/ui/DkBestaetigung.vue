<template>
  <DkDialog vorrang :model-value="!!bestaetigung" :title="bestaetigung?.titel || 'Bitte prüfen'"
            size="sm" @update:model-value="bestaetigungAntwort(false)">
    <p>{{ bestaetigung?.text }}</p>
    <template #footer>
      <DkButton variant="ghost" autofocus @click="bestaetigungAntwort(false)">{{ bestaetigung?.abbrechen || 'Abbrechen' }}</DkButton>
      <DkButton :variant="bestaetigung?.gefahr ? 'danger' : 'primary'" @click="bestaetigungAntwort(true)">{{ bestaetigung?.aktion || 'Fortfahren' }}</DkButton>
    </template>
  </DkDialog>
</template>

<script setup>
import DkDialog from './DkDialog.vue'
import DkButton from './DkButton.vue'
import { bestaetigung, bestaetigungAntwort } from '../../composables/useBestaetigen.js'
</script>
