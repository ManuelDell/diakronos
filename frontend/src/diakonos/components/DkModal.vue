<template>
  <Teleport to="body">
    <div v-if="modelValue" class="dk-modal-overlay" @click.self="close">
      <div class="dk-modal">
        <h3 v-if="title">{{ title }}</h3>
        <slot />
        <div v-if="$slots.footer" class="dk-modal-actions">
          <slot name="footer" />
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
const props = defineProps({
  modelValue: Boolean,
  title: String,
})
const emit = defineEmits(['update:modelValue'])

function close() {
  emit('update:modelValue', false)
}
</script>
