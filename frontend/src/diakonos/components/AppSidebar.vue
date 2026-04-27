<template>
  <!-- Sidebar -->
  <aside class="dk-sidebar" :class="{ 'is-collapsed': collapsed }">

    <!-- Top: Brand + Collapse -->
    <div class="dk-sb-top">
      <a href="#/" class="dk-sb-brand" @click="$emit('close-mobile')">
        <div class="dk-sb-logo">
          <img v-if="logoUrl" :src="logoUrl" alt="Diakonos" />
          <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
            <circle cx="9" cy="7" r="4"/>
            <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
            <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
          </svg>
        </div>
        <div v-if="!collapsed" class="dk-sb-brand-text">
          <span class="dk-sb-brand-name">Diakonos</span>
          <span class="dk-sb-brand-sub">{{ churchName }}</span>
        </div>
      </a>
      <button
        class="dk-sb-collapse"
        @click="$emit('toggle-collapse')"
        :title="collapsed ? 'Ausklappen' : 'Einklappen'"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="9" y1="3" x2="9" y2="21"/>
        </svg>
      </button>
    </div>

    <!-- Search -->
    <div class="dk-sb-search">
      <div v-if="!collapsed" class="dk-sb-search-bar">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        <span>Suchen…</span>
        <kbd>⌘K</kbd>
      </div>
      <button v-else class="dk-sb-search-icon" title="Suchen">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
      </button>
    </div>

    <!-- Navigation -->
    <nav class="dk-sb-nav">
      <div class="dk-sb-section">Diakonos</div>
      <NavItem href="#/" icon="home" label="Dashboard" :active="page === 'Home'" :collapsed="collapsed" />
      <NavItem href="#/mitglieder" icon="users" label="Mitglieder" :active="page === 'Mitglieder' || page === 'MitgliedDetail'" :collapsed="collapsed" />
      <NavItem href="#/gruppen" icon="layout-grid" label="Gruppen" :active="page === 'Gruppen' || page === 'GruppeDetail'" :collapsed="collapsed" />
      <NavItem href="#/adressbuch" icon="book-open" label="Adressbuch" :active="page === 'Adressbuch'" :collapsed="collapsed" />

      <div class="dk-sb-section" style="margin-top:8px">Kronos</div>
      <NavItem href="#/kalender" icon="calendar" label="Kalender" :active="page === 'Kalender'" :collapsed="collapsed" />
      <NavItem href="#/dienstplan" icon="clock" label="Dienstplan" :active="page === 'Dienstplan'" :collapsed="collapsed" />
      <NavItem href="#/ressourcen" icon="box" label="Ressourcen" :active="page === 'Ressourcen'" :collapsed="collapsed" />
      <NavItem href="#/beitraege" icon="file-text" label="Beiträge" :active="page === 'Beitraege'" :collapsed="collapsed" />
      <NavItem href="#/wiki" icon="help-circle" label="Wiki" :active="page === 'Wiki'" :collapsed="collapsed" />

      <template v-if="isAdmin">
        <div class="dk-sb-section" style="margin-top:8px">Verwaltung</div>
        <NavItem href="#/anmeldungen" icon="user-plus" label="Anmeldungen" :active="page === 'Anmeldungen'" :collapsed="collapsed" :badge="pendingCount" />
        <NavItem href="#/organigramm" icon="git-branch" label="Organigramm" :active="page === 'Organigramm'" :collapsed="collapsed" />
        <NavItem href="#/statistik" icon="bar-chart-2" label="Statistik" :active="page === 'Statistik'" :collapsed="collapsed" />
        <NavItem href="#/dsgvo" icon="shield" label="DSGVO" :active="page === 'Dsgvo'" :collapsed="collapsed" />
      </template>
    </nav>

    <!-- Footer -->
    <div class="dk-sb-foot">
      <!-- Kronos/Psalmos Upsell -->
      <div v-if="!collapsed" class="dk-sb-upsell">
        <div class="dk-sb-upsell-title">Kronos & Psalmos</div>
        <div class="dk-sb-upsell-body">Kalender und Gottesdienstmodul – bald verfügbar.</div>
      </div>

      <!-- Admin Mode Toggle -->
      <button
        v-if="isAdmin"
        class="dk-sb-admin-toggle"
        :class="isAdminMode ? 'is-on' : 'is-off'"
        @click="isAdminMode ? exitAdminMode() : (showAdminDialog = true)"
        :title="collapsed ? (isAdminMode ? 'Admin-Modus beenden' : 'Admin-Modus') : ''"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
        <span v-if="!collapsed">{{ isAdminMode ? 'Admin-Modus beenden' : 'Admin-Modus' }}</span>
      </button>

      <!-- User -->
      <a href="#/profile" class="dk-sb-user">
        <div class="dk-avatar dk-avatar-sm" :style="{ background: avatarColor, color: '#fff' }">{{ initials }}</div>
        <div v-if="!collapsed" class="dk-sb-user-text">
          <div class="dk-sb-user-name">{{ user.fullname || 'Nutzer' }}</div>
          <div class="dk-sb-user-role">{{ mitglied ? `${mitglied.vorname || ''} ${mitglied.nachname || ''}`.trim() || 'Kein Mitglied' : 'Kein Mitglied' }}</div>
        </div>
        <button
          v-if="!collapsed"
          class="dk-sb-theme-btn"
          @click.prevent="$emit('toggle-theme')"
          :title="theme === 'dark' ? 'Hell-Modus' : 'Dunkel-Modus'"
        >
          <svg v-if="theme === 'dark'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
          <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
        </button>
      </a>
    </div>
  </aside>

  <!-- Admin Mode Dialog -->
  <Teleport to="body">
    <div v-if="showAdminDialog" class="dk-modal-overlay" @click.self="showAdminDialog = false">
      <div class="dk-modal">
        <h3>Admin-Modus aktivieren</h3>
        <p>Bitte gib eine Begründung ein. Sie wird protokolliert und der zuständigen Stelle gemeldet.</p>
        <textarea
          v-model="adminReason"
          rows="3"
          placeholder="z. B. Korrektur Mitgliedsdaten für Herrn Mustermann…"
        />
        <div class="dk-modal-actions">
          <button class="dk-btn dk-btn-secondary" @click="showAdminDialog = false">Abbrechen</button>
          <button
            class="dk-btn dk-btn-primary"
            :disabled="!adminReason.trim()"
            @click="doActivateAdmin"
          >Aktivieren</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed, h, resolveComponent } from 'vue'
import { useSession } from '../composables/useSession.js'
import { currentPageName } from '../router.js'

const props = defineProps({
  collapsed: Boolean,
  theme: String,
})
const emit = defineEmits(['toggle-collapse', 'toggle-theme', 'close-mobile'])

const { user, mitglied, isAdmin, isAdminMode, enterAdminMode, exitAdminMode } = useSession()
const page = currentPageName

const showAdminDialog = ref(false)
const adminReason = ref('')
const pendingCount = ref(0)

const churchName = window.__DIakonosBOOT?.church_name || 'Meine Gemeinde'
const logoUrl = window.__DIakonosBOOT?.logo_url || null

const initials = computed(() => {
  const n = user.value.fullname || ''
  return n.split(' ').map(x => x[0]).join('').toUpperCase().slice(0, 2) || 'U'
})

const AVATAR_COLORS = ['#3e4d78', '#1c2850', '#6e7ca6', '#d4a24c', '#8B5E3C', '#2563eb']
const avatarColor = computed(() => {
  const idx = (user.value.fullname || 'U').charCodeAt(0) % AVATAR_COLORS.length
  return AVATAR_COLORS[idx]
})

function doActivateAdmin() {
  if (!adminReason.value.trim()) return
  enterAdminMode(adminReason.value.trim())
  showAdminDialog.value = false
  adminReason.value = ''
}

// --- NavItem as inline component ---
const ICONS = {
  home: 'M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z M9 22V12h6v10',
  users: 'M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2 M23 21v-2a4 4 0 0 0-3-3.87 M16 3.13a4 4 0 0 1 0 7.75',
  'layout-grid': 'M3 3h7v7H3z M14 3h7v7h-7z M14 14h7v7h-7z M3 14h7v7H3z',
  'book-open': 'M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z',
  calendar: 'M3 4h18v16H3z M16 2v4 M8 2v4 M3 10h18',
  clock: 'M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z M12 6v6l4 2',
  'user-plus': 'M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2 M12 7a4 4 0 1 1-4-4 M20 8v6 M23 11h-6',
  'git-branch': 'M6 3v12 M18 9a3 3 0 1 0 0-6 3 3 0 0 0 0 6z M6 21a3 3 0 1 0 0-6 3 3 0 0 0 0 6z M18 9a9 9 0 0 1-9 9',
  'bar-chart-2': 'M18 20V10 M12 20V4 M6 20v-6',
  shield: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z',
  box: 'M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z M3.27 6.96L12 12.01l8.73-5.05 M12 22.08V12',
  'file-text': 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M16 13H8 M16 17H8 M10 9H8',
  'help-circle': 'M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3 M12 17h.01 M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z',
}

const NavItem = {
  props: ['href', 'icon', 'label', 'active', 'collapsed', 'badge'],
  setup(props) {
    return () => h('a', {
      href: props.href,
      class: ['dk-nav-item', props.active ? 'is-active' : ''],
      title: props.collapsed ? props.label : '',
    }, [
      h('svg', {
        width: 16, height: 16,
        viewBox: '0 0 24 24',
        fill: 'none',
        stroke: 'currentColor',
        'stroke-width': '2',
        'stroke-linecap': 'round',
        'stroke-linejoin': 'round',
        style: 'flex-shrink:0',
      }, [h('path', { d: ICONS[props.icon] || '' })]),
      !props.collapsed && h('span', props.label),
      !props.collapsed && props.badge && h('span', { class: 'dk-nav-badge' }, props.badge),
    ])
  }
}
</script>
