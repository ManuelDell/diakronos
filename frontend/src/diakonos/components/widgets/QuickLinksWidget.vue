<template>
  <div class="dk-widget-card dk-widget-full">
    <div class="dk-quick-row">
      <button v-for="link in links" :key="link.href" class="dk-quick-card" @click="navigate(link.href)">
        <div class="dk-quick-icon" v-html="link.icon"></div>
        <div>
          <div class="dk-quick-title">{{ link.title }}</div>
          <div class="dk-quick-desc">{{ link.desc }}</div>
        </div>
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useSession } from '../../composables/useSession'

const { isAdmin } = useSession()

function navigate(href) { window.location.hash = href }

const links = computed(() => {
  if (isAdmin.value) {
    return [
      { href: '#/mitglieder', title: 'Mitgliederliste', desc: 'Alle Mitglieder suchen und verwalten.', icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>' },
      { href: '#/gruppen', title: 'Gruppen & Dienste', desc: 'Mitarbeitende zu Bereichen zuordnen.', icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>' },
      { href: '#/kalender', title: 'Kalender', desc: 'Termine und Veranstaltungen verwalten.', icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>' },
    ]
  }
  return [
    { href: '#/kalender', title: 'Kalender', desc: 'Termine und Veranstaltungen.', icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>' },
    { href: '#/gruppen', title: 'Gruppen', desc: 'Deine Gruppen und Bereiche.', icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>' },
    { href: '#/mitglieder', title: 'Mitglieder', desc: 'Kontakte der Gemeinde.', icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/></svg>' },
  ]
})
</script>
