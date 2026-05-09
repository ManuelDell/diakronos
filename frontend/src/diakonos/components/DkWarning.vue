<template>
  <Teleport to="body">
    <div v-if="modelValue" class="dk-modal-overlay" @click.self="onCancel">
      <div class="dk-modal" style="max-width:420px;width:100%;">
        <h3 style="color:var(--dk-warning);">⚠️ {{ title }}</h3>
        <p style="margin:8px 0 16px;font-size:0.9rem;color:var(--dk-text);">{{ message }}</p>
        <label v-if="sessionKey" style="display:flex;align-items:center;gap:8px;font-size:0.85rem;color:var(--dk-text-muted);cursor:pointer;margin-bottom:16px;">
          <input type="checkbox" v-model="noMore" />
          In dieser Session nicht mehr warnen
        </label>
        <div class="dk-modal-actions">
          <button class="dk-btn dk-btn-ghost" @click="onCancel">Abbrechen</button>
          <button class="dk-btn dk-btn-warning" @click="onConfirm">{{ confirmLabel }}</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  modelValue: Boolean,
  title: String,
  message: String,
  confirmLabel: { type: String, default: 'Trotzdem fortfahren' },
  sessionKey: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue', 'confirm', 'cancel'])

const noMore = ref(false)

watch(() => props.modelValue, (val) => {
  if (val) noMore.value = false
})

function onCancel() {
  emit('update:modelValue', false)
  emit('cancel')
}

function onConfirm() {
  if (props.sessionKey && noMore.value) {
    sessionStorage.setItem(props.sessionKey, '1')
  }
  emit('update:modelValue', false)
  emit('confirm')
}
</script>
