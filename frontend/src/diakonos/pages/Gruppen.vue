<template>
  <div class="dk-screen dk-screen-enter">
    <!-- Header -->
    <div class="dk-screen-header">
      <div>
        <h1 class="dk-screen-title">Gruppen</h1>
        <p class="dk-screen-sub">Übersicht aller Gruppen und Untergruppen.</p>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="space-y-4">
      <div v-for="n in 5" :key="n" class="animate-pulse dk-card p-4">
        <div class="h-4 bg-[var(--dk-surface-2)] rounded w-1/3 mb-2"></div>
        <div class="h-3 bg-[var(--dk-surface-2)] rounded w-1/4"></div>
      </div>
    </div>

    <!-- Empty State -->
    <div v-else-if="gruppen.length === 0" class="text-center py-12">
      <div class="text-[var(--dk-text-subtle)] text-5xl mb-4">👥</div>
      <h3 class="text-lg font-medium text-[var(--dk-text)]">Keine Gruppen vorhanden</h3>
      <p class="text-[var(--dk-text-muted)] mt-1">Es wurden noch keine Gruppen angelegt.</p>
    </div>

    <!-- Baum-Ansicht -->
    <div v-else class="space-y-3">
      <GruppenItem
        v-for="gruppe in gruppen"
        :key="gruppe.name"
        :gruppe="gruppe"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { apiCall } from '../composables/useApi.js'
import GruppenItem from '../components/GruppenItem.vue'

const gruppen = ref([])
const loading = ref(true)
const error = ref(null)

const fetchGruppen = async () => {
  loading.value = true
  try {
    const result = await apiCall('diakronos.diakonos.api.gruppen.get_gruppen_hierarchie')
    gruppen.value = result?.gruppen || []
  } catch (err) {
    console.error('Fehler beim Laden der Gruppen:', err)
    error.value = err
    gruppen.value = []
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchGruppen()
})
</script>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
