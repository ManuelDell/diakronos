<template>
  <div class="moderation-page">
    <div v-if="loading" class="moderation-loading">Lade…</div>
    <div v-else-if="!canModerate" class="moderation-forbidden">
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/></svg>
      <p>Keine Berechtigung für die Terminmoderation.</p>
    </div>
    <iframe
      v-else
      src="/kronos/moderation"
      class="moderation-frame"
      frameborder="0"
      allow="same-origin"
    ></iframe>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const canModerate = ref(false)
const loading = ref(true)

onMounted(async () => {
  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content
  if (!csrfToken) { loading.value = false; return }
  try {
    const res = await fetch('/api/method/diakronos.kronos.api.permissions.get_session_info', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': csrfToken },
      credentials: 'include',
      body: JSON.stringify({})
    })
    if (res.ok) {
      const { message } = await res.json()
      canModerate.value = message?.can_moderate || false
    }
  } catch (_) {}
  loading.value = false
})
</script>

<style scoped>
.moderation-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}
.moderation-frame {
  flex: 1;
  width: 100%;
  height: 100%;
  border: none;
}
.moderation-loading,
.moderation-forbidden {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  height: 100%;
  color: var(--dk-text-muted, #6b7280);
  font-size: 14px;
}
</style>
