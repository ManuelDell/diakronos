<template>
  <!-- Nur auf Touch/Mobile sichtbar (via CSS) -->
  <nav class="dk-bottom-nav" :class="{ 'is-kronos': isKronosMode }">

    <!-- Haupttabs -->
    <a class="dk-bn-tab" href="#/" :class="{ active: page === 'Home' }" @click="closeMore">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" :stroke="page === 'Home' ? 'currentColor' : 'currentColor'" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
        <polyline points="9 22 9 12 15 12 15 22"/>
      </svg>
      <span>Dashboard</span>
    </a>

    <a class="dk-bn-tab" href="#/kalender" :class="{ active: page === 'Kalender' }" @click="closeMore">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
        <line x1="16" y1="2" x2="16" y2="6"/>
        <line x1="8" y1="2" x2="8" y2="6"/>
        <line x1="3" y1="10" x2="21" y2="10"/>
      </svg>
      <span>Kalender</span>
    </a>

    <a class="dk-bn-tab" href="#/ressourcen" :class="{ active: page === 'Ressourcen' }" @click="closeMore">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
        <polyline points="3.27 6.96 12 12.01 20.73 6.96"/>
        <line x1="12" y1="22.08" x2="12" y2="12"/>
      </svg>
      <span>Ressourcen</span>
    </a>

    <a class="dk-bn-tab" href="#/profile" :class="{ active: page === 'Profile' }" @click="closeMore">
      <div class="dk-bn-avatar" :style="{ background: avatarColor }">{{ initials }}</div>
      <span>Profil</span>
    </a>

    <button class="dk-bn-tab" :class="{ active: showMore }" @click.stop="toggleMore">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>
      </svg>
      <span>Mehr</span>
    </button>

  </nav>

  <!-- Slide-up Sheet -->
  <Teleport to="body">
    <Transition name="sheet">
      <div v-if="showMore" class="dk-bn-sheet-overlay" @click.self="closeMore">
        <div class="dk-bn-sheet">
          <div class="dk-bn-sheet-handle"></div>
          <div class="dk-bn-sheet-title">Navigation</div>

          <div class="dk-bn-sheet-grid">
            <template v-if="!isGast">
              <a class="dk-bn-sheet-item" href="#/mitglieder" @click="closeMore">
                <div class="dk-bn-sheet-icon">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
                </div>
                <span>Mitglieder</span>
              </a>
              <a class="dk-bn-sheet-item" href="#/gruppen" @click="closeMore">
                <div class="dk-bn-sheet-icon">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
                </div>
                <span>Gruppen</span>
              </a>
              <a class="dk-bn-sheet-item" href="#/adressbuch" @click="closeMore">
                <div class="dk-bn-sheet-icon">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>
                </div>
                <span>Adressbuch</span>
              </a>
              <a class="dk-bn-sheet-item" href="#/dienstplan" @click="closeMore">
                <div class="dk-bn-sheet-icon">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                </div>
                <span>Dienstplan</span>
              </a>
              <a class="dk-bn-sheet-item" href="#/beitraege" @click="closeMore">
                <div class="dk-bn-sheet-icon">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
                </div>
                <span>Beiträge</span>
              </a>
              <a class="dk-bn-sheet-item" href="#/wiki" @click="closeMore">
                <div class="dk-bn-sheet-icon">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                </div>
                <span>Wiki</span>
              </a>
            </template>

            <template v-if="isAdmin">
              <a class="dk-bn-sheet-item" href="#/registrierung" @click="closeMore">
                <div class="dk-bn-sheet-icon dk-bn-sheet-icon--badge">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/><rect x="9" y="3" width="6" height="4" rx="1" ry="1"/></svg>
                </div>
                <span>Registrierung</span>
              </a>
              <a class="dk-bn-sheet-item" href="#/statistik" @click="closeMore">
                <div class="dk-bn-sheet-icon">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
                </div>
                <span>Statistik</span>
              </a>
              <a class="dk-bn-sheet-item" href="#/organigramm" @click="closeMore">
                <div class="dk-bn-sheet-icon">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="6" y1="3" x2="6" y2="15"/><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M18 9a9 9 0 0 1-9 9"/></svg>
                </div>
                <span>Organigramm</span>
              </a>
              <a class="dk-bn-sheet-item" href="#/moderation" @click="closeMore">
                <div class="dk-bn-sheet-icon">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z"/><path d="M4 5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1h-4a1 1 0 0 1-1-1l0-4"/><path d="M14 5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1h-4a1 1 0 0 1-1-1l0-4"/><path d="M4 15a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1h-4a1 1 0 0 1-1-1l0-4"/><path d="M14 17h6m-3-3v6"/></svg>
                </div>
                <span>Moderation</span>
              </a>
            </template>
          </div>

        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, computed } from 'vue'
import { currentPageName, currentHash, navigate } from '../router.js'
import { useSession } from '../composables/useSession.js'

const { user, mitglied, isAdmin } = useSession()

const props = defineProps({ isKronosMode: Boolean })
const emit = defineEmits([])

const page = currentPageName
const showMore = ref(false)

const isGast = computed(() => !isAdmin.value && mitglied.value?.status === 'Gast')

const COLORS = ['#3e4d78', '#1c2850', '#6e7ca6', '#d4a24c', '#8B5E3C']
const initials = computed(() => {
  const v = user.value?.fullname || ''
  return v.split(' ').map(x => x[0]).join('').toUpperCase().slice(0, 2) || 'U'
})
const avatarColor = computed(() => {
  const idx = (user.value?.fullname || 'U').charCodeAt(0) % COLORS.length
  return COLORS[idx]
})

function toggleMore() { showMore.value = !showMore.value }
function closeMore() { showMore.value = false }
</script>

<style scoped>
/* Bottom Nav — nur auf Touch/Mobile */
.dk-bottom-nav {
  display: none;
  position: fixed;
  bottom: 0; left: 0; right: 0;
  height: calc(64px + env(safe-area-inset-bottom));
  padding-bottom: env(safe-area-inset-bottom);
  background: var(--dk-surface);
  border-top: 1px solid var(--dk-border);
  z-index: 200;
  flex-direction: row;
  align-items: stretch;
}
@media (hover: none) and (pointer: coarse) {
  .dk-bottom-nav { display: flex; }
}

/* Tabs */
.dk-bn-tab {
  flex: 1;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 3px;
  text-decoration: none;
  color: var(--dk-text-muted);
  font-size: 10px; font-weight: 500;
  background: none; border: none; cursor: pointer;
  padding: 0;
  transition: color 0.15s;
  -webkit-tap-highlight-color: transparent;
}
.dk-bn-tab.active { color: var(--dk-brand-500, #1c2850); }
.dk-bn-tab svg { flex-shrink: 0; }

/* Avatar mini */
.dk-bn-avatar {
  width: 22px; height: 22px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 9px; font-weight: 700; color: #fff; flex-shrink: 0;
}

/* Slide-up sheet */
.dk-bn-sheet-overlay {
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.4);
  z-index: 300;
  display: flex; flex-direction: column; justify-content: flex-end;
}
.dk-bn-sheet {
  background: var(--dk-surface);
  border-radius: 16px 16px 0 0;
  padding-bottom: calc(16px + env(safe-area-inset-bottom));
  max-height: 80vh;
  overflow-y: auto;
}
.dk-bn-sheet-handle {
  width: 36px; height: 4px; border-radius: 2px;
  background: var(--dk-border);
  margin: 12px auto 8px;
}
.dk-bn-sheet-title {
  font-size: 12px; font-weight: 600;
  color: var(--dk-text-muted);
  text-transform: uppercase; letter-spacing: 0.5px;
  padding: 4px 20px 12px;
}
.dk-bn-sheet-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 4px;
  padding: 0 12px;
}
.dk-bn-sheet-item {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 6px; padding: 14px 8px;
  border-radius: 12px;
  text-decoration: none;
  color: var(--dk-text);
  font-size: 12px; font-weight: 500;
  background: none;
  transition: background 0.15s;
  -webkit-tap-highlight-color: transparent;
}
.dk-bn-sheet-item:active { background: var(--dk-surface-2); }
.dk-bn-sheet-icon {
  width: 44px; height: 44px; border-radius: 12px;
  background: var(--dk-surface-2);
  display: flex; align-items: center; justify-content: center;
  color: var(--dk-text);
}
.dk-bn-sheet-footer {
  padding: 12px 16px 0;
  border-top: 1px solid var(--dk-border);
  margin-top: 8px;
}
/* Sheet transition */
.sheet-enter-active, .sheet-leave-active { transition: opacity 0.2s; }
.sheet-enter-active .dk-bn-sheet, .sheet-leave-active .dk-bn-sheet {
  transition: transform 0.25s cubic-bezier(0.32, 0.72, 0, 1);
}
.sheet-enter-from, .sheet-leave-to { opacity: 0; }
.sheet-enter-from .dk-bn-sheet, .sheet-leave-to .dk-bn-sheet {
  transform: translateY(100%);
}
</style>
