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
      <span class="current-date">{{ shortTitle || 'Lade...' }}<span class="date-year"> {{ yearPart }}</span></span>
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

      <a
        v-if="canModerate"
        class="moderation-btn"
        href="#/moderation"
        title="Terminmoderation öffnen"
      >
        <span v-html="ICON_MODERATION"></span>
        <span class="moderation-btn-label">Moderation</span>
      </a>
    </div>
  </header>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue';

const props = defineProps({
  dateTitle: { type: String, default: '' },
  currentView: { type: String, default: 'dayGridMonth' },
  viewMode: { type: String, default: 'view' },
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
const shortTitle = computed(() => {
  return (props.dateTitle || '').replace(/\s+\d{4}(\s|$)/g, ' ').trim()
})
const yearPart = computed(() => {
  const m = (props.dateTitle || '').match(/\d{4}/)
  return m ? m[0] : ''
})
const lastNormalView = ref('dayGridMonth');
const isResourceView = computed(() => RESOURCE_VIEWS.has(props.currentView));

const canModerate = ref(false);

const ICON_CHEVRON_LEFT = `<svg xmlns=http://www.w3.org/2000/svg viewBox=0 0 24 24 width=23 height=23 fill=none stroke=currentColor stroke-width=2 stroke-linecap=round stroke-linejoin=round><path stroke=none d=M0 0h24v24H0z/><path d=M15 6l-6 6l6 6/></svg>`;
const ICON_CHEVRON_RIGHT = `<svg xmlns=http://www.w3.org/2000/svg viewBox=0 0 24 24 width=23 height=23 fill=none stroke=currentColor stroke-width=2 stroke-linecap=round stroke-linejoin=round><path stroke=none d=M0 0h24v24H0z/><path d=M9 6l6 6l-6 6/></svg>`;
const ICON_EYE = `<svg xmlns=http://www.w3.org/2000/svg viewBox=0 0 24 24 width=20 height=20 fill=none stroke=currentColor stroke-width=1.5 stroke-linecap=round stroke-linejoin=round><path stroke=none d=M0 0h24v24H0z/><path d=M10 12a2 2 0 1 0 4 0a2 2 0 0 0-4 0/><path d=M21 12c-2.4 4-5.4 6-9 6c-3.6 0-6.6-2-9-6c2.4-4 5.4-6 9-6c3.6 0 6.6 2 9 6/></svg>`;
const ICON_PENCIL = `<svg xmlns=http://www.w3.org/2000/svg viewBox=0 0 24 24 width=20 height=20 fill=none stroke=currentColor stroke-width=1.5 stroke-linecap=round stroke-linejoin=round><path stroke=none d=M0 0h24v24H0z/><path d=M4 20h4l10.5-10.5a2.828 2.828 0 1 0-4-4l-10.5 10.5v4/><path d=M13.5 6.5l4 4/></svg>`;
const ICON_ROOM_VIEW = `<svg xmlns=http://www.w3.org/2000/svg viewBox=0 0 24 24 width=16 height=16 fill=none stroke=currentColor stroke-width=2 stroke-linecap=round stroke-linejoin=round><path stroke=none d=M0 0h24v24H0z/><path d=M4 6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-12a2 2 0 0 1-2-2l0-12/><path d=M12 4l0 16/></svg>`;
const ICON_MODERATION = `<svg xmlns=http://www.w3.org/2000/svg viewBox=0 0 24 24 width=16 height=16 fill=none stroke=currentColor stroke-width=2 stroke-linecap=round stroke-linejoin=round><path stroke=none d=M0 0h24v24H0z/><path d=M4 5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1h-4a1 1 0 0 1-1-1l0-4/><path d=M14 5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1h-4a1 1 0 0 1-1-1l0-4/><path d=M4 15a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1h-4a1 1 0 0 1-1-1l0-4/><path d=M14 17h6m-3-3v6/></svg>`;

watch(() => props.currentView, (newVal) => {
  if (!RESOURCE_VIEWS.has(newVal)) {
    displayView.value = newVal;
    lastNormalView.value = newVal;
  }
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

function onKeyDown(e) {
  if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
    e.preventDefault();
    emit('searchOpen');
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
    canModerate.value = userInfo?.can_moderate || false;
  } catch (_) {}
}

onMounted(() => {
  loadDeskLink();
  document.addEventListener('keydown', onKeyDown, { capture: true });
});

onUnmounted(() => {
  document.removeEventListener('keydown', onKeyDown, { capture: true });
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
.moderation-btn {
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
  text-decoration: none;
}
.moderation-btn:hover {
  background: var(--dk-surface-2, #f3f4f6);
}
@media (hover: none) and (pointer: coarse) {
  .moderation-btn-label { display: none; }
}
</style>
<style scoped>
@media (hover: none) and (pointer: coarse) {
  .date-year { display: none; }
  .resource-toggle-btn { display: none; }
  .view-dropdown { font-size: 11px; padding: 4px 6px; }
}
</style>
