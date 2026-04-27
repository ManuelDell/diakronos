<template>
  <div class="dk-screen dk-screen-wide dk-screen-enter">

    <!-- Header -->
    <div class="dk-screen-header">
      <div>
        <h1 class="dk-screen-title">Mitglieder</h1>
        <p class="dk-screen-sub">{{ filteredCount }} von {{ totalCount }} Personen</p>
      </div>
      <div class="dk-screen-actions">
        <template v-if="isAdmin">
          <button class="dk-btn dk-btn-secondary">
            <IconUpload /> Importieren
          </button>
          <button class="dk-btn dk-btn-secondary" @click="exportList">
            <IconDownload /> Export
          </button>
        </template>
        <button v-if="isAdmin" class="dk-btn dk-btn-primary" @click="navigate('#/anmeldungen')">
          <IconUserPlus /> Mitglied hinzufügen
        </button>
      </div>
    </div>

    <!-- Toolbar -->
    <div class="dk-toolbar">
      <div class="dk-toolbar-search">
        <svg class="dk-search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Nach Name, E-Mail, Gruppe suchen…"
          @input="onSearchInput"
        />
      </div>

      <button
        v-for="f in filters"
        :key="f.id"
        class="dk-filter-chip"
        :class="{ 'is-active': statusFilter === f.id }"
        @click="statusFilter = f.id === statusFilter ? '' : f.id"
      >
        {{ f.label }}
        <span class="dk-chip-count">{{ f.count }}</span>
      </button>

      <span style="flex:1" />

      <button class="dk-filter-chip" @click="toggleSortOrder" :title="sortOrder === 'asc' ? 'A–Z' : 'Z–A'">
        <IconSort /> {{ sortOrder === 'asc' ? 'A–Z' : 'Z–A' }}
      </button>
    </div>

    <!-- Loading Skeleton -->
    <div v-if="loading && mitglieder.length === 0" style="display:flex;flex-direction:column;gap:0;background:var(--dk-surface);border:1px solid var(--dk-border);border-radius:12px;overflow:hidden">
      <div v-for="n in 8" :key="n" style="display:flex;align-items:center;gap:12px;padding:12px 16px;border-top:1px solid var(--dk-divider)" :style="n===1?'border-top:none':''">
        <div style="width:28px;height:28px;border-radius:50%;background:var(--dk-surface-2);animation:dk-pulse 1.5s infinite" />
        <div style="flex:1;display:flex;flex-direction:column;gap:6px">
          <div style="height:12px;width:140px;border-radius:4px;background:var(--dk-surface-2);animation:dk-pulse 1.5s infinite" />
          <div style="height:10px;width:100px;border-radius:4px;background:var(--dk-surface-2);animation:dk-pulse 1.5s infinite" />
        </div>
      </div>
    </div>

    <!-- Error -->
    <div v-else-if="error" style="padding:20px;background:color-mix(in oklch,var(--dk-danger) 8%,var(--dk-surface));border:1px solid color-mix(in oklch,var(--dk-danger) 25%,var(--dk-surface));border-radius:12px;color:var(--dk-danger);font-size:13px">
      {{ error }}
    </div>

    <!-- Table -->
    <template v-else>
      <table class="dk-table">
        <thead>
          <tr>
            <th @click="setSort('full_name')">
              Name <SortIcon field="full_name" :sort-by="sortBy" :sort-order="sortOrder" />
            </th>
            <th @click="setSort('status')">
              Status <SortIcon field="status" :sort-by="sortBy" :sort-order="sortOrder" />
            </th>
            <th>Gruppen</th>
            <th @click="setSort('creation')">
              Dabei seit <SortIcon field="creation" :sort-by="sortBy" :sort-order="sortOrder" />
            </th>
            <th style="width:32px"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="mitglieder.length === 0">
            <td colspan="5">
              <div class="dk-list-empty">
                <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="margin:0 auto 12px;display:block;color:var(--dk-text-subtle)"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
                <p style="margin:0;font-size:14px;font-weight:500">Keine Mitglieder gefunden</p>
                <p style="margin:4px 0 0;font-size:13px;color:var(--dk-text-subtle)">Suche oder Filter anpassen.</p>
              </div>
            </td>
          </tr>
          <tr
            v-for="m in mitglieder"
            :key="m.name"
            @click="navigate('#/mitglied/' + m.name)"
          >
            <td>
              <div class="dk-cell-person">
                <div class="dk-avatar" style="width:28px;height:28px;font-size:11px" :style="{ background: avatarColor(m.full_name), color:'#fff' }">
                  {{ getInitials(m.full_name) }}
                </div>
                <div>
                  <div class="dk-cell-name">{{ m.full_name }}</div>
                  <div class="dk-cell-email">{{ m.email || '–' }}</div>
                </div>
              </div>
            </td>
            <td>
              <span class="dk-badge" :class="statusBadge(m.status)">
                <span class="dk-badge-dot" />{{ m.status || 'Unbekannt' }}
              </span>
            </td>
            <td>
              <div class="dk-cell-groups">
                <span v-for="g in (m.gruppen || []).slice(0, 2)" :key="g" class="dk-badge">{{ g }}</span>
                <span v-if="(m.gruppen || []).length > 2" class="dk-badge">+{{ m.gruppen.length - 2 }}</span>
              </div>
            </td>
            <td class="dk-text-subtle">{{ m.creation ? new Date(m.creation).getFullYear() : '–' }}</td>
            <td>
              <button class="dk-btn dk-btn-ghost dk-btn-icon" @click.stop style="width:28px;height:28px;padding:0;display:flex;align-items:center;justify-content:center">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/></svg>
              </button>
            </td>
          </tr>
        </tbody>
      </table>

      <!-- Pagination / Load More -->
      <div class="dk-pagination">
        <div class="dk-text-muted">{{ mitglieder.length }} von {{ totalCount }} geladen</div>
        <div>
          <button
            v-if="hasMore"
            class="dk-btn dk-btn-secondary dk-btn-sm"
            :disabled="loading"
            @click="loadMore"
          >
            {{ loading ? 'Laden…' : 'Mehr laden' }}
          </button>
          <span v-else class="dk-text-subtle">Alle geladen</span>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, h } from 'vue'
import { useMitglieder } from '../composables/useMitglieder.js'
import { useSession } from '../composables/useSession.js'
import { navigate } from '../router.js'

const { isAdmin } = useSession()

const {
  mitglieder,
  loading,
  error,
  hasMore,
  searchQuery,
  statusFilter,
  sortBy,
  sortOrder,
  loadMore,
  reload,
} = useMitglieder()

const totalCount = computed(() => mitglieder.value.length + (hasMore.value ? '+' : ''))
const filteredCount = computed(() => mitglieder.value.length)

const filters = computed(() => [
  { id: 'Mitglied',  label: 'Mitglied',  count: mitglieder.value.filter(m => m.status === 'Mitglied').length },
  { id: 'Gast',      label: 'Gast',      count: mitglieder.value.filter(m => m.status === 'Gast').length },
  { id: 'Kind',      label: 'Kind',      count: mitglieder.value.filter(m => m.status === 'Kind').length },
  { id: 'Inaktiv',   label: 'Inaktiv',   count: mitglieder.value.filter(m => m.status === 'Inaktiv').length },
])

let searchTimer = null
function onSearchInput() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(reload, 300)
}

function setSort(field) {
  if (sortBy.value === field) {
    sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortBy.value = field
    sortOrder.value = 'asc'
  }
}
function toggleSortOrder() {
  sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
}

function exportList() {
  alert('Export-Funktion folgt in Phase 3.')
}

function getInitials(name) {
  if (!name) return '?'
  return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
}
const COLORS = ['#3e4d78', '#1c2850', '#6e7ca6', '#d4a24c', '#8B5E3C', '#2563eb']
function avatarColor(name) {
  return COLORS[(name || 'A').charCodeAt(0) % COLORS.length]
}
function statusBadge(s) {
  if (s === 'Mitglied') return 'dk-badge-success'
  if (s === 'Gast')     return 'dk-badge-warning'
  if (s === 'Kind')     return 'dk-badge-info'
  return ''
}

onMounted(reload)

// --- Inline components ---
const IconUpload   = () => h('svg', { width:14, height:14, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round' }, [h('path',{d:'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4'}), h('polyline',{points:'17 8 12 3 7 8'}), h('line',{x1:12,y1:3,x2:12,y2:15})])
const IconDownload = () => h('svg', { width:14, height:14, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round' }, [h('path',{d:'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4'}), h('polyline',{points:'7 10 12 15 17 10'}), h('line',{x1:12,y1:15,x2:12,y2:3})])
const IconUserPlus = () => h('svg', { width:14, height:14, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round' }, [h('path',{d:'M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2'}), h('circle',{cx:8.5,cy:7,r:4}), h('line',{x1:20,y1:8,x2:20,y2:14}), h('line',{x1:23,y1:11,x2:17,y2:11})])
const IconSort     = () => h('svg', { width:13, height:13, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round' }, [h('line',{x1:8,y1:6,x2:21,y2:6}), h('line',{x1:8,y1:12,x2:21,y2:12}), h('line',{x1:8,y1:18,x2:21,y2:18}), h('line',{x1:3,y1:6,x2:3.01,y2:6}), h('line',{x1:3,y1:12,x2:3.01,y2:12}), h('line',{x1:3,y1:18,x2:3.01,y2:18})])

const SortIcon = {
  props: ['field', 'sortBy', 'sortOrder'],
  setup(p) {
    return () => p.sortBy === p.field
      ? h('svg', { width:10, height:10, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round', style:'display:inline-block;margin-left:4px' },
          p.sortOrder === 'asc'
            ? [h('polyline',{points:'18 15 12 9 6 15'})]
            : [h('polyline',{points:'6 9 12 15 18 9'})]
        )
      : null
  }
}
</script>

<style scoped>
@keyframes dk-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
</style>
