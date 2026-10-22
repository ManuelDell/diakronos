<template>
  <BaseWidgetCard label="Zu moderierende Termine" gridSize="medium" :loading="loading" :error="error" :isEmpty="isEmpty" emptyMessage="Alle Termine sind auf dem neuesten Stand." :isEditing @refresh="refresh" @hide="$emit('hide')" @collapse-change="$emit('collapse-change', $event)">
    <!-- BF1-G: Jeder Termin ist ein eigenes kleines Element (abgerundetes
         Rechteck) mit Titel, Datum/Uhrzeit und Ort/Gruppe — keine internen IDs.
         Uebersichtliche Vorschau: wenige Termine, Rest als „+N weitere“. -->
    <ul class="mod-termin-liste">
      <li
        v-for="(item, i) in vorschau"
        :key="item.schluessel"
        class="mod-termin"
        role="button"
        tabindex="0"
        @click="zurModeration"
        @keydown.enter.prevent="zurModeration"
        @keydown.space.prevent="zurModeration"
      >
        <span class="mod-termin-farbe" :style="{ background: farbe(item) }" aria-hidden="true"></span>
        <span class="mod-termin-inhalt">
          <span class="mod-termin-titel">{{ item.titel }}</span>
          <span class="mod-termin-meta">
            <span class="mod-termin-zeit">{{ item.zeit }}</span>
            <span v-if="item.ort" class="mod-termin-ort">{{ item.ort }}</span>
          </span>
        </span>
      </li>
    </ul>

    <button v-if="rest > 0" type="button" class="mod-termin-rest" @click="zurModeration">
      +{{ rest }} weitere
    </button>

    <button class="dk-btn" @click="zurModeration">→ Zur Terminmoderation</button>
  </BaseWidgetCard>
</template>
<script setup>
import BaseWidgetCard from './BaseWidgetCard.vue'
import { useWidgetData } from '../../composables/useWidgetData'
import { computed } from 'vue'
import { terminAnzeige } from '../../composables/bf1Anzeige.js'

const props = defineProps({ isEditing: Boolean, refreshInterval: { type: Number, default: 60 } })
const emit = defineEmits(['hide', 'collapse-change'])
const { data, loading, error, refresh } = useWidgetData('pending-registrations', props.refreshInterval)

const VORSCHAU_MAX = 5

function farbe(item) {
  // Farbe der Reihe nach aus den Marken-Tokens — ohne feste Farbwerte.
  const farben = ['var(--dk-gold-500)', 'var(--dk-navy-400)', 'var(--dk-green-600)', 'var(--dk-navy-300)']
  let h = 0
  for (const c of String(item.calendar || '')) h = (h + c.charCodeAt(0)) % farben.length
  return farben[h]
}

const alle = computed(() => (Array.isArray(data.value) ? data.value : []))
const vorschau = computed(() => alle.value.slice(0, VORSCHAU_MAX).map(terminAnzeige))
const rest = computed(() => Math.max(0, alle.value.length - VORSCHAU_MAX))
const isEmpty = computed(() => !data.value || (Array.isArray(data.value) && !data.value.length))

function zurModeration() {
  window.location.hash = '#/moderation'
}
</script>

<style scoped>
.mod-termin-liste {
  list-style: none;
  margin: 0 0 10px;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.mod-termin {
  display: flex;
  align-items: stretch;
  gap: 10px;
  padding: 8px 10px;
  background: var(--dk-surface-2, var(--surface-2));
  border: 1px solid var(--dk-border, var(--line));
  border-radius: 10px;
  cursor: pointer;
  transition: border-color var(--dk-fast, .15s), background var(--dk-fast, .15s);
}
.mod-termin:hover,
.mod-termin:focus-visible {
  border-color: var(--dk-border-strong, var(--line-strong));
  background: var(--dk-surface, var(--surface));
  outline: none;
}
.mod-termin-farbe {
  flex: none;
  width: 4px;
  border-radius: 999px;
}
.mod-termin-inhalt {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.mod-termin-titel {
  font-weight: 600;
  font-size: var(--fs-sm, 13px);
  color: var(--dk-text, var(--text));
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mod-termin-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 10px;
  font-size: var(--fs-xs, 11px);
  color: var(--dk-text-muted, var(--muted));
}
.mod-termin-ort::before {
  content: '· ';
}
.mod-termin-rest {
  width: 100%;
  margin-bottom: 10px;
  padding: 6px 10px;
  background: none;
  border: 1px dashed var(--dk-border, var(--line));
  border-radius: 8px;
  color: var(--dk-text-muted, var(--muted));
  font: inherit;
  font-size: var(--fs-xs, 11px);
  cursor: pointer;
}
.mod-termin-rest:hover { border-color: var(--dk-border-strong, var(--line-strong)); }
</style>
