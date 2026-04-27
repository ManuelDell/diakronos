<template>
  <div class="gruppen-item">
    <div
      class="dk-card cursor-pointer transition-shadow hover:shadow-md"
      @click="navigateToGruppe(gruppe)"
    >
      <div class="p-4 flex items-start justify-between">
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 mb-1">
            <h3 class="text-base font-semibold text-[var(--dk-text)] truncate">
              {{ gruppe.gruppenname || gruppe.name }}
            </h3>
            <span
              v-if="gruppe.status"
              :class="getStatusColor(gruppe.status)"
            >
              {{ gruppe.status }}
            </span>
          </div>
          <div class="flex flex-wrap gap-x-4 gap-y-1 text-sm text-[var(--dk-text-muted)]">
            <span v-if="gruppe.dienstbereich" class="flex items-center gap-1">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"/>
              </svg>
              {{ gruppe.dienstbereich }}
            </span>
            <span v-if="gruppe.gruppentyp" class="flex items-center gap-1">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z"/>
              </svg>
              {{ gruppe.gruppentyp }}
            </span>
            <span v-if="gruppe.mitglieder_count != null" class="flex items-center gap-1">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"/>
              </svg>
              {{ gruppe.mitglieder_count }} Mitglieder
            </span>
          </div>
          <p v-if="gruppe.beschreibung" class="text-sm text-[var(--dk-text-muted)] mt-2 line-clamp-2">
            {{ gruppe.beschreibung }}
          </p>
        </div>
        <button
          v-if="gruppe.untergruppen && gruppe.untergruppen.length > 0"
          class="ml-3 p-1 rounded hover:bg-[var(--dk-surface-hover)] transition-colors"
          @click.stop="toggle"
        >
          <svg
            :class="['w-5 h-5 text-[var(--dk-text-subtle)] transition-transform', expanded ? 'rotate-90' : '']"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- Untergruppen -->
    <div
      v-if="gruppe.untergruppen && gruppe.untergruppen.length > 0 && expanded"
      class="ml-6 mt-2 space-y-2 border-l-2 border-[var(--dk-border)] pl-4"
    >
      <GruppenItem
        v-for="kind in gruppe.untergruppen"
        :key="kind.name"
        :gruppe="kind"
      />
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  gruppe: {
    type: Object,
    required: true
  }
})

const expanded = ref(false)

const toggle = () => {
  expanded.value = !expanded.value
}

const navigateToGruppe = (gruppe) => {
  const route = gruppe.is_untergruppe
    ? `#/untergruppe/${gruppe.name}`
    : `#/gruppe/${gruppe.name}`
  window.location.hash = route
}

const getStatusColor = (status) => {
  const map = {
    Aktiv: 'dk-badge dk-badge-success',
    Inaktiv: 'dk-badge',
    Archiviert: 'dk-badge dk-badge-danger'
  }
  return map[status] || 'dk-badge'
}
</script>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
