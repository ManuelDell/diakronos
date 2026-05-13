<template>
  <FrappeUIProvider>
    <div class="dk-app" :class="{ 'is-collapsed': sidebarCollapsed }" :data-theme="theme">
      <KronosSidebar v-if="isKronosMode" @backClick="navigate('#/')" />
      <AppSidebar v-else :collapsed="sidebarCollapsed" :theme="theme" @toggle-collapse="sidebarCollapsed = !sidebarCollapsed" @toggle-theme="toggleTheme" />
      <div class="dk-main-wrap">
        <AppTopbar v-if="!isKronosMode" :collapsed="sidebarCollapsed" @toggle-collapse="sidebarCollapsed = !sidebarCollapsed" />
        <div class="dk-content" :class="{ 'dk-content--kronos': isKronosMode }">
          <component :is="currentComponent" v-if="currentComponent" />
          <div v-else class="dk-screen dk-screen-enter" style="display:flex;align-items:center;justify-content:center;min-height:300px;">
            <div style="text-align:center;color:var(--dk-text-subtle)">
              <div style="width:32px;height:32px;border:2px solid var(--dk-border);border-top-color:var(--dk-brand-800);border-radius:50%;animation:spin 0.8s linear infinite;margin:0 auto 12px"></div>
              <p style="font-size:13px;margin:0">Wird geladen…</p>
            </div>
          </div>
        </div>
        <AuditConfirmModal v-if="!isKronosMode" />
      </div>
    </div>
  </FrappeUIProvider>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { FrappeUIProvider } from 'frappe-ui'
import AppSidebar from './components/AppSidebar.vue'
import AppTopbar from './components/AppTopbar.vue'
import AuditConfirmModal from './components/AuditConfirmModal.vue'
import KronosSidebar from './components/kronos/KronosSidebar.vue'
import { currentComponent, currentHash, navigate } from './router.js'

const sidebarCollapsed = ref(false)
const theme = ref(localStorage.getItem('dk-theme') || 'light')

const isKronosMode = computed(() => currentHash.value === '#/kalender')

watch(isKronosMode, (val) => {
  if (val) sidebarCollapsed.value = false
})

function toggleTheme() {
  theme.value = theme.value === 'dark' ? 'light' : 'dark'
  localStorage.setItem('dk-theme', theme.value)
}
</script>

<style>
@keyframes spin { to { transform: rotate(360deg); } }
</style>
