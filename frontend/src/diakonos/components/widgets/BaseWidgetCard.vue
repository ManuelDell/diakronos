<template>
  <div
    class="dk-widget-card"
    :class="[
      `dk-widget-${gridSize}`,
      { 'dk-widget-collapsed': collapsed, 'dk-widget-editing': isEditing }
    ]"
  >
    <!-- Header -->
    <div class="dk-widget-header" @click="collapsed && toggleCollapse()">
      <div class="dk-widget-header-left">
        <span v-if="icon" class="dk-widget-icon">{{ icon }}</span>
        <h3 class="dk-widget-title">{{ label }}</h3>
        <span v-if="badgeCount > 0" class="dk-widget-badge">{{ badgeCount }}</span>
      </div>
      <div class="dk-widget-header-actions">
        <!-- UX1d (D3): Hier stand ein „Aktualisieren“-Knopf je Karte. Die Karte
             lädt selbst; wann sie zuletzt geladen hat, sagt jetzt der kleine
             Stand-Hinweis unten in Tertiärfarbe. Im Bearbeiten-Modus bleiben
             die Griffe (verschieben, ein-/ausklappen, ausblenden). -->
        <button
          v-if="isEditing"
          class="dk-widget-action-btn dk-drag-handle"
          title="Verschieben"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="9" cy="5" r="1"/><circle cx="9" cy="12" r="1"/><circle cx="9" cy="19" r="1"/><circle cx="15" cy="5" r="1"/><circle cx="15" cy="12" r="1"/><circle cx="15" cy="19" r="1"/></svg>
        </button>
        <button
          v-if="isEditing"
          class="dk-widget-action-btn"
          :title="collapsed ? 'Aufklappen' : 'Einklappen'"
          @click.stop="toggleCollapse"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline v-if="!collapsed" points="18 15 12 9 6 15"/>
            <polyline v-else points="6 9 12 15 18 9"/>
          </svg>
        </button>
        <button
          v-if="isEditing"
          class="dk-widget-action-btn dk-widget-hide-btn"
          title="Ausblenden"
          @click.stop="$emit('hide')"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
        </button>
      </div>
    </div>

    <!-- Body -->
    <div v-if="!collapsed" class="dk-widget-body">
      <!-- Loading -->
      <div v-if="loading" class="dk-widget-skeleton">
        <div class="dk-skeleton-line" style="width:80%"></div>
        <div class="dk-skeleton-line" style="width:60%"></div>
        <div class="dk-skeleton-line" style="width:70%"></div>
      </div>

      <!-- Error -->
      <div v-else-if="error" class="dk-widget-error">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
        <span>{{ fehlerText }}</span>
        <button class="dk-btn dk-btn-xs" @click="$emit('refresh')">Erneut versuchen</button>
      </div>

      <!-- Empty state -->
      <div v-else-if="isEmpty" class="dk-widget-empty">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
        <p>{{ emptyMessage }}</p>
      </div>

      <!-- Content -->
      <slot v-else />
    </div>

    <!-- UX1d (D3): „Stand hh:mm“ in Tertiärfarbe — der einzige Hinweis auf
         den Ladezeitpunkt, seit der Neuladen-Knopf je Karte entfallen ist
         (Prinzip S2: Information über Helligkeit, nicht über ein Bedienelement).
         Er steht NUR, wenn wirklich geladen wurde; vor dem ersten Ladevorgang
         und im Fehlerfall schwiege er sonst Falsches. -->
    <p v-if="!collapsed && standText" class="dk-widget-stand">{{ standText }}</p>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
// UX2g: eine angezeigte Fehlermeldung statt der Floskel „Fehler beim Laden".
import { fehlertext } from '../../../shared/fehlertexte.js'

const props = defineProps({
  label:        { type: String, required: true },
  icon:         { type: String, default: '' },
  gridSize:     { type: String, default: 'medium' },
  loading:      { type: Boolean, default: false },
  error:        { type: [String, null], default: null },
  isEmpty:      { type: Boolean, default: false },
  emptyMessage: { type: String, default: 'Keine Daten.' },
  isEditing:    { type: Boolean, default: false },
  badgeCount:   { type: Number, default: 0 },
  initialCollapsed: { type: Boolean, default: false },
})

const emit = defineEmits(['refresh', 'hide', 'collapse-change'])

/**
 * UX2g: Der Fehler wird ANGEZEIGT (er stand vorher als String-Prop bereit,
 * die Fläche zeigte aber immer „Fehler beim Laden"). Ein Fachsatz des Servers
 * bleibt stehen; eine leere/technische Meldung wird zum Katalogtext.
 */
const fehlerText = computed(() => fehlertext(props.error ? { message: props.error } : null))

const collapsed = ref(props.initialCollapsed)

/**
 * UX1d (D3): Der Zeitpunkt des letzten erfolgreichen Ladens, nur in der
 * Anzeige. Die Karte lädt selbst (ihre Seite ruft `laden()` beim Einbau und
 * nach jeder Änderung) — deshalb genügt es, den Wechsel von „lädt“ auf
 * „fertig“ mitzuschreiben. Kein Timer, keine zweite Uhr: der Text steht
 * still, bis wieder geladen wird.
 */
const stand = ref(null)
watch(
  () => props.loading,
  (laedt, vorher) => {
    if (vorher === true && laedt === false && !props.error) stand.value = new Date()
  },
  { immediate: true },
)
const standText = computed(() => {
  if (!stand.value) return ''
  const stunde = String(stand.value.getHours()).padStart(2, '0')
  const minute = String(stand.value.getMinutes()).padStart(2, '0')
  return `Stand ${stunde}:${minute}`
})

function toggleCollapse() {
  collapsed.value = !collapsed.value
  emit('collapse-change', collapsed.value)
}
</script>
