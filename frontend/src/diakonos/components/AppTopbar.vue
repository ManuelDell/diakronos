<template>
  <header class="dk-topbar">
    <div class="dk-topbar-left">
      <!-- Mobile menu toggle -->
      <button class="dk-icon-btn" style="display:none" @click="$emit('toggle-collapse')">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
      </button>

      <!-- Back button for detail pages -->
      <button
        v-if="showBack"
        class="dk-btn dk-btn-ghost dk-btn-sm"
        @click="navigateBack"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
        Zurück
      </button>

      <!-- Breadcrumbs -->
      <nav class="dk-crumbs">
        <span v-for="(crumb, i) in breadcrumbs" :key="i" class="dk-crumb">
          <span class="dk-crumb-sep" v-if="i > 0">/</span>
          <span :class="i === breadcrumbs.length - 1 ? 'dk-crumb-current' : ''">{{ crumb }}</span>
        </span>
      </nav>
    </div>

    <div class="dk-topbar-right">
      <!-- Search -->
      <button class="dk-topbar-search">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        <span>Suchen</span>
        <kbd>⌘K</kbd>
      </button>

      <!-- Notifications -->
      <button class="dk-icon-btn" title="Benachrichtigungen" @click="markAsRead">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
        <span v-if="unreadCount > 0" class="dk-notify-badge">{{ unreadCount }}</span>
      </button>

      <div class="dk-topbar-divider" />
    </div>
  </header>
</template>

<script setup>
import { computed } from 'vue'
import { currentPageName, navigate } from '../router.js'
import { useNotifications } from '../composables/useNotifications.js'

defineProps({ collapsed: Boolean })
defineEmits(['toggle-collapse'])

const { unreadCount, markAsRead } = useNotifications()
const page = currentPageName

const CRUMB_MAP = {
  Home:          ['Dashboard'],
  Mitglieder:    ['Diakonos', 'Mitglieder'],
  MitgliedDetail:['Diakonos', 'Mitglieder', 'Profil'],
  Gruppen:       ['Diakonos', 'Gruppen'],
  GruppeDetail:  ['Diakonos', 'Gruppen', 'Detail'],
  Adressbuch:    ['Diakonos', 'Adressbuch'],
  Kalender:      ['Kronos', 'Kalender'],
  Dienstplan:    ['Kronos', 'Dienstplan'],
  Ressourcen:    ['Kronos', 'Ressourcen'],
  Beitraege:     ['Diakonos', 'Beiträge'],
  Wiki:          ['Diakonos', 'Wiki'],
  Anmeldungen:   ['Verwaltung', 'Anmeldungen'],
  Organigramm:   ['Verwaltung', 'Organigramm'],
  Statistik:     ['Verwaltung', 'Statistik'],
  Dsgvo:         ['Verwaltung', 'DSGVO'],
  Profile:       ['Profil'],
}

const breadcrumbs = computed(() => CRUMB_MAP[page.value] || [page.value])

const showBack = computed(() => ['MitgliedDetail', 'GruppeDetail'].includes(page.value))

function navigateBack() {
  if (page.value === 'MitgliedDetail') navigate('#/mitglieder')
  else if (page.value === 'GruppeDetail') navigate('#/gruppen')
}
</script>
