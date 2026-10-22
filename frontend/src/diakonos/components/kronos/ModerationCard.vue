<template>
  <a
    class="dk-mcard"
    :class="{
      'dk-mcard--konflikt': isKonflikt,
      'dk-mcard--serie': item.type === 'serie',
    }"
    :data-id="item.id"
    :data-type="item.type || 'event'"
    href="#"
    :aria-label="'Termin „' + (item.title || 'ohne Titel') + '“ pruefen'"
    @click.prevent="$emit('click', item)"
  >
    <!-- Color strip -->
    <div class="dk-mcard-strip" :style="{ background: sichereFarbe(item.calendar_color) }"></div>

    <div class="dk-mcard-body">
      <!-- Header row -->
      <div class="dk-mcard-header">
        <span class="dk-mcard-title">{{ item.title }}</span>

        <!-- Serie badge -->
        <DkBadge v-if="item.type === 'serie'" variant="neutral" class="dk-mcard-badge">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/></svg>
          {{ item.count }} Termine
        </DkBadge>

        <!-- Konflikt badge -->
        <DkBadge v-if="isKonflikt" variant="err" class="dk-mcard-badge">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
          Konflikt
        </DkBadge>

        <!-- P1-5b (W-1): Abgelehnt-Kennzeichnung in der Historie-Spalte -->
        <DkBadge v-if="column === 'abgelehnt'" variant="neutral" class="dk-mcard-badge">
          Abgelehnt
        </DkBadge>

        <!-- Remove button (Festlegen column only) -->
        <button
          v-if="inFestlegen"
          class="dk-mcard-remove"
          title="Zurück"
          @click.stop="$emit('remove', item)"
        >×</button>
      </div>

      <!-- Date/time -->
      <div class="dk-mcard-time">{{ formatDate(item) }}</div>

      <!-- Calendar -->
      <div class="dk-mcard-cal">
        <span class="dk-mcard-dot" :style="{ background: sichereFarbe(item.calendar_color) }"></span>
        {{ item.calendar_title }}
      </div>

      <!-- OP-EVENT-12: Antragsteller und Beschreibung auf der Karte -->
      <div v-if="item.antragsteller || item.owner" class="dk-mcard-antragsteller">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
        Antragsteller: {{ item.antragsteller || item.owner }}
      </div>
      <div v-if="item.description" class="dk-mcard-beschreibung">{{ item.description }}</div>

      <!-- P1-5b (W-1): Ablehnungsgrund nur in der Historie-Spalte (Moderatoren) -->
      <div v-if="column === 'abgelehnt' && item.ablehnungs_grund" class="dk-mcard-beschreibung">
        Grund: {{ item.ablehnungs_grund }}
      </div>

      <!-- Ressource -->
      <div v-if="item.ressource" class="dk-mcard-ressource">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/></svg>
        {{ item.ressource }}
      </div>

      <!-- Notification indicator -->
      <div v-if="notification" class="dk-mcard-notif">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
        Bearbeitet von {{ notification.by || 'Unbekannt' }}
      </div>

      <!-- Serie conflict details (collapsible) -->
      <div v-if="item.type === 'serie' && item.konflikt_events?.length && column === 'konflikte'" class="dk-mcard-serie-conflicts">
        <div class="dk-mcard-conflict-toggle" @click.stop="showConflicts = !showConflicts">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
          {{ item.konflikt_events.length }} von {{ item.count }} Terminen haben einen Konflikt
        </div>
        <ul v-if="showConflicts" class="dk-mcard-conflict-list">
          <li
            v-for="ev in item.konflikt_events"
            :key="ev.id"
            class="dk-mcard-conflict-item"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
            {{ fmtDate(ev.start, ev.all_day) }}
            <button class="dk-mcard-resolve-btn" @click.stop="$emit('resolve-conflict', ev)">Auflösen</button>
          </li>
        </ul>
      </div>
    </div>
  </a>
</template>

<script setup>
import { ref, computed } from 'vue'
import DkBadge from '../ui/DkBadge.vue'
import { terminZeitText } from './moderationskarte.js'
// UXD-R28: Kalenderfarbe nur als gueltiger Hex-Wert in den style-String.
import { sichereFarbe } from '../../../shared/sichere-ausgabe.js'

const props = defineProps({
  item: { type: Object, required: true },
  column: { type: String, default: 'vorschlaege' },
  notification: { type: Object, default: null },
})

defineEmits(['click', 'remove', 'resolve-conflict'])

const showConflicts = ref(false)

const isKonflikt = computed(() => {
  if (props.item.type === 'serie') return props.item.has_konflikt
  return props.item.status === 'Konflikt'
})

const inFestlegen = computed(() => props.column === 'festlegen')

function formatDate(item) {
  return terminZeitText(item)
}
</script>

<style scoped>
/* ── Card base ───────────────────────────────────────────────────────────── */
.dk-mcard {
  display: flex;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  overflow: hidden;
  cursor: pointer;
  transition: border-color var(--fast), box-shadow var(--fast);
  /* UXK-006: In der Flex-Spalte (.dk-mboard-col-body) liessen sich die Karten
     zusammendruecken — mobil bis auf 10 px, am Desktop ab ~10 Karten auf 37 px.
     `flex-shrink: 0` haelt die natuerliche Hoehe, die Spalte scrollt stattdessen. */
  flex-shrink: 0;
}
.dk-mcard:hover {
  border-color: var(--line-strong);
  box-shadow: var(--shadow-sm);
}
.dk-mcard--konflikt {
  border-color: color-mix(in oklch, var(--err) 40%, var(--line));
}
.dk-mcard--konflikt:hover {
  border-color: var(--err);
}

/* Strip */
.dk-mcard-strip {
  width: 4px;
  flex-shrink: 0;
}

/* Body */
.dk-mcard-body {
  flex: 1;
  padding: 10px 12px;
  min-width: 0;
}

/* Header */
.dk-mcard-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}
.dk-mcard-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Badges (Fläche/Farbe liefert DkBadge) */
.dk-mcard-badge {
  font-size: var(--fs-xs);
  font-weight: 600;
  flex-shrink: 0;
}

/* Remove button */
.dk-mcard-remove {
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: none;
  color: var(--subtle);
  font-size: 16px;
  cursor: pointer;
  border-radius: var(--radius-sm);
  flex-shrink: 0;
  transition: background var(--fast), color var(--fast);
}
.dk-mcard-remove:hover {
  background: var(--err-soft);
  color: var(--err);
}

/* Time */
.dk-mcard-time {
  font-size: var(--fs-sm);
  color: var(--muted);
  margin-bottom: 3px;
}

/* Calendar */
.dk-mcard-cal {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: var(--fs-xs);
  color: var(--subtle);
}
.dk-mcard-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}

/* Ressource */
.dk-mcard-ressource {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: var(--fs-xs);
  color: var(--subtle);
  margin-top: 3px;
}

/* OP-EVENT-12: Antragsteller + Beschreibung auf der Vorschlagskarte */
.dk-mcard-antragsteller {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: var(--fs-xs);
  color: var(--subtle);
  margin-top: 3px;
}
.dk-mcard-beschreibung {
  font-size: var(--fs-xs);
  color: var(--muted);
  margin-top: 3px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* Notification */
.dk-mcard-notif {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: var(--fs-xs);
  color: var(--info);
  margin-top: 4px;
  padding-top: 4px;
  border-top: 1px solid var(--divider);
}

/* Serie conflict details */
.dk-mcard-serie-conflicts {
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px solid var(--divider);
}
.dk-mcard-conflict-toggle {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: var(--fs-xs);
  color: var(--err);
  cursor: pointer;
  user-select: none;
}
.dk-mcard-conflict-toggle:hover {
  opacity: 0.8;
}
.dk-mcard-conflict-list {
  list-style: none;
  margin: 6px 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.dk-mcard-conflict-item {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: var(--fs-xs);
  color: var(--muted);
  padding: 3px 6px;
  background: var(--err-soft);
  border-radius: var(--radius-sm);
}
.dk-mcard-resolve-btn {
  margin-left: auto;
  padding: 2px 6px;
  font-size: var(--fs-xs);
  font-weight: 500;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  color: var(--text);
  cursor: pointer;
  transition: background var(--fast);
}
.dk-mcard-resolve-btn:hover {
  background: var(--surface-hover);
}
</style>
