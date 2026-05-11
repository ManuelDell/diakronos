<template>
  <header class="kronos-header">
    <div class="header-left">
      <button class="todaybutton" aria-label="Zum heutigen Tag springen" @click="$emit('today')">
        Heute
      </button>
    </div>

    <div class="header-center">
      <button class="nav-btn prev-month" aria-label="Vorheriger Monat" @click="$emit('prev')">
        <span class="icon-chevron" v-html="ICON_CHEVRON_LEFT"></span>
      </button>
      <button class="nav-btn next-month" aria-label="Nächster Monat" @click="$emit('next')">
        <span class="icon-chevron" v-html="ICON_CHEVRON_RIGHT"></span>
      </button>
      <span class="current-date">{{ dateTitle || 'Lade...' }}</span>
    </div>

    <div class="header-right">
      <button
        id="resource-toggle-btn"
        class="resource-toggle-btn"
        :class="{ active: isResourceView }"
        :aria-pressed="isResourceView ? 'true' : 'false'"
        aria-label="Ressourcenplan anzeigen"
        title="Ressourcenplan"
        @click="onResourceToggle"
      >
        <span v-html="ICON_ROOM_VIEW"></span>
        <span class="resource-btn-label">Ressourcenplan</span>
      </button>

      <select
        id="view-selector"
        class="view-dropdown"
        aria-label="Ansicht wählen"
        :value="displayView"
        @change="onViewChange"
      >
        <option value="dayGridMonth">Monat</option>
        <option value="timeGridWeek">Woche</option>
        <option value="timeGridDay">Tag</option>
        <option value="listMonth">Liste</option>
      </select>

      <div class="toggle-container" data-toggle-group="edit-mode" aria-label="Bearbeitungs- / Ansichtsmodus">
        <button
          class="toggle-btn toggle-left"
          :class="{ active: viewMode === 'view' }"
          aria-label="Ansichtsmodus"
          title="Nur anzeigen"
          @click="$emit('viewModeChange', 'view')"
        >
          <span v-html="ICON_EYE"></span>
        </button>
        <button
          class="toggle-btn toggle-right"
          :class="{ active: viewMode === 'edit' }"
          aria-label="Bearbeitungsmodus"
          title="Termine verschieben / bearbeiten"
          @click="$emit('viewModeChange', 'edit')"
        >
          <span v-html="ICON_PENCIL"></span>
        </button>
      </div>

      <div class="profile-menu-wrapper">
        <div ref="avatarRef" class="profile-avatar" :title="userFullname" @click.stop="toggleDropdown">
          <img
            v-if="userImage && !imgError"
            :src="userImage"
            :alt="userFullname"
            style="width:100%;height:100%;object-fit:cover;border-radius:50%;"
            @error="imgError = true"
          />
          <span v-else>{{ userInitial }}</span>
        </div>
        <div
          v-show="dropdownOpen"
          ref="dropdownRef"
          class="profile-dropdown"
        >
          <a v-if="canAccessDesk" class="profile-dropdown-item" href="/app">
            <span v-html="ICON_DASHBOARD"></span> Zurück zum Desk
          </a>
          <a v-if="canModerate" class="profile-dropdown-item" href="/kronos/moderation">
            <span v-html="ICON_MODERATION"></span> Terminmoderation
          </a>
          <button class="profile-dropdown-item" @click="openSearch">
            <span v-html="ICON_SEARCH"></span> Suche
          </button>
          <button class="profile-dropdown-item profile-dropdown-logout" @click="doLogout">
            <span v-html="ICON_LOGOUT"></span> Abmelden
          </button>
        </div>
      </div>
    </div>
  </header>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue';

const props = defineProps({
  dateTitle: { type: String, default: '' },
  currentView: { type: String, default: 'dayGridMonth' },
  viewMode: { type: String, default: 'view' },
  userInitial: { type: String, default: '?' },
  userFullname: { type: String, default: '' },
  userImage: { type: String, default: '' }
});

const emit = defineEmits([
  'prev', 'next', 'today', 'viewChange', 'resourceToggle',
  'viewModeChange', 'sidebarToggle', 'searchOpen'
]);

const RESOURCE_VIEW_MAP = {
  dayGridMonth: 'resourceTimelineMonth',
  timeGridWeek: 'resourceTimelineWeek',
  timeGridDay:  'resourceTimelineDay',
  listMonth:    'resourceTimelineWeek',
};
const RESOURCE_VIEWS = new Set(Object.values(RESOURCE_VIEW_MAP));

const displayView = ref('dayGridMonth');
const lastNormalView = ref('dayGridMonth');
const isResourceView = computed(() => RESOURCE_VIEWS.has(props.currentView));

const dropdownOpen = ref(false);
const avatarRef = ref(null);
const dropdownRef = ref(null);
const imgError = ref(false);
const canAccessDesk = ref(false);
const canModerate = ref(false);

const ICON_CHEVRON_LEFT = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="23" height="23" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z"/><path d="M15 6l-6 6l6 6"/></svg>`;
const ICON_CHEVRON_RIGHT = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="23" height="23" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z"/><path d="M9 6l6 6l-6 6"/></svg>`;
const ICON_EYE = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z"/><path d="M10 12a2 2 0 1 0 4 0a2 2 0 0 0-4 0"/><path d="M21 12c-2.4 4-5.4 6-9 6c-3.6 0-6.6-2-9-6c2.4-4 5.4-6 9-6c3.6 0 6.6 2 9 6"/></svg>`;
const ICON_PENCIL = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z"/><path d="M4 20h4l10.5-10.5a2.828 2.828 0 1 0-4-4l-10.5 10.5v4"/><path d="M13.5 6.5l4 4"/></svg>`;
const ICON_ROOM_VIEW = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z"/><path d="M4 6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-12a2 2 0 0 1-2-2l0-12"/><path d="M12 4l0 16"/></svg>`;
const ICON_LOGOUT = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z"/><path d="M14 8v-2a2 2 0 0 0-2-2h-7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h7a2 2 0 0 0 2-2v-2"/><path d="M9 12h12l-3-3"/><path d="M18 15l3-3"/></svg>`;
const ICON_DASHBOARD = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z"/><path d="M5 4h4a1 1 0 0 1 1 1v6a1 1 0 0 1-1 1h-4a1 1 0 0 1-1-1v-6a1 1 0 0 1 1-1"/><path d="M5 16h4a1 1 0 0 1 1 1v2a1 1 0 0 1-1 1h-4a1 1 0 0 1-1-1v-2a1 1 0 0 1 1-1"/><path d="M15 12h4a1 1 0 0 1 1 1v6a1 1 0 0 1-1 1h-4a1 1 0 0 1-1-1v-6a1 1 0 0 1 1-1"/><path d="M15 4h4a1 1 0 0 1 1 1v2a1 1 0 0 1-1 1h-4a1 1 0 0 1-1-1v-2a1 1 0 0 1 1-1"/></svg>`;
const ICON_MODERATION = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z"/><path d="M4 5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1h-4a1 1 0 0 1-1-1l0-4"/><path d="M14 5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1h-4a1 1 0 0 1-1-1l0-4"/><path d="M4 15a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1h-4a1 1 0 0 1-1-1l0-4"/><path d="M14 17h6m-3-3v6"/></svg>`;
const ICON_SEARCH = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z"/><path d="M3 10a7 7 0 1 0 14 0a7 7 0 1 0-14 0"/><path d="M21 21l-6-6"/></svg>`;

watch(() => props.currentView, (newVal) => {
  if (!RESOURCE_VIEWS.has(newVal)) {
    displayView.value = newVal;
    lastNormalView.value = newVal;
  }
});

watch(() => props.userImage, () => {
  imgError.value = false;
});

function onViewChange(e) {
  const val = e.target.value;
  lastNormalView.value = val;
  emit('viewChange', val);
}

function onResourceToggle() {
  if (isResourceView.value) {
    emit('viewChange', lastNormalView.value);
  } else {
    lastNormalView.value = displayView.value;
    const resourceView = RESOURCE_VIEW_MAP[displayView.value] || 'resourceTimelineWeek';
    emit('viewChange', resourceView);
  }
}

function toggleDropdown() {
  dropdownOpen.value = !dropdownOpen.value;
  if (dropdownOpen.value) {
    nextTick(positionDropdown);
  }
}

function positionDropdown() {
  if (!avatarRef.value || !dropdownRef.value) return;
  const rect = avatarRef.value.getBoundingClientRect();
  const dd = dropdownRef.value;
  dd.style.position = 'fixed';
  dd.style.top = (rect.bottom + 8) + 'px';
  dd.style.right = (window.innerWidth - rect.right) + 'px';
  dd.style.left = '';
}

function closeDropdown() {
  dropdownOpen.value = false;
}

function openSearch() {
  dropdownOpen.value = false;
  emit('searchOpen');
}

async function doLogout() {
  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
  try {
    await fetch('/api/method/logout', {
      method: 'POST',
      headers: { 'X-Frappe-CSRF-Token': csrfToken },
      credentials: 'include'
    });
  } finally {
    window.location.href = '/login';
  }
}

async function loadDeskLink() {
  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
  if (!csrfToken) return;
  try {
    const res = await fetch('/api/method/diakronos.kronos.api.permissions.get_session_info', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': csrfToken },
      credentials: 'include',
      body: JSON.stringify({})
    });
    if (!res.ok) return;
    const { message: userInfo } = await res.json();
    canAccessDesk.value = userInfo?.can_access_desk || false;
    canModerate.value = userInfo?.can_moderate || false;
  } catch (_) {}
}

function onKeyDown(e) {
  if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
    e.preventDefault();
    emit('searchOpen');
  }
}

onMounted(() => {
  loadDeskLink();
  document.addEventListener('keydown', onKeyDown, { capture: true });
  document.addEventListener('click', closeDropdown);
});

onUnmounted(() => {
  document.removeEventListener('keydown', onKeyDown, { capture: true });
  document.removeEventListener('click', closeDropdown);
});
</script>

<style scoped>
.kronos-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 56px;
  padding: 0 16px;
  background: var(--dk-surface, #fff);
  border-bottom: 1px solid var(--dk-border, #e5e7eb);
  gap: 12px;
}
.header-left,
.header-center,
.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
}
.header-center {
  flex: 1;
  justify-content: center;
}
.hamburger {
  display: flex;
  flex-direction: column;
  gap: 4px;
  background: none;
  border: none;
  cursor: pointer;
  padding: 6px;
}
.hamburger .line {
  display: block;
  width: 20px;
  height: 2px;
  background: var(--dk-text, #111);
  border-radius: 1px;
}
.todaybutton {
  padding: 6px 12px;
  font-size: 13px;
  font-weight: 500;
  border: 1px solid var(--dk-border, #e5e7eb);
  border-radius: 6px;
  background: var(--dk-surface, #fff);
  cursor: pointer;
  color: var(--dk-text, #111);
}
.nav-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  background: none;
  border: 1px solid var(--dk-border, #e5e7eb);
  border-radius: 6px;
  cursor: pointer;
  color: var(--dk-text, #111);
}
.icon-chevron {
  display: inline-flex;
  align-items: center;
}
.current-date {
  font-size: 16px;
  font-weight: 600;
  min-width: 120px;
  text-align: center;
  color: var(--dk-text, #111);
}
.resource-toggle-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  font-size: 13px;
  border: 1px solid var(--dk-border, #e5e7eb);
  border-radius: 6px;
  background: var(--dk-surface, #fff);
  cursor: pointer;
  color: var(--dk-text, #111);
}
.resource-toggle-btn.active {
  background: var(--dk-btn-primary, #3b82f6);
  color: #fff;
  border-color: var(--dk-btn-primary, #3b82f6);
}
.view-dropdown {
  padding: 6px 24px 6px 10px;
  font-size: 13px;
  border: 1px solid var(--dk-border, #e5e7eb);
  border-radius: 6px;
  background: var(--dk-surface, #fff);
  cursor: pointer;
  color: var(--dk-text, #111);
}
.toggle-container {
  display: inline-flex;
  border: 1px solid var(--dk-border, #e5e7eb);
  border-radius: 6px;
  overflow: hidden;
}
.toggle-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 32px;
  background: var(--dk-surface, #fff);
  border: none;
  cursor: pointer;
  color: var(--dk-text-muted, #6b7280);
}
.toggle-btn.active {
  background: var(--dk-btn-primary, #3b82f6);
  color: #fff;
}
.profile-menu-wrapper {
  position: relative;
}
.profile-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--dk-surface-2, #f3f4f6);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  color: var(--dk-text, #111);
  user-select: none;
}
.profile-dropdown {
  position: fixed;
  background: var(--dk-surface, #fff);
  border: 1px solid var(--dk-border, #e5e7eb);
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
  padding: 6px;
  min-width: 180px;
  z-index: 2000;
}
.profile-dropdown-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 10px;
  font-size: 13px;
  color: var(--dk-text, #111);
  background: none;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  text-decoration: none;
}
.profile-dropdown-item:hover {
  background: var(--dk-surface-2, #f3f4f6);
}
</style>
