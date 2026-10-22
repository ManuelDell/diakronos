<template>
  <header class="kronos-header">
    <div class="header-left">
      <!-- UXK-R9: Am Handy liegt die Kalender-Seitenleiste (Kalenderliste,
           CalDAV-Anleitung, Import) dauerhaft ausserhalb des Bildes. Dieser
           Knopf oeffnet sie — nur auf schmalen Bildschirmen sichtbar. -->
      <DkButton
        class="sidebar-toggle-btn"
        variant="secondary"
        size="sm"
        aria-label="Meine Kalender und Hilfe anzeigen"
        title="Meine Kalender"
        @click="$emit('sidebarToggle')"
      >
        <span class="icon-menu" v-html="ICON_MENU"></span>
      </DkButton>
      <DkButton class="todaybutton" variant="secondary" size="sm" aria-label="Zum heutigen Tag springen" title="Heute" @click="$emit('today')">
        <span class="today-label">Heute</span>
        <span class="icon-calendar-today" v-html="ICON_CALENDAR_TODAY"></span>
      </DkButton>
    </div>

    <div class="header-center">
      <DkButton class="nav-btn prev-month" variant="secondary" size="sm" aria-label="Vorheriger Monat" @click="$emit('prev')">
        <span class="icon-chevron" v-html="ICON_CHEVRON_LEFT"></span>
      </DkButton>
      <DkButton class="nav-btn next-month" variant="secondary" size="sm" aria-label="Nächster Monat" @click="$emit('next')">
        <span class="icon-chevron" v-html="ICON_CHEVRON_RIGHT"></span>
      </DkButton>
      <span class="current-date">{{ shortTitle || 'Lade...' }}<span v-if="yearPart" class="date-year">&nbsp;{{ yearPart }}</span></span>
    </div>

    <div class="header-right">
      <DkButton
        id="resource-toggle-btn"
        class="resource-toggle-btn"
        :variant="isResourceView ? 'primary' : 'secondary'"
        size="sm"
        :aria-pressed="isResourceView ? 'true' : 'false'"
        aria-label="Ressourcenplan anzeigen"
        title="Ressourcenplan"
        @click="onResourceToggle"
      >
        <span v-html="ICON_ROOM_VIEW"></span>
        <span class="resource-btn-label">Ressourcenplan</span>
      </DkButton>

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

      <div v-if="canWrite" class="toggle-container" data-toggle-group="edit-mode" aria-label="Bearbeitungs- / Ansichtsmodus">
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
      <span v-else class="readonly-hinweis" title="Du kannst Termine nur lesen">
        <span v-html="ICON_EYE"></span>
        <span class="readonly-label">Nur lesen</span>
      </span>

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
import { apiAntwortPruefen } from '../../composables/useApi.js'
import { ref, computed, watch, onMounted } from 'vue';
import DkButton from '../ui/DkButton.vue';

const props = defineProps({
  dateTitle: { type: String, default: '' },
  currentView: { type: String, default: 'dayGridMonth' },
  viewMode: { type: String, default: 'view' },
  canWrite: { type: Boolean, default: true },
});

const emit = defineEmits([
  'prev', 'next', 'today', 'viewChange', 'resourceToggle',
  'viewModeChange', 'sidebarToggle'
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
  // Monatsteil ohne Jahr, egal ob die Quelle „Oktober 2026“ oder „Oktober2026“ liefert.
  return (props.dateTitle || '').replace(/\s*\d{4}\s*$/g, '').trim()
})
const yearPart = computed(() => {
  const m = (props.dateTitle || '').match(/\d{4}(?!.*\d{4})/)
  return m ? m[0] : ''
})
const lastNormalView = ref('dayGridMonth');
const isResourceView = computed(() => RESOURCE_VIEWS.has(props.currentView));

const canModerate = ref(false);

const ICON_CHEVRON_LEFT = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="23" height="23" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z"/><path d="M15 6l-6 6l6 6"/></svg>`;
const ICON_CHEVRON_RIGHT = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="23" height="23" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z"/><path d="M9 6l6 6l-6 6"/></svg>`;
const ICON_EYE = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z"/><path d="M10 12a2 2 0 1 0 4 0a2 2 0 0 0-4 0"/><path d="M21 12c-2.4 4-5.4 6-9 6c-3.6 0-6.6-2-9-6c2.4-4 5.4-6 9-6c3.6 0 6.6 2 9 6"/></svg>`;
const ICON_PENCIL = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z"/><path d="M4 20h4l10.5-10.5a2.828 2.828 0 1 0-4-4l-10.5 10.5v4"/><path d="M13.5 6.5l4 4"/></svg>`;
const ICON_ROOM_VIEW = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z"/><path d="M4 6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-12a2 2 0 0 1-2-2l0-12"/><path d="M12 4l0 16"/></svg>`;
const ICON_MODERATION = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z"/><path d="M4 5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1h-4a1 1 0 0 1-1-1l0-4"/><path d="M14 5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1h-4a1 1 0 0 1-1-1l0-4"/><path d="M4 15a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1h-4a1 1 0 0 1-1-1l0-4"/><path d="M14 17h6m-3-3v6"/></svg>`;
const ICON_MENU = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z"/><line x1="4" y1="6" x2="20" y2="6"/><line x1="4" y1="12" x2="20" y2="12"/><line x1="4" y1="18" x2="20" y2="18"/></svg>`;
const ICON_CALENDAR_TODAY = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z"/><rect x="4" y="5" width="16" height="16" rx="2"/><line x1="16" y1="3" x2="16" y2="7"/><line x1="8" y1="3" x2="8" y2="7"/><line x1="4" y1="11" x2="20" y2="11"/><line x1="8" y1="16" x2="8.01" y2="16"/></svg>`;

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

// UXK-R16: Der frühere Strg+F-Handler fing die Browsersuche ab, öffnete aber
// nichts. Entfernt — die normale Browsersuche funktioniert dadurch wieder.
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
    const { message: userInfo } = await apiAntwortPruefen(res);
    canModerate.value = userInfo?.can_moderate || false;
  } catch (_) {}
}

onMounted(() => {
  loadDeskLink();
});
</script>

<style scoped>
.kronos-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: var(--topbar-h);
  padding: 8px var(--sp-4);
  background: var(--surface);
  border-bottom: 1px solid var(--line);
  gap: var(--gap);
  /* UXK-008: Auf schmalen Bildschirmen darf die Kopfzeile nicht aus dem
     Fenster laufen — die Umbruchfaehigkeit ist die Grundlage dafuer, dass
     Stift und „Moderation“ am Handy erreichbar bleiben. */
  flex-wrap: wrap;
}
.header-left,
.header-center,
.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
  /* min-width:0 erlaubt es den Flexkindern zu schrumpfen statt die Zeile zu
     sprengen (Vorbedingung fuer den Umbruch). */
  min-width: 0;
}
.header-center {
  flex: 1;
  justify-content: center;
}
/* UXK-R9: Der Umschalter fuer die Kalender-Seitenleiste wird nur am Handy
   gebraucht; am Desktop ist die Leiste ohnehin sichtbar. */
.sidebar-toggle-btn { display: none; }
.icon-calendar-today { display: none; }
.nav-btn {
  padding: 0;
  width: 32px;
}
.icon-chevron {
  display: inline-flex;
  align-items: center;
}
.current-date {
  font-size: var(--fs-h3);
  font-weight: 600;
  min-width: 0;   /* UXK-008: vorher 120px — sprengte die Zeile am Handy */
  text-align: center;
  color: var(--text);
}
.resource-toggle-btn {
  gap: 6px;
}
.view-dropdown {
  height: var(--control-h);
  padding: 0 24px 0 10px;
  font-size: 13px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--surface);
  cursor: pointer;
  color: var(--text);
}
.toggle-container {
  display: inline-flex;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  overflow: hidden;
}
.toggle-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: var(--control-h);
  background: var(--surface);
  border: none;
  cursor: pointer;
  color: var(--muted);
}
.toggle-btn.active {
  background: var(--primary);
  color: var(--primary-ink);
}
.moderation-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: var(--control-h);
  padding: 0 10px;
  font-size: 13px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--surface);
  cursor: pointer;
  color: var(--text);
  text-decoration: none;
}
.moderation-btn:hover {
  background: var(--surface-hover);
}
.readonly-hinweis {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: var(--control-h);
  padding: 0 10px;
  font-size: 13px;
  color: var(--muted);
  border: 1px dashed var(--line);
  border-radius: var(--radius);
}
@media (hover: none) and (pointer: coarse) {
  .moderation-btn-label { display: none; }
}

/* UXK-008: Auf schmalen Bildschirmen umbrechen Kopfzeile und Bedienelemente
   so, dass Auswahl-Umschalter, Stift „Bearbeiten“ und „Moderation“ im Bild
   bleiben. „Heute“ wird zum Symbol, die Datumsanzeige darf schrumpfen. */
@media (max-width: 768px) {
  .kronos-header {
    /* Zwei Zeilen: oben Navigation/Datum, unten die Bedienelemente. */
    row-gap: 6px;
  }
  .header-left { order: 1; }
  .header-center { order: 2; flex: 1 1 auto; }
  .header-right {
    order: 3;
    flex: 1 0 100%;       /* volle Breite -> eigene Zeile unter dem Datum */
    justify-content: flex-end;
    flex-wrap: wrap;
    row-gap: 6px;
  }
  .sidebar-toggle-btn { display: inline-flex; }
  .today-label { display: none; }
  .icon-calendar-today { display: inline-flex; align-items: center; }
  .current-date {
    font-size: var(--fs);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
}

</style>
<style scoped>
@media (hover: none) and (pointer: coarse) {
  .date-year { display: none; }
  .resource-toggle-btn { display: none; }
  .view-dropdown { font-size: var(--fs-xs); padding: 4px 6px; }
}
</style>
