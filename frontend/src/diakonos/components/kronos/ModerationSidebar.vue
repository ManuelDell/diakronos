<template>
  <aside class="dk-sidebar dk-sidebar--moderation">
    <div class="dk-sb-top">
      <a href="#/kalender" class="dk-sb-brand" @click.prevent="goToKalender">
        <div class="dk-sb-logo">
          <img v-if="logoUrl" :src="logoUrl" alt="Diakronos" />
          <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
            <circle cx="9" cy="7" r="4"/>
            <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
            <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
          </svg>
        </div>
        <div class="dk-sb-brand-text">
          <span class="dk-sb-brand-name">Diakronos</span>
          <span class="dk-sb-brand-sub">{{ churchName }}</span>
        </div>
      </a>
    </div>

    <nav class="dk-sb-nav">
      <div class="dk-sb-section">Moderation</div>
      <a href="#/kalender" class="dk-nav-item" @click.prevent="goToKalender">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0">
          <polyline points="15 18 9 12 15 6"/>
        </svg>
        <span>Zurück zum Kalender</span>
      </a>
    </nav>

    <!-- Footer -->
    <div class="dk-sb-foot">
      <a href="#/profile" class="dk-sb-user">
        <div class="dk-avatar dk-avatar-sm" :style="avatarStil(user.fullname)">{{ initials }}</div>
        <div class="dk-sb-user-text">
          <div class="dk-sb-user-name">{{ user.fullname || 'Nutzer' }}</div>
          <div class="dk-sb-user-role">Moderator</div>
        </div>
      </a>
    </div>
  </aside>
</template>

<script setup>
import { computed } from 'vue'
import { useSession } from '../../composables/useSession.js'
import { navigate } from '../../router.js'

const { user } = useSession()

const churchName = window.__DIakonosBOOT?.church_name || 'Meine Gemeinde'
const logoUrl = window.__DIakonosBOOT?.logo_url || null

const initials = computed(() => {
  const n = user.value.fullname || ''
  return n.split(' ').map(x => x[0]).join('').toUpperCase().slice(0, 2) || 'U'
})

/* DES-08: Initialen tragen Schrift UND Flaeche aus Tokens — vorher
   --primary-ink auf Gold (2,68:1) bzw. im Dunkelmodus 1,41:1. */
const AVATAR_PAARE = [
  { bg: 'var(--dk-avatar-1-bg)', ink: 'var(--dk-avatar-1-ink)' },
  { bg: 'var(--dk-avatar-2-bg)', ink: 'var(--dk-avatar-2-ink)' },
  { bg: 'var(--dk-avatar-3-bg)', ink: 'var(--dk-avatar-3-ink)' },
  { bg: 'var(--dk-avatar-4-bg)', ink: 'var(--dk-avatar-4-ink)' },
  { bg: 'var(--dk-avatar-5-bg)', ink: 'var(--dk-avatar-5-ink)' },
  { bg: 'var(--dk-avatar-6-bg)', ink: 'var(--dk-avatar-6-ink)' },
]
function avatarStil(name) {
  const n = String(name || 'U').trim()
  const summe = (n.charCodeAt(0) || 85) + (n.length > 1 ? n.charCodeAt(n.length - 1) : 0)
  const paar = AVATAR_PAARE[summe % AVATAR_PAARE.length]
  return { background: paar.bg, color: paar.ink }
}

function goToKalender() {
  navigate('#/kalender')
}
</script>

<style scoped>
.dk-sidebar--moderation {
  /* Same base styles as dk-sidebar, inherited from global */
}

/* Mobile: hide sidebar (same pattern as KronosSidebar / AppSidebar) */
@media (max-width: 768px) {
  .dk-sidebar--moderation {
    display: none;
  }
}
</style>
