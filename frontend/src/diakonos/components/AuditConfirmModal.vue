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
      <DkButton
        variant="secondary"
        :disabled="isSubmitting" @click="cancel"
      >Abbrechen</DkButton>
      <DkButton
        variant="primary"
        :disabled="!reason.trim() || isSubmitting" @click="confirm"
      >
        <span v-if="isSubmitting" class="dk-spinner dk-spinner-sm" />
        <template v-else>Mit Begründung speichern</template>
        
      </DkButton>
    </template>
  </DkModal>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useAuditConfirm } from '../composables/useAuditConfirm.js'
import DkModal from './DkModal.vue'
import DkButton from '../components/ui/DkButton.vue'

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
