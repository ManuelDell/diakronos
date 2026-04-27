<template>
  <DkModal v-model="visible" :title="currentPolicy?.confirm_prompt">
    <div class="dk-form-group">
      <label>{{ currentPolicy?.confirm_field_label }}</label>
      <textarea
        v-model="reason"
        class="dk-form-textarea"
        rows="3"
        placeholder="Begründung eingeben..."
      />
    </div>
    <template #footer>
      <button class="dk-btn dk-btn-secondary" :disabled="isSubmitting" @click="cancel">Abbrechen</button>
      <button class="dk-btn dk-btn-primary" :disabled="!reason.trim() || isSubmitting" @click="confirm">
        <span v-if="isSubmitting" class="dk-spinner dk-spinner-sm" />
        <template v-else>Mit Begründung speichern</template>
      </button>
    </template>
  </DkModal>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useAuditConfirm } from '../composables/useAuditConfirm.js'
import DkModal from './DkModal.vue'

const { isOpen, isSubmitting, currentPolicy, submit, cancel } = useAuditConfirm()
const visible = computed({
  get: () => isOpen.value,
  set: (v) => { if (!v) cancel() }
})
const reason = ref('')

watch(isOpen, (open) => {
  if (open) reason.value = ''
})

function confirm() {
  if (!reason.value.trim()) return
  submit(reason.value.trim())
}
</script>
